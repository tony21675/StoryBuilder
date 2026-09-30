# StoryBuilder

StoryBuilder is a small standalone desktop utility for creating and maintaining novel packages used by LocalStoryChat.

## First version

- Create a new novel package
- Open an existing novel package
- Edit title, premise, and basic story metadata
- Add, edit, and remove character cards
- Guided novel setup through a reusable question-and-answer flow
- Optional story-planning fields with explicit room for undecided details
- Edit current chapter/scene state
- Make simple natural-language changes such as:
  - "Change Maya's age to 22"
  - "Change Tony's occupation to mechanic"
  - "Change the story title to The Long Road"
  - "Set the current chapter to 2"
- Validate the package before using it with LocalStoryChat
- Save directly in the shared novel-package format
- Preserve optional root-level JSON modules already present in a package

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

## Workspace storage

StoryBuilder can keep the entire local AI/story workspace on a separate drive.

Recommended layout:

```
StoryWorkspace/
├── StoryBuilder/
├── MyNovel/
├── LocalStoryChat/
├── Models/
└── llama.cpp/
```

The applications discover the workspace from their repository location. You can also override it with:

```
STORY_WORKSPACE_ROOT=/path/to/StoryWorkspace
```

Optional overrides are available for the model directory, llama-cli path, and novel directory with `STORY_MODELS_DIR`, `STORY_LLAMA_PATH`, and `STORY_NOVEL_ROOT`.

GitHub stores the source code and novel files. Large local AI assets such as GGUF models and the llama.cpp build stay on the workspace drive and are not committed to the repositories.

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
