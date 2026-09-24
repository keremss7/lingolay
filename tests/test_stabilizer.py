import time

from lingolay.text.cleaning import TextStabilizer


def make(**kw):
    kw.setdefault('stability_count', 1)
    kw.setdefault('settle_ms', 50)
    return TextStabilizer(**kw)


def test_text_becomes_stable_after_settle_time():
    st = make()
    first = st.process('Where did you put the keys?')
    assert not first.is_stable  # just arrived
    time.sleep(0.12)
    second = st.process('Where did you put the keys?')
    assert second.is_stable
    assert second.text == 'Where did you put the keys?'


def test_recently_translated_text_is_not_repeated():
    st = make()
    st.process('Follow me!')
    time.sleep(0.12)
    stable = st.process('Follow me!')
    assert stable.is_stable
    st.mark_translated(stable.normalized)
    time.sleep(0.12)
    assert not st.process('Follow me!').is_stable


def test_ocr_jitter_does_not_reset_settle_timer():
    st = make()
    st.process('The bridge is about to collapse')
    time.sleep(0.12)
    # one-character OCR flicker must count as the same subtitle
    assert st.process('The bridge is about to col1apse').is_stable


def test_poll_pending_finishes_a_settled_subtitle():
    st = make()
    st.process('Run!')
    assert st.poll_pending() is None
    time.sleep(0.12)
    pending = st.poll_pending()
    assert pending is not None and pending.is_stable


def test_garbage_is_never_stable():
    st = make()
    st.process('12:45')
    time.sleep(0.12)
    assert not st.process('12:45').is_stable


def test_reset_clears_state():
    st = make()
    st.process('Hello there, general Kenobi.')
    st.reset()
    assert st.poll_pending() is None
