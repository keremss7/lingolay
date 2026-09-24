import ctypes
import math
import sys

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QTextDocument
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QLabel, QVBoxLayout, QWidget

from lingolay.core.config import get_settings
from lingolay.i18n import t

_HWND_TOPMOST = -1
_GWL_EXSTYLE = -20
_WS_EX_TOPMOST = 0x00000008
_WS_EX_NOACTIVATE = 0x08000000
_WS_EX_TRANSPARENT = 0x00000020
_WS_EX_LAYERED = 0x00080000
_SWP_NOMOVE = 0x0002
_SWP_NOSIZE = 0x0001
_SWP_NOACTIVATE = 0x0010
_SWP_FLAGS = _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOACTIVATE


def _w32_apply(hwnd, click_through):
    """
    Apply the TOPMOST + NOACTIVATE extended styles via Win32.

    Qt's own setWindowFlags sometimes resets these, so we re-apply them.
    Thanks to NOACTIVATE the overlay never becomes the foreground window,
    so clicking into the game does not push the overlay behind it.
    """
    if sys.platform != 'win32':
        return
    user32 = ctypes.windll.user32
    ex = user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
    ex |= _WS_EX_TOPMOST | _WS_EX_NOACTIVATE | _WS_EX_LAYERED
    if click_through:
        ex |= _WS_EX_TRANSPARENT
    else:
        ex &= ~_WS_EX_TRANSPARENT
    user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, ex)
    user32.SetWindowPos(hwnd, _HWND_TOPMOST, 0, 0, 0, 0, _SWP_FLAGS)


