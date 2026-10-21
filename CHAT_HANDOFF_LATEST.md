## Final runtime-source grep follow-up — October 21, 2026

After the latest local `334 passed` run, Tony searched runtime source/templates for the old novel's character names and terms. One match remained at `storybuilder.py`: the Story Interview's Relationships section explicitly read `relationship_with_tony`. It was not a Writer prompt or cross-package loader, but it was still an unnecessary prior-novel field assumption.

The field lookup is now generic: always include `relationships` and `friendship_dynamics`, then include any character-card key beginning `relationship_with_`. Added a regression test that verifies the interview displays a generic `relationship_with_zoe` field, and expanded source isolation checking to cover this method. Remote commits: `8f99587a21868576c740813f1819a19eafdbb3fc` and `c6162d400dd978b35b027158adcb2b43b6d537a4`. Not yet pulled or locally tested.

Next on laptop: `cd ~/Documents/StoryBuilder && git pull --ff-only`, then `cd ~/Documents/StoryBuilder && python3 -m pytest -q`. If green, repeat the runtime grep:
```bash
cd ~/Documents/StoryBuilder && git grep -n -i -E 'Tony|Tiffany|Maya|Barnaby|Chloe|Taken at Dusk|bubble bath|cologne|pine needle' -- storybuilder.py builder templates || echo "No matches found in runtime source or templates."
```
Expected result is no matches. Keep both novels and the existing Mars draft untouched while verifying.

# IMMEDIATE NEXT STEP: Latest prompt fixes — October 21, 2026

The laptop was pulled through `f8756db`, then reported **330 passed, 4 failed**. The remaining issues have now been fixed on the remote redesign branch:
- The dynamically assembled prompt in `builder/scene_completion.py::_audit_prompt` retained an older mystery-specific paragraph even though its system prompt had been generalized. It now uses genre-neutral language about unsupported consequential facts, boundaries, speculation, and established evidence.
- `tests/test_scene_completion.py` now checks for that generic wording and explicitly guards the dynamically assembled prompt against the words `abduction` and `Tiffany` in the generic test scenario.
- `builder/scene_contract.py` retains the important “acknowledged requests/preferences” instruction while staying at 1,464 characters, under the 1,500-character guard.
- `tests/test_scene_contract.py` assertions were aligned to the intentionally shortened generic scope/provenance wording.

Latest code/test commit at checkpoint: `14cb7ba4586d94ee9c52c894a8069a7b7f40e49d`. These newest changes have **not** yet been pulled or run on Tony's laptop. Do not claim tests are green until his full `python3 -m pytest -q` result confirms it.

The local Mars package audit completed read-only: 45 regular files, 0 symlinks, 0 unreadable files. All six declared character cards match the Mars crew; current pointer is Chapter 1, Scene 3. The only keyword hits outside docs are in `Manuscript/Chapters/Chapter_01/Chapter_01_Section_01_draft.txt` (Maya x2, Chloe x2; file size 4,309 bytes; modified October 21, 2026 at 07:16). StoryBuilder's normal historical retrieval explicitly excludes `*_draft.txt`, and startup restores the accepted section, not that draft. Do not delete it during code verification. README.md and TEST_PROTOCOL.md each have one title mention and are not included in the Writer JSON reference-file assembly.

Next terminal actions, one at a time:
1. `cd ~/Documents/StoryBuilder && git pull --ff-only`
2. Then `cd ~/Documents/StoryBuilder && python3 -m pytest -q`
3. Share the full result. If green, do one final read-only verification of the actual prompt assembly before launching the app. Never edit/sync either novel as part of this audit; keep `Taken_at_Dusk` untouched.

---

# LATEST CHECKPOINT: Cross-novel code audit and package scan pending — October 21, 2026

Read `CROSS_NOVEL_CONTEXT_AUDIT_2026-10-21.md` first. The audit found and removed multiple previous-novel assumptions from shared runtime prompts/helpers: named characters and an old title in UI examples; a specific character name in continuity retrieval ranking; a mystery-specific integrity-audit instruction; prior-novel scent descriptors; and a fixed list of old character names used during cast inference. Shared Writer/contract/idea/validation prompts now use genre-neutral rules that make the original Scene Idea and established evidence authoritative. New tests cover prompt isolation, state-summary evidence precedence, read-only/copyable Scene Direction, and isolation between sibling novel packages/manuscripts.

