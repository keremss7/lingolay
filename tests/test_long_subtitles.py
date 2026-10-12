from lingolay.translation.nllb import NLLBTranslator

# Issue #12: a three-line game subtitle (187 chars) lost its last words
LONG = ('The Seven Shus assembled once again and, at tremendous cost, destroyed it, with only "Lantern" '
        'surviving among them. Their ally Oxia suffered heavy losses, and Bailu Youyun lost her life.')


def _echo_translator(monkeypatch):
    monkeypatch.setattr(NLLBTranslator, '_init_model', lambda self: None)
    tr = NLLBTranslator(from_lang='en', to_lang='ru', model_dir='.', post_process=False)
    tr._ready = True
    monkeypatch.setattr(tr, '_translate_with_retry', lambda text: (text, None))
    return tr


def test_long_subtitle_reaches_the_model_whole(monkeypatch):
    tr = _echo_translator(monkeypatch)
    assert tr.translate(LONG).text == LONG


def test_runaway_text_is_cut_on_a_word_boundary(monkeypatch):
    tr = _echo_translator(monkeypatch)
    out = tr.translate('word ' * 200).text
    assert len(out) <= NLLBTranslator.MAX_TEXT_LENGTH
    assert out.endswith('word')
