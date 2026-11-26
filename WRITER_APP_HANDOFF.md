# Writer App handoff

**Updated:** November 23, 2026  
**Repository:** `tony21675/StoryBuilder`  
**Branch:** `main` (GitHub default and sole working branch)  
**Local path:** `~/Projects/StoryBuilder`

## UI migration status

The Story Bible is the first of the two novel-app interfaces being migrated to PySide6. Its Qt version is being tested alongside the existing Tkinter version. The Writer remains on Tkinter until the Story Bible port has passed desktop testing.

- Keep the Writer and Story Bible as separate applications. They may share PySide6 theme and utility components, but must not be combined into one window.
- The future Writer port must preserve the existing WriterEngine and workflows, including Qwen scene planning, Gemma prose generation, author-required beats, scene-cast boundaries, prompt tracing, model preferences, novel browsing, ODT/TXT editing, and safe novel synchronization.
- Do not change story content, canon, manuscript formats, model configuration, prompt behavior, or novel data as part of a UI-only migration.
- Keep `minimal_writer.py` and its existing launcher usable until a PySide6 Writer replacement has been tested and verified. Do not change Writer behavior as part of the Story Bible migration.

## Purpose

This is the single technical handoff for the StoryBuilder Writer. The Story Bible is a separate app with its own handoff, `STORY_BIBLE_APP_HANDOFF.md`. Novel canon, characters, locations, current state, and accepted prose belong in each novel's own repository and its one handoff.

## Launch and local requirements

- Run `cd ~/Projects/StoryBuilder && ./start.sh` to launch the Minimal Writer.
- The launcher requires the local repository to be on `main` and safely synchronizes `origin/main` before opening the app. It fast-forwards only; it does not force-push or resolve diverged history by overwriting local work. Uncommitted local changes are temporarily stashed and restored around the startup sync.
- Default models directory: `~/Documents/Models` (GGUF files).
- Default llama.cpp executable: `~/Documents/llama.cpp/build/bin/llama-cli`.
- The default context is 16,384 tokens; output defaults to 4,000 tokens. Existing environment variables can override paths and limits, including `STORY_MODELS_DIR`, `STORY_LLAMA_PATH`, `STORY_NOVEL_ROOT`, `STORY_WRITER_CONTEXT`, and `STORY_WRITER_MAX_TOKENS`.
- Novel packages are discovered under `~/Documents/MyNovel` by default.

## Model roles

- **Qwen** handles Prepare Scene and scene planning.
- **Gemma** handles manuscript prose: Write, Continue, Rewrite Scene, and passage revision.
- The two models load sequentially through one WriterEngine process. The previous model process is stopped before the other role loads; StoryBuilder does not keep both models loaded together.
- Model-role choices are configurable in the Writer UI and saved outside the repository in the user's configuration directory.

## Current Writer behavior

The active entry point is `minimal_writer.py`. It supports Prepare Scene, Write, Continue, Rewrite Scene, New Session, selected-passage revision/replacement, text and ODT document editing, novel/chapter/scene browsing, safe scene saving, and explicit novel-to-GitHub synchronization.

- Prepare Scene fills the prompt box only. It does not save a manuscript scene or change the novel's current state.
- Write replaces the visible draft. Continue extends the visible passage. Rewrite Scene is confirmation-gated and preserves the previous draft if canceled, stopped, or unsuccessful.
- ODT is the preferred manuscript format; UTF-8 TXT remains supported.
- Saving over a selected source scene requires an explicit path-specific confirmation.
- Novel synchronization is separate from app-code synchronization. It previews the selected novel repository and requires confirmation. It refuses unsafe history divergence, unresolved Git operations, and protected local secret/encrypted paths. Never force-push, reset, or overwrite local novel changes to resolve a sync problem.

## Prepare Scene context and author intent

The Planner is deliberately given substantial novel-specific reference context because its job is to understand the story and prepare a useful blueprint for Gemma. For the selected novel it receives, when available:

- Premise and setting.
- All fixed-canon and relationship entries from the Story Bible.
- All registered character cards, including populated standard, nested, and custom fields.
- Saved locations and their descriptions.
- Current story situation, relevant continuity notes, time-of-day marker, and the complete immediately preceding saved scene.
- The novel's writing preferences and selected genre, mood, and audience guidance.
- The current Author's Direction.

These facts are reference context, not a requirement to include every character or location in every scene. Qwen can invent plausible connective details and choose any number of additional beats while preserving established canon.

