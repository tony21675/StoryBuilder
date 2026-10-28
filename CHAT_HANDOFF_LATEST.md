# StoryBuilder handoff, current checkpoint

Date: October 28, 2026

## Direction

Rebuild StoryBuilder piece by piece. The active app should load a local model and write without app-added story rules or story-management machinery. Keep legacy code recoverable for now. Do not touch novel packages or accepted prose.

## Minimal Writer, confirmed on laptop

- Launched by `./start.sh`.
- The user confirmed local model writing, live text streaming, and opening/saving text files.
- `minimal_writer.py` loads the model with an empty system prompt and sends the author's writing prompt directly to `WriterEngine`.
- **Stop Writing was tested live and the user confirmed it worked.** Stopping terminates the local model process; reload the model before writing again.
- UTF-8 open/save helpers preserve text and final-newline state.
- No novel or saved story state has been changed.

## New piece: Continue

A separate **Continue** action has been implemented in `minimal_writer.py`, but still needs its live laptop test.

- **Write** continues to replace the output with a new passage.
- **Continue** asks the current model conversation to continue from where it left off and appends the new response after a paragraph break.
- The existing passage remains in the output while more words stream in.
- The app's final cleaned response is appended to the saved-visible passage when generation completes.
- If continuation fails, the previous text and file tracking are restored.
- If Stop is pressed during continuation, the previous text plus any streamed continuation is kept. If no new text arrived, the previous document is restored.
- No hidden system prompt or broader writing rules were added.

Automated tests passed for this feature on commit `682a3556`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40641414447) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40641414419).

## Next laptop test

After finishing any current writing experiment, close the running app and run:

```bash
cd ~/Documents/StoryBuilder && ./start.sh
```

Load the model and generate a short passage. Click **Continue**. Confirm the original stays there and new text appears below it without repeating the whole passage. Then click **Write** with a new prompt and confirm it still replaces the output. Save the result if needed. Stop/reload behavior was already confirmed by the user, but make sure it still works if you interrupt a continuation.

Do not add more features until Continue is tested live.

## Out of scope

No novel package loading, scene planning, character cards, continuity system, writing rules, validators, state summaries, automatic reviews, or automatic state changes. Do not delete legacy modules until removal is discussed.

## Protected novel checkpoint

- Local: `~/Documents/MyNovel/The-Long-Way-Home`.
- Remote: `tony21675/The-Long-Way-Home`, branch `main`.
- Accepted Chapter 1 Scene 10 prose: `Manuscript/Chapters/Chapter_01/Chapter_01_Section_10.txt`.
- Remote `current_state.json` remains at Scene 10; the after-state file is absent.
- Do not modify or regenerate Scene 10 during Minimal Writer work.

## Working rules

Use `python3`, never `python`, in Linux terminal commands. Keep StoryBuilder on `redesign/simplified-writing-workflow` for now; do not switch or delete branches blindly. Discuss app or novel changes before making them, except handoff-only updates. Preserve accepted prose. Keep terminal steps short.
