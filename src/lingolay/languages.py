"""
Supported languages — the single source of truth.

To add a language, add a row to this table (NLLB supports 200 languages:
https://github.com/facebookresearch/flores/blob/main/flores200/README.md#languages-in-flores-200).
For dubbing, add a Piper voice to VOICE_TABLE in models/manifest.py.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str          # ISO 639-1 (internal key)
    name: str          # English name
    native: str        # Name in the language itself
    nllb: str          # NLLB-200 / FLORES-200 code
    ocr: str           # Windows OCR (BCP-47) tag
    latin: bool        # Latin script? (for OCR cleanup rules)


LANGUAGES = {
    lang.code: lang for lang in (
        Language('en', 'English', 'English', 'eng_Latn', 'en-US', True),
        Language('tr', 'Turkish', 'Türkçe', 'tur_Latn', 'tr-TR', True),
        Language('de', 'German', 'Deutsch', 'deu_Latn', 'de-DE', True),
        Language('fr', 'French', 'Français', 'fra_Latn', 'fr-FR', True),
        Language('es', 'Spanish', 'Español', 'spa_Latn', 'es-ES', True),
        Language('pt', 'Portuguese', 'Português', 'por_Latn', 'pt-BR', True),
        Language('it', 'Italian', 'Italiano', 'ita_Latn', 'it-IT', True),
        Language('nl', 'Dutch', 'Nederlands', 'nld_Latn', 'nl-NL', True),
        Language('pl', 'Polish', 'Polski', 'pol_Latn', 'pl-PL', True),
        Language('ru', 'Russian', 'Русский', 'rus_Cyrl', 'ru-RU', False),
        Language('uk', 'Ukrainian', 'Українська', 'ukr_Cyrl', 'uk-UA', False),
        Language('ar', 'Arabic', 'العربية', 'arb_Arab', 'ar-SA', False),
        Language('zh', 'Chinese (Simplified)', '简体中文', 'zho_Hans', 'zh-Hans-CN', False),
        Language('ja', 'Japanese', '日本語', 'jpn_Jpan', 'ja-JP', False),
        Language('ko', 'Korean', '한국어', 'kor_Hang', 'ko-KR', False),
    )
}


def get_language(code):
    return LANGUAGES.get(code) or LANGUAGES['en']


def is_latin(code):
    return get_language(code).latin


def display_name(code):
    lang = get_language(code)
    return lang.name if lang.name == lang.native else f'{lang.native} — {lang.name}'