class OutlineLabel(QLabel):
    """Label that draws outlined text when the background box is disabled."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fill_color = QColor('#ffffff')
        self._outline_color = QColor('#000000')
        self._outline_width = 3
        self._use_outline = False
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)

    def configure(self, use_outline, fill, outline, outline_w):
        self._use_outline = use_outline
        self._fill_color = QColor(fill)
        self._outline_color = QColor(outline)
        self._outline_width = max(1, outline_w)
        self.update()

    def paintEvent(self, event):
        if not self._use_outline or not self.text():
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        font = self.font()
        fm = QFontMetrics(font)
        max_w = self.width() - 56
        lines = self._wrap(self.text(), fm, max_w)
        line_h = fm.height() + 3
        total_h = line_h * len(lines)
        y = (self.height() - total_h) // 2 + fm.ascent()
        pen = QPen(self._outline_color, self._outline_width * 2)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        for line in lines:
            x = (self.width() - fm.horizontalAdvance(line)) // 2
            path = QPainterPath()
            path.addText(x, y, font, line)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self._fill_color))
            painter.drawPath(path)
            y += line_h

    @staticmethod
    def _wrap(text, fm, max_w):
        """Word-based line wrapping."""
        lines = []
        cur = ''
        for w in text.split():
            test = (cur + ' ' + w).strip()
            if cur and fm.horizontalAdvance(test) > max_w:
                lines.append(cur)
                cur = w
            else:
                cur = test
        if cur:
            lines.append(cur)
        return lines or [text]


class OverlayWindow(QWidget):
    """Always-on-top, non-activating, draggable translation window."""
    position_changed = Signal(int, int)

    FONT_SCALE_MEDIUM = 90
    FONT_SCALE_SMALL = 160
    FONT_SCALE_TINY = 240
    _LABEL_PAD_H = 28
    _LABEL_PAD_V = 14

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_text = ''
        self._drag_position = QPoint()
        self._is_dragging = False
        self._base_font_size = 18
        self._setup_window()
        self._setup_ui()
        self._apply_style()
        self._restore_or_snap_position()
        self._topmost_timer = QTimer(self)
        self._topmost_timer.timeout.connect(self._enforce_win32)
        self._topmost_timer.start(400)

    def _setup_window(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMinimumWidth(120)
        self.setMinimumHeight(24)

    def showEvent(self, event):
        super().showEvent(event)
        self._enforce_win32()

    def _enforce_win32(self):
        """Re-apply the Win32 extended styles while visible."""
        if self.isVisible():
            _w32_apply(int(self.winId()), click_through=get_settings().overlay.click_through)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._container = QWidget()
        self._container.setObjectName('overlay_container')
        con_lay = QVBoxLayout(self._container)
        con_lay.setContentsMargins(0, 0, 0, 0)
        con_lay.setSpacing(0)
        self._container.setMinimumSize(1, 1)
        self._mode_label = QLabel()
        self._mode_label.setObjectName('mode_label')
        self._mode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mode_label.hide()
        con_lay.addWidget(self._mode_label)
        self._text_label = OutlineLabel()
        self._text_label.setObjectName('text_label')
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_label.setWordWrap(True)
        self._text_label.setMinimumHeight(1)
        self._text_label.setText(t('Lingolay is ready...'))
        con_lay.addWidget(self._text_label)
        layout.addWidget(self._container)
        self._shadow = QGraphicsDropShadowEffect()
        self._shadow.setBlurRadius(22)
        self._shadow.setColor(QColor(0, 0, 0, 120))
        self._shadow.setOffset(0, 4)
        self._container.setGraphicsEffect(self._shadow)

    @staticmethod
    def _text_label_style(ov, font_size):
        return f"""
            #text_label {{
                color: {ov.text_color};
                font-family: "{ov.font_family}";
                font-size: {font_size}px;
                font-weight: bold;
                padding: 14px 28px;
                background: transparent;
            }}
        """

    def _apply_style(self):
        ov = get_settings().overlay
        self._base_font_size = ov.font_size
        self.setWindowOpacity(ov.opacity)
        self.setMaximumWidth(self._get_max_width())
        bg_hex = ov.backdrop_color.lstrip('#')
        bg_r = int(bg_hex[0:2], 16)
        bg_g = int(bg_hex[2:4], 16)
        bg_b = int(bg_hex[4:6], 16)
        bg_a = ov.backdrop_alpha if ov.backdrop else 0
        border = '2px solid rgba(255,255,255,0.12)' if ov.backdrop else 'none'
        self._container.setStyleSheet(f"""
            QWidget#overlay_container {{
                background: rgba({bg_r},{bg_g},{bg_b},{bg_a});
                border-radius: 12px;
                border: {border};
                padding: {ov.padding}px;
            }}
        """)
        self._text_label.setStyleSheet(self._text_label_style(ov, ov.font_size))
        self._text_label.setFont(QFont(ov.font_family, ov.font_size, QFont.Weight.Bold))
        self._text_label.configure(use_outline=not ov.backdrop, fill=ov.text_color, outline=ov.outline_color, outline_w=ov.outline_width)
        self._mode_label.setStyleSheet(f"""
            #mode_label {{
                color: #ffd700;
                font-family: "{ov.font_family}";
                font-size: {max(12, ov.font_size - 4)}px;
                font-weight: bold;
                padding: 5px 10px;
                background: rgba(255,215,0,0.15);
                border-radius: 6px;
            }}
        """)
        self._shadow.setBlurRadius(22 if ov.backdrop else 0)
        if self.isVisible():
            _w32_apply(int(self.winId()), click_through=ov.click_through)

    def _get_screen_geometry(self):
        screen = self.screen() if self.isVisible() else None
        if not screen:
            screen = QApplication.primaryScreen()
        return screen.availableGeometry() if screen else None

    def _get_max_width(self):
        geo = self._get_screen_geometry()
        if geo:
            return int(geo.width() * get_settings().overlay.max_width_pct)
        return 1200

    def _get_scaled_font_size(self, text_len):
        base = self._base_font_size
        if text_len >= self.FONT_SCALE_TINY:
            return max(12, base - 6)
        if text_len >= self.FONT_SCALE_SMALL:
            return max(13, base - 4)
        if text_len >= self.FONT_SCALE_MEDIUM:
            return max(14, base - 2)
        return base

    def set_click_through(self, enabled):
        """
        Click-through at the Win32 level — avoids setWindowFlags, so the native
        window is not recreated and NOACTIVATE is not reset.
        """
        get_settings().overlay.click_through = enabled
        if sys.platform == 'win32':
            _w32_apply(int(self.winId()), click_through=enabled)
        else:
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, enabled)
            if self.isVisible():
                self.show()

    def set_preview_mode(self, enabled):
        if enabled:
            self._mode_label.setText(t('🔍 OCR preview'))
            self._mode_label.show()
        else:
            self._mode_label.hide()

    def set_translation(self, text):
        """Anti-flicker: only update when the text actually changes."""
        if text == self._current_text:
            return
        self._current_text = text
        self._render_current()

    def _render_current(self):
        """
        Redraw the current text with the current style settings and resize the
        window to fit. Called both on new text and on style changes (font size
        etc.), so the user does not have to wait for a new subtitle.
        """
        text = self._current_text
        scaled = self._get_scaled_font_size(len(text))
        ov = get_settings().overlay
        self._text_label.setFont(QFont(ov.font_family, scaled, QFont.Weight.Bold))
        self._text_label.setStyleSheet(self._text_label_style(ov, scaled))
        self._text_label.setText(text)
        self._smart_resize()

    def set_error(self, message):
        msg = f'⚠️ {message}'
        if self._current_text != msg:
            self._current_text = msg
            self._text_label.setText(msg)
            self._smart_resize()

    def clear(self):
        self.set_translation('')

    def _smart_resize(self):
        geo = self._get_screen_geometry()
        if not geo:
            return
        pad = get_settings().overlay.padding
        max_w = self._get_max_width()
        chrome_w = (pad + self._LABEL_PAD_H) * 2
        chrome_h = (pad + self._LABEL_PAD_V) * 2
        avail_text_w = max(50, max_w - chrome_w)
        doc = QTextDocument()
        doc.setDefaultFont(self._text_label.font())
        doc.setPlainText(self._text_label.text())
        doc.setTextWidth(avail_text_w)
        text_w = min(math.ceil(doc.idealWidth()), avail_text_w)
        doc.setTextWidth(text_w)
        text_h = math.ceil(doc.size().height())
        mode_h = 0
        if self._mode_label.isVisible():
            mdoc = QTextDocument()
            mdoc.setDefaultFont(self._mode_label.font())
            mdoc.setPlainText(self._mode_label.text())
            mdoc.setTextWidth(max_w - 40)
            mode_h = int(mdoc.size().height()) + 20
        final_w = min(max(text_w + chrome_w, 200), max_w)
        final_h = text_h + chrome_h + mode_h
        # Keep the bottom-center anchored while resizing
        old = self.geometry()
        old_bottom = old.y() + old.height()
        old_cx = old.x() + old.width() // 2
        # QWidget ignores stylesheet padding, so apply it as layout margins instead
        self._container.layout().setContentsMargins(pad, pad, pad, pad)
        self._text_label.setFixedWidth(final_w - pad * 2)
        self._container.setFixedSize(final_w, final_h)
        self.setFixedSize(final_w, final_h)
        self.move(old_cx - final_w // 2, old_bottom - final_h)
        self._clamp_to_screen()

    def _restore_or_snap_position(self):
        ov = get_settings().overlay
        if ov.pos_x is not None and ov.pos_y is not None:
            self.move(ov.pos_x, ov.pos_y)
            self._clamp_to_screen()
        else:
            self._snap_to_bottom_center()

    def _snap_to_bottom_center(self):
        geo = self._get_screen_geometry()
        if not geo:
            return
        self.move(geo.center().x() - self.width() // 2, geo.bottom() - self.height() - 60)

    def _clamp_to_screen(self):
        geo = self._get_screen_geometry()
        if not geo:
            return
        pos = self.pos()
        size = self.size()
        nx, ny = pos.x(), pos.y()
        if nx + size.width() > geo.x() + geo.width():
            nx = geo.x() + geo.width() - size.width()
        if ny + size.height() > geo.y() + geo.height():
            ny = geo.y() + geo.height() - size.height()
        nx = max(geo.x(), nx)
        ny = max(geo.y(), ny)
        if nx != pos.x() or ny != pos.y():
            self.move(nx, ny)

    def save_position(self):
        pos = self.pos()
        ov = get_settings().overlay
        ov.pos_x = pos.x()
        ov.pos_y = pos.y()

    def update_appearance(self):
        """Style settings changed — re-apply the style and re-layout the current text."""
        self._apply_style()
        self._render_current()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            self.save_position()
            pos = self.pos()
            self.position_changed.emit(pos.x(), pos.y())
            self._enforce_win32()
            event.accept()
