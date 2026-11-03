# StoryBuilder handoff, current checkpoint

Date: November 3, 2026

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

### Completed Story Bible milestone: Character Cards manager

- Added a compact Character Cards preview and **Manage Character Cards** window with a selectable list, full detail preview, and **Add Character**, **Edit Selected**, and **Remove Selected** actions. Removing a card requires explicit confirmation.
- **Corrected the storage model to match the existing novels.** Their `story_bible.json` files store character filenames such as `Daniel_Okafor.json`; each character's actual data is a separate JSON file in the novel package root. The manager now loads those files and displays the full JSON content instead of treating the filename as a plain-text card.
- **Edit Selected** updates only Name, Role, and Description in the referenced character file while preserving every other key and nested value. **Add Character** creates a separate JSON file and adds its filename to `character_cards`. **Remove Selected** removes only the Story Bible reference and leaves the source JSON file in place. Older non-JSON string notes remain visible but read-only. Embedded structured card objects remain supported for backward compatibility.
- The reader validates that referenced card filenames are root-level JSON files inside the selected novel folder; paths cannot traverse outside the package. File saves use atomic replacement and stop if the source changes while the save is being prepared. No existing novel card file is migrated or rewritten just by loading the manager.
- Automated tests cover opening existing referenced JSON cards, editing only selected fields while preserving age/personality/skills/custom data, creating separate files, handling duplicate names, safe path validation, and removing a reference without deleting its source file. Both CI workflows passed on commit `87760d39588a29bc3b184ed577bed0a982ce73f5`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41141717908) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41141717989).
- **Live testing is complete.** Existing file-backed cards displayed correctly in **The Long Way Home** and **Taken at Dusk**. The full Add / Cancel, Add / Save, Edit / Save, and Remove / Confirm workflow passed in the local-only `Story-Bible-Save-Test`. The Relationship character-name dropdown also passed, including free-text entry for names not already in the list. The Jessica save-and-refresh path was verified in `Taken_at_Dusk`. See the dated Character Cards integration notes below for details.
- Keep `Story-Bible-Save-Test` local-only. Do not sync or publish it, and do not delete it until Story Bible development is complete.

### Expanded plain-English Character Card editor (October 30, 2026)

- Replaced the three-field editor with a scrollable tabbed form: **Basic Information**, **Appearance**, **Background & Personality**, **Skills & Story**, **Relationships**, and **Additional Fields**.
- **Name is the only required field.** Age accepts a number or descriptive text. All other fields are optional; newly created cards contain only the information entered. Empty optional fields are not invented or filled with defaults.
- Common details use labeled text boxes. Lists use one item per line. Relationships use separate Character and Relationship boxes with Add / Remove row actions. Custom scalar details use Field Name and Value rows. No user-facing JSON editing, commas, or brackets are required.
- Common existing fields are mapped into the editor, including school performance. Nested and unknown information is displayed in readable form and preserved when left alone; unrecognized structured values are not rewritten from a simplified view.
- The editor writes JSON behind the scenes. Existing card files are carried forward while form changes are applied; the file-only save supports a full edited object with atomic replacement and a changed-on-disk check. New cards accept optional JSON-compatible fields but require a non-empty name.
- Added unit tests verifying Name-only cards, optional/worded ages, preservation of nested data, relationship rows, readable custom fields, and intentional removal of custom fields.
- **Live UI check confirmed by the author on October 30, 2026:** the expanded plain-English Character Card editor looks good. The author requested removal of the unused Pronouns field.
- **Pronouns removed from the editor.** Existing cards that already contain a `pronouns` value keep it unchanged when edited; the legacy key is hidden rather than moved into Additional Fields or deleted. The schema retains the property for backward compatibility.
- Regression test verifies that Pronouns is absent from editable form fields and existing values survive a save unchanged. Both CI workflows passed on commit `ab2232973c6f72f6f6b3b0be897069247ca9ac70`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41150756923) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41150756988).
- **Locations manager implemented (October 30, 2026).** Added a dedicated Manage Locations preview and window backed by the existing top-level locations object. Entries are keyed by location Name. The plain-English editor requires only Name; Type, Description, Geography, Climate, Notable Details, and custom fields are optional. New entries contain only the details entered. Existing custom and nested fields are carried forward when untouched. Legacy string descriptions remain visible and are converted to a Description field only when that entry is intentionally edited.
- Add, edit, rename, and remove are explicit actions. Removing an entry removes only that location from the Story Bible; there are no separate source files. Saving changes only locations, uses the existing atomic-write / changed-on-disk protection, and preserves Premise, Setting, Canon Rules, Character Cards, and unknown top-level data. Unsupported location shapes remain untouched and disable the manager.
- Added automated tests for field-only storage, preservation of nested/custom details, optional fields, duplicate names, cancel, rename, removal, and automatically pre-filling an existing location's required Name field.
- Both CI workflows passed on commit `6a87ed077582b3a5de5820c6147d86a38cecd7d1`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41153174530), with **525 passed and 75 subtests passed**, and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41153174510), with **525 tests passed**.
- **Live UI verification passed on the Surface on October 30, 2026:** the author confirmed the Locations manager test worked. Continue to use only `Story-Bible-Save-Test` for future add/edit/remove checks; keep it local-only and never sync it.

### Minimal Writer: scene-aware saved location context (October 30, 2026)

