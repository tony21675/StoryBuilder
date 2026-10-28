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
4. Shows the result in an editable text area.
5. Opens UTF-8 text files into that editable area.
6. Saves to the currently open file, or uses Save As when untitled.
7. Saves As to a chosen destination and makes that the current file.
8. Warns before replacing a document or closing with unsaved output edits.

There is no novel package loading, scene planning, continuity tracking, state summary, automatic review, validator, or writing-rule prompt in the active UI. The interface is deliberately plain so the basic writing and file-editing path can be tested before any other features are considered.

## Local requirements

By default, StoryBuilder looks for:

- Models: `~/Documents/Models/*.gguf`
- llama.cpp executable: `~/Documents/llama.cpp/build/bin/llama-cli`

The paths can be changed through the existing environment variables in `builder/workspace.py`, including `STORY_MODELS_DIR` and `STORY_LLAMA_PATH`.

The launcher defaults to a 16,384-token context and 4,000 output tokens, configurable with `STORY_WRITER_CONTEXT` and `STORY_WRITER_MAX_TOKENS`.

## Rebuild status and test limits

The UI is in `minimal_writer.py`. It reuses the existing local-model `WriterEngine` and loads it with an empty system prompt. The full old application remains in the repository temporarily for recovery, but `start.sh` opens the Minimal Writer. Legacy features will be removed deliberately after the replacement's basic behavior is proven.

The author has confirmed live model generation and saved-output opening on the Linux laptop. Automated tests also cover the model prompt path and UTF-8 text file round-tripping. They do not replace testing the full GUI manually.

Known limitation: the current shared engine flattens line breaks in the prompt before sending it to the interactive model session. Revisit only if this affects the writing workflow.

## Data safety

The Minimal Writer does not open or alter novel repositories or novel state files. Text files are opened and changed only through explicit Open Text, Save, or Save As actions. Saving writes exactly the current output text as UTF-8. The currently open file is tracked, and unsaved output changes are marked in the window title.
