"""
Catalog of downloadable model / voice files.

No model is distributed with this repository. Files are downloaded on first use
directly from public sources on the Hugging Face Hub, pinned to a specific
commit (revision), and large files are verified with SHA-256.

  • NLLB-200 (Meta AI)   — CC-BY-NC-4.0 (non-commercial use)
    CTranslate2 int8 conversion: huggingface.co/JustFrederik
  • Piper voices         — rhasspy/piper-voices (each voice has its own model card/license)

To use your own mirror, set the LINGOLAY_HF_ENDPOINT environment variable
(e.g. https://hf-mirror.com).
"""
import os
from dataclasses import dataclass, field

HF_ENDPOINT = os.environ.get('LINGOLAY_HF_ENDPOINT', 'https://huggingface.co').rstrip('/')


@dataclass(frozen=True)
class RemoteFile:
    path: str                      # path inside the repository
    size: int                      # bytes (for the progress bar)
    sha256: str | None = None   # verification for large (LFS) files
    dest_name: str | None = None  # local file name (default: last path component)

    @property
    def local_name(self):
        return self.dest_name or self.path.rsplit('/', 1)[-1]


@dataclass(frozen=True)
class ModelInfo:
    id: str
    kind: str                      # 'translation' | 'voice'
    display_name: str
    description: str
    repo: str
    revision: str
    files: tuple[RemoteFile, ...] = field(default_factory=tuple)
    license: str = ''
    homepage: str = ''

    @property
    def approx_size_mb(self):
        return round(sum(f.size for f in self.files) / (1024 * 1024))

    def url_for(self, remote_file):
        return f'{HF_ENDPOINT}/{self.repo}/resolve/{self.revision}/{remote_file.path}'


_NLLB_COMMON = (
    RemoteFile('config.json', 159),
    RemoteFile('shared_vocabulary.txt', 2568098, 'a132a83330f45514c2476eb81d1d69b3c41762264d16ce0a7ea982e5d6c728e5'),
    RemoteFile('special_tokens_map.json', 3548),
    RemoteFile('tokenizer_config.json', 564),
    RemoteFile('tokenizer.json', 17331176, 'e316b82de11d0f951f370943b3c438311629547285129b0b81dadabd01bca665'),
    RemoteFile('sentencepiece.bpe.model', 4852054, '14bb8dfb35c0ffdea7bc01e56cea38b9e3d5efcdcb9c251d6b40538e1aab555a'),
)

MODELS = {
    'fast': ModelInfo(
        id='fast',
        kind='translation',
        display_name='Fast model (NLLB-200 600M)',
        description='Uses less RAM and runs faster. Ideal for everyday use.',
        repo='JustFrederik/nllb-200-distilled-600M-ct2-int8',
        revision='302d78f00e6fdb50a1064059df7c392b735e9d05',
        files=(RemoteFile('model.bin', 622595991, 'ed1beaf75134de7505315a5223162f56acff397eff6b50638a500d3936fe707b'),) + _NLLB_COMMON,
        license='CC-BY-NC-4.0',
        homepage='https://huggingface.co/facebook/nllb-200-distilled-600M',
    ),
    'quality': ModelInfo(
        id='quality',
        kind='translation',
        display_name='Quality model (NLLB-200 1.3B)',
        description='Higher translation quality, needs more RAM (~4 GB).',
        repo='JustFrederik/nllb-200-distilled-1.3B-ct2-int8',
        revision='30c36268408177b0fce2bfcfa205d877accd327d',
        files=(RemoteFile('model.bin', 1381827087, '72d7533dc7a0e8f10f19a650d4e90faf9cbfa899db5411ad124bd5802bd91263'),) + _NLLB_COMMON,
        license='CC-BY-NC-4.0',
        homepage='https://huggingface.co/facebook/nllb-200-distilled-1.3B',
    ),
}

_PIPER_REPO = 'rhasspy/piper-voices'
_PIPER_REVISION = 'c10ece1aade47bb51c153c893d14e5bf8e5b7117'

