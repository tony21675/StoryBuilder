# StoryBuilder philosophy and current checkpoint — October 25, 2026

## The product principle comes first

Tony has explicitly called out a repeated failure pattern: each imperfect State Analysis proposal leads to another filter, exception, and regression test, making StoryBuilder increasingly complicated and turning novel writing into maintenance work. Do not repeat that cycle.

**The story is the novel. The state is only a memory aid.** State Analysis is not a transcript of everything that happened and is not supposed to catalogue ordinary life. Zoe's shirt color or breakfast is not worth preserving unless the detail becomes story-relevant. Ordinary gestures, clothing, meals, and minor movements should remain in prose, not be promoted to continuity records without a meaningful reason.

Preserve what helps the story continue: major unresolved situations, concrete discoveries, consequential decisions/actions, meaningful changes in relationships or character understanding, and important predictions or hypotheses clearly attributed and left uncertain. Do not try to record or classify every sentence. It is acceptable for a suggestion to be imperfect; avoid over-engineering low-risk bookkeeping to chase perfection.

StoryBuilder must not prescribe plot beats or a step-by-step sequence of what characters must do. The writer owns what happens next, including whether Daniel's estimate is right, whether the crew finds a temporary workaround, and whether it buys time. Do not hard-code Mars, character names, the 24-hour estimate, or any repair idea into the app. Keep the story free to surprise the writer.

When a failure appears, first ask whether it truly threatens continuity or merely reflects a nonessential detail. Prefer a simpler design or tolerate a harmless imperfection over adding a special-case filter. Do not turn prompts into an IKEA manual. Do not add another guard, workflow, or test for every single model mistake. App changes still require discussion and approval; handoff updates may be made directly.

## Current StoryBuilder checkpoint

