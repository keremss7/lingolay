"""
First-run wizard: choose a translation model → download → ready.

There is no account or license. Models are downloaded straight from Hugging
Face; DeepL users can skip the download.
"""
import logging
import threading
import time

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from lingolay import __app_name__
from lingolay.i18n import t

logger = logging.getLogger(__name__)

_STYLE = """
QWidget {
    background-color: #0d0d0f;
    color: #e8e8f0;
    font-size: 13px;
}
QPushButton {
    background-color: #ff6929;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px 24px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover  { background-color: #ff8050; }
QPushButton:disabled {
    background-color: rgba(255, 105, 41, 0.25);
    color: rgba(255, 255, 255, 0.3);
}
QPushButton#secondary {
    background-color: transparent;
    border: 1px solid rgba(255, 105, 41, 0.4);
    color: rgba(255, 180, 130, 0.8);
    padding: 8px 18px;
}
QPushButton#secondary:hover { background-color: rgba(255, 105, 41, 0.12); }
QProgressBar {
    border: 1px solid #333340;
    border-radius: 5px;
    background: #1a1a1f;
    text-align: center;
    color: white;
    height: 20px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #ff6929,stop:1 #30cc74);
    border-radius: 4px;
}
QTextEdit {
    background: #111115;
    border: 1px solid #2a2a35;
    border-radius: 6px;
    color: #8ad68a;
    font-family: 'Consolas', 'Menlo', monospace;
    font-size: 11px;
    padding: 6px;
}
QRadioButton, QCheckBox {
    color: #c8c8d8;
    font-size: 13px;
    spacing: 10px;
    padding: 8px;
}
QRadioButton::indicator { width: 16px; height: 16px; }
QRadioButton::indicator:checked { background: #ff6929; border-radius: 8px; }
QRadioButton::indicator:unchecked {
    background: #1a1a1f;
    border: 2px solid #555560;
    border-radius: 8px;
}
"""


def _label(text, style=None):
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    if style:
        lbl.setStyleSheet(style)
    return lbl


def _divider():
    line = QWidget()
    line.setFixedHeight(1)
    line.setStyleSheet('background: #222230;')
    return line


def _format_size(mb):
    return f'{mb / 1024:.1f} GB' if mb >= 1024 else f'{mb} MB'


def _format_speed(bytes_per_sec):
    """1240000 → '1.2 MB/s', 350000 → '342 KB/s'."""
    if bytes_per_sec >= 1024 * 1024:
        return f'{bytes_per_sec / (1024 * 1024):.1f} MB/s'
    if bytes_per_sec >= 1024:
        return f'{bytes_per_sec / 1024:.0f} KB/s'
    return f'{int(bytes_per_sec)} B/s'


def _format_eta(seconds):
    """245 → '4m 5s', 18 → '18s', 4000 → '1h 6m'."""
    if seconds < 1:
        return t('almost done')
    if seconds < 60:
        return f'{int(seconds)}s'
    if seconds < 3600:
        return f'{int(seconds // 60)}m {int(seconds % 60)}s'
    return f'{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m'


class DownloadWorker(QThread):
    """Downloads one or more models sequentially."""
    progress = Signal(object, object)  # (done, total) — object avoids 32-bit int overflow
    log_line = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, model_ids, parent=None):
        super().__init__(parent)
        self._model_ids = list(model_ids)
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def run(self):
        from lingolay.models.manager import DownloadCancelled, get_model_manager
        from lingolay.models.manifest import MODELS, get_model
        mgr = get_model_manager()
        try:
            for model_id in self._model_ids:
                info = get_model(model_id)
                self.log_line.emit(t('Downloading: {name}\n  Source: huggingface.co/{repo}\n  License: {license}\n',
                                     name=t(info.display_name), repo=info.repo, license=info.license))
                path = mgr.download(model_id, progress_cb=lambda d, t: self.progress.emit(d, t), cancel_event=self._cancel_event)
                if model_id in MODELS:
                    mgr.set_active_model(model_id)
                self.log_line.emit(t('Installed: {path}\n', path=path))
            self.finished.emit(True, '')
        except DownloadCancelled:
            self.log_line.emit(t('Download cancelled.\n'))
            self.finished.emit(False, 'cancelled')
        except Exception as e:
            logger.exception('[Download] Error')
            self.log_line.emit(t('ERROR: {error}\n', error=e))
            self.finished.emit(False, str(e))


