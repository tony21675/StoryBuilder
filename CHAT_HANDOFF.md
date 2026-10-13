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

### Latest Scene 4 generation and revision checkpoint (October 13, 2026)

The author tested a Scene 4 generation after the plain-English Scene Idea was passed directly into the Writer. The author reported it was **“Much much better”** and later summarized the lesson: **less is better, with a little guidance**. This is an encouraging manual result, not proof that every scene will behave correctly.

The generation followed substantially more of the requested idea: Tony offered a warm bubble bath; he made calls to Beth and to Jessica/Rick/Chloe; Barnaby appeared; Tony retrieved clothes; he prepared chamomile tea; and the scene reached the kitchen table. Several execution errors remained:
- The opening repeated some of Scene 3's account/reassurance instead of continuing cleanly from the accepted ending.
- The call timing/invitations were inconsistent: “later this morning,” “Sunday,” and “tomorrow”/coffee drifted together instead of one clear invitation to breakfast the next morning.
- Barnaby was picked up from a laundry-room shelf rather than his established place in Tiffany's bedroom.
- Maya appeared in a towel and apparently did not dress privately before coming to the kitchen.
- The final sentence was outline-like rather than finished scene prose.

The author clarified that Tony may use affectionate, familiar nicknames such as “sunshine” with Beth or Jessica. They have been friends and neighbors for years; this is natural familiarity, not a characterization error.

**Revision workflow rule:** Correct the generated scene *through StoryBuilder*, using a short plain-English revision instruction. Do not replace the draft with prose written by ChatGPT or silently repair the scene on the author's behalf. The point is to test and improve StoryBuilder's own ability to revise its work. Keep the parts that succeeded, request only the necessary corrections, then inspect the app's actual revised output. Do not turn each miss into another long checklist or add validator gates after one sample.

Revision intent for this test: continue from Scene 3 without replaying its account; keep the bath as a bubble bath; invite Beth to the same breakfast the next morning, then invite Jessica, Rick, and Chloe together to that same breakfast; keep both calls casual and disclose nothing about the abduction; get clothes from Tiffany's bedroom; briefly pick up Barnaby and return him to his usual place there; let Maya dress privately; prepare chamomile tea and finish in natural prose with Tony and Maya at the kitchen table. Do not add bedtime or rescue planning.

**Current status:** A natural-language revision instruction was provided, and the author reported StoryBuilder's revised output on October 13, 2026. See **Second Scene 4 revision result** below. The result remains an unaccepted draft and still contains important canon/continuity errors; the next step is a focused correction in StoryBuilder, not a ChatGPT-written replacement. The initial prompt-path fix is helping, but another app-code change is not justified by this draft alone.

### Second Scene 4 revision result (October 13, 2026)

The author supplied StoryBuilder's revised draft. It maintained some improvements: it offered a bubble bath, invited Beth to breakfast the next morning, invited Jessica/Rick/Chloe together, showed Maya dressed before the kitchen-table ending, and included chamomile tea. However, notable errors remain:
- **Major canon error:** Barnaby is described as “the family dog” curled on a rug. Barnaby is Tiffany's worn stuffed rabbit, given to her after Sarah died.
- Tony still picks up and returns the wrong imagined object, and the scene omits his brief private vow to bring Tiffany home.
- The draft offers a bubble bath but later says Maya “showered.”
- Tony seems to retrieve clothes near the laundry, rather than selecting Maya's clean clothes from Tiffany's bedroom.
- The calls include “Rough afternoon here,” “after today,” and “we're all feeling a little low this evening,” which can hint something is wrong. Keep these as ordinary neighborly breakfast invitations and do not raise suspicion before the Chapter 3 breakfast.
- The opening repeats some of the prior reassurance rather than moving cleanly into the bath beat.

The author has explicitly asked that StoryBuilder do its own revisions. **Do not rewrite the scene in ChatGPT.** The next revision should target only the remaining errors, preserve the portions that worked, and keep the prompt natural and reasonably short. Do not respond to a single generation error by adding a new validator gate or expanding the whole Scene Idea.

