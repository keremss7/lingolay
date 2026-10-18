"""Home-page tile for "match the speaker's voice": a toggle switch, a NEW badge and a live status chip."""
from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton, QFrame, QHBoxLayout, QLabel, QVBoxLayout

from lingolay.i18n import t

VIOLET = '#a78bfa'
VIOLET_BG = 'rgba(167,139,250,0.10)'
VIOLET_BORDER = 'rgba(167,139,250,0.45)'
FEMALE = '#f472b6'
MALE = '#60a5fa'
# chip fills: the accent at low opacity
FILL = {FEMALE: (244, 114, 182, 38), MALE: (96, 165, 250, 38), '#8a8a92': (138, 138, 146, 30)}
TEXT = '#ececef'
TEXT2 = '#8a8a92'
TRACK_OFF = '#3a3a42'


class ToggleSwitch(QAbstractButton):
    """An on/off switch with a sliding knob."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._offset = 0.0
        self._anim = QPropertyAnimation(self, b'offset', self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def sizeHint(self):
        return QSize(46, 26)

    def _animate(self, checked):
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def set_checked_silently(self, checked):
        self.blockSignals(True)
        self.setChecked(checked)
        self.blockSignals(False)
        self._offset = 1.0 if checked else 0.0
        self.update()

    def get_offset(self):
        return self._offset

    def set_offset(self, value):
        self._offset = value
        self.update()

    offset = Property(float, get_offset, set_offset)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        on, off = QColor(VIOLET), QColor(TRACK_OFF)
        track = QColor(
            int(off.red() + (on.red() - off.red()) * self._offset),
            int(off.green() + (on.green() - off.green()) * self._offset),
            int(off.blue() + (on.blue() - off.blue()) * self._offset),
        )
        if not self.isEnabled():
            track.setAlpha(90)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.left() + 3 + (r.width() - d - 6) * self._offset
        p.setBrush(QColor('#ffffff' if self.isEnabled() else '#9a9aa2'))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))


class Pill(QLabel):
    """A label drawn as a rounded pill (Qt stylesheets don't round QLabel corners reliably)."""

    def __init__(self, text='', parent=None):
        super().__init__(text, parent)
        self._fill, self._border = QColor(0, 0, 0, 0), QColor(0, 0, 0, 0)
        self.setContentsMargins(9, 2, 9, 2)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_colors(self, text, fill, border=None):
        """fill/border: '#rrggbb' or an (r, g, b, alpha) tuple."""
        to_color = lambda c: QColor(*c) if isinstance(c, tuple) else QColor(c)  # noqa: E731
        self._fill, self._border = to_color(fill), to_color(border or fill)
        self.setStyleSheet(f'color: {text}; background: transparent; border: none;')
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(self._border)
        p.setBrush(self._fill)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.end()
        super().paintEvent(event)


class SpeakerVoiceTile(QFrame):
    """Shows the feature on the home page; emits toggled(bool) when the user flips the switch."""

    toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('speaker_tile')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f'QFrame#speaker_tile {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {VIOLET_BG}, stop:1 transparent);'
            f' border: 1px solid {VIOLET_BORDER}; border-radius: 12px; }}'
            'QLabel#tile_text { background: transparent; border: none; }')
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(12)

        icon = QLabel('🎭')
        icon.setFixedSize(40, 40)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(f'QLabel {{ background: {VIOLET_BG}; border: 1px solid {VIOLET_BORDER}; border-radius: 10px; font-size: 20px; }}')
        lay.addWidget(icon, alignment=Qt.AlignmentFlag.AlignVCenter)

        text = QVBoxLayout()
        text.setSpacing(3)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        self._title = QLabel(t('Speaker-aware voice'))
        self._title.setObjectName('tile_text')
        self._title.setStyleSheet(f'color: {TEXT}; font-size: 14px; font-weight: 700;')
        title_row.addWidget(self._title)
        self._badge = Pill(t('NEW'))
        self._badge.setContentsMargins(7, 1, 7, 1)
        font = self._badge.font()
        font.setPixelSize(9)
        font.setBold(True)
        font.setLetterSpacing(font.SpacingType.AbsoluteSpacing, 0.6)
        self._badge.setFont(font)
        self._badge.set_colors('#0d0d0f', VIOLET)
        title_row.addWidget(self._badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        title_row.addStretch()
        text.addLayout(title_row)
        self._subtitle = QLabel(t("A woman's line in a female voice, a man's in a male voice — automatically."))
        self._subtitle.setWordWrap(True)
        self._subtitle.setObjectName('tile_text')
        self._subtitle.setStyleSheet(f'color: {TEXT2}; font-size: 12px;')
        text.addWidget(self._subtitle)
        lay.addLayout(text, 1)

        self._chip = Pill()
        font = self._chip.font()
        font.setPixelSize(11)
        font.setWeight(font.Weight.DemiBold)
        self._chip.setFont(font)
        self._chip.setContentsMargins(10, 3, 10, 3)
        self._chip.setVisible(False)
        lay.addWidget(self._chip, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.switch = ToggleSwitch()
        self.switch.setToolTip(t('Listens to the game or video (nothing is recorded), detects whether a man or a woman is speaking '
                                 'and uses a matching voice. Downloads a ~60 MB model and the extra voices on first use.'))
        self.switch.toggled.connect(self.toggled)
        lay.addWidget(self.switch, alignment=Qt.AlignmentFlag.AlignVCenter)

    def set_checked(self, checked):
        self.switch.set_checked_silently(checked)

    def set_supported(self, supported):
        self.switch.setEnabled(supported)
        if not supported:
            self._subtitle.setText(t('Requires Windows 10 version 2004 or later.'))

    def set_new(self, is_new):
        self._badge.setVisible(is_new)

    def set_status(self, state):
        """state: None (hidden) | 'listening' | 'female' | 'male' | 'default'."""
        if state is None:
            self._chip.setVisible(False)
            return
        text, color = {
            'listening': (t('Listening…'), TEXT2),
            'female': ('♀  ' + t('Female voice'), FEMALE),
            'male': ('♂  ' + t('Male voice'), MALE),
            'default': (t('Default voice'), TEXT2),
        }[state]
        self._chip.setText(text)
        self._chip.set_colors(color, FILL[color], color)
        self._chip.setVisible(True)
