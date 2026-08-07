#!/usr/bin/env python3
"""SO101 单臂 ACT 多数据集联合训练"""
import os
import subprocess
import glob

# 自动扫描本地所有数据集
datasets_root = os.path.expanduser("~/.cache/huggingface/lerobot/test")
all_dirs = sorted(glob.glob(f"{datasets_root}/*"))
dataset_list = [f"test/{os.path.basename(d)}" for d in all_dirs if os.path.isdir(d)]

print(f"找到 {len(dataset_list)} 个数据集:")
for ds in dataset_list:
    print(f"  {ds}")

# 构建训练参数
dataset_args = []
for ds in dataset_list:
    dataset_args.extend(["--dataset.repo_id", ds])

cmd = [
    "python", "-m", "lerobot.scripts.lerobot_train",
    "--policy.type=act",
    "--policy.n_obs_steps=1",
    "--policy.chunk_size=50",
    "--policy.n_action_steps=50",
    "--policy.dim_model=256",
    "--policy.vision_backbone=resnet18",
    "--policy.pretrained_backbone_weights=ResNet18_Weights.IMAGENET1K_V1",
    "--policy.use_vae=true",
    "--policy.latent_dim=32",
    "--policy.input_features",
    '{"observation.images.front": {"type": "VISUAL", "shape": [3, 480, 640]}, "observation.state": {"type": "STATE", "shape": [6]}}',
    "--policy.output_features",
    '{"action": {"type": "ACTION", "shape": [6]}}',
] + dataset_args + [
    "--dataset.local_files_only=true",
    "--dataset.use_imagenet_stats=true",
    "--dataset.video_backend=pyav",
    "--batch_size=4",
    "--steps=50000",
    "--save_freq=5000",
    "--eval_freq=5000",
    "--log_freq=100",
    "--output_dir=outputs/train/so101_act_pick",
    "--device=cuda",
    "--num_workers=4",
    "--seed=42",
]

env = os.environ.copy()
env["HF_HUB_OFFLINE"] = "1"

print(f"\n开始训练（{len(dataset_list)} 个数据集，50000 步，batch=4）...")
subprocess.run(cmd, env=env, check=True)
