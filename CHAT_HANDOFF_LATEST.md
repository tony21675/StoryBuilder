# StoryBuilder handoff, current checkpoint

Date: October 29, 2026

## Current direction

Keep the Minimal Writer stable while building App #2, **Story Bible**, one small, tested feature at a time. The Writer remains the focused prose-writing app; Story Bible is a separate companion for novel setup and reference information. Nothing should save or alter a novel automatically.

## Latest milestone: Setting field editor (October 29, 2026)

App #2 now has two editable text fields: **Premise** and **Setting**. Each opens its own modal text editor with explicit Save and Cancel actions. The main-page previews and full JSON remain read-only.

- **Premise editor live verification passed:** the author typed in the separate editor, Cancel worked, then saved a test premise to the ongoing test package `~/Documents/MyNovel/Story-Bible-Save-Test`. A read-only `python3` assertion confirmed the exact premise and all other starter fields matched. Do not delete this package yet: it is the integration-test fixture while new fields are built. Never publish or sync it as a real novel.
- **Setting editor implementation:** added a read-only Setting preview and **Edit Setting** button. The separate editor has **Save Setting** and **Cancel Edit**, supports typing plus Ctrl+A/Ctrl+C, and closing the editor discards the unsaved draft. While a modal editor is open, novel selection, refresh, and load controls are disabled.
- Added `setting: ""` to the novel creator and `templates/story_bible.json`, so new packages start with an empty Setting field. Existing story bibles are not bulk-migrated or rewritten just by loading them.
- Generalized safe field writing as `save_story_bible_text_field`, allowing only the `premise` and `setting` keys. It rereads the latest file, preserves all other/unknown JSON keys and nested content, writes via a temporary file and atomic replacement, preserves permission bits, and cancels if the source changes during save. The existing `save_story_bible_premise` function remains as a compatibility wrapper.
- Regression tests now cover Setting-only changes, retaining Premise/canon rules/unknown keys, rejection of unsupported fields and non-text values, and ensuring new packages get an empty Setting.
- **Live Setting editor verification is pending.** No real novel or manuscript has been changed by this work. The fixture package currently contains the verified test premise; use it for the first Setting save test.

### Next laptop check

After the latest CI passes, close the current Story Bible app and run:

    cd ~/Documents/StoryBuilder && bash start_story_bible.sh

In **View Story Bible**, select **Story-Bible-Save-Test** and click **Load Story Bible**. You should see both **Premise** and **Setting** previews. Click **Edit Setting**, enter `A temporary setting-edit test on Mars.`, then click **Save Setting**. Do not edit the real The-Long-Way-Home Story Bible. After saving, check the test package's JSON from the terminal to confirm that `setting` was added and `premise` remains exactly the previously verified test text; then we can record the live pass. Keep the test package after verification for future fields.

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
