# ui/pages.py
import threading, json, os, sys
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, QCheckBox,
    QGroupBox, QComboBox, QLineEdit, QRadioButton, QButtonGroup, QDialog, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence
from ui.services.icon_manager import set_message_box_icon
from Module.Hwnd.game_hwnd import get_game_hwnd

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_external_path(filename):
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, filename)

class BasePage(QWidget):
    def __init__(self, bg_color):
        super().__init__()
        self.setStyleSheet(f"background-color: {bg_color};")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

class SetupPage(BasePage):
    def __init__(self, theme):
        super().__init__(theme["panel_bg"])

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(10)
        scroll_layout.setContentsMargins(10, 10, 10, 10)

        try:
            from plugins.window_detect.window_detect_ui import WindowDetectUI
            detect_widget = WindowDetectUI()
            detect_widget.setMinimumHeight(500)
            scroll_layout.addWidget(detect_widget)
        except Exception as e:
            scroll_layout.addWidget(QLabel(f"⚠️ 窗口检测加载失败：{e}"))

        # 自动领取月卡
        monthly_group = QGroupBox("自动领取月卡")
        monthly_group.setStyleSheet("""
            QGroupBox {
                color: #00ffff;
                border: 1px solid #00ffff;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #00ffff;
            }
        """)
        monthly_layout = QVBoxLayout(monthly_group)
        self.cb_monthly = QCheckBox("自动领取月卡")
        self.cb_monthly.setStyleSheet("color: #00ffff; font-size: 14px;")
        self.cb_monthly.stateChanged.connect(self.on_monthly_toggled)
        monthly_layout.addWidget(self.cb_monthly)
        self.lbl_monthly_status = QLabel("")
        self.lbl_monthly_status.setStyleSheet("color: #888; font-size: 12px;")
        monthly_layout.addWidget(self.lbl_monthly_status)
        scroll_layout.addWidget(monthly_group)

        self.setup_shortcut_ui(scroll_layout)

        scroll.setWidget(scroll_content)
        self.layout.addWidget(scroll)

        self.monthly_stop_event = None
        self.monthly_thread = None

    def setup_shortcut_ui(self, parent_layout):
        group = QGroupBox("快捷键设置")
        group.setStyleSheet("""
            QGroupBox {
                color: #00ffff;
                border: 1px solid #00ffff;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #00ffff;
            }
        """)
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(10)

        title_row = QHBoxLayout()
        title_lbl = QLabel("快捷键设置")
        title_lbl.setStyleSheet("color: #00ffff; font-size: 16px; font-weight: bold;")
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        help_btn = QPushButton("?")
        help_btn.setFixedSize(24, 24)
        help_btn.setStyleSheet("""
            QPushButton { background-color: #00f0ff; color: #1e1e2f; border: 1px solid #00f0ff; border-radius: 12px; font-weight: bold; font-size: 14px; }
            QPushButton:hover { background-color: #00f0ff; color: #1e1e2f; }
        """)
        help_btn.setToolTip("点击查看快捷键使用帮助")
        help_btn.clicked.connect(self.open_shortcut_help)
        title_row.addWidget(help_btn)
        group_layout.addLayout(title_row)

        self.functions = ["fishing", "task", "macro", "fortissimo", "driving"]
        self.func_labels = {"fishing":"钓鱼", "task":"任务", "macro":"宏", "fortissimo":"超强音", "driving":"粉爪"}
        self.shortcut_buttons = {}
        self.scope_combos = {}
        self.status_labels = {}

        for func in self.functions:
            func_group = QGroupBox(self.func_labels[func])
            func_group.setStyleSheet("""
                QGroupBox {
                    color: #00ffff;
                    border: 1px solid #00ffff;
                    border-radius: 5px;
                    margin-top: 10px;
                    font-weight: bold;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                    color: #00ffff;
                }
            """)
            func_layout = QVBoxLayout(func_group)
            btn_row = QHBoxLayout()
            btn = QPushButton("未设置")
            btn.setFixedWidth(120)
            btn.setStyleSheet("""
                QPushButton { color: #00ffff; background-color: #2a2a3a; border: 1px solid #00ffff; border-radius: 4px; padding: 4px; font-size: 14px; }
                QPushButton:hover { background-color: #00ffff; color: #1e1e2f; }
            """)
            btn.clicked.connect(lambda checked, f=func: self.capture_shortcut(f))
            self.shortcut_buttons[func] = btn
            btn_row.addWidget(btn)

            combo = QComboBox()
            combo.addItems(["全局", "软件内"])
            combo.setStyleSheet("""
                QComboBox { color: #00ffff; background-color: #2a2a3a; border: 1px solid #00ffff; border-radius: 4px; padding: 4px; font-size: 14px; }
                QComboBox QAbstractItemView { color: #00ffff; background-color: #2a2a3a; selection-background-color: #00ffff; selection-color: #1e1e2f; }
            """)
            combo.currentIndexChanged.connect(lambda index, f=func: self.on_scope_changed(f, index))
            self.scope_combos[func] = combo
            btn_row.addWidget(combo)

            status_lbl = QLabel("⚪")
            status_lbl.setFixedWidth(20)
            status_lbl.setStyleSheet("color: #888; font-size: 14px;")
            btn_row.addWidget(status_lbl)
            self.status_labels[func] = status_lbl
            btn_row.addStretch()
            func_layout.addLayout(btn_row)
            group_layout.addWidget(func_group)

        self.load_shortcut_settings()
        parent_layout.addWidget(group)
        QTimer.singleShot(1000, self.update_shortcut_status)

    def open_shortcut_help(self):
        from PyQt5.QtGui import QDesktopServices
        from PyQt5.QtCore import QUrl
        help_path = resource_path("help/shortcut_help.html")
        if os.path.exists(help_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(help_path))
        else:
            QMessageBox.warning(self, "帮助", f"帮助文件未找到：{help_path}")

    def capture_shortcut(self, func):
        dialog = QDialog(self)
        dialog.setWindowTitle("按下快捷键")
        dialog.setFixedSize(350, 150)
        dialog.setStyleSheet("background-color: #1e1e2f; color: #00ffff;")
        layout = QVBoxLayout(dialog)
        hint_label = QLabel("请按下要设置的快捷键组合...\n(支持单独 F1-F12、字母、数字，或带修饰键)")
        hint_label.setStyleSheet("color: #00ffff; font-size: 13px;")
        layout.addWidget(hint_label)
        display_label = QLabel("当前按键：")
        display_label.setStyleSheet("color: #ffaa00; font-size: 16px; font-weight: bold;")
        layout.addWidget(display_label)

        captured_str = None
        def on_key_press(event):
            nonlocal captured_str
            key = event.key()
            mods = event.modifiers()
            if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
                return
            parts = []
            if mods & Qt.ControlModifier: parts.append("CTRL")
            if mods & Qt.AltModifier: parts.append("ALT")
            if mods & Qt.ShiftModifier: parts.append("SHIFT")
            key_name = QKeySequence(key).toString()
            if key_name: parts.append(key_name)
            current = "+".join(parts)
            display_label.setText(f"当前按键：{current}")
            captured_str = current
            if key == Qt.Key_Return or key == Qt.Key_Enter:
                dialog.accept()
        dialog.keyPressEvent = on_key_press

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确认")
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        if dialog.exec_() == QDialog.Accepted and captured_str:
            self.shortcut_buttons[func].setText(captured_str)
            self.save_shortcut_settings()

    def on_scope_changed(self, func, index):
        self.save_shortcut_settings()

    def load_shortcut_settings(self):
        config_path = get_external_path("config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except:
            cfg = {}
        shortcuts = cfg.get("shortcuts", {})
        defaults = {
            "fishing": ("F1", "全局"),
            "task": ("F2", "全局"),
            "macro": ("F3", "全局"),
            "fortissimo": ("F4", "全局"),
            "driving": ("F5", "全局")
        }
        for func in self.functions:
            info = shortcuts.get(func, defaults[func])
            key, scope = info
            self.shortcut_buttons[func].setText(key)
            self.scope_combos[func].setCurrentText(scope)

    def save_shortcut_settings(self):
        config_path = get_external_path("config.json")
        cfg = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except:
                pass

        new_shortcuts = {}
        for func in self.functions:
            key = self.shortcut_buttons[func].text()
            scope = self.scope_combos[func].currentText()
            new_shortcuts[func] = [key, scope]

        # 冲突检测：后者覆盖前者，清空旧功能
        key_to_func = {}
        for func in self.functions:
            key = new_shortcuts[func][0]
            if key and key != "未设置":
                key_to_func[key] = func

        for func in self.functions:
            key = new_shortcuts[func][0]
            if key and key != "未设置":
                if key_to_func.get(key) != func:
                    new_shortcuts[func] = ["未设置", "全局"]
                    self.shortcut_buttons[func].setText("未设置")
                    self.scope_combos[func].setCurrentText("全局")

        cfg["shortcuts"] = new_shortcuts
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)

        main_win = self.window()
        if main_win and hasattr(main_win, 'hotkey_mgr'):
            main_win.hotkey_mgr.clear_all()
            main_win.register_all_shortcuts()
            QTimer.singleShot(200, self.update_shortcut_status)

    def update_shortcut_status(self):
        main_win = self.window()
        if main_win and hasattr(main_win, 'hotkey_mgr'):
            for func in self.functions:
                ok = main_win.hotkey_mgr.is_registered(func)
                self.status_labels[func].setText("🟢" if ok else "🔴")
                self.status_labels[func].setStyleSheet("color: #00ff00;" if ok else "color: #ff0000;")

    def on_monthly_toggled(self, state):
        if state == Qt.Checked: self.start_monthly()
        else: self.stop_monthly()

    def start_monthly(self):
        hwnd = get_game_hwnd()
        if not hwnd:
            QMessageBox.warning(self, "提示", "未锁定游戏窗口，请先锁定窗口后再开启月卡领取。")
            self.cb_monthly.setChecked(False)
            return
        self.monthly_stop_event = threading.Event()
        from plugins.monthly.monthly_card import monthly_card_worker
        self.monthly_thread = threading.Thread(target=monthly_card_worker, args=(self.monthly_stop_event, get_game_hwnd), daemon=True)
        self.monthly_thread.start()
        self.lbl_monthly_status.setText("月卡领取中...")
        self.lbl_monthly_status.setStyleSheet("color: #00ff00; font-size: 12px;")

    def stop_monthly(self):
        if self.monthly_stop_event:
            self.monthly_stop_event.set()
        if self.monthly_thread and self.monthly_thread.is_alive():
            self.monthly_thread.join(timeout=1)
        self.lbl_monthly_status.setText("月卡领取已停止")
        self.lbl_monthly_status.setStyleSheet("color: #ff8800; font-size: 12px;")

    def closeEvent(self, event):
        self.stop_monthly()
        event.accept()

