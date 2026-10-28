# StoryBuilder Long-Term Goals

**Purpose:** Keep future product ideas separate from the active bug-fix and current-novel work tracked in `CHAT_HANDOFF.md`. This is a discussion backlog, not authorization to implement everything listed.

**Status:** Living document. Ideas are candidates unless explicitly marked approved. Review and prioritize with Tony before implementation. Do not let this list interrupt the current novel task.

## Permanent working method: Fix Now / Add Later

Keep two tracks, in this order:

### FIX NOW — active work

- The immediate issue, its root cause, the smallest agreed fix, affected files, tests, and the exact live verification still needed belong in `CHAT_HANDOFF.md`.
- First inspect the live source and current GitHub `main`; do not assume old notes describe the current implementation.
- Discuss a proposed change before editing. Explain what it changes, why, and its likely effect or risk, and wait for Tony's approval unless he has explicitly approved that specific action.
- Make one focused, testable change at a time. Preserve accepted manuscript scenes, current story state, author-approved Scene Ideas, and existing working prose.
- Run relevant regression tests and distinguish automated test evidence from behavior actually observed with Tony's local model.
- Update `CHAT_HANDOFF.md` with the current status, the verified result, and one clear next step. Keep it operational, brief enough to resume from, and free of speculative feature planning.
- Do not start a later feature while an active fix or live test is unresolved unless Tony explicitly reprioritizes it.

### ADD LATER — product ideas

- Keep future features, architecture ideas, trade-offs, and open design questions in this file.
- Items remain **proposed**, not implicit promises or implementation instructions.
- Before promoting an item into FIX NOW, discuss scope, intended behavior, risks, and how we will test it. Only the agreed scope moves forward.
- Avoid speculative refactors, unnecessary new settings, prompt bloat, duplicate canon stores, or features built only because another application has them.
- Use one branch per repository: `main`. Commit approved, verified work directly to `main`; do not create temporary branches.
- Keep StoryBuilder generic. Novel-specific facts, rules, and decisions belong in that novel's own files, not hard-coded into the app.

## Long-term design principles

1. **Keep the author's destination and creative freedom together.** The plain-English Scene Idea expresses intent and meaningful waypoints. Required Beats should be explicit author-defined requirements, not every incidental detail. The Writer remains free to invent natural dialogue, gestures, pacing, transitions, and connective action inside those boundaries.
2. **One source of truth per kind of information.** Distinguish durable canon, style guidance, current state, scene direction, and transient revision notes. Avoid copying the same rule into several competing files with different authority.
3. **Make data flow visible and testable.** A rule stored in a novel must reach the Writer and any relevant validator. Tests should assert which instructions a stage actually receives, not merely that the source file contains them.
4. **Propose before changing.** Generated revisions and state updates stay reviewable. Acceptance remains the author's decision. Failed or unaccepted attempts should not create clutter unless Tony chooses to save them.
5. **Prefer graceful, honest failure.** Do not silently replace missing guidance, an unavailable model, invalid structured output, or failed validation with plausible-looking fallback content. Preserve recoverable work, identify what failed, and show a copyable error.
6. **Fit the local machine.** Keep the existing Gemma 4 E4B GGUF through llama.cpp as the general-purpose writer. The author has access to a 16 GB RAM laptop temporarily for the next couple of months; older notes describe the longer-term 8 GB RAM laptop. Use the temporary headroom to test a separate, more capable adult-erotica model, but consider memory available for the OS, runtime, and context, and keep a smaller fallback for the longer-term machine. Never change or replace the model without discussion.
7. **Test general behavior, not just one novel.** Add regression tests for minimal/older novel packages, multiple novel configurations, natural paraphrases, missing meaningful actions, and invalid model responses.

## Proposed roadmap

The order below is a suggested discussion order, not a promise to implement without review.

### 1. Focused revision workflow

**Problem to solve:** When a scene is mostly good, the author needs a precise correction without restarting the whole scene or losing working prose.

