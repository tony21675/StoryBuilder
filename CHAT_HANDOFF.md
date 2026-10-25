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
- Hardware/model fit: the terminal prompt identifies the laptop as a **Surface Laptop 3**. `LONG_TERM_GOALS.md` records an **8 GB RAM laptop** running local Gemma 4 E4B GGUF through llama.cpp. Treat 8 GB as the current documented RAM limit unless a newer hardware inventory says otherwise. Don't casually recommend 14B models or ask the user to retype specs before checking repository notes. This handoff does not record a verified dedicated GPU/VRAM configuration.

## Current code experiment: main-plot-only State Analysis

The regular Writer **Analyze Accepted Scene** path now passes `main_plot_only=True` to `StateManager.propose`.

- It uses a single model call with only the saved `current_situation` and the full accepted scene as inputs.
- It proposes one field only: `current_situation`, as a concise main-plot continuity summary. The default human-readable change review should therefore display only this change.
- It does not update clues, unresolved questions, recent events, physical state, location, time, active objectives, or character knowledge. Existing values are left as-is, not deleted.
- The prompt says to retain the main danger and meaningful plot advances, attribute estimates/hypotheses, avoid preserving unrelated mysteries, and not invent actions or prescribe the next plot beat.
- The separate saved-state recovery feature still uses the legacy detailed reconstruction path.
- Prompt Trace classifies this as `state_main_plot_summary`.
- Added regression tests assert that main-plot mode makes one model call, returns only `current_situation`, skips the knowledge audit, leaves the source state unchanged, and uses its dedicated trace role.

The earlier laptop baseline was **378 passed in 0.79s**. After the October 25 validation-policy and test-assertion updates, the full local suite passed **381 tests in 0.61s** on the laptop at branch commit `5c2b961`. The main-plot-only State Analysis mode is covered by the passing suite; a post-update in-app behavior check is still needed.

## Writer recovery and validation redesign

- Code commit `81d04fe` changed missing-beat recovery from continuation-plus-append to a complete-scene replacement. There is no append path. The full suite passed **380 tests on the laptop before the current validation-policy changes**.
- The October 25, 2026 Scene 5 Prompt Trace showed the initial prose explicitly included Daniel's worsening critical-window prediction, but the semantic validator reported it missing. A full replacement then included Daniel's prediction and Elena's question about which path to pursue. The replacement validator first returned malformed checklist JSON; its correction then incorrectly claimed the decision point was missing. The separate continuity/scope audit marked all five categories clear. StoryBuilder preserved the initial draft rather than using the rejected replacement.
- Phase 1 implementation: when the continuity/scope audit is clear, missing-beat-only findings are advisory. Preserve the generated draft, show the reported concern, and do not trigger an automatic full-scene rewrite solely because coverage validation says an event is missing. Evidence-backed continuity conflicts can still trigger one bounded complete-scene replacement; use it only if both required follow-up checks pass, otherwise preserve the original.
- The semantic validator prompts now distinguish a decision point from a final decision: presenting alternatives and making clear a choice is due satisfies a decision-point endpoint unless the author explicitly requires a final choice.
- Manual app trial on October 25: Scene 5 returned the intended advisory coverage warning: the continuity/scope audit found no verified conflict, and the draft was preserved. However, StoryBuilder blocked acceptance and only allowed the focused change prompt. Root cause: `completion_notice_is_success()` in `builder/scene_completion.py` does not recognize the advisory notice as a review-complete outcome; `_finish_generated_scene()` in `storybuilder.py` consequently sets `writer_scene_accept_block_reason` and shows a blocking error. This is an app acceptance-gate bug, separate from the model's false-positive coverage finding. A targeted fix was discussed but **not approved or implemented**. Tomorrow, get approval before changing code. Proposed fix: allow author acceptance when the continuity/scope audit is clear and the only concern is advisory coverage, while keeping the warning visible and keeping verified conflicts or uncertain audits blocking. Add regression tests for the advisory and blocking paths.
- Scene 5's reviewer falsely claimed the crew had not reached a decision point even though Elena's final line is "We need to decide what moves first." The trial generated no automatic replacement. Treat this as a reviewer/model judgment problem; do not force a final decision just to satisfy the validator.
- Science/plot note from the prose shared October 25: Daniel's graph reports a rising temperature and conditional model-predicted deadline, Morgan feels vibration at the housing, and Zoe hypothesizes a self-generated telemetry loop. The crew has not independently verified whether the temperature reflects a real physical fault or sensor/software reporting error. Keep both explanations unresolved until the story naturally investigates them; no scene rewrite was authorized.
- Phase 2 is still planned: a separate source-backed science reviewer for consequential real-world technical claims. It has not been implemented.
- Chapter 1, Scene 5 remains unaccepted. Do not apply the old proposed ending-state update. The failed validation attempt did not advance the saved scene state.

## The Long Way Home

