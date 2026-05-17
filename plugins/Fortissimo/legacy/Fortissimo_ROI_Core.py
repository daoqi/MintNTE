# core/Fortissimo/Fortissimo_ROI_Core.py
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
from dataclasses import dataclass, asdict
from collections import deque
import json
from UI.logui import info, error, warning

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from Module.Hwnd.game_hwnd import get_game_hwnd, set_locked_hwnd

# 尝试导入 dxcam
try:
    import dxcam
    DXCAM_AVAILABLE = True
except ImportError:
    DXCAM_AVAILABLE = False

# ---------- 颜色定义 ----------
COLOR_A_BGR = (0xb4, 0xd5, 0x2f)   # #2fd5b4
COLOR_B_BGR = (0x95, 0xf4, 0xfe)   # #fef495
COLOR_TOLERANCE = 30
MIN_PIXELS = 5

# ---------- 全局 DXcam 实例 ----------
_camera = None
_camera_region = None

def start_dxcam_for_hwnd(hwnd, target_fps=240):
    global _camera, _camera_region
    if not DXCAM_AVAILABLE:
        return False
    rect = win32gui.GetWindowRect(hwnd)
    left, top, right, bottom = rect
    region = (left, top, right, bottom)
    try:
        _camera = dxcam.create(output_color="BGR")
        _camera.start(target_fps=target_fps, region=region)
        _camera_region = region
        info(f"ROI Core: DXcam 前台截图已启动，区域 {region}")
        time.sleep(0.1)
        return True
    except Exception as e:
        error(f"ROI Core: DXcam 启动失败: {e}")
        return False

def get_dxcam_frame():
    global _camera
    return _camera.get_latest_frame() if _camera else None

def stop_dxcam():
    global _camera
    if _camera:
        _camera.stop()
        _camera = None

def capture_with_printwindow(hwnd, region=None):
    if not win32gui.IsWindow(hwnd):
        return None
    rect = win32gui.GetClientRect(hwnd)
    left, top, right, bottom = rect
    w, h = right - left, bottom - top
    if w <= 0 or h <= 0:
        return None
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
    save_dc.SelectObject(bitmap)
    success = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)
    if not success:
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)
        return None
    bits = bitmap.GetBitmapBits(True)
    img = Image.frombuffer("RGB", (w, h), bits, "raw", "BGRX", 0, 1)
    opencv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    win32gui.DeleteObject(bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)
    if region:
        x1, y1, x2, y2 = region
        x1 = max(0, min(x1, w-1))
        y1 = max(0, min(y1, h-1))
        x2 = max(x1+1, min(x2, w))
        y2 = max(y1+1, min(y2, h))
        opencv_img = opencv_img[y1:y2, x1:x2]
    return opencv_img

class FishingROICore:
    def __init__(self, roi_region, capture_mode="background"):
        """
        roi_region: (x1, y1, x2, y2) 客户区坐标（已包含偏移）
        capture_mode: "background" 或 "foreground"
        """
        self.hwnd = get_game_hwnd()
        if not self.hwnd or not win32gui.IsWindow(self.hwnd):
            raise RuntimeError("未找到有效的游戏窗口句柄，请先通过「窗口检测」锁定窗口")
        self.roi_region = roi_region
        self.capture_mode = capture_mode
        self.running = False
        self.threads = []
        self.data = {
            'color_a': {'pixels': 0, 'rect': None},
            'color_b': {'pixels': 0, 'rect': None},
        }
        self.lock = threading.Lock()
        set_locked_hwnd(self.hwnd)

        if capture_mode == "foreground" and DXCAM_AVAILABLE:
            start_dxcam_for_hwnd(self.hwnd)
            # 前台模式：启动帧缓存线程
            self.frame_lock = threading.Lock()
            self._latest_frame = None
            self._frame_stop = threading.Event()
            self._frame_thread = threading.Thread(target=self._frame_updater, daemon=True)
            self._frame_thread.start()
        else:
            self.capture_mode = "background"

    def _frame_updater(self):
        while not self._frame_stop.is_set() and self.running:
            frame = get_dxcam_frame()
            if frame is not None:
                with self.frame_lock:
                    self._latest_frame = frame
            time.sleep(0.005)

    def _get_current_frame(self):
        if self.capture_mode == "foreground" and DXCAM_AVAILABLE:
            with self.frame_lock:
                return self._latest_frame.copy() if self._latest_frame is not None else None
        else:
            return capture_with_printwindow(self.hwnd, region=None)

    def _detect_worker(self, name, target_bgr):
        while self.running:
            full_img = self._get_current_frame()
            if full_img is None:
                time.sleep(0.01)
                continue
            x1, y1, x2, y2 = self.roi_region
            h, w = full_img.shape[:2]
            if x2 > w or y2 > h:
                time.sleep(0.01)
                continue
            roi = full_img[y1:y2, x1:x2]
            if roi.size == 0:
                continue
            lower = np.array([max(0, c - COLOR_TOLERANCE) for c in target_bgr], dtype=np.uint8)
            upper = np.array([min(255, c + COLOR_TOLERANCE) for c in target_bgr], dtype=np.uint8)
            mask = cv2.inRange(roi, lower, upper)
            pixel_count = cv2.countNonZero(mask)
            if pixel_count < MIN_PIXELS:
                rect = None
            else:
                points = cv2.findNonZero(mask)
                if points is not None:
                    x, y, w, h = cv2.boundingRect(points)
                    rect = (x, y, x+w, y+h)
                else:
                    rect = None
            with self.lock:
                if name == 'color_a':
                    self.data['color_a']['pixels'] = pixel_count
                    self.data['color_a']['rect'] = rect
                else:
                    self.data['color_b']['pixels'] = pixel_count
                    self.data['color_b']['rect'] = rect
            time.sleep(0.005)

    def start(self):
        if self.running:
            return
        self.running = True
        if self.capture_mode == "foreground":
            self._frame_stop.clear()
        t1 = threading.Thread(target=self._detect_worker, args=('color_a', COLOR_A_BGR), daemon=True)
        t2 = threading.Thread(target=self._detect_worker, args=('color_b', COLOR_B_BGR), daemon=True)
        t1.start()
        t2.start()
        self.threads = [t1, t2]

    def stop(self):
        self.running = False
        if self.capture_mode == "foreground":
            self._frame_stop.set()
            if hasattr(self, '_frame_thread'):
                self._frame_thread.join(timeout=1)
            stop_dxcam()
        for t in self.threads:
            t.join(timeout=1)

    def get_data(self):
        with self.lock:
            return self.data.copy()

    def get_full_screenshot(self):
        if self.capture_mode == "foreground":
            frame = self._get_current_frame()
            if frame is not None:
                return frame
        return capture_with_printwindow(self.hwnd, region=None)