"""DeepL API translation engine (optional, uses the user's own API key)."""
import logging
import os
import time

from lingolay.i18n import t
from lingolay.translation.base import TranslationResult
from lingolay.translation.cache import TranslationCache

logger = logging.getLogger(__name__)

DEEPL_AVAILABLE = False
DEEPL_IMPORT_ERROR = None
try:
    import deepl as _deepl
    DEEPL_AVAILABLE = True
except Exception as _e:
    DEEPL_IMPORT_ERROR = str(_e)

DEEPL_SOURCE_CODES = {
    'en': 'EN', 'tr': 'TR', 'de': 'DE', 'fr': 'FR', 'es': 'ES', 'ru': 'RU', 'ar': 'AR', 'zh': 'ZH',
    'ja': 'JA', 'ko': 'KO', 'pt': 'PT', 'it': 'IT', 'nl': 'NL', 'pl': 'PL', 'uk': 'UK',
}
# DeepL requires a regional variant for some target languages (EN → EN-US, PT → PT-BR)
DEEPL_TARGET_CODES = dict(DEEPL_SOURCE_CODES, en='EN-US', pt='PT-BR')


def _is_transient_error(e):
    """
    Transient network errors (timeout, connection reset, DNS) can be retried.
    Auth/limit/quota errors are permanent; retrying is pointless.
    """
    s = str(e).lower()
    transient_keywords = ('timeout', 'timed out', 'connection', 'reset', 'refused', 'dns', 'network', 'unreachable', 'temporarily')
    permanent_keywords = ('auth', '401', '403', '456', 'limit', 'quota', 'forbidden')
    if any(kw in s for kw in permanent_keywords):
        return False
    return any(kw in s for kw in transient_keywords)


class DeepLTranslator:
    MAX_RETRIES = 1

    def __init__(self, from_lang='en', to_lang='tr', api_key='', plan='free', cache_size=500):
        self._from_lang = from_lang
        self._to_lang = to_lang
        self._api_key = (api_key or '').strip()
        self._plan = plan
        self._src_code = DEEPL_SOURCE_CODES.get(from_lang, from_lang.upper())
        self._tgt_code = DEEPL_TARGET_CODES.get(to_lang, to_lang.upper())
        self._cache = TranslationCache(max_size=cache_size)
        self._client = None
        self._ready = False
        self._init_error = None
        self._last_latency_ms = 0
        self._translation_count = 0
        self._error_count = 0
        self._init_client()

    def _init_client(self):
        if not DEEPL_AVAILABLE:
            self._init_error = t('The DeepL library could not be loaded.\nDetails: {error}', error=DEEPL_IMPORT_ERROR or '?')
            logger.error(self._init_error)
            return
        if not self._api_key:
            self._init_error = t('No DeepL API key entered (Translation → Translation engine)')
            logger.error('[DeepL] API key is empty')
            return
        try:
            import certifi
            os.environ.setdefault('SSL_CERT_FILE', certifi.where())
        except Exception:
            pass
        try:
            self._client = _deepl.Translator(self._api_key)
            usage = self._client.get_usage()
            plan_label = 'Free' if self._plan == 'free' else 'Pro'
            if usage.character.limit:
                used_pct = usage.character.count / usage.character.limit * 100
                logger.info('[DeepL] Ready (%s) — usage: %s/%s characters (%.1f%%)', plan_label,
                            f'{usage.character.count:,}', f'{usage.character.limit:,}', used_pct)
            else:
                logger.info('[DeepL] Ready (%s)', plan_label)
            self._ready = True
        except Exception as e:
            self._init_error = t('Could not connect to DeepL: {error}', error=e)
            logger.error(self._init_error)

    @property
    def is_ready(self):
        return self._ready

    @property
    def init_error(self):
        return self._init_error

    @property
    def device_name(self):
        plan_label = t('Free') if self._plan == 'free' else t('Pro')
        return f'DeepL API ({plan_label})'

    @property
    def last_latency_ms(self):
        return self._last_latency_ms

    @property
    def cache_hit_rate(self):
        return self._cache.hit_rate

    def translate(self, text):
        start = time.perf_counter()
        if not self._ready:
            return TranslationResult(text='', error=self._init_error or t('DeepL is not ready'))
        text = text.strip()
        if not text:
            return TranslationResult(text='')
        cached = self._cache.get(text)
        if cached is not None:
            return TranslationResult(text=cached, from_cache=True)
        last_err = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                result = self._client.translate_text(text, source_lang=self._src_code, target_lang=self._tgt_code)
                translated = result.text
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                self._last_latency_ms = elapsed_ms
                self._translation_count += 1
                self._cache.put(text, translated)
                return TranslationResult(text=translated, latency_ms=elapsed_ms)
            except Exception as e:
                last_err = str(e)
                logger.warning('[DeepL] Attempt %d failed: %s', attempt + 1, e)
                if not _is_transient_error(e):
                    break
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        self._error_count += 1
        logger.warning('[DeepL] Translation error (final): %s', last_err)
        return TranslationResult(text='', latency_ms=elapsed_ms, error=last_err or t('DeepL translation error'))

    def warm_up(self):
        """A single test translation is enough for DeepL."""
        if not self._ready:
            return
        start = time.perf_counter()
        self.translate('Hello')
        self._cache.clear()
        logger.info('[DeepL] Warm-up finished: %dms', int((time.perf_counter() - start) * 1000))

    def clear_cache(self):
        self._cache.clear()

    def get_stats(self):
        return {
            'model': 'DeepL API', 'plan': self._plan, 'cache_size': self._cache.size,
            'cache_hit_rate': round(self._cache.hit_rate, 3), 'translations': self._translation_count,
            'errors': self._error_count, 'last_latency_ms': self._last_latency_ms,
        }
