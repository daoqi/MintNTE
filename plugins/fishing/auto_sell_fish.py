# plugins/fishing/auto_sell_fish.py
import time, sys, os, cv2, numpy as np, win32gui
from PIL import ImageGrab
from utils.path_utils import resource_path
from utils.image_loader import load_template

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path: sys.path.insert(0, BASE_DIR)

from Module.click.NET_click import simulate_mouse_click_relative, send_key_press
import ui.services.logui as logui

IMG_DIR = os.path.join("plugins", "fishing", "fishingimages", "buy_bait")
PATH_SEA_FISHER = resource_path(os.path.join(IMG_DIR, "sea_fisher.bmp"))
PATH_FISH_MARKET = resource_path(os.path.join(IMG_DIR, "fish_market.bmp"))
PATH_HUOBI = resource_path(os.path.join(IMG_DIR, "huobi.png"))
PATH_CONFIRM_SALE = resource_path(os.path.join(IMG_DIR, "confirm_sale.bmp"))
PATH_FISH_CABIN_ENTER = resource_path(os.path.join(IMG_DIR, "fish_cabin_enter.bmp"))
PATH_FISH_CABIN = resource_path(os.path.join(IMG_DIR, "fish_cabin.bmp"))
PATH_ONE_CLICK_SELL = resource_path(os.path.join(IMG_DIR, "one_click_sell.bmp"))
PATH_ONE_CLICK_CONFIRM = resource_path(os.path.join(IMG_DIR, "one_click_sell_confirm.bmp"))
PATH_SELL_SUCCESS = resource_path(os.path.join(IMG_DIR, "sell_success.bmp"))
PATH_INCOME_DETAIL = resource_path(os.path.join(IMG_DIR, "income_detail.bmp"))
PATH_CLICK_BLANK_CLOSE = resource_path(os.path.join(IMG_DIR, "click_blank_close_ui.bmp"))
PATH_ROTTEN_FISH = resource_path(os.path.join(IMG_DIR, "rotten_fish.bmp"))
MATCH_THRESH = 0.7

def find_in_region(hwnd, template, left, top, right, bottom, threshold=MATCH_THRESH):
    if not hwnd or not win32gui.IsWindow(hwnd): return False
    client_lt = win32gui.ClientToScreen(hwnd, (0, 0))
    x1, y1 = client_lt[0] + left, client_lt[1] + top
    x2, y2 = client_lt[0] + right, client_lt[1] + bottom
    try:
        img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
        tpl = load_template(template)
        if tpl is None: return False
        res = cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        return max_val >= threshold
    except: return False

