# StoryBuilder current checkpoint — October 27, 2026

## Current urgent item: stop the stuck notes task and restart with the latest code

The live process list showed StoryBuilder PID 1516205 and `llama-cli` PID 1519167. The model prompt identifies a one-time startup writing-craft seed scan, not scene writing. It was launched because the notes file was blank; that startup path had not checked the intended default-off opt-in flag. The accepted Scene 10 and applied state were already saved. For the shown PIDs, send `kill -TERM 1519167` to interrupt only the child so the app can skip the scan and continue Writer startup; recheck PIDs first and do not kill the parent if recovering the current session. To apply the code fix, restart with `./start.sh` from `~/Documents/StoryBuilder` so the sync helper pulls the remote commits.

## Speed changes committed to GitHub

- `45524e27550f05db21b4ea29785ba33e07bea156`: make automatic per-novel writing-note learning explicitly opt-in via `STORYBUILDER_AUTO_WRITER_NOTES=1`; default is OFF, so it no longer blocks ordinary accept/apply workflow.
- `f2f06799bc4dc0199259ad54f515448d9eafa013`: gate the notes task on that option. If deliberately enabled, it now uses a 6,144-token context, at most 350 output tokens, and a 180-second task timeout rather than inheriting the writer's 4,000-token default and one-hour generation timeout.
- `58f08f8444224ef2dda9efeac128707e903bfa45`: tests for default-off behavior, explicit opt-in, and bounded notes settings.
- `e54b77180d29190880cb0a30eedc5a449a86a1ce`: after a successful automatic Scene Idea suggestion, do not immediately reload the writer prompt. The next writing action will set its own task prompt; this avoids one needless model initialization. Manually requested suggestions preserve the prior restoration behavior.
- `dcacdc590066bec7f1be65333a74db17709996be`: gate the separate initial startup seed scan on the same explicit opt-in. This fixes the missing guard that caused the current 30-minute task.
- `d7b9b25fa7a707529bcd05d615c474b8b1701385`: add regression coverage for default-off startup behavior.

GitHub Actions on `d7b9b25` passed both **Python tests** and **StoryBuilder tests**. The laptop is still running the old process and must sync/restart before using the fix. Re-run the local test suite after pulling; the older local checkpoint was 406 passed.

## Model-reuse limitation

A single shared WriterEngine is used, but `reset_context()` starts a new `llama-cli` process. Tasks needing different system prompts therefore still reload the model. The startup seed scan now honors the default-off flag, and the automatic Scene Idea path avoids one redundant restore; this does **not** eliminate every reload. If `STORYBUILDER_AUTO_WRITER_NOTES=1` is explicitly enabled, the startup seed scan still uses the general Writer timeout/token budget. A deeper model-session reuse redesign would require a separate, tested runtime change. Avoid rushing that architecture into the current session.

## The Long Way Home — Scene 10 accepted and applied

- Novel: `~/Documents/MyNovel/The-Long-Way-Home`; GitHub: `tony21675/The-Long-Way-Home`.
- Scene 10 was accepted. The false-positive completion finding that the team did not choose a strategy was rejected; the scene explicitly begins manual isolation.
- The Stage 2 state update was then applied and saved. Scene pointer advanced to Chapter 1, Scene 11.
- Current story handoff: Elena chose a manual, controlled isolation sequence on Sensor Node Delta-9. Daniel is to run the protocol, Morgan monitors physical feedback, and Priya monitors crew stability. Results and root cause are unresolved. Scene 11 should continue from this choice without replaying Scene 10.
- Preserve uncertainty around Daniel's “maybe another hour” estimate. Do not turn it into a certain one-hour countdown or declare isolation successful before prose shows what happens.
- The latest Stage 2 trace confirmed the state-review warning fix live: reviewer returned two findings, both failed evidence validation, trace recorded the warning, and the author confirmed it appeared in the writer status line. Strict evidence checking stayed intact; no auto-application occurred.
- Latest private trace: https://github.com/tony21675/StoryBuilder-Traces/blob/main/prompt_trace.json. It contains story text; do not share publicly.

## Project state and rules

- StoryBuilder repo: `~/Documents/StoryBuilder`; GitHub `tony21675/StoryBuilder`; active branch `redesign/simplified-writing-workflow`.
- Use `python3`, never `python`, in laptop terminal commands. One command per message; no huge copy/paste requests.
- Inspect code/traces directly on GitHub when possible. Discuss before app or novel-package changes; handoff updates are fine without permission.
- Preserve accepted prose and saved novel state. Apply state only with explicit author approval.
- Story first, flexible prose; avoid checklist writing and don't rewrite text just to appease false-positive reviewers.
- Long-term branch goal: one `main` branch after deliberate review/merge; don't switch or delete branches blindly. One branch per novel repository.
