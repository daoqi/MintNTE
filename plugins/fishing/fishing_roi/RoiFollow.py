# plugins/fishing/fishing_roi/RoiFollow.py
import sys
import time
import threading
import math
import win32gui
from Module.click.NET_click import send_key_down, send_key_up, fake_activate_window
# ✅ 修正导入路径
from plugins.fishing.fishing_roi.fishing_roi_core import FishingROICore
from Module.Hwnd.game_hwnd import get_game_hwnd

# ---------- 可配置参数 ----------
BASE_ROI = (606, 64, 1319, 85)

MOVE_THRESHOLD = 15
BASE_KEY_DURATION = 0.05
MAX_KEY_DURATION = 0.15
SPEED_FACTOR = 0.002
UPDATE_INTERVAL = 0.02
LEFT_KEY = 0x41
RIGHT_KEY = 0x44

class FishingFollower:
    def __init__(self, hwnd=None, offset=0):
        if hwnd is None:
            hwnd = get_game_hwnd()
            if not hwnd or not win32gui.IsWindow(hwnd):
                raise RuntimeError("未找到有效的游戏窗口句柄，请先通过窗口检测锁定窗口")
        else:
            if not win32gui.IsWindow(hwnd):
                raise RuntimeError(f"无效窗口句柄: {hwnd}")

        self.hwnd = hwnd
        self.offset = offset
        self.actual_roi = (BASE_ROI[0], BASE_ROI[1] + offset,
                           BASE_ROI[2], BASE_ROI[3] + offset)
        self.roi_core = FishingROICore(self.actual_roi)
        if self.roi_core.hwnd != self.hwnd:
            self.roi_core.hwnd = self.hwnd
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.last_a_center = None
        self.last_time = None
        self.current_speed = 0.0
    def start(self):
        if self.running:
            return
        self.running = True
        self.roi_core.start()
        self.thread = threading.Thread(target=self._control_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        self.roi_core.stop()
        send_key_up(self.hwnd, LEFT_KEY)
        send_key_up(self.hwnd, RIGHT_KEY)

    def _get_center(self, rect):
        if rect is None:
            return None
        x1, y1, x2, y2 = rect
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def _calculate_speed(self, current_center):
        with self.lock:
            if self.last_a_center and self.last_time:
                dt = time.time() - self.last_time
                if dt > 0.001:
                    dx = current_center[0] - self.last_a_center[0]
                    dy = current_center[1] - self.last_a_center[1]
                    speed = math.hypot(dx, dy) / dt
                    self.current_speed = speed
            self.last_a_center = current_center
            self.last_time = time.time()
        return self.current_speed

    def _get_key_duration(self, speed):
        duration = BASE_KEY_DURATION + speed * SPEED_FACTOR
        return min(duration, MAX_KEY_DURATION)

    def _control_loop(self):
        while self.running:
            fake_activate_window(self.hwnd)          # 后台按键欺骗
            data = self.roi_core.get_data()
            rect_a = data['color_a']['rect']
            rect_b = data['color_b']['rect']
            if rect_a is None or rect_b is None:
                send_key_up(self.hwnd, LEFT_KEY)
                send_key_up(self.hwnd, RIGHT_KEY)
                time.sleep(UPDATE_INTERVAL)
                continue

            center_a = self._get_center(rect_a)
            center_b = self._get_center(rect_b)
            if center_a is None or center_b is None:
                continue

            speed = self._calculate_speed(center_a)
            key_duration = self._get_key_duration(speed)

            offset = center_b[0] - center_a[0]
            if offset < -MOVE_THRESHOLD:
                send_key_up(self.hwnd, LEFT_KEY)
                send_key_down(self.hwnd, RIGHT_KEY)
                time.sleep(key_duration)
                send_key_up(self.hwnd, RIGHT_KEY)
            elif offset > MOVE_THRESHOLD:
                send_key_up(self.hwnd, RIGHT_KEY)
                send_key_down(self.hwnd, LEFT_KEY)
                time.sleep(key_duration)
                send_key_up(self.hwnd, LEFT_KEY)
            else:
                send_key_up(self.hwnd, LEFT_KEY)
                send_key_up(self.hwnd, RIGHT_KEY)

            time.sleep(UPDATE_INTERVAL)