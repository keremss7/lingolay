"""Draw translated blocks over the original text, and the click-through overlay window that shows them."""
import sys
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .style import BlockStyle

MIN_SCALE = 0.55          # shrink a translation to at most this share of the original size before giving up
FONT_FAMILY = 'Segoe UI' if sys.platform == 'win32' else 'Helvetica Neue'


@dataclass
class LensItem:
    style: BlockStyle
    text_rect: tuple          # original OCR box (x, y, w, h) in frame pixels
    line_height: int          # median OCR line height in frame pixels
    translation: str
    font_size: float = 0.0    # estimated original font size in frame pixels (0: from line height)
    line_count: int = 1       # lines in the original block
    align: str = 'left'       # 'left' for lists and paragraphs, 'center' for lone labels and buttons


def _wrap(text, metrics, max_w):
    lines, current = [], ''
    for word in text.split():
        trial = f'{current} {word}'.strip()
        if current and metrics.horizontalAdvance(trial) > max_w:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def fit_text(text, max_w, max_h, base_px, single_line=False, bold=False):
    """
    (font, lines) for the largest size from base_px down to MIN_SCALE that fits the box.
    single_line: labels and buttons are never wrapped, only shrunk (the caller may allow extra width).
    """
    font = QFont(FONT_FAMILY)
    font.setWeight(QFont.Weight.Bold if bold else QFont.Weight.Medium)
    size = base_px
    while True:
        font.setPixelSize(max(6, int(round(size))))
        metrics = QFontMetricsF(font)
        if single_line:
            if metrics.horizontalAdvance(text) <= max_w or size <= base_px * MIN_SCALE:
                return font, [text]
        else:
            lines = _wrap(text, metrics, max_w)
            if len(lines) * metrics.lineSpacing() <= max_h * 1.08 or size <= base_px * MIN_SCALE:
                return font, lines
        size *= 0.92


def _contrast(a, b):
    lum = lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]  # noqa: E731
    hi, lo = max(lum(a), lum(b)), min(lum(a), lum(b))
    return (hi + 12) / (lo + 12)


def draw_items(painter, items, scale=1.0):
    """Paint the cover patches and translations. Frame pixels are divided by `scale` (device pixel ratio)."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    for item in items:
        st = item.style
        patch = np.ascontiguousarray(st.patch[:, :, ::-1])  # BGR → RGB
        image = QImage(patch.data, patch.shape[1], patch.shape[0], patch.strides[0], QImage.Format.Format_RGB888)
        painter.drawImage(QRectF(st.x / scale, st.y / scale, st.w / scale, st.h / scale), image)

        tx, ty, tw, th = (v / scale for v in item.text_rect)
        avail_w = max(tw, st.w / scale - 2 * (tx - st.x / scale))
        base_px = (item.font_size or item.line_height / 0.85) / scale
        single = item.line_count == 1
        centered = single and item.align == 'center'
        margin = base_px * 0.3
        free_l, free_r = st.free_left / scale + margin, st.free_right / scale - margin
        cx = tx + tw / 2
        if single:
            # a label stays on one line: shrink first; on a plain background it may grow, but never
            # past its button or panel
            grow = tw * (1.5 if st.flat else 1.15)
            space = 2 * min(cx - free_l, free_r - cx) if centered else free_r - tx
            avail_w = max(tw, min(grow, space))
        # On a plain background a longer paragraph may take one extra line below the original
        room = th + (base_px * 1.2 if st.flat else 0)
        font, lines = fit_text(item.translation, avail_w, max(room, item.line_height / scale), base_px, single, st.bold)
        painter.setFont(font)
        metrics = QFontMetricsF(font)
        block_h = len(lines) * metrics.lineSpacing()
        text_w = max(metrics.horizontalAdvance(line) for line in lines)
        if centered:
            tx = cx - text_w / 2
        if st.flat:  # extend the cover under text that runs past the original box
            pad_x = st.x / scale - (item.text_rect[0] / scale)
            left = min(st.x / scale, tx + pad_x)
            right = max(st.x / scale + st.w / scale, tx + text_w - pad_x)
            bottom = max(st.y / scale + st.h / scale, ty + block_h)
            painter.fillRect(QRectF(left, st.y / scale, right - left, bottom - st.y / scale), QColor(*st.background))
        # single lines sit centered on the original line; paragraphs start where the original did
        top = ty + (th - block_h) / 2 if item.line_count == 1 else ty
        color = QColor(*st.text)
        if st.outline is not None:  # same look as the original: outlined glyphs
            pen = QPen(QColor(*st.outline), max(2.0, font.pixelSize() * 0.12))
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            for i, line in enumerate(lines):
                path = QPainterPath()
                path.addText(tx, top + i * metrics.lineSpacing() + metrics.ascent(), font, line)
                painter.strokePath(path, pen)
                painter.fillPath(path, color)
            continue
        shadow = None
        if _contrast(st.text, st.background) < 3.0:
            shadow = QColor(0, 0, 0, 200) if sum(st.text) > 382 else QColor(255, 255, 255, 200)
        for i, line in enumerate(lines):
            baseline = top + i * metrics.lineSpacing() + metrics.ascent()
            if shadow is not None:
                painter.setPen(shadow)
                painter.drawText(QRectF(tx + 1, baseline - metrics.ascent() + 1, avail_w + 4, metrics.height()),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, line)
            painter.setPen(color)
            painter.drawText(QRectF(tx, baseline - metrics.ascent(), avail_w + 4, metrics.height()),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, line)


def render_onto(frame, items):
    """The frame with the translations drawn on it (BGR in, BGR out); used by tests and previews."""
    rgb = np.ascontiguousarray(frame[:, :, ::-1])
    image = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format.Format_RGB888).copy()
    painter = QPainter(image)
    draw_items(painter, items)
    painter.end()
    image = image.convertToFormat(QImage.Format.Format_RGB888)
    out = np.frombuffer(image.constBits(), np.uint8).reshape(image.height(), image.bytesPerLine())
    return np.ascontiguousarray(out[:, :image.width() * 3].reshape(image.height(), image.width(), 3)[:, :, ::-1])


class LensOverlay(QWidget):
    """Full-screen, transparent, click-through window over one monitor; invisible to screen capture."""

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._items, self._scale = [], 1.0

    def show_items(self, screen, items, scale):
        self._items, self._scale = items, scale
        self.setGeometry(screen.geometry())
        self.show()
        self._apply_win32()
        self.update()

    def clear(self):
        self._items = []
        self.hide()

    @property
    def active(self):
        return self.isVisible()

    def _apply_win32(self):
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            GWL_EXSTYLE, WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_NOACTIVATE = -20, 0x80000, 0x20, 0x08000000
            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE)
            user32.SetWindowDisplayAffinity(hwnd, 0x11)  # WDA_EXCLUDEFROMCAPTURE: our own capture never sees it
        except Exception:
            pass

    def paintEvent(self, _event):
        painter = QPainter(self)
        draw_items(painter, self._items, self._scale)
        painter.end()
