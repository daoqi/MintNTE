# core/Fortissimo/fortissimo_core.py
import os
import sys
import threading
import time
import logging
import cv2
import numpy as np
import win32gui
import win32ui
import win32con
import ctypes
from PIL import Image

logger = logging.getLogger("Fortissimo")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    fh = logging.FileHandler("fortissimo.log", encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from Module.click.NET_click import send_key_down, send_key_up

WM_ACTIVATE = 0x0006
WA_ACTIVE = 1

def fake_activate(hwnd):
    try:
        win32gui.SendMessage(hwnd, WM_ACTIVATE, WA_ACTIVE, 0)
    except:
        pass

def _resolve_image_path(user_path: str) -> str:
    if os.path.exists(user_path):
        return user_path
    proj_path = os.path.join(BASE_DIR, user_path)
    if os.path.exists(proj_path):
        return proj_path
    module_image_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Image")
    basename = os.path.basename(user_path)
    img_path = os.path.join(module_image_dir, basename)
    if os.path.exists(img_path):
        return img_path
    return user_path

def capture_window_to_cv(hwnd):
    rect = win32gui.GetClientRect(hwnd)
    left, top, right, bottom = rect
    width = right - left
    height = bottom - top
    if width == 0 or height == 0:
        return None
    hdc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hdc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(bitmap)
    success = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)
    if not success:
        return None
    bitmap_bits = bitmap.GetBitmapBits(True)
    img = Image.frombuffer("RGB", (width, height), bitmap_bits, "raw", "BGRX", 0, 1)
    opencv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    return opencv_img

_screenshot_lock = threading.Lock()
_last_screenshot = None
_screenshot_updater_stop = False
_screenshot_thread = None

def _screenshot_updater_worker(hwnd, interval):
    global _last_screenshot, _screenshot_updater_stop
    while not _screenshot_updater_stop:
        img = capture_window_to_cv(hwnd)
        if img is not None:
            with _screenshot_lock:
                _last_screenshot = img
        time.sleep(interval)

def start_screenshot_updater(hwnd, interval=0.05):
    global _screenshot_thread, _screenshot_updater_stop
    if _screenshot_thread is None or not _screenshot_thread.is_alive():
        _screenshot_updater_stop = False
        _screenshot_thread = threading.Thread(target=_screenshot_updater_worker, args=(hwnd, interval), daemon=True)
        _screenshot_thread.start()

def stop_screenshot_updater():
    global _screenshot_updater_stop
    _screenshot_updater_stop = True
    if _screenshot_thread:
        _screenshot_thread.join(timeout=1)

def get_cached_screenshot():
    with _screenshot_lock:
        return _last_screenshot

def find_image_in_region(region, template_path, threshold=0.8):
    full_img = get_cached_screenshot()
    if full_img is None:
        return False
    x1, y1, x2, y2 = region
    h, w = full_img.shape[:2]
    x1 = max(0, min(x1, w-1))
    y1 = max(0, min(y1, h-1))
    x2 = max(x1+1, min(x2, w))
    y2 = max(y1+1, min(y2, h))
    roi = full_img[y1:y2, x1:x2]
    if roi.size == 0:
        return False
    actual_path = _resolve_image_path(template_path)
    template = cv2.imread(actual_path, cv2.IMREAD_GRAYSCALE)
    if template is None:
        logger.error(f"无法加载模板图片: {template_path} -> {actual_path}")
        return False
    roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    result = cv2.matchTemplate(roi_gray, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val >= threshold

def key_worker(hwnd, region, template_path, key_char, speed, stop_event):
    vk = ord(key_char.upper())
    while not stop_event.is_set():
        fake_activate(hwnd)
        found = find_image_in_region(region, template_path, threshold=0.8)
        if not found:
            send_key_down(hwnd, vk)
            time.sleep(speed)
            send_key_up(hwnd, vk)
        time.sleep(speed)

def stop_monitor(stop_image_path, stop_event):
    while not stop_event.is_set():
        full_img = get_cached_screenshot()
        if full_img is not None:
            actual_path = _resolve_image_path(stop_image_path)
            template = cv2.imread(actual_path, cv2.IMREAD_GRAYSCALE)
            if template is not None:
                full_gray = cv2.cvtColor(full_img, cv2.COLOR_BGR2GRAY)
                result = cv2.matchTemplate(full_gray, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                if max_val >= 0.8:
                    logger.info("歌曲演奏完毕")
                    stop_event.set()
                    break
        time.sleep(0.5)

class FortissimoCore:
    def __init__(self):
        self.hwnd = None
        self.stop_event = threading.Event()
        self.threads = []
        self.running = False

    def set_hwnd(self, hwnd):
        self.hwnd = hwnd

    def start(self, configs, stop_image_path="stop.png"):
        if self.running:
            logger.warning("核心已在运行中")
            return False
        if not self.hwnd or not win32gui.IsWindow(self.hwnd):
            logger.error("无效窗口句柄")
            return False
        self.stop_event.clear()
        self.threads = []

        start_screenshot_updater(self.hwnd, interval=0.05)

        for cfg in configs:
            t = threading.Thread(target=key_worker,
                                 args=(self.hwnd, cfg['region'], cfg['template_path'],
                                       cfg['key_char'], cfg['speed'], self.stop_event),
                                 daemon=True)
            t.start()
            self.threads.append(t)

        if os.path.exists(_resolve_image_path(stop_image_path)):
            monitor = threading.Thread(target=stop_monitor, args=(stop_image_path, self.stop_event), daemon=True)
            monitor.start()
            self.threads.append(monitor)
        else:
            logger.warning("未找到 stop.png，停止监控功能禁用")

        self.running = True
        logger.info("演奏已开始")
        return True

    def stop(self):
        if not self.running:
            return
        self.stop_event.set()
        for t in self.threads:
            t.join(timeout=2)
        self.threads.clear()
        stop_screenshot_updater()
        self.running = False
        logger.info("演奏已停止")