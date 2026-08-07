"""
plane_calibrator.py —— 纸面四角标定
=====================================
识别纸上的 4 个黑色标记点 A/B/C/D，建立"像素坐标 → 纸面坐标"的
单应性变换矩阵（Homography）。

纸面坐标定义（默认 180×100mm）:
  A: 左上角 = (0, 0) mm
  B: 右上角 = (180, 0) mm
  C: 右下角 = (180, 100) mm
  D: 左下角 = (0, 100) mm

用法:
    python plane_calibrator.py --width-mm 180 --height-mm 100

输出:
    plane_homography.json  —— 单应性矩阵
    plane_points_detected.jpg —— 检测结果可视化
"""

import cv2
import numpy as np
import json
import os
import argparse
from camera import Camera


class PlaneCalibrator:
    """检测纸面四角标记点，计算 Homography 矩阵。"""

    def __init__(self, width_mm=180, height_mm=100):
        self.width_mm = width_mm
        self.height_mm = height_mm

        # 纸面坐标（左上角为原点，x 向右，y 向下）
        self.paper_points = np.array([
            [0, 0],              # A: 左上
            [width_mm, 0],       # B: 右上
            [width_mm, height_mm],  # C: 右下
            [0, height_mm],      # D: 左下
        ], dtype=np.float32)

    def preprocess(self, gray):
        """预处理：自适应二值化，让黑点更突出。"""
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )
        return thresh

    def find_markers(self, frame):
        """
        从画面中找到 4 个角点。

        思路：
        1. 灰度 → 二值化 → 找轮廓
        2. 筛选近似圆形的轮廓（标记点是圆点）
        3. 按 y 坐标分上下两排，每排按 x 坐标分左右
        4. 返回 [A, B, C, D] 四个像素坐标
        """
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        thresh = self.preprocess(gray)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if len(contours) < 4:
            return None, thresh

        # 筛选：面积不要太小/太大，形状接近圆
        candidates = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < 50 or area > (w * h) * 0.1:
                continue
            # 圆形度 = 面积 / 外接圆面积
            (cx, cy), radius = cv2.minEnclosingCircle(c)
            if radius > 0:
                circularity = area / (np.pi * radius * radius)
                if circularity > 0.4:  # 不要太不圆
                    # 用质心作为定位
                    M = cv2.moments(c)
                    if M["m00"] != 0:
                        px = int(M["m10"] / M["m00"])
                        py = int(M["m01"] / M["m00"])
                        candidates.append((px, py))

        if len(candidates) < 4:
            # 不够 4 个 —— 选面积最大的 4 个
            candidates = []
            for c in sorted(contours, key=cv2.contourArea, reverse=True)[:20]:
                area = cv2.contourArea(c)
                if area < 30:
                    continue
                M = cv2.moments(c)
                if M["m00"] != 0:
                    px = int(M["m10"] / M["m00"])
                    py = int(M["m01"] / M["m00"])
                    candidates.append((px, py))
            candidates = candidates[:4]

        if len(candidates) < 4:
            return None, thresh

        # 取前 4 个并按 y 坐标排序 → 分成上下两排
        candidates = sorted(candidates[:4], key=lambda p: p[1])
        top_two = sorted(candidates[:2], key=lambda p: p[0])    # 上排按 x 排序
        bot_two = sorted(candidates[2:4], key=lambda p: p[0])   # 下排按 x 排序

        image_points = np.array([
            top_two[0],   # A: 左上
            top_two[1],   # B: 右上
            bot_two[1],   # C: 右下
            bot_two[0],   # D: 左下
        ], dtype=np.float32)

        return image_points, thresh

    def calibrate(self, frame):
        """从一帧画面中计算 Homography 矩阵。"""
        result = self.find_markers(frame)
        if result is None:
            return None, None, None
        image_points, thresh = result

        # 计算单应性矩阵
        H, mask = cv2.findHomography(image_points, self.paper_points)
        return H, image_points, thresh

    def draw_result(self, frame, image_points, H):
        """在画面上绘制检测结果。"""
        display = frame.copy()

        if image_points is not None:
            # 把检测到的四个点连成矩形
            pts = image_points.astype(np.int32)
            for i, (px, py) in enumerate(pts):
                label = ["A(0,0)", "B(W,0)", "C(W,H)", "D(0,H)"][i]
                cv2.circle(display, (px, py), 6, (0, 0, 255), -1)
                cv2.putText(display, label, (px + 10, py + 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.drawContours(display, [pts.reshape((-1, 1, 2))], 0, (255, 0, 0), 2)

        if H is not None:
            # 用 Homography 把纸面角点反投回图像验证
            paper_corners = np.array([
                [0, 0],
                [self.width_mm, 0],
                [self.width_mm, self.height_mm],
                [0, self.height_mm],
            ], dtype=np.float32).reshape(-1, 1, 2)
            projected = cv2.perspectiveTransform(paper_corners, np.linalg.inv(H))
            projected = projected.reshape(-1, 2).astype(np.int32)
            cv2.drawContours(display, [projected], 0, (0, 255, 255), 2)

        cv2.putText(display, "Paper Calibration", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        return display


def main():
    parser = argparse.ArgumentParser(description="纸面四角标定")
    parser.add_argument("--width-mm", type=int, default=180, help="纸面宽度 mm")
    parser.add_argument("--height-mm", type=int, default=100, help="纸面高度 mm")
    parser.add_argument("--min-area", type=int, default=30, help="标记点最小面积")
    args = parser.parse_args()

    print("=" * 60)
    print("纸面四角标定 —— Plane Calibration")
    print(f"纸面尺寸: {args.width_mm} x {args.height_mm} mm")
    print("=" * 60)
    print("\n操作：")
    print("  1. 纸上有 A/B/C/D 四个标记点")
    print("  2. 确保四个点都在摄像头画面中")
    print("  3. 按下 'c' 执行标定")
    print("  4. 按下 'q' 退出")
    print()
    print("纸面坐标定义：")
    print(f"  A: 左上 = (0, 0) mm")
    print(f"  B: 右上 = ({args.width_mm}, 0) mm")
    print(f"  C: 右下 = ({args.width_mm}, {args.height_mm}) mm")
    print(f"  D: 左下 = (0, {args.height_mm}) mm")

    calib = PlaneCalibrator(width_mm=args.width_mm, height_mm=args.height_mm)
    cam = Camera(index_or_path=0, width=640, height=480, fps=30)
    cam.start()
    import time
    time.sleep(1)

    os.makedirs("output", exist_ok=True)
    H = None
    image_points = None

    while True:
        frame = cam.get_latest_frame()
        if frame is None:
            continue

        display = calib.draw_result(frame, image_points, H)
        cv2.imshow("Plane Calibration", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('c'):
            H, image_points, thresh = calib.calibrate(frame)
            if H is not None:
                # 保存 Homography
                result = {
                    "paper_size_mm": [args.width_mm, args.height_mm],
                    "homography_matrix": H.tolist(),
                    "image_points": image_points.tolist() if image_points is not None else None,
                    "paper_points": calib.paper_points.tolist(),
                }
                with open("output/plane_homography.json", "w") as f:
                    json.dump(result, f, indent=2)
                print(f"\n[OK] Homography 已保存: output/plane_homography.json")

                # 保存可视化图
                vis = calib.draw_result(frame, image_points, H)
                cv2.imwrite("output/plane_points_detected.jpg", vis)
                print("[OK] 可视化图: output/plane_points_detected.jpg")
            else:
                print("\n[FAIL] 未检测到 4 个标记点，请调整光线或标记位置")

    cam.stop()
    cv2.destroyAllWindows()
    print("退出。")


if __name__ == "__main__":
    main()
