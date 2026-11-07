# Writing project handoff index

**Updated:** November 7, 2026

This index covers writing projects only. Each application and novel has one authoritative handoff. The project repositories remain the source of truth; local mirror copies are maintained separately.

## Active handoffs

### Writing applications

- [Writer App](WRITER_APP_HANDOFF.md) — Minimal Writer code, launch, sync behavior, local handoff backups, features, known app issues, and testing.
- [Story Bible App](STORY_BIBLE_APP_HANDOFF.md) — the separate Story Bible application, its code, launch, sync behavior, local handoff backups, known issues, and testing.

These are two separate applications with separate launchers. They share the `tony21675/StoryBuilder` repository and its single current branch, `redesign/simplified-writing-workflow`. That branch is the GitHub default and the only branch. Keep its name for now: sync helpers explicitly block `main`, and some workflow/test triggers still refer to this branch. There is no additional branch clutter to clean up.

### Novels

- [The Long Way Home](https://github.com/tony21675/The-Long-Way-Home/blob/main/CHAT_HANDOFF_LATEST.md) — current novel priority. Chapter 1 Scenes 01–15 are accepted; Chapter 2 was reset and has no accepted scenes. The existing Chapter 2 Scene 1 trace is pending review. The current broad author-approved direction is in [STORY_DIRECTION.md](https://github.com/tony21675/The-Long-Way-Home/blob/main/STORY_DIRECTION.md).
- [Taken at Dusk](https://github.com/tony21675/MyNovel/blob/main/HANDOFF_LATEST.md) — intentionally on hold until *The Long Way Home* is finished. Its branch reconciliation is deferred until the author resumes it.

A novel's own package is the source for its canon and manuscript: its Story Bible, character cards, locations, current state, and accepted scene files. Do not copy one novel's information into another novel's handoff.

### Future story planning

Future novel premises and unstarted concepts are kept separately in the private ChatGPT Library at `/Writing/FUTURE_STORY_PLANNING.md`. This is a parking record, not an active novel or software-project plan. The second-Mars-base fragment has now been connected by the author to *The Long Way Home*: the Japanese-owned base is part of that novel's crisis direction, not a separate standalone concept unless the author later defines a different story. The spacecraft-in-transit fragment remains separate and incomplete.

## Repository and verification checkpoint

- The obsolete nested `StoryBuilder/` checkout and its Git submodule pointer have been removed. The active Writer and Story Bible remain in the outer repository; no `.gitmodules` file or nested `StoryBuilder/` tree remains.
- Both GitHub Actions workflows passed after the cleanup. Python Tests reports 681 passed and 77 subtests passed; StoryBuilder tests reports 681 tests passed.
- The focused local handoff-backup test module passed (2 tests). The full test suite has not yet been run locally on this laptop.

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

**Project status:** The Long Way Home's broad crisis direction has been reconstructed from the author's latest decisions. The manuscript remains paused at the Chapter 2 Scene 1 review point. *Taken at Dusk* remains on hold.
