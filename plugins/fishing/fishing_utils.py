# plugins/fishing/fishing_utils.py
import cv2
import numpy as np
import win32gui
import win32ui
import ctypes
from PIL import Image
import time

def capture_window_to_cv(hwnd):
    """后台截图：使用 PrintWindow 获取窗口客户区，返回 BGR 格式的 numpy 数组。"""
    if not win32gui.IsWindow(hwnd):
        return None
    rect = win32gui.GetClientRect(hwnd)
    left, top, right, bottom = rect
    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        return None

    hwnd_dc = win32gui.GetWindowDC(hwnd)
    if not hwnd_dc:
        return None

    try:
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
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
    except Exception:
        return None
    finally:
        try:
            win32gui.DeleteObject(bitmap.GetHandle())
        except:
            pass
        try:
            save_dc.DeleteDC()
        except:
            pass
        try:
            mfc_dc.DeleteDC()
        except:
            pass
        try:
            win32gui.ReleaseDC(hwnd, hwnd_dc)
        except:
            pass