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
6. Uses **New Session** to clear the model's conversation history without reloading the model or changing the visible draft.
7. Stops generation on request, keeping any partial text already generated. The local model process is ended and must be reloaded before writing again.
8. Opens UTF-8 text files into that editable area.
9. Saves to the currently open file, or uses Save As when untitled.
10. Saves As to a chosen destination and makes that the current file.
11. Warns before replacing a document or closing with unsaved output edits.

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

Prompt line breaks are sent as actual multiline input through llama-cli's interactive reader. The CLI's `--escape` option does not decode escape sequences for interactive user turns, so the Writer uses `--multiline-input` and its trailing `/` end-of-turn marker instead. Regression tests cover raw multiline submission, literal backslash sequences, returned prose, and streaming. The live exact-output check and longer scene-generation check both passed on the Linux laptop: paragraph breaks stayed distinct, the path `C:\models\drafts\scene.txt` retained single backslashes, the literal sequence `\n` stayed literal, and the prompt was not echoed. Ctrl+A is explicitly bound to Select All in both the prompt and output text boxes and has been confirmed working live. The next focused upgrade adds New Session: clear the model's conversation history with llama.cpp's `/clear` command while preserving visible output, prompt text, and file tracking. Automated tests cover both engine clearing and draft preservation. Both CI workflows passed for code/test commit `14a2075dc99bfe1f7294ec64be485c2d4fc5581a`: [Python tests #328](https://github.com/tony21675/StoryBuilder/actions/runs/40766994889) and [StoryBuilder tests #593](https://github.com/tony21675/StoryBuilder/actions/runs/40766994908). Live GUI verification is still needed after syncing. The remaining behavior is unchanged: streaming is best-effort while the engine filters the interactive prompt echo; the final cleaned response replaces the live preview when generation finishes. Write replaces the visible output without resetting the model session. Continue asks for only new material, includes the last 2,000 characters of the current output as context, and appends the response to the output. This also anchors it to the passage as edited in the text box. Stop ends the local model process, so it must be reloaded to continue; reloading starts a new model session.

## Data safety

The Minimal Writer does not open or alter novel repositories or novel state files. Text files are opened and changed only through explicit Open Text, Save, or Save As actions. Saving writes exactly the current output text as UTF-8. The currently open file is tracked, and unsaved output changes are marked in the window title.
