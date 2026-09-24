"""
Tesseract OCR fallback — for systems without Windows OCR (Linux/macOS).
The Tesseract engine must be installed on the system:
  Windows: https://github.com/UB-Mannheim/tesseract/wiki
  macOS:   brew install tesseract
  Linux:   sudo apt install tesseract-ocr
"""
import logging
import time

from lingolay.ocr.base import OCREngine

logger = logging.getLogger(__name__)

try:
    import pytesseract
    _PYTESSERACT_AVAILABLE = True
except Exception:
    pytesseract = None
    _PYTESSERACT_AVAILABLE = False

# BCP-47 (Windows OCR style) → Tesseract language code
_LANG_MAP = {
    'en': 'eng', 'tr': 'tur', 'de': 'deu', 'fr': 'fra', 'es': 'spa', 'ru': 'rus',
    'ar': 'ara', 'zh': 'chi_sim', 'ja': 'jpn', 'ko': 'kor', 'pt': 'por', 'it': 'ita',
    'nl': 'nld', 'pl': 'pol', 'uk': 'ukr',
}


def _to_tesseract_lang(language):
    return _LANG_MAP.get((language or 'en').split('-')[0].lower(), 'eng')


class TesseractOCR(OCREngine):
    def __init__(self, language='en-US'):
        self._lang = _to_tesseract_lang(language)
        self._last_latency_ms = 0
        self._available = False
        if _PYTESSERACT_AVAILABLE:
            try:
                pytesseract.get_tesseract_version()
                self._available = True
            except Exception as e:
                logger.info('[Tesseract] Engine not found: %s', e)

    def get_name(self):
        return 'Tesseract OCR'

    def is_available(self):
        return self._available

    def set_language(self, language):
        self._lang = _to_tesseract_lang(language)

    def recognize(self, image):
        if not self._available:
            return ''
        start = time.perf_counter()
        try:
            import cv2
            rgb = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            text = pytesseract.image_to_string(rgb, lang=self._lang, config='--psm 6')
        except Exception as e:
            logger.warning('[Tesseract] Recognition error: %s', e)
            text = ''
        self._last_latency_ms = int((time.perf_counter() - start) * 1000)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return '\n'.join(lines)
