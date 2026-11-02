import pytest

from lingolay.text.cleaning import clean_ocr_text, has_turkish_content, is_garbage, is_ui_noise, normalize_text, seq_ratio, split_speaker


@pytest.mark.parametrize('raw, expected', [
    ("I'II be back.", "I'll be back."),
    ("we'II see", "we'll see"),
    ('l think so', 'I think so'),
    ('don t go', "don't go"),
])
def test_clean_fixes_common_english_ocr_errors(raw, expected):
    assert clean_ocr_text(raw, 'en') == expected


def test_clean_removes_bracketed_sfx_inside_dialogue():
    assert clean_ocr_text('[DOOR OPENS] Who is there?', 'en') == 'Who is there?'


def test_clean_keeps_non_latin_text():
    assert clean_ocr_text('お前はもう死んでいる', 'ja') == 'お前はもう死んでいる'
    assert clean_ocr_text('Где ключи?', 'ru') == 'Где ключи?'


def test_clean_returns_empty_without_letters():
    assert clean_ocr_text('12:45 ---', 'en') == ''


def test_normalize_text_collapses_whitespace_and_quotes():
    assert normalize_text('  Hello\n  “world”  ') == 'Hello "world"'


@pytest.mark.parametrize('text', ['12:34', 'HD', '1080p', '', '||', '42'])
def test_is_garbage_rejects_ui_noise(text):
    assert is_garbage(text, 'en', 'tr')


def test_is_garbage_accepts_normal_dialogue():
    assert not is_garbage('Where did you put the keys?', 'en', 'tr')


def test_own_turkish_overlay_is_rejected_only_when_target_is_turkish():
    own = 'Anahtarları nereye koydun, lütfen söyle'
    assert has_turkish_content(own)
    assert is_garbage(own, 'en', 'tr')
    assert not is_garbage(own, 'tr', 'en')


def test_non_latin_sources_are_not_treated_as_garbage():
    assert not is_garbage('お前はもう死んでいる', 'ja', 'en')
    assert not is_garbage('Где ключи?', 'ru', 'tr')
    # ...but Cyrillic noise in an English subtitle is rejected
    assert is_garbage('Где ключи?', 'en', 'tr')


def test_ui_noise_does_not_match_times_inside_sentences():
    assert is_ui_noise('10:45')
    assert not is_ui_noise('Meet me at 9:30 tomorrow')


def test_seq_ratio_tolerates_ocr_fusion():
    assert seq_ratio('So this is sea otter meat', 'So this islsa otter meat') > 0.85
    assert seq_ratio('hello', 'goodbye') < 0.5


def test_split_speaker_colon_format():
    speaker, dialogue = split_speaker('Kenji: Open the door')
    assert speaker == 'Kenji'
    assert dialogue == 'Open the door'


def test_split_speaker_multiline_formats():
    speaker, dialogue = split_speaker('Gatekeeper\nHow can this happen?')
    assert speaker == 'Gatekeeper'
    assert dialogue == 'How can this happen?'

    speaker, dialogue = split_speaker('Voice from the Gauntlet\nCome closer.')
    assert speaker == 'Voice from the Gauntlet'
    assert dialogue == 'Come closer.'

    speaker, dialogue = split_speaker('boss —\nRun!')
    assert speaker == 'boss'
    assert dialogue == 'Run!'


def test_split_speaker_no_speaker():
    assert split_speaker('Wait!\nGo now.') == (None, 'Wait!\nGo now.')
    assert split_speaker('Yes, sir\nRight away.') == (None, 'Yes, sir\nRight away.')
    assert split_speaker('13:45\nHello there.') == (None, '13:45\nHello there.')
    assert split_speaker('Open the door.') == (None, 'Open the door.')
