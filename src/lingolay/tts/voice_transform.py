"""
Turn a synthesized voice into the other gender (Praat's "Change gender": PSOLA pitch shift plus
formant scaling), for languages where Piper has only a male or only a female voice.
Settings were picked by listening tests and checked with the speaker-gender classifier.
"""
import io
import logging
import wave

import numpy as np

logger = logging.getLogger(__name__)

PARSELMOUTH_AVAILABLE = False
try:
    import parselmouth
    from parselmouth.praat import call
    PARSELMOUTH_AVAILABLE = True
except Exception:
    pass

# target → (formant shift ratio, new median pitch Hz, pitch range factor)
SETTINGS = {
    'female': (1.22, 235.0, 1.1),
    'male': (0.84, 105.0, 1.0),
}


def change_gender(wav_bytes, target):
    """Return the WAV with its voice moved toward `target` ('female' / 'male'); the original on failure."""
    if target not in SETTINGS or not PARSELMOUTH_AVAILABLE:
        return wav_bytes
    try:
        with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
            rate, channels = wf.getframerate(), wf.getnchannels()
            samples = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float64) / 32768
        if channels > 1:
            samples = samples.reshape(-1, channels).mean(axis=1)
        formant, pitch, pitch_range = SETTINGS[target]
        sound = parselmouth.Sound(samples, sampling_frequency=rate)
        out = call(sound, 'Change gender', 75, 600, formant, pitch, pitch_range, 1.0)
        y = out.values[0]
        peak = float(np.abs(y).max()) or 1.0
        pcm = (np.clip(y / max(peak, 1.0), -1, 1) * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(int(out.sampling_frequency))
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()
    except Exception as e:
        logger.warning('[TTS] Voice transform failed (%s), using the original voice', e)
        return wav_bytes
