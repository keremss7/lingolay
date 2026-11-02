def test_extract_new_sentences_skips_already_translated(qapp):
    from lingolay.core.pipeline import Pipeline
    p = Pipeline(qapp)
    assert p._extract_new_sentences('Hello there. How are you?') == 'Hello there. How are you?'
    # scrolling subtitle: first line already translated, only the new one is returned
    assert p._extract_new_sentences('How are you? I am fine.') == 'I am fine.'
    # nothing new
    assert p._extract_new_sentences('I am fine.') == ''
    # CJK sentence punctuation without spaces
    assert p._extract_new_sentences('行こう。早く！') == '行こう。早く！'


def test_own_translation_is_detected(qapp):
    import time

    from lingolay.core.pipeline import Pipeline
    p = Pipeline(qapp)
    p._recent_translations.append((p._flatten('Beni takip edin, köprü çökmek üzere!'), time.time()))
    assert p._is_own_translation('Beni takip edin, kopru çökmek üzere!')
    assert not p._is_own_translation('Something completely different here')


def test_main_window_builds(qapp):
    from lingolay.ui.main_window import MainWindow
    w = MainWindow()
    assert w.windowTitle() == 'Lingolay'
    w._hotkeys.stop()
    w._overlay.close()
    w._region_selector.close()
    w.deleteLater()
    qapp.processEvents()


def test_grown_typewriter_subtitle_is_translated_again(qapp):
    # Issue #12: the half-typed line was translated, the finished line was then taken for a duplicate
    from lingolay.core.pipeline import Pipeline
    p = Pipeline(qapp)
    full = ('But he never expected that his desperate gamble would directly cause her authority '
            'to spiral out of control, triggering the Great Shadow Calamity...')
    partial = full[:full.index('triggering') + len('triggering')]
    assert p._extract_new_sentences(partial) == partial
    assert p._extract_new_sentences(full) == full
    assert p._extract_new_sentences(full) == ''  # and only once


def test_ocr_jitter_is_still_a_duplicate(qapp):
    from lingolay.core.pipeline import Pipeline
    p = Pipeline(qapp)
    assert p._extract_new_sentences('So this is sea otter meat.')
    assert p._extract_new_sentences('So this islsa otter meat.') == ''
    assert p._extract_new_sentences('So this is sea otter meat. l') == ''


def test_speaker_tile_turns_the_feature_and_dubbing_on(qapp, monkeypatch):
    from lingolay.core.config import get_settings
    from lingolay.tts import game_audio
    from lingolay.ui import main_window as mw
    monkeypatch.setattr(game_audio, 'is_supported', lambda: True)
    started = []
    monkeypatch.setattr(mw.MainWindow, '_on_tts_toggle', lambda self, checked: started.append(checked))
    get_settings().tts.match_speaker = False
    get_settings().tts.match_speaker_seen = False
    w = mw.MainWindow()
    tile = w._speaker_tile
    assert tile.switch.isEnabled() and tile._badge.isVisibleTo(tile)
    tile.switch.setChecked(True)  # the user flips the switch
    assert get_settings().tts.match_speaker and get_settings().tts.match_speaker_seen
    assert w._chk_match.isChecked()  # the settings checkbox follows
    assert started == [True]  # dubbing was turned on with it
    assert not tile._badge.isVisibleTo(tile)  # NEW badge is gone after the first use
    tile.switch.setChecked(False)
    assert not get_settings().tts.match_speaker
    w._hotkeys.stop()
    w._overlay.close()
    w._region_selector.close()
    w.deleteLater()
    qapp.processEvents()


