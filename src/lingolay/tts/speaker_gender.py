"""
Speaker gender detection for "match the speaker's voice" dubbing (experimental).

A small ECAPA-TDNN classifier (JaesungHuh/voice-gender-classifier, MIT, trained on VoxCeleb)
exported to ONNX. The log-mel features it expects are computed here with numpy, so neither
PyTorch nor torchaudio is needed at runtime; onnxruntime already ships with Piper.
"""
import logging

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
MIN_SECONDS = 0.6
_N_FFT, _WIN, _HOP, _N_MELS, _F_MIN, _F_MAX = 512, 400, 160, 80, 20.0, 7600.0


def _mel_filterbank():
    """HTK-scale triangular filters (no normalization), as torchaudio.functional.melscale_fbanks."""
    hz_to_mel = lambda f: 2595.0 * np.log10(1.0 + f / 700.0)  # noqa: E731
    mel_to_hz = lambda m: 700.0 * (10.0 ** (m / 2595.0) - 1.0)  # noqa: E731
    freqs = np.linspace(0, SAMPLE_RATE // 2, _N_FFT // 2 + 1)
    pts = mel_to_hz(np.linspace(hz_to_mel(_F_MIN), hz_to_mel(_F_MAX), _N_MELS + 2))
    diff = np.diff(pts)
    slopes = pts[None, :] - freqs[:, None]
    down = -slopes[:, :-2] / diff[:-1]
    up = slopes[:, 2:] / diff[1:]
    return np.maximum(0.0, np.minimum(down, up)).astype(np.float32)  # (257, 80)


_FILTERS = _mel_filterbank()
_WINDOW = np.zeros(_N_FFT, np.float32)
_pad = (_N_FFT - _WIN) // 2
_WINDOW[_pad:_pad + _WIN] = 0.54 - 0.46 * np.cos(2 * np.pi * np.arange(_WIN) / _WIN)  # periodic Hamming


def log_mel(audio):
    """Mean-normalized log-mel features, shape (1, 80, frames), for 16 kHz mono float audio."""
    x = np.asarray(audio, dtype=np.float32)
    x = np.concatenate([x[1:2], x])          # reflect-pad one sample for pre-emphasis
    x = x[1:] - 0.97 * x[:-1]
    x = np.pad(x, (_N_FFT // 2, _N_FFT // 2), mode='reflect')
    frames = 1 + (len(x) - _N_FFT) // _HOP
    idx = np.arange(_N_FFT)[None, :] + _HOP * np.arange(frames)[:, None]
    power = np.abs(np.fft.rfft(x[idx] * _WINDOW, axis=1)) ** 2
    mel = np.log(power @ _FILTERS + 1e-6).T
    return (mel - mel.mean(axis=1, keepdims=True))[None].astype(np.float32)


class SpeakerGenderDetector:
    """classify(audio) → ('female' | 'male' | None, confidence); None when unsure or silent."""

    def __init__(self, model_path, threshold=0.9, threads=1):
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        self._session = ort.InferenceSession(str(model_path), options, providers=['CPUExecutionProvider'])
        self.threshold = threshold

    def classify(self, audio):
        audio = np.asarray(audio, dtype=np.float32)
        if len(audio) < MIN_SECONDS * SAMPLE_RATE or float(np.sqrt(np.mean(audio ** 2))) < 1e-3:
            return None, 0.0
        male, female = self._session.run(None, {'feats': log_mel(audio)})[0][0]
        gender, confidence = ('female', float(female)) if female > male else ('male', float(male))
        return (gender if confidence >= self.threshold else None), confidence
