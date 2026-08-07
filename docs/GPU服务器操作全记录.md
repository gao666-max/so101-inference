# GPU 云服务器操作全记录（SO101 ACT 模型训练）

## 平台信息
- 平台：Compshare 算力云
- GPU：NVIDIA GeForce RTX 4090（24GB 显存）
- CUDA：12.2
- Python：3.12.11
- 工作目录：/workspace/
- 访问方式：浏览器打开 JupyterLab → Terminal 终端操作

---

## 一、登录服务器

1. 浏览器打开 Compshare 控制台
2. 创建实例：RTX 4090，镜像选 PyTorch 2.5 + CUDA 12.1 + Python 3.10
3. 实例运行后，点击 JupyterLab 按钮进入
4. 点击 Terminal 图标打开终端
5. 所有操作都在 /workspace/ 目录下进行

## 二、环境检查

```bash
nvidia-smi                     # 确认 GPU 可用（RTX 4090, 24GB）
python3 --version              # 确认 Python 版本（3.12.11）
```

## 三、上传数据到服务器

### 3.1 在虚拟机上准备数据
```bash
# 数据集打包（在虚拟机里）
cd ~
tar -czf single_arm_dataset_63ep.tar.gz .cache/huggingface/lerobot/test/

# 大文件分片上传（单文件上传容易损坏，用分片）
split -b 50M single_arm_dataset_63ep.tar.gz single_arm_dataset_63ep.tar.gz.part_
cp single_arm_dataset_63ep.tar.gz.part_* /media/sf_Shared/
```

### 3.2 在 JupyterLab 上传
- 左侧文件列表进入 /workspace/ 目录
- 上传6个分片文件（part_aa ~ part_af）
- 同时上传 launch_train.py（训练启动脚本）

### 3.3 合并分片
```bash
cd /workspace
cat single_arm_dataset_63ep.tar.gz.part_* > single_arm_dataset_63ep.tar.gz
ls -lh single_arm_dataset_63ep.tar.gz  # 确认 296MB
```

## 四、部署训练环境

### 4.1 安装 LeRobot
```bash
pip install lerobot -i https://pypi.tuna.tsinghua.edu.cn/simple
```

注意：这一步会因为 pip 依赖解析尝试下载约 700MB 的 nvidia-cuda-* 包（服务器已有系统级 CUDA，不需要这些）。如果卡在下载 CUDA 包，按 Ctrl+C 终止，改用：

```bash
pip install lerobot --no-deps -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 4.2 安装依赖
```bash
pip install datasets accelerate wandb huggingface_hub pyav av -i https://pypi.tuna.tsinghua.edu.cn/simple
```

如果 pyav 装不上（清华源没有），用 `pip install pyav` 从官方源装。av 是 pyav 的替代品，LeRobot 支持两者。

### 4.3 确认 CUDA 版 PyTorch

pip install lerobot 可能会把 GPU 版 torch 替换为 CPU 版。验证并修复：

```bash
python3 -c "import torch; print('CUDA OK' if torch.cuda.is_available() else 'CUDA FAIL')"
```

如果输出 CUDA FAIL，重装 CUDA 版：

```bash
pip install torch torchvision torchaudio -i https://pypi.tuna.tsinghua.edu.cn/simple
```

清华源上的 torch 自带 CUDA 支持，不需要指定 --index-url。

## 五、打补丁

### 5.1 修复 av 库兼容性问题

LeRobot 新版源码引用了 `av.option.Option`，但当前 av 版本的 API 不同：

```bash
sed -i 's/av\.option\.Option/str/g' /usr/local/miniconda3/envs/py312/lib/python3.12/site-packages/lerobot/datasets/pyav_utils.py
```

确认全部替换成功：

```bash
grep "av\.option" /usr/local/miniconda3/envs/py312/lib/python3.12/site-packages/lerobot/datasets/pyav_utils.py
# 应该没有输出
```

### 5.2 修复 DEFAULT_FEATURES 缺失

```bash
cat > /usr/local/miniconda3/envs/py312/lib/python3.12/site-packages/lerobot/utils/default_features.py << 'EOF'
DEFAULT_FEATURES = {
    'timestamp': {'dtype': 'float32', 'shape': (1,), 'names': None},
    'frame_index': {'dtype': 'int64', 'shape': (1,), 'names': None},
    'episode_index': {'dtype': 'int64', 'shape': (1,), 'names': None},
    'index': {'dtype': 'int64', 'shape': (1,), 'names': None},
    'task_index': {'dtype': 'int64', 'shape': (1,), 'names': None},
}
EOF

echo -e "\nfrom .default_features import DEFAULT_FEATURES" >> /usr/local/miniconda3/envs/py312/lib/python3.12/site-packages/lerobot/utils/constants.py
```

## 六、解压数据集

```bash
cd /workspace
tar -xzf single_arm_dataset_63ep.tar.gz
ls .cache/huggingface/lerobot/test/ | wc -l  # 确认 27 个数据集