# target language → (Piper voice id, files). All voices: https://huggingface.co/rhasspy/piper-voices
VOICE_TABLE = {
    'en': ('en_US-lessac-medium', (RemoteFile('en/en_US/lessac/medium/en_US-lessac-medium.onnx', 63201294, '5efe09e69902187827af646e1a6e9d269dee769f9877d17b16b1b46eeaaf019f'), RemoteFile('en/en_US/lessac/medium/en_US-lessac-medium.onnx.json', 4885))),
    'tr': ('tr_TR-dfki-medium', (RemoteFile('tr/tr_TR/dfki/medium/tr_TR-dfki-medium.onnx', 63201294, '2844717f524ab965d3fe86e60562cbb601d3e456836efcc2196cc3a14112a8fb'), RemoteFile('tr/tr_TR/dfki/medium/tr_TR-dfki-medium.onnx.json', 4960))),
    'de': ('de_DE-thorsten-medium', (RemoteFile('de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx', 63201294, '7e64762d8e5118bb578f2eea6207e1a35a8e0c30595010b666f983fc87bb7819'), RemoteFile('de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json', 4819))),
    'fr': ('fr_FR-siwis-medium', (RemoteFile('fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx', 63201294, '641d1ab097da2b81128c076810edb052b385decc8be3381814802a64a73baf99'), RemoteFile('fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json', 4875))),
    'es': ('es_ES-davefx-medium', (RemoteFile('es/es_ES/davefx/medium/es_ES-davefx-medium.onnx', 63201294, '6658b03b1a6c316ee4c265a9896abc1393353c2d9e1bca7d66c2c442e222a917'), RemoteFile('es/es_ES/davefx/medium/es_ES-davefx-medium.onnx.json', 4817))),
    'ru': ('ru_RU-irina-medium', (RemoteFile('ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx', 63201294, '8ff38212d23da300bbe3705c645e6e5b9475f0bfde01558eb17813e22acaaaaa'), RemoteFile('ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx.json', 4765))),
    'ar': ('ar_JO-kareem-medium', (RemoteFile('ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx', 63201294, '9e95cab07b679da603bba17c4dec7ab3111320571964ee95c0379603c086491e'), RemoteFile('ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx.json', 5024))),
    'zh': ('zh_CN-huayan-medium', (RemoteFile('zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx', 63201294, '9929917bf8cabb26fd528ea44d3a6699c11e87317a14765312420be230be0f3d'), RemoteFile('zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx.json', 4822))),
    'ja': ('ja_JP-hi_fi_captain-medium', (RemoteFile('ja/ja_JP/hi_fi_captain/medium/ja_JP-hi_fi_captain-medium.onnx', 76753841, '5eafa1610fc7a0ff2e7fde9cbe0972d876266e23d8db331727eb2466f19460eb'), RemoteFile('ja/ja_JP/hi_fi_captain/medium/ja_JP-hi_fi_captain-medium.onnx.json', 5301))),
    'ko': ('ko_KR-kss-medium', (RemoteFile('ko/ko_KR/kss/medium/ko_KR-kss-medium.onnx', 63221984, '624fd774e26895f24bebae1bd9a3379e3394baeade4b584924f83e414096e2c9'), RemoteFile('ko/ko_KR/kss/medium/ko_KR-kss-medium.onnx.json', 5232))),
    'pt': ('pt_BR-faber-medium', (RemoteFile('pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx', 63201294, '858555e3a064209c57088fe6bd70c4c3dc54d03eaa00c45d5ecaf43a33f95aa7'), RemoteFile('pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json', 4855))),
    'it': ('it_IT-paola-medium', (RemoteFile('it/it_IT/paola/medium/it_IT-paola-medium.onnx', 63511038, '6fc918b5a0ea6137382833dddfa567bffbe6a5060c02043c87192ee59c04210c'), RemoteFile('it/it_IT/paola/medium/it_IT-paola-medium.onnx.json', 7099))),
    'nl': ('nl_NL-mls-medium', (RemoteFile('nl/nl_NL/mls/medium/nl_NL-mls-medium.onnx', 76584246, '88312e0fbf505b87caf2373d94c1384892e86b1bf2ee482cf65dc8ba179cc7d3'), RemoteFile('nl/nl_NL/mls/medium/nl_NL-mls-medium.onnx.json', 5856))),
    'pl': ('pl_PL-darkman-medium', (RemoteFile('pl/pl_PL/darkman/medium/pl_PL-darkman-medium.onnx', 63201294, 'db505438a5364e8e2e0242c4324130a873ed660dfbe8d9689cef428ffb1b645f'), RemoteFile('pl/pl_PL/darkman/medium/pl_PL-darkman-medium.onnx.json', 4816))),
    'uk': ('uk_UA-ukrainian_tts-medium', (RemoteFile('uk/uk_UA/ukrainian_tts/medium/uk_UA-ukrainian_tts-medium.onnx', 76735663, '7920419ac5f6fd8b6450520f24b52ed5a319cb53dd018fbcd71c9e079cbac84f'), RemoteFile('uk/uk_UA/ukrainian_tts/medium/uk_UA-ukrainian_tts-medium.onnx.json', 2002))),
}

VOICES = {
    voice_id: ModelInfo(
        id=voice_id,
        kind='voice',
        display_name=f'Dubbing voice ({voice_id})',
        description='Reads translations aloud locally. No internet needed.',
        repo=_PIPER_REPO,
        revision=_PIPER_REVISION,
        files=files,
        license='See model card (Piper voices)',
        homepage='https://huggingface.co/rhasspy/piper-voices',
    )
    for voice_id, files in VOICE_TABLE.values()
}


def voice_for_language(lang_code):
    """Piper voice id for a target language (None if there is none)."""
    entry = VOICE_TABLE.get(lang_code)
    return entry[0] if entry else None


ALL_ASSETS = {**MODELS, **VOICES}


def get_model(model_id):
    """Return ModelInfo for the given id (translation model or voice), raising KeyError if unknown."""
    if model_id not in ALL_ASSETS:
        raise KeyError(f'Unknown model id: {model_id!r}. Valid ids: {list(ALL_ASSETS)}')
    return ALL_ASSETS[model_id]
