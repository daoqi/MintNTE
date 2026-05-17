import logging
from PyQt5.QtCore import QObject, pyqtSignal

LOG_FILE = "neon_console.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class QTextEditHandler(logging.Handler, QObject):
    new_log = pyqtSignal(str)
    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    def emit(self, record):
        self.new_log.emit(self.format(record))