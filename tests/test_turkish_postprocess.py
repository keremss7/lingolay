from lingolay.text.turkish_postprocess import (
    apply_sfx_map,
    fix_sentence_capitalization,
    normalize_punctuation,
    post_process_turkish,
    remove_excessive_repeats,
    turkish_capitalize,
)


def test_turkish_capitalize_dotted_i():
    assert turkish_capitalize('istanbul') == 'İstanbul'
    assert turkish_capitalize('ılık') == 'Ilık'


def test_sfx_tags_are_translated():
    assert apply_sfx_map('[LAUGHING] Tamam') == '[GÜLÜYOR] Tamam'


def test_repeats_are_trimmed_but_reduplication_is_kept():
    assert remove_excessive_repeats('Will? Will? Will? Will?', 2) == 'Will? Will?'
    assert remove_excessive_repeats('yavaş yavaş gel', 2) == 'yavaş yavaş gel'


def test_punctuation_and_capitalization():
    assert normalize_punctuation('merhaba , nasılsın ?') == 'merhaba, nasılsın?'
    assert fix_sentence_capitalization('evet. işte bu!') == 'Evet. İşte bu!'


def test_full_pipeline():
    assert post_process_turkish('beni takip edin , köprü çökmek üzere !') == 'Beni takip edin, köprü çökmek üzere!'
