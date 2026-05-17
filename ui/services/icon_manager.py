# ui/services/icon_manager.py
import os, sys
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox
from utils.path_utils import resource_path

TITLE_ICO = resource_path("Image/logo/titlelogo.ico")
WINDOWS_ICO = resource_path("Image/logo/Windowslogo.ico")

def set_app_icon(app: QApplication = None, window: QWidget = None):
    if app is None and window is None:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            window = app.activeWindow()
    if app and os.path.exists(TITLE_ICO):
        app.setWindowIcon(QIcon(TITLE_ICO))
    if window and os.path.exists(TITLE_ICO):
        window.setWindowIcon(QIcon(TITLE_ICO))

def get_message_box_icon():
    if os.path.exists(WINDOWS_ICO):
        return QIcon(WINDOWS_ICO)
    return QIcon()

def set_message_box_icon(msg_box: QMessageBox):
    if os.path.exists(WINDOWS_ICO):
        msg_box.setWindowIcon(QIcon(WINDOWS_ICO))
    msg_box.setStyleSheet("""
        QMessageBox {
            background-color: #1e1e2f;
            color: #00f0ff;
        }
        QMessageBox QLabel {
            color: #00f0ff;
            font-size: 14px;
        }
        QMessageBox QPushButton {
            background-color: #3a3a5a;
            color: #00f0ff;
            border: 1px solid #00f0ff;
            padding: 5px 15px;
            border-radius: 4px;
            min-width: 60px;
        }
        QMessageBox QPushButton:hover {
            background-color: #5a5a7a;
        }
    """)

def setup_main_window_icon(window: QWidget):
    """直接设置主窗口图标"""
    if os.path.exists(TITLE_ICO):
        window.setWindowIcon(QIcon(TITLE_ICO))