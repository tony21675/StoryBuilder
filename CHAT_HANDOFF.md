# StoryBuilder Chat Handoff

> Purpose: Paste this document into a new ChatGPT conversation to resume work without spending time rebuilding context. Update this file after meaningful project or story changes. Treat the current-session section as the first thing to refresh.

## Current Session: 2026-10-10

- **Current status:** Tony pulled the one-step prompt experiment (`d92c572` plus test `0903bf8`) and reports the 18-test suite output pasted after running `python3 -m unittest discover -s tests -v`, which the workflow treats as passing based on his confirmation. The change is limited: writer rule 6 encourages a clear, concrete opening orientation to existing physical positions/posture/contact; rule 9 encourages trusting one effective action/image rather than stacking another metaphor that restates the same emotion. The updated prompt has passed GitHub CI. Next is to restart the app so the model uses the new prompt, then run one fresh live Scene 1 generation and review it before any more changes.
- **Current app state:** Latest live Scene 1 result from before the one-step prompt experiment was not accepted by the writer; inspect whether it remains in the app. Source/test updates are pulled locally. If StoryBuilder remains open, its in-memory prompt is the older version, so close it with **Close** (not Close & Sync) before relaunching. Rebuild package `/home/tony/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk`; never modify original `/home/tony/Documents/MyNovel`. Do not hand-edit prose or suppress Tony/Maya's established comfort gesture.
- **Prompt/validator changes committed on active branch fix/build-contract-from-idea-test:**
  - **CI email explanation:** GitHub Actions run `38089394507` (run 61 on the PR) failed only in `test_semantic_validator_checks_opening_physical_continuity`: the test expected the phrase `without a transition that explains the change`, while the validator prompt actually said `does not show a transition that explains the change`. Compilation and the other 17 tests passed. Commit `ffe602c9226d95668864b8cec1ac7959f4ca3e2e` corrected the assertion wording; its checks and all reviewed checks after it passed, including run `38098413027` for the new style-validator regression test. So the confirmed email came from a test expectation mismatch, not a runtime/application failure. Later changes still need local tests after pull.
  - Commit ede549e320d8119b2fb632dfb3432816654c0537 clarifies that stored physical continuity stays authoritative for details not contradicted by current_situation or explicit scene actions. A silent field does not cancel the prior position/posture/contact/movement.
  - Commit 433b091e312b669fa291808ea3b2f2379cae1af1 extends semantic scene validation to compare the prose opening with current state, flagging a different starting position/posture when no scene transition explains it. Since validation failure feeds the writer's retry loop, the model should correct such continuity errors automatically rather than requiring Tony to rewrite the scene.
  - Commit 8cc762d1ed85ac67af084d4e60ffb513864b27d9 adds two regression tests for physical-continuity and relationship-consistent prose prompt rules, and for the semantic validator's opening-position check.
  - Commit ffe602c9226d95668864b8cec1ac7959f4ca3e2e corrects a wording mismatch in the new test. GitHub CI push and PR runs 38089412215 and 38089408608 passed after that correction. The local suite now has 18 tests (previous 16 plus two new tests), and Tony confirmed all 18 pass on his machine.
