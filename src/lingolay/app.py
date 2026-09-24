"""Application entry point:  `python -m lingolay`  or  `lingolay`."""
import ctypes
import logging
import os
import sys

from lingolay import __app_name__, __version__

_main_window = None
_instance_mutex = None


def _acquire_single_instance():
    """
    Win32 named mutex — prevents a second instance from starting (Windows only).
    Returns True if we are the first instance.
    """
    global _instance_mutex
    if sys.platform != 'win32':
        return True
    ERROR_ALREADY_EXISTS = 183
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    _instance_mutex = kernel32.CreateMutexW(None, False, 'Local\\LingolaySingleton')
    return ctypes.GetLastError() != ERROR_ALREADY_EXISTS


def _install_excepthook(logger):
    """Log uncaught exceptions and show a visible error dialog."""
    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.error('Uncaught exception', exc_info=(exc_type, exc_value, exc_tb))
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            from lingolay.core.paths import LOG_FILE
            from lingolay.i18n import t
            if QApplication.instance() is not None:
                QMessageBox.critical(None, f'{__app_name__} — {t("Unexpected error")}',
                                     f'{exc_type.__name__}: {exc_value}\n\n{t("Details were written to the log file:")}\n{LOG_FILE}')
        except Exception:
            pass

    sys.excepthook = _hook


def _print(text):
    # Windowed (PyInstaller) builds have no console: sys.stdout may be None
    if sys.stdout is not None:
        print(text, flush=True)


def _run_cli(argv):
    """
    Headless commands. Returns an exit code, or None to start the GUI.

      lingolay --version
      lingolay --list-models
      lingolay --download fast            (fast | quality | voice:<lang> | <voice id>)
    """
    import argparse
    parser = argparse.ArgumentParser(prog='lingolay', description=f'{__app_name__} — real-time offline screen translator')
    parser.add_argument('--version', action='store_true', help='print version and exit')
    parser.add_argument('--list-models', action='store_true', help='list downloadable models/voices and their status')
    parser.add_argument('--download', nargs='+', metavar='MODEL', help='download models: fast, quality, voice:<lang> (e.g. voice:tr)')
    args, _qt_args = parser.parse_known_args(argv)
    if args.version:
        _print(f'{__app_name__} {__version__}')
        return 0
    if not (args.list_models or args.download):
        return None

    from lingolay.core.paths import ensure_dirs
    from lingolay.models.manager import get_model_manager
    from lingolay.models.manifest import ALL_ASSETS, get_model, voice_for_language
    ensure_dirs()
    mgr = get_model_manager()
    if args.list_models:
        for mid, info in ALL_ASSETS.items():
            state = 'installed' if mgr.is_installed(mid) else '-'
            _print(f'{mid:<32} {info.approx_size_mb:>6} MB  {state:<9}  {info.license}')
        return 0

    exit_code = 0
    for name in args.download:
        model_id = voice_for_language(name.split(':', 1)[1]) if name.startswith('voice:') else name
        try:
            info = get_model(model_id)
        except KeyError:
            _print(f'Unknown model: {name}. Run --list-models to see the options.')
            exit_code = 2
            continue
        _print(f'Downloading {model_id} (~{info.approx_size_mb} MB) from huggingface.co/{info.repo} ...')
        last = [-1]

        def progress(done, total, last=last):
            pct = int(done * 100 / total) if total else 0
            if pct != last[0] and pct % 5 == 0:
                last[0] = pct
                _print(f'  {pct:3d}%  {done / 1048576:,.0f} / {total / 1048576:,.0f} MB')
        try:
            path = mgr.download(model_id, progress_cb=progress)
            if model_id in ('fast', 'quality'):
                mgr.set_active_model(model_id)
            _print(f'  ✓ installed at {path}')
        except Exception as e:
            _print(f'  ✗ failed: {e}')
            exit_code = 1
    return exit_code


def main(argv=None):
    code = _run_cli(sys.argv[1:] if argv is None else argv)
    if code is not None:
        sys.exit(code)

    from lingolay.core.logging_setup import init_logging
    init_logging(dev_mode=bool(os.environ.get('LINGOLAY_DEV')))
    logger = logging.getLogger(__name__)
    logger.info('=' * 60)
    logger.info('%s %s starting (Python %s, %s)', __app_name__, __version__, sys.version.split()[0], sys.platform)
    logger.info('=' * 60)
    _install_excepthook(logger)

    from lingolay.core.paths import ensure_dirs
    ensure_dirs()

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication.instance()
    created_app = app is None
    if created_app:
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        app = QApplication(sys.argv)
        app.setApplicationName(__app_name__)
        app.setApplicationVersion(__version__)

    from lingolay.core.config import get_settings
    from lingolay.i18n import set_language, t
    set_language(get_settings().ui_language)

    if not _acquire_single_instance():
        logger.warning('[Bootstrap] Another instance is already running — exiting')
        QMessageBox.information(None, __app_name__, t('Lingolay is already running.'))
        sys.exit(0)

    from lingolay.ui.main_window import _asset_path
    icon_path = _asset_path('icon.png')
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    from lingolay.models.manager import get_model_manager
    from lingolay.ui.setup_wizard import should_show_wizard
    _auto_configure_model(get_model_manager(), logger)
    need_wizard = should_show_wizard()
    logger.info('[Bootstrap] model_installed=%s need_wizard=%s', get_model_manager().any_model_installed(), need_wizard)

    if need_wizard:
        from lingolay.ui.setup_wizard import SetupWizard
        wizard = SetupWizard()
        wizard.exec()  # modal; skip / launch / close all continue to the main window
    _show_main_window()

    if created_app:
        sys.exit(app.exec())


def _auto_configure_model(model_mgr, logger):
    """If a model is installed but settings point to a missing path, fix the setting automatically."""
    from lingolay.core.config import get_settings
    s = get_settings()
    if s.translation_engine == 'deepl':
        return
    if (s.get_nllb_model_path() / 'model.bin').exists():
        return
    preferred = 'quality' if s.translation_engine == 'nllb_quality' else 'fast'
    for model_id in (preferred, 'fast', 'quality'):
        if model_mgr.is_installed(model_id):
            model_mgr.set_active_model(model_id)
            logger.info('[Bootstrap] Auto-configured model: %s', model_id)
            return
    logger.info('[Bootstrap] No installed translation model found')


def _show_main_window():
    """
    Create and show the MainWindow. If construction fails, tear down child components such as
    the overlay and hotkeys (otherwise a lone overlay would stay on screen) and re-raise.
    """
    global _main_window
    logger = logging.getLogger(__name__)
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from lingolay.ui.main_window import MainWindow
    win = None
    try:
        win = MainWindow()
        _main_window = win
        screens = QApplication.screens()
        if screens:
            avail = QApplication.primaryScreen().availableGeometry()
            win.move(avail.center() - win.rect().center())
        win.show()
        win.setWindowState((win.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive)
        win.raise_()
        win.activateWindow()
        logger.info('[Bootstrap] MainWindow shown')
    except Exception as e:
        logger.exception('[Bootstrap] MainWindow init failed: %s', e)
        if win:
            ov = getattr(win, '_overlay', None)
            if ov:
                ov.close()
                ov.deleteLater()
            hk = getattr(win, '_hotkeys', None)
            if hk:
                hk.stop()
        raise


if __name__ == '__main__':
    main()
