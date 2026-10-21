

## Follow-up to local test results — October 21, 2026

Tony pulled the prior audit batch and ran the full suite: **330 passed, 4 failed**. Three failures were stale prompt-text assertions resulting from the deliberate shortening/generalization of shared guidance. The fourth highlighted a real omission: the system prompt for the integrity auditor had been generalized, but the dynamically assembled user prompt in `_audit_prompt` still carried the old mystery-specific instruction paragraph.

The dynamic prompt has now been rewritten in genre-neutral language: identify unsupported consequential facts and author-boundary violations, distinguish character-based speculation from established facts, and judge actual scope/progress. A new regression assertion verifies that the generic dynamic audit prompt does not contain `abduction` or `Tiffany`. The compact validator's wording now explicitly retains acknowledged requests **and preferences**; its measured character count is 1,464, below the 1,500-character test limit. Stale contract test expectations were updated to match the intentionally shorter provenance/scope guidance.

These changes are on the redesign branch through commit `14cb7ba4586d94ee9c52c894a8069a7b7f40e49d`. They have not yet been pulled or tested on the laptop. The next verification is `git pull --ff-only`, then `python3 -m pytest -q`, one command at a time.

The read-only local package scan returned 45 regular files, no symlinks or unreadable files, and six declared Mars crew cards matching the expected names. The current pointer is Chapter 1, Scene 3. Only the unaccepted file `Manuscript/Chapters/Chapter_01/Chapter_01_Section_01_draft.txt` contains old novel character-name matches (Maya x2, Chloe x2); it is 4,309 bytes and was modified on October 21 at 07:16. Source inspection confirms normal history retrieval excludes `*_draft.txt` and startup restores accepted prose, not that draft. No package files were changed. Leave the draft in place until code tests are green and its role has been fully assessed.

# Cross-Novel Context Audit
Date: October 21, 2026
Audited ref: `redesign/simplified-writing-workflow` at the code/test updates recorded in this branch.
Scope: Static review of all runtime Python modules, standard JSON templates, Writer/contract/scene-suggestion/integrity-audit prompts, package loading, Writer context assembly, manuscript history retrieval, and state continuity helpers.

## Executive summary

The code audit found real prior-novel assumptions in shared runtime instructions and helper functions. These were not limited to isolated test fixtures. Those shared-source assumptions have been removed or generalized on the redesign branch, and regression tests were added. The audit also confirms that package loading and historical-manuscript retrieval are scoped to the selected package path, and opening a novel stops the previous Writer process.

**Still unverified:** the actual files in Tony's local `~/Documents/MyNovel/The-Long-Way-Home` package have not yet been inspected. A copied or hybrid package could still contain old character cards, writing notes, state, extra JSON, or manuscript excerpts. The local package scan is the next decisive check. No novel package was modified by this audit.

## Confirmed runtime-source findings and fixes

1. `storybuilder.py`
   - The shared Writer prompt previously treated generated state recap text too authoritatively. It now treats that recap as fallible for consequential past events; accepted prose, canon, and explicit Scene Idea intent are used to check historical claims.
   - Scene Direction now keeps the state summary visibly qualified rather than silently certifying its claims.
   - Scene-cast inference previously excluded a fixed list of character names from a different novel. It now derives name tokens from the active package's characters and cast.
   - The Talk to Builder help example previously used a prior-novel character and title. It now uses generic examples.
   - Writer Scene Direction is read-only with a full-copy button, as requested in this branch.

2. `builder/continuity_context.py`
   - Search relevance previously included a specific character name and a promise/secret rule keyed to that name. These are now generic rules based on search intent and unknown identity, location, cause, or source.
   - A protected-fact list had specific scent descriptors from the prior story. These were replaced with general odor/scent terms.

3. `builder/conversation.py` and `builder/guided_setup.py`
   - Help and guided-setup examples previously used prior-novel character names and a specific house description. They now use generic placeholder examples.

4. `builder/scene_contract.py`, `builder/scene_idea_suggestion.py`, and `builder/scene_completion.py`
   - Shared contract, suggestion, and integrity-audit instructions previously contained story-specific examples or mystery/abduction-specific narrative advice. These have been generalized so the Scene Idea, canon, boundaries, and actual supplied story evidence drive each novel.
   - The validator prompt was shortened to remain below its 1,500-character regression limit.

5. `builder/state_manager.py`
   - Comments and action-log normalization previously contained prior character names; these have been removed or generalized.
   - Scent-clue normalization and recovery previously listed a particular story's scent descriptors. Scent handling now uses generic odor/scent markers and content words.
   - A conditional missing-person question helper remains intentionally gated by explicit evidence of an abduction/captivity event in the supplied story facts. It must not infer that event merely because someone is missing or their identity is unknown. This preserves the relevant mystery workflow without creating kidnapping questions for an unrelated genre.

6. Tests
   - Added `tests/test_generic_prompt_isolation.py` for shared prompt/source isolation and the read-only copy control.
   - Added `tests/test_novel_package_isolation.py` to prove one package load and one historical search do not read a sibling novel's package or manuscript.
   - Added/updated tests for unsupported state-summary claims, scene-endpoint handling, genre-neutral audit wording, and missing-person question inference.

## Package-isolation source findings

- `StoryPackage.load(folder)` reads the selected folder's story bible, current state, declared character cards, and extra JSON in that same folder. It does not scan sibling novel folders.
- `find_novel_packages` discovers only immediate package folders below the configured novel root.
- `StoryBuilderApp._open_novel` stops the previous Writer engine before loading the selected package and clears pending scene/UI state. `WriterEngine.start` also stops an existing child before starting a new session.
- Writer character/state references are assembled from the active `self.package`. Historical archive retrieval uses `ManuscriptManager(Path(self.package.path))`; it is not sourced from the StoryBuilder repository's audit documents.
- The root audit/handoff Markdown files and the test fixtures do contain historical examples from the prior novel. They are repository documentation/tests, not reference files supplied by `_writer_package_files()` to a live writing session.

These source boundaries make sibling-folder leakage unlikely from the package loader itself. They do not prove the selected package's contents are clean; that requires the next local check.

## Verification status and next steps

Tony's last local suite, before the latest fixes, reported **326 passed and 5 failed**. The five failures were:
- one historical-archive precedence wording assertion;
- one contract-context wording assertion;
- two checks that the validator prompt stays under 1,500 characters;
- one completed-events wording assertion.

The source/test changes on this branch address those failures, but the complete suite has **not yet been rerun locally** against the current head. Do not mark this audit fully verified until Tony pulls the branch and gets a clean test run.

Next:
1. On the laptop, check `git status -sb` in `~/Documents/StoryBuilder`. If clean on `redesign/simplified-writing-workflow`, use `git pull --ff-only` and then `python3 -m pytest -q`.
2. If tests pass, run the read-only package scan provided in chat against `~/Documents/MyNovel/The-Long-Way-Home`. It should report only filenames, symlinks, and counts of references to old names/titles, not print story text.
3. Do not delete or rewrite any package files based solely on keyword hits. Share the report first so we can distinguish legitimate quoted history from copied files, stale notes, or an external symlink.
4. Open StoryBuilder directly with `python3 storybuilder.py` rather than `./start.sh` while diagnosing. Use **Copy Scene Direction** to share the complete current direction. Do not regenerate the saved Scene 3 contract or write/accept prose during the package audit.
5. Keep `Taken_at_Dusk` untouched. Do not sync or change either novel during this verification.

## Limits

This is a source-level audit plus new regression tests, not a live Writer/GGUF run or a read of Tony's local novel files. The actual package scan and local full test suite remain pending.