**Local test status:** Tony's last run before these latest changes was `326 passed, 5 failed`. The failures involved prompt wording, validator prompt length, and contract-context expectations. Code/test updates address them, but the laptop must rerun the suite before verification is complete. The latest branch includes a new `tests/test_novel_package_isolation.py` and `tests/test_generic_prompt_isolation.py`.

**Important remaining diagnostic:** the actual local `~/Documents/MyNovel/The-Long-Way-Home` folder has not been inspected. The source loader stays inside the selected folder and opening a novel stops the previous Writer process, so leftover files/notes/symlinks inside the Mars folder are the remaining major cross-novel hypothesis. After tests pass, run the read-only folder scan supplied in the chat and share its output before changing any files. Do not edit either novel, do not regenerate the saved Scene 3 contract, and do not generate/accept prose during this audit. Keep `Taken_at_Dusk` untouched.

## Contract-context review finding, October 21, 2026

Inspection of `SceneContract.writer_prompt_context` confirms the contract layer separately repeats scene-idea priority/action fidelity/agency, progression/scope, event provenance, and clue boundaries. The static system prompt and scene-boundary brief already cover several of these. Some duplication is intentional, and the contract also supplies unique scene-specific facts, required beats, and the hard stop. The safe first target for simplification is duplicated *general craft guidance*, not canon, agency, character knowledge, required beats, or explicit boundaries. See the updated [STORY_FLOW_REPAIR_PLAN.md](STORY_FLOW_REPAIR_PLAN.md). No code changed.

## Prompt assembly map added — October 21, 2026

Source inspection found that the actual Writer context is layered: static Writer system prompt, generated Scene Direction/contract context, a separate scene-boundary brief, selected novel reference files, and optional retrieved historical excerpts. The static prompt and scene brief repeat several protections around required beats, emotional agency, clue boundaries, and hard stops. This may be deliberate reinforcement, so no removal is assumed. The read-only Writer Context Preview assembles the layers, estimates context size, and lists included/pruned/compacted files without generating prose or changing story state.

The plan now records this finding in [STORY_FLOW_REPAIR_PLAN.md](STORY_FLOW_REPAIR_PLAN.md). Next: inspect `SceneContract.writer_prompt_context` and, in the disposable package, use Writer Context Preview to classify duplicated instructions before designing the one-variable prose comparison. No code or novel changes.

## New writing-flow investigation — October 21, 2026

The Chapter 1 vs Chapter 2 comparison suggests Chapter 1 has more natural scene movement, while Chapter 2 sometimes repeats distress/reassurance and explains emotional conflict after the reader already understands it. This is a style hypothesis, not proof that prompt complexity alone caused the difference.

