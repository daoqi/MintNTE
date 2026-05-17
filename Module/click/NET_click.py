# Module/click/NET_click.py
import win32gui
import win32con
import win32api
import time
import ctypes
from ctypes import wintypes, byref, pointer, c_ulong

# ---------- 常量 ----------
WM_ACTIVATE = 0x0006
WA_ACTIVE = 1
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
KEYEVENTF_KEYDOWN = 0x0000
KEYEVENTF_KEYUP = 0x0002
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101

# ---------- 结构体定义 ----------
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(c_ulong)),
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(c_ulong)),
    ]

class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUT_UNION),
    ]

# ---------- 鼠标辅助 ----------
def _send_mouse_input(dx, dy, dwFlags, data=0):
    mi = MOUSEINPUT()
    mi.dx = dx
    mi.dy = dy
    mi.mouseData = data
    mi.dwFlags = dwFlags
    mi.time = 0
    mi.dwExtraInfo = pointer(c_ulong(0))
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.union.mi = mi
    ctypes.windll.user32.SendInput(1, byref(inp), ctypes.sizeof(inp))


def send_click_event(duration=0.2):
    """在当前光标位置发送鼠标左键点击（按下+释放），duration 为按下持续秒数"""
    down = INPUT()
    down.type = INPUT_MOUSE
    down.union.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
    ctypes.windll.user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))

    time.sleep(duration)

    up = INPUT()
    up.type = INPUT_MOUSE
    up.union.mi.dwFlags = MOUSEEVENTF_LEFTUP
    ctypes.windll.user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))


def click_screen_point(screen_x, screen_y, duration=0.2, pre_delay=0.05):
    """瞬移鼠标到屏幕坐标点击，然后移回原位，pre_delay 为移动后的等待时间"""
    orig_x, orig_y = win32gui.GetCursorPos()
    ctypes.windll.user32.SetCursorPos(screen_x, screen_y)
    time.sleep(pre_delay)               # 等待系统识别新位置
    send_click_event(duration)
    ctypes.windll.user32.SetCursorPos(orig_x, orig_y)


def bring_window_to_top_force(hwnd):
    """强制将窗口置顶并设为前台（UE5需要）"""
    if not win32gui.IsWindow(hwnd):
        return
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
    time.sleep(0.05)
    win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(0.05)


def simulate_mouse_click_relative(hwnd, client_x, client_y, duration=0.2, pre_delay=0.05):
    """
    UE5 前台点击：强制置顶 → 计算屏幕坐标 → 瞬移 → 等待 pre_delay 秒 → 点击（duration 秒按下） → 移回
    duration: 鼠标按下的持续时间（秒），推荐 0.15~0.3
    pre_delay: 移动后到按下前的停留时间（秒），推荐 0.03~0.1
    """
    if not win32gui.IsWindow(hwnd):
        return
    bring_window_to_top_force(hwnd)
    screen_x, screen_y = win32gui.ClientToScreen(hwnd, (client_x, client_y))
    click_screen_point(screen_x, screen_y, duration, pre_delay)


# ---------- 键盘前台按键（解决 UE5 后台按键无效的问题） ----------
def send_key_press(hwnd, vk_code, duration=0.1):
    """前台键盘按键：先强制置顶窗口，然后发送键盘按下 + 释放"""
    if not win32gui.IsWindow(hwnd):
        return
    bring_window_to_top_force(hwnd)
    time.sleep(0.02)
    key_down = INPUT()
    key_down.type = INPUT_KEYBOARD
    key_down.union.ki.wVk = vk_code
    key_down.union.ki.dwFlags = KEYEVENTF_KEYDOWN
    ctypes.windll.user32.SendInput(1, ctypes.byref(key_down), ctypes.sizeof(INPUT))

    time.sleep(duration)

    key_up = INPUT()
    key_up.type = INPUT_KEYBOARD
    key_up.union.ki.wVk = vk_code
    key_up.union.ki.dwFlags = KEYEVENTF_KEYUP
    ctypes.windll.user32.SendInput(1, ctypes.byref(key_up), ctypes.sizeof(INPUT))


# ---------- 后台键盘（保留，供特殊场景） ----------
def send_key_down(hwnd, vk_code):
    if win32gui.IsWindow(hwnd):
        win32gui.PostMessage(hwnd, WM_KEYDOWN, vk_code, 0)

def send_key_up(hwnd, vk_code):
    if win32gui.IsWindow(hwnd):
        win32gui.PostMessage(hwnd, WM_KEYUP, vk_code, 0)


def fake_activate_window(hwnd):
    if win32gui.IsWindow(hwnd):
        win32gui.SendMessage(hwnd, WM_ACTIVATE, WA_ACTIVE, 0)

def bring_window_to_top(hwnd):
    bring_window_to_top_force(hwnd)


if __name__ == "__main__":
    print("NET_click 模块已加载 ")