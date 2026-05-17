# plugins/fishing/fishing_core.py
import os, sys, time, threading, traceback, datetime, win32gui, win32con, cv2, numpy as np
from utils.path_utils import resource_path
from utils.image_loader import load_template

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path: sys.path.insert(0, BASE_DIR)

import ui.services.logui as logui
from Module.click.NET_click import (
    send_key_down, send_key_up,
    simulate_mouse_click_relative
)
from plugins.fishing.auto_buy_bait import auto_buy_bait
from plugins.fishing.auto_sell_fish import sell_fish
from plugins.fishing.fishing_follow import start_follow
from plugins.fishing.fishing_utils import capture_window_to_cv
from Module.Hwnd.game_hwnd import set_locked_hwnd, get_game_hwnd
from plugins.auto_reconnect.auto_reconnect import check_and_click_enter_game

# ---------- 图片路径 ----------
IMG_DIR = os.path.join("plugins", "fishing", "fishingimages")
PATH_DIAOYU = resource_path(os.path.join(IMG_DIR, "diaoyu.png"))
PATH_KAISHIDIAOYU = resource_path(os.path.join(IMG_DIR, "kaishidiaoyu.png"))
PATH_DIANJIKONGBAI = resource_path(os.path.join(IMG_DIR, "dianjikongbai.png"))
PATH_PANDUANDIAOYU = resource_path(os.path.join(IMG_DIR, "panduandiaoyu.png"))
PATH_YUER = resource_path(os.path.join(IMG_DIR, "yuer.png"))
PATH_RECONNECT_ON_DISCONNECT = resource_path(os.path.join(IMG_DIR, "reconnect_on_disconnect.png"))

PATH_FISH_GONE = resource_path(os.path.join(IMG_DIR, "rank_fish", "fish_gone.bmp"))
PATH_RANK_A = resource_path(os.path.join(IMG_DIR, "rank_fish", "rank_a_fish.bmp"))
PATH_RANK_B = resource_path(os.path.join(IMG_DIR, "rank_fish", "rank_b_fish.bmp"))
PATH_RANK_S = resource_path(os.path.join(IMG_DIR, "rank_fish", "rank_s_fish.bmp"))

MATCH_THRESH = 0.7
RECONNECT_REGION = (42, 50, 147, 180)

WM_ACTIVATE = 0x0006
WA_ACTIVE = 1

def fake_activate(hwnd):
    try: win32gui.SendMessage(hwnd, WM_ACTIVATE, WA_ACTIVE, 0)
    except: pass

def send_key(hwnd, vk_code, down=True):
    fake_activate(hwnd)
    if down: send_key_down(hwnd, vk_code)
    else: send_key_up(hwnd, vk_code)

def press_key(hwnd, vk_code, duration=0.05):
    send_key(hwnd, vk_code, down=True)
    time.sleep(duration)
    send_key(hwnd, vk_code, down=False)

def find_image_in_window(template_path, hwnd, region=None, threshold=MATCH_THRESH):
    """在窗口中查找模板图片，支持 ROI 区域"""
    full_img = capture_window_to_cv(hwnd)   # 只接受 hwnd
    if full_img is None:
        return False, 0.0
    if region:
        x1, y1, x2, y2 = region
        h, w = full_img.shape[:2]
        x1 = max(0, min(x1, w-1))
        y1 = max(0, min(y1, h-1))
        x2 = max(x1+1, min(x2, w))
        y2 = max(y1+1, min(y2, h))
        img = full_img[y1:y2, x1:x2]
    else:
        img = full_img
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    template = load_template(template_path)
    if template is None:
        return False, 0.0
    res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    found = max_val >= threshold
    if found:
        h_t, w_t = template.shape
        center_x = max_loc[0] + w_t // 2
        center_y = max_loc[1] + h_t // 2
        if region:
            center_x += region[0]
            center_y += region[1]
        return True, (center_x, center_y)
    return False, 0.0

