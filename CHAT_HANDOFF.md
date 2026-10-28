# StoryBuilder handoff — October 27, 2026

## Current checkpoint: app closed; focused-revision fix committed

StoryBuilder was closed with Ctrl+C. Scene 11 was never accepted. The latest prose was pasted into this conversation, but do not assume it was saved to the novel package; the closed app's in-memory draft may be gone. Do not repeat revision attempts yet.

The focused-revision change is committed on `redesign/simplified-writing-workflow`: `fa012c2` gives the revision model the complete current scene as explicitly read-only context while keeping the selected passage as the only editable span; `5454cc3` adds regression tests that check the full-scene context reaches the initial and retry prompts. This changes the focused-edit workflow only. It adds no global Writer instructions or novel-specific rules. The connected status lookup returned no published checks for the new commits, and this execution environment could not clone from GitHub. Treat the regression tests as unverified until GitHub Actions or a laptop test run confirms them.

When ready later tonight, launch `./start.sh` from `~/Documents/StoryBuilder` to sync the branch (fast-forward only). After sync, a useful local check is `python3 -m pytest tests/test_focused_revision.py -q`, followed by the full suite if convenient. Focused revisions are not yet included in prompt-trace capture, which remains a separate observability gap.


## Cross-computer novel sync diagnosis

I checked GitHub directly. `tony21675/The-Long-Way-Home` on `main` still has `current_state.json` set to Chapter 1, Scene 10. Its latest novel sync commit is `3367931421b466fef0e7d9d8f7b6bb2f2ee2a391` (2026-10-27 21:17 UTC / 3:17 PM MDT). The Scene 10 after-state file is not present on the remote branch. The Oct 27 evening trace therefore loaded an older novel state; the earlier handoff's Scene 11 pointer described local state on the other computer and was not pushed to GitHub.

Important distinction: `./start.sh` and **Close & Sync App** synchronize StoryBuilder application code only. They do not synchronize the novel. Ctrl+C bypasses the app's close handler. Novel data has its own toolbar button: **Sync Novel**.

Recovery sequence: on the computer where the Stage 2 update actually advanced The Long Way Home to Scene 11, open that package and press **Sync Novel**; verify the app reports “Novel synchronized successfully.” Only then move to the other computer, open the same package, and press **Sync Novel** there before writing. The second sync should pull the Scene 11 state. If the first computer no longer has Scene 11 locally, or either sync reports an error/conflict, stop and inspect the local novel repository before attempting another scene. Do not edit `current_state.json` manually or accept the aborted Scene 10 draft.

Latest remote code commits on `redesign/simplified-writing-workflow`:

- `45524e27550f05db21b4ea29785ba33e07bea156`: make automatic writing-notes learning explicitly opt-in; default OFF.
- `f2f06799bc4dc0199259ad54f515448d9eafa013`: bound the optional post-accept notes review to 6,144 context tokens, 350 output tokens, and a 180-second timeout.
- `58f08f8444224ef2dda9efeac128707e903bfa45`: test the setting and limits.
- `e54b77180d29190880cb0a30eedc5a449a86a1ce`: skip one redundant Writer restore after successful automatic Scene Idea suggestion.
- `dcacdc590066bec7f1be65333a74db17709996be`: make the separate initial notebook seed scan honor the same default-off flag.
- `d7b9b25fa7a707529bcd05d615c474b8b1701385`: test that startup skips the seed scan by default.
- `eebf744a4308e30f28f6fb70f1e1431f045f90ca`: remove the duplicate Writer restoration after the continuity audit. The combined review now restores Writer once.
- `dbc268ba563a20784b186630d9c737e8b3ee0525` and `eb43886aad4a104a848ee20c0fbf1faf79599e49`: add a generic endpoint-evidence check for author-marked End/Hard Stop sections. It requires one dedicated `HARD_STOP` check with exact supporting text from the ending passage. This affects validation only, not the Writer prose prompt, and does not promote stale model-generated endpoint summaries into mandatory stops.
- `d55d5826ebba1f13afea443136109e869c381a49`: regression tests for endpoint false passes and duplicate Writer restoration.
- `fa012c2eb49974f4ad8ce788cee7ac87372c5025`: focused passage revisions now receive the complete current scene as read-only context; only the selected passage can be replaced.
- `5454cc3bc7c1e43e4ac242468b6fb6557d3f95df`: regression tests verify that full-scene context is included in the initial and retry prompts.