Prepare Scene asks Qwen to return separate **AUTHOR-REQUIRED BEATS** and **QWEN-SELECTED ADDITIONAL BEATS** sections:
- The current Author's Direction is the **only source** for AUTHOR-REQUIRED BEATS. Only concrete events, actions, or moments explicitly requested in that field qualify. The Story Bible, current state, continuity notes, character cards, locations, preceding scene, previous prepared direction, earlier conversation, and Qwen's own ideas are context only and cannot create required beats.
- If the current Author's Direction is empty, AUTHOR-REQUIRED BEATS must be completely blank. Do not insert a placeholder such as "None specified" or infer a required beat from surrounding context. If the field contains only tone, mood, general goals, or preferences without a concrete requested event, leave the section blank as well. The app also clears any model-generated content from this section when the original Author's Direction is empty, while preserving QWEN-SELECTED ADDITIONAL BEATS.
- Every concrete event explicitly requested in the current Author's Direction must happen in that destination scene; do not omit, soften, replace, or defer it.
- Qwen's additional beats are optional. It should add only details that genuinely help the scene, usually zero to three short additions; it must not pad the plan or restate the author's events.
- Qwen returns a short, plain-language scene direction paragraph (normally two to four sentences), followed by separate AUTHOR-REQUIRED BEATS and QWEN-SELECTED ADDITIONAL BEATS headings. It must not return screenplay formatting, INT./EXT. slug lines, character-name dialogue labels, camera directions, scripted dialogue, a long numbered breakdown, or finished manuscript prose.
- The application inserts the current Author's Direction unchanged under AUTHOR-REQUIRED BEATS after generation. Qwen must leave that section empty and must not copy, quote, restate, or paraphrase the Author's Direction elsewhere in its output.
- Qwen should use canon selectively, avoid importing unrelated future plot material, and leave ordinary dialogue, gestures, staging, and connective prose to Gemma. It must not invent specific memories, sensory experiences, calls, messages, props, relationships, backstory, or future events as established facts.
- When refining a previous direction, the current Author's Direction controls classification; old beat labels must not be treated as authoritative.

When the author presses Write, Gemma receives Qwen's prepared direction and the original Author's Direction as a separate authoritative instruction. Qwen's omission or misclassification must not erase the author's original required event.
- **Scene Cast is author-selected and binding.** The Writer shows the registered character-card roster in a simple multi-select dialog. Before Prepare Scene, the author selects who may appear in that destination scene; if no selection exists, Prepare Scene asks for one. Qwen receives only the selected characters' full cards, not the other cards, plus an explicit boundary excluding every unselected character from the scene. Gemma receives only the same selected cards and the same exclusion boundary. An unselected character must not appear, speak, act, be referred to by name or pronoun, or participate through an off-page interaction, cutaway, flashback, call, text, or email. Previous-scene text and continuity notes remain available for understanding continuity, but cannot override the cast boundary. The selection is tied to the selected novel and scene inside the active Writer session; changing novel or scene clears it. The selection is not written into current_state.json.

Prepare Scene plans one destination scene. The Writer also receives a one-scene scope for Write, Continue, and Rewrite Scene. This does not impose a fixed scene count, mandatory endpoint, or checklist. Let the scene find a natural shape and ending.

## Prompt trace

The Planner-to-Writer trace is an essential diagnostic and must remain active.

- The trace records the planner input and raw response, the final direction presented to the Writer, the original author-required direction, the complete assembled Writer prompt, and the Writer response.
- It is saved locally after the prose-generation attempt. Upload is manual only, using the Writer's **Upload Prompt Trace** button; never upload automatically.
- The button uploads the latest local `prompt_trace.json` to the existing private `StoryBuilder-Traces` repository. That repository intentionally retains only the latest trace, overwriting the prior latest trace.
- Keep local trace capture and retention active. Do not add automatic uploads or extra trace copies in the repository.

## Source-of-truth and working rules

- This handoff describes the shared Writer application only. Never put a novel's plot, character canon, or manuscript progress here.
- Each novel has one `HANDOFF_LATEST.md`; that handoff points to the novel's own Story Bible, character cards, accepted manuscript, and `current_state.json`.
- Treat discarded drafts and superseded handoffs as obsolete. Do not resurrect them because an old conversation or backup mentions them.
- Keep StoryBuilder application development, testing, commits, and pushes directly on `main`. Do not create or switch to feature/redesign branches. Preserve existing historical branches, but do not use them for active work.
- Keep the writing process flexible. Do one focused change at a time, discuss code/model changes first, and avoid rigid formulas or micromanaging prose.
- Update this handoff after each meaningful Writer-app milestone. Keep the Story Bible app handoff separate.

## Verification

The strict Author-Required Beats source rule and empty-input output safeguard are implemented in commit fbd6a69a1163bc5e04b54dd9c516e6de43be54cb. Both GitHub Actions workflows passed on that code revision:
- [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/43185289330)
- [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/43185289198)