def test_voice_picker_lists_the_target_language_voices_and_saves_the_choice(qapp, monkeypatch):
    from lingolay.core.config import get_settings
    from lingolay.ui import main_window as mw
    s = get_settings()
    monkeypatch.setattr(s, 'target_lang', 'hi')
    monkeypatch.setattr(s.tts, 'voices', {})
    w = mw.MainWindow()
    combo = w._cmb_voice
    assert [combo.itemData(i) for i in range(combo.count())] == ['hi_IN-pratham-medium', 'hi_IN-priyamvada-medium', 'hi_IN-rohan-medium']
    assert combo.currentData() == 'hi_IN-pratham-medium' and combo.isEnabled()
    combo.setCurrentIndex(2)
    w._apply_tts_settings()
    assert s.tts.voices['hi'] == 'hi_IN-rohan-medium'
    assert w._dubbing_voice('hi') == 'hi_IN-rohan-medium'
    monkeypatch.setattr(s.tts, 'voices', {'hi': 'not-a-voice'})
    assert w._dubbing_voice('hi') == 'hi_IN-pratham-medium'  # stale settings fall back to the default
    w._hotkeys.stop()
    w._overlay.close()
    w._region_selector.close()
    w.deleteLater()
    qapp.processEvents()


def test_black_capture_warns_once(qapp, monkeypatch):
    import numpy as np

    from lingolay.core import pipeline as pl
    p = pl.Pipeline(qapp)
    now = [100.0]
    monkeypatch.setattr(pl.time, 'monotonic', lambda: now[0])
    warned = []
    p.capture_black.connect(lambda: warned.append(1))
    black, game = np.zeros((90, 160, 3), np.uint8), np.full((90, 160, 3), 80, np.uint8)
    p._check_black(black)
    now[0] += 4
    p._check_black(game)  # a real frame in between resets the timer
    now[0] += 1
    p._check_black(black)
    now[0] += pl.BLACK_HINT_SECONDS - 1
    p._check_black(black)
    assert warned == []
    now[0] += 2
    p._check_black(black)
    now[0] += 30
    p._check_black(black)
    assert warned == [1]  # once per run


class _DummyOCR:
    def __init__(self, text=''):
        self.text = text
        self.last_latency_ms = 5

    def recognize(self, img):
        return self.text


def _setup_pipeline_for_test(p, ocr_text='', monkeypatch=None, now_box=None):
    import numpy as np

    from lingolay.capture.screen import CaptureFrame
    from lingolay.core import pipeline as pl
    p._ocr = _DummyOCR(ocr_text)
    p._status.is_running = True
    if monkeypatch and now_box:
        monkeypatch.setattr(pl.time, 'time', lambda: now_box[0])

    def send(text=None, pixel_val=50):
        if text is not None:
            p._ocr.text = text
        img = np.full((64, 64, 3), pixel_val, dtype=np.uint8)
        frame = CaptureFrame(image=img, timestamp=now_box[0] if now_box else 100.0, monitor_index=0, capture_latency_ms=1)
        p._on_frame(frame)

    return send


def test_subtitle_cleared_after_400ms_blank_frames(qapp, monkeypatch):
    from lingolay.core.pipeline import Pipeline
    now = [1000.0]
    p = Pipeline(qapp)
    send = _setup_pipeline_for_test(p, 'Hello world', monkeypatch, now)

    cleared = []
    p.subtitle_cleared.connect(lambda: cleared.append(1))

    # 1. Text is on screen and translated
    send('Hello world', pixel_val=50)
    p._on_translation('Merhaba dunya', req_gen=p._subtitle_generation)
    assert p.subtitle_visible

    # Empty frames start
    now[0] += 0.1
    send('', pixel_val=60)  # new pixel so OCR runs, sees empty
    assert cleared == []
    assert p.subtitle_visible

    # Reach 400ms
    now[0] += 0.4
    send('', pixel_val=70)
    assert cleared == [1]
    assert not p.subtitle_visible
    # Further empty frames do not emit again
    now[0] += 0.5
    send('', pixel_val=80)
    assert cleared == [1]