Suggested brief in-app revision direction:
“Keep the parts that are working and correct these details: Barnaby is Tiffany's stuffed rabbit, not a dog. Tony gave him to her after Sarah died. Tony picks him up for a brief private moment, renews his determination to bring Tiffany home, and returns the rabbit to its usual place in Tiffany's bedroom. Maya takes the bubble bath already offered, not a shower. Tony gets her clean clothes from Tiffany's bedroom and leaves her privacy to dress. Keep both breakfast calls casual and ordinary; remove hints that something is wrong, and don't let either household suspect the abduction. Trim the repeated Scene 3 reassurance and finish naturally with Tony and Maya at the kitchen table over chamomile tea. Preserve the good material and do not add bedtime or rescue planning.”

**Status:** Revised draft has been seen, but remains unaccepted. Next, test this focused revision in StoryBuilder and review the returned output. Do not touch accepted Scenes 1–3.

### Novel and manuscript status### Novel and manuscript status

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
- **Keep the record automatically:** when the author provides a durable correction or direction about the novel, character behavior, collaboration workflow, or app behavior, update the appropriate GitHub handoff as part of the work rather than waiting to be asked again. Use MyNovel's `HANDOFF.md` / `STORY_PLAN.md` for story continuity and canon, and StoryBuilder's `CHAT_HANDOFF.md` for app behavior, workflow decisions, tests, and the next action. Distinguish confirmed canon from unverified test outcomes; never include sensitive letter material or credentials.
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

### Confirmed Scene Idea workflow: plain-English author conversation

On October 13, 2026, the author clarified the intended product workflow. The Scene Idea is supposed to be a natural, plain-English conversation with the model, not a staged scene outline or a miniature script. We drifted into formal Beginning/Middle/End/Required Beats structures and over-prescriptive lists; do not treat those as the author's ideal input experience.

Target workflow:
- A future Scene Planner (or the prior-scene/chapter planning step) proposes a **rough projected Scene Idea** based on what the chapter and scene are already meant to establish, canon, the current state, and the immediately preceding accepted scene.
- The author reviews that draft and makes small, natural-language refinements instead of writing a scene specification from scratch. Example: if the proposed idea says Tony runs a bath or shower for Maya, the author changes it to “Tony runs a bubble bath for Maya.” That correction is intentional and authoritative; do not dilute it back to a choice between bath and shower.
- The Scene Idea should read like the author talking to a writing partner: what the scene is generally about, a few things they want to happen, and where they want it to finish. Do not force the author to provide staged paragraphs, ordered micro-actions, or a long checklist of ordinary gestures and dialogue.
- The model should interpret that plain-English idea together with the current story state and established canon, then write the scene. It should invent ordinary dialogue, reactions, gestures, pacing, transitions, and connective details itself.
- Preserve clear author choices, essential plot events, and the scene boundary. Do not turn every preference into another validator gate or repeat constraints in several prompt sections.
- Keep the internal contract and Writer prompt short. The contract builder is an implementation detail that helps the model follow the idea, not a reason to make the author write in a rigid format.
- On future code changes, inspect how the Scene Idea is proposed, saved, loaded, and converted into a contract. Propose the smallest generic improvement and agree with the author before making that next code change. Do not change the saved Scene 4 idea merely to match an example or overwrite the author's edits.

The app still does not automatically draft a plain-English Scene Idea from chapter plans; that future planning improvement is separate. The current fix preserves the author-edited idea exactly when passing it to the Writer and validator, so the summarizing contract can no longer replace it.

### Manual plain-English Scene Idea test and code fix

On October 13, 2026, the author tested a short conversational Scene Idea for Chapter 2, Scene 4. The generated scene missed most named events, stayed in the bedroom, and replayed or extended the preceding scene. Its generated contract had a broad direction, a hard stop of “Before bedtime or rescue planning begins,” and an empty Required Beats list.

Source inspection identified the structural cause: `scene_idea` was saved, then sent to the contract builder for summarization. The Writer prompt was assembled from generated direction and contract but did **not** include the original plain-English Scene Idea. The contract therefore became a lossy bottleneck before the Writer ever saw the instructions.

