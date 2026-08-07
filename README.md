# SO101 单臂机械臂 ACT 模型推理控制

端到端具身智能项目 —— 从数据采集、GPU训练、到CPU推理+串口控制从动臂的完整闭环。

## 项目概述

- 硬件：SO101 主从机械臂（单臂，6个舵机）+ USB单目摄像头
- 环境：VirtualBox Ubuntu 22.04 + conda robot_arm (Python 3.10.12)
- 模型：ACT (Action Chunking Transformer)，2900万参数，110MB权重
- 训练：RTX 4090 云GPU，27个数据集（63段），50K步，loss 12.7→0.039
- 推理：CPU实时推理，摄像头→模型→串口→从动臂

## 目录结构

```
├── src/                    # 核心推理代码
│   ├── inference.py         # 纯视觉推理（不连从动臂，安全测试）
│   ├── inference_control.py # 完整推理控制（摄像头+模型+串口+从动臂）
│   ├── servo_test.py        # 舵机硬件诊断工具
│   ├── async_camera.py      # 5.1.2 异步摄像头类
│   └── launch_train.py      # GPU服务器训练启动脚本
├── scripts/                 # 辅助脚本
│   ├── start_teleop.sh      # 一键遥操作
│   └── start_record.sh      # 一键数据采集
├── vision/                  # 第5章 视觉系统
│   ├── camera.py            # 摄像头封装
│   ├── color_detector.py    # HSV颜色识别
│   ├── plane_calibrator.py  # 纸面四角标定
│   └── ...
├── docs/                    # 学习资料
│   ├── 20个踩坑记录.md
│   ├── ROS2核心概念.md
│   ├── GPU服务器操作全记录.md
│   └── 学习路线_项目改造计划.md
└── config/
    └── 99-so101-arms.rules   # udev固定端口规则示例
```

## 环境要求

- conda 26.3.2+
- Python 3.10.12
- LeRobot 0.4.3（源码安装，含 DEFAULT_FEATURES 补丁）
- PyTorch 2.7.1+cpu
- feetech-servo-sdk 1.0.0
- OpenCV 4.12.0

## 快速开始

```bash
# 1. 激活环境
conda activate robot_arm
cd src/

# 2. 纯视觉推理（安全，不连机械臂）
python inference.py

# 3. 完整推理控制（需连接从动臂+摄像头）
python inference_control.py
# 按键: = 放大动作, - 缩小动作, q 退出

# 4. 舵机测试（诊断硬件）
python servo_test.py
```

## 操作视频


## 关键踩坑记录（20条）

见 `docs/20个踩坑记录.md` —— 每个坑都标注了根因和学到的知识。

## 训练参数

| 参数 | 值 |
|------|-----|
| 模型 | ACT (Action Chunking Transformer) |
| 视觉骨干 | ResNet18 (ImageNet预训练) |
| chunk_size | 50 |
| dim_model | 256 |
| use_vae | true |
| batch_size | 4 |
| 训练步数 | 50,000 |
| 优化器 | AdamW, lr=1e-5 |
| 最终loss | 0.039 |
| 训练时长 | 46分钟 |
| GPU | RTX 4090 24GB (Compshare) |

## 许可证

MIT
