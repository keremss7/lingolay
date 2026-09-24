import glob
import logging
import os
import re
import tempfile
import threading
import time
import uuid
from collections import OrderedDict
from queue import Empty, Queue

from lingolay.i18n import t

from .audio_gain import boost_wav, concat_wavs
from .ducking import AudioDucker
from .piper_engine import DEFAULT_VOICE, PIPER_AVAILABLE, PIPER_IMPORT_ERROR, PiperEngine, model_is_downloaded

logger = logging.getLogger(__name__)

PYGAME_AVAILABLE = False
try:
    os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
    import pygame
    PYGAME_AVAILABLE = True
except Exception:
    pass

_MAX_UTTERANCE_AGE = 3.0
_MAX_PENDING_UTTERANCES = 2
_DEBOUNCE_SEC = 0.18
_SENTENCE_END = {'.', '!', '?', '…'}
_MAX_SEG_LEN = 200

# Speed key from the settings → Piper speech rate (edge-tts style percentage)
SPEED_RATES = {'normal': '+0%', 'fast': '+35%', 'very_fast': '+60%'}
SPEED_LABELS = {'normal': 'Normal', 'fast': 'Fast (recommended)', 'very_fast': 'Very fast'}


def clean_dialogue(text: str) -> str:
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    return text


class TTSCache:
    def __init__(self, max_size: int = 128, max_age_seconds: float = 300.0):
        self._cache = OrderedDict()
        self._max_size = max_size
        self._max_age = max_age_seconds

    def _key(self, text: str, rate: str) -> str:
        import hashlib
        return hashlib.md5(f'{rate}:{text}'.encode()).hexdigest()

    def get(self, text: str, rate: str) -> bytes | None:
        k = self._key(text, rate)
        entry = self._cache.get(k)
        if entry is None:
            return None
        ts, data = entry
        if time.time() - ts > self._max_age:
            del self._cache[k]
            return None
        self._cache.move_to_end(k)
        return data

    def put(self, text: str, rate: str, data: bytes):
        k = self._key(text, rate)
        self._cache[k] = (time.time(), data)
        self._cache.move_to_end(k)
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)


