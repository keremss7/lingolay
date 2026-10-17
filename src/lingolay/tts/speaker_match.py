"""
"Match the speaker's voice" (experimental): listen to the game or video, decide whether the person
speaking is a man or a woman, and let the dubbing pick a matching voice.
"""
import logging
import threading
import time

from .game_audio import GameAudioCapture, is_supported

logger = logging.getLogger(__name__)

SNAPSHOT_SECONDS = 2.0
KEEP_LAST_SECONDS = 10.0   # when unsure, keep the last confident gender this long


class SpeakerMatcher:
    def __init__(self, model_path, threshold=0.9):
        self._model_path = model_path
        self._threshold = threshold
        self._capture = GameAudioCapture()
        self._detector = None
        self._lock = threading.Lock()
        self._last = None          # (gender, time)
        self.error = None

    @staticmethod
    def supported():
        return is_supported()

    def start(self):
        try:
            from .speaker_gender import SpeakerGenderDetector
            self._detector = SpeakerGenderDetector(self._model_path, threshold=self._threshold)
        except Exception as e:
            self.error = f'Gender model could not be loaded: {e}'
            return False
        if not self._capture.start():
            self.error = self._capture.error
            return False
        logger.info('[SpeakerMatch] Listening to the game audio')
        return True

    def stop(self):
        self._capture.stop()

    def snapshot(self):
        """Copy of the last seconds of game audio; cheap, call when a line arrives."""
        return self._capture.recent(SNAPSHOT_SECONDS)

    def decide(self, audio):
        """'female' / 'male' for a snapshot, or None to use the default voice."""
        gender, confidence = (None, 0.0)
        if self._detector is not None and audio is not None and len(audio):
            try:
                gender, confidence = self._detector.classify(audio)
            except Exception as e:
                logger.debug('[SpeakerMatch] Classification failed: %s', e)
        now = time.monotonic()
        with self._lock:
            if gender:
                self._last = (gender, now)
            elif self._last and now - self._last[1] < KEEP_LAST_SECONDS:
                gender = self._last[0]
        logger.debug('[SpeakerMatch] speaker=%s (%.2f)', gender, confidence)
        return gender
