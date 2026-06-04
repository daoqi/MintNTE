# plugins/dark_racing/dark_racing_core.py
import threading, time, os, cv2, numpy as np, win32gui
from utils.path_utils import resource_path
from utils.image_loader import load_template
from Module.Hwnd.game_hwnd import get_game_hwnd
from Module.click.NET_click import (
    simulate_mouse_click_relative,
    send_key_press
)
from Module.capture.frame_capture import capture_frame
import ui.services.logui as logui

IMG_DIR = os.path.join("plugins", "dark_racing", "dark_racing_img")
PATH_FIND_ACTIVITY = resource_path(os.path.join(IMG_DIR, "find_activity.bmp"))
PATH_ESC_HOME = resource_path(os.path.join(IMG_DIR, "activity_esc_home.bmp"))
PATH_FONT = resource_path(os.path.join(IMG_DIR, "activity_font.bmp"))
PATH_IMG = resource_path(os.path.join(IMG_DIR, "activity_img.bmp"))
PATH_LEAVE = resource_path(os.path.join(IMG_DIR, "activity_leave.bmp"))

MATCH_THRESH = 0.7

def find_in_region(hwnd, template, left, top, right, bottom, threshold=MATCH_THRESH):
    if not hwnd or not win32gui.IsWindow(hwnd):
        return False
    try:
        frame = capture_frame(hwnd)
        if frame is None:
            return False
        h, w = frame.shape[:2]
        x1 = max(0, min(left, w-1))
        y1 = max(0, min(top, h-1))
        x2 = max(x1+1, min(right, w))
        y2 = max(y1+1, min(bottom, h))
        if x2-x1 < 10 or y2-y1 < 10:
            return False
        roi = frame[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        tpl = load_template(template)
        if tpl is None:
            return False
        res = cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        return max_val >= threshold
    except Exception as e:
        logui.error(f"find_in_region 异常: {e}")
        return False

def click_template_center(hwnd, template, left, top, right, bottom, threshold=MATCH_THRESH):
    if not hwnd or not win32gui.IsWindow(hwnd):
        return False
    try:
        frame = capture_frame(hwnd)
        if frame is None:
            return False
        h, w = frame.shape[:2]
        x1 = max(0, min(left, w-1))
        y1 = max(0, min(top, h-1))
        x2 = max(x1+1, min(right, w))
        y2 = max(y1+1, min(bottom, h))
        if x2-x1 < 10 or y2-y1 < 10:
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
        th, tw = tpl.shape
        cx = x1 + max_loc[0] + tw//2
        cy = y1 + max_loc[1] + th//2
        simulate_mouse_click_relative(hwnd, cx, cy)
        return True
    except Exception as e:
        logui.error(f"click_template_center 异常: {e}")
        return False

class DarkRacingWorker:
    def __init__(self, stop_event, status_cb, finish_cb):
        self.stop_event = stop_event
        self._status_cb = status_cb
        self._finish_cb = finish_cb
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        complete = 0
        self._status_cb(f"完成次数: {complete}")
        logui.info("黑暗赛车线程启动")
        try:
            while not self.stop_event.is_set():
                hwnd = get_game_hwnd()
                if not hwnd or not win32gui.IsWindow(hwnd):
                    time.sleep(0.5)
                    continue

                # 查找活动入口
                logui.info("查找活动入口...")
                found_activity = False
                while not self.stop_event.is_set():
                    if find_in_region(hwnd, PATH_FIND_ACTIVITY, 1565, 12, 1655, 80):
                        logui.info("找到活动入口，按F4")
                        send_key_press(hwnd, 0x73)  # F4
                        time.sleep(3)
                    else:
                        logui.info("未找到活动入口，按ESC")
                        send_key_press(hwnd, 0x1B)
                        time.sleep(0.5)

                    if find_in_region(hwnd, PATH_ESC_HOME, 1493, 417, 1609, 516):
                        click_template_center(hwnd, PATH_ESC_HOME, 1493, 417, 1609, 516)
                        time.sleep(1)

                    if find_in_region(hwnd, PATH_FONT, 93, 33, 211, 86) or \
                       find_in_region(hwnd, PATH_IMG, 24, 30, 95, 92):
                        found_activity = True
                        break
                    time.sleep(0.5)

                if not found_activity or self.stop_event.is_set():
                    continue

                # 进入比赛，点击固定坐标
                logui.info("进入比赛界面...")
                simulate_mouse_click_relative(hwnd, 165,743)
                time.sleep(0.1)
                simulate_mouse_click_relative(hwnd, 165,743)
                time.sleep(0.1)
                simulate_mouse_click_relative(hwnd, 165, 743)
                time.sleep(0.1)
                simulate_mouse_click_relative(hwnd, 165, 743)
                time.sleep(0.1)
                simulate_mouse_click_relative(hwnd, 165, 743)
                time.sleep(0.1)
                simulate_mouse_click_relative(hwnd, 165, 743)
                time.sleep(0.1)
                # 点击开始比赛
                simulate_mouse_click_relative(hwnd, 1687,1015)
                time.sleep(0.1)
                simulate_mouse_click_relative(hwnd, 1687, 1015)
                time.sleep(0.1)
                simulate_mouse_click_relative(hwnd, 1687, 1015)
                time.sleep(0.1)
                time.sleep(1)

                # 等待离开按钮，最长10分钟
                enter_time = time.time()
                while not self.stop_event.is_set() and (time.time() - enter_time) < 600:
                    hwnd = get_game_hwnd()
                    if not hwnd or not win32gui.IsWindow(hwnd):
                        break

                    if find_in_region(hwnd, PATH_LEAVE, 1563, 990, 1637, 1035):
                        logui.info("检测到离开按钮，点击离开并计数")
                        if click_template_center(hwnd, PATH_LEAVE, 1563, 990, 1637, 1035):
                            complete += 1
                            self._status_cb(f"完成次数: {complete}")
                            logui.info(f"完成第 {complete} 次")
                            time.sleep(2)   # 等待界面切换
                            break
                    time.sleep(1)
                else:
                    logui.warning("等待离开按钮超时（10分钟），退出比赛循环")

                # 短暂休息后继续下一轮
                time.sleep(1)
        except Exception as e:
            logui.error(f"黑暗赛车异常: {e}")
        finally:
            logui.info("黑暗赛车线程退出")
            self._finish_cb()
