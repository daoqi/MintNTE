# plugins/task/Task_core.py
import threading, time, sys, os, cv2, numpy as np, win32gui, win32con, traceback
from utils.path_utils import resource_path
from utils.image_loader import load_template

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path: sys.path.insert(0, BASE_DIR)

from Module.Hwnd.game_hwnd import get_game_hwnd
from Module.click.NET_click import simulate_mouse_click_relative
from Module.capture.frame_capture import capture_frame
import ui.services.logui as logui

TASK_IMG = os.path.join("plugins", "task", "Taskimages")
PATH_GET_ITEM        = resource_path(os.path.join(TASK_IMG, "taks_huodewupin.bmp"))
PATH_DIALOG_FORBID_1 = resource_path(os.path.join(TASK_IMG, "taks_zuo_2_duihua.bmp"))
PATH_DIALOG_FORBID_2 = resource_path(os.path.join(TASK_IMG, "taks_zuo_1_jinzhi.bmp"))
PATH_SKIP_STORY      = resource_path(os.path.join(TASK_IMG, "taks_you_1_tiaoguo.bmp"))
PATH_TRACK_1         = resource_path(os.path.join(TASK_IMG, "taks_zuo1_zhuizong.bmp"))
PATH_TRACK_2         = resource_path(os.path.join(TASK_IMG, "taks_you1_zhuizong.bmp"))
PATH_TELEPORT        = resource_path(os.path.join(TASK_IMG, "dianhuatingchuansong.bmp"))
PATH_HAND            = resource_path(os.path.join(TASK_IMG, "hand.bmp"))
PATH_NAKUPEIDA_1     = resource_path(os.path.join(TASK_IMG, "nakupeidazhichi1.png"))
PATH_QIANCHENG       = resource_path(os.path.join(TASK_IMG, "qianchengxuyuan.png"))
PATH_QIFU            = resource_path(os.path.join(TASK_IMG, "qifu.png"))
PATH_PINGANFU        = resource_path(os.path.join(TASK_IMG, "pinganfu.png"))
PATH_TY_QUEREN       = resource_path(os.path.join(TASK_IMG, "ty_queren.png"))
PATH_TY_QUEREN1      = resource_path(os.path.join(TASK_IMG, "ty_queren1.png"))
PATH_TX_LINGQU       = resource_path(os.path.join(TASK_IMG, "tx_lingqu.png"))
PATH_TX_LINGQU1      = resource_path(os.path.join(TASK_IMG, "tx_lingqu1.png"))
PATH_LINGQU_JNP      = resource_path(os.path.join(TASK_IMG, "lingqujinianpin.png"))
PATH_LL_QUANBU       = resource_path(os.path.join(TASK_IMG, "ll_quanbulingqu.png"))
PATH_FPAISHE         = resource_path(os.path.join(TASK_IMG, "fpaishefengjing.png"))
PATH_ANXIAKUAIMEN    = resource_path(os.path.join(TASK_IMG, "anxiakuaimen.png"))
PATH_SHOOT           = resource_path(os.path.join(TASK_IMG, "paishe.png"))
PATH_SHOOT1          = resource_path(os.path.join(TASK_IMG, "paishe1.png"))
PATH_SHOOT2          = resource_path(os.path.join(TASK_IMG, "paishe2.png"))
PATH_END             = resource_path(os.path.join(TASK_IMG, "END.png"))
PATH_DUANXIN         = resource_path(os.path.join(TASK_IMG, "duanxinduihua01.bmp"))
PATH_11D_1           = resource_path(os.path.join(TASK_IMG, "11dian1.png"))
PATH_11D_GIFT        = resource_path(os.path.join(TASK_IMG, "11dianzengli.png"))
PATH_CONFIRM         = resource_path(os.path.join(TASK_IMG, "tishiqueren.png"))

MATCH_THRESH = 0.7

