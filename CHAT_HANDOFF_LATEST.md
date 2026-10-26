# StoryBuilder current checkpoint — October 25, 2026

## State-summary and state-review prompt refinement (October 25, 2026)

Approved code changes are committed on `redesign/simplified-writing-workflow`:
- `3907a214d40527fe244c1946c8785936e1341a64`: main-plot summaries should retain concise, materially important unresolved evidence and active diagnostic responsibilities without becoming a clue ledger. Predictions, observations, hypotheses, and causal links must remain distinct.
- `20abe48bf4aebfcbca40440b13433a286af19129`: state reviewer must inspect the accepted scene from beginning to end before claiming a discovery or activity is absent; it must distinguish a fact missing from the scene from one present in the scene but omitted from the proposed summary.
- `d34b7913f384679a82fe3a38ab0e288e23da3a39`: regression tests for those prompt requirements.
- GitHub Actions results for these new commits have not yet been verified. Do not report them as passing until confirmed.
- The work laptop has not yet been verified against these prompt changes. Do not sync or restart while a draft is being generated or is otherwise unprotected.


## Text selection and copy controls (October 25, 2026)

The author prefers Ctrl+A/Ctrl+C over dedicated copy buttons. Main-screen fields already receive shared keyboard handlers, but dynamically created popup fields were missed. Remove visible copy-only buttons from Writer, Manuscript, validator-review, error, and scene-flow-report interfaces; right-click context menus may remain as secondary helpers.

The modal scene-review popup has a **Full Scene Draft** tab showing the complete draft in a read-only field, while keeping review actions in the same modal. The concern, request, target, replacement, error, confirmation, and scene-flow report fields support Ctrl+A/Ctrl+C. Dedicated copy-only buttons have been removed. Both GitHub CI workflows passed on code commit `bd07e474685c4fc32b9c89150584d9490d61ef8a`: 400 pytest tests plus 60 subtests, and 400 unittest tests with compile checks. The confirmation popup now copies to the app clipboard, preserving the selection after it closes. Live GUI verification remains pending. No novel prose or saved state should change.

## Proposed state review design (October 25, 2026)

The author approved extending the sequential, author-controlled scene validator pattern to proposed state changes and removing the three separate state-review tabs. The intended UI is one unified, plain-English state-review surface: human-readable change summary plus the existing no-JSON correction fields. Do not expose the raw JSON editor or a Copy Full JSON action. JSON can remain internal implementation detail.

The proposed state is reviewed one concern at a time using the familiar modal controls: generate a focused wording suggestion, apply it only to the proposal, dismiss a false alarm, or skip for later. After an approved correction, the proposal is rechecked. Accepted prose and saved current state remain unchanged until the author explicitly clicks Apply State Update. A review failure must remain advisory rather than silently rewriting state.

For full project history and novel context, see [CHAT_HANDOFF.md](CHAT_HANDOFF.md). This checkpoint supersedes stale statements in prior handoffs about automatic full-scene replacement/recovery and the Scene 5 acceptance gate.

## Current branch and hardware

- Repo: `tony21675/StoryBuilder`; local path: `~/Documents/StoryBuilder`.
- Branch: `redesign/simplified-writing-workflow`. The intended eventual end state is one StoryBuilder branch, `main`, after deliberate review/merge. Do not create/delete branches casually.
- Laptop: Surface Laptop 3. `LONG_TERM_GOALS.md` records **8 GB RAM** and local Gemma 4 E4B GGUF through llama.cpp. No dedicated GPU/VRAM details are verified here. Do not recommend a 14B reviewer without assessing memory fit or asking the user to repeat known specs.
- Always use `python3` on the laptop, one terminal command at a time. Handoff-only edits do not require permission; discuss code/novel changes first.
- On October 25, Tony confirmed the active work laptop already had the previous StoryBuilder checkpoint and was writing there. The new text-selection change is a later remote update and has not yet been verified live. Confirm which machine is active if unclear; protect unaccepted prose and saved story state during testing.

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

