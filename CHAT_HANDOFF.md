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
- An author prompt field and Write button.
- Editable output.
- Open Text, Save, and Save As.
- Status line and filename/unsaved marker in the window title.

No novel package loader, scene planner, scene contract, continuity context, character cards, validator, state updater, or writer-notes process is invoked by the new UI.

## 3. Direct model path

File: `minimal_writer.py`.

- `load_model_for_writing(engine, model_path)` calls `engine.start(model_path, system_prompt="")`; there is no app-authored system prompt.
- `write_from_prompt(engine, prompt)` passes the prompt straight to `engine.generate(prompt)`.
- Uses the existing `WriterEngine` and `MODELS_DIR` only.
- Runs model loading/generation on a worker thread so the window can remain responsive.
- Keeps the current output visible while generation runs. A failed model response doesn't clear an existing draft.
- Do not infer the quality of live generation from CI alone; the real-model smoke test was performed separately.

Default environment:
- Models: `~/Documents/Models/*.gguf`
- llama.cpp: `~/Documents/llama.cpp/build/bin/llama-cli`
- `STORY_MODELS_DIR`, `STORY_LLAMA_PATH`, `STORY_WRITER_CONTEXT`, `STORY_WRITER_MAX_TOKENS` remain available as runtime overrides.

Known limitation to revisit only when required: the existing `WriterEngine.generate()` flattens newline characters in the prompt before sending it to the interactive llama.cpp process. It currently returns completed text to the output area rather than streaming partial text.

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

The current incremental step is for the user to sync/relaunch and test file editing with the actual desktop UI: open a text file, edit and Save, then Save As a second copy, reopen it, and verify in an external text editor. Don't add another feature until this basic document workflow works.

## 5. Rebuild boundaries

Do not delete old helper modules yet. They are currently dormant from the new UI's entry point. Once basic model writing and plain text editing are demonstrated reliably on the laptop, discuss and remove unused legacy code in planned pieces, with tests for each change.

Do not add the previous system back by accident. Specifically out of scope unless later requested:
- novel package management
- continuity summaries, clues, character state, or state update
- scene planning, Scene Idea parsing, or scene contracts
- semantic validators or automatic regeneration/review
- writing rules or hidden system prompts
- automatic manuscript file writes

The application should stay a simple writer until further pieces are agreed and proven.

## 6. Protected novel checkpoint: The Long Way Home

- Local: `~/Documents/MyNovel/The-Long-Way-Home`.
- Remote: `tony21675/The-Long-Way-Home`, permanent branch `main`.
- Accepted Chapter 1 Scene 10 is saved at `Manuscript/Chapters/Chapter_01/Chapter_01_Section_10.txt`.
- The remote state pointer remains Chapter 1, Scene 10. `Chapter_01_Section_10_after_state.json` is absent, so no transition to Scene 11 was saved.
- The latest model summary incorrectly sharpened Daniel's uncertain “maybe another hour” estimate into a near-certain critical-failure deadline, turned Morgan's hypothetical structural degradation into a diagnosis, and misdescribed Elena's instructions. The reviewer then returned unsupported claims and was correctly rejected by evidence validation.
- No change to accepted prose or novel state was made. Don't edit `current_state.json` manually, and don't bring old state-analysis workflow into the new Minimal Writer.

## 7. Repo / terminal / collaboration rules

- StoryBuilder repository: `~/Documents/StoryBuilder`.
- Current branch: `redesign/simplified-writing-workflow`; the remote currently has one branch. Long-term goal remains one stable `main` branch after deliberate review and merge; never switch/delete branches blindly.
- Use `python3`, never `python`, in Linux-laptop commands.
- Keep terminal instructions short, one command per step where practical.
- Discuss changes to app or novel packages first, except handoff-only updates.
- Preserve accepted text and saved story state.
- Update and prune handoffs at milestones.
