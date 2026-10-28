# StoryBuilder handoff, current checkpoint

Date: October 28, 2026

## Current direction

Rebuild StoryBuilder piece by piece. The active app should load a local model and write without app-added story rules or story-management machinery. Keep the old code recoverable for now. Do not touch novel repositories or accepted prose.

## Minimal Writer baseline, confirmed on laptop

- `minimal_writer.py` is launched by `./start.sh`.
- Select a local GGUF model, load it, enter a prompt, write, then edit the output.
- Model loads with an empty system prompt; the user's prompt goes straight to `WriterEngine`.
- The user confirmed model generation and Save As output opening in an external text editor.
- Open Text, Save, and Save As were then tested live and reported working.
- The output editor shows the filename and an asterisk for unsaved edits. Opening a file or closing offers to save changes.
- UTF-8 text and newline state are preserved by the file helpers.
- Novels and saved story state have not been changed.

## New change: live text streaming

The next incremental feature is implemented in `minimal_writer.py`:
- Generated text is appended to the output as the local model emits it.
- Streaming callbacks are scheduled onto Tk's UI thread.
- Once generation completes, the engine's cleaned final response replaces the live preview.
- If generation fails, the app restores the previous document and its file/saved-text tracking.
- No app-added prompt or writing rules were introduced.

Automated coverage was updated to verify that the streaming callback is passed through and receives chunks. CI status for this newest change must be checked after the latest commits. The streaming feature still needs a live laptop test with the user's actual local model; CI cannot prove terminal echo filtering or GUI responsiveness.

## Next laptop test

After the current app window is closed, run:

```bash
cd ~/Documents/StoryBuilder && ./start.sh
```

Load the model and ask for a short passage. Confirm words appear before generation finishes, the final text looks normal without the prompt echoed into it, and editing/saving still work. Then try a second generation with an existing draft open only if the first test succeeds. A failed generation should restore the original draft.

## Still out of scope

No novel package loading, scene planning, character cards, continuity, writing rules, validators, state summaries, automatic reviews, or automatic state changes. Do not delete legacy modules until the new basic workflow is proven and their removal is discussed.

## Protected novel checkpoint

- Local package: `~/Documents/MyNovel/The-Long-Way-Home`.
- Remote: `tony21675/The-Long-Way-Home`, branch `main`.
- Accepted Chapter 1 Scene 10 prose: `Manuscript/Chapters/Chapter_01/Chapter_01_Section_10.txt`.
- Remote `current_state.json` remains at Scene 10; the after-state file is absent.
- Do not modify or regenerate Scene 10 during Minimal Writer testing.

## Working rules

Use `python3`, never `python`, in Linux laptop commands. Keep StoryBuilder on `redesign/simplified-writing-workflow` for now; do not switch or delete branches blindly. Discuss app/novel changes before making them, except handoff-only updates. Preserve accepted prose. Keep terminal steps short.
