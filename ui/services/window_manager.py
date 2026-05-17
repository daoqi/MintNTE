# ui/services/window_manager.py
"""
窗口管理器：负责在程序退出时关闭所有注册的子窗口，释放资源。
"""
import gc
from PyQt5.QtWidgets import QWidget


class WindowManager:
    def __init__(self):
        self._windows = []

    def register(self, window: QWidget):
        """注册一个子窗口，以便在程序退出时关闭"""
        if window is not None and window not in self._windows:
            self._windows.append(window)

    def unregister(self, window: QWidget):
        """取消注册（窗口手动关闭时调用）"""
        if window in self._windows:
            self._windows.remove(window)

    def close_all(self):
        """关闭所有注册的窗口并释放资源"""
        for win in self._windows[:]:
            try:
                if not win.isHidden():
                    win.close()
                win.deleteLater()
            except RuntimeError:
                pass
        self._windows.clear()
        gc.collect()


# 全局单例
_window_manager = WindowManager()


def get_window_manager():
    return _window_manager