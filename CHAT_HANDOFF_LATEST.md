# StoryBuilder handoff, current checkpoint

Date: October 28, 2026

## Current direction

Rebuild StoryBuilder piece by piece. The active app should load a local model and write without app-added story rules or story-management machinery. Keep the old code recoverable for now. Do not touch novel repositories or accepted prose.

## Minimal Writer baseline, confirmed on laptop

- `minimal_writer.py` is launched by `./start.sh`.
- Select a local GGUF model, load it, enter a prompt, write, then edit the output.
- Model loads with an empty system prompt; the user's prompt goes straight to `WriterEngine`.
- The user confirmed model generation and Save As output opening in an external text editor.
- Open Text, Save, and Save As were tested live and reported working.
- The user has now confirmed live streaming works: generated words appear in the output as the model produces them.
- The output editor shows the filename and an asterisk for unsaved edits. Opening a file or closing offers to save changes.
- UTF-8 text and newline state are preserved by the file helpers.
- Novels and saved story state have not been changed.

## Live text streaming, verified

- Generated text is appended to the output as the local model emits it.
- Streaming callbacks are scheduled onto Tk's UI thread.
- When generation completes, the engine's cleaned final response replaces the live preview.
- If generation fails, the app restores the previous document and its file/saved-text tracking.
- No app-added prompt or writing rules were introduced.
- Unit tests cover forwarding the streaming callback and receiving chunks; the user has confirmed that words appear while generation is happening on the laptop.

## New piece: Stop Writing

A Stop Writing button and engine interruption path have been added, but have not yet been tested live on the laptop.

- Stop terminates the active `llama-cli` process without waiting for the generation lock.
- Any streamed partial text remains editable. If Stop is pressed before the first chunk, the previous document is restored.
- The model is marked unloaded after stopping and must be loaded again before the next generation.
- Automated tests cover prompt-thread-independent interruption and preservation of partial or prior text. Both workflows passed on commit `3e0e70d9`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40640287788) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40640287647). The stop behavior itself still needs the live laptop test.

Next laptop test, after closing the current app window:

```bash
cd ~/Documents/StoryBuilder && ./start.sh
```

Load the model, generate a longer passage, and press Stop while words are appearing. Confirm generation stops promptly, the partial text remains editable, and the app allows model reload followed by a new generation. Also try pressing Stop very soon after clicking Write to check that the previous text is not lost.

Do not add another feature until this test is complete.

## Still out of scope

No novel package loading, scene planning, character cards, continuity, writing rules, validators, state summaries, automatic reviews, or automatic state changes. Do not delete legacy modules until the replacement has been proven further and their removal is discussed.

## Protected novel checkpoint

- Local package: `~/Documents/MyNovel/The-Long-Way-Home`.
- Remote: `tony21675/The-Long-Way-Home`, branch `main`.
- Accepted Chapter 1 Scene 10 prose: `Manuscript/Chapters/Chapter_01/Chapter_01_Section_10.txt`.
- Remote `current_state.json` remains at Scene 10; the after-state file is absent.
- Do not modify or regenerate Scene 10 during Minimal Writer testing.

## Working rules

Use `python3`, never `python`, in Linux laptop commands. Keep StoryBuilder on `redesign/simplified-writing-workflow` for now; do not switch or delete branches blindly. Discuss app/novel changes before making them, except handoff-only updates. Preserve accepted prose. Keep terminal steps short.
