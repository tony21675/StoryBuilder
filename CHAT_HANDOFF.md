# StoryBuilder Chat Handoff

## Latest checkpoint — October 18, 2026: Current State edits did not persist across restart

**Verification after sync:** Tony re-ran `./start.sh`, corrected Time of Day to `daybreak / early morning` using **Apply & Save State Edits**, then restarted StoryBuilder. The daybreak value **survived the restart**. This confirms the immediate local state-persistence issue is resolved. Chapter/Scene were left unchanged; `time.exact_time` remains not established. Continue from Chapter 3, Scene 2 with the persisted state; do not rerun Scene 1 analysis.

Tony clarified that he had manually corrected the time to daybreak/early morning during the previous Scene 2 session, but restarting StoryBuilder restored the old value. Source inspection distinguishes **two separate bugs**:

1. The Writer's editable full ending-state preview was ignored by Apply State Update, which applied only the hidden original proposal.
2. **Current State → Apply State Edits** modified `package.current_state` in memory and marked it dirty, but did not itself write the package to disk. Unless a separate Save followed, the edit could be lost on restart.

**Fixes committed to `main`:**
- [`a1f43a1`](https://github.com/tony21675/StoryBuilder/commit/a1f43a110064cc7d23fa8f639bd50ca56a8a3ff6) and [`f8c0239`](https://github.com/tony21675/StoryBuilder/commit/f8c02398555ab3073d47fba337154ac45453fe30): apply actual edits made to the ending-state preview.
- [`a58cd52`](https://github.com/tony21675/StoryBuilder/commit/a58cd526a19e9cb503324130430c792a2df4f04b) and [`92f5720`](https://github.com/tony21675/StoryBuilder/commit/92f5720b8cbf98063091ee3b18f0e0f5eb7cd418): add preview safety tests and preserve invalid preview edits for correction/retry.
- [`b74ab6a`](https://github.com/tony21675/StoryBuilder/commit/b74ab6a691a1155d63f86a9958ea3ce556bedec9): rename the Current State button to **Apply & Save State Edits** and persist the package immediately when the button is used. The handler reports a clear error if saving fails or the package has no saved folder. It also returns a success flag so a failed/cancelled state change is not treated as successfully applied by the shared Apply All workflow.
- [`baf6ea1`](https://github.com/tony21675/StoryBuilder/commit/baf6ea122ab91951bbe9c3da112237c46da12c7d): add focused tests for persistence success, save failure, missing package folder, and cancelled state edits.

**Verification limitation:** tests have been added but not executed in this session. GitHub's commit-status endpoint returned no checks for these direct `main` commits. After syncing locally from the StoryBuilder repo root, run:
`python -m unittest discover -s tests -p 'test_state_preview.py'`
and
`python -m unittest discover -s tests -p 'test_state_edits_persist.py'`.

**Next action after the updated StoryBuilder source is on Tony's laptop:** In the open MyNovel package, keep the current Chapter/Scene numbers unchanged, set Time of Day to `daybreak / early morning`, and click **Apply & Save State Edits**. Then restart StoryBuilder and verify the time remains daybreak/early morning. Keep exact time not established. Do not reapply Scene 1 analysis, which could advance the scene pointer again. Do not overwrite the local novel package from the stale GitHub `current_state.json`.

## Latest checkpoint — October 18, 2026: Entry context-menu copy/cut callback fix

Tony ran `./start.sh`; synchronization reported up to date, but a Tkinter callback then raised `TypeError: Entry.get() takes 1 positional argument but 3 were given` in the context-menu `copy()` callback. Root cause: the generic selection handler used `widget.get(start_index, end_index)` for both `tk.Text` and Entry-style widgets. Entry/ttk.Entry/Combobox/Spinbox only accept zero arguments for `get()`.

**Fix committed to StoryBuilder main:**
- [`5ff19ce`](https://github.com/tony21675/StoryBuilder/commit/5ff19ce025afc8d1e0b82f14be0a8cfc5c74b53f): add `StoryBuilderApp._selected_widget_text()`; Text reads via Tk indices while Entry-style widgets slice the full string returned by `get()`. Both Copy and Cut use the helper.
- [`3a0d850`](https://github.com/tony21675/StoryBuilder/commit/3a0d8507a4e9394b4fb1fe163eec29cd8bc121bb): add `tests/test_text_edit_context_menu.py` for selected Entry substring extraction.

**Local checkout:** Tony's reported `git status -sb` was `## main...origin/main` plus untracked root-level `FETCH_HEAD`. Do not stage/commit that file as source. The reported `./start.sh` sync happened before this callback-fix commit, so rerun `./start.sh` from `~/Documents/StoryBuilder` to retrieve it. The sync script stashes and restores untracked files automatically.

**Verification:** the test was added but not executed in this session. Once synced locally, run:
`python -m unittest discover -s tests -p 'test_text_edit_context_menu.py'`
Then run the two recent state-workflow tests:
`python -m unittest discover -s tests -p 'test_state_preview.py'`
`python -m unittest discover -s tests -p 'test_state_edits_persist.py'`

State-persistence and ending-preview fixes remain in the preceding handoff entry. The existing MyNovel package still needs its daybreak correction applied using the new **Apply & Save State Edits** control after StoryBuilder has been updated, then a restart check.

## Latest checkpoint — October 18, 2026: apply the reviewed ending-state JSON

Found a state-update workflow bug: the **Reconstructed Ending State** text area was editable, but `_apply_state_update()` validated/applied `self.pending_state_patch`, the hidden original proposal. Manual changes made to the displayed JSON, including Tony's correction from "the middle of the night" to daybreak/early morning, were ignored.

**Fixes committed directly to `main`:**
- [`a1f43a1`](https://github.com/tony21675/StoryBuilder/commit/a1f43a110064cc7d23fa8f639bd50ca56a8a3ff6): add reviewed-preview-to-patch conversion, protect StoryBuilder-managed navigation fields, reject accidental removal of existing fields.
- [`f8c0239`](https://github.com/tony21675/StoryBuilder/commit/f8c02398555ab3073d47fba337154ac45453fe30): apply the edited visible preview; clarify the label/help text.
- [`a58cd52`](https://github.com/tony21675/StoryBuilder/commit/a58cd526a19e9cb503324130430c792a2df4f04b): add `tests/test_state_preview.py` with four focused tests.
- [`92f5720`](https://github.com/tony21675/StoryBuilder/commit/92f5720b8cbf98063091ee3b18f0e0f5eb7cd418): retain invalid preview text and pending proposal so the author can correct the JSON and retry rather than losing edits.

Tests were added but not executed in this tool session; the commit-status endpoint returned no checks for these direct `main` commits. After syncing, run `python -m unittest discover -s tests -p 'test_state_preview.py'` from the repository root.

This code fix only affects future Apply State Update operations. It does not fix Tony's existing local novel state. For the existing package, safely use **Current State**: set **Time of Day** to `daybreak / early morning`, keep the current Chapter and Scene numbers unchanged, click **Apply State Edits**, then use the normal Save action. `time.exact_time` remains not established. Do not reapply Scene 1's state analysis, which could advance the scene pointer again. Do not overwrite the local novel package with stale remote `current_state.json`.

## Latest checkpoint — October 18, 2026: plan reload and scene-pacing improvements

The first generated Chapter 3, Scene 2 draft was rejected as structurally off-plan. Tony's direction is to improve reusable StoryBuilder behavior rather than manually author a large, novel-specific prompt.

**Source changes committed to StoryBuilder main:**
- Add a distinct **Load from STORY_PLAN.md** control to Scene Contract. It explicitly reloads the current chapter/scene's plan section even if an older Scene Idea is already saved. It asks before replacing visible edits, changes only the editor, and does not save the plan text or alter an existing contract until Tony uses the normal save/Generate-Replace flow.
- Add a generic per-scene **SCENE PROGRESSION AND SCOPE** prompt instruction. It tells the writer to preserve planned phases and endpoint, match the requested degree of progress, and not automatically jump from a disclosure, discovery, reaction, or offer of help into later investigation, assignments, execution, or resolution.
- Add tests for refreshing a stale saved idea from the plan without silently saving it, respecting cancellation, and including progression guidance in Writer context.

This is deliberately generic. No *Taken at Dusk* names, facts, plot beats, or character assignments are being hard-coded into application code.

The concise canonical MyNovel Scene 2 plan is in [STORY_PLAN.md](https://github.com/tony21675/MyNovel/blob/main/STORY_PLAN.md), updated at commit [35c4384](https://github.com/tony21675/MyNovel/commit/35c438422144fcc7b4de5777e08c7571b55421c3). Once this code is pulled locally, use **Load from STORY_PLAN.md** for the active Chapter 3, Scene 2 to load the revised plan into Scene Idea; check its Direction and End, then generate a new attempt. Do not accept the rejected attempt or use a chain of Focused Changes for this structural miss.

The contract parser/endpoint fix remains complete at [commit 1665e923](https://github.com/tony21675/StoryBuilder/commit/1665e9231e77325aa6da7be61ebe02c837be0c24). The latest source commit including the corrected test helper is [6f0ca21](https://github.com/tony21675/StoryBuilder/commit/6f0ca216d4bb2c930be3c4fdbece04ba9106bac2). **Verification:** GitHub Actions [run 39173615322](https://github.com/tony21675/StoryBuilder/actions/runs/39173615322) compiled the application successfully and ran 189 tests. The new Scene Plan tests passed, including loading a revised plan over a stale saved idea and preserving current editor text when the user cancels. The full suite still reports one unrelated, previously known failure: `test_writer_prompt_preserves_uncontradicted_physical_continuity`, which expects the Writer system prompt to contain `Prefer what characters say and do over narration`. That prompt/test wording mismatch predates this feature; keep it separate unless Tony authorizes addressing it.


## Current blocker — Scene Contract time reverted to night

Tony reports the Scene Contract start summary again displays `Time: the middle of the night`. Source inspection confirms `storybuilder.py` method `_scene_contract_start_summary()` reads `package.current_state["time"]["period"]`, falling back to `time_of_day`. `_build_scene_direction()` likewise reads the active saved state; neither derives the time from accepted prose or the plan.

The remote MyNovel `current_state.json` is confirmed stale at Chapter 3, Scene 1 with `scene_completed: false`, time period `the middle of the night`, and a night-time current situation. That differs from the recorded local checkpoint where Scene 1 was accepted, its time was manually corrected to daybreak/early morning, and the state update was reported applied. No novel state file was changed during this diagnosis.

Before editing source code, inspect the *active local novel package* and determine whether it has reopened stale data or whether the corrected state failed to persist. Compare local `current_state.json` with the accepted Scene 1 ending snapshot and any state-update history, and inspect `git status -sb` in the actual MyNovel repository if present. Do not blindly pull or overwrite the unsynchronized MyNovel JSON files. Restore the verified accepted Scene 1 endpoint state locally if necessary, preserving `exact_time: not established` and advancing to Chapter 3, Scene 2; then refresh Scene Contract and confirm the display reads daybreak/early morning. Leave accepted prose and the rejected Scene 2 draft untouched. Only consider a generic source-code change if evidence shows the state is correct but Scene Contract still displays the old value.

## Current checkpoint: Chapter 3, Scene 2 and generic plan-to-idea loading, October 18, 2026

**Read first:** [MyNovel HANDOFF.md](https://github.com/tony21675/MyNovel/blob/main/HANDOFF.md), [STORY_PLAN.md](https://github.com/tony21675/MyNovel/blob/main/STORY_PLAN.md), and then inspect the active local novel package's current_state.json, writing_guidance.json, accepted immediately preceding scene, and before/after state snapshots. When local novel files differ from GitHub, the current saved local package is authoritative until safely reconciled.

**Current accepted-scene checkpoint:** Tony approved the fresh Chapter 3, Scene 1 generated after the generic Writer style-prompt rule 9 change. He reviewed the ending-state preview, manually changed `time.period` from `the middle of the night` to a daybreak/early-morning value because the prose and `current_situation` clearly end at first light, left `exact_time` unestablished, and accepted/applied the state update. The scene is accepted, and the workflow should now be at Chapter 3, Scene 2; verify the current local package and app pointer before proceeding. The scene follows Tony through the night after he checks Maya once and gently covers her when her blanket slips; it ends at daybreak. Tony likes it overall despite some ornate prose. Its emotional center is Tony's grief and disorientation after losing Tiffany, the last piece of Sarah he has left, and his loneliness: he comforted Maya, but nobody is there to comfort him. Do not treat every return to his grief as automatically wrong; preserve that emotional truth. Do not regenerate or rewrite the accepted scene.

**Phase 1 implementation status:** Plan-to-Scene-Idea autofill is now implemented in StoryBuilder main. It reads only the `STORY_PLAN.md` at the active novel package root, extracts the matching chapter/scene heading and its body up to the next same-or-higher-level heading, and prefills the Scene Idea only if that scene has no saved author idea. Saved author notes win; prefilled content is not persisted until the user saves it or generates the contract. The Writer's read-only Scene Idea preview uses the same fallback. If the plan/section is absent the editor stays blank; if the plan cannot be read, the issue is shown. This is a deterministic file read and makes no model call. Focused parser and UI integration tests were added.

**Verification status for plan autofill:** The focused test_scene_plan.py suite passed all 11 tests, including both Scene Contract UI integration tests. The later contract-endpoint regression tests also pass. The latest full run [39169607366](https://github.com/tony21675/StoryBuilder/actions/runs/39169607366) ran 187 tests with one unrelated failure: test_writer_prompt_preserves_uncontradicted_physical_continuity expects the Writer prompt to contain 'Prefer what characters say and do over narration', which was already absent in the parent commit before the autofill change. The endpoint tests passed in that run. Do not fold a repair of that unrelated prompt/test mismatch into this feature without discussing it separately.

**Current writing position:** Chapter 3, Scene 1, *The Long Night*, is accepted and its ending-state update has been applied in the active local StoryBuilder package. Chapter 3, Scene 2's first generated draft was rejected as structurally off-plan. The canonical MyNovel `STORY_PLAN.md` and `HANDOFF.md` now specify a fresh composition centered on the group's shocked response and questions, a clear disclosure, Chloe's active participation, Maya changing into Tiffany's pajamas, and a hard stop before operational planning. See current [MyNovel HANDOFF.md](https://github.com/tony21675/MyNovel/blob/main/HANDOFF.md) and [STORY_PLAN.md](https://github.com/tony21675/MyNovel/blob/main/STORY_PLAN.md).

Phase 1 implementation reads the active novel package's `STORY_PLAN.md` and pre-fills a missing Scene Idea for the matching chapter/scene; a saved `scene_idea` always wins, and plan-loaded text remains an unsaved editor value until Tony saves it or generates the contract. This feature is generic and must not hard-code `Taken at Dusk` details into application code. Next, update the active local Scene Idea to match the new canonical Scene 2 plan, generate/verify its contract endpoint, and generate a fresh scene. Do not overwrite local scene/state data or pull `current_state.json` and `writing_guidance.json` blindly because local files may differ from remote.

**Agreed roadmap (only Phase 1 currently authorized/active):** 1) automatic Scene Idea population from the novel's existing scene plan; 2) a plain-English Story Planner that proposes chapter/scene plan edits for Tony's approval; 3) a central Writing Desk that reuses current contract, Writer/review, and state-apply workflows. Finish and verify Phase 1 before starting Phase 2 or 3. Preserve current tabs and accepted content. No local-model change.

**Agreed Scene 1 arc:** Start in the middle of the night. Tony is awake in his bedroom after learning from Maya what happened to Tiffany. He quietly checks on Maya while she sleeps in Tiffany's bedroom, adjusts her covers only if needed without waking her, returns to his own room, and continues processing his worry, guilt, and uncertainty through the remainder of the night. End at daybreak. Do not begin breakfast preparation, wake Maya, bring in guests, or disclose the abduction to the group in this scene. Tony did not witness the abduction; never give him first-hand sensory memories of it. Do not invent the kidnapper, motive, destination, buyer, or new clues. Required Beats is intentionally empty.

**Sarah continuity to preserve:** Tony promised Sarah he would change and not return to the “old Tony” from his military days. The letter Sarah left for Tony remains unopened and is marked “For emergencies only.” Tony does not know its contents. It is the one thing that might let him break his promise, but he cannot know whether it permits or requires anything until the letter is opened and its contents are revealed. Never invent, quote, or imply knowledge of the letter's contents. Do not have Tony open, reach for, or decide to open it at this stage; its opening is reserved for a later point in the story.

**Latest code and verification:** Explicit author endpoints, including temporal boundaries, now take priority over stopping after one highlighted action. The Writer can let elapsed time pass through relevant thoughts and natural transitions without padding or inventing consequential events. Code is on StoryBuilder main at [commit 64f92ed](https://github.com/tony21675/StoryBuilder/commit/64f92ed9e29d55673a6e8ac88cb8ee45b0e682ba). GitHub Actions [run 39109698501](https://github.com/tony21675/StoryBuilder/actions/runs/39109698501) passed compilation and all 174 unit tests. On Tony's laptop, the focused test command was run after pulling; the reported final test result was 47 tests, OK. The latest live generation ended at daybreak as requested, checked Maya once, and was approved by Tony. This confirms the behavior for this particular attempt, not a guarantee that every generation will behave identically.
The Writer style rule was then simplified in [commit ba89fa61](https://github.com/tony21675/StoryBuilder/commit/ba89fa61ae853fd62feeaccce953a58d6221adbe), replacing the existing rule rather than adding a new one. This was a prompt-text-only change; no automated status checks were reported for that commit, and the earlier test results are not verification of this latest prompt edit.

## Small generic improvement note (not implemented)

During this scene, the accepted prose and `current_situation` clearly ended at daybreak, but the ending-state analyzer retained the starting `time.period` value `the middle of the night`. Tony manually corrected the time period in the preview to daybreak/early morning (while leaving `exact_time` unestablished) before applying the update. Later, discuss and implement a generic improvement so the ending-state analysis derives/updates the time period from the scene's actual ending and explicit temporal endpoint, instead of blindly carrying forward stale starting-time metadata. This must work across novels and preserve uncertainty about exact clock time. **This is a backlog note only; no code has been changed for it.**

## Correct scene workflow

1. **Scene Contract:** Edit the plain-English Scene Idea. **Generate/Replace Contract** saves the idea, generates the supporting direction and endpoint, saves the generated fields to the local novel package, and automatically refreshes Writer's Scene Direction. If an existing contract is present, confirm replacement only when that is intended. A separate **Build Scene Direction** click is not normally needed after contract generation; it remains available for a manual refresh.
2. **Check the generated direction:** Confirm chapter/scene, cast, starting situation, physical continuity, and the End line. The Scene Idea is primary. Generated direction and compact contract are supporting context. Do not turn ordinary prose into Required Beats; only author-labeled Required Beats are formal beats.
3. **Write:** Click **Write Next Scene** only when the direction is correct and no generation is already running. Let generation finish before navigating or closing.
4. **Review:** Read the entire prose. StoryBuilder does not decide acceptance for Tony. Review the requested scene movement and endpoint, continuity, character knowledge, established canon, and whether consequential facts were invented. Before any edit, discuss the specific correction with Tony and get his agreement. For **Focused Change**, handle exactly one agreed correction per run, then review the full returned scene with Tony before discussing the next correction. Never bundle multiple corrections into one run. Use **Regenerate Scene** only when a whole new attempt is appropriate. **Reject Scene** discards the current unaccepted attempt without changing accepted prose or Current State. Tony's preference is to discard failed attempts rather than create separate draft files; use **Save Draft** only when he explicitly wants to preserve an attempt.
5. **Accept only after approval:** **Accept Scene** saves the prose as the accepted manuscript section and saves its starting-state snapshot. If the prose fails review, do not accept it to advance the workflow.
6. **Analyze accepted prose:** Click **Analyze Accepted Scene** only after acceptance. Inspect the full merged ending-state JSON preview. The preview alone changes nothing. Click **Apply State Update** only after the proposed facts, locations, physical state, time, and character knowledge are understood and acceptable.
7. **Continue:** Applying a valid state update saves the state, saves a recoverable ending snapshot, advances the current scene pointer, and automatically refreshes Writer's Scene Direction. It does **not** automatically finalize a chapter. Use the explicit chapter-finalization action only when Tony confirms the chapter is complete.
8. **Save and sync intentionally:** **Save** writes the novel package locally. **Close** saves locally without syncing GitHub. **Close & Sync Novel** commits/synchronizes the MyNovel repository; do not use it merely to update StoryBuilder code. StoryBuilder and MyNovel are separate repositories.

## Local/remote MyNovel boundary

Tony's active local novel package has saved changes for Chapter 3, Scene 1 and the accepted/applied ending state. GitHub's remote current_state.json and writing_guidance.json have not yet been reconciled with the active local package and may still describe the old breakfast opening or stale time. **Do not pull, overwrite, or sync those two JSON files blindly.** Reconcile deliberately when local novel work is ready to sync; the saved local package remains the source of truth.

The latest StoryBuilder startup reported an untracked root-level file named FETCH_HEAD. It was left untouched because it needs read-only inspection before deciding whether it is safe to remove. Do not stage it accidentally or delete it as routine cleanup.

## Permanent collaboration and safety rules

- Always discuss a proposed change with Tony and get agreement on the specific change before editing, unless he has already explicitly authorized that exact change. This applies to prose, Focused Change requests, prompts, story/state data, code, UI, and workflow. Having a list of issues is not permission to fix them all at once. For Focused Change, make exactly one agreed correction per run, review the full returned scene with Tony, and only then discuss the next correction. Preserve accepted manuscript prose and existing state.
- StoryBuilder writes the novel; ChatGPT reviews and discusses the smallest useful correction. Do not substitute a ChatGPT rewrite for StoryBuilder's generation unless Tony explicitly asks.
- Keep StoryBuilder generic. Novel-specific facts and directions belong in the novel package, not hard-coded into application code.
- Keep the existing local Gemma 4 E4B instruction-tuned GGUF model. Do not replace, delete, or add another local model without discussion. Use sequential model execution on the resource-limited laptop.
- Before any app restart, first confirm there is no generation/revision running and determine whether unaccepted prose is on screen. Respect the Save/Discard/Cancel prompt; Cancel leaves the app open.
- Keep one remote branch, main, in each repository. Before any manual pull, inspect git status -sb and fast-forward only when safe. If anything is dirty or divergent, inspect and reconcile it rather than resetting or force-pulling.
- At the beginning of a future session, use the newest checkpoint here, not old Scene 4/Chapter 2 next-step notes from historical conversations. Older project history is not authorization to repeat superseded work.