GitHub Actions passed on `d55d582`: both **Python tests** and **StoryBuilder tests** succeeded (414 tests plus 71 subtests in the Python run). These are remote results; sync the laptop and rerun its local test suite after pulling.


## What the speed fix changes (and doesn't)

There are two distinct writing-notes paths. The post-accept updater requires `STORYBUILDER_AUTO_WRITER_NOTES=1`; the prior commits bound that path to a 6,144-token context, 350 output tokens, and a 180-second timeout. The current process is almost certainly the old local version of that post-accept task, based on the saved-state sequence and its 16,384/4,000 process arguments. A separate one-time seed scan runs before Writer startup when the notebook file is blank; that path had missed the same opt-in check. Commit `dcacdc5` closes that separate gap, so the normal default-off workflow should skip both housekeeping paths.

Existing notes are retained; no note files are deleted. If the flag is explicitly enabled, the initial seed scan still uses the general Writer generation budget/timeout rather than fully applying the note-specific limits; keep it disabled unless intentionally testing this feature. The app uses a shared `WriterEngine`, and changing system prompts still restarts `llama-cli`.

The automatic Scene Idea path no longer reloads the previous Writer system prompt immediately after a successful suggestion. The next writing task installs the relevant prompt. This saves one unnecessary model startup in the common next-scene workflow.

**Remaining limitation:** Changing task-specific system prompts in the shared `WriterEngine` still calls `reset_context()`, which stops and restarts `llama-cli`. Several distinct tasks can therefore still reload the model. A larger persistent-server/per-request-prompt redesign would be needed to remove most of these reloads; don't attempt that untested architecture change mid-session.

## The Long Way Home — Scene 10 accepted; Scene 11 draft needs its endpoint

Local novel: `~/Documents/MyNovel/The-Long-Way-Home`; GitHub repo: `tony21675/The-Long-Way-Home`.

Scene 10 was accepted, the false-positive “team didn't commit to one high-risk strategy” finding was rejected, and Stage 2's proposed state was applied and saved. Current pointer is Chapter 1, Scene 11.

The accepted end of Scene 10 has Elena committing to a manual, controlled isolation sequence on Delta-9. Daniel runs the protocol; Morgan watches physical feedback; Priya monitors crew stability. The operation's result and underlying root cause remain unknown. Scene 11 begins from this immediate choice and must not replay Scene 10.

Preserve the uncertainty in Daniel's line, “maybe another hour before that slight curve decides to become a cliff.” Do not state a definite remaining hour or claim the isolation succeeded prematurely. Two potentially over-definite details in Scene 10 (“critical leak” and elevated cortisol readings “through environmental monitoring”) were noted as cautions, but the author accepted the scene; do not reopen it or expand either into confirmed diagnosis/cause without evidence.

## Scene 11 trace findings (October 27)

Private trace: `tony21675/StoryBuilder-Traces` `prompt_trace.json`, Chapter 1 Scene 11, trace window 22:25:31–22:43:59 UTC. It completed without runtime error. Recorded model work was about 11m36s writing, 2m26s semantic validation, and 4m01s continuity/scope audit.

The prose starts the Delta-9 isolation, includes Morgan's physical warning and Daniel's recalculation, then ends while the crew is redirected to deal with a suspected local leak. It does **not** reach the author-marked endpoint: pressure readings stabilizing just above the collapse threshold while underlying instability is exposed. Both automated reviews incorrectly passed because the endpoint was treated as satisfied without showing it in the scene. Scene 11 remains unaccepted. Stop the repeated revision loop until the new focused-revision code has been synced and tested. It now receives the complete current scene as read-only context, but this does not guarantee that the model will dramatize every requested event; check the next result once and stop if it still only summarizes the outcome.

The new generic `HARD_STOP` check should catch this class of false pass on future runs after the laptop syncs/restarts. It activates only when the author explicitly marked an ending in the Scene Idea. It adds no novel-specific facts or prose-writing rules.

