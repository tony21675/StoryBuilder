# StoryBuilder, Minimal Writer

StoryBuilder is being rebuilt piece by piece. The current app keeps local-model writing simple and is beginning to restore the useful novel workflow around it. You can browse a novel's existing chapter and scene text and load a scene as a safe working copy, without automatic story rules or state changes.

## Start the app

From the Linux computer:

```bash
cd ~/Projects/StoryBuilder && ./start.sh
```

The launcher synchronizes `main` before starting the app. All StoryBuilder application development, testing, commits, and pushes happen directly on `main`; do not create or switch to feature or redesign branches.

The active Minimal Writer and Prepare Scene paths do not hard-code novel characters, settings, or plot rules. They read novel-specific information from the currently selected package's own Story Bible, character cards, locations, current state, and accepted manuscript. Shared Python prompts provide only general workflow guidance; a novel's special requirements belong in that novel's own files.

After the safe app-code pull, both launchers refresh a separate local mirror of the project handoffs in `~/Documents/Project_Handoff_Backups`. A successful Writer or Story Bible sync of a selected novel refreshes that mirror again. The mirror contains only named Markdown handoff and story-direction files, not manuscripts, model files, credentials, encrypted files, or secret-letter assets. Run `python3 ~/Projects/StoryBuilder/backup_handoffs.py` to refresh it manually. Set `STORY_HANDOFF_BACKUP_DIR` to use a different backup directory. The GitHub repositories remain authoritative; this folder is an independent local safety copy.

## App #2: Story Bible

Story Bible is a separate companion app. Start it from the repository folder with:

```bash
cd ~/Projects/StoryBuilder && bash start_story_bible.sh
```

The original Tkinter interface remains available through that launcher. A parallel PySide6 version is available for migration testing:

```bash
cd ~/Projects/StoryBuilder && ./start_story_bible_qt.sh
```

The Qt launcher uses the project's `.venv` and synchronizes `main` before launching. Install its UI dependency once with `.venv/bin/python -m pip install -r requirements-ui.txt`. The PySide6 launcher uses the project's `.venv`. On minimal Ubuntu/Mint installations, Qt may also need the system runtime libraries `libegl1`, `libgl1`, `libxcb-cursor0`, and `libxkbcommon-x11-0`; install them with `sudo apt install libegl1 libgl1 libxcb-cursor0 libxkbcommon-x11-0` if Qt reports a missing shared library. The Qt version uses the same Story Bible read/write helpers and novel-package format; it does not convert or rewrite existing novels merely by opening them. The original launcher remains the normal fallback until the Qt interface has passed desktop testing.

It currently has two tabs:

- **Create Novel:** enter a title and optionally customize the folder name. The app creates a new package under the configured novel library (`STORY_NOVEL_ROOT`, default `~/Documents/MyNovel`), with a `story_bible.json` based on the existing template and a `Manuscript/Chapters/` directory. New Story Bibles include empty `premise` and `setting` text fields. It never overwrites an existing destination, initializes Git, or invents story content. The Minimal Writer can discover the new package after **Refresh Novels**.
- **View Story Bible:** click **Refresh Novels**, select an existing package, and click **Load Story Bible** to display its formatted JSON in a scrollable text area. The entire tab scrolls vertically when its sections extend below the window, using the side scrollbar or mouse wheel. The JSON viewer itself is read-only and copyable with **Ctrl+A**, then **Ctrl+C**. Click **Edit Premise** or **Edit Setting** to open a separate text-editor window. **Manage Character Cards** opens a list of the entries referenced by the Story Bible. **Manage Locations** opens a separate add/edit/remove manager for the Story Bible's name-keyed locations object. Location Name is required; Type, Description, Geography, Climate, Notable Details, and optional custom fields can be left blank. Existing custom and nested details are preserved when untouched, and removing a location removes only that entry. Existing `.json` filename entries open their full character JSON files from the novel folder. The expanded editor uses plain-English tabs for Basic Information, Appearance, Background & Personality, Skills & Story, Relationships, and Additional Information. **Only Name is required**; age, gender, occupation, appearance, relationships, and other details are optional and may be left blank. Lists use one item per line. Relationship rows have an editable character dropdown populated from saved Character Cards, plus a plain-English description; names can still be typed manually when no card exists. Custom fields use ordinary field-name and value boxes. You never need to type JSON, commas, or brackets. **Save Character** writes the form back to the JSON file, while preserving untouched nested information and custom fields. **Add Character** creates a separate JSON file and adds its filename to the Story Bible. **Remove Selected** removes only the reference; it never deletes the source file. **Cancel Edit** discards the draft. Other fields remain untouched, including fields this app does not know about. Missing or malformed files are reported without being changed.
- **Sync Selected Novel to GitHub:** the View Story Bible tab has an explicit sync button for switching computers. It previews the selected novel's local folder, branch, configured remote, pending local commits, and changed files. Nothing runs until you click **Sync** in the confirmation. Sync fetches the remote, only fast-forwards when histories allow it, then commits/pushes the selected novel branch if needed. Diverged history, unresolved Git operations/conflicts, missing remotes/upstreams, and protected local secret/encrypted assets block the sync. This operates only inside the selected package's own Git repository, not StoryBuilder code. The ongoing `Story-Bible-Save-Test` fixture is deliberately blocked from syncing. New packages are not automatically made into Git repositories.
  
