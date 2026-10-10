# StoryBuilder Chat Handoff

> Purpose: Paste this document into a new ChatGPT conversation to resume work without spending time rebuilding context. Update this file after meaningful project or story changes. Treat the current-session section as the first thing to refresh.

## Current Session: 2026-10-10

- **Status: Ready to launch StoryBuilder, then open the separate rebuild package.** Tony has resumed after the recorded pause.
- **Active StoryBuilder branch:** `fix/build-contract-from-idea-test`. Local checkout: `~/Documents/StoryBuilder` on the Surface Laptop 3. Tony pulled commit `273ed8b` successfully, which updated `CHAT_HANDOFF.md` after the local test pass. The branch code commit under test is `0d8a796c4c447f79c0044f351d809b041cdf6164`; latest CI on that code commit passed.
- **Local tests (confirmed by Tony on 2026-10-10):** Tony ran `python3 -m unittest discover -s tests -v`. All 14 tests passed, ending with `Ran 14 tests ... OK`. Use `python3`, not `python`, on this Linux Mint machine.
- **Package paths inspected read-only on 2026-10-10:**
  - Original novel: `/home/tony/Documents/MyNovel`; title `Taken at Dusk`; Git root is itself; branch `chapter1-clean-reset`; current state Ch2 Scene 2, in progress. Do not modify it during this rebuild workflow.
  - Pre-migration copy: `/home/tony/Documents/MyNovel_before_migration`; no Git repo detected; state Ch1 Scene 5. Not the target copy for the current restart.
  - **Likely separate rebuild package:** `/home/tony/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk`; title `Taken at Dusk`; no Git repo detected. This has not been edited by this session. It currently says Ch2 Scene 1, but its `current_situation` is an older start that says Maya has just arrived at Tony's bedroom and has not yet told him Tiffany is gone. That is inconsistent with the actual Chapter 1 Section 6 ending and MUST be corrected in this separate package before generating Scene 1 prose.
  - `/home/tony/Documents/StoryBuilder/Test_Novel` is a StoryBuilder test package titled `The Last Signal`; do not use it for the real novel.
- **Correct story restart point:** Chapter 1 has six saved sections. Section 6 already has Maya reach Tony's bedroom, Tony catch and settle her against his chest, comfort her, and Maya say “Tiffany is gone.” Do not replay her arrival or repeat this revelation in Chapter 2.
- **Chapter 2 boundaries for the fresh rebuild:**
  - Scene 1: Continue with Maya already against Tony's chest after saying Tiffany is gone. Tony comforts her, notices the slap mark, gently asks if she is hurt, and patiently gives her room to admit the kidnapper hit her. End when she manages to say she was hit; she remains shaken and with Tony.
  - Scene 2: Continue from that admission. Maya tells Tony what happened to Tiffany. End once Tony has heard the full account. Exactly one kidnapper.
  - Keep later plans (bath, Beth calling, clothes, tea) out of these scenes unless Tony explicitly directs otherwise.
- **Safeguards implemented and tested:** Current situation takes precedence over stale physical-state details; generated prose is bound to its origin chapter/scene/start state; unfinished Writer prose saves to its originating scene draft before navigation/package changes/closing; navigation is blocked during generation and before an accepted scene's state update is applied; successful “Build Contract from Scene Idea” should save the contract and refresh Writer direction automatically if that scene remains active.
- **What has not happened:** StoryBuilder has not yet been launched during this resumed session, and the workflow has not been smoke-tested with Tony's local model `Gemma-4-E4B_q4_0-it.gguf`. No Chapter 2 files were created/deleted, and no write actions were made to either MyNovel path. The package inspection was read-only.
- **Next step:** Pull this handoff update locally and launch StoryBuilder directly with `python3 storybuilder.py` from `~/Documents/StoryBuilder`. Avoid `./start.sh` for now because it invokes the extra `sync.sh start` synchronization step. Then open only `/home/tony/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk`; do not open the original package. Inspect the current-state UI and update the rebuild copy's starting situation to exactly reflect the end of Chapter 1 before building Scene 1 contract or prose. Give Tony one terminal/UI action at a time.
- **Handoff rule:** Every meaningful code/workflow change, test result, branch action, package-path finding, decision, or story-canon/scene-plan correction must be recorded here on the active StoryBuilder branch. Keep current-session details current before pausing or ending a session; don't present guesses as confirmed facts.

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
