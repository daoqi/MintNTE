# updater/updater.py
import os, sys, json, shutil, tempfile, zipfile, re, threading
from pathlib import Path
from datetime import datetime
import requests
from PyQt5.QtCore import QObject, pyqtSignal
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from ui.services.logger import logger

GITHUB_REPO = "daoqi/MintNTE"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
PLUGINS_DIR = "plugins"

def _root():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).resolve().parents[2]

def shell_version():
    vf = _root() / "version.txt"
    return vf.read_text(encoding='utf-8').strip() if vf.exists() else "0.0.0"

def parse_version(v: str):
    try:
        return tuple(map(int, v.split('.')))
    except:
        return (0,0,0)

# ---------- 主程序更新线程（保留 QThread 以保持兼容，但也可改为原生线程）----------
class CheckUpdateThread(threading.Thread):
    def __init__(self, callback, parent=None):
        super().__init__(daemon=True)
        self._callback = callback
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        if self._cancel: return
        local = shell_version()
        try:
            req = requests.get(API_URL, headers={"User-Agent": "MintNTE"}, timeout=10, verify=False)
            req.raise_for_status()
            data = req.json()
            remote_tag = data["tag_name"].lstrip("v")
            needs = parse_version(remote_tag) > parse_version(local)
            self._callback(1 if needs else 0, remote_tag)
        except Exception as e:
            logger.error(f"检查主程序更新失败: {e}")
            self._callback(-1, str(e))

# ---------- 插件更新线程（改为 Python 原生线程，避免 QThread 冲突）----------
class PluginCheckThread(threading.Thread):
    def __init__(self, callback, parent=None):
        super().__init__(daemon=True)
        self._callback = callback

    def run(self):
        try:
            req = requests.get(API_URL, headers={"User-Agent": "MintNTE"}, timeout=10, verify=False)
            req.raise_for_status()
            body = req.json().get("body", "")
            if not body:
                self._callback({})
                return

            # 优先匹配代码块（```json 或 ```）
            m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', body, re.DOTALL)
            if m:
                json_str = m.group(1)
            else:
                json_str = body.strip()

            try:
                versions = json.loads(json_str)
            except Exception:
                logger.error(f"解析 JSON 失败: {body}")
                self._callback({})
                return

            logger.info(f"解析到的远程插件版本: {versions}")
            self._callback(versions)
        except Exception as e:
            logger.error(f"检查插件更新失败: {e}")
            self._callback({})

class PluginDownloadThread(threading.Thread):
    def __init__(self, plugins, progress_cb, finish_cb, parent=None):
        super().__init__(daemon=True)
        self.plugins = plugins
        self._progress_cb = progress_cb
        self._finish_cb = finish_cb

    def run(self):
        root = _root()
        try:
            req = requests.get(API_URL, headers={"User-Agent": "MintNTE"}, timeout=10, verify=False)
            req.raise_for_status()
            assets = req.json().get("assets", [])
            url = None
            for a in assets:
                if a["name"] == "plugins.zip":
                    url = a["browser_download_url"]
                    break
            if not url:
                self._finish_cb(False, "未找到 plugins.zip")
                return

            self._progress_cb(10, "下载插件包...")
            with requests.get(url, stream=True, headers={"User-Agent": "MintNTE"}, verify=False) as r:
                r.raise_for_status()
                total = int(r.headers.get('content-length', 0))
                tmpf = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
                downloaded = 0
                for chunk in r.iter_content(8192):
                    tmpf.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        p = 10 + int(downloaded / total * 30)
                        self._progress_cb(p, f"{downloaded//1024}KB / {total//1024}KB")
                tmpf.close()

            self._progress_cb(40, "解压中...")
            tmpdir = tempfile.mkdtemp()
            with zipfile.ZipFile(tmpf.name, 'r') as zf:
                zf.extractall(tmpdir)
            os.unlink(tmpf.name)

            plugins_root = root / PLUGINS_DIR
            backup_root = root / "plugins_backup" / datetime.now().strftime("%Y%m%d_%H%M%S")
            for pname in self.plugins:
                src = Path(tmpdir) / PLUGINS_DIR / pname
                dst = plugins_root / pname
                if not src.exists():
                    logger.warning(f"插件 {pname} 不在压缩包中")
                    continue
                if dst.exists():
                    backup_dst = backup_root / pname
                    backup_dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(dst, backup_dst, dirs_exist_ok=True)
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                logger.info(f"插件 {pname} 已更新")

            shutil.rmtree(tmpdir)
            self._progress_cb(100, "完成")
            self._finish_cb(True, "插件更新成功，请重启程序")
        except Exception as e:
            logger.error(f"插件更新失败: {e}")
            self._finish_cb(False, str(e))

# ---------- 统一 Updater ----------
class Updater(QObject):
    checkResult = pyqtSignal(int, str)
    pluginCheckResult = pyqtSignal(dict)
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    pluginProgress = pyqtSignal(int, str)
    pluginFinished = pyqtSignal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shell_thread = None
        self._plugin_thread = None
        self._download_thread = None
        self._remote_versions = {}

    def cancel(self):
        if self._shell_thread and self._shell_thread.is_alive():
            self._shell_thread.cancel()
        if self._plugin_thread and self._plugin_thread.is_alive():
            # 无法直接取消，但线程会在下次循环检查
            pass
        if self._download_thread and self._download_thread.is_alive():
            pass

    def get_local_version(self):
        return shell_version()

    def check_for_update(self):
        if self._shell_thread and self._shell_thread.is_alive():
            return
        self._shell_thread = CheckUpdateThread(
            lambda status, info: self.checkResult.emit(status, info)
        )
        self._shell_thread.start()

    def check_plugin_updates(self):
        if self._plugin_thread and self._plugin_thread.is_alive():
            return
        self._plugin_thread = PluginCheckThread(
            lambda versions: self._on_plugin_versions(versions)
        )
        self._plugin_thread.start()

    def _on_plugin_versions(self, versions):
        self._remote_versions = versions
        self.pluginCheckResult.emit(versions)

    def download_plugin_updates(self, names: list):
        if self._download_thread and self._download_thread.is_alive():
            return
        targets = {n: self._remote_versions.get(n, "0.0.0") for n in names}
        self._download_thread = PluginDownloadThread(
            targets,
            lambda p, msg: self.pluginProgress.emit(p, msg),
            lambda success, msg: self.pluginFinished.emit(success, msg)
        )
        self._download_thread.start()

    def perform_update(self):
        pass

    def skip_this_version(self, version):
        pass