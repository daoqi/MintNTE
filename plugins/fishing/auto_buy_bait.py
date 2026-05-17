# plugins/fishing/auto_buy_bait.py
import time
import sys
import os
import cv2
import numpy as np
import win32gui
from utils.path_utils import resource_path
from utils.image_loader import load_template

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from Module.Hwnd.game_hwnd import get_game_hwnd
from Module.click.NET_click import send_key_press, simulate_mouse_click_relative
from Module.capture.frame_capture import capture_frame
import ui.services.logui as logui

IMG_DIR = os.path.join("plugins", "fishing", "fishingimages", "buy_bait")

PATH_TACKLE_SHOP_BMP = resource_path(os.path.join(IMG_DIR, "tackle_shop.bmp"))
PATH_TACKLE_SHOP_PNG = resource_path(os.path.join(IMG_DIR, "tackle_shop.png"))
PATH_UNIVERSAL_BAIT = resource_path(os.path.join(IMG_DIR, "universal_bait.bmp"))
PATH_MAX_BAIT = resource_path(os.path.join(IMG_DIR, "max_bait.bmp"))
PATH_BUY_BAIT = resource_path(os.path.join(IMG_DIR, "buy_bait.bmp"))
PATH_CONFIRM_BUY = resource_path(os.path.join(IMG_DIR, "confirm_buy_bait.bmp"))
PATH_GET_BAIT = resource_path(os.path.join(IMG_DIR, "get_bait.bmp"))
PATH_CHANGE_BAIT = resource_path(os.path.join(IMG_DIR, "change_bait.bmp"))
PATH_BUY_FISH_BAIT = resource_path(os.path.join(IMG_DIR, "buy_fish_bait.bmp"))

MATCH_THRESH = 0.7


def find_in_region(hwnd, template, left, top, right, bottom, threshold=MATCH_THRESH):
    if not hwnd or not win32gui.IsWindow(hwnd):
        return False
    frame = capture_frame(hwnd)
    if frame is None:
        return False
    h, w = frame.shape[:2]
    x1, y1 = max(0, min(left, w - 1)), max(0, min(top, h - 1))
    x2, y2 = max(x1 + 1, min(right, w)), max(y1 + 1, min(bottom, h))
    if x2 <= x1 or y2 <= y1:
        return False
    roi = frame[y1:y2, x1:x2]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    tpl = load_template(template)
    if tpl is None:
        return False
    res = cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    return max_val >= threshold


def find_template_and_click(hwnd, template, left, top, right, bottom,
                            threshold=MATCH_THRESH, click_duration=0.25, pre_delay=0.08):
    if not hwnd or not win32gui.IsWindow(hwnd):
        return False
    frame = capture_frame(hwnd)
    if frame is None:
        return False
    h, w = frame.shape[:2]
    x1, y1 = max(0, min(left, w - 1)), max(0, min(top, h - 1))
    x2, y2 = max(x1 + 1, min(right, w)), max(y1 + 1, min(bottom, h))
    if x2 <= x1 or y2 <= y1:
        return False
    roi = frame[y1:y2, x1:x2]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    tpl = load_template(template)
    if tpl is None:
        return False
    res = cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val < threshold:
        return False
    tpl_h, tpl_w = tpl.shape
    center_x = x1 + max_loc[0] + tpl_w // 2
    center_y = y1 + max_loc[1] + tpl_h // 2
    simulate_mouse_click_relative(hwnd, center_x, center_y, duration=click_duration, pre_delay=pre_delay)
    return True


# ---------- 进入渔具商店 ----------
def enter_tackle_shop():
    hwnd = get_game_hwnd()
    if not hwnd:
        logui.error("未找到游戏窗口")
        return False

    def press_key(vk, dur=0.1):
        send_key_press(hwnd, vk, dur)

    logui.info("按 R 进入渔具商店")
    press_key(0x52)
    time.sleep(1.5)

    if not find_in_region(hwnd, PATH_TACKLE_SHOP_BMP, 25, 15, 286, 101) and \
       not find_in_region(hwnd, PATH_TACKLE_SHOP_PNG, 25, 15, 286, 101):
        logui.error("未进入渔具商店")
        press_key(0x1B)
        return False
    logui.info("已进入渔具商店")
    return True