def click_region_center(hwnd, left, top, right, bottom):
    simulate_mouse_click_relative(hwnd, (left + right) // 2, (top + bottom) // 2)

def find_template_and_click(hwnd, template, left, top, right, bottom, threshold=MATCH_THRESH):
    if not hwnd or not win32gui.IsWindow(hwnd): return False
    from Module.capture.frame_capture import capture_frame
    frame = capture_frame(hwnd)
    if frame is None: return False
    h, w = frame.shape[:2]
    x1, y1 = max(0, min(left, w-1)), max(0, min(top, h-1))
    x2, y2 = max(x1+1, min(right, w)), max(y1+1, min(bottom, h))
    if x2-x1 < 10 or y2-y1 < 10: return False
    roi = frame[y1:y2, x1:x2]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    tpl = load_template(template)
    if tpl is None: return False
    res = cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val < threshold: return False
    tpl_h, tpl_w = tpl.shape
    center_x = x1 + max_loc[0] + tpl_w // 2
    center_y = y1 + max_loc[1] + tpl_h // 2
    simulate_mouse_click_relative(hwnd, center_x, center_y)
    return True

def sell_fish(hwnd):
    if not win32gui.IsWindow(hwnd): return False
    def press_key(vk, dur=0.1): send_key_press(hwnd, vk, dur)

    logui.info("===== 开始自动卖鱼 =====")
    max_q_retries = 3; entered = False
    for attempt in range(1, max_q_retries + 1):
        logui.info(f"按 Q 尝试进入卖鱼界面 ({attempt}/{max_q_retries})")
        press_key(0x51); time.sleep(2.0)
        if find_in_region(hwnd, PATH_SEA_FISHER, 96, 2, 295, 143) or find_in_region(hwnd, PATH_FISH_MARKET, 245, 231, 420, 322):
            entered = True; break
        else:
            logui.warning(f"未检测到卖鱼界面 (尝试 {attempt}/{max_q_retries})"); press_key(0x1B); time.sleep(0.5)
    if not entered: logui.error("无法进入卖鱼界面"); return False
    logui.info("已进入卖鱼界面")

    high_price_regions = [
        (830, 397, 1128, 479, "高性价比鱼1"),
        (778, 573, 1114, 660, "高性价比鱼2"),
        (758, 755, 1128, 833, "高性价比鱼3"),
    ]
    for left, top, right, bottom, name in high_price_regions:
        if find_in_region(hwnd, PATH_HUOBI, left, top, right, bottom):
            logui.info(f"发现 {name}")
            find_template_and_click(hwnd, PATH_HUOBI, left, top, right, bottom)
            time.sleep(1.5)
            for retry in range(2):
                if find_in_region(hwnd, PATH_CONFIRM_SALE, 1430, 901, 1642, 1010):
                    click_region_center(hwnd, 1430, 901, 1642, 1010)
                    logui.info("已卖出"); time.sleep(1.5); break
                else:
                    if retry == 0:
                        logui.warning("确认按钮未出现，重新点击鱼图标")
                        find_template_and_click(hwnd, PATH_HUOBI, left, top, right, bottom)
                        time.sleep(1.5)
                    else:
                        logui.error(f"{name} 卖出失败，按 ESC 取消"); press_key(0x1B); time.sleep(1.0)
        else: logui.info(f"{name} 不存在或已卖完")

    logui.info("进入普通鱼舱")
    if not find_in_region(hwnd, PATH_FISH_CABIN_ENTER, 55, 343, 250, 495):
        logui.error("找不到进入普通鱼舱的入口"); press_key(0x1B); return False
    click_region_center(hwnd, 55, 343, 250, 495)
    time.sleep(1.5)

    rotten_count = 0; start = time.time(); cabin_entered = False
    while time.time() - start < 15:
        if find_in_region(hwnd, PATH_ROTTEN_FISH, 764, 418, 1177, 528):
            rotten_count += 1
            logui.info(f"检测到发臭鱼 (第{rotten_count}次)，按 ESC"); press_key(0x1B); time.sleep(1.5)
            if rotten_count >= 3: logui.warning("连续发臭鱼，可能卡住，强行继续"); break
            continue
        rotten_count = 0
        if find_in_region(hwnd, PATH_FISH_CABIN, 249, 211, 419, 327):
            cabin_entered = True; logui.info("已进入普通卖鱼界面"); break
        time.sleep(0.5)
    if not cabin_entered: logui.error("进入普通卖鱼界面超时"); press_key(0x1B); return False

    sold = False
    for attempt in range(2):
        if not find_in_region(hwnd, PATH_ONE_CLICK_SELL, 985, 914, 1154, 1021):
            logui.warning("未找到一键出售按钮"); time.sleep(1); continue
        click_region_center(hwnd, 985, 914, 1154, 1021)
        logui.info("已点击一键出售"); time.sleep(1.5)
        confirm_clicked = False; start = time.time()
        while time.time() - start < 5:
            if find_in_region(hwnd, PATH_ROTTEN_FISH, 764, 418, 1177, 528): press_key(0x1B); time.sleep(1.0)
            if find_in_region(hwnd, PATH_ONE_CLICK_CONFIRM, 1079, 649, 1264, 783):
                click_region_center(hwnd, 1079, 649, 1264, 783)
                confirm_clicked = True; logui.info("已确认出售"); break
            time.sleep(0.5)
        if confirm_clicked: sold = True; break
        else: logui.warning("确认按钮未找到，重试一键出售")
    if not sold: logui.error("一键出售失败"); press_key(0x1B); return False

    logui.info("等待出售结果..."); start = time.time(); result_ok = False
    while time.time() - start < 10:
        if find_in_region(hwnd, PATH_ROTTEN_FISH, 764, 418, 1177, 528): press_key(0x1B); time.sleep(0.5)
        if find_in_region(hwnd, PATH_SELL_SUCCESS, 649, 582, 797, 639) or \
           find_in_region(hwnd, PATH_INCOME_DETAIL, 890, 789, 1037, 842) or \
           find_in_region(hwnd, PATH_CLICK_BLANK_CLOSE, 819, 920, 1096, 1004):
            result_ok = True; logui.info("出售完成，按 ESC 关闭"); press_key(0x1B); time.sleep(1.0); break
        time.sleep(0.5)
    if not result_ok: logui.warning("出售结果检测超时，尝试强制退出")

    if find_in_region(hwnd, PATH_SEA_FISHER, 96, 2, 295, 143): press_key(0x1B); time.sleep(1.5)
    logui.info("===== 卖鱼流程结束 ====="); return True