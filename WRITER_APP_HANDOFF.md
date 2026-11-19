# Writer App handoff

**Updated:** November 18, 2026  
**Repository:** `tony21675/StoryBuilder`  
**Branch:** `main` (GitHub default and sole working branch)  
**Local path:** `~/Projects/StoryBuilder`

## Future UI modernization (planned, not started)

When work on the novel applications resumes, plan a gradual migration of the Writer interface from Tkinter to **PySide6**, using Vape Recipe Studio as the desktop usability and design reference.

- Keep the Writer and Story Bible as separate applications. This is a shared UI toolkit and visual-standard decision, not a plan to combine them into one program.
- Replace the Tkinter presentation layer only after the PySide6 version is ready. Preserve the existing Writer engine and workflows, including Qwen scene planning, Gemma prose generation, author-required beats, scene-cast boundaries, prompt tracing, model preferences, novel browsing, and safe novel synchronization.
- Aim for consistent, dependable text selection and clipboard shortcuts, comfortable scrolling in long passages and dialogs, resizable windows and layouts, and usable forms, lists, and tables on both desktop monitors and smaller laptop screens.
- Migrate incrementally and test each workflow against existing novel packages. Do not change story content, canon, manuscript formats, model configuration, prompt behavior, or novel data as part of a UI-only migration.
- Keep the current Tkinter application usable until the PySide6 replacement has been tested and verified. Do not begin this modernization as part of unrelated maintenance; it is a future upgrade for when novel work resumes.

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
- It is saved locally after the prose-generation attempt and uploaded to the existing private `StoryBuilder-Traces` repository.
- That repository intentionally retains the latest `prompt_trace.json`, overwriting the prior latest trace. The local trace remains available if upload fails.
- Do not disable tracing, change its upload timing, create extra trace copies in the repository, or weaken local retention without explicit discussion.

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
