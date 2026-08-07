"""
teleop_collect_above_grasp_points.py —— 遥操作示教采集（一体化版）
=================================================================
一个程序同时做两件事：
  A. 后台循环读领导臂 → 实时驱动从动臂（遥操作）
  B. 按 Enter 时记录从动臂当前 6 个关节角度

用法:
    python teleop_collect_above_grasp_points.py

输出:
    output/plane_above_grasp_joint_points.json
"""

import json
import os
import time
import threading

JOINT_NAMES = ["shoulder_pan", "shoulder_lift", "elbow_flex",
               "wrist_flex", "wrist_roll", "gripper"]
MOTOR_IDS = [1, 2, 3, 4, 5, 6]

# ============================================================
# 串口操作
# ============================================================
def open_bus(port, baudrate=1000000):
    """打开串口总线，返回 (PortHandler, PacketHandler)。"""
    import scservo_sdk as scs
    ph = scs.PortHandler(port)
    pk = scs.PacketHandler(0)
    if not ph.openPort():
        raise RuntimeError(f"无法打开串口: {port}")
    if not ph.setBaudRate(baudrate):
        raise RuntimeError(f"无法设置波特率: {port}")
    return scs, ph, pk


def enable_torque(scs, ph, pk, enable=True):
    """使能/关闭所有舵机扭矩。"""
    for mid in MOTOR_IDS:
        try:
            pk.writeTxRx(ph, mid, 1 if enable else 0, 0, scs.SCS_TORQUE_ENABLE, 0, 0)
        except Exception:
            pass


def sync_read_joints(scs, ph, pk):
    """同步读取 6 个舵机位置。"""
    joints = {}
    for mid, name in zip(MOTOR_IDS, JOINT_NAMES):
        try:
            pos, comm, err = pk.readTxRx(ph, mid, scs.SCS_PRESENT_POSITION_L, 2)
            if comm == scs.COMM_SUCCESS:
                joints[name] = pos
            else:
                joints[name] = 2048
        except Exception:
            joints[name] = 2048
    return joints


def sync_write_joints(scs, ph, pk, target_joints, speed=300):
    """同步写入 6 个舵机位置。"""
    for mid, name in zip(MOTOR_IDS, JOINT_NAMES):
        val = target_joints.get(name, 2048)
        try:
            pk.writeTxRx(ph, mid, int(val), 0, speed, 0)
        except Exception:
            pass


# ============================================================
# 遥操作线程（后台）
# ============================================================
class TeleopThread:
    """后台线程：持续读领导臂 → 写从动臂，实现遥操作。"""

    def __init__(self, leader_port, follower_port):
        self.leader_port = leader_port
        self.follower_port = follower_port
        self._running = False
        self._thread = None
        self.error = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _loop(self):
        """只读领导臂，不写从动臂（我们改用单独写从动臂的方式）。"""
        pass


# ============================================================
# 一体化遥操作 + 记录
# ============================================================
def main():
    print("=" * 60)
    print("遥操作示教采集 —— 一体化版")
    print("=" * 60)

    LEADER_PORT = "/dev/so101_leader_single"
    FOLLOWER_PORT = "/dev/so101_follower_single"
    PAPER_W = 180
    PAPER_H = 100

    CORNERS = {
        "A": f"左上 (0, 0) mm",
        "B": f"右上 ({PAPER_W}, 0) mm",
        "C": f"右下 ({PAPER_W}, {PAPER_H}) mm",
        "D": f"左下 (0, {PAPER_H}) mm",
    }
    POSES = ["above", "grasp"]

    print(f"\n领导臂: {LEADER_PORT}")
    print(f"从动臂: {FOLLOWER_PORT}")
    print(f"纸面: {PAPER_W} x {PAPER_H} mm")
    print()
    print("工作方式：")
    print("  1. 程序后台持续读领导臂 → 驱动从动臂")
    print("  2. 你用手扳领导臂，从动臂跟着动")
    print("  3. 到位后按 ENTER 记录当前从动臂角度")
    print()
    print("采集顺序: A-above → A-grasp → B-above → ... → D-grasp (共 8 点)")
    print("在任何提示下输入 'r' 重试上一个点, 'q' 退出")
    print("-" * 40)

    # ---- 打开两个串口 ----
    try:
        scs, leader_ph, leader_pk = open_bus(LEADER_PORT)
        _, follower_ph, follower_pk = open_bus(FOLLOWER_PORT)
    except RuntimeError as e:
        print(f"\n[ERROR] {e}")
        print("请检查：机械臂电源是否开启、VirtualBox USB 是否勾选。")
        return

    # ---- 使能从动臂扭矩 ----
    print("\n初始化从动臂...")
    enable_torque(scs, follower_ph, follower_pk, True)
    print("[OK] 从动臂已使能，准备遥操作。")

    result = {
        "paper_width_mm": PAPER_W,
        "paper_height_mm": PAPER_H,
        "description": "四角 above/grasp 示教关节角度",
    }
    os.makedirs("output", exist_ok=True)

    # ---- 主循环：边遥操作边记录 ----
    teleop_running = True

    def teleop_loop():
        """后台遥操作循环：读领导臂 → 写从动臂。"""
        while teleop_running:
            try:
                leader_joints = sync_read_joints(scs, leader_ph, leader_pk)
                sync_write_joints(scs, follower_ph, follower_pk, leader_joints, speed=500)
            except Exception:
                pass
            time.sleep(0.02)  # ~50Hz

    teleop_thread = threading.Thread(target=teleop_loop, daemon=True)
    teleop_thread.start()
    print("[Teleop] 遥操作已启动 —— 扳领导臂，从动臂跟随。")

    try:
        for corner_name, corner_desc in CORNERS.items():
            for pose in POSES:
                print(f"\n{'=' * 50}")
                print(f"  >>> {corner_name} ({corner_desc}) —— {pose} <<<")
                if pose == "above":
                    print(f"  要求：夹爪打开，从动臂悬停在纸面上方")
                else:
                    print(f"  要求：从动臂下降到实际夹取位置")
                print(f"{'=' * 50}")
                print(f"  扳领导臂遥控从动臂到位后，按 ENTER 记录...")

                while True:
                    cmd = input("  >>> ").strip().lower()
                    if cmd == 'q':
                        print("用户退出。")
                        return
                    elif cmd == 'r':
                        break  # 重试
                    elif cmd == '':
                        # 暂停遥操作瞬间 → 读从动臂当前角度
                        joints = sync_read_joints(scs, follower_ph, follower_pk)
                        if corner_name not in result:
                            result[corner_name] = {}
                        result[corner_name][pose] = joints
                        print(f"  [OK] {corner_name}-{pose} 已记录:")
                        for name, val in joints.items():
                            print(f"    {name}: {val}")
                        break
                    else:
                        print("  按 ENTER 记录, 'r' 重试, 'q' 退出")

    finally:
        teleop_running = False
        teleop_thread.join(timeout=2.0)

        # 关闭从动臂扭矩
        enable_torque(scs, follower_ph, follower_pk, False)
        leader_ph.closePort()
        follower_ph.closePort()

    # ---- 保存 ----
    output_path = "output/plane_above_grasp_joint_points.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n{'=' * 60}")
    print(f"[DONE] 示教数据已保存: {output_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
