"""
Main pipeline:  screen capture → preprocessing → OCR → stabilization → translation → overlay.

Capture runs on its own QThread and translation on another. OCR and text
stabilization run on the main thread via the capture signal; when the frame has
not changed OCR is skipped (frame-diff) and a pending subtitle is completed via
`poll_pending`.
"""
import logging
import re
import threading
import time
from collections import deque
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal

from lingolay.capture.screen import ScreenCapture
from lingolay.core.config import get_settings, save_settings
from lingolay.i18n import t
from lingolay.ocr import create_ocr_engine
from lingolay.preprocessing.filters import ImagePreprocessor
from lingolay.text.stabilizer import TextStabilizer, seq_ratio
from lingolay.text.turkish_postprocess import post_process_turkish
from lingolay.translation import create_translator

logger = logging.getLogger(__name__)

# If the mean pixel difference between two sampled frames is below this,
# the screen is considered unchanged and OCR is skipped.
FRAME_DIFF_THRESHOLD = 1.5
_SENTENCE_END = ('.', '!', '?', '…', '。', '！', '？')
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?…])\s+|(?<=[。！？])\s*')


def _join_sentences(parts):
    """Join sentences with a space, except after CJK punctuation (no spaces in CJK text)."""
    out = ''
    for part in parts:
        if out and not out.endswith(('。', '！', '？')):
            out += ' '
        out += part
    return out


@dataclass
class PipelineStatus:
    is_running: bool = False
    region_set: bool = False
    translator_ready: bool = False
    translator_error: str | None = None
    ocr_engine_name: str = '—'
    device_name: str = '—'
    fps: float = 0.0
    ocr_latency_ms: int = 0
    translate_latency_ms: int = 0
    cache_hit_rate: float = 0.0
    current_ocr_text: str = ''
    current_translation: str = ''
    preview_mode: bool = False


class TranslationWorker(QThread):
    """Loads the translation engine and translates the latest request (older requests are dropped)."""
    translation_ready = Signal(str)
    translation_error = Signal(str)
    translator_loaded = Signal()
    translator_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._translator = None
        self._pending = None
        self._lock = threading.Lock()
        self._event = threading.Event()
        self._stop = False
        self._loading = True

    def run(self):
        settings = get_settings()
        try:
            self._translator = create_translator(settings)
            if not self._translator.is_ready:
                self.translator_failed.emit(self._translator.init_error or t('The model could not be loaded'))
                self._loading = False
                return
            self._translator.warm_up()
            self.translator_loaded.emit()
        except Exception as e:
            logger.exception('[Translator] Load error')
            self.translator_failed.emit(str(e))
            self._loading = False
            return
        self._loading = False
        while not self._stop:
            self._event.wait(timeout=0.5)
            self._event.clear()
            if self._stop:
                return
            with self._lock:
                text = self._pending
                self._pending = None
            if not text:
                continue
            try:
                result = self._translator.translate(text)
                if result.error:
                    logger.warning('Translation error: %s', result.error)
                    self.translation_error.emit(result.error)
                elif result.text:
                    out = result.text
                    if settings.target_lang == 'tr':
                        out = post_process_turkish(out)
                    self.translation_ready.emit(out)
                else:
                    logger.warning('Empty translation result for: %r', text[:60])
                    self.translation_error.emit(t('Empty translation result — check the source/target language settings.'))
            except Exception as e:
                logger.exception('Translation exception')
                self.translation_error.emit(t('Translation error: {error}', error=e))

    def request_translation(self, text):
        """Queue a translation request (replaces any pending request)."""
        with self._lock:
            self._pending = text
        self._event.set()

    def stop(self):
        self._stop = True
        self._event.set()
        self.wait(3000)

    @property
    def translator(self):
        return self._translator


