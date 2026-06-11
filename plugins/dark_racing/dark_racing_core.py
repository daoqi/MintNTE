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
PATH_IMG = resource_path(os.path.join(IMG_DIR, "activity_img.bmp"))
PATH_DARK_RACING_ENTRY = resource_path(os.path.join(IMG_DIR, "dark_racing_entry.bmp"))
PATH_DARK_RACING_GO_GAME = resource_path(os.path.join(IMG_DIR, "dark_racing_go_game.bmp"))
PATH_LEAVE = resource_path(os.path.join(IMG_DIR, "activity_leave.bmp"))

MATCH_THRESH = 0.7


def find_in_frame(frame, template, left, top, right, bottom, threshold=MATCH_THRESH):
    """在传入的 frame 上直接匹配，不重新截图"""
    if frame is None:
        return False
    h, w = frame.shape[:2]
    x1 = max(0, min(left, w - 1))
    y1 = max(0, min(top, h - 1))
    x2 = max(x1 + 1, min(right, w))
    y2 = max(y1 + 1, min(bottom, h))
    if x2 - x1 < 10 or y2 - y1 < 10:
        return False
    roi = frame[y1:y2, x1:x2]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    tpl = load_template(template)
    if tpl is None:
        return False
    res = cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    return max_val >= threshold


def click_template_center_from_frame(hwnd, frame, template, left, top, right, bottom, threshold=MATCH_THRESH):
    """在传入的 frame 上匹配并点击中心，不重新截图"""
    if frame is None or not hwnd or not win32gui.IsWindow(hwnd):
        return False
    h, w = frame.shape[:2]
    x1 = max(0, min(left, w - 1))
    y1 = max(0, min(top, h - 1))
    x2 = max(x1 + 1, min(right, w))
    y2 = max(y1 + 1, min(bottom, h))
    if x2 - x1 < 10 or y2 - y1 < 10:
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
    cx = x1 + max_loc[0] + tw // 2
    cy = y1 + max_loc[1] + th // 2
    simulate_mouse_click_relative(hwnd, cx, cy)
    return True


class DarkRacingWorker:
    def __init__(self, stop_event, status_cb, finish_cb):
        self.stop_event = stop_event
        self._status_cb = status_cb
        self._finish_cb = finish_cb
        self._thread = None
        # 离开按钮冷却，防止重复计数
        self._last_leave_time = 0

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

                # 每轮只截一次图，所有匹配都在这同一帧上做
                frame = capture_frame(hwnd)
                if frame is None:
                    time.sleep(0.5)
                    continue

                action_done = False

                # ========== 优先级1：离开按钮（比赛结束） ==========
                # 3秒冷却，防止界面切换慢导致重复计数
                if time.time() - self._last_leave_time > 3:
                    if click_template_center_from_frame(hwnd, frame, PATH_LEAVE, 1563, 990, 1637, 1035):
                        logui.info("点击离开")
                        self._last_leave_time = time.time()
                        complete += 1
                        self._status_cb(f"完成次数: {complete}")
                        logui.info(f"完成第 {complete} 次")
                        time.sleep(2)
                        action_done = True

                # ========== 优先级2：开始比赛按钮 ==========
                if not action_done:
                    if click_template_center_from_frame(hwnd, frame, PATH_DARK_RACING_GO_GAME, 1538, 941, 1823, 1072):
                        logui.info("点击开始比赛")
                        time.sleep(1)
                        action_done = True

                # ========== 优先级3：黑暗赛车入口 ==========
                if not action_done:
                    if click_template_center_from_frame(hwnd, frame, PATH_DARK_RACING_ENTRY, 66, 197, 297, 858):
                        logui.info("点击黑暗赛车入口")
                        time.sleep(1)
                        action_done = True

                # ========== 优先级4：活动入口（按F4） ==========
                if not action_done:
                    if (find_in_frame(frame, PATH_FIND_ACTIVITY, 1573, 12, 1644, 78) or
                        find_in_frame(frame, PATH_ESC_HOME, 1573, 12, 1644, 78) or
                        find_in_frame(frame, PATH_IMG, 24, 30, 95, 92)):
                        logui.info("找到活动入口，按F4")
                        send_key_press(hwnd, 0x73)  # F4
                        time.sleep(3)
                        action_done = True

                if not action_done:
                    time.sleep(0.5)

        except Exception as e:
            logui.error(f"黑暗赛车异常: {e}")
        finally:
            logui.info("黑暗赛车线程退出")
            self._finish_cb()