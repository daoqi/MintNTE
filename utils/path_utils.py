# utils/path_utils.py
import sys, os

def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        # 优先 exe 同级目录，其次 _internal
        for base in (os.path.dirname(sys.executable), sys._MEIPASS):
            p = os.path.join(base, relative_path)
            if os.path.exists(p):
                return p
        return os.path.join(os.path.dirname(sys.executable), relative_path)
    return os.path.join(os.path.abspath("."), relative_path)