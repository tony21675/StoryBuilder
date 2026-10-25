# StoryBuilder current checkpoint — October 25, 2026

## Writing principle

**The story is the novel. The state is only a memory aid.** Do not turn State Analysis into a transcript or a database of every detail. Zoe's shirt, breakfast, routine gestures, minor movements, and ordinary dialogue are not worth recording unless they materially affect the story. Preserve the main plot, its unresolved danger, meaningful discoveries/decisions, important stakes, and uncertainty. It is acceptable for a proposal to be imperfect. Do not add special-case filters for every individual model mistake.

Never prescribe the plot or a step-by-step sequence of what characters must do. The writer decides what happens next, including whether a prediction is right and whether a temporary fix is found. Do not hard-code any novel, character, genre, deadline, or repair idea into StoryBuilder.

## The one-pass main-plot experiment

Branch: `redesign/simplified-writing-workflow`, repo `tony21675/StoryBuilder`.

The regular Writer **Analyze Accepted Scene** path now calls State Analysis in main-plot-only mode:
- One model call reads the saved `current_situation` and the full accepted scene.
- It proposes only `current_situation`, a concise main-plot summary. The plain-English change review should show just that change.
- It does not propose updates to clue lists, unresolved questions, recent-events history, physical positions, locations, time, or character knowledge. Those existing fields are left untouched, not deleted.
- Estimates and hypotheses remain attributed/uncertain. A secondary thread is not retained merely because it appeared in the previous summary; it must materially affect the main plot.
- The separate saved-state recovery workflow still uses its detailed reconstruction path.
- Prompt Trace labels the regular pass `state_main_plot_summary`.

New regression tests cover the one-call output and its Prompt Trace role. GitHub's `test` and `Compile and unit tests` checks passed on code commit `e46834e`. The laptop's last confirmed baseline was **378 passed** before the main-plot experiment. GitHub's full tests and compile checks also passed for the duplicate-scene safeguard commit `81d04fe`; local tests must still be run after sync.

## Writer duplicate-scene bug: fix approved, implementation pending

The Scene 5 trace showed the completion reviewer falsely flagged a decision point as missing; recovery then generated a second complete scene and the app appended it to the first. The first Writer call produced 5,690 characters and ended with Elena's repair-versus-diagnostics question. The recovery call produced 5,693 characters and began a fresh version. The combined result was 11,385 characters. This was automatic recovery, not a second writing action by Tony.

Tony explicitly approved a generic fix: **never show both tellings of a scene**. Recovery may keep the original or replace it with a complete new draft, but must never append a second full scene. The existing `builder/scene_completion.py` source on the branch still has the old append behavior, so do not claim the fix is implemented or tested yet. At the stopping point, code/test edits have not been committed or pushed. Proposed direction: use a full-scene replacement when the planned-beat reviewer flags missing beats; accept that replacement only if follow-up validation and continuity/scope checks pass; otherwise preserve the original draft. Add regression tests for both outcomes. Do not add novel-specific rules.

No novel prose was accepted or edited. Chapter 1, Scene 5 remains unaccepted and the current Writer draft contains the duplicate. Do not accept it. Resume by implementing and testing the generic recovery fix, then push to the existing redesign branch.

## Current novel: The Long Way Home

Path: `~/Documents/MyNovel/The-Long-Way-Home`; repo: `tony21675/The-Long-Way-Home`.

Chapter 1, Scene 4 accepted prose is unchanged and its last proposed state update remains unapplied. Chapter 1, Scene 5 has been generated but is **not accepted** because the old recovery path joined two tellings of the scene. No scene was accepted and the saved scene pointer has not advanced because of this draft.

Central situation at the start of Scene 5: the primary oxygen scrubber manifold temperature is rising while emergency ventilation/reserve blower maintain pressure. Daniel estimates thermal runaway could become critical in about 24 hours if the current rate holds; this is a prediction, not a confirmed deadline. The silicate-like trace remains unverified and does not establish contamination or cause. Elena has ended monitoring-only work and is heading toward an inspection at the scrubber housing with Morgan and Priya; Daniel remains at the hub to monitor trends and offered to prepare diagnostic tools. Ryan and Zoe are independently investigating patterned communications bursts; no connection to life support is established.

The latest private trace is [prompt_trace.json](https://github.com/tony21675/StoryBuilder-Traces/blob/main/prompt_trace.json). It demonstrated both the noisy old State Analysis path and the exact duplicate-scene recovery failure. The main-plot-only State Analysis experiment avoids proposing separate event/knowledge/position updates in the regular workflow.

## Next action / freeze

1. **Freeze for tonight.** No code change has been made in this session. The duplicate-scene fix is approved but still needs implementation.
2. Resume by editing `builder/scene_completion.py` and `tests/test_scene_completion.py` on `redesign/simplified-writing-workflow`. Do not use an append/concatenate fallback. The replacement must pass both follow-up checks; if not, keep the first draft.
3. Push the code and regression tests, then verify GitHub checks. Only after that, close StoryBuilder normally on the laptop to sync, run `cd ~/Documents/StoryBuilder && python3 -m pytest -q`, and regenerate the unaccepted Scene 5 draft.
4. Do not accept Scene 5 or apply its old state proposal. Keep the main-plot-only State Analysis experiment as-is.

## Standing collaboration rules

Use `python3`, never `python`, for Tony's Linux terminal. One terminal command at a time, no long paste blocks. Discuss app/novel changes before making them; handoff-only updates are okay. Preserve accepted prose and never apply a proposed state without explicit approval. StoryBuilder branch policy: ultimately only `main` after the redesign is merged; check before deleting branches. Novel repos: one branch per novel.
