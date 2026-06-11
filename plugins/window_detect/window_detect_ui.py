# plugins/window_detect/window_detect_ui.py
import sys, os, webbrowser
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QGroupBox, QLineEdit,
    QVBoxLayout, QHBoxLayout, QFormLayout, QFrame, QPushButton,
    QRadioButton, QButtonGroup, QComboBox, QMessageBox, QScrollArea
)
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QPixmap, QImage, QCursor
import win32gui, win32con, win32process, win32ui
from ctypes import windll
from PIL import Image

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ui.services.logui import info as log_info, warning as log_warning, error as log_error
from Module.Hwnd.game_hwnd import set_locked_hwnd, clear_locked_hwnd, get_game_hwnd
from ui.services.capture_config import (
    get_capture_mode, set_capture_mode,
    get_detect_mode, set_detect_mode
)

IMAGE_DIR = os.path.join(BASE_DIR, "Image", "logo")
BG_PATH = os.path.join(IMAGE_DIR, "Window_Picker.png")
SPY_PATH = os.path.join(IMAGE_DIR, "Window_Spy.png")

EXCLUDED_CLASSES = [
    "TXGuiFoundation",
    "Chrome_WidgetWin_1",
    "MozillaWindowClass",
    "IEFrame",
    "ApplicationFrameWindow",
]

