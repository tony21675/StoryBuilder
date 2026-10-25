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

New regression tests cover the one-call output and its Prompt Trace role. The last confirmed laptop baseline was **378 passed** before this experiment. GitHub's `test` and `Compile and unit tests` checks were still running on code commit `e46834e` when this checkpoint was written. Do not claim local verification yet.

## Current novel: The Long Way Home

Path: `~/Documents/MyNovel/The-Long-Way-Home`; repo: `tony21675/The-Long-Way-Home`.

Chapter 1, Scene 4 accepted prose is unchanged and its last proposed state update remains unapplied. Central situation: the primary oxygen scrubber manifold temperature is rising while emergency ventilation/reserve blower maintain pressure. Daniel estimates thermal runaway could become critical in about 24 hours if the current rate holds; this is a prediction, not a confirmed deadline. The silicate-like trace remains unverified and does not establish contamination or cause. Elena has ended monitoring-only work and is heading toward an inspection at the scrubber housing with Morgan and Priya; Daniel remains at the hub to monitor trends and offered to prepare diagnostic tools. Ryan and Zoe are independently investigating patterned communications bursts; no connection to life support is established.

The latest previous private trace is [prompt_trace.json](https://github.com/tony21675/StoryBuilder-Traces/blob/main/prompt_trace.json). It showed the three-pass version running successfully, but the evidence pass invented or distorted a few events. The new experiment avoids those separate event/knowledge/position updates in regular State Analysis rather than adding more event filters.

## Next action

1. Let StoryBuilder close and auto-sync, then verify the updated branch head on the laptop.
2. Run `python3 -m pytest -q` once. The laptop's last confirmed result before this experiment was 378 passed in 0.79s.
3. If the tests pass, open StoryBuilder and Analyze Accepted Scene for Chapter 1, Scene 4. Review the single plain-English main-plot change; don't use Advanced JSON and don't apply it until Tony chooses.
4. If it works, proceed with the novel. Do not start another State Analysis code-fix cycle for minor details.

## Standing collaboration rules

Use `python3`, never `python`, for Tony's Linux terminal. One terminal command at a time, no long paste blocks. Discuss app/novel changes before making them; handoff-only updates are okay. Preserve accepted prose and never apply a proposed state without explicit approval. StoryBuilder branch policy: ultimately only `main` after the redesign is merged; check before deleting branches. Novel repos: one branch per novel.
