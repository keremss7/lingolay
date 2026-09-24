"""Turkish-specific post-processing of machine-translated subtitles (only used when the target is Turkish)."""
import re

# English SFX tags → Turkish equivalents

SFX_MAP = {
    '[LAUGHING]': '[GÜLÜYOR]',
    '[LAUGHTER]': '[KAHKAHA]',
    '[CRYING]': '[AĞLIYOR]',
    '[SCREAMING]': '[ÇIĞLIK]',
    '[GASPS]': '[NEFES NEFESE]',
    '[SIGHS]': '[İÇ ÇEKİYOR]',
    '[COUGHS]': '[ÖKSÜRÜYOR]',
    '[CLAPPING]': '[ALKIŞ]',
    '[MUSIC]': '[MÜZİK]',
    '[MUSIC PLAYING]': '[MÜZİK ÇALIYOR]',
    '[APPLAUSE]': '[ALKIŞ]',
    '[CHEERING]': '[TEZAHÜRAT]',
    '[SILENCE]': '[SESSİZLİK]',
    '[KNOCKING]': '[KAPI ÇALIYOR]',
    '[PHONE RINGING]': '[TELEFON ÇALIYOR]',
    '[DOOR CLOSES]': '[KAPI KAPANIYOR]',
    '[DOOR OPENS]': '[KAPI AÇILIYOR]',
    '[FOOTSTEPS]': '[AYAK SESLERİ]',
    '[GUNSHOT]': '[SİLAH SESİ]',
    '[EXPLOSION]': '[PATLAMA]',
    '[THUNDER]': '[GÖK GÜRÜLTÜSÜ]',
    '[WHISPERS]': '[FISILDIYOR]',
    '[INDISTINCT]': '[BELİRSİZ]',
    '[INAUDIBLE]': '[DUYULMUYOR]',
    '[NARRATOR]': '[ANLATICI]',
    '[SOBBING]': '[HIÇKIRARAK AĞLIYOR]',
    '[SNIFFLES]': '[BURNUNU ÇEKİYOR]',
    '[GROANS]': '[İNLİYOR]',
    '[GRUNTS]': '[HOMURDANIYOR]',
}

_SFX_PATTERNS = [(re.compile(re.escape(eng), re.IGNORECASE), tr) for eng, tr in SFX_MAP.items()]
_TURKISH_UPPER_MAP = str.maketrans('iığüşöç', 'İIĞÜŞÖÇ')


def apply_sfx_map(text):
    """Replace English SFX tags with their Turkish equivalents."""
    if not text:
        return text
    for pattern, tr in _SFX_PATTERNS:
        text = pattern.sub(tr, text)
    return text


def turkish_capitalize(text):
    """Capitalize the first letter using Turkish rules (i→İ, ı→I)."""
    if not text:
        return text
    first = text[0]
    rest = text[1:]
    if first == 'i':
        return 'İ' + rest
    if first == 'ı':
        return 'I' + rest
    return first.translate(_TURKISH_UPPER_MAP).upper() + rest


def fix_sentence_capitalization(text):
    """Capitalize sentence starts using Turkish rules."""
    if not text:
        return text
    parts = re.split('([.!?]+\\s*)', text)
    result = []
    capitalize_next = True
    for part in parts:
        if re.match('^[.!?]+\\s*$', part):
            result.append(part)
            capitalize_next = True
        elif capitalize_next and part:
            result.append(turkish_capitalize(part))
            capitalize_next = False
        else:
            result.append(part)
    return ''.join(result)


def normalize_punctuation(text):
    """Normalize punctuation."""
    if not text:
        return text
    result = text
    result = re.sub('\\s+([.!?,;:])', '\\1', result)
    result = re.sub('([.!?,;:])(\\w)', '\\1 \\2', result)
    result = re.sub('\\.{2,}', '...', result)
    result = re.sub('([!?])\\1+', '\\1', result)
    result = re.sub('\\s{2,}', ' ', result)
    result = result.replace('\u201c', '"').replace('\u201d', '"')
    result = result.replace('‘', "'").replace('’', "'")
    return result.strip()


def remove_excessive_repeats(text, max_repeats=3):
    """
    Trim excessive word repetition: 'Will? Will? Will? Will?' → 'Will? Will?'

    NLLB sometimes hallucinates huge repetitions (e.g. after tags like
    [name softly]). With max_repeats=2, legitimate Turkish reduplications such
    as 'yavaş yavaş' are KEPT; the 3rd and later repeats are dropped.
    """
    if not text:
        return text
    tokens = re.findall('\\S+', text)
    if not tokens:
        return text
    result_tokens = []
    current_stripped = None
    repeat_count = 0
    for token in tokens:
        stripped = re.sub('[^\\w]', '', token).lower()
        if stripped == current_stripped:
            repeat_count += 1
            if repeat_count <= max_repeats:
                result_tokens.append(token)
        else:
            current_stripped = stripped
            repeat_count = 1
            result_tokens.append(token)
    result = ' '.join(result_tokens)
    result = re.sub('\\b(\\w+)(\\s*[-–—]\\s*\\1){2,}', '\\1', result, flags=re.IGNORECASE)
    return result


def remove_phrase_repeats(text):
    """
    Remove repeated phrases:
    'konuş benimle konuş benimle' → 'konuş benimle'
    """
    if not text:
        return text
    for _ in range(3):
        text = re.sub('\\b(\\w+\\s+\\w+)(\\s+\\1)+\\b', '\\1', text, flags=re.IGNORECASE)
        text = re.sub('\\b(\\w+\\s+\\w+\\s+\\w+)(\\s+\\1)+\\b', '\\1', text, flags=re.IGNORECASE)
    return text


def post_process_turkish(text):
    """
    Full post-processing pipeline for Turkish translations.
    Order matters: SFX → punctuation → repetition cleanup → capitalization.
    """
    if not text:
        return text
    result = apply_sfx_map(text)
    result = normalize_punctuation(result)
    result = remove_excessive_repeats(result, 2)
    result = remove_phrase_repeats(result)
    result = re.sub('\\s{2,}', ' ', result).strip()
    result = fix_sentence_capitalization(result)
    if result and result[0].islower():
        result = turkish_capitalize(result)
    return result
