# StoryBuilder Chat Handoff

> Purpose: Paste this document into a new ChatGPT conversation to resume work without spending time rebuilding context. Update this file after meaningful project or story changes. Treat the current-session section as the first thing to refresh.

## Current Session: 2026-10-10

- **Status: 16 local unit tests passed after pulling the permanent save fix.** Tony pulled the latest code into `~/Documents/StoryBuilder` on his Surface Laptop 3, then ran `python3 -m unittest discover -s tests -v`. Output: 16 tests, `OK`, including:
  - `test_normal_save_applies_and_persists_current_situation`
  - `test_save_is_blocked_if_current_situation_cannot_be_applied_during_generation`
  - the original 14 tests.
- **Permanent fix and passing CI:** on active branch `fix/build-contract-from-idea-test`, commit `dd0915a69574acc1a01cf0386d9f23c11f5a7f34` routes normal full-form saves through guarded `_apply_situation_edit()`; the subsequent test commit `195a3bc0e3c4647ca24edd3db55bff3db7ba489c` adds two regression tests. GitHub push/PR workflow run `38084870558` passed for the regression commit, and the subsequent handoff update push run `38084914881` passed. No unverified test claims.
- **Live test failure/root cause:** the earlier running app was on the old code. The Current Situation text box has an explicit Apply Situation button, but previous `_apply_all_edits()` skipped `_apply_situation_edit()`; normal Save did not transfer changed textbox text into `package.current_state["current_situation"]`. Contract generation then correctly consumed stale internal state and repeated the obsolete start. Tony followed the assistant's incomplete Save instruction; this was a program wiring issue, not user error or a confirmed model mistake.
- **Application state:** Tony closed the old StoryBuilder process with toolbar **Close** (not Close & Sync), pulled the latest handoff, and relaunched the updated app via `python3 storybuilder.py`. He then re-entered the corrected Scene 1 situation in Current State and clicked ordinary **Save**, specifically without clicking Apply Situation. **The on-disk persistence check is still pending**, so don't claim the fix is proven until read-only inspection confirms `current_state.json` contains the corrected value. Reconfirm app path label `/home/tony/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk` before later editing if not visibly clear. Original `/home/tony/Documents/MyNovel` remains protected. No rebuilt Scene 1 prose has been generated.
- **Next steps after restart:** (1) run `python3 storybuilder.py` from `~/Documents/StoryBuilder`; (2) use **Open Novel** and verify top-right shows `/home/tony/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk`; (3) re-enter the corrected situation below; (4) click ordinary **Save** only; (5) verify the in-memory/persisted value before rebuilding the contract; (6) click Build Contract from Scene Idea and inspect its beginning; only generate prose after that check passes. Keep each action one at a time. Do not ask Tony to use Apply Situation as the permanent workaround: the new code makes normal Save apply it.
- **Correct Current Situation text to re-enter for Ch2 Scene 1:** “Maya is in Tony's bedroom, curled against Tony's chest as he holds and comforts her. She has already told him that Tiffany is gone. She is deeply shaken and struggling to explain what happened. Tony has not yet heard any details of the abduction. The slap mark from the kidnapper's blow is present on Maya's cheek, but Tony has not yet noticed it. Maya has not yet admitted to Tony that she was hit.”
- **Correct narrative continuity:** Chapter 1 Section 6 already includes Maya reaching Tony's bedroom, Tony catching and settling her against his chest, comforting her, and Maya telling him “Tiffany is gone.” Chapter 2 starts immediately after that. Scene 1: Tony continues comfort, notices the slap mark, gently asks about it, and Maya eventually admits the kidnapper hit her. End on that admission, before full details. Scene 2: Maya recounts the abduction and ends once Tony knows the full account. Exactly one kidnapper. Later bath/Beth call/clothes/tea beats are out of these scenes unless Tony directs otherwise.
- **Package paths:** Original `/home/tony/Documents/MyNovel`, title Taken at Dusk, Git branch `chapter1-clean-reset`, current state Ch2 Scene 2, keep untouched. Intended rebuild package `/home/tony/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk`, no Git repo detected. Pre-migration copy `/home/tony/Documents/MyNovel_before_migration` at Ch1 Scene 5. StoryBuilder test package `/home/tony/Documents/StoryBuilder/Test_Novel` is a different novel titled The Last Signal.
- **Other workflow safeguards on this branch:** `current_situation` outranks stale physical-state fields in contract-builder prompt; generated prose is tied to its origin chapter/scene/start state; unfinished Writer text is saved to source-scene draft before navigation/package change/closing; scene switching is blocked during generation or before accepted-scene state is applied; successful Scene Idea contract build auto-refreshes Writer direction when same scene remains active.
- **Model:** `Gemma-4-E4B_q4_0-it.gguf`. Live contract/workflow smoke test still pending after restart. Do not state that live model test passed until the corrected starting state survives normal Save and contract generation uses it.
- **Environment:** On this Linux Mint laptop the Python command is `python3`; `python` is not installed.
- **Handoff rule:** Keep this document updated with each meaningful code/workflow change, test outcome, live observation, package path discovery, and story correction. Distinguish confirmed results from next steps and hypotheses; never make Tony repeat existing context.

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
