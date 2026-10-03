# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [2.1.0] — 2026-10-04

### Added
- **Natural flow dubbing** (on by default, *Voice dubbing* settings): the line being spoken is no longer cut off by the next subtitle, sentences get a short pause between them, the voice speaks a little faster when it falls behind, and text that was just spoken is not repeated. Turn it off to get the previous behavior.
- **Russian interface** and a [Russian README](docs/README.ru.md).
- Regional interface translations (e.g. `pt-BR.json`) are picked automatically from the system language.

### Fixed
- Longer translations no longer get clipped in field labels and the profile *Delete* / *Save* buttons.

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
