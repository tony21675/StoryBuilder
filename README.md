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
9. Keeps the accepted source scene out of the ordinary Save target. After loading a scene copy, **Save** opens **Save As**.
10. Provides **Save to Selected Scene**, a separate action that displays the exact file path and requires confirmation before replacing that scene. Cancel leaves the file unchanged.
11. Provides **Sync Novel to GitHub** as an explicit, separate action. It shows the selected novel folder, branch, remote, local changes, and local commits before confirmation. It safely fast-forwards when possible, commits the novel's local changes, and pushes only that novel's branch.
12. Uses compact popups for short messages and a scrollable, read-only text box for long messages and confirmations. Popup text can be selected and copied with **Ctrl+A**, then **Ctrl+C**.
13. Opens other UTF-8 text files, saves ordinary drafts, and warns before replacing a document or closing with unsaved output edits.
14. Highlights a sentence or paragraph, then either asks the AI for a plain-English revision or provides exact replacement wording. The proposed passage is previewed and editable before **Use Revision** applies it; **Keep Original** leaves it untouched.

The Writer does not load or modify `current_state.json`, before/after state JSON, character cards, or other novel state files as part of ordinary writing or syncing. Selected-passage revision changes only the marked text after explicit approval in the preview; it does not save automatically. Direct scene saving is protected by a path-specific confirmation. Novel-to-GitHub syncing requires a second explicit confirmation and operates only inside the selected novel's own Git repository, not StoryBuilder's code repository. It requires an existing `origin` and matching `origin/<current-branch>` upstream, creates no branches, and stops rather than merging if the local and remote histories have diverged. Local-only secret/encrypted paths found in Git's change list block syncing before staging or pushing. Scene planning, continuity analysis, validators, automatic state changes, and whole-scene automatic rewrites remain outside the active Writer.

## Local requirements

By default, StoryBuilder looks for:

- Models: `~/Documents/Models/*.gguf`
- llama.cpp executable: `~/Documents/llama.cpp/build/bin/llama-cli`

The paths can be changed through the existing environment variables in `builder/workspace.py`, including `STORY_MODELS_DIR`, `STORY_LLAMA_PATH`, and `STORY_NOVEL_ROOT`.

The launcher defaults to a 16,384-token context and 4,000 output tokens, configurable with `STORY_WRITER_CONTEXT` and `STORY_WRITER_MAX_TOKENS`.

## Rebuild status and test limits

The active UI is `minimal_writer.py` and reuses the existing `WriterEngine` with an empty system prompt. The full old application remains in the repository temporarily for recovery; `start.sh` opens Minimal Writer.

The author has confirmed live model generation, continuation, stopping, text-file open/save, Ctrl+A selection, and New Session on the Linux laptop. New Session was tested end to end: it preserved the visible draft, and an unrelated prompt produced a story that did not carry over the previous story's context.

Novel browsing and direct scene saving were tested live on the laptop. The author verified that Cancel leaves Scene 10 untouched, then confirmed a write against a separate disposable test scene and read back the exact saved text. The disposable test package was removed afterwards. The first live novel-to-GitHub sync was then confirmed on The Long Way Home; the author ran `git -C ~/Documents/MyNovel/The-Long-Way-Home status -sb` and received `## main...origin/main`, showing the local working tree clean and aligned with its recorded upstream. Automated tests cover sync behavior using disposable Git repositories, including commit/push, remote fast-forward, diverged histories, and protected secret paths.

Prompt line breaks use llama-cli's `--multiline-input` and trailing `/` end-of-turn marker. Tests cover paragraph breaks, literal backslashes, returned prose, and streaming. Live checks confirmed paragraph breaks stay distinct, Windows-style paths retain single backslashes, literal `\n` stays literal, and the prompt is not echoed. **Write** replaces visible text but retains model context; **Continue** appends new material using the visible passage ending as context. **New Session** clears the model conversation without reloading weights.

## Popup messages

Writer's popups use a scrollable, selectable text area. Long errors and confirmation summaries are capped to the available screen size rather than stretching from top to bottom. Click inside the message text, press **Ctrl+A**, then **Ctrl+C** to copy it. The message is read-only, and the copied text remains available after the popup closes. Confirmation dialogs preserve their **Yes**, **No**, and **Cancel** choices; safety-sensitive confirmations default to the non-destructive choice. Live visual verification passed on October 28, 2026: the author opened the long Sync Novel to GitHub confirmation and said the scrollable popup was “much better.” Keyboard copying has not been separately confirmed live.

## Data safety

The browser reads selected manuscript text without loading story state. **Save** and **Save As** never silently target the selected manuscript after a scene is loaded as a copy. **Save to Selected Scene** displays the exact target and requires confirmation; declining leaves the file untouched. Novel sync shows a preview and requires confirmation, uses a stash to temporarily protect local changes while attempting a fast-forward, restores the stash before committing, and refuses unresolved conflicts or diverged branches. If a push fails, any local commit is preserved. These Git safety paths are automated-tested, and the sync button has passed its first live test on The Long Way Home. The selected-passage revision workflow passed automated regression tests and live laptop testing: the author confirmed that both exact-text replacement and AI revision worked. Ordinary text files are saved as UTF-8, with the current file tracked and unsaved edits marked in the window title.
