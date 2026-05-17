import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QApplication)
from PyQt5.QtCore import Qt
from UI import logui

class JoinUsUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        logui.info("加入我们界面已加载")
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        title_label = QLabel("技术作者与玩家交流群")
        title_label.setStyleSheet("color: #f0f; font-size: 22px; font-weight: bold;")
        main_layout.addWidget(title_label, alignment=Qt.AlignCenter)

        info_label = QLabel("NTE 薄荷 AI 助手 开发团队招募：")
        info_label.setStyleSheet("color: #0ff; font-size: 28px;")
        main_layout.addWidget(info_label)

        items = [
            ("- 开发项目", "", None),
            ("- 薄荷AI①群", "796636370", "796636370"),
            ("- 薄荷AI②群", "1094574886", "1094574886"),
            ("- 薄荷AI③群", "571288937", "571288937"),
            ("- 薄荷AI④群", "（以上满了再新建）", None),
            ("- 薄荷AI开源作者群", "1098508219", "1098508219"),
            ("----------------项目技术提供作者!!!排名不分先后----------------", "", None),
            ("- 开源作者:稻七学长：QQ", "635444099", "635444099"),
            # ("- 开源作者:☂️：QQ", "422702500", "422702500"),
            # ("- 开源作者:文曦達：QQ", "195262874", "195262874"),
            ("- 为爱发电", "欢迎加入我们", None),
        ]

        for prefix, number, copy_text in items:
            row_layout = QHBoxLayout()
            prefix_label = QLabel(prefix)
            prefix_label.setStyleSheet("color: #0ff; font-size: 20px;")
            row_layout.addWidget(prefix_label)
            if number:
                number_label = QLabel(number)
                number_label.setStyleSheet("color: #f0f; font-size: 16px; font-weight: bold;")
                row_layout.addWidget(number_label)
            if copy_text:
                btn = QPushButton("复制")
                btn.setFixedSize(60, 25)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2a2a3a;
                        color: #0ff;
                        border: 1px solid #0ff;
                        border-radius: 4px;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: #0ff;
                        color: #1e1e2f;
                    }
                """)
                btn.clicked.connect(lambda checked, text=copy_text: self.copy_to_clipboard(text))
                row_layout.addWidget(btn)
            row_layout.addStretch()
            main_layout.addLayout(row_layout)

        main_layout.addStretch()

    def copy_to_clipboard(self, text):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        logui.info(f"已复制: {text}")