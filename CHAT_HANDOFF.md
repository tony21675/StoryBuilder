# StoryBuilder Chat Handoff

> Purpose: Paste this document into a new ChatGPT conversation to resume work without spending time rebuilding context. Update this file after meaningful project or story changes. Treat the current-session section as the first thing to refresh.

## Current Session: 2026-10-10

- **Current priority:** the StoryBuilder workflow safeguards are implemented on `fix/build-contract-from-idea-test`. GitHub Actions checks passed for commit `af5c9d93cd7ae3f581be17a1760800d75acf1638` (14 unit tests plus Python compilation). A handoff-only update may trigger another CI run; check the latest result before telling Tony the branch is ready to pull.
- Do not edit or delete anything in `tony21675/MyNovel` while repairing StoryBuilder. The active novel branch remains `chapter1-clean-reset`; its current state is Ch2 Scene 2, but its Chapter 2 plan and state have contradictions. It remains the source of safety/recovery data, not the target for this restart.
- Confirmed from the actual manuscript: Chapter 1 has six saved sections. Section 6 already has Maya rush into Tony's bedroom, Tony catch and settle her against his chest, comfort her, and Maya finally say, “Tiffany is gone.” Chapter 2 must continue from that exact moment. Do NOT repeat the arrival or that revelation in Chapter 2.
- GitHub history search found no committed `Chapter_02_Section_01.txt` or `Chapter_02_Section_01_draft.txt` on the current novel branch. The only Chapter 2 manuscript artifact there is `Chapter_02_Section_02_after_state.json`. There is no confirmed Scene 1 prose commit to restore. Most likely it only existed in StoryBuilder's unsaved Writer pane, but that precise cause is not proven.
- Scene-boundary idea for the fresh rebuild, grounded in the Chapter 1 ending:
  - Chapter 2 Scene 1: Continue from Maya against Tony's chest after she says Tiffany is gone. Tony stays patient and comforts her. He notices the fresh slap mark on her cheek and asks if she is hurt. Maya struggles to admit the man hit her. End when she manages to tell him she was hit; she remains deeply shaken against Tony.
  - Chapter 2 Scene 2: Continue from the admission; Maya tells Tony the details of Tiffany's abduction. End after he has the full account. Keep exactly one kidnapper.
  - Later plans (bath, Beth calling, clothes, tea) must not be pulled forward into these scenes unless the author explicitly adds them.
- **Root causes addressed in StoryBuilder code:**
  - Current situation is now explicitly authoritative over stale physical-state details in the scene-contract builder and Writer direction.
  - Building a contract from the Scene Idea now stores it under the chapter/scene that requested it, persists the novel package when it has a folder, and automatically refreshes Writer direction when the target scene is still active. This should remove the unnecessary “Apply Contract” then “Build Writer Direction” tab hopping after an ordinary contract build.
  - Generated Writer text is bound to its originating chapter, scene, and start state. Accepting it under a different scene number or changed start state is blocked, instead of misfiling it.
  - Unfinished Writer text is saved as a scene-specific draft before navigation, applying a changed starting situation, opening/creating another novel, or closing. Scene navigation is blocked while generation is running or before an accepted scene's state update is applied.
- Commits in this repair series include: `be17749` (scene-start precedence); `7ede018`, `5fd24e0`, `94118cf`, `baf2f32`, `937fe50` (scene drafts/context/contracts/navigation); `1154f56` (normalize semantic validator return values); `b034cd4` (test/API correction); `af5c9d9` (CI installs requirements and reports green checks).
- Added `tests/test_scene_workflow_safety.py` for draft-to-origin-scene, blocking navigation before applying an accepted scene's state, and state-precedence rules; updated the lint test to match its diagnostics API; added `.github/workflows/storybuilder-checks.yml`. Latest confirmed runs for `af5c9d9` passed both push and PR checks: run IDs `38033115769` and `38033118282`.
- No novel files or novel branches were modified by this repair. No branches were deleted.
- **Next step after latest CI is confirmed:** Tony pulls `fix/build-contract-from-idea-test` in the StoryBuilder checkout, starts the app, opens the separate Save As novel copy (not the original MyNovel package), and rebuilds Chapter 2 there. Guide this one step at a time. First set the Chapter 2 starting state from the saved Chapter 1 ending: Tony and Maya in Tony's bedroom, late afternoon; Maya is already against Tony's chest and has already told him “Tiffany is gone”; Tony knows only that disclosure so far. Then enter Scene 1's idea once, build the contract, and verify that Writer direction appears automatically. Do not ask him to shuffle between tabs or recreate the same event across multiple prompts.
- When reporting branch readiness, explain that code and tests are ready, not that the app was tested live with Tony's local Gemma model. That real-model smoke test only happens after he pulls and launches it. The active model is `Gemma-4-E4B_q4_0-it.gguf`.
  
## How to Work With Tony

- Read this handoff before responding and continue from the current task instead of restarting.
- Do not make Tony repeat details already included here.
- Do not guess what files, code, or branches contain. When current repository information matters, inspect GitHub's actual current branch and files first.
- Do not assume `main` is current. Use the branches named above unless the user reports a change, and verify as needed.
- Do not claim a test passed without evidence.
- Prefer local testing before permanent code changes.
- Never overwrite, reset, delete, or replace work without discussing it with Tony first.
- Give one clear next step at a time for computer walkthroughs.
- If something essential is unclear, ask one focused question rather than inventing details.
- Stay on the task at hand. Don't turn a minimal-contract test into a long list of new instructions before examining the actual result.

