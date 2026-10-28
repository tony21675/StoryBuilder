# StoryBuilder, Minimal Writer

StoryBuilder is being rebuilt piece by piece. The current app keeps local-model writing simple and is beginning to restore the useful novel workflow around it. You can browse a novel's existing chapter and scene text and load a scene as a safe working copy, without automatic story rules or state changes.

## Start the app

From the Linux laptop:

```bash
cd ~/Documents/StoryBuilder && ./start.sh
```

The launcher synchronizes the current StoryBuilder branch before starting the app.

## What this version does

1. Lists local GGUF models and loads the selected model.
2. Sends your writing prompt to the model without an app-added system prompt.
3. Streams generated text into the editable area as the model writes, then finalizes the cleaned response.
4. Uses **Write** to replace visible prose while preserving the current model session/context, or **Continue** to append more text to the visible passage.
5. Uses **New Session** to clear model conversation history without reloading the model or changing the visible draft.
6. Stops generation on request, keeping any partial text already generated. The model process must be reloaded before writing again.
7. Lists novel packages found in `STORY_NOVEL_ROOT` (default `~/Documents/MyNovel`), then lets you choose a chapter and saved scene.
8. Uses **Load Scene Copy** to read the selected numbered scene `.txt` file into the editable area.
9. Keeps the accepted source scene out of the Save target. After loading a scene copy, **Save** opens **Save As**, so the original scene is not silently overwritten.
10. Opens other UTF-8 text files, saves ordinary drafts, and warns before replacing a document or closing with unsaved output edits.

The novel browser is intentionally read-first. It does not load or modify `current_state.json`, before/after state JSON, character cards, or other novel data. Direct saving back into a selected manuscript scene and novel-to-GitHub syncing have **not** been restored yet. Those will be separate steps after the browser is verified on the laptop. Scene planning, continuity analysis, validators, automatic review, and automatic state changes remain outside the active Writer.

## Local requirements

By default, StoryBuilder looks for:

- Models: `~/Documents/Models/*.gguf`
- llama.cpp executable: `~/Documents/llama.cpp/build/bin/llama-cli`

The paths can be changed through the existing environment variables in `builder/workspace.py`, including `STORY_MODELS_DIR`, `STORY_LLAMA_PATH`, and `STORY_NOVEL_ROOT`.

The launcher defaults to a 16,384-token context and 4,000 output tokens, configurable with `STORY_WRITER_CONTEXT` and `STORY_WRITER_MAX_TOKENS`.

## Rebuild status and test limits

The active UI is `minimal_writer.py` and reuses the existing `WriterEngine` with an empty system prompt. The full old application remains in the repository temporarily for recovery; `start.sh` opens Minimal Writer.

The author has confirmed live model generation, continuation, stopping, text-file open/save, Ctrl+A selection, and New Session on the Linux laptop. New Session was tested end to end: it preserved the visible draft, and an unrelated prompt produced a story that did not carry over the previous story's context.

The first novel-browser slice is implemented in commit `bf4e4f81709466f450739cdcb38906736e171dd0`. Automated workflows passed: [Python tests #342](https://github.com/tony21675/StoryBuilder/actions/runs/40773141944) and [StoryBuilder tests #607](https://github.com/tony21675/StoryBuilder/actions/runs/40773141964). The browser's live GUI behavior still needs to be checked on the laptop. Tests cover package discovery, numeric chapter/scene ordering, exclusion of state JSON files, and loading a scene as a copy without changing the source file.

Prompt line breaks use llama-cli's `--multiline-input` and trailing `/` end-of-turn marker. Tests cover paragraph breaks, literal backslashes, returned prose, and streaming. Live checks confirmed paragraph breaks stay distinct, Windows-style paths retain single backslashes, literal `\n` stays literal, and the prompt is not echoed. **Write** replaces visible text but retains model context; **Continue** appends new material using the visible passage ending as context. **New Session** clears the model conversation without reloading weights.

## Data safety

The browser reads only the selected scene's plain-text manuscript file. Loading a scene does not set that source as the current save target; the initial **Save** action opens **Save As**. The app does not edit novel state files or sync the novel repository to GitHub yet. Ordinary text files are saved as UTF-8, with the current file tracked and unsaved edits marked in the window title.