After Scene 11 is accepted and its ending-state update applied, StoryBuilder should save, advance to Scene 12, refresh Writer direction, and invoke the next-Scene-Idea suggestion automatically. Verify that trigger in the next trace instead of manually requesting a duplicate suggestion.

## Verified State Analysis warning fix



Earlier code commit `2c4d7778b5e8e1a656289cf44e6c394d918bf0b9` makes the state reviewer return a warning when the model produces findings but strict evidence validation rejects all of them. After accepting Scene 10, the live trace showed two rejected findings (Zoe's independent communications inquiry and Daniel's predictive modeling task). The trace recorded: “The state reviewer returned findings, but none passed evidence validation. No review popup was shown; no state changes were saved.” The author confirmed the warning appeared in the app's writer status line. This behavior is verified live: it's a status message, not a modal popup, and invalid findings still do not pass validation or get applied automatically.

Latest private trace: https://github.com/tony21675/StoryBuilder-Traces/blob/main/prompt_trace.json (contains private story text; don't expose publicly).



## Repo and collaboration rules

- StoryBuilder local: `~/Documents/StoryBuilder`; remote `tony21675/StoryBuilder`; active branch `redesign/simplified-writing-workflow`.
- Startup `./start.sh` calls `sync.sh start` then `exec python3 storybuilder.py`. The sync script refuses to sync from `main`, requires the current branch to track `origin/<branch>`, stashes/restores uncommitted StoryBuilder changes, and only fast-forward pulls. No branch switch/reset/rebase.
- Use `python3`, never `python`, for Linux terminal commands. One terminal command per message. Avoid large copy/paste.
- Inspect GitHub source and trace directly instead of asking user to paste large files.
- Discuss before changes to StoryBuilder app code or novel packages. Handoff-only edits don't require permission. Update/prune handoffs after meaningful milestones.
- Preserve accepted prose and state; never apply state proposals without explicit author approval. Keep scene suggestions editable. State is a fallible memory aid, not canon.
- Let the story breathe; avoid over-prescriptive instructions and don't rewrite accepted prose merely to satisfy false-positive review findings.
- End StoryBuilder on `main` only after deliberate final merge/review. Never delete or switch branches blindly. Each novel repo should keep one branch per novel.

## *The Long Way Home* premise

Mars research outpost; six main characters under 30 (four women, two men), all single/unmarried at the beginning. The crisis is accidental, not sabotage, and the goal is survival until repair or rescue. Mars rescue/resupply takes months. Keep possible causes separate unless evidence connects them. Silicate-like trace and entry route remain unconfirmed; Zoe's patterned communications anomalies remain unexplained and unconnected to the life-support issue unless later evidence proves otherwise.

## Other project context

- `Taken_at_Dusk` at `~/Documents/MyNovel/Taken_at_Dusk`, GitHub `tony21675/MyNovel`: Chapter 3 Scene 3 snapshot was Saturday morning at Tony's home. Tiffany is in the van with the kidnapper; Maya is shaken at the table; Chloe is steadying Tony at the kitchen island; Beth, Jessica, and Rick are present. No operational plan established. Chloe should be unexpectedly steady for Tony; allow Maya's possible stress-slip “I love you” naturally, never force it.
- LocalStoryChat fallback: `~/Documents/LocalStoryChat`, GitHub `tony21675/LocalStoryChat`; Local Story Chat v7, Dolphin 3.0 Llama 3.1 8B Q4_K_M, llama-cli Vulkan, 10 GPU layers, `--simple-io`, default files under `~/StoryFiles/`.
- Future separate app idea: e-liquid flavor/recipe tracker with separate flavor profiles for the user and his wife, separate from StoryBuilder.

## Next steps

1. Stop the stuck old app process. The accepted Scene 10 and applied state should already be saved; an unsaved generated Scene 11 suggestion, if any, can be regenerated.
2. Restart with `./start.sh` so the code updates sync from GitHub.
3. Run `python3 -m pytest -q` to verify the new changes.
4. Continue Scene 11 from the manual Delta-9 isolation decision.
