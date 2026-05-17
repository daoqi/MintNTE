# core/Fortissimo/dxcam_capture.py
import win32gui
import dxcam
import time
import logging

logger = logging.getLogger("Fortissimo.DXCam")

_camera = None
_last_rect = None

def start_dxcam(hwnd, target_fps=240):
    """初始化DXcam，捕获指定窗口区域（屏幕坐标）"""
    global _camera, _last_rect
    if not win32gui.IsWindow(hwnd):
        logger.error("无效窗口句柄")
        return False
    rect = win32gui.GetWindowRect(hwnd)
    left, top, right, bottom = rect
    region = (left, top, right, bottom)
    try:
        _camera = dxcam.create(output_color="BGR")
        _camera.start(target_fps=target_fps, region=region)
        _last_rect = region
        logger.info(f"DXcam 已启动，区域 {region}")
        time.sleep(0.1)
        return True
    except Exception as e:
        logger.error(f"DXcam 启动失败: {e}")
        return False

def get_latest_frame():
    """获取最新一帧（BGR）"""
    global _camera
    if _camera is None:
        return None
    return _camera.get_latest_frame()

def stop_dxcam():
    global _camera
    if _camera is not None:
        _camera.stop()
        _camera = None
        logger.info("DXcam 已停止")

def update_region(hwnd):
    """窗口移动时更新捕获区域"""
    global _camera, _last_rect
    if _camera is None:
        return
    rect = win32gui.GetWindowRect(hwnd)
    if rect != _last_rect:
        _camera.stop()
        _camera.start(target_fps=240, region=rect)
        _last_rect = rect
        logger.info(f"DXcam 区域更新为 {rect}")