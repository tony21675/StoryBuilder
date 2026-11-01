# StoryBuilder handoff, current checkpoint

Date: October 30, 2026

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

- Added a compact Character Cards preview and **Manage Character Cards** window with a selectable list, full detail preview, and **Add Character**, **Edit Selected**, and **Remove Selected** actions. Removing a card requires explicit confirmation.
- **Corrected the storage model to match the existing novels.** Their `story_bible.json` files store character filenames such as `Daniel_Okafor.json`; each character's actual data is a separate JSON file in the novel package root. The manager now loads those files and displays the full JSON content instead of treating the filename as a plain-text card.
- **Edit Selected** updates only Name, Role, and Description in the referenced character file while preserving every other key and nested value. **Add Character** creates a separate JSON file and adds its filename to `character_cards`. **Remove Selected** removes only the Story Bible reference and leaves the source JSON file in place. Older non-JSON string notes remain visible but read-only. Embedded structured card objects remain supported for backward compatibility.
- The reader validates that referenced card filenames are root-level JSON files inside the selected novel folder; paths cannot traverse outside the package. File saves use atomic replacement and stop if the source changes while the save is being prepared. No existing novel card file is migrated or rewritten just by loading the manager.
- Automated tests cover opening existing referenced JSON cards, editing only the basic fields while preserving age/personality/skills/custom data, creating separate files, handling duplicate names, safe path validation, and removing a reference without deleting its file. Both CI workflows passed on commit `87760d39588a29bc3b184ed577bed0a982ce73f5`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41141717908) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41141717989). The expanded plain-English editor layout was visually checked on the Surface. The complete Add / Save / Edit / Remove workflow still needs a live end-to-end check in the local-only test package.
- Next: on the Surface, open **The-Long-Way-Home** and **Taken_at_Dusk** and confirm an existing JSON filename entry displays its actual card contents. Keep those real cards read-only during this check. Use only `Story-Bible-Save-Test` for add/edit/remove testing, then verify Premise, Setting, Canon Rules, and all unrelated data are unchanged. Keep the fixture local-only and do not delete it yet.
- Next: run CI, then test on the Surface using only `Story-Bible-Save-Test`: add a temporary card and Cancel; add and Save a separate card; edit it; then test Remove using its confirmation. Verify Premise, Setting, Canon Rules, and all other fields remain unchanged. Keep the test package local-only and do not delete it yet.

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
- Live UI verification is pending. Check the dropdown in the local-only Story-Bible-Save-Test first; do not save or alter real novel cards during the visual test.

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
- Code changes are committed together in one feature commit. Automated CI and live visual verification on Tony's laptop are still pending; the author should restart both apps after syncing to see the new palette.
