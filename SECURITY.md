# Security Policy

## Supported versions

Only the latest release receives security fixes.

## Reporting a vulnerability

Please **do not** open a public issue. Instead use [GitHub private vulnerability reporting](https://github.com/keremss7/lingolay/security/advisories/new).
You'll get a response within a few days.

## Design notes

- Lingolay makes network requests **only** to download models/voices from Hugging Face (pinned commits, SHA‑256 verified) and, if you enable it, to the DeepL API with your own key.
- No telemetry, analytics or accounts. Settings and your DeepL key are stored locally in your user data folder.
