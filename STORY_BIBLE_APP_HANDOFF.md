# Story Bible App handoff

**Updated:** November 6, 2026  
**Application:** Story Bible  
**Repository:** `tony21675/StoryBuilder`  
**Current branch:** `redesign/simplified-writing-workflow`  
**Application-code checkpoint reviewed in the audit:** `380bc31056ca635a14243234eb0fe363dfe589ed` (documentation-only commits followed).

## Purpose and boundary

The Story Bible is a separate application from the Writer. It has its own application file and launcher, but both applications currently share the same GitHub code repository. The Writer's technical instructions are in [WRITER_APP_HANDOFF.md](WRITER_APP_HANDOFF.md).

The Story Bible App edits and maintains reference information inside an individual novel package. It is not the place to store the app's own development history, and this handoff is not a novel's canon document.

## Launch and code locations

- Main application file: `story_bible_app.py`
- Launcher: `bash start_story_bible.sh`
- Local repository: `~/Documents/StoryBuilder`
- The application shares the Writer App repository and branch. Inspect local Git status before syncing or changing files. Do not create a separate branch for this documentation cleanup.

## Application responsibilities and functionality recorded

The app manages novel setup and reference material, including:
- Novel title, premise, setting, creative direction, genre, and audience.
- Canon Rules stored in the novel package's `story_bible.json`.
- Character cards, edited through plain-English fields and saved as structured data.
- Location definitions through the Location Manager.
- Creation and editing of story-bible information for the selected novel.

The individual novel package remains the source of that novel's canon. Use that novel's `story_bible.json`, character-card files, location data, current state, and accepted manuscript. Do not treat this technical handoff as a substitute.

## Previously reported behavior to verify before further development

The following issues were reported during earlier use. Their current status has not been verified, so do not describe them as fixed or currently reproducible without checking:
- A save popup once reported a `story_role` error.
- The main character list did not always refresh immediately after a card was saved; a restart appeared to refresh it.
- Stale cached character-card text was a concern.

Other improvements previously reported include plain-English character fields, optional blank fields, a character dropdown, location management, and a darker interface. Verify behavior in the live local app before changing or claiming anything.

## Verification and working agreement

- No separate, current Story Bible App CI or local test result was established during the November 6 audit. Treat testing as unverified until run and recorded.
- Discuss app or data-model changes before editing.
- Make one focused change at a time.
- Do not silently change the schema or rewrite a novel's existing cards, canon, or locations.
- Preserve local package changes and inspect Git status before any sync.
- Update this handoff after each agreed Story Bible App milestone.

## Current status

**Paused while project handoffs are being cleaned up.** Do not make app-code, schema, canon, character-card, or location changes as part of this documentation cleanup.

