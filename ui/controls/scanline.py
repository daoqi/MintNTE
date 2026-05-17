from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen

class ScanlineWidget(QWidget):
    def __init__(self, parent, line_color):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.line_pos = 0
        self.line_color = QColor(line_color)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_line)
        self.timer.start(50)

    def _update_line(self):
        self.line_pos = (self.line_pos + 2) % self.height()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QPen(self.line_color, 1, Qt.DashLine))
        painter.drawLine(0, self.line_pos, self.width(), self.line_pos)

    def update_color(self, color_str):
        self.line_color = QColor(color_str)