# Handoff for Antigravity

## Project
`C:\Users\naoya\myproject\book_maker_app`

## What changed
The app now supports different book-publishing clients/authors by collecting and passing a per-author profile through the full generation flow. Prompts were also cleaned to avoid forced placement of tone, backstory, achievements, voice types, and failure stories.

## Files changed
- `templates/index.html`
  - Added "出版希望者プロフィール" form block.
- `static/app.js`
  - Sends profile fields to `/generate-titles`.
  - Saves/loads profile fields in local project data.
  - Clears profile fields on new project.
- `app.py`
  - Accepts profile form fields.
  - Stores them in `BookConfig` and `JOB_STATE`.
  - Restores them for title regeneration, structure generation, structure modification, and writing.
- `generator.py`
  - Adds clean prompt variable mapping via `_clean_profile_kwargs()`.
  - Stops strict validation from forcing `voice_type` / `failure_bank`.
  - Removes fixed default chapter voice type.
- `static/style.css`
  - Hides structure meta badges that were reducing visibility.
- `prompts/*.txt`
  - Rewritten around practical, input-grounded generation.

## Expected behavior
- If a new publisher/author uses the app, they can set their own tone, background, achievements, target reader, keywords, and optional examples.
- If those fields are blank, the model must not invent them or force them into the manuscript.
- Failure stories and voice types are optional, not required structure decorations.
- Outputs should be based on:
  - uploaded/read references
  - theme
  - target reader
  - author profile
- Public-facing manuscript output should not contain internal generation artifacts such as `*`, OpenXML pagebreak tags, `第99章`, or AI/ChatGPT/Gemini-origin wording.

## Verification already run
```powershell
python -m py_compile app.py generator.py references.py _resource.py
node --check static\app.js
```

Prompt formatting was also smoke-tested through `_load_prompt()` for:
`titles.txt`, `titles_bestseller.txt`, `system.txt`, `structure.txt`, `structure_bestseller.txt`, `structure_modify.txt`, `chapter.txt`, `reference.txt`, `promotion.txt`, `description.txt`, `outline.txt`.

## Remaining cautions
- No live Gemini generation was run, so model output quality should still be checked with a real API key.
- Existing UI text outside the newly added profile block still contains old mojibake text from prior work; this task focused on profile behavior, prompt discipline, and visibility issues.

## GitHub / Vercel
- Pushed to GitHub `origin/main`.
- Production alias: `https://bookmakerapp.vercel.app`
- Deployment URL: `https://bookmaker-b1f6jxddu-harry-n2.vercel.app`
- Inspect: `https://vercel.com/harry-n2/book_maker_app/GKGtP44XHz1SPE8KkRQda2GtGKJk`

## Vercel Build Notes
- Vercel failed twice due Python function bundle limits:
  - 607.78 MB before removing `pypandoc-binary`
  - 257.69 MB before excluding local artifacts
- Fixes added:
  - `pypandoc.py` local shim using system Pandoc when available, otherwise `python-docx` fallback
  - `requirements.txt` no longer installs `pypandoc-binary` in production
  - `.vercelignore` excludes `build/`, `dist/`, `jobs/`, cache files, and local handoff/build artifacts

## Latest Output Cleanup Change
- `generator.py` added final cleanup through `clean_public_manuscript()`.
- `chapter.txt` and `reference.txt` prompts now forbid:
  - `*` bullet markers
  - `<w:p><w:r><w:br w:type="page"/></w:r></w:p>`
  - `第99章`
  - AI/ChatGPT/Gemini-origin wording
- README and `FIRST_TIME_USER_MANUAL.md` were updated for first-time users.
