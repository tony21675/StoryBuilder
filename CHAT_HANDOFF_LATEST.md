# StoryBuilder handoff, current checkpoint

Date: October 28, 2026

## Direction from the author

The app is being rebuilt piece by piece. The starting point is deliberately minimal: **load a local model and write, with no app-added writing rules or story-management workflow**. Add nothing else until this simple path is reliable.

## First minimal version

- `minimal_writer.py` is the new desktop UI: choose a local GGUF model, load it, enter a prompt, generate text, edit the output, and save it as a text file.
- The model is loaded with an empty system prompt (`system_prompt=""`). The app sends the author's prompt directly to the existing `WriterEngine`; it does not load a novel package, scene contract, character cards, prior state, validator, continuity summary, scene planner, or state updater.
- `start.sh` now launches `minimal_writer.py` after its existing safe Git sync.
- Two focused unit tests cover the empty system prompt and direct prompt handoff. Both current GitHub Actions workflows passed on commit `d8690b9e1bce89ad0d38d667d2031be2193668ec`:
  - [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40634415847)
  - [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40634415795)

## What is not yet proven

The app has **not yet been smoke-tested with the author's local GGUF model**. CI confirms code/tests, not live text generation or GUI behavior.

Next step on the Linux laptop:
```bash
cd ~/Documents/StoryBuilder && ./start.sh
```
Expected: the Minimal Writer window, a model selector, a Load Model button, a prompt area, an editable output area, and Save Output As. First verify that the model loads, a short prompt generates text, the text can be edited, and Save Output As creates a readable text file. Report the exact error if any stage fails; don't add story features yet.

Default model folder: `~/Documents/Models`. Default runtime: `~/Documents/llama.cpp/build/bin/llama-cli`. Environment overrides remain supported in `builder/workspace.py`.

Known initial limitation: the existing interactive model engine flattens prompt line breaks to a single line before sending them to llama.cpp, and this first UI displays the answer after generation completes rather than streaming it. Don't expand the scope until the basic local test succeeds.

## Safe incremental rebuild

The old `storybuilder.py` and its helper modules remain in Git for recovery, but `./start.sh` no longer launches that feature-heavy UI. Do not delete the legacy modules until the minimal writer has been verified on the laptop. Do not reintroduce continuity, scene contracts, validators, state summaries, automatic notes, or novel-package management without a separate discussion.

The novel manuscripts and their state files were not touched by this app change.

## Active novel recovery point

- Local novel: `~/Documents/MyNovel/The-Long-Way-Home`.
- Remote repository: `tony21675/The-Long-Way-Home`, branch `main`.
- Accepted Chapter 1, Scene 10 prose is saved at `Manuscript/Chapters/Chapter_01/Chapter_01_Section_10.txt`.
- Remote `current_state.json` still points to Chapter 1, Scene 10; `Chapter_01_Section_10_after_state.json` is absent. The latest flawed state proposal was rejected and **not saved**.
- Preserve Scene 10. Do not manually change `current_state.json`, regenerate the accepted scene, or try to finish state updates while the minimal app is being established.

## Working rules

Use `python3`, never `python`, in Linux terminal commands. Keep one StoryBuilder development branch for now: `redesign/simplified-writing-workflow`; don't switch or delete branches blindly. Discuss app/novel changes before making them, except handoff updates. Preserve accepted prose.
