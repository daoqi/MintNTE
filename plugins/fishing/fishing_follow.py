# plugins/fishing/fishing_follow.py
import os, sys, time, threading, queue, ctypes, cv2, numpy as np, win32gui, win32con
from windows_capture import WindowsCapture, Frame, InternalCaptureControl
from utils.path_utils import resource_path
from utils.image_loader import load_template

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from Module.click.NET_click import send_key_down, send_key_up
import ui.services.logui as logui

IMG_DIR = os.path.join("plugins", "fishing", "fishingimages")
TEMPLATE_HS = resource_path(os.path.join(IMG_DIR, "hs.png"))
ROI = (605, 61, 1322, 88)
GREEN_HSV_LOWER = np.array([60, 100, 150])
GREEN_HSV_UPPER = np.array([90, 255, 255])
YELLOW_MATCH_THRESH = 0.6
FIRST_FRAME_TIMEOUT = 1.0
detection_queue = queue.Queue(maxsize=1)

WM_ACTIVATE = 0x0006
WA_ACTIVE = 1

def fake_activate(hwnd):
    try: win32gui.SendMessage(hwnd, WM_ACTIVATE, WA_ACTIVE, 0)
    except: pass

def get_client_crop(hwnd):
    DWMWA_EXTENDED_FRAME_BOUNDS = 9
    rect = ctypes.wintypes.RECT()
    ctypes.windll.dwmapi.DwmGetWindowAttribute(
        ctypes.wintypes.HWND(hwnd),
        ctypes.c_uint(DWMWA_EXTENDED_FRAME_BOUNDS),
        ctypes.byref(rect),
        ctypes.sizeof(rect)
    )
    dwm_left, dwm_top = rect.left, rect.top
    client_origin = win32gui.ClientToScreen(hwnd, (0, 0))
    client_left, client_top = client_origin
    client_rect = win32gui.GetClientRect(hwnd)
    client_w, client_h = client_rect[2], client_rect[3]
    return {
        'left': client_left - dwm_left,
        'top': client_top - dwm_top,
        'width': client_w,
        'height': client_h,
    }

def detect_green_zone(frame_rgb):
    roi_l, roi_t, roi_r, roi_b = ROI
    h, w = frame_rgb.shape[:2]
    if roi_r > w or roi_b > h or roi_l < 0 or roi_t < 0: return None
    roi_img = frame_rgb[roi_t:roi_b, roi_l:roi_r]
    hsv = cv2.cvtColor(roi_img, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv, GREEN_HSV_LOWER, GREEN_HSV_UPPER)
    cols = np.any(mask > 0, axis=0)
    indices = np.where(cols)[0]
    if len(indices) == 0: return None
    return (int(indices[0]) + roi_l, int(indices[-1]) + roi_l)

def detect_yellow_marker(frame_rgb, template):
    if template is None: return None
    roi_l, roi_t, roi_r, roi_b = ROI
    h, w = frame_rgb.shape[:2]
    if roi_r > w or roi_b > h or roi_l < 0 or roi_t < 0: return None
    roi_img = frame_rgb[roi_t:roi_b, roi_l:roi_r]
    gray = cv2.cvtColor(roi_img, cv2.COLOR_RGB2GRAY)
    th, tw = template.shape[:2]
    if gray.shape[0] < th or gray.shape[1] < tw: return None
    result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val < YELLOW_MATCH_THRESH: return None
    return max_loc[0] + tw // 2 + roi_l

