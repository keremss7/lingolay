"""
OCR text cleaning and subtitle stabilization.

`clean_ocr_text` fixes common OCR mistakes, `is_garbage` rejects noise and UI
text, and `TextStabilizer` waits until a subtitle has "settled" on screen before
it is sent to the translator.
"""
import collections
import difflib
import logging
import re
import time
from dataclasses import dataclass

# Used to detect when OCR accidentally reads our own Turkish overlay
TURKISH_CHARS = set('şŞğĞüÜöÖçÇıİ')
TURKISH_WORDS = ['merhaba', 'nasılsın', 'teşekkür', 'evet', 'hayır', 'tamam', 'için', 'değil', 'oldu', 'olur', 'gibi', 'neden', 'nasıl', 'nerede', 'zaman', 'şimdi', 'sonra', 'önce', 'üzerinden', 'taşındı', 'kulüp', 'tanıştık', 'bilmiyordum', 'nişanlandı', 'yaklaşık', 'muhteşem', 'yazık', 'doğru', 'tatlım', 'hatırlıyor', 'musun', 'utangaç', 'dönersiniz', 'verirseniz', 'gersekten', 'üzgünüm', 'lütfen', 'müzik', 'ıslak', 'kurutma', 'ipucu', 'telefon', 'nedir', 'görünüm', 'herhangi', 'burada', 'ıyor', 'iyor', 'uyor', 'üyor', 'acak', 'ecek', 'mış', 'miş', 'muş', 'müş', 'bölüm', 'sezon', 'altyazı', 'çeviri', 'çevirmen', 'tarafından', 'karakter', 'aktif', 'değişir', 'sıkıştır', 'kapat', 'başlat', 'durdur', 'ayarlar', 'profil', 'cihaz', 'lisans', 'bizim', 'benim', 'senin', 'onun', 'bunu', 'şunu', 'ama', 'çünkü', 'kadar', 'daha', 'çok', 'var', 'yok', 'ile', 'bir']
UI_NOISE_PATTERNS = ['Q Ara', 'Ara$', '^ENG$', '^HD$', '\\d+:\\d+', '\\d+:\\d+:\\d+', '\\d+%', '^CC$', '^SUB$', '\\d+p$', '\\d+K$', '^LIVE$', '^PLAY$', '^PAUSE$', '\\[Music\\]', '\\[Musicl\\]', '\\(Music\\)', 'IMusic\\]', 'ILIusic\\]', '\\[Music$', '^Music\\]', 'uslC\\]', 'Mitglied werden', 'SPARKTV', '^[JDOol1\\.]$', '^\\d+$']
OCR_FIXES = [("\\bwe'II\\b", "we'll"), ("\\bWe'II\\b", "We'll"), ("\\bI'II\\b", "I'll"), ("\\byou'II\\b", "you'll"), ("\\bhe'II\\b", "he'll"), ("\\bshe'II\\b", "she'll"), ("\\bthey'II\\b", "they'll"), ("\\bthat'II\\b", "that'll"), ("\\bthere'II\\b", "there'll"), ('\\bIow\\b', 'low'), ('\\b3ut\\b', 'But'), ('\\b3e\\b', 'Be'), ('\\b1t\\b', 'It'), ('\\b0n\\b', 'On'), ('\\b0f\\b', 'Of'), ('\\b0r\\b', 'Or'), ('\\bl\\b', 'I'), ('\\bln\\b', 'In'), ('\\blt\\b', 'It'), ('\\bwlth\\b', 'with'), ('\\bthls\\b', 'this'), ('\\bhlm\\b', 'him'), ('\\bdon t\\b', "don't"), ('\\bcan t\\b', "can't"), ('\\bwon t\\b', "won't"), ('\\bdidn t\\b', "didn't"), ('\\bdoesn t\\b', "doesn't"), ('\\bwasn t\\b', "wasn't"), ('\\bisn t\\b', "isn't"), ('\\baren t\\b', "aren't"), ('\\bweren t\\b', "weren't"), ('\\bcouldn t\\b', "couldn't"), ('\\bwouldn t\\b', "wouldn't"), ('\\bshouldn t\\b', "shouldn't"), ('\\bhaven t\\b', "haven't"), ('\\bhasn t\\b', "hasn't"), ('\\bhadn t\\b', "hadn't"), ('\\bI m\\b', "I'm"), ('\\bI ve\\b', "I've"), ('\\bI ll\\b', "I'll"), ('\\bI d\\b', "I'd"), ('\\byou re\\b', "you're"), ('\\byou ve\\b', "you've"), ('\\byou ll\\b', "you'll"), ('\\bwe re\\b', "we're"), ('\\bwe ve\\b', "we've"), ('\\bthey re\\b', "they're"), ('\\bthey ve\\b', "they've"), ('\\bthat s\\b', "that's"), ('\\bit s\\b', "it's"), ('\\bwhat s\\b', "what's"), ('\\bwho s\\b', "who's"), ('\\blet s\\b', "let's"), ('\\bhere s\\b', "here's"), ('\\bthere s\\b', "there's"), ('[`´]', "'"), ('thelnternet', 'the Internet')]
logger = logging.getLogger(__name__)


