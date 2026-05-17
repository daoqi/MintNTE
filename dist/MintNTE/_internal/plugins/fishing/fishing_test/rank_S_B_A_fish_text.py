# core/fishing/rank_capture.py
#仅用于自动截图保存SAB级鱼类使用并无其他作�?仅调试用
# 窗口句柄后台找图，固定句�?20977790（调试用，你如果需要调试用需要自己修改窗口句柄）
# 使用 PrintWindow 后台截图 + WM_ACTIVATE 欺骗窗口
# 在区�?(828,946,1082,1014) 寻找 dianjikongbai.png
# 在区�?(1069,346,1128,409) 寻找 rank_b_fish.bmp / rank_a_fish.bmp
# 如果两个 rank 图片都未找到，则将该区域截取保存为递增 BMP
# 截图保存目录：fishingimages/rank_b_fish/

import os
import sys
import time
import cv2
import numpy as np
import win32gui

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.fishing.fishing_utils import capture_window_to_cv

# ---------- 固定参数 ----------
HWND = 20977790                       # 调试句柄，正式使用可改为 get_game_hwnd()
IMG_DIR = os.path.join(BASE_DIR, "core", "fishing", "fishingimages")
SAVE_DIR = os.path.join(IMG_DIR, "rank_b_fish")  # 截图保存目录
os.makedirs(SAVE_DIR, exist_ok=True)

# 模板路径
PATH_DIANJIKONGBAI = os.path.join(IMG_DIR, "dianjikongbai.png")
PATH_RANK_B_FISH    = os.path.join(IMG_DIR, "rank_b_fish.bmp")
PATH_RANK_A_FISH    = os.path.join(IMG_DIR, "rank_a_fish.bmp")

# 找图区域
ROI_DIANJIKONGBAI = (828, 946, 1082, 1014)
ROI_RANK          = (1069, 346, 1128, 409)

MATCH_THRESH = 0.7   # 匹配阈�?

# ---------- 工具函数 ----------
def match_region(frame, template_path, left, top, right, bottom):
    """在帧的指定区域内匹配模板，返回中心坐标或 None"""
    h, w = frame.shape[:2]
    x1 = max(0, left)
    y1 = max(0, top)
    x2 = min(w, right)
    y2 = min(h, bottom)
    if x2 - x1 < 5 or y2 - y1 < 5:
        return None
    roi = frame[y1:y2, x1:x2]
    tpl = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
    if tpl is None:
        print(f"无法读取模板：{template_path}")
        return None
    roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    res = cv2.matchTemplate(roi_gray, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val >= MATCH_THRESH:
        th, tw = tpl.shape
        cx = max_loc[0] + tw // 2 + x1
        cy = max_loc[1] + th // 2 + y1
        return (cx, cy)
    return None

def get_next_index():
    """获取下一个截图序�?""
    existing = [f for f in os.listdir(SAVE_DIR) if f.endswith(".bmp")]
    if not existing:
        return 1
    nums = []
    for f in existing:
        try:
            nums.append(int(os.path.splitext(f)[0]))
        except:
            continue
    return max(nums) + 1

def save_roi(frame, left, top, right, bottom):
    """保存指定区域�?BMP 文件"""
    h, w = frame.shape[:2]
    x1, y1 = max(0, left), max(0, top)
    x2, y2 = min(w, right), min(h, bottom)
    if x2 <= x1 or y2 <= y1:
        return
    roi = frame[y1:y2, x1:x2]
    idx = get_next_index()
    filename = f"{idx:04d}.bmp"
    savepath = os.path.join(SAVE_DIR, filename)
    cv2.imwrite(savepath, roi)
    print(f"截图已保存：{savepath}")

# ---------- 主循�?----------
def main():
    print("开始监控区�?.. �?Ctrl+C 停止")
    while True:
        # 后台截图
        frame = capture_window_to_cv(HWND)
        if frame is None:
            print("截图失败，等待窗�?..")
            time.sleep(1)
            continue

        # 1. 检�?dianjikongbai.png
        pos = match_region(frame, PATH_DIANJIKONGBAI, *ROI_DIANJIKONGBAI)
        if pos:
            print("找到 dianjikongbai.png，开始判�?rank �?)
            found_b = match_region(frame, PATH_RANK_B_FISH, *ROI_RANK) is not None
            found_a = match_region(frame, PATH_RANK_A_FISH, *ROI_RANK) is not None

            if found_b:
                print("找到 rank_b_fish.bmp")
            if found_a:
                print("找到 rank_a_fish.bmp")

            if not found_b and not found_a:
                print("未找�?rank 图，准备截图保存")
                save_roi(frame, *ROI_RANK)
            else:
                print("至少找到一�?rank 图，不截�?)
        else:
            print("未找�?dianjikongbai.png")

        time.sleep(0.5)   # 检测间�?

if __name__ == "__main__":
    main()
