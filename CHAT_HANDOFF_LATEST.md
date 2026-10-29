# StoryBuilder handoff, current checkpoint

Date: October 29, 2026

## Current direction

Keep the Minimal Writer stable while building App #2, **Story Bible**, one small, tested feature at a time. The Writer remains the focused prose-writing app; Story Bible is a separate companion for novel setup and reference information. Nothing should save or alter a novel automatically.

## Latest milestone: Story Bible read-only viewer

App #2 now has two tabs in \`story_bible_app.py\`:

- **Create Novel:** enter a title and optional folder name. \`builder/novel_creator.py\` creates a new package under \`STORY_NOVEL_ROOT\` (normally \`~/Documents/MyNovel\`) containing \`story_bible.json\` and \`Manuscript/Chapters/\`. It refuses existing destinations, rejects path traversal, and does not initialize Git or invent story content.
- **View Story Bible:** refresh the package list, select a package, and load its existing \`story_bible.json\`. The formatted JSON appears in a scrollable, read-only text area. Ctrl+A selects all and Ctrl+C copies the selection. Missing, malformed, or invalid top-level JSON is reported without writing to the file.

Implementation details:
- Added \`builder/story_bible_reader.py\`, which reads and validates a Story Bible without modifying it.
- Added \`tests/test_story_bible_reader.py\` for loading, non-modification, missing files, malformed JSON, and non-object JSON.
- Updated the app and README to document the new tab and its read-only behavior.
- Both automated workflows passed on implementation/handoff commit \`50518e3a31ff3ccb2604c136cf3aecf8741482c3\`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40835008109) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40835008114).
- **Live UI verification of the viewer is still pending.** The user previously confirmed the Create Novel tab worked on the Surface: title-to-folder suggestions, custom folder name, package creation, and correct \`story_bible.json\` plus \`Manuscript/Chapters/\` structure. The disposable \`~/Documents/MyNovel/My-Test-Folder\` package was removed after that test.

### Next laptop check

The app window already open on the Surface predates the viewer update. Close it, then run:

\`\`\`bash
cd ~/Documents/StoryBuilder && bash start_story_bible.sh
\`\`\`

The launcher synchronizes the current branch before starting the app. Then open **View Story Bible**, click **Refresh Novels**, select an existing package such as \`The-Long-Way-Home\`, and click **Load Story Bible**. Confirm that formatted JSON appears and can be selected/copied with Ctrl+A/Ctrl+C. This is a read-only check; do not create a test novel for it. Report any error text exactly. Keep the existing novels unchanged.

## Minimal Writer checkpoint

- Repository: \`~/Documents/StoryBuilder\`, GitHub \`tony21675/StoryBuilder\`, working branch \`redesign/simplified-writing-workflow\`.
- Launcher: \`cd ~/Documents/StoryBuilder && ./start.sh\`; it syncs the current branch and opens \`minimal_writer.py\`.
- Live-confirmed features include local GGUF model loading/writing, Continue append behavior, Write replacing visible prose while retaining model context, New Session clearing model conversation without changing the visible draft, stop/reload behavior, text open/save, novel/chapter/scene browsing, safe scene-copy loading, separately confirmed direct scene save, explicit novel-to-GitHub sync, selectable/copyable popups, and selected-passage revision with preview/accept.
- The user likes the focused revision pattern: highlight a passage, describe a change in plain English or provide exact replacement wording, inspect the proposal, then choose whether to apply it. Do not add lots of copy buttons; make text selectable/copyable instead.
- Do not reintroduce over-prescriptive writing rules, validators, or automatic story-state edits into the Minimal Writer. Keep work incremental.

## Protected novel data

- Main test novel: \`~/Documents/MyNovel/The-Long-Way-Home\`, GitHub \`tony21675/The-Long-Way-Home\`, branch \`main\`.
- Accepted Scene 10 is \`Manuscript/Chapters/Chapter_01/Chapter_01_Section_10.txt\`. Its prose and the novel's story state must not be modified or regenerated during app work.
- **Taken_at_Dusk has important saved content.** Preserve the two encrypted secret letters and all related local-only metadata, helper scripts, private key, and \`/secrets/\` ignore rule. Do not decrypt, display, copy, upload, or change them unless the author explicitly asks.
- The test package \`StoryBuilder_Save_Test_20261028\` and latest Story Bible test package \`My-Test-Folder\` were explicitly removed after their respective tests. No other novel package should be created or deleted without an explicit test plan.
- The current Story Bible viewer must only read \`story_bible.json\`; no editing or saving is included in this milestone.

## Working rules and preferences

- On the user's Linux machine, terminal commands must use \`python3\`, never \`python\`.
- Keep terminal instructions short and do one feature at a time.
- Discuss app or novel changes before making them; user-approved work and handoff-only updates are exceptions.
- Preserve accepted manuscripts. Do not blindly switch or delete Git branches. StoryBuilder should eventually have only \`main\` after a deliberate merge/cleanup; each novel repo should have its own branch.
- Keep all app text areas and popups selectable so Ctrl+A/Ctrl+C work; avoid cluttering the UI with many copy buttons.
- Model preference: retain Gemma 4 E4B as the current general-purpose writer. The author is separately exploring a second model for explicit adult erotica featuring consenting adults. Do not download/replace models or change model setup without discussion.
