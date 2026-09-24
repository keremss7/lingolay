import io
import logging
import time
import wave
from pathlib import Path

from lingolay.i18n import t

logger = logging.getLogger(__name__)

PIPER_AVAILABLE = False
PIPER_IMPORT_ERROR = ''

try:
    import piper  # noqa: F401
    PIPER_AVAILABLE = True
except Exception as _e:
    PIPER_IMPORT_ERROR = str(_e)

DEFAULT_VOICE = 'tr_TR-dfki-medium'


def _local_paths(voice_key: str) -> tuple[Path, Path]:
    from lingolay.core.paths import VOICES_DIR
    base = VOICES_DIR / voice_key / voice_key
    return base.with_suffix('.onnx'), Path(str(base) + '.onnx.json')


def voice_for_target(lang_code: str) -> str | None:
    from lingolay.models.manifest import voice_for_language
    return voice_for_language(lang_code)


def model_is_downloaded(voice_key: str = DEFAULT_VOICE) -> bool:
    if not voice_key:
        return False
    onnx_path, json_path = _local_paths(voice_key)
    return onnx_path.exists() and json_path.exists()


def _get_short_path(path: str) -> str | None:
    """Return the Windows 8.3 short path (espeak struggles with Unicode paths); None on failure."""
    import sys
    if sys.platform != 'win32':
        return path
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(512)
        ret = ctypes.windll.kernel32.GetShortPathNameW(path, buf, 512)
        if ret and ret < 512:
            return buf.value
        return None
    except Exception:
        return None


def _pcm_to_wav(pcm_data: bytes, sample_rate: int, channels: int, sampwidth: int = 2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def _pitch_shift_wav(wav_bytes: bytes, semitones: float) -> bytes:
    if semitones == 0.0:
        return wav_bytes
    try:
        import numpy as np
        with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
            sr = wf.getframerate()
            ch = wf.getnchannels()
            sw = wf.getsampwidth()
            frames = wf.readframes(wf.getnframes())
        samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        ratio = 2.0 ** (semitones / 12.0)
        n_orig = len(samples)
        n_stretched = max(1, int(round(n_orig / ratio)))
        x_orig = np.linspace(0.0, 1.0, n_orig)
        stretched = np.interp(np.linspace(0.0, 1.0, n_stretched), x_orig, samples)
        shifted = np.interp(x_orig, np.linspace(0.0, 1.0, n_stretched), stretched)
        out = np.clip(shifted * 32768.0, -32768, 32767).astype(np.int16)
        return _pcm_to_wav(out.tobytes(), sr, ch, sw)
    except Exception as e:
        logger.debug('[Piper] pitch_shift failed (%s), returning the original', e)
        return wav_bytes


class PiperEngine:
    def __init__(self, voice_key: str = DEFAULT_VOICE):
        self._voice_key = voice_key
        self._voice = None
        self._sample_rate = 22050
        self._num_speakers = 1
        self._init_error = None
        self._try_load()

    @property
    def is_ready(self) -> bool:
        return self._voice is not None

    @property
    def init_error(self) -> str | None:
        return self._init_error

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def _rate_to_length_scale(self, rate: str) -> float:
        """edge-tts style '+50%' → Piper length_scale (smaller = faster)."""
        try:
            pct = float(rate.replace('%', '').replace('+', ''))
            return max(0.4, min(2.0, 1.0 / (1.0 + pct / 100.0)))
        except Exception:
            return 1.0

    def _try_load(self):
        if not PIPER_AVAILABLE:
            self._init_error = t('piper-tts is not installed: {error}', error=PIPER_IMPORT_ERROR)
            return
        onnx_path, _ = _local_paths(self._voice_key)
        if not onnx_path.exists():
            self._init_error = t('Voice model not found: {name}. You will be asked to download it when you first enable dubbing.', name=onnx_path.name)
            return
        try:
            import os

            import piper as _piper_pkg
            espeak_data = Path(_piper_pkg.__file__).parent / 'espeak-ng-data'
            espeak_data_str = _get_short_path(str(espeak_data)) if espeak_data.exists() else None
            if espeak_data_str:
                os.environ.setdefault('ESPEAK_DATA_PATH', espeak_data_str)
                try:
                    from piper import espeakbridge as _esb
                    _esb.initialize(espeak_data_str)
                except Exception:
                    pass
            from piper.voice import PiperVoice
            self._voice = PiperVoice.load(
                str(onnx_path),
                espeak_data_dir=espeak_data_str if espeak_data_str else str(espeak_data),
            )
            self._sample_rate = self._voice.config.sample_rate
            self._num_speakers = int(getattr(self._voice.config, 'num_speakers', 1) or 1)
            logger.info('[Piper] Model loaded: %s (%sHz, %s speakers)', self._voice_key, self._sample_rate, self._num_speakers)
        except Exception as e:
            self._init_error = str(e)
            logger.error('[Piper] Model could not be loaded: %s', e)

    def synthesize(
        self,
        text: str,
        rate: str = '+35%',
        speaker_id: int | None = None,
        pitch: float = 0.0,
    ) -> tuple[bytes | None, str | None]:
        if not self._voice:
            return (None, self._init_error or t('Piper is not ready'))
        text = text.strip()
        if not text:
            return (None, 'Empty text')
        if self._num_speakers > 1 and speaker_id is None:
            speaker_id = 0
        if speaker_id is not None:
            speaker_id = speaker_id % max(1, self._num_speakers)
        length_scale = self._rate_to_length_scale(rate)
        try:
            from piper.config import SynthesisConfig
            try:
                syn_cfg = SynthesisConfig(length_scale=length_scale, speaker_id=speaker_id)
            except TypeError:
                syn_cfg = SynthesisConfig(length_scale=length_scale)
        except Exception:
            syn_cfg = None
        try:
            start = time.perf_counter()
            pcm_parts = []
            sample_rate = self._sample_rate
            channels = 1
            syn_kwargs = {'syn_config': syn_cfg} if syn_cfg is not None else {}
            for chunk in self._voice.synthesize(text, **syn_kwargs):
                pcm_parts.append(chunk.audio_int16_bytes)
                sample_rate = chunk.sample_rate
                channels = chunk.sample_channels
            wav_data = _pcm_to_wav(b''.join(pcm_parts), sample_rate, channels)
            if pitch != 0.0:
                wav_data = _pitch_shift_wav(wav_data, pitch)
            latency = int((time.perf_counter() - start) * 1000)
            logger.debug('[Piper] %d chars → %dms (spk=%s, ls=%.2f)', len(text), latency, speaker_id, length_scale)
            return (wav_data, None)
        except Exception as e:
            return (None, f'[Piper] Synthesis error: {e}')