def test_single_blank_frame_then_text_no_signal(qapp, monkeypatch):
    from lingolay.core.pipeline import Pipeline
    now = [1000.0]
    p = Pipeline(qapp)
    send = _setup_pipeline_for_test(p, 'First subtitle', monkeypatch, now)

    cleared = []
    p.subtitle_cleared.connect(lambda: cleared.append(1))

    send('First subtitle', pixel_val=50)
    p._on_translation('Ilk altyazi', req_gen=p._subtitle_generation)
    assert p.subtitle_visible

    # One blank frame (e.g. 100ms)
    now[0] += 0.1
    send('', pixel_val=60)
    assert cleared == []

    # Next frame text appears again
    now[0] += 0.1
    send('Second subtitle', pixel_val=70)
    assert cleared == []

    # Even after 1s from the first text, text is still on screen so no clear
    now[0] += 1.0
    send('Second subtitle', pixel_val=70)  # frame diff
    assert cleared == []


def test_static_frame_diff_screen_with_text_for_2s_no_signal(qapp, monkeypatch):
    from lingolay.core.pipeline import Pipeline
    now = [1000.0]
    p = Pipeline(qapp)
    send = _setup_pipeline_for_test(p, 'Static subtitle', monkeypatch, now)

    cleared = []
    p.subtitle_cleared.connect(lambda: cleared.append(1))

    send('Static subtitle', pixel_val=50)
    p._on_translation('Sabit altyazi', req_gen=p._subtitle_generation)
    assert p.subtitle_visible

    # 2 seconds with identical frames (diff < FRAME_DIFF_THRESHOLD)
    for _ in range(10):
        now[0] += 0.2
        send(pixel_val=50)

    assert cleared == []
    assert p.subtitle_visible


def test_static_empty_screen_clears_after_timeout(qapp, monkeypatch):
    from lingolay.core.pipeline import Pipeline
    now = [1000.0]
    p = Pipeline(qapp)
    send = _setup_pipeline_for_test(p, 'Line will vanish', monkeypatch, now)

    cleared = []
    p.subtitle_cleared.connect(lambda: cleared.append(1))

    send('Line will vanish', pixel_val=50)
    p._on_translation('Satir kaybolacak', req_gen=p._subtitle_generation)
    assert p.subtitle_visible

    # First blank frame sets _last_ocr_had_text = False
    now[0] += 0.1
    send('', pixel_val=60)
    assert cleared == []

    # Subsequent frames are static empty (frame-diff path with pixel_val=60)
    now[0] += 0.4
    send('', pixel_val=60)
    assert cleared == [1]
    assert not p.subtitle_visible


def test_garbage_and_own_translation_not_counted_as_text(qapp, monkeypatch):
    from lingolay.core.pipeline import Pipeline
    now = [1000.0]
    p = Pipeline(qapp)
    send = _setup_pipeline_for_test(p, 'Real dialog', monkeypatch, now)

    cleared = []
    p.subtitle_cleared.connect(lambda: cleared.append(1))

    send('Real dialog', pixel_val=50)
    p._on_translation('Gercek diyalog', req_gen=p._subtitle_generation)
    assert p.subtitle_visible

    # Send garbage / UI noise / own translation
    now[0] += 0.1
    send('12:45', pixel_val=60)  # UI noise / garbage
    assert not p._last_ocr_had_text

    now[0] += 0.2
    send('Gercek diyalog', pixel_val=70)  # own translation
    assert not p._last_ocr_had_text

    # Wait out 400ms from the last real text
    now[0] += 0.3
    send('12:45', pixel_val=80)
    assert cleared == [1]
    assert not p.subtitle_visible


def test_translation_arrives_after_text_gone(qapp, monkeypatch):
    from lingolay.core.pipeline import Pipeline
    now = [1000.0]
    p = Pipeline(qapp)
    send = _setup_pipeline_for_test(p, 'Vanishing fast', monkeypatch, now)

    translations = []
    p.translation_ready.connect(lambda txt: translations.append(txt))

    # Capture text and trigger dispatch
    send('Vanishing fast', pixel_val=50)
    req_gen = p._subtitle_generation

    # Text disappears and clears before translation returns
    now[0] += 0.1
    send('', pixel_val=60)
    now[0] += 0.8
    send('', pixel_val=70)
    assert not p.subtitle_visible

    # Translation finally returns with old req_gen
    p._on_translation('Hizli kaybolan', req_gen=req_gen)
    assert not p.subtitle_visible
    assert translations == ['Hizli kaybolan']


