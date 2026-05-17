# Module/Hwnd/game_hwnd.py
import win32gui
import win32con
from PyQt5.QtCore import QTimer

_locked_hwnd = None
_restore_timer = None

def set_locked_hwnd(hwnd):
    global _locked_hwnd, _restore_timer
    _locked_hwnd = hwnd
    if _restore_timer is not None:
        _restore_timer.stop()
        _restore_timer.deleteLater()
        _restore_timer = None
    if hwnd:
        # 主线程安全定时器，只恢复最小化，不抢焦点
        def _check():
            if win32gui.IsWindow(_locked_hwnd) and win32gui.IsIconic(_locked_hwnd):
                win32gui.ShowWindow(_locked_hwnd, win32con.SW_RESTORE)
        _restore_timer = QTimer()
        _restore_timer.timeout.connect(_check)
        _restore_timer.start(500)

def clear_locked_hwnd():
    global _locked_hwnd, _restore_timer
    _locked_hwnd = None
    if _restore_timer:
        _restore_timer.stop()
        _restore_timer.deleteLater()
        _restore_timer = None

def get_game_hwnd():
    if _locked_hwnd and win32gui.IsWindow(_locked_hwnd):
        return _locked_hwnd
    return None