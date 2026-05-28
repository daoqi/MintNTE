# plugins/fishing/fishing_roi/fishing_roi_core.py
import os
import sys
import time
import threading
import cv2
import numpy as np
import win32gui
import win32ui
import win32con
import ctypes
from PIL import Image

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from Module.Hwnd.game_hwnd import get_game_hwnd, set_locked_hwnd
from Module.capture.frame_capture import capture_frame  # 统一截图

# ---------- 颜色定义 (BGR) ----------
COLOR_A_BGR = (0xb4, 0xd5, 0x2f)   # #2fd5b4
COLOR_B_BGR = (0x95, 0xf4, 0xfe)   # #fef495
COLOR_TOLERANCE = 30
MIN_PIXELS = 5

def get_color_rect(img, target_bgr, tolerance=COLOR_TOLERANCE, min_pixels=MIN_PIXELS):
    lower = np.array([max(0, c - tolerance) for c in target_bgr], dtype=np.uint8)
    upper = np.array([min(255, c + tolerance) for c in target_bgr], dtype=np.uint8)
    mask = cv2.inRange(img, lower, upper)
    pixel_count = cv2.countNonZero(mask)
    if pixel_count < min_pixels:
        return pixel_count, None
    points = cv2.findNonZero(mask)
    if points is None:
        return pixel_count, None
    x, y, w, h = cv2.boundingRect(points)
    return pixel_count, (x, y, x + w, y + h)


class FishingROICore:
    def __init__(self, roi_region):
        self.hwnd = get_game_hwnd()
        if not self.hwnd or not win32gui.IsWindow(self.hwnd):
            raise RuntimeError("No valid window handle found")
        self.roi_region = roi_region
        self.running = False
        self.threads = []

        self.latest_frame = None
        self.frame_lock = threading.Lock()

        self.data = {
            'color_a': {'pixels': 0, 'rect': None},
            'color_b': {'pixels': 0, 'rect': None},
        }
        self.data_lock = threading.Lock()

        set_locked_hwnd(self.hwnd)

    def _capture_loop(self):
        while self.running:
            img = capture_frame(self.hwnd)  # 统一接口
            if img is not None:
                with self.frame_lock:
                    self.latest_frame = img
            time.sleep(0.01)

    def _detect_worker(self, name, target_bgr):
        while self.running:
            with self.frame_lock:
                full_img = self.latest_frame
            if full_img is None:
                time.sleep(0.005)
                continue

            x1, y1, x2, y2 = self.roi_region
            h, w = full_img.shape[:2]
            if x2 > w or y2 > h:
                time.sleep(0.005)
                continue
            roi = full_img[y1:y2, x1:x2]
            if roi.size == 0:
                continue

            pixels, rect = get_color_rect(roi, target_bgr)
            with self.data_lock:
                if name == 'color_a':
                    self.data['color_a']['pixels'] = pixels
                    self.data['color_a']['rect'] = rect
                else:
                    self.data['color_b']['pixels'] = pixels
                    self.data['color_b']['rect'] = rect
            time.sleep(0.005)

    def start(self):
        if self.running:
            return
        self.running = True

        capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        capture_thread.start()

        t1 = threading.Thread(target=self._detect_worker, args=('color_a', COLOR_A_BGR), daemon=True)
        t2 = threading.Thread(target=self._detect_worker, args=('color_b', COLOR_B_BGR), daemon=True)
        t1.start()
        t2.start()

        self.threads = [capture_thread, t1, t2]

    def stop(self):
        self.running = False
        for t in self.threads:
            t.join(timeout=1)

    def get_data(self):
        with self.data_lock:
            return self.data.copy()

    def get_full_screenshot(self):
        with self.frame_lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None