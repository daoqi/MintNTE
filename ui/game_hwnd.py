# Module/Hwnd/game_hwnd.py
import win32gui

_locked_hwnd = None

def set_locked_hwnd(hwnd):
    global _locked_hwnd
    _locked_hwnd = hwnd

def clear_locked_hwnd():
    global _locked_hwnd
    _locked_hwnd = None

def get_game_hwnd():
    return _locked_hwnd

def get_window_title(hwnd):
    try:
        return win32gui.GetWindowText(hwnd)
    except:
        return ""