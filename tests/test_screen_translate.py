"""Translate screen: layout, style and rendering on a synthetic game screen drawn with Qt."""
import sys

import numpy as np
import pytest

from lingolay.ocr.base import OcrLine
from lingolay.screen_translate.layout import font_size_of, group_blocks
from lingolay.screen_translate.style import analyze

MENU = ['Inventory', 'Quest Log', 'Settings', 'Save Game', 'Exit to Main Menu']
EXPECTED = MENU + ['Continue', 'An ancient sword forged by the elves.', 'Objective: Find the lost village']


def _scene(qapp=None):
    """
    1600x900 game screen: textured world, dark see-through menu, orange button, parchment note and
    outlined HUD text. Drawn with OpenCV's built-in fonts so it is identical on every platform.
    """
    import cv2
    rng = np.random.default_rng(0)
    W, H = 1600, 900
    noise = rng.normal(0, 14, (H // 8 + 1, W // 8 + 1, 1)).repeat(8, 0).repeat(8, 1)[:H, :W]
    gradient = np.linspace(170, 90, H)[:, None, None] * np.array([1.1, 0.9, 0.7])  # BGR: bluish sky
    img = np.clip(gradient + noise, 0, 255).astype(np.uint8)
    font, scale = cv2.FONT_HERSHEY_DUPLEX, 1.0

    def text(t, org, color, thickness=1):
        cv2.putText(img, t, org, font, scale, color, thickness, cv2.LINE_AA)

    panel = img[160:560, 60:440].astype(float)
    img[160:560, 60:440] = (panel * 0.18 + np.array([20, 12, 10]) * 0.82).astype(np.uint8)  # see-through dark menu
    for i, item in enumerate(MENU):
        text(item, (100, 220 + i * 72), (240, 235, 235))
    cv2.rectangle(img, (1300, 780), (1550, 850), (40, 130, 240), -1)  # orange button, bold label
    text('Continue', (1350, 828), (15, 20, 25), thickness=4)
    img[220:440, 540:1220] = (160, 200, 222)  # parchment
    text('An ancient sword forged by the elves.', (580, 280), (20, 40, 70))
    text('It glows blue when enemies are near.', (580, 320), (20, 40, 70))
    cv2.putText(img, 'Objective: Find the lost village', (980, 80), font, scale, (0, 0, 0), 7, cv2.LINE_AA)
    text('Objective: Find the lost village', (980, 80), (255, 255, 255))
    return img


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
    box = _dark_box(frame, 1310, 790, 1540, 840)  # bold "Continue" on the orange button
    button = analyze(frame, box, box[3], font_size_of(OcrLine('Continue', *box)))
    assert button.flat and button.free_left <= 1305 and button.free_right >= 1545
    # the absolute bold threshold is calibrated on real fonts; OpenCV's test font is thicker overall
    assert button.stroke > 1.3 * style.stroke
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
    import time

    from lingolay.screen_translate.controller import find_lines
    start = time.perf_counter()
    blocks = group_blocks(find_lines(ocr, frame))
    elapsed = (time.perf_counter() - start) * 1000
    texts = [b.text.lower() for b in blocks]
    found = [e for e in EXPECTED if any(e.lower()[:12] in t for t in texts)]
    import warnings
    warnings.warn(f'Windows OCR found {len(found)}/{len(EXPECTED)} in {elapsed:.0f} ms; missing {sorted(set(EXPECTED) - set(found))}; '
                  f'blocks {[b.text for b in blocks]}', stacklevel=1)  # shown in the CI log even when passing
    assert len(found) >= 6


def test_hotkey_flow_shows_and_hides_the_translation(qapp, qtbot, monkeypatch):
    from PySide6.QtGui import QGuiApplication

    from lingolay.screen_translate.controller import ScreenTranslator
    frame = _scene()

    class FakeOCR:
        def recognize_layout(self, image):
            return [OcrLine('Settings', 100, 340, 120, 30)] if image.shape == frame.shape and image.std() > 20 else []

    class FakeTranslator:
        is_ready = True

        def translate_many(self, texts):
            return ['Ayarlar' for _ in texts]

    st = ScreenTranslator(lambda: FakeTranslator(), lambda: 'en-US', lambda: [])
    monkeypatch.setattr(ScreenTranslator, '_capture', staticmethod(lambda screen: (frame, 1.0)))
    monkeypatch.setattr(st, '_ocr_engine', lambda: FakeOCR())
    with qtbot.waitSignal(st.finished, timeout=10000) as blocker:
        st.toggle()
    items = blocker.args[0]
    assert [i.translation for i in items] == ['Ayarlar']
    assert st.active and blocker.args[1] in QGuiApplication.screens()
    st.toggle()  # second press hides it
    assert not st.active

    st_not_ready = ScreenTranslator(lambda: None, lambda: 'en-US', lambda: [])
    with qtbot.waitSignal(st_not_ready.failed, timeout=2000) as failed:
        st_not_ready.toggle()
    assert failed.args == ['translator']

    black = np.zeros_like(frame)
    st_black = ScreenTranslator(lambda: FakeTranslator(), lambda: 'en-US', lambda: [])
    monkeypatch.setattr(ScreenTranslator, '_capture', staticmethod(lambda screen: (black, 1.0)))
    with qtbot.waitSignal(st_black.failed, timeout=5000) as failed:
        st_black.toggle()
    assert failed.args == ['black']  # exclusive fullscreen: a hint instead of an empty overlay
    qtbot.waitUntil(lambda: st_black.active, timeout=2000)
    st_black.hide()
