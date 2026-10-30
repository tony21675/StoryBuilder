# StoryBuilder handoff, current checkpoint

Date: October 29, 2026

## Current direction

Keep the Minimal Writer stable while building App #2, **Story Bible**, one small, tested feature at a time. The Writer remains the focused prose-writing app; Story Bible is a separate companion for novel setup and reference information. Nothing should save or alter a novel automatically.

## Latest milestone: Setting editor and novel sync button (October 29, 2026)

App #2 now contains the package creator, read-only full-JSON viewer, and separate editors for **Premise** and **Setting**. Each editor has explicit Save and Cancel actions; typing is done in a dedicated modal editor window. The new **Sync Selected Novel to GitHub** button supports switching computers by syncing the selected real novel's own Git repository.

### Setting field

- Added a read-only Setting preview and **Edit Setting** button. The separate editor has **Save Setting** and **Cancel Edit**, supports typing plus Ctrl+A/Ctrl+C, and closing the editor discards the unsaved draft. While a modal editor is open, novel selection, refresh, and load controls are disabled.
- Added `setting: ""` to the novel creator and `templates/story_bible.json`, so new packages start with an empty Setting field. Existing story bibles are not bulk-migrated or rewritten just by loading them.
- Generalized safe field writing as `save_story_bible_text_field`, allowing only the `premise` and `setting` keys. It rereads the latest file, preserves all other/unknown JSON keys and nested content, writes via a temporary file and atomic replacement, preserves permission bits, and cancels if the source changes during save. The existing `save_story_bible_premise` function remains as a compatibility wrapper.
- Regression tests cover Setting-only changes, retaining Premise/canon rules/unknown keys, rejection of unsupported fields and non-text values, and ensuring new packages get an empty Setting.

### Switching computers: novel sync

- Added **Sync Selected Novel to GitHub** on the View Story Bible tab, reusing `builder.novel_git_sync` and its existing safe repository checks. The confirmation displays the selected package path, branch, remote, local commits ahead of the last fetched upstream, and changed files.
- **Cancel** starts no Git operation. Confirming runs the sync helper in a background thread, reports success/failure in the status area, and refreshes/reloads the selected Story Bible after a successful fast-forward so remote changes show up in the UI.
- It operates only in the selected package's own Git repository, not the StoryBuilder code repo. It requires the package to be the root of its own repo with an `origin` and matching `origin/<branch>` upstream. It doesn't create repositories, remotes, branches, or GitHub repos for new packages.
- The existing helper fetches, only fast-forwards when possible, safely stashes/restores uncommitted changes, checks for unresolved operations/conflicts, refuses divergent histories, and blocks secret/encrypted files. The confirmation is scrollable/copyable.
- `Story-Bible-Save-Test` is a local-only integration fixture and is explicitly blocked from syncing/publishing. Keep it while adding more fields; do not delete it until Story Bible work is complete.
- Added `tests/test_story_bible_sync_action.py` to verify the local test fixture is never sent to Git sync and that cancelling the confirmation never invokes the sync operation.
- The new app, backend changes, tests, and README passed both CI workflows on commit `bd5f459d49e0114e4345049269919a72805e096c`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40837883780) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40837883837).

### Live laptop status and next check

- Premise editing passed live on the Surface, including typing, Cancel, Save, and a full JSON verification against the test package at `~/Documents/MyNovel/Story-Bible-Save-Test`. Its known premise is `This is a temporary save test. Only the premise should change.`.
- **Setting editor live verification passed** on the Surface. The author saved `A temporary setting-edit test on Mars.` to `Story-Bible-Save-Test`, then the read-only `python3` assertion passed: `PASS: Setting saved correctly; premise and title remain unchanged.` The saved Setting was exact and the existing Premise and title were preserved.
- **Novel sync live verification passed on the Surface.** The confirmation showed `/home/tony/Documents/MyNovel/The-Long-Way-Home`, branch `main`, and remote `https://github.com/tony21675/The-Long-Way-Home.git`. It reported no uncommitted local changes. The author proceeded, and Story Bible reported `synced`; no local file commit was needed. The author first tested Cancel, then completed the sync successfully.
- **Desktop round-trip passed.** After the successful Surface sync, the author opened Story Bible on the desktop, selected `The-Long-Way-Home`, ran **Sync Selected Novel to GitHub**, and confirmed the app reported `synced`. This verifies the live two-computer workflow in both directions: Surface push followed by desktop fetch/sync. No local file commit was needed on the Surface. The next time the author switches back to the Surface, they can use the same button to fetch any desktop-side updates before continuing.
- Keep `Story-Bible-Save-Test` local-only and do not delete it until Story Bible feature development is complete. The sync button must continue to block it.
### Next Story Bible milestone: Canon Rules editor

