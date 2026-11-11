# Writer App handoff

**Updated:** November 11, 2026  
**Application:** StoryBuilder Minimal Writer  
**Repository:** `tony21675/StoryBuilder`  
**Active/default branch:** `redesign/simplified-writing-workflow`  
**Local repository:** `~/Documents/StoryBuilder`

## Purpose and boundary

This document covers the Writer application only. The Story Bible is a separate application with its own launcher and technical handoff: [STORY_BIBLE_APP_HANDOFF.md](STORY_BIBLE_APP_HANDOFF.md).

The Writer creates and edits manuscript prose. Novel canon, character cards, locations, scene state, and accepted manuscripts belong to each novel's own package. Do not copy a novel's full story details into this app handoff.

## Launch and synchronization

- Main entry point: `minimal_writer.py`
- Launcher: `./start.sh`
- Local repository: `~/Documents/StoryBuilder`
- The launcher runs `sync.sh start` before opening the app. It uses the current branch and its matching `origin/<branch>` upstream, fetches, fast-forwards only, and temporarily stashes/restores uncommitted app-repository changes. It stops on divergence, an unfinished Git operation, a conflict, a detached HEAD, or an unexpected upstream.
- The Writer's app sync uses `builder/app_sync.py`. It stages/commits local StoryBuilder changes, fetches, fast-forwards only, and pushes the current branch. It refuses to sync from `main` and stops without pushing if histories cannot be fast-forwarded safely.
- **Keep the existing branch name.** The repository currently has one branch, `redesign/simplified-writing-workflow`, which is also its GitHub default. The sync helpers explicitly refuse `main`, and some GitHub Actions triggers still name the existing branch. Renaming it would require a coordinated code, test, workflow, and upstream migration. There is no extra StoryBuilder branch clutter to clean up.
- The Writer's **Sync Novel to GitHub** action is separate. It previews the selected novel repository and asks for explicit confirmation before syncing that novel's own branch. It does not sync StoryBuilder code.
- Do not force-push, reset, or overwrite local changes to resolve a sync problem. Inspect the branch relationship and preserve both sides.

## Local handoff safety copies

- `backup_handoffs.py` calls `builder/handoff_backup.py`.
- It refreshes `~/Documents/Project_Handoff_Backups` by default. Set `STORY_HANDOFF_BACKUP_DIR` to choose another destination.
- The mirror includes the current StoryBuilder index and both app handoffs, the Long Way Home handoff and story-direction file, and the Taken at Dusk handoff/reference documents when those source files exist locally.
- The backup runs after the launcher has synchronized StoryBuilder and after successful StoryBuilder or selected-novel GitHub syncs. It can also be run manually with `python3 ~/Documents/StoryBuilder/backup_handoffs.py`.
- The mirror copies only named Markdown handoff/planning documents. It does not copy manuscripts, model files, credentials, encrypted material, or secret-letter assets. Missing source files are skipped; old local copies are not deleted.
- The repositories remain authoritative. The separate mirror is an emergency local copy and should not be edited as the primary record.

## Current functionality recorded

- Load and use local language models for separate writing tasks: Prepare Scene (planner) and manuscript prose (writer).
- The app uses one WriterEngine process and switches models sequentially. It loads the planner model for Prepare Scene and the writing model for Write, Continue, Rewrite Scene, AI passage revision, and New Session. The previous model process is stopped before the other model starts; both models are never held in memory by StoryBuilder at the same time.
- Two model selectors are shown in the Writer UI. Model filenames are saved outside the repository in `~/.config/storybuilder/model_roles.json` (or the path specified by `STORYBUILDER_MODEL_ROLES_FILE`). Defaults select a Qwen3.5-4B filename for Prepare Scene and Gemma 4 E4B for manuscript writing when those files are available. Both selections can be changed in the UI and persist across launches.
- The existing **Load Writer** button preloads the selected manuscript-writing model. Prepare Scene and manuscript actions also load their selected role automatically when needed.
- Write, Continue, Prepare Scene (a planning-only helper that fills the prompt box), and Rewrite Scene (an explicitly confirmed fresh generation of the visible draft) workflows.
- Rewrite Scene keeps the existing draft if canceled, stopped, or generation fails.
- Editable author direction supplied by Prepare Scene.
- Open and save manuscript drafts and scenes, including ODT support.
- Browse and save the selected scene.
- Revise or replace an explicitly selected passage with a preview/accept workflow.
- GitHub sync for a selected novel, with visible status feedback.