- Added exact-name selection in `builder.continuity_context.select_relevant_locations`. The helper includes locations named in the active writing text and preserves legacy string descriptions and structured entries. Matching is case-insensitive and uses complete names, not fuzzy or partial matches.
- The active app is `minimal_writer.py`, launched by `start.sh`. It now reads only the selected novel's `locations` field from `story_bible.json` when preparing **Write**, **Continue**, or AI revision prompts. It does not edit the Story Bible or read character cards / current-state files.
- **Write** matches against the new prompt. **Continue** matches against the prompt plus the visible passage, so a scene that starts at one house and later visits another can load both. AI revision matches the selected passage. Only matching saved entries are appended as a readable location-reference section; the status line lists included location names.
- If no full location name matches, the prompt is unchanged. If the selected novel has no readable Story Bible locations, ordinary writing continues without location context. The location loader does not modify package files.
- Added `tests/test_writer_location_context.py` for exact matching, exclusion of unrelated locations, legacy / structured entries, prompt formatting, read-only Story Bible access, and Write / Continue integration.
- Both CI workflows passed on commit `c92ac1f3ad2e74dd3ea067750abfbf3ee371233b`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41154778485), with **536 passed and 75 subtests passed**, and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41154778391).
- **Live Minimal Writer verification passed on October 31, 2026.** The author confirmed automatic location context had already been tested. Keep the prior behavior: exact full-name matches only, no unrelated locations, no Story Bible edits, and no extra character/state context.

### Story Bible whole-tab scrolling improvement (October 30, 2026)

- Wrapped all **View Story Bible** content in a vertically scrollable Canvas with a scrollbar. The embedded content frame resizes to the viewport width and updates the scroll region as sections change size.
- Mouse-wheel scrolling works throughout the visible tab, including Linux Button-4 / Button-5 and standard MouseWheel events. Wheel events are ignored when the pointer is outside the view or when the tab is not mapped.
- All controls, editors, character-card manager, and JSON viewer remain inside the same scrollable tab. The Create Novel tab is unchanged.
- Added `tests/test_story_bible_view_scrolling.py` for wheel direction, high-resolution deltas, off-tab pointer handling, and Linux wheel buttons. The author confirmed live scrolling works on October 31, 2026. The status label initially overlapped the JSON viewer; it was moved to its own row below the viewer and this was also live-confirmed. Both workflows passed after the regression-test correction on commit `3f63372388a784303ce3a9a817ff8125444dcd6b`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41250915497) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41250915570).

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


### Minimal Writer: LibreOffice ODT support (October 30, 2026)
- Added standard-library ODT read/write support. The Writer can open ODT and UTF-8 TXT documents, defaults Save As to ODT, and preserves legacy TXT behavior.
- ODT import reads paragraphs and bold/italic character styles. Markdown-style bold / italic output is rendered using real editor font tags without visible asterisks; save/export writes actual ODT text styles. TXT saves retain the Markdown markers for portability.
- Scene browsing now accepts `Chapter_##_Section_##.odt` and legacy `.txt`. When both exist, ODT is preferred and duplicate entries are hidden. Draft filenames and state JSON files remain excluded.
- Added tests for ODT package structure, Markdown formatting conversion, read/write dispatch, malformed ODT handling, and ODT scene preference.
- Both automated GitHub test workflows passed on commit `2e2fb7b0485d5ba07efb518505f87ced25e9557b`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41157465979) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41157466011).

- **GitHub manuscript conversion completed October 31, 2026.** Added 17 ODT siblings in `tony21675/MyNovel` (commit `d3c8f37da53932fc4006ff60a4e082082d57f837`) and 10 in `tony21675/The-Long-Way-Home` (commit `ed1ad049337af9986eb838eaf504d7844099dab9`). Original TXT files were retained unchanged. Full tree comparison verified that all existing paths and blob IDs were unchanged; the only additions were the 27 ODT files under `Manuscript`. `MyNovel/SECRET_LETTERS_HANDOFF.md` is unchanged.
- Sample ODT binary verification confirmed the ZIP structure, first uncompressed `mimetype` entry, all four required package entries, and valid CRCs. The author confirmed the ODT opens in StoryBuilder and that the documents render correctly in LibreOffice after the paragraph-spacing correction. Keep the TXT originals as backups.
- After updating StoryBuilder code with `./start.sh`, sync each real novel repository through the Writer's novel sync action on each computer so the new ODT files are downloaded. Test opening an ODT in LibreOffice and in StoryBuilder before making ODT the sole manuscript copy.

### LibreOffice paragraph spacing correction (October 30, 2026)

- Live user feedback showed the first ODT copies looked compressed in LibreOffice because body paragraphs had no defined spacing. The ODT writer now applies a dedicated paragraph style to each body paragraph: 0.12-inch space after and 120% line height.
- Added regression assertions in `tests/test_odt_document.py`. Both CI workflows passed on StoryBuilder commit `9fffb5c058c014c8418b9796cb8f4ae7ba85f85b`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41160468204) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41160468155).
- Regenerated all 17 ODT copies in `tony21675/MyNovel` (commit `48dfec60767715b6f6fe479faa4646b1de5d90d0`) and all 10 in `tony21675/The-Long-Way-Home` (commit `a2f1255262aa03c56203e32bc7a7a37ab6f3dd9a`) from the unchanged TXT originals. Repository comparisons confirmed no TXT files or other novel content changed; only the ODT copies and each novel's handoff/readme changed.
- ZIP package structure, entry CRCs, and paragraph-style application were checked on samples from both repositories. The author confirmed both novels display readable paragraph spacing in LibreOffice on October 31, 2026.

### Story Bible status-bar layout correction (October 31, 2026)

- Live scrolling test exposed the status message overlapping the JSON viewer because both widgets were gridded in row 10 of the scrollable content frame.
- Moved the status label to row 11, keeping the JSON viewer in row 10. Added a regression test that inspects the View Story Bible layout and verifies the two widgets occupy separate rows.
- Live verification completed on October 31, 2026: user confirmed the status label is now below the JSON viewer and no longer overlaps it. No novel data was changed.
- The first CI attempt exposed an indentation issue in the AST-based regression test, not the application code. The test now uses `textwrap.dedent` before parsing. Both workflows passed on StoryBuilder commit `3f63372388a784303ce3a9a817ff8125444dcd6b`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41250915497) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41250915570).


## Character Cards integration checks (October 31, 2026)

- The complete add/cancel, add/save, edit/save, and remove/confirm workflow passed in the local-only `Story-Bible-Save-Test`. The fixture remains local-only and must never be synced or deleted until Story Bible development is complete.
- Read-only display of real file-backed cards passed in both novels: Zoe Bennett's `Zoe_Bennett.json` in The Long Way Home and Jessica's `Jessica.json` in Taken_at_Dusk. Both previews showed their actual saved JSON details. Neither real card was edited during those display checks.