class Pipeline(QObject):
    translation_ready = Signal(str)
    translation_error = Signal(str)
    ocr_text_ready = Signal(str)
    status_updated = Signal(object)
    error_occurred = Signal(str)
    translator_loading = Signal()
    translator_ready = Signal()
    translator_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        settings = get_settings()
        self._capture = ScreenCapture()
        self._preprocessor = ImagePreprocessor(settings.preprocessing)
        self._ocr = None
        self._stabilizer = TextStabilizer(
            stability_count=settings.stability_count,
            min_length=settings.min_text_length,
            cooldown_ms=settings.cooldown_ms,
            text_expiry_sec=settings.text_expiry_sec,
            settle_ms=settings.subtitle_settle_ms,
            source_lang=settings.source_lang,
            target_lang=settings.target_lang,
        )
        self._translation_worker = None
        self._status = PipelineStatus()
        self._preview_mode = False
        self._frame_times = []
        self._frame_count_debug = 0
        self._last_region = None
        self._last_monitor_index = 0
        self._last_dpi_scale = 1.0
        self._last_frame_sample = None
        self._translated_sentences = {}
        self._recent_translations = deque(maxlen=12)
        self._capture.frame_ready.connect(self._on_frame)
        self._capture.error_occurred.connect(self._on_capture_error)

    # ── Lifecycle ──────────────────────────────────────────────────────
    def initialize(self):
        """Initialize OCR engine and start the translation worker. Call once at startup."""
        settings = get_settings()
        from lingolay.languages import get_language
        self._ocr = create_ocr_engine(get_language(settings.source_lang).ocr)
        self._status.ocr_engine_name = self._ocr.get_name()
        self._start_worker()

    def _start_worker(self):
        self._translation_worker = TranslationWorker()
        self._translation_worker.translation_ready.connect(self._on_translation)
        self._translation_worker.translation_error.connect(self.translation_error)
        self._translation_worker.translator_loaded.connect(self._on_translator_loaded)
        self._translation_worker.translator_failed.connect(self._on_translator_failed)
        self._status.translator_ready = False
        self.translator_loading.emit()
        self._emit_status()
        self._translation_worker.start()

    def set_region(self, x, y, width, height, monitor_index, dpi_scale):
        """Set the capture region and reset stabilizer."""
        self._capture.set_region(x, y, width, height, monitor_index, dpi_scale)
        self._stabilizer.reset()
        self._translated_sentences.clear()
        self._recent_translations.clear()
        self._last_frame_sample = None
        self._last_region = (x, y, width, height)
        self._last_monitor_index = monitor_index
        self._last_dpi_scale = dpi_scale
        self._status.region_set = True
        self._emit_status()

    @property
    def current_region(self):
        """Returns (x, y, w, h) of the currently set region, or None."""
        return self._last_region

    @property
    def current_monitor_index(self):
        return self._last_monitor_index

    @property
    def current_dpi_scale(self):
        return self._last_dpi_scale

    def start(self):
        """Start the pipeline (requires region to be set)."""
        if not self._status.region_set:
            self.error_occurred.emit(t('Select a region first'))
            return
        if not self._status.translator_ready and not self._preview_mode:
            self.error_occurred.emit(t('The translator is not ready yet, please wait'))
            return
        self._stabilizer.reset()
        self._translated_sentences.clear()
        self._recent_translations.clear()
        self._last_frame_sample = None
        self._frame_count_debug = 0
        self._status.is_running = True
        self._capture.start_capture()
        logger.info('[Pipeline] Started — region=%s  preview=%s', self._last_region, self._preview_mode)
        self._emit_status()

    def stop(self):
        self._status.is_running = False
        self._capture.stop_capture()
        self._stabilizer.reset()
        self._emit_status()

    def set_preview_mode(self, enabled):
        """
        Preview mode: show raw OCR text without translation.
        Useful for calibrating region and preprocessing settings.
        """
        self._preview_mode = enabled
        self._status.preview_mode = enabled
        self._emit_status()

    def update_preprocessing(self, config):
        self._preprocessor.update_config(config)

    def update_stability(self, stability_count):
        self._stabilizer.update_settings(stability_count=stability_count)

    def set_languages(self, source_lang, target_lang):
        """Language pair changed: update the stabilizer and OCR language (the translator is reloaded separately)."""
        from lingolay.languages import get_language
        self._stabilizer.set_languages(source_lang, target_lang)
        self._stabilizer.reset()
        self._translated_sentences.clear()
        if self._ocr is not None:
            self._ocr.set_language(get_language(source_lang).ocr)

    def reload_translator(self):
        """Hot-swap the translator with current settings — no app restart needed."""
        was_running = self._status.is_running
        if was_running:
            self._capture.stop_capture()
        if self._translation_worker:
            self._translation_worker.stop()
            self._translation_worker.deleteLater()
            self._translation_worker = None
        self._status.device_name = '—'
        self._start_worker()
        if was_running:
            self._capture.start_capture()

    def shutdown(self):
        """Clean shutdown of all components."""
        self.stop()
        if self._translation_worker:
            self._translation_worker.stop()
        save_settings()

    # ── Frame processing ────────────────────────────────────────────────────────
    def _on_frame(self, frame):
        """Process a captured frame through the OCR pipeline."""
        if not self._status.is_running or self._ocr is None:
            return
        start = time.perf_counter()
        self._frame_count_debug += 1
        if self._frame_count_debug == 1 or self._frame_count_debug % 100 == 0:
            logger.debug('[Pipeline] Frame #%d received  shape=%s', self._frame_count_debug, frame.image.shape)

        # Frame-diff: if the screen did not change, skip OCR and only poll the pending subtitle.
        img = frame.image
        channel = img[::8, ::8, 0] if img.ndim == 3 else img[::8, ::8]
        frame_sample = channel.astype(np.int16)
        if self._last_frame_sample is not None and self._last_frame_sample.shape == frame_sample.shape:
            diff = float(np.mean(np.abs(frame_sample - self._last_frame_sample)))
            if diff < FRAME_DIFF_THRESHOLD and not self._preview_mode:
                pending = self._stabilizer.poll_pending()
                if pending is not None:
                    self._dispatch_translation(pending)
                self._update_fps()
                return
        self._last_frame_sample = frame_sample.copy()

        processed = self._preprocessor.process(img)
        raw_text = self._ocr.recognize(processed)
        ocr_ms = self._ocr.last_latency_ms
        self._status.ocr_latency_ms = ocr_ms
        self._status.current_ocr_text = raw_text
        if raw_text.strip():
            logger.debug('[Pipeline] OCR: %r  (%dms)', raw_text[:80], ocr_ms)

        if self._preview_mode:
            self.ocr_text_ready.emit(raw_text)
        elif raw_text.strip():
            stable = self._stabilizer.process(raw_text)
            if stable.is_stable:
                self._dispatch_translation(stable)

        self._update_fps()
        process_ms = int((time.perf_counter() - start) * 1000)
        self._capture.report_processing_time(process_ms)
        self._emit_status()

    def _dispatch_translation(self, stable):
        """
        Send settled text to the translator — but first drop sentences that were
        already translated (prevents re-translating the top line of scrolling subtitles).
        """
        if self._is_own_translation(stable.text):
            logger.debug('[Pipeline] Read our own translation (overlay) — skipped')
            self._stabilizer.mark_translated(stable.normalized)
            return
        self._stabilizer.mark_translated(stable.normalized)
        text = self._extract_new_sentences(stable.text)
        if not text:
            return
        logger.info('[Pipeline] → Translating: %r', text[:80])
        if self._translation_worker:
            self._translation_worker.request_translation(text)

    @staticmethod
    def _flatten(text):
        return re.sub(r'\s+', ' ', text.replace('\n', ' ')).strip().lower()

    def _is_own_translation(self, text):
        """
        Is this OCR text our own overlay output?

        Language detection is unreliable for short sentences. Comparing directly
        with recent translations is decisive; fuzzy matching tolerates OCR jitter.
        """
        probe = self._flatten(text)
        if len(probe) < 6:
            return False
        now = time.time()
        for prev, ts in self._recent_translations:
            if now - ts < 5.0 and (prev == probe or seq_ratio(prev, probe) >= 0.85):
                return True
        return False

    def _is_sentence_seen(self, key):
        """
        Was this sentence translated before? Falls back to fuzzy matching:
        OCR jitter can produce the same sentence with different spellings
        ("So this is sea otter meat" vs "So this islsa otter meat"); difflib
        catches these and prevents duplicate translation + duplicate dubbing.
        """
        if key in self._translated_sentences:
            return True
        kc = key.replace(' ', '')
        if len(kc) < 6:
            return False
        for seen in self._translated_sentences:
            if seen.replace(' ', '') == kc or seq_ratio(seen, key) >= 0.88:
                return True
        return False

    def _extract_new_sentences(self, text):
        """
        Split text into sentences, drop COMPLETE sentences already translated and
        return the new ones. Fully unfinished text (no sentence end) is translated as-is.
        """
        flat = re.sub(r'\s+', ' ', text.replace('\n', ' ')).strip()
        if not flat:
            return ''
        now = time.time()
        for sentence, ts in list(self._translated_sentences.items()):
            if now - ts > 300.0:
                del self._translated_sentences[sentence]

        parts = _SENTENCE_SPLIT.split(flat)
        new_parts = []
        tail = []
        has_complete = False
        for p in parts:
            p = p.strip()
            if not p:
                continue
            if p.endswith(_SENTENCE_END):
                has_complete = True
                key = p.lower()
                if self._is_sentence_seen(key):
                    continue
                self._translated_sentences[key] = now
                new_parts.append(p)
            else:
                tail.append(p)

        if new_parts:
            items = sorted(self._translated_sentences.items(), key=lambda kv: kv[1])
            self._translated_sentences = dict(items[-100:])
            return _join_sentences(new_parts + tail)
        if has_complete:
            # All complete sentences were already translated; the unfinished tail is translated once complete.
            return ''
        key = flat.lower()
        if self._is_sentence_seen(key):
            return ''
        self._translated_sentences[key] = now
        return flat

    # ── Signal handlers ────────────────────────────────────────────────
    def _on_translation(self, text):
        logger.info('[Pipeline] ← Translation: %r', text[:80])
        self._recent_translations.append((self._flatten(text), time.time()))
        self._status.current_translation = text
        self.translation_ready.emit(text)
        if self._translation_worker and self._translation_worker.translator:
            self._status.translate_latency_ms = self._translation_worker.translator.last_latency_ms
            self._status.cache_hit_rate = self._translation_worker.translator.cache_hit_rate
        self._emit_status()

    def _on_translator_loaded(self):
        self._status.translator_ready = True
        self._status.translator_error = None
        if self._translation_worker and self._translation_worker.translator:
            self._status.device_name = self._translation_worker.translator.device_name
        self.translator_ready.emit()
        self._emit_status()

    def _on_translator_failed(self, error):
        self._status.translator_ready = False
        self._status.translator_error = error
        self.translator_failed.emit(error)
        self._emit_status()

    def _on_capture_error(self, message):
        logger.error('Capture error: %s', message)
        self.error_occurred.emit(message)

    def _update_fps(self):
        now = time.perf_counter()
        self._frame_times.append(now)
        cutoff = now - 1.0
        self._frame_times = [t for t in self._frame_times if t >= cutoff]
        self._status.fps = len(self._frame_times)

    def _emit_status(self):
        self.status_updated.emit(self._status)

    @property
    def status(self):
        return self._status
