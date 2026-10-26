# StoryBuilder handoff — October 25, 2026

## October 25, 2026: scene-validator clipboard access

The author asked for a way to copy the full draft while the sequential scene-validator popup is open. Added **Copy Draft Prose** for scene review only; it copies the complete current Writer text using the main application clipboard, leaves the popup open, and makes no prose or saved-state changes. Proposed-state review remains unchanged. Regression coverage is present and both GitHub CI workflows passed on commit `60e7117c25d0dbd9231adceb3930cfbdf1060453`; live UI verification remains pending.

## October 25, 2026: proposed state review

The author approved a unified, plain-English review of proposed state changes using the sequential scene-validator workflow. Remove the separate “Changes to Review”, “Quick Edits (No JSON)”, and “Full State JSON (Advanced)” tabs and replace them with one state-review surface containing the change summary and plain-English correction controls. The author should not need to read or edit JSON. The validator's findings must be reviewed one at a time; a focused correction changes only the temporary proposal and triggers a recheck. Dismissed false alarms and skipped concerns remain author-controlled. The saved state changes only after the author explicitly applies the final reviewed update. No manuscript/state package is modified as part of this code change.

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

## Validator review redesign (current)

The Scene 5 prompt trace showed that the model sometimes claims a planned event is missing even when the prose already covers it, and the older recovery path could create an unwanted second telling. The design has now shifted from automatic pass/fail recovery to **author-controlled review of individual findings**.

- Generate the complete scene once, then run the semantic coverage/violation check and the separate continuity/scope audit. Reviewers do not get to rewrite the scene automatically.
- Combine findings into a deduplicated queue. The app opens a popup for one finding at a time, showing the concern, the exact proposed target passage, editable correction instructions, and an editable replacement suggestion.
- Actions: **Apply Fix**, **Dismiss: false alarm**, and **Skip for later**. A model can suggest a local fix, but only the explicit Apply Fix action changes the prose.
- The focused-patch helper verifies the target exists in the source draft, rejects an entire-scene target and over-broad replacements, and uses the existing focused-edit undo history. The proposed patch is never applied automatically.
- After an approved edit, re-run the review against the revised draft, filter dismissed/skipped concerns, and rebuild the remaining queue so resolved findings are not needlessly repeated.
- Continuity conflicts, uncertain audits, and validator/audit errors become review findings. They do not start an automatic full-scene replacement. The author may dismiss, skip, or apply a small proposed fix and remains responsible for deciding whether to accept the scene.
- A clean review bypasses the popup and proceeds to ordinary scene review. Acceptance is disabled only while the finding queue is active; after the queue finishes, the author's decision is final.
- The popup supports editing correction instructions, not just the model's proposed replacement. This gives the author a way to correct the reviewer's interpretation before asking for another suggestion.
- Regression coverage was added for finding normalization/deduplication, local patch proposals, no automatic full-scene retry, and the acceptance gate during active review.
- **GitHub CI verified on code/test commit `24cb281`:** pytest reported **388 passed, 53 subtests passed in 1.76s**. The compile-and-unittest workflow also passed: **388 tests ran successfully**, and `compileall` succeeded. This is remote CI, not a new test run on the laptop.

The scene validator now presents findings for author judgment instead of automatic whole-scene rewrites. In the October 25 trial, it reported that the team had not made a definitive choice after the draft presented the competing physical-repair and software-diagnostics paths. The author can decide whether that scene should end on the tradeoff or an actual decision; do not force a plot outcome solely to satisfy the validator.

Science/plot note from Scene 5: Daniel's graph reports a rising temperature and conditional model-predicted deadline; Morgan feels vibration on the housing; Zoe hypothesizes a self-generated telemetry loop. The crew has not independently verified whether the reported temperature reflects a real physical fault or a sensor/software reporting error. Keep both possibilities unresolved until the story naturally investigates them. A separate source-backed science reviewer is still a future phase, not part of this code change.

## The Long Way Home

