# StoryBuilder current checkpoint — October 25, 2026

This file was refreshed after the Scene 5 in-app trial. For the full project context, use **[CHAT_HANDOFF.md](CHAT_HANDOFF.md)**. The older copy of this checkpoint had stale statements about the duplicate-scene fix and must not be used as current status.

## Current verified status

- Repo: `tony21675/StoryBuilder`; local path: `~/Documents/StoryBuilder`.
- Current branch: `redesign/simplified-writing-workflow`. Do not create or delete branches casually. The eventual goal remains a deliberate merge into `main`.
- Laptop shown in terminal prompt: **Surface Laptop 3**. `LONG_TERM_GOALS.md` documents an **8 GB RAM laptop** running Gemma 4 E4B GGUF via llama.cpp for StoryBuilder writing. Do not recommend a 14B model without checking memory feasibility; do not ask the user to repeat the specs before looking in project notes. Dedicated GPU/VRAM details are not verified in this handoff.
- Always use `python3`, one terminal command at a time. Handoff-only edits do not require permission; app or novel changes do.
- Full local suite passed: **381 passed in 0.61s**, on October 25, 2026, after the validation-policy and test assertion updates.
- No app-code change was made after that test run. The latest in-app trial exposed a separate acceptance-gate defect.

## Scene 5 trial result

The unaccepted Chapter 1 Scene 5 draft for *The Long Way Home* was generated. The completion check returned:

> The scene-coverage review flagged possible omission(s), but the continuity/scope audit found no verified conflict. Coverage findings are advisory; the original draft was preserved for author review.

This is partly the intended behavior: the draft was preserved and no full replacement / duplicate scene was generated. However, the UI blocked acceptance and only allowed the focused change prompt.

### Root cause located, not yet fixed

- `completion_notice_is_success()` in `builder/scene_completion.py` does not classify the advisory notice as a completed review outcome.
- `_finish_generated_scene()` in `storybuilder.py` therefore sets `writer_scene_accept_block_reason` and presents a blocking error dialog.
- This is an **app acceptance-gate bug**, separate from the local model's false-positive coverage finding.
- The proposed code change was discussed but the user did **not** approve it yet. Ask before changing code. Suggested narrow direction: allow acceptance when the continuity/scope audit is clear and only coverage findings are advisory; retain the visible warning; keep verified conflicts and uncertain audits blocked. Add regression tests for both advisory and blocking cases.

## Model/review finding

The coverage reviewer claimed the final decision point was missing even though Elena's final line explicitly says, “We need to decide what moves first.” The scene presents the alternatives and makes clear a choice is due; it need not make the final decision yet. This is a reviewer/model judgment limitation, not evidence the prose lacks a decision point. Do not force a final repair-versus-software choice just to satisfy the validator.

## Science/continuity note from the supplied prose

Daniel's graph reports rising temperature and a conditional model-predicted deadline. Morgan feels vibration at the housing. Zoe hypothesizes a self-generated telemetry loop. The crew has not yet independently verified whether the temperature reflects a real physical fault or a sensor/software reporting error. Keep the competing explanations unresolved until the story naturally investigates them. No rewrite was authorized tonight.

## Next session

1. Start with the acceptance-gate defect. The user is frustrated and said to resume tomorrow. Do not make code changes until they approve.
2. Keep the advisory warning visible but non-blocking only when the continuity/scope audit is clear. Uncertain audits and verified conflicts must retain safeguards.
3. Run `python3 -m pytest -q`, then verify the acceptance path in the app before declaring the behavior fixed.
4. Preserve Scene 5 as unaccepted until the user decides. Do not apply the old proposed ending-state update. Saved novel state has not advanced.
5. Before discussing a larger reviewer model, use the documented 8 GB RAM constraint to evaluate viable sizes/options. Fix the app gate first; don't imply a bigger model can repair app logic.

## Writing and project principles

**The story is the novel. The state is only a memory aid.** Keep State Analysis focused on the central unresolved danger, stakes, meaningful discoveries/decisions, and changes affecting what happens next. Avoid transcript-like state and special-case rules for every model mistake. Do not prescribe plot outcomes or hard-code novel-specific facts in StoryBuilder. Preserve accepted prose and never apply a proposed state without explicit user approval.
