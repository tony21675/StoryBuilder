# StoryBuilder Chat Handoff


## Latest checkpoint — October 18, 2026: Writer direction now honors explicit Scene Idea metadata

Tony approved a focused source-of-truth fix after the Writer tab showed `Time: daybreak / early morning` and `Cast: Tony, Maya`, while the loaded original Scene Idea specified `Time: Saturday morning at daybreak` and said Beth, Chloe, Jessica, and Rick would arrive later. The previous direction builder copied time and cast straight from `current_state.json` without identifying them as opening-state details.

**Implemented across the actual Writer direction path:** `builder/scene_contract.py` now extracts explicit `Location:` and `Time:` from the author's Scene header. The contract-builder prompt gives those fields priority over broad state summaries. `storybuilder.py` reuses the exact saved Scene Idea shown in Writer: explicit header values override state labels; `scene_cast` is labeled as the opening cast only; physical positions are labeled opening continuity; and characters named to arrive later are not excluded. State still controls completed events, character knowledge, and starting physical position.

**Verification at code/test commit `57a8513`:** compilation succeeded. All three new regression tests passed, including the test against the real `_build_scene_direction` method; two parser tests also passed. The full suite ran 216 tests and showed five older failures also present before this change: three workflow-safety errors (empty ending-state preview), one existing Writer-prompt assertion, and one existing text-selection assertion. No new regression test failed. [Actions run](https://github.com/tony21675/StoryBuilder/actions/runs/39201291424).

**Next step:** The in-progress/unaccepted Chapter 3, Scene 2 draft was generated with the prior stale direction. Do not accept it. After it finishes, sync the current StoryBuilder code using `cd ~/Documents/StoryBuilder && ./start.sh`. Then, before generating another draft, click Writer's **Build Scene Direction** to refresh the display. Verify it shows `Time: Saturday morning at daybreak` and `Opening cast (present at scene start only; not the full scene cast): Tony, Maya`, with the explicit rule that later arrivals from the Scene Idea may enter. Regenerate Scene 2 only after that check. Keep accepted Scene 1 untouched and do not apply Scene 2 state until Tony reviews it.

**Required collaboration workflow:** Read the handoff first. Diagnose, recommend the narrow fix, and ask Tony for explicit approval before modifying code, prompts, story files, or repository state. Implement only after approval; then test, update this handoff, and report exact results. Discussing a problem is not permission to change files.

---
## Follow-up — October 18, 2026: indentation correction in authored-header direction fix

The first CI run exposed an indentation error in storybuilder.py, which has been fixed; the next run passed compilation. Its one new Writer-direction test then revealed it had been appended to a test class without the helper it relied on, so the test now builds its lightweight app fixture directly. Verify the next Actions run before asking Tony to sync.

---
## Latest checkpoint — October 18, 2026: prevent stale starting-state metadata from overriding the Scene Idea

Tony approved this focused fix after finding the Writer's Scene Idea said `Time: Saturday morning at daybreak` and required Beth, Chloe, Jessica, and Rick to arrive later, while the Writer direction showed `Time: daybreak / early morning` and `Cast: Tony, Maya`. The starting state's time/cast describe the scene's opening snapshot; they must not override explicit scene-wide author metadata or exclude later arrivals.

**Code change:** `builder/scene_contract.py` provides `extract_scene_header_metadata()` to retrieve explicit `Location:`/`Time:` from the author's Scene header, and the contract-builder prompt now gives those fields priority over broad state summaries. `storybuilder.py` reuses the same saved Scene Idea plan entry used by the Writer preview; the direction uses explicit author header values when present, labels `scene_cast` as the opening cast only, labels physical positions as opening continuity, and explicitly permits later arrivals named in the Scene Idea. State still controls completed events, knowledge, and starting positions.

**Regression tests:** parser tests cover explicit Saturday time/location and ensure metadata is not inferred from body prose. A Writer-direction integration test exercises the actual UI-direction builder: explicit author time overrides `daybreak / early morning`, opening cast is clearly scoped, and later arrivals remain allowed. Verify the latest GitHub Actions run before asking Tony to sync.

**Next step after verification:** Let the current unaccepted generation finish, but do not accept it. Once code and tests are confirmed, Tony should run `./start.sh` from `~/Documents/StoryBuilder` to sync and launch, then click Writer's `Build Scene Direction` button to refresh the displayed direction before regenerating Chapter 3, Scene 2. Keep accepted Scene 1 untouched. MyNovel's `STORY_PLAN.md` already has the approved `Saturday morning at daybreak` header.

**Required collaboration workflow:** Read the handoff first. Diagnose, recommend a narrow fix, and ask Tony for explicit approval before modifying code, prompts, story files, or repository state. Implement only after approval; then test, update this handoff, and report exact results. Discussing a problem is not permission to change files.

---
## Latest checkpoint — October 18, 2026: evidence-backed continuity audit and Saturday scene-time anchor

Tony approved the next focused StoryBuilder change before implementation. The audit now requires five distinct checks: timeline/event order, character presence and knowledge, physical/location continuity, unsupported consequential details, and the scene hard stop. Any reported conflict must cite an exact excerpt from the draft and an exact excerpt from the original scene direction, starting-state JSON, or stable author guidance. The app verifies both quotes against the supplied text. Missing categories, unsupported quotes, uncertain categories, or disagreement between the semantic validator and the evidence-backed audit preserve the original draft rather than triggering a rewrite. Only a fully structured, evidence-backed conflict permits one full-scene retry. A continuation for missing beats is appended only when the entire combined draft receives a clear audit.

Verification on code commit `154e19a`: compilation succeeded and all 14 `test_scene_completion` tests passed. The full suite ran 213 tests and still failed on five older, unrelated tests: three workflow-safety tests raise `ValueError: The ending-state preview is empty`, one writer-prompt test expects a phrase absent from the current prompt, and one text-selection test gets `' earl'` instead of `'early'`. These are the same five failures seen before this focused audit change; no new scene-completion test failed. Actions run: https://github.com/tony21675/StoryBuilder/actions/runs/39199395194.

**Novel plan time label:** `MyNovel/STORY_PLAN.md` now identifies Chapter 3, Scene 2 as `Location: Tony's home` and `Time: Saturday morning at daybreak`. The local MyNovel checkout was not edited by this remote change; follow its existing reconciliation steps and do not overwrite its pending local state/guidance edits blindly. After the local package is safely reconciled, reload the Scene Idea from `STORY_PLAN.md` and refresh the contract before generating.

**Required collaboration workflow:** Read this handoff first. For changes to code, story files, prompts, or repository state, diagnose first, report the concrete findings and recommend a focused change, then stop and ask Tony for explicit approval. Do not edit, commit, or push those changes until approval is given. After approval, implement the agreed scope, test it, update this handoff, and report exactly what passed and failed. Never treat a request to discuss a problem as permission to change files.

**Next step after the latest code is pushed:** Tony should sync once from `~/Documents/StoryBuilder` with `./start.sh`, then test the new Writer behavior after the MyNovel plan has been safely reconciled. Keep accepted Chapter 3, Scene 1 untouched. Never auto-accept Scene 2 or apply its state update.

---
## Follow-up — October 18, 2026: Chapter 1, Scene 5 fact check

Correction to the draft critique: Tiffany's resistance during the abduction is established in `Manuscript/Chapters/Chapter_01/Chapter_01_Section_05.txt` and repeated in `current_state.json`: two elbow strikes to the solar plexus, a kick to the thigh, a slap to the jaw, and scratches to the kidnapper's left cheek. Maya witnesses this. Do not label those details invented or treat them as a continuity violation. The independent audit receives the whole current state, which explicitly carries those facts forward.

The valid eyewitness problem in the attempted Chapter 3, Scene 2 draft is assigning Chloe firsthand knowledge of the abduction although she was home sick. Other valid review concerns include the loose 'last night' timing (the abduction begins in late afternoon in Chapter 1, Scene 5), having Maya change clothes in the kitchen rather than privately, and pushing into operational investigation beyond the Scene 2 hard stop.

CI follow-up for the generic scene completion/audit change: fixed a mismatch between a new test's expected notice capitalization and the actual notice. The full suite may still report the same five pre-existing failures documented in the prior checkpoint; verify the latest Actions run before asking Tony to sync. Do not ask for another manual prose correction.

---
## Latest checkpoint — October 18, 2026: independent scene-integrity audit and bounded full retry

The next Chapter 3, Scene 2 draft reached the intended rough endpoint but still contained major continuity/scope failures: it assigned Chloe eyewitness knowledge despite her being home sick, asserted unestablished details about Tiffany fighting the abductor, misplaced the timing of the abduction, and advanced into operational investigation. This showed completion checking alone was not enough.

**Second generic mechanics improvement:** the post-generation workflow now runs an independent, conservative continuity/scope audit using the existing local model sequentially. It checks timeline, presence/knowledge, consequential unsupported claims, explicit no-go constraints, and scene hard stop. Ordinary atmosphere and plausible details, including familiar household scents, must not be flagged merely because they are not spelled out in the plan. A material conflict triggers at most one full-scene retry. The regenerated scene must pass both the existing semantic completion review and a follow-up integrity audit before replacing the initial draft. If verification fails, StoryBuilder keeps the original draft and shows a review notice. A safe but incomplete draft may still receive one append-only continuation, which is audited before it is retained. Nothing is auto-accepted and no state is advanced.

`tests/test_scene_completion.py` now covers a full retry when a material conflict is flagged, rechecking after retry, audit failure preserving the original, and refusing an unsafe append-only continuation. Check GitHub Actions before telling Tony this second change is fully verified.

**Next step:** Tony has already pulled the first completion-recovery change and tried a new Scene 2. Do not ask him to make manual prose edits. After the latest code is pushed and checked enough to pull, use the existing `./start.sh` workflow from `~/Documents/StoryBuilder`, then regenerate Chapter 3, Scene 2. Load the current `STORY_PLAN.md` scene plan first if the saved Scene Idea has not been refreshed. Keep Scene 1 accepted, and do not accept Scene 2 or apply its state update without Tony's review.

---
## Latest checkpoint — October 18, 2026: bounded completion recovery for incomplete scene drafts

Tony approved a generic StoryBuilder mechanics change after Chapter 3, Scene 2 ended immediately after the first disclosure instead of carrying through the planned group response and initial role formation.

**Implemented on main in one commit:** `builder/scene_completion.py` runs the existing semantic Scene Contract review after a generated scene. If review reports missing author-intended events but no continuity violations, and the scene contract allows retries, StoryBuilder resets the same local model to the Writer prompt and requests one append-only continuation. It keeps all original draft text verbatim, appends only the continuation, and leaves acceptance/state changes to Tony. If the check fails, reports a continuity contradiction, or cannot safely continue, the original draft stays intact and the Writer status displays a review notice. This behavior is generic; it contains no novel-specific names or plot facts.

Added `tests/test_scene_completion.py` to cover successful review, missing-beat continuation, avoiding append-only repair when continuity is contradicted, validator failure, a missing saved Scene Idea, and retry-limit behavior. GitHub Actions compiled the application and builder modules successfully and ran 205 tests; all six new SceneCompletion tests passed. The overall test job still reports five failures that were already present on parent commit `32ab638`: three SceneWorkflowSafety tests raise `ValueError: The ending-state preview is empty. Analyze the accepted scene again.`; `test_writer_prompt_preserves_uncontradicted_physical_continuity` expects the phrase `Prefer what characters say and do over narration`; and `test_entry_selection_uses_full_value_and_slice_indices` returns ` earl` instead of `early`. These failures were unchanged from the parent run and are outside this focused fix; keep them separate unless Tony authorizes addressing them.

**Tony's next action after pulling once:** Close StoryBuilder safely after confirming no generation is running and no unsaved draft needs keeping. From `~/Documents/StoryBuilder`, use the existing `./start.sh` sync workflow to fast-forward `main` and launch the updated app. For Chapter 3, Scene 2, use **Load from STORY_PLAN.md** once if the saved Scene Idea is stale, then generate a fresh attempt. Review the entire combined draft; automatic continuation is bounded to one pass and is not automatic acceptance. Do not touch accepted Scene 1 or apply a state update before Tony approves Scene 2.

---
## Latest checkpoint — October 18, 2026: MyNovel sync paused before Chapter 3, Scene 2

StoryBuilder on Tony's laptop was synchronized through `./sync.sh start` and finished clean at `7c5f01d` on `main`. A zero-byte root-level untracked `FETCH_HEAD` had been noticed before sync, but a removal attempt found it already absent; the successful sync finished with a clean status. Do not stage or recreate it. No test commands were run as part of this laptop sync.

The MyNovel laptop checkout at `~/Documents/MyNovel/Taken_at_Dusk` was fast-forwarded from `70ba8d3` to GitHub `c4b1ca1`. The local edits were backed up to `~/Documents/MyNovel_pre_sync_backup_20261018_182247` and saved in `stash@{0}` before fast-forward. Applying the stash conflicted only in `STORY_PLAN.md`; Tony resolved it by choosing the updated branch's plan and staging it. The original stash and older `stash@{1}` remain intact.

At pause, the MyNovel working copy still has staged changes to `current_state.json`, `writing_guidance.json`, and `working_writer_notes.json`, plus an untracked Chapter 3 Scene 1 after-state snapshot. These edits have not been committed or pushed. JSON parsing succeeded and the hard sleepwear rule was confirmed in guidance, but final reconciliation remains incomplete:
- active state is Chapter 3 Scene 2, `daybreak / early morning`, with exact time not established;
- Maya's state still carries the stale line that she is wrapped in her robe rather than the clean pajamas established in Chapter 2 Scene 5;
- the Scene 1 ending snapshot says `the middle of the night` despite describing daybreak;
- the Scene 2 guidance and snapshot ignore status still need a full read-only inspection with the Git pager disabled.

Continue from the latest [MyNovel handoff](https://github.com/tony21675/MyNovel/blob/main/HANDOFF.md). Preserve `~/Documents/MyNovel_pre_sync_backup_20261018_182247`, `stash@{0}`, and `stash@{1}`; do not run `git stash pop`, discard the snapshot, or start another Scene 2 generation yet. Finish the state/snapshot reconciliation, validate and commit/push MyNovel, then reload the canonical Scene 2 plan in StoryBuilder and generate a fresh attempt. The previous draft beginning with Maya in a robe is unaccepted and must remain unused.

## Latest checkpoint — October 18, 2026: hard bed-sleepwear rule made persistent in Taken at Dusk

Tony established a hard continuity rule: anyone sleeping in a bed must be either wearing sleepwear or naked. Robes/bathrobes/dressing gowns and ordinary daytime clothing are not sleepwear and must never be what a character sleeps in. If a character uses a robe after a bath, they must privately change into sleepwear (or be explicitly established as naked) before falling asleep. The sleeping outfit carries into the next waking scene until a change is shown.

The rule has been recorded in all three canonical MyNovel planning/guidance locations:
- [story_bible.json](https://github.com/tony21675/MyNovel/commit/b5353b7cf924b5ac9b9bb0020ff2dc15fc76cbdc): permanent canon rule.
- [writing_guidance.json](https://github.com/tony21675/MyNovel/commit/41800c458acb75f5d2bffdd0d0afea77ce1dfc2d): first recurring instruction so the writer receives it across future scenes.
- [STORY_PLAN.md](https://github.com/tony21675/MyNovel/commit/34a9616d1e85c73c087afab417506c7739fa0577): confirmed global hard rule; Chapter 2 Scene 5 requires Tony to offer clean pajamas and give Maya privacy to change before bed.

Chapter 2 Scene 5 prose was already corrected in [commit 4e80dcf](https://github.com/tony21675/MyNovel/commit/4e80dcfa88f676ffc3f77158dc36c8d1ccb1a206); compiled Chapter 2 was updated in [commit c481aec](https://github.com/tony21675/MyNovel/commit/c481aeccb7712b12c6a277dc0a046ecce3f325a8). The Scene 5 saved guidance now also makes sleepwear a required beat. Chapter 3 Scene 2 in-progress draft has Maya waking in a robe and must not be accepted; regenerate after the corrected local files are reconciled.

**Local package safety:** the changes above are committed to the MyNovel GitHub copy. Local MyNovel state/guidance files had known unsynchronized edits. Do not pull/overwrite the novel package blindly. Inspect local MyNovel `git status -sb`, preserve local `current_state.json`, and deliberately reconcile only the changed Chapter 2 Scene 5 prose, compiled Chapter 2, STORY_PLAN.md, story_bible.json, and writing_guidance.json.

## Latest checkpoint — October 18, 2026: Maya's robe-to-bed continuity repaired in MyNovel

Review of the actual manuscript confirmed that Chapter 2, Scene 5 explicitly had Maya wrapped in a thick white robe when Tony settled her onto Tiffany's bed, followed by her falling asleep. Chapter 3, Scene 1 starts with her asleep under the duvet but says nothing about clothing, so the prior scene implicitly left her sleeping in the robe.

The canonical MyNovel GitHub copy has now been corrected:
- [Chapter 2, Scene 5](https://github.com/tony21675/MyNovel/commit/4e80dcfa88f676ffc3f77158dc36c8d1ccb1a206): Tony offers the clean pajamas previously noticed on Tiffany's bed, gives Maya privacy to change, and returns after she's changed and beneath the duvet.
- [Compiled Chapter 2](https://github.com/tony21675/MyNovel/commit/c481aeccb7712b12c6a277dc0a046ecce3f325a8): synchronized to the same prose.
- [STORY_PLAN.md](https://github.com/tony21675/MyNovel/commit/4f6e050e93f531b3c837a28bb160785f090087cb): Maya wakes wearing the borrowed clean pajamas, then privately changes into ordinary daytime clothes before breakfast.

Chapter 3, Scene 1 itself was left unchanged because it does not specify the outfit. The scene state snapshots don't store Maya's clothing, so none were altered. The recent generated Chapter 3, Scene 2 draft is now inconsistent with this corrected canon when it has Maya in a robe on waking; keep it unaccepted and regenerate after the local plan/manuscript is safely synchronized.

**Local/remote caution:** These manuscript/plan changes were committed to the MyNovel GitHub copy only. The local package has known unsynchronized current-state/writing-guidance edits. Do not blindly pull/overwrite those files. Inspect the local MyNovel repo status and synchronize/reconcile only the specific manuscript, compiled chapter, and STORY_PLAN files deliberately.

## Latest checkpoint — October 18, 2026: review of regenerated Chapter 3, Scene 2

A fresh Chapter 3, Scene 2 draft has been generated after the Scene Contract check. It has **not yet been accepted or explicitly rejected by Tony**. Initial review recommends another generation rather than a chain of focused edits because several major scene-level constraints are missed:

- The accepted story timeline says Tiffany was abducted the previous afternoon near the corner; the draft says “taken last night.”
- Tony says only “Tiffany is gone” before a vague follow-up (“She was taken last night. She... she had company.”). The group needs a clear disclosure that Tiffany was abducted, grounded in Maya's account; Tony did not witness the abduction.
- The draft adds unestablished sensory/action details to Maya's recollection, including old cigarettes/cheap cologne/pine needles and specific struggle details. The planned scene explicitly says not to invent new clues or answers.
- It advances too far into concrete investigation: Jessica mentions tracing cameras/digital footprints, Beth proposes questioning neighbors, and Rick mentions perimeter checks. This scene should only establish broad possible contributions and initial shared commitment; specific investigation steps and assignments remain later.
- Chloe is largely sidelined after a one-line commitment; Maya also needs a meaningful voice without being pressured into a full account.
- Maya wakes wearing a robe and remains in it through breakfast. Tony clarified she should already be in pajamas when woken and can change into regular clothes before breakfast.
- The friends arrive as if making an unplanned stop (“we just wanted to swing by”), rather than clearly arriving for the breakfast Tony arranged.

The dawn/breakfast atmosphere and initial shock work as a foundation, and the broad arc is recognizable. The main failure is execution against timeline/canon and the hard stop, not the premise itself. Next step: revise reusable plan/contract or guidance as needed and regenerate; don't accept this draft yet unless Tony decides otherwise. Existing accepted Scene 1, saved daybreak state, and rejected earlier Scene 2 draft remain untouched.

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
