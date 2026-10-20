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

## Active generation context and continuity archive

StoryBuilder separates what is needed in this scene from what must remain saved for later.

- **Active generation context:** Current state, opening physical continuity, relevant character cards and knowledge, author rules, relevant writer notes, and only supporting people referenced by the current scene. Incidental food/drink choices and routine details are deprioritized unless the scene explicitly asks about them.
- **Persistent continuity record:** The full saved state, character-knowledge ledger, character cards, relationship facts, writing guidance, clues, and unresolved story threads remain in the novel package. Context pruning changes the prompt view only; it does not delete or rewrite those records.
- **Searchable historical archive:** Existing accepted manuscript sections are searched on demand. A scene receives at most four short excerpts (up to 2,400 characters combined) that match words in its direction. Each excerpt identifies its manuscript source. Only sections earlier than the target are eligible; drafts and future/current scenes are not pulled in.
- **Authority and uncertainty:** Current saved state and current scene direction outrank old descriptions. Historical excerpts are evidence about the past, not instructions to reinstate stale physical state. When a detail cannot be found or the source is ambiguous, the Writer is told not to invent it or claim certainty.
- **Context accounting:** Writer status reports a before/after prompt-size estimate and number of historical excerpts. The estimate uses characters divided by four, so it is a repeatable rough estimate rather than exact tokenizer output. Prompt tracing, when deliberately armed, also records these measurements.

Retrieval is currently lexical rather than embedding-based: it works best when a scene idea names a person, object, event, or phrase associated with the historical detail. Full accepted prose remains the archive of record even when a detail is not retrieved. Tests cover pruning without persistent deletion, recovering a requested incidental drink, source labeling, excluding current/future scenes, current-state precedence, and estimated context reduction.

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

### Scene-specific Writer context and budget

The Writer builds its context from the current Scene Idea, current state, opening physical continuity, and scene-relevant knowledge instead of treating every consequential historical fact as relevant to every scene. In Scene Contract, the **Relevant Continuity (optional)** field lets the author pin earlier clues, promises, injuries, or conversations a scene must draw on. Leave it blank for automatic selection.

Before starting or writing a scene, StoryBuilder applies a conservative total-input budget to the complete system/reference prompt plus scene direction. It reserves the configured output budget and a safety margin, then removes low-priority notes/supporting references, compacts oversized character cards, and trims the lowest-ranked active knowledge facts as needed. Current scene state, opening physical continuity, author canon, and stable author guidance are protected. If those required materials still cannot fit, generation stops with a clear error rather than silently discarding them. Pruning affects only the transient prompt and never deletes source records or accepted prose.

Defaults: STORY_WRITER_CONTEXT=16384, STORY_WRITER_MAX_TOKENS=4000, and STORY_WRITER_CONTEXT_MARGIN=2400. The budget uses a conservative character-based estimate (three characters per estimated token), not the model's exact tokenizer. Writer status reports the input estimate, output reserve, margin, and pruned/compacted references.
