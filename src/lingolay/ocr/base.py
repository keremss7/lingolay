from abc import ABC, abstractmethod

import numpy as np

from lingolay.i18n import t


class OCREngine(ABC):
    """Common interface for all OCR engines."""

    @abstractmethod
    def recognize(self, image: np.ndarray) -> str:
        """
        Perform OCR on an image.
        Args:
            image: BGR or grayscale numpy array from screen capture
        Returns:
            Recognized text (lines separated by newlines), '' on failure
        """

    @abstractmethod
    def get_name(self) -> str:
        """Human-readable engine name."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this engine is available on the system."""

    @property
    def last_latency_ms(self) -> int:
        """Latency of last recognition in milliseconds."""
        return getattr(self, '_last_latency_ms', 0)

    def set_language(self, language: str) -> None:  # noqa: B027 - optional hook, not abstract
        """Set recognition language (override if supported)."""


class FallbackOCR(OCREngine):
    """Used when no OCR engine is available — returns empty text so the app keeps running."""

    def __init__(self):
        self._last_latency_ms = 0

    def get_name(self):
        return t('OCR unavailable')

    def is_available(self):
        return True

    def recognize(self, image):
        return ''
