# Comparative Writing Pipeline Audit: LocalStoryChat vs StoryBuilder

**Date:** 2026-10-21  
**Scope:** Read-only source audit of `tony21675/LocalStoryChat` and StoryBuilder's current `main` design, cross-checked against the leaner-scene-boundary experiment branch. This report does not change application code or any novel package.

## Executive finding

The strongest difference is not simply the number of instructions. LocalStoryChat's system prompt is itself detailed and contains canon, knowledge, continuity, and writing-mode rules. Its generation path is comparatively direct: one central system prompt plus seven JSON reference files, followed by the user's request in a persistent `llama-cli` conversation.

StoryBuilder builds a more elaborate scene-specific pipeline: it derives a scene direction from saved state and guidance, creates a scene contract, assembles selected reference files and sometimes historical excerpts, fits the context to a token budget, then uses completion/continuity review that can trigger another full-scene generation or a continuation. These layers can improve continuity and protect against unsupported plot changes, but they also create more opportunities for the writer to over-attend to constraints, duplicate requirements, or add material to satisfy a reviewer.

**This is a plausible explanation for the difference in creative feel, not proof that any one layer caused the prose problem.** No valid, controlled A/B prose comparison has yet been completed.

## 1. What the code does

### LocalStoryChat

Source reviewed: `server.py`, `README.txt` on the repository's `main` branch.

- `SYSTEM_PROMPT` establishes the authority of character files, story bible, current state, and writing guidance.
- It explicitly protects character knowledge, continuity, and hidden canon while permitting ordinary, harmless interpersonal invention.
- It tells the model to output story prose only during normal writing, continue from the requested point, avoid restarting, and keep the scene focused.
- The application combines this central prompt with seven JSON reference files: four character files, story bible, current state, and writing guidance.
- It starts `llama-cli` with the system prompt and maintains an interactive session through normal stdin/stdout pipes. The user request enters that session as a conversation turn.

The README says the context size is 4096, while the inspected active UI/configuration code indicates 12288. Treat the README's context-size statement as stale until it is corrected or verified against the actual launch configuration.

### StoryBuilder

Sources reviewed: `storybuilder.py`, `builder/scene_completion.py`, and `builder/writer_context_budget.py` on `experiment/leaner-scene-boundary`. The relevant pipeline also exists in the current StoryBuilder design; the experiment primarily shortens the scene-boundary prompt.

- The target chapter and scene are taken from the loaded `package.current_state`.
- The app derives Scene Direction from the current state and the relevant `writing_guidance.json` entry, including location, time, opening cast, current situation, and rules about knowledge, physical state, and completed events.
- The Writer builds a scene contract and combines its writer context with a separate scene-boundary prompt.
- It assembles package reference files and can add up to four historical archive excerpts, with a combined excerpt limit of 2400 characters.
- The context budget estimates input size, protects core scene state/canon/guidance, and may prune optional references, compact character cards, remove historical excerpts, or reduce selected knowledge facts if required. This pruning affects the transient prompt view, not the saved novel files.
- Scene completion runs semantic review and a five-category integrity audit. Depending on the result, it can preserve the first draft, regenerate the full scene once for verified conflicts, or continue the draft when intended beats appear missing. Reviewer calls reset the model context and then attempt to restore the Writer's context.

This is a more controlled pipeline than LocalStoryChat's direct request flow. It is not inherently worse, but each additional instruction source and review pass adds complexity.

## 2. Main findings

### Finding A: The issue is not “LocalStoryChat has fewer rules”

LocalStoryChat has a substantial system prompt. Its advantage may be that its rules are consolidated in one place and the user can guide the scene directly in an ongoing conversation. StoryBuilder distributes authority across static instructions, generated Scene Direction, a scene contract, saved guidance, current-state details, reference files, historical snippets, and later reviewer prompts.

**Recommendation:** Reduce duplication and competing instruction layers rather than indiscriminately deleting continuity rules.

### Finding B: StoryBuilder can turn scene writing into a multi-stage compliance task

The completion pipeline can ask the model to assess missing beats or continuity conflicts after it has written. If semantic review judges beats missing, a continuation may be appended; if an integrity audit confirms conflicts, a full regeneration may be requested. This can be useful for factual reliability, but can also lead to a scene being shaped by checklist coverage instead of organic dramatic development.

**Recommendation:** For the next creative-quality test, keep the first draft visible and make review diagnostic-only. Do not automatically continue or regenerate just because a reviewer sees missing beats. Retain automatic recovery only for clearly verified, material canon or character-knowledge conflicts, after a controlled comparison shows it helps.

### Finding C: Scene Direction and the scene contract may repeat or over-specify the same concerns

The Scene Direction embeds a chapter/scene header, state, location, time, opening cast, and multiple rules about knowledge, physical continuity, completed revelations, and precedence. A scene contract and separate boundary prompt are then added. Some of this is important; repeated or overly prescriptive phrasing may make the model focus on satisfying the apparatus rather than advancing the scene.

**Recommendation:** Keep one concise scene brief that states:
1. where and when the scene starts;
2. what has already happened and what each character knows;
3. the author's intended dramatic direction and endpoint, if any;
4. hard canon boundaries that genuinely matter.