class ModelSelectScreen(QWidget):
    models_selected = Signal(list)
    skip_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        from lingolay.core.config import get_settings
        from lingolay.models.manifest import MODELS, VOICES, voice_for_language
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(_label(t('Choose a translation model'), 'font-size:20px; font-weight:bold; color:#ff6929;'))
        lay.addWidget(_label(t('Download the model once — after that everything runs fully offline. '
                               'Models are downloaded directly from their source on Hugging Face.'), 'color:#a0a0b8;'))
        lay.addWidget(_divider())
        self._radios = {}
        for model_id, info in MODELS.items():
            rb = QRadioButton(f'{t(info.display_name)}  (~{_format_size(info.approx_size_mb)})\n  {t(info.description)}')
            self._radios[model_id] = rb
            lay.addWidget(rb)
        self._radios['fast'].setChecked(True)
        # Optional dubbing voice for the configured target language
        self._voice_id = voice_for_language(get_settings().target_lang)
        self._chk_voice = QCheckBox()
        if self._voice_id:
            voice = VOICES[self._voice_id]
            self._chk_voice.setText(t('Also download the dubbing voice ({voice}, ~{size})', voice=self._voice_id,
                                      size=_format_size(voice.approx_size_mb)))
            lay.addWidget(self._chk_voice)
        lay.addWidget(_label(t('NLLB-200 models are published by Meta AI under the CC-BY-NC-4.0 license '
                               '(non-commercial use).'), 'color:#555568; font-size:11px;'))
        lay.addStretch()
        row = QHBoxLayout()
        btn_skip = QPushButton(t('Skip (I will use DeepL)'))
        btn_skip.setObjectName('secondary')
        btn_skip.clicked.connect(self.skip_requested)
        self._btn = QPushButton(t('Download and install'))
        self._btn.clicked.connect(self._on_next)
        row.addWidget(btn_skip)
        row.addStretch()
        row.addWidget(self._btn)
        lay.addLayout(row)

    def _on_next(self):
        selected = next((k for k, v in self._radios.items() if v.isChecked()), 'fast')
        ids = [selected]
        if self._voice_id and self._chk_voice.isChecked():
            ids.append(self._voice_id)
        self.models_selected.emit(ids)


class DownloadScreen(QWidget):
    download_done = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._dl_start_time = None
        self._last_ui_update = 0.0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self._title = _label(t('Downloading model...'), 'font-size:20px; font-weight:bold; color:#ff6929;')
        lay.addWidget(self._title)
        self._sub = _label(t('Please wait. Do not disconnect from the internet.'), 'color:#a0a0b8;')
        lay.addWidget(self._sub)
        lay.addWidget(_divider())
        lay.addSpacing(8)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        lay.addWidget(self._progress)
        self._speed_lbl = _label('', 'color:#a0a0b8; font-size:12px; font-weight:600;')
        lay.addWidget(self._speed_lbl)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(160)
        lay.addWidget(self._log)
        lay.addStretch()
        self._btn_cancel = QPushButton(t('Cancel'))
        self._btn_cancel.setObjectName('secondary')
        self._btn_cancel.clicked.connect(self._on_cancel)
        lay.addWidget(self._btn_cancel, alignment=Qt.AlignmentFlag.AlignCenter)

    def start_download(self, model_ids):
        if isinstance(model_ids, str):
            model_ids = [model_ids]
        self._log.clear()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._speed_lbl.setText(t('Connecting to server...'))
        self._btn_cancel.setEnabled(True)
        self._title.setText(t('Downloading model...'))
        self._sub.setText(t('Please wait. Do not disconnect from the internet.'))
        self._sub.setStyleSheet('color:#a0a0b8;')
        self._dl_start_time = time.monotonic()
        self._last_ui_update = 0.0
        self._worker = DownloadWorker(model_ids)
        self._worker.progress.connect(self._on_progress)
        self._worker.log_line.connect(self._on_log)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, done, total):
        now = time.monotonic()
        if now - self._last_ui_update < 0.3:
            return
        self._last_ui_update = now
        mb_done = done / (1024 * 1024)
        if total <= 0:
            self._progress.setRange(0, 0)
            self._speed_lbl.setText(t('{mb} MB downloaded', mb=f'{mb_done:.1f}'))
            return
        self._progress.setValue(int(done * 100 / total))
        mb_total = total / (1024 * 1024)
        elapsed = now - (self._dl_start_time or now)
        if elapsed < 0.5 or done <= 0:
            self._speed_lbl.setText(f"{mb_done:.1f} MB / {mb_total:.1f} MB  ·  {t('Starting...')}")
            return
        bytes_per_sec = done / elapsed
        eta_sec = max(0, total - done) / bytes_per_sec if bytes_per_sec > 0 else 0
        self._speed_lbl.setText(f'{mb_done:.1f} MB / {mb_total:.1f} MB  ·  {_format_speed(bytes_per_sec)}  ·  '
                                + t('{eta} left', eta=_format_eta(eta_sec)))

    def _on_log(self, line):
        self._log.insertPlainText(line)
        self._log.moveCursor(QTextCursor.MoveOperation.End)

    def _on_finished(self, success, msg):
        self._btn_cancel.setEnabled(False)
        self._progress.setRange(0, 100)
        if success:
            self._progress.setValue(100)
            self._title.setText(t('Installation complete'))
            self._sub.setText(t('The model was installed successfully.'))
        elif msg == 'cancelled':
            self._title.setText(t('Cancelled'))
            self._sub.setText(t('The download was cancelled.'))
        else:
            self._title.setText(t('An error occurred'))
            self._sub.setText(msg.split('\n')[0] if msg else t('Unknown error'))
            self._sub.setStyleSheet('color:#f04040;')
        self.download_done.emit(success, msg)

    def _on_cancel(self):
        if self._worker:
            self._worker.cancel()
        self._btn_cancel.setEnabled(False)


