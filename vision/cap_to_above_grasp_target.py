"""
cap_to_above_grasp_target.py —— 瓶盖检测 + 目标关节角度生成
============================================================
综合管线：
  1. 摄像头拍照 → 颜色检测 → 瓶盖像素坐标 (u, v)
  2. Homography 变换 → 纸面坐标 (x, y) mm
  3. 在 A/B/C/D 示教点间双线性插值 → above/grasp 关节角度
  4. 输出 cap_above_grasp_target.json

用法:
    python cap_to_above_grasp_target.py

输出:
    output/cap_above_grasp_target.json
    output/cap_above_grasp_debug.jpg  （调试可视化）
"""

import cv2
import json
import os
import time
import numpy as np
from camera import Camera
from color_detector import ColorDetector
from pixel_to_joint import PixelToJoint


def main():
    print("=" * 60)
    print("瓶盖检测 + 目标关节生成")
    print("=" * 60)

    # ---- 文件路径 ----
    homography_path = "output/plane_homography.json"
    demo_points_path = "output/plane_above_grasp_joint_points.json"

    # ---- 检查前置文件 ----
    if not os.path.exists(homography_path):
        print(f"\n[ERROR] 缺少 Homography 文件: {homography_path}")
        print("请先运行 plane_calibrator.py")
        return
    if not os.path.exists(demo_points_path):
        print(f"\n[ERROR] 缺少示教文件: {demo_points_path}")
        print("请先运行 teleop_collect_above_grasp_points.py")
        return

    # ---- 初始化 ----
    p2j = PixelToJoint(homography_path, demo_points_path)
    detector = ColorDetector(target="red")
    cam = Camera(index_or_path=0, width=640, height=480, fps=30)
    cam.start()
    time.sleep(1)

    print("\n请确保：")
    print("  1. 纸面在摄像头视野中")
    print("  2. 红色瓶盖放在纸面上")
    print("  3. 按下 'c' 执行检测和计算")
    print("  4. 按下 'q' 退出")
    print("-" * 40)

    os.makedirs("output", exist_ok=True)

    while True:
        frame = cam.get_latest_frame()
        if frame is None:
            continue

        display = frame.copy()

        # 实时检测瓶盖
        center, contour, mask = detector.detect(frame)

        if center is not None:
            u, v = center
            detector.draw_result(display, center, contour)

            # 转纸面坐标
            try:
                x_mm, y_mm = p2j.pixel_to_paper(u, v)
                cv2.putText(display, f"Paper: ({x_mm:.1f}, {y_mm:.1f}) mm",
                            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            except Exception:
                x_mm, y_mm = 0, 0

        cv2.putText(display, "Press 'c' to capture target", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.imshow("Cap to Above/Grasp Target", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('c'):
            if center is None:
                print("\n[FAIL] 未检测到红色瓶盖！")
                continue

            u, v = center

            # 像素 → 纸面
            try:
                x_mm, y_mm = p2j.pixel_to_paper(u, v)
            except Exception as e:
                print(f"\n[FAIL] Homography 转换失败: {e}")
                continue

            # 插值关节角度
            try:
                above_joints = p2j.interpolate_joints(x_mm, y_mm, "above")
                grasp_joints = p2j.interpolate_joints(x_mm, y_mm, "grasp")
            except Exception as e:
                print(f"\n[FAIL] 插值失败: {e}")
                continue

            # 组装结果
            target = {
                "cap_pixel": {"u": u, "v": v},
                "paper_xy_mm": {"x": round(x_mm, 2), "y": round(y_mm, 2)},
                "above_joints": above_joints,
                "grasp_joints": grasp_joints,
            }

            # 保存
            output_path = "output/cap_above_grasp_target.json"
            with open(output_path, "w") as f:
                json.dump(target, f, indent=2)

            # 保存调试图
            debug = display.copy()
            cv2.putText(debug, f"TARGET SAVED", (10, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imwrite("output/cap_above_grasp_debug.jpg", debug)

            print(f"\n{'=' * 40}")
            print(f"[OK] 目标已生成:")
            print(f"  像素: ({u}, {v})")
            print(f"  纸面: ({x_mm:.1f}, {y_mm:.1f}) mm")
            print(f"  above_joints: {above_joints}")
            print(f"  grasp_joints: {grasp_joints}")
            print(f"  已保存: {output_path}")
            print(f"  调试图: output/cap_above_grasp_debug.jpg")
            print(f"{'=' * 40}")

    cam.stop()
    cv2.destroyAllWindows()
    print("退出。")


if __name__ == "__main__":
    main()
