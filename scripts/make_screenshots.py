"""Render the README images from the real app (headless).

Requires an installed Fast model (lingolay --download fast). Usage:
    QT_QPA_PLATFORM=offscreen python scripts/make_screenshots.py [--lang en|tr]

Writes docs/images/main-window.png, translation-settings.png and demo.png.
The demo image uses the real overlay widget and a real NLLB translation.
"""
import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
OUT = ROOT / 'docs' / 'images'

DEMO_SOURCE = "Stay close to me. The bridge won't hold much longer!"


def wait_until(app, cond, timeout=60.0):
    end = time.time() + timeout
    while time.time() < end and not cond():
        app.processEvents()
        time.sleep(0.02)
    return cond()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lang', default='en')
    ap.add_argument('--target', default='tr')
    ap.add_argument('--out', default=str(OUT))
    args = ap.parse_args()

    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    from lingolay.core.config import get_settings
    from lingolay.i18n import set_language
    s = get_settings()
    s.ui_language = args.lang
    s.source_lang, s.target_lang = 'en', args.target
    s.overlay.font_size = 28
    set_language(args.lang)

    from lingolay.ui.main_window import MainWindow
    win = MainWindow()
    win.resize(1000, 900)
    win.show()
    ok = wait_until(app, lambda: win._pipeline.status.translator_ready, 90)
    print('translator ready:', ok, win._pipeline.status.device_name)

    # Real translation through the loaded engine
    translator = win._pipeline._translation_worker.translator
    result = translator.translate(DEMO_SOURCE)
    from lingolay.text.turkish_postprocess import post_process_turkish
    translated = post_process_turkish(result.text) if args.target == 'tr' else result.text
    print('translation:', translated, result.latency_ms, 'ms')

    win._on_region_selected(0, 930, 1920, 150, 0, 1.0)
    st = win._pipeline.status
    st.translate_latency_ms = result.latency_ms
    win._on_status_update(st)
    win._lbl_ocr.setText(DEMO_SOURCE)
    for _ in range(20):
        app.processEvents()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    win._switch_page(0)
    app.processEvents()
    win.grab().save(str(out / 'main-window.png'))
    win._switch_page(1)
    app.processEvents()
    win.grab().save(str(out / 'translation-settings.png'))

    # ── Demo composite: a stylised scene + the real overlay widget ─────────────
    ov = win._overlay
    ov.set_translation(translated)
    for _ in range(10):
        app.processEvents()
    ov_pix = ov.grab()

    W, H = 1600, 900
    canvas = QPixmap(W, H)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    sky = QLinearGradient(0, 0, 0, H)
    sky.setColorAt(0, QColor('#1b2440'))
    sky.setColorAt(0.55, QColor('#3a2a4a'))
    sky.setColorAt(1, QColor('#120d14'))
    p.fillRect(0, 0, W, H, sky)
    glow = QRadialGradient(QPointF(W * 0.72, H * 0.32), 260)
    glow.setColorAt(0, QColor(255, 150, 80, 170))
    glow.setColorAt(1, QColor(255, 150, 80, 0))
    p.fillRect(0, 0, W, H, glow)
    # mountains
    for color, pts in (
        ('#241a2e', [(0, 560), (220, 380), (420, 520), (640, 330), (900, 540), (1150, 360), (1400, 500), (1600, 400), (1600, 900), (0, 900)]),
        ('#150f1b', [(0, 680), (300, 520), (560, 650), (820, 500), (1100, 660), (1350, 540), (1600, 640), (1600, 900), (0, 900)]),
    ):
        path = QPainterPath()
        path.moveTo(*pts[0])
        for pt in pts[1:]:
            path.lineTo(*pt)
        p.fillPath(path, QColor(color))
    # bridge
    p.setPen(QPen(QColor('#0b0810'), 10))
    p.drawLine(260, 640, 1340, 640)
    p.setPen(QPen(QColor('#0b0810'), 4))
    for x in range(300, 1340, 80):
        p.drawLine(x, 640, x + 40, 560)
        p.drawLine(x + 40, 560, x + 80, 640)

    # "game" subtitle (what the game shows)
    font = QFont('Helvetica Neue', 30, QFont.Weight.DemiBold)
    p.setFont(font)
    fm = p.fontMetrics()
    tw = fm.horizontalAdvance(DEMO_SOURCE)
    sub_y = 690
    path = QPainterPath()
    path.addText((W - tw) / 2, sub_y, font, DEMO_SOURCE)
    p.setPen(QPen(QColor('#000000'), 6))
    p.drawPath(path)
    p.fillPath(path, QColor('#ffffff'))

    # dashed capture region
    region = QRectF((W - tw) / 2 - 30, sub_y - fm.ascent() - 22, tw + 60, fm.height() + 40)
    pen = QPen(QColor('#ff6929'), 3, Qt.PenStyle.DashLine)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(region, 8, 8)

    # real overlay widget
    ox = int((W - ov_pix.width()) / 2)
    oy = int(region.bottom() + 36)
    p.drawPixmap(ox, oy, ov_pix)

    # caption badges
    def badge(x, y, text, bg, fg='#ffffff'):
        f = QFont('Helvetica Neue', 15, QFont.Weight.Bold)
        p.setFont(f)
        w = p.fontMetrics().horizontalAdvance(text) + 28
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(bg))
        p.drawRoundedRect(QRectF(x, y, w, 34), 17, 17)
        p.setPen(QColor(fg))
        p.drawText(QRectF(x, y, w, 34), Qt.AlignmentFlag.AlignCenter, text)
        return w

    x = 40
    x += badge(x, 36, 'Lingolay', '#ff6929') + 12
    x += badge(x, 36, f'EN → {args.target.upper()}', 'rgba(0,0,0,150)') + 12
    x += badge(x, 36, f'NLLB-200 · offline · {result.latency_ms} ms', 'rgba(0,0,0,150)') + 12
    p.setFont(QFont('Helvetica Neue', 13))
    p.setPen(QColor(255, 255, 255, 150))
    p.drawText(QRectF(0, H - 40, W - 30, 30), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
               'Illustrative scene · overlay and translation rendered by Lingolay')
    p.end()
    canvas.save(str(out / 'demo.png'))
    print('written to', out)

    win._hotkeys.stop()
    win._pipeline.shutdown()
    ov.close()
    os._exit(0)


if __name__ == '__main__':
    main()
