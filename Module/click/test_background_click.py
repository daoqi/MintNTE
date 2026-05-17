# test_enhanced_click.py
import time
import win32gui
import win32api
import win32con

def simulate_click_enhanced(hwnd, x, y, hold_seconds=0.05):
    """
    增强的后台点击：先移动鼠标，发送激活/光标消息，再同步按下/弹起
    """
    # 构造 lParam (坐标)
    lparam = win32api.MAKELONG(x, y)

    # 1. 发送鼠标移动消息，让 UI 感知悬停
    win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
    time.sleep(0.01)

    # 2. 发送鼠标激活和光标设置消息（模拟更真实的激活过程）
    win32gui.SendMessage(hwnd, win32con.WM_MOUSEACTIVATE, hwnd,
                         win32api.MAKELONG(win32con.HTCLIENT, win32con.WM_LBUTTONDOWN))
    win32gui.SendMessage(hwnd, win32con.WM_SETCURSOR, 0,
                         win32api.MAKELONG(win32con.HTCLIENT, win32con.WM_MOUSEMOVE))

    # 3. 同步发送按下消息
    win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
    time.sleep(hold_seconds)   # 按住时间

    # 4. 同步发送弹起消息
    win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)

def main():
    hwnd = 330674  # 句柄
    x, y = 321,247

    # 验证句柄是否有效
    if not win32gui.IsWindow(hwnd):
        print("句柄无效，请检查窗口是否仍然存在")
        return

    print(f"目标窗口句柄: {hwnd}")
    print(f"点击坐标 (客户区): ({x}, {y})")
    print("发送增强后台点击...")
    simulate_click_enhanced(hwnd, x, y, hold_seconds=0.05)
    print("点击完成，请观察游戏是否跳转")

if __name__ == "__main__":
    main()