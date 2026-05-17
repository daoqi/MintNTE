# -*- coding: utf-8 -*-
# core/Fortissimo/background/background_ui.py
import sys, os, cv2, numpy as np, win32gui
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QSpinBox, QGroupBox, QGridLayout, QStatusBar, QSplitter,
                             QMessageBox)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QImage, QPixmap, QFont, QIcon
import core.Fortissimo.background.background_core as bgc
from Module.Hwnd.game_hwnd import get_game_hwnd

# 项目根目录（本文件在 core/Fortissimo/background/ 下，往上四级到根目录）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

NEON_STYLE = """
QMainWindow { background-color: #050510; }
QGroupBox { color: #00ffff; border: 2px solid #00ffff; border-radius: 5px; margin-top: 10px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
QLabel { color: #00ffff; }
QPushButton { background-color: #0a0a2a; border: 2px solid #00ffff; border-radius: 5px; color: #00ffff; padding: 5px 12px; }
QPushButton:hover { background-color: #00ffff; color: #050510; }
QPushButton:pressed { background-color: #0080ff; }
QLineEdit { background-color: #0a0a2a; border: 2px solid #00ffff; border-radius: 5px; color: #00ffff; padding: 3px; }
QSpinBox { background-color: #0a0a2a; border: 2px solid #00ffff; border-radius: 5px; color: #00ffff; padding: 2px; }
QStatusBar { background-color: #0a0a2a; color: #00ffff; }
"""

class Bridge(QObject):
    update_counts = pyqtSignal(list)
    update_states = pyqtSignal(list)

class BackgroundWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fortissimo 后台演奏")
        self.resize(1400, 820)

        # 图标
        try:
            from config import TITLE_LOGO_PATH
            if os.path.exists(TITLE_LOGO_PATH):
                self.setWindowIcon(QIcon(TITLE_LOGO_PATH))
        except:
            pass

        self.player = None
        self.running = False
        self.bridge = Bridge()
        self.bridge.update_counts.connect(self.on_counts)
        self.bridge.update_states.connect(self.on_states)

        # 默认参数
        self.default_pix = {'D': 7, 'F': 7, 'J': 4, 'K': 3}
        self.default_cool = {'D': 20, 'F': 20, 'J': 12, 'K': 20}
        self.default_rad = {'D': 20, 'F': 21, 'J': 20, 'K': 20}
        self.default_yoff = {'D': 10, 'F': 10, 'J': 10, 'K': 10}

        self.init_ui()
        self.setStyleSheet(NEON_STYLE)

        # 状态刷新定时器（30ms）
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.setInterval(30)

        # 句柄自动轮询定时器
        self.hwnd_timer = QTimer()
        self.hwnd_timer.timeout.connect(self.refresh_hwnd)
        self.hwnd_timer.start(1000)

        # 初始填充句柄
        self.auto_fill_hwnd()

    # ----- 窗口句柄管理 -----
    def auto_fill_hwnd(self):
        hwnd = get_game_hwnd()
        if hwnd:
            self.edit_hwnd.setText(str(hwnd))
            self.status_bar.showMessage("已获取锁定窗口句柄")
        else:
            self.btn_start.setEnabled(False)
            self.status_bar.showMessage("⚠ 未获取到游戏窗口句柄，请先在主界面锁定窗口")

    def refresh_hwnd(self):
        if self.running:
            return
        try:
            cur = int(self.edit_hwnd.text()) if self.edit_hwnd.text() else None
        except:
            cur = None
        locked = get_game_hwnd()
        if locked and locked != cur:
            self.edit_hwnd.setText(str(locked))
            self.status_bar.showMessage("窗口句柄已自动更新")
            self.btn_start.setEnabled(True)
        elif not locked:
            self.status_bar.showMessage("⚠ 未锁定任何窗口，请前往「窗口检测」")
            self.btn_start.setEnabled(False)

    # ----- 界面构建 -----
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # 控制栏
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("窗口句柄:"))
        self.edit_hwnd = QLineEdit()
        self.edit_hwnd.setFixedWidth(100)
        ctrl_layout.addWidget(self.edit_hwnd)

        self.btn_start = QPushButton("开始演奏")
        self.btn_start.clicked.connect(self.start_stop)
        ctrl_layout.addWidget(self.btn_start)
        ctrl_layout.addStretch()
        main_layout.addLayout(ctrl_layout)

        # 分割器
        main_splitter = QSplitter(Qt.Horizontal)

        # 左侧轨道配置
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        track_names = ['D', 'F', 'J', 'K']
        self.track_params = {}
        self.track_previews = {}
        self.track_visible = {name: True for name in track_names}
        self.track_vis_btns = {}

        for name in track_names:
            group = QGroupBox(f"轨道 {name}")
            hbox = QHBoxLayout()

            # 参数控件
            control_layout = QGridLayout()
            control_layout.addWidget(QLabel("触发像素:"), 0, 0)
            spin_pix = QSpinBox()
            spin_pix.setRange(1, 200)
            spin_pix.setValue(self.default_pix[name])
            control_layout.addWidget(spin_pix, 0, 1)

            control_layout.addWidget(QLabel("冷却 (ms):"), 1, 0)
            spin_cool = QSpinBox()
            spin_cool.setRange(10, 500)
            spin_cool.setValue(self.default_cool[name])
            spin_cool.setSuffix(" ms")
            control_layout.addWidget(spin_cool, 1, 1)

            control_layout.addWidget(QLabel("半径:"), 2, 0)
            spin_rad = QSpinBox()
            spin_rad.setRange(5, 50)
            spin_rad.setValue(self.default_rad[name])
            control_layout.addWidget(spin_rad, 2, 1)

            control_layout.addWidget(QLabel("Y偏移:"), 3, 0)
            spin_yoff = QSpinBox()
            spin_yoff.setRange(-30, 30)
            spin_yoff.setValue(self.default_yoff[name])
            control_layout.addWidget(spin_yoff, 3, 1)

            hbox.addLayout(control_layout, 1)

            # 预览图
            img_label = QLabel()
            img_label.setFixedSize(200, 200)
            img_label.setStyleSheet("border: 2px solid #00ffff;")
            hbox.addWidget(img_label, 0, Qt.AlignCenter)

            # 预览开关按钮
            btn_toggle = QPushButton("关闭预览")
            btn_toggle.setCheckable(True)
            btn_toggle.setChecked(True)
            btn_toggle.clicked.connect(lambda checked, n=name: self.toggle_preview(n, checked))
            hbox.addWidget(btn_toggle, 0, Qt.AlignCenter)

            group.setLayout(hbox)
            left_layout.addWidget(group)

            self.track_params[name] = {
                'pix': spin_pix,
                'cool': spin_cool,
                'rad': spin_rad,
                'yoff': spin_yoff
            }
            self.track_previews[name] = img_label
            self.track_vis_btns[name] = btn_toggle

        main_splitter.addWidget(left_widget)

        # 右侧状态区
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        status_group = QGroupBox("触发状态")
        s_layout = QGridLayout()
        self.lbl_counts = []
        self.lbl_leds = []
        for i, name in enumerate(track_names):
            s_layout.addWidget(QLabel(f"{name}:"), i, 0)
            cnt_label = QLabel("0")
            self.lbl_counts.append(cnt_label)
            s_layout.addWidget(cnt_label, i, 1)
            led_label = QLabel("⚫")
            led_label.setFont(QFont("Arial", 16))
            self.lbl_leds.append(led_label)
            s_layout.addWidget(led_label, i, 2)
        status_group.setLayout(s_layout)
        right_layout.addWidget(status_group)
        right_layout.addStretch()

        main_splitter.addWidget(right_widget)
        main_layout.addWidget(main_splitter, stretch=3)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    def toggle_preview(self, name, checked):
        self.track_visible[name] = checked
        self.track_previews[name].setVisible(checked)
        self.track_vis_btns[name].setText("关闭预览" if checked else "打开预览")

    # ----- 开始/停止控制 -----
    def start_stop(self):
        if self.running:
            self.stop_player()
        else:
            self.start_player()

    def start_player(self):
        try:
            hwnd = int(self.edit_hwnd.text())
        except:
            QMessageBox.critical(self, "错误", "窗口句柄无效")
            return
        if not win32gui.IsWindow(hwnd):
            QMessageBox.critical(self, "错误", "窗口句柄无效或游戏已关闭")
            return

        self.sync_params_to_core()
        self.player = bgc.BackgroundPlayer(hwnd, bgc.TRACKS)
        self.player.start()
        self.running = True
        self.btn_start.setText("停止演奏")
        self.status_bar.showMessage("演奏中...")
        self.timer.start()

    def stop_player(self):
        self.timer.stop()
        if self.player:
            self.player.stop()
        self.running = False
        self.btn_start.setText("开始演奏")
        self.status_bar.showMessage("已停止")

    def sync_params_to_core(self):
        for name in ['D', 'F', 'J', 'K']:
            bgc.MIN_TRIGGER_PIXELS = bgc.MIN_TRIGGER_PIXELS or {}
            bgc.MIN_TRIGGER_PIXELS[name] = self.track_params[name]['pix'].value()
            bgc.COOLDOWN_MS = bgc.COOLDOWN_MS or {}
            bgc.COOLDOWN_MS[name] = self.track_params[name]['cool'].value()
            bgc.JUDGE_RADIUS = bgc.JUDGE_RADIUS or {}
            bgc.JUDGE_RADIUS[name] = self.track_params[name]['rad'].value()
            bgc.JUDGE_Y_OFFSET = bgc.JUDGE_Y_OFFSET or {}
            bgc.JUDGE_Y_OFFSET[name] = self.track_params[name]['yoff'].value()

    # ----- 实时预览（全部使用后台截图） -----
    def tick(self):
        if not self.running or not self.player:
            return

        self.sync_params_to_core()

        # 更新触发状态
        try:
            counts, actives, _ = self.player.get_shared_data()
        except:
            return
        self.bridge.update_counts.emit(counts)
        self.bridge.update_states.emit(actives)

        # 使用后台截图更新四个预览窗口
        hwnd = self.player.hwnd
        bg_frame = bgc.capture_window_background(hwnd)  # 纯后台截图
        if bg_frame is None:
            return  # 截图失败，不清除预览，保持上一帧

        for name in ['D', 'F', 'J', 'K']:
            if self.track_visible[name]:
                crop = self.crop_from_frame(bg_frame, name, 200)
                if crop is not None:
                    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb.shape
                    bytes_per_line = ch * w
                    qt_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                    pixmap = QPixmap.fromImage(qt_img)
                    self.track_previews[name].setPixmap(pixmap)
                else:
                    self.track_previews[name].clear()
            else:
                self.track_previews[name].clear()

    def crop_from_frame(self, frame, track_name, size=200):
        """从后台截图中裁剪对应轨道的预览区域，并画上判定圆"""
        if frame is None:
            return None
        track = next((t for t in bgc.TRACKS if t['name'] == track_name), None)
        if not track:
            return None
        cx, cy = track['circle_base']
        r = bgc.JUDGE_RADIUS.get(track_name, 15) if bgc.JUDGE_RADIUS else 15
        offset_y = bgc.JUDGE_Y_OFFSET.get(track_name, 0) if bgc.JUDGE_Y_OFFSET else 0
        cy += offset_y

        half = size // 2
        x1 = max(0, cx - half)
        y1 = max(0, cy - half)
        x2 = min(frame.shape[1], cx + half)
        y2 = min(frame.shape[0], cy + half)
        if x2 <= x1 or y2 <= y1:
            return None

        crop = frame[y1:y2, x1:x2].copy()
        # 画上黄色的判定圆
        cv2.circle(crop, (cx - x1, cy - y1), r, (0, 255, 255), 2)
        return crop

    # ----- 数据更新 slots -----
    def on_counts(self, counts):
        for i, cnt in enumerate(counts):
            self.lbl_counts[i].setText(str(cnt))

    def on_states(self, actives):
        for i, active in enumerate(actives):
            self.lbl_leds[i].setText("🟢" if active else "🔴")

    def closeEvent(self, event):
        self.stop_player()
        event.accept()