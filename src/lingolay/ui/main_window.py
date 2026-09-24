import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QKeySequence, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFontComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from lingolay import __app_name__, __version__
from lingolay.capture.region import RegionSelector
from lingolay.core.config import Profile, get_settings, save_settings
from lingolay.core.hotkeys import ACTION_LABELS, HotkeyManager, parse_hotkey_string
from lingolay.core.pipeline import Pipeline
from lingolay.i18n import available_languages, t
from lingolay.languages import LANGUAGES, display_name, get_language
from lingolay.overlay.window import OverlayWindow

logger = logging.getLogger(__name__)


# ── Color palette ──────────────────────────────────────────────────────────────
BG = '#0d0d0f'
SURFACE = '#161619'
SURFACE2 = '#1e1e22'
SURFACE3 = '#262629'
BORDER = '#28282e'
BORDER2 = '#333339'
ACCENT = '#ff6929'
ACCENT_H = '#ff7f44'
ACCENT_D = '#e05420'
ACCENT_G = 'rgba(255,105,41,0.12)'
RED = '#f04040'
RED_H = '#f55b5b'
RED_G = 'rgba(240,64,64,0.10)'
GREEN = '#30cc74'
GREEN_G = 'rgba(48,204,116,0.12)'
TEXT = '#ececef'
TEXT2 = '#8a8a92'
TEXT3 = '#4a4a52'
MONO = "'Consolas', 'Menlo', 'DejaVu Sans Mono', monospace"

STYLE = f"""
QMainWindow, QWidget {{
    background: {BG};
    color: {TEXT};
    font-size: 13px;
}}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 4px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {BORDER2}; border-radius: 2px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QPushButton {{
    background: {ACCENT}; color: #ffffff; border: none; border-radius: 9px;
    padding: 10px 22px; font-weight: 700; font-size: 13px;
}}
QPushButton:hover {{ background: {ACCENT_H}; }}
QPushButton:pressed {{ background: {ACCENT_D}; }}
QPushButton:disabled {{ background: {SURFACE2}; color: {TEXT3}; border: 1px solid {BORDER}; }}

QPushButton#btn_stop {{ background: {RED}; color: #ffffff; }}
QPushButton#btn_stop:hover {{ background: {RED_H}; }}
QPushButton#btn_stop:disabled {{ background: {SURFACE2}; color: {TEXT3}; border: 1px solid {BORDER}; }}

QPushButton#btn_sec {{ background: {SURFACE2}; color: {TEXT}; border: 1px solid {BORDER2}; font-weight: 600; }}
QPushButton#btn_sec:hover {{ background: {SURFACE3}; border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton#btn_sec:checked {{ background: {ACCENT}; border-color: {ACCENT}; color: #ffffff; font-weight: 700; }}
QPushButton#btn_sec:checked:hover {{ background: {ACCENT_H}; border-color: {ACCENT_H}; }}

QPushButton#btn_save {{ background: transparent; color: {ACCENT}; border: 1.5px solid {ACCENT}; font-weight: 700; border-radius: 8px; }}
QPushButton#btn_save:hover {{ background: {ACCENT}; color: #ffffff; }}
QPushButton#btn_save:pressed {{ background: {ACCENT_D}; border-color: {ACCENT_D}; color: #ffffff; }}
QPushButton#btn_save:disabled {{ background: {SURFACE2}; color: {TEXT3}; border: 1px solid {BORDER2}; font-weight: 600; }}

QPushButton#btn_save_full {{ background: {SURFACE2}; color: {TEXT}; border: 1.5px solid {BORDER2}; font-weight: 700; border-radius: 9px; }}
QPushButton#btn_save_full:hover {{ background: {SURFACE3}; border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton#btn_save_full:pressed {{ background: {ACCENT_G}; border-color: {ACCENT}; color: {ACCENT}; }}

QPushButton#btn_del {{ background: transparent; border: 1px solid #2e1f1f; color: #8a4040; padding: 9px 12px; border-radius: 9px; font-weight: 600; }}
QPushButton#btn_del:hover {{ background: {RED_G}; border-color: {RED}; color: {RED}; }}

QLineEdit, QSpinBox {{
    background: {SURFACE3}; border: 1px solid {BORDER2}; border-radius: 8px; padding: 8px 11px;
    color: {TEXT}; selection-background-color: {ACCENT}; selection-color: #fff;
}}
QLineEdit:focus, QSpinBox:focus {{ border-color: {ACCENT}; }}
QSpinBox::up-button, QSpinBox::down-button {{ background: {SURFACE2}; border: none; width: 18px; }}

QComboBox {{ background: {SURFACE3}; border: 1px solid {BORDER2}; border-radius: 8px; padding: 8px 11px; color: {TEXT}; }}
QComboBox:hover {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE}; border: 1px solid {BORDER2}; border-radius: 7px; color: {TEXT};
    selection-background-color: {ACCENT_G}; selection-color: {ACCENT}; outline: none; padding: 4px;
}}

QCheckBox {{ spacing: 10px; color: {TEXT}; }}
QCheckBox::indicator {{ width: 17px; height: 17px; border: 1.5px solid {BORDER2}; border-radius: 5px; background: {SURFACE3}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}

QSlider::groove:horizontal {{ height: 4px; background: {BORDER2}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: #ffffff; width: 14px; margin: -6px 0; border-radius: 7px; }}

QStatusBar {{ background: #0a0a0c; color: {TEXT2}; font-size: 11px; border-top: 1px solid {BORDER}; padding: 3px 10px; }}
QToolTip {{ background: {SURFACE}; border: 1px solid {BORDER2}; color: {TEXT}; padding: 5px 9px; border-radius: 6px; }}
"""


def _fmt_size_mb(mb):
    """558 → '558 MB',  1225 → '1.2 GB'."""
    return f'{mb / 1024:.1f} GB' if mb >= 1024 else f'{mb} MB'


def _asset_path(name):
    base = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent)) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
    return base / 'assets' / name


# ── Small helper widgets ────────────────────────────────────────────────
class NoWheelComboBox(QComboBox):
    """Ignores the mouse wheel so scrolling the page never changes the value by accident."""
    def wheelEvent(self, event):
        event.ignore()


class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()


class NoWheelFontComboBox(QFontComboBox):
    def wheelEvent(self, event):
        event.ignore()


class Divider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFixedHeight(1)
        self.setStyleSheet(f'background: {BORDER}; border: none;')


class StatusDot(QLabel):
    _COLORS = {'idle': TEXT3, 'loading': ACCENT, 'running': GREEN, 'error': RED}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(8, 8)
        self._color = QColor(TEXT3)

    def set_state(self, state):
        self._color = QColor(self._COLORS.get(state, TEXT3))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(self._color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, 8, 8)


class MetricCard(QFrame):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f'QFrame {{ background: {SURFACE2}; border: 1px solid {BORDER}; border-radius: 10px; }}')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 8)
        lay.setSpacing(4)
        self._val = QLabel('—')
        self._val.setStyleSheet(f'color: {ACCENT}; font-size: 17px; font-weight: 700; font-family: {MONO}; border: none;')
        self._val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl = QLabel(label.upper())
        self._lbl.setStyleSheet(f'color: {TEXT2}; font-size: 9px; font-weight: 700; letter-spacing: 0.8px; border: none;')
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._val)
        lay.addWidget(self._lbl)

    def set_value(self, v):
        self._val.setText(v)


class HotkeyEditDialog(QDialog):
    def __init__(self, action_label, current_key, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t('Change shortcut'))
        self.setModal(True)
        self.setFixedSize(380, 190)
        self.setStyleSheet(f'QDialog {{ background: {BG}; }} QLabel {{ background: transparent; color: {TEXT}; }}')
        self._captured = ''
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        title = QLabel(t('New shortcut for <b>{action}</b>:', action=action_label))
        lay.addWidget(title)
        self._badge = QLabel(current_key or '—')
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setFixedHeight(44)
        self._badge.setStyleSheet(f"""
            QLabel {{
                background: {SURFACE2}; color: {ACCENT}; border: 1px solid {BORDER2};
                border-bottom: 3px solid {ACCENT}; border-radius: 8px;
                font-family: {MONO}; font-size: 16px; font-weight: 700;
            }}""")
        lay.addWidget(self._badge)
        hint = QLabel(t('Press Ctrl / Alt / Shift + a key…'))
        hint.setStyleSheet(f'color: {TEXT2}; font-size: 11px;')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(hint)
        self._lbl_err = QLabel('')
        self._lbl_err.setStyleSheet(f'color: {RED}; font-size: 11px;')
        self._lbl_err.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._lbl_err)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_cancel = QPushButton(t('Cancel'))
        btn_cancel.setObjectName('btn_sec')
        self._btn_ok = QPushButton(t('Apply'))
        self._btn_ok.setEnabled(False)
        btn_cancel.clicked.connect(self.reject)
        self._btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(self._btn_ok)
        lay.addLayout(btn_row)

    def keyPressEvent(self, event):
        key = event.key()
        if key in {Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift, Qt.Key.Key_Meta, Qt.Key.Key_AltGr}:
            return
        mods = event.modifiers()
        parts = []
        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append('Ctrl')
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append('Alt')
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append('Shift')
        if mods & Qt.KeyboardModifier.MetaModifier:
            parts.append('Win')
        if not parts:
            self._lbl_err.setText(t('At least one modifier is required (Ctrl / Alt / Shift)'))
            return
        key_name = QKeySequence(key).toString().upper()
        if not key_name:
            self._lbl_err.setText(t('This key is not supported.'))
            return
        key_str = '+'.join(parts + [key_name])
        if parse_hotkey_string(key_str) is None:
            self._lbl_err.setText(t("'{key}' could not be mapped, try another key.", key=key_name))
            return
        self._lbl_err.setText('')
        self._captured = key_str
        self._badge.setText(key_str)
        self._btn_ok.setEnabled(True)

    def get_key(self):
        return self._captured


