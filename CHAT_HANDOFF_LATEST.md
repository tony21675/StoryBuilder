# StoryBuilder handoff, current checkpoint

Date: October 28, 2026

## Direction

Rebuild StoryBuilder piece by piece. The active app should load a local model and write without app-added story rules or story-management machinery. Keep legacy code recoverable for now. Do not touch novel packages or accepted prose.

## Minimal Writer, confirmed on laptop

- Launched by `./start.sh`.
- The user confirmed local model writing, live text streaming, and opening/saving text files.
- `minimal_writer.py` loads the model with an empty system prompt and sends the author's writing prompt directly to `WriterEngine`.
- **Stop Writing was tested live and the user confirmed it worked.** Stopping terminates the local model process; reload the model before writing again.
- UTF-8 open/save helpers preserve text and final-newline state.
- No novel or saved story state has been changed.

## New piece: Continue

A separate **Continue** action has been implemented and tested live on the laptop. In the user's Tiffany/Kim test, the original passage remained and the continuation followed it without repeating the original. The user inserted “(Continued here)” manually as a visual marker to show me the boundary between Part 1 and Part 2; it was not model-generated text or an app issue.

- **Write** replaces the visible output, but deliberately keeps the current model session/context. The user likes that this lets a changed prompt pick up the story where the prior scene left off, even though the old prose is no longer visible. Do not reset/reload the model on Write unless the user later asks for a fresh-session option.
- **Continue** asks the model for only new material, includes up to the last 2,000 characters of the visible passage as context, and appends the response after a paragraph break. This anchors continuation to the text as edited in the output box.
- The existing passage remains in the output while more words stream in.
- The app's final cleaned response is appended to the saved-visible passage when generation completes.
- If continuation fails, the previous text and file tracking are restored.
- If Stop is pressed during continuation, the previous text plus any streamed continuation is kept. If no new text arrived, the previous document is restored.
- No hidden system prompt or broader writing rules were added.

Automated tests passed on commit `091280b0`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40641857573) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40641857583).

## Latest behavior confirmation

The user tested **Write** after a passage and Continue, then tested again with a changed prompt. Write replaces the visible output but preserves the current model session/context, so the model can carry the story forward from where the prior scene ended. The user explicitly likes this behavior. Keep it as intended: Write = replace visible prose while preserving ongoing model/story context; Continue = append new prose to the visible output. Do not implement a fresh-session reset for Write. A separate explicit “new session” action would be a future option only if requested.

Stop/reload behavior, Continue append behavior, and Write's replace/context-preserving behavior have all been confirmed live on the laptop. The regression test exercises two successive Write actions with changed prompts: visible output is replaced each time, while the fake engine session is not restarted and retains both prompts in its session history. Both CI workflows passed after the test double was completed: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40647067750) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40647067765). This milestone changes tests and documentation only, not runtime behavior.

## Read-only legacy dependency audit (October 28, 2026)

- The active launcher is `start.sh` → `sync.sh start` → `python3 minimal_writer.py`. The launcher does not run the old `storybuilder.py` interface.
- The Minimal Writer's project-code path is `minimal_writer.py` → `builder.writer_engine.WriterEngine` and `builder.workspace.MODELS_DIR`. The engine uses standard-library modules plus `pexpect`, the external `llama-cli` executable, and local GGUF model files.
- `WriterEngine` still has optional prompt-trace hooks, but Minimal Writer does not attach a trace object. The model is started with an empty system prompt. No StoryBuilder-added NSFW filter or writing-rule prompt is present.
- `builder.workspace` still contains legacy novel-discovery helpers, but Minimal Writer uses only `MODELS_DIR`; it does not load novel packages or story state.
- The legacy `storybuilder.py` remains in the repository and imports most of the old workflow modules. Those modules are not active through the Minimal Writer entry point, but they remain dependencies of the preserved legacy interface and/or its tests. Keep them until any removal is deliberately reviewed.
- Review candidate only: `builder/secret_letter.py` has no references found in `storybuilder.py`, the other `builder/*.py` files, or the test suite. No deletion was made; leave it in place until a later cleanup review.
- This was a read-only static audit. No application code, model configuration, branch, novel package, accepted prose, or novel state was changed.

## Out of scope

No novel package loading, scene planning, character cards, continuity system, writing rules, validators, state summaries, automatic reviews, or automatic state changes. Do not delete legacy modules until removal is discussed.

## Protected novel checkpoint

- Local: `~/Documents/MyNovel/The-Long-Way-Home`.
- Remote: `tony21675/The-Long-Way-Home`, branch `main`.
- Accepted Chapter 1 Scene 10 prose: `Manuscript/Chapters/Chapter_01/Chapter_01_Section_10.txt`.
- Remote `current_state.json` remains at Scene 10; the after-state file is absent.
- Do not modify or regenerate Scene 10 during Minimal Writer work.

## Working rules

Use `python3`, never `python`, in Linux terminal commands. Keep StoryBuilder on `redesign/simplified-writing-workflow` for now; do not switch or delete branches blindly. Discuss app or novel changes before making them, except handoff-only updates. Preserve accepted prose. Keep terminal steps short.
