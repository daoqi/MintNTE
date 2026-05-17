import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont

class KeyStopwatch(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Z 键计时器")
        self.resize(400, 220)

        self.running = False
        self.count = 0
        self.timer = QTimer()
        self.timer.setInterval(10)
        self.timer.timeout.connect(self.update_time)

        # 显示文字
        self.label = QLabel("00:00.00")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setFont(QFont("Microsoft YaHei", 48, QFont.Bold))

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

    def keyPressEvent(self, event):
        # 按 Z 开始 / 结束
        if event.key() == Qt.Key_Z:
            if not self.running:
                # 开始计时
                self.running = True
                self.count = 0
                self.timer.start()
            else:
                # 停止计时
                self.running = False
                self.timer.stop()

    def update_time(self):
        self.count += 1
        ms = self.count * 10
        s = ms // 1000
        min = s // 60
        sec = s % 60
        msec = (ms % 1000) // 10

        self.label.setText(f"{min:02d}:{sec:02d}.{msec:02d}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = KeyStopwatch()
    win.show()
    sys.exit(app.exec_())