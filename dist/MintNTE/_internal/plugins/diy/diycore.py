"""
diycore.py - 动作执行引擎（后台按键、找图、循环控制）
"""

import time
import json
import threading
import cv2
import numpy as np
import win32gui
import win32con
import win32api
from ctypes import windll
from PIL import ImageGrab

# ---------- 后台辅助函数（沿用欺骗代码思路）----------
def find_window(title):
    """根据窗口标题查找句柄（精确匹配）"""
    hwnd = None
    def callback(h, _):
        nonlocal hwnd
        if win32gui.GetWindowText(h) == title:
            hwnd = h
    win32gui.EnumWindows(callback, None)
    return hwnd

def fake_activate(hwnd):
    """持续假激活，让游戏以为窗口在前台"""
    try:
        win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, 1, 0)
    except:
        pass

def send_key(hwnd, key, interval=0.01):
    """后台发送按键（key为虚拟键码，如0x46=F）"""
    fake_activate(hwnd)
    win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, key, 0)
    time.sleep(interval)
    win32gui.PostMessage(hwnd, win32con.WM_KEYUP, key, 0)

def send_click(hwnd, x, y):
    """后台发送鼠标左键点击（客户区坐标）"""
    fake_activate(hwnd)
    lparam = win32api.MAKELONG(x, y)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
    time.sleep(0.02)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)

def capture_window(hwnd):
    """截取窗口客户区图片（返回BGR格式）"""
    left, top, right, bot = win32gui.GetClientRect(hwnd)
    left, top = win32gui.ClientToScreen(hwnd, (left, top))
    right, bot = win32gui.ClientToScreen(hwnd, (right, bot))
    img = ImageGrab.grab((left, top, right, bot))
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

# ---------- 动作执行器 ----------
class ActionRunner:
    def __init__(self, actions, stop_event, status_callback=None):
        self.actions = actions           # 动作列表
        self.stop_event = stop_event     # 线程停止事件
        self.status = status_callback    # 回调输出状态
        self.hwnd = None

    def log(self, msg):
        if self.status:
            self.status(msg)

    def run(self):
        """执行动作序列（栈式循环处理）"""
        self.hwnd = None
        idx = 0
        loop_stack = []  # 保存 (type, start_idx, current_iter, max_iter/condition)
        while idx < len(self.actions):
            if self.stop_event.is_set():
                self.log("🛑 用户停止")
                return

            action = self.actions[idx]
            act_type = action.get("type")

            # ---------- 基础动作 ----------
            if act_type == "wait":
                # 延时（秒）
                delay = float(action.get("value", 1))
                time.sleep(delay)

            elif act_type == "key":
                # 按键：需要窗口句柄
                if not self.hwnd:
                    self.hwnd = find_window(action.get("window", ""))
                    if not self.hwnd:
                        self.log("❌ 未找到窗口")
                        return
                key = int(action.get("key", 0x46), 16) if isinstance(action.get("key"), str) else action.get("key")
                send_key(self.hwnd, key)

            elif act_type == "click":
                if not self.hwnd:
                    self.hwnd = find_window(action.get("window", ""))
                    if not self.hwnd:
                        self.log("❌ 未找到窗口")
                        return
                x, y = int(action.get("x", 0)), int(action.get("y", 0))
                send_click(self.hwnd, x, y)

            elif act_type == "find_image":
                # 找图并可选点击偏移
                path = action.get("path", "")
                confidence = float(action.get("confidence", 0.8))
                offset_x = int(action.get("offset_x", 0))
                offset_y = int(action.get("offset_y", 0))
                do_click = action.get("do_click", False)

                if not self.hwnd:
                    self.hwnd = find_window(action.get("window", ""))
                    if not self.hwnd:
                        self.log("❌ 未找到窗口")
                        return

                screenshot = capture_window(self.hwnd)
                template = cv2.imread(path)
                if template is None:
                    self.log(f"❌ 找不到图片：{path}")
                else:
                    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                    if max_val >= confidence:
                        self.log(f"✅ 找到图片，相似度：{max_val:.2f}")
                        if do_click:
                            click_x = max_loc[0] + offset_x
                            click_y = max_loc[1] + offset_y
                            send_click(self.hwnd, click_x, click_y)
                            self.log(f"🖱️ 点击位置：{click_x}, {click_y}")
                    else:
                        self.log(f"❌ 未找到图片（最高相似度：{max_val:.2f}）")

            # ---------- 循环控制 ----------
            elif act_type == "for_start":
                # For循环开始：记录循环信息
                count = int(action.get("count", 1))
                loop_stack.append({
                    "type": "for",
                    "start_idx": idx + 1,
                    "iter": 0,
                    "max": count
                })
                self.log(f"🔁 For循环开始（{count}次）")

            elif act_type == "while_start":
                loop_stack.append({
                    "type": "while",
                    "start_idx": idx + 1,
                    "condition": action.get("condition", "True")  # 可扩展
                })
                self.log("🔁 While循环开始")

            elif act_type == "loop_end":
                if not loop_stack:
                    self.log("⚠️ 多余的循环结束标记，忽略")
                else:
                    top = loop_stack[-1]
                    top["iter"] += 1
                    if top["type"] == "for" and top["iter"] < top["max"]:
                        idx = top["start_idx"] - 1  # 之后会+1
                        self.log(f"↩️ 回到For循环开始（第{top['iter']+1}次）")
                    elif top["type"] == "while":
                        # While条件始终为真（无限循环），由退出循环动作停止
                        idx = top["start_idx"] - 1
                    else:
                        loop_stack.pop()
                        self.log("🔚 循环结束")

            elif act_type == "exit_loop":
                if loop_stack:
                    loop_stack.pop()
                    # 找到最近的 loop_end，跳过整個循环
                    # 简单处理：向后找到对应的 loop_end 并跳转到其后
                    depth = 1
                    for j in range(idx+1, len(self.actions)):
                        if self.actions[j]["type"] == "loop_end":
                            depth -= 1
                            if depth == 0:
                                idx = j
                                break
                        elif self.actions[j]["type"] in ("for_start", "while_start"):
                            depth += 1
                    self.log("⏹️ 退出当前循环")
                else:
                    self.log("⚠️ 无循环可退出")

            idx += 1

        self.log("✅ 所有动作执行完毕")