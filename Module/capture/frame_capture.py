# Module/capture/frame_capture.py
import sys
import os
import cv2
import numpy as np
import win32gui
import win32ui
import win32con
import ctypes
from PIL import Image

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ui.services.capture_config import get_capture_mode

def resource_path(relative_path):
    """获取资源绝对路径，兼容开发环境和PyInstaller打包"""
    try:
        base = sys._MEIPASS
    except Exception:
        base = os.path.abspath(".")
    return os.path.join(base, relative_path)

# ---------- 方式1：PrintWindow ----------
def _capture_printwindow(hwnd):
    if not win32gui.IsWindow(hwnd):
        return None
    rect = win32gui.GetClientRect(hwnd)
    width = rect[2] - rect[0]
    height = rect[3] - rect[1]
    if width <= 0 or height <= 0:
        return None

    try:
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(bitmap)

        success = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)
        if not success:
            win32gui.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)
            return None

        bits = bitmap.GetBitmapBits(True)
        img = Image.frombuffer("RGB", (width, height), bits, "raw", "BGRX", 0, 1)
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        win32gui.DeleteObject(bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)
        return frame
    except Exception as e:
        # 静默失败，返回 None
        return None

# ---------- 方式2：dxcam ----------
dxcam_available = False
try:
    import dxcam
    dxcam_available = True
except ImportError:
    pass

_dxcam_cameras = {}  # 按句柄存储相机对象

def _capture_dxcam(hwnd):
    global _dxcam_cameras
    if not dxcam_available:
        return _capture_printwindow(hwnd)
    if not win32gui.IsWindow(hwnd):
        return None

    try:
        # 获取或创建相机
        if hwnd not in _dxcam_cameras:
            # 需要窗口可见，所以先置顶一下（已在统一接口外调用时处理）
            rect = win32gui.GetClientRect(hwnd)
            pt = win32gui.ClientToScreen(hwnd, (0, 0))
            region = (pt[0], pt[1], pt[0] + rect[2], pt[1] + rect[3])
            cam = dxcam.create(output_color="BGR", region=region)
            cam.start(target_fps=60, video_mode=True)
            _dxcam_cameras[hwnd] = cam
        frame = _dxcam_cameras[hwnd].get_latest_frame()
        if frame is None:
            return _capture_printwindow(hwnd)
        return frame
    except Exception:
        # dxcam 出错时回退到 PrintWindow
        return _capture_printwindow(hwnd)

# ---------- 方式3：WGC ----------
wgc_available = False
try:
    from windows_capture import WindowsCapture, Frame, InternalCaptureControl
    wgc_available = True
except ImportError:
    pass

_wgc_captures = {}

def _capture_wgc(hwnd):
    global _wgc_captures
    if not wgc_available:
        return _capture_printwindow(hwnd)
    if not win32gui.IsWindow(hwnd):
        return None

    try:
        if hwnd not in _wgc_captures:
            capture = WindowsCapture(
                cursor_capture=False,
                draw_border=False,
                monitor_index=None,
                window_name=None,
                window_hwnd=hwnd,
            )
            # 需要存储最新帧，简单起见用闭包
            latest_frame = None

            @capture.event
            def on_frame_arrived(frame: Frame, capture_control: InternalCaptureControl):
                nonlocal latest_frame
                arr = np.array(frame.frame_buffer)
                if arr.shape[2] == 4:
                    arr = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
                latest_frame = arr

            @capture.event
            def on_closed():
                pass

            capture.start_free_threaded()
            _wgc_captures[hwnd] = (capture, lambda: latest_frame)

        capture, get_frame = _wgc_captures[hwnd]
        frame = get_frame()
        if frame is None:
            return _capture_printwindow(hwnd)
        return frame
    except Exception:
        return _capture_printwindow(hwnd)

# ---------- 统一接口 ----------
def capture_frame(hwnd):
    """根据全局配置选择截图方式，返回 BGR numpy 数组"""
    if not win32gui.IsWindow(hwnd):
        return None
    mode = get_capture_mode()
    if mode == 1:   # dxcam
        return _capture_dxcam(hwnd)
    elif mode == 2: # WGC
        return _capture_wgc(hwnd)
    else:           # 0 或未知
        return _capture_printwindow(hwnd)