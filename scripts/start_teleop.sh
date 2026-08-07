#!/bin/bash
# =============================================
# SO101 单臂遥操作一键启动脚本
# 路径: ~/lerobot/start_teleop.sh
# 用法: bash start_teleop.sh
# =============================================

echo "===== SO101 遥操作启动 ====="

# 1. 检查串口
echo "[1/3] 检查串口连接..."
LEADER=$(ls -l /dev/so101_leader_single 2>/dev/null | wc -l)
FOLLOWER=$(ls -l /dev/so101_follower_single 2>/dev/null | wc -l)

if [ "$LEADER" -eq 0 ] || [ "$FOLLOWER" -eq 0 ]; then
    echo "❌ 串口未全部就绪！"
    echo "请检查："
    echo "  1. 机械臂电源是否开启"
    echo "  2. VirtualBox「设备→USB」是否勾选 2 个 CH343"
    echo "  3. USB 线是否插紧"
    ls -l /dev/so101_* 2>/dev/null
    exit 1
fi
echo "✅ 领导臂: /dev/so101_leader_single"
echo "✅ 从动臂: /dev/so101_follower_single"

# 2. 激活环境
echo "[2/3] 激活 conda 环境..."
source ~/anaconda3/etc/profile.d/conda.sh
conda activate robot_arm
cd ~/lerobot

# 3. 启动遥操作
echo "[3/3] 启动遥操作..."
echo ""
echo "⚠️  安全提醒：先小幅度慢动作测试，确认方向正确！"
echo "⚠️  从动臂运动范围内不要放手/工具！"
echo "⚠️  遇到问题立刻 Ctrl+C 停止！"
echo ""

lerobot-teleoperate --teleop.type=so101_leader --teleop.port=/dev/so101_leader_single --teleop.id=so101_leader_single --robot.type=so101_follower --robot.port=/dev/so101_follower_single --robot.id=so101_follower_single
