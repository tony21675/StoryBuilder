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

- Load and use a local language model for manuscript generation.
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

## Working agreement

- The author prefers one focused change at a time and discussion before code or model changes.
- Keep the writing process flexible. Avoid oversized prompts, rigid formulas, or micromanaging scene prose.
- Gemma writes; ChatGPT reviews direction and generated prose for continuity when asked. Do not write manuscript scenes unless explicitly requested.
- Do not change a novel's prose, story state, canon, or package data from the Writer app handoff.
- After an agreed app milestone, update this handoff and verify the commit.

## Verification status

- The focused handoff-backup test module passed locally on November 7, 2026 (2 tests).
- After the character-card context update, both GitHub Actions workflows passed on commit `6787b8f601f82e2358a146fead6d148040c51db4` (November 7, 2026). Python Tests reports 682 passed and 77 subtests passed; StoryBuilder tests reports 682 tests passed.
- The previous full local suite on Tony's laptop passed 681 tests before this character-card update. Re-run the full suite locally after pulling the latest StoryBuilder commit.


## Current status

The character-card context fix is committed and CI-verified. After Tony pulls it locally, test Prepare Scene and Write against The Long Way Home cards to confirm that the six leads' documented expertise is available to the model. The separate Prepare Scene retry-direction issue remains open.
