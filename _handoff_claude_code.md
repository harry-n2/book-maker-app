# Handoff for Claude Code

## Project

- Path: `C:\Users\naoya\myproject\book_maker_app`
- Repository: `https://github.com/harry-n2/book-maker-app`
- Branch: `main`
- Production alias: `https://bookmakerapp.vercel.app`

## Latest Change

The generated book must always contain a table of contents directly under `はじめに`.

Implementation details:

- `generator.py` now builds a manual TOC from `structure.json`.
- The TOC is inserted immediately after the first intro H1.
- Intro/outro H1s are normalized to `# はじめに` and `# おわりに`.
- Main chapter H1s are normalized from the approved chapter structure.
- Pandoc `--toc` was removed to prevent the TOC from appearing before the intro.

UI correction:

- The expand/collapse-style partial-edit panel was removed.
- `templates/index.html` no longer includes the modify panel controls.
- `static/app.js` no longer binds modify-panel open/cancel/submit handlers.
- `static/style.css` no longer includes modify-panel styling.

## Preserve

- Manual TOC directly under `はじめに`.
- Existing manuscript artifact cleanup.
- Per-author profile fields from UI to API to prompt rendering.
- Optional blank profile fields.
- Reference material priority over generic assumptions.

## Verify

```powershell
python -m py_compile app.py generator.py references.py _resource.py pypandoc.py
node --check static\app.js
```

Also verify:

- `## 目次` appears immediately under `# はじめに` in a merged manuscript.
- No `open-modify-btn`, `modify-panel`, `modifyInstruction`, `cancelModifyBtn`, `submitModifyBtn`, or `openModifyBtn` UI references remain.

## Caution

Do not remove the TOC again. The TOC placement under `はじめに` is mandatory.
