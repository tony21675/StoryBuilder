# StoryBuilder current checkpoint — October 27, 2026

## Current checkpoint: preserve the Scene 11 draft, then sync the verified fixes

The old PID snapshot (StoryBuilder 1516205 / `llama-cli` 1519167) is stale; do not signal those PIDs without checking the current process list. The latest Scene 11 trace completed at 2026-10-27 22:43:59 UTC. Scene 11 is generated for author review but not accepted. Preserve any draft held only in the UI before restarting the app. Then launch `./start.sh` from `~/Documents/StoryBuilder` to pull the commits below. Sync is fast-forward-only.


## Speed changes committed to GitHub

- `45524e27550f05db21b4ea29785ba33e07bea156`: optional writing-notes learning is default OFF.
- `f2f06799bc4dc0199259ad54f515448d9eafa013`: post-accept notes review uses a 6,144-token context, 350 output-token cap, and 180-second timeout when enabled.
- `58f08f8444224ef2dda9efeac128707e903bfa45`: tests for default-off and bounded settings.
- `e54b77180d29190880cb0a30eedc5a449a86a1ce`: avoid one redundant Writer restore after automatic Scene Idea suggestion.
- `dcacdc590066bec7f1be65333a74db17709996be`: initial notebook scan now honors the default-off flag.
- `d7b9b25fa7a707529bcd05d615c474b8b1701385`: regression test for default-off startup.
- `eebf744a4308e30f28f6fb70f1e1431f045f90ca`: remove duplicate Writer restoration after continuity audit.
- `dbc268ba563a20784b186630d9c737e8b3ee0525` and `eb43886aad4a104a848ee20c0fbf1faf79599e49`: generic, validation-only check for explicit author-marked End/Hard Stop sections. It requires a dedicated `HARD_STOP` check and supporting quote from the ending passage. No Writer prose instructions or novel-specific facts were added; stale model-generated stops are not new gates.
- `d55d5826ebba1f13afea443136109e869c381a49`: regression tests for endpoint false passes and duplicate Writer restoration.

Both GitHub Actions workflows passed on `d55d582`: **Python tests** and **StoryBuilder tests** (414 tests plus 71 subtests in the Python run). Sync/restart the laptop before using these changes, then run the local suite.


## Model-reuse limitation

A single shared WriterEngine is used, but `reset_context()` starts a new `llama-cli` process. Tasks needing different system prompts therefore still reload the model. The post-accept notes review is opt-in and bounded in the newer code; the initial seed scan now honors the same default-off flag, and the automatic Scene Idea path avoids one redundant restore. This does **not** eliminate every reload. If `STORYBUILDER_AUTO_WRITER_NOTES=1` is explicitly enabled, the initial seed scan still uses the general Writer timeout/token budget. A deeper model-session reuse redesign would require a separate, tested runtime change. Avoid rushing that architecture into the current session.

## The Long Way Home — Scene 10 accepted/applied; Scene 11 awaiting endpoint

- Novel: `~/Documents/MyNovel/The-Long-Way-Home`; GitHub: `tony21675/The-Long-Way-Home`.
- Scene 10 was accepted. The false-positive completion finding that the team did not choose a strategy was rejected; the scene explicitly begins manual isolation.
- The Stage 2 state update was then applied and saved. Scene pointer advanced to Chapter 1, Scene 11.
- Current story handoff: Elena chose a manual, controlled isolation sequence on Sensor Node Delta-9. Daniel is to run the protocol, Morgan monitors physical feedback, and Priya monitors crew stability. Results and root cause are unresolved. Scene 11 should continue from this choice without replaying Scene 10.
- Preserve uncertainty around Daniel's “maybe another hour” estimate. Do not turn it into a certain one-hour countdown or declare isolation successful before prose shows what happens.
- The latest Stage 2 trace confirmed the state-review warning fix live: reviewer returned two findings, both failed evidence validation, trace recorded the warning, and the author confirmed it appeared in the writer status line. Strict evidence checking stayed intact; no auto-application occurred.
- Latest private trace: https://github.com/tony21675/StoryBuilder-Traces/blob/main/prompt_trace.json. It contains story text; do not share publicly.

### Scene 11 trace finding

The trace for Chapter 1 Scene 11 completed at 2026-10-27 22:43:59 UTC without runtime error. It starts the Delta-9 isolation and includes Morgan's physical warning and Daniel's recalculation, but ends while the crew is redirected to deal with a suspected local leak. It does **not** reach the explicit endpoint: pressure readings stabilizing just above the collapse threshold while underlying instability remains exposed. Both reviews incorrectly passed. Scene 11 remains a draft for author review, not accepted. Prefer a focused continuation/revision over a full rewrite.

The new generic endpoint check activates only when the author explicitly marks an End/Hard Stop, requiring one `HARD_STOP` status and a supporting quote from the ending prose. No story-specific rules or Writer prose instructions were added.

After Scene 11 is accepted and the ending-state update is applied, StoryBuilder should save, advance to Scene 12, refresh the Writer direction, and automatically invoke the next Scene Idea suggestion. Verify this in the next trace; do not manually duplicate the suggestion.

## Project state and rules

- StoryBuilder repo: `~/Documents/StoryBuilder`; GitHub `tony21675/StoryBuilder`; active branch `redesign/simplified-writing-workflow`.
- Use `python3`, never `python`, in laptop terminal commands. One command per message; no huge copy/paste requests.
- Inspect code/traces directly on GitHub when possible. Discuss before app or novel-package changes; handoff updates are fine without permission.
- Preserve accepted prose and saved novel state. Apply state only with explicit author approval.
- Story first, flexible prose; avoid checklist writing and don't rewrite text just to appease false-positive reviewers.
- Long-term branch goal: one `main` branch after deliberate review/merge; don't switch or delete branches blindly. One branch per novel repository.