### Character Card relationship-name dropdown (October 31, 2026)

- The Relationships tab in the existing per-character editor now uses an editable dropdown for each relationship's Character field. Options are gathered from the selected novel's referenced JSON character cards and any embedded structured cards, then trimmed, de-duplicated case-insensitively, and sorted alphabetically.
- The dropdown remains editable, so names that are not yet represented by a Character Card can still be typed. Existing relationship names/descriptions remain populated as before, including legacy names not present in the current card list.
- No novel data is changed by opening the editor. Regression tests cover name loading from file-backed and embedded cards, ignoring legacy notes or missing files, passing options to the editor, and option normalization.
- Both automated workflows passed on commit `b318bc1b81a07300f63f094ad3597c9decde097b`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41252999168) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41252999165). The first StoryBuilder run exposed only a test fixture omission (Zoe's file was not listed in `character_cards`); the fixture was corrected to match the real data model.
- Live UI verification completed November 1, 2026: the author confirmed the dropdown lists existing character names and remains editable for names not in the list. The test used the local-only Story-Bible-Save-Test; no test-fixture or real novel data was saved or changed.

### Story Bible Character Card save failure diagnosis and fix (October 31, 2026)

- The first save-path audit found that modal editor failures were written only to the status line behind the modal. Added foreground error dialogs to Character Cards, Premise, Setting, and Canon Rules; file read-back verification for card saves; and callback exception handling.
- Live reproduction then exposed two separate form-data crashes:
  1. Existing Additional Fields rows did not initialize `original_key`, while `build_card()` accessed it directly. The test helper had incorrectly supplied this key, so unit tests did not mirror the GUI. Fixed the row initializer and use a safe `.get()` fallback.
  2. The next visible error was `KeyError: 'story_role'`. `story_role`, `protective_nature`, and `knowledge_rule` were incorrectly listed as single-line `_STRING_FIELDS`, although the UI creates multiline `tk.Text` widgets for them. They are now in `_TEXT_FIELDS`; the single-line entry collection contains only actual `ttk.Entry` / `StringVar` fields. Updated the tab-field map to match the real UI.
- Unexpected exceptions while collecting form data are displayed in a dialog attached to the Character editor. The editor now shows immediate `Saving character...` feedback and disables Save while processing. The app callback returns an explicit boolean success result. Failed saves keep the editor open and show the failure; successful file-backed saves read the JSON back, verify it, refresh the main-page Character Cards preview and manager, then close the editor.
- Regression tests now cover real custom-field row initialization, legacy row fallback, form-build exceptions, the multiline story fields (including a two-line value), immediate Save feedback, callback result handling, visible modal errors, file read-back mismatch, and confirmation that a changed Role appears in the main-page summary after a temporary-package file save.
- All code and tests are committed on `redesign/simplified-writing-workflow`. Latest code/test commit: `17fabd7dd69d6ced04e5811724c45797adaaa6cf`. GitHub's combined commit-status endpoint did not return CI status entries, so CI remains unverified. Do not describe the workflows as passed until their runs are confirmed.
- Live verification is still pending. The author has restarted Story Bible after the first save-feedback changes, but the latest field-classification correction was committed afterward and requires another launch through `bash start_story_bible.sh` to pull. Preserve the unsaved Jessica Role text before closing the editor. Use only the local-only `Story-Bible-Save-Test` for the first save test; never sync the fixture or edit real novel cards during this check.

## Latest milestone: Unified dark palette and softer writing surfaces (October 31, 2026)

- Connected the existing appearance system to both Minimal Writer and Story Bible. Neither app had been applying the shared Tk/ttk palette, which left native widgets using bright desktop defaults.
- Updated the dark palette to use near-black window and panel surfaces, dark charcoal buttons/tabs, and soft light-gray editable fields with dark text. This keeps long writing areas readable without the stark white glare.
- Also softened the light-mode field surface from pure white to light gray and added separate field-text and error colors so text remains legible on both palettes.
- Applied the palette at app startup. Story Bible's launcher now defaults to the same dark mode as Minimal Writer; either launcher still honors an explicit `STORYBUILDER_THEME=light` override.
- Classic Tk Text, Listbox, Canvas, Entry, Scrollbar, dialog, editor, character-card, and location widgets inherit the palette. Muted labels and character-save errors use contrast-appropriate colors.
- Added palette regression tests, including the dark-surface/light-field contrast and child-window palette inheritance.
- Code change commit: `e7d75dd22dce42ccaa12aea6bedb7c2606f2740a`.
- Both GitHub workflows completed after this commit. Compilation and launcher syntax checks passed; the unit suites each hit one unrelated pre-existing test-harness error in `test_blank_name_does_not_save_or_close_the_editor`, where the test calls a real Tk message box with a fake root object. The same failure is present on parent commit `c0fb66c32352f0e3aea8d59b9af7b448ec9a4c88`, before the palette changes. The Python test workflow reported 564 passed and 75 subtests passed, with that one failure. The new dark/light palette tests passed.
- Live visual verification completed November 1, 2026: the author confirmed the softer palette looks better in both Minimal Writer and Story Bible.

## Future standalone apps (October 31, 2026)

- App 3 (a simple, independent local-model chat window) and App 4 (a local DIY vape recipe and inventory studio) are explicitly **on hold** until the author considers Minimal Writer and Story Bible finished.
- Neither app is to be implemented as part of StoryBuilder. Both are intended to become independent projects with their own data and desktop launchers.
- Full scope, boundaries, preferences, and restart checklist: [`FUTURE_APPS_ON_HOLD.md`](FUTURE_APPS_ON_HOLD.md).
- A matching parking handoff has also been added to the `LocalStoryChat` repository. Its existing v7 app remains unchanged; it is reference material only, not an automatic decision to turn it into the new generic chat app.
- No repository has yet been created for App 4. Create its dedicated repository only when the author decides to start that project.


## Live Character Card save verification (November 1, 2026)

- The author tested the Jessica Character Card save in the real `Taken_at_Dusk` novel after syncing and launching Story Bible.
- The updated Role saved successfully, and the main Story Bible screen refreshed to show the saved value. This confirms the full live save-and-refresh path, not just the automated tests.
- GitHub issue [#51, Jessica card not saving](https://github.com/tony21675/StoryBuilder/issues/51) is resolved and closed.
- No other novel cards or story data were changed as part of this verification.
- The earlier Character Card save-failure section's "live verification pending" note is superseded by this result.


## Character Relationship dropdown live verification (November 1, 2026)

- The author confirmed the Character field in the Relationships tab displays available existing character names and still permits free-text entry for a name that is not in the list.
- This completes the live UI verification for the Character Relationship dropdown. No character data was saved or changed during the test.


## Minimal Writer: Prepare Scene discovery (November 1, 2026)

- Checked the current `minimal_writer.py` on `redesign/simplified-writing-workflow`. The Writer currently has controls for Write, Continue, New Session, Stop Writing, loading/saving scenes, and revising selected text, but no Prepare Scene button or associated action.
- GitHub issue [#50](https://github.com/tony21675/StoryBuilder/issues/50) contains only the note "prepare Scene button" and an older screenshot, with no comments or defined behavior. It is an unfinished feature note, not a broken existing button.
- At discovery time, implementation was intentionally deferred until the author clarified the intended workflow. The subsequent design and implementation are recorded below.


## Minimal Writer: Prepare Scene feature intent (November 1, 2026)

- The author clarified the intended purpose of the planned **Prepare Scene** feature: it should set up the next scene by placing a suggested starting direction into the existing **What should I write?** text box.
- The author liked the earlier scene-preparation workflow, but the old approach overwhelmed the model with too many rules and an excessively large prompt. The goal is to retain the useful scene setup while restoring room for model creativity.
- Design direction: create a concise, editable scene starter based on the story's current position and only the continuity that matters to the next scene. It should give the model a situation and direction, not a rigid beat sheet or long checklist. The author remains free to edit the prompt before pressing **Write**.
- Do not dump the entire Story Bible, character cards, state files, or a long list of writing rules into the generation prompt. Prefer selective relevant context and let the prose breathe.
- This is a design note only. Prepare Scene is not implemented, and no application code or novel data was changed.


### Prepare Scene destination behavior agreed (November 1, 2026)

- Default behavior: Prepare Scene starts from the currently selected chapter/scene and proposes the next scene.
- The author can override the destination by selecting a different chapter and scene in the existing selectors before preparing.
- Prepare Scene only fills the existing **What should I write?** box with a concise, editable scene starter. It does not generate prose, save manuscript files, advance story state, or silently change the selected novel.
- This confirms the destination behavior for the planned feature; implementation remains pending.


## Minimal Writer: Prepare Scene implemented, awaiting live verification (November 1, 2026)

- Added a **Prepare Scene** button beside the existing **What should it write?** prompt box. It is enabled only when a local model is loaded and a novel is selected.
- For a novel with no saved scenes, the default target is Chapter 01, Scene 01. For an existing selected scene, the default target is the next scene after that selection. The selected chapter/scene dropdowns let the author anchor preparation elsewhere.
- The button asks the loaded local model for a short, flexible scene starter and puts the result into the existing prompt box. The author can edit it before pressing Write. This is a planning turn, not scene prose.
- Context is intentionally compact: Story Bible title, premise, setting, a matching current-state summary/location/cast/up to three open questions, and only the ending of the selected saved scene. It does not send the full Story Bible, canon rules, character cards, clue collections, or unrelated state.
- Context files and scene documents are read only. Prepare Scene does not create scene folders/files, save manuscript text, edit the Story Bible, update current_state.json, or alter novel selection.
- Existing prompt text is protected: if the box is non-empty, the author must confirm replacement. Cancelling keeps it. If the author edits the box while preparation is running, the returned suggestion is discarded so those newer edits are not overwritten. An empty result, failure, or Stop also leaves the existing prompt untouched.
- While preparing, the Writer shows a preparation status and the stop control reads **Stop Preparing**. Stopping uses the existing interrupt behavior, so the model must be loaded again afterward.
- Added 13 tests for empty-novel opening scene preparation, selected-scene advancement, ODT/TXT scene paths, relevant and mismatched current-state matching, compact context selection, read-only file behavior, cancellation, and prompt-edit preservation.
- Both automated workflows compiled the app and tests successfully. All 13 new tests passed. The complete suites ran 578 tests with 577 passing and one unrelated known Story Bible test-harness error: `test_blank_name_does_not_save_or_close_the_editor` creates a fake root that lacks Tk's `.tk` attribute before calling a real messagebox. This same failure was already present before the Prepare Scene changes. Runs: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41352026062) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41352025968).
- Implementation and test commits are on `redesign/simplified-writing-workflow`; latest commit at this handoff update is `a9ff5de1605ac8c1b911a1abadac2f66d82cb20f`.
- Live verification is pending on the author's machine:
  1. Use the local-only `Story-Bible-Save-Test` with no saved scenes. Prepare Scene should create a Chapter 01, Scene 01 starter.
  2. Select `The-Long-Way-Home`, Chapter 01, Scene 10. Prepare Scene should target Scene 11 and use the saved Scene 10 ending plus the matching Scene 11 current-state context.
  3. Review only. Do not press Write, Save, or sync during these checks. Issue [#50](https://github.com/tony21675/StoryBuilder/issues/50) remains open until the live behavior is confirmed.


### Prepare Scene selector and confirmation correction (November 1, 2026)

- The author live-tested the first version. It generated an opening-scene suggestion for a novel with no saved scenes, but the Chapter and Scene selectors remained blank. In the existing-story test, the author selected Scene 10 and the prompt-replacement confirmation was mistaken for a request to overwrite Scene 10; the selectors did not yet display Scene 11.
- Corrected the behavior: after a successful preparation, the Chapter and Scene selectors now move to the prepared destination, even when that chapter/scene has no saved manuscript file yet. The destination is shown as a selectable virtual entry; Load Scene Copy and Save to Selected Scene remain disabled until an actual saved file exists. No folders or scene files are created.
- Selecting Scene 10 now calculates Scene 11 from the selected filename or selector label. The selected scene remains the context source.
- Changed the confirmation title to **Replace prompt box text?** and made the message name both the selected source and target destination. It explicitly says only the **What should it write?** box will be replaced, and that no selected scene or manuscript file will be overwritten or saved.
- Expanded the regression test to reproduce the author's exact Scene 10 → Scene 11 case, assert the target appears in the selectors, confirm Scene 11 has no file until written/saved, and check the safety wording. All 15 scene-preparation tests pass.
- Both CI workflows compile successfully and all new Prepare Scene tests pass. The full suite remains at 579 passed with one unrelated known Story Bible test-harness error: `test_blank_name_does_not_save_or_close_the_editor` uses a fake root without Tk's `.tk` attribute for a real messagebox. Runs for commit `ad9ccc76be43ac1e959f2f4e17ea33d30452522b`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41354159634), [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41354159706).
- Live verification is pending again. Ask the author to relaunch/sync the Writer, then repeat Scene 10 → Prepare Scene. Expected: popup identifies Scene 10 as the source and Scene 11 as the destination; after accepting and successful generation, selectors show Chapter 01 / Scene 11. Do not press Write, Save, or sync during this check. Keep issue [#50](https://github.com/tony21675/StoryBuilder/issues/50) open until confirmation.

## Prepare Scene live verification completed (November 1, 2026)

- The author retested the corrected workflow in Minimal Writer using **The-Long-Way-Home**, Chapter 01, Scene 10.
- After confirming prompt-box replacement, Prepare Scene successfully generated a starter for the next scene and advanced the selectors to **Chapter 01 / Scene 11**.
- This confirms the corrected existing-story path works live: Scene 10 remains the source context, Scene 11 is the prepared destination, and the new scene starter is placed in the editable writing prompt rather than written to the manuscript.
- No accepted Scene 10 prose was overwritten, and Prepare Scene did not save new manuscript prose.
- The earlier empty-novel check had already confirmed that a starter can be generated for a novel with no saved scenes. The later selector correction is covered by automated tests; the author's latest live retest specifically confirmed Scene 10 → Scene 11.
- All 15 Prepare Scene regression tests pass. The full CI suite still has the one unrelated Story Bible fake-root Tk messagebox harness error documented above; do not describe the full suite as completely green.
- GitHub issue [#50](https://github.com/tony21675/StoryBuilder/issues/50) is now closed as completed.

## Story Bible: Genre, Mood & Audience creative direction (November 1, 2026)

- Added an optional **Genre & Mood** section to the Create Novel form. Genre and Mood & Tone are multi-select checkboxes. Available genres include Adventure, Comedy, Crime, Drama, Fantasy, Historical, Horror, Literary, Mystery, Romance, Science Fiction, Suspense, Thriller, and Western. Mood choices include Cozy, Dark, Emotional, Gritty, Hopeful, Humorous, Lighthearted, Melancholy, Serious, Tense, and Whimsical.
- Added one optional **Intended Audience** selection: Children's, Middle Grade, Young Adult, Adult, or Not specified. **Explicit Adult Content (consenting adults only)** is a separate checkbox and is enabled only when Adult is selected.
- New packages save the selections in the creative_direction object in story_bible.json, with genres, moods, audience, and explicit_adult_content. All fields are optional. Older novels without this object remain unchanged when loaded.
- Added a read-only Genre & Mood preview and a dedicated **Edit Genre & Mood** window in View Story Bible. Saving updates only the creative_direction object through the existing atomic, changed-on-disk-protected save path. Cancel makes no changes.
- Minimal Writer now reads this profile from the selected novel and appends a short, flexible creative-direction note to Write, Continue, and AI revision prompts. Prepare Scene adds the same direction to its planning prompt. The note describes the choices as overall flavor, not a checklist; it does not require every scene to use every genre or mood. Explicit adult content is mentioned only when its checkbox is enabled, with consenting-adults-only wording.
- Missing or malformed optional Story Bible data continues to leave ordinary writing usable. Reading the creative profile does not modify novel files.
- Added tests for choice normalization, adult-audience gating, plain-English preview and prompt wording, new-package storage, safe Story Bible updates, Writer integration, and Prepare Scene integration. Compilation and launcher syntax checks passed.
- CI on commit 85e6444a867925bca652d5e7aaa6cd52e3dd2c56: all feature tests passed. Both overall workflows still report the known unrelated pre-existing failure in test_blank_name_does_not_save_or_close_the_editor, where a fake root without Tk's .tk attribute is passed to a real messagebox. Python pytest reports **591 passed, 1 failed, 75 subtests passed**; the unittest workflow reports **592 tests run, 1 error**. Runs: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41357770172) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41357770188).
- Live UI verification is pending. On the next Story Bible launch, inspect the Create Novel form. For save/edit and Writer verification, use only the local-only Story-Bible-Save-Test; do not sync or publish that fixture. Do not alter real novel packages during this check.

- **Live Create Novel UI verification passed on November 1, 2026:** the author confirmed the Genre, Mood & Tone, Intended Audience, and Explicit Adult Content controls appear and work, including the Adult-only gating for Explicit Adult Content. Save/edit and Writer prompt integration verification remain pending. Use only the local-only `Story-Bible-Save-Test` for save/edit testing; do not sync or publish the fixture, and do not alter real novel packages during this check.

- **Live Writer sample reviewed on November 1, 2026:** with the local test novel loaded, the author generated an opening scene about a supposedly decommissioned research-station console emitting an unexplained signal. The prose showed science-fiction setting, mystery hook, tension, and dry humor without forcing every influence into every beat. This is qualitatively consistent with the chosen direction, but a single sample does not independently prove which saved profile values reached the prompt. Preserve this distinction until the test package's saved creative_direction is checked against the Writer's actual prompt/trace or a controlled comparison is made.

- **Live save/reload verification passed on November 1, 2026:** after leaving the editor and reopening Story Bible, the author reloaded `Story-Bible-Save-Test` and confirmed all selected Genre, Mood, Audience, and Explicit Adult Content values remained selected in the preview/editor. This confirms the saved profile persisted. Combined with the successful live Create Novel controls, the representative Writer sample, and automated prompt-integration tests for Write, Continue, AI revision, and Prepare Scene, the creative-direction feature's planned verification is complete. The local test package remains local-only and must not be synced or published.

## Next discussed feature: Manual Prose-Health Check (November 2, 2026)

- The author agreed to explore a lightweight Prose-Health Check for the current unaccepted Writer draft.
- **Trigger: manual only.** The author explicitly chose option A: checks run only when the author clicks **Check Draft**. Do not run automatically after Write or Continue.
- Initial candidate checks: exact duplicate sentences/paragraphs, unusually repeated phrases close together, likely truncation/abrupt ending, and leftover AI preamble/commentary.
- Findings must be advisory warnings, never pass/fail gates. Do not block accepting a draft, change prose, or automatically invoke revision. The author decides whether to ignore a finding or use the existing selected-passage revision workflow.
- Prefer lightweight deterministic local checks first; avoid extra model calls and keep the feature usable on the author's laptop.
- Repetition detection must be conservative because repetition can be intentional in fiction. Do not flag ordinary stylistic repetition as an error.
- **Design agreement only.** No application code has been changed. Before implementation, inspect the current Writer UI and relevant test structure, propose the smallest UI/result behavior, and confirm the remaining acceptance criteria with the author.

## Manual Prose-Health Check implemented (November 2, 2026)

- Added `builder/prose_health.py`, a local deterministic checker that returns advisory findings without modifying the supplied text. It checks substantial duplicate paragraphs, duplicate complete sentences, distinctive six-word phrases repeated at least three times in a 500-word window, clear unfinished endings/unmatched delimiters, and assistant preamble/closing boilerplate at document edges.
- Added **Check Draft** beside **Revise Selection** in the Minimal Writer Output header. It checks the current Output text whether generated, opened, or loaded. It is manual only, enabled when non-empty output exists and the Writer is idle, does not require a loaded model, and displays results in the existing selectable/copyable dialog.
- Findings include category, explanation, location, and a short excerpt. A clean result says no obvious mechanical issues were found and explains the check's limits. The status line confirms no text was changed.
- The check does not call a model, edit output, save anything, alter manuscript files/state, block acceptance, or prevent ordinary Save. It is advisory only.
- Added 10 checker tests covering duplicates, short dialogue, repeated phrases, clean prose, possible truncation, assistant leftovers, empty drafts, and advisory report behavior. Added 2 Writer integration tests for preserving the draft and refusing to run while busy.
- Latest implementation/test commits: `cba4dd178777110c112e55d2d30576ab420aa7d8` (checker), `79ebdecc3d5057d71763ef8601dfdec224fdf7bb` (checker tests), `88cb4474f4df3f23f5d67f9c79373ccfdc4d6550` (Writer button/integration), `c3ea55dd6d9d42c74b02ff811874bf298a3f3eab` (Writer integration tests).
- Both GitHub workflows completed with the new tests passing. The full suites each retain the same unrelated pre-existing failure: `test_blank_name_does_not_save_or_close_the_editor` calls a real Tk messagebox with a fake root that has no `.tk` attribute. Python pytest reports **603 passed, 1 failed, 75 subtests passed**; the unittest workflow reports **604 tests run, 1 error**. Do not call the overall CI fully green. Run URLs: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41535063932), [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41535064084).
- **Live desktop test results (November 2, 2026):** the author confirmed a clean draft returns the expected no-obvious-issues result and an intentionally duplicated substantial paragraph is correctly reported at paragraphs 4 and 10. The author then tested a scene cut off at the words "the difference between"; it incorrectly returned a clean result.
- Inspection found the narrow cause: `between` was missing from the unfinished-ending connector set. Added it to the generic connector-word check in `builder/prose_health.py`; detection is based on the final word's grammatical role, not on a memorized sentence or passage. Regression coverage now uses two differently phrased incomplete endings with `between` and a complete sentence ending in `between them`, proving the check is not tied to one exact wording. Commits: `afbc54c97400a42f4387a7c1c55327b99c19c295` (checker fix), `b8878cb0561eacaa1a5058df7b419b2f3214c657` (initial regression test), and `9739e48216974c80090c7a99d22ffc46eddf44cd` (generic phrasing coverage).
- **Second live truncation test (November 2, 2026):** the author inserted an unfinished phrase ending in "between" inside a scene, then continued with later paragraphs. The checker returned a clean result. Root cause: the connector heuristic only examined the end of the entire draft, not intermediate paragraph endings.
- Updated the same single connector-word heuristic to inspect each paragraph ending, while retaining the separate end-of-draft punctuation check. No new model call, prompt instruction, editing behavior, or large rule set was added. A warning points to the paragraph and line; complete wording such as "the space between them" remains a negative control.
- Added regression coverage for an unfinished paragraph followed by more prose and for a complete paragraph ending in "between them". Commits: `1ce2e234930ab7c264994beebc7332c88cec60c8` (paragraph-level checker) and `ba5a9684f7a6963402b77f3bab06ac230841317e` (regression test).
- Automated test results on the resulting code: the Python workflow reports **605 passed, 1 failed, 77 subtests passed**; the StoryBuilder unittest workflow reports **606 tests run, 1 error**. Both failures are the same pre-existing unrelated Tk test-harness issue in `test_blank_name_does_not_save_or_close_the_editor`, where a fake root lacks the `.tk` attribute required by a real messagebox. The new prose-health tests passed. Runs: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41550505983) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41550506102).
- **Live retest pending after syncing/relaunching Minimal Writer:** reuse a disposable scene where one paragraph ends with an unfinished connector such as "the difference between", followed by another complete paragraph. Expected: **Possible abrupt ending** at the incomplete paragraph, with the later prose and entire draft left byte-for-byte unchanged. Also confirm a complete phrase such as "the space between them" does not trigger. The clean-draft and duplicate-paragraph checks have already passed live. Do not use any accepted manuscript as the test target; use a disposable draft or the local-only Story-Bible-Save-Test. Keep that fixture local-only and never sync/publish it.

## Manual Prose-Health Check live verification closed (November 2, 2026)

- The author completed the live checks in Minimal Writer:
  - Clean ordinary prose returned the expected no-obvious-issues result.
  - An intentionally duplicated substantial paragraph was detected, with both paragraph locations and an excerpt.
  - An unfinished quotation at the end of a draft produced a possible-truncation warning.
  - A complete sentence using "between them" did not trigger an abrupt-ending warning.
  - Opening assistant preamble ("Certainly! Here's your scene.") was detected.
  - Closing assistant commentary ("I hope you enjoy the story!") was detected when isolated as the final paragraph.
- The checker did not detect an unfinished sentence ending in "had". The author explicitly rejected expanding the connector/helping-verb lists into a dictionary-sized set of suspicious words. This is an accepted limitation: the checker is a small, conservative mechanical aid, not a grammar engine, and will miss some incomplete sentences.
- The author also chose not to spend more time optimizing detection around the rare phrase "difference between". Do not add more word lists, grammar rules, or special-case phrase matching. Keep the current lightweight behavior unless the author later asks to revisit it.
- All findings remain advisory. Check Draft is manual only, makes no edits, makes no model calls, and does not save or alter manuscript/state files.
- **Live verification is complete within the agreed scope.** No further Prose-Health Check testing is required now. Treat the feature as closed and move to the next agreed StoryBuilder task.
- The earlier automated test status remains: new Prose-Health tests passed; the full CI workflows still include the unrelated known Tk fake-root test-harness failure documented above. Do not describe the full suite as entirely green.

## Character Card sexual orientation and Writer character context (November 2, 2026)

- Added an optional **Sexual Orientation** dropdown to Character Cards under **Basic Information**, directly below the existing **Gender** field. Gender is unchanged and remains a separate field. Choices are **Straight**, **Bisexual**, and **Not specified**. Not specified is stored as an empty optional value; unknown legacy values remain visible and preserved if encountered.
- The existing **Personality** list remains flexible plain text, one item per line. No preset trait list or required values were introduced.
- Added `builder/character_context.py` to create concise character references from the existing Character Cards. The reference includes available role, age, gender, sexual orientation, relationship status, personality traits, and established relationships. It does not dump full character files or long background text.
- Minimal Writer now includes relevant references in **Write**, **Continue**, and selected-passage revision prompts. It selects characters named in the prompt or visible/supporting prose, recognizes full names and first/last-name references, and also includes the saved `current_state.json` scene cast when available. At a fresh `story_start` with no cast selected, it includes all Character Cards so the opening scene has access to the character foundations.
- **Prepare Scene** includes the saved current scene cast, or all character cards for an opening scene with no cast yet. Missing or malformed individual card files are skipped without preventing ordinary writing.
- Character facts are presented as background, not as a plot checklist or a requirement for romance. The prompt says to keep attraction consistent with stated orientation while allowing friendship, teasing, and affection to remain platonic. Orientation does not force a romantic plot.
- Added regression tests for separate gender/orientation storage, optional blank orientation, clearing to Not specified, concise card summaries, first-name matching, selecting only relevant characters, current scene cast, opening-scene all-cast context, missing card files, and Prepare Scene cast selection.
- Implementation files: `builder/character_card_editor.py`, new `builder/character_context.py`, `minimal_writer.py`, and `builder/scene_preparation.py`. Test files: `tests/test_character_card_editor.py`, new `tests/test_character_context.py`, `tests/test_minimal_writer.py`, and `tests/test_scene_preparation.py`.
- Latest feature code/test checkpoint before this handoff update: `d725dfd3b826535e904af5449ab021102c0afbf0` on `redesign/simplified-writing-workflow`.
- Automated tests on that checkpoint: Python workflow reports **615 passed, 1 failed, 77 subtests passed**. The single failure is the same pre-existing unrelated `test_blank_name_does_not_save_or_close_the_editor` Tk test-harness error: its fake root lacks the `.tk` attribute required by a real messagebox. The StoryBuilder unittest workflow likewise reports only that known Tk error; all new character-orientation and context tests passed. Runs: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41571855706) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41571855662).
- **Live UI verification (November 2, 2026):** the author confirmed the Sexual Orientation field appeared separately from Gender and assigned values to all six Mars Character Cards. The dedicated diagnostic prompt asking the model to recite each card's facts was not run; prompt-context selection and formatting are covered by automated tests.



## Flexible story-opening pacing guidance (November 2, 2026)

- Added shared prompt guidance in new `builder/story_pacing.py`. It asks the Writer to choose opening pace based on the story's premise, genre, tone, author direction, and what is already established.
- The note encourages enough early groundwork for readers to connect with characters, setting, and relationships. It explicitly acknowledges that ensemble stories may need several scenes and can establish the cast through different groupings.
- It does **not** prescribe a scene count, percentage, or mandatory sequence. It says not to assume the central conflict must begin in Scene 1 or immediately afterward, while also avoiding filler or artificially delaying an urgent conflict when the story or author calls for immediate action.
- The same guidance is included in both **Prepare Scene** and the Minimal Writer **Write / Continue** prompt context. It is generic across novels and does not modify any novel package or current manuscript.
- Added regression assertions in `tests/test_scene_preparation.py` and `tests/test_minimal_writer.py` to verify both prompt paths include the flexible guidance and retain the no-fixed-count / no-artificial-delay balance.
- Implementation commits: `ba13bc6be72ac6d1c152330577d8d4c7c7d1431b` (shared guidance and prompt integration), `2c00a852c5bea332ec4b82b63385025153d5a994` (correct Writer prompt paragraph spacing and add a spacing assertion), and `7d9300f42fc55a1b83dde44ac85883f989a282db` (preserve the existing no-op behavior when the Story Bible is missing or malformed and align wording assertions).
- Automated results on the final code commit: Python workflow **615 passed, 1 failed, 77 subtests passed**; StoryBuilder unittest workflow **616 tests run, 1 error**. The only remaining failure in both workflows is the known, unrelated `test_blank_name_does_not_save_or_close_the_editor` Tk test-harness error where a fake root has no `.tk` attribute. All new pacing guidance assertions pass. Runs: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41585876469) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41585876521).


