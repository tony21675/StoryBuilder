# Story Bible App handoff

**Updated:** November 11, 2026  
**Repository:** `tony21675/StoryBuilder`  
**Branch:** `redesign/simplified-writing-workflow` (GitHub default and only branch)  
**Local path:** `~/Documents/StoryBuilder`

## Purpose

This is the single technical handoff for the separate Story Bible application. The Writer has its own handoff in `WRITER_APP_HANDOFF.md`. Every novel has one separate `HANDOFF_LATEST.md` in that novel's repository.

The Story Bible app creates and edits reference data inside a selected novel package. The novel's own package remains the source of truth for premise, setting, canon, character cards, relationships, locations, current state, and manuscript.

## Launch and synchronization

- Run `cd ~/Documents/StoryBuilder && bash start_story_bible.sh`.
- The launcher synchronizes the current StoryBuilder branch before opening the app. It fast-forwards only and does not force-push or overwrite diverged local work.
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

- Discuss schema or app changes before making them.
- Do not migrate, flatten, or discard novel-specific fields just because the editor does not have a dedicated control for them.
- Preserve local changes and inspect Git status before syncing. Never use force-push, hard reset, or overwrite to resolve a sync problem.
- Do not open, edit, move, rename, delete, or copy secret-letter contents or encrypted/private assets. Protected paths must remain local and must block novel synchronization when detected.
- Keep this handoff current after meaningful Story Bible app changes. Do not duplicate it with another index or historical handoff.

## Verification

The latest handoff cleanup and consolidated handoff set passed both shared-repository GitHub Actions workflows on commit `398d8a9bc67440b6feb0e8711f088f877ad48d0d`; current workflow links are in `WRITER_APP_HANDOFF.md`. This is CI evidence, not a claim that every local computer has pulled or tested the latest revision.
