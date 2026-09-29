# StoryBuilder

StoryBuilder is a small standalone desktop utility for creating and maintaining novel packages used by LocalStoryChat.

## First version

- Create a new novel package
- Open an existing novel package
- Edit title, premise, and basic story metadata
- Add, edit, and remove character cards
- Guided novel setup through a question-and-answer flow
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

The first version uses Python's standard library and Tkinter only.

## Roadmap

The guided setup flow now asks about the novel, characters, relationships, locations, and starting state, then writes the answers directly into the package. A small optional local LLM can later help interpret richer natural-language answers without becoming the source of truth for the package.
