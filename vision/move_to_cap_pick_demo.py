"""
move_to_cap_pick_demo.py —— 执行视觉抓取
==========================================
读取 cap_above_grasp_target.json 中的目标关节角度，
控制从动臂执行抓取序列：
  1. 打开夹爪
  2. 移动到 above 位置（线性插值）
  3. 等待人工确认
  4. 下降到 grasp 位置
  5. 等待人工确认
  6. 闭合夹爪
  7. 等待人工确认
  8. 抬回 above 位置

为安全起见，每一步之间保留人工确认（按 Enter 继续）。

用法:
    python move_to_cap_pick_demo.py
"""

import json
import time
import numpy as np


class ServoController:
    """通过 scservo_sdk 控制从动臂舵机。"""

    JOINT_NAMES = ["shoulder_pan", "shoulder_lift", "elbow_flex",
                   "wrist_flex", "wrist_roll", "gripper"]
    MOTOR_IDS = [1, 2, 3, 4, 5, 6]

    # 安全速度（越小越慢，1-1023）
    SAFE_SPEED = 300

    def __init__(self, port, baudrate=1000000):
        self.port = port
        self.baudrate = baudrate
        self.connected = False
        try:
            import scservo_sdk as scs
            self.scs = scs
            self.ph = scs.PortHandler(port)
            self.pk = scs.PacketHandler(0)
            if self.ph.openPort() and self.ph.setBaudRate(baudrate):
                self.connected = True
                print(f"[ServoController] 已连接 {port}")
            else:
                print(f"[ServoController] 连接失败 {port}")
        except Exception as e:
            print(f"[ServoController] 初始化失败: {e}")

    def read_current_joints(self):
        """读取当前关节角度。"""
        joints = {}
        for motor_id, name in zip(self.MOTOR_IDS, self.JOINT_NAMES):
            try:
                pos, comm, err = self.pk.readTxRx(self.ph, motor_id,
                                                  self.scs.SCS_PRESENT_POSITION_L, 2)
                if comm == self.scs.COMM_SUCCESS:
                    joints[name] = pos
                else:
                    joints[name] = 2048
            except:
                joints[name] = 2048
        return joints

    def write_joint(self, name, target_position, speed=None):
        """写入单个舵机目标位置。"""
        if name not in self.JOINT_NAMES:
            return
        idx = self.JOINT_NAMES.index(name)
        motor_id = self.MOTOR_IDS[idx]
        spd = speed if speed is not None else self.SAFE_SPEED

        if self.connected:
            try:
                # 写目标位置
                self.pk.writeTxRx(self.ph, motor_id, int(target_position), 0, spd, 0)
            except Exception as e:
                print(f"  [WARN] 写入 {name} (id={motor_id}) 失败: {e}")
        else:
            print(f"  [模拟] 写入 {name} → {int(target_position)}")

    def write_joints_smooth(self, target_joints, steps=30, delay=0.03):
        """
        从当前关节角度平滑移动到目标角度（线性插值）。

        steps:  插值步数
        delay:  每步间隔（秒）
        """
        current = self.read_current_joints()
        print(f"  当前: {dict((k, v) for k, v in current.items())}")
        print(f"  目标: {dict((k, int(v)) for k, v in target_joints.items())}")
        print(f"  插值: {steps} 步, 每步 {delay}s, 总时长约 {steps * delay:.1f}s")

        for step in range(1, steps + 1):
            t = step / steps  # 0 → 1
            for name in self.JOINT_NAMES:
                start = current[name]
                end = target_joints.get(name, start)
                val = start + (end - start) * t
                self.write_joint(name, val)
            time.sleep(delay)

    def enable_torque(self, enable=True):
        """使能/关闭所有舵机扭矩。"""
        if not self.connected:
            return
        for motor_id in self.MOTOR_IDS:
            try:
                self.pk.writeTxRx(self.ph, motor_id, 1 if enable else 0,
                                  0, self.scs.SCS_TORQUE_ENABLE, 0, 0)
            except:
                pass

    def close(self):
        if self.ph:
            self.ph.closePort()


def main():
    print("=" * 60)
    print("视觉抓取执行 —— Move to Cap Pick Demo")
    print("=" * 60)

    TARGET_PATH = "output/cap_above_grasp_target.json"
    FOLLOWER_PORT = "/dev/so101_follower_single"

    # ---- 加载目标 ----
    try:
        with open(TARGET_PATH, "r") as f:
            target = json.load(f)
    except FileNotFoundError:
        print(f"\n[ERROR] 目标文件不存在: {TARGET_PATH}")
        print("请先运行 cap_to_above_grasp_target.py")
        return

    print(f"\n目标信息:")
    print(f"  像素: ({target['cap_pixel']['u']}, {target['cap_pixel']['v']})")
    print(f"  纸面: ({target['paper_xy_mm']['x']}, {target['paper_xy_mm']['y']}) mm")
    print(f"  above: {dict((k, int(v)) for k, v in target['above_joints'].items())}")
    print(f"  grasp: {dict((k, int(v)) for k, v in target['grasp_joints'].items())}")

    # ---- 连接从动臂 ----
    servo = ServoController(FOLLOWER_PORT)
    if not servo.connected:
        print("\n[WARN] 串口未连接，将模拟执行。")

    print("\n" + "=" * 60)
    print("抓取序列")
    print("=" * 60)
    print("每步之间需要按 Enter 确认，输入 'q' 退出。")
    print()

    try:
        # ---- Step 1: 打开夹爪 ----
        input(f"[Step 1/6] 打开夹爪 —— 按 Enter 执行 ")
        print("  执行：打开夹爪...")
        servo.write_joint("gripper", 3000, speed=500)
        time.sleep(0.5)
        print("  [OK]")

        # ---- Step 2: 移到 above ----
        input(f"\n[Step 2/6] 移动到 above 位置 —— 按 Enter 执行 ")
        servo.write_joints_smooth(target["above_joints"], steps=50, delay=0.03)
        print("  [OK]")

        # ---- Step 3: 确认 ----
        cmd = input(f"\n[Step 3/6] 确认从动臂在瓶盖正上方，可以下降？(Enter/q) ")
        if cmd.lower() == 'q':
            return

        # ---- Step 4: 降到 grasp ----
        input(f"\n[Step 4/6] 下降到 grasp 位置 —— 按 Enter 执行 ")
        servo.write_joints_smooth(target["grasp_joints"], steps=30, delay=0.03)
        print("  [OK]")

        # ---- Step 5: 确认闭合 ----
        cmd = input(f"\n[Step 5/6] 确认夹爪在瓶盖两侧，闭合夹爪？(Enter/q) ")
        if cmd.lower() == 'q':
            return

        # 闭合夹爪
        input(f"  按 Enter 闭合夹爪 ")
        print("  执行：闭合夹爪...")
        servo.write_joint("gripper", 2048, speed=500)
        time.sleep(0.5)
        print("  [OK]")

        # ---- Step 6: 抬起 ----
        cmd = input(f"\n[Step 6/6] 抬起到 above 位置？(Enter/q) ")
        if cmd.lower() == 'q':
            return

        servo.write_joints_smooth(target["above_joints"], steps=40, delay=0.03)
        print("  [OK]")

        print("\n" + "=" * 60)
        print("[DONE] 抓取序列执行完毕！")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n用户中断。")

    finally:
        servo.close()
        print("退出。")


if __name__ == "__main__":
    main()
