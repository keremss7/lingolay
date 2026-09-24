import json
import re
import string

from lingolay.i18n import LOCALES_DIR
from lingolay.languages import LANGUAGES, display_name, get_language
from lingolay.models.manifest import MODELS, VOICE_TABLE, VOICES, get_model, voice_for_language


def test_every_language_has_codes():
    for code, lang in LANGUAGES.items():
        assert lang.code == code
        assert re.fullmatch(r'[a-z]{3}_[A-Z][a-z]{3}', lang.nllb)
        assert lang.ocr


def test_get_language_falls_back_to_english():
    assert get_language('xx').code == 'en'
    assert 'Türkçe' in display_name('tr')


def test_every_language_has_a_dubbing_voice():
    for code in LANGUAGES:
        assert voice_for_language(code), code
    assert set(VOICES) == {v for v, _ in VOICE_TABLE.values()}


def test_model_manifest_is_pinned_and_verified():
    for info in list(MODELS.values()) + list(VOICES.values()):
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