class FishingPage(BasePage):
    def __init__(self, theme):
        super().__init__(theme["panel_bg"])
        try:
            from plugins.fishing.FishingUI import FishingUI
            self.fishing_widget = FishingUI()
            self.layout.addWidget(self.fishing_widget)
        except Exception as e:
            import traceback
            QMessageBox.critical(self, "钓鱼模块加载失败", traceback.format_exc())
            self.layout.addWidget(QLabel(f"⚠️ 钓鱼模块加载失败：{e}"))

class MissionPage(BasePage):
    def __init__(self, theme):
        super().__init__(theme["panel_bg"])
        try:
            from plugins.task.TaskUI import TaskUI
            self.task_widget = TaskUI()
            self.layout.addWidget(self.task_widget)
        except Exception as e:
            import traceback
            QMessageBox.critical(self, "任务模块加载失败", traceback.format_exc())
            self.layout.addWidget(QLabel(f"⚠️ 任务模块加载失败：{e}"))

class CombatPage(BasePage):
    def __init__(self, theme):
        super().__init__(theme["panel_bg"])
        try:
            from plugins.Macro.macro_ui import MacroPanel
            self.macro_widget = MacroPanel()
            self.layout.addWidget(self.macro_widget)
        except Exception as e:
            self.layout.addWidget(QLabel(f"⚠️ 宏模块加载失败：{e}"))

