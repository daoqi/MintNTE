# plugins/dark_racing/dark_racing_ui.py
import threading
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox, QMessageBox
)
from PyQt5.QtCore import Qt
from plugins.dark_racing.dark_racing_core import DarkRacingWorker
from Module.Hwnd.game_hwnd import get_game_hwnd   # 需要引入
import ui.services.logui as logui

class DarkRacingUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.stop_event = None
        self.worker = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        control_group = QGroupBox("黑暗赛车控制")
        control_layout = QVBoxLayout(control_group)

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("开始赛车")
        self.btn_start.setObjectName("BigStartButton")
        self.btn_start.clicked.connect(self.toggle_race)
        btn_row.addWidget(self.btn_start)

        self.btn_stop = QPushButton("停止赛车")
        self.btn_stop.setObjectName("BigStopButton")
        self.btn_stop.clicked.connect(self.stop_race)
        self.btn_stop.setEnabled(False)
        btn_row.addWidget(self.btn_stop)
        btn_row.addStretch()
        control_layout.addLayout(btn_row)

        self.lbl_count = QLabel("完成次数: 0")
        self.lbl_count.setStyleSheet("color: #00ffff; font-size: 14px;")
        control_layout.addWidget(self.lbl_count)

        layout.addWidget(control_group)
        layout.addStretch()

        self.setStyleSheet("""
        QGroupBox { color: #00ffff; border: 2px solid #00ffff; border-radius: 5px; margin-top: 10px; font-weight: bold; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        QLabel { color: #00ffff; }
        QPushButton { background-color: #0a0a2a; border: 2px solid #00ffff; border-radius: 5px; color: #00ffff; padding: 5px 12px; }
        QPushButton:hover { background-color: #00ffff; color: #050510; }
        #BigStartButton { background-color: #2a2a3a; color: #0f0; border: 2px solid #0f0; border-radius: 8px; padding: 8px 20px; font-size: 14px; font-weight: bold; }
        #BigStartButton:hover { background-color: #0f0; color: #1e1e2f; }
        #BigStopButton { background-color: #2a2a3a; color: #f00; border: 2px solid #f00; border-radius: 8px; padding: 8px 20px; font-size: 14px; font-weight: bold; }
        #BigStopButton:hover { background-color: #f00; color: #1e1e2f; }
        """)

    def toggle_race(self):
        if self.worker and self.worker._thread and self.worker._thread.is_alive():
            self.stop_race()
        else:
            self.start_race()

    def start_race(self):
        hwnd = get_game_hwnd()
        if not hwnd:
            QMessageBox.warning(self, "错误", "未找到游戏窗口，请先锁定窗口。")
            return
        self.stop_event = threading.Event()
        status_cb = lambda text: self.lbl_count.setText(text)
        finish_cb = lambda: self._on_worker_finished()
        self.worker = DarkRacingWorker(self.stop_event, status_cb, finish_cb)
        self.worker.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        logui.info("黑暗赛车已启动")

    def stop_race(self):
        if self.stop_event:
            self.stop_event.set()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        logui.info("黑暗赛车已停止")

    def _on_worker_finished(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)