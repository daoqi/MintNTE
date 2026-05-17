import sys
import os
import win32gui
import pygame
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QCheckBox, QLabel, QLineEdit, QPushButton,
    QGridLayout, QMessageBox, QShortcut, QInputDialog, QApplication
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.Fortissimo.fortissimo_core import FortissimoCore
from Module.Hwnd.game_hwnd import get_game_hwnd, set_locked_hwnd
from core.Fortissimo.Fortissimo_ROI_UI import show_roi_window

pygame.mixer.init()
SOUND_START = os.path.join(BASE_DIR, "Image", "logo", "start.mp3")
SOUND_END = os.path.join(BASE_DIR, "Image", "logo", "end.mp3")


class FortissimoUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.core = FortissimoCore()
        self._roi_win = None
        self.setup_ui()
        self.setup_hotkey()
        self.update_ui_state(False)
        self.update_hwnd_status()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        title = QLabel("超强音-后台演奏")
        title.setStyleSheet("color: #f0f; font-size: 22px; font-weight: bold;")
        main_layout.addWidget(title, alignment=Qt.AlignCenter)
        tip_label = QLabel("提示：一定要在「帮助」中的图片把游戏设置好，不然无法识别！")
        tip_label.setStyleSheet("color: #ffaa00; font-size: 12px;")
        tip_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(tip_label)

        status_layout = QHBoxLayout()
        self.hwnd_status_label = QLabel("窗口状态: 未绑定")
        self.hwnd_status_label.setStyleSheet("color: #ffaa00;")
        status_layout.addWidget(self.hwnd_status_label)
        self.btn_refresh_status = QPushButton("刷新绑定状态")
        self.btn_refresh_status.setObjectName("NeonButton")
        self.btn_refresh_status.clicked.connect(self.update_hwnd_status)
        status_layout.addWidget(self.btn_refresh_status)
        main_layout.addLayout(status_layout)

        group = QGroupBox("按键配置")
        group.setStyleSheet("color: #0ff; font-size: 14px;")
        grid = QGridLayout(group)
        grid.setSpacing(8)

        default_keys = [
            ("D", "415,813,461,853", 0.005, "D", "#1f1f20"),
            ("F", "752,813,805,853", 0.005, "F", "#1f1f20"),
            ("J", "1117,813,1164,853", 0.005, "J", "#1f1f20"),
            ("K", "1452,813,1504,853", 0.005, "K", "#1f1f20"),
        ]
        custom_keys = [(f"自定义{i}", "0,0,100,100", 0.005, "", "#000000") for i in range(1, 3)]
        all_keys = default_keys + custom_keys
        row = 0
        grid.addWidget(QLabel("启用"), row, 0)
        grid.addWidget(QLabel("区域(x1,y1,x2,y2)"), row, 1)
        grid.addWidget(QLabel("速度(s)"), row, 2)
        grid.addWidget(QLabel("按键"), row, 3)
        grid.addWidget(QLabel("颜色(#RRGGBB)"), row, 4)
        grid.addWidget(QLabel("恢复默认"), row, 5)
        row += 1

        self.key_configs = []
        for name, region_str, speed_val, default_key, default_color in all_keys:
            cb = QCheckBox(name)
            cb.setChecked(name in ["D", "F", "J", "K"])
            cb.setStyleSheet("color: #0ff; font-size: 12px;")

            line_region = QLineEdit(region_str)
            line_region.setPlaceholderText("x1,y1,x2,y2")
            line_region.setFixedWidth(150)

            line_speed = QLineEdit(str(speed_val))
            line_speed.setFixedWidth(60)

            line_keychar = QLineEdit(default_key)
            line_keychar.setPlaceholderText("字母")
            line_keychar.setFixedWidth(40)
            if not name.startswith("自定义"):
                line_keychar.setReadOnly(True)

            line_color = QLineEdit(default_color)
            line_color.setPlaceholderText("#RRGGBB")
            line_color.setFixedWidth(80)

            btn_restore = QPushButton("恢复")
            btn_restore.setFixedWidth(60)
            btn_restore.clicked.connect(lambda checked, r=line_region, c=line_color, dr=region_str, dc=default_color: self.restore_row(r, c, dr, dc))

            grid.addWidget(cb, row, 0)
            grid.addWidget(line_region, row, 1)
            grid.addWidget(line_speed, row, 2)
            grid.addWidget(line_keychar, row, 3)
            grid.addWidget(line_color, row, 4)
            grid.addWidget(btn_restore, row, 5)

            self.key_configs.append({
                "name": name,
                "cb": cb,
                "region_edit": line_region,
                "speed_edit": line_speed,
                "keychar_edit": line_keychar,
                "color_edit": line_color,
                "is_custom": name.startswith("自定义"),
                "default_region": region_str,
                "default_color": default_color,
                "default_speed": speed_val,
                "default_keychar": default_key,
            })
            row += 1
        main_layout.addWidget(group)

        btn_layout = QHBoxLayout()
        self.btn_start_stop = QPushButton("开始 (Alt+F1)")
        self.btn_start_stop.setObjectName("NeonButton")
        self.btn_start_stop.clicked.connect(self.toggle_run)
        btn_layout.addWidget(self.btn_start_stop)

        self.btn_roi = QPushButton("ROI调试窗口")
        self.btn_roi.setObjectName("NeonButton")
        self.btn_roi.clicked.connect(self.open_roi_window)
        btn_layout.addWidget(self.btn_roi)

        self.btn_restore_all = QPushButton("恢复所有默认")
        self.btn_restore_all.setObjectName("NeonButton")
        self.btn_restore_all.clicked.connect(self.restore_all_defaults)
        btn_layout.addWidget(self.btn_restore_all)
        main_layout.addLayout(btn_layout)

        log_layout = QHBoxLayout()
        self.cb_save_screenshot = QCheckBox("保存按键截图")
        self.cb_save_screenshot.setChecked(False)
        self.cb_save_screenshot.stateChanged.connect(self.on_save_screenshot_changed)
        self.cb_save_pixel_log = QCheckBox("保存像素日志(TXT)")
        self.cb_save_pixel_log.setChecked(True)
        self.cb_save_pixel_log.stateChanged.connect(self.on_save_pixel_log_changed)
        log_layout.addWidget(self.cb_save_screenshot)
        log_layout.addWidget(self.cb_save_pixel_log)
        main_layout.addLayout(log_layout)

        param_layout = QHBoxLayout()
        lbl_speed = QLabel("轮询间隔(s):")
        lbl_speed.setStyleSheet("color: #03bccd;")
        param_layout.addWidget(lbl_speed)
        self.spin_speed = QLineEdit("0.005")
        self.spin_speed.setFixedWidth(70)
        param_layout.addWidget(self.spin_speed)
        lbl_speed_hint = QLabel("(调低提高灵敏度)")
        lbl_speed_hint.setStyleSheet("color: #03bccd;")
        param_layout.addWidget(lbl_speed_hint)

        lbl_tolerance = QLabel("  颜色容差:")
        lbl_tolerance.setStyleSheet("color: #03bccd;")
        param_layout.addWidget(lbl_tolerance)
        self.spin_tolerance = QLineEdit("7")
        self.spin_tolerance.setFixedWidth(50)
        param_layout.addWidget(self.spin_tolerance)
        lbl_tolerance_hint = QLabel("(调低更严格)")
        lbl_tolerance_hint.setStyleSheet("color: #03bccd;")
        param_layout.addWidget(lbl_tolerance_hint)

        lbl_min_pixels = QLabel("  最小像素:")
        lbl_min_pixels.setStyleSheet("color: #03bccd;")
        param_layout.addWidget(lbl_min_pixels)
        self.spin_min_pixels = QLineEdit("15")
        self.spin_min_pixels.setFixedWidth(50)
        param_layout.addWidget(self.spin_min_pixels)
        lbl_min_hint = QLabel("(调高减少误触)")
        lbl_min_hint.setStyleSheet("color: #03bccd;")
        param_layout.addWidget(lbl_min_hint)

        main_layout.addLayout(param_layout)

        self.status_label = QLabel("▶就绪,可可！随时准备演奏")
        self.status_label.setStyleSheet("color: #0ff;")
        main_layout.addWidget(self.status_label)

        self.setStyleSheet("""
            QGroupBox { color: #0ff; border: 1px solid #0ff; border-radius: 5px; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QLineEdit { background-color: #2a2a3a; color: #0ff; border: 1px solid #0ff; border-radius: 3px; padding: 2px; }
            QPushButton { background-color: #2a2a3a; color: #0ff; border: 1px solid #0ff; border-radius: 5px; padding: 6px 12px; }
            QPushButton:hover { background-color: #0ff; color: #1e1e2f; }
        """)

    def setup_hotkey(self):
        self.shortcut = QShortcut(QKeySequence("Alt+F1"), self)
        self.shortcut.activated.connect(self.toggle_run)

    def play_sound(self, path):
        if os.path.exists(path):
            try:
                pygame.mixer.music.load(path)
                pygame.mixer.music.play()
            except:
                pass

    def restore_row(self, region_edit, color_edit, default_region, default_color):
        region_edit.setText(default_region)
        color_edit.setText(default_color)

    def restore_all_defaults(self):
        for cfg in self.key_configs:
            cfg["region_edit"].setText(cfg["default_region"])
            cfg["color_edit"].setText(cfg["default_color"])
            cfg["speed_edit"].setText(str(cfg["default_speed"]))
            cfg["keychar_edit"].setText(cfg["default_keychar"])
            cfg["cb"].setChecked(cfg["name"] in ["D", "F", "J", "K"])
        self.status_label.setText("已恢复所有默认")

    def update_hwnd_status(self):
        hwnd = get_game_hwnd()
        if hwnd and win32gui.IsWindow(hwnd):
            title = win32gui.GetWindowText(hwnd)
            self.hwnd_status_label.setText(f"窗口状态: 已绑定 (句柄: {hwnd}, 标题: {title})")
            self.hwnd_status_label.setStyleSheet("color: #00ff00;")
            return hwnd
        else:
            self.hwnd_status_label.setText("窗口状态: 未绑定 (请到「窗口检测」锁定或手动输入)")
            self.hwnd_status_label.setStyleSheet("color: #ffaa00;")
            return None

    def on_save_screenshot_changed(self, state):
        self.core.set_save_screenshot_enabled(state == Qt.Checked)

    def on_save_pixel_log_changed(self, state):
        self.core.set_save_pixel_log_enabled(state == Qt.Checked)

    def toggle_run(self):
        if self.core.running:
            self.stop()
        else:
            self.start()

    def start(self):
        hwnd = get_game_hwnd()
        if not hwnd or not win32gui.IsWindow(hwnd):
            text, ok = QInputDialog.getText(self, "窗口句柄", "未自动检测到窗口，请输入窗口句柄(十进制):")
            if ok and text:
                try:
                    hwnd = int(text)
                    set_locked_hwnd(hwnd)
                except ValueError:
                    QMessageBox.warning(self, "错误", "句柄无效")
                    return
            else:
                QMessageBox.warning(self, "错误", "未提供窗口句柄")
                return
        if not win32gui.IsWindow(hwnd):
            QMessageBox.warning(self, "错误", f"窗口句柄 {hwnd} 无效")
            return
        self.core.set_hwnd(hwnd)
        self.update_hwnd_status()

        try:
            global_speed = float(self.spin_speed.text())
            if global_speed <= 0: raise ValueError
        except:
            QMessageBox.warning(self, "错误", "轮询间隔必须为正数")
            return
        try:
            global_tolerance = int(self.spin_tolerance.text())
            if global_tolerance < 0: raise ValueError
        except:
            QMessageBox.warning(self, "错误", "颜色容差必须为非负整数")
            return
        try:
            global_min_pixels = int(self.spin_min_pixels.text())
            if global_min_pixels < 1: raise ValueError
        except:
            QMessageBox.warning(self, "错误", "最小像素必须为正整数")
            return

        configs = []
        for cfg in self.key_configs:
            if not cfg["cb"].isChecked():
                continue
            try:
                region = tuple(map(int, cfg["region_edit"].text().split(',')))
                if len(region) != 4:
                    raise ValueError
            except:
                QMessageBox.warning(self, "配置错误", f"按键 {cfg['name']} 区域格式错误")
                return
            key_char = cfg["keychar_edit"].text().strip().upper()
            if len(key_char) != 1 or not key_char.isalpha():
                QMessageBox.warning(self, "配置错误", f"按键 {cfg['name']} 必须输入字母")
                return
            configs.append({
                "region": region,
                "key_char": key_char,
                "speed": global_speed,
            })

        if not configs:
            QMessageBox.information(self, "提示", "没有启用任何按键")
            return

        self.play_sound(SOUND_START)
        if self.core.start(configs, stop_image_path="stop.png", finished_callback=self.on_play_finished,
                           global_speed=global_speed,
                           global_color_tolerance=global_tolerance,
                           global_min_pixels=global_min_pixels):
            self.update_ui_state(True)
        else:
            QMessageBox.warning(self, "错误", "启动失败，查看日志")

    def on_play_finished(self):
        QTimer.singleShot(0, self.stop)

    def stop(self):
        self.core.stop()
        self.update_ui_state(False)
        self.play_sound(SOUND_END)

    def update_ui_state(self, is_running):
        self.btn_start_stop.setText("停止 (Alt+F1)" if is_running else "开始 (Alt+F1)")
        self.status_label.setText("⏸️演奏中..." if is_running else "▶就绪,可可！随时准备演奏")
        for cfg in self.key_configs:
            cfg["cb"].setEnabled(not is_running)
            cfg["region_edit"].setEnabled(not is_running)
            cfg["speed_edit"].setEnabled(not is_running)
            cfg["keychar_edit"].setEnabled(not is_running)
            cfg["color_edit"].setEnabled(not is_running)
        self.btn_restore_all.setEnabled(not is_running)
        self.btn_refresh_status.setEnabled(not is_running)

    def open_roi_window(self):
        if self._roi_win is not None:
            try:
                if self._roi_win.isVisible():
                    self._roi_win.raise_()
                    self._roi_win.activateWindow()
                    return
                else:
                    self._roi_win = None
            except RuntimeError:
                self._roi_win = None
        try:
            self._roi_win = show_roi_window(self.core)
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "错误", f"打开ROI窗口失败: {e}")

    def closeEvent(self, event):
        self.core.stop()
        if self._roi_win:
            try:
                self._roi_win.close()
            except:
                pass
        try:
            pygame.mixer.music.stop()
            pygame.mixer.quit()
        except:
            pass
        event.accept()