- Branch: `redesign/simplified-writing-workflow`.
- Latest confirmed laptop test result: **378 passed**, before the newest experimental character-action support filter was added.
- The latest branch now includes `filter_unsupported_character_action_events` and a regression test. This new filter has **not been run locally or otherwise verified**. Do not stack further fixes on top of it or assume it is sound. Reassess whether this special-case filter is worth keeping; prefer reverting/simplifying it if it adds complexity disproportionate to its benefit.
- The broader safeguards already in place preserve unresolved crises, keep explicit projection-only clues out of the clue ledger while retaining an attributed estimate as an event, reduce a narrow class of routine event clutter, and retain up to 16 recent events. Avoid expanding these into a detailed event-classification system.
- The latest private trace is [StoryBuilder-Traces/prompt_trace.json](https://github.com/tony21675/StoryBuilder-Traces/blob/main/prompt_trace.json). It showed Daniel's 24-hour estimate correctly retained as a recent event, earlier significant history surviving, and some fabricated event claims by the model. The appropriate response is not to police every sentence.
- The accepted Chapter 1, Scene 4 prose and saved novel state remain untouched. The last state proposal was not applied. No novel repository has been edited.

## Next action

Resume by reviewing the scope and complexity of the experimental character-action filter, not by adding more rules. Do not ask Tony to repeatedly diagnose code internals or search through long files. After deciding on the smallest sensible scope with Tony, run `python3 -m pytest -q`; the most recent full-suite result after adding that filter is not yet known. Then retest State Analysis without applying a proposal unless Tony explicitly chooses to.

---


---

# Trace compile correction — October 24, 2026

The first CI run for commit `66defa419df614a8e018a7ebdef220c5d10c7c23` caught a malformed duplicate method splice in `storybuilder.py`; compilation failed before tests ran. The splice has been removed, and the initial trace-button label now reflects the saved On/Off preference. Do not pull the code until the correction commit's compile and test workflows pass.

# Persistent prompt tracing for State Analysis — October 24, 2026

## Current remote change under test

Tony authorized changing the existing Prompt Trace from one-shot capture to a persistent On/Off setting. The intended behavior is:
- Trace is on by default on a new install and the choice persists locally across restarts until changed in the Writer tab.
- While on, each Writer generation and each regular **Analyze Accepted Scene** run saves the latest trace to the same local file, `~/.local/share/storybuilder/prompt_trace.json`, then attempts the existing private `StoryBuilder-Traces` GitHub upload.
- The private trace repository keeps only the newest trace reachable on its branch; the next capture overwrites the previous trace. This is not a secure-erasure guarantee for previously copied/unreachable objects.
- State Analysis capture includes the accepted scene, before-state, both analysis prompts, both raw model outputs, runtime details, and the assembled proposed patch/error. It does not apply any state changes.
- Off is saved locally in `~/.config/storybuilder/prompt_trace_enabled.json` (or `$XDG_CONFIG_HOME/storybuilder/prompt_trace_enabled.json`) so turning tracing off persists after restart. A missing setting defaults to On; a malformed setting fails closed to Off.
- The trace contains unpublished story text and internal prompts. Upload still relies on the existing uploader confirming the destination repository is private. If upload fails, the local trace remains and the UI should display the error.

Current code path: `redesign/simplified-writing-workflow`. Do not touch or accept any novel text or apply the rejected Scene 4 state proposal. After the code commit, pull on the laptop only when Tony is ready, run `python3 -m pytest -q`, open StoryBuilder, and use **Analyze Accepted Scene** once. Inspect the state-analysis trace in the private GitHub trace repository; no additional prompt change should be made until the raw exchanges have been examined.

---

# Structural continuity analysis split — October 24, 2026

## Repair implemented and CI verified

Tony approved one final structural attempt after the launcher was fixed and he confirmed StoryBuilder opened normally. His Scene 4 retest still proposed an internal scrubber inspection, unsupported character movements, and broad objective changes. He did not apply it.

On `redesign/simplified-writing-workflow`, `StateManager.propose` now uses two isolated model passes instead of asking one long prompt to handle every continuity task:

1. **Ending-state pass:** Receives the before-state's immediate situation, time, locations, and physical state, plus only the last four accepted-prose paragraphs (capped at 6,000 characters). Its allowed output is limited to `current_situation`, `location`, `physical_state`, and `time_of_day`. It cannot change objectives.
2. **Whole-scene evidence pass:** Receives the full accepted prose plus the existing clue/question/event history for deduplication. It can return only `new_clues`, `resolved_clues`, `new_unresolved_questions`, `resolved_questions`, and `new_recent_events`. Any situation, location, physical-state, or objective fields it might emit are discarded before the proposal is assembled.
3. Existing objective values remain unchanged by automated state analysis, so a scene summary cannot casually rewrite everyone's goal or invent a new relationship between the communications anomaly and life-support crisis.

Both passes have smaller, role-specific system prompts, independent JSON validation, and one correction attempt. The old scene-end guidance stays excluded.

Regression coverage now uses the Mars hatch sequence and deliberately has the evidence pass claim the crew already entered the scrubber housing. The test verifies this contradiction cannot overwrite the ending-state pass, verifies the ending prompt omits an earlier plan paragraph, and confirms the full scene is still available to event/evidence extraction.

Latest tested commit: `e93db10a8592cebb5f2b2982527f98b294c2a036`. GitHub Actions both passed:
- [Python tests: 371 passed, 53 subtests passed](https://github.com/tony21675/StoryBuilder/actions/runs/40146507680)
- [StoryBuilder compile and unit tests](https://github.com/tony21675/StoryBuilder/actions/runs/40146507657)

No novel files were changed. The accepted Scene 4 prose is still safe and the rejected state proposal remains unapplied. The user's laptop is still on the earlier shell-sync repair until he explicitly pulls this final structural fix; do not ask him to pull before this handoff update is committed. After this handoff commit, ask him to pull with `git pull --ff-only origin redesign/simplified-writing-workflow`, then run `python3 -m pytest -q`, then reopen/test the app. Give one terminal action at a time. The critical live test is to re-analyze accepted Scene 4, inspect the proposal, and do not apply unless it reflects partial pressurization at the sealed hatch, external mount checks by Morgan/Priya, Daniel monitoring the temperature trend, and an independent communications investigation by Ryan/Zoe. If the real local model still makes unsupported ending-state changes, report that honestly rather than layering on more prompt checklists.

---

# Latest continuity test result — October 24, 2026

## App launch and continuity retest

- Tony pulled the shell-sync repair to the local `redesign/simplified-writing-workflow` branch and ran `python3 -m pytest -q`: **371 passed**.
- `./start.sh` succeeded: it fetched GitHub, fast-forwarded the active development branch, reported it up to date, and launched StoryBuilder. Tony confirmed the application window opened normally.
- Tony re-ran post-scene analysis for accepted Scene 4 of *The Long Way Home*. The new proposal is still unsafe and **must not be applied**.
- The result still advances Elena, Morgan, and Priya toward an internal scrubber-housing inspection, though the canonical Scene 4 endpoint is Elena beginning partial pressurization at the sealed maintenance hatch while Morgan and Priya check external housing mounts. It also invents/changes physical details (e.g. Daniel closing the tablet, Ryan seated, Zoe leaning over display), changes several objectives without adequate support, incorrectly describes Daniel's temperature projection as exponential, and risks correlating Zoe's independent communications investigation with onboard diagnostics. Its recent-events list contains a mixture of potentially real scene beats and claims that must be verified against accepted prose; do not treat those proposed events as canon.
- No state changes were applied. The accepted Scene 4 prose remains intact. The novel repository was not modified by this retest. GitHub's novel manuscript archive currently contains Sections 1–3 only, so the exact active Scene 4 prose is not available in the remote manuscript tree for independent line-by-line inspection; rely on the prose already accepted in StoryBuilder and the established endpoint noted above.
- Removing Scene End Guidance from the StateManager prompt was insufficient. The remaining failure is not solved by another prompt checklist. Current architecture asks one local-model call to reconstruct the ending situation, all physical state/location changes, objectives, clues, unresolved questions, and new events from the full prose plus state context. `STATE_SYSTEM_PROMPT` is about 11.3k characters and the CLI sets an 8192-token context with a 1000-token output budget. This creates a plausible context/attention bottleneck, though it is not yet proven that hard truncation occurred.
- Recommended next design, discuss with Tony before changing app code: split the analysis responsibilities. One focused pass should derive only the actual ending state from the before-state plus the final few prose paragraphs. A separate whole-scene pass should propose new events/clues/questions but must not be allowed to override end-of-scene locations/physical state/current situation. Keep existing objectives unless the accepted prose directly establishes that a goal or assigned role changed. Add a regression case where earlier movement toward the hatch is superseded by final partial pressurization and external mount checks. Do not add a longer checklist or change any novel files.
- Current branch remains `redesign/simplified-writing-workflow`. Shell-sync repair commits are already pulled locally; no need to repull them. Next changes require discussion/approval before app code or novel edits. Continue using `python3`, never `python`, in Tony's laptop commands.

---

# Shell launcher and sync repair — October 24, 2026

## Root cause and repair

The shell launcher was blocked by an outdated branch rule. `sync.sh` refused to run unless the branch name was exactly `main`, while the repository's current default/development branch is `redesign/simplified-writing-workflow` and the app's own `builder/app_sync.py` intentionally syncs the current development branch while refusing `main`. Since `start.sh` calls `sync.sh start` first, it could exit before opening the app.

Changes now committed to `redesign/simplified-writing-workflow`:
- `sync.sh` follows the app's policy: refuses `main`, requires the current branch to track `origin/<same branch>`, and stops before syncing if a Git operation or unresolved conflict is present.
- Startup sync stashes and restores uncommitted tracked and untracked changes, fetches, and uses `git pull --ff-only`. It does not rebase or reset local work.
- Finish sync stages and commits local app changes, fetches and fast-forwards only when safe, and will not push if the branch cannot be fast-forwarded. Any local commit is preserved on failure.
- `start.sh` uses Bash strict mode, resolves the application directory safely, invokes the Bash sync helper explicitly, and launches `python3 storybuilder.py` only after sync succeeds. Existing theme/context/token defaults are preserved.
- Added `tests/test_shell_sync.py` to guard the branch policy and startup ordering.
- Added `bash -n start.sh sync.sh` to the StoryBuilder GitHub Actions workflow.

Relevant code commits:
- `87964666e0de35f9b60cdad91b8b7510d00fb21c` — repair shell sync.
- `a52c0030e1a9e0ad16e36eecad1768c75b64aad1` — harden launcher.
- `86a43675bb9cba9fce0d43cb9bb8c4bc46cc9f41` — add shell sync regression tests.
- `4ad14f46bf6abd902d18f6fa9e57ee8ceb386b53` — validate shell syntax in CI.

**Do not ask Tony to pull until both GitHub Actions workflows pass on the latest branch head.** Then give one terminal action at a time: first `git pull --ff-only origin redesign/simplified-writing-workflow`, next `python3 -m pytest -q`, and then launch with `./start.sh`. The launcher will perform its own safe sync. Do not switch or delete branches as part of this repair. The accepted Scene 4 prose remains saved, the bad state proposal remains unapplied, and no novel files were changed.

---

# Post-scene continuity input repair: October 24, 2026

## Repair under test

Tony approved trying one narrow change rather than adding another model checklist. Post-scene state analysis was receiving Scene End Guidance, including an optional expected end-state hint, alongside the accepted prose and before-state. This is a competing input that can describe a planned ending beyond what actually happened in the scene.

The working-branch change:
- State analysis no longer inserts Scene End Guidance or an expected end-state hint into the model prompt.
- The accepted prose and the before-state remain the input sources for the continuity proposal.
- The GUI no longer computes or passes scene-end guidance for post-scene analysis or manuscript state recovery.
- The optional StateManager.propose argument is retained for compatibility, but deliberately ignored.
- A focused regression test supplies conflicting Mars guidance claiming the crew has entered the scrubber housing while the accepted prose stops at partial pressurization and external mount checks. It verifies that the conflicting guidance is absent from the prompt.
- No extra checklist or repeated warnings were added to the writer prompt.

- Updated the existing app-level workflow test so it now fails if Scene End Guidance is computed and verifies StateManager receives the accepted scene text without a guidance keyword. This replaces the old test expectation that required passing the hint.

The previous JSON parsing/event-shape fix remains included. The accepted Scene 4 prose remains saved; its invalid proposed state update is still unapplied. No novel files were edited.

Do not ask Tony to pull until both GitHub Actions workflows pass on the latest repair commit. Then give one terminal action at a time: pull fast-forward only from origin/redesign/simplified-writing-workflow, run python3 -m pytest -q, then retry Scene 4 analysis. Inspect the proposal before any state is applied.

---

# Continuity proposal parsing repair: October 24, 2026

## Current defect and fix

Tony ran the refreshed local app after the 366-test pass. The post-scene continuity model returned an invalid state proposal; no changes were applied. The diagnostic showed only a nested {"event": "..."} object even though the response tail contained state fields and new_recent_events entries. This indicates that malformed enclosing JSON can cause the parser to mistake a later nested object for the complete proposal.

The targeted repair on redesign/simplified-writing-workflow:
- Continuity extraction requires the last complete JSON object to contain current_situation; it must not fall back to a nested {"event": "..."} object or stale echoed state.
- Exact new_recent_events entries shaped as {"event": "plain text"} are unwrapped to plain strings. Other malformed entry shapes remain subject to normal validation.
- The system and retry prompts explicitly require plain JSON strings for recent-event list items.
- Regression tests cover malformed outer JSON with a valid nested event object, exact event-wrapper normalization, and the actual proposal pipeline. New-event proposal items are converted to plain strings before appending; the saved recent_events ledger intentionally retains its existing {"event": "..."} record shape.

Safety: The rejected Scene 4 state proposal was not applied. Keep it unapplied. The accepted Scene 4 prose remains saved. Do not edit novel files or ask Tony to hand-edit source/JSON.

Before asking Tony to pull: Confirm both GitHub Actions workflows pass on the repair commit. Then give one terminal action at a time: git pull --ff-only origin redesign/simplified-writing-workflow; run python3 -m pytest -q; then launch python3 storybuilder.py and re-test post-scene analysis. The local checkout was clean on redesign/simplified-writing-workflow at a1e5c45 before this remote fix. Keep the app repo and novel repo separate; do not reset work or change branches blindly.

---

# Resumed session checkpoint — October 24, 2026

Tony resumed testing. His local checkout was clean and at `c91d1ed` on `redesign/simplified-writing-workflow`; he pulled the handoff-only update and ran `python3 -m pytest -q`, which reported **363 passed**. He launched StoryBuilder and confirmed that **Scene Contract** and **Writer** are again separate tabs. The Scene Contract button label still truncates to “Prepare Scene...” because its width is too small; this is a minor UI issue and can wait.

## Quick Edit character switching verified locally

Tony re-analyzed accepted Scene 4, opened Quick Edits, saw Daniel selected, switched to Elena, and confirmed both knowledge and objective changed. He switched back to Daniel and confirmed his own values returned. The character-switch fix is working in the local application.

The current model-generated state proposal still incorrectly says Elena, Morgan, and Priya have moved to conduct an internal inspection. Scene 4 ends with Elena beginning to partially pressurize the inspection chamber while Morgan and Priya check external housing mounts. The proposal should **not** be applied unchanged.

## New plain-language state editing tools added remotely

Latest code commit: `915c3db4b166452d5acf2675dcf144ba0bb93b9e` (“Make optional Quick Edit controls safe in tests”). This commit includes UI changes and tests committed earlier in the current sequence:
- Quick Edits now includes plain-language per-character fields for **current location**, **physical position/current activity**, **posture**, and **movement**, plus existing knowledge and objective fields.
- These edits update the candidate `location` and `physical_state` data, including the duplicate per-character location in physical state, then refresh the human-readable proposed-change list.
- The advanced JSON tab now includes **Refresh Changes to Review**, so the summary can be rebuilt after advanced edits.
- Apply State Update now blocks and warns if the JSON preview differs from the last reviewed snapshot. This prevents applying a stale list without refreshing.
- Regression tests cover location/physical-state editing, refreshing the review, blocking unreviewed advanced JSON edits, and ensuring each character's plain-text fields remain separate when switching the dropdown.

Both GitHub Actions workflows passed on commit `915c3db4b166452d5acf2675dcf144ba0bb93b9e`:
- [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40136729286)
- [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40136729327)

**This latest UI commit has NOT been pulled to Tony's laptop yet.** The app is currently open. Do not ask him to edit source or JSON. Before pulling, make sure he closes StoryBuilder safely; there is no generation in progress, but the current Scene 4 state proposal is still un-applied. The accepted Scene 4 prose remains safe. After pulling the latest commit, run `python3 -m pytest -q`, launch the app, and verify the new Quick Edit fields before asking him to change any state. Keep the instructions one step at a time. Do not apply the old proposal.

---

# Session close checkpoint — October 22, 2026 (latest)

**Tony is closing StoryBuilder for tonight. Stop here. Do not ask him to pull, run tests, reopen the app, or continue reviewing state tonight.**

## User workflow requirement: no manual code or JSON editing

Tony clearly stated that he cannot reasonably edit code or navigate hundreds of lines of code to change one sentence, and he should not be expected to manage raw JSON to write a novel. Previous instructions made the workflow frustrating and too technical. This is a product usability requirement, not a user failing.

- Never ask Tony to edit `storybuilder.py`, search through large source files, or hand-edit a large JSON state.
- Do not use the Full State JSON editor as the default solution to ordinary continuity problems.
- Give one simple UI action at a time while actively testing, not multiple fields/instructions in a single turn.
- The assistant should handle code changes remotely on the working branch, test them, and update the handoff; Tony will pull only when he chooses to resume.
- Improve StoryBuilder so normal state corrections, including location/physical-state continuity, can be handled in accessible plain language controls with a clear refreshed review. Do not make the author manually reconstruct an entire state object.
- Tony prefers separate **Scene Contract** and **Writer** tabs because each is easier to scroll and inspect than the combined vertical workspace. The latest remote code restores separate tabs.

## Scene 4 status: accepted prose safe, ending-state update not applied

- The Mars story's Scene 4 prose is accepted and remains saved in the manuscript. It has not been rewritten or lost.
- Post-scene analysis completed. Tony reviewed the proposed state changes and edited character knowledge/objectives through Quick Edits.
- Character review included Daniel, Elena, Morgan, Priya, Ryan, and Zoe. Corrections intended:
  - Daniel: do not add the claim that temperature rises exponentially; scene says steady/incremental and mentions the curve flattening slightly. Preserve his existing objective.
  - Elena: her fourth knowledge line ("She decided against monitoring the readings further...") is an action, not new knowledge; remove that line only. Objective should reflect beginning partial pressurization and preliminary external inspection, not an internal inspection already underway.
  - Morgan: keep existing knowledge; objective is external casing and housing mounts, watching for heat/sounds/visible stress.
  - Priya: keep existing knowledge; objective is preliminary external inspection with vent safety caution.
  - Ryan: keep existing knowledge and objective; unexplained burst investigation should not be assumed connected to life support.
  - Zoe: preserve her three prior knowledge facts and add the new rhythmic-bursts/power-fluctuation hypothesis as unverified. The latest Changes to Review showed only that new Zoe fact added, with no removals. Objective compares bursts with power-grid diagnostics without assuming a life-support link.
- Canonical Scene 4 physical endpoint: Elena has reached the sealed maintenance hatch and begins the partial pressurization sequence; Morgan and Priya check the external housing mounts. The internal scrubber-housing inspection has not begun. No physical findings from an internal inspection are established.
- Preserve the unresolved threads: primary scrubber manifold temperature keeps rising, Daniel's silicate-like trace remains unverified and establishes no source/route/cause, and the patterned communications bursts remain unexplained with no established connection to life support.
- Tony pasted/shared a Full State JSON snapshot to get help with the entire correction, then the Changes to Review panel continued to display old proposed location details. The review did not clearly reflect the full intended corrections. Tony was told not to apply the proposal and did not report clicking Apply State Update. Treat the current state preview as **unapplied/uncertain**. Do not assume manually editing the JSON successfully refreshed the review.
- Do not apply the current state proposal. When Tony resumes, inspect app state safely and make the state-review workflow usable before asking him to do more review. A fresh re-analysis may be appropriate after the fixed app is available, but do not force this as the first action before confirming his readiness.

## Remote code checkpoint

Branch: `redesign/simplified-writing-workflow`.

Latest code commit before this handoff update: `52592660d671f6f3a6a81cc862aaedf897dbe3e9`. It contains:
- Quick Edit character-switch fix: track which character's text is loaded, save edits to that previously loaded character before loading the newly selected character, and regression coverage.
- Restore independent, scrollable Scene Contract and Writer tabs.

Both CI workflows passed on that code commit:
- [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/39775656160)
- [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/39775656121)

Handoff-only documentation commits occur after the code commit. No local desktop verification has confirmed the Quick Edit fix or separate-tab layout.

## Resume next session

1. Start calmly by acknowledging this checkpoint and ask whether Tony is ready to resume. Do not make him repeat what happened.
2. Do not tell him to pull automatically. Confirm the app is closed and check current local git state safely before recommending any pull. Tony had pulled an earlier fix during the session, then was asked to stop pulling while the separate-tab change was still being finished; do not assume his checkout has the latest remote commit.
3. Before handling state, make sure the current/accepted scene remains safe and no analysis or generation is running. Do not apply the old proposal.
4. Primary development task: make post-scene state review accessible without raw JSON. Ensure author-edited location/physical-state/current-situation/character knowledge/objective changes are reflected in the review summary before applying. The review should make it obvious which preview is current, preserve untouched fields, avoid overwriting knowledge across characters, and prevent stale change summaries after advanced JSON edits.
5. Test the corrected UI, including dropdown character switching, keeping each character's knowledge/objective distinct, and making sure no state is saved before explicit approval. Keep instructions one action per turn during live testing.
6. Longer-term test path remains: finish the Mars story test, try a fresh children's-book project for cross-genre coverage, then return to *Taken at Dusk*.

---

# Latest session checkpoint — October 22, 2026

**STOP POINT: Tony explicitly asked to leave the laptop alone tonight. Do not tell him to pull or run commands until he resumes.** The code updates below are on GitHub only and have not been pulled to his laptop.

## Current scene-review status

- The Mars story's Scene 4 prose remains saved/accepted in the manuscript.
- Its post-scene analysis completed and produced an ending-state proposal. The proposed state update has **not** been applied.
- Tony opened Quick Edit and found that switching through all six characters showed the same knowledge and current objective for each. He also requested instructions one field at a time; honor that pacing and do not dump multiple edits/instructions at once.
- Do not apply the existing Quick Edit preview. Once the corrected app is installed, re-analyze the accepted Scene 4 to rebuild a clean proposal, then review it together one field at a time. Preserve the three ongoing story threads: rising scrubber-manifold temperature/thermal-runaway risk, Daniel's unverified silicate-like trace, and the unexplained patterned communications bursts. The scene ends with Elena beginning partial pressurization while Morgan and Priya check external housing mounts; do not assume an internal inspection has begun.

## Quick Edit character-switch bug — fixed remotely, local verification pending

Cause: the Tk combobox changes to the new character before its selection callback runs. The old callback saved the currently visible character fields using the *new* dropdown name, which could overwrite/copy the previous character's knowledge and objective into the newly selected character.

Remote fix tracks `_quick_edit_loaded_character` and saves the visible text under the previously loaded name before loading the newly selected character. A regression test covers preserving Daniel's and Zoe's separate knowledge/objectives during a switch.

## Restore separate Scene Contract and Writer tabs

Tony said the old separate-tab layout was easier to scroll and see than the combined vertical Write workspace. The remote code has restored independent, scrollable **Scene Contract** and **Writer** tabs. The intermediate UI commits had CI failures while the replacement test and duplicate initialization were being corrected; the latest commit below is the corrected version.

## Latest remote code and CI

Branch: `redesign/simplified-writing-workflow`

Latest commit: `52592660d671f6f3a6a81cc862aaedf897dbe3e9` — “Remove duplicate initialization from restored tab layout”. It includes the Quick Edit character-switch fix and separate-tab restoration. Both workflows passed:
- [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/39775656160)
- [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/39775656121)

These are GitHub CI results only, not a local desktop run. Nothing was pulled locally.

## Next session: safe sequence

1. Start by confirming Tony is ready to resume. Do not rush him or assume the laptop has pulled these changes.
2. Before pulling, ensure no generation/revision is running, check whether any unaccepted prose needs preserving, then inspect local status with `cd ~/Documents/StoryBuilder && git status -sb`. If local changes or divergence appear, inspect/reconcile; never reset or blindly overwrite.
3. When safe, pull the latest remote branch with `git pull --ff-only origin redesign/simplified-writing-workflow`, run `python3 -m pytest -q`, then launch `python3 storybuilder.py`.
4. Re-analyze the accepted Scene 4 and inspect the state proposal. Verify that selecting a character loads distinct stored knowledge/objective and no data is applied until Tony approves it.
5. Keep Scene Contract and Writer on separate tabs. Continue testing the Mars story first, then a new children's-book project, and later return to *Taken at Dusk*.

---

## Final runtime-source grep follow-up — October 21, 2026

After the latest local `334 passed` run, Tony searched runtime source/templates for the old novel's character names and terms. One match remained at `storybuilder.py`: the Story Interview's Relationships section explicitly read `relationship_with_tony`. It was not a Writer prompt or cross-package loader, but it was still an unnecessary prior-novel field assumption.

The field lookup is now generic: always include `relationships` and `friendship_dynamics`, then include any character-card key beginning `relationship_with_`. Added a regression test that verifies the interview displays a generic `relationship_with_zoe` field, and expanded source isolation checking to cover this method. Remote commits: `8f99587a21868576c740813f1819a19eafdbb3fc` and `c6162d400dd978b35b027158adcb2b43b6d537a4`. Not yet pulled or locally tested.

Next on laptop: `cd ~/Documents/StoryBuilder && git pull --ff-only`, then `cd ~/Documents/StoryBuilder && python3 -m pytest -q`. If green, repeat the runtime grep:
```bash
cd ~/Documents/StoryBuilder && git grep -n -i -E 'Tony|Tiffany|Maya|Barnaby|Chloe|Taken at Dusk|bubble bath|cologne|pine needle' -- storybuilder.py builder templates || echo "No matches found in runtime source or templates."
```
Expected result is no matches. Keep both novels and the existing Mars draft untouched while verifying.

# IMMEDIATE NEXT STEP: Latest prompt fixes — October 21, 2026

The laptop was pulled through `f8756db`, then reported **330 passed, 4 failed**. The remaining issues have now been fixed on the remote redesign branch:
- The dynamically assembled prompt in `builder/scene_completion.py::_audit_prompt` retained an older mystery-specific paragraph even though its system prompt had been generalized. It now uses genre-neutral language about unsupported consequential facts, boundaries, speculation, and established evidence.
- `tests/test_scene_completion.py` now checks for that generic wording and explicitly guards the dynamically assembled prompt against the words `abduction` and `Tiffany` in the generic test scenario.
- `builder/scene_contract.py` retains the important “acknowledged requests/preferences” instruction while staying at 1,464 characters, under the 1,500-character guard.
- `tests/test_scene_contract.py` assertions were aligned to the intentionally shortened generic scope/provenance wording.

Latest code/test commit at checkpoint: `14cb7ba4586d94ee9c52c894a8069a7b7f40e49d`. These newest changes have **not** yet been pulled or run on Tony's laptop. Do not claim tests are green until his full `python3 -m pytest -q` result confirms it.

The local Mars package audit completed read-only: 45 regular files, 0 symlinks, 0 unreadable files. All six declared character cards match the Mars crew; current pointer is Chapter 1, Scene 3. The only keyword hits outside docs are in `Manuscript/Chapters/Chapter_01/Chapter_01_Section_01_draft.txt` (Maya x2, Chloe x2; file size 4,309 bytes; modified October 21, 2026 at 07:16). StoryBuilder's normal historical retrieval explicitly excludes `*_draft.txt`, and startup restores the accepted section, not that draft. Do not delete it during code verification. README.md and TEST_PROTOCOL.md each have one title mention and are not included in the Writer JSON reference-file assembly.

Next terminal actions, one at a time:
1. `cd ~/Documents/StoryBuilder && git pull --ff-only`
2. Then `cd ~/Documents/StoryBuilder && python3 -m pytest -q`
3. Share the full result. If green, do one final read-only verification of the actual prompt assembly before launching the app. Never edit/sync either novel as part of this audit; keep `Taken_at_Dusk` untouched.

---

# LATEST CHECKPOINT: Cross-novel code audit and package scan pending — October 21, 2026

Read `CROSS_NOVEL_CONTEXT_AUDIT_2026-10-21.md` first. The audit found and removed multiple previous-novel assumptions from shared runtime prompts/helpers: named characters and an old title in UI examples; a specific character name in continuity retrieval ranking; a mystery-specific integrity-audit instruction; prior-novel scent descriptors; and a fixed list of old character names used during cast inference. Shared Writer/contract/idea/validation prompts now use genre-neutral rules that make the original Scene Idea and established evidence authoritative. New tests cover prompt isolation, state-summary evidence precedence, read-only/copyable Scene Direction, and isolation between sibling novel packages/manuscripts.

**Local test status:** Tony's last run before these latest changes was `326 passed, 5 failed`. The failures involved prompt wording, validator prompt length, and contract-context expectations. Code/test updates address them, but the laptop must rerun the suite before verification is complete. The latest branch includes a new `tests/test_novel_package_isolation.py` and `tests/test_generic_prompt_isolation.py`.

**Important remaining diagnostic:** the actual local `~/Documents/MyNovel/The-Long-Way-Home` folder has not been inspected. The source loader stays inside the selected folder and opening a novel stops the previous Writer process, so leftover files/notes/symlinks inside the Mars folder are the remaining major cross-novel hypothesis. After tests pass, run the read-only folder scan supplied in the chat and share its output before changing any files. Do not edit either novel, do not regenerate the saved Scene 3 contract, and do not generate/accept prose during this audit. Keep `Taken_at_Dusk` untouched.

## Contract-context review finding, October 21, 2026

Inspection of `SceneContract.writer_prompt_context` confirms the contract layer separately repeats scene-idea priority/action fidelity/agency, progression/scope, event provenance, and clue boundaries. The static system prompt and scene-boundary brief already cover several of these. Some duplication is intentional, and the contract also supplies unique scene-specific facts, required beats, and the hard stop. The safe first target for simplification is duplicated *general craft guidance*, not canon, agency, character knowledge, required beats, or explicit boundaries. See the updated [STORY_FLOW_REPAIR_PLAN.md](STORY_FLOW_REPAIR_PLAN.md). No code changed.

## Prompt assembly map added — October 21, 2026

Source inspection found that the actual Writer context is layered: static Writer system prompt, generated Scene Direction/contract context, a separate scene-boundary brief, selected novel reference files, and optional retrieved historical excerpts. The static prompt and scene brief repeat several protections around required beats, emotional agency, clue boundaries, and hard stops. This may be deliberate reinforcement, so no removal is assumed. The read-only Writer Context Preview assembles the layers, estimates context size, and lists included/pruned/compacted files without generating prose or changing story state.

The plan now records this finding in [STORY_FLOW_REPAIR_PLAN.md](STORY_FLOW_REPAIR_PLAN.md). Next: inspect `SceneContract.writer_prompt_context` and, in the disposable package, use Writer Context Preview to classify duplicated instructions before designing the one-variable prose comparison. No code or novel changes.

## New writing-flow investigation — October 21, 2026

The Chapter 1 vs Chapter 2 comparison suggests Chapter 1 has more natural scene movement, while Chapter 2 sometimes repeats distress/reassurance and explains emotional conflict after the reader already understands it. This is a style hypothesis, not proof that prompt complexity alone caused the difference.

Prompt-history investigation confirmed that the creative-first Writer prompt is already merged into `main`: [rewrite commit](https://github.com/tony21675/StoryBuilder/commit/1c88b9139203886224a83eb6cdf084e72073b52f), [merge commit](https://github.com/tony21675/StoryBuilder/commit/e43314e17173d178588fea31c5969769007a7a1e). The rewrite intentionally replaced a long numbered craft-rule list with a smaller set of anchors and broader creative guidance; the scene brief was also shortened. So the next step is not to blindly revert to that version. Inspect the full current assembled Writer prompt and injected context for duplicated/conflicting instructions, and search available prompt traces for evidence of the actual Chapter 1 prompt. Git history alone does not prove the exact prompt used for that generation.

Plan: see [STORY_FLOW_REPAIR_PLAN.md](STORY_FLOW_REPAIR_PLAN.md). No app code, Story Plan, state, or manuscript prose changed. Keep accepted scenes and the real novel protected; keep the unaccepted Scene 3 draft isolated and unaccepted. No code changes yet. Next action: map current prompt assembly and trace availability, then design one controlled disposable comparison with the same model and same scene anchors. Keep canon, character knowledge, required beats, and explicit hard stops firm while giving dialogue, pacing, emotional development, gestures, and transitions more creative room.

## Final verification — October 21, 2026

Selection-aware Focused Change plus the concurrent-editor safety regression are verified by CI on code/test commit [252ab9a](https://github.com/tony21675/StoryBuilder/commit/252ab9a2c7c84d330e7a5d7f6a635a4cc3d3e3f9): **302 unit tests passed**, compile passed. Both workflows also passed on the subsequent latest handoff-only main commit: [checks](https://github.com/tony21675/StoryBuilder/actions/runs/39560296419), [tests](https://github.com/tony21675/StoryBuilder/actions/runs/39560296424). The latest repair code remains on `main`. No live desktop/local-GGUF test has been done.

**Next action:** On the laptop, first ensure no Writer generation/revision is running. Decide how to preserve or discard the unaccepted test draft; never use Close & Sync Novel for the disposable package. Then update/launch StoryBuilder from `main` with the disposable package selected and test a short selected passage, verifying that all surrounding prose stays unchanged. After the live test, update both handoffs again. Do not accept the current draft or apply its state update.

## Final race-safety regression added — October 21, 2026

Added one more focused test in [commit 252ab9a](https://github.com/tony21675/StoryBuilder/commit/252ab9a2c7c84d330e7a5d7f6a635a4cc3d3e3f9): if the Writer editor changes during model generation, Focused Change must refuse to apply the returned revision and preserve the user's newer text. This test is now part of the suite. CI for this latest test addition must finish before the test milestone is considered green; the previous 301-test baseline passed both workflows.

## Verification complete — October 21, 2026

Verified code baseline: `cb73a10bae2b1e845419d67f79eeb8a98e1abee4`; commits after this baseline have changed handoff documentation only. Both CI workflows passed on this commit: [checks](https://github.com/tony21675/StoryBuilder/actions/runs/39559964629) and [tests](https://github.com/tony21675/StoryBuilder/actions/runs/39559964594). The unit-test job reports **301 tests passed** and compilation succeeded. Code repair commit: [d382e471](https://github.com/tony21675/StoryBuilder/commit/d382e471b3c9046b9c6a77e0049aa2b7caa1221e); the subsequent test-fixture correction is [7ac07a9](https://github.com/tony21675/StoryBuilder/commit/7ac07a9b37df5a16ff9523b2185753bd96a43bcd). Changes after that were handoff documentation only. No local model/UI run has been performed yet.

**Next:** test in the local desktop app against a disposable novel, only after checking for unaccepted prose/generation and updating StoryBuilder main safely. Select only a paragraph/short dialogue span in Generated Scene, type a narrow request, apply, and compare all text before/after the selection byte-for-byte. Test one deliberate failed response/no-selection case if practical. Do not accept or sync the current novel test draft.
 
## Test-fixture correction — October 21, 2026

Fixed the incorrect stale-offset fixture in `tests/test_focused_revision.py` commit [7ac07a9](https://github.com/tony21675/StoryBuilder/commit/7ac07a9b37df5a16ff9523b2185753bd96a43bcd): its expected selected text now includes the period that is outside the truncated source slice. This was a test assertion problem; no production code changed in this correction. New CI runs have been triggered by this commit. Do not claim the selected revision path is verified until both workflows pass.

## CI checkpoint — October 21, 2026

The first CI run for implementation commit `d382e471b3c9046b9c6a77e0049aa2b7caa1221e` failed on one newly added test fixture, not a syntax or compile error: the "stale selection offsets" fixture accidentally described a slice that did match its selected text, so the helper correctly did not raise. Compile succeeded. Correct the fixture by making its claimed selected text differ from the captured slice, then rerun CI. Links: [tests run](https://github.com/tony21675/StoryBuilder/actions/runs/39559839393), [checks run](https://github.com/tony21675/StoryBuilder/actions/runs/39559839228). The selection-aware code is not yet CI-verified and has not yet been live-tested with the local model.

## Latest repair checkpoint — October 21, 2026

**Implemented on main:** [d382e471](https://github.com/tony21675/StoryBuilder/commit/d382e471b3c9046b9c6a77e0049aa2b7caa1221e), “Make focused revision selection-aware.” CI is running: [tests](https://github.com/tony21675/StoryBuilder/actions/runs/39559839393), [checks](https://github.com/tony21675/StoryBuilder/actions/runs/39559839228).

Focused Change now requires the author to select the exact passage in Generated Scene. The UI retains the local selection when focus moves to the request box, captures exact source offsets, sends the selected passage plus short read-only neighboring context, and asks the model for replacement_text only. The app checks that offsets still match the selected source, rejects whole-scene selections, and checks the entire editor still matches the captured draft before applying. A mismatch or model failure leaves the draft unchanged. Each retry now starts a fresh task context, then restores the normal Writer context. Added 8 targeted tests, including long-scene/multiline preservation, changed source offsets, target_text rejection, retry context reset, and failed edit handling.

**Not yet verified:** CI results for this commit are pending, and the local desktop/model has not been tested. Do not use the test-copy draft for acceptance or state update. Once CI passes, update local main safely using the project's normal start/sync workflow only after confirming no unfinished or unaccepted work is at risk. Then test selection-based Focused Change in a disposable novel. The previous Scene 3 draft remains unaccepted, with Chloe's emotional beat and the separate hard-stop issue unresolved.

The full audit remains at [APP_AUDIT_2026-10-21.md](APP_AUDIT_2026-10-21.md). Continue honoring all permanent collaboration/safety rules in `CHAT_HANDOFF.md`.
# Current StoryBuilder Handoff Checkpoint
Date: October 21, 2026

**Read this checkpoint first for the latest status.** It supplements the older `CHAT_HANDOFF.md`, which retains historical context and permanent collaboration rules.

## Audit complete

- Audit report: [APP_AUDIT_2026-10-21.md](APP_AUDIT_2026-10-21.md) (updated in commit `f772902fe29aaa6bad057c1d53d0c917db0141fa`)
- Code audited: `main` at `96b29b94775029e64eccee07dfd816e0dc96ffd9`
- Audit documentation commit: `f11a8987c8ed826124e486a3514f146465431103`
- Both CI workflows passed on the audited code commit: [checks](https://github.com/tony21675/StoryBuilder/actions/runs/39557373301), [tests](https://github.com/tony21675/StoryBuilder/actions/runs/39557373271).
- No application code or novel prose was changed by the audit.

## Current defect and next action

Focused Change has repeatedly failed to apply an edit because the model-generated `target_text` cannot be matched exactly in the full draft. Source review shows it asks the model to choose and copy the exact target itself. Whitespace flexibility exists, but punctuation and characters still must match. Its two attempts reuse one model conversation; attempt two repeats the full draft and includes the failed response. Focused revision also uses llama.cpp default temperature/top-k/top-p rather than task-specific sampling settings, a consistency risk but not a proven sole cause. Existing tests use short artificial text, not long real-scene prose.

**Do not retry prompt variations.** Next, agree on and implement a selection-aware patch path: the author highlights the exact passage; the app provides that exact selected source span to the model and asks for replacement text only; the app verifies the original selection still matches before replacing only that span. Reset the model context between attempts. Add tests for long prose, multi-paragraph selections, quote/punctuation variants, concurrent editor changes, retry resets, and unchanged surrounding text. No fuzzy target match that could silently edit the wrong passage.

## Other audit priorities

1. Improve visibility and effectiveness tests for Scene Contract coverage and the five-category continuity/scope audit. The last live scene overran its explicit endpoint despite the existing model-assisted review pipeline; exact reason is not yet known because the live audit output was not captured.
2. Later, consider splitting the ~418 KB `storybuilder.py` UI module incrementally.
3. Optional later cleanup: consolidate the two CI workflows into a Python 3.11/3.12 matrix; investigate the unexplained root `StoryBuilder` gitlink (mode 160000, no `.gitmodules` present); decide whether branch protection is appropriate for the main-only workflow.

## Safety and evidence boundaries

- Static source review and latest GitHub CI were inspected; this was not a local desktop/model run.
- Keep the app and novel as separate repositories. Do not change novel data during the repair.
- Resume by reading this file, then the audit report and older `CHAT_HANDOFF.md` for detailed workflow rules and historical context.
