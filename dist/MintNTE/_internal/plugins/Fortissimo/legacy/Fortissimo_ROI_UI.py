# core/Fortissimo/Fortissimo_ROI_UI.py
import sys
import os
import time
import logging
import threading
import cv2
import numpy as np
import win32gui
from collections import deque
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGridLayout, QGroupBox, QPushButton, QLineEdit,
    QApplication, QMessageBox, QInputDialog, QFileDialog
)
from PyQt5.QtCore import Qt, QTimer, QEvent, QPoint, QRect, pyqtSignal, QObject
from PyQt5.QtGui import QPixmap, QImage, QCursor, QPainter, QPen, QColor, QFont, QKeyEvent, QIcon

from Module.Hwnd.game_hwnd import get_game_hwnd, set_locked_hwnd
from core.Fortissimo.fortissimo_core import get_cached_screenshot, start_screenshot_updater, stop_screenshot_updater

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logger = logging.getLogger("Fortissimo.ROI")
logging.basicConfig(level=logging.INFO)

COLOR_TOLERANCE = 10
MIN_PIXELS = 5


class DetectionWorker(QObject):
    data_updated = pyqtSignal(dict)

    def __init__(self, hwnd, rois, key_colors):
        super().__init__()
        self.hwnd = hwnd
        self.rois = rois
        self.key_colors = key_colors
        self.running = False
        self.thread = None
        self.stop_event = threading.Event()
        self.last_state = {k: False for k in rois}

    def update_roi(self, key, region):
        self.rois[key] = region

    def update_color(self, key, color_hex):
        self.key_colors[key] = color_hex

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.running = True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1)

    def _run(self):
        while self.running and not self.stop_event.is_set():
            img = get_cached_screenshot()
            if img is None:
                time.sleep(0.01)
                continue
            data = {}
            for key, (x1, y1, x2, y2) in self.rois.items():
                h, w = img.shape[:2]
                if x2 > w or y2 > h or x1 < 0 or y1 < 0:
                    data[key] = (0, False)
                    continue
                roi = img[y1:y2, x1:x2]
                if roi.size == 0:
                    data[key] = (0, False)
                    continue
                hex_color = self.key_colors.get(key, "#1f1f20").lstrip('#')
                if len(hex_color) != 6:
                    hex_color = "1f1f20"
                try:
                    r = int(hex_color[0:2], 16)
                    g = int(hex_color[2:4], 16)
                    b = int(hex_color[4:6], 16)
                    target_bgr = (b, g, r)
                except:
                    target_bgr = (0x20, 0x1f, 0x1f)
                lower = np.array([max(0, c - COLOR_TOLERANCE) for c in target_bgr], dtype=np.uint8)
                upper = np.array([min(255, c + COLOR_TOLERANCE) for c in target_bgr], dtype=np.uint8)
                mask = cv2.inRange(roi, lower, upper)
                pixel_count = cv2.countNonZero(mask)
                matched = pixel_count > MIN_PIXELS
                triggered = matched and not self.last_state[key]
                self.last_state[key] = matched
                data[key] = (pixel_count, triggered)
            self.data_updated.emit(data)
            time.sleep(0.005)