def has_turkish_content(text):
    """
    Return True if the text likely contains Turkish.
    Used to detect when OCR is accidentally reading our own overlay.
    """
    if not text:
        return False
    char_hits = sum(1 for c in text if c in TURKISH_CHARS)
    if char_hits >= 2:
        return True
    text_lower = text.lower()
    word_hits = 0
    for word in TURKISH_WORDS:
        if len(word) >= 5:
            if word in text_lower:
                word_hits += 1
        else:
            if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
                word_hits += 1
        if word_hits >= 2:
            return True
    return char_hits >= 1 and word_hits >= 1


def normalize_text(text):
    """Normalize OCR text for comparison / cache key generation."""
    if not text:
        return ''
    text = text.strip()
    text = text.replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ')
    text = re.sub(' +', ' ', text)
    text = re.sub('\\.{2,}', '...', text)
    text = text.replace('“', '"').replace('”', '"')
    text = text.replace('‘', "'").replace('’', "'")
    text = re.sub('^[|l1]\\s*', '', text)
    text = re.sub('\\s*[|l1]$', '', text)
    return text


def clean_ocr_text(text, source_lang='en'):
    """Fix common OCR mistakes and normalize formatting."""
    if not text:
        return ''
    from lingolay.languages import is_latin
    latin = is_latin(source_lang)
    english = source_lang == 'en'
    result = text
    # Strip our own UI labels in case the capture region overlaps this window
    _own_ui = re.compile('\\b\\w*(?:ublaj|dublaj|altyaz|raporla|kontrol|türkqe|türkçe|durdur|başlat|baslat|kaydet|ayarlar|profil|önizleme|onizleme|görünüm|goruntu|hakkında|yardım|kısayol|kisayol)\\w*\\b|(?:film\\s*/\\s*dizi|bölge\\s*se\\w*|oyun\\s*m[oö]d\\w*|sesli\\s*okuma|tam\\s*/\\s*yard)', re.IGNORECASE)
    if latin and _own_ui.search(result):
        lines_out = []
        for ln in result.split('\n'):
            stripped = _own_ui.sub(' ', ln)
            stripped = re.sub('\\s{2,}', ' ', stripped).strip(' _-•:\t')
            if re.search('[A-Za-z]{3,}', stripped):
                lines_out.append(stripped)
        result = '\n'.join(lines_out)
    result = re.sub('(?m)^\\s*(?:>>?|»)\\s*', '', result)
    result = re.sub('(^|\\s)-([CE])([a-zA-Z][a-zA-Z\\s]*)\\]', '\\1-[\\3]', result)
    result = re.sub('(?:^|(?<=\\s))([EC])([a-zA-Z][a-zA-Z\\s]+)\\]', lambda m: '[' + m.group(2) + ']', result)
    bracket_only_re = re.compile('^\\s*[-\\s]*(\\[[^\\]]+\\]\\s*[-\\s]*\\n?)+\\s*$')
    if re.match('^\\s*\\[[^\\]]+\\]\\s*$', result):
        result = re.sub('^\\s*\\[([^\\]]+)\\]\\s*$', '\\1', result)
    elif bracket_only_re.match(result):
        parts = re.findall('\\[([^\\]]+)\\]', result)
        result = '. '.join(p.strip() for p in parts if p.strip()) + '.'
    else:
        result = re.sub('\\[[^\\]]+\\]\\s*', ' ', result)
    result = re.sub('(?<!\\[)\\)', '', result)
    if english:
        # English-specific OCR errors (I'II → I'll, l → I, merged CamelCase words)
        result = re.sub('\\b11m\\b', "I'm", result)
        result = re.sub('([A-Z])([A-Z][a-z])', '\\1 \\2', result)
        for pattern, replacement in OCR_FIXES:
            flags = 0 if "'II" in pattern else re.IGNORECASE
            result = re.sub(pattern, replacement, result, flags=flags)
        result = re.sub('([a-z])([A-Z])', '\\1 \\2', result)
    result = re.sub('([.!?,])([A-Za-z])', '\\1 \\2', result)
    result = re.sub('(?<=[a-zA-Z])-(?=[A-Z][a-z])', ' - ', result)
    result = re.sub('(^|\\s)-(?=[A-Z][a-z])', '\\1- ', result)
    if english:
        result = re.sub('[åßàèéêë€£¥¢©®™°±²³´µ¶·¹º»¼½¾@\\\\]', '', result)
    else:
        result = re.sub('[€£¥¢©®™°±²³µ¶·¹º»¼½¾@\\\\]', '', result)
    result = result.replace('•', ' ')
    result = result.replace('–', '-').replace('—', '-')
    result = result.replace('„', '')
    result = result.replace('\u201c', '"').replace('\u201d', '"')
    result = re.sub('"[ \\t]*,', ',', result)
    result = re.sub(',[ \\t]*"', ',', result)
    result = re.sub('\\.[ \\t]*"', '.', result)
    result = re.sub('![ \\t]*"', '!', result)
    result = re.sub('\\?[ \\t]*"', '?', result)
    result = re.sub(' +', ' ', result)
    result = re.sub('(?m)^(\\s*-\\s+){2,}', '- ', result)
    result = re.sub('(\\n)(\\s*-\\s+){2,}', '\\1- ', result)
    result = result.strip()
    if not any(c.isalpha() for c in result):
        return ''
    return result


