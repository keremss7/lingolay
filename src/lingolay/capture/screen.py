import logging
import time
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QMutex, QMutexLocker, QThread, Signal

from lingolay.core.config import get_settings
from lingolay.i18n import t

logger = logging.getLogger(__name__)

try:
    import dxcam  # Windows Desktop Duplication API (fast, also works for games)
    _DXCAM_AVAILABLE = True
except Exception:
    dxcam = None
    _DXCAM_AVAILABLE = False

try:
    import mss
    _MSS_AVAILABLE = True
except Exception:
    mss = None
    _MSS_AVAILABLE = False


@dataclass
class CaptureFrame:
    image: np.ndarray
    timestamp: float
    monitor_index: int
    capture_latency_ms: int


class ScreenCapture(QThread):
    """Captures the selected region periodically; the interval adapts to processing time."""
    frame_ready = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._region = None
        self._monitor_index = 0
        self._dpi_scale = 1.0
        self._running = False
        self._paused = False
        self._latest_frame = None
        self._frame_mutex = QMutex()
        self._current_interval_ms = 200
        self._last_process_time_ms = 0
        self._frame_count = 0
        self._dropped_frames = 0
        self._last_capture_latency = 0

    def set_region(self, x, y, width, height, monitor_index, dpi_scale):
        """
        Set the capture region.
        Coordinates are in logical pixels relative to the monitor; DPI scale is
        applied to get physical pixels.
        """
        self._region = (int(x * dpi_scale), int(y * dpi_scale), int(width * dpi_scale), int(height * dpi_scale))
        self._monitor_index = monitor_index
        self._dpi_scale = dpi_scale

    def start_capture(self):
        if not self._region:
            self.error_occurred.emit(t('Select a region first'))
            return
        if self.isRunning():
            return
        self._current_interval_ms = get_settings().capture_interval_ms
        self._running = True
        self._paused = False
        self.start()

    def stop_capture(self):
        self._running = False
        self.wait(3000)

    def pause_capture(self):
        self._paused = True

    def resume_capture(self):
        self._paused = False

    def get_latest_frame(self):
        """Get and consume the most recently captured frame (thread-safe)."""
        with QMutexLocker(self._frame_mutex):
            frame = self._latest_frame
            self._latest_frame = None
        return frame

    def report_processing_time(self, time_ms):
        """How long the pipeline took to process the last frame — feedback for the adaptive interval."""
        self._last_process_time_ms = time_ms
        settings = get_settings()
        if not settings.adaptive_interval:
            return
        if time_ms > self._current_interval_ms:
            self._current_interval_ms = min(settings.max_interval_ms, self._current_interval_ms + 50)
        elif time_ms < self._current_interval_ms * 0.5:
            self._current_interval_ms = max(settings.min_interval_ms, self._current_interval_ms - 25)

    @property
    def capture_latency_ms(self):
        return self._last_capture_latency

    @property
    def current_interval_ms(self):
        return self._current_interval_ms

    @property
    def dropped_frame_count(self):
        return self._dropped_frames

    def run(self):
        """Main capture loop — tries dxcam first, falls back to mss."""
        if _DXCAM_AVAILABLE:
            try:
                logger.info('[Capture] Using dxcam (Desktop Duplication API)')
                self._run_dxcam()
                return
            except Exception as e:
                logger.warning('[Capture] dxcam failed (%s) — falling back to mss', e)
        if not _MSS_AVAILABLE:
            self.error_occurred.emit(t('No screen capture library found (mss/dxcam)'))
            return
        logger.info('[Capture] Using mss')
        try:
            self._run_mss()
        except Exception as e:
            logger.exception('[Capture] mss error')
            self.error_occurred.emit(t('Screen capture error: {error}', error=e))

    def _publish(self, img, start_time):
        cap_ms = int((time.perf_counter() - start_time) * 1000)
        self._last_capture_latency = cap_ms
        frame = CaptureFrame(image=img, timestamp=time.time(), monitor_index=self._monitor_index, capture_latency_ms=cap_ms)
        with QMutexLocker(self._frame_mutex):
            self._latest_frame = frame
        self._frame_count += 1
        self.frame_ready.emit(frame)

    def _sleep_rest(self, start_time):
        elapsed = (time.perf_counter() - start_time) * 1000
        time.sleep(max(0.0, self._current_interval_ms - elapsed) / 1000)

    def _run_dxcam(self):
        """Capture loop using dxcam (DirectX Desktop Duplication)."""
        x, y, w, h = self._region
        region = (x, y, x + w, y + h)
        camera = dxcam.create(output_idx=self._monitor_index, output_color='BGR')
        if camera is None:
            raise RuntimeError('dxcam could not create a camera')
        logger.info('[Capture][dxcam] output=%d region=%s', self._monitor_index, region)
        last_img = None
        try:
            while self._running:
                if self._paused:
                    time.sleep(0.1)
                    continue
                start_time = time.perf_counter()
                img = camera.grab(region=region)
                if img is None:
                    # dxcam returns None when the screen has not changed — re-publish the
                    # last frame so the pipeline can finish a pending subtitle.
                    self._dropped_frames += 1
                    img = last_img
                if img is not None:
                    last_img = img
                    self._publish(img, start_time)
                self._sleep_rest(start_time)
        finally:
            del camera

    def _run_mss(self):
        """Capture loop using mss (BitBlt / Quartz / X11)."""
        with mss.mss() as sct:
            monitors = sct.monitors
            mon_idx = self._monitor_index + 1  # mss: 0 = all screens
            if mon_idx >= len(monitors):
                self.error_occurred.emit(t('Monitor {index} not found', index=self._monitor_index))
                return
            monitor = monitors[mon_idx]
            x, y, w, h = self._region
            capture_region = {'left': monitor['left'] + x, 'top': monitor['top'] + y, 'width': w, 'height': h}
            logger.info('[Capture][mss] region=%s', capture_region)
            while self._running:
                if self._paused:
                    time.sleep(0.1)
                    continue
                start_time = time.perf_counter()
                screenshot = sct.grab(capture_region)
                img = np.ascontiguousarray(np.array(screenshot)[:, :, :3])  # BGRA → BGR
                self._publish(img, start_time)
                self._sleep_rest(start_time)
