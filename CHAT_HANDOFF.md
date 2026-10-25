# StoryBuilder handoff — October 25, 2026

## Non-negotiable writing philosophy

**The story is the novel. The state is only a memory aid.** State Analysis should track the main plot only: the central unresolved problem/danger, the stakes and important deadlines, meaningful discoveries/decisions, and changes that materially affect what happens next. It is not an event transcript or a character database. Routine gestures, clothing, meals, minor movements, and ordinary dialogue should stay in the prose unless they become consequential.

Do not turn every model mistake into another filter, rule, or regression test. A harmless imperfection is preferable to an over-engineered writing workflow. The app must not prescribe a step-by-step plot, required beat sequence, repair solution, or character outcome. Keep uncertainty explicit; a prediction can be correct, wrong, or overtaken by a temporary workaround. No novel-specific facts belong in StoryBuilder code.

## Project and collaboration rules

- StoryBuilder local repo: `~/Documents/StoryBuilder`; GitHub: `tony21675/StoryBuilder`.
- Current branch: `redesign/simplified-writing-workflow`. End goal: only `main` after deliberate review/merge. Never delete branches blindly.
- Novel root is `~/Documents/MyNovel`. Each novel repo should have one branch per novel after checking before branch deletion.
- Always use `python3`, never `python`, on Tony's Linux laptop.
- Give one terminal command at a time; avoid long copy/paste blocks. StoryBuilder auto-syncs on close.
- Discuss app/novel code or canon changes before making them. Handoff-only updates do not need permission.
- Preserve accepted prose. Never apply a State Analysis proposal without the user's explicit choice.

## Current code experiment: main-plot-only State Analysis

The regular Writer **Analyze Accepted Scene** path now passes `main_plot_only=True` to `StateManager.propose`.

- It uses a single model call with only the saved `current_situation` and the full accepted scene as inputs.
- It proposes one field only: `current_situation`, as a concise main-plot continuity summary. The default human-readable change review should therefore display only this change.
- It does not update clues, unresolved questions, recent events, physical state, location, time, active objectives, or character knowledge. Existing values are left as-is, not deleted.
- The prompt says to retain the main danger and meaningful plot advances, attribute estimates/hypotheses, avoid preserving unrelated mysteries, and not invent actions or prescribe the next plot beat.
- The separate saved-state recovery feature still uses the legacy detailed reconstruction path.
- Prompt Trace classifies this as `state_main_plot_summary`.
- Added regression tests assert that main-plot mode makes one model call, returns only `current_situation`, skips the knowledge audit, leaves the source state unchanged, and uses its dedicated trace role.

The previous verified laptop baseline was **378 passed in 0.79s**, before this experiment. GitHub check-runs `test` and `Compile and unit tests` both passed on code commit `e46834e`. The laptop has not yet run the new mode's test suite. Run the local tests after sync before using it in the app.

## Writer recovery and validation redesign

- Code commit `81d04fe` changed missing-beat recovery from continuation-plus-append to a complete-scene replacement. There is no append path. The full suite passed **380 tests on the laptop before the current validation-policy changes**.
- The October 25, 2026 Scene 5 Prompt Trace showed the initial prose explicitly included Daniel's worsening critical-window prediction, but the semantic validator reported it missing. A full replacement then included Daniel's prediction and Elena's question about which path to pursue. The replacement validator first returned malformed checklist JSON; its correction then incorrectly claimed the decision point was missing. The separate continuity/scope audit marked all five categories clear. StoryBuilder preserved the initial draft rather than using the rejected replacement.
- Phase 1 implementation: when the continuity/scope audit is clear, missing-beat-only findings are advisory. Preserve the generated draft, show the reported concern, and do not trigger an automatic full-scene rewrite solely because coverage validation says an event is missing. Evidence-backed continuity conflicts can still trigger one bounded complete-scene replacement; use it only if both required follow-up checks pass, otherwise preserve the original.
- The semantic validator prompts now distinguish a decision point from a final decision: presenting alternatives and making clear a choice is due satisfies a decision-point endpoint unless the author explicitly requires a final choice.
- Phase 2 is still planned: a separate source-backed science reviewer for consequential real-world technical claims. It has not been implemented.
- Chapter 1, Scene 5 remains unaccepted. Do not apply the old proposed ending-state update. The failed validation attempt did not advance the saved scene state.

