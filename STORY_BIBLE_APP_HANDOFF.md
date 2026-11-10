# Story Bible App handoff

**Updated:** November 10, 2026  
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

## Generic genre and audience profile resources

**Implemented:** November 8, 2026  
**Verification:** Profile-loading and prompt tests were added or updated; GitHub Actions and local GUI verification are pending.

Genre and intended-audience choices are loaded from shared Markdown files under `profiles/genres/` and `profiles/audiences/`. The first Markdown heading is the visible choice name; the remaining text describes the guidance sent to the models. Adding a profile file adds a choice without changing Python code.

Each novel's `story_bible.json` stores only its selected genre labels, mood labels, audience, and the existing `explicit_adult_content` boolean. Profile descriptions remain shared app resources, not novel-specific data. The same selected profile guidance is used by Prepare Scene and manuscript writing.

The Explicit Adult Content checkbox remains a separate setting and is available only for an Adult audience. Adult does not automatically mean explicit. When the setting is off, explicit sexual detail is not permitted; when on, it is allowed only where appropriate and involving consenting adults.

The individual novel package remains the source of that novel's canon. Use that novel's `story_bible.json`, character-card files, location definitions, current state, and accepted manuscript. Do not treat this technical handoff as a substitute.

## Previously reported behavior to verify before further development

The following issues were reported during earlier use. Their current status has not been verified, so do not describe them as fixed or currently reproducible without checking:
- A save popup once reported a `story_role` error.
- The main character list did not always refresh immediately after a card was saved; a restart appeared to refresh it.
- Stale cached character-card text was a concern.

Other improvements previously reported include plain-English character fields, optional blank fields, a character dropdown, location management, and a darker interface. Verify behavior in the live local app before changing or claiming anything.

## Verification status and working agreement

- The focused handoff-backup test module passed locally on November 7, 2026 (2 tests).
- Both GitHub Actions workflows passed after the November 7 repository cleanup. The Python Tests workflow reports 681 passed and 77 subtests passed; the StoryBuilder tests workflow reports 681 tests passed.
- The full test suite has not yet been run locally on this laptop after the latest changes.
- Discuss app or data-model changes before editing.
- Make one focused change at a time.
- Do not silently change the schema or rewrite a novel's existing cards, canon, or locations.
- Preserve local package changes and inspect Git status before any sync.
- Update this handoff after each agreed Story Bible App milestone.


## Per-novel writing preferences — implemented November 10, 2026

The Story Bible View tab now includes an optional **How This Novel Should Read** section with an **Edit Writing Preferences** action. Authors can enter plain-English preferences for prose style and storytelling behavior, such as natural versus lyrical prose, how much figurative language to use, and whether to trust the reader rather than repeatedly explaining established ideas.

Implementation details:
- Saved as the novel-specific `writing_preferences` text field in that novel's `story_bible.json`.
- Kept separate from Premise, Setting, Genre & Mood, Intended Audience, Explicit Adult Content, and Canon Rules.
- New novel packages initialize the field as an empty string.
- Existing packages without the field load with a blank value and can be edited without a migration.
- Editing saves only this field and preserves all other Story Bible data.
- The field is optional. Blank means no additional novel-specific writing guidance.
- It is generic app functionality. No story, character, genre, or setting assumptions are hard-coded.

The goal is one generic Writer that can support distinct novel voices without imposing one writing personality on every project.

**Verification:** Both GitHub Actions workflows passed on source/test commit `4fbeea85d80d95dbe125b5c18f2415e5b8584e49`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/42783731649) report 714 passed and 77 subtests passed; [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/42783731793) report 714 tests passed. Local pull and GUI verification remain pending.

## AI-assisted story planning and idea organization — discussion only, November 10, 2026

The author would like AI help developing story outlines without having to write a conventional outline. The desired experience is free-form brainstorming: the author supplies ideas in any order, and the AI helps organize and place them. This is a future design discussion only; no Story Bible schema, UI, or code changes have been approved.

Potential planning material for each novel should distinguish:
- **Confirmed:** author-approved story decisions.
- **Proposed:** possibilities under consideration.
- **Open:** unresolved questions.
- **Needs placement:** ideas to retain before deciding where they belong.

The author should be able to brainstorm conversationally and review the AI's proposed organization. Nothing becomes official until approved. Approved material could be arranged into an overall story roadmap and broad chapter roadmaps; these should steer the story rather than prescribe every scene.

A future chapter-preparation workflow could assemble a focused packet for the Writer from the active novel's chapter direction, current state, relevant character cards/knowledge, essential canon, necessary prior continuity, and only the boundaries relevant to that chapter. The manuscript-writing model should not receive unrelated chapter histories or future revelations simply because they exist elsewhere in the project.

Keep planning data generic in the app and isolated per novel. Do not hard-code characters, story arcs, genre assumptions, or plot structures in shared application code. Before implementation, discuss where the idea bank and roadmaps should live in a novel package and how the Writer should retrieve only the active chapter's information. The previous checklist-heavy approach repeatedly made generated prose mechanical; chapter roadmaps must remain broad guidance, not mandatory beat checklists, scene counts, or forced endings.
