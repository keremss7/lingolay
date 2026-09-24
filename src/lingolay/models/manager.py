"""
Model download / installation manager.

Download flow (per file):  download to <name>.part → verify SHA-256 → move into place.
When all files are done, an `.installed` marker file is written to the install dir.
Interrupted connections are resumed (HTTP Range); already completed and verified
files are not downloaded again.
"""
import hashlib
import logging
import shutil
import sys
from pathlib import Path

from lingolay.i18n import t

logger = logging.getLogger(__name__)

SENTINEL_FILE = '.installed'
MODEL_BIN = 'model.bin'
_CHUNK = 256 * 1024
_USER_AGENT = 'Lingolay (+https://github.com/keremss7/lingolay)'


class DownloadCancelled(Exception):
    """The user cancelled the download."""


def _find_model_bin_dir(root):
    """Return the first directory containing model.bin in root or two levels below (None if absent)."""
    try:
        root = Path(root)
        if not root.exists():
            return None
        if (root / MODEL_BIN).exists():
            return root
        children = sorted(c for c in root.iterdir() if c.is_dir())
        for child in children:
            if (child / MODEL_BIN).exists():
                return child
        for child in children:
            try:
                for grandchild in sorted(g for g in child.iterdir() if g.is_dir()):
                    if (grandchild / MODEL_BIN).exists():
                        return grandchild
            except OSError:
                continue
    except OSError:
        pass
    return None


def _sha256(path):
    sha = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            sha.update(block)
    return sha.hexdigest()


