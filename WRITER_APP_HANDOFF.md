# Writer App handoff

**Updated:** November 7, 2026  
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

## Character-card context update

**Implemented:** November 7, 2026

The shared `build_character_card_context_prompt` now supplies the character information that was previously being left out of prompts:
- Role and occupation / department.
- Skills, expertise, specialties, and technical skills.
- Background and experience.
- Training, qualifications, and certifications when present.
- Personality, interests and hobbies, longer descriptive notes, and established relationships.
- Existing personal-reference fields such as age, gender, orientation, and relationship status remain available.

This shared formatter is used by both Prepare Scene and Write. Prepare Scene includes all detailed cards when no scene cast has been saved, or the saved cast when one is available. Write includes detailed cards for characters identified by name in the writing prompt or supporting scene context, with saved scene-cast names also used when present.

The prompt gives one concise distinction: documented professional fields ground what a character knows and can do; hobbies are not professional qualifications; ideas outside a specialty may be raised as questions or hypotheses rather than treated as established expertise.

The context-budget compactor was also updated to preserve skills, expertise, specialties, background, experience, hobbies, interests, training, qualifications, certifications, and description fields when it needs to shorten large character-card payloads.

No novel character cards, Story Bible files, current story state, accepted manuscript scenes, or model files were changed by this StoryBuilder update.

**Separate known issue:** Prepare Scene still does not pass its existing generated scene direction back into the planner on retry. That is a distinct follow-up change and was not part of this character-card fix.

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

- Separate planner/writer model assignment and sequential model switching are implemented on the active branch. CI verification is pending for this update.

- The focused handoff-backup test module passed locally on November 7, 2026 (2 tests).
- After the character-card context update, both GitHub Actions workflows passed on commit `6787b8f601f82e2358a146fead6d148040c51db4` (November 7, 2026). Python Tests reports 682 passed and 77 subtests passed; StoryBuilder tests reports 682 tests passed.
- The previous full local suite on Tony's laptop passed 681 tests before this character-card update. Re-run the full suite locally after pulling the latest StoryBuilder commit.


## Current status

The character-card context fix is committed and CI-verified. After Tony pulls it locally, test Prepare Scene and Write against The Long Way Home cards to confirm that the six leads' documented expertise is available to the model. The separate Prepare Scene retry-direction issue remains open.
