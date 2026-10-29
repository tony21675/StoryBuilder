# StoryBuilder handoff, current checkpoint

Date: October 29, 2026

## Current direction

Keep the Minimal Writer stable while building App #2, **Story Bible**, one small, tested feature at a time. The Writer remains the focused prose-writing app; Story Bible is a separate companion for novel setup and reference information. Nothing should save or alter a novel automatically.

## Latest milestone: premise-only Story Bible editing (October 29, 2026)

App #2 still contains the package creator and the read-only JSON viewer. The viewer now adds one carefully limited edit path for the **Premise** field only.

- Select a novel and click **Load Story Bible**.
- Click **Edit Premise** to enable the text area. **Save Premise** saves; **Cancel Edit** discards the draft. Novel selection and refresh controls are disabled while editing so the draft cannot be lost accidentally through navigation.
- The full JSON viewer remains read-only and copyable. After a successful save, it reloads the displayed JSON.
- Added save_story_bible_premise in builder/story_bible_reader.py. It rereads the latest JSON from disk, changes only the premise key, writes to a temporary file in the same directory, flushes the content, preserves the original permission bits, and atomically replaces the source file. Before replacement it checks that the source has not changed while the save was being prepared. If it has changed, the save is refused and the user can cancel/reload rather than overwrite the newer version.
- Other fields, including unknown keys, nested data, character-card references, canon rules, and planning fields, are preserved. Invalid JSON and non-text premises are rejected without changing the file. No edits to character cards or other Story Bible fields are part of this milestone.
- Added regression tests for premise-only changes, preservation of unknown fields, preservation of edits made to other fields before Save, malformed JSON protection, and non-text premise input. Automated CI is being checked on the latest branch commits.
- The user previously verified the Create Novel tab live on the Surface and then pasted formatted JSON from the existing The-Long-Way-Home package, confirming the View Story Bible tab loaded and copy/paste worked. **Live verification of the new premise editor and Save/Cancel controls is pending.** No manuscript prose or Story Bible content was changed during implementation.

### Next laptop check

After the latest CI passes, close the currently open Story Bible app, then run this command:

    cd ~/Documents/StoryBuilder && bash start_story_bible.sh

The launcher syncs the current branch before starting the app. In **View Story Bible**, select an existing novel and load its Story Bible. Click **Edit Premise**, change a word, and click **Cancel Edit**. Confirm the original premise text returns and the JSON stays unchanged. To verify saving end-to-end without risking an accepted novel, use a disposable package for this test or tell me before saving any change to a real novel. Do not edit or save the real premise just for verification.

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
