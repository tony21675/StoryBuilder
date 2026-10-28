# StoryBuilder handoff, current checkpoint

Date: October 28, 2026

## Direction from the author

The app is being rebuilt piece by piece. The starting point is deliberately minimal: **load a local model and write, with no app-added writing rules or story-management workflow**. Add nothing else until this simple path is reliable.

## First minimal version

- `minimal_writer.py` is the new desktop UI: choose a local GGUF model, load it, enter a prompt, generate text, edit the output, and save it as a text file.
- The model is loaded with an empty system prompt (`system_prompt=""`). The app sends the author's prompt directly to the existing `WriterEngine`; it does not load a novel package, scene contract, character cards, prior state, validator, continuity summary, scene planner, or state updater.
- `start.sh` launches `minimal_writer.py` after the existing safe Git sync.
- The author has now confirmed that running `./start.sh` opens the Minimal Writer. The earlier confusing window problem is resolved.
- Both GitHub Actions workflows passed on commit `c2237337524abcc236329179ce7c97ce15059fdd`:
  - [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40634603660)
  - [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40634603671)

## Next test: local model generation

The window opens, but we have not yet confirmed that the local GGUF model loads, generates text, allows editing, and saves a text file.

Test only that basic path, one step at a time:
1. Select the usual GGUF and click Load Model.
2. If loading succeeds, enter a short prompt and click Write.
3. Confirm generated text appears in the editable output.
4. Edit a word and use Save Output As to save a text file.

If any step fails, capture the exact status/error and address only that step. Do not add story features until this path is reliable.

Launch command:
```bash
cd ~/Documents/StoryBuilder && ./start.sh
```

Default model folder: `~/Documents/Models`. Default runtime: `~/Documents/llama.cpp/build/bin/llama-cli`. Environment overrides remain supported in `builder/workspace.py`.

Known initial limitation: the existing interactive model engine flattens prompt line breaks to a single line before sending them to llama.cpp, and this first UI displays the answer after generation completes rather than streaming it. Do not expand the scope until the basic local-model test succeeds.

## Safe incremental rebuild

The old `storybuilder.py` and its helper modules remain in Git for recovery, but `./start.sh` now opens the minimal UI. Do not delete the legacy modules until the Minimal Writer has passed a real local-model test. Do not reintroduce continuity, scene contracts, validators, state summaries, automatic notes, or novel-package management without a separate discussion.

The novel manuscripts and their state files were not touched by this app change.

## Active novel recovery point

- Local novel: `~/Documents/MyNovel/The-Long-Way-Home`.
- Remote repository: `tony21675/The-Long-Way-Home`, branch `main`.
- Accepted Chapter 1, Scene 10 prose is saved at `Manuscript/Chapters/Chapter_01/Chapter_01_Section_10.txt`.
- Remote `current_state.json` still points to Chapter 1, Scene 10; `Chapter_01_Section_10_after_state.json` is absent. The latest flawed state proposal was rejected and **not saved**.
- Preserve Scene 10. Do not manually change `current_state.json`, regenerate the accepted scene, or resume state updates while the minimal writer is being established.

## Working rules

Use `python3`, never `python`, in Linux terminal commands. Keep one StoryBuilder development branch for now: `redesign/simplified-writing-workflow`; don't switch or delete branches blindly. Discuss app/novel changes before making them, except handoff updates. Preserve accepted prose.