The fix is committed on main:
- `SceneContract.from_guidance` now carries the saved `scene_idea` through runtime as `author_idea`, unchanged.
- `SceneContract.writer_prompt_context` builds a concise context: continuity first, only the compact supporting beats/ending next, then the **full original Scene Idea as primary intent** with an explicit priority statement. The serialized supporting contract no longer redundantly repeats generated direction or retry count.
- `storybuilder.py::_write_next_scene` uses this helper. The raw user paragraph is passed directly to the Writer. If the model-generated direction or contract is vague or disagrees with the original idea, the original idea is explicitly authoritative.
- `SceneContract.validate_with_engine` retains `author_idea` instead of filtering it out, and the validator's instructions/prompt use the same priority. It checks major requested actions and the intended endpoint without demanding every incidental detail word-for-word.
- The contract builder is also instructed to capture a few major named actions when present and to name a specific final moment instead of substituting a vague “before X” condition. This is supplemental; the original idea is no longer dependent on the contract summary to reach the Writer.
- No novel JSON migration is needed. Existing saved `scene_idea` text is reused; no specific Scene 4 instructions were hard-coded into the runtime path.

Regression coverage added:
- Original plain-English idea survives even when the contract summary is vague and Required Beats is empty.
- Writer context puts the original idea after the supporting contract and labels it primary.
- Validator receives the exact original idea and is told it supersedes incomplete generated hints.
- The actual app runtime contract loader retrieves the saved idea from the active scene and passes it through unchanged.

**Verification:** [GitHub Actions passed](https://github.com/tony21675/StoryBuilder/actions/runs/38373611359) on [commit 358890a](https://github.com/tony21675/StoryBuilder/commit/358890adebc5873101f462ccc7c294adec757e4f). The full suite compiled the application and passed **82 unit tests**. This proves the generic prompt/data path is wired correctly, but it does not yet prove how the local GGUF model behaves at runtime on the author's laptop.

### Next step after the first manual generation

The first post-fix manual generation has now been tested. Its result was a substantial improvement, with a few continuity and execution errors. Do **not** repeat the initial sync/rebuild/generation steps unless code changes or a new app-state issue make them necessary.

The immediate task is to use StoryBuilder's own revision workflow on the generated Scene 4 draft, then review that actual revised output. Do not rewrite the prose in ChatGPT as a substitute for this test. The correction intent and known defects are documented in **Latest Scene 4 generation and revision checkpoint** above. The revision result is not yet confirmed.

After this input-to-writing path has proved itself across a little more use, the next separate improvement can be an automatic **rough Scene Idea drafter** based on the chapter/scene plan, current state, canon, and immediately preceding accepted scene. The author should only need to make small plain-English corrections before writing begins. Keep that future work generic, do not hard-code the bath/bubble-bath example, and inspect/discuss the design before beginning it.

### Test status
The GitHub Actions check **passed** on [commit 1e68f8f](https://github.com/tony21675/StoryBuilder/commit/1e68f8f75a79855516ff3c13f8f74edc1781305d): compile checks and the full unit suite passed (79 tests). [View the passing workflow run](https://github.com/tony21675/StoryBuilder/actions/runs/38364175575). This is CI coverage only; it does not prove the local model now generates or validates scenes well on the author's 8 GB laptop.

Relevant implementation commits include [c480b99](https://github.com/tony21675/StoryBuilder/commit/c480b994832c43e0b46255729e881868761774fa), [837dd49](https://github.com/tony21675/StoryBuilder/commit/837dd491b2bbc2ce356ad5ab82458b8686b9dd2d), [3d04cd7](https://github.com/tony21675/StoryBuilder/commit/3d04cd7b74f6ea965fed371e95f538b87e83bcd9), [8c3518a](https://github.com/tony21675/StoryBuilder/commit/8c3518ab42ecf0aeecc53fa5ee25fa06e875a9d7), [b493e37](https://github.com/tony21675/StoryBuilder/commit/b493e37aa69d62583e989d2e2f92caad3492dfb0), and [1e68f8f](https://github.com/tony21675/StoryBuilder/commit/1e68f8f75a79855516ff3c13f8f74edc1781305d). Regression tests for prompt size, auxiliary-field omission, process reuse, copyable errors, and draft preservation are included in the passing suite.

### Initial laptop verification (completed; see current revision checkpoint)
The author completed the first manual generation after the plain-English idea was passed into the Writer and reported a major improvement. The initial generation still had several Scene 4 execution errors, documented in the latest manual test section above. The current next step is to test StoryBuilder's own revision of that draft. Do not rerun the initial setup ritual or add generic rules without new evidence.

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
