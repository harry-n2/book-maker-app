# Handoff for Claude Code

## Project

- Path: `C:\Users\naoya\myproject\book_maker_app`
- Repository: `https://github.com/harry-n2/book-maker-app`
- Branch: `main`
- Production alias: `https://bookmakerapp.vercel.app`

## Strict Rules

- Markdown keeps normal heading spacing only. Do not emit any visible page-start marker.
- DOCX must use custom paragraph styles: `BookTitle`, `BookTOCHeading`, `BookHeading1`, `BookHeading2`, and `BookHeading3`.
- Do not use built-in Word heading style IDs in the final document paragraphs.
- Do not use `pageBreakBefore` for these heading styles. That creates the excess whitespace seen in the current output.
- Keep `w:outlineLvl` removed from the generated custom heading styles.
- Keep the Word TOC on style mapping: `TOC \h \z \t "BookHeading1,1,BookHeading2,2,BookHeading3,3"`.
- Keep the heading collapse controls removed from the generated Word file.

## Implementation Notes

- `generator.py` contains `move_word_toc_after_intro(docx_path)`.
- The function extracts the DOCX, parses `word/document.xml`, finds the TOC block via `w:instrText` containing `TOC`, removes it from its original position, and inserts it after the intro section.
- `_make_word_toc_sdt()` is fallback-only for environments without a system Pandoc.
- `reference_v8.docx` / `reference_v7.docx` selection remains unchanged.

## Verify

```powershell
python -m py_compile app.py generator.py references.py _resource.py pypandoc.py
node --check static\app.js
```

Also verify the DOCX XML order:

- `Heading1` containing `はじめに`
- intro body paragraphs
- Word TOC `w:sdt`
- next `Heading1`

Do not revert this back to a manual Markdown TOC.

## Heading Spacing Rule

- Preserve heading-after spacing in both Markdown and DOCX.
- `build_merged_md()` must run `ensure_markdown_heading_spacing()` after `clean_public_manuscript()` so every Markdown H1-H3 line has a blank line immediately after it.
- Do not create a manual Markdown TOC while doing this. The Markdown file still must not contain a manual `## TOC` / `## 目次` block.
- `move_word_toc_after_intro()` must run `apply_heading_after_spacing()` before writing `word/document.xml`.
- DOCX `Title`, `TOCHeading`, `Heading1`, `Heading2`, and `Heading3` paragraphs must keep direct `w:spacing w:after="80"`.
- This covers the title, intro heading, Word TOC heading, H1, H2, H3, and outro heading. Do not remove or weaken this rule.

## Heading Page Start Rule

- Preserve page-start behavior in both Markdown and DOCX.
- Do not emit any visible page-start marker into Markdown.
- Markdown keeps only the normal heading spacing; page-start control happens in DOCX.
- `move_word_toc_after_intro()` must run `apply_heading_page_starts()` before writing `word/document.xml`.
- DOCX `Title`, `TOCHeading`, `Heading1`, `Heading2`, and `Heading3` paragraphs must keep `w:pageBreakBefore`.
- Do not restore the old before-heading or after-heading page-break paragraph behavior.
- The partial-edit UI and `/modify-structure` API are prohibited. Keep `modify_structure()`, `structure_modify_count`, and `modifying_structure` out of the codebase.

## Latest Deployment

- Implementation commit: `3ae3eda fix: preserve heading page breaks`
- Production deployment URL: `https://bookmaker-krczurzus-harry-n2.vercel.app`
- Vercel inspect URL: `https://vercel.com/harry-n2/book_maker_app/5syj2xf2eLqjyAsQHGsaVfuXyE4N`
- Production alias: `https://bookmakerapp.vercel.app`
