"""
Translate screen, instant mode: on a hotkey, capture the monitor under the mouse, find every piece
of text, translate it and show it in place; press again to hide. Heavy work runs off the UI thread.
"""
import logging
import threading
import time

from PySide6.QtCore import QObject, QRect, Signal

from .layout import group_blocks
from .render import LensItem, LensOverlay
from .style import analyze

logger = logging.getLogger(__name__)


def _overlaps(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    return ix * iy > 0.3 * min(aw * ah, bw * bh)


def find_lines(ocr, frame):
    """
    OCR lines with boxes. A second pass reads only the white pixels (as black on white): outlined
    white HUD text over a busy scene is often missed on the full image but is clean in that view.
    """
    import cv2
    import numpy as np
    lines = list(ocr.recognize_layout(frame))
    white = cv2.inRange(frame, (200, 200, 200), (255, 255, 255))
    if cv2.countNonZero(white):
        isolated = cv2.cvtColor(255 - white, cv2.COLOR_GRAY2BGR)
        for line in ocr.recognize_layout(np.ascontiguousarray(isolated)):
            box = (line.x, line.y, line.w, line.h)
            if not any(_overlaps(box, (o.x, o.y, o.w, o.h)) for o in lines):
                lines.append(line)
    return lines


def build_items(frame, lines, translate, skip_rects=()):
    """OCR lines → LensItems for the blocks worth showing. `translate(text) -> str`."""
    items = []
    blocks = group_blocks(lines)
    for block in blocks:
        rect = block.rect
        if any(QRect(*r).intersects(QRect(*rect)) for r in skip_rects):
            continue  # Lingolay's own windows
        translation = (translate(block.text) or '').strip()
        if not translation or translation.casefold() == block.text.casefold():
            continue  # untranslated or already in the target language: leave the original alone
        items.append(LensItem(analyze(frame, rect, block.line_height, block.font_size), rect, block.line_height, translation,
                              font_size=block.font_size, line_count=len(block.lines), align=_alignment(block, blocks)))
    return items


def _alignment(block, blocks):
    """Paragraphs and list items (left edge shared with a nearby block) stay left; lone labels center."""
    if len(block.lines) > 1:
        return 'left'
    x, y, _, _ = block.rect
    lh = block.line_height
    for other in blocks:
        if other is block:
            continue
        ox, oy, _, _ = other.rect
        if abs(ox - x) <= 0.5 * lh and abs(oy - y) <= 6 * lh:
            return 'left'
    return 'center'


class ScreenTranslator(QObject):
    """toggle() shows or hides the in-place translation of the screen under the mouse."""

    finished = Signal(object, object, float, str)   # items, QScreen, device pixel ratio, summary
    failed = Signal(str)

    def __init__(self, get_translator, get_ocr_language, get_skip_rects, parent=None):
        super().__init__(parent)
        self._get_translator = get_translator
        self._get_ocr_language = get_ocr_language
        self._get_skip_rects = get_skip_rects
        self._overlay = LensOverlay()
        self._ocr, self._ocr_lang = None, None
        self._busy = False
        self.finished.connect(self._show)

    @property
    def active(self):
        return self._overlay.active

    def toggle(self):
        if self._overlay.active:
            self._overlay.clear()
            return
        if self._busy:
            return
        translator = self._get_translator()
        if translator is None or not getattr(translator, 'is_ready', False):
            self.failed.emit('translator')
            return
        from PySide6.QtGui import QCursor, QGuiApplication
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        self._busy = True
        threading.Thread(target=self._work, args=(translator, screen, self._get_skip_rects()),
                         daemon=True, name='ScreenTranslate').start()

    def _work(self, translator, screen, skip_rects):
        try:
            t0 = time.perf_counter()
            frame, scale = self._capture(screen)
            t1 = time.perf_counter()
            lines = find_lines(self._ocr_engine(), frame)
            t2 = time.perf_counter()
            g = screen.geometry()  # skip rects are global logical coordinates; frames start at the monitor
            skip = [(int((x - g.x()) * scale), int((y - g.y()) * scale), int(w * scale), int(h * scale))
                    for x, y, w, h in skip_rects]
            items = build_items(frame, lines, lambda s: translator.translate(s).text, skip)
            t3 = time.perf_counter()
            summary = (f'{len(items)} blocks · capture {1000 * (t1 - t0):.0f} ms · OCR {1000 * (t2 - t1):.0f} ms'
                       f' · translate+style {1000 * (t3 - t2):.0f} ms')
            logger.info('[ScreenTranslate] %s', summary)
            self.finished.emit(items, screen, scale, summary)
        except Exception as e:
            logger.exception('[ScreenTranslate] failed')
            self.failed.emit(str(e))
        finally:
            self._busy = False

    def _ocr_engine(self):
        lang = self._get_ocr_language()
        if self._ocr is None or self._ocr_lang != lang:
            from lingolay.ocr import create_ocr_engine
            self._ocr, self._ocr_lang = create_ocr_engine(lang), lang
        return self._ocr

    @staticmethod
    def _capture(screen):
        """Physical-pixel BGR frame of `screen` and its device pixel ratio."""
        import mss
        import numpy as np
        scale = screen.devicePixelRatio()
        g = screen.geometry()
        want_w, want_h = round(g.width() * scale), round(g.height() * scale)
        with mss.mss() as sct:
            # Qt's logical coordinates don't map 1:1 to pixels on mixed-DPI setups; match the
            # physical monitor by size, then by position
            candidates = sct.monitors[1:] or sct.monitors
            monitor = min(candidates, key=lambda m: (abs(m['width'] - want_w) + abs(m['height'] - want_h),
                                                     abs(m['left'] - g.x() * scale) + abs(m['top'] - g.y() * scale)))
            shot = sct.grab(monitor)
        return np.ascontiguousarray(np.asarray(shot)[:, :, :3]), scale

    def _show(self, items, screen, scale, _summary):
        if items:
            self._overlay.show_items(screen, items, scale)

    def hide(self):
        self._overlay.clear()
