"""List every UI string passed to t() and report which are missing from a locale.

    python scripts/extract_strings.py            # missing keys for all locales
    python scripts/extract_strings.py --all      # print every source string
"""
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src' / 'lingolay'
LOCALES = SRC / 'i18n' / 'locales'
# Constants translated at display time (not literal t() calls)
EXTRA_MODULES = {
    'core/hotkeys.py': 'ACTION_LABELS',
    'tts/fast_dubbing.py': 'SPEED_LABELS',
}


def collect():
    found = {}
    for path in sorted(SRC.rglob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        rel = path.relative_to(SRC).as_posix()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 't'
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                found.setdefault(node.args[0].value, rel)
            if rel in EXTRA_MODULES and isinstance(node, ast.Assign):
                if any(isinstance(tg, ast.Name) and tg.id == EXTRA_MODULES[rel] for tg in node.targets) and isinstance(node.value, ast.Dict):
                    for v in node.value.values:
                        if isinstance(v, ast.Constant):
                            found.setdefault(v.value, rel)
    # model display names / descriptions
    sys.path.insert(0, str(ROOT / 'src'))
    from lingolay.models.manifest import MODELS, VOICES
    for info in MODELS.values():
        found.setdefault(info.display_name, 'models/manifest.py')
        found.setdefault(info.description, 'models/manifest.py')
    for info in VOICES.values():
        found.setdefault(info.description, 'models/manifest.py')
    return found


def main():
    strings = collect()
    if '--all' in sys.argv:
        for s, where in strings.items():
            print(f'{where:32} {s!r}')
        return 0
    missing_total = 0
    for loc in sorted(LOCALES.glob('*.json')):
        data = json.loads(loc.read_text(encoding='utf-8'))
        missing = [s for s in strings if s not in data]
        unused = [k for k in data if not k.startswith('_meta') and k not in strings]
        print(f'{loc.name}: {len(strings) - len(missing)}/{len(strings)} translated, {len(missing)} missing, {len(unused)} unused')
        for s in missing:
            print('   MISSING', repr(s))
        for s in unused:
            print('   UNUSED ', repr(s))
        missing_total += len(missing)
    return 1 if missing_total else 0


if __name__ == '__main__':
    sys.exit(main())
