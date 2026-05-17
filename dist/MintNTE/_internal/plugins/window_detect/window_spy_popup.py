import sys, os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QGroupBox, QLineEdit,
    QVBoxLayout, QHBoxLayout, QFormLayout, QFrame
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QEvent
from PyQt5.QtGui import QPixmap, QCursor, QFont, QPalette, QColor
import win32gui, win32con, win32process, win32api
from ctypes import windll

# ---------- 动态获取资源路径 ----------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMAGE_DIR = os.path.join(BASE_DIR, "Image", "logo")

# 可选进程名库
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

class NeonWindowSpy(QWidget):
    def __init__(self):
        super().__init__()
        self.capturing = False
        self.last_rect = None
        self.target_hwnd = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.capture_motion)

        self.init_ui()
        self.apply_neon_style()

    def init_ui(self):
        self.setWindowTitle("窗口拾取器 · 霓虹")
        self.setFixedSize(380, 520)
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 主容器
        self.main_frame = QFrame(self)
        self.main_frame.setObjectName("mainFrame")
        self.main_frame.setGeometry(5, 5, 370, 510)

        main_layout = QVBoxLayout(self.main_frame)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # ---- 图标区域 ----
        icon_layout = QVBoxLayout()
        self.icon_frame = QFrame()
        self.icon_frame.setFixedSize(200, 120)
        self.icon_frame.setStyleSheet("background: transparent;")

        # 背景图 (32x32) + 靶心图 (17x17)，不存在时用纯色Label替代
        self.bg_label = QLabel(self.icon_frame)
        bg_pix = self._load_pixmap("Window_Picker.png", 32, 32)
        self.bg_label.setPixmap(bg_pix)
        self.bg_label.setGeometry(84, 44, 32, 32)

        self.spy_label = QLabel(self.icon_frame)
        spy_pix = self._load_pixmap("Window_Spy.png", 17, 17)
        self.spy_label.setPixmap(spy_pix)
        self.spy_label.setGeometry(91, 51, 17, 17)
        self.spy_label.setCursor(Qt.CrossCursor)
        self.spy_label.setMouseTracking(True)
        self.spy_label.installEventFilter(self)

        icon_layout.addWidget(self.icon_frame, alignment=Qt.AlignCenter)
        hint = QLabel("按住靶心拖到目标窗口后松开")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: #00ddff; font-size: 9pt; font-family: 'Microsoft YaHei';")
        icon_layout.addWidget(hint)
        main_layout.addLayout(icon_layout)

        # ---- 信息面板 ----
        info_group = QGroupBox(" 窗口信息 ")
        info_group.setObjectName("infoGroup")
        form = QFormLayout()
        form.setSpacing(2)

        self.fields = {}
        field_list = [
            ("句柄", "handle"),
            ("标题", "title"),
            ("类名", "class_name"),
            ("位置X", "pos_x"),
            ("位置Y", "pos_y"),
            ("宽度", "width"),
            ("高度", "height"),
            ("进程ID", "pid"),
            ("进程名", "process_name"),
            ("风格", "style"),
            ("扩展风格", "ex_style"),
        ]
        for label, key in field_list:
            ledit = QLineEdit()
            ledit.setReadOnly(True)
            ledit.setStyleSheet("background: #0a0a1a; color: #00ffcc; border: 1px solid #00ccff; padding: 2px;")
            self.fields[key] = ledit
            form.addRow(QLabel(f"{label}:"), ledit)

        info_group.setLayout(form)
        main_layout.addWidget(info_group)

        # 关闭按钮
        close_btn = QLabel("✕ 关闭")
        close_btn.setAlignment(Qt.AlignCenter)
        close_btn.setStyleSheet("color: #ff4488; font-size: 9pt; margin-top: 4px;")
        close_btn.mousePressEvent = lambda e: self.close()
        main_layout.addWidget(close_btn, alignment=Qt.AlignRight)

    def _load_pixmap(self, filename, w, h):
        """尝试加载图片，失败则返回一个纯色QPixmap占位"""
        path = os.path.join(IMAGE_DIR, filename)
        if os.path.exists(path):
            return QPixmap(path).scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            pix = QPixmap(w, h)
            pix.fill(QColor(0, 200, 255))  # 占位色
            return pix

    def apply_neon_style(self):
        self.setStyleSheet("""
            QWidget {
                background: transparent;
                font-family: "Microsoft YaHei", "Segoe UI";
            }
            #mainFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(10,5,30,200), stop:1 rgba(5,10,40,220));
                border: 2px solid #00ccff;
                border-radius: 12px;
            }
            QGroupBox {
                color: #00ddff;
                font-weight: bold;
                border: 1px solid #00aaff;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                background: rgba(0, 0, 30, 120);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: #00ffff;
            }
            QLabel {
                color: #ccddff;
                background: transparent;
            }
            QLineEdit {
                background: #0a0a1a;
                color: #00ffcc;
                border: 1px solid #00ccff;
                border-radius: 3px;
                padding: 2px 4px;
            }
        """)

    # ========== 鼠标事件过滤器 ==========
    def eventFilter(self, obj, event):
        if obj == self.spy_label:
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self.start_capture()
                return True
            elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self.stop_capture()
                return True
        return super().eventFilter(obj, event)

    def start_capture(self):
        if self.capturing:
            return
        self.capturing = True
        self.setWindowOpacity(0.1)
        self.timer.start(50)

    def stop_capture(self):
        if not self.capturing:
            return
        self.capturing = False
        self.timer.stop()
        self.setWindowOpacity(1.0)

        if self.last_rect:
            self._draw_rect(self.last_rect)
            self.last_rect = None

        pt = win32gui.GetCursorPos()
        hwnd = win32gui.WindowFromPoint(pt)
        own_hwnd = int(self.winId())
        if hwnd == own_hwnd:
            self.hide()
            hwnd = win32gui.WindowFromPoint(pt)
            self.show()
        self.target_hwnd = hwnd
        self.update_info()

    def capture_motion(self):
        if not self.capturing:
            return
        try:
            pt = win32gui.GetCursorPos()
            hwnd = win32gui.WindowFromPoint(pt)
            own_hwnd = int(self.winId())
            if hwnd == own_hwnd:
                return
            rect = win32gui.GetWindowRect(hwnd)
            if rect != self.last_rect:
                if self.last_rect:
                    self._draw_rect(self.last_rect)
                self._draw_rect(rect)
                self.last_rect = rect
        except Exception:
            pass

    def _draw_rect(self, rect):
        try:
            hdc = win32gui.GetDC(0)
            win32gui.DrawFocusRect(hdc, rect)
            win32gui.ReleaseDC(0, hdc)
        except Exception:
            pass

    def update_info(self):
        hwnd = self.target_hwnd
        if not hwnd or not win32gui.IsWindow(hwnd):
            return

        self.fields["handle"].setText(f"0x{hwnd:08X} ({hwnd})")
        title = win32gui.GetWindowText(hwnd)
        self.fields["title"].setText(title)
        cls = win32gui.GetClassName(hwnd)
        self.fields["class_name"].setText(cls)
        x, y, r, b = win32gui.GetWindowRect(hwnd)
        self.fields["pos_x"].setText(str(x))
        self.fields["pos_y"].setText(str(y))
        self.fields["width"].setText(str(r - x))
        self.fields["height"].setText(str(b - y))
        tid, pid = win32process.GetWindowThreadProcessId(hwnd)
        self.fields["pid"].setText(str(pid))
        if HAS_PSUTIL:
            try:
                pname = psutil.Process(pid).name()
            except Exception:
                pname = "N/A"
        else:
            pname = "(需安装psutil)"
        self.fields["process_name"].setText(pname)
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        self.fields["style"].setText(f"0x{style:08X}")
        self.fields["ex_style"].setText(f"0x{ex:08X}")


# ========== 独立运行测试 ==========
if __name__ == "__main__":
    try:
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = NeonWindowSpy()
    window.show()
    sys.exit(app.exec_())