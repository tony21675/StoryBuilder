# StoryBuilder current checkpoint — October 25, 2026

## Proposed state review design (October 25, 2026)

The author approved extending the sequential, author-controlled scene validator pattern to proposed state changes and removing the three separate state-review tabs. The intended UI is one unified, plain-English state-review surface: human-readable change summary plus the existing no-JSON correction fields. Do not expose the raw JSON editor or a Copy Full JSON action. JSON can remain internal implementation detail.

The proposed state is reviewed one concern at a time using the familiar modal controls: generate a focused wording suggestion, apply it only to the proposal, dismiss a false alarm, or skip for later. After an approved correction, the proposal is rechecked. Accepted prose and saved current state remain unchanged until the author explicitly clicks Apply State Update. A review failure must remain advisory rather than silently rewriting state.

For full project history and novel context, see [CHAT_HANDOFF.md](CHAT_HANDOFF.md). This checkpoint supersedes stale statements in prior handoffs about automatic full-scene replacement/recovery and the Scene 5 acceptance gate.

## Current branch and hardware

- Repo: `tony21675/StoryBuilder`; local path: `~/Documents/StoryBuilder`.
- Branch: `redesign/simplified-writing-workflow`. The intended eventual end state is one StoryBuilder branch, `main`, after deliberate review/merge. Do not create/delete branches casually.
- Laptop: Surface Laptop 3. `LONG_TERM_GOALS.md` records **8 GB RAM** and local Gemma 4 E4B GGUF through llama.cpp. No dedicated GPU/VRAM details are verified here. Do not recommend a 14B reviewer without assessing memory fit or asking the user to repeat known specs.
- Always use `python3` on the laptop, one terminal command at a time. Handoff-only edits do not require permission; discuss code/novel changes first.
- **The local laptop has not pulled these new changes.** Tony explicitly said to hold before pulling because he has another question. Do not give terminal pull/sync instructions until he says he is ready.

## Validator redesign now on GitHub

The user proposed, and approved, replacing automatic pass/fail recovery with a sequential, author-controlled review queue:

1. Generate the complete scene once. Semantic and continuity validators produce findings, not automatic scene rewrites.
2. Open a popup showing one finding at a time. It displays the concern, the exact passage targeted for replacement, editable correction instructions, and an editable local replacement suggestion.
3. The author chooses **Apply Fix**, **Dismiss: false alarm**, or **Skip for later**. Model suggestions are never applied automatically.
4. Applying a fix replaces only the exact target text, after safety validation, and records the earlier draft for Undo. Whole-scene and over-broad replacements remain rejected.
5. After an applied fix, the current draft is checked again. Resolved findings should drop out; dismissed findings stay dismissed; remaining skipped items can be revisited or left for author judgment.
6. The acceptance gate remains disabled only while the review queue is actively open. When review finishes, acceptance is the author's decision, including when a concern was dismissed or left unresolved.

Relevant implementation:
- `builder/scene_completion.py`: `review_scene_draft`, `collect_review_findings`, `review_findings_match`; generation now produces prose once and returns review findings rather than regenerating a full scene.
- `builder/focused_revision.py`: validation and suggestion helper for local replacement patches. It does not mutate the draft.
- `storybuilder.py`: sequential popup and queue controls; uses editable request/replacement fields, exact target checking, re-review after approved edit, and accept/reject guards while review is active.
- Tests cover no automatic full-scene retries, finding queue deduplication, local patch safety, the advisory acceptance gate, and active-review safeguards.

## Verified tests

GitHub Actions passed on code/test commit `24cb281`:
- Pytest: **388 passed, 53 subtests passed in 1.76s**.
- Compile-and-unittest workflow: **388 unittest tests passed**, and compileall succeeded.

These are remote CI results only. No fresh test run has been done on Tony's laptop for the review-queue changes. A subsequent handoff-only commit updates `CHAT_HANDOFF.md`; it does not alter tested code.

## The Long Way Home

- Canonical local novel: `~/Documents/MyNovel/The-Long-Way-Home`; GitHub `tony21675/The-Long-Way-Home`.
- Premise: six-person Mars research outpost, all under 30, four women/two men, all single. Life-support crisis is accidental, no sabotage and no one to blame. Survival until Earth rescue or repair is the goal.
- Chapter 1, Scene 4 accepted prose remains unchanged; its proposed state update was not applied.
- Scene 5 remains **unaccepted**. Do not apply the old proposed ending-state update. No recent validator-code change modified the novel, its manuscript, or saved scene state.
- Science/continuity concern from the draft: Daniel's graph reports a rising temperature and conditional predicted deadline; Morgan feels vibration at the housing; Zoe hypothesizes an internal telemetry loop. The crew has not independently verified whether the temperature reading reflects real heating or a sensor/software reporting problem. Keep both possibilities unresolved until the story investigates them on-page.
- The earlier Scene 5 validator incorrectly claimed the explicit decision point (“We need to decide what moves first”) was missing. Do not force the crew to make a final decision just to satisfy the validator.

## Next step after Tony's question

Wait for Tony's other question and do not pull yet. When he says he is ready:
1. Sync the existing branch on the laptop and run `python3 -m pytest -q`.
2. Open StoryBuilder and test a fresh scene in the new sequential validator popup. Verify local-only edits, dismiss/skip, refreshed findings after a fix, one complete scene, and author-controlled acceptance.
3. Only after that in-app trial, revisit whether a separate source-backed science reviewer or stronger local reviewer model is needed. Fit any model recommendation to the documented 8 GB RAM limit.

## Standing writing principle

**The story is the novel. The state is only a memory aid.** Keep State Analysis to the main plot, stakes, meaningful discoveries/decisions, and unresolved danger. Don't build a rule for every model mistake, prescribe plot outcomes, or hard-code novel-specific facts into StoryBuilder. Preserve accepted prose, and never apply a proposed state change without explicit approval.

## State review CI repair note

Commit `684caf2` introduced the unified plain-English state review and the sequential state proposal audit. The first CI run found three stale attempts to select the removed Notebook tabs and one new prompt assertion mismatch. The follow-up commit removes those obsolete tab selections; validator-unavailable results remain advisory in the status text rather than pretending an audit finding was produced. Re-run both Python test workflows before treating this change as ready to pull.

## State proposal correction safety and CI follow-up

State-focused corrections may replace a complete text-valued proposed field when necessary, or target one unique passage within it. They never touch another field, accepted prose, or saved current state. The first CI run found stale Notebook selections and a prompt assertion mismatch; a follow-up repair is on the same development branch. Do not treat this feature as ready until both CI workflows pass.

## State review test correction

The current state review implementation is on `redesign/simplified-writing-workflow`. The last CI run passed 394 tests and 53 subtests except one newly added ambiguity test whose fixture accidentally differed by letter case. The fixture is corrected to contain two identical targets. Await both CI workflow results before declaring ready.

## State review CI verification, October 25, 2026

The unified single-screen, plain-English proposed-state workflow is implemented on `redesign/simplified-writing-workflow`. The three state tabs and visible JSON controls are removed. The state proposal is reviewed one finding at a time using the same focused correction, dismiss and skip controls as scene validation. A focused correction changes only the temporary proposed state value; the accepted scene and saved state remain untouched until the author explicitly applies the update.

Verified on commit `a3d61564d794e0c9f11431d2b77b12d190fdfbfd`: GitHub Python tests passed **395 tests and 53 subtests**; the compile-and-unit-test workflow passed. A follow-up wording cleanup is being made after that run. This remains remote CI only, and the live application has not yet been tested with the new state-review popup. Do not pull to the user's machines until the next CI check passes and the user says ready.
