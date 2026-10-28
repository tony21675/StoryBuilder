# StoryBuilder current checkpoint — October 27, 2026

## Current checkpoint: app closed; focused-revision fix committed

StoryBuilder was closed with Ctrl+C. Scene 11 was never accepted. The latest prose was pasted into this conversation, but do not assume it was saved to the novel package; the closed app's in-memory draft may be gone. Do not repeat revision attempts yet.

The focused-revision change is committed on `redesign/simplified-writing-workflow`: `fa012c2` gives the revision model the complete current scene as explicitly read-only context while keeping the selected passage as the only editable span; `5454cc3` adds regression tests that check the full-scene context reaches the initial and retry prompts. This changes the focused-edit workflow only. It adds no global Writer instructions or novel-specific rules. The connected status lookup returned no published checks for the new commits, and this execution environment could not clone from GitHub. Treat the regression tests as unverified until GitHub Actions or a laptop test run confirms them.

When ready later tonight, launch `./start.sh` from `~/Documents/StoryBuilder` to sync the branch (fast-forward only). After sync, a useful local check is `python3 -m pytest tests/test_focused_revision.py -q`, followed by the full suite if convenient. Focused revisions are not yet included in prompt-trace capture, which remains a separate observability gap.




## Latest trace check: wrong scene, stopped

The trace uploaded after the focused-revision change is dated 2026-10-28 02:51:40–02:58:58 UTC (October 27 evening local time) and records a **new Chapter 1, Scene 10 generation** using `gemma-4-E4B_q4_0-it.gguf`. It is not Scene 11 and does not contain a focused-revision operation, so it is not a test of commit `fa012c2`. The author correctly stopped the run with Ctrl+C after noticing the scene mismatch. Do not treat its output as accepted manuscript prose or as validation of the focused-revision fix.

This unrelated Scene 10 trace also shows the semantic validator marking the explicit manual-isolation decision missing even though the prose ends with Elena choosing manual isolation and saying, “Then do it.” The continuity/scope audit calls the endpoint clear, so the two reviews disagree. Keep this as a separate validation false-negative to investigate later; do not alter the accepted scene or add writing rules based on this aborted run.

## Cross-computer novel sync diagnosis and safeguards

Confirmed on GitHub: `tony21675/The-Long-Way-Home` on `main` had `current_state.json` at Chapter 1, Scene 10 as of the latest check. The earlier Scene 11 pointer was saved locally on the home computer but had not been pushed. The cause was that the old close handler synced StoryBuilder code only, and terminal Ctrl+C bypassed the close handler.

New generic safeguards now committed on this StoryBuilder branch:
- `68f84fcccab51958669e99f688bfce25d63271b4`: closing the app saves the current accepted package, syncs the novel repository first, and syncs StoryBuilder code second. A novel sync error/conflict leaves the app open for resolution. Terminal Ctrl+C is captured and routed through the same safe shutdown path after active tasks settle.
- `f1a6623836dcf8048cd049278e9c24ad4a65d584`: StoryBuilder synchronizes a novel repository **before loading its local state** at startup or when opening a novel. If sync fails or the folder is not a Git repository, opening is cancelled by default and the user must explicitly choose to open a potentially stale local copy.
- `6615acae6513c04c4baba56f5f5c16dbc22797cf`, `06a1fbb4f86dd241f5958fbb2bca830047e2fbb5`, and `d03292bf2aa42f7597b920272f4b8fad6503b66c`: regression tests for the safe shutdown sequence, Ctrl+C routing, pre-open sync, and default-cancel behavior.

The user cannot currently access the home computer. Do not try to repair or manually change the remote `current_state.json` from this computer. Later, once home, launch StoryBuilder using `./start.sh` so the app code updates. Opening The Long Way Home will attempt to synchronize the local novel before reading its state; if it succeeds, the Scene 11 state should be pushed/pulled before the Writer loads. If any sync error or conflict appears, choose **No / cancel opening** and report the exact message rather than using an older scene. The close path will then save and synchronize novel data before app code on future exits. The app never accepts unaccepted prose as part of this process.

The new tests have not been run in this execution environment, and the connected GitHub status lookup returned no published checks. After the next code sync, run `python3 -m pytest tests/test_terminal_shutdown_sync.py tests/test_focused_revision.py -q`, then the full suite when convenient.
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

The trace for Chapter 1 Scene 11 completed at 2026-10-27 22:43:59 UTC without runtime error. It starts the Delta-9 isolation and includes Morgan's physical warning and Daniel's recalculation, but ends while the crew is redirected to deal with a suspected local leak. It does **not** reach the explicit endpoint: pressure readings stabilizing just above the collapse threshold while underlying instability remains exposed. Both reviews incorrectly passed. Scene 11 remains unaccepted. Stop the repeated revision loop until the new focused-revision code has been synced and tested. It now receives the complete current scene as read-only context, but this does not guarantee that the model will dramatize every requested event; check the next result once and stop if it still only summarizes the outcome.

The new generic endpoint check activates only when the author explicitly marks an End/Hard Stop, requiring one `HARD_STOP` status and a supporting quote from the ending prose. No story-specific rules or Writer prose instructions were added.

After Scene 11 is accepted and the ending-state update is applied, StoryBuilder should save, advance to Scene 12, refresh the Writer direction, and automatically invoke the next Scene Idea suggestion. Verify this in the next trace; do not manually duplicate the suggestion.

## Project state and rules

- StoryBuilder repo: `~/Documents/StoryBuilder`; GitHub `tony21675/StoryBuilder`; active branch `redesign/simplified-writing-workflow`.
- Use `python3`, never `python`, in laptop terminal commands. One command per message; no huge copy/paste requests.
- Inspect code/traces directly on GitHub when possible. Discuss before app or novel-package changes; handoff updates are fine without permission.
- Preserve accepted prose and saved novel state. Apply state only with explicit author approval.
- Story first, flexible prose; avoid checklist writing and don't rewrite text just to appease false-positive reviewers.
- Long-term branch goal: one `main` branch after deliberate review/merge; don't switch or delete branches blindly. One branch per novel repository.