## Prepare Scene automatically clears model conversation (November 2, 2026)

- After Prepare Scene successfully generates its editable suggestion, Minimal Writer now calls `WriterEngine.clear_context()` before presenting the completed result. This removes the planner turn from the persistent llama-cli chat history; the generated suggestion remains in the prompt box for the author to edit and pass to Write.
- The clear runs in the existing worker thread after generation completes, so it does not block the UI. It does not clear the visible prose/output or alter manuscript files, Story Bible, or current state.
- If clearing the context fails, the generated suggestion is still preserved and selected as before. The app marks the model as unloaded and tells the author to reload it before Write, avoiding a silent fallback to contaminated chat history.
- Added tests verifying the order (generate first, clear second), normal success, and failure behavior preserving the suggestion while requiring a model reload.
- Implementation commits: `caac100cc4e9b45e2bee212b50125029b906e489` (automatic context clear after Prepare Scene) and `bc007e6872c1dc92fa8fee3f9a3c2aa49899a28c` (test formatting fix).
- Automated test result on the final code commit: StoryBuilder workflow ran **618 tests, with 1 error**. The single error is the same pre-existing unrelated `test_blank_name_does_not_save_or_close_the_editor` Tk test-harness issue where a fake root lacks `.tk`. Thus **617 tests passed**, including both new context-clear tests. Run: [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41587687161).


