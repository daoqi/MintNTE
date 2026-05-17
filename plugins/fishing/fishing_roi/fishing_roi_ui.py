# core/fishing/fishing_roi/fishing_roi_ui.py
# plugins/fishing/fishing_roi/fishing_roi_ui.py
import sys
import os
import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGridLayout, QGroupBox, QApplication, QPushButton, QSlider, QSpinBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage, QIcon

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# ✅ 修正导入路径
from plugins.fishing.fishing_roi.fishing_roi_core import FishingROICore

# 基础ROI区域（客户区坐标，未偏移）
BASE_ROI = (606, 64, 1319, 85)
DEFAULT_OFFSET = 0

class FishingROIWindow(QWidget):
    def __init__(self):
        super().__init__()
        icon_path = os.path.join(BASE_DIR, "Image", "logo", "titlelogo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.roi_core = None
        self.current_offset = DEFAULT_OFFSET
        self.setup_ui()
        self.init_core()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_display)
        self.timer.start(50)
    def setup_ui(self):
        self.setWindowTitle("钓鱼ROI调试窗口 (可调偏移)")
        self.resize(1200, 800)

        main_layout = QHBoxLayout(self)

        # 左侧画面显示
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(800, 600)
        left_layout.addWidget(self.image_label)
        main_layout.addWidget(left_widget, stretch=3)

        # 右侧控制面板
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setAlignment(Qt.AlignTop)

        # 偏移量控制组
        offset_group = QGroupBox("标题栏偏移 (像素)")
        offset_layout = QVBoxLayout(offset_group)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(self.current_offset)
        self.slider.valueChanged.connect(self.on_offset_changed)
        self.spinbox = QSpinBox()
        self.spinbox.setRange(0, 100)
        self.spinbox.setValue(self.current_offset)
        self.spinbox.valueChanged.connect(self.on_offset_spin)
        offset_layout.addWidget(self.slider)
        offset_layout.addWidget(self.spinbox)

        # 提示文字
        hint_label = QLabel("如果ROI区域不准确，需要+标题偏移30")
        hint_label.setStyleSheet("color: #888888; font-size: 12px;")
        offset_layout.addWidget(hint_label)

        right_layout.addWidget(offset_group)

        # 显示当前ROI区域
        self.roi_label = QLabel(f"当前ROI区域: {self.get_current_roi()}")
        self.roi_label.setStyleSheet("color: #0ff; background: rgba(20,20,40,200); border: 1px solid #0ff; padding: 2px;")
        right_layout.addWidget(self.roi_label)

        # 颜色A数据
        group_a = QGroupBox("颜色A (#2fd5b4 浅湖蓝绿)")
        layout_a = QGridLayout(group_a)
        self.pixel_label_a = QLabel("0")
        self.rect_label_a = QLabel("无")
        for lbl in [self.pixel_label_a, self.rect_label_a]:
            lbl.setStyleSheet("background: rgba(20,20,40,200); border: 1px solid #0ff; padding: 2px; color: #0ff;")
        layout_a.addWidget(QLabel("像素数:"), 0, 0)
        layout_a.addWidget(self.pixel_label_a, 0, 1)
        layout_a.addWidget(QLabel("区域坐标:"), 1, 0)
        layout_a.addWidget(self.rect_label_a, 1, 1)
        right_layout.addWidget(group_a)

        # 颜色B数据
        group_b = QGroupBox("颜色B (#fef495 浅柠檬黄)")
        layout_b = QGridLayout(group_b)
        self.pixel_label_b = QLabel("0")
        self.rect_label_b = QLabel("无")
        for lbl in [self.pixel_label_b, self.rect_label_b]:
            lbl.setStyleSheet("background: rgba(20,20,40,200); border: 1px solid #0ff; padding: 2px; color: #0ff;")
        layout_b.addWidget(QLabel("像素数:"), 0, 0)
        layout_b.addWidget(self.pixel_label_b, 0, 1)
        layout_b.addWidget(QLabel("区域坐标:"), 1, 0)
        layout_b.addWidget(self.rect_label_b, 1, 1)
        right_layout.addWidget(group_b)

        # 刷新按钮
        self.btn_refresh = QPushButton("重启检测")
        self.btn_refresh.clicked.connect(self.restart_core)
        right_layout.addWidget(self.btn_refresh)

        main_layout.addWidget(right_widget, stretch=1)
        self.setLayout(main_layout)

        self.setStyleSheet("""
            QGroupBox { color: #0ff; border: 1px solid #0ff; border-radius: 5px; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QLabel { color: #0ff; }
            QPushButton { background-color: #2a2a3a; color: #0ff; border: 1px solid #0ff; border-radius: 5px; padding: 4px 8px; }
            QPushButton:hover { background-color: #0ff; color: #1e1e2f; }
        """)

    def get_current_roi(self):
        x1, y1, x2, y2 = BASE_ROI
        y1 += self.current_offset
        y2 += self.current_offset
        return (x1, y1, x2, y2)

    def on_offset_changed(self, value):
        self.spinbox.blockSignals(True)
        self.spinbox.setValue(value)
        self.spinbox.blockSignals(False)
        self.current_offset = value
        self.roi_label.setText(f"当前ROI区域: {self.get_current_roi()}")
        self.restart_core()

    def on_offset_spin(self, value):
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.slider.blockSignals(False)
        self.current_offset = value
        self.roi_label.setText(f"当前ROI区域: {self.get_current_roi()}")
        self.restart_core()

    def restart_core(self):
        if self.roi_core:
            self.roi_core.stop()
        new_roi = self.get_current_roi()
        self.roi_core = FishingROICore(new_roi)
        self.roi_core.start()

    def init_core(self):
        try:
            new_roi = self.get_current_roi()
            self.roi_core = FishingROICore(new_roi)
            self.roi_core.start()
        except Exception as e:
            print(f"初始化检测核心失败: {e}")

    def update_display(self):
        if not self.roi_core:
            return
        data = self.roi_core.get_data()
        self.pixel_label_a.setText(str(data['color_a']['pixels']))
        rect_a = data['color_a']['rect']
        if rect_a:
            x1, y1, x2, y2 = rect_a
            roi_x1, roi_y1, _, _ = self.get_current_roi()
            ax1, ay1, ax2, ay2 = x1 + roi_x1, y1 + roi_y1, x2 + roi_x1, y2 + roi_y1
            self.rect_label_a.setText(f"({ax1},{ay1})-({ax2},{ay2})")
        else:
            self.rect_label_a.setText("无")

        self.pixel_label_b.setText(str(data['color_b']['pixels']))
        rect_b = data['color_b']['rect']
        if rect_b:
            x1, y1, x2, y2 = rect_b
            roi_x1, roi_y1, _, _ = self.get_current_roi()
            bx1, by1, bx2, by2 = x1 + roi_x1, y1 + roi_y1, x2 + roi_x1, y2 + roi_y1
            self.rect_label_b.setText(f"({bx1},{by1})-({bx2},{by2})")
        else:
            self.rect_label_b.setText("无")

        full_img = self.roi_core.get_full_screenshot()
        if full_img is None:
            self.image_label.setText("截图失败，请检查窗口是否最小化")
            return
        overlay = full_img.copy()
        rx1, ry1, rx2, ry2 = self.get_current_roi()
        cv2.rectangle(overlay, (rx1, ry1), (rx2, ry2), (255, 0, 0), 2)

        if rect_a:
            ax1, ay1, ax2, ay2 = rect_a
            ax1 += rx1; ay1 += ry1; ax2 += rx1; ay2 += ry1
            cv2.rectangle(overlay, (ax1, ay1), (ax2, ay2), (0, 0, 255), 2)

        if rect_b:
            bx1, by1, bx2, by2 = rect_b
            bx1 += rx1; by1 += ry1; bx2 += rx1; by2 += ry1
            cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (0, 255, 0), 2)

        rgb = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qt_img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_img)
        scaled = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled)

    def closeEvent(self, event):
        if self.roi_core:
            self.roi_core.stop()
        event.accept()