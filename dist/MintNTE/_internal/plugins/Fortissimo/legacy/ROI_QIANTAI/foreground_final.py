# -*- coding: utf-8 -*-
# foreground_final.py —— 最终修复双击 + 高成功率参数
import threading, time, cv2, numpy as np
from collections import deque
import dxcam, win32gui, pydirectinput

# ================= 全局动态参数（由 UI 写入） =================
MIN_TRIGGER_PIXELS = None
JUDGE_RADIUS = None
JUDGE_Y_OFFSET = None
COOLDOWN_MS = None          # UI 会设置，例如 {'D':20,'F':15,'J':12,'K':20}
TARGET_FPS = 60

# ================= 颜色配置（固定） =================
TRACK_COLORS = {
    'D': [ (255, 244, 86), (28, 27, 27) ],
    'F': [ (132, 216, 255), (26, 26, 26) ],
    'J': [ (111, 130, 255), (26, 26, 26) ],
    'K': [ (26, 26, 26) ],
}

def build_hsv_ranges(bgr_list, h_ext=20, sv_ext=40):
    ranges = []
    for bgr in bgr_list:
        col = np.uint8([[bgr]])
        hsv = cv2.cvtColor(col, cv2.COLOR_BGR2HSV)[0][0]
        h, s, v = hsv
        if v < 30:
            h_ext_dark, sv_ext_dark = 10, 25
            h_low = max(0, h - h_ext_dark)
            h_high = min(179, h + h_ext_dark)
            s_low = max(0, s - sv_ext_dark)
            s_high = min(255, s + sv_ext_dark)
            v_low = max(0, v - sv_ext_dark)
            v_high = min(255, v + sv_ext_dark)
        else:
            h_low = max(0, h - h_ext)
            h_high = min(179, h + h_ext)
            s_low = max(0, s - sv_ext)
            s_high = min(255, s + sv_ext)
            v_low = max(0, v - sv_ext)
            v_high = min(255, v + sv_ext)
            if v_low < 80:
                v_low = 80
        ranges.append( (np.array([h_low, s_low, v_low], dtype=np.uint8),
                        np.array([h_high, s_high, v_high], dtype=np.uint8)) )
    return ranges

HSV_RANGES = {}
for name, colors in TRACK_COLORS.items():
    HSV_RANGES[name] = build_hsv_ranges(colors)

HWND = 16912878      # 默认句柄，UI 可覆盖

AUX_LINES = {
    'D': {'start': (424, 325), 'end': (440, 787)},
    'F': {'start': (772, 277), 'end': (778, 787)},
    'J': {'start': (1147, 297), 'end': (1142, 787)},
    'K': {'start': (1496, 290), 'end': (1479, 787)},
}

TRACKS = [
    {'name': 'D', 'key': 'd', 'circle_base': (442, 838)},
    {'name': 'F', 'key': 'f', 'circle_base': (779, 838)},
    {'name': 'J', 'key': 'j', 'circle_base': (1141, 838)},
    {'name': 'K', 'key': 'k', 'circle_base': (1477, 838)},
]