def is_ui_noise(text):
    """
    Return True if the text looks like a UI element or known noise.

    Patterns WITHOUT an anchor (^/$) must match the whole text, so a time like
    '9:30 AM' inside a sentence is not treated as UI noise.
    """
    if not text:
        return True
    for pattern in UI_NOISE_PATTERNS:
        if pattern.startswith('^') or pattern.endswith('$'):
            if re.search(pattern, text, re.IGNORECASE):
                return True
        else:
            if re.fullmatch(r'\s*' + pattern + r'\s*', text, re.IGNORECASE):
                return True
    return False


def is_garbage(text, source_lang='en', target_lang='tr'):
    """
    Return True if the text is clearly garbage / not a subtitle line.
    Combines several heuristics; script-dependent rules only apply to Latin sources.
    """
    if not text:
        return True
    text = text.strip()
    if len(text) < 2:
        return True
    if len(text) < 4:
        stripped = text.replace(' ', '')
        if not any(c.isalpha() for c in stripped):
            return True
        if len(set(stripped.lower())) < 2:
            return True
    from lingolay.languages import is_latin
    latin = is_latin(source_lang)
    # Ignore our own Turkish overlay (only when the target is TR and the source is not)
    if target_lang == 'tr' and source_lang != 'tr' and has_turkish_content(text):
        return True
    if is_ui_noise(text):
        return True
    if re.search(r'\[?Music[l\]]?\]?', text, re.IGNORECASE):
        clean = re.sub(r'\[?Music[l\]]?\]?', '', text, flags=re.IGNORECASE).strip()
        if len(clean) < 10:
            return True
    if re.match(r'^[\W\d_]+$', text):
        return True
    for token in text.split():
        if token.count("'") >= 2:
            if re.search(r'(?<=.)[A-Z]', token):
                return True
    unique_chars = len(set(text.replace(' ', '')))
    if len(text) > 5 and unique_chars < 3:
        return True
    words = text.lower().split()
    if len(words) >= 6 and len(set(words)) <= 2:
        return True
    if not latin:
        # Non-Latin scripts: the letter/special-character ratio rules do not apply
        return False
    special = len(re.findall(r'[^a-zA-Z0-9À-ÿ\s.,!?\'"\-\[\]\(\)]', text))
    if len(text) > 5 and special / len(text) > 0.25:
        return True
    letters = len(re.findall('[a-zA-Z]', text))
    if len(text) > 12 and letters / len(text) < 0.4:
        return True
    non_latin = 0
    for ch in text:
        cp = ord(ch)
        # Cyrillic, Arabic, Hebrew, Kana, CJK, Hangul — unexpected in a Latin-script source
        if 1024 <= cp <= 1279 or 1536 <= cp <= 1791 or 1424 <= cp <= 1535 or 12352 <= cp <= 12543 or 19968 <= cp <= 40959 or 44032 <= cp <= 55215:
            non_latin += 1
    alpha = sum(1 for c in text if c.isalpha())
    if non_latin > 0 and alpha > 0 and non_latin / alpha > 0.05:
        return True
    return False


def seq_ratio(a, b):
    """
    Whitespace-free, lower-case character sequence similarity (0-1).

    The metric most robust to OCR's shifted/merged errors (is sea → islsa).
    Used to match different readings of the same subtitle.
    """
    ca = a.lower().replace(' ', '')
    cb = b.lower().replace(' ', '')
    if not ca:
        return 0.0
    return difflib.SequenceMatcher(None, ca, cb).ratio()