**Possible design:**
- The author selects or describes a specific issue in the current unaccepted scene.
- StoryBuilder prepares a focused revision request using the author's wording, the saved Scene Idea, relevant stable guidance, starting state, and current prose.
- The revised scene remains a proposal until reviewed. Where practical, show a readable before/after or word-level difference.
- Keep unrelated passages and accepted scenes untouched. Do not save extra draft files automatically.
- Verify that the requested change was made and that material events, relationships, knowledge, action order, and the scene endpoint were preserved.
- If validation is unavailable, say so clearly; never claim a revision passed when no usable check ran.

**Open questions:** Should revision target an entire scene only, or allow author-selected passages? What is the simplest readable comparison in the existing UI? How can the app avoid over-rewriting when the request is small?

**Reference:** Brasslamp's public [revision and review approach](https://github.com/brasslamp-app/brasslamp) is inspiration, not a design specification to copy.

### 2. Modular prompt files

**Problem to solve:** Major prompt instructions are currently spread between constants and prompt-building code. They can be hard to inspect and safely tune.

**Possible design:**
- Store task prompts in readable, version-controlled text files with a small loader and an explicit manifest.
- Separate task roles: Writer, scene-contract builder, semantic validator, state/continuity analyzer, and any future planning/interview stages.
- Keep truly universal safety or schema requirements protected in code where appropriate; keep creative behavior instructions editable and testable.
- Assemble prompts from clear components with documented precedence. Include a small test or diagnostic view for the final assembled prompt so missing context can be caught.
- Preserve today's behavior first: extraction should be a behavior-preserving refactor, not a simultaneous prompt rewrite. Compare assembled prompts and run all regression tests before changing content.
- Do not let modular files multiply the same rule across several prompts unnecessarily.

**Risks:** Prompt fragmentation, contradictory instructions, accidental omissions, oversized context, and configuration that is harder for the user to understand. Keep the first version simple.

**Reference:** Brasslamp's `prompts/` tree and `builder_prompts.py` loader use separate task/genre files, an audience layer, and a manifest. See [its prompt directory](https://github.com/brasslamp-app/brasslamp/tree/main/prompts) and [loader](https://github.com/brasslamp-app/brasslamp/blob/main/builder_prompts.py).

### 3. Optional audience and genre profiles

**Problem to solve:** StoryBuilder should support different novels without hand-editing its core code for every genre or intended readership.

**Possible design:**
- A novel can optionally choose a genre/profile and intended audience, with a useful general-fiction default.
- Profiles influence relevant brainstorming, story-bible development, planning, and writing choices, but do not override established canon or explicit author instructions.
- Allow custom genre blends as a compact saved profile: main story engine, reader promises, structural emphasis, tone, and things that would betray the intended blend.
- Use audience profiles as content/tone guidance, not as a replacement for author-approved boundaries.
- Keep profile choices attached to the novel, and shared reusable profile templates attached to StoryBuilder.
- A profile should be skippable; don't make setup a quiz or force users to complete a large planning interview before writing.

**Open questions:** Start with just a small list of profiles or let authors begin with general fiction and add a profile only when needed? Should custom profiles be generated through an optional guided interview or edited directly as text?

