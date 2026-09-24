# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [2.0.0] — 2026-09-24

First public open-source release.

### Added
- **Any-direction translation between 15 languages** (on-screen language → target language), with the OCR language, text cleanup rules and dubbing voice following the selected pair.
- **Dubbing voices for all 15 languages** (Piper), downloaded on demand.
- **English and Turkish interface** with a JSON-based i18n system — new UI languages need no code.
- Models download straight from Hugging Face: pinned revisions, SHA-256 verification, automatic retry and resume.
- Command-line model management: `lingolay --list-models`, `lingolay --download fast voice:tr`.
- Tesseract OCR fallback and graceful degradation on Linux/macOS.
- Click-through overlay option, remembered overlay position, overlay background opacity.
- Diagnostics window with one-click copy and GitHub issue link.
- Test suite, CI (Windows + Linux) and automated Windows builds.

### Changed
- No account, license key or server connection is required anymore — the app is fully free and open source.
- Settings are stored per platform (`%LOCALAPPDATA%\Lingolay`, `~/Library/Application Support/Lingolay`, `~/.local/share/Lingolay`); override with `LINGOLAY_HOME`.

### Fixed
- Numerous stability fixes in capture, subtitle stabilization, overlay positioning, hotkey handling and settings dialogs.
