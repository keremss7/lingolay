"""
Listen to what the user hears, minus Lingolay itself (Windows 10 version 2004 or later).

Uses WASAPI *process loopback* in "exclude target process tree" mode with our own process id,
so the game or video is captured but Lingolay's dubbing voice is not. Audio is converted by
Windows to 16 kHz mono and the last few seconds are kept in a ring buffer for speaker-gender
detection. Nothing is recorded to disk.
"""
import logging
import os
import sys
import threading

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
BUFFER_SECONDS = 4.0


def is_supported():
    """Process loopback needs Windows 10 build 19041 (version 2004) or newer."""
    return sys.platform == 'win32' and sys.getwindowsversion().build >= 19041


class GameAudioCapture:
    """start() / stop(); recent(seconds) returns the latest audio as float32 at 16 kHz mono."""

    def __init__(self, buffer_seconds=BUFFER_SECONDS):
        self._size = int(buffer_seconds * SAMPLE_RATE)
        self._ring = np.zeros(self._size, np.float32)
        self._written = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread = None
        self.error = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive() and self.error is None

    def start(self, timeout=5.0):
        """Start capturing in a background thread. Returns True once audio is flowing."""
        if not is_supported():
            self.error = 'Windows 10 version 2004 or later is required'
            return False
        if self.running:
            return True
        self.error = None
        self._stop.clear()
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name='GameAudioCapture')
        self._thread.start()
        self._ready.wait(timeout)
        if self.error is None and not self._ready.is_set():
            self.error = 'Audio capture did not start in time'
        return self.error is None

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread = None

    def recent(self, seconds):
        n = min(int(seconds * SAMPLE_RATE), self._size)
        with self._lock:
            n = min(n, self._written)
            if n == 0:
                return np.zeros(0, np.float32)
            end = self._written % self._size
            if end >= n:
                return self._ring[end - n:end].copy()
            return np.concatenate([self._ring[self._size - (n - end):], self._ring[:end]])

    def _push(self, samples):
        if len(samples) >= self._size:
            samples = samples[-self._size:]
        with self._lock:
            start = self._written % self._size
            first = min(len(samples), self._size - start)
            self._ring[start:start + first] = samples[:first]
            self._ring[:len(samples) - first] = samples[first:]
            self._written += len(samples)

    def _run(self):
        try:
            import comtypes
            comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
        except Exception as e:
            self.error = f'COM is unavailable: {e}'
            self._ready.set()
            return
        try:
            _capture_loop(self)
        except Exception as e:
            logger.warning('[GameAudio] Capture stopped: %s', e)
            self.error = str(e)
        finally:
            self._ready.set()
            try:
                comtypes.CoUninitialize()
            except Exception:
                pass


# ── WASAPI process loopback (Windows only) ────────────────────────────────────────────────────