@dataclass
class StabilizedText:
    text: str = ''
    normalized: str = ''
    is_stable: bool = False
    consecutive_count: int = 0


class TextStabilizer:
    """Settles OCR output over time; only 'settled' subtitles are sent to the translator."""

    _SENTENCE_END = ('.', '!', '?', '…', '。', '！', '？')

    def __init__(self, stability_count=1, min_length=2, cooldown_ms=0, text_expiry_sec=4, settle_ms=280, source_lang='en', target_lang='tr'):
        self._source_lang = source_lang
        self._target_lang = target_lang
        self._stability_count = stability_count
        self._min_length = min_length
        self._cooldown_ms = cooldown_ms
        self._text_expiry_sec = text_expiry_sec
        self._settle_ms = settle_ms
        self._grow_factor = 2.5
        self._max_settle_ms = 2500
        self._fast_settle_ms = 90
        self._arrival_history = collections.deque(maxlen=8)
        self._episode_grew = False
        self._episode_started = False
        self._incremental_mode = False
        self._last_normalized = ''
        self._last_cleaned = ''
        self._consecutive_count = 0
        self._last_change_time = 0.0
        self._last_translation_time = 0.0
        self._translated_texts = {}

    def update_settings(self, stability_count=None, min_length=None, cooldown_ms=None, text_expiry_sec=None, settle_ms=None):
        if stability_count is not None:
            self._stability_count = stability_count
        if min_length is not None:
            self._min_length = min_length
        if cooldown_ms is not None:
            self._cooldown_ms = cooldown_ms
        if text_expiry_sec is not None:
            self._text_expiry_sec = text_expiry_sec
        if settle_ms is not None:
            self._settle_ms = settle_ms

    @staticmethod
    def _is_growth(old, new):
        """
        Is `new` a grown version of `old`? (typewriter / scrolling subtitle signal)

        It is growth if the beginning matches and the text got noticeably longer;
        the beginning is compared fuzzily to tolerate OCR jitter.
        """
        if not old:
            return False
        if len(new) <= len(old) * 1.05:
            return False
        return seq_ratio(new[:len(old)], old) >= 0.8

    def _refresh_arrival_mode(self):
        """Update the mode based on how many recent subtitles arrived by growing."""
        if len(self._arrival_history) < 3:
            return
        ratio = sum(self._arrival_history) / len(self._arrival_history)
        mode = ratio >= 0.4
        if mode != self._incremental_mode:
            self._incremental_mode = mode
            logger.debug('[Stabilizer] Mode changed: %s', 'INCREMENTAL (wait for completion)' if mode else 'INSTANT (translate immediately)')

    @property
    def arrival_mode(self):
        return 'incremental' if self._incremental_mode else 'instant'

    def _effective_settle_ms(self):
        """
        The wait time depends on the source's arrival mode and how the text ends.

        In INSTANT mode (subtitles appear all at once) waiting gains nothing →
        `_fast_settle_ms`. In INCREMENTAL mode:
        - text ending with sentence punctuation → normal settle time
        - unfinished text → wait `grow_factor` times longer, since the subtitle
          will likely keep growing until the sentence is complete.
        """
        if not self._incremental_mode:
            return self._fast_settle_ms
        txt = self._last_normalized.rstrip(' "\'')
        if txt.endswith(self._SENTENCE_END):
            return self._settle_ms
        return self._settle_ms * self._grow_factor

    @staticmethod
    def _word_similarity(a, b):
        """Word-level Jaccard similarity (robust to shifted OCR errors)."""
        wa = set(a.lower().split())
        wb = set(b.lower().split())
        if not wa:
            return 0.0
        return len(wa & wb) / len(wa | wb)

    @classmethod
    def _is_minor_jitter(cls, a, b):
        """
        Is the change a → b just OCR jitter (a slightly different reading of the same subtitle)?

        NOT typewriter growth: lengths are close and the content largely overlaps.
        Such changes are not counted as a "change" — otherwise a flickering
        subtitle would never settle.

        Two metrics:
        - char-zip: single-character jitter ("col0r" vs "color")
        - word Jaccard: shifted errors ("But I live" vs "Butyllive")
        Movie subtitle OCR jitters heavily, so the word metric is critical.
        """
        if not a or not b:
            return False
        la = len(a)
        lb = len(b)
        if min(la, lb) / max(la, lb) < 0.75:
            return False
        char_sim = sum(1 for x, y in zip(a, b) if x == y) / max(la, lb)
        if char_sim >= 0.85:
            return True
        if cls._word_similarity(a, b) >= 0.6:
            return True
        return seq_ratio(a, b) >= 0.82

    def process(self, raw_text):
        """
        Process new OCR text.

        Returns a StabilizedText with is_stable=True when the pipeline should
        trigger a translation. For typewriter-style subtitles (letter by letter
        or word by word) the settle timer resets on every change, so nothing is
        translated until typing finishes — then only the FINAL text is
        translated, once.
        """
        if is_garbage(raw_text, self._source_lang, self._target_lang):
            return StabilizedText(text=raw_text, normalized='', is_stable=False, consecutive_count=0)
        cleaned = clean_ocr_text(raw_text, self._source_lang)
        normalized = normalize_text(cleaned)
        if len(normalized) < self._min_length:
            return StabilizedText(text=cleaned, normalized=normalized, is_stable=False, consecutive_count=0)
        now = time.time()
        if normalized == self._last_normalized or self._is_minor_jitter(self._last_normalized, normalized):
            # Same subtitle (or OCR jitter) — bump the counter, don't reset the settle timer
            self._consecutive_count += 1
        else:
            if self._is_growth(self._last_normalized, normalized):
                # Typewriter / scrolling subtitle: the same episode is growing
                self._episode_grew = True
            else:
                # New subtitle episode: record whether the previous one grew
                if self._episode_started:
                    self._arrival_history.append(self._episode_grew)
                    self._refresh_arrival_mode()
                self._episode_started = True
                self._episode_grew = False
            self._consecutive_count = 1
            self._last_normalized = normalized
            self._last_cleaned = cleaned
            self._last_change_time = now
        if not self._last_cleaned:
            self._last_cleaned = cleaned
        is_stable = (
            self._is_settled(now)
            and self._consecutive_count >= self._stability_count
            and not self._is_recently_translated(normalized)
            and not self._is_in_cooldown()
        )
        return StabilizedText(text=self._last_cleaned, normalized=self._last_normalized, is_stable=is_stable, consecutive_count=self._consecutive_count)

    def _is_settled(self, now):
        elapsed_ms = (now - self._last_change_time) * 1000
        return elapsed_ms >= min(self._effective_settle_ms(), self._max_settle_ms)

    def poll_pending(self):
        """
        Called when OCR was skipped (the frame did not change).

        When a typewriter subtitle finishes, the screen stops changing and the
        frame-diff skips OCR, so `process` is never called again once the settle
        time elapses. This returns the pending (not yet translated) subtitle as
        stable once it has settled — so the translation still fires.
        """
        if not self._last_normalized:
            return None
        if not self._is_settled(time.time()):
            return None
        if self._consecutive_count < self._stability_count:
            return None
        if self._is_recently_translated(self._last_normalized):
            return None
        if self._is_in_cooldown():
            return None
        return StabilizedText(text=self._last_cleaned, normalized=self._last_normalized, is_stable=True, consecutive_count=self._consecutive_count)

    def mark_translated(self, normalized_text):
        """Record that this text was translated (updates cooldown & expiry)."""
        self._last_translation_time = time.time()
        self._translated_texts[normalized_text] = time.time()
        if len(self._translated_texts) > 50:
            sorted_items = sorted(self._translated_texts.items(), key=lambda kv: kv[1])
            self._translated_texts = dict(sorted_items[-50:])

    def set_languages(self, source_lang, target_lang):
        self._source_lang = source_lang
        self._target_lang = target_lang

    def reset(self):
        """Reset all state (call when stopping/changing region)."""
        self._last_normalized = ''
        self._last_cleaned = ''
        self._consecutive_count = 0
        self._last_change_time = 0.0
        self._last_translation_time = 0.0
        self._translated_texts.clear()
        self._arrival_history.clear()
        self._episode_grew = False
        self._episode_started = False
        self._incremental_mode = False

    def _is_recently_translated(self, normalized):
        """Check if this normalized text was translated recently."""
        now = time.time()
        if normalized in self._translated_texts:
            elapsed = now - self._translated_texts[normalized]
            if elapsed < self._text_expiry_sec:
                return True
            del self._translated_texts[normalized]
            return False
        for cached, ts in list(self._translated_texts.items()):
            elapsed = now - ts
            if elapsed >= self._text_expiry_sec:
                del self._translated_texts[cached]
        return False

    def _is_in_cooldown(self):
        if self._cooldown_ms <= 0 or self._last_translation_time == 0:
            return False
        elapsed_ms = (time.time() - self._last_translation_time) * 1000
        return elapsed_ms < self._cooldown_ms

    @property
    def current_count(self):
        return self._consecutive_count
