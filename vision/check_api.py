import scservo_sdk as scs
import inspect

# 1. PacketHandler 是函数还是类？
print("PacketHandler type:", type(scs.PacketHandler))
print("PortHandler type:", type(scs.PortHandler))
print()

# 2. 创建实例看方法
ph = scs.PortHandler("/dev/so101_follower_single")
pk = scs.PacketHandler(0)

# print all public methods
for name in sorted(dir(pk)):
    if not name.startswith('_') and 'write' in name.lower() or 'read' in name.lower() or 'tx' in name.lower() or 'rx' in name.lower():
        try:
            sig = inspect.signature(getattr(pk, name))
            print(f"PacketHandler.{name}{sig}")
        except:
            pass

print()
for name in sorted(dir(ph)):
    if not name.startswith('_') and ('open' in name.lower() or 'baud' in name.lower() or 'close' in name.lower() or 'write' in name.lower() or 'read' in name.lower()):
        try:
            sig = inspect.signature(getattr(ph, name))
            print(f"PortHandler.{name}{sig}")
        except:
            pass

print()
print("SCS_PRESENT_POSITION_L:", scs.SCS_PRESENT_POSITION_L)
print("COMM_SUCCESS:", scs.COMM_SUCCESS)
print("SCS_LOBYTE:", scs.SCS_LOBYTE)
print("SCS_HIBYTE:", scs.SCS_HIBYTE)

print()
for attr in sorted(dir(scs)):
    if 'ADDR' in attr.upper() or 'TORQUE' in attr.upper() or 'SPEED' in attr.upper() or 'GOAL' in attr.upper() or 'LOCK' in attr.upper() or 'POSITION' in attr.upper():
        print(f"  {attr}: {getattr(scs, attr, 'N/A')}")
