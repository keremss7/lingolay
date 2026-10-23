"""Group OCR lines into text blocks (paragraphs, labels, buttons) that are translated as one unit."""
import re
from dataclasses import dataclass, field

MIN_LETTERS = 2           # "OK" is worth translating, "x" or "12" is not
MIN_LINE_HEIGHT = 9       # px; smaller text is usually unreadable noise to OCR
_LETTER = re.compile(r'[^\W\d_]', re.UNICODE)
# An OCR box spans from the top of the capitals to the bottom of the descenders (g, y, p...).
# Relative to the font size that is about 0.72 without descenders and 0.94 with them.
CAP_HEIGHT, DESCENDER = 0.72, 0.22
_DESCENDERS = set('gjpqyçşğ,;()[]{}|')


def font_size_of(line):
    """Estimated font size (px) of an OCR line, independent of which letters it contains."""
    has_descender = any(c in _DESCENDERS for c in line.text)
    return line.h / (CAP_HEIGHT + (DESCENDER if has_descender else 0.0))


@dataclass
class TextBlock:
    lines: list = field(default_factory=list)   # OcrLine, top to bottom

    @property
    def text(self):
        return ' '.join(line.text.strip() for line in self.lines)

    @property
    def rect(self):
        x0 = min(line.x for line in self.lines)
        y0 = min(line.y for line in self.lines)
        x1 = max(line.x + line.w for line in self.lines)
        y1 = max(line.y + line.h for line in self.lines)
        return x0, y0, x1 - x0, y1 - y0

    @property
    def line_height(self):
        return sorted(line.h for line in self.lines)[len(self.lines) // 2]

    @property
    def font_size(self):
        sizes = sorted(font_size_of(line) for line in self.lines)
        return sizes[len(sizes) // 2]


def is_translatable(text):
    return len(_LETTER.findall(text)) >= MIN_LETTERS


def _continues(block, line):
    """Does `line` continue `block` as the next line of the same paragraph?"""
    last = block.lines[-1]
    h = block.line_height
    if not (0.7 <= line.h / h <= 1.4):
        return False                                   # different font size: a different element
    gap = line.y - (last.y + last.h)
    if gap < -0.3 * h or gap > 0.8 * h:
        return False                                   # too far below (or overlapping)
    bx0, _, bw, _ = block.rect
    left_aligned = abs(line.x - bx0) <= 1.5 * h
    overlap = min(bx0 + bw, line.x + line.w) - max(bx0, line.x)
    centered = abs((line.x + line.w / 2) - (bx0 + bw / 2)) <= 1.5 * h
    return overlap > 0 and (left_aligned or centered)


def group_blocks(lines):
    """OcrLine list → TextBlock list in reading order; drops noise and tiny or letterless lines."""
    kept = [ln for ln in lines if ln.h >= MIN_LINE_HEIGHT and ln.text.strip()]
    kept.sort(key=lambda ln: (ln.y, ln.x))
    blocks = []
    for line in kept:
        for block in blocks:
            if _continues(block, line):
                block.lines.append(line)
                break
        else:
            blocks.append(TextBlock([line]))
    return [b for b in blocks if is_translatable(b.text)]
