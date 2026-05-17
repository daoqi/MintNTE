# plugins/fishing/throw_rod.py
import os, sys, time, cv2, numpy as np, win32gui
from utils.path_utils import resource_path
from utils.image_loader import load_template

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path: sys.path.insert(0, BASE_DIR)

from Module.Hwnd.game_hwnd import get_game_hwnd
from Module.click.NET_click import send_key_down, send_key_up
import ui.services.logui as logui

IMG_DIR = os.path.join("plugins", "fishing", "fishingimages")
PATH_FISH_HOOK = resource_path(os.path.join(IMG_DIR, "fish_hook.png"))
PATH_ENDURANCE_FISH = resource_path(os.path.join(IMG_DIR, "endurance_fish.bmp"))
MATCH_THRESH = 0.7

IMG_BUY = os.path.join(IMG_DIR, "buy_bait")
PATH_CABIN_FULL = resource_path(os.path.join(IMG_BUY, "fish_cabin_full.bmp"))
PATH_NEED_BAIT = resource_path(os.path.join(IMG_BUY, "need_equip_bait.bmp"))

TIMEOUT_FIND_HOOK = 35
TIMEOUT_FISHING = 60

def fake_activate(hwnd):
    try: win32gui.SendMessage(hwnd, 0x0006, 1, 0)
    except: pass

def press_key(hwnd, vk_code, duration=0.05):
    fake_activate(hwnd)
    send_key_down(hwnd, vk_code)
    time.sleep(duration)
    send_key_up(hwnd, vk_code)

def find_image_in_region(hwnd, template_path, left, top, right, bottom, threshold=MATCH_THRESH):
    if not win32gui.IsWindow(hwnd): return None
    from plugins.fishing.fishing_utils import capture_window_to_cv
    img = capture_window_to_cv(hwnd)
    if img is None: return None
    h, w = img.shape[:2]
    x1, y1 = max(0, min(left, w-1)), max(0, min(top, h-1))
    x2, y2 = max(x1+1, min(right, w)), max(y1+1, min(bottom, h))
    if x2-x1 < 10 or y2-y1 < 10: return None
    roi = img[y1:y2, x1:x2]
    tpl = load_template(template_path)
    if tpl is None: return None
    res = cv2.matchTemplate(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val >= threshold:
        th, tw = tpl.shape
        return (max_loc[0] + tw//2 + x1, max_loc[1] + th//2 + y1)
    return None

def check_cabin_full(hwnd):
    return find_image_in_region(hwnd, PATH_CABIN_FULL, 668, 513, 903, 565) is not None

def check_need_bait(hwnd):
    return find_image_in_region(hwnd, PATH_NEED_BAIT, 779, 512, 917, 567) is not None

def throw_rod(stop_event=None, options=None):
    if options is None: options = {}
    logui.info("当前在钓鱼界面全速后台钓鱼")

    start = time.time()
    while True:
        if stop_event and stop_event.is_set(): return False
        if time.time() - start > TIMEOUT_FIND_HOOK:
            logui.warning(f"等待鱼钩超时({TIMEOUT_FIND_HOOK}s)"); return False
        hwnd = get_game_hwnd()
        if not hwnd or not win32gui.IsWindow(hwnd): time.sleep(0.5); continue
        if find_image_in_region(hwnd, PATH_FISH_HOOK, 1731, 925, 1818, 1012):
            logui.info("检测到鱼钩，开始持续按F"); break
        time.sleep(1.5)

    start = time.time()
    cabin_retry = 0
    bait_retry = 0
    while True:
        if stop_event and stop_event.is_set():
            send_key_up(hwnd, 0x46); return False
        if time.time() - start > TIMEOUT_FISHING:
            logui.warning(f"抛竿超时({TIMEOUT_FISHING}s)"); send_key_up(hwnd, 0x46); return False
        hwnd = get_game_hwnd()
        if not hwnd or not win32gui.IsWindow(hwnd):
            logui.warning("窗口丢失，退出抛竿"); return False
        if find_image_in_region(hwnd, PATH_ENDURANCE_FISH, 478, 26, 591, 123):
            logui.info("检测到结束图标，停止按F"); return True
        cabin_full = check_cabin_full(hwnd)
        need_bait = check_need_bait(hwnd)
        if cabin_full:
            logui.info("鱼舱满了！")
            if options.get("cabin_full_action", 0) == 0:
                logui.info("用户选择关机"); os.system("shutdown /s /t 60"); send_key_up(hwnd, 0x46); return False
            else:
                cabin_retry += 1
                if cabin_retry > 3:
                    logui.error("连续3次卖鱼后鱼舱仍满，请检查游戏界面或手动处理"); send_key_up(hwnd, 0x46); return False
                logui.info("清空鱼舱继续钓鱼")
                from plugins.fishing.auto_sell_fish import sell_fish
                sell_fish(hwnd)
                time.sleep(3)
                continue
        else: cabin_retry = 0
        if need_bait:
            logui.info("鱼饵不足！")
            if options.get("bait_low_action", 0) == 0:
                logui.info("用户选择关机"); os.system("shutdown /s /t 60"); send_key_up(hwnd, 0x46); return False
            else:
                bait_retry += 1
                if bait_retry > 3:
                    logui.error("连续3次购买鱼饵后仍显示鱼饵不足，请检查游戏界面或手动处理"); send_key_up(hwnd, 0x46); return False
                logui.info("自动购买鱼饵")
                from plugins.fishing.auto_buy_bait import auto_buy_bait
                auto_buy_bait()
                time.sleep(3)
                continue
        else: bait_retry = 0
        press_key(hwnd, 0x46, duration=0.05)
        time.sleep(0.1)