# ---------- 核心购买（一次选择→拉满→购买→确认→获得）----------
def buy_bait_core():
    hwnd = get_game_hwnd()
    if not hwnd:
        logui.error("未找到游戏窗口")
        return False

    def press_key(vk, dur=0.1):
        send_key_press(hwnd, vk, dur)

    for attempt in range(1, 4):
        if find_template_and_click(hwnd, PATH_UNIVERSAL_BAIT, 29, 115, 682, 837):
            logui.info("选择万能鱼饵")
            time.sleep(1.0)
            break
        else:
            logui.info(f"未找到万能鱼饵 (第{attempt}次)")
            time.sleep(0.3)
    else:
        logui.error("找不到万能鱼饵")
        return False

    if find_template_and_click(hwnd, PATH_MAX_BAIT, 1761, 896, 1902, 1004):
        logui.info("拉满鱼饵数量")
        time.sleep(0.5)
    else:
        logui.warning("未找到拉满按钮，可能已最大")

    if not find_template_and_click(hwnd, PATH_BUY_BAIT, 1550, 1005, 1660, 1053,
                                   click_duration=0.3, pre_delay=0.1):
        logui.error("未找到购买按钮")
        return False
    logui.info("点击购买")
    time.sleep(1.5)

    if find_template_and_click(hwnd, PATH_CONFIRM_BUY, 1098, 687, 1222, 739,
                               click_duration=0.3, pre_delay=0.1):
        logui.info("确认购买")
        time.sleep(2.0)
    else:
        logui.warning("未找到确认购买按钮，可能无需确认")

    start = time.time()
    while time.time() - start < 5:
        if find_in_region(hwnd, PATH_GET_BAIT, 901, 450, 1012, 490):
            logui.info("获得鱼饵，按 ESC")
            press_key(0x1B)
            time.sleep(1.0)
            return True
        time.sleep(0.5)
    logui.warning("未检测到获得鱼饵，可能已结束")
    return True


# ---------- 退出渔具商店 ----------
def exit_tackle_shop():
    hwnd = get_game_hwnd()
    if not hwnd:
        return

    def press_key(vk, dur=0.1):
        send_key_press(hwnd, vk, dur)

    if find_in_region(hwnd, PATH_TACKLE_SHOP_BMP, 25, 15, 286, 101) or \
       find_in_region(hwnd, PATH_TACKLE_SHOP_PNG, 25, 15, 286, 101):
        logui.info("按 ESC 退出渔具商店")
        press_key(0x1B)
        time.sleep(2.0)
    else:
        logui.info("可能已退出渔具商店")


# ---------- 更换鱼饵 ----------
def change_bait():
    hwnd = get_game_hwnd()
    if not hwnd:
        logui.error("未找到游戏窗口")
        return False

    def press_key(vk, dur=0.1):
        send_key_press(hwnd, vk, dur)

    logui.info("===== 更换鱼饵 =====")
    time.sleep(1)
    press_key(0x45)
    time.sleep(2.0)

    if find_template_and_click(hwnd, PATH_CHANGE_BAIT, 1041, 618, 1325, 777):
        logui.info("点击更换鱼饵")
        time.sleep(1.0)
    elif find_in_region(hwnd, PATH_BUY_FISH_BAIT, 1130, 688, 1203, 724):
        logui.info("检测到购买鱼饵按钮，按 ESC 取消（可能已装备）")
        press_key(0x1B)
        time.sleep(0.5)
    else:
        logui.info("未找到更换或购买按钮，按 ESC 退出")
        press_key(0x1B)
        time.sleep(0.5)

    press_key(0x1B)
    time.sleep(0.5)
    logui.info("更换鱼饵完成")
    return True


# ---------- 完整一次购买+更换（智能模式调用）----------
def auto_buy_bait():
    if not enter_tackle_shop():
        return False
    if not buy_bait_core():
        return False
    exit_tackle_shop()
    change_bait()
    return True