mkdir -p ~/.cache/huggingface/lerobot/
cp -r /workspace/.cache/huggingface/lerobot/test/ ~/.cache/huggingface/lerobot/test/
```

## 七、编写训练启动脚本

文件：`/workspace/launch_train.py`

```python
#!/usr/bin/env python3
"""SO101 单臂 ACT 多数据集联合训练"""
import os, subprocess, glob

datasets_root = os.path.expanduser("~/.cache/huggingface/lerobot/test")
all_dirs = sorted(glob.glob(f"{datasets_root}/*"))
dataset_list = [f"test/{os.path.basename(d)}" for d in all_dirs if os.path.isdir(d)]
print(f"找到 {len(dataset_list)} 个数据集")

dataset_args = []
for ds in dataset_list:
    dataset_args.extend(["--dataset.repo_id", ds])

cmd = [
    "python", "-m", "lerobot.scripts.lerobot_train",
    "--policy.type=act",
    "--policy.repo_id=local/so101_act_pick",
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
    "--policy.device=cuda",
] + dataset_args + [
    "--dataset.video_backend=pyav",
    "--dataset.use_imagenet_stats=true",
    "--batch_size=4",
    "--steps=50000",
    "--save_freq=5000",
    "--log_freq=100",
    "--output_dir=outputs/train/so101_act_pick",
    "--num_workers=4",
    "--seed=42",
]

env = os.environ.copy()
env["HF_HUB_OFFLINE"] = "1"
print(f"\n开始训练（{len(dataset_list)} 个数据集，50000 步，batch=4）...")
subprocess.run(cmd, env=env, check=True)
```

## 八、执行训练

```bash
cd /workspace
python launch_train.py
```

训练输出：
```
找到 27 个数据集
开始训练（27 个数据集，50000 步，batch=4）...
step=100: loss=12.717  grad_norm=260.95
step=200: loss=3.998   grad_norm=126.74
step=300: loss=3.229   grad_norm=105.13
step=50K:  loss=0.039   grad_norm=7.34
Training: 100% | 50000/50000 [46:49<00:00, 17.80step/s]
```

## 九、训练结果

| 指标 | 数值 |
|------|------|
| 总步数 | 50,000 |
| 总时长 | 46 分钟 |
| 平均步速 | 约 18 步/秒 |
| GPU 显存占用 | 约 1GB / 24GB |
| 初始 Loss | 12.717 |
| 最终 Loss | 0.039 |
| 模型参数 | 约 2900 万（29M） |
| 权重文件 | 110MB |

## 十、导出模型

```bash
cd /workspace
tar -czf so101_act_model.tar.gz -C outputs/train/so101_act_pick/checkpoints/050000/ .
ls -lh so101_act_model.tar.gz  # 301MB
```

退出时忽略训练末尾的 OfflineModeIsEnabled 错误——那是程序尝试上传 HuggingFace Hub 被 HF_HUB_OFFLINE=1 阻止了，模型已保存到本地。

## 十一、下载模型到本地

- JupyterLab 左侧右键 so101_act_model.tar.gz → Download → 保存到 E:\Shared\
- 虚拟机内解压：`tar -xzf /media/sf_Shared/so101_act_model.tar.gz -C ~/`
- 得到 `~/pretrained_model/` 目录（含 model.safetensors 等 7 个文件）

## 十二、踩坑记录

| 序号 | 问题 | 原因 | 解决 |
|------|------|------|------|
| 1 | pip 安装 lerobot 下 700MB CUDA 包 | 依赖解析拉取 nvidia-cuda-* 系列包 | Ctrl+C 终止，改用 --no-deps |
| 2 | pip 安装 lerobot 替换 torch 为 CPU 版 | lerobot 依赖解析 | 手动 pip install torch -i 清华源 |
| 3 | av.option.Option 属性不存在 | 新版 av 库 API 变更 | sed 替换为 str |
| 4 | 训练脚本参数不兼容 | 新版 LeRobot 参数体系不同 | 通过 --help 查看后逐一修正 |
| 5 | DEFAULT_FEATURES 缺失 | 源码漏定义 | 创建补丁文件 + import |
| 6 | 浏览器上传数据集损坏（380MB 变 60MB） | 大文件传输不稳定 | split 分片上传（50MB×6）+ cat 合并 |
| 7 | 训练结束报 OfflineModeIsEnabled | HF_HUB_OFFLINE=1 阻止上传 | 不影响训练结果，忽略 |

## 十三、关闭服务器

训练完成、模型下载后，在 Compshare 控制台**释放/销毁实例**，停止计费。如果只是关机（不释放），数据盘仍然按天收费（几毛钱/天）。
