# ui/services/tray_icon.py
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon

class TrayIcon(QSystemTrayIcon):
    def __init__(self, main_window, app_icon_path):
        super().__init__(main_window)
        self.main_window = main_window
        self.setIcon(QIcon(app_icon_path))
        self.setToolTip("MintNTE")

        menu = QMenu()
        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self.show_main)
        menu.addAction(show_action)

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.exit_app)
        menu.addAction(exit_action)

        self.setContextMenu(menu)
        self.activated.connect(self.on_activated)

    def show_main(self):
        self.main_window.show()
        if self.main_window.isMinimized():
            self.main_window.showNormal()
        self.main_window.activateWindow()

    def exit_app(self):
        # 正确退出程序：停止热键，关闭所有窗口，退出 Qt 事件循环
        self.main_window.close_app()

    def on_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_main()