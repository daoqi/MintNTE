# ui/services/logui.py
import logging
from logging.handlers import TimedRotatingFileHandler
import sys

_logger = None
_log_file = "MintNTE.log"

def setup_logging(log_file="MintNTE.log", console_level=logging.INFO, file_level=logging.DEBUG):
    global _logger, _log_file
    if _logger is not None:
        return _logger
    _log_file = log_file
    logger = logging.getLogger("MintNTE")
    logger.setLevel(logging.DEBUG)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(console_level)
    console_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
    console.setFormatter(console_format)
    logger.addHandler(console)

    file_handler = TimedRotatingFileHandler(
        log_file, when='midnight', interval=1, backupCount=7, encoding='utf-8'
    )
    file_handler.setLevel(file_level)
    file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    _logger = logger
    return logger

def get_logger():
    if _logger is None:
        setup_logging()
    return _logger

def get_log_file():
    return _log_file

def info(msg):   get_logger().info(msg)
def error(msg):  get_logger().error(msg)
def warning(msg): get_logger().warning(msg)
def debug(msg):  get_logger().debug(msg)
def critical(msg): get_logger().critical(msg)