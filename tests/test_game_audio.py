import subprocess
import sys

import numpy as np
import pytest

from lingolay.tts import game_audio


def test_ring_buffer_keeps_the_latest_audio_in_order():
    cap = game_audio.GameAudioCapture(buffer_seconds=1.0)
    assert len(cap.recent(0.5)) == 0
    a = np.arange(10000, dtype=np.float32)
    cap._push(a)
    assert np.array_equal(cap.recent(0.25), a[-4000:])
    b = np.arange(10000, 20000, dtype=np.float32)
    cap._push(b)  # wraps around the 16000-sample buffer
    assert np.array_equal(cap.recent(1.0), np.concatenate([a, b])[-16000:])
    assert np.array_equal(cap.recent(0.1), b[-1600:])


@pytest.mark.skipif(not game_audio.is_supported(), reason='Windows 10 2004+ only')
def test_process_loopback_starts_without_crashing():
    # Run in a child process: a wrong COM declaration would crash the interpreter, not just fail.
    code = (
        'import time; from lingolay.tts.game_audio import GameAudioCapture\n'
        'c = GameAudioCapture(); ok = c.start(); time.sleep(0.5)\n'
        'print("started" if ok else "error:", c.error, len(c.recent(0.5))); c.stop()\n'
    )
    out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=60)
    print(out.stdout, out.stderr)
    assert out.returncode == 0, out.stderr
    # CI runners have no sound card; activation may then fail cleanly, but it must not crash.
    assert out.stdout.startswith(('started', 'error:'))