## Repositories

- StoryBuilder: https://github.com/tony21675/StoryBuilder
- Current StoryBuilder test branch: https://github.com/tony21675/StoryBuilder/tree/fix/build-contract-from-idea-test
- Private novel repository: https://github.com/tony21675/MyNovel
- Current novel branch: https://github.com/tony21675/MyNovel/tree/chapter1-clean-reset
- Archive branch: https://github.com/tony21675/MyNovel/tree/archive/pre-cleanup-2026-10-08
- Legacy archived files: https://github.com/tony21675/MyNovel/tree/archive/pre-cleanup-2026-10-08/archive/legacy-from-main

The novel archive branch preserves older material for retrieval. The active novel branch is the current working version. Older material was copied into the archive folder on the archive branch; do not assume further cleanup or deletion was done on the active branch.

## Technical Goal: Author-Controlled Scene Contract

StoryBuilder is being tested to see whether a local model can turn a small amount of author direction into a coherent, natural scene while respecting the intended boundaries.

Evaluate whether the model:
- Respects the intended beginning, middle, and stopping point.
- Preserves established story facts, chronology, character knowledge, and scene state.
- Develops natural dialogue, ordinary interaction, and believable emotional reactions on its own.
- Stops at the intended point rather than continuing into a later scene.
- Can do this without requiring a growing list of micro-instructions.

When output misses the target, first compare the contract and generated prose. Consider whether the cause is contract construction, prompt construction, story state, or model behavior. Make the smallest justified change and test again. Do not compensate for every miss by piling on extra constraints.

## Story Canon

- Tiffany, Maya, and Chloe are all **18 years old**.
- Maya has **dirty blonde hair** and brown eyes. She enjoys playing piano.
- Maya's father left after learning Beth was pregnant. Maya struggles with abandonment fears, being alone, disappointing people she loves, and feeling not good enough.
- Tony is Tiffany's father. He raised her after his wife Sarah died following Tiffany's birth.
- Tony has known Maya since she was a baby and regards her as family, like another daughter. He must not call her “kid.”
- Maya secretly loves Tony, but he does not know. Tony's care for her is parental and non-romantic.
- Tiffany and Maya are best friends with a sister-like bond. Chloe is also a close friend of both. The girls grew up together as neighbors.
- Tony is 40, 5'10", athletic, brown hair, hazel eyes, and a goatee. He is caring, protective, determined, and a retired former U.S. Army Special Forces soldier.
- Tiffany has long curly dark red hair and green eyes. She is affectionate, independent, talkative, outgoing, observant, and fiery.
- Chloe has long wavy medium-brown hair and hazel eyes. She is outgoing, direct, protective, and emotionally expressive.
- Tiffany always wears Tony's dog tags close to her heart. They contain a hidden tracker from Tony's former Special Forces equipment, linked to Tony's phone, not a military database. Tiffany does not know about it.
- Tony works night shifts, so sleeping in the late afternoon is normal. He cannot see or hear the road outside from his bedroom.
- Only one kidnapper was involved in the incident Maya witnessed.
- Maya, Tiffany, and Chloe have their own homes; Tony is protective and fatherly but respects their adult autonomy.

## Style and Scene Preferences

- Grounded, tense, emotional, suspenseful, character-focused prose.
- Let characters have natural everyday conversation and small moments before major events.
- The model may invent small talk, shared memories, ordinary feelings, and natural interaction if it does not contradict canon, chronology, character knowledge, or explicit constraints.
- Avoid screenplay-like or meta narration.
- Do not foreshadow later danger unless an active plot module or the author's directions permit it.
- Keep Tony and Maya's interactions parental/non-romantic from Tony's side.

## Established Story Outline and Continuity

- Chapter 1 scene plan: Scene 1 school to gas station; Scene 2 at gas station; Scene 3 leaving the gas station and establishing the road; Scene 4 van appears but stop before the abduction; Scene 5 the abduction on a quieter road; Scene 6 Maya reaches Tony and wakes him.
- Tony is asleep in the late afternoon due to night work and cannot see or hear the road from his bedroom.
- In earlier Chapter 2 planning, Maya was comforted by Tony after reaching his home. Planned later details included a warm bubble bath (not a shower), giving Maya choices about privacy/help, a call from Beth while Maya bathes, Tiffany's clothes placed in the kitchen for Maya, and tea at the kitchen table. Check the actual current files before assuming any of those beats have already been written.

## Recommended Workflow for Each Test

1. State the intended behavior of the current contract in plain language.
2. Let the user run the current setup and provide the actual output.
3. Compare output with the intended scene boundary and canon.
4. Identify the likely source of the miss before proposing a fix.
5. Make one small, testable adjustment.
6. Update this handoff's **Current Session** section after the test result or task changes.

## Updating This File

After meaningful progress, update this file on the current StoryBuilder test branch with:
- The new current task and scene status.
- What was actually tested and observed.
- Any confirmed code/contract changes and their commit or branch.
- The next concrete step.
- Any new canon correction that should persist across chats.

Keep stable canon and working preferences, but replace stale current-session details. Do not record guesses as facts.
