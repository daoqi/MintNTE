# main.py
import sys, os, ctypes, json, traceback
from utils.path_utils import resource_path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# ---------- Python 自身提权（无需 Launcher.exe）----------
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

if not is_admin():
    python_exe = sys.executable
    params = " ".join([f'"{a}"' if ' ' in a else a for a in sys.argv])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", python_exe, params, None, 1)
    sys.exit(0)
# ------------------------------------------------------------

def play_startup_music():
    music_path = resource_path("Image/logo/boheai.mp3")
    if os.path.exists(music_path):
        ctypes.windll.winmm.mciSendStringW(f'open "{music_path}" type mpegvideo alias startup_music', None, 0, None)
        ctypes.windll.winmm.mciSendStringW("play startup_music", None, 0, None)

from PyQt5.QtWidgets import QApplication, QMessageBox
from ui.main_window import MainWindow
from ui.services.logui import get_logger
from ui.services.icon_manager import set_app_icon

logger = get_logger()
logger.info("=" * 60)
logger.info("📋 日志策略：本文件每天午夜自动切片，最多保留最近 7 天的日志，旧日志将自动删除。")
logger.info("=" * 60)

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {
        "theme": "赛博粉",
        "window_width": 1000,
        "window_height": 600,
        "last_page": 0,
    }

if __name__ == "__main__":
    try:
        play_startup_music()
        app = QApplication(sys.argv)
        app.setStyleSheet("""
            QMessageBox { background-color: #1e1e2f; color: #00f0ff; }
            QMessageBox QLabel { color: #00f0ff; font-size: 14px; }
            QMessageBox QPushButton { background-color: #3a3a5a; color: #00f0ff; border: 1px solid #00f0ff; padding: 5px 15px; border-radius: 4px; min-width: 60px; }
            QMessageBox QPushButton:hover { background-color: #5a5a7a; }
            QToolTip { font-size: 14px; background-color: #1e1e2f; color: #00f0ff; border: 1px solid #00f0ff; padding: 4px; }
        """)
        set_app_icon(app)
        cfg = load_config()
        win = MainWindow(cfg)
        win.show()
        logger.info("程序启动完成")
        sys.exit(app.exec_())
    except Exception as e:
        error_msg = ''.join(traceback.format_exception(None, e, e.__traceback__))
        logger.critical(f"程序崩溃:\n{error_msg}")
        try:
            app = QApplication(sys.argv) if not QApplication.instance() else QApplication.instance()
            QMessageBox.critical(None, "错误", f"程序发生致命错误，请将日志文件 MintNTE.log 发送给开发者。\n\n{str(e)}")
        except:
            pass
        sys.exit(1)