Prompt-history investigation confirmed that the creative-first Writer prompt is already merged into `main`: [rewrite commit](https://github.com/tony21675/StoryBuilder/commit/1c88b9139203886224a83eb6cdf084e72073b52f), [merge commit](https://github.com/tony21675/StoryBuilder/commit/e43314e17173d178588fea31c5969769007a7a1e). The rewrite intentionally replaced a long numbered craft-rule list with a smaller set of anchors and broader creative guidance; the scene brief was also shortened. So the next step is not to blindly revert to that version. Inspect the full current assembled Writer prompt and injected context for duplicated/conflicting instructions, and search available prompt traces for evidence of the actual Chapter 1 prompt. Git history alone does not prove the exact prompt used for that generation.

Plan: see [STORY_FLOW_REPAIR_PLAN.md](STORY_FLOW_REPAIR_PLAN.md). No app code, Story Plan, state, or manuscript prose changed. Keep accepted scenes and the real novel protected; keep the unaccepted Scene 3 draft isolated and unaccepted. No code changes yet. Next action: map current prompt assembly and trace availability, then design one controlled disposable comparison with the same model and same scene anchors. Keep canon, character knowledge, required beats, and explicit hard stops firm while giving dialogue, pacing, emotional development, gestures, and transitions more creative room.

## Final verification — October 21, 2026

Selection-aware Focused Change plus the concurrent-editor safety regression are verified by CI on code/test commit [252ab9a](https://github.com/tony21675/StoryBuilder/commit/252ab9a2c7c84d330e7a5d7f6a635a4cc3d3e3f9): **302 unit tests passed**, compile passed. Both workflows also passed on the subsequent latest handoff-only main commit: [checks](https://github.com/tony21675/StoryBuilder/actions/runs/39560296419), [tests](https://github.com/tony21675/StoryBuilder/actions/runs/39560296424). The latest repair code remains on `main`. No live desktop/local-GGUF test has been done.

**Next action:** On the laptop, first ensure no Writer generation/revision is running. Decide how to preserve or discard the unaccepted test draft; never use Close & Sync Novel for the disposable package. Then update/launch StoryBuilder from `main` with the disposable package selected and test a short selected passage, verifying that all surrounding prose stays unchanged. After the live test, update both handoffs again. Do not accept the current draft or apply its state update.

## Final race-safety regression added — October 21, 2026

Added one more focused test in [commit 252ab9a](https://github.com/tony21675/StoryBuilder/commit/252ab9a2c7c84d330e7a5d7f6a635a4cc3d3e3f9): if the Writer editor changes during model generation, Focused Change must refuse to apply the returned revision and preserve the user's newer text. This test is now part of the suite. CI for this latest test addition must finish before the test milestone is considered green; the previous 301-test baseline passed both workflows.

## Verification complete — October 21, 2026

Verified code baseline: `cb73a10bae2b1e845419d67f79eeb8a98e1abee4`; commits after this baseline have changed handoff documentation only. Both CI workflows passed on this commit: [checks](https://github.com/tony21675/StoryBuilder/actions/runs/39559964629) and [tests](https://github.com/tony21675/StoryBuilder/actions/runs/39559964594). The unit-test job reports **301 tests passed** and compilation succeeded. Code repair commit: [d382e471](https://github.com/tony21675/StoryBuilder/commit/d382e471b3c9046b9c6a77e0049aa2b7caa1221e); the subsequent test-fixture correction is [7ac07a9](https://github.com/tony21675/StoryBuilder/commit/7ac07a9b37df5a16ff9523b2185753bd96a43bcd). Changes after that were handoff documentation only. No local model/UI run has been performed yet.

**Next:** test in the local desktop app against a disposable novel, only after checking for unaccepted prose/generation and updating StoryBuilder main safely. Select only a paragraph/short dialogue span in Generated Scene, type a narrow request, apply, and compare all text before/after the selection byte-for-byte. Test one deliberate failed response/no-selection case if practical. Do not accept or sync the current novel test draft.
 
## Test-fixture correction — October 21, 2026

Fixed the incorrect stale-offset fixture in `tests/test_focused_revision.py` commit [7ac07a9](https://github.com/tony21675/StoryBuilder/commit/7ac07a9b37df5a16ff9523b2185753bd96a43bcd): its expected selected text now includes the period that is outside the truncated source slice. This was a test assertion problem; no production code changed in this correction. New CI runs have been triggered by this commit. Do not claim the selected revision path is verified until both workflows pass.

## CI checkpoint — October 21, 2026

The first CI run for implementation commit `d382e471b3c9046b9c6a77e0049aa2b7caa1221e` failed on one newly added test fixture, not a syntax or compile error: the "stale selection offsets" fixture accidentally described a slice that did match its selected text, so the helper correctly did not raise. Compile succeeded. Correct the fixture by making its claimed selected text differ from the captured slice, then rerun CI. Links: [tests run](https://github.com/tony21675/StoryBuilder/actions/runs/39559839393), [checks run](https://github.com/tony21675/StoryBuilder/actions/runs/39559839228). The selection-aware code is not yet CI-verified and has not yet been live-tested with the local model.

## Latest repair checkpoint — October 21, 2026

**Implemented on main:** [d382e471](https://github.com/tony21675/StoryBuilder/commit/d382e471b3c9046b9c6a77e0049aa2b7caa1221e), “Make focused revision selection-aware.” CI is running: [tests](https://github.com/tony21675/StoryBuilder/actions/runs/39559839393), [checks](https://github.com/tony21675/StoryBuilder/actions/runs/39559839228).

Focused Change now requires the author to select the exact passage in Generated Scene. The UI retains the local selection when focus moves to the request box, captures exact source offsets, sends the selected passage plus short read-only neighboring context, and asks the model for replacement_text only. The app checks that offsets still match the selected source, rejects whole-scene selections, and checks the entire editor still matches the captured draft before applying. A mismatch or model failure leaves the draft unchanged. Each retry now starts a fresh task context, then restores the normal Writer context. Added 8 targeted tests, including long-scene/multiline preservation, changed source offsets, target_text rejection, retry context reset, and failed edit handling.

**Not yet verified:** CI results for this commit are pending, and the local desktop/model has not been tested. Do not use the test-copy draft for acceptance or state update. Once CI passes, update local main safely using the project's normal start/sync workflow only after confirming no unfinished or unaccepted work is at risk. Then test selection-based Focused Change in a disposable novel. The previous Scene 3 draft remains unaccepted, with Chloe's emotional beat and the separate hard-stop issue unresolved.

The full audit remains at [APP_AUDIT_2026-10-21.md](APP_AUDIT_2026-10-21.md). Continue honoring all permanent collaboration/safety rules in `CHAT_HANDOFF.md`.
# Current StoryBuilder Handoff Checkpoint
Date: October 21, 2026

**Read this checkpoint first for the latest status.** It supplements the older `CHAT_HANDOFF.md`, which retains historical context and permanent collaboration rules.

## Audit complete

- Audit report: [APP_AUDIT_2026-10-21.md](APP_AUDIT_2026-10-21.md) (updated in commit `f772902fe29aaa6bad057c1d53d0c917db0141fa`)
- Code audited: `main` at `96b29b94775029e64eccee07dfd816e0dc96ffd9`
- Audit documentation commit: `f11a8987c8ed826124e486a3514f146465431103`
- Both CI workflows passed on the audited code commit: [checks](https://github.com/tony21675/StoryBuilder/actions/runs/39557373301), [tests](https://github.com/tony21675/StoryBuilder/actions/runs/39557373271).
- No application code or novel prose was changed by the audit.

## Current defect and next action

Focused Change has repeatedly failed to apply an edit because the model-generated `target_text` cannot be matched exactly in the full draft. Source review shows it asks the model to choose and copy the exact target itself. Whitespace flexibility exists, but punctuation and characters still must match. Its two attempts reuse one model conversation; attempt two repeats the full draft and includes the failed response. Focused revision also uses llama.cpp default temperature/top-k/top-p rather than task-specific sampling settings, a consistency risk but not a proven sole cause. Existing tests use short artificial text, not long real-scene prose.

**Do not retry prompt variations.** Next, agree on and implement a selection-aware patch path: the author highlights the exact passage; the app provides that exact selected source span to the model and asks for replacement text only; the app verifies the original selection still matches before replacing only that span. Reset the model context between attempts. Add tests for long prose, multi-paragraph selections, quote/punctuation variants, concurrent editor changes, retry resets, and unchanged surrounding text. No fuzzy target match that could silently edit the wrong passage.

## Other audit priorities

1. Improve visibility and effectiveness tests for Scene Contract coverage and the five-category continuity/scope audit. The last live scene overran its explicit endpoint despite the existing model-assisted review pipeline; exact reason is not yet known because the live audit output was not captured.
2. Later, consider splitting the ~418 KB `storybuilder.py` UI module incrementally.
3. Optional later cleanup: consolidate the two CI workflows into a Python 3.11/3.12 matrix; investigate the unexplained root `StoryBuilder` gitlink (mode 160000, no `.gitmodules` present); decide whether branch protection is appropriate for the main-only workflow.

## Safety and evidence boundaries

- Static source review and latest GitHub CI were inspected; this was not a local desktop/model run.
- Keep the app and novel as separate repositories. Do not change novel data during the repair.
- Resume by reading this file, then the audit report and older `CHAT_HANDOFF.md` for detailed workflow rules and historical context.