## Save New Scene workflow (November 3, 2026)

- Added a dedicated **Save New Scene** action to Minimal Writer. It writes the current output directly to the selected novel's `Manuscript/Chapters/Chapter_NN/Chapter_NN_Section_MM.odt` path and does not open a file picker.
- When Prepare Scene has selected an unsaved scene number, that destination is used. If the selector is blank or still points at an already-saved scene (such as after restarting the app), the action appends after the highest saved scene number. It checks both ODT and TXT names and never overwrites an existing scene.
- After saving, Minimal Writer refreshes the chapter's Scene dropdown and selects the new scene. The existing **Save to Selected Scene** remains the explicit, confirmation-protected overwrite path for a scene already loaded as a copy.
- Renamed the ordinary **Save** and **Save As** labels to **Save Draft** and **Save Draft As…** to distinguish standalone files from manuscript scene saves.
- Added tests for correct scene path/filename, reading the saved ODT back, appending when the selector points at an existing scene, no-overwrite behavior against TXT/ODT scenes, and blank-output protection.
- Implementation commit: `2e177655764d89a9ea8dfea0a89ff5c0b3d6324c`.
- Automated results on this commit: Python workflow **621 passed, 1 failed, 77 subtests passed**; StoryBuilder unittest workflow **622 tests run, 1 error**. Both have only the same pre-existing unrelated Tk harness error in `test_blank_name_does_not_save_or_close_the_editor` because a fake root lacks `.tk`. All new Save New Scene tests passed. Runs: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41589179869) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41589179746).