class FishingCore:
    def __init__(self, hwnd, stop_event, timeout=60, options=None, stats_callback=None):
        self.hwnd = hwnd
        self.stop_event = stop_event
        self.fish_count = 0
        self.fish_count_a = 0
        self.fish_count_b = 0
        self.fish_count_s = 0
        self.timeout = timeout
        self.options = options or {}
        self.today_forced_sell = False
        self.last_sell_date = ""
        self.enable_follow = False
        self.roi_follower = None
        self.stats_callback = stats_callback
        self.throw_count = 0
        self.escape_count = 0
        self.buy_bait_count = 0
        self.sell_fish_count = 0

    def _update_web_state(self, status_text="监测中..."): pass

    def fish_logic(self):
        self.enable_follow = False
        today_str = datetime.date.today().isoformat()
        if today_str != self.last_sell_date:
            self.today_forced_sell = False
            self.last_sell_date = today_str
        try:
            logui.info("开始监测图像...")
            last_prompt = time.time()
            last_reconnect_check = time.time()
            while not self.stop_event.is_set():
                latest_hwnd = get_game_hwnd()
                if latest_hwnd and latest_hwnd != self.hwnd:
                    logui.info(f"窗口句柄已更新: {self.hwnd} -> {latest_hwnd}")
                    self.hwnd = latest_hwnd
                    set_locked_hwnd(self.hwnd)
                if time.time() - last_reconnect_check > 5:
                    last_reconnect_check = time.time()
                    reconnect_found, _ = find_image_in_window(
                        PATH_RECONNECT_ON_DISCONNECT, self.hwnd, region=RECONNECT_REGION, threshold=0.8
                    )
                    if reconnect_found:
                        logui.warning("检测到被踢出钓鱼准备进入游戏 (后台重连)")
                        check_and_click_enter_game()
                        time.sleep(3)
                        return False

                frame = capture_window_to_cv(self.hwnd)
                if frame is None: time.sleep(0.02); continue
                gray_all = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                def match_in_region(tpl_path, left, top, right, bottom):
                    h, w = gray_all.shape
                    x1 = max(0, min(left, w - 1)); y1 = max(0, min(top, h - 1))
                    x2 = max(x1 + 1, min(right, w)); y2 = max(y1 + 1, min(bottom, h))
                    if x2 - x1 < 10 or y2 - y1 < 10: return None
                    roi_gray = gray_all[y1:y2, x1:x2]
                    tpl = load_template(tpl_path)
                    if tpl is None: return None
                    res = cv2.matchTemplate(roi_gray, tpl, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(res)
                    if max_val >= MATCH_THRESH:
                        tpl_h, tpl_w = tpl.shape
                        cx = max_loc[0] + tpl_w // 2 + x1
                        cy = max_loc[1] + tpl_h // 2 + y1
                        return (cx, cy)
                    return None

                pos = match_in_region(PATH_DIAOYU, 1153, 548, 1271, 626)
                if pos:
                    logui.info("按 F 进入钓鱼 (后台按键)")
                    press_key(self.hwnd, 0x46)
                    time.sleep(0.5)
                    continue

                pos = match_in_region(PATH_KAISHIDIAOYU, 1471, 880, 1730, 993)
                if pos:
                    logui.info("开始钓鱼 (前台点击)")
                    simulate_mouse_click_relative(self.hwnd, pos[0], pos[1])
                    time.sleep(0.8)
                    continue

                pos = match_in_region(PATH_DIANJIKONGBAI, 826, 918, 1081, 1033)
                if pos:
                    logui.info("点击空白区域关闭界面优先后台ESC (后台ESC)")
                    press_key(self.hwnd, 0x1B)
                    time.sleep(1.0)
                    continue

                pos = match_in_region(PATH_PANDUANDIAOYU, 1346, 919, 1459, 1040)
                if pos:
                    self.enable_follow = True
                    from plugins.fishing.throw_rod import throw_rod
                    throw_rod(self.stop_event, options=self.options)
                    self.throw_count += 1
                    self._update_web_state("抛竿中...")
                    break

                if time.time() - last_prompt > 3:
                    logui.info("监测中...")
                    last_prompt = time.time()
                time.sleep(0.02)

            logui.info("启动跟随")
            follow_stop = threading.Event()
            follow_started = False
            if self.enable_follow:
                try:
                    fish_mode = self.options.get("fish_mode", 0)
                    if fish_mode == 0:
                        from plugins.fishing.fishing_roi.RoiFollow import FishingFollower
                        self.roi_follower = FishingFollower(offset=self.options.get("roi_offset", 0))
                        self.roi_follower.start()
                        follow_started = True
                    elif fish_mode == 1:
                        from plugins.fishing.fishing_roi.AI_RoiFollow import FishingFollower as AIFollower
                        self.roi_follower = AIFollower(offset=self.options.get("roi_offset", 0))
                        self.roi_follower.start()
                        follow_started = True
                    else:
                        if start_follow(follow_stop, target_hwnd=self.hwnd):
                            follow_started = True
                except Exception as e:
                    logui.error(f"跟随启动异常: {e}")
            else:
                logui.info("跟随功能已关闭")

            if not follow_started:
                logui.error("跟随启动失败，放弃本次钓鱼")
                self.enable_follow = False
                return False

            logui.info("等待结果...")
            start_wait = time.time()
            result = None
            prev_escape_found = False
            success_frame = None
            timeout_count = 0

            while not self.stop_event.is_set():
                frame = capture_window_to_cv(self.hwnd)
                if frame is not None:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    def check_img(tpl_path, roi, name):
                        left, top, right, bottom = roi
                        h, w = gray.shape
                        x1 = max(0, min(left, w - 1)); y1 = max(0, min(top, h - 1))
                        x2 = max(x1 + 1, min(right, w)); y2 = max(y1 + 1, min(bottom, h))
                        if x2 - x1 < 10 or y2 - y1 < 10: return False, 0.0
                        roi_gray = gray[y1:y2, x1:x2]
                        tpl = load_template(tpl_path)
                        if tpl is None: return False, 0.0
                        res = cv2.matchTemplate(roi_gray, tpl, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, _ = cv2.minMaxLoc(res)
                        found = max_val >= MATCH_THRESH
                        if not found: logui.info(f"[等待结果] {name} 匹配度={max_val:.3f}")
                        return found, max_val

                    found_dian, _ = check_img(PATH_DIANJIKONGBAI, (826, 918, 1081, 1033), "dianjikongbai")
                    if found_dian: success_frame = frame; result = 'success'; break
                    found_pan, _ = check_img(PATH_PANDUANDIAOYU, (1346, 919, 1459, 1040), "panduandiaoyu")
                    if found_pan:
                        if prev_escape_found: result = 'escape'; break
                        else: prev_escape_found = True; time.sleep(0.3); continue
                    else: prev_escape_found = False

                if time.time() - start_wait > self.timeout:
                    timeout_count += 1
                    if timeout_count >= 3:
                        logui.warning(f"等待超时次数过多({self.timeout * 3}秒)，退出跟随")
                        result = 'timeout'; break
                    logui.warning(f"等待超时({self.timeout}秒)，仍在跟随中... (第{timeout_count}次)")
                    start_wait = time.time()
                time.sleep(0.15)

            if self.roi_follower: self.roi_follower.stop()
            else: follow_stop.set()
            self.enable_follow = False

            if result == 'success' and success_frame is not None:
                gray = cv2.cvtColor(success_frame, cv2.COLOR_BGR2GRAY)
                def match_grade(tpl_path, left, top, right, bottom, name="?"):
                    h, w = gray.shape
                    x1 = max(0, min(left, w-1)); y1 = max(0, min(top, h-1))
                    x2 = max(x1+1, min(right, w)); y2 = max(y1+1, min(bottom, h))
                    if x2-x1<10 or y2-y1<10: return False, 0.0
                    roi_gray = gray[y1:y2, x1:x2]
                    tpl = load_template(tpl_path)
                    if tpl is None: return False, 0.0
                    res = cv2.matchTemplate(roi_gray, tpl, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(res)
                    logui.info(f"[鱼获识别] {name} 匹配度={max_val:.3f}")
                    return max_val >= MATCH_THRESH, max_val

                is_gone, _ = match_grade(PATH_FISH_GONE, 828, 504, 1091, 578, "fish_gone")
                grade = None
                if is_gone: grade = 'escape'
                else:
                    found_s, _ = match_grade(PATH_RANK_S, 1033, 323, 1160, 439, "rank_s")
                    found_a, _ = match_grade(PATH_RANK_A, 1033, 323, 1160, 439, "rank_a")
                    found_b, _ = match_grade(PATH_RANK_B, 1033, 323, 1160, 439, "rank_b")
                    if found_s: grade = 'S'
                    elif found_a: grade = 'A'
                    elif found_b: grade = 'B'

                if grade and grade != 'escape':
                    logui.info(f"钓起{grade}级鱼")
                    self.fish_count += 1
                    if grade == 'A': self.fish_count_a += 1
                    elif grade == 'B': self.fish_count_b += 1
                    elif grade == 'S': self.fish_count_s += 1
                    if self.stats_callback: self.stats_callback(grade)
                elif not grade:
                    logui.info("未识别到鱼获等级，仍计为成功")
                    self.fish_count += 1
                    if self.stats_callback: self.stats_callback('unknown')

                logui.info("钓鱼成功，后台按 ESC")
                press_key(self.hwnd, 0x1B)
                time.sleep(0.5)
                return True
            elif result == 'escape':
                logui.info("鱼逃走了"); self.escape_count += 1; return False
            elif result == 'timeout':
                logui.info("等待超时次数过多，放弃本次钓鱼"); return False
            else:
                logui.info("未知状态，退出本次钓鱼"); return False

        except Exception as e:
            logui.error(f"逻辑异常: {e}\n{traceback.format_exc()}")
            self.enable_follow = False
            return False

    def run(self):
        if self.hwnd and win32gui.IsWindow(self.hwnd): set_locked_hwnd(self.hwnd)
        logui.info("开始循环钓鱼")
        try:
            while not self.stop_event.is_set():
                if self.fish_logic(): self._smart_sleep(1)
                else: self._smart_sleep(3)
        finally:
            for vk in [0x41,0x44,0x46,0x52,0x45,0x1B]: send_key_up(self.hwnd, vk)
            total = self.fish_count_a + self.fish_count_b + self.fish_count_s
            logui.info(f"结束，共钓鱼 {total} 条 (A:{self.fish_count_a} B:{self.fish_count_b} S:{self.fish_count_s})")

    def _smart_sleep(self, seconds, interval=0.05):
        elapsed = 0
        while elapsed < seconds and not self.stop_event.is_set():
            time.sleep(min(interval, seconds - elapsed))
            elapsed += interval