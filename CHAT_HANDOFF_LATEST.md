# Writing project handoff index

**Updated:** November 6, 2026

This file is an index only. It is not a general-purpose handoff and contains no active novel scene instructions.

## Active handoffs

### Applications
- [Writer App](WRITER_APP_HANDOFF.md) — Minimal Writer code, launch, features, known app issues, and testing.
- [Story Bible App](STORY_BIBLE_APP_HANDOFF.md) — Story Bible application code, launch, features, known app issues, and testing.

These are two separate applications with separate launchers. They currently share the `tony21675/StoryBuilder` code repository. Each has its own technical handoff.

### Novels
- [The Long Way Home](https://github.com/tony21675/The-Long-Way-Home/blob/main/CHAT_HANDOFF_LATEST.md) — only current operational handoff for that novel.
- [Taken at Dusk](https://github.com/tony21675/MyNovel/blob/main/HANDOFF_LATEST.md) — only current operational handoff for that novel.

A novel's own package is the source for canon and manuscript: its Story Bible, character cards, locations, current state, and accepted scene files. Do not copy one novel's information into another novel's handoff.

### Future story planning
The private planning record is maintained separately in the ChatGPT Library at `/Writing/FUTURE_STORY_PLANNING.md`. It is a parking file for story concepts that are not active novels. It is not canon and does not authorize development.

## Documents that are not active handoffs

- `FUTURE_APPS_ON_HOLD.md` is about possible future **applications**, not future story premises.
- `LONG_TERM_GOALS.md`, `REDESIGN_PLAN.md`, and `STORY_FLOW_REPAIR_PLAN.md` are older product-planning references. They do not override the current Writer App or Story Bible App handoff.
- `APP_AUDIT_2026-10-21.md`, `CROSS_NOVEL_CONTEXT_AUDIT_2026-10-21.md`, `WRITER_FLOW_EXPERIMENT_AUDIT_2026-10-21.md`, and files under `docs/` are historical audits. Consult them only for background when a current handoff points to a specific issue.
- Older dated handoffs, addenda, and copied checkpoints are historical. They must not be used to infer current status or next steps.

## Rules that prevent handoff drift

1. Each application has one active technical handoff.
2. Each novel has one active novel handoff.
3. Future story ideas have one separate planning record.
4. Do not duplicate the same current status across multiple documents. Link to the authoritative document instead.
5. After a meaningful milestone, update the relevant handoff after the milestone finishes, not before. Include the resulting commit and verification status.
6. Clearly label generated prose as pending review until the author accepts it and it is saved in the manuscript.
7. Never delete an archive or overwrite local work as part of handoff maintenance.
8. When sources disagree, record the conflict and pause. Do not choose a version by guessing.

**Project status:** Story development and app changes are paused while these records are being stabilized.