class ReadyScreen(QWidget):
    launch_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        lay.addStretch()
        tick = _label('✓', 'font-size:56px; color:#30cc74;')
        tick.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(tick)
        ready_lbl = _label(t('Ready!'), 'font-size:22px; font-weight:bold; color:#e8e8f0;')
        ready_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(ready_lbl)
        sub = _label(t('Setup is complete. You can start the app.'), 'color:#a0a0b8;')
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(sub)
        lay.addStretch()
        btn = QPushButton(t('Start the app'))
        btn.clicked.connect(self.launch_requested)
        lay.addWidget(btn)


def should_show_wizard():
    """True if no translation model is installed and DeepL is not configured."""
    from lingolay.core.config import get_settings
    from lingolay.models.manager import get_model_manager
    s = get_settings()
    if s.translation_engine == 'deepl' and s.deepl_api_key:
        return False
    if (s.get_nllb_model_path() / 'model.bin').exists():
        return False
    return not get_model_manager().any_model_installed()


class SetupWizard(QDialog):
    wizard_complete = Signal()

    SCREEN_MODEL = 0
    SCREEN_DOWNLOAD = 1
    SCREEN_READY = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._stack.setCurrentIndex(self.SCREEN_MODEL)

    def _setup_ui(self):
        self.setWindowTitle(f"{__app_name__} — {t('Setup')}")
        self.setFixedSize(560, 560)
        self.setStyleSheet(_STYLE)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(36, 32, 36, 32)
        outer.setSpacing(0)
        brand_row = QHBoxLayout()
        brand_row.addWidget(_label(__app_name__, 'font-size:16px; font-weight:bold; color:#ff6929;'))
        brand_row.addStretch()
        outer.addLayout(brand_row)
        outer.addSpacing(24)
        self._stack = QStackedWidget()
        outer.addWidget(self._stack, 1)
        self._model_screen = ModelSelectScreen()
        self._dl_screen = DownloadScreen()
        self._ready_screen = ReadyScreen()
        self._stack.addWidget(self._model_screen)
        self._stack.addWidget(self._dl_screen)
        self._stack.addWidget(self._ready_screen)
        self._model_screen.models_selected.connect(self._on_models_selected)
        self._model_screen.skip_requested.connect(self._finish)
        self._dl_screen.download_done.connect(self._on_download_done)
        self._ready_screen.launch_requested.connect(self._finish)
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.center().x() - self.width() // 2, geo.center().y() - self.height() // 2)

    def _finish(self):
        self.accept()
        self.wizard_complete.emit()

    def _on_models_selected(self, model_ids):
        self._stack.setCurrentIndex(self.SCREEN_DOWNLOAD)
        self._dl_screen.start_download(model_ids)

    def _on_download_done(self, success, msg):
        if success:
            self._stack.setCurrentIndex(self.SCREEN_READY)
        elif msg == 'cancelled':
            self._stack.setCurrentIndex(self.SCREEN_MODEL)
        # On error the message stays visible on the download screen; the user can close the window and retry.