def test_dialogue_retranslated_after_cleared(qapp, monkeypatch):
    from lingolay.core.pipeline import Pipeline
    now = [1000.0]
    p = Pipeline(qapp)
    send = _setup_pipeline_for_test(p, 'Hello again.', monkeypatch, now)

    dispatched = []
    monkeypatch.setattr(p, '_extract_new_sentences', lambda txt: txt)
    if p._translation_worker is None:
        class DummyWorker:
            translator = None
            def request_translation(self, txt, gen):
                dispatched.append((txt, gen))
        p._translation_worker = DummyWorker()

    now[0] += 0.3
    send('Hello again.', pixel_val=50)
    now[0] += 0.3
    send('Hello again.', pixel_val=51)
    p._on_translation('Tekrar merhaba.', req_gen=p._subtitle_generation)
    assert len(dispatched) == 1

    # Text disappears and clears
    now[0] += 0.1
    send('', pixel_val=60)
    now[0] += 0.8
    send('', pixel_val=70)
    assert not p.subtitle_visible

    # Same dialogue reappears later
    now[0] += 1.0
    now[0] += 0.3
    send('Hello again.', pixel_val=80)
    now[0] += 0.3
    send('Hello again.', pixel_val=81)
    assert len(dispatched) == 2


def test_subtitle_clear_disabled_emits_no_signal(qapp, monkeypatch):
    from lingolay.core.config import get_settings
    from lingolay.core.pipeline import Pipeline
    monkeypatch.setattr(get_settings(), 'subtitle_clear_enabled', False)

    now = [1000.0]
    p = Pipeline(qapp)
    send = _setup_pipeline_for_test(p, 'Never clear', monkeypatch, now)

    cleared = []
    p.subtitle_cleared.connect(lambda: cleared.append(1))

    send('Never clear', pixel_val=50)
    p._on_translation('Asla silme', req_gen=p._subtitle_generation)
    assert p.subtitle_visible

    now[0] += 0.1
    send('', pixel_val=60)
    now[0] += 2.0
    send('', pixel_val=70)

    assert cleared == []
    assert p.subtitle_visible


def test_overlay_speaker_font_scaled_and_hidden_when_none(qtbot):
    from lingolay.core.config import get_settings
    from lingolay.overlay.window import OverlayWindow
    from lingolay.text.cleaning import subtitle_lines

    # Test subtitle_lines does not split ellipsis
    text_ellipsis = 'Wait... do not go.'
    assert subtitle_lines(text_ellipsis) == 'Wait... do not go.'

    # Test 3 sentences become 3 lines with single font
    three_sentences = 'First sentence. Second sentence! Third sentence?'
    lines = subtitle_lines(three_sentences)
    assert lines == 'First sentence.\nSecond sentence!\nThird sentence?'

    window = OverlayWindow()
    get_settings().overlay.font_size = 20
    window._base_font_size = 20
    qtbot.addWidget(window)

    # With speaker: speaker font size is max(11, int(scaled * 0.7))
    window.set_translation('Hello world.', speaker='Alice')
    scaled = window._get_scaled_font_size(len('Hello world.'))
    expected_speaker_pt = max(11, int(scaled * 0.7))
    assert not window._speaker_label.isHidden()
    assert window._speaker_label.text() == 'Alice'
    assert f'font-size: {expected_speaker_pt}px' in window._speaker_label.styleSheet()

    # Without speaker: speaker label is hidden
    window.set_translation('Hello world.', speaker=None)
    assert window._speaker_label.isHidden()

    # Clear: clears speaker and text
    window.set_translation('Something', speaker='Bob')
    assert not window._speaker_label.isHidden()
    window.clear()
    assert window._current_text == ''
    assert window._current_speaker is None
    assert window._speaker_label.isHidden()
