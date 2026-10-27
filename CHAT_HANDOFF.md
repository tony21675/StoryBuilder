# StoryBuilder handoff — October 27, 2026

## Immediate action: recover from the 30-minute writing-notes task

The live `ps` snapshot showed StoryBuilder PID 1516205 (48:42 elapsed) and `llama-cli` PID 1519167 (26:38 elapsed). Its system prompt identifies the task as the initial writing-craft notebook seed scan, not scene writing. The scan runs before Writer startup when the notebook is blank, but its code was missing the default-off opt-in check. The accepted Scene 10/state update was already saved before this later scan. For this exact snapshot, interrupt only the child with `kill -TERM 1519167` to let the error-recovery path skip the scan and continue Writer startup; recheck PIDs before signaling, and do not kill the StoryBuilder parent if recovering the current session. To apply the remote fix, close/restart with `./start.sh` from `~/Documents/StoryBuilder` so `sync.sh start` pulls the commits.

Latest remote code commits on `redesign/simplified-writing-workflow`:
- `45524e27550f05db21b4ea29785ba33e07bea156`: automatic writing-notes review now requires explicit opt-in with `STORYBUILDER_AUTO_WRITER_NOTES=1`; default is OFF.
- `f2f06799bc4dc0199259ad54f515448d9eafa013`: optional notes review constrained to 6,144 context tokens, 350 output tokens, and a 180-second generation timeout.
- `58f08f8444224ef2dda9efeac128707e903bfa45`: tests for opt-in/default-off and bounded settings.
- `e54b77180d29190880cb0a30eedc5a449a86a1ce`: skip redundant restoration/reload of the Writer prompt after a successful **automatic** Scene Idea suggestion. Manual suggestions retain prior behavior.
- `dcacdc590066bec7f1be65333a74db17709996be`: make the **initial startup seed scan** honor the same explicit opt-in flag. This was the missing path: the post-accept updater was gated, but Writer startup still launched the seed scan whenever the notebook was blank.
- `d7b9b25fa7a707529bcd05d615c474b8b1701385`: add a regression test that startup skips the seed scan when the setting is off.

GitHub Actions passed for the latest test commit `d7b9b25`: both **Python tests** and **StoryBuilder tests** completed successfully. The laptop still needs to sync the remote commits and rerun its local test suite after pulling. The earlier local checkpoint was **406 passed in 0.67s**, with 13 state-review tests passed; do not treat that older local run as verification of the newer changes.

## What the speed fix changes (and doesn't)

There are two distinct writing-notes paths. The post-accept updater already requires `STORYBUILDER_AUTO_WRITER_NOTES=1`. A separate one-time seed scan runs before Writer startup when the notes file is blank; that path had missed the opt-in check and could restart `llama-cli` before allowing the Writer to start. Commit `dcacdc5` closes that gap, so the normal default-off workflow proceeds directly to Writer startup and does not create or overwrite notes.

Existing notes are retained; no note files are deleted. If the flag is explicitly enabled, the initial seed scan still uses the general Writer generation budget/timeout rather than fully applying the note-specific limits; keep it disabled unless intentionally testing this feature. The app uses a shared `WriterEngine`, and changing system prompts still restarts `llama-cli`.

The automatic Scene Idea path no longer reloads the previous Writer system prompt immediately after a successful suggestion. The next writing task installs the relevant prompt. This saves one unnecessary model startup in the common next-scene workflow.

**Remaining limitation:** Changing task-specific system prompts in the shared `WriterEngine` still calls `reset_context()`, which stops and restarts `llama-cli`. Several distinct tasks can therefore still reload the model. A larger persistent-server/per-request-prompt redesign would be needed to remove most of these reloads; don't attempt that untested architecture change mid-session.

## Scene 10 and current novel continuity

Local novel: `~/Documents/MyNovel/The-Long-Way-Home`; GitHub repo: `tony21675/The-Long-Way-Home`.

Scene 10 was accepted, the false-positive “team didn't commit to one high-risk strategy” finding was rejected, and Stage 2's proposed state was applied and saved. Current pointer is Chapter 1, Scene 11.

The accepted end of Scene 10 has Elena committing to a manual, controlled isolation sequence on Delta-9. Daniel runs the protocol; Morgan watches physical feedback; Priya monitors crew stability. The operation's result and underlying root cause remain unknown. Scene 11 begins from this immediate choice and must not replay Scene 10.

Preserve the uncertainty in Daniel's line, “maybe another hour before that slight curve decides to become a cliff.” Do not state a definite remaining hour or claim the isolation succeeded prematurely. Two potentially over-definite details in Scene 10 (“critical leak” and elevated cortisol readings “through environmental monitoring”) were noted as cautions, but the author accepted the scene; do not reopen it or expand either into confirmed diagnosis/cause without evidence.

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
