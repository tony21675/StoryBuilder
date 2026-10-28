# StoryBuilder project handoff

Date: October 28, 2026

## 1. Agreed rebuild direction

The author decided to rebuild the app piece by piece, starting with the simplest useful thing: load a local model and write. Remove the old rule-heavy workflow from the active path. Do not add features back until the current layer has been verified on the author's laptop.

The active rebuild is explicitly authorized. Keep the old app code recoverable for now; do not touch novel repositories or accepted prose.

## 2. Minimal Writer works on the laptop

The normal launcher `./start.sh` runs `sync.sh start`, then starts `minimal_writer.py` with `python3`.

First live smoke test completed on October 28, 2026:
- The Minimal Writer window opened after launch.
- The user loaded their local model, submitted a short scene prompt, and received generated text.
- The user saved the output, then opened the saved text successfully in a separate text editor.

Current minimal UI has:
- GGUF model selector, Refresh, and Load Model.
- An author prompt field plus Write, Continue, and Stop Writing.
- Editable output that streams model text as it is generated.
- Open Text, Save, and Save As.
- Status line and filename/unsaved marker in the window title.

No novel package loader, scene planner, scene contract, continuity context, character cards, validator, state updater, or writer-notes process is invoked by the new UI.

## 3. Direct model path

File: `minimal_writer.py`.

- `load_model_for_writing(engine, model_path)` calls `engine.start(model_path, system_prompt="")`; there is no app-authored system prompt.
- `write_from_prompt(engine, prompt)` passes the prompt straight to `engine.generate(prompt)`.
- Uses the existing `WriterEngine` and `MODELS_DIR` only.
- Runs model loading/generation on a worker thread so the window can remain responsive.
- Streams generated text into the output area as the model writes. The prior document is held in memory during generation and restored if generation fails.
- Do not infer the quality of live generation from CI alone; the real-model smoke test was performed separately.

Default environment:
- Models: `~/Documents/Models/*.gguf`
- llama.cpp: `~/Documents/llama.cpp/build/bin/llama-cli`
- `STORY_MODELS_DIR`, `STORY_LLAMA_PATH`, `STORY_WRITER_CONTEXT`, `STORY_WRITER_MAX_TOKENS` remain available as runtime overrides.

Known limitations: `WriterEngine.generate()` flattens newline characters in the prompt before sending it to the interactive llama.cpp process. Streaming uses the existing prompt-echo filter and is best-effort; after completion, the cleaned final response replaces the live preview. Stop Writing terminates the local `llama-cli` process without waiting for the generation lock, keeps partial streamed text (or restores the previous document if no text arrived), and requires reloading the model. The user tested Stop live and confirmed it works.

## 4. Open Text / Save / Save As

Commit `1954d62be1aebbd62f2f8014201e01cdfe9a6089` adds:
- `Open Text…`: opens a UTF-8 text file into the editable output field.
- `Save`: writes to the current file; for untitled text it launches Save As.
- `Save As…`: writes to a chosen destination and sets that as the current file.
- Title displays the active filename; an asterisk indicates changes compared with the saved text.
- When opening another file or closing, the app offers to save dirty output first.
- Text file helpers round-trip Unicode and newline sequences exactly.

Tests added in `tests/test_minimal_writer.py` cover empty system prompt, direct prompt handoff, text round-trip, and preserving the final-newline state. CI results for code commit `f45e969c1f1bc433f30d7dcb84bfc53049c04ca6`:
- [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40636160718): passed.
- [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40636160677): passed.

The user has confirmed that the real model streams words into the output area while generating. The basic streaming milestone is verified on the laptop; prompt-echo cleanup and failure restoration are useful follow-up checks.

## 5. Live text streaming

The Minimal Writer now calls `WriterEngine.generate(prompt, on_delta=...)`. The stream callback schedules text appends onto Tk's UI thread. The completed cleaned answer replaces the preview when the model finishes. The app saves the prior document text and tracking metadata in memory and restores it if generation fails. The user confirmed that the real model streams words into the output as it generates. The user also tested Stop Writing live and confirmed that it stops generation.

## 6. Continue action

The Minimal Writer now includes a **Continue** button, and the user has confirmed the append behavior live on the laptop. **Write** replaces the visible output but preserves the current model session/context, so it can carry the story forward even when the prompt changes. The user tested this after Continue and likes this behavior; do not change Write to reset/reload the model unless they later request a fresh-session option. **Continue** sends a short continuation instruction with up to the last 2,000 characters of the current visible passage, appends a paragraph boundary to the existing output, then streams the response at the end. This anchors it to text the author may have edited. At completion the cleaned response is appended to the prior text. On generation failure, the original document is restored. If stopped, partial streamed continuation stays; if no chunks arrived, the original document is restored.

The user tested a comedic Tiffany/Kim passage: the first passage remained intact and the new writing followed it without repeating the whole original. The “(Continued here)” marker in the pasted sample was added manually by the user to show me where Part 1 ends and Part 2 begins, not generated by the model. Unit tests passed in commit `091280b0`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40641857573) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40641857583).

The user has confirmed all key behaviors live: **Write** replaces the visible prose while keeping the story context, including with a changed prompt; **Continue** appends new prose to what is visible; Stop halts generation and requires reloading. A regression test now exercises two Write actions with different prompts and asserts that output is replaced while the model session is not restarted and retains both prompts. This milestone changes tests and documentation only; the runtime app behavior is unchanged.

## 7. Rebuild boundaries

Do not delete old helper modules yet. They are currently dormant from the new UI's entry point. Once basic model writing and plain text editing are demonstrated reliably on the laptop, discuss and remove unused legacy code in planned pieces, with tests for each change.

Do not add the previous system back by accident. Specifically out of scope unless later requested:
- novel package management
- continuity summaries, clues, character state, or state update
- scene planning, Scene Idea parsing, or scene contracts
- semantic validators or automatic regeneration/review
- writing rules or hidden system prompts
- automatic manuscript file writes

The application should stay a simple writer until further pieces are agreed and proven.

## 8. Protected novel checkpoint: The Long Way Home

- Local: `~/Documents/MyNovel/The-Long-Way-Home`.
- Remote: `tony21675/The-Long-Way-Home`, permanent branch `main`.
- Accepted Chapter 1 Scene 10 is saved at `Manuscript/Chapters/Chapter_01/Chapter_01_Section_10.txt`.
- The remote state pointer remains Chapter 1, Scene 10. `Chapter_01_Section_10_after_state.json` is absent, so no transition to Scene 11 was saved.
- The latest model summary incorrectly sharpened Daniel's uncertain “maybe another hour” estimate into a near-certain critical-failure deadline, turned Morgan's hypothetical structural degradation into a diagnosis, and misdescribed Elena's instructions. The reviewer then returned unsupported claims and was correctly rejected by evidence validation.
- No change to accepted prose or novel state was made. Don't edit `current_state.json` manually, and don't bring old state-analysis workflow into the new Minimal Writer.

## 9. Repo / terminal / collaboration rules

- StoryBuilder repository: `~/Documents/StoryBuilder`.
- Current branch: `redesign/simplified-writing-workflow`; the remote currently has one branch. Long-term goal remains one stable `main` branch after deliberate review and merge; never switch/delete branches blindly.
- Use `python3`, never `python`, in Linux-laptop commands.
- Keep terminal instructions short, one command per step where practical.
- Discuss changes to app or novel packages first, except handoff-only updates.
- Preserve accepted text and saved story state.
- Update and prune handoffs at milestones.
