"""
camera.py —— USB 摄像头异步采集封装
=====================================
后台线程持续抓图，主线程无阻塞获取最新一帧。
支持 YUYV 格式转换、可配置分辨率和帧率。

用法:
    cam = Camera(index_or_path=0, width=640, height=480, fps=30)
    cam.start()
    frame = cam.get_latest_frame()  # 非阻塞
    cam.stop()
"""

import cv2
import threading
import time


class Camera:
    """USB 摄像头封装：后台线程持续抓帧，主线程无阻塞取最新一帧。"""

    def __init__(self, index_or_path=0, width=640, height=480, fps=30):
        self.index_or_path = index_or_path
        self.width = width
        self.height = height
        self.fps = fps

        self._cap = None
        self._thread = None
        self._running = False
        self._lock = threading.Lock()
        self._latest_frame = None
        self._frame_count = 0

    def start(self):
        """打开摄像头并启动后台抓图线程。"""
        self._cap = cv2.VideoCapture(self.index_or_path)
        if not self._cap.isOpened():
            raise RuntimeError(f"无法打开摄像头: {self.index_or_path}")

        # 设置 MJPG 格式（避免 YUYV 带宽瓶颈）
        self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)
        self._cap.read()  # 预热

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print(f"[Camera] 摄像头 {self.index_or_path} 已启动 ({self.width}x{self.height} @ {self.fps}fps)")

    def stop(self):
        """停止后台线程并释放摄像头。"""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._cap is not None:
            self._cap.release()
        print(f"[Camera] 已停止，共抓取 {self._frame_count} 帧")

    def _capture_loop(self):
        """后台线程：循环读取摄像头帧。"""
        while self._running:
            ret, frame = self._cap.read()
            if ret:
                with self._lock:
                    self._latest_frame = frame.copy()
                    self._frame_count += 1
            else:
                time.sleep(0.001)

    def get_latest_frame(self):
        """主线程调用：无阻塞获取最新一帧。返回 None 表示还没抓到帧。"""
        with self._lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    @property
    def is_running(self):
        return self._running

    @property
    def frame_count(self):
        with self._lock:
            return self._frame_count


if __name__ == "__main__":
    cam = Camera(index_or_path=0, width=640, height=480, fps=30)
    cam.start()
    time.sleep(2)
    frame = cam.get_latest_frame()
    if frame is not None:
        cv2.imwrite("camera_test.jpg", frame)
        print(f"测试图已保存: camera_test.jpg, 形状={frame.shape}")
    cam.stop()
