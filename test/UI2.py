import sys, os, json, random, time, math, logging
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtCore import QObject, pyqtSignal
# ========== 日志 ==========
LOG_FILE = "neon_console.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "theme": "默认",
    "window_width": 1000,
    "window_height": 600,
    "last_page": 0,
    "particles_enabled": True
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except:
        pass

THEMES = {
    "默认": {
        "bg": "#0a0a18", "sidebar_bg": "#12122a", "panel_bg": "#0d0d1a",
        "toolbar_bg": "#1a1a2e", "breadcrumb_color": "#00f0ff",
        "btn_colors": ["#00f0ff", "#39ff14", "#ff003c", "#ffd700", "#ff44cc", "#a200ff"],
        "page_title_color": "#ffffff", "log_bg": "#12122a", "log_text": "#aaaaff"
    },
    "极光紫": {
        "bg": "#0a0a18", "sidebar_bg": "#1a0a2a", "panel_bg": "#0d0d1a",
        "toolbar_bg": "#1a0a2a", "breadcrumb_color": "#d400ff",
        "btn_colors": ["#a200ff", "#d400ff", "#ff00ff", "#ff44cc", "#fe019a", "#a200ff"],
        "page_title_color": "#e0b0ff", "log_bg": "#1a0a2a", "log_text": "#c0a0ff"
    },
    "赛博粉": {
        "bg": "#1a0a1a", "sidebar_bg": "#2a122a", "panel_bg": "#1d0d1d",
        "toolbar_bg": "#2a122a", "breadcrumb_color": "#ff69b4",
        "btn_colors": ["#ff44cc", "#ff69b4", "#ff1493", "#ff00ff", "#ff8c00", "#ff44cc"],
        "page_title_color": "#ffb0ff", "log_bg": "#2a122a", "log_text": "#ffb0ff"
    },
    "荧光蓝": {
        "bg": "#0a1a2a", "sidebar_bg": "#122a3a", "panel_bg": "#0d1d2d",
        "toolbar_bg": "#122a3a", "breadcrumb_color": "#00bfff",
        "btn_colors": ["#00f0ff", "#00bfff", "#1e90ff", "#00ced1", "#40e0d0", "#00f0ff"],
        "page_title_color": "#b0e0ff", "log_bg": "#122a3a", "log_text": "#b0e0ff"
    },
}

# ========== 粒子系统（不变） ==========
class ParticleOverlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.particles = []
        self.mouse_pos = QPoint(0, 0)
        self.mouse_inside = False
        self.current_style = "star"
        self.enabled = True
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_particles)

    def start_particles(self):
        if not self.timer.isActive():
            self.timer.start(16)

    def stop_particles(self):
        if self.timer.isActive():
            self.timer.stop()
        self.particles.clear()
        self.update()

    def set_enabled(self, enabled):
        self.enabled = enabled
        if not enabled:
            self.particles.clear()
            self.update()

    def set_particle_style(self, style):
        self.current_style = style
        self.particles.clear()

    def update_particles(self):
        if self.mouse_inside and self.enabled:
            for _ in range(3):
                hue = random.randint(0, 360)
                color = QColor()
                color.setHsv(hue, 200, 255)
                self.particles.append({
                    'x': self.mouse_pos.x(), 'y': self.mouse_pos.y(),
                    'vx': random.uniform(-1.5, 1.5),
                    'vy': random.uniform(0.5, 2.5),
                    'life': random.uniform(0.5, 1.0),
                    'max_life': 1.0,
                    'size': random.randint(3, 7),
                    'color': color,
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
            if self.current_style == "star":
                self.draw_star(painter, size, p['angle'])
            elif self.current_style == "heart":
                self.draw_heart(painter, size)
            elif self.current_style == "wing":
                self.draw_wing(painter, size, p['angle'])
            elif self.current_style == "diamond":
                self.draw_diamond(painter, size, p['angle'])
            painter.restore()

    def rotate_point(self, pt, angle_deg):
        x, y = pt
        rad = math.radians(angle_deg)
        return x * math.cos(rad) - y * math.sin(rad), x * math.sin(rad) + y * math.cos(rad)

    def draw_star(self, painter, size, angle):
        points = []
        for i in range(10):
            r = size if i % 2 == 0 else size * 0.4
            theta = math.radians(angle + i * 36)
            points.append((r * math.cos(theta), r * math.sin(theta)))
        painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in points]))

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
        path.moveTo(*wp(0, -s*0.3))
        path.quadTo(*wp(-s*0.6, -s*0.9), *wp(-s*0.9, -s*0.4))
        path.quadTo(*wp(-s*0.5, s*0.1), *wp(0, s*0.5))
        path.quadTo(*wp(s*0.5, s*0.1), *wp(s*0.9, -s*0.4))
        path.quadTo(*wp(s*0.6, -s*0.9), *wp(0, -s*0.3))
        painter.drawPath(path)

    def draw_diamond(self, painter, size, angle):
        pts = [(0, -size), (size*0.6, 0), (0, size), (-size*0.6, 0)]
        rotated = [self.rotate_point(p, angle) for p in pts]
        painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in rotated]))

