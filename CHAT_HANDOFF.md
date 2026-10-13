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

## Completed implementation: simplify Scene Idea and Scene Contract

The author approved proceeding with the agreed simplification on October 13, 2026. The goal is to make the local model write the novel, using fewer instructions and fewer generated checks instead of micromanaging every action.

**The core change is implemented on main.** The observed pattern from the author's experiments is recorded as product guidance:
- Beginning, Middle, End, and Required Beats are the useful author-planning structure.
- Populating Required Facts, Required Sequence, Forbidden / Do Not Advance, or Forbidden Details has repeatedly correlated with failed validation.
- Shorter prompts and fewer rules work better with the current local model. Do not add replacement rules just to cover every conceivable failure.

### Implemented behavior
- The Scene Contract tab now shows the current starting state, Middle / Scene Direction, End / Hard Stop, and Required Beats. The auxiliary fields are no longer shown.
- Contract generation uses a small JSON shape containing only direction, hard stop, required beats, and retry count. Beginning/Middle/End/Required Beats from the author's idea remain authoritative; explicit Required Beats are preserved.
- Newly generated contracts save only Required Beats and retry count inside the contract, alongside the direction and hard stop.
- At runtime, old novel packages remain loadable, but Required Facts, Required Sequence, Forbidden / Do Not Advance, Forbidden Details, hidden state-after hints, and regex gates are ignored by the active scene contract. Positive story events can still become required beats. Do not reintroduce auxiliary gates without discussing the behavior with the author first.
- The Writer prompt's repeated scene-boundary paragraph is shorter. It keeps the useful boundaries: start from current state, preserve character knowledge and opening position/contact unless changed in-scene, reach the hard stop, and leave prose choices to the writer.
- When the Writer is already running, Scene Contract generation and validation reuse that same WriterEngine process with a smaller context/output budget, avoiding a second concurrent copy of the model. Writer tasks are serialized while a contract is being built.
- Timeouts kill the stalled model process. If prose exists but validation fails, the draft remains visible and saveable, remains unaccepted, and cannot be accepted until a successful validation. Writer and Scene Contract errors use the copyable dialog.

