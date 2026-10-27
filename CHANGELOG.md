# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [2.5.1] — 2026-10-27

### Added
- **Black-screen hint**: some games run in exclusive fullscreen, where Windows gives screen capture only a black image ([#2](https://github.com/keremss7/lingolay/issues/2)). Lingolay now notices this and shows a tip on the overlay to switch the game to *Borderless* or *Windowed* mode, both for subtitles and for *Translate screen* ([#27](https://github.com/keremss7/lingolay/pull/27)).

## [2.5.0] — 2026-10-23

### Added
- **Translate screen** *(experimental)*: press **Ctrl+Alt+T** (or *Translate screen* on the home page) and every piece of text on the screen is translated in place, drawn over the original with its background, colors, outline and size; press again to hide. Built for game menus, notes, item descriptions and HUD text. Plain backgrounds are filled, textured ones are repaired, so the original disappears without a visible box. The first translation of a screen takes a few seconds, repeats are instant ([#25](https://github.com/keremss7/lingolay/pull/25)).
- Faster batch translation with the NLLB models.

## [2.4.1] — 2026-10-22

### Fixed
- **Game mode missed grey or tinted subtitles on the black bar below the picture** when the selected region also covered part of the game image. Dark bars and boxes are now detected row by row ([#15](https://github.com/keremss7/lingolay/issues/15)).

## [2.4.0] — 2026-10-20

### Added
- **Choose the dubbing voice** for each language in *Voice dubbing → Voice*, with its gender shown. Hindi gets a third voice (Rohan). With *Speaker-aware voice* on, your choice is used for its gender.

### Fixed
- **Game mode missed subtitles inside a dark box.** Light grey or tinted text in a black or see-through box is now read too; white subtitles over the game look the same as before. Thanks to the Hindi/Urdu users who reported it ([discussion #14](https://github.com/keremss7/lingolay/discussions/14)).

## [2.3.1] — 2026-10-18

### Changed
- **Speaker-aware voice is now on the home page**, right under Dubbing, instead of at the bottom of the Translation page. One switch turns it (and dubbing) on, and a live label shows which voice is speaking: female, male or default ([#20](https://github.com/keremss7/lingolay/pull/20)).

## [2.3.0] — 2026-10-17

### Added
- **Speaker-aware dubbing** *(experimental, off by default)*: Lingolay listens to the game or video, detects whether a man or a woman is speaking and dubs each line with a matching voice, in all 20 dubbed languages. Enable it under *Voice dubbing → Match the speaker's voice* (Windows 10 version 2004 or later). It hears the system audio without Lingolay's own voice, nothing is recorded, and it works offline after a one-time download of a ~60 MB model and the extra voices ([#18](https://github.com/keremss7/lingolay/pull/18)).
- `lingolay --listen-test [seconds]` checks the audio capture and speaker detection on your PC.

## [2.2.1] — 2026-10-17

### Fixed
- **Japanese dubbing produced no audio.** The Japanese voice needs the OpenJTalk phonemizer, which was missing from the Windows build; it is now included and works fully offline ([#17](https://github.com/keremss7/lingolay/pull/17)). The download is about 35 MB larger because of the Japanese dictionary.

## [2.2.0] — 2026-10-17

### Added
- **Six new languages: Hindi, Urdu, Bengali, Vietnamese, Indonesian and Thai** (now 21), with offline dubbing voices for all of them except Thai ([#16](https://github.com/keremss7/lingolay/pull/16)). Requested in [#2](https://github.com/keremss7/lingolay/issues/2), [#15](https://github.com/keremss7/lingolay/issues/15) and [discussion #14](https://github.com/keremss7/lingolay/discussions/14).
- Lingolay can now be supported on [GitHub Sponsors](https://github.com/sponsors/keremss7).

### Fixed
- Dubbing recognizes the Hindi/Bengali danda (।), the Urdu full stop (۔) and CJK sentence marks, so those lines are spoken right away.

## [2.1.1] — 2026-10-12

### Added
- **German interface** — thanks to [@Mr-Neutr0n](https://github.com/Mr-Neutr0n) ([#11](https://github.com/keremss7/lingolay/pull/11)).

### Fixed
- Long subtitles (over 150 characters) lost their last words before translation ([#12](https://github.com/keremss7/lingolay/issues/12)).
- Subtitles that are typed out letter by letter were translated while half-typed, and the finished line was skipped as a duplicate ([#12](https://github.com/keremss7/lingolay/issues/12)). Thanks to [@povizun](https://github.com/povizun) for the detailed report.

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
