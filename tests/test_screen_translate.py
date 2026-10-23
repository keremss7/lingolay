"""Translate screen: layout, style and rendering on a synthetic game screen drawn with Qt."""
import sys

import numpy as np
import pytest

from lingolay.ocr.base import OcrLine
from lingolay.screen_translate.layout import font_size_of, group_blocks
from lingolay.screen_translate.style import analyze

MENU = ['Inventory', 'Quest Log', 'Settings', 'Save Game', 'Exit to Main Menu']
EXPECTED = MENU + ['Continue', 'An ancient sword forged by the elves.', 'Objective: Find the lost village']


def _scene(qapp):
    """1600x900 game screen: textured world, dark menu panel, orange button, parchment note, HUD text."""
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
    rng = np.random.default_rng(0)
    W, H = 1600, 900
    noise = rng.normal(0, 14, (H // 8 + 1, W // 8 + 1, 1)).repeat(8, 0).repeat(8, 1)[:H, :W]
    world = np.clip(np.linspace(170, 90, H)[:, None, None] + noise * np.ones(3), 0, 255).astype(np.uint8)
    world = np.ascontiguousarray(world * np.array([0.7, 0.9, 1.1]).clip(0, 1.5)).clip(0, 255).astype(np.uint8)
    img = QImage(world.data, W, H, W * 3, QImage.Format.Format_RGB888).copy()
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont('Arial')
    font.setPixelSize(30)
    p.setFont(font)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(10, 12, 20, 210))
    p.drawRoundedRect(60, 160, 380, 400, 16, 16)
    p.setPen(QColor(235, 235, 240))
    for i, item in enumerate(MENU):
        p.drawText(100, 220 + i * 72, item)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(240, 130, 40))
    p.drawRoundedRect(1300, 780, 250, 70, 12, 12)
    bold = QFont(font)
    bold.setBold(True)
    p.setFont(bold)
    p.setPen(QColor(25, 20, 15))
    p.drawText(QRect(1300, 780, 250, 70), Qt.AlignmentFlag.AlignCenter, 'Continue')
    p.setFont(font)
    p.fillRect(540, 220, 680, 220, QColor(222, 200, 160))
    p.setPen(QColor(70, 40, 20))
    p.drawText(580, 280, 'An ancient sword forged by the elves.')
    p.drawText(580, 320, 'It glows blue when enemies are near.')
    path = QPainterPath()
    path.addText(980, 80, font, 'Objective: Find the lost village')
    p.strokePath(path, QPen(QColor(0, 0, 0), 4))
    p.fillPath(path, QColor(255, 255, 255))
    p.end()
    img = img.convertToFormat(QImage.Format.Format_RGB888)
    arr = np.frombuffer(img.constBits(), np.uint8).reshape(H, img.bytesPerLine())[:, :W * 3].reshape(H, W, 3)
    return np.ascontiguousarray(arr[:, :, ::-1])  # BGR like a screen capture


def test_lines_are_grouped_into_labels_and_paragraphs():
    lines = [OcrLine('Inventory', 100, 200, 140, 30), OcrLine('Quest Log', 100, 272, 150, 30),
             OcrLine('An ancient sword forged by the elves.', 580, 260, 520, 30),
             OcrLine('It glows blue when enemies are near.', 580, 300, 500, 30),
             OcrLine('42', 900, 600, 30, 30), OcrLine('x', 10, 10, 9, 12)]
    texts = [b.text for b in group_blocks(lines)]
    assert texts == ['Inventory', 'An ancient sword forged by the elves. It glows blue when enemies are near.', 'Quest Log']


def test_font_size_does_not_depend_on_descenders():
    # OCR boxes are shorter without g/y/p; both lines are the same 34 px font
    assert font_size_of(OcrLine('Save Game', 0, 0, 100, 25)) == pytest.approx(font_size_of(OcrLine('Quest Log', 0, 0, 100, 32)), rel=0.05)


