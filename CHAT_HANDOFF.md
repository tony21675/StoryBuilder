# StoryBuilder Chat Handoff

> Purpose: Paste this document into a new ChatGPT conversation to resume work without spending time rebuilding context. Update this file after meaningful project or story changes. Treat the current-session section as the first thing to refresh.

## Current Session: 2026-10-11

- **Current task:** Finish live testing of scene-state recovery after fixing confirmation-dialog usability. The built-in Yes/No popups were replaced by a shared resizable dialog with a scrollable, selectable/copyable message area and persistent Yes/No buttons; the restore preview is no longer truncated. Code commit: `d2a33213646531b1499d6fac39ac1adb26c462fa`. The first check found tests still mocking the old native popup; their mocks were updated in `123f845029d63f07614eeed300ceeefe08c69aa6`, and both push run [146](https://github.com/tony21675/StoryBuilder/actions/runs/38137225369) and PR run [147](https://github.com/tony21675/StoryBuilder/actions/runs/38137228785) passed compilation and all 38 unit tests. Once checks pass, Tony should pull the changes, restart StoryBuilder, open Current State, click **Restore Previous End State**, inspect the full preview, and only confirm if it shows the correct Chapter 1 Scene 6 ending. Continue one action at a time. Permanent novel path: `~/Documents/MyNovel/Taken_at_Dusk`; no test/rebuild folders. New issue to fix in the next code pull: restoring a scene from the prior chapter's ending state copies the old chapter-scoped continuity note `Chapter 1 begins here.` into Chapter 2. Update the restore logic so chapter-specific opening markers are not carried into the next chapter, while preserving the general continuity notes and canon. Tony manually removed that one line from Current State and clicked Apply State Edits during the live session; still verify that the edited state is saved. Do not alter the novel files from this app-repo task.
- **Generic design requirement:** Shared behavior must work across genres, including science fiction, horror, children's books, and future novels. Notes and canon stay isolated inside each novel's package.
- **Per-novel file:** `working_writer_notes.json`. A new unsaved `StoryPackage` starts with a clean empty notes object; a normal first save/save-as creates the file. Older packages load clean defaults without changing the package just by opening it, then get the notes file on the next save. Notes survive subsequent package saves.
- **Writer prompt integration:** Learned craft notes are included as a small, separate reference only when notes exist. The writer prompt treats them as provisional craft observations, never canon, plot instructions, or higher priority than author directions, state, scene contracts, character knowledge, or continuity. The writer receives the note text without the evidence/review metadata.
- **Initial startup seed:** When a novel's notes file has no learned notes and no reviewed scene IDs, the first **Start Writer** action scans every accepted scene in the earliest chapter that has at least two accepted scenes. Drafts are excluded. Long scenes are represented by excerpts from their beginning and ending to keep the prompt bounded. The scan adds at most two craft observations supported by at least two distinct scenes, and records every scanned scene even if it adds no notes, preventing the same initial scan from repeating. If the scan fails, StoryBuilder logs the failure and starts the writer without seeded notes.
- **Ongoing automatic learning:** After an accepted scene's state update has been applied and saved, StoryBuilder continues to review up to the three latest accepted manuscript sections using the active local model. It waits until at least two accepted scenes are available and may add at most two observations when a recurring writing-craft pattern is supported by at least two distinct supplied scenes. It skips rejected drafts, does not change accepted prose/story state, deduplicates similar notes, caps the notebook at eight notes, and records reviewed scene IDs. The note merge layer requires craft-guidance-style phrasing and verifies evidence scene labels against the sampled scenes.
- **Concurrency/safety:** Initial seeding and later reviews run on a background thread while holding the shared writer-engine lock and restore the prior writer prompt when needed. Writer generation/start, save/export, novel switching/closing, and contract building are blocked while a review runs to avoid races. A failed later review leaves the accepted scene saved; a failed initial scan does not prevent writer startup.
- **Feature/test commits:** Writer-notes commits `1f7771005cb1b9223060bef78183ddf48bac79f2`, `a939a0def379e93d2abf24fc0e986b7e33805447`, startup seeding `625c5765126f3e96d61ffd31896d4e0bc235aa70`, storage layout `309e94c69987f31d7f8e2a022f32d51363bc0ea4`, and removal of the tracked sample novel `8b8350e6a057fb0b31e5d7429a64d61858d4e383` are followed by contextual scene reset commits `e5401750ab54fed31876bfbbf5f9d0f6290b1d19`, `223db99a67ba5f6f5d8fe916300e622110eaff8b`, `6e905a6671560966155c5f4a5c8da01265f366e3`, and `be99000b04cc493cf22509394f220ace70d0750b`. GitHub Actions run [138](https://github.com/tony21675/StoryBuilder/actions/runs/38123221870) passed compilation and all 38 unit tests. Commit `d2a33213646531b1499d6fac39ac1adb26c462fa` replaces all native `messagebox.askyesno` calls with a shared resizable confirmation window: message text scrolls and supports mouse selection, Ctrl+A/Ctrl+C, and a right-click Copy menu; Yes/No buttons remain fixed at the bottom. The Restore Previous End State dialog now shows the entire saved Current Situation instead of truncating it. GitHub Actions for this commit are still pending. Test mocks for the four reset confirmations now patch `StoryBuilderApp._ask_yes_no` rather than `messagebox.askyesno`. The local-model restore workflow still needs Tony's live test.
- **Novel library layout:** `~/Documents/MyNovel` is the parent library, not a place where novel files should be mixed together. Each novel package is one immediate child folder. StoryBuilder startup opens the only package automatically; if multiple novel packages exist, it asks which one to open. New novels save under this parent using a folder derived from the title. Open Novel and Save As are restricted to this library. A legacy package stored directly at the library root remains discoverable so it can be migrated safely.
- **Permanent novel path:** `~/Documents/MyNovel/Taken_at_Dusk`. The original repository, Git history, character/module files, accepted Chapter 1 Scenes 1-6, and compiled Chapter 1 were moved together into that folder. The intentional local edit to `writing_guidance.json` is preserved. The test-only `Manuscript/Chapters/Chapter_02/Chapter_02_Section_06_after_state.json` was deleted at Tony's request. Keep Chapter 2 reset: do not restore the abandoned Scene 1 draft from the old rebuild copy.
- **Cleanup completed:** `~/Documents/MyNovel_before_migration` and `~/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk` were removed after verifying all six accepted Chapter 1 scenes and compiled Chapter 1 in `~/Documents/MyNovel/Taken_at_Dusk`. The test-only `Manuscript/Chapters/Chapter_02/Chapter_02_Section_06_after_state.json` was deleted at Tony's request. `StoryBuilder/Test_Novel` was emptied by a tracked StoryBuilder cleanup commit and its empty local folder was removed. The sole known local novel-repository modification was the intentional `writing_guidance.json` edit.
- **Current scene/canon reminder:** Chapter 2 Scene 1 starts immediately after Chapter 1 Scene 6: Maya is curled against Tony's chest after telling him Tiffany is gone. Tony has NOT yet noticed the slap mark, and Maya has NOT yet told him that the kidnapper hit her. Scene 1 ends at Maya's admission that the single kidnapper hit her. Tony remains gently patient; his established fatherly comfort gesture toward Maya must not be suppressed or recast as sexual.
- **State-reset behavior added:** Current State > `Restore Previous End State` loads the saved `_after_state.json` of the prior accepted scene, previews its Current Situation in a Yes/No dialog, preserves the target chapter/scene pointer, resets status/completion flags, and refuses to overwrite accepted target prose. Scene Contract > `Reset Contract` clears saved `direction`, `end_condition`, and `scene_contract` for the current scene while preserving its `scene_idea`, and asks for confirmation. `Reload Saved Contract` confirms before discarding unsaved editor contents. Writer > `Clear Writer Context` confirms and does not delete manuscript prose or reset story state.
- **Next step:** With StoryBuilder closed, pull `fix/build-contract-from-idea-test`, then restart the app. In Current State, click **Restore Previous End State** and verify the confirmation preview says Maya has told Tony Tiffany is gone while Tony has not yet noticed the slap mark. Then use Scene Contract > **Reset Contract**, rebuild from the preserved Scene Idea, and verify the Beginning before generating prose.
- **Storage change in current StoryBuilder work:** The app now treats `NOVEL_ROOT` (`~/Documents/MyNovel` by default) as a one-level-deep library. It opens a sole child novel automatically, prompts when there are multiple, and saves/open novel packages within that library. Existing root-level legacy packages remain discoverable. `builder.workspace.find_novel_packages()` has regression tests.
- **Environment/model:** Linux Mint, Python 3; current local writer model `Gemma-4-E4B_q4_0-it.gguf`.

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

- **New bug found during live test:** Restore Previous End State copies prior-chapter-scoped continuity note `Chapter 1 begins here.` into Chapter 2 Scene 1. Fix the app logic on a future pull so prior-chapter opening markers do not carry forward, while retaining shared canon/continuity notes. Tony manually removed only that line from Current State and clicked Apply State Edits; verify save/persistence before assuming the novel file is corrected.
- **New contract-generation bug found during live test:** `Build Contract from Scene Idea` generated an incomplete ending and omitted an explicit required beat from Tony's Scene Idea for Chapter 2 Scene 1. The generated End only said Tony finishes rubbing Maya's back and butt, and Required Beats omitted Maya struggling to tell him that the man hit her and becoming upset as she remembers. Improve the generic contract-building logic so authored scene ideas' significant emotional/action beats are retained in Required Beats, and the End describes the intended scene-ending state rather than merely the last gesture. Do not hard-code Taken at Dusk or overconstrain other genres. For the current live test, Tony manually changed End and added this Required Beat: `Maya struggles to tell Tony that the man hit her and becomes upset again as she remembers what happened.` Fix in a future app-code pull so this correction is not repeatedly needed.
- **New prose-generation issue found during live test:** Gemma 4 initially made Tony's established familiar comforting gesture trigger Maya's distress, although the authored Scene Idea/canon intends that gesture to reassure and ground her; the distress should come from remembering the blow and struggling to explain it. Tony manually revised the passage so the comfort remains protective and the memory brings the fear back. Investigate whether Writer Direction/prompting can better preserve the intended emotional cause-and-effect from the scene idea and character continuity without hard-coding this novel's specific gesture. For the current Scene 1, review the manually corrected draft before accepting it.
- **New end-to-end scene-generation issue found during live test:** The generated Chapter 2 Scene 1 prose stopped at Maya stammering `H-he... he...` instead of completing the required admission that the man hit her. The author had to manually append a continuation so Maya says what happened, Tony comforts her, and she remains too shaken to explain the full abduction. Improve the generic writer workflow so generated drafts complete all required beats and reach the authored End/scene boundary before they are presented for review, without padding or inventing later-scene information. Do not hard-code this novel or make the author hand-write missing beats after each generation. The manually added continuation was saved; the scene has not yet been accepted.
- **New state-update analysis failure found during live test:** After Chapter 2 Scene 1 was accepted, Analyze Accepted Scene proposed malformed state JSON: character-knowledge arrays for Tony, Tiffany, and Maya were placed under the top-level `location` field, while parts of the same facts were also placed under `character_knowledge`. Do not Apply this candidate. Investigate the state-analysis prompt/merge validation so fields respect the current-state schema and model-generated location remains actual location data; reject or repair candidates that place knowledge lists under `location`. Intended canon update for this scene: Tony has noticed the slap mark and Maya has told him the man hit her; Tony still does not know the kidnapper's identity, motive, or destination. The scene remains accepted but the state update is not applied. Resume with this first tomorrow.

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