class CaptureWorker:
    def __init__(self, hwnd, hs_template, stop_event, first_frame_event):
        self.hwnd = hwnd
        self.hs_template = hs_template
        self.stop_event = stop_event
        self.first_frame_event = first_frame_event
        self.crop = get_client_crop(hwnd)
        self.capture_handle = None

    def start(self):
        capture = WindowsCapture(
            cursor_capture=False,
            draw_border=False,
            monitor_index=None,
            window_name=None,
            window_hwnd=self.hwnd,
        )

        @capture.event
        def on_frame_arrived(frame: Frame, capture_control: InternalCaptureControl):
            if self.stop_event.is_set():
                capture_control.stop()
                return
            try:
                arr = frame.frame_buffer
                fh, fw = arr.shape[:2]
                cl = max(0, min(self.crop['left'], fw))
                ct = max(0, min(self.crop['top'], fh))
                cr = min(cl + self.crop['width'], fw)
                cb = min(ct + self.crop['height'], fh)
                arr = arr[ct:cb, cl:cr]
                rgb = cv2.cvtColor(arr, cv2.COLOR_BGRA2RGB)
                green = detect_green_zone(rgb)
                yellow_x = detect_yellow_marker(rgb, self.hs_template)
                if green is not None and yellow_x is not None:
                    logui.info("找到鱼摆动区域")
                    logui.info("找到浮漂")
                    detection = (yellow_x, green[0], green[1])
                    try:
                        detection_queue.put_nowait(detection)
                    except queue.Full:
                        try:
                            detection_queue.get_nowait()
                            detection_queue.put_nowait(detection)
                        except queue.Empty:
                            pass
                self.first_frame_event.set()
            except Exception as e:
                logui.error(f"[capture] frame error: {e}")

        @capture.event
        def on_closed():
            pass

        self.capture_handle = capture.start_free_threaded()

    def stop(self):
        if self.capture_handle is not None:
            try: self.capture_handle.stop()
            except: pass
            self.capture_handle = None

def control_worker(stop_event, hwnd):
    DEAD_ZONE = 3
    vk_a = 0x41
    vk_d = 0x44

    def send_key(key_code, down=True):
        fake_activate(hwnd)
        if down: send_key_down(hwnd, key_code)
        else: send_key_up(hwnd, key_code)

    while not stop_event.is_set():
        try:
            yellow_x, green_left, green_right = detection_queue.get_nowait()
        except queue.Empty:
            continue

        green_center = (green_left + green_right) // 2
        deviation = yellow_x - green_center
        abs_dev = abs(deviation)

        if abs_dev <= DEAD_ZONE:
            send_key(vk_a, down=False)
            send_key(vk_d, down=False)
        elif deviation > 0:
            send_key(vk_d, down=False)
            send_key(vk_a, down=True)
            logui.info("需要按A")
        else:
            send_key(vk_a, down=False)
            send_key(vk_d, down=True)
            logui.info("需要按D")

    send_key(vk_a, down=False)
    send_key(vk_d, down=False)

def start_follow(stop_event, target_hwnd=None):
    if target_hwnd is None:
        logui.error("错误：未传入目标窗口句柄")
        return False
    if not win32gui.IsWindow(target_hwnd):
        logui.error(f"错误：窗口句柄 {target_hwnd} 无效")
        return False

    logui.info(f"使用窗口句柄: {target_hwnd}")

    hs_template = load_template(TEMPLATE_HS)
    if hs_template is None:
        logui.error(f"错误：无法读取 hs.png，路径={TEMPLATE_HS}")
        return False

    while not detection_queue.empty():
        try: detection_queue.get_nowait()
        except queue.Empty: break

    first_frame_event = threading.Event()
    capture = CaptureWorker(target_hwnd, hs_template, stop_event, first_frame_event)
    try: capture.start()
    except Exception as e:
        logui.error(f"错误：WGC 启动失败 {e}")
        return False

    if not first_frame_event.wait(timeout=FIRST_FRAME_TIMEOUT):
        logui.warning(f"警告：{FIRST_FRAME_TIMEOUT}秒内未收到首帧")

    control_thread = threading.Thread(target=control_worker, args=(stop_event, target_hwnd), daemon=True, name="fishing-control")
    control_thread.start()

    stop_event._capture_worker = capture
    logui.info("开始跟随...")
    return True