#!/bin/bash
# =============================================
# SO101 单臂数据采集脚本（第六章标准 + 稳定版）
# 参数：3段 × 15秒，段间 3秒复位
# 用法: bash ~/lerobot/start_record.sh
# =============================================

echo "===== SO101 数据采集（第六章标准）====="

if [ ! -L /dev/so101_leader_single ] || [ ! -L /dev/so101_follower_single ]; then
    echo "❌ 串口未就绪！请检查机械臂电源和 VirtualBox USB 勾选。"
    exit 1
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "✅ 领导臂: /dev/so101_leader_single"
echo "✅ 从动臂: /dev/so101_follower_single"
echo "📷 摄像头: /dev/video0 (640x480, 30fps)"
echo "📁 数据集: test/single_arm_pick_${TIMESTAMP}"
echo "📹 录制 3 段，每段 15 秒，段间 3 秒复位"
echo ""
echo "⚠️  流程："
echo "  - 每段开始前 3 秒把机械臂和方块归位"
echo "  - 15 秒内完成一次夹取/移动动作"
echo "  - 录完 3 段自动停止"
echo "  - 操作失误按 Ctrl+C 终止"
echo ""

HF_HUB_OFFLINE=1 lerobot-record \
    --robot.type=so101_follower \
    --robot.port=/dev/so101_follower_single \
    --robot.id=so101_follower_single \
    --robot.cameras='{"front": {"type": "opencv", "index_or_path": 0, "width": 640, "height": 480, "fps": 30}}' \
    --teleop.type=so101_leader \
    --teleop.port=/dev/so101_leader_single \
    --teleop.id=so101_leader_single \
    --dataset.repo_id="test/single_arm_pick_${TIMESTAMP}" \
    --dataset.num_episodes=3 \
    --dataset.episode_time_s=15 \
    --dataset.reset_time_s=3 \
    --dataset.single_task="single_arm_pick" \
    --dataset.fps=30 \
    --dataset.push_to_hub=False \
    --display_data=False
