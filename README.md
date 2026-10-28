# StoryBuilder, Minimal Writer

StoryBuilder is being rebuilt piece by piece. The current version does two related jobs: load a local language model to generate text, and let you open, edit, and save ordinary text documents.

## Start the app

From the Linux laptop:

```bash
cd ~/Documents/StoryBuilder && ./start.sh
```

The launcher synchronizes the current StoryBuilder branch before starting the app.

## What this version does

1. Lists local GGUF models.
2. Loads the selected model.
3. Sends your writing prompt to the model without an app-added system prompt.
4. Streams generated text into the editable area as the model writes, then finalizes the cleaned response.
5. Uses **Write** to replace the visible prose while preserving the already-loaded model session/context, or **Continue** to append more text to the current visible passage. A changed prompt with Write can carry the story forward; it does not start a fresh model session.
6. Stops generation on request, keeping any partial text already generated. The local model process is ended and must be reloaded before writing again.
7. Opens UTF-8 text files into that editable area.
8. Saves to the currently open file, or uses Save As when untitled.
9. Saves As to a chosen destination and makes that the current file.
10. Warns before replacing a document or closing with unsaved output edits.

There is no novel package loading, scene planning, continuity tracking, state summary, automatic review, validator, or writing-rule prompt in the active UI. The interface is deliberately plain so the basic writing and file-editing path can be tested before any other features are considered.

## Local requirements

By default, StoryBuilder looks for:

- Models: `~/Documents/Models/*.gguf`
- llama.cpp executable: `~/Documents/llama.cpp/build/bin/llama-cli`

The paths can be changed through the existing environment variables in `builder/workspace.py`, including `STORY_MODELS_DIR` and `STORY_LLAMA_PATH`.

The launcher defaults to a 16,384-token context and 4,000 output tokens, configurable with `STORY_WRITER_CONTEXT` and `STORY_WRITER_MAX_TOKENS`.

## Rebuild status and test limits

The UI is in `minimal_writer.py`. It reuses the existing local-model `WriterEngine` and loads it with an empty system prompt. The full old application remains in the repository temporarily for recovery, but `start.sh` opens the Minimal Writer. Legacy features will be removed deliberately after the replacement's basic behavior is proven.

The author has confirmed live model generation and saved-output opening on the Linux laptop. Automated tests cover the direct model prompt path, UTF-8 text round-tripping, and a regression proving that repeated **Write** actions replace visible prose while preserving the loaded model session across changed prompts. The regression passed both automated workflows: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40647067750) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40647067765). These checks do not replace testing the full GUI manually.

Prompt line breaks are transported through llama-cli's escape handling so paragraph breaks are restored before tokenization; existing backslashes are escaped first so literal sequences are retained. Regression tests cover the encoded multiline input, returned prose, and streaming. This still needs a live GUI check with the local model after syncing the update. The remaining behavior is unchanged: Streaming is best-effort while the engine filters the interactive prompt echo; the final cleaned response replaces the live preview when generation finishes. Write replaces the visible output without resetting the model session. Continue asks for only new material, includes the last 2,000 characters of the current output as context, and appends the response to the output. This also anchors it to the passage as edited in the text box. Stop ends the local model process, so it must be reloaded to continue; reloading starts a new model session.

## Data safety

The Minimal Writer does not open or alter novel repositories or novel state files. Text files are opened and changed only through explicit Open Text, Save, or Save As actions. Saving writes exactly the current output text as UTF-8. The currently open file is tracked, and unsaved output changes are marked in the window title.
