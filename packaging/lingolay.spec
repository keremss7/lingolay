# PyInstaller spec — builds dist/Lingolay/Lingolay.exe (one-folder, windowed).
#   pip install ".[all]" pyinstaller
#   pyinstaller packaging/lingolay.spec --noconfirm --clean
# Models are NOT bundled; they are downloaded on first launch
# (or put a models/<fast|quality>/ folder next to Lingolay.exe for a portable build).
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = Path(SPECPATH).parent
SRC = ROOT / 'src'

datas = [
    (str(SRC / 'lingolay' / 'assets'), 'lingolay/assets'),
    (str(SRC / 'lingolay' / 'i18n' / 'locales'), 'lingolay/i18n/locales'),
]
binaries = []
hiddenimports = collect_submodules('lingolay')

for pkg in ('ctranslate2', 'tokenizers', 'onnxruntime'):
    try:
        binaries += collect_dynamic_libs(pkg)
    except Exception:
        pass
# pyopenjtalk ships the OpenJTalk dictionary the Japanese voice needs
for pkg in ('piper', 'certifi', 'pyopenjtalk'):
    try:
        datas += collect_data_files(pkg)
    except Exception:
        pass
if sys.platform == 'win32':
    hiddenimports += collect_submodules('winrt') + collect_submodules('pycaw') + collect_submodules('comtypes') + ['dxcam']
hiddenimports += collect_submodules('piper') + collect_submodules('pyopenjtalk') + ['pygame', 'deepl', 'mss']

a = Analysis(
    [str(ROOT / 'packaging' / 'launcher.py')],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    # sudachidict_core (~190 MB) only refines rare kanji readings; OpenJTalk's own dictionary is used instead
    excludes=['tkinter', 'matplotlib', 'PySide6.Qt3DCore', 'PySide6.QtWebEngineCore', 'PySide6.QtQuick', 'sudachidict_core'],
    noarchive=False,
)
# The sudachipy hook still collects the dictionary's data files; drop them
a.datas = [d for d in a.datas if not d[0].replace('\\', '/').startswith('sudachidict_core/')]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Lingolay',
    console=False,
    icon=str(SRC / 'lingolay' / 'assets' / 'icon.ico'),
    version=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Lingolay')