- Canonical local package: `~/Documents/MyNovel/The-Long-Way-Home`.
- GitHub: `tony21675/The-Long-Way-Home`.
- Premise: six-person Mars research outpost crew, all under 30, four women/two men, single/unmarried. Their life-support crisis is accidental, with no sabotage and no one to blame. Goal: survive until rescue from Earth or repair.
- Chapter 1, Scene 4 accepted prose remains unchanged; its last proposed state update was not applied. Chapter 1, Scene 5 remains **unaccepted**. The earlier duplicate-telling failure came from the old append recovery path, now replaced by bounded full-scene replacement. The latest test attempt preserved the original draft because the replacement follow-up check did not pass; the saved scene state did not advance. The current Phase 1 policy should make coverage-only findings advisory when the continuity/scope audit is clear. Verify that through a controlled Scene 5 trial; do not accept the draft or apply the old ending-state proposal during the test.
- Main plot at this point: primary oxygen scrubber manifold temperature continues to rise while emergency ventilation/reserve blower maintain acceptable pressure. Daniel estimates thermal runaway could become critical in about 24 hours if the current rate holds; that is a conditional prediction, not a verified countdown. The silicate-like trace remains unverified and establishes no contamination, entry route, or cause. Elena has ended monitoring-only work and is heading toward a scrubber-housing inspection with Morgan and Priya. Daniel remains at the hub to monitor temperature and offered to prepare diagnostic tools. Ryan and Zoe are separately examining patterned communications bursts; no connection to life support is established.
- Latest private trace: [StoryBuilder-Traces/prompt_trace.json](https://github.com/tony21675/StoryBuilder-Traces/blob/main/prompt_trace.json). It showed the older three-pass State Analysis generated some inaccurate event details, motivating main-plot-only mode. It also proved the Scene 5 duplicate was caused by automatic recovery: the first Writer call produced a complete scene ending with Elena's repair-versus-diagnostics question; the validator still flagged that decision point as missing, then a continuation call wrote another full version. The old code appended both drafts. Code commit `81d04fe` replaces that append behavior with a full-scene replacement that must pass both follow-up checks, otherwise the first draft remains. GitHub `test` and `Compile and unit tests` passed for that fix.
- The local regression suite is now green, but a manual in-app verification of the current workflow remains. Current immediate priority is the controlled Scene 5 validation trial below. Preserve the accepted Scene 4 prose and do not apply any proposed state change without explicit approval.

## Other novel context

**Taken_at_Dusk**: Chapter 3, Scene 3 snapshot was Saturday morning at Tony's home. Tiffany is in the van with the kidnapper; Maya is shaken at the table; Chloe is steadying Tony at the kitchen island; Beth, Jessica, and Rick are present. No operational plan is established yet. Chloe should be an unexpectedly steady “rock” for Tony; allow Maya's possible stress-slip “I love you” to happen naturally, never force it.

**LocalStoryChat fallback**: `~/Documents/LocalStoryChat`, GitHub `tony21675/LocalStoryChat`; Local Story Chat v7, Dolphin 3.0 Llama 3.1 8B Q4_K_M, llama-cli Vulkan, 10 GPU layers, `--simple-io`, default files under `~/StoryFiles/`.

A future separate app idea: an e-liquid flavor/recipe tracker with separate flavor profiles for Tony and his wife, conceptually similar to StoryBuilder. Do not mix that project into current StoryBuilder work.

## Immediate next steps

1. **Verified locally:** `python3 -m pytest -q` passed **381 tests in 0.61s** on October 25, 2026, after syncing branch commit `5c2b961`. The tests were run on the existing `redesign/simplified-writing-workflow` branch; no branch was created and no novel state was changed.
2. Next session: start with the acceptance-gate defect above. The user is tired and explicitly said to resume tomorrow. Do not ask them to repeat specs; use the documented 8 GB RAM note. Do not change code until they approve the targeted fix. No code or novel change was made after the 381-test run.
3. Once approved, narrow the acceptance classification so advisory-only coverage is non-blocking only when the continuity/scope audit is clear. Keep the warning visible. Add tests proving advisory cases can be accepted and verified conflicts/uncertain outcomes remain blocked. Run `python3 -m pytest -q`, then verify in-app.
4. Keep the duplicate-scene safeguard. Never join two complete scene drafts. Evidence-backed continuity conflicts may trigger a bounded full-scene replacement only when both follow-up checks pass; otherwise preserve the original. Preserve accepted prose and saved state unless the user explicitly chooses otherwise.
5. After the acceptance gate is fixed and verified, evaluate whether a separate science reviewer or stronger reviewer model provides enough benefit. First assess models that fit an 8 GB RAM laptop; do not jump straight to a 14B recommendation. Keep real-world science checks separate from novel-specific canon and avoid a huge fixed rule list.

**Milestone note:** The full local suite passed **381 tests in 0.61s** before the in-app trial. The trial confirmed that coverage-only findings no longer trigger a duplicate/replacement draft, but exposed the acceptance-gate mismatch described above. The scene remains unaccepted and saved novel state is unchanged. No app-code change has yet been approved or made for the acceptance gate.