Do not infer that every feature has been freshly tested on the author's laptop. Record verification separately as local, CI, or GitHub evidence.

## Visible runtime status display

**Implemented:** November 7, 2026  
**Verification:** Focused unit tests added; local GUI behavior and the full suite still need confirmation after pulling.

The Writer now has a prominent **Current Activity** panel directly below the model selectors. It displays:
- Current task (Prepare Scene, Write, Continue, Rewrite Scene, passage revision, New Session, manual load, or saved-scene state update).
- The model assigned to that task.
- Runtime state: Loading, Ready, Generating, Finished, Stopped, Error, or Not loaded.

The panel does not claim a selected model is loaded merely because it is selected. It shows Loading until the model loader returns, then Generating when the generation call begins. When idle it reports the model whose process is actually alive, or Not loaded. The detailed bottom status strip remains in place for messages and explanations.

The Prepare Scene unit-test fixture now models the live subprocess that the two-model routing code expects, and its assertions use the planner-specific status wording and the automatic Writer reload behavior.

After pulling, check three things on the author's laptop:
1. Prepare Scene shows Qwen as Loading, then Generating, then Finished.
2. Write and Rewrite Scene show Gemma as Loading when switching from Qwen, then Generating, then Finished.
3. After generation, the panel identifies the model that remains loaded. If the process is stopped or fails, it must not show Ready.

## Generic manuscript prompt and character-context cleanup

**Implemented:** November 8, 2026  
**Verification:** Both GitHub Actions workflows passed on source/test commit `b7166475842c3e452ef002c6fb4290caa9938fd1`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/42576439788) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/42576439836). Local verification of this cleanup is pending.

The shared Writer no longer appends a dialogue-first, Computer-specific, or other narrative-style instruction to manuscript requests. Its manuscript prompt helper passes the author's prompt through unchanged. The general Continue behavior remains: develop the passage over several connected paragraphs and reach a natural pause.

Character-card names and facts are loaded from the selected novel's own Story Bible. Registered card names are reference data only, not a complete cast list or a restriction on introducing characters. The shared character-context prompt no longer contains a blanket romance/attraction instruction. It retains general factual guidance for interpreting recorded character details and areas of expertise.

After a scene is saved, the active Writer's ending-state update uses neutral story-thread language. It no longer assumes a crisis, investigation, crew, or technical setting. It updates only the supported ending-state fields from the accepted prose.

Novel-specific characters, locations, relationships, plot developments, and any special writing rules belong in that novel's own project files. They are not added to shared Python prompts.

## Author intent and scene-to-scene flow

**Implemented:** November 9, 2026  
**Verification:** Focused regression tests updated. Both GitHub Actions workflows passed on commit `48e0edff4bad52aa1bf3a039dc7c8cb2764465c5`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/42759403074) report 710 passed and 77 subtests passed; [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/42759402861) report 710 passed. Local pull and live laptop retest are pending.

The active Prepare Scene prompt no longer requires a `Natural endpoint:` field or a prescribed final beat. It asks for a concise direction expressing the author's intent. Events the author explicitly asks to happen remain intended events; the Writer is free to decide how they unfold and where the scene ends.

The active Writer no longer appends endpoint-enforcement instructions, and Rewrite Scene no longer preserves an endpoint as a mandatory boundary. Continue also no longer asks the prose to stop at an imposed natural pause.

The full preceding saved scene remains available as context. The handoff now asks for a natural continuation of the same story without requiring the next scene to begin in the very next second or remain in the same place. Time, place, focus, and pacing can move when the story calls for it.