def _capture_loop(capture):
    import ctypes
    from ctypes import POINTER, Structure, byref, c_int, c_longlong, c_uint32, c_uint64, c_ushort, c_void_p, wintypes

    import comtypes
    from comtypes import GUID, STDMETHOD, COMObject, IUnknown

    class WAVEFORMATEX(Structure):
        _fields_ = [('wFormatTag', wintypes.WORD), ('nChannels', wintypes.WORD), ('nSamplesPerSec', wintypes.DWORD),
                    ('nAvgBytesPerSec', wintypes.DWORD), ('nBlockAlign', wintypes.WORD), ('wBitsPerSample', wintypes.WORD),
                    ('cbSize', wintypes.WORD)]

    class PROCESS_LOOPBACK_PARAMS(Structure):
        _fields_ = [('TargetProcessId', wintypes.DWORD), ('ProcessLoopbackMode', c_int)]

    class ACTIVATION_PARAMS(Structure):
        _fields_ = [('ActivationType', c_int), ('ProcessLoopbackParams', PROCESS_LOOPBACK_PARAMS)]

    class BLOB(Structure):
        _fields_ = [('cbSize', wintypes.ULONG), ('pBlobData', c_void_p)]

    class PROPVARIANT(Structure):
        _fields_ = [('vt', c_ushort), ('wReserved1', wintypes.WORD), ('wReserved2', wintypes.WORD),
                    ('wReserved3', wintypes.WORD), ('blob', BLOB)]

    class IAudioCaptureClient(IUnknown):
        _iid_ = GUID('{C8ADBD64-E71E-48a0-A4DE-185C395CD317}')
        _methods_ = [
            STDMETHOD(comtypes.HRESULT, 'GetBuffer', [POINTER(c_void_p), POINTER(c_uint32), POINTER(wintypes.DWORD),
                                                      POINTER(c_uint64), POINTER(c_uint64)]),
            STDMETHOD(comtypes.HRESULT, 'ReleaseBuffer', [c_uint32]),
            STDMETHOD(comtypes.HRESULT, 'GetNextPacketSize', [POINTER(c_uint32)]),
        ]

    class IAudioClient(IUnknown):
        _iid_ = GUID('{1CB9AD4C-DBFA-4c32-B178-C2F568A703B2}')
        _methods_ = [
            STDMETHOD(comtypes.HRESULT, 'Initialize', [c_int, wintypes.DWORD, c_longlong, c_longlong,
                                                       POINTER(WAVEFORMATEX), POINTER(GUID)]),
            STDMETHOD(comtypes.HRESULT, 'GetBufferSize', [POINTER(c_uint32)]),
            STDMETHOD(comtypes.HRESULT, 'GetStreamLatency', [POINTER(c_longlong)]),
            STDMETHOD(comtypes.HRESULT, 'GetCurrentPadding', [POINTER(c_uint32)]),
            STDMETHOD(comtypes.HRESULT, 'IsFormatSupported', [c_int, POINTER(WAVEFORMATEX), POINTER(c_void_p)]),
            STDMETHOD(comtypes.HRESULT, 'GetMixFormat', [POINTER(c_void_p)]),
            STDMETHOD(comtypes.HRESULT, 'GetDevicePeriod', [POINTER(c_longlong), POINTER(c_longlong)]),
            STDMETHOD(comtypes.HRESULT, 'Start', []),
            STDMETHOD(comtypes.HRESULT, 'Stop', []),
            STDMETHOD(comtypes.HRESULT, 'Reset', []),
            STDMETHOD(comtypes.HRESULT, 'SetEventHandle', [wintypes.HANDLE]),
            STDMETHOD(comtypes.HRESULT, 'GetService', [POINTER(GUID), POINTER(POINTER(IAudioCaptureClient))]),
        ]

    class IActivateAudioInterfaceAsyncOperation(IUnknown):
        _iid_ = GUID('{72A22D78-CDE4-431D-B8CC-843A71199B6D}')
        _methods_ = [
            STDMETHOD(comtypes.HRESULT, 'GetActivateResult', [POINTER(comtypes.HRESULT), POINTER(POINTER(IUnknown))]),
        ]

    class IActivateAudioInterfaceCompletionHandler(IUnknown):
        _iid_ = GUID('{41D949AB-9862-444A-80F6-C261334DA5EB}')
        _methods_ = [
            STDMETHOD(comtypes.HRESULT, 'ActivateCompleted', [POINTER(IActivateAudioInterfaceAsyncOperation)]),
        ]

    class IAgileObject(IUnknown):
        _iid_ = GUID('{94EA2B94-E9CC-49E0-C0FF-EE64CA8F5B90}')
        _methods_ = []

    class CompletionHandler(COMObject):
        _com_interfaces_ = [IActivateAudioInterfaceCompletionHandler, IAgileObject]

        def __init__(self):
            super().__init__()
            self.done = threading.Event()

        def ActivateCompleted(self, this, operation):
            self.done.set()
            return 0

    AUDCLNT_SHAREMODE_SHARED = 0
    AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
    AUDCLNT_STREAMFLAGS_EVENTCALLBACK = 0x00040000
    AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY = 0x08000000
    AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM = 0x80000000
    AUDCLNT_BUFFERFLAGS_SILENT = 0x2
    ACTIVATION_TYPE_PROCESS_LOOPBACK = 1
    PROCESS_LOOPBACK_MODE_EXCLUDE_TARGET_PROCESS_TREE = 1
    VT_BLOB = 65

    params = ACTIVATION_PARAMS(ACTIVATION_TYPE_PROCESS_LOOPBACK,
                               PROCESS_LOOPBACK_PARAMS(os.getpid(), PROCESS_LOOPBACK_MODE_EXCLUDE_TARGET_PROCESS_TREE))
    prop = PROPVARIANT(vt=VT_BLOB)
    prop.blob.cbSize = ctypes.sizeof(params)
    prop.blob.pBlobData = ctypes.cast(ctypes.pointer(params), c_void_p)

    activate = ctypes.WinDLL('Mmdevapi.dll').ActivateAudioInterfaceAsync
    activate.argtypes = [wintypes.LPCWSTR, POINTER(GUID), POINTER(PROPVARIANT),
                         POINTER(IActivateAudioInterfaceCompletionHandler), POINTER(POINTER(IActivateAudioInterfaceAsyncOperation))]
    activate.restype = comtypes.HRESULT

    handler = CompletionHandler()
    handler_ptr = handler.QueryInterface(IActivateAudioInterfaceCompletionHandler)
    operation = POINTER(IActivateAudioInterfaceAsyncOperation)()
    iid = IAudioClient._iid_
    activate('VAD\\Process_Loopback', byref(iid), byref(prop), handler_ptr, byref(operation))
    if not handler.done.wait(5.0):
        raise RuntimeError('Audio interface activation timed out')
    result, unknown = comtypes.HRESULT(), POINTER(IUnknown)()
    operation.GetActivateResult(byref(result), byref(unknown))
    if result.value != 0:
        raise OSError(f'Audio interface activation failed (0x{result.value & 0xFFFFFFFF:08X})')
    client = unknown.QueryInterface(IAudioClient)

    fmt = WAVEFORMATEX(1, 1, SAMPLE_RATE, SAMPLE_RATE * 2, 2, 16, 0)  # PCM, mono, 16-bit
    flags = (AUDCLNT_STREAMFLAGS_LOOPBACK | AUDCLNT_STREAMFLAGS_EVENTCALLBACK
             | AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM | AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY)
    client.Initialize(AUDCLNT_SHAREMODE_SHARED, flags, 2_000_000, 0, byref(fmt), None)  # 200 ms buffer

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.CreateEventW.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    event = kernel32.CreateEventW(None, False, False, None)
    client.SetEventHandle(event)

    capture_client = POINTER(IAudioCaptureClient)()  # owned reference, released by comtypes
    capture_iid = IAudioCaptureClient._iid_
    client.GetService(byref(capture_iid), byref(capture_client))

    client.Start()
    capture._ready.set()
    logger.info('[GameAudio] Capturing system audio (excluding Lingolay) at %d Hz', SAMPLE_RATE)
    try:
        packet, data, frames, buf_flags = c_uint32(), c_void_p(), c_uint32(), wintypes.DWORD()
        while not capture._stop.is_set():
            kernel32.WaitForSingleObject(event, 100)
            capture_client.GetNextPacketSize(byref(packet))
            while packet.value:
                capture_client.GetBuffer(byref(data), byref(frames), byref(buf_flags), None, None)
                n = frames.value
                if buf_flags.value & AUDCLNT_BUFFERFLAGS_SILENT or not data.value:
                    samples = np.zeros(n, np.float32)
                else:
                    samples = np.frombuffer(ctypes.string_at(data.value, n * 2), dtype=np.int16).astype(np.float32) / 32768
                capture_client.ReleaseBuffer(n)
                capture._push(samples)
                capture_client.GetNextPacketSize(byref(packet))
    finally:
        client.Stop()
        kernel32.CloseHandle(event)
