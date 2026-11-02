"""Çeviri yazısı konumu: yazı bitip yenisi gelince pencere alt-orta çapasında sabit kalmalı (kaymamalı)."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent

from lingolay.core.config import get_settings
from lingolay.overlay.window import OverlayWindow

UZUN = 'Bu biraz daha uzun bir çeviri cümlesi, iki satıra taşabilir mi bakalım.'
KISA = 'Kısa.'


def _capa(w):
    g = w.geometry()
    return (g.x() + g.width() // 2, g.y() + g.height())


def _pencere(qtbot, x=100, y=300):
    get_settings().overlay.pos_x = None
    get_settings().overlay.pos_y = None
    w = OverlayWindow()
    qtbot.addWidget(w)
    w.move(x, y)
    w.set_translation(KISA)
    return w


def test_clear_dongusu_alt_orta_sabit(qtbot):
    w = _pencere(qtbot)
    # ilk metin sonrası alt-orta çapası referanstır
    w.move(300, 350)
    ref = _capa(w)
    for i in range(20):
        w.clear()
        w.set_translation(KISA if i % 2 else UZUN)
        cx, bottom = _capa(w)
        # uzayıp kısalan metinde genişlik değişir ama alt kenar sabit kalmalı
        assert bottom == ref[1], (i, bottom, ref)
        assert abs(cx - ref[0]) <= 1, (i, cx, ref)


def test_uzayan_kisalan_metinde_alt_kenar_sabit(qtbot):
    w = _pencere(qtbot)
    w.move(300, 350)
    ref = _capa(w)
    for metin in (UZUN, KISA, UZUN, UZUN + ' ' + UZUN, KISA):
        w.set_translation(metin)
        assert _capa(w)[1] == ref[1]
        assert abs(_capa(w)[0] - ref[0]) <= 1


def test_surukle_clear_metin(qtbot):
    w = _pencere(qtbot)
    w.set_translation(UZUN)
    w.move(w.x() + 40, w.y() - 60)   # kullanıcı sürükledi
    ev = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(5, 5), QPointF(5, 5),
                     Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    w.mouseReleaseEvent(ev)
    ref = _capa(w)
    for _ in range(5):
        w.clear()
        w.set_translation(UZUN)
        assert _capa(w)[1] == ref[1]
        assert abs(_capa(w)[0] - ref[0]) <= 1


def test_kayitli_konumla_ilk_metin_kaymaz(qtbot):
    ov = get_settings().overlay
    ov.pos_x, ov.pos_y = 200, 250
    w = OverlayWindow()
    qtbot.addWidget(w)
    w._restore_or_snap_position()
    w.set_translation(KISA)
    ilk = (w.x(), w.y())
    for _ in range(10):
        w.clear()
        w.set_translation(KISA)
    assert (w.x(), w.y()) == ilk


def test_ekran_disina_tasmaz(qtbot):
    w = _pencere(qtbot, 5, 5)
    w.set_translation(UZUN)
    geo = w._get_screen_geometry()
    for _ in range(10):
        w.clear()
        w.set_translation(UZUN)
        assert w.x() >= geo.x() and w.y() >= geo.y()
        assert w.x() + w.width() <= geo.x() + geo.width()
        assert w.y() + w.height() <= geo.y() + geo.height()