**Author-approved principle:** The author's direction determines what the author wants to happen. The Writer determines how it happens and where the scene ends. The only scene-to-scene requirement is that the novel continues coherently from what actually happened.

## Previous-scene continuity in Prepare Scene

**Implemented:** November 9, 2026  
**Verification:** Focused regression tests are included, and both GitHub Actions workflows passed on commit `c96281a191fb08e1438fc5b5c09b6a829b216bfb`. The five-scene live trial below evaluated manuscript continuation, not Prepare Scene's planner output.

When a previous saved scene has text, Prepare Scene gives the planner the full scene and asks for a direction that continues the same story naturally. The next scene may begin later or elsewhere when that makes sense; it is not required to begin in the next second or repeat the previous scene's final action.

This guidance is generic. It does not add story, character, relationship, or genre assumptions, and it is not added to an opening-scene prompt with no previous ending.

## Full previous-scene context

**Implemented:** November 9, 2026  
**Verification:** Regression tests cover long saved scenes in both Prepare Scene and manuscript writing. Both GitHub Actions workflows passed on commit `c96281a191fb08e1438fc5b5c09b6a829b216bfb`. A five-scene live manuscript trial was completed on the laptop; its behavioral findings and limits are recorded below.

Prepare Scene and manuscript Write/Rewrite now receive the complete text of the immediately preceding saved scene. The previous 1,800-character planner excerpt and 2,000-character Writer excerpt have been removed. The existing target-scene selection still determines which saved scene is considered immediately preceding; no older scenes or future scenes are added.

This gives the planner and Writer the whole immediate scene, including details established before its final paragraphs. The context remains limited to one previous scene rather than the entire manuscript. Very long scenes can still consume a substantial portion of the configured model context window.

## Five-scene live manuscript trial — November 9, 2026

**Test setup:** A disposable test novel was reset and five consecutive scenes were generated and reviewed. No code, prompt, or model-setting changes were made during this test. The test was intended to evaluate the new previous-scene context behavior; it did not capture the actual runtime prompt, so observed prose cannot prove exactly how much prior-scene text the model received.

**Observed results:**
- **Scene 1:** Readable opening and useful character introduction. The requested porch admission was rendered as Mara's private thought rather than spoken to Noah, so the endpoint was only partially met.
- **Scene 2:** Continued from the extension-cord situation and gave Noah a response hook for the prior scene. It closely restated the direction's psychological interpretation in explanatory narration. It stopped before the requested exchange and Noah's admission, so the endpoint was missed.
- **Scene 3:** Continued the unfinished exchange from Scene 2, introduced a fountain/pump problem, and reached the approaching-footsteps interruption. Direction interpretation still appeared explicitly in the narration.
- **Scene 4:** Did not continue from Scene 3's approaching footsteps. It restarted the pump-inspection moment, omitted the planned awkward wave, introduced an unrequested hand touch, and then brought in Mara's aunt. The endpoint was reached, but chronological continuity failed.
- **Scene 5:** Carried forward the aunt, pump setup, and invented hand touch, then took Mara away with her tools. The endpoint was reached, although the physical staging was unclear and the invented romantic beat received more emphasis than the original progression required.

**Run-level findings:**
- Natural endpoints were substantially reached in 3 of 5 scenes. Scenes 1 and 2 stopped short of their requested final interactions.
- The Writer carried useful immediate details and unfinished dialogue across some scene boundaries. That is evidence of useful carry-over, not proof of the exact previous-scene prompt payload.
- Chronological continuity was inconsistent. Scene 4 is the clearest failure because it skipped the approaching footsteps at the end of Scene 3 and returned to an earlier activity.
- Scene directions were repeatedly converted into explanatory narration instead of being dramatized through behavior and dialogue. Scene 2 showed the strongest example.
- The Writer also accepted and amplified its own invented romantic/physical detail from Scene 4 into Scene 5, illustrating that continuity can preserve an invention even when it shifts the intended pacing.