- Canonical local package: `~/Documents/MyNovel/The-Long-Way-Home`.
- GitHub: `tony21675/The-Long-Way-Home`.
- Premise: six-person Mars research outpost crew, all under 30, four women/two men, single/unmarried. Their life-support crisis is accidental, with no sabotage and no one to blame. Goal: survive until rescue from Earth or repair.
- Chapter 1, Scene 4 accepted prose remains unchanged; its last proposed state update was not applied. Chapter 1, Scene 5 remains **unaccepted**. On October 25, the work laptop generated a fresh draft through the sequential validator review queue; the latest trace is saved in the private trace repository. No scene was accepted and no proposed state update was applied.
- Main plot: the primary oxygen scrubber manifold temperature continues to rise while emergency ventilation/reserve blower maintain acceptable pressure. Daniel estimates thermal runaway could become critical if the current rate holds; this is a conditional prediction, not a verified countdown. The silicate-like trace remains unverified and establishes no contamination, entry route, or cause. Elena is moving toward a scrubber-housing inspection with Morgan and Priya. Daniel remains at the hub to monitor temperature. Ryan and Zoe are separately examining patterned communications bursts; no connection to life support is established.
- The latest Scene 5 prose has three unresolved possibilities: true physical overheating, vibration caused by a mechanical issue, and misleading readings from a sensor/software loop. The crew has not independently verified whether the temperature report reflects a real physical fault. Do not resolve this by assumption; let the story investigate it on-page.
- [Latest StoryBuilder prompt trace](https://github.com/tony21675/StoryBuilder-Traces/blob/main/prompt_trace.json). It records earlier duplicate-scene behavior and State Analysis history; traces contain prompts and story text.

## Other novel context

**Taken_at_Dusk**: Chapter 3, Scene 3 snapshot was Saturday morning at Tony's home. Tiffany is in the van with the kidnapper; Maya is shaken at the table; Chloe is steadying Tony at the kitchen island; Beth, Jessica, and Rick are present. No operational plan is established yet. Chloe should be an unexpectedly steady “rock” for Tony; allow Maya's possible stress-slip “I love you” to happen naturally, never force it.

**LocalStoryChat fallback**: `~/Documents/LocalStoryChat`, GitHub `tony21675/LocalStoryChat`; Local Story Chat v7, Dolphin 3.0 Llama 3.1 8B Q4_K_M, llama-cli Vulkan, 10 GPU layers, `--simple-io`, default files under `~/StoryFiles/`.

A future separate app idea: an e-liquid flavor/recipe tracker with separate flavor profiles for Tony and his wife, conceptually similar to StoryBuilder. Do not mix that project into current StoryBuilder work.

## Immediate next steps

1. The author-controlled review workflow is committed to the existing `redesign/simplified-writing-workflow` branch. GitHub CI passed on code/test commit `24cb281`: 388 pytest cases plus 53 subtests, and 388 unittest cases with compile checks. No local test run has been done for this revision.
2. On October 25, the author confirmed the work laptop already had the previous StoryBuilder checkpoint and generated a fresh unaccepted draft there. The new Copy Draft Prose change is a later remote update and has not yet been verified live.
3. When the author is ready to sync the new code, close StoryBuilder, check branch/status first, and sync the existing branch one command at a time. Then test the scene popup's Copy Draft Prose button and verify the copied text is the complete current draft. Do not accept Scene 5 or apply a state update during that test.
4. Watch for these actual behaviors: one complete scene only; one finding per popup; suggested local replacement may be edited before applying; dismiss leaves prose untouched; skip preserves the option to revisit; applying a fix affects only the exact target span and triggers re-review; after review the author can accept without an advisory-only finding blocking the button.
5. Keep hardware/model fit in mind: Surface Laptop 3 with 8 GB RAM, documented as running Gemma 4 E4B GGUF through llama.cpp. Revisit stronger review/science models only after the new workflow has been tested in the app. No separate science reviewer has been implemented.

**Milestone note:** The author-controlled validator review workflow and regression tests are committed on the existing redesign branch. GitHub Actions passed on code/test commit `24cb281` (388 pytest tests and 53 subtests; 388 unittest tests plus compile checks). The handoff-only update will advance the remote branch again, but the code is the same tested code. No changes have been pulled to the laptop, no app has been run locally, and no novel files, accepted prose, or saved story state have been modified.

## October 25, 2026: proposed-state review implemented and verified

The author approved removing the separate “Changes to Review”, “Quick Edits (No JSON)”, and “Full State JSON (Advanced)” tabs. The Writer's state area now presents one plain-English change summary and correction fields. Proposed state concerns use the same sequential, author-controlled review popup as scene validation: focused correction, dismiss false alarm, or skip for later. A focused correction changes only the temporary proposed text field and reruns the audit. No correction is written to the saved current state until the author explicitly clicks Apply State Update. The visible flow does not require reading or editing JSON.

The current normal Writer State Analysis deliberately asks for a concise main-plot summary. The new state audit reviews that generated summary against the before-state, accepted scene, and author guidance. Other values the author edits through the plain-language correction fields remain part of the unified proposal and are checked by the existing state-shape validation before application. Audit failures are reported plainly and leave the proposal for author judgment.

**Latest GitHub verification:** both CI workflows passed on code/test commit `60e7117c25d0dbd9231adceb3930cfbdf1060453`: the Python test suite and StoryBuilder compile/unit-test workflow. The Copy Draft Prose regression test passed in these workflows. The work laptop has run the scene-validator review queue, but the newer Copy Draft Prose button still awaits sync/live verification; the plain-English state-review screen also needs an in-app check. No novel prose or saved state was changed by the code update.
