# updater/updater.py
import os, sys, json, shutil, tempfile, zipfile, re
from pathlib import Path
from datetime import datetime
import requests
from PyQt5.QtCore import QObject, pyqtSignal, QThread
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

# ---------- 主程序更新线程 ----------
class CheckUpdateThread(QThread):
    result = pyqtSignal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancel = False

    def cancel(self):
        self._cancel = True
        self.wait(2000)

    def run(self):
        if self._cancel: return
        local = shell_version()
        try:
            req = requests.get(API_URL, headers={"User-Agent": "MintNTE"}, timeout=10, verify=False)
            req.raise_for_status()
            data = req.json()
            remote_tag = data["tag_name"].lstrip("v")
            needs = parse_version(remote_tag) > parse_version(local)
            self.result.emit(1 if needs else 0, remote_tag)
        except Exception as e:
            logger.error(f"检查主程序更新失败: {e}")
            self.result.emit(-1, str(e))

# ---------- 插件更新线程 ----------
class PluginCheckThread(QThread):
    result = pyqtSignal(dict)

    def run(self):
        try:
            req = requests.get(API_URL, headers={"User-Agent": "MintNTE"}, timeout=10, verify=False)
            req.raise_for_status()
            body = req.json().get("body", "")
            m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', body, re.DOTALL)
            if m:
                versions = json.loads(m.group(1))
            else:
                versions = {}
            self.result.emit(versions)
        except Exception as e:
            logger.error(f"检查插件更新失败: {e}")
            self.result.emit({})

class PluginDownloadThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, plugins: dict, parent=None):
        super().__init__(parent)
        self.plugins = plugins

    def run(self):
        root = _root()
        try:
            # 1. 获取 plugins.zip 下载链接
            req = requests.get(API_URL, headers={"User-Agent": "MintNTE"}, timeout=10, verify=False)
            req.raise_for_status()
            assets = req.json().get("assets", [])
            url = None
            for a in assets:
                if a["name"] == "plugins.zip":
                    url = a["browser_download_url"]
                    break
            if not url:
                self.finished.emit(False, "未找到 plugins.zip")
                return

            # 2. 下载
            self.progress.emit(10, "下载插件包...")
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
                        self.progress.emit(p, f"{downloaded//1024}KB / {total//1024}KB")
                tmpf.close()

            # 3. 解压
            self.progress.emit(40, "解压中...")
            tmpdir = tempfile.mkdtemp()
            with zipfile.ZipFile(tmpf.name, 'r') as zf:
                zf.extractall(tmpdir)
            os.unlink(tmpf.name)

            # 4. 备份并替换插件目录
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
            self.progress.emit(100, "完成")
            self.finished.emit(True, "插件更新成功，请重启程序")
        except Exception as e:
            logger.error(f"插件更新失败: {e}")
            self.finished.emit(False, str(e))

# ---------- 统一 Updater ----------
class Updater(QObject):
    checkResult = pyqtSignal(int, str)          # 主程序更新结果
    pluginCheckResult = pyqtSignal(dict)        # 远程插件版本
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    pluginProgress = pyqtSignal(int, str)       # 下载进度
    pluginFinished = pyqtSignal(bool, str)      # 下载完成

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shell_thread = None
        self._plugin_thread = None
        self._download_thread = None
        self._remote_versions = {}

    def cancel(self):
        for t in [self._shell_thread, self._plugin_thread, self._download_thread]:
            if t and t.isRunning():
                t.terminate()
                t.wait(2000)

    def get_local_version(self):
        return shell_version()

    def check_for_update(self):               # 主程序更新
        if self._shell_thread and self._shell_thread.isRunning():
            return
        self._shell_thread = CheckUpdateThread(self)
        self._shell_thread.result.connect(self.checkResult)
        self._shell_thread.start()

    def check_plugin_updates(self):           # 插件更新检查
        if self._plugin_thread and self._plugin_thread.isRunning():
            return
        self._plugin_thread = PluginCheckThread(self)
        self._plugin_thread.result.connect(self._on_plugin_versions)
        self._plugin_thread.start()

    def _on_plugin_versions(self, versions):
        self._remote_versions = versions
        self.pluginCheckResult.emit(versions)

    def download_plugin_updates(self, names: list):
        if self._download_thread and self._download_thread.isRunning():
            return
        targets = {n: self._remote_versions.get(n, "0.0.0") for n in names}
        self._download_thread = PluginDownloadThread(targets, self)
        self._download_thread.progress.connect(self.pluginProgress)
        self._download_thread.finished.connect(self.pluginFinished)
        self._download_thread.start()

    def perform_update(self):
        pass

    def skip_this_version(self, version):
        pass