"""
Meta NLLB-200 translation engine — runs fully locally/offline via CTranslate2.

Model files are not part of the repository; they are downloaded from Hugging
Face on first launch (see lingolay/models/manifest.py). The NLLB-200 weights are
published by Meta under the CC-BY-NC-4.0 license.
"""
import logging
import re
import time
from pathlib import Path

from lingolay.i18n import t
from lingolay.languages import LANGUAGES
from lingolay.translation.base import TranslationResult
from lingolay.translation.cache import TranslationCache

logger = logging.getLogger(__name__)

NLLB_LANG_CODES = {code: lang.nllb for code, lang in LANGUAGES.items()}

CT2_AVAILABLE = False
CT2_IMPORT_ERROR = None
try:
    import ctranslate2
    CT2_AVAILABLE = True
except Exception as _e:
    CT2_IMPORT_ERROR = str(_e)

TOKENIZERS_AVAILABLE = False
TOKENIZERS_IMPORT_ERROR = None
try:
    from tokenizers import Tokenizer
    TOKENIZERS_AVAILABLE = True
except Exception as _e:
    TOKENIZERS_IMPORT_ERROR = str(_e)

_VC_REDIST_URL = 'https://aka.ms/vs/17/release/vc_redist.x64.exe'
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?…])\s+(?=\S)|(?<=[。！？])')
_QUESTION_WORDS = frozenset(('what', 'when', 'where', 'who', 'why', 'how', 'which'))
_NEGATION_WORDS = frozenset(('if', 'unless', 'not', "don't", "doesn't", "won't", "can't"))


def _post_process_turkish(text):
    """Turkish-specific cleanup of common NLLB spacing quirks."""
    if not text:
        return text
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)
    text = re.sub(' {2,}', ' ', text)
    return text.strip()


