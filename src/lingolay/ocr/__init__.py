import logging

from lingolay.ocr.base import FallbackOCR, OCREngine

logger = logging.getLogger(__name__)

__all__ = ['OCREngine', 'FallbackOCR', 'create_ocr_engine']


def create_ocr_engine(language):
    """
    Factory: return the best available OCR engine.
      1. Windows OCR (WinRT) — built into Windows 10/11, fast, free
      2. Tesseract — other platforms, or when WinRT is unavailable
      3. FallbackOCR — when nothing is available (returns empty text, the app keeps running)
    """
    from lingolay.ocr.windows_ocr import WindowsOCR
    engine = WindowsOCR(language)
    if engine.is_available():
        logger.info('[OCR] Windows OCR ready (language: %s)', language)
        return engine

    from lingolay.ocr.tesseract_ocr import TesseractOCR
    engine = TesseractOCR(language)
    if engine.is_available():
        logger.info('[OCR] Tesseract ready (language: %s)', language)
        return engine

    logger.error('[OCR] No OCR engine available — text recognition disabled')
    return FallbackOCR()
