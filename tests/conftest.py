import os
import sys
import tempfile
from pathlib import Path

# Isolate all app data (settings, profiles, models) in a temp dir BEFORE lingolay is imported.
os.environ.setdefault('LINGOLAY_HOME', tempfile.mkdtemp(prefix='lingolay-test-'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import pytest  # noqa: E402


@pytest.fixture(scope='session')
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
    # Tear down Qt objects deterministically; letting the interpreter destroy them at exit
    # can crash on Windows after all tests have passed.
    for widget in QApplication.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    app.processEvents()
