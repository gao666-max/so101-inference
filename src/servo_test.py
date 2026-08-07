"""
舵机测试 —— 验证从动臂硬件是否正常
用法: python3 ~/servo_test.py
"""
import scservo_sdk as scs
import time

PORT = "/dev/ttyACM0"
MOTORS = [1, 2, 3, 4, 5, 6]
NAMES = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]

ph = scs.PortHandler(PORT)
pk = scs.PacketHandler(0)
ph.openPort()
ph.setBaudRate(1000000)

print("=" * 50)
print("舵机测试")
print("=" * 50)

# 读当前位置 —— readTxRx 返回的 data 是字节列表 [低字节, 高字节]
def read_position(mid):
    data, comm, err = pk.readTxRx(ph, mid, 56, 2)
    if comm == scs.COMM_SUCCESS:
        return data[0] + (data[1] << 8)
    else:
        return -1

print("\n当前位置:")
orig_positions = {}
for mid in MOTORS:
    val = read_position(mid)
    orig_positions[mid] = val
    status = "OK" if val >= 0 else "FAIL"
    print(f"  ID {mid} ({NAMES[mid-1]:>15s}): {val}  [{status}]")

# 使能
print("\n使能舵机...")
for mid in MOTORS:
    pk.writeTxRx(ph, mid, 40, 1, [1])   # Torque_Enable
    pk.writeTxRx(ph, mid, 55, 1, [1])   # Lock
time.sleep(0.3)

# 逐个测试：小幅移动 +150 再回原位
for mid in MOTORS:
    orig = orig_positions[mid]
    if orig <= 0:
        print(f"  ID {mid} ({NAMES[mid-1]}): 跳过（位置无效）")
        continue

    target = min(orig + 150, 4095)
    print(f"\n测试 ID {mid} ({NAMES[mid-1]}): {orig} -> {target}")
    data = [scs.SCS_LOBYTE(target), scs.SCS_HIBYTE(target)]
    pk.writeTxRx(ph, mid, 42, 2, data)
    time.sleep(0.5)

    new_val = read_position(mid)
    moved = abs(new_val - target) < 100
    if moved:
        print(f"  当前位置: {new_val}  ✅ 动了")
    elif new_val == orig:
        print(f"  当前位置: {new_val}  ❌ 没动")
    else:
        print(f"  当前位置: {new_val}  ⚠️  在动但没到位")

    # 回原位
    data = [scs.SCS_LOBYTE(orig), scs.SCS_HIBYTE(orig)]
    pk.writeTxRx(ph, mid, 42, 2, data)
    time.sleep(0.3)

# 关扭矩
print("\n关闭扭矩...")
for mid in MOTORS:
    pk.writeTxRx(ph, mid, 40, 1, [0])
ph.closePort()
print("测试完成")
