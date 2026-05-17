import threading, time, cv2, numpy as np
import win32gui, win32ui, win32con, ctypes
from PIL import Image
import os, sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path: sys.path.insert(0, BASE_DIR)
from Module.click.NET_click import send_key_down, send_key_up
from UI import logui

MIN_TRIGGER_PIXELS = None
JUDGE_RADIUS = None
JUDGE_Y_OFFSET = None
COOLDOWN_MS = None

TRACK_COLORS = {
    'D': [(255, 244, 86), (28, 27, 27)],
    'F': [(132, 216, 255), (26, 26, 26)],
    'J': [(111, 130, 255), (26, 26, 26)],
    'K': [(26, 26, 26)],
}

def build_hsv_ranges(bgr_list, h_ext=20, sv_ext=40):
    ranges = []
    for bgr in bgr_list:
        col = np.uint8([[bgr]]); hsv = cv2.cvtColor(col, cv2.COLOR_BGR2HSV)[0][0]; h,s,v = hsv
        if v<30:
            h_low=max(0,h-10); h_high=min(179,h+10)
            s_low=max(0,s-25); s_high=min(255,s+25)
            v_low=max(0,v-25); v_high=min(255,v+25)
        else:
            h_low=max(0,h-h_ext); h_high=min(179,h+h_ext)
            s_low=max(0,s-sv_ext); s_high=min(255,s+sv_ext)
            v_low=max(0,v-sv_ext); v_high=min(255,v+sv_ext)
            if v_low<80: v_low=80
        ranges.append((np.array([h_low,s_low,v_low], dtype=np.uint8),
                       np.array([h_high,s_high,v_high], dtype=np.uint8)))
    return ranges

HSV_RANGES = {name: build_hsv_ranges(colors) for name,colors in TRACK_COLORS.items()}

TRACKS = [
    {'name':'D','key':'d','circle_base':(442,838)},
    {'name':'F','key':'f','circle_base':(779,838)},
    {'name':'J','key':'j','circle_base':(1141,838)},
    {'name':'K','key':'k','circle_base':(1477,838)},
]

WM_ACTIVATE = 0x0006; WA_ACTIVE = 1
def fake_activate(hwnd):
    try: win32gui.SendMessage(hwnd, WM_ACTIVATE, WA_ACTIVE, 0)
    except: pass

def press_key_bg(hwnd, vk_code, duration=0.05):
    fake_activate(hwnd)
    send_key_down(hwnd, vk_code); time.sleep(duration); send_key_up(hwnd, vk_code)

def capture_window_background(hwnd):
    if not win32gui.IsWindow(hwnd): return None
    rect = win32gui.GetClientRect(hwnd); w,h = rect[2]-rect[0], rect[3]-rect[1]
    if w<=0 or h<=0: return None
    try:
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
        save_dc.SelectObject(bitmap)
        success = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)
        if not success:
            win32gui.DeleteObject(bitmap.GetHandle()); save_dc.DeleteDC(); mfc_dc.DeleteDC(); win32gui.ReleaseDC(hwnd, hwnd_dc)
            return None
        bits = bitmap.GetBitmapBits(True)
        img = Image.frombuffer("RGB", (w,h), bits, "raw", "BGRX", 0,1)
        opencv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        win32gui.DeleteObject(bitmap.GetHandle()); save_dc.DeleteDC(); mfc_dc.DeleteDC(); win32gui.ReleaseDC(hwnd, hwnd_dc)
        return opencv_img
    except:
        try:
            win32gui.DeleteObject(bitmap.GetHandle()); save_dc.DeleteDC(); mfc_dc.DeleteDC(); win32gui.ReleaseDC(hwnd, hwnd_dc)
        except: pass
        return None

