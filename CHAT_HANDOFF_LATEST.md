# StoryBuilder current checkpoint — October 27, 2026

## Current urgent item: stop the stuck notes task and restart with the latest code

After the author applied the Scene 10 state update, StoryBuilder saved the updated novel state and recovery snapshot, advanced to Chapter 1, Scene 11, then started optional “temporary writing notes” learning. The app sat on that background task for roughly 30 minutes. The novel/state save happens before the notes review begins, so the accepted Scene 10 and applied state are already saved. The task can be stopped; at most, an unsaved editable Scene 11 idea could be lost and regenerated.

Remote code updates are on `redesign/simplified-writing-workflow`, but the app currently running on the laptop is still the old process. Close/terminate the stuck StoryBuilder process, then launch `./start.sh` from `~/Documents/StoryBuilder`; its `sync.sh start` pulls the updates safely. Run tests after syncing before relying on the new code.

## Speed changes committed to GitHub

- `45524e27550f05db21b4ea29785ba33e07bea156`: make automatic per-novel writing-note learning explicitly opt-in via `STORYBUILDER_AUTO_WRITER_NOTES=1`; default is OFF, so it no longer blocks ordinary accept/apply workflow.
- `f2f06799bc4dc0199259ad54f515448d9eafa013`: gate the notes task on that option. If deliberately enabled, it now uses a 6,144-token context, at most 350 output tokens, and a 180-second task timeout rather than inheriting the writer's 4,000-token default and one-hour generation timeout.
- `58f08f8444224ef2dda9efeac128707e903bfa45`: tests for default-off behavior, explicit opt-in, and bounded notes settings.
- `e54b77180d29190880cb0a30eedc5a449a86a1ce`: after a successful automatic Scene Idea suggestion, do not immediately reload the writer prompt. The next writing action will set its own task prompt; this avoids one needless model initialization. Manually requested suggestions preserve the prior restoration behavior.

These changes are remote and **not yet tested on the laptop**. Previous code checkpoint tests were 406 passed, but rerun the suite after pulling these commits. New changes have tests added, but do not claim they passed until verified.

## Model-reuse limitation

A single shared WriterEngine is used, but `reset_context()` starts a new `llama-cli` process. Tasks needing different system prompts therefore still reload the model. This update removes the worst optional 30-minute task and one redundant automatic-suggestion restore; it does **not** eliminate every reload. A deeper change would require a more substantial runtime refactor, such as a persistent model server with per-request system prompts. Avoid rushing that into the current session without tests.

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
