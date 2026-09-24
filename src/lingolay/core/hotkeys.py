"""
Global keyboard shortcuts (Windows RegisterHotKey).

The Win32 message loop runs on its own thread so shortcuts work even while a
game is fullscreen. On other platforms global shortcuts are disabled (the app
still works, the shortcuts are just inactive).
"""
import ctypes
import logging
import sys
import threading

logger = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == 'win32'
if IS_WINDOWS:
    import ctypes.wintypes
    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32
else:
    _user32 = None
    _kernel32 = None

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

ACTION_LABELS = {
    'start_stop': 'Start / Stop',
    'select_region': 'Select region',
    'toggle_overlay': 'Show/hide overlay',
    'toggle_preview': 'OCR preview',
    'toggle_window': 'Show/hide window',
    'game_mode': 'Game mode',
    'toggle_tts': 'Dubbing on/off',
}

DEFAULT_HOTKEYS = {
    'start_stop': 'Ctrl+Alt+S',
    'select_region': 'Ctrl+Alt+R',
    'toggle_overlay': 'Ctrl+Alt+O',
    'toggle_preview': 'Ctrl+Alt+P',
    'toggle_window': 'Ctrl+Alt+W',
    'game_mode': 'Ctrl+Alt+G',
    'toggle_tts': 'Ctrl+Alt+D',
}

_KEY_TO_VK: dict[str, int] = {}
for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
    _KEY_TO_VK[c] = ord(c)
for i in range(10):
    _KEY_TO_VK[str(i)] = ord(str(i))
for i in range(1, 13):
    _KEY_TO_VK[f'F{i}'] = 111 + i
_KEY_TO_VK.update({
    'SPACE': 32, 'TAB': 9, 'RETURN': 13, 'ENTER': 13, 'ESCAPE': 27, 'ESC': 27,
    'BACKSPACE': 8, 'DELETE': 46, 'DEL': 46, 'INSERT': 45, 'INS': 45,
    'HOME': 36, 'END': 35, 'PAGEUP': 33, 'PGUP': 33, 'PAGEDOWN': 34, 'PGDN': 34,
    'LEFT': 37, 'UP': 38, 'RIGHT': 39, 'DOWN': 40,
    'PRINTSCREEN': 44, 'PAUSE': 19, 'NUMLOCK': 144, 'SCROLLLOCK': 145, 'CAPSLOCK': 20,
    'NUMPAD0': 96, 'NUMPAD1': 97, 'NUMPAD2': 98, 'NUMPAD3': 99, 'NUMPAD4': 100,
    'NUMPAD5': 101, 'NUMPAD6': 102, 'NUMPAD7': 103, 'NUMPAD8': 104, 'NUMPAD9': 105,
    'NUMPAD*': 106, 'NUMPAD+': 107, 'NUMPAD-': 109, 'NUMPAD.': 110, 'NUMPAD/': 111,
    ';': 186, ':': 186, '=': 187, '+': 187, ',': 188, '<': 188,
    '-': 189, '_': 189, '.': 190, '>': 190, '/': 191, '?': 191,
    '`': 192, '~': 192, '[': 219, '{': 219, '\\': 220, '|': 220,
    ']': 221, '}': 221, "'": 222, '"': 222,
})


def parse_hotkey_string(s):
    """
    "Ctrl+Alt+S" → (modifier_flags, vk_code)
    Invalid string → None
    """
    if not s:
        return None
    parts = [p.strip().upper() for p in s.split('+')]
    modifier = MOD_NOREPEAT
    vk = None
    for part in parts:
        if part == 'CTRL':
            modifier |= MOD_CONTROL
        elif part == 'ALT':
            modifier |= MOD_ALT
        elif part == 'SHIFT':
            modifier |= MOD_SHIFT
        elif part == 'WIN':
            modifier |= MOD_WIN
        else:
            vk = _KEY_TO_VK.get(part)
    if vk is None:
        logger.warning("[Hotkeys] No main key found in: '%s'", s)
        return None
    return (modifier, vk)