class NLLBTranslator:
    MAX_TEXT_LENGTH = 150
    MAX_RETRIES = 2
    LENGTH_PENALTY = 1.2

    def __init__(self, from_lang='en', to_lang='tr', model_dir=None, use_gpu=True, beam_size=2, cache_size=500, post_process=True):
        self._from_lang = from_lang
        self._to_lang = to_lang
        self._beam_size = beam_size
        self._use_gpu = use_gpu
        self._post_process = post_process and to_lang == 'tr'
        if model_dir:
            self._model_dir = Path(model_dir)
        else:
            from lingolay.core.config import get_settings
            self._model_dir = get_settings().get_nllb_model_path()
        self._src_lang = NLLB_LANG_CODES.get(from_lang, f'{from_lang}_Latn')
        self._tgt_lang = NLLB_LANG_CODES.get(to_lang, f'{to_lang}_Latn')
        self._cache = TranslationCache(max_size=cache_size)
        self._translator = None
        self._tokenizer = None
        self._device = 'cpu'
        self._ready = False
        self._init_error = None
        self._last_latency_ms = 0
        self._translation_count = 0
        self._error_count = 0
        self._init_model()

    def _init_model(self):
        """Load NLLB model and tokenizer."""
        if not CT2_AVAILABLE:
            self._init_error = t('CTranslate2 could not be loaded.\nDetails: {error}\nFix (Windows): install the Microsoft Visual C++ 2015-2022 Redistributable (x64): {url}',
                                 error=CT2_IMPORT_ERROR or '?', url=_VC_REDIST_URL)
            logger.error(self._init_error)
            return
        if not TOKENIZERS_AVAILABLE:
            self._init_error = t('tokenizers could not be loaded.\nDetails: {error}\nFix (Windows): install the Microsoft Visual C++ 2015-2022 Redistributable (x64): {url}',
                                 error=TOKENIZERS_IMPORT_ERROR or '?', url=_VC_REDIST_URL)
            logger.error(self._init_error)
            return
        model_path = self._model_dir
        tokenizer_path = model_path / 'tokenizer.json'
        if not (model_path / 'model.bin').exists():
            self._init_error = t('NLLB model not found:\n{path}\n\nDownload it from the Translation page.', path=model_path)
            logger.error(self._init_error)
            return
        if not tokenizer_path.exists():
            self._init_error = t('tokenizer.json not found:\n{path}', path=tokenizer_path)
            logger.error(self._init_error)
            return

        try:
            self._tokenizer = Tokenizer.from_file(str(tokenizer_path))
        except Exception as e:
            self._init_error = t('The tokenizer could not be loaded: {error}', error=e)
            logger.error(self._init_error)
            return

        device = 'cpu'
        if self._use_gpu:
            try:
                if ctranslate2.get_cuda_device_count() > 0:
                    device = 'cuda'
                    logger.info('[NLLB] CUDA GPU detected, trying it')
                else:
                    logger.info('[NLLB] No CUDA, using CPU')
            except Exception:
                logger.info('[NLLB] Could not query CUDA, using CPU')

        try:
            self._translator = self._build_translator(device)
            self._device = device
            if device == 'cuda':
                self._smoke_test_translator()
        except Exception as e:
            if device != 'cuda':
                self._init_error = t('The model could not be loaded: {error}', error=e)
                logger.error(self._init_error)
                return
            logger.warning('[NLLB] CUDA failed (%s) — cuBLAS/cuDNN may be missing. Falling back to CPU.', e)
            try:
                self._translator = self._build_translator('cpu')
                self._device = 'cpu'
                self._smoke_test_translator()
            except Exception as e2:
                self._init_error = t('The model could not be loaded: {error}', error=e2)
                logger.error(self._init_error)
                return

        self._ready = True
        model_name = '1.3B' if '1.3B' in str(model_path) else '600M'
        logger.info('[NLLB] Ready: %s->%s | %s | NLLB-%s', self._from_lang, self._to_lang, self._device.upper(), model_name)

    def _build_translator(self, device):
        """Create a ctranslate2.Translator tuned for the device."""
        if device == 'cpu':
            return ctranslate2.Translator(str(self._model_dir), device='cpu', compute_type='int8', inter_threads=1, intra_threads=4)
        return ctranslate2.Translator(str(self._model_dir), device='cuda', compute_type='int8_float16', inter_threads=1, intra_threads=1)

    def _smoke_test_translator(self):
        """Tiny test translation — missing CUDA DLLs raise here."""
        self._translator.translate_batch([self._tokenize('test')], target_prefix=[[self._tgt_lang]], beam_size=1, max_decoding_length=8)
        return True

    @property
    def is_ready(self):
        return self._ready

    @property
    def init_error(self):
        return self._init_error

    @property
    def device_name(self):
        return f'NLLB-200 ({self._device.upper()})'

    @property
    def last_latency_ms(self):
        return self._last_latency_ms

    @property
    def cache_hit_rate(self):
        return self._cache.hit_rate

    def _tokenize(self, text):
        """NLLB input format: [src_lang] + pieces + </s>."""
        pieces = self._tokenizer.encode(text, add_special_tokens=False).tokens
        return [self._src_lang] + pieces + ['</s>']

    def _detokenize(self, tokens):
        """Convert SentencePiece tokens back to text, skipping special/language tokens."""
        ids = [self._tokenizer.token_to_id(t) for t in tokens]
        ids = [i for i in ids if i is not None]
        text = self._tokenizer.decode(ids, skip_special_tokens=True)
        return re.sub(r'\s{2,}', ' ', text).strip()

    def _is_complex(self, text):
        """Heuristic: complex sentences benefit from a wider beam."""
        if self._from_lang != 'en':
            return len(text.split()) > 12 or len(text) > 60
        t = text.lower()
        words = set(re.findall(r"[a-z']+", t))
        if words & _QUESTION_WORDS or words & _NEGATION_WORDS:
            return True
        clause_markers = t.count(',') + t.count(' and ') + t.count(' but ') + t.count(' or ')
        if clause_markers >= 2:
            return True
        return len(text.split()) > 15

    def _preprocess(self, text):
        """Remove tags and noise that cause NLLB hallucinations."""
        text = re.sub(r'\[[^\]]+\]\s*', ' ', text)
        if self._from_lang == 'en':
            text = re.sub(r'-[A-Z](?=\w)', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @staticmethod
    def _split_sentences(text):
        """
        Split into sentences. NLLB was trained on single sentences and tends to drop
        one of them when given several at once, so each sentence is translated separately.
        """
        parts = [p.strip() for p in _SENTENCE_SPLIT.split(text) if p and p.strip()]
        return parts or [text]

    def _translate_raw(self, text):
        """Translate text (sentence by sentence, in a single batch)."""
        sentences = self._split_sentences(text)
        beam = 4 if self._is_complex(text) else self._beam_size
        results = self._translator.translate_batch(
            [self._tokenize(s) for s in sentences],
            target_prefix=[[self._tgt_lang]] * len(sentences),
            beam_size=beam,
            length_penalty=self.LENGTH_PENALTY,
            max_decoding_length=100,
            max_input_length=120,
            replace_unknowns=True,
        )
        outputs = []
        for sentence, result in zip(sentences, results):
            output_tokens = result.hypotheses[0]
            if output_tokens and output_tokens[0] == self._tgt_lang:
                output_tokens = output_tokens[1:]
            out = self._detokenize(output_tokens)
            # NLLB sometimes prepends a dialogue dash that isn't in the source
            if out.startswith(('- ', '– ', '— ')) and not sentence.startswith(('-', '–', '—')):
                out = out[2:]
            outputs.append(out)
        sep = '' if self._to_lang in ('zh', 'ja') else ' '
        return sep.join(o for o in outputs if o)

    def _translate_with_retry(self, text):
        last_error = None
        for attempt in range(self.MAX_RETRIES + 1):
            clean = text.strip()
            if not clean:
                return ('', None)
            try:
                translated = self._translate_raw(clean)
                self._translation_count += 1
                return (translated, None)
            except Exception as e:
                last_error = str(e)
                logger.warning('[NLLB] Translation attempt %d failed: %s', attempt + 1, e)
        self._error_count += 1
        return ('', last_error)

    def translate(self, text):
        """Translate text. Returns TranslationResult. Thread-safe (CTranslate2 releases the GIL)."""
        start = time.perf_counter()
        if not self._ready:
            return TranslationResult(text='', error=self._init_error or t('The model is not ready'))
        text = self._preprocess(text)
        if len(text) > self.MAX_TEXT_LENGTH:
            text = text[:self.MAX_TEXT_LENGTH]
        if not text.strip():
            return TranslationResult(text='')
        cached = self._cache.get(text)
        if cached is not None:
            return TranslationResult(text=cached, from_cache=True)
        translated, error = self._translate_with_retry(text)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        self._last_latency_ms = elapsed_ms
        if error:
            return TranslationResult(text='', latency_ms=elapsed_ms, error=error)
        if self._post_process:
            translated = _post_process_turkish(translated)
        self._cache.put(text, translated)
        return TranslationResult(text=translated, latency_ms=elapsed_ms)

    def warm_up(self):
        """Run a couple of translations to warm up the model."""
        if not self._ready:
            return
        logger.info('[NLLB] Warming up...')
        start = time.perf_counter()
        self.translate('Hello, how are you?')
        self.translate('The quick brown fox jumps over the lazy dog.')
        self._cache.clear()
        logger.info('[NLLB] Warm-up finished: %dms', int((time.perf_counter() - start) * 1000))

    def clear_cache(self):
        self._cache.clear()

    def get_stats(self):
        return {
            'model': 'NLLB-200', 'device': self._device, 'beam_size': self._beam_size,
            'cache_size': self._cache.size, 'cache_hit_rate': round(self._cache.hit_rate, 3),
            'translations': self._translation_count, 'errors': self._error_count,
            'last_latency_ms': self._last_latency_ms,
        }
