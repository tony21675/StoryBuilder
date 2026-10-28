# StoryBuilder handoff — October 27, 2026

## Current checkpoint: saved Scene 10 restoration fixed in Open Novel

The new trace exposed a loading bug, not a missing GitHub manuscript. `_load_startup_novel()` already restores saved prose; the explicit **Open Novel** path cleared the Writer but omitted that restore call. The app therefore generated a fresh Scene 10 even though the saved version existed remotely.

Fix and verification on `redesign/simplified-writing-workflow`:
- `77b2075`: explicit Open Novel now calls `_load_saved_scene_into_writer()` after the package and Writer controls refresh.
- `1d4d3ce` and `1d14215`: regression test exercises restoration from an actual saved Scene 10 file with a matching before-state, plus a Tk test-fixture fix.
- `c05bc6b`: update legacy close-flow tests to match the already-implemented safe novel-first sync behavior.

Both GitHub Actions checks passed at `c05bc6b`: **Compile and unit tests** and **StoryBuilder tests**. These changes do not edit the novel package or its state.

The latest trace (2026-10-28 03:54:48–04:01:39 UTC) was a new Chapter 1 Scene 10 generation, not a focused revision and not the saved manuscript. It produced three review findings even though Elena's generated ending orders immediate manual isolation; the independent continuity audit considered the endpoint clear. Treat those findings as a separate validator disagreement. Do not revise the saved manuscript to appease them before verifying restoration.

When next using the laptop, start StoryBuilder through `./start.sh` to pull the branch. Open *The Long Way Home* and check for the Writer status **“Restored saved Chapter 1, Scene 10 into Writer.”** Verify that the saved prose is visible before generating anything. If the status reports a state mismatch or missing prose, stop and capture the exact message.

## Cross-computer novel sync diagnosis and safeguards

GitHub has `tony21675/The-Long-Way-Home` on `main` with remote `current_state.json` still pointing at Chapter 1, Scene 10. The manuscript file `Manuscript/Chapters/Chapter_01/Chapter_01_Section_10.txt` exists, and `Chapter_01_Section_10_before_state.json` matches that current state. `Chapter_01_Section_10_after_state.json` is absent, so the state transition to Scene 11 is not saved remotely.

The earlier sync safeguards remain:
- `68f84fc`: app close saves/syncs the novel before syncing StoryBuilder; Ctrl+C uses the safe close flow.
- `f1a6623`: sync the novel before loading its local state at startup or Open Novel; sync failure cancels opening by default.
- `6615aca`, `06a1fbb`, and `d03292b`: regression coverage for shutdown, Ctrl+C, and pre-open sync.
- `e838ec1`: toolbar text is **Save & Sync & Close**.
- `77b2075`: restore saved manuscript prose on explicit Open Novel, matching startup recovery.

The author is okay recreating the old unsaved Scene 11 draft; do not chase or manually restore it. Restore the saved Scene 10 prose first. Then analyze the ending and review the state-update proposal; apply it only after the author confirms the proposed changes. Do not manually edit `current_state.json`.

## What the speed fix changes (and doesn't)

There are two distinct writing-notes paths. The post-accept updater requires `STORYBUILDER_AUTO_WRITER_NOTES=1`; the prior commits bound that path to a 6,144-token context, 350 output tokens, and a 180-second timeout. The current process is almost certainly the old local version of that post-accept task, based on the saved-state sequence and its 16,384/4,000 process arguments. A separate one-time seed scan runs before Writer startup when the notebook file is blank; that path had missed the same opt-in check. Commit `dcacdc5` closes that separate gap, so the normal default-off workflow should skip both housekeeping paths.

Existing notes are retained; no note files are deleted. If the flag is explicitly enabled, the initial seed scan still uses the general Writer generation budget/timeout rather than fully applying the note-specific limits; keep it disabled unless intentionally testing this feature. The app uses a shared `WriterEngine`, and changing system prompts still restarts `llama-cli`.

The automatic Scene Idea path no longer reloads the previous Writer system prompt immediately after a successful suggestion. The next writing task installs the relevant prompt. This saves one unnecessary model startup in the common next-scene workflow.

**Remaining limitation:** Changing task-specific system prompts in the shared `WriterEngine` still calls `reset_context()`, which stops and restarts `llama-cli`. Several distinct tasks can therefore still reload the model. A larger persistent-server/per-request-prompt redesign would be needed to remove most of these reloads; don't attempt that untested architecture change mid-session.

## The Long Way Home — current recovery point

- Local novel: `~/Documents/MyNovel/The-Long-Way-Home`; GitHub: `tony21675/The-Long-Way-Home`, branch `main`.
- Saved Scene 10 prose is on GitHub and its before-state matches the live remote state. The remote pointer is still Scene 10 because the after-state snapshot was not pushed.
- Saved Scene 10 ends with Elena committing to immediate manual isolation on Delta-9. Daniel runs the procedure, Morgan monitors physical feedback, and Priya watches crew stability. The result and root cause are unresolved.
- After syncing StoryBuilder, load the saved Scene 10, not the newly generated draft in the latest trace. Review it, analyze its ending, and apply the proposed state update only after reviewing it. The Writer should then point to Scene 11.
- Preserve uncertainty in Daniel's line, “maybe another hour before that slight curve decides to become a cliff.” Do not turn it into a definite countdown or claim isolation succeeded prematurely.

## Previous Scene 11 draft (not the current recovery source)

The earlier Scene 11 trace was not saved as accepted manuscript prose on GitHub. Its draft may be recreated once the Scene 10 ending-state update has been reviewed and the pointer advances. Do not try to recover that draft from the current remote novel package.

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

1. Run `./start.sh` from `~/Documents/StoryBuilder` to sync the latest branch.
2. Open *The Long Way Home* and confirm the status says the saved Chapter 1, Scene 10 was restored. Do not regenerate until the saved prose is visible.
3. Review the saved Scene 10 ending, run **Analyze Accepted Scene**, and inspect the proposed state changes. Apply them only when they accurately reflect the saved prose.
4. Once the pointer advances to Scene 11, regenerate that scene from the established Delta-9 isolation decision; the earlier unsaved draft is not needed.
5. GitHub Actions passed both test workflows at commit `c05bc6b`. Use `python3 -m pytest -q` after syncing if a local verification run is desired.
