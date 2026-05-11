# Handoff for Claude Code

## Scope

- Project: `C:\Users\naoya\myproject\book_maker_app`
- Branch: `main`
- Production alias: `https://bookmakerapp.vercel.app`
- Current task: prevent public manuscripts from exposing generation artifacts, then push and deploy.

## Latest Change

- `generator.py` now removes all asterisk characters from public manuscript text through `clean_public_manuscript()`.
- `generator.py` now normalizes duplicate intro and outro headings such as `はじめに はじめに` and `おわりに おわりに`.
- Chapter title cleanup now avoids duplicating the chapter label, `はじめに`, or `おわりに` when the model repeats it in the title field.
- `prompts/chapter.txt` and `prompts/reference.txt` no longer contain a literal asterisk character and instruct the model not to use the asterisk symbol.
- README and first-time user manual were rewritten with readable Japanese and the current output-cleanup behavior.

## Existing Important Behavior

- The app supports per-author profile fields from UI to API to prompt rendering.
- Empty profile fields must not be forced into generated output.
- The model must not invent achievements, numbers, titles, case studies, or personal history absent from the profile or references.
- Reference material and explicit user input take priority over generic assumptions.
- Public output cleanup removes:
  - asterisk characters
  - OpenXML pagebreak tags
  - unnecessary `第99章`
  - AI, ChatGPT, Gemini, or similar generation-origin wording
  - duplicated intro and outro headings

## Files Updated

- `generator.py`
- `prompts/chapter.txt`
- `prompts/reference.txt`
- `README.md`
- `FIRST_TIME_USER_MANUAL.md`
- `_handoff_claude_code.md`
- `_handoff_antigravity.md`
- `_handoff_codex.md`

## Verification

Run before handing off:

```powershell
python -m py_compile app.py generator.py references.py _resource.py pypandoc.py
node --check static\app.js
```

Also verify:

- `clean_public_manuscript()` removes asterisk characters.
- `clean_public_manuscript()` removes duplicated `はじめに` and `おわりに`.
- `_load_prompt()` can render `chapter.txt` and `reference.txt` without a literal asterisk character.

## Deployment

- Pushed to `origin/main`.
- Final implementation commit: `f57ed0e fix: clean manuscript artifacts`
- Production alias: `https://bookmakerapp.vercel.app`
- Production deployment URL: `https://bookmaker-ctcpaz30k-harry-n2.vercel.app`
- Vercel inspect URL: `https://vercel.com/harry-n2/book_maker_app/8Ao6HP7cLPCaK6CVZNA4ozULgTtf`

## Notes

- PowerShell profile execution-policy warnings may appear and can be ignored if commands continue.
- The local Vercel command that avoids the blocked `vercel.ps1` execution policy is:

```powershell
& 'C:\Users\naoya\AppData\Roaming\npm\vercel.cmd' --prod --yes
```
