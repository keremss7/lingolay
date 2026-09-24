import logging
import os
import threading
import time

from lingolay.i18n import t

logger = logging.getLogger(__name__)

PYCAW_AVAILABLE = False
PYCAW_IMPORT_ERROR = ''

try:
    from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
    PYCAW_AVAILABLE = True
except Exception as _e:
    PYCAW_IMPORT_ERROR = str(_e)

_SESSION_CACHE_SEC = 10.0
_HOLD_SEC = 0.6
_TICK_SEC = 0.05


class AudioDucker:
    def __init__(self, level=0.25):
        self._level = max(0.05, min(1.0, level))
        self._own_pid = os.getpid()
        self._want_duck = False
        self._release_at = 0.0
        self._ducked = False
        self._sessions = []
        self._sessions_at = 0.0
        self._saved = []
        self._thread = None
        self._stop_event = threading.Event()
        self._failed = False

    @property
    def is_available(self):
        return PYCAW_AVAILABLE and not self._failed

    @property
    def init_error(self):
        if not PYCAW_AVAILABLE:
            return t('pycaw is unavailable: {error}', error=PYCAW_IMPORT_ERROR)
        return ''

    def set_level(self, level):
        self._level = max(0.05, min(1.0, level))

    def start(self):
        if not self.is_available:
            return self.is_available
        if self._thread and self._thread.is_alive():
            return self.is_available
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name='AudioDucker')
        self._thread.start()
        return True

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    def request_duck(self):
        self._want_duck = True

    def request_release(self):
        if self._want_duck:
            self._want_duck = False
            self._release_at = time.time()

    def _loop(self):
        try:
            while not self._stop_event.is_set():
                try:
                    if self._want_duck and not self._ducked:
                        self._apply_duck()
                    elif not self._want_duck and self._ducked:
                        if time.time() - self._release_at >= _HOLD_SEC:
                            self._apply_restore()
                    self._stop_event.wait(_TICK_SEC)
                except Exception as e:
                    logger.warning('[Ducking] Error, disabling: %s', e)
                    self._failed = True
                    break
        finally:
            if self._ducked:
                try:
                    self._apply_restore()
                except Exception:
                    pass

    def _refresh_sessions(self):
        now = time.time()
        if self._sessions and (now - self._sessions_at) < _SESSION_CACHE_SEC:
            return
        found = []
        for s in AudioUtilities.GetAllSessions():
            proc = s.Process
            if proc is None or proc.pid == self._own_pid:
                continue
            try:
                found.append((proc.name(), s._ctl.QueryInterface(ISimpleAudioVolume)))
            except Exception:
                continue
        self._sessions = found
        self._sessions_at = now

    def _apply_duck(self):
        self._refresh_sessions()
        saved = []
        for _name, vol in self._sessions:
            try:
                current = vol.GetMasterVolume()
                vol.SetMasterVolume(current * self._level, None)
                saved.append((vol, current))
            except Exception:
                continue
        self._saved = saved
        self._ducked = True
        if saved:
            logger.debug('[Ducking] Lowered %d apps to %.0f%%', len(saved), self._level * 100)

    def _apply_restore(self):
        for vol, original in self._saved:
            try:
                vol.SetMasterVolume(original, None)
            except Exception:
                continue
        self._saved = []
        self._ducked = False