class ExchangePage(BasePage):
    def __init__(self, theme):
        super().__init__(theme["panel_bg"])
        try:
            btn = QPushButton("🎵 打开超强音")
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: {theme['btn_colors'][5]}; color: white; border-radius: 8px; font-size: 16px; padding: 10px; }}
                QPushButton:hover {{ background-color: {theme['btn_colors'][4]}; }}
            """)
            def launch():
                try:
                    from plugins.Fortissimo.foreground.foreground_ui import ForegroundWindow
                    self.fort_win = ForegroundWindow(mode='foreground')
                    self.fort_win.show()
                except Exception as e2:
                    box = QMessageBox(QMessageBox.Critical, "错误", str(e2))
                    set_message_box_icon(box)
                    box.exec_()
            btn.clicked.connect(launch)
            self.layout.addWidget(btn, 0)
        except Exception as e:
            self.layout.addWidget(QLabel(f"⚠️ 超强音加载失败：{e}"))

class PinkClawPage(BasePage):
    def __init__(self, theme):
        super().__init__(theme["panel_bg"])
        try:
            from plugins.JoinUs.JoinUsUI import JoinUsUI
            self.join_widget = JoinUsUI()
            self.layout.addWidget(self.join_widget)
        except Exception as e:
            self.layout.addWidget(QLabel(f"⚠️ 加入我们加载失败：{e}"))

class DrivingPage(BasePage):
    def __init__(self, theme):
        super().__init__(theme["panel_bg"])
        self.layout.addWidget(QLabel("粉爪功能开发中..."))

class DarkRacingPage(BasePage):
    def __init__(self, theme):
        super().__init__(theme["panel_bg"])
        try:
            from plugins.dark_racing.dark_racing_ui import DarkRacingUI
            self.racing_widget = DarkRacingUI()
            self.layout.addWidget(self.racing_widget)
        except Exception as e:
            import traceback
            QMessageBox.critical(self, "黑暗赛车加载失败", traceback.format_exc())
            self.layout.addWidget(QLabel(f"⚠️ 黑暗赛车加载失败：{e}"))