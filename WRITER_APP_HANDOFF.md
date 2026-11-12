# Writer App handoff

**Updated:** November 12, 2026  
**Repository:** `tony21675/StoryBuilder`  
**Branch:** `redesign/simplified-writing-workflow` (GitHub default and only branch)  
**Local path:** `~/Documents/StoryBuilder`

## Purpose

This is the single technical handoff for the StoryBuilder Writer. The Story Bible is a separate app with its own handoff, `STORY_BIBLE_APP_HANDOFF.md`. Novel canon, characters, locations, current state, and accepted prose belong in each novel's own repository and its one handoff.

## Launch and local requirements

- Run `cd ~/Documents/StoryBuilder && ./start.sh` to launch the Minimal Writer.
- The launcher synchronizes the existing StoryBuilder branch before opening the app. It fast-forwards only; it does not force-push or resolve diverged history by overwriting local work.
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
- If the current Author's Direction is empty, AUTHOR-REQUIRED BEATS must be completely blank. Do not insert a placeholder such as "None specified" or infer a required beat from surrounding context. If the field contains only tone, mood, general goals, or preferences without a concrete requested event, leave the section blank as well.
- Every concrete event explicitly requested in the current Author's Direction must happen in that destination scene; do not omit, soften, replace, or defer it.
- Qwen may choose zero, one, or any number of additional beats. There is no quota or cap. All ideas Qwen adds belong only under QWEN-SELECTED ADDITIONAL BEATS.
- When refining a previous direction, the current Author's Direction controls classification; old beat labels must not be treated as authoritative.

When the author presses Write, Gemma receives Qwen's prepared direction and the original Author's Direction as a separate authoritative instruction. Qwen's omission or misclassification must not erase the author's original required event.

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
- Keep the writing process flexible. Do one focused change at a time, discuss code/model changes first, and avoid rigid formulas or micromanaging prose.
- Update this handoff after each meaningful Writer-app milestone. Keep the Story Bible app handoff separate.

## Verification

The strict Author-Required Beats source rule was implemented in commit 7726b79bd30eb7c5c3072e18aa0d4ab280aadf39. Both GitHub Actions workflows passed on that code revision:
- [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/43184533931)
- [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/43184534052)

The regression tests cover an empty Author's Direction (including when a previous prepared direction contains event language), current-direction-only sourcing, and preservation of separate Qwen-selected additions. The wider suite also covers the existing Planner and Writer workflows. CI success does not claim every computer has pulled or locally tested this revision.
