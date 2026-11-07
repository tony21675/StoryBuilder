# Writer App handoff

**Updated:** November 6, 2026  
**Application:** StoryBuilder Minimal Writer  
**Repository:** `tony21675/StoryBuilder`  
**Current branch:** `redesign/simplified-writing-workflow`  
**Current remote handoff checkpoint:** `fb28ae59a5b2ac5fd070aab44971fc9d169b93c3`

## Purpose and boundary

This document covers the Writer application only. The Story Bible is a separate application with its own launcher and its own handoff: [STORY_BIBLE_APP_HANDOFF.md](STORY_BIBLE_APP_HANDOFF.md).

The Writer creates and edits manuscript prose. Novel canon, character cards, locations, scene state, and accepted manuscripts belong to each novel's own package. Do not copy a novel's full story details into this app handoff.

## Launch and local safety

- Main entry point: `minimal_writer.py`
- Launcher: `./start.sh`
- Local repository: `~/Documents/StoryBuilder`
- The launcher synchronizes the active branch before starting. **Before launching or syncing, inspect the local Git status. Do not pull, reset, or overwrite local work while the status is unknown.**
- The author previously reported a local mode-only change to `storybuilder.py`; its current local status has not been verified. Preserve it until inspected.

## Current functionality recorded

- Load and use a local language model for manuscript generation.
- Write, Continue, and Prepare Scene workflows.
- Editable scene direction and natural endpoint supplied by Prepare Scene.
- Open and save manuscript drafts and scenes, including ODT support.
- Browse and save the selected scene.
- Revise or replace an explicitly selected passage with a preview/accept workflow.
- GitHub sync for a selected novel, with visible status feedback.

Do not infer that every feature has been freshly tested on the author's laptop. Record verification separately as local, CI, or GitHub evidence.

## Verification checkpoint

The latest audited GitHub Actions on the current handoff checkpoint reported:
- Python test workflow: 678 passed, 1 failed, 77 subtests passed.
- StoryBuilder test workflow: 679 tests, 1 error.
- The single known failure is the Tkinter test fixture `test_blank_name_does_not_save_or_close_the_editor`: its fake root lacks the `.tk` attribute expected by Tkinter's messagebox. This was identified as a test-harness issue, not evidence of a Writer behavior regression.
- Compile and shell syntax checks passed.

No claim is made that the current remote code has been pulled or fully tested on the author's laptop. Recheck the live repository and local status before any app update.

## Working agreement

- The author prefers one focused change at a time and discussion before code or model changes.
- Keep the writing process flexible. Avoid oversized prompts, rigid formulas, or micromanaging scene prose.
- Gemma writes; ChatGPT reviews direction and generated prose for continuity when asked. Do not write manuscript scenes unless explicitly requested.
- Do not change a novel's prose, story state, canon, or package data from the Writer app handoff.
- After an agreed app milestone, update this handoff and verify the commit.

## Current status

**Paused while project handoffs are being cleaned up.** Do not start new Writer features, change prompts, pull code, or modify model settings as part of the documentation cleanup.