def _bright_box(frame, x0, y0, x1, y1, threshold=200):
    """Bounding box of the bright (text) pixels in a region: font metrics differ between platforms."""
    ys, xs = np.nonzero(frame[y0:y1, x0:x1].mean(axis=2) > threshold)
    return int(x0 + xs.min()), int(y0 + ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)


def _dark_box(frame, x0, y0, x1, y1, threshold=80):
    ys, xs = np.nonzero(frame[y0:y1, x0:x1].mean(axis=2) < threshold)
    return int(x0 + xs.min()), int(y0 + ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)


def test_plain_panel_is_covered_with_its_own_color(qapp):
    frame = _scene(qapp)
    box = _bright_box(frame, 70, 185, 430, 240)  # "Inventory" on the dark menu panel
    style = analyze(frame, box, box[3], font_size_of(OcrLine('Inventory', *box)))
    assert style.flat
    assert style.patch.reshape(-1, 3).std(axis=0).max() < 2  # the text is gone, only the panel color remains
    assert style.outline is None
    assert not style.bold
    box = _dark_box(frame, 1310, 790, 1540, 840)  # bold "Continue" on the orange button
    button = analyze(frame, box, box[3], font_size_of(OcrLine('Continue', *box)))
    assert button.bold and button.flat and button.free_left <= 1305 and button.free_right >= 1545
    assert max(style.text) > 200 and max(style.background) < 60  # light text on a dark panel


def test_textured_background_is_inpainted_not_painted_over(qapp):
    frame = _scene(qapp)
    x, y, w, h = 975, 52, 470, 38  # outlined HUD text over the textured world
    style = analyze(frame, (x, y, w, h), h)
    assert not style.flat
    assert min(style.text) > 200 and max(style.outline) < 60  # white text with a black outline
    before = frame[style.y:style.y + style.h, style.x:style.x + style.w].astype(float)
    assert style.patch.astype(float).std() < before.std() * 0.6  # the text strokes were removed


def test_rendering_draws_the_translation_over_the_original(qapp):
    from lingolay.screen_translate.controller import build_items
    from lingolay.screen_translate.render import render_onto
    frame = _scene(qapp)
    lines = [OcrLine('Settings', 100, 340, 120, 32)]
    items = build_items(frame, lines, lambda s: 'Ayarlar')
    out = render_onto(frame, items)
    region = (slice(330, 380), slice(90, 260))
    assert not np.array_equal(out[region], frame[region])
    assert build_items(frame, lines, lambda s: s) == []  # untranslated text is left alone


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows OCR')
def test_windows_ocr_finds_the_game_texts(qapp):
    from lingolay.ocr.windows_ocr import WindowsOCR
    ocr = WindowsOCR('en-US')
    if not ocr.is_available():
        pytest.skip('Windows OCR unavailable')
    frame = _scene(qapp)
    import warnings

    from lingolay.ocr.windows_ocr import _run_async_in_loop
    try:
        raw = _run_async_in_loop(ocr._recognize_raw(frame))
        diag = f'raw lines={len(raw.lines)}'
        if raw.lines:
            w = raw.lines[0].words[0]
            diag += f' first word={w.text!r} rect attrs={[a for a in dir(w.bounding_rect) if not a.startswith("_")]}'
    except Exception as e:  # diagnostics for CI
        diag = f'raw error {type(e).__name__}: {e}'
    warnings.warn(f'plain text: {ocr.recognize(frame)[:120]!r}; {diag}', stacklevel=1)
    blocks = group_blocks(ocr.recognize_layout(frame))
    texts = [b.text.lower() for b in blocks]
    found = [e for e in EXPECTED if any(e.lower()[:12] in t for t in texts)]
    import warnings
    warnings.warn(f'Windows OCR found {len(found)}/{len(EXPECTED)}; missing {sorted(set(EXPECTED) - set(found))}; '
                  f'blocks {[b.text for b in blocks]}', stacklevel=1)  # shown in the CI log even when passing
    assert len(found) >= 6
