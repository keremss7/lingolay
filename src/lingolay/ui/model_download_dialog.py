from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QVBoxLayout

from lingolay.i18n import t
from lingolay.ui.setup_wizard import _STYLE, DownloadScreen


class ModelDownloadDialog(QDialog):
    """Progress dialog for downloading individual models/voices from the settings page."""

    def __init__(self, model_ids, parent=None, title=None):
        super().__init__(parent)
        if isinstance(model_ids, str):
            model_ids = [model_ids]
        self._success = False
        self.setWindowTitle(title or t('Download model'))
        self.setMinimumSize(520, 460)
        self.resize(540, 480)
        self.setStyleSheet(_STYLE)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        self._dl_screen = DownloadScreen()
        lay.addWidget(self._dl_screen)
        btn_row = QHBoxLayout()
        self._btn_close = QPushButton(t('Close'))
        self._btn_close.setObjectName('secondary')
        self._btn_close.setEnabled(False)
        self._btn_close.clicked.connect(self.accept)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_close)
        lay.addLayout(btn_row)
        self._dl_screen.download_done.connect(self._on_done)
        self._dl_screen.start_download(model_ids)

    def _on_done(self, success, msg):
        self._success = success
        self._btn_close.setEnabled(True)

    def reject(self):
        # Closing the window cancels the download
        if not self._btn_close.isEnabled():
            self._dl_screen._on_cancel()
            return
        super().reject()

    @property
    def succeeded(self):
        return self._success