class ModelManager:
    def __init__(self):
        from lingolay.core.paths import MODELS_DIR, VOICES_DIR
        self._models_dir = MODELS_DIR
        self._voices_dir = VOICES_DIR

    # ── Sorgular ───────────────────────────────────────────────────────────
    def install_dir(self, model_id):
        from lingolay.models.manifest import get_model
        info = get_model(model_id)
        return (self._voices_dir if info.kind == 'voice' else self._models_dir) / model_id

    def is_installed(self, model_id):
        """True if the asset is available — bundled next to the app or installed in the data dir."""
        if self._bundled_path(model_id) is not None:
            return True
        return (self.install_dir(model_id) / SENTINEL_FILE).exists()

    def any_model_installed(self):
        from lingolay.models.manifest import MODELS
        return any(self.is_installed(mid) for mid in MODELS)

    def get_model_path(self, model_id):
        """
        Return the directory holding the asset (for translation models: the one containing model.bin).
        Priority: 1) bundled next to the app  2) data dir. None if not installed.
        """
        bundled = self._bundled_path(model_id)
        if bundled is not None:
            return bundled
        install_dir = self.install_dir(model_id)
        if not (install_dir / SENTINEL_FILE).exists():
            return None
        from lingolay.models.manifest import get_model
        if get_model(model_id).kind == 'voice':
            return install_dir
        return _find_model_bin_dir(install_dir)

    def _bundled_path(self, model_id):
        """
        Portable install: a models/<id> folder next to the app
        (PyInstaller bundle or repository root). Translation models only.
        """
        from lingolay.models.manifest import MODELS
        if model_id not in MODELS:
            return None
        if getattr(sys, 'frozen', False):
            base = Path(sys.executable).parent / 'models' / model_id
        else:
            base = Path(__file__).resolve().parents[3] / 'models' / model_id
        return _find_model_bin_dir(base)

    def get_active_model_id(self):
        from lingolay.core.config import get_settings
        return 'quality' if get_settings().translation_engine == 'nllb_quality' else 'fast'

    # ── Download ────────────────────────────────────────────────────────────
    def download(self, model_id, progress_cb=None, cancel_event=None):
        """
        Download, verify and install an asset. Blocking — call from a worker thread.

        progress_cb(bytes_downloaded, total_bytes) is called during download.
        cancel_event.set() aborts mid-download (raises DownloadCancelled).
        Returns the installed path. Raises RuntimeError on failure.
        """
        from lingolay.models.manifest import get_model
        info = get_model(model_id)
        install_dir = self.install_dir(model_id)
        install_dir.mkdir(parents=True, exist_ok=True)
        (install_dir / SENTINEL_FILE).unlink(missing_ok=True)

        total = sum(f.size for f in info.files)
        done_before = 0
        logger.info("[ModelManager] Downloading '%s' from %s@%s", model_id, info.repo, info.revision[:8])
        for rf in info.files:
            dest = install_dir / rf.local_name
            if dest.exists() and dest.stat().st_size == rf.size and (not rf.sha256 or _sha256(dest) == rf.sha256):
                logger.info('[ModelManager] %s already present, skipped', rf.local_name)
            else:
                tmp = dest.with_name(dest.name + '.part')
                try:
                    self._download_file(
                        info.url_for(rf), tmp,
                        lambda d, _t, base=done_before: progress_cb(base + d, total) if progress_cb else None,
                        cancel_event,
                    )
                    if rf.sha256:
                        actual = _sha256(tmp)
                        if actual != rf.sha256:
                            raise RuntimeError(t('Checksum verification failed: {file}\n  Expected: {expected}\n  Got:      {actual}',
                                             file=rf.local_name, expected=rf.sha256, actual=actual))
                    shutil.move(str(tmp), str(dest))
                finally:
                    tmp.unlink(missing_ok=True)
            done_before += rf.size
            if progress_cb:
                progress_cb(done_before, total)

        (install_dir / SENTINEL_FILE).write_text(f'{info.repo}@{info.revision}\n', encoding='utf-8')
        path = self.get_model_path(model_id)
        logger.info("[ModelManager] '%s' installed at %s", model_id, path)
        return path

    def remove(self, model_id):
        """Delete an installed model (to free disk space)."""
        shutil.rmtree(self.install_dir(model_id), ignore_errors=True)

    def set_active_model(self, model_id):
        """Point the settings at an installed translation model."""
        from lingolay.core.config import get_settings, save_settings
        model_path = self.get_model_path(model_id)
        if not model_path:
            logger.error("[ModelManager] set_active_model: '%s' not installed", model_id)
            return False
        settings = get_settings()
        settings.nllb_model_dir = str(model_path)
        settings.translation_engine = 'nllb_quality' if model_id == 'quality' else 'nllb_fast'
        save_settings(settings)
        logger.info("[ModelManager] Active model: '%s' → %s", model_id, model_path)
        return True

    @staticmethod
    def _download_file(url, dest, progress_cb, cancel_event, retries=5):
        """
        Download a file. If the connection drops, resume where it left off
        (HTTP Range), retrying up to `retries` times.
        """
        import ssl
        import time
        import urllib.error
        import urllib.request
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ctx = ssl.create_default_context()

        dest = Path(dest)
        dest.unlink(missing_ok=True)
        last_error = None
        for attempt in range(retries + 1):
            downloaded = dest.stat().st_size if dest.exists() else 0
            headers = {'User-Agent': _USER_AGENT}
            if downloaded:
                headers['Range'] = f'bytes={downloaded}-'
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                    if 'text/html' in resp.headers.get('Content-Type', ''):
                        preview = resp.read(256).decode('utf-8', errors='replace').strip()
                        raise RuntimeError(t('The server returned HTML instead of the file.\nURL: {url}\nResponse: {preview}', url=url, preview=preview[:120]))
                    if downloaded and resp.status != 206:
                        downloaded = 0  # server does not support Range — start over
                    total = downloaded + int(resp.headers.get('Content-Length', 0) or 0)
                    with open(dest, 'ab' if downloaded else 'wb') as f:
                        while True:
                            if cancel_event is not None and cancel_event.is_set():
                                raise DownloadCancelled('Download cancelled by user')
                            chunk = resp.read(_CHUNK)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_cb:
                                progress_cb(downloaded, total)
                    if total and downloaded < total:
                        raise ConnectionError(f'Eksik indirme: {downloaded}/{total} bayt')
                return
            except (DownloadCancelled, RuntimeError):
                raise
            except urllib.error.HTTPError as e:
                if e.code == 416:  # requested range is past the end of the file → already complete
                    return
                if 400 <= e.code < 500 and e.code != 429:
                    raise RuntimeError(t('The server returned an error: HTTP {code} {reason}\nURL: {url}', code=e.code, reason=e.reason, url=url)) from e
                last_error = f'HTTP {e.code} {e.reason}'
            except (urllib.error.URLError, OSError) as e:
                last_error = str(getattr(e, 'reason', e))
            if attempt < retries:
                wait = min(2 ** attempt, 20)
                logger.warning('[ModelManager] Download interrupted (%s) — resuming in %ds (%d/%d)', last_error, wait, attempt + 1, retries)
                time.sleep(wait)
        raise RuntimeError(t('Download failed: {error}\nCheck your internet connection and try again.', error=last_error))


_manager = None


def get_model_manager():
    global _manager
    if _manager is None:
        _manager = ModelManager()
    return _manager
