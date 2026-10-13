# StoryBuilder Chat Handoff

## First instruction for every new session

Read the current versions on GitHub `main` before acting:
1. [MyNovel HANDOFF.md](https://github.com/tony21675/MyNovel/blob/main/HANDOFF.md)
2. [MyNovel STORY_PLAN.md](https://github.com/tony21675/MyNovel/blob/main/STORY_PLAN.md)
3. [MyNovel current_state.json](https://github.com/tony21675/MyNovel/blob/main/current_state.json)
4. [MyNovel writing_guidance.json](https://github.com/tony21675/MyNovel/blob/main/writing_guidance.json)
5. The complete accepted immediately preceding scene and its saved before/after-state files, from the active local novel package.

**Use the "Current Checkpoint" below as the session handoff. Older conversation context or stale repository copies do not overrule the current author-confirmed checkpoint.**

## Current Checkpoint: October 12, 2026 (synchronized and verified)

### Author-confirmed workflow state

- Chapter 2, Scene 3 was **accepted**, and the author clicked **Apply State Update**.
- After applying, the author confirmed the Writer, current state, and Scene Contract all showed **Chapter 2, Scene 4**.
- The initial local/GitHub discrepancy is **resolved**. On October 12, 2026, local commit [`eb05527`](https://github.com/tony21675/MyNovel/commit/eb05527) pushed the accepted Scene 3 prose, its before/after-state files, saved draft, current state, writer notes, and reconciled writing guidance. The push succeeded; local and GitHub `current_state.json` both reported Chapter 2, Scene 4, and `git status -sb` was clean.
- A safety backup remains at `~/MyNovel_scene4_recovery_20261012_205345`, and stash `54651b3` remains available. Keep them until the author confirms the reopened StoryBuilder package works. Don't run recovery/rebase/pull procedures again unless a new concrete issue appears.
- Do not ask the author to accept, re-analyze, regenerate, or rewrite Scene 3. Continue from Scene 4 after verifying the app has reloaded the synchronized package.
- If you cannot inspect the local checkout directly, walk the author through one small, read-only diagnostic step at a time. Do not ask them to re-explain the story or redo Scene 3.

### Novel and manuscript status

- Repositories: `tony21675/StoryBuilder` and `tony21675/MyNovel`, each on `main` only. Do not recreate old reset/archive branches.
- Active novel package on the author's laptop: `~/Documents/MyNovel/Taken_at_Dusk`.
- Scenes 1, 2, and 3 of Chapter 2 are accepted and must remain untouched unless the author explicitly asks for a rewrite.
- **Next scene: Chapter 2, Scene 4, "Care and memory."** Its saved idea is in `writing_guidance.json`; Scene Contract reads from that file. The accepted Scene 3 and Scene 4 state are now pushed to GitHub in MyNovel commit `eb05527`. On resume, open/reload the existing novel package and verify the Writer, current state, and Scene Contract show Scene 4. Do not ask the author to copy/retype the idea or modify it unless a genuine issue is found.

### Scene 3 continuity and eyewitness rule

Maya recounted Tiffany's resistance: two elbow strikes to the solar plexus, a kick to the thigh, a slap across the jaw, and three scratches down the kidnapper's left cheek that drew blood. Tony offered natural reassurance as Maya struggled to continue.

**Maya is a frightened eyewitness, not a police reporter.** Her words may be broken, emotional, fragmented, imperfect, or out of chronological order. She may remember a later detail and then jump back to an earlier one. This is intentional and believable. Keep the required core actions and the facts actually witnessed, but do not polish her account into a perfectly ordered statement, insist on chronology edits, or regenerate accepted prose just because the recollection moves around. Tony still does not know the kidnapper's identity, motive, or destination.

### Chapter 2, Scene 4: Care and memory

Follow this established sequence, allowing natural dialogue and quiet moments:
1. Tony offers Maya a **warm bubble bath, not a shower**, and respects her adult autonomy, privacy, and choice about help.
2. While she bathes, Tony calls Beth to invite her to breakfast and tells her only that Maya is safe at his house. He then calls Jessica to invite Jessica, Chloe, and Rick together because they all live in the same household; he does not call Chloe and Rick separately. Both calls must sound ordinary and must not reveal or hint that Tiffany was abducted. Nobody else knows or suspects before the Chapter 3 breakfast.
3. Tony goes to Tiffany's bedroom for clean clothes for Maya. He notices the stuffed rabbit he gave Tiffany after Sarah died, which she kept all these years. He hugs it and privately vows to bring Tiffany home by any means necessary.
4. He makes tea for Maya, and they sit together at the kitchen table to recover quietly.

Scene 4's exact stopping point is supplied by its loaded Scene Idea/Contract. Do not jump ahead to Scene 5's bedtime or Tony's private planning.

### Chapter 2, Scene 5 and chapter ending

- Tony settles Maya in Tiffany's bedroom beside his own and stays until she falls asleep.
- He returns to his own room and begins preparing, but does not yet have all the answers or a complete rescue plan.
- Chapter 2 ends only when the author has finished and explicitly finalizes it. Do not infer that a chapter is finished because a scene list ends.

### Chapter 3 and future Scene Planner checkpoint

After Chapter 2 is accepted through its final scene and explicitly finalized, pause before writing Chapter 3 and design/build a reusable, genre-neutral **Scene Planner** in StoryBuilder. It should support batch planning multiple future scenes; expansion from novel premise/story arc to chapters and scenes; author review/editing before save; and automatic storage of approved scene ideas and cast under the active novel's `writing_guidance.json` so Scene Contract loads them when they become current. Avoid manual JSON editing and copy/paste. Preserve **guardrails, not rails**: the author sets the meaningful beats, hard stops, canon, and continuity; the model writes natural dialogue and connective tissue. Before coding, inspect the live code and tests, propose a small design, and discuss the workflow with the author. Do not interrupt Chapter 2 to build this.

At the Chapter 3 breakfast, Tony first tells Beth, Chloe, Jessica, and Rick about the abduction in person. Until then only Tony and Maya know. No police during the kidnapping/rescue. Tony trains both Maya and Chloe and both become active participants; Jessica contributes computer expertise, Beth her community connections, and Rick conventional Army experience/logistics. Reveal Tony's Special Forces history through action rather than a long info dump. Preserve the one-kidnapper rule and do not reveal identity, motive, destination, or the overseas buyer prematurely.

## Standing collaboration rules

- **Guardrails, not rails.** Once the author sets required beats and boundaries, write naturally and creatively between them.
- Don't micromanage small decisions or ask the author to approve ordinary dialogue, gestures, pacing, or connective detail. Use good judgment unless a choice changes canon or a major plot commitment.
- Don't fight settled instructions or repeatedly propose a different approach after the author has clarified a preference. Acknowledge the correction and update the appropriate source file so it persists.
- Keep Maya's interactions with Tony parental/non-romantic from Tony's side. Tony is caring and protective, patient with distress, and respects the girls' adult autonomy.
- Preserve accepted prose. Do not rewrite/regenerate an accepted scene unless explicitly requested.
- Don't force every scene to deliver a major plot development. Let dialogue, silence, everyday details, tenderness, and reactions breathe.
- Sensitive Sarah-related letters, their contents, passphrases, ciphertext, metadata, and keys are local-only. Never place them in GitHub, story prompts, or handoffs. One letter's author/recipient direction remains unresolved; do not decide it without the author's approval.
- Laptop storage cleanup was paused by the author; do not resume unless asked.

## Next development task: make Scene Idea generation generic and durable

The author wants StoryBuilder itself to produce the novel prose. Do not default to writing/replacing full scene passages in ChatGPT; help improve the Scene Idea, contract/prompt logic, and tests so StoryBuilder reliably writes the intended scene. The author should not need to correct the same kind of mistake by hand every time.

**Improve the generic path from Scene Idea to Scene Contract/writer prompt** so it carries author-specified constraints through without weakening, contradicting, or inventing alternatives. Preserve the meaning and ordering of concrete beats, required props/actions, destination/location changes, who has what object, privacy, and scene boundaries. Treat negative constraints as real constraints, not suggestions. Keep the prose flexible between the required beats: guardrails, not rails.

Use the current Chapter 2, Scene 4 corrections as regression examples for generic behavior, not as permanent hard-coded special cases:
- The author specified a **warm bubble bath**. Do not change it into a shower or invent a bath-versus-shower choice.
- Tony briefly holds Tiffany's stuffed rabbit in her room, then returns it to its original place. He must not carry it away with the clean clothes.
- Tony brings the clean clothes back to Maya and leaves them for her to dress privately before she comes to the kitchen table.
- Preserve the causal/order sequence and keep the planned endpoint at quiet recovery at the table; do not skip ahead to later scene beats.

Inspect the actual current Scene Idea builder, writing_guidance.json loading, Scene Contract construction/validation, and writer prompt path before changing code. Identify where constraints are being diluted or contradicted; prefer a reusable prompt/contract improvement plus focused regression tests rather than scene-specific patches. Test that concrete constraints survive from idea through final writer instructions and that the model still has creative freedom for natural dialogue and connective prose. Update this handoff with implementation commits and actual test results; do not claim tests passed unless run.

The larger generation settings were made permanent in start.sh on October 13, 2026, commit [51b0fc3](https://github.com/tony21675/StoryBuilder/commit/51b0fc311d2a1ca1b19cf7ed433b281995e93adb): default STORY_WRITER_CONTEXT=16384 and STORY_WRITER_MAX_TOKENS=4000, while allowing environment-variable overrides. The author reported the next Scene 4 generation was much better and reached the intended ending; keep these defaults and verify local startup sync picks them up.

### Follow-up observation: over-prescribed Scene Ideas can worsen scene coherence

On October 13, 2026, the author reviewed a longer generated draft for Chapter 2, Scene 4 and observed that too much direction appears to make the model muddle staging and continuity. The draft included Tony watching/helping adult Maya bathe and dress, duplicate/unclear clothing movements, "You're home" when Maya is at Tony's house, an overconfident promise about an unidentified kidnapper, and an ending before Maya settles at the table.

Treat this as a core product-design signal for the generic Scene Idea → Contract → writer prompt work:
- Keep Scene Ideas concise, with a small number of meaningful beats, canon facts, and hard boundaries.
- Do not expand an author's short idea into a rigid step-by-step script that prescribes every gesture, transition, or line of dialogue.
- Separate true non-negotiable constraints from optional prose suggestions. Preserve the former faithfully; let the model invent coherent ordinary actions and connective tissue for the latter.
- Maintain physical staging, privacy/autonomy, known facts, and scene endpoint, but avoid repeating the same constraint in multiple ways if repetition makes the prompt noisy.
- Regression tests should check that essential constraints survive without testing for one exact phrasing or hard-coding Chapter 2 scene logic into generic behavior.
- For Scene 4 specifically, preserve the bath (not shower), Maya's adult privacy, Tony returning the rabbit to Tiffany's room, clothes being made available so Maya dresses privately, routine breakfast calls, and the quiet kitchen-table endpoint. Avoid dictating every motion between these beats.

The current scene's defects are evidence to inspect the actual prompt-building path and identify where an idea becomes over-specified or contradictory, not a reason to add more and more rules to the same Scene Idea.


Additional continuity correction from the author: Scene 4 begins directly from the accepted Scene 3 position, with Maya curled against Tony as he holds her on the bed. Do not casually relocate Tony to a chair or invent a different starting arrangement. For the bath and dressing, Tony may offer help and make it available **if Maya chooses**; he should respect her adult privacy and must not assume she wants him to help her bathe or dress. Preserve the offer and her agency without scripting an elaborate consent dialogue or over-explaining it.


### Completed UI request: Clear & Reload Scene Idea

On October 13, 2026, added a **Clear & Reload Scene Idea** button beside **Build Contract from Scene Idea** in the Scene Contract tab. It reloads only the saved Scene Idea for the current scene, leaving generated contract fields and novel data untouched. If the editor differs from the saved idea, it asks before discarding unsaved edits. It blocks reload during contract building or writer generation and warns/reloads the displayed scene if the editor is out of sync with current state.

- Source commits: [c759667](https://github.com/tony21675/StoryBuilder/commit/c75966792d556d71a0d7baa727a950c67c5524e8) and [c15ae58](https://github.com/tony21675/StoryBuilder/commit/c15ae58ba96d34b37cc07928f94b5cf863bb09ef).
- Added regression tests covering replacement after confirmation, cancellation without losing edits, and reload without confirmation when the idea already matches the saved value: [cd311f5](https://github.com/tony21675/StoryBuilder/commit/cd311f5f3bac607a22f2c32fe9ef1c16afbc4af9).
- The tests were committed but **not executed in this environment**. Run `python3 -m pytest -q tests/test_scene_workflow_safety.py` after pulling on the laptop and fix any failures before claiming verification.

## StoryBuilder changes and verification notes

- Reusable scene-contract reassurance handling was committed in `builder/scene_contract.py` at [`b52b1c9`](https://github.com/tony21675/StoryBuilder/commit/b52b1c98ce786cb676a862b5bd8db0e7a5cb17d5).
- General writer-prompt reassurance handling was committed in `storybuilder.py` at [`a7eaa92`](https://github.com/tony21675/StoryBuilder/commit/a7eaa923af3193836cd81867e12bd5afb84c5fc0).
- Reassurance prompt regression assertions were added at [`05ce6cf`](https://github.com/tony21675/StoryBuilder/commit/05ce6cfe33aa846ea5c2f547b5a047ff2e9e89b1). These changes were committed, but this handoff has no evidence that the tests were executed after the additions. Do not claim they passed until verified.
- Copyable error dialog clipboard handling was changed in [`ce5d563`](https://github.com/tony21675/StoryBuilder/commit/ce5d5637939119021ec181f155a666005ca2dfcb), with a regression test in [`0b1e992`](https://github.com/tony21675/StoryBuilder/commit/0b1e992787936d04b6bf0349cf098645641c09a6). Both the test and live clipboard behavior remain unverified.
- The local writer model is user-configured. Do not switch or delete models as part of the current novel checkpoint.
- After Chapter 2 is finalized, inspect the actual current StoryBuilder source/tests before implementing Scene Planner. Make one testable change at a time and update this handoff after verification.
