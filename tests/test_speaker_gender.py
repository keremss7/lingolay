import numpy as np
import pytest

from lingolay.tts import speaker_gender as sg


def test_log_mel_shape_and_normalization():
    t = np.arange(32000) / sg.SAMPLE_RATE
    feats = sg.log_mel(0.3 * np.sin(2 * np.pi * 220 * t))
    assert feats.shape == (1, 80, 201) and feats.dtype == np.float32
    assert np.allclose(feats.mean(axis=2), 0, atol=1e-3)  # mean-normalized per band


class _FakeSession:
    def __init__(self, probs):
        self.probs = np.array([probs], dtype=np.float32)

    def run(self, _outputs, inputs):
        assert inputs['feats'].shape[1] == 80
        return [self.probs]


@pytest.mark.parametrize('probs, expected', [((0.02, 0.98), 'female'), ((0.97, 0.03), 'male'), ((0.4, 0.6), None)])
def test_classify_applies_the_confidence_threshold(probs, expected):
    det = sg.SpeakerGenderDetector.__new__(sg.SpeakerGenderDetector)
    det._session, det.threshold = _FakeSession(probs), 0.9
    gender, confidence = det.classify(np.random.default_rng(0).normal(0, 0.1, 32000))
    assert gender == expected and confidence == pytest.approx(max(probs))


def test_silence_and_short_clips_are_not_classified():
    det = sg.SpeakerGenderDetector.__new__(sg.SpeakerGenderDetector)
    det._session, det.threshold = _FakeSession((0.0, 1.0)), 0.9
    assert det.classify(np.zeros(32000)) == (None, 0.0)
    assert det.classify(np.ones(1000) * 0.5) == (None, 0.0)
