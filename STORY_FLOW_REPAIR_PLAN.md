# StoryBuilder Natural-Flow Repair Plan
Date: October 21, 2026
Status: Investigation and plan only. No application code or manuscript prose changed by this update.

## Why this plan exists

Comparing the accepted Chapter 1 with Chapter 2 of *Taken at Dusk* suggests a difference in narrative flow. Chapter 1 moves from ordinary banter to unease, danger, and Maya's arrival at Tony's home through changing actions and dialogue. Chapter 2 has important plot movement, but sometimes repeats Maya's distress, Tony's physical reassurance, and her difficulty speaking after the emotional beat is already clear. Some internal conflict is also explained more than once.

This is a useful observation, not proof that prompt length alone caused the difference. The chapters have different dramatic jobs, and there is no preserved exact record proving which final assembled prompt produced Chapter 1.

## What prompt history tells us

- StoryBuilder's creative-first Writer prompt experiment was merged into `main` in commit [e43314e](https://github.com/tony21675/StoryBuilder/commit/e43314e17173d178588fea31c5969769007a7a1e).
- The underlying prompt rewrite is visible in [1c88b91](https://github.com/tony21675/StoryBuilder/commit/1c88b9139203886224a83eb6cdf084e72073b52f): it deliberately replaced a long numbered set of craft rules with a smaller set of anchors, a creative job, and shape/voice guidance. It asks the model to make natural creative decisions and avoid repetitive emotional description without enforcing a mechanical formula.
- The accompanying scene brief was shortened in [be802eb](https://github.com/tony21675/StoryBuilder/commit/be802ebc0e3dd8f39e4461a3183ec04a8e8deffa).
- The creative-first prompt is already on `main`. The next step is not simply “restore the creative-first prompt.” Inspect the complete assembled prompt and context actually sent by the current Writer, including the contract, scene brief, canon, guidance, validators/recovery prompts, and overlapping instructions.
- The merge also included separate improvements to the continuity/scope audit and streaming. Do not casually remove those safeguards while investigating writing style.
- Git history preserves code versions, not necessarily the exact prompt/context sent for the original Chapter 1 generation. Do not claim we recovered that exact prompt unless a saved trace proves it.

## Design principle

**Give the Writer the story's anchors, then let it tell the story.**

Keep firm:
- Established canon and current story state.
- Character knowledge and whether events were witnessed or learned second-hand.
- Explicit author boundaries, forbidden content, and concrete required actions.
- The scene's emotional purpose, meaningful turning points, and hard stop/endpoint.

Give the Writer creative control over:
- Natural dialogue, banter, pauses, reactions, gestures, sensory details, and transitions.
- How emotional beats develop and change rather than repeat.
- Pacing, paragraph rhythm, small ordinary details, and connective actions.
- The exact phrasing and staging of a beat, while preserving its agency and meaning.

Do not turn every writing preference into a hard rule, duplicate the same instruction in several context blocks, or force a quota of dialogue, sensory detail, or emotion. “Fewer rules” must not mean losing canon, knowledge, or explicit boundaries.

## Repair plan, in order

### 1. Freeze the evidence and protect the novel
- Keep accepted manuscript sections and the real `~/Documents/MyNovel/Taken_at_Dusk` package untouched.
- Keep the disposable `~/Documents/MyNovel_creative_test/Taken_at_Dusk` isolated.
- Do not accept the unaccepted Chapter 3 Scene 3 draft, apply its state, or sync the disposable package.
- No code changes during prompt investigation.

### 2. Map the actual Writer prompt
Inspect the current prompt assembly end-to-end, from the top-level Writer system prompt through the scene brief and every injected context section. Identify duplicated, conflicting, overly granular, or stale rules. Separate core anchors from optional style preferences and workflow safeguards. Do not remove anything just because it is long; establish whether it adds unique value.

### 3. Recover historical evidence where possible
Review relevant prompt-history commits and available saved prompt traces. Compare versions and note what can and cannot be established. Treat Chapter 1 as a style example, not as proof of an exact prompt. If no trace exists, say so plainly.

### 4. Create a controlled disposable test
Use one short, representative scene or passage in the disposable package and the same local model/settings. Compare the current assembled prompt with a proposed leaner prompt while holding canon, scene intent, required beats, and hard stop constant. Change one variable at a time. Do not bundle prompt, sampling, validator, and story-plan changes.

### 5. Review the prose, not the rule count
Evaluate whether the scene feels like events unfolding rather than explaining intended emotion; whether emotional beats progress instead of repeating; whether dialogue, action, and transitions flow naturally; whether key movements and character agency remain intact; whether canon and knowledge are respected; and whether the scene stops at the intended boundary.

### 6. Decide from evidence
Keep the simpler variant only if it improves flow without increasing continuity errors, missed beats, or hard-stop overruns. If results are mixed, isolate the cause and run one more controlled comparison. No broad refactor, sampling change, or validator redesign belongs in the first experiment.

### 7. Implement only the agreed smallest change
After reviewing the evidence together, make one scoped change and add tests for the intended behavior and the boundaries it must preserve. Run CI, then perform one live local-GGUF test in the disposable package. Report unit-test evidence separately from live-generation results.

## Current status and next action

The source-history review confirmed that the creative-first prompt is already merged. The remaining investigation is to map the current assembled Writer prompt and look for saved traces that could establish what was actually sent to the model. No code or manuscript change is authorized or made by this plan.
