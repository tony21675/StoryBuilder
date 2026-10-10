# StoryBuilder Chat Handoff

> Purpose: Paste this document into a new ChatGPT conversation to resume work without spending time rebuilding context. Update this file after meaningful project or story changes. Treat the current-session section as the first thing to refresh.

## Current Session: 2026-10-10

- **Status: Correct rebuild package is open; its stale scene-start description has been corrected by Tony.** Confirmed app path: `/home/tony/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk`. Tony replaced the old `current_situation` with the corrected opening and replied “Done” after being instructed to save it. No contract or prose has been generated yet.
- **Important diagnosis:** The wrong opening was already stored in the rebuild package before the current session changed it. It said Maya had just burst into Tony's bedroom and had not told Tony Tiffany was gone. So this specific error did not come from a new prose generation in this session. The generator prompt already says `current_situation` outranks stale physical-state data, but there is currently no automated check that verifies `current_situation` against the end of the previous manuscript section. It can obey an inaccurate snapshot perfectly and still start in the wrong place. The precise historical reason the rebuild copy acquired this stale snapshot has not been established.
- **Corrected Scene 1 opening now intended (Tony reports he changed it and saved):** “Maya is in Tony's bedroom, curled against Tony's chest as he holds and comforts her. She has already told him that Tiffany is gone. She is deeply shaken and struggling to explain what happened. Tony has not yet heard any details of the abduction. The slap mark from the kidnapper's blow is present on Maya's cheek, but Tony has not yet noticed it. Maya has not yet admitted to Tony that she was hit.”
- **Known gap for durable fix:** Existing tests confirm that current_situation takes priority over stale physical-state data, but they do not test current_situation against the previous scene's saved ending. To prevent recurrence across future scenes, consider a generic pre-generation continuity preflight that compares the proposed scene opening with the latest saved scene/previous ending and warns about contradictions before contract generation. Do not hard-code Maya/Tony/Tiffany specifics. The safety feature should avoid auto-overwriting an author's intended opening; present the conflict for author confirmation or correction.
- **Safety and paths:** Original `/home/tony/Documents/MyNovel` is titled `Taken at Dusk`, Git branch `chapter1-clean-reset`, state Ch2 Scene 2, and must stay untouched. Pre-migration `/home/tony/Documents/MyNovel_before_migration` was seen at Ch1 Scene 5. `/home/tony/Documents/StoryBuilder/Test_Novel` is the unrelated test package titled `The Last Signal`.
- **Story continuity:** Chapter 1 Section 6 already has Maya reach Tony's bedroom, be caught and settled against Tony's chest, be comforted, and tell him “Tiffany is gone.” Chapter 2 must not repeat the arrival or that revelation.
- **Chapter 2 boundaries:** Scene 1 continues with Maya already against Tony's chest after saying Tiffany is gone. Tony comforts her, notices the slap mark, gently asks whether she is hurt, and gives her room to admit the kidnapper hit her. End when she manages to say she was hit. Scene 2 continues from that admission as Maya tells Tony what happened to Tiffany; end after Tony has the full account. Exactly one kidnapper. Keep the later bath, Beth call, clothes, and tea out of these scenes unless Tony directs otherwise.
- **Active StoryBuilder branch:** `fix/build-contract-from-idea-test`. Local checkout `~/Documents/StoryBuilder`. Tony pulled handoff commit `155cb0c` before launch; new handoff-only session updates were committed separately. Tony's local `python3 -m unittest discover -s tests -v` passed all 14 tests. Use `python3`, not `python`, on Linux Mint. Code-under-test commit `0d8a796c4c447f79c0044f351d809b041cdf6164` had passing CI.
- **Implemented safeguards:** current situation outranks stale physical state; generated prose is tied to origin chapter/scene/start-state; unfinished Writer text is saved to its origin-scene draft; navigation blocks during generation and before accepted-scene state is applied; Build Contract from Scene Idea should persist the contract and automatically refresh Writer direction while scene remains active.
- **Contract test result (reported by Tony 2026-10-10):** Tony clicked Build Contract from Scene Idea using the intended idea: “Continue from the current situation. Tony patiently comforts Maya as she struggles to speak through her distress. He notices the slap mark on her cheek and gently asks if she is hurt. Maya struggles to admit that the kidnapper hit her. Tony gives her time and comforts her until she manages to tell him she was hit. End the scene there, with Maya still deeply shaken and not yet ready to explain the full abduction.” The generated contract's `begin` section still repeated the stale opening: “Maya has just burst into Tony's bedroom ... Maya has not yet told Tony that Tiffany is gone, and Tony does not yet know what happened.” Its `middle`/`end`/`beats` generally aligned with the intended comfort/admission boundary, but the stale opening is a hard continuity failure. Tony had previously reported updating and saving Current State in the rebuild copy. Do not generate writer prose yet. Next step: inspect the Current State tab again and verify the text currently visible, then investigate why the contract builder received/stored the stale opening. Distinguish the on-screen edit from the persisted package state; avoid touching the original MyNovel. The real-model workflow test is in progress and is not passing yet.
- **Handoff rule:** Record meaningful code/workflow changes, test results, branch actions, package paths, decisions, and story-canon/scene-plan corrections here. Keep current-session details current before pausing or ending. Never present guesses as confirmed facts.

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
