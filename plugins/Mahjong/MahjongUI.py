from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton
from PyQt5.QtCore import Qt
from UI import logui

logui.info("麻将界面加载")
logui.error("麻将功能开发中")
class MahjongUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel("麻将功能开发中")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #0ff; font-size: 20px;")
        layout.addWidget(label)
        btn = QPushButton("占位按钮")
        btn.setObjectName("NeonButton")
        layout.addWidget(btn)
        self.setStyleSheet("""
        #NeonButton {
            background-color: #2a2a3a;
            color: #0ff;
            border: 1px solid #0ff;
            border-radius: 5px;
            padding: 5px;
        }
        """)