"""Switch a game window to "borderless windowed" mode (Windows only)."""
import ctypes
import logging
import sys

from lingolay.i18n import t

if sys.platform == 'win32':
    import ctypes.wintypes

logger = logging.getLogger(__name__)

GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
BORDER_MASK = WS_CAPTION | WS_THICKFRAME | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX
SWP_FRAMECHANGED = 0x0020
SWP_NOACTIVATE = 0x0010
SWP_NOZORDER = 0x0004
MONITOR_DEFAULTTONEAREST = 2

if sys.platform == 'win32':
    class _MONITORINFO(ctypes.Structure):
        _fields_ = [('cbSize', ctypes.c_ulong), ('rcMonitor', ctypes.wintypes.RECT), ('rcWork', ctypes.wintypes.RECT), ('dwFlags', ctypes.c_ulong)]


class WindowState:
    """Previous style and position of a window, for restoring it later."""

    def __init__(self, hwnd, style, rect):
        self.hwnd = hwnd
        self.style = style
        self.rect = rect


def force_borderless_foreground():
    """
    Switch the current foreground window to borderless windowed.
    Returns: (success, message, window_state_for_restore)
    """
    if sys.platform != 'win32':
        return (False, t('Borderless mode is only supported on Windows.'), None)
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return (False, t('No active window found.'), None)
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    title = buf.value or '(untitled)'
    old_style = user32.GetWindowLongW(hwnd, GWL_STYLE)
    old_rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(old_rect))
    state = WindowState(hwnd, old_style, old_rect)
    user32.SetWindowLongW(hwnd, GWL_STYLE, old_style & ~BORDER_MASK)
    hmon = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    mi = _MONITORINFO()
    mi.cbSize = ctypes.sizeof(_MONITORINFO)
    user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
    r = mi.rcMonitor
    user32.SetWindowPos(hwnd, 0, r.left, r.top, r.right - r.left, r.bottom - r.top, SWP_FRAMECHANGED | SWP_NOACTIVATE | SWP_NOZORDER)
    logger.info("[Borderless] '%s' → borderless (%dx%d)", title, r.right - r.left, r.bottom - r.top)
    return (True, t("'{title}' switched to borderless.", title=title), state)


def restore_window(state):
    """Restore a window to its previous state."""
    if not state or sys.platform != 'win32':
        return False
    user32 = ctypes.windll.user32
    user32.SetWindowLongW(state.hwnd, GWL_STYLE, state.style)
    r = state.rect
    user32.SetWindowPos(state.hwnd, 0, r.left, r.top, r.right - r.left, r.bottom - r.top, SWP_FRAMECHANGED | SWP_NOACTIVATE | SWP_NOZORDER)
    logger.info('[Borderless] Window restored.')
    return True
