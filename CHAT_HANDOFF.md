# StoryBuilder Chat Handoff

## Current Session: 2026-10-12

- **Current working branches:** StoryBuilder is on `main`. The private novel repository `tony21675/MyNovel` was cleaned and consolidated to `main` on October 12, 2026; GitHub currently lists only `main`. Do not recreate or resurrect the deleted `chapter1-clean-reset` or archive branches.
- **Current writing task:** Begin fresh with **Chapter 2, Scene 3** in the next writing session, Tuesday, October 13, 2026. Use `tony21675/MyNovel/HANDOFF.md` as the authoritative novel handoff and the actual files on MyNovel `main`; this document's older MyNovel notes below are historical where they conflict.
- **Scene 2 status:** Chapter 2 Scenes 1 and 2 are saved. Do not rewrite, regenerate, or reopen either unless Tony explicitly asks. The current pointer in `current_state.json` is Chapter 2, Scene 2, `status: in_progress`, `scene_completed: false`.
- **Precise Scene 3 starting point:** Scene 2 ends in Tony's bedroom with Maya curled against Tony's chest. Tony is holding and comforting her while she recounts what she witnessed. She has described the dark van pulling up quickly near the corner, Tiffany laughing just before the man moved, the man grabbing Tiffany's arm, his dead-looking eyes, and his smell: old cigarettes, something sweet like cheap cologne, and pine needles. Continue after the end of that paragraph; do not repeat those details as new information.
- **Scene 3 process:** Before drafting, establish Tony's intended scene goal, essential beats, and a precise hard stop with him. Do not assume Maya must finish the entire abduction account in Scene 3. Keep Tony patient and attentive, let pauses and imperfect recollection breathe, and preserve knowledge boundaries. No search/rescue begins unless Tony's Scene 3 direction calls for it and continuity supports it.
- **Recovered broader planning:** `MyNovel/HANDOFF.md` now preserves partial planning fragments for the rest of Chapter 2 and the Chapter 3 breakfast opening: warm bubble bath (not shower), Maya choosing privacy/help, Beth's call during the bath, Tiffany's clothes placed in the kitchen, and tea at the kitchen table; Chapter 3 breakfast is the point when others may learn Tiffany is missing, with only Tony and Maya knowing before then. The longer-range rescue setup includes Tony training Maya and Chloe, Jessica's computer expertise, Beth's community connections, and Rick's practical/logistics experience. These are recovered fragments only: the exact remaining Chapter 2 scene order/boundaries and Chapter 3 breakfast beats were not found in the checked repository files. Do not present a newly invented outline as the old agreement or ask Tony to restate the recovered details.
- **Continuity:** One unidentified male kidnapper was physically involved. Tony knows Tiffany has been taken and that Maya was struck. He does not know the kidnapper's identity, motive, destination, or the full sequence. Tiffany is in the van, conscious and distressed. Maya is with Tony in his bedroom. Chloe is home sick and is not participating.
- **Sealed letters:** The latest `tony21675/MyNovel/SECRET_LETTERS_HANDOFF.md` confirms the local-only verification work is complete: Tiffany's remembered passphrase was validated without displaying or saving plaintext, and Tony's separate letter verification script passed key-match, integrity, and decryption checks while discarding plaintext. The encrypted letters, metadata, and private key stay local-only and outside GitHub. Never record a passphrase, private-key material, ciphertext, or letter plaintext in a handoff, prompt, manuscript, or repository. The possible beat where Tony considers Sarah's letter to him remains an idea, not accepted canon.
- **Laptop cleanup:** Storage cleanup was paused at Tony's request. Do not resume unless asked.
- **Model for the next writing session:** `~/Documents/Models/01 gemma-4-E4B_q4_0-it.gguf`, the tested and preferred local writer model.
- **StoryBuilder code status:** The latest commits on `main` include vertically scrollable tabs, author-controlled chapter completion, confirmed advance into an unplanned scene, and compact dropdown navigation. Do not start a new app feature or branch unless Tony directs it.

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