Both GitHub workflows passed on code/test commit `60e7117c25d0dbd9231adceb3930cfbdf1060453`: the Python test workflow and the StoryBuilder compile-and-unit-test workflow. These are remote CI results, not a full local suite run. On October 25, the work laptop ran a fresh unaccepted draft through the sequential scene-review popup; this new keyboard selection is a subsequent remote change and still needs sync/live UI verification. The proposed plain-English state-review screen also needs a live UI check.

## The Long Way Home

- Canonical local novel: `~/Documents/MyNovel/The-Long-Way-Home`; GitHub `tony21675/The-Long-Way-Home`.
- Premise: six-person Mars research outpost, all under 30, four women/two men, all single. Life-support crisis is accidental, no sabotage and no one to blame. Survival until Earth rescue or repair is the goal.
- Chapter 1, Scenes 5 and 6 are accepted. The proposed state updates for both scenes were reviewed and applied by the author.
- Current story position: next scene is Chapter 1, Scene 7. The crew has chosen a phased response to the rising scrubber temperature, prioritizing controlled isolation/manual-bypass checks while preserving temperature monitoring, crew-vitals monitoring, and external communications watch.
- Current main-plot state: Daniel's model warns that, if the accelerating temperature rise continues, thermal runaway may become probable within three hours. Morgan reports an intermittent metallic vibration inside the scrubber housing; Ryan notes a possible timing match with older maintenance cycles but cannot confirm a link. Zoe suspects the patterned communications are an echo from a faulty localized sensor relay. Whether the sensor fault, vibration, and overheating share a cause remains unknown. Do not turn the three-hour projection into a confirmed countdown or infer a causal connection.
- No novel files were changed by the StoryBuilder prompt update.

## Next step

The next in-app writing task is Chapter 1, Scene 7; Scenes 5 and 6 and their state updates are already accepted. The new summary/reviewer prompt changes are remote only until pulled onto the laptop.
When ready to sync, make sure no scene is being generated and no draft is at risk. From `~/Documents/StoryBuilder`, follow the standing rule: run `python3 -m pytest -q` before pulling; if green, run `git pull --ff-only` on the existing branch; then rerun `python3 -m pytest -q`. Do not proceed after a failure. Restart StoryBuilder only after both test runs pass. Use one terminal command at a time; never use `python`.
After syncing, test a later state summary to see whether it keeps material unresolved evidence and whether the state reviewer avoids false omissions. Do not edit accepted prose or story state just to satisfy a validator.

## Standing writing principle

**The story is the novel. The state is only a memory aid.** Keep State Analysis to the main plot, stakes, meaningful discoveries/decisions, and unresolved danger. Don't build a rule for every model mistake, prescribe plot outcomes, or hard-code novel-specific facts into StoryBuilder. Preserve accepted prose, and never apply a proposed state change without explicit approval.

## State proposal review implementation checkpoint, October 25, 2026

The author approved one plain-English state-review screen, replacing the three previous state tabs. The unified pane shows a human-readable summary and plain-language correction fields. No JSON editor or Copy JSON button is exposed. The same sequential review popup is reused for state findings, with focused correction, dismiss false alarm, and skip for later. Corrections edit only the temporary proposed state text and trigger re-review. The accepted scene and saved state remain unchanged until the author explicitly clicks Apply State Update.

The state proposal audit compares the generated main-plot summary with the before-state, accepted scene, and author guidance. Findings are advisory. Audit errors show a plain-language warning rather than pretending an audit result exists. A state text correction may replace a whole single proposed text field or one unique passage inside it; it cannot edit another field. The old full-state JSON remains only as an unshown internal buffer for existing validation/merge plumbing.

**Latest code verification:** Both GitHub CI workflows passed on `bd07e474685c4fc32b9c89150584d9490d61ef8a`: 400 pytest tests plus 60 subtests, and 400 unittest tests with compile checks. Live GUI verification remains pending. The work laptop must not sync or restart while an unaccepted draft is being written. The plain-English state-review screen also needs an in-app check. No novel package, accepted prose, or saved story state was changed by this code update.
