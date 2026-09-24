from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QLabel, QWidget

from lingolay.i18n import t

_MIN_SIZE = 8
_ACCENT = '#ff6929'


class RegionSelector(QWidget):
    """Full-screen translucent layer that lets the user draw the subtitle region."""
    # x, y, w, h (logical pixels relative to the monitor), monitor_index, dpi_scale
    region_selected = Signal(int, int, int, int, int, float)
    selection_cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_pos = QPoint()
        self._current_pos = QPoint()
        self._is_selecting = False
        self._monitor_index = 0
        self._dpi_scale = 1.0
        self._setup_window()

    def _setup_window(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._instructions = QLabel(t('🎯 Drag to select the subtitle area  |  ESC: cancel'), self)
        self._instructions.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 0.85);
                color: white;
                font-size: 16px;
                padding: 12px 24px;
                border-radius: 8px;
            }
        """)
        self._instructions.adjustSize()

    def start_selection(self, monitor_index=None):
        """Open the overlay on the specified monitor (or all monitors if None)."""
        screens = QGuiApplication.screens()
        if monitor_index is not None and 0 <= monitor_index < len(screens):
            screen = screens[monitor_index]
            geometry = screen.geometry()
            self._dpi_scale = screen.devicePixelRatio()
            self._monitor_index = monitor_index
        else:
            geometry = QRect()
            for screen in screens:
                geometry = geometry.united(screen.geometry())
            self._dpi_scale = screens[0].devicePixelRatio() if screens else 1.0
            self._monitor_index = 0
        self.setGeometry(geometry)
        self._instructions.move((self.width() - self._instructions.width()) // 2, 20)
        self._is_selecting = False
        self._start_pos = QPoint()
        self._current_pos = QPoint()
        self.show()
        self.raise_()
        self.activateWindow()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        if not self._is_selecting:
            return
        rect = self._get_selection_rect()
        if not rect.isValid():
            return
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(rect, Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setPen(QPen(QColor(_ACCENT), 3, Qt.PenStyle.SolidLine))
        painter.drawRect(rect)
        cs = 10
        for corner in (rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight()):
            painter.fillRect(corner.x() - cs // 2, corner.y() - cs // 2, cs, cs, QColor(_ACCENT))
        dim_text = f'{rect.width()} × {rect.height()}'
        painter.setFont(QFont(self.font().family(), 14, QFont.Weight.Bold))
        painter.setPen(QColor('#ffffff'))
        fm = painter.fontMetrics()
        text_rect = fm.boundingRect(dim_text)
        text_x = rect.center().x() - text_rect.width() // 2
        text_y = rect.bottom() + 30
        painter.fillRect(text_x - 8, text_y - text_rect.height(), text_rect.width() + 16, text_rect.height() + 8, QColor(0, 0, 0, 180))
        painter.drawText(text_x, text_y, dim_text)

    def _get_selection_rect(self):
        return QRect(
            min(self._start_pos.x(), self._current_pos.x()),
            min(self._start_pos.y(), self._current_pos.y()),
            abs(self._current_pos.x() - self._start_pos.x()),
            abs(self._current_pos.y() - self._start_pos.y()),
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_pos = event.position().toPoint()
            self._current_pos = self._start_pos
            self._is_selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self._is_selecting:
            self._current_pos = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or not self._is_selecting:
            return
        self._is_selecting = False
        rect = self._get_selection_rect()
        if rect.width() < _MIN_SIZE or rect.height() < _MIN_SIZE:
            self.update()  # too small — let the user draw again
            return
        global_pos = self.mapToGlobal(rect.topLeft())
        for i, screen in enumerate(QGuiApplication.screens()):
            if screen.geometry().contains(global_pos):
                self._monitor_index = i
                self._dpi_scale = screen.devicePixelRatio()
                global_pos = global_pos - screen.geometry().topLeft()
                break
        self.hide()
        self.region_selected.emit(global_pos.x(), global_pos.y(), rect.width(), rect.height(), self._monitor_index, self._dpi_scale)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._is_selecting = False
            self.hide()
            self.selection_cancelled.emit()
            return
        super().keyPressEvent(event)
