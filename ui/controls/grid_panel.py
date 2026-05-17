# ui/grid_panel.py
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QPen
from ui.controls.scanline import ScanlineWidget   # 修正导入


class GridPanel(QWidget):
    def __init__(self, grid_color, scanline_color):
        super().__init__()
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.grid_color = QColor(grid_color)
        self.scanline = ScanlineWidget(self, scanline_color)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        pen = QPen(self.grid_color)
        pen.setWidth(1)
        painter.setPen(pen)
        w, h = self.width(), self.height()
        step = 30
        for x in range(0, w + step, step):
            painter.drawLine(x, 0, x - h, h)
        for y in range(0, h + step, step):
            painter.drawLine(0, y, w, y - w)

    def resizeEvent(self, event):
        self.scanline.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    def update_colors(self, grid_color, scanline_color):
        self.grid_color = QColor(grid_color)
        self.scanline.update_color(scanline_color)
        self.update()