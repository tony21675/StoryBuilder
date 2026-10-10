# StoryBuilder Chat Handoff

> Purpose: Paste this document into a new ChatGPT conversation to resume work without spending time rebuilding context. Update this file after meaningful project or story changes. Treat the current-session section as the first thing to refresh.

## Current Session: 2026-10-10

- **Status: Scene Contract exposed an exact Current Situation apply/save bug. Do not generate prose yet.** StoryBuilder has the separate rebuild package `/home/tony/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk` open. The original `/home/tony/Documents/MyNovel` must remain untouched.
- **Observed test result:** Tony entered the intended Scene 1 idea and clicked Build Contract from Scene Idea. The generated contract still began with the old opening: Maya has just burst into Tony's bedroom and has not told Tony Tiffany is gone. Its middle/end/beats broadly matched the idea, but the beginning contradicted the Chapter 1 ending. Tony had followed the prior instruction to edit the Current Situation field and click Save.
- **Root cause verified in the actual code at branch `fix/build-contract-from-idea-test`:** the Current State UI's Current Situation is a distinct `self.situation_text` widget with its own **Apply Situation** button. `_apply_all_edits()`, called by the Save handler, invokes `_apply_state_edits()` but does *not* invoke `_apply_situation_edit()`. Consequently, typing corrected text then pressing Save alone does not copy that text into `package.current_state["current_situation"]`; saving the package persists the old internal value. The contract builder then receives `self.package.current_state`, so it correctly generates from the stale string that it still has. This is a confirmed UI/save workflow bug, not a Gemma generation failure. Assistant gave the incomplete instruction to click Save without first clicking Apply Situation; Tony followed that instruction correctly. Apologize and own this.
- **Immediate workaround to try now in the open app:** open the Current State tab, keep the corrected situation already entered in the text box, click **Apply Situation**, then click **Save**. Confirm if the visible path label remains the rebuild path and the status indicates saved. Then rebuild the contract and inspect the beginning again. Do not generate prose until its beginning matches Chapter 1's ending and Writer direction status is confirmed.
- **Permanent code fix still needed:** make the general Save path persist the Current Situation widget safely, without interfering with the safeguards in `_apply_situation_edit()` that protect active generation, accepted scenes, and unfinished drafts. Add a unit test proving a general save/apply operation commits the edited situation into `package.current_state`. Prefer a dedicated helper / carefully guarded wiring; do not merely bypass the safety checks. Implement the code fix on `fix/build-contract-from-idea-test`, add or extend tests, run `python3 -m unittest discover -s tests -v` and confirm CI, update this handoff, then guide Tony to pull/restart when safe.
- **Correct intended Scene 1 start:** “Maya is in Tony's bedroom, curled against Tony's chest as he holds and comforts her. She has already told him that Tiffany is gone. She is deeply shaken and struggling to explain what happened. Tony has not yet heard any details of the abduction. The slap mark from the kidnapper's blow is present on Maya's cheek, but Tony has not yet noticed it. Maya has not yet admitted to Tony that she was hit.”
- **Correct scene boundaries:** Scene 1 continues with Maya already against Tony's chest after saying Tiffany is gone. Tony comforts her, notices the slap mark, gently asks if hurt, and gives her room to admit the kidnapper hit her. End after she manages to say she was hit. Scene 2 continues from that admission as she tells Tony what happened to Tiffany, ending after he hears the full account. Exactly one kidnapper; do not move the later bath, Beth call, clothes, or tea into these scenes without direction.
- **Confirmed continuity:** Chapter 1 Section 6 already has Maya reach Tony's bedroom, Tony catch and settle her against his chest, comfort her, and Maya tell him “Tiffany is gone.” Do not repeat arrival/revelation in Chapter 2.
- **Paths:** Original `/home/tony/Documents/MyNovel` title Taken at Dusk, Git branch `chapter1-clean-reset`, current state Ch2 Scene 2, protect it. Intended rebuild package `/home/tony/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk`, no Git repo detected. Pre-migration copy `/home/tony/Documents/MyNovel_before_migration` at Ch1 Scene 5; StoryBuilder test package `/home/tony/Documents/StoryBuilder/Test_Novel` is a different novel titled The Last Signal.
- **Branch/tests:** active StoryBuilder branch `fix/build-contract-from-idea-test`; local checkout `~/Documents/StoryBuilder`. Tony's local `python3 -m unittest discover -s tests -v` passed all 14 tests before this live app test. Use `python3` on Linux Mint. Code under test is `0d8a796c4c447f79c0044f351d809b041cdf6164`, CI passed at that code commit. Later handoff-only commits record discoveries.
- **Live model test:** model is `Gemma-4-E4B_q4_0-it.gguf`. This contract test is not yet passing due to the confirmed state-application bug. No prose has been generated for this rebuilt Scene 1.
- **Handoff rule:** Keep this file current with all meaningful tests, causes, decisions, fixes, and next steps. Distinguish observed results from hypotheses. Never make Tony repeat established context.

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
