# StoryBuilder handoff — October 27, 2026

## Immediate current state

**Live State Analysis warning fix verified.** After accepting Chapter 1, Scene 10 of *The Long Way Home*, the author ran Stage 2 State Analysis and uploaded a trace. The state summary was proposed, then the model reviewer returned two findings:
1. Add Zoe's independent monitoring of the patterned communications anomalies.
2. Give more prominence to Daniel's predictive modeling task.

Both findings failed the required evidence validation and were suppressed. The trace recorded the warning “The state reviewer returned findings, but none passed evidence validation. No review popup was shown; no state changes were saved.” The author confirmed that the app displayed the warning in the writer status line. This is the desired transparency behavior; the new warning is a status message, not a modal popup. Invalid findings are not allowed through, and no state update is applied automatically.

**The Scene 10 state proposal has not been applied yet.** The proposed summary says Daniel estimates “less than an hour remains before critical failure,” while accepted dialogue says “maybe another hour before that slight curve decides to become a cliff.” Before applying, review that wording for calibrated uncertainty. Click Apply State Update only if the summary is acceptable.

Latest trace (contains private story text): https://github.com/tony21675/StoryBuilder-Traces/blob/main/prompt_trace.json

## Scene 10 accepted prose status

Local novel: `~/Documents/MyNovel/The-Long-Way-Home`; GitHub repo: `tony21675/The-Long-Way-Home`.

The accepted scene ends with Elena committing the crew to a manual, controlled isolation sequence on Sensor Node Delta-9. Daniel is to run the protocol, Morgan will monitor external/physical feedback, and Priya will monitor crew stability. The procedure's result and the root cause are still unresolved. Start Scene 11 from this decision; do not replay Scene 10.

The completion review's “team collectively commits” missed-beat finding was a false positive because Elena explicitly says, “Then that’s the course. Manual isolation sequence commencing immediately.” The author rejected the false positive and accepted the scene. The author often rejects reviewer false positives; don't treat every finding as a request to rewrite.

Two prose details were noted as potentially over-definite/specific: calling the infrared reading a “critical leak,” and Priya claiming elevated cortisol signatures can be read through environmental monitoring. The author accepted the scene; keep these as potential cautions, not reasons to change accepted prose or assert a confirmed cause.

## StoryBuilder repo and validation

- Local path: `~/Documents/StoryBuilder`.
- GitHub repo: `tony21675/StoryBuilder`.
- Active development branch: `redesign/simplified-writing-workflow`. No branch switching or deletion without checking first. Long-term preference: end with only `main` after deliberate review/merge.
- Code transparency fix: commit `2c4d7778b5e8e1a656289cf44e6c394d918bf0b9`; regression test added to `builder/state_review.py` / `tests/test_state_review.py`. If the reviewer returns findings but all are rejected by strict evidence validation, the flow now returns a warning instead of silently appearing to do nothing. It does not bypass evidence checks or auto-save state.
- Handoff-only update before this live verification: commit `70fdc37383ecfdcd6b546724d36dd8d5021fa4ad`.
- Laptop update: clean tree confirmed on the redesign branch, fetched and fast-forward-pulled updates, then focused tests passed (**13 passed in 0.02s**) and full suite passed (**406 passed in 0.67s**).
- Current in-app verification: warning displayed in the writer status line; trace has no final error, validation warning, or trace-save error. Live verification complete.
- Startup: `./start.sh` runs `sync.sh start` before launching `python3 storybuilder.py`. The current sync script rejects syncing from `main`, requires the current branch to track `origin/<branch>`, stashes/restores uncommitted local work, and only fast-forward pulls. It does not switch branches or use reset/rebase.

## Collaboration preferences and non-negotiables

- Always use `python3`, never `python`, in terminal commands on the user's Linux laptop.
- Give one terminal command per message. Avoid long copy/paste blocks.
- Inspect GitHub files/traces directly when accessible instead of asking the user to paste large amounts of output.
- Discuss before changing StoryBuilder code or novel packages. Handoff-only changes do not require permission.
- Update handoff files after meaningful code/app/novel milestones and prune stale detail so the handoff stays useful.
- Preserve accepted prose and state. Never apply a state proposal without explicit author approval.
- StoryBuilder should support natural writing, not turn prose into a checklist. The author wants a more streamlined writing workflow, fewer duplicate screens/buttons, editable scene ideas, copyable review content, and fewer false-positive review chores.
- Treat saved summaries as fallible memory aids, not authoritative proof. Keep uncertainty explicit. Do not invent past events, causation, or character knowledge.
- Avoid unnecessary rewrites caused by automated findings the accepted prose already satisfies.
- Do not make app changes or novel-package changes without prior discussion. Never delete branches blindly.

## *The Long Way Home* continuity

Mars research outpost survival story; six main characters under 30, four women and two men; all single/unmarried at the beginning. The crisis is accidental, not sabotage, and the goal is survival until repair or rescue. Earth rescue/resupply takes months.

Current situation after Scene 10: The oxygen scrubber manifold temperature is still climbing despite the Delta-9 bypass. The rate was less steep after the initial spike, and Morgan observed an unusual localized infrared signature at the junction plate. The crew has chosen a manual, controlled isolation procedure, which carries pressure-fluctuation risk. Do not say isolation has succeeded before prose shows it. The source of the heat problem, the silicate-like trace and any entry route remain unconfirmed. Zoe's patterned communications readings remain a separate unresolved investigation unless later evidence establishes a connection.

Next writing target: Chapter 1, Scene 11, after the author reviews and (if satisfied) applies the current state proposal.

## Writing philosophy and future UX ideas

- “The story is the novel. The state is only a memory aid.” Track main-plot stakes, decisions, material discoveries, and unresolved danger. Avoid prompting for every possible state detail.
- User reports that characters rarely laugh, joke, or make ordinary chit-chat. A future optional, light-touch tone field may help (for example, “tense, grounded, warm, occasional humor”), but no tone feature has been approved or implemented.
- UX priorities: fewer screens to write a scene; remove duplicate/confusing buttons; editable next-scene suggestion; plain-English guided review rather than full JSON; provide copy options where text is trapped in popups. Ctrl+F isn't available in the user's UI, so don't rely on search-in-text instructions.

## Other project context

- `Taken_at_Dusk` at `~/Documents/MyNovel/Taken_at_Dusk`, GitHub `tony21675/MyNovel`: Chapter 3 Scene 3 snapshot was Saturday morning at Tony's home. Tiffany is in the van with the kidnapper; Maya is shaken at the table; Chloe is steadying Tony at the kitchen island; Beth, Jessica, and Rick are present. No operational plan established. Chloe should be unexpectedly steady for Tony; allow Maya's possible stress-slip “I love you” naturally, never force it.
- LocalStoryChat fallback: `~/Documents/LocalStoryChat`, GitHub `tony21675/LocalStoryChat`; Local Story Chat v7, Dolphin 3.0 Llama 3.1 8B Q4_K_M, llama-cli Vulkan, 10 GPU layers, `--simple-io`, default files under `~/StoryFiles/`.
- Future separate app idea: e-liquid flavor/recipe tracker with separate flavor profiles for the user and his wife. Keep it separate from StoryBuilder.

## Current next actions

1. Review the un-applied Stage 2 state summary in StoryBuilder.
2. If satisfactory, use **Apply State Update** explicitly. If not, edit the plain-English summary so it preserves the uncertainty in Daniel's deadline estimate.
3. Continue to Scene 11 from Elena's decision to start manual isolation.
4. Keep the current app session intact; remote handoff-only commits can be synced safely when convenient.
