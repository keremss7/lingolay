"""Generate the app icon (PNG + ICO) with Qt — no external design assets needed.

Usage: python scripts/make_icon.py
"""
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'src' / 'lingolay' / 'assets'


def render(size):
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 256.0
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0, QColor('#ff8a3d'))
    grad.setColorAt(1, QColor('#e8461a'))
    path = QPainterPath()
    path.addRoundedRect(QRectF(8 * s, 8 * s, 240 * s, 240 * s), 56 * s, 56 * s)
    p.fillPath(path, grad)
    # "L" letter
    f = QFont('Helvetica Neue', int(150 * s))
    f.setWeight(QFont.Weight.Black)
    p.setFont(f)
    p.setPen(QColor('#ffffff'))
    p.drawText(QRectF(0, -18 * s, 256 * s, 220 * s), Qt.AlignmentFlag.AlignCenter, 'L')
    # subtitle bars
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(13, 13, 15, 220))
    p.drawRoundedRect(QRectF(44 * s, 178 * s, 168 * s, 22 * s), 11 * s, 11 * s)
    p.setBrush(QColor(255, 255, 255, 235))
    p.drawRoundedRect(QRectF(62 * s, 185 * s, 84 * s, 8 * s), 4 * s, 4 * s)
    p.setBrush(QColor(255, 255, 255, 140))
    p.drawRoundedRect(QRectF(154 * s, 185 * s, 40 * s, 8 * s), 4 * s, 4 * s)
    p.end()
    return img


def main():
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)  # noqa: F841
    OUT.mkdir(parents=True, exist_ok=True)
    render(256).save(str(OUT / 'icon.png'))
    ok = render(256).save(str(OUT / 'icon.ico'), 'ICO')
    print('icon.png written; icon.ico', 'written' if ok else 'NOT supported by this Qt build')


if __name__ == '__main__':
    main()
