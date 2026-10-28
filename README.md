# StoryBuilder, Minimal Writer

StoryBuilder is being rebuilt piece by piece. The current starting version does one job: load a local language model and let you write with it.

## Start the app

From the Linux laptop:

```bash
cd ~/Documents/StoryBuilder && ./start.sh
```

The launcher synchronizes the current StoryBuilder branch before starting the app.

## What this first version does

1. Lists local GGUF models.
2. Loads the selected model.
3. Sends your writing prompt to the model without adding an app-written system prompt.
4. Shows the result in an editable text area.
5. Saves the text to a file you choose.

There is no novel package loading, scene planning, continuity tracking, state summary, automatic review, validator, or writing-rule prompt in the active UI. The initial UI is intentionally plain so the writing path can be tested before features are considered.

## Local requirements

By default, StoryBuilder looks for:

- Models: `~/Documents/Models/*.gguf`
- llama.cpp executable: `~/Documents/llama.cpp/build/bin/llama-cli`

The paths can be changed through the existing environment variables in `builder/workspace.py`, including `STORY_MODELS_DIR` and `STORY_LLAMA_PATH`.

The launcher defaults to a 16,384-token context and 4,000 output tokens, configurable with `STORY_WRITER_CONTEXT` and `STORY_WRITER_MAX_TOKENS`.

## Rebuild status and test limits

The first UI is in `minimal_writer.py`. It reuses the existing local-model `WriterEngine` and loads it with an empty system prompt. The full old application remains in the repository temporarily for recovery, but `start.sh` now opens the Minimal Writer. Legacy features will be removed deliberately after the replacement's basic behavior is proven.

GitHub Actions test the source and unit tests, but they do not run the author's local model. A real laptop smoke test must verify that the model loads, produces text, allows editing, and saves the output. The current shared engine also flattens line breaks in the submitted prompt before sending it to the interactive model session; this limitation is recorded for later review.

## Data safety

This initial app does not open or alter novel repositories or novel state files. Saving output is an explicit action to a text file path chosen by the author. Existing manuscripts and story packages are left untouched.