class HotkeyBadge(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"""
            QLabel {{
                background: {SURFACE2}; color: {TEXT}; border: 1px solid {BORDER2};
                border-bottom: 2px solid {BORDER2}; border-radius: 6px; padding: 3px 9px;
                font-family: {MONO}; font-size: 11px; font-weight: 600;
            }}""")


class SectionCard(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName('section_card')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f'QWidget#section_card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        title_row = QWidget()
        title_row.setStyleSheet('background: transparent;')
        tr_lay = QHBoxLayout(title_row)
        tr_lay.setContentsMargins(16, 12, 16, 8)
        tr_lay.setSpacing(8)
        bar = QFrame()
        bar.setFixedSize(3, 13)
        bar.setStyleSheet(f'background: {ACCENT}; border-radius: 2px;')
        tr_lay.addWidget(bar, alignment=Qt.AlignmentFlag.AlignVCenter)
        lbl = QLabel(title.upper())
        lbl.setStyleSheet(f'color: {TEXT2}; font-size: 10px; font-weight: 700; letter-spacing: 0.9px; background: transparent;')
        tr_lay.addWidget(lbl)
        tr_lay.addStretch()
        self._content_widget = QWidget()
        self._content_widget.setStyleSheet('background: transparent;')
        self._inner = QVBoxLayout(self._content_widget)
        self._inner.setContentsMargins(16, 4, 16, 16)
        self._inner.setSpacing(8)
        outer.addWidget(title_row)
        outer.addWidget(self._content_widget)

    def add_row(self, layout):
        self._inner.addLayout(layout)

    def add_widget(self, widget, *args):
        self._inner.addWidget(widget, *args)

    def add_divider(self):
        self._inner.addWidget(Divider())

    def add_spacing(self, n):
        self._inner.addSpacing(n)


class InfoBox(QLabel):
    # style → (background, text color, border)
    _STYLES = {
        'info': ('rgba(60,140,255,0.10)', '#8cc4ff', 'rgba(60,140,255,0.30)'),
        'tip': ('rgba(48,204,116,0.10)', '#5fe09a', 'rgba(48,204,116,0.30)'),
        'warn': ('rgba(255,140,0,0.10)', '#ffb35c', 'rgba(255,140,0,0.30)'),
    }

    def __init__(self, text, style='info', parent=None):
        super().__init__(text, parent)
        self.setWordWrap(True)
        bg, color, border = self._STYLES.get(style, self._STYLES['info'])
        self.setStyleSheet(f'QLabel {{ background: {bg}; color: {color}; border: 1px solid {border}; border-radius: 8px; padding: 8px 12px; font-size: 11px; }}')


def _field_label(text, width=96):
    lbl = QLabel(text)
    lbl.setStyleSheet(f'color: {TEXT2};')
    lbl.setFixedWidth(width)
    return lbl


# ── Main window ──────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    # Hotkeys fire on a background thread → forwarded to the GUI thread via signals
    _sig_hk_start_stop = Signal()
    _sig_hk_select_region = Signal()
    _sig_hk_toggle_overlay = Signal()
    _sig_hk_toggle_preview = Signal()
    _sig_hk_toggle_window = Signal()
    _sig_hk_game_mode = Signal()
    _sig_hk_toggle_tts = Signal()

    def __init__(self):
        super().__init__()
        self._region_selector = RegionSelector()
        self._overlay = OverlayWindow()
        self._pipeline = Pipeline()
        self._hotkeys = HotkeyManager()
        self._current_profile = None
        self._borderless_state = None
        self._tts_engine = None
        self._tts_timer = QTimer(self)
        self._tts_timer.setInterval(25)
        self._tts_timer.timeout.connect(self._poll_tts_playback)
        icon = _asset_path('icon.png')
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self._build_ui()
        self._connect_all()
        self._setup_hotkeys()
        self._load_settings_to_ui()
        self._overlay_shown_once = False
        QTimer.singleShot(50, self._pipeline.initialize)
        self.setWindowTitle(__app_name__)
        self.resize(920, 760)
        self.setMinimumSize(800, 640)

    # ── Layout skeleton ──────────────────────────────────────────────────────────
    def _build_ui(self):
        self.setStyleSheet(STYLE)
        central = QWidget()
        central.setStyleSheet(f'background: {BG};')
        self.setCentralWidget(central)
        main_lay = QHBoxLayout(central)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        main_lay.addWidget(self._make_sidebar())
        self._pages = QStackedWidget()
        self._pages.addWidget(self._wrap_scroll(self._make_home_page()))
        self._pages.addWidget(self._wrap_scroll(self._make_engines_page()))
        self._pages.addWidget(self._wrap_scroll(self._make_appearance_page()))
        self._pages.addWidget(self._wrap_scroll(self._make_hotkeys_page()))
        main_lay.addWidget(self._pages, 1)
        self._sb = QStatusBar()
        self._sb.showMessage(t('Ready  ·  Ctrl+Alt+S Start/Stop  ·  Ctrl+Alt+R Region  ·  Ctrl+Alt+W Window'))
        self.setStatusBar(self._sb)

    def _wrap_scroll(self, content):
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.Shape.NoFrame)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sc.setStyleSheet(f'QScrollArea {{ background: {BG}; border: none; }}')
        sc.setWidget(content)
        return sc

    def _make_sidebar(self):
        sb = QWidget()
        sb.setObjectName('sidebar')
        sb.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        sb.setFixedWidth(212)
        sb.setStyleSheet(f'QWidget#sidebar {{ background: #08080a; border-right: 1px solid {BORDER}; }}')
        lay = QVBoxLayout(sb)
        lay.setContentsMargins(14, 20, 14, 14)
        lay.setSpacing(6)

        brand = QWidget()
        brand.setStyleSheet('background: transparent;')
        b_lay = QHBoxLayout(brand)
        b_lay.setContentsMargins(2, 0, 0, 0)
        b_lay.setSpacing(10)
        logo = QFrame()
        logo.setFixedSize(36, 36)
        logo.setStyleSheet(f'background: {ACCENT}; border-radius: 9px;')
        logo_lbl = QLabel('L', logo)
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_lbl.setGeometry(0, 0, 36, 36)
        logo_lbl.setStyleSheet('color: #ffffff; font-size: 19px; font-weight: 900; background: transparent;')
        b_lay.addWidget(logo)
        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        name = QLabel(__app_name__)
        name.setStyleSheet(f'color: {TEXT}; font-size: 16px; font-weight: 800; background: transparent;')
        ver = QLabel(f'v{__version__}')
        ver.setStyleSheet(f'color: {TEXT2}; font-size: 10px; font-weight: 700; background: transparent;')
        text_col.addWidget(name)
        text_col.addWidget(ver)
        b_lay.addLayout(text_col)
        b_lay.addStretch()
        lay.addWidget(brand)
        lay.addSpacing(24)

        section = QLabel(t('MENU'))
        section.setStyleSheet(f'color: {TEXT3}; font-size: 9px; font-weight: 800; letter-spacing: 1.2px; padding: 0 6px 6px 6px; background: transparent;')
        lay.addWidget(section)
        self._nav_buttons = []
        tabs = [('⏵', t('Control')), ('⚙', t('Translation')), ('◐', t('Appearance')), ('⌨', t('Shortcuts'))]
        for i, (icon, label) in enumerate(tabs):
            btn = self._make_nav_btn(icon, label, i)
            self._nav_buttons.append(btn)
            lay.addWidget(btn)
        self._nav_buttons[0].setChecked(True)
        lay.addStretch()

        self._btn_diagnostic = QPushButton(f"   ?     {t('Diagnostics / Help')}")
        self._btn_diagnostic.setObjectName('nav_btn')
        self._btn_diagnostic.setMinimumHeight(36)
        self._btn_diagnostic.setStyleSheet(f"""
            QPushButton#nav_btn {{ background: transparent; color: {TEXT2}; border: 1px solid transparent;
                border-radius: 8px; padding: 0; text-align: left; font-size: 12px; font-weight: 600; }}
            QPushButton#nav_btn:hover {{ background: rgba(255,105,41,0.08); color: {TEXT}; }}""")
        self._btn_diagnostic.clicked.connect(self._open_diagnostic_dialog)
        lay.addWidget(self._btn_diagnostic)

        foot = QFrame()
        foot.setStyleSheet(f'background: transparent; border-top: 1px solid {BORDER};')
        f_lay = QHBoxLayout(foot)
        f_lay.setContentsMargins(6, 10, 4, 0)
        f_lay.setSpacing(8)
        self._sidebar_dot = StatusDot()
        f_lay.addWidget(self._sidebar_dot)
        self._sidebar_status = QLabel(t('Loading'))
        self._sidebar_status.setStyleSheet(f'color: {TEXT2}; font-size: 11px; font-weight: 600; background: transparent; border: none;')
        self._sidebar_status.setWordWrap(True)
        f_lay.addWidget(self._sidebar_status, 1)
        lay.addWidget(foot)
        return sb

    def _make_nav_btn(self, icon, label, index):
        btn = QPushButton(f'   {icon}     {label}')
        btn.setObjectName('nav_btn')
        btn.setCheckable(True)
        btn.setMinimumHeight(40)
        btn.setStyleSheet(f"""
            QPushButton#nav_btn {{ background: transparent; color: {TEXT2}; border: 1px solid transparent;
                border-radius: 8px; padding: 0; text-align: left; font-size: 13px; font-weight: 600; }}
            QPushButton#nav_btn:hover {{ background: {SURFACE}; color: {TEXT}; }}
            QPushButton#nav_btn:checked {{ background: {ACCENT_G}; color: {ACCENT};
                border: 1px solid rgba(255,105,41,0.30); font-weight: 700; }}""")
        btn.clicked.connect(lambda checked=False, i=index: self._switch_page(i))
        return btn

    def _switch_page(self, idx):
        for i, btn in enumerate(self._nav_buttons):
            btn.blockSignals(True)
            btn.setChecked(i == idx)
            btn.blockSignals(False)
        self._pages.setCurrentIndex(idx)

    def _page(self, title, subtitle):
        page = QWidget()
        page.setStyleSheet(f'background: {BG};')
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 22, 24, 24)
        lay.setSpacing(12)
        head = QWidget()
        head.setStyleSheet('background: transparent;')
        h_lay = QVBoxLayout(head)
        h_lay.setContentsMargins(0, 0, 0, 6)
        h_lay.setSpacing(2)
        tl = QLabel(title)
        tl.setStyleSheet(f'color: {TEXT}; font-size: 21px; font-weight: 800; background: transparent;')
        h_lay.addWidget(tl)
        if subtitle:
            sl = QLabel(subtitle)
            sl.setStyleSheet(f'color: {TEXT2}; font-size: 12px; background: transparent;')
            h_lay.addWidget(sl)
        lay.addWidget(head)
        return page, lay

    # ── Pages ─────────────────────────────────────────────────────────
    def _make_home_page(self):
        page, lay = self._page(t('Control'), t('Translator status, region selection and metrics'))
        lay.addWidget(self._make_status_card())
        lay.addWidget(self._make_region_card())
        lay.addWidget(self._make_control_card())
        lay.addWidget(self._make_metrics_card())
        self._lbl_ocr = QLabel('')
        self._lbl_ocr.setWordWrap(True)
        self._lbl_ocr.setMaximumHeight(50)
        self._lbl_ocr.setStyleSheet(f'color: {TEXT2}; font-size: 11px; padding: 4px 8px 4px 12px; border-left: 2px solid {BORDER2};')
        lay.addWidget(self._lbl_ocr)
        lay.addStretch()
        return page

    def _make_engines_page(self):
        page, lay = self._page(t('Translation'), t('Languages, translation engine, models and voice dubbing'))
        lay.addWidget(self._make_languages_card())
        lay.addWidget(self._make_settings_card())
        lay.addWidget(self._make_tts_card())
        lay.addStretch()
        return page

    def _make_appearance_page(self):
        page, lay = self._page(t('Appearance'), t('Overlay colors, size, transparency and interface language'))
        lay.addWidget(self._make_overlay_style_card())
        lay.addWidget(self._make_general_card())
        lay.addStretch()
        return page

    def _make_hotkeys_page(self):
        page, lay = self._page(t('Shortcuts'), t('Global keyboard shortcuts — work even inside games'))
        lay.addWidget(self._make_hotkeys_card())
        lay.addStretch()
        return page

    # ── Control page cards ─────────────────────────────────────────
    def _make_status_card(self):
        card = SectionCard(t('Translator status'))
        row = QHBoxLayout()
        row.setSpacing(10)
        self._status_dot = StatusDot()
        self._lbl_tr = QLabel(t('Loading model...'))
        self._lbl_tr.setStyleSheet(f'color: {ACCENT}; font-weight: 700; font-size: 13px;')
        self._lbl_tr.setWordWrap(True)
        row.addWidget(self._status_dot, alignment=Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self._lbl_tr, 1)
        card.add_row(row)
        self._lbl_pair = QLabel('')
        self._lbl_pair.setStyleSheet(f'color: {TEXT2}; font-size: 12px;')
        card.add_widget(self._lbl_pair)
        return card

    def _make_region_card(self):
        card = SectionCard(t('Capture region'))
        card.add_widget(InfoBox(t('Draw a rectangle around the subtitle area with your mouse. '
                                  'For movies pick the bottom of the screen, for games the in-game subtitle box.\n'
                                  'Tip: save a profile so you never have to select it again.'), 'info'))
        self._lbl_region = QLabel(t('No region selected yet'))
        self._lbl_region.setStyleSheet(f'color: {TEXT2}; font-size: 12px; font-family: {MONO};')
        self._lbl_region.setWordWrap(True)
        card.add_widget(self._lbl_region)
        self._btn_sel_reg = QPushButton(f"⊹  {t('Select region')}")
        self._btn_sel_reg.setObjectName('btn_save')
        self._btn_sel_reg.setMinimumHeight(38)
        card.add_widget(self._btn_sel_reg)
        card.add_divider()
        card.add_spacing(4)
        prof_row = QHBoxLayout()
        self._combo_prof = NoWheelComboBox()
        self._combo_prof.setMinimumHeight(36)
        prof_row.addWidget(self._combo_prof, 1)
        self._btn_del_prof = QPushButton(t('Delete'))
        self._btn_del_prof.setObjectName('btn_del')
        self._btn_del_prof.setFixedWidth(72)
        self._btn_del_prof.setEnabled(False)
        prof_row.addWidget(self._btn_del_prof)
        card.add_row(prof_row)
        save_row = QHBoxLayout()
        save_row.setSpacing(8)
        self._edit_prof_name = QLineEdit()
        self._edit_prof_name.setPlaceholderText(t('Profile name (e.g. Elden Ring, Netflix)…'))
        self._edit_prof_name.setMinimumHeight(36)
        self._btn_save_prof = QPushButton(t('Save'))
        self._btn_save_prof.setObjectName('btn_save')
        self._btn_save_prof.setEnabled(False)
        self._btn_save_prof.setFixedWidth(86)
        self._btn_save_prof.setMinimumHeight(36)
        self._edit_prof_name.textChanged.connect(self._update_save_prof_btn)
        save_row.addWidget(self._edit_prof_name)
        save_row.addWidget(self._btn_save_prof)
        card.add_row(save_row)
        self._refresh_profiles()
        return card

    def _make_control_card(self):
        card = SectionCard(t('Control'))
        card.add_widget(InfoBox(t('Movies / series (Netflix, YouTube…) →  Select region  ▶  Start\n'
                                  'Games →  Select region  ▶  Game mode  (window hides automatically)\n'
                                  'Run games in Windowed or Borderless mode — exclusive fullscreen cannot be captured.'), 'tip'))
        card.add_spacing(2)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._btn_start = QPushButton(f"▶  {t('Start')}")
        self._btn_start.setEnabled(False)
        self._btn_start.setMinimumHeight(46)
        self._btn_stop = QPushButton(f"■  {t('Stop')}")
        self._btn_stop.setObjectName('btn_stop')
        self._btn_stop.setEnabled(False)
        self._btn_stop.setMinimumHeight(46)
        btn_row.addWidget(self._btn_start)
        btn_row.addWidget(self._btn_stop)
        card.add_row(btn_row)
        self._btn_game_mode = QPushButton(f"🎮  {t('Game mode')}")
        self._btn_game_mode.setObjectName('btn_sec')
        self._btn_game_mode.setMinimumHeight(36)
        self._btn_game_mode.setToolTip(t('Starts translating, hides this window and switches the game window to borderless.\n'
                                         'Bring the window back with Ctrl+Alt+W.'))
        self._btn_game_mode.clicked.connect(self._enter_game_mode)
        card.add_widget(self._btn_game_mode)
        card.add_spacing(4)
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(8)
        self._btn_preview = QPushButton(f"◎  {t('OCR preview')}")
        self._btn_preview.setObjectName('btn_sec')
        self._btn_preview.setCheckable(True)
        self._btn_preview.setMinimumHeight(36)
        self._btn_preview.setToolTip(t('Shows the raw recognized text without translating — useful for tuning the region.'))
        self._btn_overlay = QPushButton(f"◉  {t('Overlay')}")
        self._btn_overlay.setObjectName('btn_sec')
        self._btn_overlay.setCheckable(True)
        self._btn_overlay.setChecked(True)
        self._btn_overlay.setMinimumHeight(36)
        self._btn_tts = QPushButton(f"🔊  {t('Dubbing')}")
        self._btn_tts.setObjectName('btn_sec')
        self._btn_tts.setCheckable(True)
        self._btn_tts.setMinimumHeight(36)
        self._btn_tts.setToolTip(t('Reads translations aloud with a local neural voice (offline).\nShortcut: Ctrl+Alt+D'))
        toggle_row.addWidget(self._btn_preview)
        toggle_row.addWidget(self._btn_overlay)
        toggle_row.addWidget(self._btn_tts)
        card.add_row(toggle_row)
        return card

    def _make_metrics_card(self):
        card = SectionCard(t('Performance'))
        row = QHBoxLayout()
        row.setSpacing(8)
        self._c_fps = MetricCard('FPS')
        self._c_ocr = MetricCard(t('OCR ms'))
        self._c_tr = MetricCard(t('Translate ms'))
        self._c_cache = MetricCard(t('Cache'))
        for c in (self._c_fps, self._c_ocr, self._c_tr, self._c_cache):
            row.addWidget(c)
        card.add_row(row)
        return card

    # ── Translation page cards ──────────────────────────────────────────
    def _make_languages_card(self):
        card = SectionCard(t('Languages'))
        row = QHBoxLayout()
        row.setSpacing(8)
        self._combo_src = NoWheelComboBox()
        self._combo_tgt = NoWheelComboBox()
        for code in LANGUAGES:
            self._combo_src.addItem(display_name(code), code)
            self._combo_tgt.addItem(display_name(code), code)
        for c in (self._combo_src, self._combo_tgt):
            c.setMinimumHeight(36)
        self._btn_swap = QPushButton('↔')
        self._btn_swap.setObjectName('btn_sec')
        self._btn_swap.setFixedWidth(46)
        self._btn_swap.setStyleSheet('QPushButton#btn_sec { padding: 0; font-size: 18px; }')
        self._btn_swap.setToolTip(t('Swap languages'))
        self._btn_swap.clicked.connect(self._swap_languages)
        src_col = QVBoxLayout()
        src_col.addWidget(_field_label(t('On screen'), 200))
        src_col.addWidget(self._combo_src)
        tgt_col = QVBoxLayout()
        tgt_col.addWidget(_field_label(t('Translate to'), 200))
        tgt_col.addWidget(self._combo_tgt)
        row.addLayout(src_col, 1)
        row.addWidget(self._btn_swap, alignment=Qt.AlignmentFlag.AlignBottom)
        row.addLayout(tgt_col, 1)
        card.add_row(row)
        if sys.platform == 'win32':
            card.add_widget(InfoBox(t('Windows OCR needs the language pack of the on-screen language: '
                                      'Settings → Time & Language → Language → Add a language (with “Optical character recognition”).'), 'info'))
        else:
            card.add_widget(InfoBox(t('On this platform Tesseract OCR is used. Install the language data for the on-screen language '
                                      '(e.g. tesseract-ocr-jpn).'), 'info'))
        btn = QPushButton(t('Apply languages'))
        btn.setObjectName('btn_save_full')
        btn.setMinimumHeight(38)
        btn.clicked.connect(self._apply_languages)
        card.add_widget(btn)
        return card

    def _make_settings_card(self):
        card = SectionCard(t('Translation engine'))
        card.add_widget(InfoBox(t('• NLLB Fast (600M) — runs on any PC, good quality, fully offline\n'
                                  '• NLLB Quality (1.3B) — better quality, needs more RAM / a GPU\n'
                                  '• DeepL API — best quality, zero GPU load; needs internet and your own free API key'), 'info'))
        card.add_spacing(4)
        engine_row = QHBoxLayout()
        self._combo_engine = NoWheelComboBox()
        self._combo_engine.setMinimumHeight(36)
        self._combo_engine.addItem(t('NLLB — Fast (600M, offline)'), 'nllb_fast')
        self._combo_engine.addItem(t('NLLB — Quality (1.3B, offline)'), 'nllb_quality')
        self._combo_engine.addItem(t('DeepL — API (online)'), 'deepl')
        self._combo_engine.currentIndexChanged.connect(self._on_engine_changed)
        engine_row.addWidget(_field_label(t('Engine:')))
        engine_row.addWidget(self._combo_engine)
        card.add_row(engine_row)

        self._nllb_controls = QWidget()
        self._nllb_controls.setStyleSheet('background: transparent;')
        nllb_layout = QVBoxLayout(self._nllb_controls)
        nllb_layout.setContentsMargins(0, 0, 0, 0)
        nllb_layout.setSpacing(6)
        path_row = QHBoxLayout()
        self._edit_model_path = QLineEdit()
        self._edit_model_path.setPlaceholderText(t('Folder containing model.bin'))
        self._btn_browse = QPushButton('…')
        self._btn_browse.setObjectName('btn_sec')
        self._btn_browse.setFixedWidth(44)
        self._btn_browse.setStyleSheet('QPushButton#btn_sec { padding: 0; font-size: 16px; }')
        self._btn_browse.setToolTip(t('Choose folder'))
        path_row.addWidget(_field_label(t('Model path:')))
        path_row.addWidget(self._edit_model_path)
        path_row.addWidget(self._btn_browse)
        nllb_layout.addLayout(path_row)
        self._chk_gpu = QCheckBox(t('Use GPU (CUDA, if available — faster)'))
        nllb_layout.addWidget(self._chk_gpu)
        nllb_layout.addSpacing(4)
        models_label = QLabel(t('LOCAL MODELS'))
        models_label.setStyleSheet(f'color: {TEXT2}; font-size: 10px; font-weight: 700; letter-spacing: 0.8px;')
        nllb_layout.addWidget(models_label)
        self._model_rows = {}
        from lingolay.models.manifest import MODELS
        nllb_layout.addWidget(self._make_model_row('fast', t('Fast model (600M)'), _fmt_size_mb(MODELS['fast'].approx_size_mb)))
        nllb_layout.addWidget(self._make_model_row('quality', t('Quality model (1.3B)'), _fmt_size_mb(MODELS['quality'].approx_size_mb)))
        lic = QLabel(t('NLLB-200 weights by Meta AI, licensed CC-BY-NC-4.0 (non-commercial). Downloaded from Hugging Face.'))
        lic.setWordWrap(True)
        lic.setStyleSheet(f'color: {TEXT3}; font-size: 10px;')
        nllb_layout.addWidget(lic)
        card.add_widget(self._nllb_controls)
        self._refresh_model_rows()

        self._deepl_controls = QWidget()
        self._deepl_controls.setStyleSheet('background: transparent;')
        deepl_layout = QVBoxLayout(self._deepl_controls)
        deepl_layout.setContentsMargins(0, 0, 0, 0)
        deepl_layout.setSpacing(6)
        key_row = QHBoxLayout()
        self._edit_deepl_key = QLineEdit()
        self._edit_deepl_key.setPlaceholderText(t('Your DeepL API key (free keys end with :fx)'))
        self._edit_deepl_key.setEchoMode(QLineEdit.EchoMode.Password)
        key_row.addWidget(_field_label(t('API key:')))
        key_row.addWidget(self._edit_deepl_key)
        deepl_layout.addLayout(key_row)
        plan_row = QHBoxLayout()
        self._combo_deepl_plan = NoWheelComboBox()
        self._combo_deepl_plan.setMinimumHeight(36)
        self._combo_deepl_plan.addItem(t('Free plan (500,000 characters/month)'), 'free')
        self._combo_deepl_plan.addItem(t('Pro plan'), 'pro')
        plan_row.addWidget(_field_label(t('Plan:')))
        plan_row.addWidget(self._combo_deepl_plan)
        deepl_layout.addLayout(plan_row)
        hint = QLabel(t('Create a free “DeepL API Free” account at deepl.com/pro-api. The key stays on your computer.'))
        hint.setWordWrap(True)
        hint.setStyleSheet(f'color: {TEXT2}; font-size: 11px;')
        deepl_layout.addWidget(hint)
        card.add_widget(self._deepl_controls)
        self._deepl_controls.setVisible(False)

        stab_row = QHBoxLayout()
        self._spin_stab = NoWheelSpinBox()
        self._spin_stab.setRange(1, 5)
        self._spin_stab.setValue(1)
        self._spin_stab.setToolTip(t('1 = translate instantly   3 = wait for stable text'))
        self._spin_stab.setFixedWidth(64)
        note = QLabel(t('frames'))
        note.setStyleSheet(f'color: {TEXT2}; font-size: 11px;')
        stab_row.addWidget(_field_label(t('Stability:')))
        stab_row.addWidget(self._spin_stab)
        stab_row.addWidget(note)
        stab_row.addStretch()
        card.add_row(stab_row)
        card.add_divider()
        card.add_spacing(4)
        self._btn_save_set = QPushButton(t('Save settings'))
        self._btn_save_set.setObjectName('btn_save_full')
        self._btn_save_set.setMinimumHeight(40)
        card.add_widget(self._btn_save_set)
        return card

    def _make_model_row(self, model_id, title, size):
        row = QFrame()
        row.setObjectName('model_row')
        row.setStyleSheet(f'QFrame#model_row {{ background: {SURFACE2}; border: 1px solid {BORDER}; border-radius: 8px; }}')
        lay = QHBoxLayout(row)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(8)
        dot = QLabel('●')
        dot.setFixedWidth(12)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f'color: {TEXT}; font-size: 12px; font-weight: 600; background: transparent; border: none;')
        size_lbl = QLabel(size)
        size_lbl.setStyleSheet(f'color: {TEXT2}; font-size: 11px; background: transparent; border: none;')
        btn = QPushButton(t('Download'))
        btn.setFixedWidth(96)
        btn.setFixedHeight(28)
        btn.clicked.connect(lambda checked=False, mid=model_id: self._download_specific_model(mid))
        lay.addWidget(dot)
        lay.addWidget(title_lbl)
        lay.addStretch()
        lay.addWidget(size_lbl)
        lay.addWidget(btn)
        row._dot = dot
        row._btn = btn
        self._model_rows[model_id] = row
        return row

    def _refresh_model_rows(self):
        from lingolay.models.manager import get_model_manager
        mgr = get_model_manager()
        for model_id, row in self._model_rows.items():
            if mgr.is_installed(model_id):
                row._dot.setStyleSheet(f'color: {GREEN}; font-size: 13px; background: transparent; border: none;')
                row._btn.setText(t('Installed ✓'))
                row._btn.setEnabled(False)
                row._btn.setStyleSheet(f"""QPushButton {{ background: transparent; color: {GREEN};
                    border: 1px solid rgba(48,204,116,0.45); border-radius: 7px; font-weight: 700; font-size: 11px; padding: 0; }}""")
            else:
                row._dot.setStyleSheet(f'color: {TEXT3}; font-size: 13px; background: transparent; border: none;')
                row._btn.setText(t('Download'))
                row._btn.setEnabled(True)
                row._btn.setStyleSheet(f'QPushButton {{ background: {ACCENT}; color: #fff; padding: 0; font-size: 11px; border-radius: 7px; }}'
                                       f'QPushButton:hover {{ background: {ACCENT_H}; }}')

    def _make_tts_card(self):
        from lingolay.tts.fast_dubbing import SPEED_LABELS
        card = SectionCard(t('Voice dubbing'))
        tts = get_settings().tts
        card.add_widget(InfoBox(t('Reads translations aloud with a natural neural voice (Piper). Runs fully LOCAL — '
                                  'no internet, very low latency. The voice for your target language is downloaded on first use (~60–75 MB).'), 'info'))
        speed_row = QHBoxLayout()
        self._cmb_tts_speed = NoWheelComboBox()
        for speed_id, label in SPEED_LABELS.items():
            self._cmb_tts_speed.addItem(t(label), speed_id)
        idx = self._cmb_tts_speed.findData(tts.speed)
        if idx >= 0:
            self._cmb_tts_speed.setCurrentIndex(idx)
        speed_row.addWidget(_field_label(t('Speech rate:')))
        speed_row.addWidget(self._cmb_tts_speed, 1)
        card.add_row(speed_row)

        self._sld_tts_volume, self._lbl_tts_vol_val = self._slider_row(card, t('Volume:'), 0, 100, tts.volume, lambda v: f'%{v}')
        self._sld_tts_gain, self._lbl_tts_gain_val = self._slider_row(card, t('Boost:'), 100, 400, tts.gain, lambda v: f'{v / 100:.1f}x')
        card.add_widget(InfoBox(t('If the voice is drowned out by the game, raise Boost — it amplifies the voice even when volume is at maximum.'), 'info'))
        card.add_divider()
        self._chk_duck = QCheckBox(t('Lower other apps’ volume while the voice speaks'))
        self._chk_duck.setChecked(tts.duck_enabled)
        card.add_widget(self._chk_duck)
        self._sld_duck, self._lbl_duck_val = self._slider_row(card, t('Lower to:'), 5, 100, tts.duck_level, lambda v: f'%{v}')
        self._sld_duck.setEnabled(tts.duck_enabled)
        self._chk_duck.toggled.connect(self._sld_duck.setEnabled)
        if sys.platform != 'win32':
            self._chk_duck.setEnabled(False)
            self._chk_duck.setToolTip(t('Only available on Windows'))
        card.add_divider()
        card.add_spacing(4)
        btn_apply_tts = QPushButton(t('Save dubbing settings'))
        btn_apply_tts.setObjectName('btn_save_full')
        btn_apply_tts.setMinimumHeight(38)
        btn_apply_tts.clicked.connect(self._apply_tts_settings)
        card.add_widget(btn_apply_tts)
        return card

    def _slider_row(self, card, label, lo, hi, value, fmt):
        row = QHBoxLayout()
        row.setSpacing(8)
        sld = QSlider(Qt.Orientation.Horizontal)
        sld.setRange(lo, hi)
        sld.setValue(value)
        val = QLabel(fmt(value))
        val.setStyleSheet(f'color: {TEXT2}; min-width: 48px;')
        sld.valueChanged.connect(lambda v: val.setText(fmt(v)))
        row.addWidget(_field_label(label))
        row.addWidget(sld, 1)
        row.addWidget(val)
        card.add_row(row)
        return sld, val

    # ── Appearance page cards ─────────────────────────────────────────
    def _make_overlay_style_card(self):
        card = SectionCard(t('Overlay style'))
        s = get_settings().overlay
        self._chk_backdrop = QCheckBox(t('Show background box'))
        self._chk_backdrop.setChecked(s.backdrop)
        self._chk_backdrop.toggled.connect(self._on_backdrop_toggle)
        card.add_widget(self._chk_backdrop)

        self._row_bg_color = QWidget()
        self._row_bg_color.setStyleSheet('background: transparent;')
        bg_row = QHBoxLayout(self._row_bg_color)
        bg_row.setContentsMargins(0, 0, 0, 0)
        bg_row.setSpacing(8)
        self._btn_bg_color = self._make_color_btn(s.backdrop_color)
        self._btn_bg_color.clicked.connect(lambda: self._pick_into(self._btn_bg_color, t('Background color')))
        bg_row.addWidget(_field_label(t('Background:')))
        bg_row.addWidget(self._btn_bg_color)
        bg_row.addStretch()
        alpha_lbl = QLabel(t('Opacity:'))
        alpha_lbl.setStyleSheet(f'color: {TEXT2};')
        self._spin_bg_alpha = NoWheelSpinBox()
        self._spin_bg_alpha.setRange(0, 255)
        self._spin_bg_alpha.setValue(s.backdrop_alpha)
        self._spin_bg_alpha.setFixedWidth(72)
        self._spin_bg_alpha.setToolTip(t('0 = fully transparent, 255 = fully opaque'))
        bg_row.addWidget(alpha_lbl)
        bg_row.addWidget(self._spin_bg_alpha)
        card.add_widget(self._row_bg_color)

        txt_row = QHBoxLayout()
        self._btn_txt_color = self._make_color_btn(s.text_color)
        self._btn_txt_color.clicked.connect(lambda: self._pick_into(self._btn_txt_color, t('Text color')))
        txt_row.addWidget(_field_label(t('Text color:')))
        txt_row.addWidget(self._btn_txt_color)
        txt_row.addStretch()
        card.add_row(txt_row)

        self._sld_font_size, self._lbl_font_size_val = self._slider_row(card, t('Font size:'), 12, 60, s.font_size, lambda v: f'{v} px')
        self._sld_font_size.valueChanged.connect(self._on_font_size_slide)

        font_row = QHBoxLayout()
        self._cmb_font_family = NoWheelFontComboBox()
        self._cmb_font_family.setCurrentFont(QFont(s.font_family))
        self._cmb_font_family.setMaximumWidth(260)
        font_row.addWidget(_field_label(t('Font:')))
        font_row.addWidget(self._cmb_font_family, 1)
        card.add_row(font_row)

        self._sld_max_width, self._lbl_max_width_val = self._slider_row(card, t('Max width:'), 30, 100, int(s.max_width_pct * 100), lambda v: f'%{v}')

        self._row_outline = QWidget()
        self._row_outline.setStyleSheet('background: transparent;')
        ol_row = QHBoxLayout(self._row_outline)
        ol_row.setContentsMargins(0, 0, 0, 0)
        ol_row.setSpacing(8)
        self._btn_ol_color = self._make_color_btn(s.outline_color)
        self._btn_ol_color.clicked.connect(lambda: self._pick_into(self._btn_ol_color, t('Outline color')))
        ol_row.addWidget(_field_label(t('Outline:')))
        ol_row.addWidget(self._btn_ol_color)
        ol_row.addStretch()
        ol_w_lbl = QLabel(t('Thickness:'))
        ol_w_lbl.setStyleSheet(f'color: {TEXT2};')
        self._spin_ol_width = NoWheelSpinBox()
        self._spin_ol_width.setRange(1, 8)
        self._spin_ol_width.setValue(s.outline_width)
        self._spin_ol_width.setFixedWidth(60)
        ol_row.addWidget(ol_w_lbl)
        ol_row.addWidget(self._spin_ol_width)
        card.add_widget(self._row_outline)
        self._on_backdrop_toggle(s.backdrop)

        self._chk_click_through = QCheckBox(t('Click-through overlay (mouse clicks pass to the game)'))
        self._chk_click_through.setChecked(s.click_through)
        card.add_widget(self._chk_click_through)
        card.add_divider()
        card.add_spacing(4)
        btn_apply = QPushButton(t('Preview / apply'))
        btn_apply.setObjectName('btn_save_full')
        btn_apply.setMinimumHeight(38)
        btn_apply.clicked.connect(self._apply_overlay_style)
        card.add_widget(btn_apply)
        return card

    def _make_general_card(self):
        card = SectionCard(t('Interface'))
        row = QHBoxLayout()
        self._combo_ui_lang = NoWheelComboBox()
        self._combo_ui_lang.setMinimumHeight(36)
        self._combo_ui_lang.addItem(t('System default'), '')
        for code, name in available_languages().items():
            self._combo_ui_lang.addItem(name, code)
        idx = self._combo_ui_lang.findData(get_settings().ui_language)
        self._combo_ui_lang.setCurrentIndex(max(0, idx))
        self._combo_ui_lang.currentIndexChanged.connect(self._on_ui_language_changed)
        row.addWidget(_field_label(t('Language:')))
        row.addWidget(self._combo_ui_lang, 1)
        card.add_row(row)
        card.add_widget(InfoBox(t('Want Lingolay in your language? Translating the interface is a single JSON file — see CONTRIBUTING.md on GitHub.'), 'tip'))
        return card

    def _make_hotkeys_card(self):
        card = SectionCard(t('Keyboard shortcuts'))
        if not self._hotkeys.is_available:
            card.add_widget(InfoBox(t('Global shortcuts are currently supported on Windows only.'), 'warn'))
        self._hotkey_badges = {}
        settings = get_settings()
        for action, desc in ACTION_LABELS.items():
            row = QHBoxLayout()
            row.setSpacing(10)
            badge = HotkeyBadge(settings.hotkeys.get(action, '—'))
            badge.setFixedWidth(140)
            self._hotkey_badges[action] = badge
            desc_lbl = QLabel(t(desc))
            desc_lbl.setStyleSheet(f'color: {TEXT2}; font-size: 12px;')
            btn_edit = QPushButton(t('Change'))
            btn_edit.setObjectName('btn_sec')
            btn_edit.setFixedHeight(28)
            btn_edit.setStyleSheet('QPushButton#btn_sec { font-size: 11px; padding: 3px 12px; border-radius: 6px; }')
            btn_edit.clicked.connect(lambda checked=False, a=action: self._edit_hotkey(a))
            row.addWidget(badge)
            row.addWidget(desc_lbl)
            row.addStretch()
            row.addWidget(btn_edit)
            card.add_row(row)
        return card

    # ── Signal wiring ──────────────────────────────────────────────────────
    def _connect_all(self):
        p = self._pipeline
        p.translation_ready.connect(self._on_translation)
        p.translation_error.connect(self._on_translation_error)
        p.ocr_text_ready.connect(self._on_ocr_text)
        p.status_updated.connect(self._on_status_update)
        p.error_occurred.connect(lambda msg: self._sb.showMessage(msg, 5000))
        p.translator_loading.connect(self._on_tr_loading)
        p.translator_ready.connect(self._on_tr_ready)
        p.translator_failed.connect(self._on_tr_failed)
        self._region_selector.region_selected.connect(self._on_region_selected)
        self._region_selector.selection_cancelled.connect(lambda: self._sb.showMessage(t('Region selection cancelled'), 3000))
        self._btn_sel_reg.clicked.connect(self._start_region_selection)
        self._btn_start.clicked.connect(self._start_pipeline)
        self._btn_stop.clicked.connect(self._stop_pipeline)
        self._btn_preview.toggled.connect(self._toggle_preview)
        self._btn_overlay.toggled.connect(lambda on: self._overlay.show() if on else self._overlay.hide())
        self._btn_save_prof.clicked.connect(self._save_profile)
        self._btn_del_prof.clicked.connect(self._delete_profile)
        self._combo_prof.currentIndexChanged.connect(self._load_profile)
        self._btn_save_set.clicked.connect(self._save_settings)
        self._btn_browse.clicked.connect(self._browse_model)
        self._btn_tts.toggled.connect(self._on_tts_toggle)
        self._sig_hk_start_stop.connect(self._toggle_start_stop)
        self._sig_hk_select_region.connect(self._start_region_selection)
        self._sig_hk_toggle_overlay.connect(self._btn_overlay.toggle)
        self._sig_hk_toggle_preview.connect(self._btn_preview.toggle)
        self._sig_hk_toggle_window.connect(self._toggle_window)
        self._sig_hk_game_mode.connect(self._enter_game_mode)
        self._sig_hk_toggle_tts.connect(self._btn_tts.toggle)

    def _setup_hotkeys(self):
        hm = self._hotkeys
        hm.set_callback('start_stop', self._sig_hk_start_stop.emit)
        hm.set_callback('select_region', self._sig_hk_select_region.emit)
        hm.set_callback('toggle_overlay', self._sig_hk_toggle_overlay.emit)
        hm.set_callback('toggle_preview', self._sig_hk_toggle_preview.emit)
        hm.set_callback('toggle_window', self._sig_hk_toggle_window.emit)
        hm.set_callback('game_mode', self._sig_hk_game_mode.emit)
        hm.set_callback('toggle_tts', self._sig_hk_toggle_tts.emit)
        hm.load_from_config(get_settings().hotkeys)
        hm.start()

    # ── Languages ───────────────────────────────────────────────────────────
    def _swap_languages(self):
        src, tgt = self._combo_src.currentIndex(), self._combo_tgt.currentIndex()
        self._combo_src.setCurrentIndex(tgt)
        self._combo_tgt.setCurrentIndex(src)

    def _update_pair_label(self):
        s = get_settings()
        self._lbl_pair.setText(f'{get_language(s.source_lang).native}  →  {get_language(s.target_lang).native}')

    def _apply_languages(self):
        s = get_settings()
        src = self._combo_src.currentData()
        tgt = self._combo_tgt.currentData()
        if src == tgt:
            QMessageBox.warning(self, __app_name__, t('Source and target language must be different.'))
            return
        if src == s.source_lang and tgt == s.target_lang:
            self._sb.showMessage(t('Languages unchanged.'), 3000)
            return
        s.source_lang, s.target_lang = src, tgt
        s.ocr_language = get_language(src).ocr
        save_settings()
        self._pipeline.set_languages(src, tgt)
        self._pipeline.reload_translator()
        self._update_pair_label()
        if self._tts_engine:
            self._tts_timer.stop()
            self._tts_engine.disable()
            self._tts_engine = None
            if self._btn_tts.isChecked():
                self._btn_tts.setChecked(False)
        self._sb.showMessage(t('Languages updated: {pair}', pair=self._lbl_pair.text()), 5000)

    def _on_ui_language_changed(self, _index):
        s = get_settings()
        s.ui_language = self._combo_ui_lang.currentData()
        save_settings()
        QMessageBox.information(self, __app_name__, t('The interface language will change after restarting the app.'))

    # ── Dubbing ───────────────────────────────────────────────────────────
    def _apply_tts_settings(self):
        tts = get_settings().tts
        tts.speed = self._cmb_tts_speed.currentData()
        tts.volume = self._sld_tts_volume.value()
        tts.gain = self._sld_tts_gain.value()
        tts.duck_enabled = self._chk_duck.isChecked()
        tts.duck_level = self._sld_duck.value()
        save_settings()
        if self._tts_engine:
            self._tts_engine.configure(tts.speed, tts.volume / 100.0, tts.gain / 100.0, duck_enabled=tts.duck_enabled, duck_level=tts.duck_level / 100.0)
        self._sb.showMessage(t('Dubbing settings saved.'), 3000)

    def _set_tts_checked(self, checked):
        self._btn_tts.blockSignals(True)
        self._btn_tts.setChecked(checked)
        self._btn_tts.blockSignals(False)

    def _on_tts_toggle(self, checked):
        """Toggle dubbing — the engine and voice model are prepared on first use."""
        if not checked:
            self._tts_timer.stop()
            if self._tts_engine:
                self._tts_engine.disable()
            self._sb.showMessage(t('Dubbing off.'), 3000)
            return
        from lingolay.tts import FastDubbingEngine, voice_for_target
        s = get_settings()
        voice = voice_for_target(s.target_lang)
        if not voice:
            self._set_tts_checked(False)
            QMessageBox.information(self, __app_name__, t('No dubbing voice is available for {lang} yet.', lang=get_language(s.target_lang).name))
            return
        tts = s.tts
        if self._tts_engine is None or self._tts_engine.voice_key != voice:
            self._tts_engine = FastDubbingEngine(speed=tts.speed, voice_key=voice, volume=tts.volume / 100.0, gain=tts.gain / 100.0,
                                                 duck_enabled=tts.duck_enabled, duck_level=tts.duck_level / 100.0)
        if self._tts_engine.voice_missing:
            from lingolay.models.manifest import get_model
            size = get_model(voice).approx_size_mb
            reply = QMessageBox.question(self, t('Download voice'), t('Dubbing needs the voice model “{voice}” (~{size} MB). Download it now?', voice=voice, size=size))
            if reply != QMessageBox.StandardButton.Yes:
                self._set_tts_checked(False)
                return
            from lingolay.ui.model_download_dialog import ModelDownloadDialog
            dlg = ModelDownloadDialog([voice], parent=self, title=t('Download voice'))
            dlg.exec()
            if not dlg.succeeded:
                self._set_tts_checked(False)
                return
        if not self._tts_engine.is_ready:
            self._set_tts_checked(False)
            self._sb.showMessage(t('Dubbing could not start: {error}', error=self._tts_engine.init_error), 8000)
            return
        self._tts_engine.enable()
        self._tts_timer.start()
        self._sb.showMessage(t('Dubbing on — translations will be read aloud.'), 4000)

    def _poll_tts_playback(self):
        if self._tts_engine:
            self._tts_engine.poll_playback()

    # ── Appearance ──────────────────────────────────────────────────────────
    def _make_color_btn(self, hex_color):
        btn = QPushButton()
        btn.setFixedSize(34, 28)
        self._update_color_btn(btn, hex_color)
        return btn

    def _update_color_btn(self, btn, hex_color):
        btn.setProperty('hex_color', hex_color)
        btn.setStyleSheet(f"""QPushButton {{ background: {hex_color}; border: 2px solid {BORDER2}; border-radius: 6px; padding: 0; }}
            QPushButton:hover {{ border-color: {ACCENT}; }}""")

    def _pick_into(self, btn, title):
        color = QColorDialog.getColor(QColor(btn.property('hex_color')), self, title)
        if color.isValid():
            self._update_color_btn(btn, color.name())

    def _on_backdrop_toggle(self, checked):
        """Background on → color/opacity options; off → outline options."""
        self._row_bg_color.setVisible(checked)
        self._row_outline.setVisible(not checked)

    def _on_font_size_slide(self, value):
        """Live preview: apply the font size to the overlay while the slider moves."""
        get_settings().overlay.font_size = value
        self._overlay.update_appearance()

    def _apply_overlay_style(self):
        ov = get_settings().overlay
        ov.backdrop = self._chk_backdrop.isChecked()
        ov.backdrop_color = self._btn_bg_color.property('hex_color')
        ov.backdrop_alpha = self._spin_bg_alpha.value()
        ov.text_color = self._btn_txt_color.property('hex_color')
        ov.outline_color = self._btn_ol_color.property('hex_color')
        ov.outline_width = self._spin_ol_width.value()
        ov.font_size = self._sld_font_size.value()
        ov.font_family = self._cmb_font_family.currentFont().family()
        ov.max_width_pct = self._sld_max_width.value() / 100.0
        save_settings()
        self._overlay.set_click_through(self._chk_click_through.isChecked())
        self._overlay.update_appearance()
        if not self._overlay._current_text:
            self._overlay.set_translation(t('Lingolay — overlay preview'))
        self._sb.showMessage(t('Overlay style updated.'), 3000)

    # ── Shortcuts ───────────────────────────────────────────────────────
    def _edit_hotkey(self, action):
        settings = get_settings()
        current = settings.hotkeys.get(action, '')
        desc = t(ACTION_LABELS.get(action, action))
        self._hotkeys.stop()
        dlg = HotkeyEditDialog(desc, current, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.get_key():
            new_key = dlg.get_key()
            conflict = next((a for a, k in settings.hotkeys.items() if a != action and k == new_key), None)
            if conflict:
                QMessageBox.warning(self, t('Conflict'), t('<b>{key}</b> is already used for <i>{action}</i>. Choose a different combination.',
                                                          key=new_key, action=t(ACTION_LABELS.get(conflict, conflict))))
            else:
                settings.hotkeys[action] = new_key
                save_settings(settings)
                self._hotkey_badges[action].setText(new_key)
                self._sb.showMessage(t('Shortcut updated: {action} → {key}', action=desc, key=new_key), 3000)
        self._hotkeys.reload(settings.hotkeys)

    # ── Engine / models ─────────────────────────────────────────────────
    def _on_engine_changed(self, index):
        is_deepl = self._combo_engine.itemData(index) == 'deepl'
        self._nllb_controls.setVisible(not is_deepl)
        self._deepl_controls.setVisible(is_deepl)
        if not is_deepl:
            self._refresh_model_rows()

    def _download_specific_model(self, model_id):
        from lingolay.ui.model_download_dialog import ModelDownloadDialog
        dlg = ModelDownloadDialog([model_id], parent=self)
        dlg.exec()
        self._refresh_model_rows()
        if not dlg.succeeded:
            return
        s = get_settings()
        idx = self._combo_engine.findData(s.translation_engine)
        if idx >= 0:
            self._combo_engine.blockSignals(True)
            self._combo_engine.setCurrentIndex(idx)
            self._combo_engine.blockSignals(False)
            self._on_engine_changed(idx)
        self._edit_model_path.setText(s.nllb_model_dir)
        self._sb.showMessage(t('Model downloaded — loading...'))
        self._pipeline.reload_translator()

    def _save_settings(self):
        s = get_settings()
        old = (s.translation_engine, s.nllb_model_dir, s.use_gpu, s.deepl_api_key, s.deepl_plan)
        engine = self._combo_engine.currentData()
        s.use_gpu = self._chk_gpu.isChecked()
        s.stability_count = self._spin_stab.value()
        s.deepl_api_key = self._edit_deepl_key.text().strip()
        s.deepl_plan = self._combo_deepl_plan.currentData()
        self._pipeline.update_stability(s.stability_count)

        if engine == 'deepl' and not s.deepl_api_key:
            QMessageBox.warning(self, t('DeepL API key required'), t('Enter a DeepL API key to use the DeepL engine.\n\n'
                                                                     'You can create a free account at deepl.com/pro-api (500,000 characters/month).'))
            return
        if engine in ('nllb_fast', 'nllb_quality'):
            from lingolay.models.manager import get_model_manager
            model_id = 'quality' if engine == 'nllb_quality' else 'fast'
            mgr = get_model_manager()
            manual = self._edit_model_path.text().strip()
            if mgr.is_installed(model_id):
                path = str(mgr.get_model_path(model_id))
                if manual and (Path(manual) / 'model.bin').exists() and manual != s.nllb_model_dir:
                    path = manual
                s.nllb_model_dir = path
                self._edit_model_path.setText(path)
            elif manual and (Path(manual) / 'model.bin').exists():
                s.nllb_model_dir = manual
            else:
                pretty = t('Quality (1.3B)') if model_id == 'quality' else t('Fast (600M)')
                reply = QMessageBox.question(self, t('Model not installed'), t('The “{model}” model is not downloaded yet.\n\nDownload it now?', model=pretty))
                if reply == QMessageBox.StandardButton.Yes:
                    save_settings()
                    self._download_specific_model(model_id)
                return
        s.translation_engine = engine
        save_settings()
        if (s.translation_engine, s.nllb_model_dir, s.use_gpu, s.deepl_api_key, s.deepl_plan) != old:
            self._sb.showMessage(t('Reloading translation engine...'))
            self._pipeline.reload_translator()
        else:
            self._sb.showMessage(t('Settings saved.'), 3000)

    def _browse_model(self):
        path = QFileDialog.getExistingDirectory(self, t('Choose NLLB model folder'), self._edit_model_path.text() or str(Path.home()))
        if path:
            self._edit_model_path.setText(path)

    # ── Pipeline control ────────────────────────────────────────────────────
    def _toggle_start_stop(self):
        if self._pipeline.status.is_running:
            self._stop_pipeline()
        else:
            self._start_pipeline()

    def _toggle_window(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def _start_region_selection(self):
        if self._pipeline.status.is_running:
            self._stop_pipeline()
        self._region_selector.start_selection()

    def _describe_region(self, x, y, w, h, monitor, dpi=None):
        text = t('{w} × {h} px   at ({x}, {y})   screen {monitor}', w=w, h=h, x=x, y=y, monitor=monitor)
        if dpi:
            text += f'   DPI ×{dpi:.1f}'
        self._lbl_region.setText(text)
        self._lbl_region.setStyleSheet(f'color: {GREEN}; font-size: 12px; font-weight: 700; font-family: {MONO};')

    def _on_region_selected(self, x, y, w, h, monitor, dpi):
        self._pipeline.set_region(x, y, w, h, monitor, dpi)
        self._describe_region(x, y, w, h, monitor, dpi)
        self._update_save_prof_btn()
        if self._pipeline.status.translator_ready or self._btn_preview.isChecked():
            self._btn_start.setEnabled(True)
        self._sb.showMessage(t('Region selected: {w}×{h} px', w=w, h=h), 4000)

    def _start_pipeline(self):
        self._pipeline.start()
        if self._pipeline.status.is_running:
            self._btn_start.setEnabled(False)
            self._btn_stop.setEnabled(True)
            self._btn_sel_reg.setEnabled(False)
            self._status_dot.set_state('running')
            self._set_sidebar_status('running', t('Running'))
            self._sb.showMessage(t('Running...  ·  Ctrl+Alt+S to stop'))

    def _stop_pipeline(self):
        self._pipeline.stop()
        self._btn_start.setEnabled(self._pipeline.status.region_set)
        self._btn_stop.setEnabled(False)
        self._btn_sel_reg.setEnabled(True)
        self._overlay.set_translation('—')
        self._status_dot.set_state('idle')
        self._set_sidebar_status('idle', t('Stopped'))
        self._sb.showMessage(t('Stopped  ·  Ctrl+Alt+S to start'))

    def _enter_game_mode(self):
        """Start with the game preset, hide this window and make the game borderless."""
        if not self._pipeline.status.region_set:
            self._sb.showMessage(t('Select a region first!'), 4000)
            return
        from lingolay.preprocessing.filters import ImagePreprocessor
        settings = get_settings()
        settings.preprocessing = ImagePreprocessor.game_subtitle_preset()
        save_settings(settings)
        self._pipeline.update_preprocessing(settings.preprocessing)
        if not self._pipeline.status.is_running:
            self._start_pipeline()
        self.hide()
        if sys.platform == 'win32':
            QTimer.singleShot(600, self._do_force_borderless)

    def _do_force_borderless(self):
        from lingolay.winutils.force_borderless import force_borderless_foreground
        ok, msg, state = force_borderless_foreground()
        if ok:
            self._borderless_state = state
            logger.info('[GameMode] %s', msg)
        else:
            logger.warning('[GameMode] Force borderless failed: %s', msg)

    def _toggle_preview(self, checked):
        self._pipeline.set_preview_mode(checked)
        self._overlay.set_preview_mode(checked)
        border_col = ACCENT if checked else BORDER2
        self._lbl_ocr.setStyleSheet(f'color: {TEXT2}; font-size: 11px; padding: 4px 8px 4px 12px; border-left: 2px solid {border_col};')
        if checked and self._pipeline.status.region_set:
            self._btn_start.setEnabled(not self._pipeline.status.is_running)

    # ── Pipeline signals ──────────────────────────────────────────────
    def _on_translation(self, text):
        self._overlay.set_translation(text)
        if self._tts_engine and self._tts_engine.is_enabled:
            self._tts_engine.speak(text)

    def _on_translation_error(self, msg):
        first_line = (msg or t('Unknown error')).split('\n')[0][:200]
        self._sb.showMessage(t('Translation error: {error}', error=first_line), 6000)

    def _on_ocr_text(self, text):
        short = text[:140] + ('...' if len(text) > 140 else '')
        self._lbl_ocr.setText(short)
        if self._btn_preview.isChecked():
            self._overlay.set_translation(text)

    def _on_status_update(self, s):
        self._c_fps.set_value(f'{s.fps:.0f}')
        self._c_ocr.set_value(str(s.ocr_latency_ms))
        self._c_tr.set_value(str(s.translate_latency_ms))
        self._c_cache.set_value(f'{s.cache_hit_rate * 100:.0f}%')
        if s.is_running and not s.preview_mode:
            short = s.current_ocr_text[:140] + ('...' if len(s.current_ocr_text) > 140 else '')
            self._lbl_ocr.setText(short.replace('\n', ' '))

    def _on_tr_loading(self):
        self._status_dot.set_state('loading')
        self._lbl_tr.setText(t('Loading model...'))
        self._lbl_tr.setStyleSheet(f'color: {ACCENT}; font-weight: 700; font-size: 13px;')
        self._set_sidebar_status('loading', t('Loading'))

    def _on_tr_ready(self):
        self._status_dot.set_state('idle')
        s = self._pipeline.status
        self._lbl_tr.setText(t('Ready  ·  {device}', device=s.device_name))
        self._lbl_tr.setStyleSheet(f'color: {GREEN}; font-weight: 700; font-size: 13px;')
        self._set_sidebar_status('idle', t('Ready · {device}', device=s.device_name))
        if s.region_set:
            self._btn_start.setEnabled(True)
            self._sb.showMessage(t('Model ready — press Start'))
        else:
            self._sb.showMessage(t('Model ready — first click “Select region”'))

    def _on_tr_failed(self, err):
        self._status_dot.set_state('error')
        self._lbl_tr.setText(t('Could not load: {error}', error=err))
        self._lbl_tr.setStyleSheet(f'color: {RED}; font-weight: 700; font-size: 13px;')
        self._set_sidebar_status('error', t('Model not loaded'))
        self._sb.showMessage(t('Model could not be loaded. You can still use OCR preview mode.'))

    def _set_sidebar_status(self, state, text):
        self._sidebar_dot.set_state(state)
        color = {'idle': GREEN, 'loading': ACCENT, 'running': GREEN, 'error': RED}.get(state, TEXT2)
        self._sidebar_status.setText(text)
        self._sidebar_status.setStyleSheet(f'color: {color}; font-size: 11px; font-weight: 600; background: transparent; border: none;')

    def _open_diagnostic_dialog(self):
        from lingolay.ui.diagnostic_dialog import DiagnosticDialog
        DiagnosticDialog(self).exec()

    # ── Profiles ────────────────────────────────────────────────────────
    def _update_save_prof_btn(self):
        """Save is enabled only when a region is set AND a name is entered."""
        self._btn_save_prof.setEnabled(self._pipeline.status.region_set and bool(self._edit_prof_name.text().strip()))

    def _refresh_profiles(self):
        self._combo_prof.blockSignals(True)
        self._combo_prof.clear()
        profiles = Profile.list_profiles()
        if profiles:
            self._combo_prof.addItem(t('-- Choose a profile --'))
            for p in profiles:
                self._combo_prof.addItem(p.name)
        else:
            self._combo_prof.addItem(t('-- No saved profiles --'))
        self._combo_prof.blockSignals(False)
        self._btn_del_prof.setEnabled(False)

    def _load_profile(self, index):
        if index <= 0:
            self._btn_del_prof.setEnabled(False)
            return
        name = self._combo_prof.currentText()
        profile = Profile.load(name)
        if not profile:
            return
        self._current_profile = profile
        x, y, w, h = profile.region
        self._pipeline.set_region(x, y, w, h, profile.monitor_index, profile.dpi_scale)
        self._describe_region(x, y, w, h, profile.monitor_index)
        self._update_save_prof_btn()
        self._btn_del_prof.setEnabled(True)
        if self._pipeline.status.translator_ready:
            self._btn_start.setEnabled(True)
        self._sb.showMessage(t('Profile loaded: {name}', name=name), 3000)

    def _save_profile(self):
        name = self._edit_prof_name.text().strip()
        region = self._pipeline.current_region
        if not name or not region:
            return
        p = Profile(name=name, region=region, monitor_index=self._pipeline.current_monitor_index, dpi_scale=self._pipeline.current_dpi_scale)
        p.save()
        self._current_profile = p
        self._edit_prof_name.clear()
        self._refresh_profiles()
        idx = self._combo_prof.findText(name)
        if idx >= 0:
            self._combo_prof.blockSignals(True)
            self._combo_prof.setCurrentIndex(idx)
            self._combo_prof.blockSignals(False)
            self._btn_del_prof.setEnabled(True)
        self._sb.showMessage(t('Profile saved: {name}', name=name), 3000)

    def _delete_profile(self):
        name = self._combo_prof.currentText()
        if not name or self._combo_prof.currentIndex() <= 0:
            return
        reply = QMessageBox.question(self, t('Delete profile'), t("Delete the profile '{name}'?", name=name))
        if reply != QMessageBox.StandardButton.Yes:
            return
        Profile.delete(name)
        if self._current_profile and self._current_profile.name == name:
            self._current_profile = None
        self._refresh_profiles()
        self._sb.showMessage(t('Profile deleted: {name}', name=name), 3000)

    # ── Load settings into the UI ───────────────────────────────────────────
    def _load_settings_to_ui(self):
        s = get_settings()
        for combo, code in ((self._combo_src, s.source_lang), (self._combo_tgt, s.target_lang)):
            idx = combo.findData(code)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        self._update_pair_label()
        idx = self._combo_engine.findData(s.translation_engine)
        if idx >= 0:
            self._combo_engine.setCurrentIndex(idx)
        self._on_engine_changed(self._combo_engine.currentIndex())
        self._edit_model_path.setText(str(s.get_nllb_model_path()))
        self._chk_gpu.setChecked(s.use_gpu)
        self._edit_deepl_key.setText(s.deepl_api_key)
        idx_plan = self._combo_deepl_plan.findData(s.deepl_plan)
        if idx_plan >= 0:
            self._combo_deepl_plan.setCurrentIndex(idx_plan)
        self._spin_stab.setValue(s.stability_count)
        ov = s.overlay
        self._chk_backdrop.setChecked(ov.backdrop)
        self._spin_bg_alpha.setValue(ov.backdrop_alpha)
        self._spin_ol_width.setValue(ov.outline_width)
        self._update_color_btn(self._btn_bg_color, ov.backdrop_color)
        self._update_color_btn(self._btn_txt_color, ov.text_color)
        self._update_color_btn(self._btn_ol_color, ov.outline_color)
        self._sld_font_size.blockSignals(True)
        self._sld_font_size.setValue(ov.font_size)
        self._sld_font_size.blockSignals(False)
        self._lbl_font_size_val.setText(f'{ov.font_size} px')
        self._cmb_font_family.setCurrentFont(QFont(ov.font_family))
        self._sld_max_width.setValue(int(ov.max_width_pct * 100))
        self._on_backdrop_toggle(ov.backdrop)

    # ── Window events ─────────────────────────────────────────────────
    def showEvent(self, event):
        """
        Show the overlay only AFTER the main window is visible — otherwise the TOPMOST
        overlay can appear alone in front of everything.
        """
        super().showEvent(event)
        if not self._overlay_shown_once:
            self._overlay_shown_once = True
            QTimer.singleShot(100, self._overlay.show)

    def closeEvent(self, event):
        self._tts_timer.stop()
        if self._tts_engine:
            self._tts_engine.disable()
        self._hotkeys.stop()
        self._pipeline.shutdown()
        if self._borderless_state is not None:
            from lingolay.winutils.force_borderless import restore_window
            restore_window(self._borderless_state)
        self._overlay.close()
        self._region_selector.close()
        event.accept()
        app = QApplication.instance()
        if app:
            app.quit()