class FullscreenColorPicker(QWidget):
    def __init__(self, target_hwnd, callback, cancel_callback=None):
        super().__init__()
        self.target_hwnd = target_hwnd
        self.callback = callback
        self.cancel_callback = cancel_callback
        self.frozen_img = None
        self.mouse_pos = QPoint(0, 0)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.showFullScreen()
        self.setStyleSheet("background-color: rgba(0,0,0,180);")
        self.capture_fullscreen()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(30)
        self.installEventFilter(self)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()

    def capture_fullscreen(self):
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                self.frozen_img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        except ImportError:
            from PIL import ImageGrab
            pil_img = ImageGrab.grab()
            self.frozen_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception as e:
            logger.error(f"全屏截图失败: {e}")

    def get_window_client_pos(self, screen_pos):
        if not self.target_hwnd or not win32gui.IsWindow(self.target_hwnd):
            return None
        rect = win32gui.GetWindowRect(self.target_hwnd)
        return (screen_pos.x() - rect[0], screen_pos.y() - rect[1])

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseMove:
            self.mouse_pos = event.pos()
            self.update()
            return True
        if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            self.pick_color()
            return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self.close_picker(cancelled=True)
        else:
            super().keyPressEvent(event)

    def pick_color(self):
        screen_pos = self.mouse_pos
        client_pos = self.get_window_client_pos(screen_pos)
        if client_pos is None:
            self.close_picker(cancelled=True)
            return
        cx, cy = client_pos
        if self.frozen_img is not None:
            x, y = screen_pos.x(), screen_pos.y()
            h, w = self.frozen_img.shape[:2]
            if 0 <= x < w and 0 <= y < h:
                bgr = self.frozen_img[y, x]
                rgb = (bgr[2], bgr[1], bgr[0])
                hex_color = "#{:02X}{:02X}{:02X}".format(rgb[0], rgb[1], rgb[2])
                if self.callback:
                    self.callback(hex_color, cx, cy)
                self.close_picker(cancelled=False)
                return
        self.close_picker(cancelled=True)

    def close_picker(self, cancelled=False):
        self.timer.stop()
        self.close()
        if cancelled and self.cancel_callback:
            self.cancel_callback()

    def closeEvent(self, event):
        self.close_picker(cancelled=True)
        event.accept()

    def paintEvent(self, event):
        if self.frozen_img is None:
            return
        painter = QPainter(self)
        h, w, ch = self.frozen_img.shape
        rgb = cv2.cvtColor(self.frozen_img, cv2.COLOR_BGR2RGB)
        qt_img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_img)
        painter.drawPixmap(0, 0, pixmap)
        painter.fillRect(0, 0, w, h, QColor(0, 0, 0, 160))
        center = self.mouse_pos
        radius = 60
        cx, cy = center.x(), center.y()
        if 0 <= cx < w and 0 <= cy < h:
            sample_size = 40
            half = sample_size // 2
            x1 = max(0, cx - half)
            y1 = max(0, cy - half)
            x2 = min(w, cx + half)
            y2 = min(h, cy + half)
            roi_img = self.frozen_img[y1:y2, x1:x2]
            if roi_img.size > 0:
                zoomed = cv2.resize(roi_img, (2*radius, 2*radius), interpolation=cv2.INTER_LINEAR)
                zoomed_rgb = cv2.cvtColor(zoomed, cv2.COLOR_BGR2RGB)
                zh, zw, zch = zoomed_rgb.shape
                zoomed_qimg = QImage(zoomed_rgb.data, zw, zh, zch * zw, QImage.Format_RGB888)
                zoomed_pix = QPixmap.fromImage(zoomed_qimg)
                painter.save()
                painter.setClipRect(QRect(center.x() - radius, center.y() - radius, 2*radius, 2*radius))
                painter.drawPixmap(center.x() - radius, center.y() - radius, zoomed_pix)
                painter.restore()
                painter.setPen(QPen(QColor(0, 255, 0), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(center, radius, radius)
                painter.drawLine(center.x() - 15, center.y(), center.x() + 15, center.y())
                painter.drawLine(center.x(), center.y() - 15, center.x(), center.y() + 15)
                bgr_color = self.frozen_img[cy, cx]
                rgb_color = (bgr_color[2], bgr_color[1], bgr_color[0])
                hex_color = "#{:02X}{:02X}{:02X}".format(rgb_color[0], rgb_color[1], rgb_color[2])
                client_pos = self.get_window_client_pos(center)
                coord_text = f"({client_pos[0]},{client_pos[1]})" if client_pos else "(?,?)"
                painter.setPen(QColor(0, 255, 255))
                painter.setFont(QFont("Microsoft YaHei", 10))
                painter.drawText(center.x() + radius + 5, center.y() - 20, f"颜色: {hex_color}")
                painter.drawText(center.x() + radius + 5, center.y() - 5, f"坐标: {coord_text}")
        painter.end()


class ROIOverlayWindow(QWidget):
    def __init__(self, core_instance=None, parent=None):
        super().__init__(parent)
        icon_path = os.path.join(BASE_DIR, "Image", "logo", "titlelogo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.core_instance = core_instance
        self.hwnd = None
        self.worker = None
        self.picker = None
        self.rois = {
            'D': (415, 813, 461, 853),
            'F': (752, 813, 805, 853),
            'J': (1117, 813, 1164, 853),
            'K': (1452, 813, 1504, 853),
        }
        self.key_colors = {k: "#1f1f20" for k in self.rois}
        self.current_pixels = {k: 0 for k in self.rois}
        self.trigger_counts = {k: 0 for k in self.rois}
        self.last_trigger_time = {k: 0 for k in self.rois}
        self.setup_ui()
        self.auto_bind()
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.update_display)
        self.refresh_timer.start(50)

    def setup_ui(self):
        self.setWindowTitle("超强音 - ROI 调试窗口 (像素检测+红色闪动)")
        self.resize(1200, 800)
        main_layout = QHBoxLayout(self)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(640, 480)
        left_layout.addWidget(self.image_label)
        main_layout.addWidget(left_widget, stretch=3)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setAlignment(Qt.AlignTop)
        self.status_label = QLabel("等待绑定窗口...")
        right_layout.addWidget(self.status_label)
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("保存配置")
        self.btn_load = QPushButton("加载配置")
        self.btn_save.clicked.connect(self.save_config)
        self.btn_load.clicked.connect(self.load_config)
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_load)
        right_layout.addLayout(btn_layout)
        self.key_widgets = {}
        for key in ['D', 'F', 'J', 'K']:
            group = QGroupBox(f"按键 {key}")
            group_layout = QVBoxLayout(group)
            region_layout = QHBoxLayout()
            region_layout.addWidget(QLabel("区域:"))
            region_edit = QLineEdit(self.region_to_str(self.rois[key]))
            region_btn = QPushButton("应用")
            region_btn.clicked.connect(lambda _, k=key: self.apply_region(k))
            region_layout.addWidget(region_edit)
            region_layout.addWidget(region_btn)
            color_layout = QHBoxLayout()
            color_layout.addWidget(QLabel("颜色:"))
            color_edit = QLineEdit(self.key_colors[key])
            pick_btn = QPushButton("拾取")
            pick_btn.clicked.connect(lambda _, k=key: self.start_pick(k))
            copy_btn = QPushButton("复制")
            copy_btn.clicked.connect(lambda _, k=key: self.copy_color(k))
            color_layout.addWidget(color_edit)
            color_layout.addWidget(pick_btn)
            color_layout.addWidget(copy_btn)
            group_layout.addLayout(region_layout)
            group_layout.addLayout(color_layout)
            right_layout.addWidget(group)
            self.key_widgets[key] = {
                'region_edit': region_edit,
                'color_edit': color_edit,
                'region_btn': region_btn,
                'pick_btn': pick_btn,
                'copy_btn': copy_btn,
            }
        info_group = QGroupBox("实时检测数据")
        info_layout = QGridLayout(info_group)
        info_layout.addWidget(QLabel("按键"), 0, 0)
        info_layout.addWidget(QLabel("当前像素"), 0, 1)
        info_layout.addWidget(QLabel("触发次数"), 0, 2)
        self.pixel_labels = {}
        self.count_labels = {}
        for i, key in enumerate(['D', 'F', 'J', 'K']):
            self.pixel_labels[key] = QLabel("0")
            self.count_labels[key] = QLabel("0")
            info_layout.addWidget(QLabel(key), i+1, 0)
            info_layout.addWidget(self.pixel_labels[key], i+1, 1)
            info_layout.addWidget(self.count_labels[key], i+1, 2)
        right_layout.addWidget(info_group)
        total_group = QGroupBox("汇总")
        total_layout = QVBoxLayout(total_group)
        self.total_count_label = QLabel("总触发: 0")
        total_layout.addWidget(self.total_count_label)
        right_layout.addWidget(total_group)
        main_layout.addWidget(right_widget, stretch=1)
        self.setLayout(main_layout)
        self.setStyleSheet("""
            QGroupBox { color: #0ff; border: 1px solid #0ff; border-radius: 5px; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QLineEdit { background-color: #2a2a3a; color: #0ff; border: 1px solid #0ff; border-radius: 3px; padding: 2px; }
            QPushButton { background-color: #2a2a3a; color: #0ff; border: 1px solid #0ff; border-radius: 5px; padding: 4px 8px; }
            QPushButton:hover { background-color: #0ff; color: #1e1e2f; }
        """)

    def region_to_str(self, region):
        return f"{region[0]},{region[1]},{region[2]},{region[3]}"

    def apply_region(self, key):
        try:
            text = self.key_widgets[key]['region_edit'].text().strip()
            coords = tuple(map(int, text.split(',')))
            if len(coords) != 4 or coords[0] >= coords[2] or coords[1] >= coords[3]:
                raise ValueError
            self.rois[key] = coords
            if self.worker:
                self.worker.update_roi(key, coords)
            self.status_label.setText(f"{key} 区域已更新")
        except:
            QMessageBox.warning(self, "错误", "区域格式错误")
            self.key_widgets[key]['region_edit'].setText(self.region_to_str(self.rois[key]))

    def start_pick(self, key):
        if not self.hwnd or not win32gui.IsWindow(self.hwnd):
            QMessageBox.warning(self, "错误", "未绑定游戏窗口")
            return
        self.setEnabled(False)
        self.picker = FullscreenColorPicker(
            self.hwnd,
            lambda c, x, y: self.on_pick_done(key, c, x, y),
            lambda: self.on_pick_cancelled()
        )

    def on_pick_done(self, key, hex_color, client_x, client_y):
        self.key_widgets[key]['color_edit'].setText(hex_color)
        self.key_colors[key] = hex_color
        if self.worker:
            self.worker.update_color(key, hex_color)
        self.status_label.setText(f"按键 {key} 颜色已拾取: {hex_color} 坐标({client_x},{client_y})")
        self.setEnabled(True)
        self.picker = None

    def on_pick_cancelled(self):
        self.status_label.setText("颜色拾取已取消")
        self.setEnabled(True)
        self.picker = None

    def copy_color(self, key):
        color = self.key_widgets[key]['color_edit'].text().strip()
        if color:
            QApplication.clipboard().setText(color)
            self.status_label.setText(f"已复制 {key} 颜色: {color}")

    def save_config(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存配置", "", "JSON Files (*.json)")
        if path:
            import json
            data = {'rois': self.rois, 'key_colors': self.key_colors}
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            self.status_label.setText(f"配置已保存到 {path}")

    def load_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "加载配置", "", "JSON Files (*.json)")
        if path:
            import json
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.rois = data.get('rois', self.rois)
            self.key_colors = data.get('key_colors', self.key_colors)
            for key in self.rois:
                self.key_widgets[key]['region_edit'].setText(self.region_to_str(self.rois[key]))
                self.key_widgets[key]['color_edit'].setText(self.key_colors[key])
            self.status_label.setText("配置已加载")

    def auto_bind(self):
        hwnd = None
        if self.core_instance and hasattr(self.core_instance, 'hwnd') and self.core_instance.hwnd:
            hwnd = self.core_instance.hwnd
        else:
            hwnd = get_game_hwnd()
        if not hwnd or not win32gui.IsWindow(hwnd):
            text, ok = QInputDialog.getText(self, "窗口句柄", "请输入窗口句柄(十进制):")
            if ok and text:
                try:
                    hwnd = int(text)
                    set_locked_hwnd(hwnd)
                except ValueError:
                    QMessageBox.warning(self, "错误", "句柄无效")
                    return
            else:
                self.status_label.setText("未绑定窗口")
                return
        if not win32gui.IsWindow(hwnd):
            QMessageBox.warning(self, "错误", f"句柄 {hwnd} 无效")
            return
        self.bind_hwnd(hwnd)

    def bind_hwnd(self, hwnd):
        self.hwnd = hwnd
        stop_screenshot_updater()
        start_screenshot_updater(hwnd, interval=0.005)
        self.worker = DetectionWorker(hwnd, self.rois, self.key_colors)
        self.worker.data_updated.connect(self.on_data_updated)
        self.worker.start()
        title = win32gui.GetWindowText(hwnd)
        self.setWindowTitle(f"超强音 - ROI 调试窗口 (已绑定 {title})")
        self.status_label.setText(f"已绑定: {title}")

    def on_data_updated(self, data):
        for key, (pixel, triggered) in data.items():
            self.current_pixels[key] = pixel
            if triggered:
                self.trigger_counts[key] += 1
                self.last_trigger_time[key] = time.time()
                self.count_labels[key].setText(str(self.trigger_counts[key]))
                total = sum(self.trigger_counts.values())
                self.total_count_label.setText(f"总触发: {total}")
            self.pixel_labels[key].setText(str(pixel))

    def update_display(self):
        img = get_cached_screenshot()
        if img is None:
            self.image_label.setText("等待截图...")
            return
        overlay = img.copy()
        now = time.time()
        for key, (x1, y1, x2, y2) in self.rois.items():
            if now - self.last_trigger_time.get(key, 0) < 0.2:
                color = (0, 0, 255)
            else:
                color = (0, 255, 0)
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
        rgb = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qt_img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_img)
        scaled = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled)

    def closeEvent(self, event):
        if self.worker:
            self.worker.stop()
        if self.picker:
            self.picker.close_picker(cancelled=True)
        stop_screenshot_updater()
        event.accept()


def show_roi_window(core_instance=None):
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    win = ROIOverlayWindow(core_instance)
    win.setAttribute(Qt.WA_DeleteOnClose, False)
    win.show()
    return win


if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = ROIOverlayWindow()
    win.show()
    sys.exit(app.exec_())