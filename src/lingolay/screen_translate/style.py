"""
Read a text block's look from the captured frame and build the patch that hides the original.

- background: median of a thin ring around the box
- text color: median of the pixels inside the box that differ most from the background
- cover: a flat fill when the background is plain (UI panels, buttons), otherwise the text pixels
  are removed with OpenCV inpainting so textures and gradients continue under the translation
"""
from dataclasses import dataclass

import cv2
import numpy as np

FLAT_MAX_STD = 8.0      # ring brightness spread below which the background counts as plain
TEXT_MIN_DIST = 40.0    # color distance from the background that counts as text
OUTLINE_MIN_DIFF = 110  # brightness gap between a glyph's edge and its inside that means an outline
BOLD_MIN_STROKE = 0.132  # stroke / font size above which text is bold (measured on 4 fonts: regular <=0.124, bold mostly >=0.137)
PAD_FACTOR = 0.18       # padding around the OCR box, relative to line height
PAD_X_FACTOR = 0.45     # more on the sides: OCR boxes often leave out trailing punctuation


@dataclass
class BlockStyle:
    x: int                     # patch position and size in frame pixels (box + padding)
    y: int
    w: int
    h: int
    background: tuple          # (r, g, b)
    text: tuple                # (r, g, b)
    flat: bool
    outline: tuple | None      # (r, g, b) of an outline around the glyphs, if the original has one
    patch: np.ndarray          # BGR image hiding the original text, shape (h, w, 3)
    bold: bool = False         # thick strokes relative to the text size
    stroke: float = 0.0        # stroke width / font size
    free_left: int = 0         # how far the plain background reaches left/right of the text (frame x),
    free_right: int = 0        # so a longer translation stays inside its button or panel


def _ring(frame, x0, y0, x1, y1, width):
    H, W = frame.shape[:2]
    ox0, oy0 = max(0, x0 - width), max(0, y0 - width)
    ox1, oy1 = min(W, x1 + width), min(H, y1 + width)
    outer = frame[oy0:oy1, ox0:ox1].reshape(-1, 3)
    mask = np.ones((oy1 - oy0, ox1 - ox0), bool)
    mask[y0 - oy0:y1 - oy0, x0 - ox0:x1 - ox0] = False
    return outer[mask.reshape(-1)]


def analyze(frame, rect, line_height, font_size=None):
    """BlockStyle for the block at rect=(x, y, w, h) in a BGR frame; font_size: estimated, in px."""
    H, W = frame.shape[:2]
    pad = max(2, int(round(line_height * PAD_FACTOR)))
    pad_x = max(pad, int(round(line_height * PAD_X_FACTOR)))
    x, y, w, h = rect
    x0, y0 = max(0, x - pad_x), max(0, y - pad)
    x1, y1 = min(W, x + w + pad_x), min(H, y + h + pad)
    ring = _ring(frame, x0, y0, x1, y1, max(3, pad))
    if not len(ring):
        ring = frame[y0:y1, x0:x1].reshape(-1, 3)
    bg = np.median(ring, axis=0)
    flat = float(np.std(ring.astype(np.float32).mean(axis=1))) < FLAT_MAX_STD

    patch = frame[y0:y1, x0:x1].copy()
    dist = np.linalg.norm(patch.astype(np.float32) - bg, axis=2)
    text_mask = dist > TEXT_MIN_DIST
    outline, bold, stroke_ratio = None, False, 0.0
    if text_mask.any():
        # The glyph's color is taken from the inside of its strokes; the edge differs when the
        # text has an outline (white text with a black border is common in game HUDs)
        lum = patch.astype(np.float32).mean(axis=2)
        depth = cv2.distanceTransform(text_mask.astype(np.uint8), cv2.DIST_L2, 3)
        inner = text_mask & (depth >= np.percentile(depth[text_mask], 70))
        # stroke width: along the centre lines of the glyphs, at half contrast (ignores anti-aliasing halos)
        core_mask = (dist > 0.5 * float(dist[text_mask].max())).astype(np.uint8)
        core_depth = cv2.distanceTransform(core_mask, cv2.DIST_L2, 3)
        ridge = (core_depth >= cv2.dilate(core_depth, np.ones((3, 3), np.uint8))) & (core_mask > 0)
        stroke = 2 * float(np.median(core_depth[ridge])) if ridge.any() else 0.0
        stroke_ratio = stroke / max(1.0, font_size or line_height / 0.85)
        bold = stroke_ratio > BOLD_MIN_STROKE
        middle = float(np.median(lum[inner]))
        # the purest part of the fill: inner pixels on the far side of their median (away from blending)
        core = inner & ((lum >= middle) if middle >= float(bg.mean()) else (lum <= middle))
        fg = np.median(patch[core if core.any() else inner], axis=0)
        gap = np.abs(lum - float(fg.mean()))
        border = text_mask & (gap > OUTLINE_MIN_DIFF)
        if border.sum() > 0.15 * text_mask.sum():
            # the outline's own color, not its anti-aliased blend with the background
            candidate = np.median(patch[border & (gap >= np.percentile(gap[border], 50))], axis=0)
            # Anti-aliased edges lie between the background and the fill; a real outline lies
            # beyond the background (e.g. black around white text on a blue sky)
            if abs(float(candidate.mean()) - float(fg.mean())) > abs(float(bg.mean()) - float(fg.mean())) + 25:
                outline = candidate
    else:  # low contrast: pick black or white, whichever reads better on the background
        fg = np.array([20, 20, 20] if bg.mean() > 128 else [235, 235, 235], float)

    if flat:
        patch[:] = bg.astype(np.uint8)
    else:
        mask = cv2.dilate(text_mask.astype(np.uint8) * 255, np.ones((3, 3), np.uint8), iterations=2)
        patch = cv2.inpaint(patch, mask, 3, cv2.INPAINT_TELEA)

    free_left, free_right = x0, x1
    if flat:
        row = frame[min(H - 1, y + h // 2)].astype(np.float32)
        same = np.linalg.norm(row - bg, axis=1) < 30
        while free_left > 0 and same[free_left - 1] and x0 - free_left < 3 * w:
            free_left -= 1
        while free_right < W and same[free_right] and free_right - x1 < 3 * w:
            free_right += 1

    to_rgb = lambda c: (int(c[2]), int(c[1]), int(c[0]))  # noqa: E731  (frames are BGR)
    return BlockStyle(x0, y0, x1 - x0, y1 - y0, to_rgb(bg), to_rgb(fg), flat,
                      to_rgb(outline) if outline is not None else None, patch, bold, stroke_ratio, free_left, free_right)
