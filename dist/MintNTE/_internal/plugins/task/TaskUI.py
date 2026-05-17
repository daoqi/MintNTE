# plugins/task/TaskUI.py
import sys, os, threading, webbrowser
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QSpinBox, QCheckBox, QRadioButton, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon

def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from Module.Hwnd.game_hwnd import get_game_hwnd
from plugins.task.Task_core import TaskWorker
import ui.services.logui as logui

ICON_PATH = resource_path("Image/logo/titlelogo.ico")
TASK_HELP_HTML = resource_path("help/task_help.html")

class TaskUI(QWidget):
    update_status_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stop_event = None
        self.worker = None

        self.setup_ui()
        self.update_status_signal.connect(self.set_status)

    def _msg_box(self, icon, title, text):
        box = QMessageBox(icon, title, text, parent=self)
        if os.path.exists(ICON_PATH):
            box.setWindowIcon(QIcon(ICON_PATH))
        return box

    def _help_button_style(self):
        return """
            QPushButton {
                background-color: #00f0ff;
                color: #1e1e2f;
                border: 1px solid #00f0ff;
                border-radius: 12px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #00f0ff;
                color: #1e1e2f;
            }
        """

    def open_help(self):
        if os.path.exists(TASK_HELP_HTML):
            webbrowser.open(f"file:///{TASK_HELP_HTML}")
        else:
            QMessageBox.warning(self, "帮助", f"帮助文件未找到：{TASK_HELP_HTML}")

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        control_group = QGroupBox("任务控制")
        control_layout = QVBoxLayout(control_group)

        start_row = QHBoxLayout()
        self.btn_start = QPushButton("启动任务")
        self.btn_start.setObjectName("BigStartButton")
        self.btn_start.clicked.connect(self.toggle_task)
        start_row.addWidget(self.btn_start)

        self.btn_stop = QPushButton("停止")
        self.btn_stop.setObjectName("BigStopButton")
        self.btn_stop.clicked.connect(self.stop_task)
        self.btn_stop.setEnabled(False)
        start_row.addWidget(self.btn_stop)

        help_btn = QPushButton("?")
        help_btn.setFixedSize(24, 24)
        help_btn.setToolTip("点击查看任务使用教程")
        help_btn.setStyleSheet(self._help_button_style())
        help_btn.clicked.connect(self.open_help)
        start_row.addWidget(help_btn)
        start_row.addStretch()
        control_layout.addLayout(start_row)

        dialog_group = QGroupBox("对话内容选择")
        dialog_layout = QHBoxLayout(dialog_group)
        self.radio_dialog_1 = QRadioButton("第一项 (F键)")
        self.radio_dialog_2 = QRadioButton("第二项 (点击)")
        self.radio_dialog_3 = QRadioButton("第三项 (点击)")
        self.radio_dialog_1.setChecked(True)
        dialog_layout.addWidget(self.radio_dialog_1)
        dialog_layout.addWidget(self.radio_dialog_2)
        dialog_layout.addWidget(self.radio_dialog_3)
        dialog_layout.addStretch()
        control_layout.addWidget(dialog_group)

        self.cb_auto_pick = QCheckBox("自动拾取野外物资")
        self.cb_auto_pick.setChecked(False)
        control_layout.addWidget(self.cb_auto_pick)

        self.cb_no_remind = QCheckBox("今日不再提示跳过剧情")
        self.cb_no_remind.setChecked(False)
        control_layout.addWidget(self.cb_no_remind)

        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel("截图延迟(毫秒):"))
        self.spin_delay = QSpinBox()
        self.spin_delay.setRange(10, 5000)
        self.spin_delay.setValue(50)
        self.spin_delay.setSuffix(" ms")
        delay_row.addWidget(self.spin_delay)
        delay_row.addStretch()
        control_layout.addLayout(delay_row)

        layout.addWidget(control_group)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #00ff00; font-size: 14px; font-weight: bold;")
        layout.addWidget(self.status_label)

        layout.addStretch()

        self.setStyleSheet("""
        QGroupBox { color: #00ffff; border: 2px solid #00ffff; border-radius: 5px; margin-top: 10px; font-weight: bold; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        QLabel { color: #00ffff; }
        QPushButton { background-color: #0a0a2a; border: 2px solid #00ffff; border-radius: 5px; color: #00ffff; padding: 5px 12px; }
        QPushButton:hover { background-color: #00ffff; color: #050510; }
        QRadioButton { color: #00ffff; }
        QCheckBox { color: #00ffff; }
        QSpinBox { background-color: #0a0a2a; border: 2px solid #00ffff; border-radius: 5px; color: #00ffff; padding: 2px; }
        #BigStartButton { background-color: #2a2a3a; color: #0f0; border: 2px solid #0f0; border-radius: 8px; padding: 8px 20px; font-size: 14px; font-weight: bold; }
        #BigStartButton:hover { background-color: #0f0; color: #1e1e2f; }
        #BigStopButton { background-color: #2a2a3a; color: #f00; border: 2px solid #f00; border-radius: 8px; padding: 8px 20px; font-size: 14px; font-weight: bold; }
        #BigStopButton:hover { background-color: #f00; color: #1e1e2f; }
        """)

    def toggle_task(self):
        if self.worker and self.worker._thread and self.worker._thread.is_alive():
            self.stop_task()
        else:
            self.start_task()

    def start_task(self):
        hwnd = get_game_hwnd()
        if not hwnd:
            self._msg_box(QMessageBox.Warning, "错误", "未找到游戏窗口，请先锁定窗口。").exec_()
            return

        self.stop_event = threading.Event()
        config = {
            "dialog_option": 1 if self.radio_dialog_1.isChecked() else (2 if self.radio_dialog_2.isChecked() else 3),
            "auto_pick": self.cb_auto_pick.isChecked(),
            "delay_ms": self.spin_delay.value(),
            "no_remind_skip": self.cb_no_remind.isChecked()
        }
        status_cb = lambda msg: self.update_status_signal.emit(msg)
        finish_cb = lambda: self.update_status_signal.emit("任务结束") or self._on_worker_finished()

        self.worker = TaskWorker(hwnd, self.stop_event, config, status_cb, finish_cb)
        self.worker.start()

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        logui.info("任务线程已启动")

    def stop_task(self):
        if self.stop_event:
            self.stop_event.set()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        logui.info("任务停止信号已发出")

    def _on_worker_finished(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def set_status(self, text):
        self.status_label.setText(text)

    def closeEvent(self, event):
        self.stop_task()
        event.accept()