import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from lingolay.core.paths import CONFIG_DIR, PROFILES_DIR, models_dir
from lingolay.core.paths import SETTINGS_FILE as CONFIG_FILE

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_DIR = models_dir('fast')
_DEFAULT_FONT = 'Segoe UI' if sys.platform == 'win32' else ('Helvetica Neue' if sys.platform == 'darwin' else 'DejaVu Sans')


@dataclass
class PreprocessingConfig:
    grayscale: bool = True
    contrast: bool = True
    sharpen: bool = False
    upscale: bool = False
    subtitle_boost: bool = False
    contrast_clip: float = 2.0
    game_mode: bool = False


@dataclass
class OverlayConfig:
    font_family: str = _DEFAULT_FONT
    font_size: int = 18
    text_color: str = '#FFFFFF'
    opacity: float = 1.0
    padding: int = 12
    click_through: bool = False
    max_width_pct: float = 0.8
    pos_x: int | None = None
    pos_y: int | None = None
    backdrop: bool = True
    backdrop_color: str = '#000000'
    backdrop_alpha: int = 210
    outline_color: str = '#000000'
    outline_width: int = 3


@dataclass
class TTSConfig:
    enabled: bool = False
    speed: str = 'fast'
    volume: int = 100
    gain: int = 200
    duck_enabled: bool = True
    duck_level: int = 25


def _default_hotkeys():
    from lingolay.core.hotkeys import DEFAULT_HOTKEYS
    return dict(DEFAULT_HOTKEYS)


@dataclass
class Settings:
    ui_language: str = ''            # '' = follow the system language
    ocr_language: str = 'en-US'
    source_lang: str = 'en'
    target_lang: str = 'tr'
    translation_engine: str = 'nllb_fast'
    nllb_model_dir: str = str(_DEFAULT_MODEL_DIR)
    use_gpu: bool = True
    deepl_api_key: str = ''
    deepl_plan: str = 'free'
    stability_count: int = 1
    min_text_length: int = 2
    text_expiry_sec: int = 4
    cooldown_ms: int = 0
    subtitle_settle_ms: int = 280
    cache_size: int = 500
    capture_interval_ms: int = 200
    min_interval_ms: int = 150
    max_interval_ms: int = 1000
    adaptive_interval: bool = True
    hotkeys: dict = field(default_factory=_default_hotkeys)
    preprocessing: PreprocessingConfig = field(default_factory=PreprocessingConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)

    def get_nllb_model_path(self):
        """
        Return the CTranslate2 model directory (the one containing model.bin).

        Resolution order:
          1. nllb_model_dir itself contains model.bin → use it directly.
          2. Otherwise look for known subdir names inside nllb_model_dir.
          3. Fall back to nllb_model_dir as-is (the translator reports the error).
        """
        base = Path(self.nllb_model_dir)
        if (base / 'model.bin').exists():
            return base
        if self.translation_engine == 'nllb_quality':
            candidates = [base / 'nllb-200-distilled-1.3B-int8', base / 'nllb-200-1.3B-int8']
        else:
            candidates = [base / 'nllb-200-distilled-600M-int8', base / 'nllb-200-600M-int8']
        for c in candidates:
            if (c / 'model.bin').exists():
                return c
        return base


_settings = None


def get_settings():
    global _settings
    if _settings is None:
        _settings = _load_settings()
    return _settings


def _load_settings():
    if not CONFIG_FILE.exists():
        return Settings()
    try:
        with open(CONFIG_FILE, encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data.get('preprocessing'), dict):
            data['preprocessing'] = PreprocessingConfig(**{k: v for k, v in data['preprocessing'].items() if k in PreprocessingConfig.__dataclass_fields__})
        if isinstance(data.get('overlay'), dict):
            data['overlay'] = OverlayConfig(**{k: v for k, v in data['overlay'].items() if k in OverlayConfig.__dataclass_fields__})
        if isinstance(data.get('tts'), dict):
            data['tts'] = TTSConfig(**{k: v for k, v in data['tts'].items() if k in TTSConfig.__dataclass_fields__})
        known = Settings.__dataclass_fields__.keys()
        s = Settings(**{k: v for k, v in data.items() if k in known})
        # Legacy configs: nllb_model_size → translation_engine
        if 'translation_engine' not in data and 'nllb_model_size' in data:
            s.translation_engine = 'nllb_quality' if data.get('nllb_model_size') == '1.3B' else 'nllb_fast'
        from lingolay.core.hotkeys import DEFAULT_HOTKEYS
        for action, default_key in DEFAULT_HOTKEYS.items():
            s.hotkeys.setdefault(action, default_key)
        # Safe limits
        if s.capture_interval_ms < 150:
            s.capture_interval_ms = 200
        if s.min_interval_ms < 150:
            s.min_interval_ms = 150
        if s.max_interval_ms < 500:
            s.max_interval_ms = 1000
        if s.subtitle_settle_ms >= 350:
            s.subtitle_settle_ms = 280
        from lingolay.languages import LANGUAGES
        if s.source_lang not in LANGUAGES:
            s.source_lang = 'en'
        if s.target_lang not in LANGUAGES:
            s.target_lang = 'tr'
        return s
    except Exception as e:
        logger.warning('[Config] Failed to load settings, using defaults: %s', e)
        return Settings()


def save_settings(settings=None):
    global _settings
    if settings is not None:
        _settings = settings
    if _settings is None:
        return
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(asdict(_settings), f, indent=2, ensure_ascii=False)


def _safe_profile_name(name):
    return ''.join(c for c in name if c not in '<>:"/\\|?*').strip() or 'profil'


@dataclass
class Profile:
    """A saved capture region (one per game/platform)."""
    name: str
    region: tuple[int, int, int, int]
    monitor_index: int = 0
    dpi_scale: float = 1.0

    def save(self):
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        filepath = PROFILES_DIR / (_safe_profile_name(self.name) + '.json')
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({'name': self.name, 'region': list(self.region), 'monitor_index': self.monitor_index, 'dpi_scale': self.dpi_scale}, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, name):
        filepath = PROFILES_DIR / (_safe_profile_name(name) + '.json')
        if not filepath.exists():
            return None
        try:
            with open(filepath, encoding='utf-8') as f:
                data = json.load(f)
            return cls(name=data['name'], region=tuple(data['region']), monitor_index=data.get('monitor_index', 0), dpi_scale=data.get('dpi_scale', 1.0))
        except (OSError, KeyError, ValueError):
            return None

    @classmethod
    def list_profiles(cls):
        if not PROFILES_DIR.exists():
            return []
        profiles = []
        for file in sorted(PROFILES_DIR.glob('*.json')):
            profile = cls.load(file.stem)
            if profile:
                profiles.append(profile)
        return profiles

    @classmethod
    def delete(cls, name):
        """Delete a saved profile by name. Returns True if deleted."""
        filepath = PROFILES_DIR / (_safe_profile_name(name) + '.json')
        if filepath.exists():
            filepath.unlink()
            return True
        return False