**Conclusion / next discussion:** Keep the full immediately preceding saved scene context. This trial does not show that the change fixed continuity or direction echoing. The next issue to examine is how scene directions are translated into manuscript prose, while preserving the author's intended beats without turning the direction itself into narration. Do not add more shared rules or change prompts/models based only on this single run. Discuss the next focused change with the author first.

## Lean model context update

**Implemented:** November 7, 2026  
**Verification:** Both GitHub Actions workflows passed on commit `1c5ad3c9d2b633ae9a08a3941227f414e4cc0484`: Python Tests reported 697 passed and 77 subtests passed; StoryBuilder tests reported 697 passed. Tony's local pull and full-suite run remain pending.

The Writer and Prepare Scene prompt builders now use a deliberately small context package instead of forwarding whole Story Bible sections.

For manuscript writing, the model receives:
- The author's scene direction and any additional rewrite guidance.
- A short time anchor and current-situation summary (maximum 600 characters).
- Brief facts for characters actually named in the request or saved scene cast: gender, role, occupation/department, skills, and short personality/voice notes.
- Short saved details only for locations named in the request. No complete location allowlist is attached.
- The full text of the immediately preceding accepted scene.

For Prepare Scene, the planner receives:
- The novel title, premise and setting (each capped at 600 characters).
- A short current-situation note, time anchor, current location/cast and up to two unresolved questions when they match the requested scene.
- Brief facts for relevant characters, not complete character biographies.
- The full text of the immediately preceding saved scene.

The automatic prompt does not dump the complete canon-rules list, full location allowlist, entire profile library, generic scene-craft/media-device instructions, or full character biographies into every request. It adds only the genre and audience profile notes selected for the active novel, plus the separate explicit-content permission. The underlying Story Bible and character-card files remain the detailed source of truth.

This is a simple relevance reduction, not a new rules engine. Unknown details remain creative space. The app should not turn every gap into a prohibition or add new permanent rules because a draft needs correction.


## Model-role trial — November 7, 2026

**Implemented for local testing:** separate model assignments for scene planning and manuscript writing.

- Prepare Scene defaults to Qwen3.5-4B when that model is present.
- Write, Continue, Rewrite Scene, AI passage revision, and New Session default to the Gemma 4 E4B file when present.
- The choices are configurable in the Writer UI and saved under the user's config directory, not in Git.
- Only one model process is loaded at a time. Selecting an action that needs the other role stops the existing process and loads the selected role's model.
- llama.cpp is launched with `--reasoning off` and explicit `--jinja` so chat-template-dependent models such as Qwen3.5 use their GGUF metadata template.
- This is an initial integration trial, not a permanent model-quality verdict. Compare actual Prepare Scene and manuscript results in The Long Way Home before making further prompt or UI changes.

The author-approved creative philosophy for this trial:
- Established story facts are the foundation, not a ban on inventing details.
- Unwritten details are creative space. Plausible new technology, locations, complications, character interactions, and plot developments are welcome.
- Characters should generally act within their established personalities and expertise, while still being allowed to surprise the reader.
- Protect basic survival logic and major established story foundations, but do not overload prompts with rigid prohibitions or checklists.
- The author chooses which creative developments become accepted story canon.

## Working agreement

- The author prefers one focused change at a time and discussion before code or model changes.
- Keep the writing process flexible. Avoid oversized prompts, rigid formulas, or micromanaging scene prose.
- The planner develops possibilities and scene directions; the writer develops approved directions into manuscript prose. ChatGPT reviews direction and generated prose for continuity when asked. Do not write manuscript scenes unless explicitly requested.
- Do not change a novel's prose, story state, canon, or package data from the Writer app handoff.
- After an agreed app milestone, update this handoff and verify the commit.

## Verification status

- The two-model planner/writer routing and Current Activity panel were locally verified. The full local suite passed 696 tests before this lean-context update.
- Lean-context commit `1c5ad3c9d2b633ae9a08a3941227f414e4cc0484` passed both GitHub Actions workflows: Python Tests reported 697 passed and 77 subtests passed; StoryBuilder tests reported 697 passed.
- Tony's local pull and full-suite verification are still pending.


