from PyQt5.QtWidgets import QPushButton, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, pyqtProperty, QRectF
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush, QLinearGradient, QPainterPath, QPainterPathStroker

class NeonSelectButton(QPushButton):
    def __init__(self, text, neon_color, parent=None):
        super().__init__(text, parent)
        self.neon_color = QColor(neon_color)
        self._selected = False
        self.offset = 0.0
        self.breathe_alpha = 255
        self.breathe_dir = -1
        self.ripple_alpha = 0
        self.ripple_radius = 0
        self._scale_factor = 1.0
        self.shock_alpha = 0
        self.shock_radius = 0

        self.setFixedSize(120, 50)
        self.setCheckable(True)
        self.toggled.connect(self._on_toggled)
        self.clicked.connect(self._start_click_anim)
        self._update_style()
        self.glow = QGraphicsDropShadowEffect(self)
        self.glow.setColor(self.neon_color)
        self.glow.setOffset(0, 0)
        self.glow.setBlurRadius(28)
        self.setGraphicsEffect(self.glow)

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate)
        self.anim_timer.setInterval(30)

        self.ripple_timer = QTimer(self)
        self.ripple_timer.timeout.connect(self._ripple_animate)

        self.scale_anim = QPropertyAnimation(self, b"scale_factor")
        self.scale_anim.setDuration(250)
        self.scale_anim.setKeyValues([(0.0, 1.0), (0.4, 1.12), (0.7, 0.96), (1.0, 1.0)])
        self.destroyed.connect(self.stop_all_timers)

    def get_scale_factor(self): return self._scale_factor
    def set_scale_factor(self, val): self._scale_factor = val; self.update()
    scale_factor = pyqtProperty(float, get_scale_factor, set_scale_factor)

    def _start_click_anim(self):
        self.ripple_alpha = 255
        self.ripple_radius = 0
        if self.ripple_timer.isActive(): self.ripple_timer.stop()
        self.ripple_timer.start(16)
        self.shock_alpha = 255
        self.shock_radius = 0
        self.scale_anim.stop()
        self.scale_anim.start()

    def _update_style(self):
        color_name = self.neon_color.name()
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: #1a1a2e;
                color: {color_name};
                border: none;
                border-radius: 18px;
                font-size: 15px;
                font-weight: bold;
                padding: 0px 12px;
            }}
            QPushButton:hover {{
                background-color: {color_name};
                color: #0a0a18;
            }}
        """)

    def set_neon_color(self, color_str):
        self.neon_color = QColor(color_str)
        self._update_style()
        self.glow.setColor(self.neon_color)
        self.update()

    def _on_toggled(self, checked):
        self._selected = checked
        if checked:
            if not self.anim_timer.isActive(): self.anim_timer.start()
        else:
            if self.anim_timer.isActive(): self.anim_timer.stop()
        self.update()

    def _animate(self):
        self.offset += 0.02
        if self.offset >= 1.0: self.offset -= 1.0
        self.breathe_alpha += self.breathe_dir * 3
        if self.breathe_alpha >= 255:
            self.breathe_alpha = 255; self.breathe_dir = -1
        elif self.breathe_alpha <= 80:
            self.breathe_alpha = 80; self.breathe_dir = 1
        self.update()

    def _ripple_animate(self):
        self.ripple_radius += 4
        self.ripple_alpha -= 10
        if self.ripple_alpha <= 0: self.ripple_timer.stop()
        self.shock_radius += 6
        self.shock_alpha -= 12
        if self.shock_alpha <= 0: self.shock_alpha = 0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        super().paintEvent(event)

        if self._selected:
            painter.save()
            cx, cy = self.rect().center().x(), self.rect().center().y()
            painter.translate(cx, cy)
            painter.scale(self._scale_factor, self._scale_factor)
            painter.translate(-cx, -cy)
            margin = 8
            rect = self.rect().adjusted(margin, margin, -margin, -margin)
            if rect.width() > 0 and rect.height() > 0:
                radius = rect.height() / 2
                painter.setPen(QPen(QColor(0, 0, 0), 5))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(rect, radius, radius)

                path = QPainterPath()
                path.addRoundedRect(QRectF(rect), radius, radius)
                stroker = QPainterPathStroker()
                stroker.setWidth(5)
                stroker.setCapStyle(Qt.RoundCap)
                stroker.setJoinStyle(Qt.RoundJoin)
                outline = stroker.createStroke(path)
                painter.setClipPath(outline)

                gro_rect = rect.adjusted(-30, -30, 30, 30)
                gradient = QLinearGradient(
                    gro_rect.left() + self.offset * gro_rect.width(), 0,
                    gro_rect.left() + (self.offset + 0.15) * gro_rect.width(), 0
                )
                light = QColor(self.neon_color)
                light.setAlpha(self.breathe_alpha)
                trans = QColor(self.neon_color)
                trans.setAlpha(0)
                gradient.setColorAt(0.0, trans)
                gradient.setColorAt(0.4, light)
                gradient.setColorAt(0.6, light)
                gradient.setColorAt(1.0, trans)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(gradient))
                painter.drawRect(gro_rect)
            painter.restore()

        if self.shock_alpha > 0:
            shock_color = QColor(self.neon_color); shock_color.setAlpha(self.shock_alpha)
            painter.setPen(QPen(shock_color, 4)); painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(self.rect().center(), self.shock_radius, self.shock_radius)
        if self.ripple_alpha > 0:
            ripple_color = QColor(self.neon_color); ripple_color.setAlpha(self.ripple_alpha)
            painter.setPen(QPen(ripple_color, 3)); painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(self.rect().center(), self.ripple_radius, self.ripple_radius)

    def stop_all_timers(self):
        for t in [self.anim_timer, self.ripple_timer]:
            if t.isActive(): t.stop()
        self.scale_anim.stop()