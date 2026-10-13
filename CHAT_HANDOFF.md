# StoryBuilder Chat Handoff

## First instruction for every new session

Read the current versions on GitHub `main` before acting:
1. [MyNovel HANDOFF.md](https://github.com/tony21675/MyNovel/blob/main/HANDOFF.md)
2. [MyNovel STORY_PLAN.md](https://github.com/tony21675/MyNovel/blob/main/STORY_PLAN.md)
3. [MyNovel current_state.json](https://github.com/tony21675/MyNovel/blob/main/current_state.json)
4. [MyNovel writing_guidance.json](https://github.com/tony21675/MyNovel/blob/main/writing_guidance.json)
5. The complete accepted immediately preceding scene and its saved before/after-state files, from the active local novel package.

**Use the newest checkpoint below as the session handoff. Older conversation context or stale repository copies do not overrule the current author-confirmed checkpoint.**


## Latest Checkpoint: October 13, 2026 (explicit-beat revision mechanics committed; CI passed)

### Generic StoryBuilder revision and validation repair

After reviewing a new Chapter 2, Scene 4 draft that omitted several planned actions, Tony approved a generic mechanics repair rather than repeatedly patching the scene prompt.

- builder/scene_contract.py now tells semantic validation that every item in required_beats is mandatory. The validator should accept paraphrases but fail when a required action is missing or incomplete. Incidental omissions from ordinary scene prose remain non-blocking unless they remove a central development or defeat the scene's endpoint.
- The result normalizer now forces pass=false if the validator reports any missed_beats or material violations alongside pass=true; such contradictory output must not bypass the revision loop.
- Focused-revision feedback and SceneContract.revision_prompt now explicitly tell the model to weave missing Required Beats into natural prose, while preserving successful dialogue, pacing, and unaffected passages instead of turning the scene into an outline or checklist.
- Regression coverage was added for inconsistent validator results and for the distinction between mandatory Required Beats and incidental detail. Existing compact-prompt and physical-continuity assertions were retained.
- Latest verified source commit: [e9479f0](https://github.com/tony21675/StoryBuilder/commit/e9479f0076ddc9996894ab19907a8ed56a256405). [GitHub Actions passed](https://github.com/tony21675/StoryBuilder/actions/runs/38466770124). The intermediate commits in this sequence had compatibility-test failures; the latest commit restored the required continuity/compatibility wording. Do not treat the intermediate failures as the current result.
- The passing automated suite verifies the source and regression behavior, not the local GGUF model's runtime performance. A fresh local model test is still required.
- **October 13 local runtime test:** the scene prose included the bath and both phone calls, but the local validator incorrectly reported those actions as missing for three attempts. The actual scene also needs targeted details: an explicit bubble bath, telling Beth Maya is safe without suggesting Tiffany will attend, Jessica confirming breakfast tomorrow morning rather than deferring it, and clearer clothing pickup from Tiffany's bedroom. The draft was saved and remains unaccepted.
- **Validator evidence rule implemented:** the validation task prompt now tells the reviewer to search the entire scene for equivalent actions before calling a Required Beat missing. If the action occurs but lacks a detail, feedback should name only the missing detail rather than claiming the whole event is absent. The Writer generation prompt was not changed. Source/test commit [`b0dd2a1`](https://github.com/tony21675/StoryBuilder/commit/b0dd2a14e2409f45112ff36edbbac21336fe9427) passed all 91 automated tests in [run 38475831487](https://github.com/tony21675/StoryBuilder/actions/runs/38475831487). The first attempt briefly removed wording required by an existing opening-continuity regression test; the follow-up restored that continuity wording and moved the new evidence rule into the task-specific validator prompt. A fresh local GGUF runtime test is still required.
- **Approved follow-up validator relaxation — October 13, 2026:** a later local run still falsely reported bath and breakfast calls as absent even though the prose contained those actions. The validator now treats Required Beats as narrative-level goals: fail only for a missing core action/outcome or a material continuity/ending problem; a secondary-detail omission alone should not trigger another full generation/revision attempt. The Writer prompt remains unchanged. Regression tests include a representative bath/calls/Barnaby/tea passage and the pass-with-note behavior. Latest implementation: [`f721b87`](https://github.com/tony21675/StoryBuilder/commit/f721b871f66dca4cce84c99750c2a84ffb752223); its automated test result must be verified before updating the laptop.

### MyNovel Scene 4 planning files updated on GitHub

- [writing_guidance.json commit 16cd1d9](https://github.com/tony21675/MyNovel/commit/16cd1d9995afac02233e3c6505c76b98d6d3eebb) updates the saved Scene Idea and five major Required Beats.
- [STORY_PLAN.md commit b2508ef](https://github.com/tony21675/MyNovel/commit/b2508efd6904d9f28bffd2a2188da99d42442ae6) aligns the confirmed order: warm bubble bath; ordinary breakfast call to Beth; then a call to Jessica inviting Jessica, Chloe, and Rick together; clothes from Tiffany's bedroom; Barnaby's hug and Tony's private vow; quiet tea with Maya at the kitchen table. No extra rescue planning or bedtime in Scene 4.
- [MyNovel commit `51f160e`](https://github.com/tony21675/MyNovel/commit/51f160ed8ce44fce8ee6047fcb4430045dcefd58) now explicitly requires Jessica to confirm that she, Chloe, and Rick will attend breakfast **tomorrow morning**; the invitation cannot be deferred to a later date.
- The Scene Idea remains plain English, not a replacement checklist. Accepted Scenes 1–3 remain untouched.
- **Confirmed October 13, 2026:** Tony calls Beth “Honey” and Jessica “Jessabelle.” The seven-person core group share a close extended-family bond and innocent, nonsexual flirtatious banter; it is friendly group personality, not automatic proof of romantic intent. Canon is recorded in MyNovel's `STORY_PLAN.md`, `story_bible.json`, and relevant character/writing guidance.
- **Confirmed relationship progression:** Maya's feelings for Tony and Chloe's still-uncertain feelings may become visible through natural, cumulative behavior over time. Neither directly confesses these feelings to Tony in Chapter 3. Maya knows what she feels; Chloe is still unsure how to interpret hers. Tony's awareness develops only through what he plausibly notices. Keep this separate from ordinary group banter; see MyNovel `STORY_PLAN.md`, `relationship_dynamics.json`, and `story_bible.json`.

### Safe next pickup

1. On the laptop, check `git status -sb` in both MyNovel and StoryBuilder. Fast-forward with `git pull --ff-only` only when that repository is clean and on `main`. The saved Scene 4 draft may have left local novel-file changes; if MyNovel is dirty, stop and inspect/preserve them rather than pulling or resetting blindly. If StoryBuilder is clean, pull the latest validator commit.
2. If StoryBuilder is currently open, close it after confirming the saved draft is safely written. Then run `./start.sh` from `~/Documents/StoryBuilder` to load the new validator source and launch the app.
3. Reload Taken_at_Dusk. Verify the Writer, current state, and Scene Contract show Chapter 2, Scene 4 and the updated saved Scene Idea. If stale, use Clear & Reload Scene Idea and Build Contract from Scene Idea.
4. The rejected Scene 4 draft is saved locally for comparison. StoryBuilder has no separate revise-current-draft button; focused retries happen within one `Write Next Scene` generation cycle. Test one new generation with the unchanged Writer prompt and updated validator. Review whether the validator correctly recognizes events already present and requests only missing details. Do not accept before author review; leave accepted Scenes 1–3 untouched.
5. Do not begin Scene Planner development until Chapter 2 is accepted through Scene 5 and Tony explicitly finalizes the chapter.

## Permanent collaboration rule: discuss before changing anything

Before making changes for Tony **or changes to my own project work/process**, stop and explain the proposed change first. Say what I want to change, why, and the likely effect or risk, then discuss it with Tony and wait for his explicit approval before editing, implementing, committing, pushing, merging, or changing story canon, prompts, code, UI, workflow, files, or handoff notes.

A request to inspect, diagnose, review, or make a recommendation is not permission to modify. Start with read-only investigation when useful, explain the recommendation, and ask before carrying it out. Do not assume a change is harmless, obvious, urgent, or implied. If the approved scope changes or a new issue calls for additional changes, stop and discuss again. Always preserve existing work and avoid destructive actions.

This rule applies equally to changes in Tony's projects and to my own proposed fixes, refactors, tests, documentation, and handoff/process notes. Only proceed without another approval for the specific action Tony has already explicitly requested.


## Previous Checkpoint: October 13, 2026 (initial end-of-session sync repair; historical)

Tony is tired and frustrated after resolving the novel sync problem. The application was closed at the end of this session. Keep tomorrow's restart gentle and do not reopen Git troubleshooting unless a new failure appears.

### Novel sync incident: resolved

- MyNovel's local commit `4c433ca` and reconciliation merge `e224163` were pushed to `tony21675/MyNovel` `main`. The successful push was `40f59a0..e224163 main -> main`, and the local repository showed `## main...origin/main` with no working-tree changes immediately afterward.
- The precise conflict was `writing_guidance.json`. The merged JSON validated. The merged Scene 4 guidance preserves the local `direction`, `end_condition`, `scene_contract`, and all seven Required Beats, while combining the two Scene Ideas and retaining GitHub's additional instruction to make small, focused revisions.
- A local backup remains at `/home/tony/writing_guidance.json.before-sync-repair.bak`. Do not delete it as part of routine work.
- StoryBuilder had been refreshed through `./start.sh` before the diagnostic sync. The corrected error dialog displayed the actual conflicting filename. A regression fix now preserves both stdout and stderr from Git rebase failures: [commit `89fd515`](https://github.com/tony21675/StoryBuilder/commit/89fd515cc5b1305566750734b4027546d07ae113), with the conflict-output regression test at [commit `cd540e56`](https://github.com/tony21675/StoryBuilder/commit/cd540e56c948b1dc7f27e1b7c8284bb67f37c13d). The full suite passed on [GitHub Actions run 38399044839](https://github.com/tony21675/StoryBuilder/actions/runs/38399044839), latest inspected code commit [`1515a76`](https://github.com/tony21675/StoryBuilder/commit/1515a76bb61f2a7c2aadc5570c7271fc344fc6cd).
- The underlying sync error handler and copyable Close & Sync dialog fixes are already on `main`; there is no need to re-run the same repair or make further code changes tonight.
- Branch cleanup was verified after the earlier accidental temporary branches: both `tony21675/StoryBuilder` and `tony21675/MyNovel` have only the permanent `main` branch. No temporary branches or open PRs are part of the desired workflow.

### Tomorrow's safe pickup sequence

1. From `~/Documents/StoryBuilder`, run `./start.sh` to fast-forward the StoryBuilder handoff update and confirm the source sync succeeds.
2. Before editing the novel, ensure the MyNovel checkout is clean and on `main`, then fast-forward the handoff-only updates that are being added to GitHub now. Do not use hard resets, force-pulls, or another diagnostic Close & Sync attempt. If the repository is dirty or diverged, stop and inspect first.
3. Reopen `Taken_at_Dusk` and continue Chapter 2, Scene 4, “Care and memory.” Scene 4 is still unaccepted; accepted Scenes 1–3 are unchanged.
4. Use StoryBuilder's own **revision workflow** on the existing unaccepted Scene 4 draft. Do not rerun the initial manual generation just to repeat the test. If its loaded idea/contract is stale, use **Clear & Reload Scene Idea**, then **Build Contract from Scene Idea**, and revise the existing draft.

### Scene 4 editing checkpoint

The first manual draft had a gentle flow that Tony liked and correctly described Barnaby as Tiffany's stuffed rabbit. The focused revision should address four known misses: call Beth rather than texting her; also call Jessica and invite Jessica, Chloe, and Rick together; get Maya's clean clothes from Tiffany's bedroom rather than the utility closet; and have Tony hug Barnaby and privately vow to bring Tiffany home. Keep the prose natural and preserve all working passages. The scene ends with Tony making chamomile tea and sitting with Maya at the kitchen table as she begins to settle, before bedtime or rescue planning.

Do not develop Scene Planner until Chapter 2 is complete and the author explicitly finalizes it.
## Previous Checkpoint: October 12, 2026 (historical)

### Author-confirmed workflow state

- Chapter 2, Scene 3 was **accepted**, and the author clicked **Apply State Update**.
- After applying, the author confirmed the Writer, current state, and Scene Contract all showed **Chapter 2, Scene 4**.
- The initial local/GitHub discrepancy is **resolved**. On October 12, 2026, local commit [`eb05527`](https://github.com/tony21675/MyNovel/commit/eb05527) pushed the accepted Scene 3 prose, its before/after-state files, saved draft, current state, writer notes, and reconciled writing guidance. The push succeeded; local and GitHub `current_state.json` both reported Chapter 2, Scene 4, and `git status -sb` was clean.
- A safety backup remains at `~/MyNovel_scene4_recovery_20261012_205345`, and stash `54651b3` remains available. Keep them until the author confirms the reopened StoryBuilder package works. Don't run recovery/rebase/pull procedures again unless a new concrete issue appears.
- Do not ask the author to accept, re-analyze, regenerate, or rewrite Scene 3. Continue from Scene 4 after verifying the app has reloaded the synchronized package.
- If you cannot inspect the local checkout directly, walk the author through one small, read-only diagnostic step at a time. Do not ask them to re-explain the story or redo Scene 3.

### Scene 4 status and prompt-design repairs (October 13, 2026)

The current unaccepted Scene 4 draft supplied by the author has a gentle flow he likes. Barnaby is now correctly described as Tiffany's stuffed rabbit. The draft still used texts to Beth instead of a phone call, omitted the call to Jessica, sent Tony to the utility closet for Maya's clothes instead of Tiffany's bedroom, and missed Tony hugging Barnaby and privately vowing to bring Tiffany home. The saved novel Scene Idea specifies the intended actions. Do not change accepted Scenes 1–3.

Two generic repairs have been merged to StoryBuilder `main`:

- [PR #15](https://github.com/tony21675/StoryBuilder/pull/15), commit [`2d06f2f`](https://github.com/tony21675/StoryBuilder/commit/2d06f2fc70a6863c8e30f220e8f1531a0594f4c8), fixes a prompt hierarchy conflict. The original Scene Idea is primary; current story state governs what has already happened, physical continuity, and character knowledge; generated direction and the contract are supporting hints.
- [PR #16](https://github.com/tony21675/StoryBuilder/pull/16), commit [`f09aad7`](https://github.com/tony21675/StoryBuilder/commit/f09aad728b2f206c2e800af1f0af7840f7370b6a), reinforces the author's desired style: **more creative freedom with gentle guidance, not a checklist**. Contract generation should normally leave `required_beats` empty unless the author explicitly marks a small set as Required Beats/non-negotiable. The original Scene Idea should guide the scene's direction, important moments, emotional movement, and endpoint without making each sentence a separate hard task. Leave natural actions, dialogue, gestures, pacing, and transitions to the Writer. Validation should judge the scene holistically and report only material failures.
- If validation finds a real issue and a retry is needed, StoryBuilder now passes the previous draft into the retry and asks for a focused revision that preserves working prose instead of regenerating blindly from scratch.

Both repairs are generic, not hard-coded to this novel. The latest compile and full unit-test suite passed (85 tests) in [GitHub Actions run 38397176767](https://github.com/tony21675/StoryBuilder/actions/runs/38397176767).

**Important Talk to Builder limitation:** the chat command path calls a small pattern-based `apply_command` parser and recognizes simple structured edits such as changing a character field. It is not a natural-language manuscript revision tool. Do not direct the author to use Talk to Builder for prose edits; it returns the generic “did not recognize” message.

Next: after resting, sync/start StoryBuilder, fast-forward the clean MyNovel checkout for the handoff-only updates, then reopen/reload `Taken_at_Dusk`. Use StoryBuilder's own revision workflow on the existing unaccepted Scene 4 draft; do not regenerate a new draft just to repeat the first manual test. Use **Clear & Reload Scene Idea** and **Build Contract from Scene Idea** only if the loaded idea or contract is stale. Review the actual revised Writer output and make only focused corrections. Accepted Scenes 1–3 remain untouched. Do not use Talk to Builder for prose revisions.

### Novel and manuscript status

- **Permanent branch policy:** `tony21675/StoryBuilder` has exactly one remote branch, `main`. Each novel repository (including `tony21675/MyNovel`) also has exactly one remote branch, `main`. Do not create temporary, feature, fix, experiment, or handoff branches; do not open PRs as a normal workflow. Make changes directly on `main`, verify them with tests, and commit there. If a temporary branch is ever created accidentally, merge its work, delete the branch before finishing, and verify GitHub lists only `main`. This is a standing rule, not session-specific.
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

## Branch audit and cleanup (October 13, 2026)

Completed. The stale refs from already-merged PRs #10–16 were removed, and the live GitHub branch lists were verified to contain only `main` for both repositories. No replacements should be created.

## Permanent repository and sync safety rules

- Keep exactly one remote branch per repository: `main`. Never create temporary branches or pull requests during ordinary work. Commit verified changes directly on `main`.
- The novel's **Close & Sync Novel** commits local changes before fetching. If the remote and local edits conflict, never choose a side automatically or keep clicking Sync. The app should abort the incomplete rebase safely, preserve the local commit, and show the conflicting file details. Reconcile the actual conflict before trying again.
- If the app ever reports that a rebase is already in progress, use the updated sync handler to abort the interrupted sync safely; do not improvise with hard resets, force-pulls, or deleting local files.
- After any sync incident, check that both repositories are on `main`, their working trees are understood, and GitHub shows only `main` before moving on to story work.
- **Recurring sync failure fixed on October 13, 2026:** `builder/novel_sync.py` previously left Git mid-rebase when a local/remote content conflict occurred. The handler now detects and safely aborts an interrupted rebase before asking for the branch name (because rebase can show detached HEAD), preserves the local commit, rejects non-`main` branches, and aborts a newly failed rebase with a clear message instead of leaving the repository stuck. See [`ddffffa`](https://github.com/tony21675/StoryBuilder/commit/ddffffadb018c73edfc5e21234a5ca161061b94c), [`24b4951`](https://github.com/tony21675/StoryBuilder/commit/24b4951d13852b4fb166dcc9d3ae4b76360ec58e), and the recovery-order test in [`d3776c7`](https://github.com/tony21675/StoryBuilder/commit/d3776c7afb7e992bdf317f7a2ae65b68cba6cab4). `sync.sh` now rejects non-`main` StoryBuilder checkouts. The complete suite passed on the latest source in [run 38398226025](https://github.com/tony21675/StoryBuilder/actions/runs/38398226025).
- **Branch cleanup verified:** the seven stale StoryBuilder branches were all from merged PRs and have been removed. The live GitHub branch lists for both `tony21675/StoryBuilder` and `tony21675/MyNovel` now show exactly one branch each: `main`. A one-time cleanup job was removed after it completed successfully; no permanent branch-deletion automation remains.
- **Close & Sync error popup fixed on October 13, 2026:** `_sync_current_novel()` already used the copyable error window, but `_close_and_sync()` still used Tkinter's ordinary `messagebox.showerror` for `NovelSyncError` and OS/subprocess failures. Both Close & Sync error paths now call `_show_copyable_error()`; the complete details can be selected or copied using **Copy Full Error**. Regression test: [`c55c0e6`](https://github.com/tony21675/StoryBuilder/commit/c55c0e6de01c61ebbc1f2d0d1f69b0499c3b9230). Compile and full tests passed in [run 38398631770](https://github.com/tony21675/StoryBuilder/actions/runs/38398631770).
- **Resolved MyNovel sync conflict (October 13, 2026):** the conflict was `writing_guidance.json`. Tony's local commit `4c433ca` was preserved, reconciled in local merge commit `e224163`, validated, and pushed to GitHub `main`. The final post-push local status was clean and synchronized. This supersedes the earlier `ahead 1, behind 11/12` diagnostic state.
- **Historical app-version diagnosis (resolved):** the earlier traceback showed the old, non-copyable error dialog because the app had been launched before the latest source refresh. Tony refreshed StoryBuilder with `./start.sh`, then the corrected dialog exposed `writing_guidance.json`. No further diagnostic sync attempt is needed.
- **Handoff update coordination:** never update MyNovel handoff files directly on GitHub while the laptop has unpushed novel changes. This session's novel content is now pushed and clean; the handoff-only documentation updates being made now may leave the laptop a few commits behind, but they should be fast-forward-only. At the next session, synchronize these documentation-only updates while the local working tree is clean before editing novel content.

## StoryBuilder changes and verification notes

- Reusable scene-contract reassurance handling was committed in `builder/scene_contract.py` at [`b52b1c9`](https://github.com/tony21675/StoryBuilder/commit/b52b1c98ce786cb676a862b5bd8db0e7a5cb17d5).
- General writer-prompt reassurance handling was committed in `storybuilder.py` at [`a7eaa92`](https://github.com/tony21675/StoryBuilder/commit/a7eaa923af3193836cd81867e12bd5afb84c5fc0).
- Reassurance prompt regression assertions were added at [`05ce6cf`](https://github.com/tony21675/StoryBuilder/commit/05ce6cfe33aa846ea5c2f547b5a047ff2e9e89b1). These changes were committed, but this handoff has no evidence that the tests were executed after the additions. Do not claim they passed until verified.
- Copyable error dialog clipboard handling was changed in [`ce5d563`](https://github.com/tony21675/StoryBuilder/commit/ce5d5637939119021ec181f155a666005ca2dfcb), with a regression test in [`0b1e992`](https://github.com/tony21675/StoryBuilder/commit/0b1e992787936d04b6bf0349cf098645641c09a6). Both the test and live clipboard behavior remain unverified.
- The local writer model is user-configured. Do not switch or delete models as part of the current novel checkpoint.
- After Chapter 2 is finalized, inspect the actual current StoryBuilder source/tests before implementing Scene Planner. Make one testable change at a time and update this handoff after verification.