## Current status

The lean-context update is locally verified: Tony pulled it and the full suite passed (697 tests and 77 subtests). The latest genericity cleanup removes the app-wide Computer/dialogue instruction, complete-roster and blanket romance constraints, and crisis/investigation assumptions from the active post-save end-state prompt. Both GitHub Actions workflows passed on commit `82a5c795b66b442f06edd53d4cd9f14116d4109c`; Tony still needs to pull and locally test this cleanup. The November 9 scene-flow update removes mandatory natural endpoints from Prepare Scene and the active Writer while preserving author-requested events and full preceding-scene context. Both GitHub Actions workflows passed on commit `48e0edff4bad52aa1bf3a039dc7c8cb2764465c5` (710 tests in each workflow; Python tests also report 77 subtests passed). Local pull and live laptop retest are pending. The same five-scene Summer at Willow Bay test package is reset to its clean Chapter 1, Scene 1 starting point for a repeat run. Prepare Scene's retry-direction behavior remains a separate open issue.



## Generic genre, audience, and content profiles

**Implemented:** November 8, 2026  
**Verification:** Focused unit tests were updated. GitHub Actions and local laptop verification are pending.

Reusable Markdown profiles live in the shared application repository:
- `profiles/genres/*.md` supplies the available genre choices and their concise writing guidance.
- `profiles/audiences/*.md` supplies audience choices and age-appropriateness guidance.
- Each file uses its first `# Heading` as the display name; the remaining text is the guidance given to the model. Add a file to extend the available options without editing Python.

The Story Bible stores only the selected genre and audience labels, moods, and the existing `explicit_adult_content` boolean in that novel's own `story_bible.json`. Profile text stays in the shared app resources and is never copied into a novel package.

Both Prepare Scene and manuscript generation receive only the profiles selected in the active novel. Children's guidance explicitly excludes profanity, sexual content, and graphic violence. Middle Grade and Young Adult have their own age-appropriate guidance. The Explicit Adult Content setting remains independent: selecting Adult does not enable it, and when enabled it grants permission rather than requiring explicit material.

The selected-project prompt helper reads the currently selected novel's Story Bible at generation time. Novel-switch session isolation has since been implemented; see the section below.


## Novel-switching session isolation

**Implemented:** November 9, 2026  
**Verification:** Focused regression tests and both GitHub Actions workflows passed on commit `aac2d380ebefeedc24b4863f73b3051995dc591a`. Local GUI verification is pending.

The Writer opens with no novel selected. Refreshing the library preserves a still-valid selection, but does not automatically choose the first available novel.

When the selected novel's path changes, the Writer clears the two novel-specific direction fields and pending Prepare Scene state, then clears the live llama.cpp conversation in a background task. Refreshing the same selected novel does not clear the model session.

The visible manuscript draft, current file path, selected source-scene path, and saved-text baseline are preserved. This prevents switching projects from silently discarding an open manuscript or changing its save tracking.

If the model conversation cannot be cleared and confirmed, StoryBuilder stops the model and marks it unloaded. The next writing task must load a fresh process, rather than risking use of the previous novel's history.

Regression tests cover blank startup, switching projects, refreshing the same project, switching without a loaded model, preserving manuscript contents and file tracking, and stopping the model when history cannot be cleared.


## Planner-to-writer diagnostic trace — November 9, 2026

**Implemented:** The scene trace now records both halves of a prepared scene: the exact Prepare Scene input and raw planner response, followed by the final direction present in the prompt box when the author presses Write and the Writer's complete assembled prompt and generated response. Trace sessions label planner and writer roles separately, including when both roles use the same model file.

The planner trace remains in memory between Prepare Scene and manuscript generation. It is saved locally and uploaded to the existing private, single-file trace repository only when the prose-generation attempt finishes. A retry for the same prepared scene appends another planner attempt to that scene trace. Changing novels, preparing a different destination, or abandoning a planner result discards the unused in-memory trace without uploading it.