class ForegroundFinal:
    def __init__(self, hwnd, tracks):
        self.hwnd = hwnd
        self.tracks = tracks
        self.num_tracks = len(tracks)

        if MIN_TRIGGER_PIXELS is None or JUDGE_RADIUS is None or COOLDOWN_MS is None:
            raise RuntimeError("❌ 参数未由 UI 设置，请先启动 UI 并点击“开始演奏”")

        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.cond = threading.Condition(self.lock)
        self.frame_queue = deque(maxlen=4)

        self.color_counts = [0] * self.num_tracks
        self.active_states = [False] * self.num_tracks
        self.last_trigger_time = [0.0] * self.num_tracks
        self.prev_judge_active = [False] * self.num_tracks
        self.prev_judge_cnt = [0] * self.num_tracks

        self.last_full_frame = None
        self.last_frame_time = 0.0
        self.processing_time = 0.0
        self.camera = None
        self.region = None
        self.cap_thread = None
        self.det_thread = None

    def start(self):
        rect = win32gui.GetClientRect(self.hwnd)
        pt = win32gui.ClientToScreen(self.hwnd, (0, 0))
        self.region = (pt[0], pt[1], pt[0] + rect[2], pt[1] + rect[3])
        self.camera = dxcam.create(output_color="BGR", region=self.region)
        self.camera.start(target_fps=TARGET_FPS, video_mode=True)
        time.sleep(0.5)
        self.cap_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.cap_thread.start()
        self.det_thread = threading.Thread(target=self._detect_loop, daemon=True)
        self.det_thread.start()

    def stop(self):
        self.stop_event.set()
        with self.cond:
            self.cond.notify_all()
        if self.cap_thread and self.cap_thread.is_alive():
            self.cap_thread.join(timeout=1.5)
        if self.det_thread and self.det_thread.is_alive():
            self.det_thread.join(timeout=1.5)
        if self.camera:
            self.camera.stop()
        self.camera = None

    def get_shared_data(self):
        with self.lock:
            return (list(self.color_counts), list(self.active_states),
                    {'last_frame_time': self.last_frame_time, 'processing_time': self.processing_time})

    def get_crop_for_track(self, track_name, size=200):
        with self.lock:
            if self.last_full_frame is None:
                return None
            track = next((t for t in self.tracks if t['name'] == track_name), None)
            if not track:
                return None
            cx, cy = track['circle_base']
            r = JUDGE_RADIUS.get(track_name, 15)
            cy += JUDGE_Y_OFFSET.get(track_name, 0) if JUDGE_Y_OFFSET else 0
            half = size // 2
            x1 = max(0, cx - half)
            y1 = max(0, cy - half)
            x2 = min(self.last_full_frame.shape[1], cx + half)
            y2 = min(self.last_full_frame.shape[0], cy + half)
            if x2 <= x1 or y2 <= y1:
                return None
            crop = self.last_full_frame[y1:y2, x1:x2].copy()
            cv2.circle(crop, (cx - x1, cy - y1), r, (0, 255, 255), 2)
            return crop

    def _capture_loop(self):
        while not self.stop_event.is_set():
            frame = self.camera.get_latest_frame()
            if frame is not None:
                with self.cond:
                    self.frame_queue.append(frame)
                    self.last_full_frame = frame
                    self.last_frame_time = time.perf_counter()
                    self.cond.notify_all()
            else:
                time.sleep(0.0005)

    def _detect_loop(self):
        while not self.stop_event.is_set():
            frame = None
            with self.cond:
                while not self.frame_queue and not self.stop_event.is_set():
                    self.cond.wait(timeout=0.002)
                if self.stop_event.is_set():
                    break
                if self.frame_queue:
                    frame = self.frame_queue.popleft()
            if frame is None:
                continue

            t0 = time.perf_counter()
            now = t0

            for i, track in enumerate(self.tracks):
                track_name = track['name']
                cx_base, cy_base = track['circle_base']
                r = JUDGE_RADIUS.get(track_name, 15)
                cy = cy_base + (JUDGE_Y_OFFSET.get(track_name, 0) if JUDGE_Y_OFFSET else 0)

                x1, y1 = cx_base - r, cy - r
                x2, y2 = cx_base + r, cy + r
                if x1 < 0 or y1 < 0 or x2 > frame.shape[1] or y2 > frame.shape[0]:
                    continue

                roi_bgr = frame[y1:y2, x1:x2]
                mask = np.zeros((2 * r, 2 * r), dtype=np.uint8)
                cv2.circle(mask, (r, r), r, 255, -1)
                circle_pixels = roi_bgr[mask == 255]
                if circle_pixels.size == 0:
                    judge_cnt = 0
                else:
                    hsv = cv2.cvtColor(circle_pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2HSV).reshape(-1, 3)
                    matched = np.zeros(len(hsv), dtype=bool)
                    for (lower, upper) in HSV_RANGES[track_name]:
                        m_h = (hsv[:, 0] >= lower[0]) & (hsv[:, 0] <= upper[0])
                        m_s = (hsv[:, 1] >= lower[1]) & (hsv[:, 1] <= upper[1])
                        m_v = (hsv[:, 2] >= lower[2]) & (hsv[:, 2] <= upper[2])
                        matched |= (m_h & m_s & m_v)
                    judge_cnt = int(np.count_nonzero(matched))

                self.color_counts[i] = judge_cnt
                is_active = judge_cnt >= MIN_TRIGGER_PIXELS.get(track_name, 3)

                # 冷却时间（完全由 UI 控制）
                cooldown = COOLDOWN_MS.get(track_name, 20) / 1000.0
                in_cooldown = (now - self.last_trigger_time[i]) < cooldown

                # 强制重置：如果已经冷却完毕，且当前像素低于触发门槛，认为音符离开
                if self.prev_judge_active[i] and judge_cnt < MIN_TRIGGER_PIXELS.get(track_name, 3):
                    if not in_cooldown:
                        self.prev_judge_active[i] = False

                # 跳变阈值（高灵敏度，但冷却内不生效）
                if track_name == 'J' or track_name == 'F':
                    jump_threshold = 5
                elif track_name == 'K':
                    jump_threshold = 4
                else:
                    jump_threshold = 8

                pixel_jump = judge_cnt - self.prev_judge_cnt[i] > jump_threshold

                trigger = False
                if is_active:
                    if not self.prev_judge_active[i]:
                        # 上升沿：从无到有，必须冷却结束才能触发
                        if not in_cooldown:
                            trigger = True
                    else:
                        # 已经激活过：只有冷却结束且像素跳变足够才允许再次触发
                        if not in_cooldown and pixel_jump:
                            trigger = True

                if trigger:
                    threading.Thread(target=self._press_async, args=(track['key'], i), daemon=True).start()
                    self.last_trigger_time[i] = now
                    self.active_states[i] = True
                    print(f"{time.strftime('%H:%M:%S', time.localtime(now))}.{int(now*1000)%1000:03d} | "
                          f"[判定] 像素={judge_cnt}（{track_name}）")
                else:
                    if now - self.last_trigger_time[i] > 0.3:
                        self.active_states[i] = False

                self.prev_judge_active[i] = is_active
                self.prev_judge_cnt[i] = judge_cnt

            self.processing_time = time.perf_counter() - t0
            time.sleep(0.001)

    def _press_async(self, key, idx):
        pydirectinput.press(key)