The regression tests cover an empty Author's Direction (including when a previous prepared direction contains event language), Markdown-formatted section headings, preservation of Qwen-selected additions, and non-empty Author's Direction behavior. The wider suite also covers the existing Planner and Writer workflows. CI success does not claim every computer has pulled or locally tested this revision.


## PySide6 migration update

**Updated:** November 23, 2026

A separate first-pass Qt Writer now exists at \`writer_qt.py\`, launched with \`./start_writer_qt.sh\`. It is an additive migration preview; \`minimal_writer.py\` and \`./start.sh\` remain the known-good Tkinter fallback.

The initial Qt build currently covers:
- Independent Planner and Writer model selectors, saved model-role preferences, and on-demand loading.
- Novel, chapter, and scene browsing, plus an author-selected multi-select scene cast.
- Prepare Scene using the existing planner prompt builder and deterministic insertion of the exact Author's Direction under AUTHOR-REQUIRED BEATS.
- Balanced, minimal, and full-context modes; streaming Write, Continue, confirmation-gated Rewrite, Stop, and New Session.
- ODT/TXT open and save, save-new-scene, confirmation-gated overwrite of a loaded selected scene, and chapter/finished-novel assembly.

The port reuses existing model, scene-planning, character-context, Story Bible, manuscript, and document helpers. No Story Bible or manuscript schema migration is intended.

**Feature ports now present in the Qt Writer:** selected-passage AI revision and exact replacement with explicit review, advisory Check Draft, OpenRouter key/catalogue settings, saved-scene position plus validated ending-state updates, selected-novel GitHub sync through the existing safety checker, and Planner-to-Writer PromptTrace capture. The same trace object follows Prepare Scene through Write, records both model calls and the prepared direction, saves the single local trace, and waits for an explicit **Upload Prompt Trace** button click before sending it to the private repository. Automated CI has passed the Qt Writer regression tests, but the new flows have not yet had complete live desktop validation. Keep the original Tkinter Writer available until model generation, trace upload, revision, state update, save/reopen, OpenRouter refresh, and safe novel sync pass on a disposable test novel. Do not weaken or bypass trace upload or novel-sync safety checks.

CI now compiles \`writer_qt.py\`, checks the new launcher syntax, and discovers \`tests/test_writer_qt.py\`. Automated CI passing is not a substitute for a live desktop check. Next validation should use the separate Qt launcher and a disposable test novel before any real manuscript is saved or overwritten.


## New Chapter workflow (November 25, 2026)

- Both the normal Tkinter Writer (start.sh) and parallel Qt Writer (start_writer_qt.sh) now provide a **New Chapter** action.
- The action is available only for the latest chapter folder when it contains at least one saved scene. It refuses to proceed with unsaved Output-pane changes, and requires explicit confirmation.
- On confirmation it creates the next chapter folder, records the completed-through chapter and final scene, and moves current_state.json to the next unwritten destination: chapter = previous chapter + 1, scene = 1, scene_completed = false, and chapter_completed = true.
- The transition clears the previous scene's scene_cast so the next scene's cast is selected afresh. It preserves current story facts, including location, situation, physical state, and in-story time.
- The UI selects the new chapter and Scene 01. Prepare Scene still obtains the immediately preceding saved scene through previous_saved_scene, so the prior chapter's final scene and its continuity handoff remain the next scene's reference. No manuscript scene is rewritten or deleted.
- completed_through_chapter and completed_through_scene preserve the chapter-boundary record. Saving the first scene in the new chapter changes the active scene markers to completed and clears the transient chapter_completed flag.
- Regression tests cover current-state advancement, preservation of story facts, fresh cast selection, next-chapter folder/UI selection, and use of the previous chapter's final scene for continuity. Desktop model generation and live interaction still need validation on the user's machine.

## Selected Creative Direction in Prepare Scene (November 25, 2026)

- `builder/scene_preparation.py` now reads the selected novel's `creative_direction` from its Story Bible and uses `build_creative_direction_prompt` to add only the selected genres, moods, audience guidance, and explicit-content boundary to Qwen's Prepare Scene prompt.
- No app-wide profiles are injected when the novel has no Creative Direction selections. The Planner does not receive unselected genre profiles, writing preferences, or every profile file.
- Gemma's existing Balanced and Full Writer context behavior remains unchanged. Minimal Writer context remains intentionally minimal.
- Regression coverage verifies selected Mystery/Comedy guidance, mood and audience guidance, and isolation from unselected Comedy when only Mystery is selected.
- CI run: https://github.com/tony21675/StoryBuilder/actions/runs/45726214186 (check final result before claiming tests pass).
