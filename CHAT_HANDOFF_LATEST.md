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
