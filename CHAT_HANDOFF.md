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

## Writer duplicate-scene bug: approved fix pending implementation

- Trace root cause: the completion reviewer said the decision point was missing even though the first draft ended with Elena's repair-versus-diagnostics question. Recovery told the model to continue, but it wrote a second complete scene. StoryBuilder appended both and did not re-run the planned-beat validator on the combined result.
- Tony approved a generic safeguard: keep one scene only, never both. The code fetched from the current branch still contains the old continuation-and-append path. The fix has **not** been implemented, committed, or tested yet; don't rely on older or inaccurate handoff wording that says otherwise.
- Resume with a complete-scene replacement, not a continuation. Use the replacement only if the scene-contract validator and continuity/scope audit both pass; otherwise preserve the original. Add regression tests for successful replacement and for preserving the original when the replacement fails. No novel-specific rules.
- Scene 5 remains unaccepted. No accepted manuscript or novel state was changed.

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

## Immediate next steps / freeze

1. Freeze for tonight. The duplicate-scene fix has been approved but is not implemented yet; the branch still contains the old append path.
2. Next session, implement a full-scene replacement recovery path and regression tests. Keep the original if the replacement fails validation; never concatenate two versions.
3. Push the code and verify GitHub checks. Then sync on the laptop and run `cd ~/Documents/StoryBuilder && python3 -m pytest -q`.
4. Regenerate Chapter 1, Scene 5 only after the fix is verified. Do not accept the current duplicate draft or apply its old ending-state proposal.
5. Leave the main-plot-only State Analysis experiment unchanged; avoid adding more minor-detail filters.

**Freeze checkpoint:** only handoff files were updated tonight. No app code or novel prose was changed.
