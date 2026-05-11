# Handoff for Codex

## Project

- Path: `C:\Users\naoya\myproject\book_maker_app`
- Repository: `https://github.com/harry-n2/book-maker-app`
- Branch: `main`
- Production alias: `https://bookmakerapp.vercel.app`

## Latest Work

Updated public manuscript cleanup so generated books do not contain visible generation artifacts.

Current expected cleanup:

- Remove all asterisk characters.
- Remove OpenXML pagebreak tags.
- Remove unnecessary `第99章`.
- Remove AI, ChatGPT, Gemini, or similar generation-origin wording.
- Collapse duplicated `はじめに` and `おわりに`.
- Prevent repeated chapter headings when the chapter title repeats the chapter label or intro/outro label.

Prompt updates:

- `prompts/chapter.txt` and `prompts/reference.txt` avoid literal asterisk characters.
- The prompts instruct the model not to use the asterisk symbol.
- The prompts instruct the model not to output duplicate `はじめに` or `おわりに`.

Documentation updates:

- `README.md` was rewritten in readable Japanese.
- `FIRST_TIME_USER_MANUAL.md` was rewritten as a concise first-time user manual.
- Claude Code, Antigravity, and Codex handoff files were updated for the latest cleanup behavior.

## Files Touched

- `generator.py`
- `prompts/chapter.txt`
- `prompts/reference.txt`
- `README.md`
- `FIRST_TIME_USER_MANUAL.md`
- `_handoff_claude_code.md`
- `_handoff_antigravity.md`
- `_handoff_codex.md`

## Verification Required

```powershell
python -m py_compile app.py generator.py references.py _resource.py pypandoc.py
node --check static\app.js
```

Smoke tests should verify:

- `clean_public_manuscript()` removes asterisk characters.
- `clean_public_manuscript()` collapses duplicated `はじめに` and `おわりに`.
- `_load_prompt()` renders `chapter.txt` and `reference.txt` without a literal asterisk character.

## Existing Behavior To Preserve

- Per-author profile fields flow from UI to API to prompt rendering.
- Blank profile fields are optional and must not be forced into generated output.
- The system must not invent achievements, numbers, titles, case studies, or personal history absent from references or profile data.
- Reference material takes priority over generic assumptions.
- Vercel production uses the alias `https://bookmakerapp.vercel.app`.

## Deployment

- Pushed to `origin/main`.
- Final implementation commit: `f57ed0e fix: clean manuscript artifacts`
- Production alias: `https://bookmakerapp.vercel.app`
- Production deployment URL: `https://bookmaker-ctcpaz30k-harry-n2.vercel.app`
- Vercel inspect URL: `https://vercel.com/harry-n2/book_maker_app/8Ao6HP7cLPCaK6CVZNA4ozULgTtf`

## Notes

- Use this Vercel command to avoid the local PowerShell script execution policy issue:

```powershell
& 'C:\Users\naoya\AppData\Roaming\npm\vercel.cmd' --prod --yes
```

- PowerShell profile execution-policy warnings can be ignored if the requested command still runs.
