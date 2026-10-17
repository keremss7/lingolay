import io
import wave

from lingolay.tts.audio_gain import concat_wavs
from lingolay.tts.fast_dubbing import FastDubbingEngine, catch_up_rate, unspoken_part


def _wav(frames, rate=22050):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b'\x01\x00' * frames)
    return buf.getvalue()


def _frames(wav_bytes):
    with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
        return wf.getnframes()


def test_catch_up_rate_speeds_up_only_when_behind():
    assert catch_up_rate('+35%', 0) == '+35%'
    assert catch_up_rate('+35%', 1) == '+55%'
    assert catch_up_rate('+35%', 5) == '+75%'  # capped
    assert catch_up_rate('+0%', 1) == '+20%'


def test_unspoken_part_skips_repeats_and_keeps_new_words():
    assert unspoken_part('Hello there.', None) == 'Hello there.'
    assert unspoken_part('Hello there.', 'hello there') == ''
    assert unspoken_part('I know you were there.', 'I know you') == 'were there.'
    assert unspoken_part('I know you, were there.', 'I know you') == 'were there.'
    assert unspoken_part('Something else.', 'I know you') == 'Something else.'
    # never cut inside a word
    assert unspoken_part('I knowledge', 'I know') == 'I knowledge'


def test_unspoken_part_handles_turkish_dotted_capital_i():
    # 'İ'.casefold() is two characters; the cut must still land on the original text
    assert unspoken_part('İstanbul çok güzel.', 'İstanbul') == 'çok güzel.'


def test_concat_wavs_gap_is_optional():
    a, b = _wav(100), _wav(50)
    assert _frames(concat_wavs([a, b])) == 150
    assert _frames(concat_wavs([a, b], gap_ms=100)) == 150 + 2205


def _engine(smooth):
    eng = FastDubbingEngine(duck_enabled=False, smooth=smooth)
    eng._is_enabled = True
    return eng


def test_legacy_mode_still_interrupts_the_current_line():
    eng = _engine(smooth=False)
    eng._enqueue('First line.')
    assert eng._interrupt_event.is_set()
    eng._enqueue('First line.')
    assert eng._queue.qsize() == 2


def test_natural_flow_lets_the_current_line_finish_and_skips_repeats():
    eng = _engine(smooth=True)
    eng._enqueue('First line.')
    assert not eng._interrupt_event.is_set()
    eng._enqueue('First line.')
    eng._enqueue('Second line.')
    texts = [eng._queue.get_nowait()[1] for _ in range(eng._queue.qsize())]
    assert texts == ['First line.', 'Second line.']


def test_hindi_and_urdu_sentence_ends_are_recognized():
    eng = _engine(smooth=True)
    eng.speak('उन्होंने इसे नष्ट कर दिया।')
    eng.speak('انہوں نے اسے تباہ کر دیا۔')
    assert eng._queue.qsize() == 2  # spoken right away, not held back as unfinished fragments


def test_japanese_works_without_the_sudachi_dictionary(monkeypatch):
    import sys

    import pytest
    pyopenjtalk = pytest.importorskip('pyopenjtalk')
    from lingolay.tts.piper_engine import use_openjtalk_dictionary_only
    monkeypatch.setitem(sys.modules, 'sudachidict_core', None)  # as in the Windows build
    monkeypatch.setattr(pyopenjtalk, 'run_frontend', pyopenjtalk.run_frontend)
    use_openjtalk_dictionary_only()
    from piper.phonemize_japanese import JapanesePhonemizer
    assert JapanesePhonemizer().phonemize('一緒に行きましょう。')[0]


class _FakeMatcher:
    def __init__(self, gender):
        self.gender, self.seen = gender, []

    def snapshot(self):
        return 'audio-at-speak-time'

    def decide(self, audio):
        self.seen.append(audio)
        return self.gender


def _gender_voices():
    from lingolay.models.manifest import GenderVoice
    return {'female': GenderVoice('xx_F-voice', speaker=1), 'male': GenderVoice('xx_M-voice', transform='male')}


def test_speaker_matching_picks_the_voice_for_the_detected_gender():
    eng = _engine(smooth=True)
    matcher = _FakeMatcher('male')
    eng.set_speaker_matching(matcher, _gender_voices())
    eng.speak('Lower your weapon.')
    kind, text, audio = eng._queue.get_nowait()
    assert (kind, text, audio) == ('__MATCH__', 'Lower your weapon.', 'audio-at-speak-time')
    assert eng._choose_voice(audio) == ('xx_M-voice', None, 'male')
    matcher.gender = 'female'
    assert eng._choose_voice(audio) == ('xx_F-voice', 1, None)


def test_unknown_speaker_or_matching_off_uses_the_default_voice():
    eng = _engine(smooth=True)
    eng.set_speaker_matching(_FakeMatcher(None), _gender_voices())
    assert eng._choose_voice('audio') == (eng._voice_key, None, None)
    eng.set_speaker_matching(None, None)
    eng.speak('Hello there.')
    assert eng._queue.get_nowait()[0] == '__SYNTH__'  # the original code path
