"""
Minimal UI translation (i18n) layer.

Source strings are English. Each language has a `locales/<code>.json` file
mapping {"English text": "Translation"}. Missing keys fall back to English.

Adding a UI language:
  1. Copy locales/tr.json to locales/<code>.json
  2. Translate the values and set "_meta.name" to the language's own name
  3. Open a pull request — no code changes needed.

Usage:  from lingolay.i18n import t
           t('Start')  /  t('Region selected: {w}×{h} px', w=640, h=120)
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

LOCALES_DIR = Path(__file__).parent / 'locales'
DEFAULT_LANGUAGE = 'en'

_current = DEFAULT_LANGUAGE
_catalog = {}


def available_languages():
    """{code: native name} — English is always available."""
    langs = {'en': 'English'}
    for f in sorted(LOCALES_DIR.glob('*.json')):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            langs[f.stem] = data.get('_meta.name', f.stem)
        except (OSError, ValueError):
            continue
    return langs


def detect_system_language():
    try:
        from PySide6.QtCore import QLocale
        code = QLocale.system().name().split('_')[0].lower()
    except Exception:
        code = DEFAULT_LANGUAGE
    return code if code in available_languages() else DEFAULT_LANGUAGE


def set_language(code):
    """Set the UI language ('' → system language)."""
    global _current, _catalog
    code = code or detect_system_language()
    _catalog = {}
    if code != DEFAULT_LANGUAGE:
        path = LOCALES_DIR / f'{code}.json'
        try:
            _catalog = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as e:
            logger.warning('[i18n] Could not load %s (%s) — falling back to English', path.name, e)
            code = DEFAULT_LANGUAGE
    _current = code
    logger.info('[i18n] UI language: %s', _current)


def current_language():
    return _current


def t(text, **kwargs):
    """Translate text into the current UI language and fill in {name} placeholders."""
    out = _catalog.get(text) or text
    if kwargs:
        try:
            return out.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text.format(**kwargs)
    return out