Genre and intended-audience choices come from reusable Markdown files in `profiles/genres/` and `profiles/audiences/`. The first heading in each file is the selector label and the remaining text is the model guidance. Adding a file adds a choice without a Python edit. A novel stores only its selected labels and the existing separate Explicit Adult Content setting; profile descriptions stay in the shared app repository. Both Prepare Scene and manuscript writing receive only the selected profiles. The audience guidance controls age-appropriate language and content, so Children's guidance explicitly excludes profanity. Explicit Adult Content is a separate permission, not something automatically enabled by choosing Adult.

Premise, Setting, and Canon Rules saves reread the Story Bible before applying their field-only updates. Character Card edits use a plain-English form but save to JSON internally; untouched fields and nested values are carried forward, and file replacement stops if the source changes during save. New cards are created as separate JSON files; removing a card from the list leaves its source file untouched. Editors use their own active text boxes rather than enabling typing in the read-only page. The separate top-level relationships object and story planning are not editable yet; character-to-character relationships are edited within each Character Card. Locations are edited separately through the name-keyed Locations manager. Character Cards and Canon Rules are reference notes only; the Minimal Writer does not enforce them.

To switch computers, sync the desired real novel on the current computer, then open Story Bible on the other computer and sync that same novel there. Keep the computers on the same GitHub repository and branch.

## Optional OpenRouter models

The Minimal Writer can use local GGUF models through llama.cpp or optional remote models through OpenRouter. Planner and Writer selections are independent, so either role can use a local model or an OpenRouter model. Mixed setups are supported, for example local Qwen planning with an OpenRouter writer, or the reverse. The original local workflow remains available without an OpenRouter account.

