# StoryBuilder

StoryBuilder is a small standalone desktop utility for creating and maintaining novel packages used by LocalStoryChat.

## First version

- Create a new novel package
- Open an existing novel package
- Edit title, premise, and basic story metadata
- Add, edit, and remove character cards
- Guided novel setup through a reusable question-and-answer flow
- Optional story-planning fields with explicit room for undecided details
- Conversational scene planning with proposal review and targeted updates to STORY_PLAN.md
- Edit current chapter/scene state
- Make simple natural-language changes such as:
  - "Change Maya's age to 22"
  - "Change Tony's occupation to mechanic"
  - "Change the story title to The Long Road"
  - "Set the current chapter to 2"
- Validate the package before using it with LocalStoryChat
- Save directly in the shared novel-package format
- Preserve optional root-level JSON modules already present in a package

## Ending-state review redesign

Ending-state analysis is designed to be reviewed as a **change proposal**, not a full rewrite of the novel's state ledger.

- The default review tab groups only detected additions, removals, and changes by situation/time, physical continuity, character knowledge, investigative leads, recent events, and other state.
- The full reconstructed JSON remains available in **Full State JSON (Advanced)** for deliberate corrections. Applying still validates and merges against the saved current state; omitted fields are preserved.
- The ending-state LLM receives a compact context focused on the scene cast, immediate physical continuity, active objectives, clues, unresolved questions, and a short recent-event window. The accepted scene is supplied once instead of repeating its final excerpt.
- Character-knowledge auditing now asks for a bounded set of new facts and explicit supersessions. Existing knowledge remains in the application-owned ledger and is merged rather than regenerated from scratch.
- Regression tests cover compact context filtering, bounded/relevance-ranked knowledge context, grouped change summaries, empty diffs, and output caps.

This reduces prompt bloat and review noise; it does not make LLM proposals infallible. Read the change list before applying, and use the advanced JSON only when an actual correction is required.

## Shared package format

A novel package is a folder containing:

```
Novel_Name/
├── story_bible.json
├── current_state.json
├── Tony.json
├── Tiffany.json
└── ...
```

The shared format is versioned with `story_format_version: "1.0"`. This gives LocalStoryChat and StoryBuilder a stable interface and leaves room for future migrations.

## Separate novel repositories

StoryBuilder is the reusable application. Novel data belongs in a separate repository for each novel.

Recommended layout:

```
StoryWorkspace/
├── StoryBuilder/
├── MyNovel/
├── AnotherNovel/
├── Models/
└── llama.cpp/
```

Each novel directory is its own Git repository. StoryBuilder does not need to know the GitHub repository name or URL. It opens the selected novel folder and, when you use **Sync Novel** or **Close & Sync**, commits, rebases against `origin`, and pushes that novel repository only.

The StoryBuilder repository and the novel repository are synchronized independently:

```
StoryBuilder/
    app code and reusable logic

MyNovel/
    one novel's canon, state, guidance, and manuscript

AnotherNovel/
    another novel's canon, state, guidance, and manuscript
```

This prevents novel-specific files from becoming part of the reusable StoryBuilder project.

The **Open Novel** button can open any valid novel package, so additional novels do not require changes to StoryBuilder.

## Workspace storage

StoryBuilder can keep the entire local AI/story workspace on a separate drive.

Recommended layout:

```
StoryWorkspace/
├── StoryBuilder/
├── MyNovel/
├── AnotherNovel/
├── Models/
└── llama.cpp/
```

The applications discover the workspace from their repository location. You can also override it with:

```
STORY_WORKSPACE_ROOT=/path/to/StoryWorkspace
```

Optional overrides are available for the model directory, llama-cli path, and novel directory with `STORY_MODELS_DIR`, `STORY_LLAMA_PATH`, and `STORY_NOVEL_ROOT`.

By default, `STORY_NOVEL_ROOT` now points to the workspace-level `MyNovel/`, not a folder inside the StoryBuilder repository. Large local AI assets such as GGUF models and the llama.cpp build stay on the workspace drive and are not committed to the repositories.

## Optional private prompt trace sync

The Writer tab's **Trace Next Scene** control captures one generation and validator run for debugging. When tracing is armed, StoryBuilder saves the trace locally to `~/.local/share/storybuilder/prompt_trace.json` and uploads it to a private GitHub repository named `StoryBuilder-Traces` owned by the authenticated GitHub account.

- The upload happens only for a deliberately armed trace; ordinary scene generation does not collect or upload traces.
- StoryBuilder checks that the target repository is private and refuses to upload if it contains files other than `prompt_trace.json`.
- Authentication uses `STORYBUILDER_TRACE_GITHUB_TOKEN`, `GH_TOKEN`, or `GITHUB_TOKEN` when present, otherwise the token from GitHub CLI authentication (`gh auth token`). Never commit tokens.
- To use a different destination, set `STORYBUILDER_TRACE_GITHUB_REPO=owner/repository`.
- Each subsequent upload replaces the branch with a new root commit containing only the latest trace, so old traces do not appear in the branch's visible commit history. This is not a secure-erasure guarantee for unreachable Git objects.
- If upload fails, the local trace is preserved and StoryBuilder reports the error without changing the generated draft.

Traces can contain unpublished story text, prompts, and local runtime details. Keep the destination private and arm tracing only when diagnostic capture is needed.

## Run

From the project directory:

```bash
python3 storybuilder.py
```

Or, after making the launcher executable:

```bash
chmod +x start.sh
./start.sh
```

The desktop interface uses Python's standard library and Tkinter. The integrated local writer uses the Python `pexpect` package.

## Roadmap

The guided setup flow now asks about the novel, characters, relationships, locations, and starting state, then writes the answers directly into the package. A small optional local LLM can later help interpret richer natural-language answers without becoming the source of truth for the package.
