import asyncio
import logging
import threading
import time

import numpy as np

from lingolay.ocr.base import OCREngine

logger = logging.getLogger(__name__)

WINDOWS_OCR_AVAILABLE = False
WINDOWS_OCR_IMPORT_ERROR = ''
try:
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.media.ocr import OcrEngine as WinOcrEngine
    WINDOWS_OCR_AVAILABLE = True
except Exception as _e:  # non-Windows platform or missing winrt packages
    WINDOWS_OCR_IMPORT_ERROR = str(_e)

_ocr_loop = None
_ocr_thread = None
_ocr_lock = threading.Lock()


def _ensure_ocr_loop():
    """Ensure the OCR event loop is running in a background thread."""
    global _ocr_loop, _ocr_thread
    with _ocr_lock:
        if _ocr_loop is not None and _ocr_thread is not None and _ocr_thread.is_alive():
            return
        _ocr_loop = asyncio.new_event_loop()
        _ocr_thread = threading.Thread(target=_ocr_loop.run_forever, daemon=True, name='OCR-EventLoop')
        _ocr_thread.start()


def _run_async_in_loop(coro):
    """Run an async coroutine in the shared OCR loop."""
    _ensure_ocr_loop()
    future = asyncio.run_coroutine_threadsafe(coro, _ocr_loop)
    return future.result(timeout=5.0)


class WindowsOCR(OCREngine):
    """Built-in Windows 10/11 OCR engine (Windows.Media.Ocr)."""

    def __init__(self, language='en-US'):
        self._language = language
        self._engine = None
        self._last_latency_ms = 0
        if WINDOWS_OCR_AVAILABLE:
            self._init_engine()

    def _init_engine(self):
        try:
            lang = Language(self._language)
            if WinOcrEngine.is_language_supported(lang):
                self._engine = WinOcrEngine.try_create_from_language(lang)
                logger.info('[WinOCR] Initialized for language: %s', self._language)
            else:
                self._engine = WinOcrEngine.try_create_from_user_profile_languages()
                logger.warning("[WinOCR] Language '%s' not installed, using system default", self._language)
        except Exception as e:
            logger.error('[WinOCR] Initialization failed: %s', e)
            self._engine = None

    def get_name(self):
        return 'Windows OCR' if WINDOWS_OCR_AVAILABLE else 'Windows OCR (unavailable)'

    def is_available(self):
        return WINDOWS_OCR_AVAILABLE and self._engine is not None

    def set_language(self, language):
        self._language = language
        if WINDOWS_OCR_AVAILABLE:
            self._init_engine()

    def recognize(self, image):
        """Perform OCR on image. Returns recognized text or '' on failure."""
        if not self.is_available():
            return ''
        start = time.perf_counter()
        try:
            result = _run_async_in_loop(self._recognize_async(image))
        except Exception as e:
            logger.warning('[WinOCR] Recognition error: %s', e)
            result = ''
        self._last_latency_ms = int((time.perf_counter() - start) * 1000)
        return result

    async def _recognize_async(self, image):
        """Async OCR recognition using WinRT SoftwareBitmap."""
        import cv2
        height, width = image.shape[:2]
        if image.ndim == 2:
            bgra = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
        elif image.shape[2] == 3:
            bgra = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
        else:
            bgra = image
        if not bgra.flags['C_CONTIGUOUS']:
            bgra = np.ascontiguousarray(bgra)
        bitmap = SoftwareBitmap(BitmapPixelFormat.BGRA8, width, height, BitmapAlphaMode.PREMULTIPLIED)
        bitmap.copy_from_buffer(memoryview(bgra.tobytes()))
        ocr_result = await self._engine.recognize_async(bitmap)
        return '\n'.join(' '.join(w.text for w in line.words) for line in ocr_result.lines)

    @staticmethod
    def get_available_languages():
        """Get list of installed OCR languages."""
        if WINDOWS_OCR_AVAILABLE:
            try:
                return [lang.language_tag for lang in WinOcrEngine.available_recognizer_languages]
            except Exception:
                pass
        return ['en-US']
