# Generic event-support guard — October 25, 2026

## User's writing principle

Tony explicitly does not want StoryBuilder to prescribe a step-by-step plot or turn writing into an instruction manual. The novel must remain free to discover its own events, solutions, setbacks, and temporary workarounds. No scene sequence, Mars-specific rule, character name, 24-hour deadline, or repair solution is to be hard-coded into StoryBuilder.

## Latest Scene 4 finding

The latest trace is [the private Prompt Trace](https://github.com/tony21675/StoryBuilder-Traces/blob/main/prompt_trace.json). The 24-hour thermal estimate was retained as a recent event, not a new clue, and the original recent-event history survived under the 16-entry limit. The evidence model still proposed unsupported character actions: Morgan moving toward the hub and Daniel agreeing to switch from modeling to an applied inspection. The accepted scene instead has Morgan respond to Elena's instruction and Daniel offer to prepare diagnostic tools from the hub. The accepted prose and saved state remain untouched; the proposal was not applied.

## Generic code safeguard added

- Added `filter_unsupported_character_action_events` to `builder/state_manager.py`. It conservatively checks explicit physical-movement/positioning and agreement claims against the accepted prose and the named character, without requiring copied quotes. If the actor cannot be confidently identified, or the event is outside those action categories, the entry is left alone rather than guessed away.
- Added a regression test ensuring the unsupported Morgan movement, Daniel agreement, and unsupported active repositioning are filtered, while supported movement phrased differently, a short affirmative agreement, and Zoe's supported leaning action are retained.
- This is a state-ledger continuity safeguard, not an instruction for the writer. It does not prescribe events or outcomes and does not add any plot-specific prompt rules.

The code and regression test are on `redesign/simplified-writing-workflow` in commits `072220a` and `68813fa`. The full local test suite has **not yet been run** against this latest code. When StoryBuilder closes and syncs, run `python3 -m pytest -q`. If tests pass, rerun State Analysis on accepted Scene 4 and inspect the proposal. Do not apply any proposal automatically. No novel repository was edited.

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

# Latest resumed-session note — October 24, 2026

Read `CHAT_HANDOFF_LATEST.md` first for the full current checkpoint.

Tony's local checkout was clean at `c91d1ed`; he pulled the handoff-only update, ran `python3 -m pytest -q` (**363 passed**), launched StoryBuilder, and confirmed Scene Contract and Writer are separate tabs. He re-analyzed accepted Scene 4, selected Daniel, switched to Elena and confirmed her knowledge/objective displayed, then switched back to Daniel and confirmed his data returned. The local character-switch fix is verified.

The generated ending-state proposal still incorrectly advances the Mars crew into an internal scrubber inspection. Do not apply it: Scene 4 ends with Elena beginning to partially pressurize the chamber while Morgan and Priya check the external mounts. The accepted Scene 4 prose remains safe.

## Latest remote state-review UI changes

Latest code commit: `915c3db4b166452d5acf2675dcf144ba0bb93b9e`. It adds plain-language Quick Edit fields for per-character location, physical position/activity, posture, and movement; carries these through into location/physical_state in the proposed preview; adds **Refresh Changes to Review** for advanced JSON edits; and blocks applying a preview if its JSON changed since the displayed review was refreshed. Regression tests cover these behaviors and character-specific field switching. Both CI workflows passed:
- [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40136729286)
- [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40136729327)

This latest UI update is remote-only and has not yet been pulled to the laptop. Tony's StoryBuilder app is still open. When continuing, do not ask him to edit code or JSON. First ask him to safely close StoryBuilder, then guide him one action at a time to pull the latest code, run `python3 -m pytest -q`, reopen the app, and verify the new Quick Edit controls. Do not apply the old Scene 4 state proposal. The truncated “Prepare Scene...” button label is a minor later UI fix, not a blocker.

---

# Session close checkpoint — October 22, 2026

Read `CHAT_HANDOFF_LATEST.md` first; it contains the authoritative current checkpoint and the next-session plan.

Tony is closing StoryBuilder for tonight. Do not ask him to pull code, run tests, reopen the app, or continue this state review until he chooses to resume.

## Important collaboration requirement: no manual code or JSON editing

Tony explained that he cannot reasonably edit code or find a sentence inside hundreds of lines of source, and should not have to navigate raw JSON to write his novel. Previous help became too technical and frustrating. This is a usability problem for StoryBuilder and an instruction about how to collaborate.

- Never ask Tony to edit `storybuilder.py`, search large source files, or manually reconstruct a full state JSON object.
- Use one clear UI action at a time when he is actively testing; wait for his result before giving the next action.
- Assistant should handle code changes remotely on the development branch, test them, and update handoffs. Tony decides when he is ready to pull.
- Normal state corrections, including character locations/physical state and character knowledge/objectives, need usable plain-language controls and a review that reflects the actual current preview. Do not route ordinary corrections through Full State JSON.
- Tony prefers separate, independently scrollable **Scene Contract** and **Writer** tabs. The latest remote code restores this layout.

## Scene 4 / post-scene state status

- The Mars story's accepted Scene 4 remains saved in the manuscript. It was not rewritten or lost.
- Analysis finished and proposed a state update. Tony worked through all six characters in Quick Edits. The latest review showed Zoe's new knowledge added while her earlier three facts were preserved after correction.
- A full state snapshot was shared for assistance; the Changes to Review panel continued showing older proposed location details instead of visibly reflecting the intended full-state corrections. Tony was told not to apply the proposal. He did not report clicking Apply State Update. Treat the preview as unapplied and uncertain, and do not apply it.
- Intended continuity endpoint: Elena is at the sealed maintenance hatch beginning to partially pressurize the inspection chamber while Morgan and Priya check the external housing mounts. Internal inspection has not begun, and no internal inspection findings have been established.
- Preserve story threads: rising primary oxygen scrubber manifold temperature, Daniel's unverified silicate-like trace (no confirmed contamination/source/route/cause), and unexplained patterned communications bursts with no established life-support connection.
- Character-specific review decisions: Daniel should not gain an “exponential” temperature claim; Elena's action sentence should not be stored as new knowledge; Morgan and Priya stay with an external inspection objective; Ryan's established investigation continues; Zoe's old three knowledge facts must not be removed, and the new rhythmic-burst/power-fluctuation theory remains explicitly unverified.

## Current remote code checkpoint

Branch: `redesign/simplified-writing-workflow`.

Latest code commit before handoff documentation updates: `52592660d671f6f3a6a81cc862aaedf897dbe3e9`. It includes the Quick Edit character-switch fix and restored separate Scene Contract / Writer tabs. Both automated workflows passed:
- [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/39775656160)
- [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/39775656121)

No local desktop/UI verification has confirmed those changes. Tony pulled an earlier fix during this session, but then was asked to stop pulling while the separate-tab layout change was still being completed; do not assume his local checkout is at the latest remote commit. When he resumes, confirm readiness, ensure the app is closed and no generation is running, inspect the local git status, and only recommend a safe fast-forward when appropriate.

## Next development priorities

1. Fix the author-facing ending-state review workflow so corrections to current situation, locations/physical state, character knowledge, and objectives can be made without JSON.
2. Ensure Changes to Review refreshes from the exact currently edited preview; it must not display stale location proposals after a full-state preview edit.
3. Ensure character-dropdown switching preserves each character's own data and never saves the previously visible field under the newly selected name.
4. Keep the proposed update preview-only until Tony explicitly approves Apply State Update.
5. Resume live testing one simple action at a time. Roadmap remains: finish Mars test, use a fresh children's-book project as a cross-genre check, then return to `Taken at Dusk`.

No ending-state update was applied in this session.

---

# Latest working-session note — October 22, 2026

Read [CHAT_HANDOFF_LATEST.md](CHAT_HANDOFF_LATEST.md) first for the detailed current checkpoint.

Tony asked to stop for tonight and **not pull the latest changes to the laptop yet**. Latest code edits live on remote branch `redesign/simplified-writing-workflow`; local code has not been updated.

- Scene 4 in the Mars story remains saved/accepted. Its analysis completed, but the proposed ending-state changes were not applied. Rebuild the proposal after updating StoryBuilder, then review it with Tony one field at a time.
- Quick Edit bug diagnosed and fixed remotely: changing the character dropdown caused the callback to save the text for the previously displayed character under the newly selected character name. The fix tracks the loaded character name and saves under that old name before loading the next character. Regression test added; both CI workflows passed on latest code commit `52592660d671f6f3a6a81cc862aaedf897dbe3e9`.
- Tony prefers separate **Scene Contract** and **Writer** tabs because the combined vertical workspace was harder to scroll and see. This has been restored remotely in the same latest commit; both tests and compile workflows passed:
  - [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/39775656160)
  - [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/39775656121)
- Do not apply the current Quick Edit preview. The six-character fields looked identical, and the old screen may have a contaminated in-memory draft. On resume: check readiness and app state first, run `git status -sb`, reconcile local changes if any, then fast-forward pull only when safe; use `python3` for tests and launch commands. Re-analyze the accepted Scene 4 after the updated app starts and verify character-specific knowledge/objectives before applying any state update.
- Preserve the story's unresolved threads: the scrubber manifold keeps heating, Daniel's silicate-like trace remains unverified, and the patterned communications bursts are unexplained. At Scene 4's end, Elena has begun partial pressurization while Morgan and Priya check external housing mounts; internal inspection findings must not be invented.
- Tony prefers instructions one at a time. Do not offer a multi-field list when he is actively working through Quick Edit.

No changes were pulled onto the laptop, and no state update was applied.

---

# IMMEDIATE NEXT STEP: latest prompt fixes, October 21, 2026

Local full-suite result on the previous audit code: **330 passed, 4 failed**. A second, dynamically assembled audit prompt still had genre-specific mystery language even after the integrity-audit system prompt had been generalized. This was fixed along with stale test assertions; the compact validator also retains explicit guidance to check acknowledged requests/preferences while remaining below 1,500 characters. A regression assertion now checks that the generic dynamic audit prompt contains neither `abduction` nor `Tiffany`.

Latest remote branch code/test commit: `14cb7ba4586d94ee9c52c894a8069a7b7f40e49d` (the newest handoff update follows this code commit). Tony's laptop has not yet pulled or tested it. Next, one command at a time:
```bash
cd ~/Documents/StoryBuilder && git pull --ff-only
```
Then:
```bash
cd ~/Documents/StoryBuilder && python3 -m pytest -q
```
Share the full output before taking any further action. Do not launch StoryBuilder or modify either novel until the test result is clean.

The read-only `The-Long-Way-Home` package audit found 45 regular files, no symlinks, no unreadable files, correct Mars crew cards, and current pointer Chapter 1, Scene 3. The only old-character hits are Maya x2 / Chloe x2 in `Chapter_01_Section_01_draft.txt`. Normal historical retrieval excludes `*_draft.txt`; startup restores accepted prose rather than this saved draft. Do not delete it during verification. `README.md` and `TEST_PROTOCOL.md` mentions of *Taken at Dusk* are documentation and are not loaded into Writer reference context. Keep the real `Taken_at_Dusk` novel untouched.

---


# LATEST HANDOFF: Cross-novel contamination audit — October 21, 2026

Read `CROSS_NOVEL_CONTEXT_AUDIT_2026-10-21.md` for the code-source inventory and limits. The audit found previous-novel assumptions in shared runtime prompts and helpers. Removed character/title examples from the chat UI and guided setup, a character-name search cue from continuity retrieval, abduction-specific prose from the general scene integrity audit, and specific scent descriptors from clue ranking/recovery. The shared Writer and scene-planning rules now treat the generated state recap as fallible and preserve the original Scene Idea/canon/evidence precedence. The fixed prior-novel character-name list used by cast inference was replaced with names derived from the current story. Added regression tests for runtime prompt/source isolation and sibling package/manuscript isolation.

Package-source review confirms `StoryPackage.load(folder)` uses the selected folder only, Writer reference files are assembled from the active package object, history retrieval uses that package path, and novel switching stops the previous Writer process. Root audit/handoff Markdown and story-heavy automated test fixtures are not passed as files to the live Writer. A remaining conditional helper generates identity/location/vehicle questions only when the supplied knowledge establishes an abduction/captivity event; a mere missing person or unknown identity must not create kidnapping questions. It does not read another novel's files by itself.

**Local test status:** last run before this batch was `326 passed, 5 failed`. The branch now fixes the wording assertions and validator size, and adds additional regression tests, but no local verification exists yet. Next on laptop: `git status -sb`; if clean on `redesign/simplified-writing-workflow`, `git pull --ff-only`, then `python3 -m pytest -q`.

**Do not alter novel data yet.** After tests pass, run the read-only package scan from chat against `~/Documents/MyNovel/The-Long-Way-Home`, which reports path/symlink and prior-novel keyword counts without printing story prose. Share the results before any cleanup. The actual local package has not yet been scanned, so copied files or notes in that folder remain a possible cause. Keep the saved Mars Scene 3 contract and `Taken_at_Dusk` untouched. Do not generate or accept prose during this audit. Launch directly with `python3 storybuilder.py`, not `./start.sh`, during the check.

---

# LATEST CHECKPOINT — Read-only copyable Writer direction plus generic prompt/state safeguards — October 21, 2026

Current redesign branch changes include the read-only copyable Writer Scene Direction and a larger generic-prompt/state-safety cleanup. These changes are committed to `redesign/simplified-writing-workflow` but have **not** been verified by Tony's local full test suite.

**Read-only / copy:** `storybuilder.py` shows Scene Direction as `state='disabled'` and `exportselection=False`. Internal refresh temporarily enables it and returns it to disabled; **Copy Scene Direction** puts the complete text on the clipboard. The widget is removed from live spell-check edit hooks. Scene Idea remains the editable source. Tests in `tests/test_generic_prompt_isolation.py` test button/state declaration and full-text copy; `tests/test_scene_workflow_safety.py` checks internal refresh ends disabled.

**Generic state correctness:** Shared Writer, Scene Contract, validator, Scene Idea suggestion, and character-knowledge prompts have been generalized to avoid story-specific examples/details. Generated `current_situation` is explicitly a fallible summary; accepted prose, canon, and the Scene Idea/author corrections are evidence for established history. Unverified summary-only claims must not be repeated as fact. Scene Idea generation uses the same rule. A missing person or the word `kidnapper` alone must not cause state analysis to invent a kidnapping; question inference requires an explicit event signal. Character-name exclusion and demeanor clue deduplication no longer depend on names from one novel. Tests are updated in `tests/test_scene_contract.py`, `tests/test_scene_idea_suggestion.py`, `tests/test_state_analysis_transitions.py`, `tests/test_scene_workflow_safety.py`, and new `tests/test_generic_prompt_isolation.py`.

Newest related commits include `6cf95f6` (read-only/copy button), `c79d1f4` (copy tests), `0d2972c` (read-only-after-refresh test), `0e1818b` (Scene Idea precedence wording), `2225f30` (do not infer abduction from label alone), `de57611` and `e0f3c67` (generic prompt tests/fixture), `e1f7cab` (updated Writer prompt assertions), `d12ba39`/`67cf855` (explicit Scene Idea evidence precedence), and documentation updates. Branch head may advance from these as commits are sequentially recorded.

**Story data:** No novel package was edited by this work. The saved Mars Scene 3 contract with End `Elena issues clear next steps for isolating the source of the contamination.` remains as last confirmed. Do not regenerate it or generate/accept prose until tests pass and the visible direction can be reviewed. The stale saved `current_situation` phrase about a pressure leak was not manually changed; the new generic evidence hierarchy is intended to prevent a summary-only claim from being carried forward as established history. Never touch `Taken_at_Dusk` as part of these changes.

**Next step on Tony's laptop:** `cd ~/Documents/StoryBuilder && git status -sb`. If clean on `redesign/simplified-writing-workflow`, use `git pull --ff-only`, then `python3 -m pytest -q`. Do not use `python`; `python3` is required. After passing tests, start directly with `python3 storybuilder.py` (avoid `./start.sh` during this inspection) and verify that Scene Direction cannot be edited and **Copy Scene Direction** copies the full text. Paste it into chat for review. Do not sync or change novel data in this verification step.

---

# LATEST FOLLOW-UP — Read-only, copyable Scene Direction — October 21, 2026

Tony asked that the generated Writer box be read-only but easy to copy into chat. Implemented on the redesign branch:
- Writer's **Scene Direction** widget now starts disabled/read-only, with text selection available and `exportselection=False` so selecting the text does not rely on another application's primary selection.
- **Copy Scene Direction** copies the entire displayed guidance to the clipboard and reports when it is ready to paste with Ctrl+V.
- `_build_scene_direction` temporarily enables the widget only for its internal refresh and always returns it to disabled state.
- Removed the generated direction widget from live spell-check hooks because it is no longer an editable field. The saved Scene Idea remains editable.
- Added tests for the read-only UI and full-text clipboard action.

Latest main code commit for this request: `6cf95f6`; copy/read-only regression tests: `c79d1f4`; docs: `6c4d5bb`. This is StoryBuilder code and docs only; no novel package was modified. Current test suite must be rerun locally after pulling the complete latest branch. Next: `git status -sb`; if clean on `redesign/simplified-writing-workflow`, `git pull --ff-only`, then `python3 -m pytest -q`. Fix any test failures on the branch before launching. Once tests pass, launch directly using `python3 storybuilder.py`, verify Scene Direction cannot be typed into but **Copy Scene Direction** copies all of it, and paste it in chat for review. Do not regenerate the already corrected Scene 3 contract or generate/accept prose during this UI check. Keep `Taken_at_Dusk` untouched.

---

# LATEST FOLLOW-UP — Scene Idea precedence clarified — October 21, 2026

The final wording in the shared Writer and Scene Idea suggestion prompts now explicitly recognizes the existing Scene Idea and author corrections as evidence when correcting a stale generated state recap, alongside accepted prose and canon. This update follows the generic-prompt cleanup and is committed on `redesign/simplified-writing-workflow` at `d12ba39` (Scene Idea suggestion prompt) and `67cf855` (Writer prompt). The latest source/test branch also includes generic state-question safeguards, name-independent scene-cast inference, and regression tests for cross-genre prompt isolation.

**Verification pending on laptop.** The last complete local test run before this batch was `318 passed`. Do not treat that as verification of the new batch. Next: Tony runs `git status -sb` in `~/Documents/StoryBuilder`; if the worktree is clean and branch remains `redesign/simplified-writing-workflow`, pull with `git pull --ff-only` and run `python3 -m pytest -q`. The current local Mars novel data has not been edited by these code changes. Leave Chapter 1 Scene 3's saved contract and Idea as they are; do not regenerate or accept prose as part of this verification.

---

# LATEST MILESTONE — Scene Idea authority and generic-prompt cleanup — October 21, 2026

Tony reminded us that writers should not have to repair the Writer prompt or Current State form by hand; the editable Scene Idea is the normal author-facing correction point. The app was still treating its generated current_situation recap as absolute history, and shared prompts contained novel-specific examples. Code changes have now been committed to `redesign/simplified-writing-workflow`:

- `storybuilder.py`: Writer system prompt and Scene Direction now treat the saved current_situation as a fallible starting summary. Accepted prose, canon, and explicit author intent support established history; an unsupported state-only claim must not be repeated as fact. The Scene Idea can explicitly correct a stale recap. Removed the separate fixed list of character names from cast inference and instead derive name tokens from the current package.
- `builder/scene_contract.py`: removed the globally embedded bubble-bath example and mystery-specific clue guidance. Author Scene Idea and stated boundaries remain primary; supporting direction/contract must not overrule them. Validator guidance is now genre-neutral.
- `builder/scene_idea_suggestion.py`: a saved situation is a starting summary, not sole proof of historical claims; the idea suggester must not carry forward unsupported state-only claims as facts.
- `builder/state_manager.py`: removed novel-specific character examples from the knowledge-audit prompt. Routine-knowledge and clue deduplication guidance no longer names the prior novel's characters. Character demeanor deduplication derives identity from the current fact instead of a hard-coded Tiffany-specific key. Missing-person or unknown-identity text alone no longer generates kidnapping questions; those questions require supporting event evidence. Vehicle-plate follow-up wording is generic.
- Regression tests updated/added in `tests/test_scene_contract.py`, `tests/test_scene_idea_suggestion.py`, `tests/test_state_analysis_transitions.py`, and new `tests/test_generic_prompt_isolation.py`.

**Important story-data boundary:** This was a StoryBuilder source/test/doc-only change. The local Mars package has not been edited. Its saved Chapter 1 Scene 3 `current_situation` still contains the phrase about a prior pressure leak; this is known stale/unsupported text. We did not silently alter it. The Writer instructions now explicitly prevent a generated recap alone from making consequential historical claims canonical. Do not have Tony manually edit Current State or Writer direction as a workaround, and do not touch `Taken_at_Dusk`.

**Verification status:** The last laptop full suite, before these prompt/state-manager changes, was `318 passed in 0.54s`. Latest source changes have NOT yet been pulled or locally tested. Next step: run `cd ~/Documents/StoryBuilder && git status -sb`; if clean and on `redesign/simplified-writing-workflow`, run `git pull --ff-only`, then `python3 -m pytest -q`. The test run is required because multiple shared prompts and state-manager rules changed. Only after all tests pass should we launch directly with `python3 storybuilder.py` (not `./start.sh`), verify the Prepare Scene/Writer layout remains correct, and then review what the Writer direction shows. The saved Scene 3 contract now has the intended End value; do not regenerate/replace it. Do not generate or accept prose before reviewing how the generic state-precedence fix behaves.

---

# LATEST FOLLOW-UP: Keep novel examples out of runtime prompt — October 21, 2026

Tony correctly flagged that the failing unit test output contains Tony/Maya narrative details from an existing test fixture. Those strings are inputs to an isolated automated test; they are not pulled from the currently open Mars novel package or passed to live Writer calls just because the test runs. The failure was about an exact prompt sentence assertion, not a live continuity leak.

However, the previous generic contract-prompt edit used a concrete illustrative phrase derived from the Mars Scene 3 idea. Removed that Mars-specific example from `builder/scene_contract.py`; the instruction now speaks only in general terms about a scene purpose stating a specific outcome, including when not labeled End. Kept the exact legacy sentence checked by the existing test, along with the expanded generic guidance. This respects the rule that novel-specific plot facts belong in the novel package, not StoryBuilder source.

Latest prompt commit: `d2d998f` (`Keep contract endpoint guidance independent of novel examples`). Tony's laptop has not yet pulled this follow-up. After a clean-status check on `redesign/simplified-writing-workflow`, pull with `git pull --ff-only` and run `python3 -m pytest -q`. The last run was 317 passed, 1 failed due solely to the original exact-wording assertion; the wording was restored in `2daf3f4`, and the Mars-specific illustrative phrase was then removed in `d2d998f`. Full suite must be rerun locally to verify both. Do not edit or regenerate either novel package as part of this code correction.

---

# LATEST FOLLOW-UP: Existing prompt wording test restored — October 21, 2026

Tony pulled the endpoint-generation prompt clarification and ran `python3 -m pytest -q`: **317 passed, 1 failed**. The only failure is `SceneContractTests.test_plain_english_idea_survives_as_primary_writer_intent`, which asserts the exact phrase `When the idea gives a clear endpoint, put that endpoint in hard_stop` is present in the contract-builder prompt. The new prompt had equivalent but rewritten wording. Updated `builder/scene_contract.py` on `redesign/simplified-writing-workflow` to restore that exact sentence while retaining the expanded guidance that a clearly intended outcome can serve as the endpoint even when not labeled End. This is a prompt wording compatibility correction, not a change to the fallback logic or novel data.

Latest code commit: `2daf3f4` (`Preserve explicit endpoint wording for regression test`). Tony's laptop has not yet pulled this correction. Next: from `~/Documents/StoryBuilder`, confirm branch/status, then `git pull --ff-only`, then `python3 -m pytest -q`. Do not restart into the scene workflow or replace the saved contract until tests pass. Keep `The Long Way Home` and `Taken_at_Dusk` files untouched during this code/test step.

---

# LATEST FOLLOW-UP: Contract endpoint generation clarified — October 21, 2026

Tony checked the saved local package after Writer's End line remained empty. The read-only inspection confirms this is a missing stored endpoint, not just a display problem. The active package is Chapter 1, Scene 3. Its writing_guidance.json entry has a saved Scene Idea and a short direction, but top-level end_condition, top-level hard_stop, and nested scene_contract.hard_stop are all missing. The nested contract contains only boundaries, max_attempts, and required_beats.

The earlier endpoint-display fallback remains valid, but cannot produce an endpoint from no saved value. Updated the generic contract-builder prompt so stated scene outcomes, such as a meeting intended to let someone issue next steps, are translated into a concise stopping point even when not explicitly labeled End. It tells the model to stop at the author's stated outcome, avoid adding later actions, and leave the endpoint blank only when no defensible outcome or temporal boundary exists. Added a regression test. This is generic behavior, not a Mars-specific rule.

Current commits on redesign branch: 979d625 (contract prompt), 22c5fd7 (regression test), 1a9516b (plan documentation), plus prior endpoint fallback and button consolidation commits.

Local verification pending: Tony's laptop has the prior milestone pulled and tested at 317 passed, but has not pulled these newest prompt/test/docs updates. After a clean-status check in ~/Documents/StoryBuilder on redesign/simplified-writing-workflow, use git pull --ff-only, then python3 -m pytest -q. After tests pass, restart directly with python3 storybuilder.py. The saved Scene 3 contract still has no endpoint until a new contract is deliberately generated. When ready, Tony must click the single Prepare Scene... action and confirm replacement of the saved generated contract; this preserves the Scene Idea and does not alter accepted prose or state. Review the resulting End / Hard Stop before proceeding. Do not generate or accept prose during this contract check. Do not edit the Mars novel files from the coding tools and do not touch Taken_at_Dusk. main remains untouched.

---

# LATEST MILESTONE — Single scene-preparation action and saved endpoint fix — October 21, 2026

Tony confirmed the full-width Write layout is easier to use and that the Scene Details panel expands/collapses correctly. The latest StoryBuilder changes on `redesign/simplified-writing-workflow` are:

- **Saved endpoint fallback:** Writer's Scene Direction now resolves the endpoint through `SceneContract.from_guidance`, so a saved nested `scene_contract.hard_stop` is shown even when the legacy/top-level `end_condition` field is empty. If a saved contract is malformed, direction building falls back to the readable legacy endpoint fields instead of failing outright.
- **One primary scene-preparation action:** The Scene Idea row now has **Prepare Scene...**. It runs the existing contract-generation workflow and keeps the existing replace-confirmation safeguard. The separate **Build Scene Direction** button is removed from Writer, avoiding two controls that appear to build overlapping prompt guidance. Direction still refreshes automatically from the app's internal update paths.
- **Regression coverage:** Added a test that a nested saved hard stop appears when `end_condition` is missing, plus a UI-source check for the single primary preparation action.
- StoryBuilder code/tests/plan/handoff only. No Mars novel files were changed, and `main` remains untouched.

**Verification status:** These remote updates have not yet been pulled or tested on Tony's laptop. After checking `git status -sb` in `~/Documents/StoryBuilder`, fast-forward pull only if the checkout is clean and on `redesign/simplified-writing-workflow`. Then run `python3 -m pytest -q`. If it passes, open the app directly with `python3 storybuilder.py` (not `./start.sh` for this UI check). Confirm the Scene Idea row shows **Prepare Scene...**, Writer no longer has a manual **Build Scene Direction** button, and the displayed Writer direction includes the saved **End:** line. Do not click Prepare Scene during this verification if the current saved contract should remain unchanged. Do not generate or accept a scene as part of the check.

---

# LATEST MILESTONE — Full-width Write layout and collapsed details — October 21, 2026

Tony reported that the side-by-side layout did not let him comfortably see the workspace. Revised the first slice accordingly:
- The Write pane split is now vertical and full-width rather than horizontal; Writer receives a larger pane.
- The Scene Idea remains visible at the top with short everyday actions: Suggest Idea, Save Idea, and a Scene Details toggle.
- Contract generation/reload tools, continuity focus, starting-state summary, beginning/middle direction, hard stop, beats, boundaries, and automatic-attempt control are under a collapsible **Scene details (optional)** area, closed by default.
- Added a test for opening/closing that detail area and changed the layout test to assert the vertical orientation and weights.
- Commits: `c6a9856` (layout), `d2701c1` (tests). A docs-only plan update follows this milestone.
- The current laptop checkout has not pulled these changes or tested them yet. The last confirmed laptop suite was **314 passed** before this revision.
- No novel files were changed. `main` remains untouched.

**Next action:** Pull the latest redesign branch onto Tony's laptop, run `python3 -m pytest -q`, and inspect the Write view. Confirm the Scene Idea controls are visible, Scene details starts collapsed and expands on click, and the Writer area is full-width below. Do not generate/accept a scene during the layout check. If the vertical split is too short, try resizing its sash only for observation and report what fits; avoid further UI edits until that screen check is confirmed.

---

# LATEST MILESTONE — First unified Write workspace slice — October 21, 2026

Code changes now on `redesign/simplified-writing-workflow`:
- `_build_write_workspace()` creates one top-level **Write** destination with a horizontal, resizable split. The existing Scene Contract panel is placed on the left and the existing Writer panel on the right. Both retain their existing controls, callbacks, and scrollable content.
- The separate top-level Scene Contract and Writer destinations are no longer registered; they are embedded in Write. Write is built first so it opens as the primary area. The Current State page remains for now as an advanced/direct-edit destination.
- `tests/test_scene_workflow_safety.py` has a structural regression test verifying that Write contains the two panels and that the detailed builders do not register separate destinations.
- Relevant commits: `1755d13` (combined Write workspace) and `b038b93` (test).
- This is the first workflow slice, not the finished redesign. The two panes currently reuse the existing long forms; next iterations should simplify and collapse detailed contract controls rather than remove working functionality abruptly.
- The last laptop test run was before these new code/test commits and reported 313 passed. These latest commits have not yet been pulled or tested on the laptop.
- `main` remains unchanged, and no novel-package files were edited.

**Next action:** Fetch/pull the redesign branch on Tony's laptop and run `python3 -m pytest -q`. If tests pass, launch StoryBuilder directly with `python3 storybuilder.py` (not `./start.sh`, which may sync) and inspect only the new Write layout. The test novel remains `~/Documents/MyNovel/The-Long-Way-Home`; do not open or change `Taken_at_Dusk` for this check. Confirm how the two panes appear before making further visual changes.

---

# LATEST MILESTONE — Window-close sync safety — October 21, 2026

First code change in the redesign branch:
- `storybuilder.py`: the OS window-close event (`WM_DELETE_WINDOW`, X button / window close) now calls `_close_without_sync`, not `_close_and_sync`. Explicit **Close & Sync Novel** and **Sync Novel** controls remain available for deliberate sync.
- `tests/test_scene_workflow_safety.py`: added a regression test to ensure default window close remains local-only.
- Commits: `685491c` (code) and `4d4be07` (test). These changes are on `redesign/simplified-writing-workflow`; `main` is unchanged.
- The change was made on GitHub through the connected repository editor. Tony's laptop has not pulled these new code/test commits yet, so no local run has verified them.

**Next action:** Have Tony run `git pull --ff-only` from `~/Documents/StoryBuilder`, then `python3 -m pytest -q`. Keep the one-step-at-a-time workflow. After the tests pass, proceed with the first Write-workspace slice. Do not touch or sync any novel repository.

---

# LATEST UPDATE — October 21, 2026

The design inventory is now recorded in `REDESIGN_PLAN.md`, including a mapping of all 16 existing UI sections into the proposed Home, Write, Story Bible, Plan, Manuscript, and Advanced areas, plus the first implementation slice. Latest redesign-branch planning commit: `141fa50bf55bd781555c69793d86777cde9b270d`.

No application code changed in these latest commits; they only add/update design and handoff documentation. The last full code test run on this branch was `python3 -m pytest -q` with **312 passed**. Next: pull the latest redesign branch onto Tony's laptop, confirm the worktree is clean, then begin the first Write-workspace slice after inspecting the current Writer and state-acceptance handlers. Do not change novel repositories or sync novel content as part of this step.

---

# CURRENT HANDOFF — StoryBuilder redesign — October 21, 2026

This section supersedes older status and branch-policy notes later in this historical handoff.

## Current repository state
- Working branch: `redesign/simplified-writing-workflow`.
- The only remaining local/remote StoryBuilder branches are `main` and `redesign/simplified-writing-workflow`.
- All other discovered remote branches were removed after comparing them against `main`; the final local `experiment/leaner-scene-boundary` branch was deleted only after confirming its commits were already included in `origin/main`.
- The automatic next-scene suggestion fix from PR #49 is included on the redesign branch. PR #49 was merged into the redesign branch, not into `main`.
- Tony ran `python3 -m pytest -q` on the redesign branch and got **312 passed**. This was before the latest documentation-only change.
- No novel repository or novel-package files were edited as part of branch cleanup or this redesign planning checkpoint. Keep `Taken_at_Dusk` untouched.

## Redesign baseline
- Created `REDESIGN_PLAN.md` on the working branch. It is a design document, not an application-code rewrite.
- Code inspection found 16 current UI sections: Talk to Builder, New Novel Assistant, Story, Canon & Rules, Change Assistant, Characters, Relationships, Locations, Story Modules, Story Planning, Story Interview, Scene Contract, Scene Planner, Current State, Writer, and Manuscript.
- The top toolbar separately exposes New/Open, Save/Save As, Validate, Sync Novel, Close, and Close & Sync Novel.
- Proposed main areas: **Write**, **Story Bible**, **Plan**, and **Manuscript**, with Home/Open at startup and advanced/diagnostic tools available outside the ordinary writing path.
- The Write workspace should combine editable next-scene idea, contract preparation, prose generation/revision, acceptance, reviewed continuity updates, and automatic preparation of the next idea. No direct JSON editing should be required for ordinary writing.
- Closing the app must not trigger an unexpected sync. Save and novel sync should be clear, separate, deliberate actions.
- Preserve the existing shared novel-package format and compatibility with LocalStoryChat. Keep code and novel repositories separate.

## Next action
1. Fetch/switch to the latest `origin/redesign/simplified-writing-workflow` on Tony's laptop so the new `REDESIGN_PLAN.md` and this handoff update are present locally.
2. No code edits yet. Build a feature inventory mapping all current UI functions to the proposed areas, identify duplicates and advanced functions, and decide the new writing screen interaction before restructuring code.
3. Keep using `python3`, not `python`, for every Python terminal command.
4. After each meaningful code or workflow milestone, update this handoff immediately. Run `python3 -m pytest -q` after meaningful code changes, and test live model behavior only with `The Long Way Home` in the designated safe test package.

---

## Writer prompt assembly map, October 21, 2026

The current Writer input is assembled from the static system prompt, generated Scene Direction/contract context, a separate scene-boundary brief, selected novel reference files, and optional historical manuscript excerpts. The static prompt and scene brief repeat some protections for required beats, emotional agency, clue boundaries, and hard stops. This may be purposeful reinforcement; do not remove rules without classifying them and testing. The read-only Writer Context Preview assembles the layers and reports estimated size plus included/pruned/compacted files. See [STORY_FLOW_REPAIR_PLAN.md](STORY_FLOW_REPAIR_PLAN.md). Next: inspect `SceneContract.writer_prompt_context`, then review the preview in the disposable package. No code or novel change.
## Natural-flow investigation checkpoint, October 21, 2026

Current plan: [STORY_FLOW_REPAIR_PLAN.md](STORY_FLOW_REPAIR_PLAN.md). Chapter 1 flows from character interaction into plot more naturally than Chapter 2, which sometimes repeats distress/reassurance and overexplains already-clear emotions. This is a hypothesis about craft, not proof that prompt length alone caused the difference.

History confirms the creative-first Writer prompt is already merged: [1c88b91](https://github.com/tony21675/StoryBuilder/commit/1c88b9139203886224a83eb6cdf084e72073b52f), merged at [e43314e](https://github.com/tony21675/StoryBuilder/commit/e43314e17173d178588fea31c5969769007a7a1e). Next, inspect the full runtime prompt/context and any saved traces; do not blindly revert prompts or change code yet. Test one proposed simplification in a disposable package, holding story anchors and model/settings constant. Preserve canon, character knowledge, required beats, and explicit hard stops. No novel prose or state changed.

## Active handoff — October 21, 2026: current audit checkpoint in [CHAT_HANDOFF_LATEST.md](CHAT_HANDOFF_LATEST.md) and [APP_AUDIT_2026-10-21.md](APP_AUDIT_2026-10-21.md)

**Current checkpoint:** The whole-app audit is at [APP_AUDIT_2026-10-21.md](APP_AUDIT_2026-10-21.md); the up-to-date repair/status/next-step summary is [CHAT_HANDOFF_LATEST.md](CHAT_HANDOFF_LATEST.md). The selection-aware Focused Change repair is committed; the latest code/test baseline passed both CI workflows (302 unit tests; compile passed). This is not yet a live local-model test. The next step is safe local update plus a focused edit in a disposable package. Do not accept or sync the current Scene 3 test draft.



**Current state:** PR #44, [Experiment: creative-first Writer prompt](https://github.com/tony21675/StoryBuilder/pull/44), is merged into `main` at `e43314e17173d178588fea31c5969769007a7a1e`. The merge includes the creative-first Writer prompt, streamed initial-draft output, and Scene Contract/continuity-audit refinements. This changed StoryBuilder application code only. MyNovel and accepted manuscript prose were not changed by the merge.

**Hard rule for every future session:** After each meaningful change or milestone, update the relevant handoff file(s) immediately, before proceeding to the next step. Update this `CHAT_HANDOFF.md` for StoryBuilder code, prompt, application workflow, sync, launch, or test milestones. Update MyNovel's `HANDOFF.md` for story-plan, novel-state, manuscript, or active-story-position milestones. For cross-repository changes or any milestone that affects how the next session should proceed, update both. Record what actually happened, verification/results, current status, safety boundaries, and the exact next action. Do not wait until the end of a task, and do not skip this rule when a new chat starts.

**Verified local checkpoint (October 21, 2026):** Tony ran `cd ~/Documents/StoryBuilder && git status -sb`; output was `## main...origin/main`. StoryBuilder launched from that checkout. The UI appears to show Chapter 3, Scene 3 in the real/main novel. Treat this as the real package unless its path proves otherwise. No generation or state update has been reported; do not click Write Next Scene, Regenerate, Accept, Analyze Accepted Scene, Apply State Update, or sync the novel for this test.

**Code inspection confirmed the package-selection mechanism:** `builder/workspace.py` sets `WORKSPACE_ROOT` to the parent of the StoryBuilder repository by default, unless `STORY_WORKSPACE_ROOT` is set. `NOVEL_ROOT` defaults to `WORKSPACE_ROOT/MyNovel`, unless `STORY_NOVEL_ROOT` is set. Startup loads the only discovered package automatically, or asks which package to open when multiple package folders are present. A folder with `story_bible.json` directly inside can itself be the package. These facts are verified from source; the actual runtime environment override and active local path have not yet been checked.

**Author decision, clarified October 21, 2026:** Chloe is meant to be Tony's rock at this moment. She recognizes that Tony is on the verge of losing control and takes the initiative to pull him back with a long, grounding hug. Chloe normally does not show this unusually soft, openly comforting side of herself, so the tenderness should catch Tony and the surrounding group off guard. The emotional focus is Chloe steadying Tony, not Chloe seeking reassurance for her own distress. Tony is moved enough that tears come to his eyes, and he tells her something to the effect of, “You have no idea how much I needed that from you.” He then expresses his gratitude and calls her “my little wildcat” for the first time. Preserve the surprise, tenderness, and shift in their dynamic without overexplaining or making the moment melodramatic.

**Verified package comparison:** A read-only `diff -qr --exclude=.git` showed only backup snapshots and `writing_guidance.json` differ between `~/Documents/MyNovel/Taken_at_Dusk` and `~/Documents/MyNovel_creative_test/Taken_at_Dusk`. Both packages contain Chapter 3 Scene 3, “Forming the Private Effort.” The focused guidance diff shows the above difference in emotional agency; the real package's file was timestamped 2026-10-20 23:57 and the test copy's 23:02, but the user’s explicit decision now settles the intended beat. No package files have been edited in this conversation. Do not modify the real package as a side effect of testing.

**Verified test-launch and first-generation milestone (October 21, 2026):** Tony confirmed the app was open with the test-copy path and Chapter 3, Scene 3 selected after launching with `STORY_NOVEL_ROOT="$HOME/Documents/MyNovel_creative_test/Taken_at_Dusk" ./start.sh` from `~/Documents/StoryBuilder`. He generated one draft and pasted the complete prose into chat for review. The draft remains unaccepted; no state update or sync was reported. Test package and isolation were user-confirmed.

**First-draft review findings:**
- **Strengths:** Atmosphere and emotional tone are clear; Chloe does initiate the hug and the “my little wildcat” nickname lands as a tender moment. Maya's reaction and each person's broad contribution give the group some distinct texture.
- **Emotional-agency miss, now clarified by Tony:** Although Chloe initiates the hug, the draft frames her as distressed and needing to be anchored herself, and Tony asks whether *she* is okay. The intended reversal is that Chloe is the rock: Tony is close to losing control, she recognizes it and deliberately grounds him, and this normally-uncharacteristically soft gesture surprises Tony and the others. Tony's eyes should fill with tears, and he should say in his own natural voice something like, “You have no idea how much I needed that from you.”
- **Hard-stop/boundary miss:** The draft proceeds from tentative broad roles into specific task assignments (“start flagging anomalies,” “check ... routine gaps,” “map out our approach for discreet surveillance”) and frames the kitchen as a command center. This goes beyond “the rough framework begins to take shape” and violates the explicit boundary against finalized assignments and detailed investigation/surveillance planning.
- Maya's and Chloe's suggestions stay at the level of general possibilities and do not name a concrete destination or new evidence; retain that kind of tentative brainstorming rather than turning it into actionable leads.
- A CLI performance/footer line appears after the prose in the pasted output; treat it as UI/output cleanup, not story text.

**Focused Change #1 review (October 21, 2026):** The first Focused Change changed Chloe's approach to “sudden certainty” and called the hug “long, grounding,” so there was a small improvement in physical staging. However, the core emotional reversal still did not land: Chloe continues to tremble, says “I don’t think I’m okay,” and is portrayed as needing Tony to anchor her; Tony still asks if she is okay. There are no tears or line expressing how much Tony needed her support, and no clear reaction from the group to Chloe's uncharacteristic tenderness. The correction therefore only partially succeeded and the targeted requirement remains unmet. The hard-stop overrun was unchanged as requested, and must remain a separate correction. Draft stays unaccepted; no state update or sync reported.

**Focused Change #2 review (October 21, 2026):** The second returned version still preserves the exact failed dialogue: Tony asks “You okay?” and Chloe replies “No, I don’t think I’m okay.” It also keeps Chloe trembling and frames the hug as anchoring her. Tony's tears, his line about how deeply he needed her support, and the group's surprise at her unusual softness are still absent. Only a few descriptive phrases changed, so the core correction again failed. The later task assignments and discreet-surveillance planning are still present as expected; they were intentionally out of scope. The draft is unaccepted and no state update or sync is reported.

**Focused Change #3 result (October 21, 2026):** The next attempt did not modify any prose. StoryBuilder returned: “The model could not produce a safe, exact-text edit after two attempts. The quoted target does not appear in the current draft exactly.” This is a target-selection/edit-contract failure before a successful edit, not evidence that the requested emotional change was implemented or that the prose itself was rejected. The previous instruction described the passage by beginning and ending phrases rather than providing a verified contiguous exact-text target, so it may not have satisfied the Focused Change mechanism's target contract. The draft remains unaccepted; no state update or sync is reported.

**Focused Change implementation inspected (October 21, 2026):** `storybuilder.py` passes the complete current draft and the user's request into `builder.focused_revision.build_focused_revision_prompt`; this UI workflow has no manually selected target span. The local model must return JSON with `target_text` and `replacement_text`, with `target_text` copied verbatim from the draft. `apply_focused_replacement` allows whitespace variations but rejects a target that is absent or ambiguous, a whole-scene target, or an overbroad replacement. The reported error occurs when the model's proposed target cannot be found, and the app correctly leaves the draft unchanged. `tests/test_focused_revision.py` covers missing/ambiguous targets and exact replacement behavior, but it cannot guarantee the local model will quote a longer passage reliably.

**Next step:** Do not change code or repeat the broad range-based prompt without agreement. For one further content attempt, target a shorter, unique dialogue passage and explicitly instruct the model to copy the `target_text` verbatim from `CURRENT_DRAFT`, character for character, and return only that local JSON patch. If that fails, stop live retries and agree on a focused workflow/prompt improvement with a regression test. Keep the later hard-stop/task-assignment correction separate, draft unaccepted, and the real MyNovel package untouched.

**Branch policy:** Tony requested one working branch, `main`, with no new feature or experiment branches. Prior merged PR work is already integrated. Old remote branch references still exist because this session's GitHub connection cannot delete branch refs. The local experimental worktree at `~/Documents/StoryBuilder-creative-first` is detached at PR #44's former head; the former working folder is `~/Documents/StoryBuilder-creative-test`. Do not launch, switch, reset, or delete those local directories until local status and any uncommitted work are inspected.

### Active collaboration rules

- **Discuss first, agree, then change.** No surprise edits. Tony's explicit request authorizes only the specific change requested, not adjacent cleanup or a bundle of fixes.
- **Let the story breathe.** Protect canon, continuity, character knowledge, author boundaries, and meaningful commitments. Do not micromanage every sentence or turn ordinary prose into a checklist. Give the Writer room for natural dialogue, atmosphere, gestures, small moments, connective action, and fitting developments.
- **Keep safeguards purposeful.** Catch real continuity, boundary, and workflow failures without flattening harmless creative variation.
- **Test and review together.** Prefer a small, controlled test and the smallest agreed change. Report what was actually tested; never imply that a live writing test happened when it did not.
- **Keep communication and terminal work concise.** No long copy-and-paste walls of commands, code, or logs in the terminal or chat. Use short commands, targeted excerpts, and concise result summaries.
- **Do not repeat completed investigation** unless new evidence or a specific question makes it necessary.
- **Keep repositories separate.** StoryBuilder code and this handoff belong here; MyNovel content and accepted manuscript prose must not be changed as a side effect.

---

## Latest checkpoint — October 20, 2026: ending-state redesign, context pruning, and historical retrieval (merged)

Tony approved a broad StoryBuilder redesign because proposed ending states repeatedly required extensive manual reconstruction, then supplied a second handoff requiring context reduction without sacrificing continuity. Both requirements are implemented and **merged into main**.

- PR: https://github.com/tony21675/StoryBuilder/pull/37
- Merge commit: `d5117bf950b6fb320446ff2dc2f6dd168b81ff7d`
- `main` was verified at that merge commit before this handoff refresh.
- This is reusable StoryBuilder code only. No MyNovel files or accepted manuscript content were modified.

### Ending-state review redesign
- Writer → Analyze Accepted Scene opens on **Changes to Review**, grouped into situation/time, locations/physical state, objectives, character knowledge, investigative leads, recent events, and other state changes.
- Full reconstructed JSON remains available under **Full State JSON (Advanced)** for deliberate corrections. Applying the proposal still validates and merges against saved current state; omitted fields remain unchanged.
- Ending-state analysis receives compact physical/current context instead of the full state ledger. It no longer repeats the final 3,000 characters of the completed scene.
- Character-knowledge auditing asks for new facts and exact explicit supersessions. The full persisted ledger remains application-owned and is merged, not regenerated wholesale.

### Context pruning and historical continuity retrieval
- Added `builder/continuity_context.py`. It ranks active character knowledge and prioritizes consequential facts such as relationships, promises/secrets, injuries, evidence, clues, and timeline cues. Incidental food/drink and routine details are deprioritized, not deleted from their source ledger.
- If the per-novel writing-notes notebook grows beyond 24 entries, relevant notes are selected for the prompt, falling back to the eight most recent when lexical overlap yields no matches. Supporting people, off-scene anchors, and relationship context are filtered to people referenced by the current scene.
- Character cards and knowledge for characters explicitly named in the scene plan can be included even when those characters arrive later. Opening physical-state context remains limited to the opening cast.
- Extended `builder/manuscript.py` to search the existing accepted manuscript read-only. Writer may receive up to four source-labelled historical excerpts capped at 2,400 combined characters. Retrieval only searches scenes strictly earlier than the target scene and supports legacy `Scene_XX.txt` files under `Chapter_XX` folders. This reuses the manuscript archive rather than creating a competing continuity database.
- Archived excerpts are explicitly historical evidence, not current state. Current saved state and scene direction take precedence over old descriptions. If a detail cannot be found or the source is ambiguous, the Writer is instructed not to invent it or claim certainty.
- Writer status reports approximate before/after prompt size and the number of historical excerpts. Deliberately armed prompt traces capture budget metrics. Estimates use characters divided by four, not the model's exact tokenizer.
- Retrieval is lexical rather than embedding-based. It works best when the scene direction names the relevant person, object, event, or phrase. An implicit detail may not be retrieved unless the prompt offers useful search terms.

### Files changed
`builder/state_manager.py`, `builder/continuity_context.py`, `builder/manuscript.py`, `storybuilder.py`, `tests/test_state_analysis_transitions.py`, `tests/test_continuity_context.py`, `tests/test_scene_workflow_safety.py`, `README.md`, and `CHAT_HANDOFF.md`.

### Verification
- Pre-merge PR-head workflows passed: [StoryBuilder checks](https://github.com/tony21675/StoryBuilder/actions/runs/39364129910) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/39364129912).
- Post-merge workflows on merge commit `d5117bf950b6fb320446ff2dc2f6dd168b81ff7d` passed: [StoryBuilder checks](https://github.com/tony21675/StoryBuilder/actions/runs/39364685933) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/39364685995). Compilation passed and all **272 unit tests** passed.
- Synthetic context benchmark: 126 knowledge facts across three characters, 9,834 source characters (about 2,459 rough tokens) reduced to six selected facts, 344 characters (about 86 rough tokens): **96.5% reduction in that character-knowledge subcontext**. This is not a measured whole-generation prompt reduction.
- The real novel's overall prompt savings and archive-retrieval quality still need a live check on Tony's laptop.

### Next steps for Tony
1. On the laptop, inspect `git status -sb` before syncing. Pull/fast-forward only if the checkout is clean and can fast-forward safely.
2. In Writer, confirm the accepted-scene state preview begins with **Changes to Review**, with the full JSON available in the advanced tab.
3. Generate a test scene without modifying accepted prose/state just for testing. Review the displayed approximate context budget and number of historical excerpts.
4. Explicitly request a clearly named detail from an older accepted scene (for example, which soda was chosen at lunch) to test retrieval. If the excerpt is not found, include the relevant person/object/event in the scene direction; lexical retrieval is not a guarantee for vague references.
5. Check continuity manually during this first live trial, especially character-specific knowledge, later-arriving cast, physical state, and whether an archive excerpt is stale. Report any regression and fix the underlying context-selection logic rather than patching one scene.

---

## Latest checkpoint — October 19, 2026: preserve Planned Beats and Boundaries through Scene Contract

Tony approved repairing the reusable Scene Planner → Scene Contract → Writer handoff after Chapter 3, Scene 3's plan contained all agreed details but the generated read-only contract compressed them into a generic direction and endpoint.

**Implemented on PR #33, branch fix/planned-beats-boundaries:**
- Scene Contract now recognizes explicit **Planned Beats** as author-authored event-level requirements as well as **Required Beats**. Model-invented beats are still ignored.
- Explicit **Boundaries** are parsed separately, retained in the runtime contract, shown in a read-only **Author Boundaries** field, and passed prominently to both Writer and semantic validator prompts.
- Scene Idea remains the editable source of truth; generated beginning/middle and end fields remain read-only. Regenerating the contract re-derives beat and boundary data from the original idea and prevents stale generated values from surviving.
- Writer prompt guidance and UI help now describe Planned Beats and Boundaries consistently.
- Added regression tests for the exact Scene 3 plan format, including all five planned beats, hard-stop preservation, and boundary propagation.

**Verification:** On commit b3b22848c61dc55c512798deaadf1f8f13fe4cc7, GitHub Actions compiled the application and builder modules successfully. Both new focused tests passed. The full 248-test suite still has five previously known unrelated failures: three state-workflow tests (empty ending-state preview/Tk mock behavior), one writer-prompt wording assertion, and one text-selection assertion. No new test failures remain from this change; the complete suite is not fully green. The initial run also exposed a prompt-wording regression, which was corrected and the latest run no longer reports that failure.

**Novel safety boundary:** No MyNovel files, STORY_PLAN.md, writing_guidance.json, current_state.json, accepted manuscript prose, or Scene 3 plan text were changed by this repair. After the code is merged and Tony syncs StoryBuilder, reload/check the Scene Contract for Chapter 3, Scene 3 and regenerate it from the saved Scene Idea. Confirm the five Planned Beats and Boundaries appear in the read-only fields before writing. Do not sync the novel merely to apply the reusable code fix.

PR: https://github.com/tony21675/StoryBuilder/pull/33

---
## Latest checkpoint: October 19, 2026: dark theme detection priority corrected

Tony shared a screenshot after syncing/restarting StoryBuilder: the app still showed a light palette even though his Linux Mint desktop/window theme was dark. The screenshot's window/field colors corresponded to the light palette, pointing to theme detection rather than a failed code sync.

**Focused fix on main:** [commit `24a874b`](https://github.com/tony21675/StoryBuilder/commit/24a874b0fd9d86c046ed370cc4d0921387a0c54f) moves `GTK_THEME` environment-variable detection behind the desktop's saved settings. The environment variable can be inherited/stale; now the app checks GNOME's explicit color scheme and Cinnamon/GNOME/XFCE selected theme first. Added a regression in [commit `18fb9fb`](https://github.com/tony21675/StoryBuilder/commit/18fb9fbf6bee3b20bcda664dd75de5d13916ecbb) that simulates `GTK_THEME=Mint-Y` conflicting with Cinnamon's `Mint-Y-Dark-Aqua` and verifies that the desktop's dark setting wins.

**Verification:** GitHub Actions [run 39321100829](https://github.com/tony21675/StoryBuilder/actions/runs/39321100829) compiled successfully; the new conflict-priority test passed and the 8 appearance tests had no failures. The complete suite ran 246 tests, still with the same five known unrelated failures (3 state-preview workflow errors, 1 Writer prompt assertion, 1 text-selection assertion). This is not a fully green suite. The dark theme still needs live verification after the next sync/start on Tony's laptop.

**Next step:** Tony has already approved/saved the Chapter 3, Scene 3 proposal locally and restarted StoryBuilder; screenshot shows its title `Forming the Private Effort` loaded into Writer's Scene Idea preview. The remote MyNovel `STORY_PLAN.md` is still at blob SHA `64163da22d9f0f5bf7e170f47c035720a49dc0d2` and has no Scene 3 heading, so the approved plan appears to be local-only so far. Do not overwrite or pull stale MyNovel files. Run `cd ~/Documents/StoryBuilder && ./start.sh` to fetch the latest detector-priority fix, then verify the UI is dark. If it remains light, report this before any novel sync; we can use `STORYBUILDER_THEME=dark` as a session override and inspect the actual desktop settings. Once the theme is confirmed, use the app's **Close & Sync Novel** only when ready to push the saved local Scene 3 plan to MyNovel's GitHub main. Chapters 3, Scenes 1 and 2 and accepted prose remain protected.

---

## Follow-up verification: echoed-prompt fallback and dark-theme tests, October 19, 2026

The real Scene Planner output still showed the CLI banner/context during Tony's last live use, so the cleanup was hardened rather than treating the helper-only test as proof. builder/scene_planner.py commit [ff12f0f](https://github.com/tony21675/StoryBuilder/commit/ff12f0f9661d3c332dd64813af85b62252e2b521) now strips through the echoed prompt's distinctive final line if whole-prompt matching fails; [403e3fe](https://github.com/tony21675/StoryBuilder/commit/403e3fe51195e00c091fff6d2afa29093e724470) adds a regression for altered prompt prefixes.

Actions [run 39319751978](https://github.com/tony21675/StoryBuilder/actions/runs/39319751978) compiled successfully. The exact-echo cleanup test, fallback cleanup test, proposal extraction test, and all seven appearance tests pass. The full suite ran 245 tests and has only the same five previously known unrelated failures (3 state-preview workflow errors, 1 Writer-prompt assertion, 1 text-selection assertion). Live verification on Tony's desktop is still required.

**Important:** Tony's current Chapter 3, Scene 3 proposal may be visible but is unsaved. Do not ask him to restart/sync StoryBuilder before he has either approved/saved that proposal or explicitly chosen to leave it unsaved, because restarting clears the transient conversation and proposal. The latest proposal body needs an explicit boundaries section before approval. After that decision, use cd ~/Documents/StoryBuilder && ./start.sh and verify that the app opens dark and that the planning conversation no longer displays the llama.cpp banner/context. If bloat remains, treat live output as a new diagnostic and do not claim cleanup complete.

---

## Latest checkpoint: October 19, 2026: desktop-aware dark appearance

Tony approved adding desktop-aware light/dark styling because bright white StoryBuilder widgets were uncomfortable for his eyes. Implemented on main:
- Added `builder/appearance.py` ([commit `42df251`](https://github.com/tony21675/StoryBuilder/commit/42df25197e050a5aff9a1ee58da48e2b06c8e15e)), which detects GNOME/Cinnamon/XFCE appearance preferences and common GTK theme names, with `STORYBUILDER_THEME=dark|light` as an override and dark mode as the fallback.
- Applied the palette before UI construction in `storybuilder.py` ([commit `aeecad9`](https://github.com/tony21675/StoryBuilder/commit/aeecad9ddffee710417487f239b593a798fc738d)). It styles ttk controls and classic Tk widgets (text areas, entry/list/menu/canvas defaults), using a dark palette with soft off-white text and muted borders or a matching light palette.
- Added 7 focused detection/palette tests in `tests/test_appearance.py` ([commit `911943f`](https://github.com/tony21675/StoryBuilder/commit/911943f1c1af8cd1c1cf56bf11aea4db4f40216e)).

**Verification:** [Actions run 39319396216](https://github.com/tony21675/StoryBuilder/actions/runs/39319396216) compiled successfully and all 7 appearance tests passed. The full suite ran 244 tests and retained the same five known unrelated failures (3 empty ending-state preview workflow errors, 1 Writer prompt assertion, and 1 text-selection assertion). This is not a fully green run. The appearance change is committed but has not yet been visually verified in Tony's local desktop session.

**Next step:** Before running the app's `./start.sh` sync/restart, preserve the current unsaved Chapter 3, Scene 3 proposal shown in the app. The plan body has been shared in chat, but no **Approve & Save Plan** action has been confirmed. Do not let a restart silently discard it. After Tony has finished reviewing/saving the proposal (or has explicitly chosen to leave it unsaved), run `cd ~/Documents/StoryBuilder && ./start.sh`, then visually check that StoryBuilder opens dark on his Linux Mint desktop. If detection doesn't match his setting, report which Mint desktop session is in use and we can make a focused adjustment. Do not modify novel state or accepted prose as part of theme validation.

---

## Latest checkpoint: October 19, 2026: Scene Planner output parsing and clutter cleanup

Tony approved two focused changes after Prepare Plan Proposal failed with `the local model's proposal must contain string fields title and plan_body`.

**Implemented on StoryBuilder main:**
- `builder/scene_planner.py` commit [`c12c9dd`](https://github.com/tony21675/StoryBuilder/commit/c12c9dd6c10e8725cc00658c0f1bdbf3cdcb5131) now separates llama.cpp stdout from stderr rather than merging startup diagnostics into the text shown as the model's answer. It strips an echoed copy of the exact prompt and common timing/exit footer lines when present, so the visible planner conversation should show the actual reply rather than the banner and TARGET SCENE / CURRENT STARTING STATE dump.
- Proposal JSON extraction now scans candidates and selects the last object with string fields `title` and `plan_body`, instead of stopping at the first dictionary in the echoed context. This covers both the scene-context JSON and the example proposal JSON preceding Gemma's generated answer.
- `tests/test_scene_planner.py` adds two regressions. The corrected tests are in [commit `acc1125`](https://github.com/tony21675/StoryBuilder/commit/acc11253d21cedf5bfb16ba2d48aeae37a0510d0).

**Verification:** GitHub Actions [run 39317293682](https://github.com/tony21675/StoryBuilder/actions/runs/39317293682) passed compilation. Both new tests passed: echoed prompt/banner/footer cleanup, and selection of the actual proposal instead of context/example objects. The full suite ran 237 tests and still has the same five known unrelated failures (three state-preview workflow errors, one Writer-prompt assertion, and one text-selection assertion). The run therefore is not fully green; no new test failed.

**Next step for Tony:** In `~/Documents/StoryBuilder`, run the usual `./start.sh` sync/start workflow, open Taken_at_Dusk, and return to Scene Planner for Chapter 3, Scene 3. If the old conversation remains, click **Prepare Plan Proposal** again. The expected result is an editable Scene title and plan body, without llama.cpp startup/context clutter in the visible conversation. Review the content carefully before **Approve & Save Plan**. If it still errors, report the newest error message; the dialog should now be easier to copy. Do not click approve until the proposal is reviewed.

**Novel boundary:** No manuscript prose, `current_state.json`, `writing_guidance.json`, or `STORY_PLAN.md` changes were made by this code fix. Chapter 3, Scene 3 remains unplanned in the novel until Tony reviews and approves a valid proposal.

---

## Follow-up diagnostic: exact Scene Planner error, October 19, 2026

Tony subsequently supplied the exact error from **Prepare Plan Proposal**: `the local model's proposal must contain string fields title and plan_body.`

This narrows the immediate diagnostic: the proposal-generation path rejected the local model's output because the parsed proposal did not satisfy the required `title` and `plan_body` string-field contract. The exact raw model response and parsed object are not available yet, so do not assume whether the model emitted malformed JSON, omitted/renamed a field, or whether the parser/response handling is at fault. Tomorrow, inspect the proposal-generation code and error path, capture or log a bounded/safe excerpt of the raw model output and parsed structure, and add a focused regression test for the observed failure. Do not change the expected schema or patch the implementation by guesswork. No app code has been changed in response to this error yet.

---

## Latest checkpoint: October 19, 2026: Scene Planner proposal error, pause for tomorrow

Tony tested the new Scene Planner for Chapter 3, Scene 3 in the local StoryBuilder app using the Gemma 4 E4B instruction-tuned GGUF model. The multi-turn planning conversation itself works: Gemma produced several outlines, and the latest outline correctly captures the emotional opening, organically emerging tentative roles, meaningful ideas from Maya and Chloe, Tony gently connecting the ideas, and a hard stop once the initial framework begins taking shape.

**Current blocker:** Tony clicked **Prepare Plan Proposal** and received an error. He was getting ready for bed and could not copy the exact error, so its cause is unknown. The title/body proposal has not been successfully reviewed or approved. There is no confirmation that a proposal was saved; assume no plan was saved and retry tomorrow. The canonical MyNovel STORY_PLAN.md was not intentionally edited during this test. Do not change the accepted manuscript, current state, writing guidance, or plan as part of diagnosing this error.

**Next session:** Reopen StoryBuilder normally with cd ~/Documents/StoryBuilder && ./start.sh. Return to **Scene Planner**, target Chapter 3, Scene 3. If the old conversation survived, retry **Prepare Plan Proposal** once and capture the exact error, preferably with a screenshot if selecting or copying the error is difficult. If the conversation did not survive, restart it with a short summary rather than pasting the full transcript:

> Plan Chapter 3, Scene 3. Start Saturday morning at Tony's home immediately after Scene 2. Tony holds Chloe in a long, emotional hug, tears forming, sincerely thanks her, and calls her “my little wildcat” for the first time; Chloe likes the nickname. Then let Jessica's technical skills, Beth's community connections, Rick's practical/Army experience, and meaningful ideas from Maya and Chloe emerge naturally. Tony gently connects their ideas into tentative broad roles. End when a preliminary framework is beginning to form, before specific assignments, investigation steps, new leads, training, or rescue planning. Scene 2 already ends with the group committed to privately helping find Tiffany. No invented clues, no kidnapper or buyer identification, and no police call. Prepare an editable plan proposal for review; do not save it until approved.

Review the generated proposal before clicking **Approve & Save Plan**. If proposal generation fails again, record the exact error before retrying further; do not repeatedly click without seeing what failed.

**Readability backlog, not implemented:** Tony found the planning display hard to read because each model call shows the llama.cpp startup banner and a large TARGET SCENE / CURRENT STARTING STATE context dump. Later, discuss a focused UI/logging improvement to keep the context available to the model but hide it from the normal conversation view, leaving user messages and planner replies visible. Tony explicitly said not to change this now; finish basic Scene Planner testing first. When sharing results in ChatGPT, only the newest planner reply or the error screenshot is needed, not the full transcript.

No code changes were made in this checkpoint. This note records a live-test blocker only; it does not establish the root cause.

---

# StoryBuilder Chat Handoff

## October 19, 2026: Scene Planner implementation

The dedicated Scene Planner tab is now on main. It uses the selected local GGUF model for a multi-turn planning conversation, then builds an editable title/body proposal. Conversation and proposal generation do not write files. Only **Approve & Save Plan** changes the active novel's STORY_PLAN.md.

The save path is limited to one identified chapter/scene section. Before saving, the app confirms that the active novel and exact plan contents still match the proposal snapshot. Duplicate or ambiguous headings are rejected. Existing plan files are backed up outside the novel repository at `~/.local/share/storybuilder/scene_plan_backups` and replaced atomically. Existing saved Scene Ideas are preserved; refresh one through **Scene Contract → Load from STORY_PLAN.md** when needed.

Implementation commits: `829fc68` (planner engine), `6642858` (9 focused tests), `fc3edd2` (tab and workflow), `36a0770` (README), and `871c7de` (headless-safe busy checks). GitHub Actions run [39253355987](https://github.com/tony21675/StoryBuilder/actions/runs/39253355987): compilation passed and all 9 new tests passed. The full 235-test suite has the same 5 failures as the baseline run [39219602262](https://github.com/tony21675/StoryBuilder/actions/runs/39219602262): 3 existing workflow test errors and 2 existing assertion failures. The MyNovel repository and manuscript were not changed.

Next: pull StoryBuilder main using `cd ~/Documents/StoryBuilder && ./start.sh`. Open the novel, select **Scene Planner**, and work through the active scene purpose, beats, and hard stop before preparing a proposal. Review the proposal before saving.

---

## Follow-up checkpoint — October 19, 2026: MyNovel sync confirmed; pause at Scene 3 planning

Tony clicked **Close & Sync Novel** and reported that StoryBuilder closed normally without errors. Remote MyNovel was verified at commit [`86d0e4f`](https://github.com/tony21675/MyNovel/commit/86d0e4f19de7c6a79c47b0b9e75e6e8a37a9aee3). Its `current_state.json` now points to **Chapter 3, Scene 3**, with the reviewed Scene 2 ending situation, changed physical state, daytime clothing for Maya, knowledge updates for Beth/Jessica/Chloe/Rick, broad group objectives, and recent breakfast/disclosure events. The MyNovel handoff was then updated at [`2a2b1b2`](https://github.com/tony21675/MyNovel/commit/2a2b1b2f9ca2c2cd1f98efd17a6e94d4262df595) to record this confirmed sync.

**Next writing step is planning, not generation.** Remote `STORY_PLAN.md` covers Chapter 3, Scenes 1 and 2 only. There is no Scene 3 plan yet; the blank `"3": {}` created in `writing_guidance.json` is just an empty scene placeholder, not a plan. At the next session, discuss Scene 3's purpose, sequence, and hard stop with Tony. Do not create or edit the plan until its content has been agreed; do not click **Write Next Scene** before Scene 3 is planned.

**Project pause status:** StoryBuilder code repair is pushed and documented; the focused regression tests and existing malformed-location recovery test pass. Latest Actions run [39215058007](https://github.com/tony21675/StoryBuilder/actions/runs/39215058007) compiled successfully and ran 226 tests with five previously known failures. MyNovel state is saved and remotely synced; no further application or repository changes are needed before pausing.

---
## Latest checkpoint — October 19, 2026: Scene 2 state applied; pause at unplanned Scene 3

Tony synchronized the latest StoryBuilder code after the focused physical-state proposal repair. He ran **Analyze Accepted Scene** for accepted Chapter 3, Scene 2, and this time received an editable full ending-state preview instead of the earlier unsupported top-level Beth/Jessica/Rick validation error.

Tony pasted a reviewed JSON ending-state preview and clicked **Apply State Update**. StoryBuilder cleared the preview, refreshed Writer direction, and showed the separate message: “Writing notes reviewed. No new recurring craft lesson was strong enough to add.” The refreshed Writer direction now identifies **Chapter 3, Scene 3** and its starting situation summarizes the group beginning a private effort to find Tiffany. This is strong evidence the apply flow completed locally and advanced the in-memory/saved scene pointer. Do not rerun Scene 2 analysis or reapply the JSON.

**Scene 3 planning status:** Scene 3 and later scenes have not yet been planned. Remote `STORY_PLAN.md` has an approved plan for Chapter 3, Scene 1 and Scene 2, but no Chapter 3, Scene 3 section. Do not click **Write Next Scene** or invent a plan. The next creative task, after syncing and pausing, is to agree Scene 3's purpose, beats, and hard stop with Tony, then update `STORY_PLAN.md` only after approval.

**Sync safety is the immediate next step:** A read-only check of GitHub showed the remote MyNovel `current_state.json` still at Chapter 3, Scene 2 with the pre-breakfast state. The local app's new Chapter 3, Scene 3 state has not yet been verified on GitHub. Do not pull/overwrite remote MyNovel state or guidance from another direction. Tony should use the app's **Close & Sync Novel** action to sync the active local MyNovel package, then share the final sync result if it reports a conflict or error. Only after that result is confirmed should the MyNovel handoff be updated to say the Scene 2 ending state is remotely synced.

**Current StoryBuilder code status:** Physical-state normalization and diagnostic changes are on main at [`ea19601`](https://github.com/tony21675/StoryBuilder/commit/ea196012559b7117947edf263f5a273ba93803ea) and [`e887395`](https://github.com/tony21675/StoryBuilder/commit/e887395449c61a89a5a99267e08c62c485f6a169); [handoff verification commit](https://github.com/tony21675/StoryBuilder/commit/4b0f4ecd7b7ed0138ffd8cb6f696a03a42007906). Actions [run 39215058007](https://github.com/tony21675/StoryBuilder/actions/runs/39215058007): compile succeeded; both new state-analysis regression tests and the existing malformed-location recovery test passed. The full suite ran 226 tests and retained the same five older failures (three empty-state-preview workflow errors, one writer-prompt wording assertion, one text-selection assertion).

**No local MyNovel checkout was directly inspected by ChatGPT in this step.** Keep existing MyNovel local edits and both saved stashes intact. Do not reset, stash-drop, or blindly pull. The active local package is authoritative until sync is confirmed.

---
## Latest checkpoint — October 19, 2026: recover misplaced per-character physical-state fields

Tony approved a focused fix after **Analyze Accepted Scene** rejected the proposal with unsupported top-level fields for later arrivals (Beth, Jessica, and Rick), even though those fields described their physical positions. No state changes had been applied, and this patch does not edit the novel package or accepted manuscript.

**Implemented on main:**
- The state-analysis path now recognizes a top-level character object as misplaced physical state only when its name belongs to the known scene/state character roster and the object contains recognizable physical-state fields. It moves those unambiguous entries beneath `physical_state`; unknown metadata and conflicting duplicate character entries remain validation errors.
- Legacy top-level location normalization leaves recognizable character physical-state dictionaries for the physical-state normalizer, while preserving bounded recovery for older malformed location values.
- If validation still fails after the correction attempt, the error includes the exact parsed JSON proposal before normalization, plus a shorter raw-response excerpt. This should make the next failure diagnosable without guessing from a truncated tail.
- Added regression coverage for Beth/Jessica/Rick-style misnesting and for refusing to move unrecognized metadata.

**Implementation commits:** [`ea19601`](https://github.com/tony21675/StoryBuilder/commit/ea196012559b7117947edf263f5a273ba93803ea) adds the normalization, diagnostics, and two regression tests; [`e887395`](https://github.com/tony21675/StoryBuilder/commit/e887395449c61a89a5a99267e08c62c485f6a169) preserves legacy malformed-location recovery.

**Verification:** GitHub Actions [run 39215058007](https://github.com/tony21675/StoryBuilder/actions/runs/39215058007) compiled the application and builder modules successfully and ran 226 tests. Both new physical-state regression tests passed, as did the existing malformed-location recovery test. The whole suite still fails on the same five older tests: three `SceneWorkflowSafety` errors because mocked tests have an empty ending-state preview, one Writer-prompt assertion expecting `Prefer what characters say and do over narration`, and one text-selection assertion returning `' earl'` instead of `'early'`. No new regression test failed.

**Next step:** Sync StoryBuilder with the usual `cd ~/Documents/StoryBuilder && ./start.sh` workflow, then open Writer and run **Analyze Accepted Scene** again. Review the proposal before applying it. The accepted prose and MyNovel state were not changed by this code patch.

**Collaboration boundary:** This patch only addresses the malformed state proposal. Do not add other prompt or story changes as part of this repair.
---

## Latest checkpoint — October 19, 2026: accepted-scene state analysis follows scene transitions

Tony approved a focused StoryBuilder fix after the accepted Chapter 3, Scene 2 produced an ending-state proposal with stale details. The accepted scene text is confirmed saved and synced at `MyNovel/Taken_at_Dusk/Manuscript/Chapters/Chapter_03/Chapter_03_Section_02.txt`; Git status in the local MyNovel checkout was clean. No StoryBuilder change in this checkpoint edits the novel or accepted manuscript.

**Implemented on main:**
- `builder/state_manager.py` now allows the main state proposal to update a partial `active_objectives` object and emit transient `new_recent_events`. StoryBuilder appends new events to the existing recent-event history, normalizes whitespace/case for duplicate checks, and keeps the latest 12 events rather than requiring the model to rewrite the history.
- State-analysis prompt now explicitly asks for ending positions that match final prose, including standing/embracing interactions, and continuity-relevant clothing changes such as sleepwear to daytime clothes. It can replace stale objectives directly contradicted by accepted prose without inventing tasks or plans. A stale prompt line that prohibited objective/event updates was removed.
- State-analysis character candidates now combine the opening `scene_cast`, planned cast, and known characters named in the accepted prose. The knowledge audit is instructed to distinguish actual participants from characters merely mentioned or off-scene, so later arrivals can be assigned knowledge they learned while unrelated characters retain their prior knowledge.
- Knowledge merging removes simple duplicate variants such as `Know...` / `Knows that...`, and temporary physical/clothing details are kept separate from durable character knowledge. Legacy rule `Only characters explicitly listed for a scene are physically present and participating in that scene` is explicitly treated as stale schema wording in state analysis. Stored continuity requirements are not rewritten by the analysis patch.

**Regression coverage:** Added `tests/test_state_analysis_transitions.py` with eight tests covering recent-event append/deduplication/cap, output validation, objective changes, knowledge deduplication/supersession, state-prompt rules, and inclusion of later named characters in the analysis candidate roster.

**CI result at head `4a2eaa7`:** compilation succeeded and all eight new tests passed. The whole suite ran 224 tests; it still has the same five unrelated failures recorded before this work: three `SceneWorkflowSafety` errors because the ending-state preview is empty in older mocked tests (then the Tk error dialog recurses in headless CI), one old Writer-prompt assertion expecting `Prefer what characters say and do over narration`, and one text-selection test getting ` earl` rather than `early`. No new regression test failed. [Latest Actions run](https://github.com/tony21675/StoryBuilder/actions/runs/39212141787).

**Next step for Tony:** When ready, run the normal application sync once from `~/Documents/StoryBuilder` with `./start.sh`. Open `Taken_at_Dusk`, use **Reload Saved Scene** if Writer does not already show the accepted scene, then **Analyze Accepted Scene**. Review the proposed state; do not blindly apply it. Confirm Maya's daytime clothing, Chloe's changed objective and hug, the arrivals' knowledge, final positions, and breakfast/hug recent events. Keep the accepted prose untouched; no novel-state changes have been applied by this code work.

**Collaboration workflow remains mandatory:** Diagnose, recommend the focused fix, and get Tony's approval before any code, prompt, story file, or repository changes. Implement only the approved scope, test, update this handoff, and report precise results. Never edit or reset local MyNovel changes as part of a StoryBuilder code sync.
---

## Latest checkpoint — October 18, 2026: Writer direction now honors explicit Scene Idea metadata

Tony approved a focused source-of-truth fix after the Writer tab showed `Time: daybreak / early morning` and `Cast: Tony, Maya`, while the loaded original Scene Idea specified `Time: Saturday morning at daybreak` and said Beth, Chloe, Jessica, and Rick would arrive later. The previous direction builder copied time and cast straight from `current_state.json` without identifying them as opening-state details.

**Implemented across the actual Writer direction path:** `builder/scene_contract.py` now extracts explicit `Location:` and `Time:` from the author's Scene header. The contract-builder prompt gives those fields priority over broad state summaries. `storybuilder.py` reuses the exact saved Scene Idea shown in Writer: explicit header values override state labels; `scene_cast` is labeled as the opening cast only; physical positions are labeled opening continuity; and characters named to arrive later are not excluded. State still controls completed events, character knowledge, and starting physical position.

**Verification at code/test commit `57a8513`:** compilation succeeded. All three new regression tests passed, including the test against the real `_build_scene_direction` method; two parser tests also passed. The full suite ran 216 tests and showed five older failures also present before this change: three workflow-safety errors (empty ending-state preview), one existing Writer-prompt assertion, and one existing text-selection assertion. No new regression test failed. [Actions run](https://github.com/tony21675/StoryBuilder/actions/runs/39201291424).

**Next step:** The in-progress/unaccepted Chapter 3, Scene 2 draft was generated with the prior stale direction. Do not accept it. After it finishes, sync the current StoryBuilder code using `cd ~/Documents/StoryBuilder && ./start.sh`. Then, before generating another draft, click Writer's **Build Scene Direction** to refresh the display. Verify it shows `Time: Saturday morning at daybreak` and `Opening cast (present at scene start only; not the full scene cast): Tony, Maya`, with the explicit rule that later arrivals from the Scene Idea may enter. Regenerate Scene 2 only after that check. Keep accepted Scene 1 untouched and do not apply Scene 2 state until Tony reviews it.

**Required collaboration workflow:** Read the handoff first. Diagnose, recommend the narrow fix, and ask Tony for explicit approval before modifying code, prompts, story files, or repository state. Implement only after approval; then test, update this handoff, and report exact results. Discussing a problem is not permission to change files.

---
## Follow-up — October 18, 2026: indentation correction in authored-header direction fix

The first CI run exposed an indentation error in storybuilder.py, which has been fixed; the next run passed compilation. Its one new Writer-direction test then revealed it had been appended to a test class without the helper it relied on, so the test now builds its lightweight app fixture directly. Verify the next Actions run before asking Tony to sync.

---
## Latest checkpoint — October 18, 2026: prevent stale starting-state metadata from overriding the Scene Idea

Tony approved this focused fix after finding the Writer's Scene Idea said `Time: Saturday morning at daybreak` and required Beth, Chloe, Jessica, and Rick to arrive later, while the Writer direction showed `Time: daybreak / early morning` and `Cast: Tony, Maya`. The starting state's time/cast describe the scene's opening snapshot; they must not override explicit scene-wide author metadata or exclude later arrivals.

**Code change:** `builder/scene_contract.py` provides `extract_scene_header_metadata()` to retrieve explicit `Location:`/`Time:` from the author's Scene header, and the contract-builder prompt now gives those fields priority over broad state summaries. `storybuilder.py` reuses the same saved Scene Idea plan entry used by the Writer preview; the direction uses explicit author header values when present, labels `scene_cast` as the opening cast only, labels physical positions as opening continuity, and explicitly permits later arrivals named in the Scene Idea. State still controls completed events, knowledge, and starting positions.

**Regression tests:** parser tests cover explicit Saturday time/location and ensure metadata is not inferred from body prose. A Writer-direction integration test exercises the actual UI-direction builder: explicit author time overrides `daybreak / early morning`, opening cast is clearly scoped, and later arrivals remain allowed. Verify the latest GitHub Actions run before asking Tony to sync.

**Next step after verification:** Let the current unaccepted generation finish, but do not accept it. Once code and tests are confirmed, Tony should run `./start.sh` from `~/Documents/StoryBuilder` to sync and launch, then click Writer's `Build Scene Direction` button to refresh the displayed direction before regenerating Chapter 3, Scene 2. Keep accepted Scene 1 untouched. MyNovel's `STORY_PLAN.md` already has the approved `Saturday morning at daybreak` header.

**Required collaboration workflow:** Read the handoff first. Diagnose, recommend a narrow fix, and ask Tony for explicit approval before modifying code, prompts, story files, or repository state. Implement only after approval; then test, update this handoff, and report exact results. Discussing a problem is not permission to change files.

---
## Latest checkpoint — October 18, 2026: evidence-backed continuity audit and Saturday scene-time anchor

Tony approved the next focused StoryBuilder change before implementation. The audit now requires five distinct checks: timeline/event order, character presence and knowledge, physical/location continuity, unsupported consequential details, and the scene hard stop. Any reported conflict must cite an exact excerpt from the draft and an exact excerpt from the original scene direction, starting-state JSON, or stable author guidance. The app verifies both quotes against the supplied text. Missing categories, unsupported quotes, uncertain categories, or disagreement between the semantic validator and the evidence-backed audit preserve the original draft rather than triggering a rewrite. Only a fully structured, evidence-backed conflict permits one full-scene retry. A continuation for missing beats is appended only when the entire combined draft receives a clear audit.

Verification on code commit `154e19a`: compilation succeeded and all 14 `test_scene_completion` tests passed. The full suite ran 213 tests and still failed on five older, unrelated tests: three workflow-safety tests raise `ValueError: The ending-state preview is empty`, one writer-prompt test expects a phrase absent from the current prompt, and one text-selection test gets `' earl'` instead of `'early'`. These are the same five failures seen before this focused audit change; no new scene-completion test failed. Actions run: https://github.com/tony21675/StoryBuilder/actions/runs/39199395194.

**Novel plan time label:** `MyNovel/STORY_PLAN.md` now identifies Chapter 3, Scene 2 as `Location: Tony's home` and `Time: Saturday morning at daybreak`. The local MyNovel checkout was not edited by this remote change; follow its existing reconciliation steps and do not overwrite its pending local state/guidance edits blindly. After the local package is safely reconciled, reload the Scene Idea from `STORY_PLAN.md` and refresh the contract before generating.

**Required collaboration workflow:** Read this handoff first. For changes to code, story files, prompts, or repository state, diagnose first, report the concrete findings and recommend a focused change, then stop and ask Tony for explicit approval. Do not edit, commit, or push those changes until approval is given. After approval, implement the agreed scope, test it, update this handoff, and report exactly what passed and failed. Never treat a request to discuss a problem as permission to change files.

**Next step after the latest code is pushed:** Tony should sync once from `~/Documents/StoryBuilder` with `./start.sh`, then test the new Writer behavior after the MyNovel plan has been safely reconciled. Keep accepted Chapter 3, Scene 1 untouched. Never auto-accept Scene 2 or apply its state update.

---
## Follow-up — October 18, 2026: Chapter 1, Scene 5 fact check

Correction to the draft critique: Tiffany's resistance during the abduction is established in `Manuscript/Chapters/Chapter_01/Chapter_01_Section_05.txt` and repeated in `current_state.json`: two elbow strikes to the solar plexus, a kick to the thigh, a slap to the jaw, and scratches to the kidnapper's left cheek. Maya witnesses this. Do not label those details invented or treat them as a continuity violation. The independent audit receives the whole current state, which explicitly carries those facts forward.

The valid eyewitness problem in the attempted Chapter 3, Scene 2 draft is assigning Chloe firsthand knowledge of the abduction although she was home sick. Other valid review concerns include the loose 'last night' timing (the abduction begins in late afternoon in Chapter 1, Scene 5), having Maya change clothes in the kitchen rather than privately, and pushing into operational investigation beyond the Scene 2 hard stop.

CI follow-up for the generic scene completion/audit change: fixed a mismatch between a new test's expected notice capitalization and the actual notice. The full suite may still report the same five pre-existing failures documented in the prior checkpoint; verify the latest Actions run before asking Tony to sync. Do not ask for another manual prose correction.

---
## Latest checkpoint — October 18, 2026: independent scene-integrity audit and bounded full retry

The next Chapter 3, Scene 2 draft reached the intended rough endpoint but still contained major continuity/scope failures: it assigned Chloe eyewitness knowledge despite her being home sick, asserted unestablished details about Tiffany fighting the abductor, misplaced the timing of the abduction, and advanced into operational investigation. This showed completion checking alone was not enough.

**Second generic mechanics improvement:** the post-generation workflow now runs an independent, conservative continuity/scope audit using the existing local model sequentially. It checks timeline, presence/knowledge, consequential unsupported claims, explicit no-go constraints, and scene hard stop. Ordinary atmosphere and plausible details, including familiar household scents, must not be flagged merely because they are not spelled out in the plan. A material conflict triggers at most one full-scene retry. The regenerated scene must pass both the existing semantic completion review and a follow-up integrity audit before replacing the initial draft. If verification fails, StoryBuilder keeps the original draft and shows a review notice. A safe but incomplete draft may still receive one append-only continuation, which is audited before it is retained. Nothing is auto-accepted and no state is advanced.

`tests/test_scene_completion.py` now covers a full retry when a material conflict is flagged, rechecking after retry, audit failure preserving the original, and refusing an unsafe append-only continuation. Check GitHub Actions before telling Tony this second change is fully verified.

**Next step:** Tony has already pulled the first completion-recovery change and tried a new Scene 2. Do not ask him to make manual prose edits. After the latest code is pushed and checked enough to pull, use the existing `./start.sh` workflow from `~/Documents/StoryBuilder`, then regenerate Chapter 3, Scene 2. Load the current `STORY_PLAN.md` scene plan first if the saved Scene Idea has not been refreshed. Keep Scene 1 accepted, and do not accept Scene 2 or apply its state update without Tony's review.

---
## Latest checkpoint — October 18, 2026: bounded completion recovery for incomplete scene drafts

Tony approved a generic StoryBuilder mechanics change after Chapter 3, Scene 2 ended immediately after the first disclosure instead of carrying through the planned group response and initial role formation.

**Implemented on main in one commit:** `builder/scene_completion.py` runs the existing semantic Scene Contract review after a generated scene. If review reports missing author-intended events but no continuity violations, and the scene contract allows retries, StoryBuilder resets the same local model to the Writer prompt and requests one append-only continuation. It keeps all original draft text verbatim, appends only the continuation, and leaves acceptance/state changes to Tony. If the check fails, reports a continuity contradiction, or cannot safely continue, the original draft stays intact and the Writer status displays a review notice. This behavior is generic; it contains no novel-specific names or plot facts.

Added `tests/test_scene_completion.py` to cover successful review, missing-beat continuation, avoiding append-only repair when continuity is contradicted, validator failure, a missing saved Scene Idea, and retry-limit behavior. GitHub Actions compiled the application and builder modules successfully and ran 205 tests; all six new SceneCompletion tests passed. The overall test job still reports five failures that were already present on parent commit `32ab638`: three SceneWorkflowSafety tests raise `ValueError: The ending-state preview is empty. Analyze the accepted scene again.`; `test_writer_prompt_preserves_uncontradicted_physical_continuity` expects the phrase `Prefer what characters say and do over narration`; and `test_entry_selection_uses_full_value_and_slice_indices` returns ` earl` instead of `early`. These failures were unchanged from the parent run and are outside this focused fix; keep them separate unless Tony authorizes addressing them.

**Tony's next action after pulling once:** Close StoryBuilder safely after confirming no generation is running and no unsaved draft needs keeping. From `~/Documents/StoryBuilder`, use the existing `./start.sh` sync workflow to fast-forward `main` and launch the updated app. For Chapter 3, Scene 2, use **Load from STORY_PLAN.md** once if the saved Scene Idea is stale, then generate a fresh attempt. Review the entire combined draft; automatic continuation is bounded to one pass and is not automatic acceptance. Do not touch accepted Scene 1 or apply a state update before Tony approves Scene 2.

---
## Latest checkpoint — October 18, 2026: MyNovel sync paused before Chapter 3, Scene 2

StoryBuilder on Tony's laptop was synchronized through `./sync.sh start` and finished clean at `7c5f01d` on `main`. A zero-byte root-level untracked `FETCH_HEAD` had been noticed before sync, but a removal attempt found it already absent; the successful sync finished with a clean status. Do not stage or recreate it. No test commands were run as part of this laptop sync.

The MyNovel laptop checkout at `~/Documents/MyNovel/Taken_at_Dusk` was fast-forwarded from `70ba8d3` to GitHub `c4b1ca1`. The local edits were backed up to `~/Documents/MyNovel_pre_sync_backup_20261018_182247` and saved in `stash@{0}` before fast-forward. Applying the stash conflicted only in `STORY_PLAN.md`; Tony resolved it by choosing the updated branch's plan and staging it. The original stash and older `stash@{1}` remain intact.

At pause, the MyNovel working copy still has staged changes to `current_state.json`, `writing_guidance.json`, and `working_writer_notes.json`, plus an untracked Chapter 3 Scene 1 after-state snapshot. These edits have not been committed or pushed. JSON parsing succeeded and the hard sleepwear rule was confirmed in guidance, but final reconciliation remains incomplete:
- active state is Chapter 3 Scene 2, `daybreak / early morning`, with exact time not established;
- Maya's state still carries the stale line that she is wrapped in her robe rather than the clean pajamas established in Chapter 2 Scene 5;
- the Scene 1 ending snapshot says `the middle of the night` despite describing daybreak;
- the Scene 2 guidance and snapshot ignore status still need a full read-only inspection with the Git pager disabled.

Continue from the latest [MyNovel handoff](https://github.com/tony21675/MyNovel/blob/main/HANDOFF.md). Preserve `~/Documents/MyNovel_pre_sync_backup_20261018_182247`, `stash@{0}`, and `stash@{1}`; do not run `git stash pop`, discard the snapshot, or start another Scene 2 generation yet. Finish the state/snapshot reconciliation, validate and commit/push MyNovel, then reload the canonical Scene 2 plan in StoryBuilder and generate a fresh attempt. The previous draft beginning with Maya in a robe is unaccepted and must remain unused.

## Latest checkpoint — October 18, 2026: hard bed-sleepwear rule made persistent in Taken at Dusk

Tony established a hard continuity rule: anyone sleeping in a bed must be either wearing sleepwear or naked. Robes/bathrobes/dressing gowns and ordinary daytime clothing are not sleepwear and must never be what a character sleeps in. If a character uses a robe after a bath, they must privately change into sleepwear (or be explicitly established as naked) before falling asleep. The sleeping outfit carries into the next waking scene until a change is shown.

The rule has been recorded in all three canonical MyNovel planning/guidance locations:
- [story_bible.json](https://github.com/tony21675/MyNovel/commit/b5353b7cf924b5ac9b9bb0020ff2dc15fc76cbdc): permanent canon rule.
- [writing_guidance.json](https://github.com/tony21675/MyNovel/commit/41800c458acb75f5d2bffdd0d0afea77ce1dfc2d): first recurring instruction so the writer receives it across future scenes.
- [STORY_PLAN.md](https://github.com/tony21675/MyNovel/commit/34a9616d1e85c73c087afab417506c7739fa0577): confirmed global hard rule; Chapter 2 Scene 5 requires Tony to offer clean pajamas and give Maya privacy to change before bed.

Chapter 2 Scene 5 prose was already corrected in [commit 4e80dcf](https://github.com/tony21675/MyNovel/commit/4e80dcfa88f676ffc3f77158dc36c8d1ccb1a206); compiled Chapter 2 was updated in [commit c481aec](https://github.com/tony21675/MyNovel/commit/c481aeccb7712b12c6a277dc0a046ecce3f325a8). The Scene 5 saved guidance now also makes sleepwear a required beat. Chapter 3 Scene 2 in-progress draft has Maya waking in a robe and must not be accepted; regenerate after the corrected local files are reconciled.

**Local package safety:** the changes above are committed to the MyNovel GitHub copy. Local MyNovel state/guidance files had known unsynchronized edits. Do not pull/overwrite the novel package blindly. Inspect local MyNovel `git status -sb`, preserve local `current_state.json`, and deliberately reconcile only the changed Chapter 2 Scene 5 prose, compiled Chapter 2, STORY_PLAN.md, story_bible.json, and writing_guidance.json.

## Latest checkpoint — October 18, 2026: Maya's robe-to-bed continuity repaired in MyNovel

Review of the actual manuscript confirmed that Chapter 2, Scene 5 explicitly had Maya wrapped in a thick white robe when Tony settled her onto Tiffany's bed, followed by her falling asleep. Chapter 3, Scene 1 starts with her asleep under the duvet but says nothing about clothing, so the prior scene implicitly left her sleeping in the robe.

The canonical MyNovel GitHub copy has now been corrected:
- [Chapter 2, Scene 5](https://github.com/tony21675/MyNovel/commit/4e80dcfa88f676ffc3f77158dc36c8d1ccb1a206): Tony offers the clean pajamas previously noticed on Tiffany's bed, gives Maya privacy to change, and returns after she's changed and beneath the duvet.
- [Compiled Chapter 2](https://github.com/tony21675/MyNovel/commit/c481aeccb7712b12c6a277dc0a046ecce3f325a8): synchronized to the same prose.
- [STORY_PLAN.md](https://github.com/tony21675/MyNovel/commit/4f6e050e93f531b3c837a28bb160785f090087cb): Maya wakes wearing the borrowed clean pajamas, then privately changes into ordinary daytime clothes before breakfast.

Chapter 3, Scene 1 itself was left unchanged because it does not specify the outfit. The scene state snapshots don't store Maya's clothing, so none were altered. The recent generated Chapter 3, Scene 2 draft is now inconsistent with this corrected canon when it has Maya in a robe on waking; keep it unaccepted and regenerate after the local plan/manuscript is safely synchronized.

**Local/remote caution:** These manuscript/plan changes were committed to the MyNovel GitHub copy only. The local package has known unsynchronized current-state/writing-guidance edits. Do not blindly pull/overwrite those files. Inspect the local MyNovel repo status and synchronize/reconcile only the specific manuscript, compiled chapter, and STORY_PLAN files deliberately.

## Latest checkpoint — October 18, 2026: review of regenerated Chapter 3, Scene 2

A fresh Chapter 3, Scene 2 draft has been generated after the Scene Contract check. It has **not yet been accepted or explicitly rejected by Tony**. Initial review recommends another generation rather than a chain of focused edits because several major scene-level constraints are missed:

- The accepted story timeline says Tiffany was abducted the previous afternoon near the corner; the draft says “taken last night.”
- Tony says only “Tiffany is gone” before a vague follow-up (“She was taken last night. She... she had company.”). The group needs a clear disclosure that Tiffany was abducted, grounded in Maya's account; Tony did not witness the abduction.
- The draft adds unestablished sensory/action details to Maya's recollection, including old cigarettes/cheap cologne/pine needles and specific struggle details. The planned scene explicitly says not to invent new clues or answers.
- It advances too far into concrete investigation: Jessica mentions tracing cameras/digital footprints, Beth proposes questioning neighbors, and Rick mentions perimeter checks. This scene should only establish broad possible contributions and initial shared commitment; specific investigation steps and assignments remain later.
- Chloe is largely sidelined after a one-line commitment; Maya also needs a meaningful voice without being pressured into a full account.
- Maya wakes wearing a robe and remains in it through breakfast. Tony clarified she should already be in pajamas when woken and can change into regular clothes before breakfast.
- The friends arrive as if making an unplanned stop (“we just wanted to swing by”), rather than clearly arriving for the breakfast Tony arranged.

The dawn/breakfast atmosphere and initial shock work as a foundation, and the broad arc is recognizable. The main failure is execution against timeline/canon and the hard stop, not the premise itself. Next step: revise reusable plan/contract or guidance as needed and regenerate; don't accept this draft yet unless Tony decides otherwise. Existing accepted Scene 1, saved daybreak state, and rejected earlier Scene 2 draft remain untouched.

## Latest checkpoint — October 18, 2026: Current State edits did not persist across restart

**Verification after sync:** Tony re-ran `./start.sh`, corrected Time of Day to `daybreak / early morning` using **Apply & Save State Edits**, then restarted StoryBuilder. The daybreak value **survived the restart**. This confirms the immediate local state-persistence issue is resolved. Chapter/Scene were left unchanged; `time.exact_time` remains not established. Continue from Chapter 3, Scene 2 with the persisted state; do not rerun Scene 1 analysis.

Tony clarified that he had manually corrected the time to daybreak/early morning during the previous Scene 2 session, but restarting StoryBuilder restored the old value. Source inspection distinguishes **two separate bugs**:

1. The Writer's editable full ending-state preview was ignored by Apply State Update, which applied only the hidden original proposal.
2. **Current State → Apply State Edits** modified `package.current_state` in memory and marked it dirty, but did not itself write the package to disk. Unless a separate Save followed, the edit could be lost on restart.

**Fixes committed to `main`:**
- [`a1f43a1`](https://github.com/tony21675/StoryBuilder/commit/a1f43a110064cc7d23fa8f639bd50ca56a8a3ff6) and [`f8c0239`](https://github.com/tony21675/StoryBuilder/commit/f8c02398555ab3073d47fba337154ac45453fe30): apply actual edits made to the ending-state preview.
- [`a58cd52`](https://github.com/tony21675/StoryBuilder/commit/a58cd526a19e9cb503324130430c792a2df4f04b) and [`92f5720`](https://github.com/tony21675/StoryBuilder/commit/92f5720b8cbf98063091ee3b18f0e0f5eb7cd418): add preview safety tests and preserve invalid preview edits for correction/retry.
- [`b74ab6a`](https://github.com/tony21675/StoryBuilder/commit/b74ab6a691a1155d63f86a9958ea3ce556bedec9): rename the Current State button to **Apply & Save State Edits** and persist the package immediately when the button is used. The handler reports a clear error if saving fails or the package has no saved folder. It also returns a success flag so a failed/cancelled state change is not treated as successfully applied by the shared Apply All workflow.
- [`baf6ea1`](https://github.com/tony21675/StoryBuilder/commit/baf6ea122ab91951bbe9c3da112237c46da12c7d): add focused tests for persistence success, save failure, missing package folder, and cancelled state edits.

**Verification limitation:** tests have been added but not executed in this session. GitHub's commit-status endpoint returned no checks for these direct `main` commits. After syncing locally from the StoryBuilder repo root, run:
`python -m unittest discover -s tests -p 'test_state_preview.py'`
and
`python -m unittest discover -s tests -p 'test_state_edits_persist.py'`.

**Next action after the updated StoryBuilder source is on Tony's laptop:** In the open MyNovel package, keep the current Chapter/Scene numbers unchanged, set Time of Day to `daybreak / early morning`, and click **Apply & Save State Edits**. Then restart StoryBuilder and verify the time remains daybreak/early morning. Keep exact time not established. Do not reapply Scene 1 analysis, which could advance the scene pointer again. Do not overwrite the local novel package from the stale GitHub `current_state.json`.

## Latest checkpoint — October 18, 2026: Entry context-menu copy/cut callback fix

Tony ran `./start.sh`; synchronization reported up to date, but a Tkinter callback then raised `TypeError: Entry.get() takes 1 positional argument but 3 were given` in the context-menu `copy()` callback. Root cause: the generic selection handler used `widget.get(start_index, end_index)` for both `tk.Text` and Entry-style widgets. Entry/ttk.Entry/Combobox/Spinbox only accept zero arguments for `get()`.

**Fix committed to StoryBuilder main:**
- [`5ff19ce`](https://github.com/tony21675/StoryBuilder/commit/5ff19ce025afc8d1e0b82f14be0a8cfc5c74b53f): add `StoryBuilderApp._selected_widget_text()`; Text reads via Tk indices while Entry-style widgets slice the full string returned by `get()`. Both Copy and Cut use the helper.
- [`3a0d850`](https://github.com/tony21675/StoryBuilder/commit/3a0d8507a4e9394b4fb1fe163eec29cd8bc121bb): add `tests/test_text_edit_context_menu.py` for selected Entry substring extraction.

**Local checkout:** Tony's reported `git status -sb` was `## main...origin/main` plus untracked root-level `FETCH_HEAD`. Do not stage/commit that file as source. The reported `./start.sh` sync happened before this callback-fix commit, so rerun `./start.sh` from `~/Documents/StoryBuilder` to retrieve it. The sync script stashes and restores untracked files automatically.

**Verification:** the test was added but not executed in this session. Once synced locally, run:
`python -m unittest discover -s tests -p 'test_text_edit_context_menu.py'`
Then run the two recent state-workflow tests:
`python -m unittest discover -s tests -p 'test_state_preview.py'`
`python -m unittest discover -s tests -p 'test_state_edits_persist.py'`

State-persistence and ending-preview fixes remain in the preceding handoff entry. The existing MyNovel package still needs its daybreak correction applied using the new **Apply & Save State Edits** control after StoryBuilder has been updated, then a restart check.

## Latest checkpoint — October 18, 2026: apply the reviewed ending-state JSON

Found a state-update workflow bug: the **Reconstructed Ending State** text area was editable, but `_apply_state_update()` validated/applied `self.pending_state_patch`, the hidden original proposal. Manual changes made to the displayed JSON, including Tony's correction from "the middle of the night" to daybreak/early morning, were ignored.

**Fixes committed directly to `main`:**
- [`a1f43a1`](https://github.com/tony21675/StoryBuilder/commit/a1f43a110064cc7d23fa8f639bd50ca56a8a3ff6): add reviewed-preview-to-patch conversion, protect StoryBuilder-managed navigation fields, reject accidental removal of existing fields.
- [`f8c0239`](https://github.com/tony21675/StoryBuilder/commit/f8c02398555ab3073d47fba337154ac45453fe30): apply the edited visible preview; clarify the label/help text.
- [`a58cd52`](https://github.com/tony21675/StoryBuilder/commit/a58cd526a19e9cb503324130430c792a2df4f04b): add `tests/test_state_preview.py` with four focused tests.
- [`92f5720`](https://github.com/tony21675/StoryBuilder/commit/92f5720b8cbf98063091ee3b18f0e0f5eb7cd418): retain invalid preview text and pending proposal so the author can correct the JSON and retry rather than losing edits.

Tests were added but not executed in this tool session; the commit-status endpoint returned no checks for these direct `main` commits. After syncing, run `python -m unittest discover -s tests -p 'test_state_preview.py'` from the repository root.

This code fix only affects future Apply State Update operations. It does not fix Tony's existing local novel state. For the existing package, safely use **Current State**: set **Time of Day** to `daybreak / early morning`, keep the current Chapter and Scene numbers unchanged, click **Apply State Edits**, then use the normal Save action. `time.exact_time` remains not established. Do not reapply Scene 1's state analysis, which could advance the scene pointer again. Do not overwrite the local novel package with stale remote `current_state.json`.

## Latest checkpoint — October 18, 2026: plan reload and scene-pacing improvements

The first generated Chapter 3, Scene 2 draft was rejected as structurally off-plan. Tony's direction is to improve reusable StoryBuilder behavior rather than manually author a large, novel-specific prompt.

**Source changes committed to StoryBuilder main:**
- Add a distinct **Load from STORY_PLAN.md** control to Scene Contract. It explicitly reloads the current chapter/scene's plan section even if an older Scene Idea is already saved. It asks before replacing visible edits, changes only the editor, and does not save the plan text or alter an existing contract until Tony uses the normal save/Generate-Replace flow.
- Add a generic per-scene **SCENE PROGRESSION AND SCOPE** prompt instruction. It tells the writer to preserve planned phases and endpoint, match the requested degree of progress, and not automatically jump from a disclosure, discovery, reaction, or offer of help into later investigation, assignments, execution, or resolution.
- Add tests for refreshing a stale saved idea from the plan without silently saving it, respecting cancellation, and including progression guidance in Writer context.

This is deliberately generic. No *Taken at Dusk* names, facts, plot beats, or character assignments are being hard-coded into application code.

The concise canonical MyNovel Scene 2 plan is in [STORY_PLAN.md](https://github.com/tony21675/MyNovel/blob/main/STORY_PLAN.md), updated at commit [35c4384](https://github.com/tony21675/MyNovel/commit/35c438422144fcc7b4de5777e08c7571b55421c3). Once this code is pulled locally, use **Load from STORY_PLAN.md** for the active Chapter 3, Scene 2 to load the revised plan into Scene Idea; check its Direction and End, then generate a new attempt. Do not accept the rejected attempt or use a chain of Focused Changes for this structural miss.

The contract parser/endpoint fix remains complete at [commit 1665e923](https://github.com/tony21675/StoryBuilder/commit/1665e9231e77325aa6da7be61ebe02c837be0c24). The latest source commit including the corrected test helper is [6f0ca21](https://github.com/tony21675/StoryBuilder/commit/6f0ca216d4bb2c930be3c4fdbece04ba9106bac2). **Verification:** GitHub Actions [run 39173615322](https://github.com/tony21675/StoryBuilder/actions/runs/39173615322) compiled the application successfully and ran 189 tests. The new Scene Plan tests passed, including loading a revised plan over a stale saved idea and preserving current editor text when the user cancels. The full suite still reports one unrelated, previously known failure: `test_writer_prompt_preserves_uncontradicted_physical_continuity`, which expects the Writer system prompt to contain `Prefer what characters say and do over narration`. That prompt/test wording mismatch predates this feature; keep it separate unless Tony authorizes addressing it.


## Current blocker — Scene Contract time reverted to night

Tony reports the Scene Contract start summary again displays `Time: the middle of the night`. Source inspection confirms `storybuilder.py` method `_scene_contract_start_summary()` reads `package.current_state["time"]["period"]`, falling back to `time_of_day`. `_build_scene_direction()` likewise reads the active saved state; neither derives the time from accepted prose or the plan.

The remote MyNovel `current_state.json` is confirmed stale at Chapter 3, Scene 1 with `scene_completed: false`, time period `the middle of the night`, and a night-time current situation. That differs from the recorded local checkpoint where Scene 1 was accepted, its time was manually corrected to daybreak/early morning, and the state update was reported applied. No novel state file was changed during this diagnosis.

Before editing source code, inspect the *active local novel package* and determine whether it has reopened stale data or whether the corrected state failed to persist. Compare local `current_state.json` with the accepted Scene 1 ending snapshot and any state-update history, and inspect `git status -sb` in the actual MyNovel repository if present. Do not blindly pull or overwrite the unsynchronized MyNovel JSON files. Restore the verified accepted Scene 1 endpoint state locally if necessary, preserving `exact_time: not established` and advancing to Chapter 3, Scene 2; then refresh Scene Contract and confirm the display reads daybreak/early morning. Leave accepted prose and the rejected Scene 2 draft untouched. Only consider a generic source-code change if evidence shows the state is correct but Scene Contract still displays the old value.

## Current checkpoint: Chapter 3, Scene 2 and generic plan-to-idea loading, October 18, 2026

**Read first:** [MyNovel HANDOFF.md](https://github.com/tony21675/MyNovel/blob/main/HANDOFF.md), [STORY_PLAN.md](https://github.com/tony21675/MyNovel/blob/main/STORY_PLAN.md), and then inspect the active local novel package's current_state.json, writing_guidance.json, accepted immediately preceding scene, and before/after state snapshots. When local novel files differ from GitHub, the current saved local package is authoritative until safely reconciled.

**Current accepted-scene checkpoint:** Tony approved the fresh Chapter 3, Scene 1 generated after the generic Writer style-prompt rule 9 change. He reviewed the ending-state preview, manually changed `time.period` from `the middle of the night` to a daybreak/early-morning value because the prose and `current_situation` clearly end at first light, left `exact_time` unestablished, and accepted/applied the state update. The scene is accepted, and the workflow should now be at Chapter 3, Scene 2; verify the current local package and app pointer before proceeding. The scene follows Tony through the night after he checks Maya once and gently covers her when her blanket slips; it ends at daybreak. Tony likes it overall despite some ornate prose. Its emotional center is Tony's grief and disorientation after losing Tiffany, the last piece of Sarah he has left, and his loneliness: he comforted Maya, but nobody is there to comfort him. Do not treat every return to his grief as automatically wrong; preserve that emotional truth. Do not regenerate or rewrite the accepted scene.

**Phase 1 implementation status:** Plan-to-Scene-Idea autofill is now implemented in StoryBuilder main. It reads only the `STORY_PLAN.md` at the active novel package root, extracts the matching chapter/scene heading and its body up to the next same-or-higher-level heading, and prefills the Scene Idea only if that scene has no saved author idea. Saved author notes win; prefilled content is not persisted until the user saves it or generates the contract. The Writer's read-only Scene Idea preview uses the same fallback. If the plan/section is absent the editor stays blank; if the plan cannot be read, the issue is shown. This is a deterministic file read and makes no model call. Focused parser and UI integration tests were added.

**Verification status for plan autofill:** The focused test_scene_plan.py suite passed all 11 tests, including both Scene Contract UI integration tests. The later contract-endpoint regression tests also pass. The latest full run [39169607366](https://github.com/tony21675/StoryBuilder/actions/runs/39169607366) ran 187 tests with one unrelated failure: test_writer_prompt_preserves_uncontradicted_physical_continuity expects the Writer prompt to contain 'Prefer what characters say and do over narration', which was already absent in the parent commit before the autofill change. The endpoint tests passed in that run. Do not fold a repair of that unrelated prompt/test mismatch into this feature without discussing it separately.

**Current writing position:** Chapter 3, Scene 1, *The Long Night*, is accepted and its ending-state update has been applied in the active local StoryBuilder package. Chapter 3, Scene 2's first generated draft was rejected as structurally off-plan. The canonical MyNovel `STORY_PLAN.md` and `HANDOFF.md` now specify a fresh composition centered on the group's shocked response and questions, a clear disclosure, Chloe's active participation, Maya changing into Tiffany's pajamas, and a hard stop before operational planning. See current [MyNovel HANDOFF.md](https://github.com/tony21675/MyNovel/blob/main/HANDOFF.md) and [STORY_PLAN.md](https://github.com/tony21675/MyNovel/blob/main/STORY_PLAN.md).

Phase 1 implementation reads the active novel package's `STORY_PLAN.md` and pre-fills a missing Scene Idea for the matching chapter/scene; a saved `scene_idea` always wins, and plan-loaded text remains an unsaved editor value until Tony saves it or generates the contract. This feature is generic and must not hard-code `Taken at Dusk` details into application code. Next, update the active local Scene Idea to match the new canonical Scene 2 plan, generate/verify its contract endpoint, and generate a fresh scene. Do not overwrite local scene/state data or pull `current_state.json` and `writing_guidance.json` blindly because local files may differ from remote.

**Agreed roadmap (only Phase 1 currently authorized/active):** 1) automatic Scene Idea population from the novel's existing scene plan; 2) a plain-English Story Planner that proposes chapter/scene plan edits for Tony's approval; 3) a central Writing Desk that reuses current contract, Writer/review, and state-apply workflows. Finish and verify Phase 1 before starting Phase 2 or 3. Preserve current tabs and accepted content. No local-model change.

**Agreed Scene 1 arc:** Start in the middle of the night. Tony is awake in his bedroom after learning from Maya what happened to Tiffany. He quietly checks on Maya while she sleeps in Tiffany's bedroom, adjusts her covers only if needed without waking her, returns to his own room, and continues processing his worry, guilt, and uncertainty through the remainder of the night. End at daybreak. Do not begin breakfast preparation, wake Maya, bring in guests, or disclose the abduction to the group in this scene. Tony did not witness the abduction; never give him first-hand sensory memories of it. Do not invent the kidnapper, motive, destination, buyer, or new clues. Required Beats is intentionally empty.

**Sarah continuity to preserve:** Tony promised Sarah he would change and not return to the “old Tony” from his military days. The letter Sarah left for Tony remains unopened and is marked “For emergencies only.” Tony does not know its contents. It is the one thing that might let him break his promise, but he cannot know whether it permits or requires anything until the letter is opened and its contents are revealed. Never invent, quote, or imply knowledge of the letter's contents. Do not have Tony open, reach for, or decide to open it at this stage; its opening is reserved for a later point in the story.

**Latest code and verification:** Explicit author endpoints, including temporal boundaries, now take priority over stopping after one highlighted action. The Writer can let elapsed time pass through relevant thoughts and natural transitions without padding or inventing consequential events. Code is on StoryBuilder main at [commit 64f92ed](https://github.com/tony21675/StoryBuilder/commit/64f92ed9e29d55673a6e8ac88cb8ee45b0e682ba). GitHub Actions [run 39109698501](https://github.com/tony21675/StoryBuilder/actions/runs/39109698501) passed compilation and all 174 unit tests. On Tony's laptop, the focused test command was run after pulling; the reported final test result was 47 tests, OK. The latest live generation ended at daybreak as requested, checked Maya once, and was approved by Tony. This confirms the behavior for this particular attempt, not a guarantee that every generation will behave identically.
The Writer style rule was then simplified in [commit ba89fa61](https://github.com/tony21675/StoryBuilder/commit/ba89fa61ae853fd62feeaccce953a58d6221adbe), replacing the existing rule rather than adding a new one. This was a prompt-text-only change; no automated status checks were reported for that commit, and the earlier test results are not verification of this latest prompt edit.

## Small generic improvement note (not implemented)

During this scene, the accepted prose and `current_situation` clearly ended at daybreak, but the ending-state analyzer retained the starting `time.period` value `the middle of the night`. Tony manually corrected the time period in the preview to daybreak/early morning (while leaving `exact_time` unestablished) before applying the update. Later, discuss and implement a generic improvement so the ending-state analysis derives/updates the time period from the scene's actual ending and explicit temporal endpoint, instead of blindly carrying forward stale starting-time metadata. This must work across novels and preserve uncertainty about exact clock time. **This is a backlog note only; no code has been changed for it.**

## Correct scene workflow

1. **Scene Contract:** Edit the plain-English Scene Idea. **Generate/Replace Contract** saves the idea, generates the supporting direction and endpoint, saves the generated fields to the local novel package, and automatically refreshes Writer's Scene Direction. If an existing contract is present, confirm replacement only when that is intended. A separate **Build Scene Direction** click is not normally needed after contract generation; it remains available for a manual refresh.
2. **Check the generated direction:** Confirm chapter/scene, cast, starting situation, physical continuity, and the End line. The Scene Idea is primary. Generated direction and compact contract are supporting context. Do not turn ordinary prose into Required Beats; only author-labeled Required Beats are formal beats.
3. **Write:** Click **Write Next Scene** only when the direction is correct and no generation is already running. Let generation finish before navigating or closing.
4. **Review:** Read the entire prose. StoryBuilder does not decide acceptance for Tony. Review the requested scene movement and endpoint, continuity, character knowledge, established canon, and whether consequential facts were invented. Before any edit, discuss the specific correction with Tony and get his agreement. For **Focused Change**, handle exactly one agreed correction per run, then review the full returned scene with Tony before discussing the next correction. Never bundle multiple corrections into one run. Use **Regenerate Scene** only when a whole new attempt is appropriate. **Reject Scene** discards the current unaccepted attempt without changing accepted prose or Current State. Tony's preference is to discard failed attempts rather than create separate draft files; use **Save Draft** only when he explicitly wants to preserve an attempt.
5. **Accept only after approval:** **Accept Scene** saves the prose as the accepted manuscript section and saves its starting-state snapshot. If the prose fails review, do not accept it to advance the workflow.
6. **Analyze accepted prose:** Click **Analyze Accepted Scene** only after acceptance. Inspect the full merged ending-state JSON preview. The preview alone changes nothing. Click **Apply State Update** only after the proposed facts, locations, physical state, time, and character knowledge are understood and acceptable.
7. **Continue:** Applying a valid state update saves the state, saves a recoverable ending snapshot, advances the current scene pointer, and automatically refreshes Writer's Scene Direction. It does **not** automatically finalize a chapter. Use the explicit chapter-finalization action only when Tony confirms the chapter is complete.
8. **Save and sync intentionally:** **Save** writes the novel package locally. **Close** saves locally without syncing GitHub. **Close & Sync Novel** commits/synchronizes the MyNovel repository; do not use it merely to update StoryBuilder code. StoryBuilder and MyNovel are separate repositories.

## Local/remote MyNovel boundary

Tony's active local novel package has saved changes for Chapter 3, Scene 1 and the accepted/applied ending state. GitHub's remote current_state.json and writing_guidance.json have not yet been reconciled with the active local package and may still describe the old breakfast opening or stale time. **Do not pull, overwrite, or sync those two JSON files blindly.** Reconcile deliberately when local novel work is ready to sync; the saved local package remains the source of truth.

The latest StoryBuilder startup reported an untracked root-level file named FETCH_HEAD. It was left untouched because it needs read-only inspection before deciding whether it is safe to remove. Do not stage it accidentally or delete it as routine cleanup.

## Permanent collaboration and safety rules

- Always discuss a proposed change with Tony and get agreement on the specific change before editing, unless he has already explicitly authorized that exact change. This applies to prose, Focused Change requests, prompts, story/state data, code, UI, and workflow. Having a list of issues is not permission to fix them all at once. For Focused Change, make exactly one agreed correction per run, review the full returned scene with Tony, and only then discuss the next correction. Preserve accepted manuscript prose and existing state.
- StoryBuilder writes the novel; ChatGPT reviews and discusses the smallest useful correction. Do not substitute a ChatGPT rewrite for StoryBuilder's generation unless Tony explicitly asks.
- Keep StoryBuilder generic. Novel-specific facts and directions belong in the novel package, not hard-coded into application code.
- Keep the existing local Gemma 4 E4B instruction-tuned GGUF model. Do not replace, delete, or add another local model without discussion. Use sequential model execution on the resource-limited laptop.
- Before any app restart, first confirm there is no generation/revision running and determine whether unaccepted prose is on screen. Respect the Save/Discard/Cancel prompt; Cancel leaves the app open.
- Keep one remote branch, main, in each repository. Before any manual pull, inspect git status -sb and fast-forward only when safe. If anything is dirty or divergent, inspect and reconcile it rather than resetting or force-pulling.
- At the beginning of a future session, use the newest checkpoint here, not old Scene 4/Chapter 2 next-step notes from historical conversations. Older project history is not authorization to repeat superseded work.
