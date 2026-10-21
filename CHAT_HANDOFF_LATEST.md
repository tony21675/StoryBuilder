# Current StoryBuilder Handoff Checkpoint
Date: October 21, 2026

**Read this checkpoint first for the latest status.** It supplements the older `CHAT_HANDOFF.md`, which retains historical context and permanent collaboration rules.

## Audit complete

- Audit report: [APP_AUDIT_2026-10-21.md](APP_AUDIT_2026-10-21.md) (updated in commit `f772902fe29aaa6bad057c1d53d0c917db0141fa`)
- Code audited: `main` at `96b29b94775029e64eccee07dfd816e0dc96ffd9`
- Audit documentation commit: `f11a8987c8ed826124e486a3514f146465431103`
- Both CI workflows passed on the audited code commit: [checks](https://github.com/tony21675/StoryBuilder/actions/runs/39557373301), [tests](https://github.com/tony21675/StoryBuilder/actions/runs/39557373271).
- No application code or novel prose was changed by the audit.

## Current defect and next action

Focused Change has repeatedly failed to apply an edit because the model-generated `target_text` cannot be matched exactly in the full draft. Source review shows it asks the model to choose and copy the exact target itself. Whitespace flexibility exists, but punctuation and characters still must match. Its two attempts reuse one model conversation; attempt two repeats the full draft and includes the failed response. Focused revision also uses llama.cpp default temperature/top-k/top-p rather than task-specific sampling settings, a consistency risk but not a proven sole cause. Existing tests use short artificial text, not long real-scene prose.

**Do not retry prompt variations.** Next, agree on and implement a selection-aware patch path: the author highlights the exact passage; the app provides that exact selected source span to the model and asks for replacement text only; the app verifies the original selection still matches before replacing only that span. Reset the model context between attempts. Add tests for long prose, multi-paragraph selections, quote/punctuation variants, concurrent editor changes, retry resets, and unchanged surrounding text. No fuzzy target match that could silently edit the wrong passage.

## Other audit priorities

1. Improve visibility and effectiveness tests for Scene Contract coverage and the five-category continuity/scope audit. The last live scene overran its explicit endpoint despite the existing model-assisted review pipeline; exact reason is not yet known because the live audit output was not captured.
2. Later, consider splitting the ~418 KB `storybuilder.py` UI module incrementally.
3. Optional later cleanup: consolidate the two CI workflows into a Python 3.11/3.12 matrix; investigate the unexplained root `StoryBuilder` gitlink (mode 160000, no `.gitmodules` present); decide whether branch protection is appropriate for the main-only workflow.

## Safety and evidence boundaries

- Static source review and latest GitHub CI were inspected; this was not a local desktop/model run.
- Keep the app and novel as separate repositories. Do not change novel data during the repair.
- Resume by reading this file, then the audit report and older `CHAT_HANDOFF.md` for detailed workflow rules and historical context.