To enable OpenRouter, click **OpenRouter Settings**, enter an API key from [openrouter.ai/keys](https://openrouter.ai/keys), and choose **Save Key & Refresh Free Models**. StoryBuilder fetches the current free chat-model catalogue and caches it in the user's configuration folder. Use the settings button to refresh the list as OpenRouter adds, removes, or changes free models. The selectors include both individually pinned `:free` model IDs and OpenRouter's `openrouter/free` automatic free-model router. Pinned IDs keep the chosen model consistent; the automatic router may select a different eligible model on each request.

The key is stored outside the repository at `~/.config/storybuilder/openrouter_api_key` (or the equivalent `XDG_CONFIG_HOME` path) with owner-only file permissions. The `OPENROUTER_API_KEY` environment variable can be used instead. Credentials are not saved in novel folders, source files, prompt traces, or Git.

**Privacy:** When an OpenRouter model is selected, the prompt and any Story Bible, character, location, timeline, or preceding-scene context that StoryBuilder adds are sent to OpenRouter and the selected model provider. Provider data practices vary. Do not send private or secret material to a remote model. Local GGUF models continue to run on the computer and do not send prompts to OpenRouter.

OpenRouter's free-model availability, request limits, and provider capacity can change. A catalogue refresh updates the choices; it cannot guarantee that every listed provider is available at the moment of generation. When a remote model is unavailable or its free quota is exhausted, choose another listed model or switch that role back to a local GGUF model. There is no silent automatic switch from a selected remote model to a local one.

Remote calls are stateless in StoryBuilder: each request contains the prompt supplied for that operation, and the remote backend does not retain a server-side Writer conversation between calls. The app's Continue workflow includes the visible passage in its prompt. **New Session** remains available and clears the local Writer session when local models are selected.

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
15. Reads the selected novel's `story_bible.json` location entries during **Write**, **Continue**, and AI revision. Only locations whose full names appear in the current prompt or passage are added as plain-English reference context. The status line shows which saved locations were included; unrelated locations are left out.\n16. Starts with no novel selected. Switching to another novel clears the previous novel's scene directions and model conversation, while preserving the visible manuscript, its file path, and save tracking. If the conversation cannot be cleared, the model is stopped and reloaded fresh before further writing.
17. When a scene-writing prompt includes a non-empty `Natural endpoint:` line, adds a short generic reminder to write through that final beat and stop there. Prompts without an endpoint are unchanged; selected-passage revision is excluded.
18. When Prepare Scene has a previous saved scene, it receives the entire scene and anchors the plan to its final moment. Manuscript Write/Rewrite also receive the complete immediately preceding saved scene. The context is omitted when no earlier saved scene exists.
19. Prepare Scene retains its generic continuation guidance: preserve the immediate time, place, and active situation unless the author's direction requests a transition.

For automatic location context, include the saved location's full name in the scene prompt (or in the visible passage being continued). A scene that names two saved places can include both. Matching is case-insensitive but not fuzzy, so partial or ambiguous references do not pull in the wrong house.

The Writer uses relevant portions of the selected novel's own Story Bible, current scene state, character cards, and named location entries as short context where appropriate. Prepare Scene and manuscript Write/Rewrite also receive the full immediately preceding saved scene, rather than a short tail excerpt. Genre and audience guidance comes from shared profile files under `profiles/`; only the selected novel's profiles are added, and the novel itself stores only the selections. These reads do not modify novel files. Selected-passage revision changes only the marked text after explicit approval in the preview; it does not save automatically. Direct scene saving is protected by a path-specific confirmation. Novel-to-GitHub syncing requires a second explicit confirmation and operates only inside the selected novel's own Git repository, not StoryBuilder's code repository. It requires an existing `origin` and matching `origin/<current-branch>` upstream, creates no branches, and stops rather than merging if the local and remote histories have diverged. Local-only secret/encrypted paths found in Git's change list block syncing before staging or pushing. Local-only secret/encrypted paths found in Git's change list block syncing before staging or pushing. Prepare Scene is an opt-in planning helper that fills only the prompt box; it does not save or change manuscript files. Rewrite Scene is an explicit, confirmation-gated regeneration of the visible draft and restores the previous draft if canceled, stopped, or unsuccessful. The Writer does not run the former full continuity-analysis/validator workflow or automatically update story-state files.

## Local requirements

By default, StoryBuilder looks for:

- Models: `~/Documents/Models/*.gguf`
- llama.cpp executable: `~/Documents/llama.cpp/build/bin/llama-cli`

The resource root defaults to `~/Documents`, independently of where the StoryBuilder source checkout lives. This keeps Models, MyNovel, and llama.cpp in their existing locations when the repository is stored under `~/Projects`. `STORY_WORKSPACE_ROOT` can override the shared resource root; the more specific `STORY_MODELS_DIR`, `STORY_LLAMA_PATH`, and `STORY_NOVEL_ROOT` variables continue to override individual paths.

The launcher defaults to a 16,384-token context and 4,000 output tokens, configurable with `STORY_WRITER_CONTEXT` and `STORY_WRITER_MAX_TOKENS`.

## Rebuild status and test limits

The active UI is `minimal_writer.py` and reuses the existing `WriterEngine` with an empty system prompt. The full old application remains in the repository temporarily for recovery; `start.sh` opens Minimal Writer.

The author has confirmed live model generation, continuation, stopping, text-file open/save, Ctrl+A selection, and New Session on the Linux laptop. New Session was tested end to end: it preserved the visible draft, and an unrelated prompt produced a story that did not carry over the previous story's context.

Novel browsing and direct scene saving were tested live on the laptop. The author verified that Cancel leaves Scene 10 untouched, then confirmed a write against a separate disposable test scene and read back the exact saved text. The accepted Scene 10 was left untouched. The first live novel-to-GitHub sync was confirmed on The Long Way Home; the author ran `git -C ~/Documents/MyNovel/The-Long-Way-Home status -sb` and received `## main...origin/main`.

Prompt line breaks use llama-cli's `--multiline-input` and trailing `/` end-of-turn marker. Tests cover paragraph breaks, literal backslashes, returned prose, and streaming. Live checks confirmed paragraph breaks stay distinct, Windows-style paths retain single backslashes, literal `\\n` stays literal, and the prompt is not echoed. **Write** replaces visible text but retains model context; **Continue** appends new material using the visible passage ending as context. **New Session** clears the model conversation without reloading weights.

## Popup messages

Writer's popups use a scrollable, selectable text area. Long errors and confirmation summaries are capped to the available screen size rather than stretching from top to bottom. Click inside the message text, press **Ctrl+A**, then **Ctrl+C** to copy it. The message is read-only, and the copied text remains available after the popup closes. Confirmation dialogs preserve their **Yes**, **No**, and **Cancel** choices; safety-sensitive confirmations default to the non-destructive choice. Live visual verification passed on October 28, 2026: the author opened the long Sync Novel to GitHub confirmation and said the scrollable popup was “much better.” Keyboard copying has not been separately confirmed live.

## Data safety

The browser reads selected manuscript text without loading story state. **Save** and **Save As** never silently target the selected manuscript after a scene is loaded as a copy. **Save to Selected Scene** displays the exact target and requires confirmation; declining leaves the file untouched. Novel sync shows a preview and requires confirmation, uses a stash to temporarily protect local changes while attempting a fast-forward, restores the stash before committing, and refuses unresolved conflicts or diverged branches. If a push fails, any local commit is preserved. These Git safety paths are automated-tested, and the sync button has passed its first live test on The Long Way Home. The selected-passage revision workflow passed automated regression tests and live laptop testing: the author confirmed that both exact-text replacement and AI revision worked. Ordinary text files are saved as UTF-8, with the current file tracked and unsaved edits marked in the window title.


### LibreOffice Writer documents (ODT)

The Minimal Writer opens and saves both LibreOffice Writer `.odt` documents and legacy UTF-8 `.txt` files. ODT is the preferred Save As format. Bold and italic Markdown markers are shown as actual formatted text in the editor and are saved as real ODT character styles; when text is saved as TXT, portable Markdown markers are retained. The scene browser prefers an ODT scene when matching TXT and ODT files both exist, so converted manuscripts are not shown twice. Existing TXT files remain supported and are not automatically deleted or rewritten.


## App #1: PySide6 Writer migration test

The Writer now has a parallel PySide6 implementation for staged testing:

\`\`\`bash
cd ~/Projects/StoryBuilder && ./start_writer_qt.sh
\`\`\`

This is an additive migration build. The original Tkinter Writer remains available through \`./start.sh\` and \`minimal_writer.py\`. Do not remove or replace it until the Qt Writer has passed live model-generation, save/reopen, revision, trace, and novel-sync checks.

The initial Qt Writer build includes separate Planner and Writer selectors, model loading, novel/chapter/scene browsing, scene-cast selection, Prepare Scene with deterministic author-required-beat insertion, balanced/minimal/full prompt modes, streaming Write, Continue, confirmation-gated Rewrite, New Session, ODT/TXT open/save, new-scene saving, explicit selected-scene overwrite confirmation, and chapter/novel ODT assembly. It reuses the existing model engine, prompt/context builders, Story Bible schema, and manuscript helpers. Existing novel packages are not converted or rewritten by opening them.

This is not yet full feature parity. Selected-passage revision, Check Draft, prompt-trace capture/upload, OpenRouter key/catalogue management, the original detailed saved-scene state update, and selected-novel GitHub sync still need to be ported and tested. Treat the Qt Writer as a migration preview until those items are completed. Never use it as a reason to remove or bypass the original Writer's safety checks.