class BackgroundPlayer:
    def __init__(self, hwnd, tracks):
        if not win32gui.IsWindow(hwnd): raise ValueError(f"无效的窗口句柄: {hwnd}")
        self.hwnd = hwnd; self.tracks = tracks; self.num_tracks = len(tracks)
        if MIN_TRIGGER_PIXELS is None or JUDGE_RADIUS is None or COOLDOWN_MS is None:
            raise RuntimeError("参数未由 UI 设置")
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.color_counts = [0]*self.num_tracks
        self.active_states = [False]*self.num_tracks
        self.last_trigger_time = [0.0]*self.num_tracks
        self.prev_judge_active = [False]*self.num_tracks
        self.prev_judge_cnt = [0]*self.num_tracks
        self.processing_time = 0.0
        self.det_thread = None

    def start(self):
        self.stop_event.clear()
        self.det_thread = threading.Thread(target=self._detect_loop, daemon=True)
        self.det_thread.start()

    def stop(self):
        self.stop_event.set()
        if self.det_thread and self.det_thread.is_alive(): self.det_thread.join(timeout=1.5)
        for track in self.tracks:
            vk = ord(track['key'].upper()); press_key_bg(self.hwnd, vk, 0)
        for vk in [0x44,0x46,0x4A,0x4B]: send_key_up(self.hwnd, vk)

    def get_shared_data(self):
        with self.lock:
            return (list(self.color_counts), list(self.active_states),
                    {'last_frame_time': time.perf_counter(), 'processing_time': self.processing_time})

    def _detect_loop(self):
        while not self.stop_event.is_set():
            frame = capture_window_background(self.hwnd)
            if frame is None: time.sleep(0.01); continue

            t0 = time.perf_counter(); now = t0
            for i,track in enumerate(self.tracks):
                track_name = track['name']; cx_base,cy_base = track['circle_base']
                r = JUDGE_RADIUS.get(track_name,15)
                cy = cy_base + (JUDGE_Y_OFFSET.get(track_name,0) if JUDGE_Y_OFFSET else 0)

                x1,y1 = cx_base-r, cy-r; x2,y2 = cx_base+r, cy+r
                if x1<0 or y1<0 or x2>frame.shape[1] or y2>frame.shape[0]: continue

                roi_bgr = frame[y1:y2,x1:x2]
                mask = np.zeros((2*r,2*r), dtype=np.uint8); cv2.circle(mask,(r,r),r,255,-1)
                circle_pixels = roi_bgr[mask==255]
                if circle_pixels.size==0: judge_cnt=0
                else:
                    hsv = cv2.cvtColor(circle_pixels.reshape(-1,1,3), cv2.COLOR_BGR2HSV).reshape(-1,3)
                    matched = np.zeros(len(hsv), dtype=bool)
                    for lower,upper in HSV_RANGES[track_name]:
                        matched |= (hsv[:,0]>=lower[0])&(hsv[:,0]<=upper[0]) & \
                                   (hsv[:,1]>=lower[1])&(hsv[:,1]<=upper[1]) & \
                                   (hsv[:,2]>=lower[2])&(hsv[:,2]<=upper[2])
                    judge_cnt = int(np.count_nonzero(matched))

                self.color_counts[i] = judge_cnt
                is_active = judge_cnt >= MIN_TRIGGER_PIXELS.get(track_name,3)
                cooldown = COOLDOWN_MS.get(track_name,20)/1000.0
                in_cooldown = (now - self.last_trigger_time[i]) < cooldown

                if self.prev_judge_active[i] and judge_cnt < MIN_TRIGGER_PIXELS.get(track_name,3):
                    if not in_cooldown: self.prev_judge_active[i] = False

                jump_threshold = 5 if track_name in ('J','F') else 4 if track_name=='K' else 8
                pixel_jump = judge_cnt - self.prev_judge_cnt[i] > jump_threshold

                trigger = False
                if is_active:
                    if not self.prev_judge_active[i]:
                        if not in_cooldown: trigger = True
                    else:
                        if not in_cooldown and pixel_jump: trigger = True

                if trigger:
                    vk = ord(track['key'].upper())
                    threading.Thread(target=press_key_bg, args=(self.hwnd,vk,0.05), daemon=True).start()
                    self.last_trigger_time[i] = now; self.active_states[i] = True
                    logui.info(f"[后台演奏] {track_name} 触发 (像素={judge_cnt})")
                else:
                    if now - self.last_trigger_time[i] > 0.3: self.active_states[i] = False

                self.prev_judge_active[i] = is_active; self.prev_judge_cnt[i] = judge_cnt

            self.processing_time = time.perf_counter() - t0
            time.sleep(0.015)