import cv2
import numpy as np

from lingolay.preprocessing.filters import ImagePreprocessor

W, H, TEXT = 900, 90, 'Where were you when the city fell?'


def _text(img, color, outline=False):
    if outline:
        cv2.putText(img, TEXT, (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.25, (0, 0, 0), 6, cv2.LINE_AA)
    cv2.putText(img, TEXT, (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.25, color, 2, cv2.LINE_AA)
    return img


def _scene(seed, high=200):
    rng = np.random.default_rng(seed)
    return cv2.GaussianBlur(rng.integers(60, high, (H, W, 3)).astype(np.uint8), (31, 31), 0)


def _ink(img):
    """Share of dark (text) pixels in the black-on-white OCR input."""
    return float(np.mean(img < 128))


def test_game_mode_reads_light_text_inside_a_black_box():
    # Issue: subtitles in a black box are often grey or tinted, not pure white, and vanished
    pre = ImagePreprocessor(ImagePreprocessor.game_subtitle_preset())
    grey_in_box = _text(np.zeros((H, W, 3), np.uint8), (175, 175, 175))
    yellow_in_box = _text((_scene(1) * 0.25).astype(np.uint8), (60, 215, 235))
    for img in (grey_in_box, yellow_in_box):
        assert _ink(pre.process(img)) > 0.02


def test_game_mode_keeps_white_text_and_ignores_dark_scenes():
    pre = ImagePreprocessor(ImagePreprocessor.game_subtitle_preset())
    assert _ink(pre.process(_text(_scene(2), (255, 255, 255), outline=True))) > 0.02
    assert _ink(pre.process(_scene(3, high=70))) < 0.002  # night scene without subtitles stays blank


def test_game_mode_reads_tinted_text_on_a_letterbox_bar_below_the_picture():
    # The region shows part of the game picture (bright pixels) above a black bar with grey text,
    # so the white mask is not empty and a whole-region check never looked at the bar.
    pre = ImagePreprocessor(ImagePreprocessor.game_subtitle_preset())
    img = cv2.GaussianBlur(np.random.default_rng(5).integers(60, 220, (140, W, 3)).astype(np.uint8), (31, 31), 0)
    img[56:] = 0
    cv2.putText(img, TEXT, (30, 115), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (180, 180, 180), 2, cv2.LINE_AA)
    out = pre.process(img)
    bar = out[50 + 2 * 60: 50 + 2 * 140]  # the bar's rows in the 2x upscaled, padded output
    assert _ink(bar) > 0.02
