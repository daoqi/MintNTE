# plugins/fishing/FishingUI.py
import sys, os, threading, time, webbrowser
from utils.path_utils import resource_path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QDoubleSpinBox, QGroupBox, QMessageBox, QComboBox,
    QScrollArea, QRadioButton, QCheckBox, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QIcon

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from Module.Hwnd.game_hwnd import get_game_hwnd
from plugins.fishing.fishing_core import FishingCore
from plugins.fishing.auto_sell_fish import sell_fish
from plugins.fishing.auto_buy_bait import (
    enter_tackle_shop, buy_bait_core, exit_tackle_shop, change_bait
)
import ui.services.logui as logui

ICON_PATH = resource_path("Image/logo/titlelogo.ico")
HELP_HTML = resource_path("help/fishing_help.html")
MANUAL_HELP_HTML = resource_path("help/manual_help.html")

class FishingUI(QWidget):
    update_stats_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fishing_stop_event = None
        self.fishing_thread = None
        self.follower = None
        self.fishing_core = None

        self.fish_mode = 0
        self.enable_smart_trade = True
        self.shutdown_after_hours = 666.0
        self.bait_low_action = 0
        self.cabin_full_action = 0

        self.manual_thread = None
        self.manual_stop = False

        self.setup_ui()
        self.update_stats_signal.connect(self.on_fish_grade)

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_stats_display)
        self.update_timer.start(1000)

    def _msg_box(self, icon, title, text):
        box = QMessageBox(icon, title, text, parent=self)
        if os.path.exists(ICON_PATH):
            box.setWindowIcon(QIcon(ICON_PATH))
        return box

    def _help_button_style(self):
        return """
            QPushButton {
                background-color: #00f0ff;
                color: #1e1e2f;
                border: 1px solid #00f0ff;
                border-radius: 12px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #00f0ff;
                color: #1e1e2f;
            }
        """

    def open_help(self):
        if os.path.exists(HELP_HTML):
            webbrowser.open(f"file:///{HELP_HTML}")
        else:
            QMessageBox.warning(self, "帮助", f"帮助文件未找到：{HELP_HTML}")

    def open_manual_help(self):
        if os.path.exists(MANUAL_HELP_HTML):
            webbrowser.open(f"file:///{MANUAL_HELP_HTML}")
        else:
            QMessageBox.warning(self, "帮助", f"帮助文件未找到：{MANUAL_HELP_HTML}")

    def setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        main_widget = QWidget()
        scroll.setWidget(main_widget)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)

        layout = QVBoxLayout(main_widget)
        layout.setSpacing(10)

        # ========== 鱼获统计 ==========
        stats_group = QGroupBox("鱼获统计")
        stats_group.setObjectName("NeonGroup")
        stats_layout = QHBoxLayout(stats_group)
        self.label_a = QLabel("A级鱼类: 0")
        self.label_b = QLabel("B级鱼类: 0")
        self.label_s = QLabel("S级鱼类: 0")
        self.label_total = QLabel("总钓鱼数: 0")
        for lbl in (self.label_a, self.label_b, self.label_s, self.label_total):
            lbl.setObjectName("StatLabel")
            lbl.setAlignment(Qt.AlignCenter)
            stats_layout.addWidget(lbl)
        layout.addWidget(stats_group)

        # ========== 状态行（状态+统计+按钮） ==========
        status_row = QHBoxLayout()
        self.status_label = QLabel("当前状态：待机")
        self.status_label.setStyleSheet("color: #00ff00; font-size: 14px; font-weight: bold;")
        status_row.addWidget(self.status_label)

        self.stats_detail_label = QLabel("抛竿:0  逃走:0  买饵:0  卖鱼:0")
        self.stats_detail_label.setStyleSheet("color: #ffaa00; font-size: 13px;")
        status_row.addWidget(self.stats_detail_label)

        status_row.addStretch()

        self.btn_start = QPushButton("开始钓鱼")
        self.btn_start.setObjectName("BigStartButton")
        self.btn_start.clicked.connect(self.start_fishing)
        status_row.addWidget(self.btn_start)

        self.btn_stop = QPushButton("停止钓鱼")
        self.btn_stop.setObjectName("BigStopButton")
        self.btn_stop.clicked.connect(self.stop_fishing)
        self.btn_stop.setEnabled(False)
        status_row.addWidget(self.btn_stop)

        layout.addLayout(status_row)

        # ========== 超时设置 ==========
        hbox_timeout = QHBoxLayout()
        hbox_timeout.addWidget(QLabel("钓鱼心跳(秒):"))
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(1, 120)
        self.spin_timeout.setValue(60)
        hbox_timeout.addWidget(self.spin_timeout)
        hbox_timeout.addStretch()
        layout.addLayout(hbox_timeout)

        # ========== 钓鱼模式 ==========
        hbox_mode = QHBoxLayout()
        hbox_mode.addWidget(QLabel("钓鱼模式:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItem("ROI钓鱼")
        self.combo_mode.addItem("A_I钓鱼")
        self.combo_mode.addItem("AI训练中 (待更新)")
        self.combo_mode.currentIndexChanged.connect(self.on_mode_changed)
        hbox_mode.addWidget(self.combo_mode)
        hbox_mode.addStretch()
        layout.addLayout(hbox_mode)

        # ========== 【一】智能模式 ==========
        group1 = QGroupBox("【一】智能模式")
        v1 = QVBoxLayout(group1)
        h1 = QHBoxLayout()

        self.cb_smart_trade = QCheckBox("智能买卖鱼饵")
        self.cb_smart_trade.setChecked(True)
        self.cb_smart_trade.stateChanged.connect(self.on_smart_trade_changed)
        h1.addWidget(self.cb_smart_trade)

        help1 = QPushButton("?")
        help1.setFixedSize(24, 24)
        help1.setToolTip("一直钓鱼不关机,有电有网,鱼饵不足会自动购买鱼饵,鱼舱满了自动卖鱼")
        help1.setStyleSheet(self._help_button_style())
        help1.clicked.connect(self.open_help)
        h1.addWidget(help1)
        h1.addStretch()
        v1.addLayout(h1)

        h1_shutdown = QHBoxLayout()
        self.cb_shutdown = QCheckBox("钓鱼")
        self.cb_shutdown.setChecked(True)
        self.cb_shutdown.stateChanged.connect(self.on_shutdown_check)
        h1_shutdown.addWidget(self.cb_shutdown)

        self.spin_hours = QDoubleSpinBox()
        self.spin_hours.setRange(0.1, 99999.0)
        self.spin_hours.setValue(66.0)
        self.spin_hours.setSingleStep(1.0)
        self.spin_hours.setDecimals(1)
        self.spin_hours.valueChanged.connect(self.on_shutdown_hours_changed)
        h1_shutdown.addWidget(self.spin_hours)
        h1_shutdown.addWidget(QLabel("小时后关机"))
        h1_shutdown.addStretch()
        v1.addLayout(h1_shutdown)

        layout.addWidget(group1)

        # ========== 【二】鱼饵不足时 ==========
        group2 = QGroupBox("【二】鱼饵不足时")
        v2 = QVBoxLayout(group2)
        h2_row = QHBoxLayout()
        self.radio_bait_shutdown = QRadioButton("关机")
        self.radio_bait_shutdown.setChecked(True)
        h2_row.addWidget(self.radio_bait_shutdown)

        self.radio_bait_continue = QRadioButton("购买鱼饵继续钓鱼")
        h2_row.addWidget(self.radio_bait_continue)

        help2 = QPushButton("?")
        help2.setFixedSize(24, 24)
        help2.setToolTip("会清理鱼舱,只有鱼饵不足时才会关机")
        help2.setStyleSheet(self._help_button_style())
        help2.clicked.connect(self.open_help)
        h2_row.addWidget(help2)
        h2_row.addStretch()
        v2.addLayout(h2_row)
        layout.addWidget(group2)

        # ========== 【三】鱼舱满仓时 ==========
        group3 = QGroupBox("【三】鱼舱满仓时")
        v3 = QVBoxLayout(group3)
        h3_row = QHBoxLayout()
        self.radio_cabin_shutdown = QRadioButton("关机")
        self.radio_cabin_shutdown.setChecked(True)
        h3_row.addWidget(self.radio_cabin_shutdown)

        self.radio_cabin_continue = QRadioButton("清空鱼舱继续钓鱼")
        h3_row.addWidget(self.radio_cabin_continue)

        help3 = QPushButton("?")
        help3.setFixedSize(24, 24)
        help3.setToolTip("会自动购买鱼饵.只有鱼舱满了才会关机")
        help3.setStyleSheet(self._help_button_style())
        help3.clicked.connect(self.open_help)
        h3_row.addWidget(help3)
        h3_row.addStretch()
        v3.addLayout(h3_row)
        layout.addWidget(group3)

        # ========== 手动操作区域 ==========
        manual_group = QGroupBox("手动操作")
        manual_layout = QVBoxLayout(manual_group)

        manual_row = QHBoxLayout()
        manual_row.addWidget(QLabel("购买鱼饵次数:"))
        self.spin_buy_count = QSpinBox()
        self.spin_buy_count.setRange(1, 999)
        self.spin_buy_count.setValue(20)
        manual_row.addWidget(self.spin_buy_count)

        btn_buy = QPushButton("开始购买")
        btn_buy.setStyleSheet("QPushButton { background-color: #00f0ff; color: #1e1e2f; font-weight: bold; border-radius: 4px; padding: 6px; }")
        btn_buy.clicked.connect(self.manual_buy_bait)
        manual_row.addWidget(btn_buy)

        btn_sell = QPushButton("卖鱼")
        btn_sell.setFixedWidth(60)
        btn_sell.setStyleSheet("QPushButton { background-color: #00f0ff; color: #1e1e2f; font-weight: bold; border-radius: 4px; padding: 6px; }")
        btn_sell.clicked.connect(self.manual_sell_fish)
        manual_row.addWidget(btn_sell)

        btn_stop_manual = QPushButton("停止")
        btn_stop_manual.setFixedWidth(60)
        btn_stop_manual.setStyleSheet("QPushButton { background-color: #ff4444; color: white; font-weight: bold; border-radius: 4px; padding: 6px; }")
        btn_stop_manual.clicked.connect(self.stop_manual)
        manual_row.addWidget(btn_stop_manual)

        manual_help_btn = QPushButton("?")
        manual_help_btn.setFixedSize(24, 24)
        manual_help_btn.setToolTip("手动模式需要在钓鱼界面启动")
        manual_help_btn.setStyleSheet(self._help_button_style())
        manual_help_btn.clicked.connect(self.open_manual_help)
        manual_row.addWidget(manual_help_btn)

        manual_row.addStretch()
        manual_layout.addLayout(manual_row)

        self.manual_progress = QProgressBar()
        self.manual_progress.setVisible(False)
        manual_layout.addWidget(self.manual_progress)

        layout.addWidget(manual_group)

        self.on_smart_trade_changed(Qt.Checked)

        self.setStyleSheet("""
        #NeonGroup { border: 1px solid #f0f; border-radius:5px; margin-top:10px; }
        #NeonGroup::title { color: #f0f; }
        #StatLabel { color: #0ff; font-size:16px; font-weight:bold; }
        #BigStartButton {
            background-color:#2a2a3a; color:#0f0; border:2px solid #0f0;
            border-radius:8px; padding:8px 20px; font-size:14px; font-weight:bold;
        }
        #BigStartButton:hover { background-color:#0f0; color:#1e1e2f; }
        #BigStopButton {
            background-color:#2a2a3a; color:#f00; border:2px solid #f00;
            border-radius:8px; padding:8px 20px; font-size:14px; font-weight:bold;
        }
        #BigStopButton:hover { background-color:#f00; color:#1e1e2f; }
        QLabel { color:#0ff; font-size:14px; }
        QRadioButton { color:#0ff; }
        QCheckBox { color:#0ff; }
        QDoubleSpinBox, QSpinBox, QComboBox {
            background-color:#2a2a3a; color:#0ff; border:1px solid #0ff;
            border-radius:4px; padding:4px; font-size:14px;
        }
        QGroupBox { color:#0ff; border:1px solid #0ff; border-radius:5px; margin-top:10px; }
        QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 5px; }
        QProgressBar {
            background-color:#2a2a3a; color:#0ff; border:1px solid #0ff;
            border-radius:4px; text-align:center;
        }
        QProgressBar::chunk { background-color:#0ff; }
        """)

    # ---------- 公开的启停接口 ----------
    def toggle_fishing(self):
        if self.fishing_thread and self.fishing_thread.is_alive():
            self.stop_fishing()
        else:
            self.start_fishing()

    # ---------- 槽函数 ----------
    def on_mode_changed(self, idx):
        self.fish_mode = idx

    def on_smart_trade_changed(self, state):
        self.enable_smart_trade = (state == Qt.Checked)
        self.radio_bait_shutdown.setEnabled(not self.enable_smart_trade)
        self.radio_bait_continue.setEnabled(not self.enable_smart_trade)
        self.radio_cabin_shutdown.setEnabled(not self.enable_smart_trade)
        self.radio_cabin_continue.setEnabled(not self.enable_smart_trade)

    def on_shutdown_check(self, state):
        self.spin_hours.setEnabled(state == Qt.Checked)

    def on_shutdown_hours_changed(self, value):
        if value == 0.0:
            QMessageBox.warning(self, "警告", "最低值不能低于 0")
            self.spin_hours.setValue(0.1)

    def get_options(self):
        bait_action = 1 if self.enable_smart_trade else (1 if self.radio_bait_continue.isChecked() else 0)
        cabin_action = 1 if self.enable_smart_trade else (1 if self.radio_cabin_continue.isChecked() else 0)
        shutdown_hours = self.spin_hours.value() if self.cb_shutdown.isChecked() else 0
        return {
            "fish_mode": self.fish_mode,
            "enable_smart_trade": self.enable_smart_trade,
            "shutdown_hours": shutdown_hours,
            "bait_low_action": bait_action,
            "cabin_full_action": cabin_action,
        }

    def start_fishing(self):
        hwnd = get_game_hwnd()
        if not hwnd:
            self._msg_box(QMessageBox.Warning, "错误", "未找到游戏窗口，请先锁定窗口。").exec_()
            return
        self.fishing_stop_event = threading.Event()
        timeout = self.spin_timeout.value()
        options = self.get_options()
        self.fishing_core = FishingCore(hwnd, self.fishing_stop_event,
                                        timeout=timeout,
                                        options=options,
                                        stats_callback=lambda grade: self.update_stats_signal.emit(grade))
        self.fishing_thread = threading.Thread(target=self.fishing_core.run, daemon=True)
        self.fishing_thread.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        logui.info("钓鱼已开始")

    def stop_fishing(self):
        if self.fishing_stop_event:
            self.fishing_stop_event.set()
        if self.fishing_thread and self.fishing_thread.is_alive():
            self.fishing_thread.join(timeout=2)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        logui.info("钓鱼已停止")

    def update_stats_display(self):
        if self.fishing_core:
            self.status_label.setText("当前状态：钓鱼中..." if self.fishing_thread and self.fishing_thread.is_alive() else "当前状态：待机")
            self.stats_detail_label.setText(
                f"抛竿:{self.fishing_core.throw_count}  逃走:{self.fishing_core.escape_count}  "
                f"买饵:{self.fishing_core.buy_bait_count}  卖鱼:{self.fishing_core.sell_fish_count}"
            )
            self.label_a.setText(f"A级鱼类: {self.fishing_core.fish_count_a}")
            self.label_b.setText(f"B级鱼类: {self.fishing_core.fish_count_b}")
            self.label_s.setText(f"S级鱼类: {self.fishing_core.fish_count_s}")
            self.label_total.setText(f"总钓鱼数: {self.fishing_core.fish_count}")

    # ---------- 手动卖鱼 ----------
    def manual_sell_fish(self):
        hwnd = get_game_hwnd()
        if not hwnd:
            self._msg_box(QMessageBox.Warning, "错误", "未找到游戏窗口，请先锁定窗口。").exec_()
            return
        self.manual_stop = False
        self.manual_progress.setVisible(True)
        self.manual_progress.setValue(0)
        self.manual_thread = threading.Thread(target=self._run_sell, args=(hwnd,), daemon=True)
        self.manual_thread.start()

    def _run_sell(self, hwnd):
        try:
            self._set_status("手动卖鱼中...")
            sell_fish(hwnd)
            self._set_status("卖鱼完成")
            QTimer.singleShot(0, lambda: self.manual_progress.setVisible(False))
            if self.fishing_core:
                self.fishing_core.sell_fish_count += 1
        except Exception as e:
            logui.error(f"手动卖鱼失败: {e}")
            self._set_status("卖鱼失败")

    # ---------- 手动购买鱼饵 ----------
    def manual_buy_bait(self):
        hwnd = get_game_hwnd()
        if not hwnd:
            self._msg_box(QMessageBox.Warning, "错误", "未找到游戏窗口，请先锁定窗口。").exec_()
            return
        count = self.spin_buy_count.value()
        self.manual_stop = False
        self.manual_progress.setVisible(True)
        self.manual_progress.setMaximum(count)
        self.manual_progress.setValue(0)
        self.manual_thread = threading.Thread(target=self._run_buy_bait, args=(hwnd, count), daemon=True)
        self.manual_thread.start()

    def _run_buy_bait(self, hwnd, count):
        try:
            if not enter_tackle_shop():
                self._set_status("进入渔具商店失败")
                QTimer.singleShot(0, lambda: self.manual_progress.setVisible(False))
                return
            for i in range(count):
                if self.manual_stop:
                    break
                self._set_status(f"购买鱼饵 {i+1}/{count}")
                buy_bait_core()
                if self.fishing_core:
                    self.fishing_core.buy_bait_count += 1
                QTimer.singleShot(0, lambda val=i+1: self.manual_progress.setValue(val))
            exit_tackle_shop()
            change_bait()
            self._set_status("购买鱼饵完成")
            QTimer.singleShot(0, lambda: self.manual_progress.setVisible(False))
        except Exception as e:
            logui.error(f"手动购买鱼饵失败: {e}")
            self._set_status("购买鱼饵失败")

    def stop_manual(self):
        self.manual_stop = True
        self._set_status("已停止手动操作")

    def _set_status(self, text):
        QTimer.singleShot(0, lambda: self.status_label.setText(text))

    def on_fish_grade(self, grade):
        if grade == 'A':
            self._add_count(self.label_a)
        elif grade == 'B':
            self._add_count(self.label_b)
        elif grade == 'S':
            self._add_count(self.label_s)
        if grade in ('A', 'B', 'S', 'unknown'):
            self._add_count(self.label_total)

    def _add_count(self, label):
        text = label.text()
        try:
            prefix, num = text.rsplit(':', 1)
            new_num = int(num.strip()) + 1
            label.setText(f"{prefix}: {new_num}")
        except:
            pass

    def closeEvent(self, event):
        self.manual_stop = True
        self.stop_fishing()
        event.accept()