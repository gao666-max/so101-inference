# HANDOFF.md — SO101 机械臂 ACT 推理

> AI 接管指引：接手后先读本文件，再读 `ARCHITECTURE.md`，最后读 `README.md`。

## 一句话

SO101 单臂机械臂端到端具身智能项目。ACT 模型从数据采集、GPU训练到CPU推理+串口控制从动臂的完整闭环。

## 启动

```bash
conda activate robot_arm
cd src/
python inference.py           # 纯视觉推理，安全，不连机械臂
python inference_control.py   # 完整推理控制，需连接从动臂+摄像头
python servo_test.py          # 舵机诊断
```

环境：VirtualBox Ubuntu 22.04 + conda robot_arm (Python 3.10.12)。

## 目录结构

| 路径 | 职责 |
|------|------|
| `src/inference.py` | 纯视觉推理（不连机械臂） |
| `src/inference_control.py` | 完整推理控制（摄像头+模型+串口+从动臂） |
| `src/servo_test.py` | 舵机硬件诊断 |
| `src/async_camera.py` | 异步摄像头类 |
| `src/launch_train.py` | GPU训练启动脚本 |
| `scripts/` | 遥操作/数据采集一键脚本 |
| `vision/` | 视觉系统（摄像头/颜色识别/标定） |
| `docs/` | 20个踩坑记录 + 学习资料 |
| `config/` | udev 固定端口规则 |

## 关键环境

| 项 | 值 |
|----|-----|
| 串口符号链接 | `/dev/so101_leader_single` 和 `/dev/so101_follower_single` |
| LeRobot 补丁 | 0.4.3 缺 DEFAULT_FEATURES，需源码补丁 |
| 模型权重 | ACT 2900万参数 110MB |

## 踩过的坑

见 `docs/20个踩坑记录.md`，最关键几条：
1. LeRobot 0.4.3 constants.py 缺 DEFAULT_FEATURES 定义，需要补丁文件
2. PyTorch 版本必须精确锁定 2.7.1+cpu，否则 torchvision 冲突
3. 串口是 /dev/ttyACM* 不是 /dev/ttyUSB*
4. 共享文件夹自动挂载路径是 /media/sf_Shared 不是 /mnt

## 用户信息

- 用户叫佳慧（高佳慧），软件工程大三，天津
- 机械臂项目已完成，8月7日最后一次推理测试通过
- 沟通：直接、口语化、单行命令、中文交流
