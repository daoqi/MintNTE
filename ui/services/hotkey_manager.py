# ui/services/hotkey_manager.py
import keyboard
import re
import time
from PyQt5.QtCore import QObject, pyqtSignal
from ui.services.logui import get_logger

logger = get_logger()

class HotkeyManager(QObject):
    hotkey_triggered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._registered = {}        # name -> shortcut_str
        self._last_trigger = {}      # name -> timestamp (防抖)

    @staticmethod
    def is_valid_shortcut(shortcut_str):
        if not shortcut_str or shortcut_str == "未设置":
            return False
        parts = shortcut_str.upper().split('+')
        has_key = False
        for part in parts:
            part = part.strip()
            if part in ('CTRL', 'CONTROL', 'ALT', 'SHIFT'):
                continue
            if re.match(r'F(1[0-9]|2[0-4]|[1-9])$', part):
                has_key = True
                break
            if len(part) == 1:
                has_key = True
                break
        return has_key

    @staticmethod
    def _normalize(shortcut_str):
        """将用户输入的快捷键转换为 keyboard 库能识别的格式 (小写)"""
        parts = shortcut_str.strip().split('+')
        normalized = []
        for p in parts:
            p = p.strip().lower()
            if p in ('ctrl', 'control'):
                normalized.append('ctrl')
            elif p == 'alt':
                normalized.append('alt')
            elif p == 'shift':
                normalized.append('shift')
            else:
                normalized.append(p)   # 功能键 f1, f2 或单字母
        return '+'.join(normalized)

    def register_hotkey(self, name, shortcut_str, callback=None):
        if name in self._registered:
            self.unregister_hotkey(name)
        if not self.is_valid_shortcut(shortcut_str):
            logger.warning(f"快捷键无效: {shortcut_str}")
            return False
        try:
            hotkey = self._normalize(shortcut_str)
            keyboard.add_hotkey(hotkey, lambda n=name: self._on_trigger(n), suppress=False)
            self._registered[name] = shortcut_str
            logger.info(f"已注册热键: {name} -> {hotkey}")
            return True
        except Exception as e:
            logger.error(f"注册热键失败: {shortcut_str} ({e})")
            return False

    def unregister_hotkey(self, name):
        if name in self._registered:
            shortcut_str = self._registered.pop(name)
            try:
                keyboard.remove_hotkey(shortcut_str)
                logger.info(f"已注销热键: {name}")
            except:
                pass

    def clear_all(self):
        for name in list(self._registered.keys()):
            self.unregister_hotkey(name)

    def is_registered(self, name):
        return name in self._registered

    def stop_hook(self):
        self.clear_all()

    def _on_trigger(self, name):
        """防抖：3 秒内重复触发忽略"""
        now = time.time()
        if name in self._last_trigger and now - self._last_trigger[name] < 3.0:
            return
        self._last_trigger[name] = now
        logger.info(f"热键按下: {name}")
        self.hotkey_triggered.emit(name)