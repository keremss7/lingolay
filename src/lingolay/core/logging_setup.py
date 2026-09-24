import logging
import sys
from logging.handlers import RotatingFileHandler

_initialized = False


def init_logging(dev_mode=False):
    """
    Initialize application logging.
    - Always writes to logs/app.log (rotating, 5MB x 3 backups)
    - Also writes to stdout if dev_mode=True (LINGOLAY_DEV env var)
    """
    global _initialized
    if _initialized:
        return
    _initialized = True
    from lingolay.core.paths import LOG_FILE, LOGS_DIR
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    fmt = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG if dev_mode else logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)
    for noisy in ('PIL', 'urllib3', 'ctranslate2'):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name):
    return logging.getLogger(name)
