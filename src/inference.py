"""
SO101 ACT 推理脚本 —— 摄像头画面 → 模型 → 舵机指令 → 从动臂自主抓取
用法: python3 ~/inference.py
"""
import cv2
import torch
import numpy as np
import time
from safetensors import safe_open

# ===== 1. 加载模型权重 =====
print("[1/4] 加载模型权重...")
state_dict = {}
with safe_open("pretrained_model/model.safetensors", framework="pt", device="cpu") as f:
    for key in f.keys():
        state_dict[key] = f.get_tensor(key)
print(f"  已加载 {len(state_dict)} 个参数")

# ===== 2. 构建 ACT 模型（手动设置配置）=====
print("[2/4] 构建模型...")
from lerobot.policies.act.configuration_act import ACTConfig
from lerobot.policies.act.modeling_act import ACTPolicy
from lerobot.configs.types import PolicyFeature, FeatureType

config = ACTConfig(
    n_obs_steps=1,
    chunk_size=50,
    n_action_steps=50,
    input_features={
        "observation.images.front": PolicyFeature(type=FeatureType.VISUAL, shape=(3, 480, 640)),
        "observation.state": PolicyFeature(type=FeatureType.STATE, shape=(6,)),
    },
    output_features={
        "action": PolicyFeature(type=FeatureType.ACTION, shape=(6,)),
    },
    vision_backbone="resnet18",
    pretrained_backbone_weights=None,
    dim_model=256,
    n_heads=8,
    dim_feedforward=3200,
    n_encoder_layers=4,
    n_decoder_layers=1,
    use_vae=True,
    latent_dim=32,
    dropout=0.1,
    kl_weight=10.0,
)

model = ACTPolicy(config)
model.load_state_dict(state_dict, strict=False)
model.eval()
print(f"  模型构建成功，参数数: {sum(p.numel() for p in model.parameters()):,}")

# ===== 3. 加载前/后处理器 =====
print("[3/4] 加载处理器...")
import json
with open("pretrained_model/policy_preprocessor.json") as f:
    pre_cfg = json.load(f)
with open("pretrained_model/policy_postprocessor.json") as f:
    post_cfg = json.load(f)

# 加载预处理器权重（归一化参数）
pre_state = {}
with safe_open("pretrained_model/policy_preprocessor_step_3_normalizer_processor.safetensors", framework="pt") as f:
    for k in f.keys():
        pre_state[k] = f.get_tensor(k)

post_state = {}
with safe_open("pretrained_model/policy_postprocessor_step_0_unnormalizer_processor.safetensors", framework="pt") as f:
    for k in f.keys():
        post_state[k] = f.get_tensor(k)

# 图像归一化 (ImageNet stats)
IMG_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
IMG_STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)

# state 归一化（从预处理器权重中读取）
state_mean = pre_state["observation.state.mean"]
state_std = pre_state["observation.state.std"]
# action 反归一化（从后处理器权重中读取）
action_mean = post_state["action.mean"]
action_std = post_state["action.std"]

print(f"  state mean: {state_mean.numpy().round(1)}")
print(f"  state std: {state_std.numpy().round(1)}")
print(f"  action mean: {action_mean.numpy().round(1)}")
print(f"  action std: {action_std.numpy().round(1)}")

# ===== 4. 推理循环 =====
print("[4/4] 启动推理...")
print("  按 'q' 退出")
print("-" * 40)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 30)

# 初始关节位置（中间值）
current_joints = torch.tensor([2048.0] * 6)
action_buffer = []

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue

        # ---- 预处理图像 ----
        img = cv2.resize(frame, (640, 480))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = torch.from_numpy(img).permute(2, 0, 1).float() / 255.0
        img = (img - IMG_MEAN.squeeze(0)) / IMG_STD.squeeze(0)
        img = img.unsqueeze(0)  # [1, 3, 480, 640]

        # ---- 预处理状态 ----
        state = (current_joints - state_mean) / (state_std + 1e-8)
        state = state.unsqueeze(0)  # [1, 6]

        # ---- 模型推理 ----
        with torch.no_grad():
            raw_action = model.select_action({
                "observation.images.front": img,
                "observation.state": state,
            })

        # select_action 输出归一化值，手动反归一化
        action = raw_action[0] * action_std + action_mean

        # ---- 缓冲区平滑 ----
        action_buffer.append(action)
        if len(action_buffer) > 5:
            action_buffer.pop(0)
        smoothed_action = torch.stack(action_buffer).mean(dim=0)
        current_joints = smoothed_action

        # ---- 显示 ----
        display = frame.copy()
        cv2.putText(display, "INFERENCE MODE", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        for i, (name, val) in enumerate(zip(
            ["pan", "lift", "elbow", "wrist_flex", "wrist_roll", "gripper"],
            current_joints.int().tolist()
        )):
            cv2.putText(display, f"{name}: {val}", (10, 60 + i * 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        cv2.imshow("Inference", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
    print("退出。")