## The Long Way Home

- Canonical local package: `~/Documents/MyNovel/The-Long-Way-Home`.
- GitHub: `tony21675/The-Long-Way-Home`.
- Premise: six-person Mars research outpost crew, all under 30, four women/two men, single/unmarried. Their life-support crisis is accidental, with no sabotage and no one to blame. Goal: survive until rescue from Earth or repair.
- Chapter 1, Scene 4 accepted prose remains unchanged; its last proposed state update was not applied. Chapter 1, Scene 5 was generated but is **not accepted** because the old automatic continuation path joined two complete tellings. The manuscript and saved scene state have not been advanced by accepting it. After syncing and testing the fix, regenerate Scene 5 and check for a single complete draft; do not accept the existing duplicate.
- Main plot at this point: primary oxygen scrubber manifold temperature continues to rise while emergency ventilation/reserve blower maintain acceptable pressure. Daniel estimates thermal runaway could become critical in about 24 hours if the current rate holds; that is a conditional prediction, not a verified countdown. The silicate-like trace remains unverified and establishes no contamination, entry route, or cause. Elena has ended monitoring-only work and is heading toward a scrubber-housing inspection with Morgan and Priya. Daniel remains at the hub to monitor temperature and offered to prepare diagnostic tools. Ryan and Zoe are separately examining patterned communications bursts; no connection to life support is established.
- Latest private trace: [StoryBuilder-Traces/prompt_trace.json](https://github.com/tony21675/StoryBuilder-Traces/blob/main/prompt_trace.json). It showed the older three-pass State Analysis generated some inaccurate event details, motivating main-plot-only mode. It also proved the Scene 5 duplicate was caused by automatic recovery: the first Writer call produced a complete scene ending with Elena's repair-versus-diagnostics question; the validator still flagged that decision point as missing, then a continuation call wrote another full version. The old code appended both drafts. Code commit `81d04fe` replaces that append behavior with a full-scene replacement that must pass both follow-up checks, otherwise the first draft remains. GitHub `test` and `Compile and unit tests` passed for that fix.
- Next: after sync and tests, re-analyze accepted Scene 4. If the output is one sensible main-plot summary, review and approve it using the plain-English change view. Do not use Advanced JSON unless an actual correction requires it.

## Other novel context

**Taken_at_Dusk**: Chapter 3, Scene 3 snapshot was Saturday morning at Tony's home. Tiffany is in the van with the kidnapper; Maya is shaken at the table; Chloe is steadying Tony at the kitchen island; Beth, Jessica, and Rick are present. No operational plan is established yet. Chloe should be an unexpectedly steady “rock” for Tony; allow Maya's possible stress-slip “I love you” to happen naturally, never force it.

**LocalStoryChat fallback**: `~/Documents/LocalStoryChat`, GitHub `tony21675/LocalStoryChat`; Local Story Chat v7, Dolphin 3.0 Llama 3.1 8B Q4_K_M, llama-cli Vulkan, 10 GPU layers, `--simple-io`, default files under `~/StoryFiles/`.

A future separate app idea: an e-liquid flavor/recipe tracker with separate flavor profiles for Tony and his wife, conceptually similar to StoryBuilder. Do not mix that project into current StoryBuilder work.

## Immediate next steps

1. Sync the current `redesign/simplified-writing-workflow` branch on the laptop and run `cd ~/Documents/StoryBuilder && python3 -m pytest -q`. The 380-passed result predates the current changes and is not verification of this implementation.
2. If local tests pass, reopen StoryBuilder and review the preserved, unaccepted Scene 5 draft. Do not accept it or apply the old state proposal until it has been reviewed. A later trial should confirm that a coverage-only warning no longer triggers a replacement rewrite.
3. Keep the duplicate-scene safeguard. Never join two complete scene drafts. Preserve accepted prose and saved state unless Tony explicitly chooses otherwise.
4. After the Phase 1 behavior is verified, design and test the separate source-backed science reviewer. Do not mix real-world science rules into novel-specific canon or add a large fixed rule list.

**Milestone note:** Phase 1 code and regression tests are committed on the existing redesign branch. The earlier 380-passed laptop result predates these edits; the updated suite has not yet been run locally or verified by a recorded CI check. Do not claim the new tests passed until verification is complete.

