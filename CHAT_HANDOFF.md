# StoryBuilder Chat Handoff

> Purpose: Paste this document into a new ChatGPT conversation to resume work without spending time rebuilding context. Update this file after meaningful project or story changes. Treat the current-session section as the first thing to refresh.

## Current Session: 2026-10-10

- **Status: StoryBuilder is open; the first loaded package is the original.** Tony reports the app's top-right path label shows `/home/tony/Documents/MyNovel`. This confirms the app initially loaded the original package, not the rebuild copy. No package changes, generation, saves, or sync actions have been performed in this session.
- **Immediate safety instruction:** Do not click Save, Sync Novel, or Close & Sync Novel while the original package is loaded. Use **Open Novel** to select the separate rebuild package `/home/tony/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk`. After loading, verify the top-right path label explicitly shows that full rebuild path before editing anything.
- **Active StoryBuilder branch:** `fix/build-contract-from-idea-test`. Local checkout `~/Documents/StoryBuilder`; Tony pulled handoff commit `155cb0c` successfully before launching the app. The code-under-test commit is `0d8a796c4c447f79c0044f351d809b041cdf6164`; latest CI for that code passed.
- **Local tests (confirmed by Tony 2026-10-10):** `python3 -m unittest discover -s tests -v` passed all 14 tests. Use `python3`, not `python`, on Linux Mint.
- **Inspected package paths (read-only):**
  - Original `/home/tony/Documents/MyNovel`, title `Taken at Dusk`, Git branch `chapter1-clean-reset`, current state Ch2 Scene 2. Keep untouched.
  - Pre-migration `/home/tony/Documents/MyNovel_before_migration`, no Git repo detected, current state Ch1 Scene 5.
  - Intended separate rebuild package `/home/tony/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk`, title `Taken at Dusk`, no Git repo detected. Its state currently says Ch2 Scene 1 but its situation incorrectly describes Maya's arrival before saying Tiffany is gone. Correct that only after its full path is visibly confirmed in StoryBuilder.
  - `/home/tony/Documents/StoryBuilder/Test_Novel` is a test package titled `The Last Signal`; do not use it.
- **Correct narrative continuity:** Chapter 1 Section 6 already has Maya arrive at Tony's bedroom, be caught and settled against his chest, be comforted, then tell Tony “Tiffany is gone.” Chapter 2 must not repeat the arrival or revelation.
- **Chapter 2 fresh boundaries:** Scene 1 continues with Maya already against Tony's chest after saying Tiffany is gone. Tony comforts her, notices the slap mark, asks gently if she is hurt, and gives her time to admit the kidnapper hit her. End when she manages to say she was hit. Scene 2 continues with her full account of Tiffany's abduction. Exactly one kidnapper. Do not bring the later bath, Beth call, clothes, or tea into these scenes without author direction.
- **Implemented safeguards:** current situation outranks stale physical state; generated prose is tied to its originating chapter/scene/start-state; unfinished Writer text saves to its origin-scene draft before navigation/package changes/closing; navigation blocks during generation and before accepted-scene state is applied; Build Contract from Scene Idea should persist the contract and automatically refresh Writer direction while the scene remains active.
- **What has not happened:** The app is running, but the correct rebuild package has not yet been opened. No prose has been generated. No package data has been edited or saved, and the original package has not been written to or synced by this session. Live model smoke test with `Gemma-4-E4B_q4_0-it.gguf` remains pending.
- **Next step:** Click **Open Novel**, select the folder `/home/tony/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk`, and verify the path label before changing state. Continue one UI action at a time, and never save/sync while the original is open.
- **Handoff rule:** Record every meaningful code/workflow change, test result, branch action, package-path finding, decision, or story-canon/scene-plan correction here on the active StoryBuilder branch. Keep current-session details current before pausing or ending; never present guesses as confirmed facts.

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
