# ROS2 核心概念：Topic / Service / Action

## 先用一句话说清楚

| 概念 | 一句话 | 类比 |
|------|--------|------|
| **Topic（话题）** | 一直发、谁爱听谁听 | 广播电台 |
| **Service（服务）** | 问一次、答一次、完了 | 打电话 |
| **Action（动作）** | 你发目标、它汇报进度、取消随时可以 | 外卖 APP |

---

## Topic（话题）—— "广播"

```
发布者（Publisher）                        订阅者（Subscriber）
   │                                           │
   ├─ msg1 ──────────────────────────────→ 收到msg1
   ├─ msg2 ──────────────────────────────→ 收到msg2
   ├─ msg3 ──────────────────────────────→ 收到msg3
   ...

特点：
- 单向：发布者不管有没有人听，只管发
- 持续：一直在发（比如每 0.1 秒发一次关节角度）
- 可以有 N 个订阅者同时听
- 适合：传感器数据（关节角度、图像、温度）、状态更新
```

### 你代码里对应的

你其实没用 ROS2 的 Topic，但你做的**跟它逻辑一样**：

```python
# 你的推理循环就是一个"发布者"
while True:
    action = model.select_action(...)     # 产生数据
    write_joints(action)                  # 发送给从动臂
```

如果换成 ROS2，就是：
```python
# 发布者
self.joint_pub = self.create_publisher(JointState, '/joint_commands', 10)
msg = JointState()
msg.position = action.tolist()
self.joint_pub.publish(msg)
```

---

## Service（服务）—— "问答"

```
客户端（Client）                          服务端（Server）
   │                                           │
   ├────── 请求：帮我算 (0.2, -0.1, 0.3) 的IK解 ────→
   │                                           │ 计算中...
   │   ←────────── 响应：[0.5, -1.2, 0.8, ...] ────┤
   │                                           │
   （完成，对话结束）


特点：
- 双向：客户端发请求 → 服务端处理 → 返回结果
- 一次性：请求-响应完成后链接就关了
- 客户端在等响应期间是**阻塞**的（卡住不动）
- 适合：查询 IK 解、急停、回零、读写一次参数
```

### 你代码里对应的

```python
# 你之前的 servo_test.py 就是这样用的
val = read_position(1)   # 发请求"告诉我舵机1的位置"
                          # 等响应 ← 程序卡在这
print(val)               # 拿到结果
```

如果换成 ROS2：
```python
# 服务端
self.stop_srv = self.create_service(Trigger, '/brain/stop_arm', self.stop_callback)

def stop_callback(self, request, response):
    disable_torque()
    response.success = True
    response.message = "已急停"
    return response
```

```bash
# 客户端调用
ros2 service call /brain/stop_arm std_srvs/srv/Trigger
```

---

## Action（动作）—— "长任务 + 进度 + 取消"

```
客户端                                      服务端
   │                                           │
   ├────── 目标：从 A 点移到 B 点 ────────→  开始执行...
   │   ←────── 反馈：进度 10% ────────────┤
   │   ←────── 反馈：进度 50% ────────────┤  （客户端不卡，可以干别的事）
   │   ←────── 反馈：进度 90% ────────────┤
   │                                          │
   │  （中途客户端觉得不对，发取消）              │
   ├────── 取消 ────────────────────────→  立刻停止！
   │   ←────── 结果：已取消 ───────────────┤


特点：
- 长耗时任务（几秒到几十秒）
- 中间有进度反馈（不是一次性的）
- 客户端不阻塞（发完目标可以干别的事）
- 可以随时取消
- 适合：运动轨迹执行、长时间抓取任务、视觉搜索
```

### 为什么有 Topic 和 Service 还要有 Action？

```
场景：让机械臂从 A 移到 B，需要 5 秒

Topic 做法：
  发一个话题 "去 B" → 然后呢？机械臂走到没有？不知道。

Service 做法：
  发请求 "去 B" → 程序卡死 5 秒 → 返回"到了"。
  5 秒内你没法获取进度、没法中途让它停。

Action 做法：
  发目标 "去 B" → 每 0.5 秒收到进度 → 走到一半觉得不对 → 取消。
  完美！
```

---

## 用你做过的东西来理解

| 你做过的事 | 对应 ROS2 概念 | 为什么 |
|-----------|-------------|--------|
| 遥操作（领导臂角度 → 从动臂角度） | Topic | 持续流式数据，单向发送 |
| 标定（"把舵机移到中间" → 等 → 读） | 类似 Service | 一次性请求-响应 |
| 数据采集（3段 × 15秒，段间自动复位） | 类似 Action | 长任务 + 自动化 + 可中断 |
| 推理控制（摄像头 → 模型 → 写舵机） | Topic + Service | 持续循环是一个 Topic，急停是 Service |

---

## 你同学的交接文档里为什么要这么设计

```
/brain/action_command（Topic）
    → 大脑发 JSON 指令（move_to / home / stop）
    → 单向，持续可发多条

/brain/action_feedback（Topic）
    → 机械臂状态的实时反馈
    → 单向，持续汇报

/brain/stop_arm（Service）
    → 急停！必须立刻响应、不能排队
    → Service 是最快的（一发一收，不等队列）

/brain/go_home（Service）
    → 回零，一次性操作
    → 成功后立刻返回"到零位了"
```

---

## 你现在要练的

1. **写一个 Topic 发布者**：发布一个假关节角度（0-4095），每秒发 10 次
2. **写一个 Topic 订阅者**：收到假角度 → 打印出来
3. **写一个 Service 服务端**：收到 Trigger 请求 → 返回 "急停成功"
4. **写一个 Service 客户端**：调用上面那个服务

你的虚拟机里已经有 ROS2 Humble，直接在终端里用 `ros2 topic pub` 和 `ros2 topic echo` 就能验证。不需要连机械臂。
