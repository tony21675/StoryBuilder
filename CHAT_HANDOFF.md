# StoryBuilder project handoff

Date: October 28, 2026

## 1. Current direction

The author explicitly requested a rebuild of StoryBuilder from a clean starting point: “it loads a model and writes nothing else to start with.” Treat the old feature set as out of scope unless the author adds features back later. The writing app should not impose its own scene rules or manage continuity behind the author's back.

Initial app work is authorized. Continue incrementally and preserve the old code until the replacement's basic local-model flow has passed a real laptop test.

## 2. Minimal Writer now launches by default

Commit `bb05e7b` added `minimal_writer.py`. It has only:
- a list of local GGUF models
- Load Model
- a prompt text box
- Write
- editable output
- Save Output As for a plain text file
- a small status line

Implementation boundary:
- `load_model_for_writing(engine, model_path)` invokes `engine.start(model_path, system_prompt="")`. No app-written system instructions.
- `write_from_prompt(engine, prompt)` passes the author's prompt straight to `WriterEngine.generate(prompt)`.
- The minimal UI does not import or call the novel package, scene contract, story planner, continuity context, state manager/reviewer, scene validators, or writer-notes workflow.
- It reuses only the existing local `WriterEngine` for llama.cpp model loading and generation, and `MODELS_DIR` for model discovery.
- Generated output is shown in an editable text field; saving is explicit, not automatic.
- Loading/generation run on a background thread so the UI can show status without freezing. Closing is deferred while the model is busy.

Launcher changes:
- `start.sh` still runs the existing safe code sync first, then starts `minimal_writer.py` with `python3`.
- No separate minimal launcher is retained.
- `tests/test_minimal_writer.py` tests that the loaded model gets an empty system prompt and the author's prompt is passed through unchanged.
- `tests/test_shell_sync.py` now asserts that the normal launcher starts the minimal writer.
- Both CI workflows passed on `d8690b9e1bce89ad0d38d667d2031be2193668ec`:
  - [Python tests run 40634415847](https://github.com/tony21675/StoryBuilder/actions/runs/40634415847)
  - [StoryBuilder tests run 40634415795](https://github.com/tony21675/StoryBuilder/actions/runs/40634415795)

These tests do not include the actual local model. This version has not yet been smoke-tested on the author's Linux laptop.

## 3. Immediate laptop smoke test

Run one command:

```bash
cd ~/Documents/StoryBuilder && ./start.sh
```

The launcher syncs the current branch before opening the Minimal Writer. The UI should let the author select/load a GGUF, enter a short writing prompt, generate text, edit it, and save it to a text file.

Test only that vertical slice. Do not introduce scene management, novel import, saved state, continuity, validators, rule prompts, or extra features until the author confirms the basic writer works. If any step fails, capture the exact error and repair that step only.

Runtime defaults:
- GGUF directory: `~/Documents/Models`
- llama.cpp executable: `~/Documents/llama.cpp/build/bin/llama-cli`
- model context default: 16,384
- maximum generation default from launcher: 4,000 tokens
- `STORY_MODELS_DIR`, `STORY_LLAMA_PATH`, `STORY_WRITER_CONTEXT`, and `STORY_WRITER_MAX_TOKENS` remain available as environment overrides where applicable.

Known limit to revisit only after a successful first test: the existing `WriterEngine.generate()` normalizes multiline user prompts to one line before sending them to the interactive llama.cpp session. The UI currently displays output when generation finishes instead of streaming partial text. No live-model claim should be made until tested locally.

## 4. Scope of the rebuild

`storybuilder.py` and its legacy helper modules remain in the repository so they can be recovered if needed. The normal launcher no longer opens that feature-heavy UI. This is a temporary safety measure during the incremental rebuild, not a plan to keep parallel apps indefinitely. Once the minimal writer succeeds on the laptop, assess the unused feature modules and remove them in deliberate, tested pieces. Do not restore legacy workflow behavior just because a module or test still exists.

Initial principles:
- No app-added writing rules or hidden story prompt.
- No automatic state changes or novel-package writes.
- No automatic generation/validation/revision loops.
- No background task that changes the manuscript.
- Keep the text writable by the author, and save only where the author chooses.
- Make no claims about the model's quality based only on unit tests.

## 5. Active novel, protected

Local path: `~/Documents/MyNovel/The-Long-Way-Home`
Remote: `tony21675/The-Long-Way-Home`, permanent branch `main`.

Accepted Chapter 1, Scene 10 is saved in:
`Manuscript/Chapters/Chapter_01/Chapter_01_Section_10.txt`

The remote `current_state.json` still points to Chapter 1, Scene 10, and `Chapter_01_Section_10_after_state.json` is missing. The most recent proposed state summary was inaccurate, and its reviewer returned unsupported findings; evidence validation discarded them. No state changes were saved.

The scene's confirmed endpoint: Elena orders immediate manual isolation of Delta-9; Daniel is told to run the protocol, Morgan monitors abnormal physical feedback, and Priya monitors crew stability. Daniel's “maybe another hour” is an uncertain estimate, not a guaranteed countdown. The IR observation is real within the prose, but its cause and significance are unresolved. The earlier silicate-like trace remains unverified and is not established as connected to the IR bleed.

Do not edit `current_state.json` manually, replace accepted prose, or resume the old analysis workflow during the initial minimal-writer test. The rebuild currently leaves this novel untouched.

## 6. Repository and collaboration rules

- StoryBuilder root: `~/Documents/StoryBuilder`.
- Current single development branch: `redesign/simplified-writing-workflow`. The remote currently has only that branch. Long-term branch target is one permanent `main` branch after deliberate merge/review, not blind switching or branch deletion.
- Use `python3`, never `python`, in commands for the author's Linux laptop.
- Prefer one short terminal command per step; avoid long copy/paste instructions.
- Discuss app/novel changes before making them; handoff-only updates don't need approval. The broad minimal rebuild is explicitly authorized.
- Update and prune handoffs after milestones.
- Preserve accepted manuscript content and saved state.