class WindowDetectUI(QWidget):   # ← 关键修复：确保类名是 WindowDetectUI
    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_hwnd = None
        self.locked_hwnd = None

        self.spy_cursor = None
        if os.path.exists(SPY_PATH):
            self.spy_cursor = QCursor(
                QPixmap(SPY_PATH).scaled(17, 17, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

        self.tracker = None
        self.drag_active = False

        self.init_ui()

    # ========== UI 构建 ==========
    def init_ui(self):
        # 外层滚动区域
        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        main_widget = QWidget()
        main_scroll.setWidget(main_widget)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(main_scroll)

        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # ---- 获取方式选择 ----
        mode_group = QGroupBox("窗口句柄获取方式")
        mode_layout = QVBoxLayout(mode_group)

        self.mode_btn_group = QButtonGroup(self)
        self.radio_auto = QRadioButton("自动获取")
        self.radio_picker = QRadioButton("标靶拾取")
        self.radio_combo = QRadioButton("下拉选择")
        self.mode_btn_group.addButton(self.radio_auto, 0)
        self.mode_btn_group.addButton(self.radio_picker, 1)
        self.mode_btn_group.addButton(self.radio_combo, 2)

        saved_mode = get_detect_mode()
        if saved_mode == 2:
            self.radio_combo.setChecked(True)
        elif saved_mode == 1:
            self.radio_picker.setChecked(True)
        else:
            self.radio_auto.setChecked(True)

        mode_layout.addWidget(self.radio_auto)
        mode_layout.addWidget(self.radio_picker)
        mode_layout.addWidget(self.radio_combo)

        # 自动获取按钮（缩小版本）
        self.auto_btn = QPushButton(" 重新获取")
        self.auto_btn.setMaximumWidth(80)
        self.auto_btn.setFixedHeight(20)
        self.auto_btn.setStyleSheet("padding: 0px 10px;")
        self.auto_btn.clicked.connect(self.auto_detect)
        mode_layout.addWidget(self.auto_btn)

        # 标靶区域（默认隐藏）
        self.picker_area = QWidget()
        picker_layout = QVBoxLayout(self.picker_area)
        picker_layout.setContentsMargins(0, 0, 0, 0)

        self.icon_frame = QFrame()
        self.icon_frame.setFixedSize(200, 120)
        self.icon_frame.setStyleSheet("background: transparent;")

        self.bg_label = QLabel(self.icon_frame)
        if os.path.exists(BG_PATH):
            self.bg_label.setPixmap(QPixmap(BG_PATH).scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.bg_label.setStyleSheet("background: white; border: 1px solid gray;")
        self.bg_label.setGeometry(84, 44, 32, 32)
        self.bg_label.setStyleSheet("background: white;")

        self.spy_static = QLabel(self.icon_frame)
        if os.path.exists(SPY_PATH):
            self.spy_static.setPixmap(QPixmap(SPY_PATH).scaled(17, 17, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.spy_static.setText("+")
            self.spy_static.setStyleSheet("color: red; font-weight: bold;")
        self.spy_static.setGeometry(91, 51, 17, 17)
        self.spy_static.setCursor(Qt.CrossCursor)
        self.spy_static.mousePressEvent = self.on_spy_press
        self.spy_static.setMouseTracking(True)

        picker_layout.addWidget(self.icon_frame, alignment=Qt.AlignCenter)

        hint = QLabel("按住靶心拖到游戏窗口后松开")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: #00ffcc; font-size: 11pt;")
        picker_layout.addWidget(hint)

        self.picker_area.setVisible(False)
        mode_layout.addWidget(self.picker_area)

        # 下拉框选择区域
        combo_widget = QWidget()
        combo_layout = QHBoxLayout(combo_widget)
        combo_layout.setContentsMargins(0, 0, 0, 0)
        self.combo_window = QComboBox()
        self.combo_window.setMinimumWidth(300)
        self.refresh_combo_btn = QPushButton("刷新窗口")
        self.refresh_combo_btn.clicked.connect(self.refresh_combo)
        self.combo_lock_btn = QPushButton("锁定窗口")
        self.combo_lock_btn.clicked.connect(self.combo_lock)
        combo_layout.addWidget(QLabel("选择窗口:"))
        combo_layout.addWidget(self.combo_window)
        combo_layout.addWidget(self.refresh_combo_btn)
        combo_layout.addWidget(self.combo_lock_btn)
        combo_widget.setVisible(False)
        mode_layout.addWidget(combo_widget)
        self.combo_widget = combo_widget

        main_layout.addWidget(mode_group)

        # ---- 锁定状态与截图方式 ----
        lock_cap_layout = QHBoxLayout()

        self.lock_status_label = QLabel("未锁定")
        self.lock_status_label.setStyleSheet("color: #ff8800; font-weight: bold;")
        lock_cap_layout.addWidget(self.lock_status_label)

        self.btn_lock = QPushButton("锁定窗口")
        self.btn_lock.clicked.connect(self.toggle_lock)
        lock_cap_layout.addWidget(self.btn_lock)

        lock_cap_layout.addSpacing(20)
        lock_cap_layout.addWidget(QLabel("截图方式:"))
        self.capture_combo = QComboBox()
        self.capture_combo.addItems(["PrintWindow", "dxcam", "WGC"])
        current_cap = get_capture_mode()
        if current_cap == 1:
            self.capture_combo.setCurrentText("dxcam")
        elif current_cap == 2:
            self.capture_combo.setCurrentText("WGC")
        else:
            self.capture_combo.setCurrentText("PrintWindow")
        self.capture_combo.currentIndexChanged.connect(self.on_capture_changed)
        lock_cap_layout.addWidget(self.capture_combo)

        # 问号帮助按钮
        help_btn = QPushButton("?")
        help_btn.setFixedSize(24, 24)
        help_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a4a;
                color: #0ff;
                border: 1px solid #0ff;
                border-radius: 12px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #0ff;
                color: #1e1e2f;
            }
        """)
        help_btn.setToolTip("点击?跳转网页查看教程")
        help_btn.clicked.connect(self.show_capture_help)
        lock_cap_layout.addWidget(help_btn)

        lock_cap_layout.addStretch()
        main_layout.addLayout(lock_cap_layout)

        # ---- 窗口信息 + 预览 横向布局 ----
        bottom_layout = QHBoxLayout()

        # 左侧：窗口信息（只保留三行）
        info_group = QGroupBox(" 窗口信息 ")
        info_form = QFormLayout()
        self.fields = {}
        self.fields["handle"] = QLineEdit()
        self.fields["title"] = QLineEdit()
        self.fields["class_name"] = QLineEdit()
        for ledit in [self.fields["handle"], self.fields["title"], self.fields["class_name"]]:
            ledit.setReadOnly(True)
            ledit.setStyleSheet("background: #0a0a1a; color: #00ffcc; border: 1px solid #00ccff; padding: 2px;")
        info_form.addRow("句柄:", self.fields["handle"])
        info_form.addRow("标题:", self.fields["title"])
        info_form.addRow("类名:", self.fields["class_name"])
        info_group.setLayout(info_form)
        bottom_layout.addWidget(info_group)

        # 右侧：预览框
        preview_group = QGroupBox("异环窗口画面 (静止画面)")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_label = QLabel()
        self.preview_label.setFixedSize(320, 180)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #000; border: 1px solid #0ff;")
        preview_layout.addWidget(self.preview_label, alignment=Qt.AlignCenter)

        self.btn_capture = QPushButton("截取最新画面")
        self.btn_capture.clicked.connect(self.capture_single_frame)
        preview_layout.addWidget(self.btn_capture, alignment=Qt.AlignCenter)
        bottom_layout.addWidget(preview_group)

        main_layout.addLayout(bottom_layout)

        # 信号
        self.mode_btn_group.buttonToggled.connect(self.on_mode_changed)
        self.on_mode_changed(self.mode_btn_group.checkedButton(), True)

        # 样式
        self.setStyleSheet("""
            QWidget { background: transparent; font-family: "Microsoft YaHei", "Segoe UI"; }
            QGroupBox { color: #00ddff; font-weight: bold; border: 1px solid #00aaff; border-radius: 6px; margin-top: 10px; padding-top: 10px; background: rgba(0,0,30,255); }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 8px; color: #00ffff; }
            QLabel { color: #ccddff; background: transparent; }
            QLineEdit { background: #0a0a1a; color: #00ffcc; border: 1px solid #00ccff; border-radius: 3px; padding: 2px 4px; }
            QPushButton { background-color: #2a2a3a; color: #0ff; border: 1px solid #0ff; padding: 6px 15px; border-radius: 4px; }
            QPushButton:hover { background-color: #0ff; color: #1e1e2f; }
            QRadioButton { color: #ccddff; }
            QComboBox { background-color: #2a2a3a; color: #0ff; border: 1px solid #0ff; padding: 3px; }
        """)

    # ========== 功能方法 ==========
    def on_capture_changed(self, idx):
        set_capture_mode({0: 0, 1: 1, 2: 2}[idx])

    def on_mode_changed(self, btn, checked):
        if not checked:
            return
        mode = self.mode_btn_group.id(btn)
        self.picker_area.setVisible(mode == 1)
        self.combo_widget.setVisible(mode == 2)
        self.auto_btn.setVisible(mode == 0)
        set_detect_mode(mode)

        if mode == 0:
            if self.locked_hwnd is None:
                self.auto_detect()
        else:
            self.btn_lock.setText("锁定窗口")
            self.lock_status_label.setText("未锁定")
            self.lock_status_label.setStyleSheet("color: #ff8800; font-weight: bold;")

    def auto_detect(self):
        hwnd = self._find_heter_ring_window()
        if hwnd:
            self.lock_hwnd(hwnd)
        else:
            QMessageBox.warning(self, "未找到", "请先启动异环游戏后再重新获取，或更换获取方式。")
            self.preview_label.setText("未找到游戏窗口")

    def _find_heter_ring_window(self):
        result = None
        def callback(hwnd, _):
            nonlocal result
            if not win32gui.IsWindowVisible(hwnd): return True
            title = win32gui.GetWindowText(hwnd)
            cls = win32gui.GetClassName(hwnd)
            if cls in EXCLUDED_CLASSES: return True
            browsers = ["Chrome", "Edge", "Firefox", "Internet Explorer", "Opera"]
            if any(b in title for b in browsers): return True
            if "QQ" in title or "TXGuiFoundation" in cls: return True
            if "异环" in title and cls == "UnrealWindow":
                result = hwnd; return False
            return True
        win32gui.EnumWindows(callback, None)
        return result

    def refresh_combo(self):
        self.combo_window.clear()
        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title.strip():
                    self.combo_window.addItem(f"{title} (0x{hwnd:X})", hwnd)
            return True
        win32gui.EnumWindows(callback, None)

    def combo_lock(self):
        idx = self.combo_window.currentIndex()
        if idx >= 0:
            hwnd = self.combo_window.itemData(idx)
            if hwnd and win32gui.IsWindow(hwnd):
                self.lock_hwnd(hwnd)

    def on_spy_press(self, event):
        if event.button() != Qt.LeftButton: return
        self.tracker = QWidget()
        self.tracker.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.tracker.setAttribute(Qt.WA_TranslucentBackground)
        self.tracker.setFixedSize(17, 17)
        label = QLabel(self.tracker)
        if os.path.exists(SPY_PATH):
            label.setPixmap(QPixmap(SPY_PATH).scaled(17, 17, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            label.setText("+")
            label.setStyleSheet("color: red; font-weight: bold; background: transparent;")
        label.setGeometry(0, 0, 17, 17)
        global_pos = QCursor.pos()
        self.tracker.move(global_pos.x() - 8, global_pos.y() - 8)
        self.tracker.show()
        if self.spy_cursor: QApplication.setOverrideCursor(self.spy_cursor)
        self.drag_active = True
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        if self.drag_active:
            if event.type() == QEvent.MouseMove:
                global_pos = QCursor.pos()
                if self.tracker: self.tracker.move(global_pos.x() - 8, global_pos.y() - 8)
                return True
            elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self.drag_active = False
                QApplication.instance().removeEventFilter(self)
                if self.tracker: self.tracker.close(); self.tracker = None
                while QApplication.overrideCursor() is not None: QApplication.restoreOverrideCursor()
                pt = win32gui.GetCursorPos()
                hwnd = win32gui.WindowFromPoint(pt)
                if hwnd == int(self.winId()): hwnd = None
                self.target_hwnd = hwnd
                self.update_info()
                if self.target_hwnd and win32gui.IsWindow(self.target_hwnd):
                    self.capture_single_frame()
                    log_info(f"拾取窗口: {win32gui.GetWindowText(self.target_hwnd)}")
                else:
                    self.preview_label.clear()
                return True
        return super().eventFilter(obj, event)

    def toggle_lock(self):
        if self.locked_hwnd is None:
            if not self.target_hwnd or not win32gui.IsWindow(self.target_hwnd):
                log_warning("没有可锁定的窗口，请先拾取一个窗口")
                return
            self.locked_hwnd = self.target_hwnd
            set_locked_hwnd(self.target_hwnd)
            title = win32gui.GetWindowText(self.target_hwnd)
            log_info(f"锁定窗口: {title} (句柄: {self.target_hwnd})")
            self.lock_status_label.setText(f"已锁定: {title[:20]}")
            self.lock_status_label.setStyleSheet("color: #00ff00; font-weight: bold;")
            self.btn_lock.setText("解除锁定")
        else:
            clear_locked_hwnd()
            log_info("已解除窗口锁定")
            self.locked_hwnd = None
            self.lock_status_label.setText("未锁定")
            self.lock_status_label.setStyleSheet("color: #ff8800; font-weight: bold;")
            self.btn_lock.setText("锁定窗口")

    def lock_hwnd(self, hwnd):
        self.target_hwnd = hwnd
        self.locked_hwnd = hwnd
        set_locked_hwnd(hwnd)
        title = win32gui.GetWindowText(hwnd)
        log_info(f"锁定窗口: {title} (句柄: {hwnd})")
        self.lock_status_label.setText(f"已锁定: {title[:20]}")
        self.lock_status_label.setStyleSheet("color: #00ff00; font-weight: bold;")
        self.btn_lock.setText("解除锁定")
        self.update_info()
        self.capture_single_frame()

    def update_info(self):
        hwnd = self.target_hwnd
        if not hwnd or not win32gui.IsWindow(hwnd): return
        try:
            self.fields["handle"].setText(f"0x{hwnd:08X}")
            self.fields["title"].setText(win32gui.GetWindowText(hwnd))
            self.fields["class_name"].setText(win32gui.GetClassName(hwnd))
        except Exception as e:
            log_error(f"更新窗口信息失败: {e}")

    def capture_single_frame(self):
        if not self.target_hwnd or not win32gui.IsWindow(self.target_hwnd):
            self.preview_label.setText("请先拾取一个窗口")
            return
        try:
            rect = win32gui.GetClientRect(self.target_hwnd)
            left, top, right, bottom = rect
            width = right - left
            height = bottom - top
            if width <= 0 or height <= 0: return
            hwnd_dc = win32gui.GetWindowDC(self.target_hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(bitmap)
            success = windll.user32.PrintWindow(self.target_hwnd, save_dc.GetSafeHdc(), 3)
            if success:
                bi = bitmap.GetInfo()
                buf = bitmap.GetBitmapBits(True)
                img = Image.frombuffer('RGB', (bi['bmWidth'], bi['bmHeight']), buf, 'raw', 'BGRX', 0, 1)
                scaled_img = img.resize(
                    (self.preview_label.width(), self.preview_label.height()),
                    Image.Resampling.LANCZOS
                )
                qim = QImage(scaled_img.tobytes(), scaled_img.width, scaled_img.height, QImage.Format_RGB888)
                self.preview_label.setPixmap(QPixmap.fromImage(qim))
            else:
                self.preview_label.setText("截图失败")
            win32gui.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(self.target_hwnd, hwnd_dc)
        except Exception as e:
            self.preview_label.setText(f"截图异常: {e}")

    def show_capture_help(self):
        help_path = os.path.join(BASE_DIR, "help", "capture_compare.html")
        if os.path.exists(help_path):
            webbrowser.open(f"file:///{help_path}")
        else:
            QMessageBox.warning(self, "帮助", f"帮助文件未找到：{help_path}")

    def start_preview(self): pass
    def stop_preview(self): pass
    def toggle_preview(self): pass
    def update_preview(self): pass

    def closeEvent(self, event):
        if self.drag_active:
            QApplication.instance().removeEventFilter(self)
            if self.tracker: self.tracker.close()
            while QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
        event.accept()