This change is diagnostic only. It does not modify planner or writer prompts, model selection, context assembly, prose generation, novel files, or the one-file overwrite retention policy.

**Verification:** Focused tests were added for separate planner/writer session labels and matching-scene trace handoff. GitHub Actions verification is pending.


## Reader-first working standard — November 9, 2026

This is the author's current, preferred approach for developing and reviewing manuscript prose. It takes priority over earlier trial methods that emphasized structural checks or beat-by-beat scoring.

**Default review mode:** Read the scenes as an ordinary reader, without consulting scene directions, planner output, prompts, or traces. Judge whether the story flows naturally from one scene to the next, whether events and character behavior make sense in context, and whether the people and interactions hold the reader's interest.

The reader's experience comes before the underlying story "bone structure." Preserve coherence where a reader would notice a contradiction, repeated event, confusing transition, unearned character shift, or break in immersion. Do not treat every scene as a checklist or a structural audit. Scene directions express author intent; they are not a scorecard for ordinary reader reviews.

Fiction does not require every technical, scientific, or logistical detail to be perfect. Allow imaginative license and ordinary imperfection. Correct inaccuracies or inconsistencies when they distract from the story or damage the reading experience, not simply because a more exact version exists.

Let scenes find their own length, focus, and ending. Do not restore hard endpoints or force every requested beat into a prescribed structure. The next scene should continue coherently from what actually happened, even when time, location, or focus changes.

Stylistic tendencies such as overwritten description, repeated thematic explanation, fast romantic progression, and minor realism questions are observations, not automatic defects. Recommend edits when they materially improve the reader's experience; do not chase perfection.

Trace inspection and direction-adherence analysis remain useful, but they are separate diagnostic modes. Use them when the author asks how a prompt or workflow behaved, or when a technical issue needs investigation. Do not let technical diagnostics override the default reader-only review.

The five-scene *Summer at Willow Bay* retest was reviewed in reader-only mode. Overall, the story flowed coherently from Mara's arrival through her growing involvement in Willow Bay and her developing connection with Noah. The clearest reader-facing continuity blemish was Scene 5 replaying the wagon being freed after Scene 4 had already resolved it. Repeated thematic explanation, ornate prose, and somewhat quick physical familiarity were lesser editorial observations. The test supports keeping scene endings flexible; it does not justify restoring forced endpoints. No code or prompt changes were approved by this review.


## Selected-novel writing preferences — implemented November 10, 2026

Before manuscript generation, the Writer reads the `writing_preferences` field from the currently selected novel's `story_bible.json`. If it contains non-empty text, that text is appended under **HOW THIS NOVEL SHOULD READ** as flexible, novel-specific creative guidance.

- Applies to manuscript generation flows that use the shared creative-direction context, including Write/Continue/Rewrite and passage revision.
- Only the currently selected novel's value is used. Switching novels switches the preferences; one novel's value is not reused for another.
- The Planner / Prepare Scene prompt was initially unchanged; as of November 11, it also receives the selected novel's writing preferences as flexible guidance.
- Existing novels without this field continue to work and receive no additional writing-preference guidance.
- An empty field adds no extra style guidance.
- The preference is author-written and stored in the novel's own Story Bible. No style is hard-coded globally.

**Verification:** Both GitHub Actions workflows passed on commit `4fbeea85d80d95dbe125b5c18f2415e5b8584e49`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/42783731649) report 714 passed and 77 subtests passed; [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/42783731793) report 714 tests passed. Local pull and live laptop testing remain pending.

## AI-assisted story planning expansion — discussion only, November 10, 2026

**No code, prompt, or model changes have been approved.** This is a design note for a possible future expansion of the existing two-model workflow.