- **Latest writing-prompt adjustment (commits `d92c57296368ba1ac5610938376b81d9d7c33ca9` and `0903bf8ebc1d07b62bd5455912c977efe74c5bf0`):** This is the single agreed follow-up experiment, not a broad rewrite: the writer prompt now asks for a concrete, natural orientation to key positions/posture/contact at the opening, without vague staging or repeated setup; it also asks the writer to trust one effective action/image instead of layering another metaphor that restates the emotion. No dialogue quotas, detailed beat rules, or validator changes were added. Tony/Maya's familiar fatherly comfort gesture is not to be suppressed or recast. GitHub CI passed for both commits (runs `38113556321` / 99 and `38113567291` / 101); local tests and a live generation using this exact prompt remain pending.
- **Earlier confirmed save fix:** Normal Save now routes Current Situation through the guarded apply handler. Tony already pulled and ran 16 tests successfully for that fix. Live verified: after entering the corrected situation and clicking ordinary Save (not Apply Situation), a read-only inspection confirmed /home/tony/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk/current_state.json contained the corrected text and Chapter 2 Scene 1.
- **Live scene setup confirmed:** intended package /home/tony/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk was opened and shown in the path label. Scene Idea contract correctly begins with Maya already curled against Tony's chest, after telling Tony Tiffany is gone; includes noticing the slap mark, asking if she is hurt, and the familiar childhood comfort gesture; ends at her admission that the kidnapper hit her. Automatic Writer direction refresh was confirmed, and direction reflected the contract.
- **Correct Scene 1 beginning:** Maya is in Tony's bedroom, curled against Tony's chest as he holds and comforts her. She has already told him that Tiffany is gone. She is deeply shaken and struggling to explain what happened. Tony has not yet heard any details of the abduction. The slap mark from the kidnapper's blow is present on Maya's cheek, but Tony has not yet noticed it. Maya has not yet admitted to Tony that she was hit.
- **Scene distinction:** Scene 1 includes the familiar fatherly childhood comfort gesture while Maya is overwhelmed and struggles to admit she was hit. Scene 2 begins after that admission; Maya is starting to calm down, so Tony only rubs her back while she explains the abduction. Scene 1 ends on the admission, before full details. Scene 2 ends once Tony has the full account. Exactly one kidnapper. Do not move later bath, Beth call, clothes, or tea into these scenes unless Tony directs otherwise.
- **Correct continuity:** Chapter 1 Section 6 already has Maya reach Tony's bedroom, Tony catch and settle her against his chest, comfort her, and Maya say “Tiffany is gone.” Chapter 2 must not replay her arrival or revelation. Tony's physical continuity for the scene opening says he is sitting upright against the headboard and holding Maya; preserve this unless the scene explicitly moves him.
- **Protect original data:** original /home/tony/Documents/MyNovel is on Git branch chapter1-clean-reset, current state Chapter 2 Scene 2; never modify it during the rebuild. The rebuild package has no Git repository, so keep using it as a separate copy. /home/tony/Documents/MyNovel_before_migration is an old pre-migration package at Chapter 1 Scene 5. /home/tony/Documents/StoryBuilder/Test_Novel is the unrelated test novel The Last Signal.
- **Next step:** Close the old StoryBuilder app via **Close** (not Close & Sync), then relaunch with `cd ~/Documents/StoryBuilder && python3 storybuilder.py`. Open only `/home/tony/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk`, confirm the package path, run Validate / Apply Contract / Build Writer Direction, and generate Scene 1 once. Review clear opening positions and whether the prose avoids restating emotions with layered metaphors. The current reported local suite has 18 tests; use the exact output if it needs to be verified in a future chat. Do not implement another change until the result is reviewed and discussed.
- **Environment/model:** Linux Mint requires python3 (not python). Active local writer model is Gemma-4-E4B_q4_0-it.gguf. The live test for the latest prompt/validator improvements is still pending.
- **Handoff rule:** Record meaningful code/workflow changes, test outcomes, package path findings, and story decisions here on the active StoryBuilder branch. Keep Current Session current before pausing, distinguish confirmed facts from next steps, and never make Tony repeat established context.

## Change Approval and Author Authority

- **Always discuss before changing or rejecting something.** Before implementing a code, prompt, validator, test, workflow, writing-style, story, character, or canon change, explain the problem you observed and the proposed adjustment. Wait for Tony's agreement before making the change. Do not interpret a general request to "fix it" as permission for an un discussed approach.
- This applies equally to adding restrictions, removing or denying a requested beat, gesture, or character behavior, changing a character's intent, or deciding that a passage is inappropriate. Do not silently sanitize, censor, forbid, or reinterpret content based on an assumption. If context or intent is unclear, ask Tony first.
- Tony is the authority on his story, character relationships, established history, and intended meaning. Respect previously agreed canon instead of re-litigating it or imposing an outside interpretation.
- Specifically, Tony and Maya's familiar comfort gesture is an established, non-sexual fatherly habit from Maya's childhood. Tony gently rubs her back and butt to help her settle when distressed. It is not groping, and neither character experiences it sexually. Do not characterize it as sexual, remove it, or add a rule to suppress it unless Tony himself asks to change that canon.
- Discuss the smallest useful fix before editing. Prefer diagnosis and a proposed option first, then wait for agreement; after agreement, implement only the agreed scope and test it.
- Do not ask Tony to hand-edit generated prose to compensate for a recurring application/prompt problem when a targeted underlying fix is appropriate. But also do not change the underlying behavior without discussing the proposed fix and receiving agreement.
- Existing explicit permissions remain in force: a clearly directed change can be carried out within that agreed scope; this rule does not require repeated confirmation of details already agreed.

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
- Author-directed scene workflow: a clear start, a few essential beats, and a clear end; the model invents natural connective tissue within those bounds.
- Prefer natural dialogue and concrete action when they fit; use selective description instead of repeating or stacking metaphors about the same emotion. No dialogue quotas or robotic checklists.
- Let characters have natural everyday conversation and small moments before major events.
- The model may invent small talk, shared memories, ordinary feelings, and natural interaction if it does not contradict canon, chronology, character knowledge, or explicit constraints.
- Avoid screenplay-like or meta narration.
- Do not foreshadow later danger unless an active plot module or the author's directions permit it.
- Keep Tony and Maya's interactions parental/non-romantic from Tony's side.
- Maya's familiar comfort gesture matters: Tony has gently rubbed her back and butt since she was little, and this touch helps her settle when distressed. It is a trusted fatherly habit with no sexual intent from either of them; do not remove it or label it sexual.

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