## Canon Rules prompt integration (November 3, 2026)

- Fixed a missing connection: the Story Bible already saved canon_rules, but neither Prepare Scene nor Minimal Writer Write / Continue included those entries in the model prompt.
- Added shared builder/canon_rules.py formatting. It renders nonblank saved rules as a compact CANON RULES section and leaves empty or unsupported values out. No schema, Story Bible UI, or novel-package storage changes.
- Integrated the shared section into builder/scene_preparation.py and MinimalWriterApp._prepare_location_context in minimal_writer.py. Prepare Scene and actual writing now receive the same saved canon directions.
- Updated tests/test_scene_preparation.py and tests/test_minimal_writer.py; added tests/test_canon_rules.py. Regression tests verify the planner and writer prompts include saved rules and the formatter ignores blank/unsupported entries.
- Latest relevant commits: b04607e301c0f69f7df4f5ffd966c29d983a2609 (formatter), d04892e562fcdf72c9befaf57b646ee37d144405 (Prepare Scene), fb84ee5b9ac492c1f1cd8ccd0dd6ec104950fb25 (Writer), 1d4c5a916402d819a3ad0b0c9f5e1a38eb539e34 and 7a09bcb5ef2cb2a33a8a68c1140bde09b573dea5 (integration tests), 714e409c90ec8141d74b0a63b31bbd1332c228d1 (formatter newline correction), and a6b3db0d47292a5ea682daf429193bcadce7a2b5 (formatter tests).
- CI on the latest code commit: Python workflow 623 passed, 1 failed, 77 subtests passed; StoryBuilder workflow 624 tests run, 1 error. The only failure is the existing unrelated test_blank_name_does_not_save_or_close_the_editor Tk harness error (fake root has no .tk). Both new formatter tests and the Prepare Scene / Writer integration tests passed. Runs: https://github.com/tony21675/StoryBuilder/actions/runs/41600277173 and https://github.com/tony21675/StoryBuilder/actions/runs/41600277280.
- Live verification still needed: close Minimal Writer and run cd ~/Documents/StoryBuilder && ./start.sh to pull the development branch. The Long Way Home's existing Accident Timing Canon Rule was saved and synced by the author; Scene 4 remains unwritten. After pulling, check that Prepare Scene's next suggestion no longer invents an anomaly. This code change does not modify any novel files or manuscript prose.