The current routing already assigns Qwen to Prepare Scene/planning and Gemma to manuscript prose. The author does not want a new model arrangement or simultaneous model loading. The proposed change is to broaden Qwen's role from generating an individual scene direction into an interactive planning partner that helps the author:
- Capture free-form brainstormed ideas without requiring the author to write a formal outline.
- Organize ideas as confirmed, proposed, open, or needing placement.
- Arrange approved ideas into an overall story roadmap and broad chapter roadmaps.
- Prepare a concise, chapter-specific information packet for Gemma.

Gemma should receive the current chapter's broad direction, the current story situation, only relevant character information and established facts, necessary continuity from earlier events, and important boundaries that genuinely matter now. Do not dump the whole novel, unrelated older chapter material, or future revelations into the manuscript-writing prompt. Retain immediate preceding-scene context where needed for coherent continuation.

The roadmap should steer the story without scripting scenes. Avoid checklists, mandatory beat sequences, fixed scene counts, forced endpoints, and repeated explanations of established character traits. Gemma retains freedom over scene structure, dialogue, pacing, and natural endings. Protect approved story direction and important canon without micromanaging creative connective tissue.

Qwen and Gemma should continue loading sequentially, one model at a time, to fit the author's 16 GB laptop. Project files, not model conversation history, hold persistent planning memory. Because small models may misorganize or misunderstand ideas, Qwen's suggestions must remain proposals until the author approves them.

**Next step:** discuss the workflow and data flow before coding. Inspect existing Prepare Scene/context assembly first; do not rebuild the routing or add a third model. Keep all novel-specific roadmaps and idea-bank content inside each novel's own project files.


## Story Bible canon and relationships in planner/writer context — November 11, 2026

A live *Taken at Dusk* opening test revealed that the app could load and save character cards correctly while still omitting important fields from model context. The compact character profile left out age and relationship status. The selected novel's Story Bible `relationships` and `canon_rules` fields were not included in Prepare Scene or manuscript generation, and current-state continuity notes were not passed through. This allowed the model to invent an incorrect age, treat a deceased character as alive in the present, and jump prematurely to later plot events.

**Focused fix committed:** `798c3e94e83d84249779ee73c4d5005420b5902f`
- Compact character references now carry age and relationship status (blank stays explicitly “Not established”).
- Prepare Scene receives the selected novel's canon facts, relationship reference, and flexible writing preferences.
- Manuscript generation receives the selected novel's canon facts and relationship reference alongside the existing creative preferences.
- Current-state continuity notes reach both planner and writer.
- The prompt labels make clear that relationships are reference information, not a cast checklist, and canon facts are anchors rather than scene-by-scene instructions.

No validator was added. The intent is to protect a few established facts while leaving ordinary creative decisions to the model.