class FastDubbingEngine:
    def __init__(
        self,
        speed: str = 'fast',
        voice_key: str = DEFAULT_VOICE,
        volume: float = 1.0,
        gain: float = 2.0,
        duck_enabled: bool = True,
        duck_level: float = 0.25,
    ):
        self._speech_rate = SPEED_RATES.get(speed, speed if str(speed).endswith('%') else '+35%')
        self._duck_level = duck_level
        self._voice_key = voice_key
        self._volume = max(0.0, min(1.0, volume))
        self._gain = max(1.0, gain)
        self._duck_enabled = duck_enabled

        self._is_enabled = False
        self._stop_event = threading.Event()
        self._interrupt_event = threading.Event()
        self._tts_playing_event = threading.Event()

        self._queue: Queue = Queue()
        self._play_queue: Queue = Queue()
        self._cache = TTSCache()

        self._piper: PiperEngine | None = None
        self._piper_lock = threading.Lock()

        self._mixer_initialized = False
        self._mixer_rate = 48000
        self._mixer_channels = 2
        self._playback_id = 0

        self._ducker: AudioDucker | None = None
        if duck_enabled:
            self._ducker = AudioDucker(level=duck_level)

        self._worker_thread: threading.Thread | None = None

        self._pending_lock = threading.Lock()
        self._pending_text: str | None = None
        self._pending_timer: threading.Timer | None = None

    @property
    def is_ready(self) -> bool:
        return PIPER_AVAILABLE and PYGAME_AVAILABLE and model_is_downloaded(self._voice_key)

    @property
    def is_enabled(self) -> bool:
        return self._is_enabled

    @property
    def voice_missing(self) -> bool:
        return not model_is_downloaded(self._voice_key)

    @property
    def voice_key(self) -> str | None:
        return self._voice_key

    @property
    def init_error(self) -> str | None:
        if not PIPER_AVAILABLE:
            return t('piper-tts is not installed ({error}). Install it with: pip install piper-tts', error=PIPER_IMPORT_ERROR)
        if not PYGAME_AVAILABLE:
            return t('pygame is not installed. Install it with: pip install pygame')
        if not self._voice_key:
            return t('There is no dubbing voice for this target language.')
        if self.voice_missing:
            return t('The dubbing voice model has not been downloaded.')
        return None

    def configure(self, speed: str, volume: float, gain: float, duck_enabled: bool = True, duck_level: float = 0.25):
        """Update settings while running."""
        self.set_speech_rate(SPEED_RATES.get(speed, '+35%'))
        self.set_volume(volume)
        self.set_gain(gain)
        self._duck_level = duck_level
        if duck_enabled and not self._duck_enabled:
            self._duck_enabled = True
            self._ducker = AudioDucker(level=duck_level)
            if self._is_enabled:
                self._start_ducker()
        elif not duck_enabled and self._duck_enabled:
            self._duck_enabled = False
            if self._ducker:
                self._ducker.stop()
                self._ducker = None
        elif self._ducker:
            self._ducker.set_level(duck_level)

    def _cleanup_old_temp_files(self):
        pattern = os.path.join(tempfile.gettempdir(), '_fast_dub_*.wav')
        for f in glob.glob(pattern):
            try:
                os.unlink(f)
            except Exception:
                pass

    def _start_ducker(self):
        if self._ducker:
            self._ducker.start()

    def enable(self) -> bool:
        if not self.is_ready:
            return False
        if self._is_enabled:
            return True
        self._is_enabled = True
        self._stop_event.clear()
        self._cleanup_old_temp_files()

        if PYGAME_AVAILABLE and not self._mixer_initialized:
            if pygame.mixer.get_init():
                pygame.mixer.quit()
            try:
                try:
                    pygame.mixer.init(frequency=48000, size=-16, channels=2, buffer=1024)
                except Exception:
                    pygame.mixer.init(frequency=24000, size=-16, channels=2, buffer=1024)
                freq, _fmt, ch = pygame.mixer.get_init()
                self._mixer_rate = freq
                self._mixer_channels = abs(ch)
                self._mixer_initialized = True
                logger.info('[TTS] Audio ready: %sHz/%sch', freq, ch)
            except Exception as e:
                logger.error('[TTS] Audio init error: %s', e)
                self._mixer_initialized = False

        if self._duck_enabled:
            if self._ducker is None:
                self._ducker = AudioDucker(level=self._duck_level)
            self._start_ducker()

        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name='TTSWorker',
        )
        self._worker_thread.start()
        logger.info('[TTS] Dubbing enabled — Piper %s (local)', self._voice_key)
        return True

    def disable(self):
        if not self._is_enabled:
            return
        self._is_enabled = False
        self._stop_event.set()

        with self._pending_lock:
            if self._pending_timer:
                self._pending_timer.cancel()
                self._pending_timer = None
            self._pending_text = None

        for q in (self._queue, self._play_queue):
            while not q.empty():
                try:
                    q.get_nowait()
                except Empty:
                    break

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)

        if self._ducker:
            self._ducker.stop()
            self._ducker = None

        if PYGAME_AVAILABLE and self._mixer_initialized:
            try:
                pygame.mixer.quit()
            except Exception:
                pass
            self._mixer_initialized = False

        logger.info('[TTS] Dubbing disabled')

    def speak(self, text: str):
        if not self._is_enabled or self._should_skip(text):
            return None
        text = clean_dialogue(text)
        if not text:
            return None
        with self._pending_lock:
            if text[-1] in _SENTENCE_END:
                if self._pending_text:
                    text = self._pending_text + ' ' + text
                    self._pending_text = None
                if self._pending_timer:
                    self._pending_timer.cancel()
                    self._pending_timer = None
                self._enqueue(text)
            else:
                self._pending_text = text
                if self._pending_timer:
                    self._pending_timer.cancel()
                t = threading.Timer(_DEBOUNCE_SEC, self._flush_pending)
                self._pending_timer = t
                t.daemon = True
                t.start()

    def _should_skip(self, text: str) -> bool:
        return not text or not text.strip()

    def _flush_pending(self):
        with self._pending_lock:
            text = self._pending_text
            self._pending_text = None
            self._pending_timer = None
        if text:
            self._enqueue(text)

    def _enqueue(self, text: str):
        self._interrupt_event.set()
        cached = self._cache.get(text, self._speech_rate)
        if cached:
            self._queue.put(('__CACHED__', text, cached))
        else:
            self._queue.put(('__SYNTH__', text, None))

    def set_speech_rate(self, rate: str):
        self._speech_rate = rate

    def set_volume(self, volume: float):
        self._volume = max(0.0, min(1.0, volume))

    def set_gain(self, gain: float):
        self._gain = max(1.0, gain)

    def clear_cache(self):
        self._cache = TTSCache()

    def _get_piper(self) -> PiperEngine | None:
        with self._piper_lock:
            if self._piper is None or not self._piper.is_ready:
                self._piper = PiperEngine(voice_key=self._voice_key)
            return self._piper

    def _split_into_segments(self, text: str, max_len: int = _MAX_SEG_LEN):
        text = text.strip()
        if len(text) <= max_len:
            return [text]
        raw = re.split(r'(?<=[.!?])\s+', text)
        segments = []
        for s in raw:
            s = s.strip()
            if not s:
                continue
            if len(s) > max_len:
                parts = []
                current = ''
                for word in s.split():
                    if len(current) + len(word) + 1 > max_len:
                        if current:
                            parts.append(current.strip())
                        current = word
                    else:
                        current = current + ' ' + word if current else word
                if current:
                    parts.append(current.strip())
                segments.extend(parts)
            else:
                segments.append(s)
        return segments

    def _worker_loop(self):
        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.1)
            except Empty:
                continue
            if self._stop_event.is_set():
                return
            self._interrupt_event.clear()
            item_type, text, data = item
            if item_type == '__CACHED__':
                self._push_playback(data)
                continue
            piper = self._get_piper()
            if piper is None or not piper.is_ready:
                logger.warning('[TTS] Piper not ready: %s', piper.init_error if piper else '?')
                continue
            parts = []
            for seg in self._split_into_segments(text):
                if self._stop_event.is_set() or self._interrupt_event.is_set():
                    break
                cached = self._cache.get(seg, self._speech_rate)
                if cached:
                    parts.append(cached)
                    continue
                audio, err = piper.synthesize(seg, rate=self._speech_rate)
                if err:
                    logger.warning('[TTS] Synthesis error: %s', err)
                    continue
                if not audio:
                    continue
                self._cache.put(seg, self._speech_rate, audio)
                parts.append(audio)
            if parts:
                self._push_playback(concat_wavs(parts))

    def _push_playback(self, audio: bytes):
        if not audio:
            return
        audio = boost_wav(
            audio,
            boost=self._gain,
            target_rate=self._mixer_rate,
            target_channels=self._mixer_channels,
        )
        self._play_queue.put((time.time(), audio))

    def _trim_queue(self):
        while self._play_queue.qsize() > _MAX_PENDING_UTTERANCES:
            try:
                self._play_queue.get_nowait()
            except Empty:
                return

    def poll_playback(self) -> bool:
        """Must ONLY be called from the main thread (QTimer)."""
        if not PYGAME_AVAILABLE:
            return False

        if self._ducker:
            if self._tts_playing_event.is_set() or not self._play_queue.empty():
                self._ducker.request_duck()
            else:
                self._ducker.request_release()

        if self._tts_playing_event.is_set():
            self._trim_queue()
            return False

        audio_data = None
        while True:
            try:
                queued_at, candidate = self._play_queue.get_nowait()
            except Empty:
                break
            if time.time() - queued_at > _MAX_UTTERANCE_AGE:
                logger.debug('[TTS] Skipped stale audio (waited too long in the queue)')
                continue
            audio_data = candidate
            break

        if not audio_data:
            return False

        if not self._mixer_initialized or not pygame.mixer.get_init():
            if pygame.mixer.get_init():
                pygame.mixer.quit()
            try:
                try:
                    pygame.mixer.init(frequency=48000, size=-16, channels=2, buffer=1024)
                except Exception:
                    pygame.mixer.init(frequency=24000, size=-16, channels=2, buffer=1024)
            except Exception as e:
                logger.error('[TTS] Mixer init failed: %s', e)
                return False
            self._mixer_initialized = True

        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except Exception:
            pass

        temp_path = os.path.join(
            tempfile.gettempdir(),
            f'_fast_dub_{uuid.uuid4().hex[:8]}.wav',
        )
        with open(temp_path, 'wb') as f:
            f.write(audio_data)

        self._playback_id += 1
        current_id = self._playback_id
        self._tts_playing_event.set()

        try:
            pygame.mixer.music.load(temp_path)
            pygame.mixer.music.set_volume(self._volume)
            pygame.mixer.music.play()
        except Exception as e:
            logger.error('[TTS] Playback failed: %s', e)
            self._tts_playing_event.clear()
            return False

        def _monitor(pb_id: int):
            try:
                while True:
                    try:
                        if not pygame.mixer.music.get_busy():
                            break
                    except Exception:
                        break
                    if self._stop_event.is_set() or self._interrupt_event.is_set():
                        try:
                            pygame.mixer.music.stop()
                        except Exception:
                            pass
                        break
                    try:
                        pygame.time.wait(50)
                    except Exception:
                        break
            except Exception:
                pass
            finally:
                if pb_id == self._playback_id:
                    self._tts_playing_event.clear()
                try:
                    pygame.mixer.music.unload()
                except Exception:
                    pass

        threading.Thread(
            target=_monitor,
            args=(current_id,),
            daemon=True,
            name='TTSAudioMonitor',
        ).start()
        return True
