# Story Bible App handoff

**Updated:** November 6, 2026  
**Application:** Story Bible  
**Repository:** `tony21675/StoryBuilder`  
**Active/default branch:** `redesign/simplified-writing-workflow`  
**Local repository:** `~/Documents/StoryBuilder`

## Purpose and boundary

The Story Bible is a separate application from the Writer. It has its own application file and launcher, but both applications currently share the same GitHub code repository. The Writer's technical instructions are in [WRITER_APP_HANDOFF.md](WRITER_APP_HANDOFF.md).

The Story Bible App edits and maintains reference information inside an individual novel package. That novel package remains the source of its canon, character cards, locations, and scene state. This technical handoff is not a novel's canon document.

## Launch and synchronization

- Main application file: `story_bible_app.py`
- Launcher: `bash start_story_bible.sh`
- The launcher runs the shared `sync.sh start` helper before opening the app. It safely fast-forwards the current StoryBuilder branch and restores any local app-repository changes it temporarily stashed.
- Both apps share `redesign/simplified-writing-workflow`, currently the only StoryBuilder branch and GitHub default. Keep this branch name for now: the sync helpers refuse `main`, and workflow/test configuration still references the current branch. Do not rename it unless all those protections and references are deliberately migrated and tested.
- **Sync Selected Novel to GitHub** is a separate, explicit action for the selected novel package. It previews the repository, branch, remote, local changes, and commits, then requires confirmation. It only syncs that novel repository, not StoryBuilder code. Diverged history, unresolved Git operations/conflicts, missing remotes/upstreams, and protected local secret/encrypted assets block the sync.
- Do not force-push, reset, or overwrite local novel data to resolve a sync problem.

## Local handoff safety copies

- The shared `backup_handoffs.py` / `builder/handoff_backup.py` utility refreshes `~/Documents/Project_Handoff_Backups` by default.
- It mirrors the Writer and Story Bible handoffs, StoryBuilder index, The Long Way Home handoff and story direction, and the Taken at Dusk handoff/reference documents when present locally.
- The launchers refresh the mirror after the app-code pull. The selected-novel sync refreshes it again after a successful push. It can also be run manually with `python3 ~/Documents/StoryBuilder/backup_handoffs.py`.
- It copies only named Markdown handoff/planning documents. It does not copy manuscripts, model files, credentials, encrypted files, or secret-letter assets; it does not delete previous local copies when a source is missing.
- The GitHub repositories remain authoritative. The separate local mirror is an emergency backup.

## Application responsibilities and functionality recorded

The app manages novel setup and reference material, including:
- Novel title, premise, setting, creative direction, genre, and audience.
- Canon Rules stored in the novel package's `story_bible.json`.
- Character cards, edited through plain-English fields and saved as structured data.
- Location definitions through the Location Manager.
- Creation and editing of story-bible information for the selected novel.
- Explicit, previewed synchronization of the selected novel repository.

The individual novel package remains the source of that novel's canon. Use that novel's `story_bible.json`, character-card files, location definitions, current state, and accepted manuscript. Do not treat this technical handoff as a substitute.

## Previously reported behavior to verify before further development

The following issues were reported during earlier use. Their current status has not been verified, so do not describe them as fixed or currently reproducible without checking:
- A save popup once reported a `story_role` error.
- The main character list did not always refresh immediately after a card was saved; a restart appeared to refresh it.
- Stale cached character-card text was a concern.

Other improvements previously reported include plain-English character fields, optional blank fields, a character dropdown, location management, and a darker interface. Verify behavior in the live local app before changing or claiming anything.

## Verification status and working agreement

- No fresh local test run on the author's laptop has been recorded after adding the handoff-backup utility. Run the focused backup tests and full test suite after pulling.
- Discuss app or data-model changes before editing.
- Make one focused change at a time.
- Do not silently change the schema or rewrite a novel's existing cards, canon, or locations.
- Preserve local package changes and inspect Git status before any sync.
- Update this handoff after each agreed Story Bible App milestone.

## Current status

Story Bible is being maintained as a separate app with a shared code repository. The current focus is preserving project records and handoffs reliably, not changing the app's story-data model.
