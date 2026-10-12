# StoryBuilder Chat Handoff
## Mandatory startup reading: do this at the start of every new session

**Do not begin drafting, changing story canon, editing state, or modifying project files until these reads are complete.** This handoff is a map, not a substitute for reading the current source files.

1. Read the full, current [MyNovel HANDOFF.md](https://github.com/tony21675/MyNovel/blob/main/HANDOFF.md). It identifies the saved manuscript position, next task, and project-state cautions.
2. Read the full, current [MyNovel STORY_PLAN.md](https://github.com/tony21675/MyNovel/blob/main/STORY_PLAN.md). It is the central planning source for chapter and scene outlines, confirmed beats, constraints, and unresolved ideas.
3. Read [MyNovel current_state.json](https://github.com/tony21675/MyNovel/blob/main/current_state.json) to establish the actual writing pointer and status. Do not infer the current scene from handoff prose alone.
3a. Read [MyNovel writing_guidance.json](https://github.com/tony21675/MyNovel/blob/main/writing_guidance.json) as the source StoryBuilder actually uses to populate Scene Idea / Author Notes. Before asking Tony to edit an idea, verify the active chapter/scene has a saved `scene_idea` entry in the proper `chapter_plans` structure. If a confirmed plan exists only in `STORY_PLAN.md`, discuss and copy the agreed idea into `writing_guidance.json` rather than asking him to paste it manually. After any external guidance-file update, synchronize and reload the local novel package so the open app reads the new data.
4. Read the accepted scene file(s) needed for the next task, especially the complete immediately preceding scene and its ending. Read related before-state/after-state files and relevant character cards when required by that scene. Do not rely on remembered excerpts.
5. Reconcile the current files before acting. If the plan, handoff, state, and accepted prose conflict, stop before making changes and report the exact conflict. Do not silently choose which version is right.
6. Preserve all accepted scene prose unless Tony explicitly requests a rewrite. Keep unapproved ideas marked **PROPOSED** or **OPEN**, not as canon.
7. After an agreed planning change, update `STORY_PLAN.md`. Update `HANDOFF.md` when the next task or manuscript position changes, and update this `CHAT_HANDOFF.md` whenever needed so the next session follows this same startup-reading procedure.

Always fetch these files from the current `main` branch when resuming. Do not assume an old in-chat copy is current.

## Scene and chapter workflow: author controls chapter endings
- **Scene Idea loading:** Scene Contract populates its editable Scene Idea from `writing_guidance.json`, not directly from `STORY_PLAN.md`. Ensure each agreed upcoming scene has an entry under the correct `chapter_plans[chapter].scene_plan[scene].scene_idea`. Never direct Tony to manually retype a scene plan that should have been preloaded. After an externally committed guidance change, synchronize and reopen/reload the local novel package before expecting the running app to display it.


- Scene plans are guidance, not a cap on how many scenes a chapter may contain. The author may keep advancing to additional scenes as the story needs them, including scenes not already listed in the structured plan.
- Do not infer that a chapter has ended merely because the existing scene plan runs out. The author decides when the actual final scene is complete.
- After the final accepted scene's state update has been applied, use **Finalize Chapter** when Tony says that chapter is finished. Then use **Start Next Chapter** when ready to begin the next chapter.
- For a new scene, use the redesigned Scene Contract workflow: edit only **Scene Idea / Author Notes**, then click **Build Contract from Scene Idea**. The detailed contract fields are generated, read-only guidance. Adjust the idea and rebuild if needed.
- Do not tell Tony to manually edit the scene number in JSON or restore the old planned-scene cap workflow.

## Standing writing principle: guardrails, not rails

Do not micromanage the story. Once Tony has established the must-happen beats, hard stops, canon, character knowledge, and continuity rules, write creatively and let each scene breathe.

- Use sound judgment for natural dialogue, reactions, body language, atmosphere, pacing, and small connective events. These ordinary creative choices do not need individual approval.
- Do not turn scene planning into an exhaustive script or keep asking Tony to decide small details. If a detail is minor, choose what best fits the established characters and story.
- Preserve explicit requirements, scene hard stops, accepted prose, and known secrets. Creativity must not contradict those boundaries or silently change canon.
- Pause to consult Tony only for meaningful conflicts, consequential ambiguities, major plot commitments, or changes to agreed requirements. Mark optional future ideas as proposed rather than settled.
- Aim for emotionally honest scenes with room for quiet moments, dialogue, humor, tenderness, and character-led discoveries, not just plot delivery.

Treat the plan as sturdy guardrails, not instructions for every sentence. Keep the story coherent, but leave room for creative surprises.



## Current Session: 2026-10-12

- **Current repositories:** StoryBuilder works on `main`. MyNovel is separate and has only `main`; do not recreate deleted reset/archive branches.
- **Current writing position:** MyNovel `current_state.json` points to Chapter 2, Scene 2 (`status: in_progress`, `scene_completed: false`). Scenes 1 and 2 are saved and must not be regenerated or edited unless Tony asks.
- **Next task:** Draft Chapter 2, Scene 3 from the exact last line of accepted Scene 2. Maya has described the van, the man grabbing Tiffany, his dead-looking eyes, and his scent (old cigarettes, cheap cologne, pine needles). Do not repeat those details. Scene 3 must cover Maya's account of Tiffany's two elbow strikes to the solar plexus, kick to the thigh, slap across his jaw, and three blood-drawing scratches on his left cheek; Tony listens and comforts her. Hard stop while Tony still does not know identity, motive, or destination.
- **Chapter 2 Scene 4:** Tony runs Maya a warm bubble bath (not shower), offers privacy/help choices, and while she bathes phones Beth, Chloe, Jessica, and Rick to invite them to breakfast without revealing or hinting at the abduction. He tells Beth only that Maya is safe at his house. Tony goes to Tiffany's room for clean clothes, finds the stuffed rabbit he gave her after Sarah died, hugs it, and privately vows to bring Tiffany home by any means necessary. He then makes tea and sits with Maya at the kitchen table.
- **Chapter 2 Scene 5:** Tony settles Maya in Tiffany's bedroom, next to his own, and stays until she sleeps. He can check on her through the night and in the morning. Then he returns to his room and begins planning without yet having all the answers. End Chapter 2 with Tony alone and preparing.
- **Chapter 3 opening:** Breakfast at Tony's house the next morning. Tony tells Beth, Chloe, Jessica, and Rick about the abduction in person at breakfast. Until then, only Tony and Maya know; the invitation calls cannot hint at Tiffany's abduction.
- **Confirmed ongoing rules/roles:** No police during the kidnapping/rescue. Tony leads and trains both Maya and Chloe; both women train and actively participate in the rescue. Maya grows from shaken witness to capable partner; Chloe brings determination and develops practical skills. Jessica is the computer specialist; Beth contributes local/community connections and supports Maya; Rick is a conventional Army veteran (not Special Forces) who helps with logistics, transportation, and planning. Tony's military background should emerge through action, not an explanatory info dump. Keep their growth believable.
- **Letter caveat:** The local-only second sealed Sarah-related letter has been safely verified, but historical handoffs contradict whether it is from Sarah to Tony or by Tony to Sarah. One possible, not-yet-approved story beat is Tony considering opening it after settling Maya, then leaving it sealed until learning what the kidnappers intend for Tiffany. Do not present that beat or the letter's direction as settled canon; never store/show plaintext, passphrases, ciphertext, or private-key data in project handoffs or StoryBuilder.
- **Secret-letter security:** Both letters, metadata, and private-key material remain local-only outside GitHub. The safe verification of both letters was successful without displaying or saving plaintext.
- **Environment/model:** Linux Mint, Python 3; use the tested model `~/Documents/Models/01 gemma-4-E4B_q4_0-it.gguf`. Laptop cleanup remains paused.
- **Current StoryBuilder code:** Recent `main` commits added vertically scrollable tabs, author-controlled chapter completion, confirmed advance into an unplanned scene, and compact dropdown navigation. Do not start unrelated app work unless asked.

## Previous Session: 2026-10-11

> Purpose: Paste this document into a new ChatGPT conversation to resume work without spending time rebuilding context. Update this file after meaningful project or story changes. Treat the current-session section as the first thing to refresh.

## Current Session: 2026-10-11

- **Repository consolidation:** PR [#8](https://github.com/tony21675/StoryBuilder/pull/8) was merged into `main` at merge commit `ff20984f6ffff7810a41512940cb8880f7ba79bd`; it includes the current application and the 45-test suite. PR [#6](https://github.com/tony21675/StoryBuilder/pull/6) was closed as superseded because its Start Next Chapter work is included in PR #8. `main` is the canonical StoryBuilder working branch. GitHub Actions passed all 45 tests before merge, and Tony later ran `python3 -m pytest -q` locally with **45 passed** and confirmed `./start.sh` launched StoryBuilder. Branch cleanup is complete: GitHub and Tony's local StoryBuilder checkout now have only `main`, and local `main` matches `origin/main`. Do not create replacement branches.
- **MyNovel state discrepancy (resolved 2026-10-12):** The earlier local-vs-GitHub mismatch and reset-branch caution were superseded by the cleanup/consolidation recorded in `MyNovel/HANDOFF.md`. Current MyNovel is on `main`; GitHub lists no reset or archive branch. The actual current state is Chapter 2, Scene 2, `status: in_progress`, `scene_completed: false`. Scenes 1 and 2 are saved and must remain untouched unless Tony asks.
- **Current code commits:** State validation/note helper in `builder/state_manager.py`; apply/restore and writer prompt guards in `storybuilder.py`; structured contract preservation and validator guidance in `builder/scene_contract.py`; regression tests in `tests/test_scene_contract.py` and `tests/test_state_manager_validation.py`.
- **Verification:** GitHub Actions run [177](https://github.com/tony21675/StoryBuilder/actions/runs/38178938732) compiled the application and builder modules and passed all 45 unit tests. This is automated test evidence; the local model still needs end-to-end live verification after Tony pulls the branch.

- **Current task:** Reconcile the MyNovel local state after the overnight pause. Preserve the accepted Chapter 2 Scene 1 prose; do not apply the incorrect state candidate or alter the prose. Begin by inspecting `git diff -- current_state.json`, then compare it against the local `HEAD` and the actual accepted scene ending. Explain the proposed state correction before modifying any file, and do not sync/pull/merge or change branches until Tony reviews the correction.
- **Generic design requirement:** Shared behavior must work across genres, including science fiction, horror, children's books, and future novels. Notes and canon stay isolated inside each novel's package.
- **Per-novel file:** `working_writer_notes.json`. A new unsaved `StoryPackage` starts with a clean empty notes object; a normal first save/save-as creates the file. Older packages load clean defaults without changing the package just by opening it, then get the notes file on the next save. Notes survive subsequent package saves.
- **Writer prompt integration:** Learned craft notes are included as a small, separate reference only when notes exist. The writer prompt treats them as provisional craft observations, never canon, plot instructions, or higher priority than author directions, state, scene contracts, character knowledge, or continuity. The writer receives the note text without the evidence/review metadata.
- **Initial startup seed:** When a novel's notes file has no learned notes and no reviewed scene IDs, the first **Start Writer** action scans every accepted scene in the earliest chapter that has at least two accepted scenes. Drafts are excluded. Long scenes are represented by excerpts from their beginning and ending to keep the prompt bounded. The scan adds at most two craft observations supported by at least two distinct scenes, and records every scanned scene even if it adds no notes, preventing the same initial scan from repeating. If the scan fails, StoryBuilder logs the failure and starts the writer without seeded notes.
- **Ongoing automatic learning:** After an accepted scene's state update has been applied and saved, StoryBuilder continues to review up to the three latest accepted manuscript sections using the active local model. It waits until at least two accepted scenes are available and may add at most two observations when a recurring writing-craft pattern is supported by at least two distinct supplied scenes. It skips rejected drafts, does not change accepted prose/story state, deduplicates similar notes, caps the notebook at eight notes, and records reviewed scene IDs. The note merge layer requires craft-guidance-style phrasing and verifies evidence scene labels against the sampled scenes.
- **Concurrency/safety:** Initial seeding and later reviews run on a background thread while holding the shared writer-engine lock and restore the prior writer prompt when needed. Writer generation/start, save/export, novel switching/closing, and contract building are blocked while a review runs to avoid races. A failed later review leaves the accepted scene saved; a failed initial scan does not prevent writer startup.
- **Feature/test commits:** Writer-notes commits `1f7771005cb1b9223060bef78183ddf48bac79f2`, `a939a0def379e93d2abf24fc0e986b7e33805447`, startup seeding `625c5765126f3e96d61ffd31896d4e0bc235aa70`, storage layout `309e94c69987f31d7f8e2a022f32d51363bc0ea4`, and removal of the tracked sample novel `8b8350e6a057fb0b31e5d7429a64d61858d4e383` are followed by contextual scene reset commits `e5401750ab54fed31876bfbbf5f9d0f6290b1d19`, `223db99a67ba5f6f5d8fe916300e622110eaff8b`, `6e905a6671560966155c5f4a5c8da01265f366e3`, and `be99000b04cc493cf22509394f220ace70d0750b`. GitHub Actions run [138](https://github.com/tony21675/StoryBuilder/actions/runs/38123221870) passed compilation and all 38 unit tests. Commit `d2a33213646531b1499d6fac39ac1adb26c462fa` replaces all native `messagebox.askyesno` calls with a shared resizable confirmation window: message text scrolls and supports mouse selection, Ctrl+A/Ctrl+C, and a right-click Copy menu; Yes/No buttons remain fixed at the bottom. The Restore Previous End State dialog now shows the entire saved Current Situation instead of truncating it. That earlier commit's local-model restore workflow still required Tony's live test at the time. Test mocks for the four reset confirmations now patch `StoryBuilderApp._ask_yes_no` rather than `messagebox.askyesno`. The local-model restore workflow was awaiting Tony's live test at the time of that earlier handoff.
- **Novel library layout:** `~/Documents/MyNovel` is the parent library, not a place where novel files should be mixed together. Each novel package is one immediate child folder. StoryBuilder startup opens the only package automatically; if multiple novel packages exist, it asks which one to open. New novels save under this parent using a folder derived from the title. Open Novel and Save As are restricted to this library. A legacy package stored directly at the library root remains discoverable so it can be migrated safely.
- **Permanent novel path:** `~/Documents/MyNovel/Taken_at_Dusk`. The original repository, Git history, character/module files, accepted Chapter 1 Scenes 1-6, and compiled Chapter 1 were moved together into that folder. The intentional local edit to `writing_guidance.json` is preserved. The test-only `Manuscript/Chapters/Chapter_02/Chapter_02_Section_06_after_state.json` was deleted at Tony's request. Keep Chapter 2 reset: do not restore the abandoned Scene 1 draft from the old rebuild copy.
- **Cleanup completed:** `~/Documents/MyNovel_before_migration` and `~/Documents/MyNovel_Scene1_Rebuild/Taken_at_Dusk` were removed after verifying all six accepted Chapter 1 scenes and compiled Chapter 1 in `~/Documents/MyNovel/Taken_at_Dusk`. The test-only `Manuscript/Chapters/Chapter_02/Chapter_02_Section_06_after_state.json` was deleted at Tony's request. `StoryBuilder/Test_Novel` was emptied by a tracked StoryBuilder cleanup commit and its empty local folder was removed. The sole known local novel-repository modification was the intentional `writing_guidance.json` edit.
- **Chapter 2 Scene 3 continuity (current):** Chapter 2 Scenes 1 and 2 are saved. Scene 2 ends after Maya describes the van, the man grabbing Tiffany, his dead-looking eyes, and his smell. Begin after that paragraph, without replaying the disclosed details. Tony knows Tiffany is gone and that Maya was struck, but does not know the kidnapper's identity, motive, destination, or full sequence. Keep Tony patient; his established fatherly comfort gesture must not be suppressed or recast as sexual.
- **State-reset behavior added:** Current State > `Restore Previous End State` loads the saved `_after_state.json` of the prior accepted scene, previews its Current Situation in a Yes/No dialog, preserves the target chapter/scene pointer, resets status/completion flags, and refuses to overwrite accepted target prose. Scene Contract > `Reset Contract` clears saved `direction`, `end_condition`, and `scene_contract` for the current scene while preserving its `scene_idea`, and asks for confirmation. `Reload Saved Contract` confirms before discarding unsaved editor contents. Writer > `Clear Writer Context` confirms and does not delete manuscript prose or reset story state.
- **Next step:** In the next writing session, define Chapter 2 Scene 3's goal, required beats, and exact hard stop before drafting. Keep accepted Scenes 1 and 2 unchanged. Work on StoryBuilder `main` and MyNovel `main` only; do not recreate deleted branches or resume laptop cleanup.
- **Storage change in current StoryBuilder work:** The app now treats `NOVEL_ROOT` (`~/Documents/MyNovel` by default) as a one-level-deep library. It opens a sole child novel automatically, prompts when there are multiple, and saves/open novel packages within that library. Existing root-level legacy packages remain discoverable. `builder.workspace.find_novel_packages()` has regression tests.
- **Environment/model:** Linux Mint, Python 3; tested local writer model `~/Documents/Models/01 gemma-4-E4B_q4_0-it.gguf`.

## Change Approval and Author Authority

- **Always discuss before changing or rejecting something.** Before implementing a code, prompt, validator, test, workflow, writing-style, story, character, or canon change, explain the problem you observed and the proposed adjustment. Wait for Tony's agreement before making the change. Do not interpret a general request to "fix it" as permission for an un discussed approach.
- This applies equally to adding restrictions, removing or denying a requested beat, gesture, or character behavior, changing a character's intent, or deciding that a passage is inappropriate. Do not silently sanitize, censor, forbid, or reinterpret content based on an assumption. If context or intent is unclear, ask Tony first.
- Tony is the authority on his story, character relationships, established history, and intended meaning. Respect previously agreed canon instead of re-litigating it or imposing an outside interpretation.
- Specifically, Tony and Maya's familiar comfort gesture is an established, non-sexual fatherly habit from Maya's childhood. Tony gently rubs her back and butt to help her settle when distressed. It is not groping, and neither character experiences it sexually. Do not characterize it as sexual, remove it, or add a rule to suppress it unless Tony himself asks to change that canon.
- Discuss the smallest useful fix before editing. Prefer diagnosis and a proposed option first, then wait for agreement; after agreement, implement only the agreed scope and test it.
- Do not ask Tony to hand-edit generated prose to compensate for a recurring application/prompt problem when a targeted underlying fix is appropriate. But also do not change the underlying behavior without discussing the proposed fix and receiving agreement.
- Existing explicit permissions remain in force: a clearly directed change can be carried out within that agreed scope; this rule does not require repeated confirmation of details already agreed.

## How to Work With Tony
- Work directly on StoryBuilder `main`; do not create feature/test branches or extra project copies. MyNovel is a separate repository whose only current branch is `main`. Follow `MyNovel/HANDOFF.md` for its status and do not resurrect deleted branches.

- Read this handoff before responding and continue from the current task instead of restarting.
- Do not make Tony repeat details already included here.
- Do not guess what files, code, or branches contain. When current repository information matters, inspect GitHub's actual current branch and files first.
- **Single-working-area rule:** Keep app work in one project folder on StoryBuilder `main`. Do not create feature/test branches, alternate clones, parallel working folders, or extra novel copies unless Tony explicitly asks. For app tasks, leave the novel repository untouched. Clean up existing obsolete branch refs only after confirming their code is represented in `main`.
- Do not claim a test passed without evidence.
- Run the available test suite or CI against the actual changed branch before declaring the code ready. Be explicit about what was tested and what still requires a live local-model test.
- Never overwrite, reset, delete, or replace work without discussing it with Tony first.
- Give one clear next step at a time for computer walkthroughs.
- If something essential is unclear, ask one focused question rather than inventing details.
- Stay on the task at hand. Don't turn a minimal-contract test into a long list of new instructions before examining the actual result.

## Repositories

- StoryBuilder: https://github.com/tony21675/StoryBuilder
- Current StoryBuilder working branch: https://github.com/tony21675/StoryBuilder/tree/main
- Private novel repository: https://github.com/tony21675/MyNovel
- Current novel branch: https://github.com/tony21675/MyNovel/tree/main

As of October 12, 2026, MyNovel's history was cleaned to remove the secret-letter directory from reachable history, and the old reset/archive branches were deleted. GitHub currently lists only `main`. Do not resurrect the deleted branches or copy old repository history back into the active checkout.

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

- **Chapter-transition fix implemented:** Restore Previous End State now removes the prior chapter's explicit opening marker (for example, `Chapter 1 begins here.`) when restoring into the next chapter, while preserving shared continuity notes. Regression tests cover marker removal, shared-note preservation, and same-chapter behavior.
- **Contract-generation fix implemented:** The contract builder now recognizes labeled Beginning, Middle, End, Required, and Required Beats sections. It preserves the authored Beginning and Middle in direction, uses the authored End as the hard stop, and merges explicitly supplied Required Beats into the generated contract. This remains generic and does not hard-code Taken at Dusk.
- **Prose-generation prompt fix implemented:** Writer and semantic-validator instructions now require completion of explicit actions/disclosures before ending, enforce the complete authored scene boundary, and preserve established emotional cause-and-effect. Trusted, reassuring care gestures should not become an invented cause of distress when the author/canon says they are comforting. Live-model behavior still needs verification.
- **End-to-end generation fix implemented:** The earlier draft stopped before completing the required disclosure because the generated contract omitted an explicit beat. Structured contract handling now preserves labeled Required Beats and End, and the writer/validator prompts require completed actions and the authored stopping point. The previously malformed candidate was not applied. The latest MyNovel handoff confirms Chapter 2 Scenes 1 and 2 are saved; leave both unchanged unless Tony asks.
- **State-update validation implemented:** The state-analysis prompt now defines the expected shapes for `location` and `character_knowledge`. Deterministic checks reject non-object `location`, non-text location entries, and malformed character-knowledge mappings before preview/application; the apply action checks again. That note described the earlier Scene 1 state-update issue and is historical. MyNovel's current handoff confirms Scenes 1 and 2 are saved and the pointer is at Scene 2. For Scene 3, inspect the newly analyzed candidate before applying any state update.

## Recommended Workflow for Each Test

1. State the intended behavior of the current contract in plain language.
2. Let the user run the current setup and provide the actual output.
3. Compare output with the intended scene boundary and canon.
4. Identify the likely source of the miss before proposing a fix.
5. Make one small, testable adjustment.
6. Update this handoff's **Current Session** section after the test result or task changes.

## Updating This File

After meaningful progress, update this file on the current StoryBuilder `main` branch with:
- The new current task and scene status.
- What was actually tested and observed.
- Any confirmed code/contract changes and their commit or branch.
- The next concrete step.
- Any new canon correction that should persist across chats.

Keep stable canon and working preferences, but replace stale current-session details. Do not record guesses as facts.
