# ui/controls/particles.py
import random, math
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QTimer, QPoint, QPointF
from PyQt5.QtGui import QPainter, QColor, QBrush, QPolygonF, QPainterPath

class ParticleOverlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.particles = []
        # 改动：给一个默认的鼠标位置，并直接激活鼠标在窗口内
        self.mouse_pos = QPoint(300, 200)   # 窗口内的一个大致位置
        self.mouse_inside = True             # 立即开始生成粒子
        self.current_style = "star"
        self.enabled = True
        self.particle_color = QColor("#ffffff")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_particles)

    def start_particles(self):
        if self.enabled and not self.timer.isActive():
            self.timer.start(16)

    def stop_particles(self):
        if self.timer.isActive():
            self.timer.stop()
        self.particles.clear()
        self.update()

    def set_enabled(self, enabled):
        self.enabled = enabled
        if not enabled:
            self.timer.stop()
            self.particles.clear()
            self.update()
        else:
            self.timer.start(16)

    def set_particle_style(self, style):
        self.current_style = style
        self.particles.clear()

    def set_particle_color(self, color):
        self.particle_color = QColor(color)

    def update_particles(self):
        # 鼠标在窗口内时产生粒子，我们已强制 mouse_inside = True
        if self.enabled:
            for _ in range(3):
                self.particles.append({
                    'x': self.mouse_pos.x(), 'y': self.mouse_pos.y(),
                    'vx': random.uniform(-1.5, 1.5),
                    'vy': random.uniform(0.5, 2.5),
                    'life': random.uniform(0.5, 1.0),
                    'max_life': 1.0,
                    'size': random.randint(3, 7),
                    'color': QColor(self.particle_color),
                    'angle': random.uniform(0, 360)
                })
        for p in self.particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['life'] -= 0.01
            p['angle'] += 2
        self.particles = [p for p in self.particles if p['life'] > 0]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for p in self.particles:
            ratio = p['life'] / p['max_life']
            alpha = int(255 * ratio)
            size = p['size'] * ratio
            if size < 1: continue
            color = QColor(p['color'])
            color.setAlpha(alpha)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.save()
            painter.translate(p['x'], p['y'])
            if self.current_style == "star": self.draw_star(painter, size, p['angle'])
            elif self.current_style == "heart": self.draw_heart(painter, size)
            elif self.current_style == "wing": self.draw_wing(painter, size, p['angle'])
            elif self.current_style == "diamond": self.draw_diamond(painter, size, p['angle'])
            painter.restore()

    def rotate_point(self, pt, angle):
        x, y = pt
        rad = math.radians(angle)
        return x * math.cos(rad) - y * math.sin(rad), x * math.sin(rad) + y * math.cos(rad)

    def draw_star(self, painter, size, angle):
        pts = []
        for i in range(10):
            r = size if i % 2 == 0 else size * 0.4
            theta = math.radians(angle + i * 36)
            pts.append((r * math.cos(theta), r * math.sin(theta)))
        painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))

    def draw_heart(self, painter, size):
        path = QPainterPath()
        path.moveTo(0, size * 0.6)
        path.cubicTo(-size * 0.5, -size * 0.3, -size * 0.5, -size * 0.8, 0, -size * 0.3)
        path.cubicTo(size * 0.5, -size * 0.8, size * 0.5, -size * 0.3, 0, size * 0.6)
        painter.drawPath(path)

    def draw_wing(self, painter, size, angle):
        s = size * 1.2
        path = QPainterPath()
        def wp(x, y): return self.rotate_point((x, y), angle)
        path.moveTo(*wp(0, -s * 0.3))
        path.quadTo(*wp(-s * 0.6, -s * 0.9), *wp(-s * 0.9, -s * 0.4))
        path.quadTo(*wp(-s * 0.5, s * 0.1), *wp(0, s * 0.5))
        path.quadTo(*wp(s * 0.5, s * 0.1), *wp(s * 0.9, -s * 0.4))
        path.quadTo(*wp(s * 0.6, -s * 0.9), *wp(0, -s * 0.3))
        painter.drawPath(path)

    def draw_diamond(self, painter, size, angle):
        pts = [(0, -size), (size * 0.6, 0), (0, size), (-size * 0.6, 0)]
        rotated = [self.rotate_point(p, angle) for p in pts]
        painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in rotated]))