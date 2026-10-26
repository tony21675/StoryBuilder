# StoryBuilder handoff — October 26, 2026

## State-review liberalization and evidence grounding (October 26, 2026)

The author approved a focused fix after the Scene 8 state reviewer falsely claimed the accepted scene covered only the initial alarm and tried to carry a previous diagnostic instruction into a newer bypass decision. Code is committed on the existing `redesign/simplified-writing-workflow` branch:
- `1be39969b9bff0ba5c2449378ef7c8f080e36f40`: makes the state-review prompt more liberal about concise summaries, treats before-state as a baseline rather than a checklist, and recognizes that a newer scene decision can supersede a prior instruction or task.
- `27256e017cd618c973e8ddd75ed129d6927abe6d`: fixes whitespace normalization for the quote-evidence check.
- `edde1467fbe6e796e1e988e28bd8827e216895f1` and `c8f3359ecb398cc5d866358c57fd1f1f97358d61`: add/update regression tests.
- The reviewer must supply a substantial verbatim quote from accepted scene prose. If it supplies a nonempty excerpt from the proposed summary, that excerpt must also match the summary. Unsupported findings are discarded, not shown to the author as additional correction work.
- The new tests and GitHub Actions are **not verified yet**. The commit-status endpoint returned no status entries; don't claim the checks passed until a completed run is confirmed.
- No StoryBuilder code has been pulled or run locally after these commits. The author reported saving/syncing the novel; code changes are remote only. The accepted prose and saved novel state were not changed by these code commits.

## Earlier state-summary and state-review prompt refinement (October 25, 2026)

Approved changes are committed to the existing `redesign/simplified-writing-workflow` branch:
- `3907a214d40527fe244c1946c8785936e1341a64` updates the main-plot summary prompt to retain concise, materially important unresolved evidence and active diagnostic responsibilities without building a full clue ledger. It explicitly distinguishes observed evidence, hypotheses, predictions, and causal links.
- `20abe48bf4aebfcbca40440b13433a286af19129` updates the state-review prompt to inspect the accepted scene from beginning to end and distinguish facts absent from the scene from facts present in the scene but omitted from the proposed summary.
- `d34b7913f384679a82fe3a38ab0e288e23da3a39` adds regression assertions for these prompt rules in `tests/test_state_review.py`.
- GitHub Actions for these prompt commits have not yet been verified. Do not claim the tests passed until a completed run is confirmed.
- These are StoryBuilder code/prompt changes only; no novel prose, accepted scene, or saved story state was edited by them.


## October 25, 2026: text selection and copy controls

The author prefers Ctrl+A/Ctrl+C over dedicated copy buttons. Main-screen fields have shared text-selection/context-menu support, but dynamically created popup fields were missed. Visible copy-only buttons are removed. In scene-review mode, the full prose appears in a **Full Scene Draft** tab in a read-only text field, preserving the modal review controls. Reviewer concern/request/target/replacement fields, error reports, confirmation prompts, and scene-flow reports support keyboard selection. The confirmation prompt copies through the app clipboard so text remains available when it closes. No copy-button clutter. Both CI workflows passed on `bd07e474685c4fc32b9c89150584d9490d61ef8a` (400 pytest tests plus 60 subtests; 400 unittest tests and compile checks). Live GUI verification remains pending.

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
- October 25 prompt refinement: preserve a concise mention of unresolved physical/signal/trace evidence only when it materially affects the main crisis, likely diagnoses, available choices, risks, or next investigative step. Do not build an exhaustive clue ledger. The state reviewer must read the full accepted scene before claiming a fact or activity is absent, and distinguish “not in the scene” from “in the scene but omitted from the summary.”
- Regression assertions for both rules were added to `tests/test_state_review.py`. Related source commits: `3907a214`, `20abe48b`; test commit: `d34b7913`. CI status for these new commits remains unverified.
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
- Chapter 1, Scenes 5 through 8 are accepted and their state updates have been applied. Next writing target: Chapter 1, Scene 9.
- Current accepted main-plot state after Scene 8: thermal runaway is projected within ninety minutes as manifold temperature spikes. The crew decided to prepare a risky partial bypass of Sensor Node Delta-9 to attempt stabilization; Daniel warned that bypassing a primary sensor without knowing its role could cause cascading failures. The bypass has not yet been shown as executed, and the underlying fault/cause remains unconfirmed.
- Keep the three-hour projection conditional, not a confirmed countdown. Do not assume the anomalies share a cause. Scene 6 leaves temperature monitoring with Daniel, crew-vitals monitoring with Priya, and external communications monitoring with Ryan and Zoe as the phased response proceeds.
- [Latest StoryBuilder prompt trace](https://github.com/tony21675/StoryBuilder-Traces/blob/main/prompt_trace.json). Traces include prompts and private story text.

## Other novel context

**Taken_at_Dusk**: Chapter 3, Scene 3 snapshot was Saturday morning at Tony's home. Tiffany is in the van with the kidnapper; Maya is shaken at the table; Chloe is steadying Tony at the kitchen island; Beth, Jessica, and Rick are present. No operational plan is established yet. Chloe should be an unexpectedly steady “rock” for Tony; allow Maya's possible stress-slip “I love you” to happen naturally, never force it.

**LocalStoryChat fallback**: `~/Documents/LocalStoryChat`, GitHub `tony21675/LocalStoryChat`; Local Story Chat v7, Dolphin 3.0 Llama 3.1 8B Q4_K_M, llama-cli Vulkan, 10 GPU layers, `--simple-io`, default files under `~/StoryFiles/`.

A future separate app idea: an e-liquid flavor/recipe tracker with separate flavor profiles for Tony and his wife, conceptually similar to StoryBuilder. Do not mix that project into current StoryBuilder work.

## Immediate next steps

1. Next writing target is Chapter 1, Scene 9. Scenes 5–8 are accepted and the corresponding state updates were applied.
2. The state-review liberalization commits are on remote branch `redesign/simplified-writing-workflow` only. Ensure no scene is being generated and no unaccepted draft is at risk before updating StoryBuilder.
3. From `~/Documents/StoryBuilder`, run `python3 -m pytest -q` before pulling. Stop if any test fails. If green, run `git pull --ff-only` on the existing branch, then rerun `python3 -m pytest -q`. Restart the app only if both test runs pass. Use one terminal command at a time and never use `python`.
4. Tests and GitHub Actions for the latest commits have not yet been verified. No status entries were returned for these commits; do not report tests as passing until confirmed.
5. On a future State Analysis run, check that weak findings are suppressed; core deadlines, meaningful choices, and unresolved causation are still preserved; and a new accepted decision may supersede a previous task without generating a false omission. Do not change accepted prose just to satisfy a reviewer.

**Milestone note:** This code work changes only StoryBuilder's state-review prompt, evidence validation, and tests, plus these handoffs. It does not change the novel package, accepted Scene 8 prose, or the author's applied state update.
