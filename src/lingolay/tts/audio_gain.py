import io
import logging
import wave

logger = logging.getLogger(__name__)

_TARGET_PEAK = 0.95
_MAX_NORMALIZE_GAIN = 12.0
_ATTACK_MS = 1.0
_RELEASE_MS = 40.0
_BLOCK_MS = 1.0


def _compress(x, sample_rate, boost):
    import numpy as np
    ratio = 1.0 + (boost - 1.0) * 3.0
    threshold_db = -18.0 + (boost - 2.0) * 2.0
    mono = np.max(np.abs(x), axis=0)
    n = mono.size
    block = max(1, int(sample_rate * _BLOCK_MS / 1000.0))
    n_blocks = int(np.ceil(n / block))
    padded = np.zeros(n_blocks * block, dtype=np.float32)
    padded[:n] = mono
    block_peak = padded.reshape(n_blocks, block).max(axis=1)
    a_att = float(np.exp(-block / (sample_rate * _ATTACK_MS / 1000.0)))
    a_rel = float(np.exp(-block / (sample_rate * _RELEASE_MS / 1000.0)))
    env = np.empty(n_blocks, dtype=np.float32)
    prev = float(block_peak[0])
    for i, p in enumerate(block_peak):
        a = a_att if p > prev else a_rel
        prev = a * prev + (1.0 - a) * float(p)
        env[i] = prev
    env_db = 20.0 * np.log10(np.maximum(env, 1e-06))
    over_db = np.maximum(env_db - threshold_db, 0.0)
    gain_db = -over_db * (1.0 - 1.0 / ratio)
    gain_lin = np.power(10.0, gain_db / 20.0)
    block_centers = np.arange(n_blocks, dtype=np.float32) * block + block / 2.0
    sample_idx = np.arange(n, dtype=np.float32)
    per_sample_gain = np.interp(sample_idx, block_centers, gain_lin).astype(np.float32)
    return x * per_sample_gain


def boost_wav(wav_bytes, boost, target_rate, target_channels):
    if not wav_bytes:
        return wav_bytes
    import numpy as np
    try:
        with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
            src_rate = wf.getframerate()
            src_ch = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            frames = wf.readframes(wf.getnframes())

        if sampwidth != 2 or not frames:
            return wav_bytes

        samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        if samples.size == 0:
            return wav_bytes

        if src_ch > 1:
            samples = samples.reshape(-1, src_ch).T
        else:
            samples = samples.reshape(1, -1)

        if boost > 1.0:
            samples = _compress(samples, src_rate, boost)

        peak = float(np.max(np.abs(samples)))
        if peak > 1e-5:
            samples = samples * min(_TARGET_PEAK / peak, _MAX_NORMALIZE_GAIN)

        out_ch = target_channels if target_channels > 0 else src_ch
        if out_ch != samples.shape[0]:
            if samples.shape[0] == 1:
                samples = np.repeat(samples, out_ch, axis=0)
            else:
                mono = np.mean(samples, axis=0, keepdims=True)
                samples = np.repeat(mono, out_ch, axis=0)

        out_rate = target_rate if target_rate > 0 else src_rate
        if out_rate != src_rate and samples.shape[1] > 1:
            n_out = max(1, int(round(samples.shape[1] * out_rate / src_rate)))
            x_src = np.linspace(0.0, 1.0, samples.shape[1], dtype=np.float32)
            x_out = np.linspace(0.0, 1.0, n_out, dtype=np.float32)
            samples = np.stack([np.interp(x_out, x_src, ch) for ch in samples])

        interleaved = samples.T.reshape(-1)
        out = np.clip(interleaved * 32767.0, -32768, 32767).astype(np.int16)

        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(out_ch)
            wf.setsampwidth(2)
            wf.setframerate(out_rate)
            wf.writeframes(out.tobytes())
        return buf.getvalue()
    except Exception as e:
        logger.debug('[TTS] Gain boost failed (%s), using the original audio', e)
        return wav_bytes


def concat_wavs(wav_list):
    wav_list = [w for w in wav_list if w]
    if not wav_list:
        return b''
    if len(wav_list) == 1:
        return wav_list[0]
    try:
        params = None
        pcm_parts = []
        for w in wav_list:
            with wave.open(io.BytesIO(w), 'rb') as wf:
                p = (wf.getnchannels(), wf.getsampwidth(), wf.getframerate())
                if params is None:
                    params = p
                elif p != params:
                    continue
                pcm_parts.append(wf.readframes(wf.getnframes()))

        if params is None or not pcm_parts:
            return wav_list[0]

        ch, sw, rate = params
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(ch)
            wf.setsampwidth(sw)
            wf.setframerate(rate)
            wf.writeframes(b''.join(pcm_parts))
        return buf.getvalue()
    except Exception as e:
        logger.debug('[TTS] WAV concatenation failed (%s)', e)
        return wav_list[0]

