# ui/services/capture_config.py
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)

CAPTURE_MODE_FILE = os.path.join(CONFIG_DIR, "capture_mode.txt")
DETECT_MODE_FILE = os.path.join(CONFIG_DIR, "detect_mode.txt")

def load_config(file_path, default=0):
    try:
        with open(file_path, 'r') as f:
            return int(f.read().strip())
    except:
        return default

def save_config(file_path, value):
    try:
        with open(file_path, 'w') as f:
            f.write(str(value))
    except:
        pass

def get_capture_mode():
    return load_config(CAPTURE_MODE_FILE, 0)

def set_capture_mode(mode):
    save_config(CAPTURE_MODE_FILE, mode)

def get_detect_mode():
    return load_config(DETECT_MODE_FILE, 0)

def set_detect_mode(mode):
    save_config(DETECT_MODE_FILE, mode)