**Automated verification:** Python tests passed (716 passed, 77 subtests passed); StoryBuilder tests passed (716 passed) on commit `798c3e94e83d84249779ee73c4d5005420b5902f`. [Python workflow](https://github.com/tony21675/StoryBuilder/actions/runs/42985828904) · [StoryBuilder workflow](https://github.com/tony21675/StoryBuilder/actions/runs/42985828913).

The code update is on the existing branch. Local app pull and live generation tests remain pending.


## One generation, one scene — implemented November 11, 2026

Prepare Scene's planning prompt now keeps its requested direction within the selected destination scene. It should leave distinct later time/place setups for a separate Prepare Scene request unless the author explicitly asks to combine them in the same scene.

Every manuscript Write, Continue, and Rewrite Scene request receives a **ONE-SCENE SCOPE** immediately before creative preferences are added and before the prompt trace is claimed or created. The scope identifies the selected Chapter/Scene when available, keeps one generation within one scene, and leaves later distinct setups for separate generations. It explicitly preserves natural scene endings and does not introduce forced endpoints, required beats, a scene-count limit for the chapter, or validation.

**Prompt trace and GitHub upload remain active and unchanged.** Tracing remains enabled by default. The trace still records the planner input/response, the author's final prepared direction, the fully assembled Writer prompt (including the new scene scope), and the Writer response. It is saved locally and uploaded after the generation attempt to the existing private, single-file GitHub trace repository as the latest `prompt_trace.json`. Upload failure does not discard the local trace.

**Regression coverage added:** planner prompts stay within one destination scene; Writer generations include the selected Chapter/Scene scope; and the existing trace tests continue to verify local saving, GitHub upload attempts, and retention of the local trace when upload fails. CI verification and the author's local pull/live generation test are pending.

## Author-required beats and Qwen-selected additions — implemented November 11, 2026

Prepare Scene's Planner request now tells Qwen to return separate sections for **AUTHOR-REQUIRED BEATS** and **QWEN-SELECTED ADDITIONAL BEATS**.

- Any concrete event, action, or moment explicitly requested in the author's direction is required in the selected scene. Qwen must preserve every requested event and cannot omit, soften, replace, or move it to a later scene.
- Qwen independently chooses any number of additional beats it believes would strengthen the scene, including none. There is no quota or cap.
- Gemma receives both the structured Qwen direction and the original Author's Direction as a separate authoritative input. Gemma must enact the author's explicit requested events in the scene, not merely mention them, imply them off-page, or defer them. Qwen's additions are carried into the prose naturally and must not displace author-required events.

The original direction is retained for the matching prepared novel/Chapter/Scene even after the UI clears the Author's Direction box. Retrying Prepare Scene for that same destination carries the original required direction forward and can append newly typed author direction. It is cleared when the author switches scene/novel or saves the new scene, preventing cross-scene leakage.

**Trace preservation:** No trace or uploader behavior was removed. The final original author-required direction is recorded in the planner-to-writer trace event. The fully assembled Writer prompt (including the original direction, Qwen's output, and scene scope) is captured by the existing trace, saved locally, and uploaded after the generation attempt to the existing private, single-file GitHub trace repository. The latest-trace-only repository behavior and local-copy retention on upload failure remain unchanged.

**Regression coverage added:** author-priority prompt text; Qwen's uncapped optional number of additions; persistence of author-required events across retries; matching novel/scene scoping; Writer prompt inclusion; and trace-event capture.

**Automated verification:** Both workflows passed on source/test commit `38be429bf89a7947262d6795b327f4b88f871f31`:
- [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/42996117903): 722 tests passed.
- [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/42996117774): 722 passed and 77 subtests passed.

The author's local pull and live Writer test are still pending.

## Expanded Prepare Scene Planner context — November 11, 2026

**Implemented:** Planner-only context expansion and beat-classification clarification.  
**Verification:** Both GitHub Actions workflows passed on commit `714942935328836410a9efcb67f297ba72527f6f`: [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/43032005816) report 723 tests passed; [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/43032005782) report 723 passed and 77 subtests passed. Local pull and live Qwen test are pending.

Prepare Scene now gives Qwen:
- Every registered character card in detailed reference form, regardless of which names appear in the current direction or previous scene.
- All Story Bible canon-rule and relationship entries, expanded premise and setting context, and all saved location names/details as non-restrictive background references.
- Explicit guidance to preserve households, residences, exact relationships, occupations and work-time markers, and ownership/wearing/carrying of important possessions. Chosen-family language must not be mistaken for literal parentage or co-residence. Domestic scenes should distinguish residents from visitors.
- Explicit time semantics: preserve the author's intended report/arrival time, meeting time, and shift start/end rather than silently reinterpreting them.

All character and location information is reference context, not a roster checklist or required itinerary. Qwen remains free to choose the scene's cast and invent plausible new places and details when consistent with canon.

Beat classification is also clearer: only events directly requested in the current Author's Direction may be marked AUTHOR-REQUIRED. Qwen's own ideas and inferred connective actions belong in QWEN-SELECTED ADDITIONAL BEATS. When a current Author's Direction accompanies a retry/refinement, it is the authority for required-beat classification rather than old labels in the previous prepared direction.

This change affects only Prepare Scene and its reference-context builder. It does not change Gemma's prose prompts or generation behavior, the original-author-direction handoff, one-scene scope, or any prompt trace and upload behavior.
