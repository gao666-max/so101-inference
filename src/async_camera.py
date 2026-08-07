"""
5.1.2 Camera 类 —— 异步图像获取与缓存管理

用法:
    cam = AsyncCamera(index_or_path=0, width=640, height=480, fps=30)
    cam.start()                        # 启动后台抓图
    frame = cam.get_latest_frame()     # 主程序随时取最新一帧
    cam.stop()                         # 停止并释放摄像头
"""

import cv2
import threading
import time
import numpy as np


class AsyncCamera:
    """异步摄像头类：后台线程持续抓图，主线程无阻塞获取最新帧。"""

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

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)

        # 预热一帧，触发摄像头缓冲区
        self._cap.read()

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print(f"[AsyncCamera] 摄像头 {self.index_or_path} 已启动 ({self.width}x{self.height} @ {self.fps}fps)")

    def stop(self):
        """停止后台线程并释放摄像头。"""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._cap is not None:
            self._cap.release()
        print(f"[AsyncCamera] 已停止，共抓取 {self._frame_count} 帧")

    def _capture_loop(self):
        """后台线程：持续读取摄像头，把最新帧存进缓存。"""
        while self._running:
            ret, frame = self._cap.read()
            if ret:
                with self._lock:
                    self._latest_frame = frame.copy()
                    self._frame_count += 1
            else:
                time.sleep(0.001)

    def get_latest_frame(self) -> np.ndarray | None:
        """主程序调用：无阻塞获取最新一帧。"""
        with self._lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def frame_count(self) -> int:
        with self._lock:
            return self._frame_count


# ========== 测试入口 ==========
if __name__ == "__main__":
    cam = AsyncCamera(index_or_path=0, width=640, height=480, fps=30)
    cam.start()

    print("\n3秒内每秒取一帧...")
    for i in range(3):
        time.sleep(1)
        frame = cam.get_latest_frame()
        if frame is not None:
            print(f"  第{i+1}秒: 帧形状={frame.shape}, 已抓总帧数={cam.frame_count}")
        else:
            print(f"  第{i+1}秒: 无帧")

    # 保存一张测试图
    frame = cam.get_latest_frame()
    if frame is not None:
        cv2.imwrite("async_camera_test.jpg", frame)
        print("\n测试图已保存: async_camera_test.jpg")

    cam.stop()