class TaskWorker:
    def __init__(self, hwnd, stop_event, config, status_cb, finish_cb):
        self.hwnd = hwnd
        self.stop_event = stop_event
        self.config = config
        self._status_cb = status_cb
        self._finish_cb = finish_cb
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive(): return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _safe_sleep(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            if self.stop_event.is_set(): return False
            time.sleep(0.1)
        return True

    def _press_key_bg(self, vk, duration=0.05):
        if self.stop_event.is_set(): return
        hwnd = get_game_hwnd()
        if not hwnd: return
        try:
            win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, vk, 0)
            if not self._safe_sleep(duration):
                win32gui.PostMessage(hwnd, win32con.WM_KEYUP, vk, 0); return
            win32gui.PostMessage(hwnd, win32con.WM_KEYUP, vk, 0)
        except Exception as e: logui.error(f"后台按键失败: {e}")

    def _press_esc_bg(self): self._press_key_bg(win32con.VK_ESCAPE, 0.1)
    def _press_f_bg(self):   self._press_key_bg(0x46, 0.1)

    def _click_foreground(self, client_x, client_y):
        if self.stop_event.is_set(): return
        hwnd = get_game_hwnd()
        if not hwnd: return
        try: simulate_mouse_click_relative(hwnd, client_x, client_y)
        except Exception as e: logui.error(f"前台点击失败: {e}")

    def _run(self):
        delay = self.config.get("delay_ms", 50) / 1000.0
        auto_pick = self.config.get("auto_pick", False)
        dialog_opt = self.config.get("dialog_option", 1)
        no_remind_skip = self.config.get("no_remind_skip", False)

        self._status_cb("任务开始...")
        logui.info("任务线程启动")
        try:
            while not self.stop_event.is_set():
                hwnd = get_game_hwnd()
                if not hwnd or not win32gui.IsWindow(hwnd):
                    self._status_cb("窗口丢失，等待...")
                    if not self._safe_sleep(1.0): break
                    continue

                try: frame = capture_frame(hwnd)
                except: self._safe_sleep(0.2); continue
                if frame is None: self._safe_sleep(delay); continue

                action_taken = False
                try:
                    if self._find_and_press_esc(PATH_GET_ITEM, 831, 411, 1084, 525):
                        logui.info("获得物品，按ESC"); self._status_cb("获得物品"); action_taken = True

                    if not action_taken and self._find_forbid_dialog():
                        logui.info("对话不可跳过，处理对话选项"); self._status_cb("处理对话"); self._handle_dialog(dialog_opt); action_taken = True

                    if not action_taken and self._find_region(PATH_SKIP_STORY, 1822, 23, 1897, 103):
                        self._press_esc_bg()
                        logui.info("跳过剧情"); self._status_cb("跳过剧情")
                        if no_remind_skip:
                            logui.info("点击今日不再提示 (1659, 692)"); self._click_foreground(1659, 692); self._safe_sleep(0.5)
                        action_taken = True

                    if not action_taken and self._find_and_click_any([PATH_TRACK_1, PATH_TRACK_2], 70, 2, 1874, 1038):
                        logui.info("点击追踪任务"); self._status_cb("追踪任务"); action_taken = True

                    if not action_taken and self._find_and_click(PATH_TELEPORT, 1611, 943, 1688, 991):
                        logui.info("点击传送"); self._status_cb("传送"); action_taken = True

                    if not action_taken and auto_pick and self._find_and_press_f(PATH_HAND, 1159, 563, 1199, 610):
                        logui.info("自动拾取"); self._status_cb("自动拾取"); action_taken = True

                    if not action_taken and self._find_and_press_f(PATH_FPAISHE, 1135, 534, 1375, 654):
                        logui.info("拍摄风景 按F"); self._status_cb("拍摄风景"); action_taken = True

                    if not action_taken and self._find_and_press_f(PATH_ANXIAKUAIMEN, 1612, 239, 1815, 332):
                        logui.info("按下快门 按F"); self._status_cb("按下快门"); action_taken = True

                    # --- 新增任务步骤 ---
                    if not action_taken and self._find_and_press_f(PATH_NAKUPEIDA_1, 1132, 545, 1407, 643):
                        logui.info("纳库佩达之池 按F"); self._status_cb("纳库佩达之池"); action_taken = True

                    if not action_taken and self._find_and_press_f(PATH_QIANCHENG, 1294, 597, 1463, 707):
                        logui.info("虔诚许愿 按F"); self._status_cb("虔诚许愿"); action_taken = True

                    if not action_taken and self._find_and_press_f(PATH_QIFU, 1128, 530, 1347, 669):
                        logui.info("祈福 按F"); self._status_cb("祈福"); action_taken = True

                    if not action_taken and self._find_and_click(PATH_PINGANFU, 1390, 169, 1467, 251):
                        logui.info("点击平安符"); self._status_cb("平安符"); action_taken = True

                    if not action_taken:
                        if self._find_and_click(PATH_TY_QUEREN, 1180, 703, 1864, 1021):
                            logui.info("确认祈福 (ty_queren)"); self._status_cb("确认祈福"); action_taken = True
                        elif self._find_and_click(PATH_TY_QUEREN1, 1097, 697, 1155, 733):
                            logui.info("确认祈福 (ty_queren1)"); self._status_cb("确认祈福"); action_taken = True

                    if not action_taken:
                        if self._find_and_click(PATH_TX_LINGQU, 1553, 180, 1834, 907):
                            logui.info("领取 (tx_lingqu)"); self._status_cb("领取"); action_taken = True
                        elif self._find_and_click(PATH_TX_LINGQU1, 1528, 254, 1831, 915):
                            logui.info("领取 (tx_lingqu1)"); self._status_cb("领取"); action_taken = True

                    if not action_taken and self._find_and_press_f(PATH_LINGQU_JNP, 1117, 515, 1331, 667):
                        logui.info("领取纪念品 按F"); self._status_cb("领取纪念品"); action_taken = True

                    if not action_taken and self._find_and_click(PATH_LL_QUANBU, 1269, 865, 1403, 915):
                        logui.info("历练奖励 全部领取"); self._status_cb("历练奖励"); action_taken = True

                    # --- 原有拍摄流程 ---
                    if not action_taken:
                        if self._find_and_press_f(PATH_SHOOT, 1134, 551, 1237, 630):
                            logui.info("拍摄 按F"); self._status_cb("拍摄1"); action_taken = True
                        elif self._find_and_press_f(PATH_SHOOT1, 949, 236, 974, 257):
                            logui.info("拍摄2 按F"); self._status_cb("拍摄2"); action_taken = True
                        elif self._find_and_press_esc(PATH_SHOOT2, 47, 994, 90, 1039):
                            logui.info("拍摄 按ESC"); self._status_cb("拍摄ESC"); action_taken = True
                        elif self._find_and_press_esc(PATH_END, 1195, 848, 1358, 947):
                            logui.info("拍摄结束 END"); self._status_cb("拍摄结束"); action_taken = True
                        elif self._find_and_click(PATH_DUANXIN, 944, 662, 1005, 723):
                            logui.info("点击短信对话"); self._status_cb("短信对话"); action_taken = True

                    # --- 11点赠礼 ---
                    if not action_taken:
                        if self._find_and_press_f(PATH_11D_1, 1092, 472, 1363, 702):
                            logui.info("11点赠礼 按F"); self._status_cb("11点赠礼1"); action_taken = True
                        elif self._find_and_press_f(PATH_11D_GIFT, 1197, 571, 1293, 609):
                            logui.info("11点赠礼2 按F"); self._status_cb("11点赠礼2"); action_taken = True
                        elif self._find_and_click(PATH_CONFIRM, 1094, 664, 1220, 757):
                            logui.info("点击确认提示"); self._status_cb("确认提示"); action_taken = True

                except Exception as e: logui.error(f"任务步骤异常: {e}"); self._safe_sleep(0.5)

                if not action_taken: self._safe_sleep(delay)
                else: self._safe_sleep(0.3)

        except Exception as e:
            logui.error(f"任务线程严重异常: {e}\n{traceback.format_exc()}")
            self._status_cb(f"错误: {e}")
        finally:
            logui.info("任务线程退出"); self._finish_cb()

    # ---------- 图像检测函数 ----------
    def _get_roi(self, frame, l, t, r, b):
        h, w = frame.shape[:2]
        x1 = max(0, min(l, w-1)); y1 = max(0, min(t, h-1))
        x2 = max(x1+1, min(r, w)); y2 = max(y1+1, min(b, h))
        if x2 <= x1 or y2 <= y1: return None
        return frame[y1:y2, x1:x2]

    def _read_template(self, path):
        if self.stop_event.is_set(): return None
        tpl = load_template(path)
        if tpl is None: logui.error(f"无法读取模板: {path}")
        return tpl

    def _match(self, roi, tpl):
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        return max_val, max_loc

    def _find_region(self, tmpl, l, t, r, b):
        if self.stop_event.is_set(): return False
        hwnd = get_game_hwnd()
        if not hwnd or not win32gui.IsWindow(hwnd): return False
        frame = capture_frame(hwnd)
        if frame is None: return False
        roi = self._get_roi(frame, l, t, r, b)
        if roi is None: return False
        tpl = self._read_template(tmpl)
        if tpl is None: return False
        if roi.shape[0] < tpl.shape[0] or roi.shape[1] < tpl.shape[1]: return False
        max_val, _ = self._match(roi, tpl)
        return max_val >= MATCH_THRESH

    def _get_click_pos(self, tmpl, l, t, r, b):
        hwnd = get_game_hwnd()
        if not hwnd or not win32gui.IsWindow(hwnd): return None
        frame = capture_frame(hwnd)
        if frame is None: return None
        roi = self._get_roi(frame, l, t, r, b)
        if roi is None: return None
        tpl = self._read_template(tmpl)
        if tpl is None: return None
        if roi.shape[0] < tpl.shape[0] or roi.shape[1] < tpl.shape[1]: return None
        max_val, max_loc = self._match(roi, tpl)
        if max_val < MATCH_THRESH: return None
        th, tw = tpl.shape
        x1 = max(0, min(l, frame.shape[1]-1)); y1 = max(0, min(t, frame.shape[0]-1))
        return (x1 + max_loc[0] + tw//2, y1 + max_loc[1] + th//2)

    def _click_template(self, tmpl, l, t, r, b):
        pos = self._get_click_pos(tmpl, l, t, r, b)
        if pos is None: return False
        self._click_foreground(pos[0], pos[1])
        return True

    def _find_and_press_f(self, tmpl, l, t, r, b):
        if self._find_region(tmpl, l, t, r, b): self._press_f_bg(); return True
        return False

    def _find_and_press_esc(self, tmpl, l, t, r, b):
        if self._find_region(tmpl, l, t, r, b): self._press_esc_bg(); return True
        return False

    def _find_and_click(self, tmpl, l, t, r, b):
        return self._click_template(tmpl, l, t, r, b)

    def _find_and_click_any(self, tmpls, l, t, r, b):
        for tp in tmpls:
            if self._click_template(tp, l, t, r, b): return True
        return False

    def _find_forbid_dialog(self):
        return (self._find_region(PATH_DIALOG_FORBID_1, 1743, 22, 1805, 95) and
                self._find_region(PATH_DIALOG_FORBID_2, 1819, 28, 1880, 93))

    def _handle_dialog(self, opt):
        hwnd = get_game_hwnd()
        if not hwnd: return
        if opt == 1: self._press_f_bg()
        elif opt == 2: self._click_foreground(1416, 808)
        elif opt == 3: self._click_foreground(1427, 880)