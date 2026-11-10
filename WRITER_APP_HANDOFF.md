# Writer App handoff

**Updated:** November 9, 2026  
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
**Verification:** Focused regression tests updated. GitHub Actions verification and local laptop testing are pending.

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

The lean-context update is locally verified: Tony pulled it and the full suite passed (697 tests and 77 subtests). The latest genericity cleanup removes the app-wide Computer/dialogue instruction, complete-roster and blanket romance constraints, and crisis/investigation assumptions from the active post-save end-state prompt. Both GitHub Actions workflows passed on commit `82a5c795b66b442f06edd53d4cd9f14116d4109c`; Tony still needs to pull and locally test this cleanup. The November 9 scene-flow update removes mandatory natural endpoints from Prepare Scene and the active Writer while preserving author-requested events and full preceding-scene context. Focused tests have been updated; CI and local verification are pending. The same five-scene Summer at Willow Bay test package is reset to its clean Chapter 1, Scene 1 starting point for a repeat run. Prepare Scene's retry-direction behavior remains a separate open issue.



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
