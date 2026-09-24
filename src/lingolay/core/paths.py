import os
import sys
from pathlib import Path


def _default_data_dir():
    """Per-platform user data directory. Override with LINGOLAY_HOME (portable mode)."""
    override = os.environ.get('LINGOLAY_HOME')
    if override:
        return Path(override)
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
    return base / 'Lingolay'


APP_DATA_DIR = _default_data_dir()
CONFIG_DIR = APP_DATA_DIR / 'config'
MODELS_DIR = APP_DATA_DIR / 'models'
VOICES_DIR = APP_DATA_DIR / 'voices'
CACHE_DIR = APP_DATA_DIR / 'cache'
LOGS_DIR = APP_DATA_DIR / 'logs'
PROFILES_DIR = APP_DATA_DIR / 'profiles'
SETTINGS_FILE = CONFIG_DIR / 'settings.json'
LOG_FILE = LOGS_DIR / 'app.log'


def models_dir(model_id):
    """Return the install directory for a specific model."""
    return MODELS_DIR / model_id


def ensure_dirs():
    """Create all required data directories on first run."""
    for d in (CONFIG_DIR, MODELS_DIR, VOICES_DIR, CACHE_DIR, LOGS_DIR, PROFILES_DIR):
        d.mkdir(parents=True, exist_ok=True)
