"""
SO101 ACT 推理控制 —— 实时可调放大倍数版
用法: python3 ~/inference_control.py
按键: q=退出, = =放大动作, -=缩小动作
"""
import cv2, torch, numpy as np, time, sys
from safetensors import safe_open
sys.path.insert(0, "/home/gao/lerobot/src")
from lerobot.policies.act.configuration_act import ACTConfig
from lerobot.policies.act.modeling_act import ACTPolicy
from lerobot.configs.types import PolicyFeature, FeatureType
import scservo_sdk as scs

print("=" * 60)
print("SO101 ACT 推理控制 (可调放大)")
print("=" * 60)

# ===== 1. 加载模型 =====
print("[1/4] 加载模型...")
state_dict = {}
with safe_open("pretrained_model/model.safetensors", framework="pt", device="cpu") as f:
    for k in f.keys():
        state_dict[k] = f.get_tensor(k)
config = ACTConfig(
    n_obs_steps=1, chunk_size=50, n_action_steps=50,
    input_features={
        "observation.images.front": PolicyFeature(type=FeatureType.VISUAL, shape=(3, 480, 640)),
        "observation.state": PolicyFeature(type=FeatureType.STATE, shape=(6,)),
    },
    output_features={"action": PolicyFeature(type=FeatureType.ACTION, shape=(6,))},
    vision_backbone="resnet18", pretrained_backbone_weights=None,
    dim_model=256, n_heads=8, dim_feedforward=3200,
    n_encoder_layers=4, n_decoder_layers=1,
    use_vae=True, latent_dim=32, dropout=0.1, kl_weight=10.0,
)
model = ACTPolicy(config)
model.load_state_dict(state_dict, strict=False)
model.eval()

# ===== 2. 归一化参数 =====
print("[2/4] 加载归一化参数...")
pre_state = {}
with safe_open("pretrained_model/policy_preprocessor_step_3_normalizer_processor.safetensors", framework="pt") as f:
    for k in f.keys():
        pre_state[k] = f.get_tensor(k)
post_state = {}
with safe_open("pretrained_model/policy_postprocessor_step_0_unnormalizer_processor.safetensors", framework="pt") as f:
    for k in f.keys():
        post_state[k] = f.get_tensor(k)

IMG_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
IMG_STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
state_mean = pre_state["observation.state.mean"]
state_std = pre_state["observation.state.std"]
action_mean = post_state["action.mean"]
action_std = post_state["action.std"]
HOMING = torch.tensor([-1033.0, 836.0, 846.0, 1065.0, -1685.0, 2036.0])

# ===== 3. 串口 =====
print("[3/4] 连接从动臂...")
PORT = "/dev/ttyACM0"
ph = scs.PortHandler(PORT)
pk = scs.PacketHandler(0)
ph.openPort()
ph.setBaudRate(1000000)
for mid in [1, 2, 3, 4, 5, 6]:
    pk.writeTxRx(ph, mid, 40, 1, [1])
    pk.writeTxRx(ph, mid, 55, 1, [1])
time.sleep(0.5)
print(f"  已连接 {PORT}")

def read_raw():
    """读取6个关节，返回整型值列表"""
    j = []
    for mid in [1, 2, 3, 4, 5, 6]:
        data, comm, err = pk.readTxRx(ph, mid, 56, 2)
        if comm == scs.COMM_SUCCESS:
            val = data[0] + (data[1] << 8)
        else:
            val = 2048
        j.append(val)
    return j

def write_joints(positions):
    for mid, pos in zip([1, 2, 3, 4, 5, 6], positions):
        val = int(pos)
        data = [scs.SCS_LOBYTE(val), scs.SCS_HIBYTE(val)]
        pk.writeTxRx(ph, mid, 42, 2, data)

start_raw = torch.tensor(read_raw(), dtype=torch.float32)
print(f"  初始臂位(归零): {(start_raw - HOMING).int().tolist()}")

# ===== 4. 推理 =====
print("[4/4] 开始推理...")
print("  按 q 退出, 按 +/= 放大动作, 按 - 缩小动作")
print("-" * 40)

cap = cv2.VideoCapture(2)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
time.sleep(0.5)

SCALE = 1.0
MAX_DELTA = 50   # 每步最多移动50个舵机单位，防止暴冲
action_buffer = []
names = ["pan", "lift", "elbow", "w_flex", "w_roll", "grip"]

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue

        img = cv2.resize(frame, (640, 480))
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_tensor = torch.from_numpy(img_rgb).permute(2, 0, 1).float() / 255.0
        img_tensor = (img_tensor - IMG_MEAN.squeeze(0)) / IMG_STD.squeeze(0)
        img_tensor = img_tensor.unsqueeze(0)

        cur_raw = torch.tensor(read_raw(), dtype=torch.float32)
        cur_centered = cur_raw - HOMING
        cur_norm = (cur_centered - state_mean) / (state_std + 1e-8)

        with torch.no_grad():
            raw_action = model.select_action({
                "observation.images.front": img_tensor,
                "observation.state": cur_norm.unsqueeze(0),
            })

        action_centered = raw_action[0] * action_std + action_mean
        delta = action_centered - cur_centered
        # 安全钳制：每步最多移动 MAX_DELTA 个单位
        delta = torch.clamp(delta, -MAX_DELTA, MAX_DELTA)
        target_centered = cur_centered + delta * SCALE
        target_raw = torch.clamp(target_centered + HOMING, 0, 4095)

        action_buffer.append(target_raw)
        if len(action_buffer) > 5:
            action_buffer.pop(0)
        smoothed = torch.stack(action_buffer).mean(dim=0)
        write_joints(smoothed.int().tolist())

        display = frame.copy()
        cv2.putText(display, f"AUTO SCALE:{SCALE:.1f} MAX_DELTA:{MAX_DELTA}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        for i, (n, v, d, c) in enumerate(zip(names, smoothed.int().tolist(), delta.int().tolist(), cur_raw.int().tolist())):
            sign = ">" if d > 0 else "<" if d < 0 else "="
            cv2.putText(display, f"{n}:{v} ({sign}{abs(d)})", (10, 60 + i * 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        cv2.imshow("Auto Control", display)

        k = cv2.waitKey(1) & 0xFF
        if k == ord("q"):
            break
        elif k in (ord("="), ord("+")):
            SCALE = min(SCALE + 0.5, 5.0)
            print(f"  SCALE = {SCALE}")
        elif k == ord("-"):
            SCALE = max(SCALE - 0.5, 0.5)
            print(f"  SCALE = {SCALE}")

except KeyboardInterrupt:
    print("\n中断")

finally:
    print("关闭扭矩...")
    for mid in [1, 2, 3, 4, 5, 6]:
        pk.writeTxRx(ph, mid, 40, 1, [0])
    ph.closePort()
    cap.release()
    cv2.destroyAllWindows()
    print("退出")