def normalize_hotkey_string(s):
    """"ctrl+alt+s" → "Ctrl+Alt+S"  (canonical form)"""
    if not s:
        return s
    parts = [p.strip() for p in s.split('+')]
    result = []
    key_part = None
    for p in parts:
        up = p.upper()
        if up == 'CTRL':
            result.append('Ctrl')
        elif up == 'ALT':
            result.append('Alt')
        elif up == 'SHIFT':
            result.append('Shift')
        elif up == 'WIN':
            result.append('Win')
        else:
            key_part = up
    if key_part:
        result.append(key_part)
    return '+'.join(result)


class HotkeyManager:
    """Win32 global hotkey listener. Callbacks are invoked from the listener thread."""

    def __init__(self):
        self._callbacks = {}
        self._thread = None
        self._thread_id = 0
        self._running = False
        self._registered = []
        self._action_keys = dict(DEFAULT_HOTKEYS)

    def set_callback(self, action, callback):
        self._callbacks[action] = callback

    def load_from_config(self, hotkeys_dict):
        """Load hotkey definitions from a config dict."""
        self._action_keys = dict(hotkeys_dict)

    @property
    def is_available(self):
        return IS_WINDOWS

    def start(self):
        if self._running:
            return
        if not IS_WINDOWS:
            logger.info('[Hotkeys] Global shortcuts are only supported on Windows — disabled')
            return
        self._running = True
        ready_event = threading.Event()
        self._thread = threading.Thread(target=self._loop, args=(ready_event,), daemon=True, name='HotkeyListener')
        self._thread.start()
        ready_event.wait(timeout=3.0)
        logger.info('[Hotkeys] Started (thread=%s)', self._thread_id)

    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._thread_id:
            _user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread_id = 0
        logger.info('[Hotkeys] Stopped')

    def reload(self, hotkeys_dict):
        """Change shortcuts: stop, load the new config, start again."""
        self.stop()
        self.load_from_config(hotkeys_dict)
        self.start()

    def get_current_keys(self):
        """Return the current action → key string mapping."""
        return dict(self._action_keys)

    def _build_hotkey_map(self):
        """Build a {hid: (action, modifier, vk, label)} table from _action_keys."""
        result = {}
        for hid, (action, key_str) in enumerate(self._action_keys.items(), start=1):
            parsed = parse_hotkey_string(key_str)
            if not parsed:
                logger.warning("[Hotkeys] Invalid shortcut for '%s': '%s' — skipped", action, key_str)
                continue
            modifier, vk = parsed
            result[hid] = (action, modifier, vk, normalize_hotkey_string(key_str))
        return result

    def _loop(self, ready_event):
        self._thread_id = _kernel32.GetCurrentThreadId()
        hotkey_map = self._build_hotkey_map()
        for hid, (action, modifier, vk, label) in hotkey_map.items():
            if _user32.RegisterHotKey(None, hid, modifier, vk):
                self._registered.append(hid)
                logger.debug('[Hotkeys] Registered: %s -> %s', label, action)
            else:
                logger.warning('[Hotkeys] Could not register %s (another app may be using it)', label)
        ready_event.set()

        msg = ctypes.wintypes.MSG()
        while self._running:
            ret = _user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:  # WM_QUIT or error
                break
            if msg.message == WM_HOTKEY:
                entry = hotkey_map.get(msg.wParam)
                if entry:
                    self._dispatch(entry[0])
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))

        for hid in self._registered:
            _user32.UnregisterHotKey(None, hid)
        self._registered.clear()
        logger.debug('[Hotkeys] Thread finished, hotkeys unregistered')

    def _dispatch(self, action):
        callback = self._callbacks.get(action)
        if callback:
            try:
                callback()
            except Exception:
                logger.exception('[Hotkeys] %s callback failed', action)
