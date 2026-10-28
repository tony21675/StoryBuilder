# StoryBuilder handoff, current checkpoint

Date: October 28, 2026

## Current direction

The author explicitly chose to rebuild StoryBuilder piece by piece, starting with a local model loader and writing area. No app-added story rules or story-management machinery in the active writing path.

## Minimal Writer baseline, confirmed on laptop

- `minimal_writer.py` is the UI launched by `./start.sh`.
- Select a local GGUF model, click Load Model, enter a writing prompt, click Write, and edit the generated output.
- The model loads with an empty system prompt, and the user's prompt is sent straight to the existing `WriterEngine`.
- First live test worked: the local model generated a scene, and the output saved through Save As opened correctly in a separate text editor.
- Local test date: October 28, 2026.
- The former `storybuilder.py` UI and helper modules are retained for recovery; novels/state were not changed.

## Newly added document editing

Commit `1954d62` adds **Open Text**, **Save**, and **Save As…** to the Minimal Writer:
- Open Text loads a UTF-8 text file into the editable output field.
- Save updates the currently open file, or prompts for a filename if the document is untitled.
- Save As selects a different destination.
- The window title shows the active filename and an asterisk for unsaved edits.
- Opening another file or closing asks about unsaved changes.
- A failed generation no longer clears the text already in the output area.
- UTF-8, Unicode characters, and newline sequences are preserved by the file helpers.

Tests:
- [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40636160718) passed.
- [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40636160677) passed.
- They test source/unit behavior, not every live GUI interaction.

## Next laptop test

Sync/relaunch with one command:

```bash
cd ~/Documents/StoryBuilder && ./start.sh
```

Please test only the new file actions: open a saved text file, make a small edit, Save, then use Save As to create a second copy and reopen it. Verify the files in a text editor. Do not add other features until this file-editing loop works.

## Still out of scope

Do not add novel package loading, scene planning, character cards, continuity, rules, validators, state summaries, automatic reviews, or automatic state changes. The writer currently takes the prompt as supplied, without an app-added system prompt.

## Protected novel checkpoint

- Local package: `~/Documents/MyNovel/The-Long-Way-Home`.
- Remote: `tony21675/The-Long-Way-Home`, branch `main`.
- Accepted Chapter 1 Scene 10 prose is saved at `Manuscript/Chapters/Chapter_01/Chapter_01_Section_10.txt`.
- Remote `current_state.json` still points to Scene 10 and its `_after_state.json` is absent. The inaccurate proposal was not saved.
- Do not modify or regenerate Scene 10 during Minimal Writer testing.

## Working rules

Use `python3`, never `python`, in Linux laptop commands. Keep StoryBuilder on the current development branch for now, `redesign/simplified-writing-workflow`; do not switch or delete branches blindly. Discuss app/novel changes before making them, except handoff-only updates. Preserve accepted prose. Keep terminal steps short.
