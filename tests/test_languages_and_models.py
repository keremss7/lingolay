import json
import re
import string

from lingolay.i18n import LOCALES_DIR
from lingolay.languages import LANGUAGES, display_name, get_language
from lingolay.models.manifest import AUX_MODELS, GENDER_VOICES, MODELS, VOICE_TABLE, VOICES, get_model, voice_for_language


def test_every_language_has_codes():
    for code, lang in LANGUAGES.items():
        assert lang.code == code
        assert re.fullmatch(r'[a-z]{3}_[A-Z][a-z]{3}', lang.nllb)
        assert lang.ocr


def test_get_language_falls_back_to_english():
    assert get_language('xx').code == 'en'
    assert 'Türkçe' in display_name('tr')


# Languages that translate fine but have no bundled-ready dubbing voice yet
TRANSLATION_ONLY = {'th'}


def test_every_language_has_a_dubbing_voice():
    for code in LANGUAGES:
        assert bool(voice_for_language(code)) == (code not in TRANSLATION_ONLY), code
    assert {v for v, _ in VOICE_TABLE.values()} <= set(VOICES)


def test_model_manifest_is_pinned_and_verified():
    for info in list(MODELS.values()) + list(VOICES.values()) + list(AUX_MODELS.values()):
        assert re.fullmatch(r'[0-9a-f]{40}', info.revision)
        big = [f for f in info.files if f.size > 1_000_000]
        assert big and all(f.sha256 and len(f.sha256) == 64 for f in big)
        assert info.url_for(info.files[0]).startswith('https://')
    assert get_model('fast').approx_size_mb > 500


def _placeholders(s):
    return {name for _, name, _, _ in string.Formatter().parse(s) if name}


def test_locale_files_are_valid_and_keep_placeholders():
    for path in LOCALES_DIR.glob('*.json'):
        data = json.loads(path.read_text(encoding='utf-8'))
        assert data.get('_meta.name'), path.name
        for src, dst in data.items():
            if src.startswith('_meta'):
                continue
            assert dst, f'{path.name}: empty translation for {src!r}'
            assert _placeholders(src) == _placeholders(dst), f'{path.name}: placeholder mismatch in {src!r}'


def test_system_locale_matches_regional_locale_files(monkeypatch):
    import lingolay.i18n as i18n
    langs = {'en': 'English', 'tr': 'Türkçe', 'pt-BR': 'Português (Brasil)'}
    monkeypatch.setattr(i18n, 'available_languages', lambda: langs)
    assert i18n.match_language('pt_BR') == 'pt-BR'
    assert i18n.match_language('pt_PT') == 'pt-BR'
    assert i18n.match_language('tr_TR') == 'tr'
    assert i18n.match_language('de_DE') == 'en'


def test_gender_voices_cover_both_genders_with_downloadable_voices():
    for code, voices in GENDER_VOICES.items():
        assert code in LANGUAGES, code
        assert set(voices) == {'female', 'male'}, code
        assert voice_for_language(code) in {v.voice for v in voices.values()}, code  # default voice stays in use
        for gender, gv in voices.items():
            assert gv.voice in VOICES, (code, gv.voice)
            assert gv.transform in (None, 'female', 'male'), (code, gv)
            assert gv.transform in (None, gender), (code, gender, gv)  # a transform always moves toward its gender


def test_aux_model_downloads_from_a_pinned_release():
    info = get_model('gender')
    assert info.url_for(info.files[0]) == 'https://github.com/keremss7/lingolay/releases/download/models-gender-v1/gender_ecapa.onnx'


def test_voice_choices_per_language():
    from lingolay.models.manifest import VOICE_GENDERS, voices_for_language
    assert voices_for_language('hi') == ['hi_IN-pratham-medium', 'hi_IN-priyamvada-medium', 'hi_IN-rohan-medium']
    assert voices_for_language('tr') == ['tr_TR-dfki-medium']
    assert voices_for_language('xx') == []
    assert set(VOICE_GENDERS) == set(VOICES)  # every downloadable voice has a known gender
    assert set(VOICE_GENDERS.values()) == {'female', 'male'}
