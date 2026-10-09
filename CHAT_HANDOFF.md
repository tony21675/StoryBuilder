# StoryBuilder Chat Handoff

> Purpose: Paste this document into a new ChatGPT conversation to resume work without spending time rebuilding context. Update this file after meaningful project or story changes. Treat the current-session section as the first thing to refresh.

## Current Session: 2026-10-08

- We are testing the new **author-controlled scene contract** in StoryBuilder.
- Current model: **Gemma 4 E4B instruction-tuned**, file `Gemma-4-E4B_q4_0-it.gguf`.
- Current novel branch: `chapter1-clean-reset` in `tony21675/MyNovel`.
- Current StoryBuilder test branch: `fix/build-contract-from-idea-test` in `tony21675/StoryBuilder`.
- We are testing **Chapter 2, Scene 2**. It has not been written yet.
- Scene 1 ends with Tony comforting Maya after she witnessed Tiffany's abduction. Maya has finally told him Tiffany is gone.
- Intended development in Scene 2: Tony continues comforting Maya as she struggles to explain what happened. He notices the red slap mark on her cheek and gently asks whether she is hurt. Maya struggles to tell him that the kidnapper hit her.
- **There was only ONE kidnapper in the incident Maya witnessed.**
- The red mark belongs in Scene 2, not Scene 1.
- The immediate goal is to test whether the contract can guide the model with minimal author input. Do not write the scene yourself or add more contract instructions unless the user asks or the generated output shows a specific reason.
- On 2026-10-08, updated `builder/scene_contract.py` so contract generation preserves explicitly requested emotional intensity rather than flattening it, while keeping the contract minimal. Updated the scene-writing boundary in `storybuilder.py` to honor intense distress through persistent physical reactions, broken/failed speech, and difficulty settling, while allowing comfort to support the character without instantly removing distress.
- The first local test of Chapter 2, Scene 2 produced a short passage in which Tony comforts Maya, notices the red slap mark on her cheek, and asks whether she is hurt. The prose and pacing were good, but the scene direction had not given the comforting moment much room to develop.
- On 2026-10-08, added a **generic reusable writing principle** to the contract builder and writer prompts: naturally draw on established relationship history, familiar caregiving habits, routines, small shared memories, and personal details when they deepen a moment. These should arise organically, not as forced callbacks or mandatory checklist items, and must not contradict canon or invent consequential backstory. This is intended to work across stories.
- After reviewing the generated passage and contract, refined the generic prompts to preserve the full emotional progression the author describes. Both contract construction and prose generation now encourage initial reactions, hesitation, pauses, failed attempts to speak, and changing emotions to have room to unfold before advancing to the next event. The goal is to avoid compressing a central emotional moment into a quick exchange while keeping the direction concise and free of micro-beat checklists. Familiar, welcome comfort remains allowed when it fits established trust and history, without over-explaining ordinary affection. These generic changes are committed on `fix/build-contract-from-idea-test` in `storybuilder.py` and `builder/scene_contract.py`; they have not yet been pulled locally or tested.
- After reviewing the latest generated contract, identified two gaps: the explicitly requested comforting action was absent from Required beats, and the End did not define a meaningful emotional stopping point. Tony clarified the scene boundary: Scene 2 ends after Maya manages to tell Tony that the kidnapper hit her, while she is still shaken and on the bed with Tony; she must not tell him the full abduction story yet. Scene 3 covers her full account, with Tony patiently helping her get through it, and ends with Maya still on the bed with Tony.
- On 2026-10-09, updated `builder/scene_contract.py` with two generic rules: preserve explicit boundaries between adjacent scenes when one scene contains a limited disclosure and a later scene contains the fuller account; and keep an explicitly requested important action visible in the direction and, when omission would materially change the scene, as a concise required beat. Commit `49a0c3b53d52b0a8d6a358a893e465a353c9cfbb` on `fix/build-contract-from-idea-test`. This is a GitHub change only and has not yet been pulled locally or tested.
- Next step: Tony pulls the branch, restarts StoryBuilder, and regenerates the Scene 2 contract. Inspect Middle, End, Required beats, and Required sequence before applying it. Scene 2 must stop after Maya tells Tony she was hit, without recounting the whole abduction. Then test the prose. After Scene 2 is accepted, build Scene 3 so Maya tells Tony the complete story while remaining on the bed with him at the end. Do not plan Scene 4 until Tony asks.
- If a generation is currently running, do not tell the user to restart the app or switch branches. Inspect the output once the user provides it.

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
