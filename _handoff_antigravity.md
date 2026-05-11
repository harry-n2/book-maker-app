# Handoff for Antigravity

## Project

- Path: `C:\Users\naoya\myproject\book_maker_app`
- Repository: `https://github.com/harry-n2/book-maker-app`
- Branch: `main`
- Production alias: `https://bookmakerapp.vercel.app`

## Current Required Behavior

- The final merged manuscript must always place `## 目次` directly under `# はじめに`.
- The TOC is deterministic and generated from `structure.json`.
- Pandoc automatic TOC generation is disabled because it places the TOC outside the required intro position.
- The intro heading is forced to `# はじめに`.
- The outro heading is forced to `# おわりに`.
- Main chapter headings are forced from the approved chapter order and title.
- The expand/collapse partial-edit panel has been removed from the structure review UI.

## Files Changed

- `generator.py`
- `templates/index.html`
- `static/app.js`
- `static/style.css`
- `_handoff_claude_code.md`
- `_handoff_antigravity.md`
- `_handoff_codex.md`

## Verification

Run:

```powershell
python -m py_compile app.py generator.py references.py _resource.py pypandoc.py
node --check static\app.js
```

Check manually or with search:

- `book_full.md` contains `# はじめに`, then `## 目次` immediately below it.
- The TOC includes intro, each chapter, outro, and promotion.
- No UI references remain for `open-modify-btn`, `modify-panel`, `modifyInstruction`, `cancelModifyBtn`, `submitModifyBtn`, or `openModifyBtn`.

## Important

Do not reintroduce TOC removal or automatic relocation. The user explicitly requires the TOC directly under `はじめに`.
