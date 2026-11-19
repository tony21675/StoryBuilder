# Story Bible App handoff

**Updated:** November 18, 2026  
**Repository:** `tony21675/StoryBuilder`  
**Branch:** `main` (GitHub default and sole working branch)  
**Local path:** `~/Projects/StoryBuilder`

## Future UI modernization (planned, not started)

When work on the novel applications resumes, plan a gradual migration of the Story Bible interface from Tkinter to **PySide6**, using Vape Recipe Studio as the desktop usability and design reference.

- Keep Story Bible and the Writer as separate applications. This is a shared UI toolkit and visual-standard decision, not a plan to combine them into one program.
- Replace the Tkinter presentation layer only after the PySide6 version is ready. Preserve the existing Story Bible data model and behavior, including novel-package creation, premise and setting editing, creative direction, canon rules, character-card management, location management, and safe novel synchronization.
- Aim for consistent, dependable text selection and clipboard shortcuts, comfortable scrolling in long text areas and dialogs, resizable windows and layouts, and usable forms, lists, and tables on both desktop monitors and smaller laptop screens.
- Migrate incrementally and test against existing novel packages. Do not change story content, canon, character-card or location data, manuscript files, or novel repositories as part of a UI-only migration.
- Keep the current Tkinter application usable until the PySide6 replacement has been tested and verified. The Writer can be migrated separately; the applications do not need to share one window or be released together.
- Do not begin this modernization as part of unrelated maintenance; it is a future upgrade for when novel work resumes.

## Purpose

This is the single technical handoff for the separate Story Bible application. The Writer has its own handoff in `WRITER_APP_HANDOFF.md`. Every novel has one separate `HANDOFF_LATEST.md` in that novel's repository.

The Story Bible app creates and edits reference data inside a selected novel package. The novel's own package remains the source of truth for premise, setting, canon, character cards, relationships, locations, current state, and manuscript.

## Launch and synchronization

- Run `cd ~/Projects/StoryBuilder && bash start_story_bible.sh`.
- The launcher requires the shared StoryBuilder repository to be on `main` and safely synchronizes `origin/main` before opening the app. It fast-forwards only and does not force-push or overwrite diverged local work. Uncommitted local changes are temporarily stashed and restored around the startup sync.
- The app shares the StoryBuilder code repository and branch with the Writer, but has a separate entry point and launcher.
- The default novel library is `~/Documents/MyNovel`; `STORY_NOVEL_ROOT` can override it.
- Novel-to-GitHub synchronization is a separate explicit action from app-code synchronization. It previews the selected novel's repository, branch, remote, and changes, then requires confirmation. It refuses unsafe divergence, unfinished Git operations, and protected local secret/encrypted paths.

## Current application capabilities

- Create a novel package with a Story Bible template and manuscript folder. Creation does not overwrite an existing destination or invent story content.
- View a selected novel's Story Bible in a scrollable, copyable read-only view.
- Edit premise, setting, writing preferences, and supported creative-direction fields.
- Manage canon rules in the novel's `story_bible.json`.
- Add, edit, and remove character-card references. The plain-English editor preserves untouched nested and custom fields; removing a reference does not delete the source character file.
- Add, edit, and remove named locations. Untouched location fields and custom data are preserved.
- Save only the selected field or card being edited; do not silently rewrite the rest of the novel package.

The app does not turn novel facts into global Writer rules. Character cards, relationships, location details, canon, and other story-specific information remain inside the selected novel's package and are read by the Planner/Writer as reference context.

## Safe working boundaries

- Keep StoryBuilder and Story Bible application development, testing, commits, and pushes directly on the shared repository's `main` branch. Do not create or switch to feature/redesign branches. Preserve existing historical branches, but do not use them for active work.
- Discuss schema or app changes before making them.
- Do not migrate, flatten, or discard novel-specific fields just because the editor does not have a dedicated control for them.
- Preserve local changes and inspect Git status before syncing. Never use force-push, hard reset, or overwrite to resolve a sync problem.
- Do not open, edit, move, rename, delete, or copy secret-letter contents or encrypted/private assets. Protected paths must remain local and must block novel synchronization when detected.
- Keep this handoff current after meaningful Story Bible app changes. Do not duplicate it with another index or historical handoff.

## Verification

The latest handoff cleanup and consolidated handoff set passed both shared-repository GitHub Actions workflows on commit `398d8a9bc67440b6feb0e8711f088f877ad48d0d`; current workflow links are in `WRITER_APP_HANDOFF.md`. This is CI evidence, not a claim that every local computer has pulled or tested the latest revision.
