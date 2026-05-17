# logViewerUI.py
import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon

# 不再 import config，因为路径将由调用方传入
class LogViewer(QWidget):
    def __init__(self, log_file="MintNTE.log", parent=None):
        super().__init__(parent)
        self.log_file = log_file
        self.setWindowTitle("运行日志")
        self.resize(600, 400)
        # 图标可以保留硬编码或后续添加
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e2f;
                border: 2px solid #0ff;
                border-radius: 8px;
            }
            QTextEdit {
                background-color: #0a0a15;
                color: #0ff;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                border: none;
                margin: 4px;
                padding: 4px;
            }
            QTextEdit:focus {
                outline: none;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_log)
        self.timer.start(1000)
        self.refresh_log()

    def refresh_log(self):
        if not os.path.exists(self.log_file):
            self.text_edit.setPlainText("日志文件不存在")
            return
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if len(lines) > 1000:
                lines = lines[-1000:]
            self.text_edit.setPlainText("".join(lines))
            cursor = self.text_edit.textCursor()
            cursor.movePosition(cursor.End)
            self.text_edit.setTextCursor(cursor)
        except Exception as e:
            self.text_edit.setPlainText(f"读取日志出错: {e}")