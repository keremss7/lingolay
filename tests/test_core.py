import json

from lingolay.core.hotkeys import MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, MOD_SHIFT, normalize_hotkey_string, parse_hotkey_string
from lingolay.translation.cache import TranslationCache


def test_parse_hotkey_string():
    assert parse_hotkey_string('Ctrl+Alt+S') == (MOD_NOREPEAT | MOD_CONTROL | MOD_ALT, ord('S'))
    assert parse_hotkey_string('ctrl+shift+f5') == (MOD_NOREPEAT | MOD_CONTROL | MOD_SHIFT, 116)
    assert parse_hotkey_string('Ctrl+Alt') is None
    assert parse_hotkey_string('') is None


def test_normalize_hotkey_string():
    assert normalize_hotkey_string('ctrl+alt+s') == 'Ctrl+Alt+S'


def test_translation_cache_lru_and_hit_rate():
    c = TranslationCache(max_size=2)
    c.put('a', 'A')
    c.put('b', 'B')
    assert c.get('a') == 'A'
    c.put('c', 'C')  # evicts least recently used ('b')
    assert c.get('b') is None
    assert c.size == 2
    assert 0 < c.hit_rate < 1


def test_settings_roundtrip_and_migration(tmp_path, monkeypatch):
    from lingolay.core import config
    cfg = tmp_path / 'settings.json'
    cfg.write_text(json.dumps({'nllb_model_size': '1.3B', 'target_lang': 'de', 'unknown_key': 1,
                               'overlay': {'font_size': 30, 'bogus': True}, 'capture_interval_ms': 10}), encoding='utf-8')
    monkeypatch.setattr(config, 'CONFIG_FILE', cfg)
    s = config._load_settings()
    assert s.translation_engine == 'nllb_quality'  # legacy key migrated
    assert s.target_lang == 'de'
    assert s.overlay.font_size == 30
    assert s.capture_interval_ms == 200  # clamped to a safe value
    assert 'toggle_tts' in s.hotkeys  # default hotkeys filled in


def test_profiles_roundtrip():
    from lingolay.core.config import Profile
    Profile(name='Elden Ring', region=(10, 20, 640, 120), monitor_index=1, dpi_scale=1.5).save()
    p = Profile.load('Elden Ring')
    assert p.region == (10, 20, 640, 120) and p.monitor_index == 1
    assert any(x.name == 'Elden Ring' for x in Profile.list_profiles())
    assert Profile.delete('Elden Ring')
    assert Profile.load('Elden Ring') is None