**Reference:** Brasslamp separates `prompts/audience/`, `prompts/bible/`, `prompts/chapters/`, `prompts/genre/`, `prompts/series/`, and `prompts/writing/`. Review examples from [its prompt library](https://github.com/brasslamp-app/brasslamp/tree/main/prompts).

### 4. Optional prose-health checks

**Problem to solve:** A scene can preserve canon yet still contain obvious mechanical defects, such as duplicated sentences, phrase loops, repeated openings, abrupt truncation, or model commentary.

**Possible design:**
- Add lightweight checks after generation for clear mechanical breakdowns.
- Feed precise feedback into a limited retry only for well-defined failures.
- Keep semantic/canon violations separate from stylistic observations.
- Initially show non-blocking warnings for subjective quality. Do not make every style preference a gate.
- Retain the least-bad generated attempt when retries exhaust, keep it unaccepted, and explain what remains unresolved.
- Ensure paraphrases and deliberate stylistic repetition are not rejected merely for varying from a template.

**Trade-offs:** Additional processing and retries cost time and may worsen good prose if a detector is too strict. A local model's self-judge can be lenient or inconsistent, so use it cautiously.

**Reference:** Brasslamp combines deterministic prose-health checks with an optional model judge. Its public [README](https://github.com/brasslamp-app/brasslamp#quality-gate) distinguishes mechanical quality gates from literary merit.

### 5. Read-only whole-novel continuity review

**Problem to solve:** The current scene check sees local intent and context; as a book grows, the author may benefit from a separate read-only pass that finds cross-scene contradictions or overlooked story threads.

**Possible design:**
- Audit accepted manuscript scenes against canon, chronology, character knowledge, and explicit must-hit events.
- Show the relevant evidence, scene location, issue type, and confidence/uncertainty.
- Distinguish confirmed contradictions from possible concerns and editorial suggestions.
- Build a review list that can retain findings across repeated audits and show whether a finding is new, persistent, or apparently resolved.
- No automatic manuscript changes. The author chooses a finding, discusses it, then uses focused revision if appropriate.
- Avoid repeating the same finding in every report without acknowledging it was already reviewed.

**Trade-offs:** More model calls, possible false positives, and the need for careful evidence linking. Begin as an opt-in report only, not as a new hurdle before accepting every scene.

**Reference:** Brasslamp's continuity and story-audit reports offer ideas for whole-book checks. See [continuity.py](https://github.com/brasslamp-app/brasslamp/blob/main/continuity.py) and [storycheck.py](https://github.com/brasslamp-app/brasslamp/blob/main/storycheck.py).

### 6. Relevant-passage retrieval for long novels

**Problem to solve:** Short current-state summaries cannot preserve every meaningful earlier interaction, planted object, promise, or relationship turn.

**Possible design:** Retrieve a small number of earlier accepted passages relevant to the current Scene Idea and supply them as context, while keeping current state and canon authoritative.

**Do not implement by default yet.** It may require an embedding endpoint/model, caching, additional settings, and CPU/RAM or latency. First determine whether actual long-novel failures justify it. Any retrieval result is supporting evidence, not a new source of canon.

**Reference:** Brasslamp's optional retrieval block selects semantically related earlier scenes and caches embeddings in [bookgen.py](https://github.com/brasslamp-app/brasslamp/blob/main/bookgen.py).

### 7. Canon-ledger improvements only if needed

Brasslamp's rolling canon ledger preserves older facts a later summary forgets and lets newer facts replace stale facts about the same subject. That is a useful idea, but StoryBuilder already has character cards, canon rules, current state, and character knowledge.

Before adding another ledger, map the current sources of truth and determine whether a specific category of fact is being lost. Prefer strengthening the existing source or adding a clearly defined field over creating a parallel canon store.

### 8. Optional series-level planning

A later series profile could track the multi-book arc, per-book resolutions, shared cast/world facts, and threads that cross books. Keep it separate from the current single-novel writing workflow until Tony has a concrete series use case and explicitly prioritizes it.

## Research notes: Brasslamp

Brasslamp is a local-model novel-writing studio. Its public repository describes modular genre/audience prompts, scene-by-scene drafting, rolling story state and canon, targeted retries, whole-book audits, revision diffs, and version history. The project says it is in open testing; treat it as a source of useful patterns, not proof that every part suits StoryBuilder.

Its closed [issue #2](https://github.com/brasslamp-app/brasslamp/issues/2) documented a real configuration handoff failure: an import path lost the connected model settings/API key, silently fell back to a default endpoint, and could produce a useless outline from fallback summaries. The maintainer fixed the shared connection handoff, showed errors in the relevant UI, and aborted when all initial derivations failed. The lesson for StoryBuilder is to test end-to-end prompt/configuration plumbing and fail visibly rather than report a degraded result as success.

## Not part of the plan unless separately discussed

- Replacing StoryBuilder wholesale with Brasslamp.
- Making detailed beat-by-beat planning mandatory for every scene.
- Forcing word targets, extra interview stages, or genre configuration onto novels that do not need them.
- Automatic acceptance or automatic editing of accepted manuscript scenes.
- Adding another model or external embedding dependency without checking resource needs.
- Hard-coding Taken at Dusk's characters, canon, or Scene 4 details into generic StoryBuilder code.
- Implementing every item in this file simply because it is written here.

## When to revisit

Revisit this list only after the active item in `CHAT_HANDOFF.md` is resolved or Tony explicitly changes priorities. Move one agreed item into FIX NOW, define its acceptance criteria, discuss the implementation, and test it before taking up the next item.
