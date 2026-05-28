"""
BetterGI 界面复刻 - PyQt5 实现
需要安装: pip install PyQt5
"""
import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QStackedWidget, QFrame, QTextEdit, QTabWidget, QGroupBox,
    QCheckBox, QComboBox, QLineEdit, QGridLayout, QScrollArea, QStatusBar,
    QSizePolicy
)
from PyQt5.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPalette, QColor


# -------------------- 自定义无边框窗口 --------------------
class FramelessWindow(QWidget):
    """提供自定义标题栏和窗口控制的无边框窗口"""
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            delta = event.globalPos() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


# -------------------- 标题栏 --------------------
class TitleBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.parent = parent
        self.setStyleSheet("""
            TitleBar {
                background: #1a1a2e;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)

        # 标题
        self.title_label = QLabel("BetterGI - 原神自动化工具")
        self.title_label.setStyleSheet("color: #eeeeee; font-weight: bold; font-size: 14px;")
        layout.addWidget(self.title_label)
        layout.addStretch()

        # 最小化按钮
        self.min_btn = QPushButton("—")
        self.min_btn.setFixedSize(40, 30)
        self.min_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #cccccc; border: none; font-size: 16px;
            }
            QPushButton:hover { background: #2a2a3e; }
        """)
        self.min_btn.clicked.connect(self.parent.showMinimized)
        layout.addWidget(self.min_btn)

        # 关闭按钮
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(40, 30)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #cccccc; border: none; font-size: 16px;
            }
            QPushButton:hover { background: #e81123; color: white; }
        """)
        self.close_btn.clicked.connect(self.parent.close)
        layout.addWidget(self.close_btn)


# -------------------- 左侧导航栏 --------------------
class NavButton(QPushButton):
    def __init__(self, text, icon_path=None, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setFixedHeight(45)
        self.setCursor(Qt.PointingHandCursor)
        if icon_path:
            self.setIcon(QIcon(icon_path))
            self.setIconSize(QSize(20, 20))
        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #cccccc;
                border: none;
                border-radius: 6px;
                margin: 2px 8px;
                text-align: left;
                padding-left: 15px;
                font-size: 14px;
            }
            QPushButton:hover { background: #2a2a3e; }
            QPushButton:checked { background: #4a6cf7; color: white; }
        """)


class Sidebar(QFrame):
    def __init__(self, stacked_widget, parent=None):
        super().__init__(parent)
        self.setFixedWidth(180)
        self.setStyleSheet("Sidebar { background: #16162a; border-bottom-left-radius: 8px; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 20, 0, 0)
        layout.setSpacing(5)

        # 导航按钮与 stacked widget 索引对应
        self.btn_start = NavButton("  🚀  启动")
        self.btn_config = NavButton("  ⚙️  配置")
        self.btn_log = NavButton("  📋  日志")
        self.btn_about = NavButton("  ℹ️  关于")

        layout.addWidget(self.btn_start)
        layout.addWidget(self.btn_config)
        layout.addWidget(self.btn_log)
        layout.addStretch()
        layout.addWidget(self.btn_about)

        # 按钮组互斥
        self.btn_group = [self.btn_start, self.btn_config, self.btn_log, self.btn_about]
        for i, btn in enumerate(self.btn_group):
            btn.clicked.connect(lambda checked, idx=i: stacked_widget.setCurrentIndex(idx))
            btn.clicked.connect(lambda checked, b=btn: self.set_checked(b))

        self.btn_start.setChecked(True)

    def set_checked(self, button):
        for btn in self.btn_group:
            btn.setChecked(btn == button)


# -------------------- 页面1：启动 --------------------
class StartPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(30)

        # 大标题
        title = QLabel("BetterGI")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 32px; font-weight: bold; color: #4a6cf7;")
        layout.addWidget(title)

        # 状态提示
        status = QLabel("状态：就绪")
        status.setAlignment(Qt.AlignCenter)
        status.setStyleSheet("font-size: 16px; color: #aaaaaa;")
        layout.addWidget(status)

        # 启动按钮
        self.launch_btn = QPushButton("🚀  启动自动化")
        self.launch_btn.setFixedSize(220, 60)
        self.launch_btn.setCursor(Qt.PointingHandCursor)
        self.launch_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4a6cf7, stop:1 #6c5ce7);
                color: white; border: none; border-radius: 30px;
                font-size: 18px; font-weight: bold;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #5b7bfa, stop:1 #7d6ff0); }
            QPushButton:pressed { background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #3a5ce6, stop:1 #5c4bd6); }
        """)
        layout.addWidget(self.launch_btn, alignment=Qt.AlignCenter)

        # 版本信息
        version = QLabel("v2.0.0 | 仅供学习交流")
        version.setAlignment(Qt.AlignCenter)
        version.setStyleSheet("color: #666666; font-size: 12px;")
        layout.addWidget(version)


# -------------------- 页面2：配置 --------------------
class ConfigPage(QWidget):
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #2a2a3e; border-radius: 6px; background: #1e1e32; }
            QTabBar::tab {
                background: #16162a; color: #aaaaaa; padding: 8px 20px;
                border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px;
            }
            QTabBar::tab:selected { background: #2a2a3e; color: #4a6cf7; }
        """)

        # 基本设置选项卡
        basic_tab = QWidget()
        basic_layout = QGridLayout(basic_tab)
        basic_layout.setVerticalSpacing(15)

        self.add_setting_row(basic_layout, 0, "自动拾取", QCheckBox(), checked=True)
        self.add_setting_row(basic_layout, 1, "自动战斗", QCheckBox(), checked=True)
        self.add_setting_row(basic_layout, 2, "截图间隔(ms)", QLineEdit("500"))
        self.add_setting_row(basic_layout, 3, "战斗策略", QComboBox())
        basic_layout.itemAtPosition(3, 1).widget().addItems(["激进", "保守", "智能"])

        tab_widget.addTab(basic_tab, "  基本设置  ")

        # 高级设置选项卡
        adv_tab = QWidget()
        adv_layout = QGridLayout(adv_tab)
        self.add_setting_row(adv_layout, 0, "调试模式", QCheckBox(), checked=False)
        self.add_setting_row(adv_layout, 1, "日志等级", QComboBox())
        adv_layout.itemAtPosition(1, 1).widget().addItems(["INFO", "DEBUG", "ERROR"])

        tab_widget.addTab(adv_tab, "  高级设置  ")
        main_layout.addWidget(tab_widget)

        # 保存按钮
        save_btn = QPushButton("保存配置")
        save_btn.setFixedWidth(120)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet("""
            QPushButton {
                background: #4a6cf7; color: white; border: none; border-radius: 6px;
                padding: 8px; font-size: 14px;
            }
            QPushButton:hover { background: #5b7bfa; }
        """)
        main_layout.addWidget(save_btn, alignment=Qt.AlignRight)

    def add_setting_row(self, layout, row, label_text, widget, checked=None):
        label = QLabel(label_text)
        label.setStyleSheet("color: #cccccc; font-size: 14px;")
        layout.addWidget(label, row, 0)
        widget.setStyleSheet("""
            QCheckBox { color: #cccccc; spacing: 8px; }
            QCheckBox::indicator { width: 18px; height: 18px; }
            QLineEdit, QComboBox {
                background: #2a2a3e; color: #cccccc; border: 1px solid #3a3a5e;
                border-radius: 4px; padding: 5px;
            }
            QComboBox::drop-down { border: none; }
        """)
        if isinstance(widget, QCheckBox) and checked is not None:
            widget.setChecked(checked)
        layout.addWidget(widget, row, 1)


# -------------------- 页面3：日志 --------------------
class LogPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background: #12122a; color: #00ff88; border: 1px solid #2a2a3e;
                border-radius: 6px; font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px; padding: 10px;
            }
        """)
        # 示例日志
        self.log_text.append("[2026-05-19 10:30:15] 系统初始化完成")
        self.log_text.append("[2026-05-19 10:30:16] 检测到游戏窗口...")
        self.log_text.append("[2026-05-19 10:30:17] 自动化脚本已就绪")
        layout.addWidget(self.log_text)

        # 清空按钮
        clear_btn = QPushButton("清空日志")
        clear_btn.setFixedWidth(100)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #2a2a3e; color: #cccccc; border: none; border-radius: 4px;
                padding: 6px;
            }
            QPushButton:hover { background: #3a3a5e; }
        """)
        clear_btn.clicked.connect(self.log_text.clear)
        layout.addWidget(clear_btn, alignment=Qt.AlignRight)