# ========== 全局鼠标追踪 ==========
class GlobalMouseTracker(QObject):
    def __init__(self, overlay, main_window):
        super().__init__(main_window)
        self.overlay = overlay
        self.main_window = main_window

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseMove:
            local_pos = self.overlay.mapFromGlobal(QCursor.pos())
            self.overlay.mouse_pos = local_pos
            if not self.overlay.mouse_inside:
                self.overlay.mouse_inside = True
            return False
        elif event.type() == QEvent.Leave:
            if obj is self.main_window:
                self.overlay.mouse_inside = False
                self.overlay.particles.clear()
                self.overlay.update()
            return False
        return super().eventFilter(obj, event)

# ========== 按钮（移除弹性缩放，保留光圈） ==========
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

        # 弹性动画：只影响背景，不影响文字和光圈
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
        self.scale_anim.stop()
        self.scale_anim.start()

    def _update_style(self):
        color_name = self.neon_color.name()
        # 只保留基础样式，背景和文字的绘制我们手动控制
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {color_name};
                border: none;
                border-radius: 18px;
                font-size: 15px;
                font-weight: bold;
                font-family: "Microsoft YaHei";
                padding: 0px 12px;
            }}
            QPushButton:hover {{
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
            if not self.anim_timer.isActive():
                self.anim_timer.start()
        else:
            if self.anim_timer.isActive():
                self.anim_timer.stop()
        self.update()

    def _ripple_animate(self):
        self.ripple_radius += 4
        self.ripple_alpha -= 10
        if self.ripple_alpha <= 0:
            self.ripple_timer.stop()
        self.update()

    def _animate(self):
        self.offset += 0.02
        if self.offset >= 1.0: self.offset -= 1.0
        self.breathe_alpha += self.breathe_dir * 3
        if self.breathe_alpha >= 255:
            self.breathe_alpha = 255
            self.breathe_dir = -1
        elif self.breathe_alpha <= 80:
            self.breathe_alpha = 80
            self.breathe_dir = 1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. 绘制缩放背景（只缩放背景矩形，不动文字）
        painter.save()
        cx, cy = self.rect().center().x(), self.rect().center().y()
        painter.translate(cx, cy)
        painter.scale(self._scale_factor, self._scale_factor)
        painter.translate(-cx, -cy)

        # 绘制按钮圆角矩形背景（模拟QPushButton的背景，但可缩放）
        bg_rect = self.rect()
        # 根据hover状态选择颜色
        if self.underMouse():
            bg_color = self.neon_color
        else:
            bg_color = QColor("#1a1a2e")
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(bg_rect, 18, 18)
        painter.restore()

        # 2. 在原始坐标系绘制文字（不缩放）
        painter.setPen(QPen(self.neon_color))
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignCenter, self.text())

        # 3. 绘制跑马灯光圈（原始坐标系，不受缩放影响）
        if self._selected:
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

        # 4. 扩散光圈（原始坐标系）
        if self.ripple_alpha > 0:
            ripple_color = QColor(self.neon_color)
            ripple_color.setAlpha(self.ripple_alpha)
            painter.setPen(QPen(ripple_color, 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(self.rect().center(), self.ripple_radius, self.ripple_radius)

    def stop_all_timers(self):
        for t in [self.anim_timer, self.ripple_timer]:
            if t.isActive():
                t.stop()
        self.scale_anim.stop()

# ========== 网格背景 ==========
class GridPanel(QWidget):
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        pen = QPen(QColor(255,255,255,15))
        pen.setWidth(1)
        painter.setPen(pen)
        w, h = self.width(), self.height()
        step = 30
        for x in range(0, w, step):
            painter.drawLine(x, 0, x - h, h)
        for y in range(0, h, step):
            painter.drawLine(0, y, w, y - w)

# ========== 页面 ==========
class BasePage(QWidget):
    def __init__(self, title, color, bg_color, log_bg, log_text):
        super().__init__()
        self.setStyleSheet(f"background-color: {bg_color};")
        layout = QVBoxLayout()
        lbl = QLabel(title)
        lbl.setStyleSheet(f"color: {color}; font-size:22px; font-weight:bold;")
        layout.addWidget(lbl)
        log = QTextEdit()
        log.setReadOnly(True)
        log.setStyleSheet(f"background-color: {log_bg}; color: {log_text}; border:1px solid {color}; border-radius:8px;")
        layout.addWidget(log)
        self.setLayout(layout)

class FishingPage(BasePage):
    def __init__(self, theme): super().__init__("🎣 自动钓鱼", theme["page_title_color"], theme["panel_bg"], theme["log_bg"], theme["log_text"])
class MissionPage(BasePage):
    def __init__(self, theme): super().__init__("📋 自动任务", theme["page_title_color"], theme["panel_bg"], theme["log_bg"], theme["log_text"])
class CombatPage(BasePage):
    def __init__(self, theme): super().__init__("⚔️ 自动战斗", theme["page_title_color"], theme["panel_bg"], theme["log_bg"], theme["log_text"])
class ExchangePage(BasePage):
    def __init__(self, theme): super().__init__("💱 自动兑换", theme["page_title_color"], theme["panel_bg"], theme["log_bg"], theme["log_text"])
class PinkClawPage(BasePage):
    def __init__(self, theme): super().__init__("🦊 粉爪助手", theme["page_title_color"], theme["panel_bg"], theme["log_bg"], theme["log_text"])
class DrivingPage(BasePage):
    def __init__(self, theme): super().__init__("🚗 自动驾驶", theme["page_title_color"], theme["panel_bg"], theme["log_bg"], theme["log_text"])

# ========== 主窗口 ==========
class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.current_theme_name = config.get("theme", "默认")
        self.particles_enabled = config.get("particles_enabled", True)

        self.setWindowTitle("N.E.O.N. 控制台")
        self.resize(config.get("window_width", 1000), config.get("window_height", 600))
        self.init_ui()
        self.init_particles()
        self.mouse_tracker = GlobalMouseTracker(self.particle_overlay, self)
        QApplication.instance().installEventFilter(self.mouse_tracker)
        last_page = min(config.get("last_page", 0), len(self.pages)-1)
        self.switch_page(last_page)

    def init_ui(self):
        theme = THEMES[self.current_theme_name]
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)

        self.toolbar = QWidget()
        self.toolbar.setFixedHeight(40)
        self.toolbar.setStyleSheet(f"background-color: {theme['toolbar_bg']};")
        tlay = QHBoxLayout(self.toolbar)
        tlay.setContentsMargins(10,5,10,5)

        self.breadcrumb = QLabel(" // 正在航行: 钓鱼模块")
        self.breadcrumb.setStyleSheet(f"color: {theme['breadcrumb_color']}; font-size:14px;")
        tlay.addWidget(self.breadcrumb)
        tlay.addStretch()

        tlay.addWidget(QLabel("主题:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEMES.keys())
        self.theme_combo.setCurrentText(self.current_theme_name)
        self.theme_combo.currentTextChanged.connect(self.apply_theme)
        tlay.addWidget(self.theme_combo)

        tlay.addWidget(QLabel("粒子:"))
        self.particle_style_combo = QComboBox()
        self.particle_style_combo.addItems(["星星", "爱心", "小翅膀", "钻石"])
        self.particle_style_combo.currentTextChanged.connect(self.change_particle_style)
        tlay.addWidget(self.particle_style_combo)

        self.particle_checkbox = QCheckBox("鼠标特效")
        self.particle_checkbox.setChecked(self.particles_enabled)
        self.particle_checkbox.stateChanged.connect(self.toggle_particles)
        tlay.addWidget(self.particle_checkbox)

        main_layout.addWidget(self.toolbar)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0,0,0,0)
        content_layout.setSpacing(0)

        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(145)
        self.sidebar.setStyleSheet(f"background-color: {theme['sidebar_bg']}; border-right:2px solid #2a2a4a;")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setAlignment(Qt.AlignTop)
        sidebar_layout.setContentsMargins(10,20,10,20)
        sidebar_layout.setSpacing(12)

        self.stack = QStackedWidget()
        self.pages = [
            FishingPage(theme), MissionPage(theme), CombatPage(theme),
            ExchangePage(theme), PinkClawPage(theme), DrivingPage(theme)
        ]
        for p in self.pages:
            self.stack.addWidget(p)

        self.nav_btns = []
        texts = ["钓鱼", "任务", "战斗", "兑换", "粉爪", "驾驶"]
        btn_colors = theme["btn_colors"]
        for i, (text, color) in enumerate(zip(texts, btn_colors)):
            btn = NeonSelectButton(text, color)
            btn.clicked.connect(lambda _, idx=i: self.switch_page(idx))
            sidebar_layout.addWidget(btn)
            self.nav_btns.append(btn)

        for btn in self.nav_btns:
            btn.setChecked(False)

        content_layout.addWidget(self.sidebar)

        self.right_panel = GridPanel()
        self.right_panel.setStyleSheet(f"background-color: {theme['panel_bg']};")
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(20,15,20,15)
        right_layout.addWidget(self.stack, 1)
        content_layout.addWidget(self.right_panel)

        main_layout.addWidget(content, 1)

    def init_particles(self):
        self.particle_overlay = ParticleOverlay(self)
        self.particle_overlay.setEnabled(self.particles_enabled)
        self.particle_overlay.setGeometry(self.rect())
        self.particle_overlay.raise_()
        self.particle_overlay.start_particles()

    def change_particle_style(self, text):
        style_map = {"星星": "star", "爱心": "heart", "小翅膀": "wing", "钻石": "diamond"}
        self.particle_overlay.set_particle_style(style_map[text])

    def toggle_particles(self, state):
        enabled = (state == Qt.Checked)
        self.particles_enabled = enabled
        self.config["particles_enabled"] = enabled
        self.particle_overlay.set_enabled(enabled)

    def switch_page(self, index):
        for i, btn in enumerate(self.nav_btns):
            btn.setChecked(i == index)
        names = ["钓鱼", "任务", "战斗", "兑换", "粉爪", "驾驶"]
        self.breadcrumb.setText(f" // 正在航行: {names[index]}模块")
        self.stack.setCurrentIndex(index)
        self.config["last_page"] = index

    def apply_theme(self, theme_name):
        theme = THEMES[theme_name]
        self.current_theme_name = theme_name
        self.config["theme"] = theme_name
        self.toolbar.setStyleSheet(f"background-color: {theme['toolbar_bg']};")
        self.breadcrumb.setStyleSheet(f"color: {theme['breadcrumb_color']}; font-size:14px;")
        self.sidebar.setStyleSheet(f"background-color: {theme['sidebar_bg']}; border-right:2px solid #2a2a4a;")
        self.right_panel.setStyleSheet(f"background-color: {theme['panel_bg']};")
        colors = theme["btn_colors"]
        for i, btn in enumerate(self.nav_btns):
            btn.set_neon_color(colors[i % len(colors)])
        current_idx = self.stack.currentIndex()
        self.stack.blockSignals(True)
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()
        self.pages = [
            FishingPage(theme), MissionPage(theme), CombatPage(theme),
            ExchangePage(theme), PinkClawPage(theme), DrivingPage(theme)
        ]
        for p in self.pages:
            self.stack.addWidget(p)
        self.stack.setCurrentIndex(current_idx)
        self.stack.blockSignals(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'particle_overlay'):
            self.particle_overlay.setGeometry(self.rect())
        self.config["window_width"] = self.width()
        self.config["window_height"] = self.height()

    def closeEvent(self, event):
        save_config(self.config)
        self.particle_overlay.stop_particles()
        for btn in self.nav_btns:
            btn.stop_all_timers()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    cfg = load_config()
    win = MainWindow(cfg)
    win.show()
    sys.exit(app.exec_())