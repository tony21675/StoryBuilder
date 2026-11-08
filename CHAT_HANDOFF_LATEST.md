# Writing project handoff index

**Updated:** November 7, 2026

This index covers writing projects only. Each application and novel has one authoritative handoff. The project repositories remain the source of truth; local mirror copies are maintained separately.

## Active handoffs

### Writing applications

- [Writer App](WRITER_APP_HANDOFF.md) — Minimal Writer code, launch, sync behavior, local handoff backups, features, known app issues, and testing.
- [Story Bible App](STORY_BIBLE_APP_HANDOFF.md) — the separate Story Bible application, its code, launch, sync behavior, local handoff backups, known issues, and testing.

These are two separate applications with separate launchers. They share the `tony21675/StoryBuilder` repository and its single current branch, `redesign/simplified-writing-workflow`. That branch is the GitHub default and the only branch. Keep its name for now: sync helpers explicitly block `main`, and some workflow/test triggers still refer to this branch. There is no additional branch clutter to clean up.

### Novels

- [The Long Way Home](https://github.com/tony21675/The-Long-Way-Home/blob/main/CHAT_HANDOFF_LATEST.md) — current novel priority. Chapter 1 Scenes 01–15 are accepted. Chapter 2 Scene 01 is saved and accepted; Scene 02 is next. The current broad author-approved direction is in [STORY_DIRECTION.md](https://github.com/tony21675/The-Long-Way-Home/blob/main/STORY_DIRECTION.md).
- [Taken at Dusk](https://github.com/tony21675/MyNovel/blob/main/HANDOFF_LATEST.md) — intentionally on hold until *The Long Way Home* is finished. Its branch reconciliation is deferred until the author resumes it.

A novel's own package is the source for its canon and manuscript: its Story Bible, character cards, locations, current state, and accepted scene files. Do not copy one novel's information into another novel's handoff.

### Future story planning

Future novel premises and unstarted concepts are kept separately in the private ChatGPT Library at `/Writing/FUTURE_STORY_PLANNING.md`. This is a parking record, not an active novel or software-project plan. The second-Mars-base fragment has now been connected by the author to *The Long Way Home*: the Japanese-owned base is part of that novel's crisis direction, not a separate standalone concept unless the author later defines a different story. The spacecraft-in-transit fragment remains separate and incomplete.

## Latest Writer app change — November 7, 2026

StoryBuilder now has a two-role model setup for trial:
- Prepare Scene uses a separately selected planner model (defaults to Qwen3.5-4B when available).
- Write, Continue, Rewrite Scene, AI passage revision, and New Session use a separately selected manuscript-writing model (defaults to Gemma 4 E4B when available).
- Both roles share one WriterEngine process and load sequentially. Switching tasks stops the previous llama-cli process before loading the selected role. Model filenames are saved in the user's config directory, outside the repository.
- llama.cpp is started with explicit Jinja chat-template handling and reasoning disabled.
- This first integration is for local testing; model assignments and creative quality remain provisional until Tony tests the updated Writer locally on The Long Way Home.

Author-approved creative philosophy: gaps in canon are creative space, not automatic prohibitions. Encourage plausible inventions, new technical details, character interactions and plot developments. Protect basic survival logic and major established story foundations, but do not smother the models with rigid lists of restrictions. The author chooses which inventions become canon.

StoryBuilder's Writer and Prepare Scene requests have now been simplified. They no longer send the full canon-rules list, complete location allowlist, full creative-direction settings, generic craft/media instructions, or full character biographies on every request. They use short current-state context, brief facts for relevant characters, only named location details, and a short ending from the previous scene. The Story Bible remains unchanged as the detailed source of truth.

Both GitHub Actions workflows passed on StoryBuilder commit `6787b8f601f82e2358a146fead6d148040c51db4`: Python Tests reports 682 passed and 77 subtests passed; StoryBuilder tests reports 682 passed. Tony still needs to pull the update and run the suite locally. No novel manuscript or canon files were changed by this Writer code update.

Separate open issue: Prepare Scene retry still does not pass its previous generated direction back into the planner. Do not treat that behavior as fixed.

## Repository and verification checkpoint

- The obsolete nested `StoryBuilder/` checkout and its Git submodule pointer have been removed. The active Writer and Story Bible remain in the outer repository; no `.gitmodules` file or nested `StoryBuilder/` tree remains.
- Before the lean-context update, the full local suite passed 696 tests. The new prompt-reduction source and tests are committed together; CI and the next local suite run are pending.
- The focused local handoff-backup tests previously passed (2 tests).


## Local handoff backups

StoryBuilder includes `backup_handoffs.py` and `builder/handoff_backup.py`. The Writer and Story Bible launchers refresh a local mirror after the StoryBuilder pull, and successful app or novel GitHub syncs refresh it again.

- Default local mirror: `~/Documents/Project_Handoff_Backups`
- Includes the StoryBuilder index and app handoffs, *The Long Way Home* handoff and story direction, and *Taken at Dusk* handoff/reference documents when present locally.
- Contains only named Markdown handoff/planning files. It does not copy manuscripts, credentials, encrypted assets, or secret-letter files.
- Run manually with `python3 ~/Documents/StoryBuilder/backup_handoffs.py`.
- GitHub repositories remain authoritative; the local mirror is an independent emergency copy.

## Rules that prevent handoff drift

1. Each writing application has one active technical handoff.
2. Each novel has one active novel handoff and, when useful, one separate broad story-direction file.
3. Future story concepts have one separate planning record.
4. Do not duplicate current status across documents. Link to the authoritative record instead.
5. After a meaningful milestone, update the relevant handoff after the milestone finishes. Include source-data checkpoints and verification status; do not use self-referential commit markers.
6. Clearly label generated prose as pending review until the author accepts it and it is saved in the manuscript.
7. Never delete an archive or overwrite local work as part of handoff maintenance.
8. When sources disagree, record the conflict and pause. Do not choose a version by guessing.
9. Preserve the working branch and its autosync behavior unless branch migration is deliberately coordinated and tested.

**Project status:** The Long Way Home's broad crisis direction has been reconstructed from the author's latest decisions. Chapter 2 Scene 01 is saved and accepted; Scene 02 is next. The Writer's lean-context update is committed on the existing branch; CI and Tony's local pull/test are pending. Prepare Scene's retry-direction behavior remains a separate known issue. *Taken at Dusk* remains on hold.
