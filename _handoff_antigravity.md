# Handoff for Antigravity

## Project

`C:\Users\naoya\myproject\book_maker_app`

Production alias: `https://bookmakerapp.vercel.app`

## Latest Change

The public manuscript output was tightened so generated files do not expose generation artifacts.

Implemented behavior:

- Remove all asterisk characters from public manuscript text.
- Remove OpenXML pagebreak tags from public manuscript text.
- Remove unnecessary `第99章`.
- Remove AI, ChatGPT, Gemini, or similar generation-origin wording.
- Normalize duplicated intro and outro headings such as `はじめに はじめに` and `おわりに おわりに`.
- Avoid forcing duplicated `はじめに` or `おわりに` when a chapter title repeats the chapter label.
- Keep `chapter.txt` and `reference.txt` free of literal asterisk characters.

## Relevant Files

- `generator.py`
  - `clean_public_manuscript()` is the final public-output cleanup function.
  - `generate_chapter()` now normalizes repeated chapter title values before prompt rendering.
- `prompts/chapter.txt`
- `prompts/reference.txt`
- `README.md`
- `FIRST_TIME_USER_MANUAL.md`
- `_handoff_claude_code.md`
- `_handoff_antigravity.md`
- `_handoff_codex.md`

## Existing App Behavior

- Each publishing client can set their own author name, background, achievements, tone, target reader, keywords, and optional examples.
- Blank profile fields are not forced into manuscripts.
- Prompts should only use facts present in profile fields or reference material.
- Failure examples and voice types are optional context, not required decorations.

## Verification

Run:

```powershell
python -m py_compile app.py generator.py references.py _resource.py pypandoc.py
node --check static\app.js
```

Then run a smoke test that checks:

- no asterisk character remains after `clean_public_manuscript()`
- duplicated `はじめに` and `おわりに` are collapsed
- `chapter.txt` and `reference.txt` render without a literal asterisk character

## Deployment

- Push to GitHub `origin/main`.
- Deploy Vercel production.
- After deployment, record the final commit hash, production URL, and Vercel inspect URL here.

## Cautions

- No live Gemini generation is required for syntax verification, but real output quality should be checked with an API key.
- PowerShell profile execution-policy warnings are expected in this environment and did not block prior checks.
