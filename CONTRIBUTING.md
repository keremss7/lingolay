# Contributing to Lingolay

First off — thank you! 🎉 Every contribution helps: code, translations, bug reports, documentation, game presets or simply sharing the project.

## 🧭 Ways to help

| I want to… | Start here |
|---|---|
| Report a bug | [Bug report](https://github.com/keremss7/lingolay/issues/new?template=bug_report.yml) — please paste the *Diagnostics* output from the app |
| Suggest a feature | [Feature request](https://github.com/keremss7/lingolay/issues/new?template=feature_request.yml) or a [Discussion](https://github.com/keremss7/lingolay/discussions) |
| Translate the UI | [see below](#-translate-the-interface) — no coding needed |
| Add a language / voice | [see below](#-add-a-translation-language-or-dubbing-voice) |
| Write code | pick a [`good first issue`](https://github.com/keremss7/lingolay/labels/good%20first%20issue) or [`help wanted`](https://github.com/keremss7/lingolay/labels/help%20wanted) |

## 🛠️ Development setup

```bash
git clone https://github.com/<you>/lingolay.git
cd lingolay
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
lingolay                          # run the app (set LINGOLAY_DEV=1 for verbose console logs)
```

Before opening a pull request:

```bash
ruff check src tests              # lint (ruff check --fix for auto-fixes)
pytest                            # tests are headless and need no models
```

Tip: set `LINGOLAY_HOME=/some/tmp/dir` to keep your development settings and models separate from your real installation.

## 🌐 Translate the interface

1. Copy `src/lingolay/i18n/locales/tr.json` to `src/lingolay/i18n/locales/<code>.json` (e.g. `de.json`).
2. Set `"_meta.name"` to the language's own name (e.g. `"Deutsch"`).
3. Translate every value. **Keep `{placeholders}` exactly as they are** — the test suite checks this.
4. Run `pytest tests/test_languages_and_models.py` and open a PR. The new language appears automatically under *Appearance → Interface*.

## 🌍 Add a translation language or dubbing voice

- Languages live in one table: `src/lingolay/languages.py`. Add the ISO code, names, the [FLORES‑200 code](https://github.com/facebookresearch/flores/blob/main/flores200/README.md#languages-in-flores-200) used by NLLB and the Windows OCR tag.
- Dubbing voices are listed in `VOICE_TABLE` in `src/lingolay/models/manifest.py`. Pick a voice from [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices), and add its paths, sizes and SHA‑256 (visible on the Hugging Face file page).

## 📐 Code guidelines

- Python ≥ 3.10, formatted/linted with `ruff`. Keep functions small and add a short docstring when the *why* isn't obvious.
- All user‑visible text goes through `t()` from `lingolay.i18n` with English source strings and `{named}` placeholders.
- Platform‑specific code must degrade gracefully (check `sys.platform` and catch `ImportError`).
- Never commit model weights — they are downloaded at runtime.
- Add or update tests for logic changes (`tests/`).

## 🔀 Pull requests

- One topic per PR, with a clear title (e.g. `fix: overlay jumps on multi-monitor setups`).
- Describe how you tested it (which game/video and language pair?). Screenshots for UI changes are very welcome.
- By contributing you agree that your work is licensed under the project's [GPL‑3.0](LICENSE) license.

Please follow our [Code of Conduct](CODE_OF_CONDUCT.md). Happy hacking! 🚀
