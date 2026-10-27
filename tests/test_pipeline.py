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
