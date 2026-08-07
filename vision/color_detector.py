"""
color_detector.py —— 基于 HSV 的颜色识别模块
=============================================
从 BGR 图像中识别指定颜色的物体（默认红色瓶盖），
返回物体中心像素坐标。

用法:
    detector = ColorDetector(target="red")
    center, contour = detector.detect(frame)
    if center is not None:
        u, v = center
"""

import cv2
import numpy as np


class ColorDetector:
    """基于 HSV 颜色空间的颜色识别器。"""

    # 预定义颜色 HSV 阈值（H: 0-180, S: 0-255, V: 0-255）
    COLOR_THRESHOLDS = {
        "red": {
            "lower1": (0, 120, 70),
            "upper1": (12, 255, 255),
            "lower2": (165, 120, 70),
            "upper2": (179, 255, 255),
        },
        "yellow": {
            "lower1": (20, 100, 100),
            "upper1": (35, 255, 255),
        },
        "blue": {
            "lower1": (90, 50, 50),
            "upper1": (130, 255, 255),
        },
        "green": {
            "lower1": (40, 50, 50),
            "upper1": (80, 255, 255),
        },
    }

    def __init__(self, target="red", min_area_ratio=0.001, max_area_ratio=0.8):
        """
        target:          颜色名 ("red", "yellow", "blue", "green")
        min_area_ratio:  物体占画面最小比例（过滤噪点）
        max_area_ratio:  物体占画面最大比例（过滤整屏误检）
        """
        self.target = target
        self.thresholds = self.COLOR_THRESHOLDS.get(target, self.COLOR_THRESHOLDS["red"])
        self.min_area_ratio = min_area_ratio
        self.max_area_ratio = max_area_ratio

    def detect(self, bgr_frame):
        """
        从 BGR 图像中检测目标颜色物体。

        返回:
            center:  (u, v) 物体中心像素坐标，没检测到返回 None
            contour: 最大轮廓对象（用于画框），没检测到返回 None
            mask:    二值掩膜（调试用）
        """
        h, w = bgr_frame.shape[:2]
        hsv = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2HSV)

        # 构建掩膜 —— 红色跨 HSV 边界需要两段
        mask = cv2.inRange(hsv, self.thresholds["lower1"], self.thresholds["upper1"])
        if "lower2" in self.thresholds:
            mask2 = cv2.inRange(hsv, self.thresholds["lower2"], self.thresholds["upper2"])
            mask = cv2.bitwise_or(mask, mask2)

        # 形态学滤波：去噪 + 填洞
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=2)

        # 找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None, None, mask

        # 取面积最大的轮廓
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)

        # 面积过滤
        min_area = (w * h) * self.min_area_ratio
        max_area = (w * h) * self.max_area_ratio
        if area < min_area or area > max_area:
            return None, largest, mask

        # 中心矩 → 中心点
        M = cv2.moments(largest)
        if M["m00"] == 0:
            return None, largest, mask
        u = int(M["m10"] / M["m00"])
        v = int(M["m01"] / M["m00"])

        return (u, v), largest, mask

    def draw_result(self, frame, center, contour):
        """在画面上绘制检测结果：轮廓 + 中心十字线 + 坐标标注。"""
        if contour is not None:
            cv2.drawContours(frame, [contour], -1, (0, 255, 0), 2)
            x, y, bw, bh = cv2.boundingRect(contour)
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 255, 0), 2)

        if center is not None:
            u, v = center
            cv2.line(frame, (u - 10, v), (u + 10, v), (0, 0, 255), 2)
            cv2.line(frame, (u, v - 10), (u, v + 10), (0, 0, 255), 2)
            cv2.putText(frame, f"({u}, {v})", (u + 15, v - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        cv2.putText(frame, f"Target: {self.target}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)


if __name__ == "__main__":
    from camera import Camera
    import time

    print("颜色识别测试 —— 找红色物体，按 'q' 退出, 's' 保存画面")
    cam = Camera(index_or_path=0, width=640, height=480, fps=30)
    cam.start()
    time.sleep(1)

    detector = ColorDetector(target="red")

    while True:
        frame = cam.get_latest_frame()
        if frame is None:
            continue

        center, contour, _ = detector.detect(frame)
        detector.draw_result(frame, center, contour)

        if center is not None:
            print(f"\r  检测到目标: ({center[0]:4d}, {center[1]:4d})", end="", flush=True)

        cv2.imshow("Color Detection", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            cv2.imwrite("color_detect_result.jpg", frame)
            print(f"\n  画面已保存")

    cam.stop()
    cv2.destroyAllWindows()
    print("\n退出。")
