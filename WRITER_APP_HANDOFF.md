# Writer App handoff

**Updated:** November 8, 2026  
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
- Editable scene direction and natural endpoint supplied by Prepare Scene.
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

## Dialogue-first manuscript guidance

**Implemented:** November 8, 2026  
**Verification:** Tony's first local run after pulling the changes reported 699 passed and 1 failed. The failure was an outdated test expectation that still compared raw user prompts rather than the prompts with the new automatic guidance appended. That test was corrected; a fresh local run is pending.

Every manuscript-writing request now receives a compact automatic instruction to show important work through direct exchanges instead of summary narration. It also makes the Computer an explicitly speaking participant: when it completes a diagnostic, calculation, scan, or requested task, it should report important findings aloud in natural dialogue. Screens may support the spoken report but must not replace it.

The instruction is appended to Write, Rewrite Scene, Continue, and passage-revision prompts. It is not added to Qwen's Prepare Scene request and does not change the Story Bible, scene direction, or manuscript files. It does not force the Computer into scenes where it is not relevant.

The Writer's Continue instruction now asks for a complete continuation over several connected paragraphs, developing the moment to a natural pause rather than stopping after one paragraph. This is guidance to the model, not a guaranteed output-length control.

Character-card context now explicitly tells the models to use each character's recorded gender for pronouns, never infer gender from a name, and avoid assuming when gender is not recorded. The existing compact context already passes the card's Gender field; this addition makes its importance clear, including for names that can belong to people of different genders.

## Lean model context update

**Implemented:** November 7, 2026  
**Verification:** Both GitHub Actions workflows passed on commit `1c5ad3c9d2b633ae9a08a3941227f414e4cc0484`: Python Tests reported 697 passed and 77 subtests passed; StoryBuilder tests reported 697 passed. Tony's local pull and full-suite run remain pending.

The Writer and Prepare Scene prompt builders now use a deliberately small context package instead of forwarding whole Story Bible sections.

For manuscript writing, the model receives:
- The author's scene direction and any additional rewrite guidance.
- A short time anchor and current-situation summary (maximum 600 characters).
- Brief facts for characters actually named in the request or saved scene cast: gender, role, occupation/department, skills, and short personality/voice notes.
- Short saved details only for locations named in the request. No complete location allowlist is attached.
- Up to 2,000 characters from the ending of the immediately preceding accepted scene.

For Prepare Scene, the planner receives:
- The novel title, premise and setting (each capped at 600 characters).
- A short current-situation note, time anchor, current location/cast and up to two unresolved questions when they match the requested scene.
- Brief facts for relevant characters, not complete character biographies.
- Up to 1,800 characters from the previous scene's ending.

The automatic prompt no longer dumps the complete canon-rules list, full location allowlist, full creative-direction settings, generic scene-craft/media-device instructions, or full character biographies into every request. The underlying Story Bible and character-card files are unchanged and remain the detailed source of truth.

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

The lean-context update is locally verified: Tony pulled it and the full suite passed (697 tests and 77 subtests). Follow-up Writer changes now make Computer findings explicitly spoken, use recorded character-card gender, and ask Continue for several connected paragraphs. The new regression tests, local run, and CI run are pending. Tony needs to pull these changes and run the suite before testing another scene. Prepare Scene's retry-direction behavior remains open.

