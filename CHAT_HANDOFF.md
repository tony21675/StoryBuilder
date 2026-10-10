# StoryBuilder Chat Handoff

> Purpose: Paste this document into a new ChatGPT conversation to resume work without spending time rebuilding context. Update this file after meaningful project or story changes. Treat the current-session section as the first thing to refresh.

## Current Session: 2026-10-10

- **Status: Root cause has been fixed in StoryBuilder source and CI passes.** Tony's app currently running on the laptop is still the older imported Python process. The new code must be pulled and the app restarted before testing the fix live. Active novel path in the app is the separate rebuild package `/home/tony/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk`; leave original `/home/tony/Documents/MyNovel` untouched.
- **Live failure observed:** Tony entered the corrected Scene 1 starting situation and clicked Save, then built a contract. The contract's `begin` remained the stale text: Maya has just burst into Tony's bedroom and has not told Tony Tiffany is gone. Middle/end/beats generally followed the idea, but beginning contradicted Chapter 1.
- **Confirmed exact root cause:** Current State's Current Situation is a separate `self.situation_text` widget with its own Apply Situation button. Old `_apply_all_edits()` did not call `_apply_situation_edit()`, so Save persisted the old in-memory `current_state["current_situation"]` even when the text box had been edited. Contract generation reads the in-memory state, hence it used stale text. Tony followed our earlier instruction correctly; assistant had mistakenly told him Save alone was sufficient.
- **Permanent code fix committed to this branch:** `storybuilder.py` commit `dd0915a69574acc1a01cf0386d9f23c11f5a7f34` updates `_apply_all_edits()` to pass Current Situation through its existing safety-guarded apply handler before the other editor fields. The handler now returns success/failure. Normal Save, Save As, Sync Novel, Validate, Guided Setup, and natural-language command operations stop if Current Situation could not be safely applied, rather than silently continuing with stale state. This preserves guards for active writing/contract generation and an accepted scene with an unapplied state update.
- **Regression tests added:** `tests/test_scene_workflow_safety.py` commit `195a3bc0e3c4647ca24edd3db55bff3db7ba489c` adds tests that normal Save persists the edited Current Situation and that Save is blocked if the state edit is refused during generation. GitHub Actions workflow run `38084870558` for commit `195a3bc0e3c4647ca24edd3db55bff3db7ba489c` passed: Python compile plus unit test job. There are now 16 total unit tests expected (the previous 14 plus these 2).
- **Immediate next steps:** Do not ask Tony to rely on Apply Situation as a permanent workaround. The Current Situation text was corrected in the older app's widget but was not copied into the package state, and will need to be re-entered after the current app is closed/restarted. There is no generated prose to preserve. Pull the new branch code locally; close the currently running old Python app only after noting it still runs old code; reopen the app with the new code and open only `/home/tony/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk`. Re-enter the corrected situation, click the normal **Save** button only, then confirm it persists (can close/reopen or inspect state JSON read-only). Rebuild the contract and verify its opening begins with Maya already curled against Tony's chest after telling him Tiffany is gone. Do not generate prose until confirmed. Keep original MyNovel untouched.
- **Correct Current Situation text to re-enter for Scene 1:** “Maya is in Tony's bedroom, curled against Tony's chest as he holds and comforts her. She has already told him that Tiffany is gone. She is deeply shaken and struggling to explain what happened. Tony has not yet heard any details of the abduction. The slap mark from the kidnapper's blow is present on Maya's cheek, but Tony has not yet noticed it. Maya has not yet admitted to Tony that she was hit.”
- **Story continuity and boundaries:** Chapter 1 Section 6 already has Maya arrive at Tony's bedroom, Tony catch and settle her against his chest, comfort her, and Maya tell him “Tiffany is gone.” Chapter 2 Scene 1 continues from that exact moment. Tony comforts her, notices the cheek mark during the scene, gently asks if she is hurt, and gives her room to admit she was hit. End when she admits that. Scene 2 carries her account of the abduction and ends after Tony has the full account. Exactly one kidnapper. Keep later bath, Beth call, clothes, tea out unless Tony directs otherwise.
- **Package paths:** Original `/home/tony/Documents/MyNovel`, title Taken at Dusk, branch `chapter1-clean-reset`, state Ch2 Scene 2. Protect it. Rebuild copy `/home/tony/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk`, no Git repo detected. Pre-migration `/home/tony/Documents/MyNovel_before_migration` at Ch1 Scene 5; test package `/home/tony/Documents/StoryBuilder/Test_Novel` is a different novel titled The Last Signal.
- **Branch/tests context:** active StoryBuilder branch `fix/build-contract-from-idea-test`, local checkout `~/Documents/StoryBuilder`. Tony's local test before the live workflow returned 14 tests OK. Use `python3`, not `python`, on Linux Mint. After the new regression commits, GitHub CI passed at the 16-test state. Run local tests again after pulling.
- **Other workflow fixes already on the branch:** Current situation outranks stale physical-state fields in contract-builder prompt; generated prose is bound to origin chapter/scene/start state; unfinished Writer text is saved to its source-scene draft before navigation/package changes/closing; navigation is blocked during generation and before accepted-scene state is applied; generated Scene Idea contract auto-refreshes Writer direction when the same scene remains active.
- **Handoff rule:** Record every meaningful code/workflow change, live observation, test result, package-path finding, decision, and story continuity correction here. Distinguish confirmed outcomes from proposals. Before a pause or handoff, keep this Current Session section current.

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
