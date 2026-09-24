import cv2
import numpy as np

from lingolay.core.config import PreprocessingConfig


class ImagePreprocessor:
    """Image enhancement before OCR (grayscale, CLAHE contrast, sharpening, game mode)."""

    def __init__(self, config=None):
        if not config:
            config = PreprocessingConfig()
        self._config = config
        self._clahe = cv2.createCLAHE(clipLimit=self._config.contrast_clip, tileGridSize=(8, 8))
        self._sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])

    def update_config(self, config):
        self._config = config
        self._clahe = cv2.createCLAHE(clipLimit=config.contrast_clip, tileGridSize=(8, 8))

    def process(self, image):
        """Apply preprocessing pipeline. Returns image ready for OCR."""
        if self._config.game_mode:
            return self._process_game_mode(image)
        result = image.copy()
        if self._config.grayscale and result.ndim == 3:
            result = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
        if self._config.contrast:
            if result.ndim == 3:
                lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB)
                lab[:, :, 0] = self._clahe.apply(lab[:, :, 0])
                result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            else:
                result = self._clahe.apply(result)
        if self._config.sharpen:
            result = cv2.filter2D(result, -1, self._sharpen_kernel)
        if self._config.upscale:
            result = cv2.resize(result, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        if self._config.subtitle_boost:
            gray = result if result.ndim == 2 else cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
            if np.mean(gray) < 127:
                # Dark background + light text → invert to get black text on white
                _, result = cv2.threshold(cv2.bitwise_not(gray), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            else:
                _, result = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return result

    def _process_game_mode(self, image):
        """
        Game subtitle preprocessing pipeline.

        Game subtitles are almost always white text with a dark outline on a
        complex background. Standard CLAHE+grayscale gives OCR a noisy mess.
        This pipeline isolates white pixels first, stripping the background
        entirely, then gives OCR clean black-on-white text.

        Steps:
          1. 2x upscale  — Windows OCR needs characters ≥30px tall
          2. White mask  — inRange isolates subtitle pixels, drops background
          3. Denoise     — GaussianBlur smooths anti-aliasing artifacts
          4. Morph close — fills tiny gaps in partially-transparent edges
          5. Invert      — white text on black → black text on white (OCR optimal)
        """
        if len(image.shape) == 2:
            bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            bgr = image.copy()
        h, w = bgr.shape[:2]
        bgr = cv2.resize(bgr, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
        mask = cv2.inRange(bgr, (200, 200, 200), (255, 255, 255))
        mask = cv2.GaussianBlur(mask, (3, 3), 0)
        _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=1)
        close_kernel = np.ones((2, 2), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)
        result = cv2.bitwise_not(mask)
        pad = np.full((50, result.shape[1]), 255, dtype=np.uint8)
        result = np.vstack([pad, result, pad])
        return result

    @staticmethod
    def subtitle_preset():
        """Default for streaming (Netflix/YouTube) — clean text on dark bg."""
        return PreprocessingConfig(grayscale=True, contrast=True, sharpen=False, upscale=False, subtitle_boost=False, contrast_clip=2.0, game_mode=False)

    @staticmethod
    def game_subtitle_preset():
        """For in-game subtitles — white pixel isolation + 2x upscale."""
        return PreprocessingConfig(grayscale=False, contrast=False, sharpen=False, upscale=False, subtitle_boost=False, contrast_clip=2.0, game_mode=True)

    @staticmethod
    def netflix_preset():
        """Aggressive preset for streaming services with small, anti-aliased fonts."""
        return PreprocessingConfig(grayscale=True, contrast=True, sharpen=True, upscale=True, subtitle_boost=True, contrast_clip=4.0)

    @staticmethod
    def document_preset():
        """For black text on light backgrounds."""
        return PreprocessingConfig(grayscale=True, contrast=True, sharpen=False, upscale=False, subtitle_boost=False, contrast_clip=2.0)