# -------------------- 页面4：关于 --------------------
class AboutPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(15)

        title = QLabel("BetterGI")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #4a6cf7;")
        layout.addWidget(title)

        desc = QLabel("原神自动化工具 · 界面复刻版\n\n技术栈：Python + PyQt5\n开发者：社区\n仅供学习交流使用")
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: #aaaaaa; font-size: 14px; line-height: 1.6;")
        layout.addWidget(desc)

        ver = QLabel("版本 2.0.0 (模拟)")
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet("color: #666666; font-size: 12px;")
        layout.addWidget(ver)


# -------------------- 主窗口 --------------------
class BetterGIClone(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BetterGI")
        self.resize(900, 600)
        self.setMinimumSize(800, 500)

        # 主容器（带圆角和阴影效果）
        container = QFrame(self)
        container.setObjectName("mainContainer")
        container.setStyleSheet("""
            #mainContainer {
                background: #1e1e32;
                border-radius: 8px;
                border: 1px solid #2a2a3e;
            }
        """)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 标题栏
        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)

        # 内容区域（横向排列）
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # 堆叠页面
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("QStackedWidget { background: transparent; }")
        self.stack.addWidget(StartPage())
        self.stack.addWidget(ConfigPage())
        self.stack.addWidget(LogPage())
        self.stack.addWidget(AboutPage())

        # 侧边栏
        self.sidebar = Sidebar(self.stack)

        content_layout.addWidget(self.sidebar)
        content_layout.addWidget(self.stack)
        main_layout.addLayout(content_layout)

        # 底部状态栏
        self.status = QLabel("  就绪  |  原神窗口未检测到  |  版本 2.0.0")
        self.status.setFixedHeight(28)
        self.status.setStyleSheet("""
            QLabel {
                background: #16162a; color: #777777; font-size: 12px;
                border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;
                padding-left: 10px;
            }
        """)
        main_layout.addWidget(self.status)

        # 将容器设为中央部件
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)  # 留出阴影空间
        outer_layout.addWidget(container)


# -------------------- 启动应用 --------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 全局暗色调色板（作为兜底）
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(30, 30, 50))
    dark_palette.setColor(QPalette.WindowText, QColor(200, 200, 200))
    dark_palette.setColor(QPalette.Base, QColor(22, 22, 42))
    dark_palette.setColor(QPalette.AlternateBase, QColor(30, 30, 50))
    dark_palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.Text, QColor(200, 200, 200))
    dark_palette.setColor(QPalette.Button, QColor(30, 30, 50))
    dark_palette.setColor(QPalette.ButtonText, QColor(200, 200, 200))
    dark_palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    dark_palette.setColor(QPalette.Highlight, QColor(74, 108, 247))
    dark_palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(dark_palette)

    window = BetterGIClone()
    window.show()
    sys.exit(app.exec_())