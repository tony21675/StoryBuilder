# StoryBuilder current checkpoint — October 27, 2026

## Current checkpoint: explicit Open Novel now restores saved prose

The saved Scene 10 manuscript was already on GitHub. The problem was in StoryBuilder: startup recovery calls `_load_saved_scene_into_writer(startup=True)`, but the explicit **Open Novel** path cleared the Writer and never restored the saved section. That made the app generate a new Scene 10 instead of showing the saved prose.

The fix is committed on `redesign/simplified-writing-workflow`:
- `77b2075`: call the saved-scene restore routine after opening the package and refreshing the Writer.
- `1d4d3ce` plus `1d14215`: add a regression test using an actual saved Scene 10 file and matching before-state; fix the Tk test fixture.
- `c05bc6b`: align older close/sync tests with the already-implemented safe novel-sync flow.

Both GitHub Actions checks passed at `c05bc6b`: **Compile and unit tests** and **StoryBuilder tests**. The fix changes StoryBuilder only; it does not edit the novel manuscript or `current_state.json`.

After the laptop syncs these commits, launch `./start.sh` and open *The Long Way Home*. The Writer should report **“Restored saved Chapter 1, Scene 10 into Writer.”** Confirm the saved text is visible before generating anything else. If the status reports a mismatch or says no saved prose was found, stop and report that exact message instead of regenerating Scene 10.

## Latest trace diagnosis: fresh Scene 10 was generated instead of restored

The latest private trace ran from 2026-10-28 03:54:48 to 04:01:39 UTC (October 27 evening in Denver). It records a new Chapter 1, Scene 10 generation, not the saved manuscript and not a focused revision. The generated text ended with Elena ordering immediate manual isolation, but the coverage validator still reported the group’s commitment and hard stop as missing while the independent continuity audit called the endpoint clear. Those overlapping findings are a separate validator disagreement, not the cause of the saved-text loading bug. Do not revise or replace the saved manuscript to satisfy those findings before verifying that Open Novel restores it.

## Cross-computer novel sync diagnosis and safeguards

GitHub currently has `tony21675/The-Long-Way-Home` on `main` with `current_state.json` pointing to Chapter 1, Scene 10. The saved file `Manuscript/Chapters/Chapter_01/Chapter_01_Section_10.txt` exists, and `Chapter_01_Section_10_before_state.json` matches the current state. `Chapter_01_Section_10_after_state.json` is absent, so the remote state transition to Scene 11 is not present.

Generic sync safeguards already committed on this branch:
- `68f84fc`: closing saves and syncs the novel before syncing StoryBuilder code; Ctrl+C uses the safe close flow.
- `f1a6623`: sync a novel repo before loading its local state at startup or through Open Novel; sync failures cancel opening by default.
- `6615aca`, `06a1fbb`, and `d03292b`: tests for safe shutdown, Ctrl+C, and pre-open syncing.
- `e838ec1`: label the action **Save & Sync & Close**.
- `77b2075`: restore saved manuscript prose in the explicit Open Novel flow, matching startup behavior.

Do not manually change the novel repo or force the state pointer. After the saved Scene 10 prose is restored, analyze its ending and review the proposed state update; apply it only after reviewing it. Once the pointer advances to Scene 11, recreate that scene from the saved endpoint. The previous unsaved Scene 11 draft is not the recovery source.

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

## The Long Way Home — current GitHub recovery point

- Novel: `~/Documents/MyNovel/The-Long-Way-Home`; GitHub: `tony21675/The-Long-Way-Home`, branch `main`.
- GitHub has the saved Chapter 1, Scene 10 prose in `Manuscript/Chapters/Chapter_01/Chapter_01_Section_10.txt`. Its `_before_state.json` matches remote `current_state.json`, which still points to Scene 10. No `_after_state.json` exists remotely.
- Scene 10's saved ending commits to immediate manual isolation of Node Delta-9: Daniel runs the protocol, Morgan monitors physical feedback, and Priya watches crew stability. The operation's result and root cause remain unresolved.
- Do not treat the latest trace's fresh Scene 10 generation as accepted prose. It did not replace the saved GitHub manuscript. After syncing the code fix, confirm the saved manuscript appears in Writer before doing anything else.
- The remote scene pointer still needs the Stage 2 ending-state update reviewed/applied before StoryBuilder moves to Scene 11. Use the UI's Analyze Accepted Scene / Apply State Update flow; do not edit `current_state.json` by hand.
- Preserve uncertainty around Daniel's “maybe another hour” estimate. Do not turn it into a definite countdown or declare isolation successful before the prose establishes what happens.

## Project state and rules

- StoryBuilder repo: `~/Documents/StoryBuilder`; GitHub `tony21675/StoryBuilder`; active branch `redesign/simplified-writing-workflow`.
- Use `python3`, never `python`, in laptop terminal commands. One command per message; no huge copy/paste requests.
- Inspect code/traces directly on GitHub when possible. Discuss before app or novel-package changes; handoff updates are fine without permission.
- Preserve accepted prose and saved novel state. Apply state only with explicit author approval.
- Story first, flexible prose; avoid checklist writing and don't rewrite text just to appease false-positive reviewers.
- Long-term branch goal: one `main` branch after deliberate review/merge; don't switch or delete branches blindly. One branch per novel repository.