Move redundant general rules into one stable system prompt. Avoid prescribing gestures, exact emotional beats, dialogue order, or every intermediate step unless the author explicitly needs them.

### Finding D: Context management is useful, but context priority deserves observation

StoryBuilder's context budget is a safety mechanism, not itself evidence of bad writing. It deliberately preserves core state, physical continuity, canon, and author guidance while pruning optional references. But a large context may still contain too many competing instructions even when it technically fits. Conversely, pruning selected knowledge facts could matter if a relevant fact is ranked low.

**Recommendation:** Keep the budget protection. For a test, inspect the read-only Writer Context Preview and record what was included, compacted, or removed. Do not increase the context window or add more references as a first response to weak prose.

### Finding E: The recent wrong-scene generation is a state/target problem until proven otherwise

In the recent experiment, the intended test was Chapter 2, Scene 1, but the generated prose corresponded to Chapter 3, Scene 3. That result is **not a valid creative-quality comparison**. Source inspection shows StoryBuilder derives the target chapter and scene from the loaded `package.current_state`; the scene idea and Scene Direction do not independently override that target.

The source review does not establish why the app used or displayed the wrong target at the moment Write was clicked. Possible areas to investigate include which package was actually loaded, whether the UI was holding a stale state, and what the read-only Writer Context Preview showed. These are hypotheses, not confirmed causes.

**Recommendation:** Before any prose comparison, verify that the preview itself says **Chapter 2, Scene 1** and that its starting situation is the accepted end of Chapter 1. If it shows Chapter 3, Scene 3, stop before generating. Do not try to repair the prose prompt to compensate for a wrong scene target.

### Finding F: The README and live code have a configuration mismatch

LocalStoryChat's README claims a 4096-token context, while active code inspected in this audit indicates 12288. That may not affect prose by itself, but it makes comparisons less reliable if the actual runtime settings are assumed from documentation.

**Recommendation:** Verify the launched configuration before an A/B test; update the README separately once the correct value is confirmed.

## 3. What to keep, simplify, and defer

| Area | Recommendation | Reason |
|---|---|---|
| Canon, character knowledge, and starting-state protection | Keep | Prevents major continuity errors and characters knowing things they could not know. |
| Permission for ordinary interpersonal invention | Keep | Helps dialogue and relationships feel lived-in without inventing consequential plot facts. |
| Context-budget guardrail | Keep | Prevents oversized prompts; observe the preview before changing it. |
| Scene Direction plus contract plus boundary prompt | Simplify and deduplicate | Reduce repeated constraints and let the story brief carry the scene's creative purpose. |
| Historical archive snippets | Keep optional and bounded | Helpful for relevant continuity, but advisory history should not crowd out current scene intent. |
| Automatic semantic continuation | Disable for the first controlled creative test | Avoids turning perceived missing beats into an appended checklist. |
| Automatic full-scene regeneration | Restrict to verified material conflicts | A reviewer can be wrong; don't replace a potentially good draft based on uncertain findings. |
| Sampling/model settings | Hold constant during the prompt test | Changing several variables makes the result uninterpretable. |
| Old Chapter 2/3 drafts and plans | Do not mass-repair before the test | A narrow test is more diagnostic and avoids a sprawling repair project. |

## 4. Minimal test plan

1. Use only a disposable novel-package copy. Keep `~/Documents/MyNovel/Taken_at_Dusk` untouched.
2. Open StoryBuilder against that copy and inspect the read-only Writer Context Preview. Confirm the displayed target is Chapter 2, Scene 1 and the starting situation matches the accepted Chapter 1 ending. Stop if either is wrong.
3. Save or copy the exact final Writer system prompt and scene brief used for the test, if the app exposes them. Note which references were pruned or compacted.
4. Generate one scene with the current configuration and one with only the leaner scene-boundary prompt, holding story context, model, and generation settings constant. Do not count the Chapter 3, Scene 3 output as either result.
5. Compare the prose on five criteria: continuity, natural dialogue, pacing, emotional credibility, and forward movement without repeated reactions or checklist-like beats.
6. For the first pass, assess the initial draft before any automatic continuation or regeneration. Then decide separately whether reviewer recovery improved or damaged it.
7. Keep PR #45 unmerged until an actual valid prose comparison supports the change. Passing tests (reported as 304) demonstrate code/test consistency, not improved literary quality.

For the intended Chapter 2 opening, the fixed facts are simple: Chapter 1 ends with Maya telling Tony, “Tiffany is gone.” Maya witnessed the abduction; Tony did not. Tony must learn what happened from Maya. Let the explanation arrive through their stressed, imperfect conversation rather than preassigning every beat.

## 5. Limits of this audit

- This was a source-level audit, not a live run of either local application.
- No controlled A/B generation has been completed, and no single root cause for the wrong chapter/scene is confirmed.
- The LocalStoryChat README's context setting conflicts with inspected code, so runtime settings must be checked before comparing prose.
- The audit makes no code, manuscript, state-file, or writing-guidance changes.

## Bottom line

Do not add another layer of instructions yet. First ensure StoryBuilder is targeting the intended scene, then run one clean comparison. The leading design hypothesis is that StoryBuilder's layered scene instructions and post-generation completion machinery may overconstrain creative flow. Test that hypothesis by simplifying one variable at a time, while keeping canon and character knowledge protected.
