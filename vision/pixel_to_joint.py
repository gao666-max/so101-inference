"""
pixel_to_joint.py —— 像素坐标 → 纸面坐标转换
==============================================
使用平面标定得到的 Homography 矩阵，将像素坐标 (u, v)
转换为纸面坐标 (x, y) mm。

也提供纸面上的线性插值 —— 在 A/B/C/D 四个示教点的关节角度之间，
对任意纸面坐标进行双线性插值，得到目标关节角度。

用法:
    from pixel_to_joint import PixelToJoint

    p2j = PixelToJoint("output/plane_homography.json")
    x_mm, y_mm = p2j.pixel_to_paper(u, v)
    joints = p2j.interpolate_joints(x_mm, y_mm)
"""

import json
import numpy as np


class PixelToJoint:
    """像素 → 纸面坐标 → 关节角度 转换器。"""

    def __init__(self, homography_path=None, demo_points_path=None):
        self.H = None
        self.inv_H = None
        self.demo_points = None  # { "A": {"above": {...}, "grasp": {...}}, ... }

        if homography_path is not None:
            self.load_homography(homography_path)
        if demo_points_path is not None:
            self.load_demo_points(demo_points_path)

    # ========== Homography ==========

    def load_homography(self, path):
        """加载 Homography 矩阵。"""
        with open(path, "r") as f:
            data = json.load(f)
        self.H = np.array(data["homography_matrix"])
        self.inv_H = np.linalg.inv(self.H)
        print(f"[PixelToJoint] 已加载 Homography: {path}")

    def pixel_to_paper(self, u, v):
        """
        像素坐标 → 纸面坐标。

        输入: u, v —— 图像像素坐标（物体中心）
        输出: x, y —— 纸面坐标（mm，原点在左上角）
        """
        if self.H is None:
            raise RuntimeError("未加载 Homography，请先调用 load_homography()")
        pixel = np.array([[[u, v]]], dtype=np.float32)
        paper = cv2.perspectiveTransform(pixel, self.H)
        return float(paper[0][0][0]), float(paper[0][0][1])

    # ========== 示教点 ==========

    def load_demo_points(self, path):
        """加载示教采集点文件。"""
        with open(path, "r") as f:
            self.demo_points = json.load(f)
        print(f"[PixelToJoint] 已加载示教点: {path}")

    def interpolate_joints(self, x_mm, y_mm, pose_type="above"):
        """
        在 A/B/C/D 四个示教点之间做双线性插值。

        pose_type: "above" 或 "grasp"

        纸面布局:
          A(0,0) --- B(W,0)
           |           |
          D(0,H) --- C(W,H)

        插值:
          先对 A-B 和 D-C 在 x 方向插值
          再对结果在 y 方向插值
        得 (x_mm, y_mm) 对应的一组关节角度。
        """
        if self.demo_points is None:
            raise RuntimeError("未加载示教点，请先调用 load_demo_points()")

        # 纸面尺寸从 demo 数据推断
        A = self.demo_points.get("A", {}).get(pose_type)
        C = self.demo_points.get("C", {}).get(pose_type)
        if A is None or C is None:
            raise RuntimeError(f"示教点缺少 A 或 C 的 {pose_type} 数据")

        W = float(self.demo_points.get("paper_width_mm", 180))
        H = float(self.demo_points.get("paper_height_mm", 100))

        # 归一化位置 (0-1)
        tx = np.clip(x_mm / (W + 1e-8), 0, 1)
        ty = np.clip(y_mm / (H + 1e-8), 0, 1)

        # 四角值
        corners = {
            "A": np.array(list(self.demo_points["A"][pose_type].values()), dtype=np.float64),
            "B": np.array(list(self.demo_points["B"][pose_type].values()), dtype=np.float64),
            "C": np.array(list(self.demo_points["C"][pose_type].values()), dtype=np.float64),
            "D": np.array(list(self.demo_points["D"][pose_type].values()), dtype=np.float64),
        }

        # 双线性插值
        top = corners["A"] * (1 - tx) + corners["B"] * tx
        bot = corners["D"] * (1 - tx) + corners["C"] * tx
        interpolated = top * (1 - ty) + bot * ty

        # 组装成关节名→值字典
        key_names = list(self.demo_points["A"][pose_type].keys())
        return dict(zip(key_names, interpolated))


# 需要 cv2 的 perspectiveTransform
import cv2


if __name__ == "__main__":
    print("pixel_to_joint.py —— 工具模块，不作为独立程序运行。")
    print("请在其他脚本中 import 使用。")
