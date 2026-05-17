# plugins/auto_reconnect/auto_reconnect.py
import os, sys, cv2, numpy as np, win32gui, win32ui, win32con, ctypes
from PIL import Image
from utils.path_utils import resource_path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path: sys.path.insert(0, BASE_DIR)

from Module.click.NET_click import simulate_mouse_click_relative
from Module.Hwnd.game_hwnd import get_game_hwnd

def capture_window_region(hwnd, region=None):
    if not win32gui.IsWindow(hwnd): return None
    rect = win32gui.GetClientRect(hwnd)
    left, top, right, bottom = rect
    w, h = right - left, bottom - top
    if w <= 0 or h <= 0: return None
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
    save_dc.SelectObject(bitmap)
    success = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)
    if not success:
        save_dc.DeleteDC(); mfc_dc.DeleteDC(); win32gui.ReleaseDC(hwnd, hwnd_dc)
        return None
    bits = bitmap.GetBitmapBits(True)
    img = Image.frombuffer("RGB", (w, h), bits, "raw", "BGRX", 0, 1)
    opencv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    win32gui.DeleteObject(bitmap.GetHandle())
    save_dc.DeleteDC(); mfc_dc.DeleteDC(); win32gui.ReleaseDC(hwnd, hwnd_dc)
    if region:
        x1, y1, x2, y2 = region
        x1 = max(0, min(x1, w-1)); y1 = max(0, min(y1, h-1))
        x2 = max(x1+1, min(x2, w)); y2 = max(y1+1, min(y2, h))
        opencv_img = opencv_img[y1:y2, x1:x2]
    return opencv_img

def find_image_on_window(hwnd, template_path, region=None, threshold=0.8):
    img = capture_window_region(hwnd, region)
    if img is None: return False, None
    template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
    if template is None: return False, None
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    result = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    found = max_val >= threshold
    if found:
        h_t, w_t = template.shape
        center_x = max_loc[0] + w_t // 2
        center_y = max_loc[1] + h_t // 2
        if region:
            center_x += region[0]
            center_y += region[1]
        return True, (center_x, center_y)
    return False, None

def check_and_click_enter_game():
    hwnd = get_game_hwnd()
    if not hwnd:
        print("未找到游戏窗口"); return False

    template_path = resource_path(os.path.join("plugins", "auto_reconnect", "auto_reconnect_IMG", "enter_game.png"))
    if not os.path.exists(template_path):
        print(f"模板图片不存在: {template_path}"); return False

    found, _ = find_image_on_window(hwnd, template_path, region=(42, 50, 147, 180), threshold=0.8)
    if found:
        # 点击固定坐标 (960, 930)
        simulate_mouse_click_relative(hwnd, 960, 930)
        print("检测到重连界面，点击固定坐标 (960, 930)")
        return True
    else:
        return False