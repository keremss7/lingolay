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