- Added a read-only, copyable Canon Rules preview and a separate **Edit Canon Rules** window. The editor uses one rule per line, ignores blank lines, and has explicit Save / Cancel actions. Closing the window cancels the draft.
- Canon Rules are stored as the existing `canon_rules` array. The dedicated save function updates only that array and uses the same safe atomic-write / changed-on-disk guard as Premise and Setting. The text-field save API remains limited to `premise` and `setting`.
- Existing non-list or non-text Canon Rules, and existing entries containing line breaks, are displayed but not editable through the line-based editor so their content cannot be silently flattened.
- Automated tests cover changing only the Canon Rules array, preserving Premise / Setting / unknown fields, and rejecting malformed values without modifying the file. The editor action tests also verify that blank lines are ignored on Save and Cancel never writes. Both CI workflows passed on commit `342563c5e84365df1fe5a97724a1e0ea532b96ef`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40958955346) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40958955267). Live UI verification passed on the Surface. The author confirmed the Save and Cancel flow worked, the Canon Rules preview updated, and the other Story Bible data remained intact. Keep Story-Bible-Save-Test local-only until Story Bible feature development is complete.
- The author confirmed the live Canon Rules Save / Cancel flow worked on the Surface and the preview updated while other Story Bible fields remained intact. Keep `Story-Bible-Save-Test` local-only until Story Bible feature development is complete.

### Next Story Bible milestone: Character Cards manager

- Added a compact Character Cards preview and **Manage Character Cards** window with a selectable list, detail preview, and **Add Character**, **Edit Selected**, and **Remove Selected** actions. Removing a structured card requires explicit confirmation.
- Each new or edited structured card has **Name**, **Role**, and **Description** fields. **Save Character** saves that card; **Cancel Edit** or closing the editor discards the draft. The manager prevents changing novels or syncing while open.
- Structured cards are stored in the existing `character_cards` array as objects. The schema now accepts these objects and legacy plain-text string entries. Legacy text cards remain visible but are not edited or removed by the structured editor. Extra metadata on structured cards is retained when editing.
- The dedicated save function updates only `character_cards` through the existing atomic-write and changed-on-disk guard. Automated tests cover list-only updates, legacy-card preservation, extra metadata, unrelated Story Bible fields, malformed entries, and editor Save / Cancel behavior. Both CI workflows passed on commit `5e5ab71743d563c100ea03301efac291f5c62db5`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41139426226) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41139426367). Live UI verification is pending.
- Next: run CI, then test on the Surface using only `Story-Bible-Save-Test`: add a temporary card and Cancel; add and Save a separate card; edit it; then test Remove using its confirmation. Verify Premise, Setting, Canon Rules, and all other fields remain unchanged. Keep the test package local-only and do not delete it yet.

## Minimal Writer checkpoint

- Repository: `~/Documents/StoryBuilder`, GitHub `tony21675/StoryBuilder`, working branch `redesign/simplified-writing-workflow`.
- Launcher: `cd ~/Documents/StoryBuilder && ./start.sh`; it syncs the current branch and opens `minimal_writer.py`.
- Live-confirmed features include local GGUF model loading/writing, Continue append behavior, Write replacing visible prose while retaining model context, New Session clearing model conversation without changing the visible draft, stop/reload behavior, text open/save, novel/chapter/scene browsing, safe scene-copy loading, separately confirmed direct scene save, explicit novel-to-GitHub sync, selectable/copyable popups, and selected-passage revision with preview/accept.
- The user likes the focused revision pattern: highlight a passage, describe a change in plain English or provide exact replacement wording, inspect the proposal, then choose whether to apply it. Do not add lots of copy buttons; make text selectable/copyable instead.
- Do not reintroduce over-prescriptive writing rules, validators, or automatic story-state edits into the Minimal Writer. Keep work incremental.

## Protected novel data

- Main test novel: `~/Documents/MyNovel/The-Long-Way-Home`, GitHub `tony21675/The-Long-Way-Home`, branch `main`.
- Accepted Scene 10 is `Manuscript/Chapters/Chapter_01/Chapter_01_Section_10.txt`. Its prose and the novel's story state must not be modified or regenerated during app work.
- **Taken_at_Dusk has important saved content.** Preserve the two encrypted secret letters and all related local-only metadata, helper scripts, private key, and `/secrets/` ignore rule. Do not decrypt, display, copy, upload, or change them unless the author explicitly asks.
- The test package `StoryBuilder_Save_Test_20261028` and latest Story Bible test package `My-Test-Folder` were explicitly removed after their respective tests. No other novel package should be created or deleted without an explicit test plan.
- The current Story Bible viewer must only read `story_bible.json`; no editing or saving is included in this milestone.

## Working rules and preferences

- On the user's Linux machine, terminal commands must use `python3`, never `python`.
- Keep terminal instructions short and do one feature at a time.
- Discuss app or novel changes before making them; user-approved work and handoff-only updates are exceptions.
- Preserve accepted manuscripts. Do not blindly switch or delete Git branches. StoryBuilder should eventually have only `main` after a deliberate merge/cleanup; each novel repo should have its own branch.
- Keep all app text areas and popups selectable so Ctrl+A/Ctrl+C work; avoid cluttering the UI with many copy buttons.
- Model preference: retain Gemma 4 E4B as the current general-purpose writer. The author is separately exploring a second model for explicit adult erotica featuring consenting adults. Do not download/replace models or change model setup without discussion.
