import json, os, sys, logging
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence, QPixmap
from utils.path_utils import resource_path

from ui.theme import THEMES
from ui.services.logui import get_logger, get_log_file
from ui.services.logViewerUI import LogViewer
from ui.controls.button import NeonSelectButton
from ui.pages import SetupPage, FishingPage, MissionPage, CombatPage, ExchangePage, PinkClawPage, DrivingPage
from ui.services.window_manager import get_window_manager
from ui.services.autostart import is_auto_start_enabled, set_auto_start
from ui.services.tray_icon import TrayIcon
from ui.services.icon_manager import setup_main_window_icon
from updater.updater import Updater, parse_version
from ui.services.hotkey_manager import HotkeyManager

logger = get_logger()

class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.current_theme_name = config.get("theme", "默认")
        self.log_window = None
        self.win_manager = get_window_manager()
        self.setWindowTitle("MintNTE-薄荷AI.异环最好用的AI,解放方双手")
        self.resize(config.get("window_width", 1000), config.get("window_height", 600))

        setup_main_window_icon(self)
        self.tray_enabled = config.get("tray_enabled", True)

        self.init_ui()
        last_page = min(config.get("last_page", 0), 6)
        self.switch_page(last_page)

        icon_path = resource_path("Image/logo/titlelogo.ico")
        if os.path.exists(icon_path):
            self.tray_icon = TrayIcon(self, icon_path)
            self.tray_icon.show()
        else:
            logger.warning("托盘图标文件未找到，托盘功能不可用")
            self.tray_icon = None

        if is_auto_start_enabled() and self.tray_icon:
            QTimer.singleShot(200, self.hide)

        self.updater = Updater(parent=self)
        self.updater.checkResult.connect(self.on_check_result)
        self.updater.progress.connect(self.update_progress.setValue)
        self.updater.status.connect(self.update_status.setText)
        self.updater.pluginCheckResult.connect(self.on_plugin_check_result)
        self.updater.pluginProgress.connect(self.on_plugin_progress)
        self.updater.pluginFinished.connect(self.on_plugin_finished)
        QTimer.singleShot(2000, self.updater.check_plugin_updates)

        self.hotkey_mgr = HotkeyManager(self)
        self.hotkey_mgr.hotkey_triggered.connect(self._on_hotkey_triggered)
        self.register_all_shortcuts()

        # 启动图片：右侧原图悬浮，5秒消失
        self.startup_label = QLabel()
        self.startup_label.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.startup_label.setAttribute(Qt.WA_TranslucentBackground)
        logo_path = resource_path("Image/logo/boheAI.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            self.startup_label.setPixmap(pixmap)
            self.startup_label.adjustSize()
            def show_logo():
                if self.isVisible():
                    geo = self.geometry()
                    self.startup_label.move(geo.right(), geo.top())
                    self.startup_label.show()
            QTimer.singleShot(200, show_logo)
            QTimer.singleShot(10000, self.startup_label.hide)
        else:
            logger.warning(f"启动图片不存在: {logo_path}")

        logger.info("主窗口初始化完成")

    def register_all_shortcuts(self):
        shortcuts_cfg = self.config.get("shortcuts", {})
        defaults = {
            "fishing":    None,
            "task":       None,
            "macro":      None,
            "fortissimo": None,
            "driving":    None,
        }
        callbacks = {
            "fishing":    self.toggle_fishing,
            "task":       self.toggle_task,
            "macro":      self.toggle_macro,
            "fortissimo": self.toggle_fortissimo,
            "driving":    self.toggle_driving,
        }
        for func, cb in callbacks.items():
            sc_info = shortcuts_cfg.get(func)
            if isinstance(sc_info, list) and len(sc_info) >= 1:
                key = sc_info[0]
                if key == "未设置" or not key:
                    logger.info(f"功能 {func} 未设置快捷键，跳过注册")
                    continue
            else:
                key = defaults.get(func)
                if not key:
                    logger.info(f"功能 {func} 未设置快捷键，跳过注册")
                    continue
            if not HotkeyManager.is_valid_shortcut(key):
                logger.warning(f"功能 {func} 的快捷键无效: {key}，跳过注册")
                continue
            if not self.hotkey_mgr.register_hotkey(func, key, cb):
                logger.warning(f"注册快捷键失败: {func} -> {key}")

    def _on_hotkey_triggered(self, name):
        logger.info(f"热键触发: {name}")
        callbacks = {
            "fishing":    self.toggle_fishing,
            "task":       self.toggle_task,
            "macro":      self.toggle_macro,
            "fortissimo": self.toggle_fortissimo,
            "driving":    self.toggle_driving,
        }
        cb = callbacks.get(name)
        if cb: cb()

    def toggle_fishing(self):
        page = self.pages[1]
        if hasattr(page, 'fishing_widget'): page.fishing_widget.toggle_fishing()

    def toggle_task(self):
        page = self.pages[2]
        if hasattr(page, 'task_widget'): page.task_widget.toggle_task()

    def toggle_macro(self):
        page = self.pages[3]
        if hasattr(page, 'macro_widget'): page.macro_widget.toggle_run()

    def toggle_fortissimo(self):
        self._launch_fortissimo('foreground')

    def toggle_driving(self): pass

    def init_ui(self):
        theme = THEMES[self.current_theme_name]
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.toolbar = QWidget()
        self.toolbar.setFixedHeight(40)
        self.toolbar.setStyleSheet(f"background-color: {theme['toolbar_bg']}; color: #cccccc;")
        tlay = QHBoxLayout(self.toolbar)
        tlay.setContentsMargins(10, 5, 10, 5)
        self.breadcrumb = QLabel("  当前: 启动设置")
        self.breadcrumb.setStyleSheet(f"color: {theme['breadcrumb_color']}; font-size:14px;")
        tlay.addWidget(self.breadcrumb)
        tlay.addStretch()

        def add_label(text):
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #cccccc;")
            tlay.addWidget(lbl)

        add_label("主题:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEMES.keys())
        self.theme_combo.setCurrentText(self.current_theme_name)
        self.theme_combo.currentTextChanged.connect(self.apply_theme)
        tlay.addWidget(self.theme_combo)

        self.autostart_checkbox = QCheckBox("开机自启")
        self.autostart_checkbox.setChecked(is_auto_start_enabled())
        self.autostart_checkbox.stateChanged.connect(self.toggle_autostart)
        self.autostart_checkbox.setStyleSheet("color: #cccccc;")
        tlay.addWidget(self.autostart_checkbox)

        self.tray_checkbox = QCheckBox("关闭到托盘")
        self.tray_checkbox.setChecked(self.tray_enabled)
        self.tray_checkbox.stateChanged.connect(self.toggle_tray_mode)
        self.tray_checkbox.setStyleSheet("color: #cccccc;")
        tlay.addWidget(self.tray_checkbox)

        self.log_checkbox = QCheckBox("运行日志")
        self.log_checkbox.setChecked(False)
        self.log_checkbox.setStyleSheet("color: #cccccc;")
        self.log_checkbox.stateChanged.connect(self.toggle_log_window)
        tlay.addWidget(self.log_checkbox)

        self.plugin_check_btn = QPushButton("检查插件更新")
        self.plugin_check_btn.clicked.connect(self.check_plugin_update)
        self.plugin_check_btn.setStyleSheet("color: #cccccc; background-color: #2a2a4a; border: 1px solid #00ffff; padding: 3px 8px;")
        tlay.addWidget(self.plugin_check_btn)

        main_layout.addWidget(self.toolbar)

        self.update_status = QLabel("")
        self.update_status.setStyleSheet("color:#00ffff; font-size:12px;")
        self.update_status.setVisible(False)
        self.update_progress = QProgressBar()
        self.update_progress.setMaximum(100)
        self.update_progress.setVisible(False)
        main_layout.addWidget(self.update_status)
        main_layout.addWidget(self.update_progress)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(145)
        self.sidebar.setStyleSheet(f"background-color: {theme['sidebar_bg']}; border-right:2px solid #2a2a4a;")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setAlignment(Qt.AlignTop)
        sidebar_layout.setContentsMargins(10, 20, 10, 20)
        sidebar_layout.setSpacing(12)

        self.stack = QStackedWidget()
        self.pages = [
            SetupPage(theme),
            FishingPage(theme),
            MissionPage(theme),
            CombatPage(theme),
            ExchangePage(theme),
            PinkClawPage(theme),
            DrivingPage(theme),
        ]
        for p in self.pages:
            self.stack.addWidget(p)

        self.nav_btns = []
        texts = ["启动", "钓鱼", "任务", "宏", "超强音", "粉爪", "加入我们"]
        btn_colors = theme["btn_colors"]
        for i, (text, color) in enumerate(zip(texts, btn_colors)):
            btn = NeonSelectButton(text, color)
            btn.clicked.connect(lambda _, idx=i: self.switch_page(idx))
            sidebar_layout.addWidget(btn)
            self.nav_btns.append(btn)

        for btn in self.nav_btns:
            btn.setChecked(False)

        content_layout.addWidget(self.sidebar)

        self.right_panel = QWidget()
        self.right_panel.setStyleSheet(f"background-color: {theme['panel_bg']};")
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(20, 15, 20, 15)
        right_layout.addWidget(self.stack, 1)
        content_layout.addWidget(self.right_panel)
        main_layout.addWidget(content, 1)

        from PyQt5.QtWidgets import QShortcut
        page_keys = [("1", 0), ("2", 1), ("3", 2), ("4", 3), ("5", 4)]
        for key, idx in page_keys:
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(lambda i=idx: self.switch_page(i))

    def toggle_log_window(self, state):
        if state == Qt.Checked:
            if self.log_window is None:
                log_file = get_log_file()
                self.log_window = LogViewer(log_file=log_file)
                self.log_window.setAttribute(Qt.WA_DeleteOnClose, False)
                self.win_manager.register(self.log_window)
            self.log_window.show()
            main_geo = self.geometry()
            log_geo = self.log_window.frameGeometry()
            x = main_geo.left() - log_geo.width()
            if x < 0: x = 0
            y = main_geo.top()
            self.log_window.move(x, y)
        else:
            if self.log_window:
                self.log_window.hide()

    def toggle_autostart(self, state):
        enabled = (state == Qt.Checked)
        set_auto_start(enabled)
        logger.info(f"开机自启 {'开启' if enabled else '关闭'}")

    def toggle_tray_mode(self, state):
        self.tray_enabled = (state == Qt.Checked)
        self.config["tray_enabled"] = self.tray_enabled
        logger.info(f"关闭到托盘 {'开启' if self.tray_enabled else '关闭'}")
        if not self.tray_enabled and self.tray_icon:
            self.tray_icon.hide()
            self.tray_icon.deleteLater()
            self.tray_icon = None

    def switch_page(self, index):
        for i, btn in enumerate(self.nav_btns):
            btn.setChecked(i == index)
        names = ["启动设置", "钓鱼", "任务", "宏", "超强音", "粉爪", "加入我们"]
        self.breadcrumb.setText(f" 当前: {names[index]}")
        self.stack.setCurrentIndex(index)
        self.config["last_page"] = index

    def apply_theme(self, theme_name):
        theme = THEMES[theme_name]
        self.current_theme_name = theme_name
        self.config["theme"] = theme_name
        self.toolbar.setStyleSheet(f"background-color: {theme['toolbar_bg']}; color: #cccccc;")
        self.breadcrumb.setStyleSheet(f"color: {theme['breadcrumb_color']}; font-size:14px;")
        self.sidebar.setStyleSheet(f"background-color: {theme['sidebar_bg']}; border-right:2px solid #2a2a4a;")
        self.right_panel.setStyleSheet(f"background-color: {theme['panel_bg']};")
        for i, btn in enumerate(self.nav_btns):
            btn.set_neon_color(theme["btn_colors"][i % len(theme["btn_colors"])])
        current_idx = self.stack.currentIndex()
        self.stack.blockSignals(True)
        while self.stack.count():
            self.stack.removeWidget(self.stack.widget(0))
        self.pages = [
            SetupPage(theme),
            FishingPage(theme),
            MissionPage(theme),
            CombatPage(theme),
            ExchangePage(theme),
            PinkClawPage(theme),
            DrivingPage(theme),
        ]
        for p in self.pages:
            self.stack.addWidget(p)
        self.stack.setCurrentIndex(current_idx)
        self.stack.blockSignals(False)

    def check_plugin_update(self):
        logger.info("手动点击了“检查插件更新”按钮")
        self.update_status.setText("正在检查插件更新...")
        self.update_status.setVisible(True)
        try:
            self.updater.check_plugin_updates()
        except Exception as e:
            logger.error(f"启动检查失败: {e}")

    def on_plugin_check_result(self, versions):
        if not versions:
            self.update_status.setText("检查完成，当前已是最新版本")
            QTimer.singleShot(3000, lambda: self.update_status.setVisible(False))
            return
        local_vers = {}
        plugins_root = resource_path("plugins")
        if os.path.exists(plugins_root):
            for d in os.listdir(plugins_root):
                info_path = os.path.join(plugins_root, d, "plugin_info.json")
                if os.path.isfile(info_path):
                    with open(info_path, encoding='utf-8') as f:
                        info = json.load(f)
                    local_vers[info['name']] = info.get('version', '0.0.0')
        need_update = []
        for name, remote_ver in versions.items():
            local_ver = local_vers.get(name, "0.0.0")
            if parse_version(remote_ver) > parse_version(local_ver):
                need_update.append(name)
        if need_update:
            reply = QMessageBox.question(self, "插件更新", f"发现可更新插件: {', '.join(need_update)}，是否下载？")
            if reply == QMessageBox.Yes:
                self.updater.download_plugin_updates(need_update)
        else:
            self.update_status.setText("所有插件已是最新")
            QTimer.singleShot(3000, lambda: self.update_status.setVisible(False))

    def on_plugin_progress(self, percent, msg):
        self.update_status.setVisible(True)
        self.update_progress.setVisible(True)
        self.update_status.setText(msg)
        self.update_progress.setValue(percent)

    def on_plugin_finished(self, success, msg):
        self.update_status.setVisible(False)
        self.update_progress.setVisible(False)
        if success:
            QMessageBox.information(self, "插件更新", msg)
        else:
            QMessageBox.warning(self, "插件更新失败", msg)

    def on_check_result(self, status, info):
        if status == -1:
            QMessageBox.warning(self, "检查更新失败", f"无法获取更新信息：\n{info}")
        elif status == 1:
            local = self.updater.get_local_version()
            QMessageBox.information(self, "发现新版本", f"当前版本: {local}\n最新版本: {info}\n请手动下载更新")
        else:
            QMessageBox.information(self, "检查更新", "当前已是最新版本。")

    def _launch_fortissimo(self, mode):
        try:
            if mode == 'foreground':
                from plugins.Fortissimo.foreground.foreground_ui import ForegroundWindow
                self.fort_win = ForegroundWindow(mode='foreground')
            else:
                from plugins.Fortissimo.background.background_ui import BackgroundWindow
                self.fort_win = BackgroundWindow()
            self.fort_win.show()
        except Exception as e:
            QMessageBox.critical(self, "启动失败", f"无法启动超强音模块：{str(e)}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.config["window_width"] = self.width()
        self.config["window_height"] = self.height()

    def close_app(self):
        try:
            self.hotkey_mgr.stop_hook()
        except:
            pass
        try:
            if hasattr(self, 'tray_icon') and self.tray_icon is not None:
                self.tray_icon.hide()
                self.tray_icon.deleteLater()
                self.tray_icon = None
        except:
            pass
        try:
            if hasattr(self, 'win_manager'):
                self.win_manager.close_all()
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"退出清理过程出错: {e}")
        finally:
            logging.shutdown()
            QApplication.quit()

    def closeEvent(self, event):
        if self.tray_enabled:
            self.hide()
            event.ignore()
        else:
            self.close_app()
            event.accept()