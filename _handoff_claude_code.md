# Handoff for Claude Code

## Project

- Path: `C:\Users\naoya\myproject\book_maker_app`
- Repository: `https://github.com/harry-n2/book-maker-app`
- Branch: `main`
- Production alias: `https://bookmakerapp.vercel.app`

## Strict Rules

- Word形式の目次を使う。Markdown手動目次は禁止。
- `book_full.md` に `## 目次` を挿入しない。
- `convert_to_docx()` の `--toc --toc-depth=3` を削除しない。
- 目次は `はじめに` 本文の文末直後、次章見出しの前に置く。
- Pandocが生成したWord TOCフィールドの `w:sdt` ブロックがある場合は、それを移動するだけにする。
- Pandocが無くローカルフォールバックでTOCが無い場合だけ、DOCX XMLに同等のWord TOCフィールドを補完する。Markdown目次は禁止。
- `apply_period_breaks()` の見出し直後空行は維持する。
- 展開折り畳み式の部分修正UIは再追加しない。

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

## Latest Deployment

- Implementation commit: `336d193 fix: keep word toc after introduction`
- Production deployment URL: `https://bookmaker-ecmw79byx-harry-n2.vercel.app`
- Vercel inspect URL: `https://vercel.com/harry-n2/book_maker_app/96QurVkTG6wbxKrp292qw34xbo3U`
- Production alias: `https://bookmakerapp.vercel.app`
