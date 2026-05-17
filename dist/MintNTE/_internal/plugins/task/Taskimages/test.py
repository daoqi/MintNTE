# ui/main_window.py
import json, os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QTimer

from ui.theme import THEMES
from ui.services.logui import get_logger, get_log_file
from ui.services.logViewerUI import LogViewer
from ui.controls.button import NeonSelectButton
from ui.pages import SetupPage, FishingPage, MissionPage, CombatPage, ExchangePage, PinkClawPage, DrivingPage
from ui.services.window_manager import get_window_manager
from ui.services.autostart import is_auto_start_enabled, set_auto_start
from ui.services.tray_icon import TrayIcon
from ui.services.icon_manager import setup_main_window_icon

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
logger = get_logger()


class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.current_theme_name = config.get("theme", "默认")
        self.log_window = None
        self.win_manager = get_window_manager()
        self.setWindowTitle("MintNTE")
        self.resize(config.get("window_width", 1000), config.get("window_height", 600))

        # ===== 最简化测试：注释所有可能崩溃的初始化代码 =====
        # setup_main_window_icon(self)  # 注释

        self.tray_enabled = config.get("tray_enabled", True)

        self.init_ui()

        # last_page = min(config.get("last_page", 0), 6)
        # self.switch_page(last_page)

        # 托盘图标
        # try:
        #     icon_path = os.path.join(BASE_DIR, "Image", "logo", "titlelogo.ico")
        #     if os.path.exists(icon_path):
        #         self.tray_icon = TrayIcon(self, icon_path)
        #         self.tray_icon.show()
        #     else:
        #         logger.warning("托盘图标文件未找到，托盘功能不可用")
        #         self.tray_icon = None
        # except Exception as e:
        #     logger.error(f"托盘初始化失败: {e}")
        #     self.tray_icon = None

        # if is_auto_start_enabled() and self.tray_icon:
        #     QTimer.singleShot(200, self.hide)

        # 启动 Web 面板
        # if self.config.get("web_enabled", False):
        #     import threading
        #     from plugins.fishing.web_panel import run_server
        #     web_port = self.config.get("web_port", 5050)
        #     web_thread = threading.Thread(target=run_server, args=(web_port,), daemon=True)
        #     web_thread.start()
        #     logger.info(f"Web 面板已启动，端口 {web_port}")

        # 更新器
        # self.updater = Updater(parent=self)
        # self.updater.checkResult.connect(self.on_check_result)
        # self.updater.progress.connect(self.update_progress.setValue)
        # self.updater.status.connect(self.update_status.setText)
        # self.updater.pluginCheckResult.connect(self.on_plugin_check_result)
        # self.updater.pluginProgress.connect(self.on_plugin_progress)
        # self.updater.pluginFinished.connect(self.on_plugin_finished)

        # logger.info("主窗口初始化完成")

    def init_ui(self):
        # ===== 最简化 UI：只显示一个标签 =====
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.addWidget(QLabel("简化 UI 测试"))

    # 以下方法保留原样，但测试时不会被调用，所以不影响测试
    def toggle_autostart(self, state):
        enabled = (state == Qt.Checked)
        set_auto_start(enabled)
        logger.info(f"开机自启 {'开启' if enabled else '关闭'}")

    def toggle_tray_mode(self, state):
        self.tray_enabled = (state == Qt.Checked)
        self.config["tray_enabled"] = self.tray_enabled
        logger.info(f"关闭到托盘 {'开启' if self.tray_enabled else '关闭'}")

    def toggle_log_window(self, state):
        if state == Qt.Checked:
            if self.log_window is None:
                log_file = get_log_file()
                self.log_window = LogViewer(log_file=log_file)
                self.log_window.setAttribute(Qt.WA_DeleteOnClose, False)
                self.win_manager.register(self.log_window)
            self.log_window.show()
        else:
            if self.log_window:
                self.log_window.hide()

    def switch_page(self, index):
        pass

    def apply_theme(self, theme_name):
        pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.config["window_width"] = self.width()
        self.config["window_height"] = self.height()

    def log_performance(self):
        pass

    def close_app(self):
        try:
            if hasattr(self, 'tray_icon') and self.tray_icon is not None:
                self.tray_icon.hide()
                self.tray_icon = None
            if hasattr(self, 'win_manager'):
                self.win_manager.close_all()
            try:
                with open("config.json", "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=4, ensure_ascii=False)
            except Exception as e:
                logger.error(f"配置保存失败: {e}")
        except Exception as e:
            logger.error(f"退出清理过程出错: {e}")
        finally:
            QApplication.quit()

    def closeEvent(self, event):
        if self.tray_enabled:
            self.hide()
            event.ignore()
        else:
            self.close_app()
            event.accept()

    # 以下方法暂时保留为空，避免引用错误
    def on_check_result(self, status, info):
        pass

    def on_plugin_check_result(self, versions):
        pass

    def on_plugin_progress(self, percent, msg):
        pass

    def on_plugin_finished(self, success, msg):
        pass