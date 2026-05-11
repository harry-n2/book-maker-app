# Handoff for Codex

## Project
- Path: `C:\Users\naoya\myproject\book_maker_app`
- Repository: `https://github.com/harry-n2/book-maker-app`
- Branch: `main`
- Vercel app: `https://bookmakerapp.vercel.app`

## Latest Work
Implemented per-author profile handling and prompt cleanup for Book Maker App.

### Behavior now expected
- Each book publishing client can set their own:
  - author display name
  - background / achievements
  - tone / writing style
  - reader keywords
  - optional failure examples
  - optional voice types
- These values flow through:
  - `templates/index.html`
  - `static/app.js`
  - `app.py`
  - `BookConfig`
  - `prompts/*.txt`
- Blank optional fields must not be forced into output.
- `voice_type` and `failure_bank` are optional only.
- Prompts instruct the model not to invent achievements, numbers, titles, case studies, or personal history not present in references/profile.
- Latest output cleanup removes public-facing artifacts:
  - leading `*` / `-` list markers
  - OpenXML pagebreak tags
  - `第99章`
  - AI/ChatGPT/Gemini-origin wording

## Files touched in this pass
- `templates/index.html`
  - Added "出版希望者プロフィール" input block.
- `static/app.js`
  - Added payload fields, project save/load, and reset handling for profile data.
- `app.py`
  - Added form parameters and state restore for profile data.
- `generator.py`
  - Added `_clean_profile_kwargs()`.
  - Routed prompt formatting through clean profile defaults.
  - Disabled strict `voice_type` / `failure_bank` validation.
  - Removed forced default chapter voice type.
- `static/style.css`
  - Hid low-value structure meta badges for readability.
- `prompts/`
  - Rewrote practical, source-grounded prompts.
- `_handoff_claude_code.md`
- `_handoff_antigravity.md`
- `_handoff_codex.md`

## Verification already run
```powershell
python -m py_compile app.py generator.py references.py _resource.py
node --check static\app.js
```

Prompt formatting smoke test was also run for all prompt files through `_load_prompt()`.

## Git / Deploy
The user requested push to GitHub and Vercel production deployment.

- Pushed to `origin/main`.
- Production alias: `https://bookmakerapp.vercel.app`
- Deployment URL: `https://bookmaker-b1f6jxddu-harry-n2.vercel.app`
- Inspect URL: `https://vercel.com/harry-n2/book_maker_app/GKGtP44XHz1SPE8KkRQda2GtGKJk`

Recent deployment-related commits:
- `6855cca feat: support per-author book profiles`
- `dc6fef0 fix: reduce Vercel Python bundle size`
- `bdb20df chore: exclude local artifacts from Vercel`

Check latest commit and deployment status before continuing:

```powershell
git -C "C:\Users\naoya\myproject\book_maker_app" log --oneline -5
vercel ls
```

## Known Cautions
- PowerShell profile execution-policy warnings appear in command output but did not block checks.
- The sandbox user required:
  `git config --global --add safe.directory C:/Users/naoya/myproject/book_maker_app`
- Existing UI text still contains older mojibake in several labels. The newest profile block and prompt behavior are the relevant functional changes from this pass.
- Live Gemini generation was not run during the implementation pass.
- Vercel production build required two fixes:
  - remove `pypandoc-binary` from production requirements and use local `pypandoc.py` shim
  - add `.vercelignore` for `build/`, `dist/`, `jobs/`, caches, and local artifacts
- After the latest cleanup pass, verify generated Markdown no longer contains `<w:p><w:r><w:br w:type="page"/></w:r></w:p>`, `第99章`, or obvious generation-origin wording.

## Latest Docs
- `README.md` was rewritten for current app behavior.
- `FIRST_TIME_USER_MANUAL.md` was added for first-time users.
