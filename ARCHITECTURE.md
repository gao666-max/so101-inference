# 架构图 · SO101 机械臂 ACT 推理

## 整体闭环

```mermaid
flowchart LR
    subgraph TRAIN[训练阶段 - GPU]
        D[27个数据集<br/>63段遥操作] --> T[ACT 模型训练<br/>RTX 4090]
        T --> M[模型权重<br/>110MB, loss 0.039]
    end
    subgraph INFER[推理阶段 - CPU]
        C[USB摄像头] --> V[视觉编码<br/>ResNet18]
        V --> I[ACT 推理<br/>预测动作chunk]
        I --> S[串口控制<br/>从动臂]
    end
    M --> I
```

## 推理控制流程

```mermaid
flowchart TD
    A[摄像头采集帧] --> B[异步摄像头类<br/>async_camera.py]
    B --> C[视觉编码 ResNet18]
    C --> D[ACT 模型前向<br/>输出动作序列]
    D --> E[串口协议<br/>feetech-servo-sdk]
    E --> F[从动臂6舵机执行]
    F -->|下一帧| A
```

## 硬件链路

```mermaid
flowchart LR
    PC[CPU 推理<br/>i9-14900HX] -->|USB串口| L[领导臂 leader]
    PC -->|USB串口| F[从动臂 follower]
    PC -->|USB| CAM[单目摄像头]
    F -->|6舵机| ARM[从动臂动作]
```

## 关键架构决策

| 决策 | 原因 |
|------|------|
| 训练 GPU / 推理 CPU 分离 | 训练需要 RTX 4090 云端，推理只需 i9 本机实时 |
| 异步摄像头 | 摄像头帧率不阻塞推理主循环，`async_camera.py` 解耦 |
| 纯视觉推理与完整控制分离 | `inference.py` 不连机械臂可安全测试，`inference_control.py` 才接串口 |
| udev 固定端口 | 两个串口固定符号链接，避免重启后 ttyACM 编号漂移 |
| LeRobot 补丁 | 0.4.3 缺 DEFAULT_FEATURES 定义，源码补丁解决 |
