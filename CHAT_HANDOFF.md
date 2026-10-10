# StoryBuilder Chat Handoff

> Purpose: Paste this document into a new ChatGPT conversation to resume work without spending time rebuilding context. Update this file after meaningful project or story changes. Treat the current-session section as the first thing to refresh.

## Current Session: 2026-10-10

- **Current priority: stop the confusing scene-by-scene patching and restart Chapter 2 cleanly in the separate StoryBuilder Save As copy.** Tony explicitly decided: delete Chapter 2 in that separate working copy and rebuild it. Do not delete or overwrite Chapter 2 in the original MyNovel repo/package. The original is the safety net.
- Repo branches remain: StoryBuilder test branch `fix/build-contract-from-idea-test` in `tony21675/StoryBuilder`; novel branch `chapter1-clean-reset` in `tony21675/MyNovel`.
- A separate copy was created with StoryBuilder's Save As, but Tony no longer remembers the exact folder/path. Do not ask him to recall it. First help him identify which StoryBuilder window/package is the copy, using safe, simple checks.
- No Chapter 2 deletion has been performed yet. Do not imply that it has. Next chat should calmly guide Tony to delete/rebuild Chapter 2 **only in the separate copy**, after confirming the app is indeed the copy. Preserve the original MyNovel and its saved files.
- The original MyNovel repo's known state was Chapter 2, Scene 2 (`current_state.json` chapter 2, scene 2, status `in_progress`). Scene 2 prose was missing / not safely recovered. Previous searches found no saved prose for Chapter 2 Scene 1; the only known after-state file was `Chapter_02_Section_02_after_state.json`.
- In the separate Save As copy, we manually changed the Current State editor to Chapter 2, Scene 1, location `Tony's bedroom, at Tony and Tiffany's home`, time `late afternoon`, cast Maya and Tony, status `in_progress`, preserving the existing continuity notes. We applied State Edits and Current Situation. Current Situation was set to the true starting point: Maya has just burst into Tony's bedroom after witnessing Tiffany's abduction; she has not yet told Tony Tiffany is gone; Tony does not yet know what happened.
- In that same copy, the Scene Idea was replaced with the correct Scene 1 goal, Build Contract from Scene Idea was run, Beginning/End were edited, and Validate Contract returned **pass**. Apply Contract and Build Writer Direction were then run. This was a repair attempt, not a confirmed successful final setup.
- The latest Writer Direction still has a contradiction: its Current state says Maya has just arrived and has not told Tony Tiffany is gone; its Physical continuity says Maya is already lying against Tony's chest and Tony is already holding her; its required beats say Tony must catch and settle her; the End says Maya tells him Tiffany is gone. This inconsistency is why Tony became overwhelmed. **Do not continue patching one field at a time.** Restart Chapter 2 in the separate copy as Tony requested.
- Intended rebuilt Chapter 2 boundaries:
  - Scene 1: Maya bursts into Tony's bedroom after witnessing Tiffany's abduction; Tony catches her and settles her against his chest; she cries and struggles to speak; scene ends when she tells him, “Tiffany is gone.”
  - Scene 2: Tony continues comforting her; notices the slap mark; Maya struggles to admit the kidnapper hit her; Tony uses their familiar childhood comfort gesture, rubbing her back and butt, in a nonsexual, fatherly way. Scene ends with Maya admitting she was hit but still too shaken to give the full account.
  - Scene 3: Maya tells Tony exactly what happened to Tiffany; scene ends with Maya still on the bed with Tony after he has the full story.
- The one-kidnapper fact remains confirmed. Do not introduce a second kidnapper.
- Do not ask Tony to decide again whether to restart Chapter 2; he has already decided. The job is to help execute that decision safely in the separate copy, with one short step at a time and no extra field patching unless needed after the clean rebuild.
- StoryBuilder code branch changes recorded below remain committed remotely but had not been locally tested in the prior handoff. Do not claim those code changes fixed this contract inconsistency unless tested.

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
