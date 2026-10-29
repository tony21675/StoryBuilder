# StoryBuilder handoff, current checkpoint

Date: October 29, 2026

## Current direction

Keep the Minimal Writer stable while building App #2, **Story Bible**, one small, tested feature at a time. The Writer remains the focused prose-writing app; Story Bible is a separate companion for novel setup and reference information. Nothing should save or alter a novel automatically.

## Latest milestone: premise editor reliability fix (October 29, 2026)

The first premise-edit implementation enabled a text field inline, but the author reported that typing did not work after clicking **Edit Premise**. Treat this as a UI bug, not user error. The edit interaction has now been changed to use a dedicated modal editor window.

- In **View Story Bible**, the premise shown on the main page remains read-only.
- Clicking **Edit Premise** opens a separate window with an actual editable `tk.Text` field and dedicated **Save Premise** and **Cancel Edit** buttons. The editor receives focus after the window is shown, supports Ctrl+A/Ctrl+C, and closing its window is equivalent to Cancel.
- The app prevents novel selection and refresh/load actions while the editor is open, preventing accidental loss of the in-progress edit.
- **Save Premise** still changes only `premise` in the latest JSON, preserves unknown/nested fields, writes atomically, preserves permission bits, and refuses a race where the file changes while a save is being prepared. **Cancel Edit** makes no disk write.
- Added `save_story_bible_premise` in `builder/story_bible_reader.py`; its automated tests verify premise-only updates, preservation of unknown keys and other recent changes, and refusal to overwrite malformed JSON or invalid premise types.
- The two workflows passed on the premise backend implementation commit `b0f1913c6133f8dc8528b6277a74c0582abf0a72`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40835737981) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40835738033). The dedicated-window UI fix is covered by passing checks: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40836332104) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40836332112).
- The author previously verified the package creator and the read-only viewer on the Surface by creating/removing a disposable test package and pasting the existing `The-Long-Way-Home` Story Bible content. **Live typing/cancel test passed** after the dedicated-window fix: the separate premise editor accepted typing, and the author confirmed it worked after being asked to cancel the edit. **Live Save Premise verification also passed** using the ongoing disposable fixture `~/Documents/MyNovel/Story-Bible-Save-Test`. The author entered the test premise and received success; then a `python3` read-only assertion compared the full saved JSON against the exact expected starter object, including the changed premise and every unchanged field. Terminal output: `PASS: Premise saved correctly; every other Story Bible field is unchanged.`
- No real novel or manuscript was changed during this milestone. The test package `Story-Bible-Save-Test` is intentionally being retained as an integration-test fixture while more Story Bible fields/features are developed; do not remove it yet or sync/publish it as a real novel. The premise editor has now passed live typing, Cancel, Save, and exact-file verification. Next field editors should reuse the separate-window interaction and retain all unrelated JSON data.

### Next laptop check

To launch the current version after further code changes, close any open Story Bible window, then run:

    cd ~/Documents/StoryBuilder && bash start_story_bible.sh

The launcher syncs the current branch before starting the app. In **View Story Bible**, use `Story-Bible-Save-Test` for any further Save-path testing. It currently contains the confirmed test premise. Do not save test changes to the real `The-Long-Way-Home` Story Bible.

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
