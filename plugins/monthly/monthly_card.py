# plugins/monthly/monthly_card.py
import os, time, threading, cv2, numpy as np, win32gui
from PIL import ImageGrab
from utils.path_utils import resource_path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMG_DIR = os.path.join(BASE_DIR, "plugins", "monthly", "image")
PATH_MONTHLY_CARD = os.path.join(IMG_DIR, "monthly_card.bmp")
PATH_CLICK_BLANK_CLOSE = os.path.join(IMG_DIR, "click_blank_close.bmp")
MATCH_THRESH = 0.7

from Module.click.NET_click import simulate_mouse_click_relative

def find_image_in_region(hwnd, template_path, left, top, right, bottom, threshold=MATCH_THRESH):
    if not hwnd or not win32gui.IsWindow(hwnd):
        return False
    try:
        client_lt = win32gui.ClientToScreen(hwnd, (0, 0))
        x1, y1 = client_lt[0] + left, client_lt[1] + top
        x2, y2 = client_lt[0] + right, client_lt[1] + bottom
        img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
        template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
        if template is None:
            return False
        res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        return max_val >= threshold
    except:
        return False

def monthly_card_worker(stop_event, hwnd_func):
    while not stop_event.is_set():
        try:
            hwnd = hwnd_func()
            if not hwnd or not win32gui.IsWindow(hwnd):
                time.sleep(0.5)
                continue
            if find_image_in_region(hwnd, PATH_MONTHLY_CARD, 844, 953, 1082, 1000):
                simulate_mouse_click_relative(hwnd, 1307, 933)
                time.sleep(0.5)
                continue
            if find_image_in_region(hwnd, PATH_CLICK_BLANK_CLOSE, 839, 930, 1083, 995):
                simulate_mouse_click_relative(hwnd, 1307, 933)
                time.sleep(0.5)
                continue
            time.sleep(0.5)
        except:
            time.sleep(1)