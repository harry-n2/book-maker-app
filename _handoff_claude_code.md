# Handoff for Claude Code

## Scope
- Project: `C:\Users\naoya\myproject\book_maker_app`
- Goal completed: per-author profile settings are now passed from UI to API to prompt generation, and prompts were cleaned so only practical, input-grounded content is produced.

## Implemented
- Added author profile inputs in `templates/index.html`:
  - display author name
  - author background / achievements
  - tone / writing style
  - target keywords / reader traits
  - optional failure examples
  - optional voice types
- Wired these fields through `static/app.js`:
  - submit payload
  - local project save/load
  - new project reset
- Wired these fields through `app.py`:
  - `/generate-titles` form parameters
  - `BookConfig` creation
  - `JOB_STATE["cfg"]`
  - `_cfg_from_state()` restoration for regeneration and writing steps
- Updated `generator.py`:
  - added `_clean_profile_kwargs()` and routed prompt rendering through it
  - disabled strict validation that forced `voice_type` / `failure_bank` matching
  - default chapter `voice_type` no longer forces a fixed type
- Replaced prompt files in `prompts/` with practical, source-grounded instructions:
  - `titles.txt`
  - `titles_bestseller.txt`
  - `system.txt`
  - `structure.txt`
  - `structure_bestseller.txt`
  - `structure_modify.txt`
  - `chapter.txt`
  - `reference.txt`
  - `promotion.txt`
  - `description.txt`
  - `outline.txt`
- Hid nonessential `voice_type` / `failure_bank` badges in `static/style.css` to improve structure-review visibility.

## Key Behavior
- Profile fields are optional.
- Empty profile fields are not forced into output.
- `voice_type` and `failure_bank` are optional and should only be used when practical and grounded in the profile.
- Prompts explicitly prohibit inventing achievements, numbers, titles, case studies, or personal history not present in the profile or references.
- Reference material takes priority over generic assumptions.

## Verification
- Ran Python compile check:
  - `python -m py_compile app.py generator.py references.py _resource.py`
- Ran JS syntax check:
  - `node --check static\app.js`
- Ran prompt formatting smoke test for all prompt files via `_load_prompt()` with dummy data.

## Notes
- PowerShell profile execution policy warnings appeared in command output but did not block checks.
- `git status` may fail under sandbox user due dubious ownership unless `safe.directory` is configured.

## GitHub / Vercel Deployment
- Pushed to `origin/main`.
- Latest deployment alias: `https://bookmakerapp.vercel.app`
- Production deployment URL: `https://bookmaker-b1f6jxddu-harry-n2.vercel.app`
- Vercel inspect URL: `https://vercel.com/harry-n2/book_maker_app/GKGtP44XHz1SPE8KkRQda2GtGKJk`

## Deployment Fixes
- Added local `pypandoc.py` shim and moved `pypandoc-binary` out of production requirements to avoid Vercel Python bundle size failure.
- Added `.vercelignore` to exclude local build artifacts:
  - `build/`
  - `dist/`
  - `jobs/`
  - `__pycache__/`
- First deploy attempts failed at 607.78 MB and then 257.69 MB bundle sizes. Final deploy succeeded after dependency and artifact exclusions.
