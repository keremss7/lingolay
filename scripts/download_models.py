"""Download translation models / dubbing voices without opening the GUI.

    python scripts/download_models.py --list-models
    python scripts/download_models.py --download fast voice:tr

Same as running `lingolay --download ...` after installation.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from lingolay.app import main  # noqa: E402

if __name__ == '__main__':
    main(sys.argv[1:] or ['--help'])