### Test status
The GitHub Actions check **passed** on [commit 1e68f8f](https://github.com/tony21675/StoryBuilder/commit/1e68f8f75a79855516ff3c13f8f74edc1781305d): compile checks and the full unit suite passed (79 tests). [View the passing workflow run](https://github.com/tony21675/StoryBuilder/actions/runs/38364175575). This is CI coverage only; it does not prove the local model now generates or validates scenes well on the author's 8 GB laptop.

Relevant implementation commits include [c480b99](https://github.com/tony21675/StoryBuilder/commit/c480b994832c43e0b46255729e881868761774fa), [837dd49](https://github.com/tony21675/StoryBuilder/commit/837dd491b2bbc2ce356ad5ab82458b8686b9dd2d), [3d04cd7](https://github.com/tony21675/StoryBuilder/commit/3d04cd7b74f6ea965fed371e95f538b87e83bcd9), [8c3518a](https://github.com/tony21675/StoryBuilder/commit/8c3518ab42ecf0aeecc53fa5ee25fa06e875a9d7), [b493e37](https://github.com/tony21675/StoryBuilder/commit/b493e37aa69d62583e989d2e2f92caad3492dfb0), and [1e68f8f](https://github.com/tony21675/StoryBuilder/commit/1e68f8f75a79855516ff3c13f8f74edc1781305d). Regression tests for prompt size, auxiliary-field omission, process reuse, copyable errors, and draft preservation are included in the passing suite.

### Immediate laptop verification
Once the author has saved any draft, Close & Sync Novel, then start StoryBuilder normally so it pulls main. Rebuild the current Scene 4 contract from the saved Scene Idea, then test one generation. Check whether validation finishes and whether the draft is natural and coherent. Do not blindly regenerate or add new rules if it fails; capture the copyable error and address that specific cause.

Scene 4 remains the reusable regression example, not a hard-coded special case: Tony offers a warm bubble bath; Maya chooses whether she wants help and retains her privacy; Tony returns Tiffany's rabbit to its original place; Maya dresses privately in the clothes he brings; Tony invites Beth, then invites Jessica, Chloe, and Rick together because they share a household; the scene ends in quiet recovery at the kitchen table. The accepted Scene 3 opening position remains Maya curled against Tony as he holds her on the bed.

### Completed UI request: Clear & Reload Scene Idea

On October 13, 2026, added a **Clear & Reload Scene Idea** button beside **Build Contract from Scene Idea** in the Scene Contract tab. It reloads only the saved Scene Idea for the current scene, leaving generated contract fields and novel data untouched. If the editor differs from the saved idea, it asks before discarding unsaved edits. It blocks reload during contract building or writer generation and warns/reloads the displayed scene if the editor is out of sync with current state.

- Source commits: [c759667](https://github.com/tony21675/StoryBuilder/commit/c75966792d556d71a0d7baa727a950c67c5524e8) and [c15ae58](https://github.com/tony21675/StoryBuilder/commit/c15ae58ba96d34b37cc07928f94b5cf863bb09ef).
- Added regression tests covering replacement after confirmation, cancellation without losing edits, and reload without confirmation when the idea already matches the saved value: [cd311f5](https://github.com/tony21675/StoryBuilder/commit/cd311f5f3bac607a22f2c32fe9ef1c16afbc4af9).
- The Clear & Reload regression tests are included in the full GitHub Actions unit suite, which passed on [commit 1e68f8f](https://github.com/tony21675/StoryBuilder/commit/1e68f8f75a79855516ff3c13f8f74edc1781305d). The local Tkinter/RustDesk clipboard behavior still merits a quick desktop check.

### Validator timeout and prompt-size reduction

The author reported **"Scene contract validation timed out in the Writer tab"** on October 13, 2026. Code inspection confirmed `builder/scene_contract.py::_run_validator` runs a second local llama-cli process with a 300-second timeout, CPU-only by default unless `STORY_LLM_DEVICE` is set. The validation system prompt repeated rules already present in the user prompt, including two duplicate instructions about familial comfort, and the validator received the full current-state object and contract `state_after` payload.

Changes committed for a generic, lighter review:
- [a165a30](https://github.com/tony21675/StoryBuilder/commit/a165a30821b05c6c2c6df6e3955c829634fa4399) shortened the validator system prompt, reduced the validator token budget from 350 to 220, default validation context from 8192 to 6144 (override with `STORY_VALIDATOR_CONTEXT`), compacted the scene-start state to fields relevant to continuity/knowledge, and removed the potentially large `state_after` from the validation prompt.
- [fec364b](https://github.com/tony21675/StoryBuilder/commit/fec364bcf04ee8880a58d599172376c632970fa5) corrected newline separators in the compact prompt.
- [779ae8c](https://github.com/tony21675/StoryBuilder/commit/779ae8c2ba4a5235e456d51966005410786a85ad) added a regression assertion that relevant physical continuity remains in the prompt while unrelated state data does not.

This first validator-prompt reduction was superseded by the low-RAM implementation below, which also reuses the existing WriterEngine and drops auxiliary contract gates. The final code and unit tests passed GitHub Actions on commit [1e68f8f](https://github.com/tony21675/StoryBuilder/commit/1e68f8f75a79855516ff3c13f8f74edc1781305d). Local-model runtime behavior still needs the laptop check described in the completed-implementation section above.

### Low-RAM behavior and contract simplification

The active laptop has 8 GB RAM. Contract generation and validation reuse the WriterEngine when running; the engine is restarted sequentially with a smaller 6144-token context and task-specific output budget so two concurrent copies of the model are not resident. Writer operations that compete for the local model are disabled during contract creation. If Writer is stopped, contract generation starts one standalone process.

Runtime and newly generated contracts use only direction, Required Beats, and Hard Stop (plus retry count). Older data may still physically contain the auxiliary fields, but `SceneContract.from_guidance` and semantic validation discard them, and writer direction no longer emits auxiliary prohibition rules. Rebuilding the current contract is still recommended so the displayed saved contract matches the new schema.

Writer validation errors use the copyable dialog. If a draft was generated but validation timed out/failed, it stays visible and saveable but unaccepted; Accept stays disabled. A timed-out model process is killed to release memory. See the completed implementation section above for the passing CI result and laptop verification plan.

### Durable design rule

The author's instruction was to discuss future significant changes before making them. The core simplification above was later explicitly approved and implemented. Continue to favor the shortest prompt that preserves the intended beats and boundary. Do not add more fields or more verbose rules just to compensate for a single bad generation. Test the generic path and use actual model output as evidence.

## StoryBuilder changes and verification notes

- Reusable scene-contract reassurance handling was committed in `builder/scene_contract.py` at [`b52b1c9`](https://github.com/tony21675/StoryBuilder/commit/b52b1c98ce786cb676a862b5bd8db0e7a5cb17d5).
- General writer-prompt reassurance handling was committed in `storybuilder.py` at [`a7eaa92`](https://github.com/tony21675/StoryBuilder/commit/a7eaa923af3193836cd81867e12bd5afb84c5fc0).
- Reassurance prompt regression assertions were added at [`05ce6cf`](https://github.com/tony21675/StoryBuilder/commit/05ce6cfe33aa846ea5c2f547b5a047ff2e9e89b1). These changes were committed, but this handoff has no evidence that the tests were executed after the additions. Do not claim they passed until verified.
- Copyable error dialog clipboard handling was changed in [`ce5d563`](https://github.com/tony21675/StoryBuilder/commit/ce5d5637939119021ec181f155a666005ca2dfcb), with a regression test in [`0b1e992`](https://github.com/tony21675/StoryBuilder/commit/0b1e992787936d04b6bf0349cf098645641c09a6). Both the test and live clipboard behavior remain unverified.
- The local writer model is user-configured. Do not switch or delete models as part of the current novel checkpoint.
- After Chapter 2 is finalized, inspect the actual current StoryBuilder source/tests before implementing Scene Planner. Make one testable change at a time and update this handoff after verification.
