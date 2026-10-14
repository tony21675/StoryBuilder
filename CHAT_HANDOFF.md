# StoryBuilder Chat Handoff

## First instruction for every new session

Read the current versions on GitHub `main` before acting:
1. [MyNovel HANDOFF.md](https://github.com/tony21675/MyNovel/blob/main/HANDOFF.md)
2. [MyNovel STORY_PLAN.md](https://github.com/tony21675/MyNovel/blob/main/STORY_PLAN.md)
3. [MyNovel current_state.json](https://github.com/tony21675/MyNovel/blob/main/current_state.json)
4. [MyNovel writing_guidance.json](https://github.com/tony21675/MyNovel/blob/main/writing_guidance.json)
5. The complete accepted immediately preceding scene and its saved before/after-state files, from the active local novel package.

**Use the newest checkpoint below as the session handoff. Older conversation context or stale repository copies do not overrule the current author-confirmed checkpoint.**


## Permanent workflow: FIX NOW / ADD LATER

- **FIX NOW lives here:** current bug or writing blocker, latest evidence, smallest approved correction, relevant tests, outstanding live verification, and one next step. Keep the active novel task and safe repository steps clear.
- **ADD LATER lives in [LONG_TERM_GOALS.md](LONG_TERM_GOALS.md):** future architecture and product ideas, candidate features, trade-offs, and open design questions. Those items are not implementation authorization.
- Always discuss changes before editing. Inspect first; explain the proposed scope, reason, and trade-offs; wait for Tony's approval unless he has already explicitly approved that exact change.
- Work one focused change at a time, preserve accepted scenes and state, test the generic path, and separate passing automated tests from live local-model results.
- Do not start long-term work while the current issue/live test is unresolved unless Tony explicitly changes priorities.


## Fix Now: validator false-pass on explicit Scene Idea details — October 14, 2026

- **Observed defect:** the Chapter 2, Scene 4 trace showed the prose omitting the explicitly requested bubbles in a warm bubble bath, but semantic validation returned `pass: true` with no missed beats or violations.
- **Generic correction committed on `main`:** when an original plain-English Scene Idea is present, the validator must return an itemized coverage report for each material action/outcome, defining object detail/history, named participant/confirmation, acknowledged boundary, meaningful location/order, and endpoint. Each claimed-met item needs a short verbatim quote from the generated scene. StoryBuilder checks that the quote is actually present; missing items and unsupported quotes become validation failures and revision feedback. Missing/malformed coverage is retried once, then validation is marked unavailable so the draft is not accepted without a usable check. No Scene 4 wording is hard-coded.
- The validator token budget default was increased from 220 to 700 so it has room to return the coverage report; `STORY_VALIDATOR_MAX_TOKENS` can override the setting.
- Regression coverage includes a reported missing bubble-bath detail despite `pass: true`, fabricated/non-verbatim evidence, and missing coverage schema. Relevant commits: [validator coverage enforcement](https://github.com/tony21675/StoryBuilder/commit/69dd195cf88454897a627803004531dc15d36b1b), [regression tests](https://github.com/tony21675/StoryBuilder/commit/660d0404e80439564f7033a6247e511c86a8867f), [prompt-input limit update](https://github.com/tony21675/StoryBuilder/commit/5d5d8fee9fa21a305337217033738d337ba44dc1), and [final validator prompt-size assertion update](https://github.com/tony21675/StoryBuilder/commit/c3a42ccf4f4c8e4e7ea959cd71b0b58972e0e8a6).
- **Verification status:** code/test files are committed and were fetched back from `main` for inspection. This session could not retrieve a push-triggered GitHub Actions run or run the repository tests locally, so automated test results are **not yet verified**. This also is not yet a live Gemma 4 validation result.
- **Next step on laptop:** after confirming `~/Documents/StoryBuilder` is clean and on `main`, update/launch StoryBuilder, run `python -m unittest discover -v`, and share any failures before another code change. If tests pass, use one fresh unaccepted Scene 4 generation to verify the validator flags the missing bubbles and any other absent material commitments. Keep MyNovel unchanged for this code fix and do not accept the generated scene without review.


## Approved diagnostic feature: one-scene Prompt Trace — October 14, 2026

- Added an opt-in **Trace Next Scene** control to the Writer tab. It is off by default; arming it captures only the next scene-generation run, then automatically disarms.
- The trace records the system prompts and their roles, scene start state, exact scene request before and after the Writer's line-flattening step, model output returned to StoryBuilder, available llama.cpp prompt/generation diagnostics, runtime context/token settings, each validator exchange, validator outcomes, and focused-revision feedback.
- The local trace is a single JSON file at `~/.local/share/storybuilder/prompt_trace.json`, saved when the one-scene capture finishes. It may contain unpublished story material and internal prompts.
- **Private GitHub sync:** after a scene is traced, StoryBuilder automatically uploads that one file to `StoryBuilder-Traces` under the authenticated GitHub account. `STORYBUILDER_TRACE_GITHUB_REPO=owner/repository` overrides the default destination. The app checks that the repository is private and refuses to upload if other files besides `prompt_trace.json` are present. The app uses `STORYBUILDER_TRACE_GITHUB_TOKEN`, `GH_TOKEN`, or `GITHUB_TOKEN` if configured; otherwise it reads the token from `gh auth token`. Never save tokens in StoryBuilder or a repository. If authentication/permissions fail, the local trace remains and the Writer status reports the sync error.
- The first upload initializes an empty repository with the trace. Subsequent uploads rewrite the target branch to a root commit whose tree contains only `prompt_trace.json`, avoiding a visible chain of prior trace commits. This is not a secure-erasure guarantee: GitHub may retain unreachable objects temporarily, and anyone who already copied a trace may still have it.
- When **Trace Next Scene** is off, no trace is collected or uploaded. Tracing is still one scene at a time and auto-disarms. Upload failure must not affect draft preservation or scene status.
- **Next action on laptop:** confirm `~/Documents/StoryBuilder` is clean on `main`, then launch `./start.sh`. Arm **Trace Next Scene (Off)** and run the scene. The Writer-tab status should say the trace synced to private GitHub and show its file URL; if it does not, share the sync error rather than pasting the full JSON into chat.
- Automated tests cover trace serialization plus mocked private-repo initialization, history replacement, privacy checks, extra-file refusal, and missing authentication. GitHub Actions [run 38648658553](https://github.com/tony21675/StoryBuilder/actions/runs/38648658553) passed the compile checks and all **127 unit tests** on commit [962d3fd](https://github.com/tony21675/StoryBuilder/commit/962d3fd20f283d8630f0f9f5cfd61e5931920550). The laptop's local run and a real GitHub upload are still unverified. Relevant code commits: [uploader](https://github.com/tony21675/StoryBuilder/commit/67ce25c81aabfb9addcdfe30eef10bd3b1bd205c), [Writer integration](https://github.com/tony21675/StoryBuilder/commit/bce3cd7fbdc376c8a90ec1d6f55f7cdd8c8e7faa), and [empty-repository branch handling](https://github.com/tony21675/StoryBuilder/commit/5a2e079f7c9b145804d55023e251a5770bf83154).

## Latest Checkpoint: October 14, 2026 (author guidance and prose fidelity)

### Newest MyNovel live test and approved Scene 4 direction — October 14, 2026

- After the latest StoryBuilder update was launched, the newest Chapter 2, Scene 4 generation completed without the old error popup. It respected the no-floral-scent rule, kept quiet after Maya asked for it, and fetched pajamas from Tiffany's bedroom. It included both breakfast calls, Barnaby's history and Tony's vow, Maya's robe, and chamomile tea.
- That generated prose remains **unaccepted**. Remaining focused corrections: make the bath explicitly a warm bubble bath; have Tony clearly check that Maya welcomes his help into the tub, assist her in a practical, respectful, nonsexual, fatherly way, make sure she is settled and comfortable, then leave to give her privacy and quiet; and make Beth's invitation specifically for breakfast tomorrow morning, not a question about her afternoon.
- The existing MyNovel Scene 4 idea and required beats have now been updated on GitHub to reflect that flow. A new generation may be underway while this handoff is being updated; let it finish before closing the app, syncing, or reloading guidance. Its source version has not yet been confirmed, so do not count it as a test of the updated scene instructions until verified. Review the result while it is still unaccepted. Afterward, safely refresh the local MyNovel guidance if needed, without rebuilding the contract, altering accepted Scenes 1–3, changing current story state, or accepting Scene 4 without Tony's review. Apply only a focused revision.
- **Confirmed family-care canon:** Tony thinks of Maya and Chloe as daughters of his heart and loves them almost as he loves Tiffany, though they have their own parents and homes. When the actual situation calls for it, practical parental care can include help with bathing or dressing. Keep it respectful, nonsexual, and attentive to their adult wishes, consent, comfort, privacy, and dignity. Do not treat it as automatically taboo or awkward because Tony is not their biological father, and do not force it into scenes where it is not needed. This paternal bond stays distinct from the separately established private feelings arcs.
- MyNovel reference updates: [Tony's character card](https://github.com/tony21675/MyNovel/commit/6b51688558b550ee2f7441b55fa225eb925246a9), [stable writing guidance](https://github.com/tony21675/MyNovel/commit/e24d8d91621b536d993a0fcb53930b70dbc90f30), [Scene 4 instructions](https://github.com/tony21675/MyNovel/commit/b3cfce5ea0dd8b43d90a6c16649d26a0ea4dd158), [story plan](https://github.com/tony21675/MyNovel/commit/e63a71cf67c78083b91480a2dc041079cc79f1f4), and [latest novel handoff](https://github.com/tony21675/MyNovel/commit/34c489b663c2781d497fc630ff88f177d6fe66ba).

### Approved generic fix: stable instructions now reach the Writer and validator

- **Root cause:** The Writer assembled scene state, character cards, and author-defined canon rules, but did not pass through the novel's separate writing_guidance.json lists: recurring_instructions, relationship_freedom, and avoid. A rule could exist in the active novel but be absent from the model's actual prompt.
- **Implementation on main:** StoryBuilderApp._author_writing_guidance() collects those stable lists without importing scene-specific plan text as general canon. _writer_package_files() includes them in the Writer's scene reference, and both first-pass generation validation and edited-prose validation now supply the same stable guidance to the semantic validator. The helper also safely handles minimal/legacy package objects without extra_json.
- **Prose consistency:** The generic Writer prompt now instructs the model to honor a character's direct request, preference, boundary, or need after another character acknowledges it, unless the scene gives a reason to do otherwise. The validator checks meaningful source locations and event order as well as action/object identity, and checks for unexplained violations of acknowledged requests. It still allows paraphrase, natural dialogue, and creative connective prose; it should not add mandatory beats for every ordinary detail.
- **Commits:** [guidance plumbing](https://github.com/tony21675/StoryBuilder/commit/c98324b053ef77b8612de405e9d37d6bbf99b834), [prompt-budget and package-safety follow-up](https://github.com/tony21675/StoryBuilder/commit/0e16333f310c93ed722561aa0d30153dc2456c1c), [validator wording restored within test budget](https://github.com/tony21675/StoryBuilder/commit/4f7e97c2d3f3d8cf36c16b54946c8a6158b90f66), and [final continuity-prompt adjustment](https://github.com/tony21675/StoryBuilder/commit/1b5aba6fe3b007a14b2fb6edc5f46d76c4f87b2b). GitHub Actions [run 38631481510](https://github.com/tony21675/StoryBuilder/actions/runs/38631481510) passed compilation and all **114 unit tests**.
- **Verification boundary:** CI proves compilation, context plumbing, and prompt regression tests; it does not prove the local Gemma 4 model will catch every violation in a live scene. Do not describe this as confirmed live prose compliance until Scene 4 has been generated and validated with this exact update.

### Live scene observations and next laptop step

- Tony relaunched the prior copyable-error-dialog update and generated Chapter 2, Scene 4 to completion **without the old error popup**. That is a successful live check of the previously reported popup problem for this run.
- That prose remains **unaccepted** and was generated before the latest author-guidance/validator commit above. It included lavender bath scent despite the standing no-floral rule, music after Maya requested quiet, and pajamas fetched from a linen closet instead of Tiffany's bedroom. It preserved the actual bubble bath and Barnaby's backstory. Do not accept this attempt or edit accepted Scenes 1–3.
- Tony's current preference is to discard failed/unaccepted Writer attempts rather than save separate draft files. When closing this older app instance, discard this unaccepted attempt if prompted; do not accept it or save a draft unless Tony changes that preference.
- On the laptop, inspect git status with **git status -sb** and the current branch with **git branch --show-current** in ~/Documents/StoryBuilder. Only if clean on main, run **./start.sh** to sync and launch the latest code. That startup updates StoryBuilder only, not MyNovel.
- Reopen Taken_at_Dusk and test a new Scene 4 attempt with the saved Scene Idea, without rebuilding its contract or changing writing_guidance.json, current_state.json, or accepted Scenes 1–3. Check for no floral scent, respect for Maya's request for quiet, pajamas obtained from Tiffany's room, bath bubbles, and Barnaby's stated history. Review the whole scene before accepting. Use focused revision if the validator flags a real issue; do not rewrite prose in chat as a shortcut.

### Long-term ideas moved to the separate goals file

The detailed Brasslamp prompt-library comparison and candidate features now live in [LONG_TERM_GOALS.md](LONG_TERM_GOALS.md). Keep this handoff focused on the active fix and the next action. The Brasslamp findings remain useful background, but they are not current implementation tasks unless Tony explicitly promotes one through the Fix Now / Add Later workflow.

## Approved error-dialog repair — October 14, 2026

- Tony reported that a long error appeared after Writer produced a scene, but the popup text was too long to read or copy. The previous fix had not covered every error path: there were still ordinary Tkinter `messagebox.showerror` calls across the application, and the validator-unavailable path still displayed a standard warning with technical diagnostics.
- Approved repair committed to `main`: all 52 ordinary `messagebox.showerror` call sites now use the shared scrollable, copyable error window. Four additional warnings that may contain long technical details (unavailable scene validation, failed edited-scene validation, recovery-snapshot failure, and novel-open exception) also use it. Short routine warnings and confirmation dialogs remain unchanged.
- **Copy Full Error** and **Close** now appear in an action row above the expandable text area so the copy button stays visible on shorter displays and long tracebacks cannot push it out of reach. The original error detail remains scrollable; copying still uses the main window's clipboard.
- Source change: [copyable diagnostics implementation](https://github.com/tony21675/StoryBuilder/commit/6688dd549609b55e61fabb1d03cdeeafff60b558). Regression-test follow-ups: [update validation-path expectations](https://github.com/tony21675/StoryBuilder/commit/bde06cebfc97f5b8986f31c424ab690921796a92) and [final test correction](https://github.com/tony21675/StoryBuilder/commit/71c7d46e8f37e66d094c5ed6525a4e77d7cdadd9). GitHub Actions [run 38565054069](https://github.com/tony21675/StoryBuilder/actions/runs/38565054069) passed compilation and all **113 unit tests**.
- Live verification completed for the reported case: Tony later relaunched the copyable-dialog update and a new Scene 4 generation finished without that popup. This confirms the popup did not recur in that run, not that every error path has been live-tested. The newest author-guidance/validator improvement is a separate later commit and still needs a live test.
- **Current author preference:** do not save failed/unaccepted scene attempts as drafts. Review generated prose; keep it only when Tony accepts it. At the next close prompt for the failed current attempt, discard it rather than saving or accepting. Do not touch accepted Scenes 1–3 or alter story state to test this UI repair.

## Latest Checkpoint: October 14, 2026 (confirmed model and writing workflow)

### Current model: Gemma 4

- **Confirmed current local writing model:** `~/Documents/Models/01 gemma-4-E4B_q4_0-it.gguf` (Gemma 4 E4B, Q4_0 instruction-tuned GGUF). This exact path is recorded in the earlier project handoff and matches Tony's latest confirmation.
- Older conversational notes contain superseded model references. Treat this current checkpoint and the selected Gemma 4 GGUF above as authoritative; Qwen is not current.
- `llama.cpp` / `llama-cli` is the inference runtime StoryBuilder launches. Those names in source code, logs, and configuration do **not** mean the loaded model is Llama. StoryBuilder loads the selected GGUF from the Models directory; do not hard-code a model family into reusable app logic.
- Default workspace behavior on Tony's documented layout puts the model directory at `~/Documents/Models`. The current model is a local asset, not a GitHub file. Never delete or replace it during routine cleanup without Tony's approval.

### Current writing workflow

1. The active novel's `current_state.json`, accepted prose, character canon, and saved plain-English Scene Idea in `writing_guidance.json` are the continuity source of truth. The original Scene Idea expresses the author's destination and meaningful waypoints; model-generated direction/contract are supporting guidance. Only Required Beats explicitly labeled by the author become formal required beats. Keep the writer's room for natural dialogue, pacing, shared memories, gestures, and connective actions.
2. Use **Build Scene Direction** to assemble context, then **Write Next Scene**. StoryBuilder writes the prose; the assistant reviews and diagnoses specific canon, continuity, character-knowledge, and scene-boundary issues. Do not rewrite scene prose in chat or edit accepted manuscript prose unless Tony explicitly asks.
3. Review the entire generated scene. Save Draft is available for preserving a draft. A readable semantic validation failure follows the focused-revision path, which should preserve working prose rather than restart blindly.
4. If the scene is accepted, continue **Analyze Accepted Scene** → review the proposed state patch → **Apply State Update** → **Build Scene Direction** for the next scene. Do not analyze before acceptance. **Reject Scene** discards the unaccepted generated attempt without changing accepted prose or current state.
5. Before closing or leaving a scene with unsaved Writer text, answer the save/discard/cancel prompt. Cancel keeps the app/text in place. Tony's current policy for this novel is to discard failed/unaccepted attempts rather than save draft files; do not select Save Draft unless he explicitly changes this preference.
6. StoryBuilder and MyNovel are independent Git repositories. From `~/Documents/StoryBuilder`, `./start.sh` syncs **StoryBuilder only** and launches the app; it does not sync the novel. Check each repository's `git status -sb`; only fast-forward a clean `main` checkout. Do not use **Close & Sync Novel** as a way to update application code, and do not reset or pull a dirty novel checkout.

### Author-specified detail fidelity update — October 14, 2026

- Tony approved a focused follow-up to preserve not only the identity of an intended action/object, but also defining details and stated history or relationships that give it meaning. This should improve fidelity without turning ordinary scene ideas into line-by-line checklists.
- The Writer boundary now explicitly says not to discard distinctive details or meaningful object history. The semantic validator now checks those details as well as action identity. Focused revision guidance tells the Writer to restore the omitted detail while preserving the prose that already works. This remains generic and does not hard-code *Taken at Dusk* into the app.
- In the Scene 4 example, the warm bubble bath needs to remain a bubble bath (including bubbles), and the prose should retain the stated history of the stuffed rabbit Tony gave Tiffany after Sarah died.
- Code: [detail-fidelity writer/validator update](https://github.com/tony21675/StoryBuilder/commit/1426c81fb573d10607ee9b01aacf7a163f531455) and [final concise validator/test compatibility fix](https://github.com/tony21675/StoryBuilder/commit/f346c85a0748b96c73bff5deead5492afc4d0c42). GitHub Actions [run 38535836346](https://github.com/tony21675/StoryBuilder/actions/runs/38535836346) passed compilation and all **110 unit tests**. These tests verify code and prompt expectations, not live Gemma 4 compliance.

### Current Scene 4 live-test status

- The newest unaccepted draft keeps the action as a bath, but Tony offers a “nice hot bath” without the specified bubbles. Tony hugs Barnaby and privately vows to find Tiffany, but the draft omits the history that Tony gave Barnaby to Tiffany after Sarah died.
- Tony saying “Maya’s here” to Beth is acceptable; Beth will understand Maya is safe in Tony’s care. Do not require Tony to use the literal word “safe.” Maya may join Tony in either a towel or a robe after bathing; both are acceptable.
- It is not confirmed whether this draft was generated and validated using the new action-fidelity code or whether StoryBuilder was still running an older copy. Do not label it a successful live test of the updated code. The scene remains unaccepted, and the active Writer draft’s save status is unknown.
- Next session: preserve the active Writer draft with **Save Draft** if needed, close StoryBuilder normally, inspect `git status -sb`, and update only a clean StoryBuilder `main` checkout. Relaunch with `cd ~/Documents/StoryBuilder && ./start.sh`. Review the loaded Scene Idea/contract and use the Writer’s focused revision workflow on the preserved draft; if it is no longer available in the app, test a fresh attempt using the same saved Scene Idea. Check specifically for the bubbles and Barnaby’s stated history. Review before accepting. Do not change `writing_guidance.json`, `current_state.json`, or accepted Scenes 1–3 for this code test. **Close & Sync Novel** does not update StoryBuilder source.

## Previous Checkpoint: October 14, 2026 (scene-contract validator JSON recovery)

### Root cause and approved fix

- Tony reported that he clicked **Write Next Scene**, the prose appeared, then the dialog said “The continuity manager did not return a JSON object.” **Accept Scene** and **Analyze Accepted Scene** were disabled; Tony had not accepted or analyzed anything.
- Diagnosis: the scene-contract validator reused a shared JSON parser that emitted the continuity-manager error text. The Writer had generated prose, but a malformed validator response was treated like a scene-generation/validation failure and marked the draft as blocked.
- Tony approved a generic repair to distinguish unreadable validator output from a genuine semantic failure.
- builder/scene_contract.py now reports scene-contract response-format errors accurately and retries the validator once with a strict JSON correction prompt. This is a retry of the validator, not a blind rewrite of the scene.
- If the response remains unreadable after that retry, StoryBuilder stops its automatic scene-revision loop, preserves the generated prose as an unaccepted draft, clearly warns that semantic validation was unavailable, and allows **Save Draft** and **Reject Scene**. **Accept Scene** is enabled, but accepting requires a separate confirmation that the author reviewed the unvalidated prose. A readable validator response that reports missing core actions or material contradictions still follows normal focused-revision validation; this recovery does not turn a genuine failed check into a pass.
- Edited prose follows the same distinction. If its validator response is unreadable after retry, the edited text is preserved and reaches the same explicit confirmation gate. Actual runtime/model errors remain errors, not “validation unavailable.”
- Source commits: [62b020e](https://github.com/tony21675/StoryBuilder/commit/62b020e34cfb5d4a04e98b307f5f7397e5afbd4a), [d77b8e3](https://github.com/tony21675/StoryBuilder/commit/d77b8e3c8cebafd6434baec0e642858caa818f96), and follow-up initialization safety fix [91d4cbf](https://github.com/tony21675/StoryBuilder/commit/91d4cbf40f59ba8c5b3abe591c1c91aff518f23b). Regression tests: [b407110](https://github.com/tony21675/StoryBuilder/commit/b4071106e211822e744b326c5c55545eeb1914db) and [265a96f](https://github.com/tony21675/StoryBuilder/commit/265a96fed241736f07d9f8b19c0734fb2683857a).
- **Verification:** GitHub Actions [run 38525120787](https://github.com/tony21675/StoryBuilder/actions/runs/38525120787) passed compilation and all **110 unit tests**. The local GGUF model has not yet been manually tested with this new runtime recovery.
- This work changed StoryBuilder code/tests/handoff only. It did not update or sync MyNovel, alter story canon or the Scene 4 idea, rewrite accepted Scenes 1–3, or accept/reject a scene.

### Safe next step on Tony's laptop

1. If the current Scene 4 prose is still open in the running app and has not been saved, click **Save Draft** before restarting. Do not click Accept or Reject merely to recover it.
2. Close StoryBuilder normally; avoid **Close & Sync Novel**. Then from ~/Documents/StoryBuilder, run ./start.sh to update StoryBuilder from GitHub main and launch it.
3. Reopen Taken_at_Dusk. The novel and its saved Scene 4 prose remain separate from this app-source update; do not run a MyNovel pull/reset/sync as part of the code update.
4. Test the Scene 4 workflow with the saved scene idea. Expected behavior if the validator again returns unreadable output twice: the scene is preserved, a clear warning appears, **Save Draft** and **Reject Scene** remain available, and **Accept Scene** asks for explicit confirmation. Inspect the prose yourself before accepting. If validation returns a readable failed result, let StoryBuilder perform its normal focused revision.
5. Once a scene is genuinely accepted, continue with **Analyze Accepted Scene** and the usual state-update workflow. Do not analyze before acceptance.

## Previous Checkpoint: October 14, 2026 (Writer draft decisions)

### Permanent prose workflow: StoryBuilder writes; assistant reviews

- Tony's permanent workflow is that the assistant reviews and diagnoses prose problems, discusses the smallest appropriate correction with Tony, and then lets StoryBuilder write/revise the scene. Do not replace scene prose in chat or directly edit manuscript prose unless Tony explicitly asks for that.
- The author owns the prose and makes the final choice. Preserve working prose and emotional flow; focus on actual continuity, canon, character-knowledge, and scene-boundary problems.

### Explicit choice for unfinished Writer text

- Approved change is on `main`: [implementation commit `f653b3f`](https://github.com/tony21675/StoryBuilder/commit/f653b3f27ac633c8d774788bfe5743d1bfbb0394). Current regression suite passed in [GitHub Actions run 38518142668](https://github.com/tony21675/StoryBuilder/actions/runs/38518142668).
- Before closing StoryBuilder, closing and syncing, or leaving the current scene when unaccepted Writer text exists, the app asks what to do:
  - **Yes:** Save Draft to the correct originating chapter/scene.
  - **No:** Discard this current attempt. If a draft file contains exactly that prose, remove that matching copy; if a pre-existing saved draft has different text, leave it untouched. Accepted scene prose and story state are not changed.
  - **Cancel:** Abort the close/navigation action and keep the current Writer text in place.
- The explicit **Save Draft** button marks that exact text as saved for the current session, so an unchanged draft does not trigger a second prompt when closing. If the text changes afterward, ask again.
- The dialog is handled by the shared unfinished-draft safeguard, so close, close-and-sync, and guarded scene/package transitions follow the same behavior. A Cancel result must prevent the requested action.
- Legacy versions silently wrote unfinished Writer prose on close/navigation. Such a draft may already exist locally; the new behavior governs future unsaved prose and lets Tony discard a matching old auto-saved copy when that same text is still in the Writer.
- The code compiled and the full current unit suite passed on the latest check. Do not claim the desktop local runtime was manually tested; Tony still needs to pull/start the updated source and exercise the dialog.

## Latest Checkpoint: October 13, 2026 (author-led beats, creative route freedom)

### Design correction: author's destination, not an AI-made checklist

The author approved a generic change after identifying that the Writer was behaving like a driver assembling a route from a rigid manual. The intended workflow is: author gives the starting situation, destination, and a few required waypoints; the Writer chooses natural dialogue, gestures, emotional pacing, memories, transitions, and connective actions along the way.

- **Deterministic rule:** Model-generated `required_beats` are ignored when building a contract. Only items in a clearly labeled `Required Beats` section of the author's original Scene Idea become formal scene-level beats.
- **Saved-contract compatibility:** When a saved guidance entry contains the original Scene Idea, StoryBuilder re-derives formal Required Beats from that idea instead of enforcing old model-generated beat lists. This prevents existing saved checklists, including Scene 4's detailed generated list, from overriding the author's plain-English idea. If the author has no original Scene Idea in a legacy entry, its existing structured events remain available for compatibility. Separately enabled modules may contribute their own requirements.
- The original Scene Idea remains primary input to the Writer and validator. The generated direction and hard stop are secondary support. Validation still checks opening continuity, character knowledge, material story actions, and the intended ending; only explicitly author-labeled Required Beats receive a separate formal beat list.
- The Scene Contract tab and overwrite confirmation now explain that generated beat suggestions do not become mandatory.
- Regression tests cover model-generated beats being ignored for both new contracts and legacy saved contracts, while explicitly author-labeled beats remain mandatory.
- The change is generic and does not modify MyNovel, its canon, accepted scenes, or the saved unaccepted Scene 4 draft.
- **Pause point, October 13:** Tony is stopping here due to time and will pull/start StoryBuilder when he gets to work. The app should be closed with **Close**, not **Reject Scene** and not **Close & Sync Novel**. The existing Chapter 2, Scene 4 draft must remain saved and unaccepted.
- **Next action at work:** From `~/Documents/StoryBuilder`, run `./start.sh`. The startup script syncs StoryBuilder and then launches it. Do not run a MyNovel sync or pull as part of this code update; the local Scene 4 draft and novel-package changes must remain untouched.
- After launch, reopen `Taken_at_Dusk` and inspect Chapter 2, Scene 4's contract. The saved plain-English Scene Idea should remain, and the five previously model-generated scene-level Required Beats should no longer be enforced. Do not click Generate / Replace Contract, regenerate, reject, or accept Scene 4 just to verify the code.
- The new regression tests were committed, but automated CI status has not been confirmed through the available GitHub status results in this session. Do not claim tests passed until the test result is checked. If needed, from `~/Documents/StoryBuilder` run `python3 -m pytest -q tests/test_scene_contract.py`, then review any failure before proceeding.
- No MyNovel files, story canon, accepted scenes, or the saved unaccepted Scene 4 prose were changed by this StoryBuilder code update.

## Previous Checkpoint: October 13, 2026 (explicit-beat revision mechanics)

### Generic StoryBuilder revision and validation repair

After reviewing a new Chapter 2, Scene 4 draft that omitted several planned actions, Tony approved a generic mechanics repair rather than repeatedly patching the scene prompt.

- builder/scene_contract.py now tells semantic validation that every item in required_beats is mandatory. The validator should accept paraphrases but fail when a required action is missing or incomplete. Incidental omissions from ordinary scene prose remain non-blocking unless they remove a central development or defeat the scene's endpoint.
- The result normalizer now forces pass=false if the validator reports any missed_beats or material violations alongside pass=true; such contradictory output must not bypass the revision loop.
- Focused-revision feedback and SceneContract.revision_prompt now explicitly tell the model to weave missing Required Beats into natural prose, while preserving successful dialogue, pacing, and unaffected passages instead of turning the scene into an outline or checklist.
- Regression coverage was added for inconsistent validator results and for the distinction between mandatory Required Beats and incidental detail. Existing compact-prompt and physical-continuity assertions were retained.
- Latest verified source commit: [e9479f0](https://github.com/tony21675/StoryBuilder/commit/e9479f0076ddc9996894ab19907a8ed56a256405). [GitHub Actions passed](https://github.com/tony21675/StoryBuilder/actions/runs/38466770124). The intermediate commits in this sequence had compatibility-test failures; the latest commit restored the required continuity/compatibility wording. Do not treat the intermediate failures as the current result.
- The passing automated suite verifies the source and regression behavior, not the local GGUF model's runtime performance. A fresh local model test is still required.
- **October 13 local runtime test:** the scene prose included the bath and both phone calls, but the local validator incorrectly reported those actions as missing for three attempts. The actual scene also needs targeted details: an explicit bubble bath, telling Beth Maya is safe without suggesting Tiffany will attend, Jessica confirming breakfast tomorrow morning rather than deferring it, and clearer clothing pickup from Tiffany's bedroom. The draft was saved and remains unaccepted.
- **Validator evidence rule implemented:** the validation task prompt now tells the reviewer to search the entire scene for equivalent actions before calling a Required Beat missing. If the action occurs but lacks a detail, feedback should name only the missing detail rather than claiming the whole event is absent. The Writer generation prompt was not changed. Source/test commit [`b0dd2a1`](https://github.com/tony21675/StoryBuilder/commit/b0dd2a14e2409f45112ff36edbbac21336fe9427) passed all 91 automated tests in [run 38475831487](https://github.com/tony21675/StoryBuilder/actions/runs/38475831487). The first attempt briefly removed wording required by an existing opening-continuity regression test; the follow-up restored that continuity wording and moved the new evidence rule into the task-specific validator prompt. A fresh local GGUF runtime test is still required.
- **Approved follow-up validator relaxation — October 13, 2026:** a later local run still falsely reported bath and breakfast calls as absent even though the prose contained those actions. The validator now treats Required Beats as narrative-level goals: fail only for a missing core action/outcome or a material continuity/ending problem; a secondary-detail omission alone should not trigger another full generation/revision attempt. The Writer prompt remains unchanged. Regression tests include a representative bath/calls/Barnaby/tea passage and the pass-with-note behavior. Latest implementation: [`f721b87`](https://github.com/tony21675/StoryBuilder/commit/f721b871f66dca4cce84c99750c2a84ffb752223); its automated test result must be verified before updating the laptop.

### MyNovel Scene 4 planning files updated on GitHub

- [writing_guidance.json commit 16cd1d9](https://github.com/tony21675/MyNovel/commit/16cd1d9995afac02233e3c6505c76b98d6d3eebb) updates the saved Scene Idea and five major Required Beats.
- [STORY_PLAN.md commit b2508ef](https://github.com/tony21675/MyNovel/commit/b2508efd6904d9f28bffd2a2188da99d42442ae6) aligns the confirmed order: warm bubble bath; ordinary breakfast call to Beth; then a call to Jessica inviting Jessica, Chloe, and Rick together; clothes from Tiffany's bedroom; Barnaby's hug and Tony's private vow; quiet tea with Maya at the kitchen table. No extra rescue planning or bedtime in Scene 4.
- [MyNovel commit `51f160e`](https://github.com/tony21675/MyNovel/commit/51f160ed8ce44fce8ee6047fcb4430045dcefd58) now explicitly requires Jessica to confirm that she, Chloe, and Rick will attend breakfast **tomorrow morning**; the invitation cannot be deferred to a later date.
- The Scene Idea remains plain English, not a replacement checklist. Accepted Scenes 1–3 remain untouched.
- **Confirmed October 13, 2026:** Tony calls Beth “Honey” and Jessica “Jessabelle.” The seven-person core group share a close extended-family bond and innocent, nonsexual flirtatious banter; it is friendly group personality, not automatic proof of romantic intent. Canon is recorded in MyNovel's `STORY_PLAN.md`, `story_bible.json`, and relevant character/writing guidance.
- **Confirmed relationship progression:** Maya's feelings for Tony and Chloe's still-uncertain feelings may become visible through natural, cumulative behavior over time. Neither directly confesses these feelings to Tony in Chapter 3. Maya knows what she feels; Chloe is still unsure how to interpret hers. Tony's awareness develops only through what he plausibly notices. Keep this separate from ordinary group banter; see MyNovel `STORY_PLAN.md`, `relationship_dynamics.json`, and `story_bible.json`.

### Safe next pickup

1. On the laptop, check `git status -sb` in both MyNovel and StoryBuilder. Fast-forward with `git pull --ff-only` only when that repository is clean and on `main`. The saved Scene 4 draft may have left local novel-file changes; if MyNovel is dirty, stop and inspect/preserve them rather than pulling or resetting blindly. If StoryBuilder is clean, pull the latest validator commit.
2. If StoryBuilder is currently open, close it after confirming the saved draft is safely written. Then run `./start.sh` from `~/Documents/StoryBuilder` to load the new validator source and launch the app.
3. Reload Taken_at_Dusk. Verify the Writer, current state, and Scene Contract show Chapter 2, Scene 4 and the updated saved Scene Idea. If stale, use Clear & Reload Scene Idea and Build Contract from Scene Idea.
4. The rejected Scene 4 draft is saved locally for comparison. StoryBuilder has no separate revise-current-draft button; focused retries happen within one `Write Next Scene` generation cycle. Test one new generation with the unchanged Writer prompt and updated validator. Review whether the validator correctly recognizes events already present and requests only missing details. Do not accept before author review; leave accepted Scenes 1–3 untouched.
5. Do not begin Scene Planner development until Chapter 2 is accepted through Scene 5 and Tony explicitly finalizes the chapter.

## Permanent collaboration rule: discuss before changing anything

Before making changes for Tony **or changes to my own project work/process**, stop and explain the proposed change first. Say what I want to change, why, and the likely effect or risk, then discuss it with Tony and wait for his explicit approval before editing, implementing, committing, pushing, merging, or changing story canon, prompts, code, UI, workflow, files, or handoff notes.

A request to inspect, diagnose, review, or make a recommendation is not permission to modify. Start with read-only investigation when useful, explain the recommendation, and ask before carrying it out. Do not assume a change is harmless, obvious, urgent, or implied. If the approved scope changes or a new issue calls for additional changes, stop and discuss again. Always preserve existing work and avoid destructive actions.

This rule applies equally to changes in Tony's projects and to my own proposed fixes, refactors, tests, documentation, and handoff/process notes. Only proceed without another approval for the specific action Tony has already explicitly requested.


## Previous Checkpoint: October 13, 2026 (initial end-of-session sync repair; historical)

Tony is tired and frustrated after resolving the novel sync problem. The application was closed at the end of this session. Keep tomorrow's restart gentle and do not reopen Git troubleshooting unless a new failure appears.

### Novel sync incident: resolved

- MyNovel's local commit `4c433ca` and reconciliation merge `e224163` were pushed to `tony21675/MyNovel` `main`. The successful push was `40f59a0..e224163 main -> main`, and the local repository showed `## main...origin/main` with no working-tree changes immediately afterward.
- The precise conflict was `writing_guidance.json`. The merged JSON validated. The merged Scene 4 guidance preserves the local `direction`, `end_condition`, `scene_contract`, and all seven Required Beats, while combining the two Scene Ideas and retaining GitHub's additional instruction to make small, focused revisions.
- A local backup remains at `/home/tony/writing_guidance.json.before-sync-repair.bak`. Do not delete it as part of routine work.
- StoryBuilder had been refreshed through `./start.sh` before the diagnostic sync. The corrected error dialog displayed the actual conflicting filename. A regression fix now preserves both stdout and stderr from Git rebase failures: [commit `89fd515`](https://github.com/tony21675/StoryBuilder/commit/89fd515cc5b1305566750734b4027546d07ae113), with the conflict-output regression test at [commit `cd540e56`](https://github.com/tony21675/StoryBuilder/commit/cd540e56c948b1dc7f27e1b7c8284bb67f37c13d). The full suite passed on [GitHub Actions run 38399044839](https://github.com/tony21675/StoryBuilder/actions/runs/38399044839), latest inspected code commit [`1515a76`](https://github.com/tony21675/StoryBuilder/commit/1515a76bb61f2a7c2aadc5570c7271fc344fc6cd).
- The underlying sync error handler and copyable Close & Sync dialog fixes are already on `main`; there is no need to re-run the same repair or make further code changes tonight.
- Branch cleanup was verified after the earlier accidental temporary branches: both `tony21675/StoryBuilder` and `tony21675/MyNovel` have only the permanent `main` branch. No temporary branches or open PRs are part of the desired workflow.

### Tomorrow's safe pickup sequence

1. From `~/Documents/StoryBuilder`, run `./start.sh` to fast-forward the StoryBuilder handoff update and confirm the source sync succeeds.
2. Before editing the novel, ensure the MyNovel checkout is clean and on `main`, then fast-forward the handoff-only updates that are being added to GitHub now. Do not use hard resets, force-pulls, or another diagnostic Close & Sync attempt. If the repository is dirty or diverged, stop and inspect first.
3. Reopen `Taken_at_Dusk` and continue Chapter 2, Scene 4, “Care and memory.” Scene 4 is still unaccepted; accepted Scenes 1–3 are unchanged.
4. Use StoryBuilder's own **revision workflow** on the existing unaccepted Scene 4 draft. Do not rerun the initial manual generation just to repeat the test. If its loaded idea/contract is stale, use **Clear & Reload Scene Idea**, then **Build Contract from Scene Idea**, and revise the existing draft.

### Scene 4 editing checkpoint

The first manual draft had a gentle flow that Tony liked and correctly described Barnaby as Tiffany's stuffed rabbit. The focused revision should address four known misses: call Beth rather than texting her; also call Jessica and invite Jessica, Chloe, and Rick together; get Maya's clean clothes from Tiffany's bedroom rather than the utility closet; and have Tony hug Barnaby and privately vow to bring Tiffany home. Keep the prose natural and preserve all working passages. The scene ends with Tony making chamomile tea and sitting with Maya at the kitchen table as she begins to settle, before bedtime or rescue planning.

Do not develop Scene Planner until Chapter 2 is complete and the author explicitly finalizes it.
## Previous Checkpoint: October 12, 2026 (historical)

### Author-confirmed workflow state

- Chapter 2, Scene 3 was **accepted**, and the author clicked **Apply State Update**.
- After applying, the author confirmed the Writer, current state, and Scene Contract all showed **Chapter 2, Scene 4**.
- The initial local/GitHub discrepancy is **resolved**. On October 12, 2026, local commit [`eb05527`](https://github.com/tony21675/MyNovel/commit/eb05527) pushed the accepted Scene 3 prose, its before/after-state files, saved draft, current state, writer notes, and reconciled writing guidance. The push succeeded; local and GitHub `current_state.json` both reported Chapter 2, Scene 4, and `git status -sb` was clean.
- A safety backup remains at `~/MyNovel_scene4_recovery_20261012_205345`, and stash `54651b3` remains available. Keep them until the author confirms the reopened StoryBuilder package works. Don't run recovery/rebase/pull procedures again unless a new concrete issue appears.
- Do not ask the author to accept, re-analyze, regenerate, or rewrite Scene 3. Continue from Scene 4 after verifying the app has reloaded the synchronized package.
- If you cannot inspect the local checkout directly, walk the author through one small, read-only diagnostic step at a time. Do not ask them to re-explain the story or redo Scene 3.

### Scene 4 status and prompt-design repairs (October 13, 2026)

The current unaccepted Scene 4 draft supplied by the author has a gentle flow he likes. Barnaby is now correctly described as Tiffany's stuffed rabbit. The draft still used texts to Beth instead of a phone call, omitted the call to Jessica, sent Tony to the utility closet for Maya's clothes instead of Tiffany's bedroom, and missed Tony hugging Barnaby and privately vowing to bring Tiffany home. The saved novel Scene Idea specifies the intended actions. Do not change accepted Scenes 1–3.

Two generic repairs have been merged to StoryBuilder `main`:

- [PR #15](https://github.com/tony21675/StoryBuilder/pull/15), commit [`2d06f2f`](https://github.com/tony21675/StoryBuilder/commit/2d06f2fc70a6863c8e30f220e8f1531a0594f4c8), fixes a prompt hierarchy conflict. The original Scene Idea is primary; current story state governs what has already happened, physical continuity, and character knowledge; generated direction and the contract are supporting hints.
- [PR #16](https://github.com/tony21675/StoryBuilder/pull/16), commit [`f09aad7`](https://github.com/tony21675/StoryBuilder/commit/f09aad728b2f206c2e800af1f0af7840f7370b6a), reinforces the author's desired style: **more creative freedom with gentle guidance, not a checklist**. Contract generation should normally leave `required_beats` empty unless the author explicitly marks a small set as Required Beats/non-negotiable. The original Scene Idea should guide the scene's direction, important moments, emotional movement, and endpoint without making each sentence a separate hard task. Leave natural actions, dialogue, gestures, pacing, and transitions to the Writer. Validation should judge the scene holistically and report only material failures.
- If validation finds a real issue and a retry is needed, StoryBuilder now passes the previous draft into the retry and asks for a focused revision that preserves working prose instead of regenerating blindly from scratch.

Both repairs are generic, not hard-coded to this novel. The latest compile and full unit-test suite passed (85 tests) in [GitHub Actions run 38397176767](https://github.com/tony21675/StoryBuilder/actions/runs/38397176767).

**Important Talk to Builder limitation:** the chat command path calls a small pattern-based `apply_command` parser and recognizes simple structured edits such as changing a character field. It is not a natural-language manuscript revision tool. Do not direct the author to use Talk to Builder for prose edits; it returns the generic “did not recognize” message.

Next: after resting, sync/start StoryBuilder, fast-forward the clean MyNovel checkout for the handoff-only updates, then reopen/reload `Taken_at_Dusk`. Use StoryBuilder's own revision workflow on the existing unaccepted Scene 4 draft; do not regenerate a new draft just to repeat the first manual test. Use **Clear & Reload Scene Idea** and **Build Contract from Scene Idea** only if the loaded idea or contract is stale. Review the actual revised Writer output and make only focused corrections. Accepted Scenes 1–3 remain untouched. Do not use Talk to Builder for prose revisions.

### Novel and manuscript status

- **Permanent branch policy:** `tony21675/StoryBuilder` has exactly one remote branch, `main`. Each novel repository (including `tony21675/MyNovel`) also has exactly one remote branch, `main`. Do not create temporary, feature, fix, experiment, or handoff branches; do not open PRs as a normal workflow. Make changes directly on `main`, verify them with tests, and commit there. If a temporary branch is ever created accidentally, merge its work, delete the branch before finishing, and verify GitHub lists only `main`. This is a standing rule, not session-specific.
- Active novel package on the author's laptop: `~/Documents/MyNovel/Taken_at_Dusk`.
- Scenes 1, 2, and 3 of Chapter 2 are accepted and must remain untouched unless the author explicitly asks for a rewrite.
- **Next scene: Chapter 2, Scene 4, "Care and memory."** Its saved idea is in `writing_guidance.json`; Scene Contract reads from that file. The accepted Scene 3 and Scene 4 state are now pushed to GitHub in MyNovel commit `eb05527`. On resume, open/reload the existing novel package and verify the Writer, current state, and Scene Contract show Scene 4. Do not ask the author to copy/retype the idea or modify it unless a genuine issue is found.

### Scene 3 continuity and eyewitness rule

Maya recounted Tiffany's resistance: two elbow strikes to the solar plexus, a kick to the thigh, a slap across the jaw, and three scratches down the kidnapper's left cheek that drew blood. Tony offered natural reassurance as Maya struggled to continue.

**Maya is a frightened eyewitness, not a police reporter.** Her words may be broken, emotional, fragmented, imperfect, or out of chronological order. She may remember a later detail and then jump back to an earlier one. This is intentional and believable. Keep the required core actions and the facts actually witnessed, but do not polish her account into a perfectly ordered statement, insist on chronology edits, or regenerate accepted prose just because the recollection moves around. Tony still does not know the kidnapper's identity, motive, or destination.

### Chapter 2, Scene 4: Care and memory

Follow this established sequence, allowing natural dialogue and quiet moments:
1. Tony offers Maya a **warm bubble bath, not a shower**, and respects her adult autonomy, privacy, and choice about help.
2. While she bathes, Tony calls Beth to invite her to breakfast and tells her only that Maya is safe at his house. He then calls Jessica to invite Jessica, Chloe, and Rick together because they all live in the same household; he does not call Chloe and Rick separately. Both calls must sound ordinary and must not reveal or hint that Tiffany was abducted. Nobody else knows or suspects before the Chapter 3 breakfast.
3. Tony goes to Tiffany's bedroom for clean clothes for Maya. He notices the stuffed rabbit he gave Tiffany after Sarah died, which she kept all these years. He hugs it and privately vows to bring Tiffany home by any means necessary.
4. He makes tea for Maya, and they sit together at the kitchen table to recover quietly.

Scene 4's exact stopping point is supplied by its loaded Scene Idea/Contract. Do not jump ahead to Scene 5's bedtime or Tony's private planning.

### Chapter 2, Scene 5 and chapter ending

- Tony settles Maya in Tiffany's bedroom beside his own and stays until she falls asleep.
- He returns to his own room and begins preparing, but does not yet have all the answers or a complete rescue plan.
- Chapter 2 ends only when the author has finished and explicitly finalizes it. Do not infer that a chapter is finished because a scene list ends.

### Chapter 3 and future Scene Planner checkpoint

After Chapter 2 is accepted through its final scene and explicitly finalized, pause before writing Chapter 3 and design/build a reusable, genre-neutral **Scene Planner** in StoryBuilder. It should support batch planning multiple future scenes; expansion from novel premise/story arc to chapters and scenes; author review/editing before save; and automatic storage of approved scene ideas and cast under the active novel's `writing_guidance.json` so Scene Contract loads them when they become current. Avoid manual JSON editing and copy/paste. Preserve **guardrails, not rails**: the author sets the meaningful beats, hard stops, canon, and continuity; the model writes natural dialogue and connective tissue. Before coding, inspect the live code and tests, propose a small design, and discuss the workflow with the author. Do not interrupt Chapter 2 to build this.

At the Chapter 3 breakfast, Tony first tells Beth, Chloe, Jessica, and Rick about the abduction in person. Until then only Tony and Maya know. No police during the kidnapping/rescue. Tony trains both Maya and Chloe and both become active participants; Jessica contributes computer expertise, Beth her community connections, and Rick conventional Army experience/logistics. Reveal Tony's Special Forces history through action rather than a long info dump. Preserve the one-kidnapper rule and do not reveal identity, motive, destination, or the overseas buyer prematurely.

## Standing collaboration rules

- **Guardrails, not rails.** Once the author sets required beats and boundaries, write naturally and creatively between them.
- Don't micromanage small decisions or ask the author to approve ordinary dialogue, gestures, pacing, or connective detail. Use good judgment unless a choice changes canon or a major plot commitment.
- Don't fight settled instructions or repeatedly propose a different approach after the author has clarified a preference. Acknowledge the correction and update the appropriate source file so it persists.
- **Keep the record automatically:** when the author provides a durable correction or direction about the novel, character behavior, collaboration workflow, or app behavior, update the appropriate GitHub handoff as part of the work rather than waiting to be asked again. Use MyNovel's `HANDOFF.md` / `STORY_PLAN.md` for story continuity and canon, and StoryBuilder's `CHAT_HANDOFF.md` for app behavior, workflow decisions, tests, and the next action. Distinguish confirmed canon from unverified test outcomes; never include sensitive letter material or credentials.
- Keep Maya's interactions with Tony parental/non-romantic from Tony's side. Tony is caring and protective, patient with distress, and respects the girls' adult autonomy.
- Preserve accepted prose. Do not rewrite/regenerate an accepted scene unless explicitly requested.
- Don't force every scene to deliver a major plot development. Let dialogue, silence, everyday details, tenderness, and reactions breathe.
- Sensitive Sarah-related letters, their contents, passphrases, ciphertext, metadata, and keys are local-only. Never place them in GitHub, story prompts, or handoffs. One letter's author/recipient direction remains unresolved; do not decide it without the author's approval.
- Laptop storage cleanup was paused by the author; do not resume unless asked.

## Completed implementation: simplify Scene Idea and Scene Contract

The author approved proceeding with the agreed simplification on October 13, 2026. The goal is to make the local model write the novel, using fewer instructions and fewer generated checks instead of micromanaging every action.

**The core change is implemented on main.** The observed pattern from the author's experiments is recorded as product guidance:
- Beginning, Middle, End, and Required Beats are the useful author-planning structure.
- Populating Required Facts, Required Sequence, Forbidden / Do Not Advance, or Forbidden Details has repeatedly correlated with failed validation.
- Shorter prompts and fewer rules work better with the current local model. Do not add replacement rules just to cover every conceivable failure.

### Implemented behavior
- The Scene Contract tab now shows the current starting state, Middle / Scene Direction, End / Hard Stop, and Required Beats. The auxiliary fields are no longer shown.
- Contract generation uses a small JSON shape containing only direction, hard stop, required beats, and retry count. Beginning/Middle/End/Required Beats from the author's idea remain authoritative; explicit Required Beats are preserved.
- Newly generated contracts save only Required Beats and retry count inside the contract, alongside the direction and hard stop.
- At runtime, old novel packages remain loadable, but Required Facts, Required Sequence, Forbidden / Do Not Advance, Forbidden Details, hidden state-after hints, and regex gates are ignored by the active scene contract. Positive story events can still become required beats. Do not reintroduce auxiliary gates without discussing the behavior with the author first.
- The Writer prompt's repeated scene-boundary paragraph is shorter. It keeps the useful boundaries: start from current state, preserve character knowledge and opening position/contact unless changed in-scene, reach the hard stop, and leave prose choices to the writer.
- When the Writer is already running, Scene Contract generation and validation reuse that same WriterEngine process with a smaller context/output budget, avoiding a second concurrent copy of the model. Writer tasks are serialized while a contract is being built.
- Timeouts kill a stalled model process. A readable semantic validation failure follows the normal focused-revision path. If the scene-contract validator's response is malformed or unreadable after one correction retry, the generated draft is preserved and remains unaccepted; Save Draft and Reject Scene remain available, and Accept Scene requires the author's separate confirmation that they reviewed and choose to accept without semantic validation. Other model/runtime failures are not bypassed.

### Confirmed Scene Idea workflow: plain-English author conversation

On October 13, 2026, the author clarified the intended product workflow. The Scene Idea is supposed to be a natural, plain-English conversation with the model, not a staged scene outline or a miniature script. We drifted into formal Beginning/Middle/End/Required Beats structures and over-prescriptive lists; do not treat those as the author's ideal input experience.

Target workflow:
- A future Scene Planner (or the prior-scene/chapter planning step) proposes a **rough projected Scene Idea** based on what the chapter and scene are already meant to establish, canon, the current state, and the immediately preceding accepted scene.
- The author reviews that draft and makes small, natural-language refinements instead of writing a scene specification from scratch. Example: if the proposed idea says Tony runs a bath or shower for Maya, the author changes it to “Tony runs a bubble bath for Maya.” That correction is intentional and authoritative; do not dilute it back to a choice between bath and shower.
- The Scene Idea should read like the author talking to a writing partner: what the scene is generally about, a few things they want to happen, and where they want it to finish. Do not force the author to provide staged paragraphs, ordered micro-actions, or a long checklist of ordinary gestures and dialogue.
- The model should interpret that plain-English idea together with the current story state and established canon, then write the scene. It should invent ordinary dialogue, reactions, gestures, pacing, transitions, and connective details itself.
- Preserve clear author choices, essential plot events, and the scene boundary. Do not turn every preference into another validator gate or repeat constraints in several prompt sections.
- Keep the internal contract and Writer prompt short. The contract builder is an implementation detail that helps the model follow the idea, not a reason to make the author write in a rigid format.
- On future code changes, inspect how the Scene Idea is proposed, saved, loaded, and converted into a contract. Propose the smallest generic improvement and agree with the author before making that next code change. Do not change the saved Scene 4 idea merely to match an example or overwrite the author's edits.

The app still does not automatically draft a plain-English Scene Idea from chapter plans; that future planning improvement is separate. The current fix preserves the author-edited idea exactly when passing it to the Writer and validator, so the summarizing contract can no longer replace it.

### Manual plain-English Scene Idea test and code fix

On October 13, 2026, the author tested a short conversational Scene Idea for Chapter 2, Scene 4. The generated scene missed most named events, stayed in the bedroom, and replayed or extended the preceding scene. Its generated contract had a broad direction, a hard stop of “Before bedtime or rescue planning begins,” and an empty Required Beats list.

Source inspection identified the structural cause: `scene_idea` was saved, then sent to the contract builder for summarization. The Writer prompt was assembled from generated direction and contract but did **not** include the original plain-English Scene Idea. The contract therefore became a lossy bottleneck before the Writer ever saw the instructions.

The fix is committed on main:
- `SceneContract.from_guidance` now carries the saved `scene_idea` through runtime as `author_idea`, unchanged.
- `SceneContract.writer_prompt_context` builds a concise context: continuity first, only the compact supporting beats/ending next, then the **full original Scene Idea as primary intent** with an explicit priority statement. The serialized supporting contract no longer redundantly repeats generated direction or retry count.
- `storybuilder.py::_write_next_scene` uses this helper. The raw user paragraph is passed directly to the Writer. If the model-generated direction or contract is vague or disagrees with the original idea, the original idea is explicitly authoritative.
- `SceneContract.validate_with_engine` retains `author_idea` instead of filtering it out, and the validator's instructions/prompt use the same priority. It checks major requested actions and the intended endpoint without demanding every incidental detail word-for-word.
- The contract builder is also instructed to capture a few major named actions when present and to name a specific final moment instead of substituting a vague “before X” condition. This is supplemental; the original idea is no longer dependent on the contract summary to reach the Writer.
- No novel JSON migration is needed. Existing saved `scene_idea` text is reused; no specific Scene 4 instructions were hard-coded into the runtime path.

Regression coverage added:
- Original plain-English idea survives even when the contract summary is vague and Required Beats is empty.
- Writer context puts the original idea after the supporting contract and labels it primary.
- Validator receives the exact original idea and is told it supersedes incomplete generated hints.
- The actual app runtime contract loader retrieves the saved idea from the active scene and passes it through unchanged.

**Verification:** [GitHub Actions passed](https://github.com/tony21675/StoryBuilder/actions/runs/38373611359) on [commit 358890a](https://github.com/tony21675/StoryBuilder/commit/358890adebc5873101f462ccc7c294adec757e4f). The full suite compiled the application and passed **82 unit tests**. This proves the generic prompt/data path is wired correctly, but it does not yet prove how the local GGUF model behaves at runtime on the author's laptop.

### Next step after the first manual generation

The first post-fix manual generation has now been tested. Its result was a substantial improvement, with a few continuity and execution errors. Do **not** repeat the initial sync/rebuild/generation steps unless code changes or a new app-state issue make them necessary.

The immediate task is to use StoryBuilder's own revision workflow on the generated Scene 4 draft, then review that actual revised output. Do not rewrite the prose in ChatGPT as a substitute for this test. The correction intent and known defects are documented in **Latest Scene 4 generation and revision checkpoint** above. The revision result is not yet confirmed.

After this input-to-writing path has proved itself across a little more use, the next separate improvement can be an automatic **rough Scene Idea drafter** based on the chapter/scene plan, current state, canon, and immediately preceding accepted scene. The author should only need to make small plain-English corrections before writing begins. Keep that future work generic, do not hard-code the bath/bubble-bath example, and inspect/discuss the design before beginning it.

### Test status
The GitHub Actions check **passed** on [commit 1e68f8f](https://github.com/tony21675/StoryBuilder/commit/1e68f8f75a79855516ff3c13f8f74edc1781305d): compile checks and the full unit suite passed (79 tests). [View the passing workflow run](https://github.com/tony21675/StoryBuilder/actions/runs/38364175575). This is CI coverage only; it does not prove the local model now generates or validates scenes well on the author's 8 GB laptop.

Relevant implementation commits include [c480b99](https://github.com/tony21675/StoryBuilder/commit/c480b994832c43e0b46255729e881868761774fa), [837dd49](https://github.com/tony21675/StoryBuilder/commit/837dd491b2bbc2ce356ad5ab82458b8686b9dd2d), [3d04cd7](https://github.com/tony21675/StoryBuilder/commit/3d04cd7b74f6ea965fed371e95f538b87e83bcd9), [8c3518a](https://github.com/tony21675/StoryBuilder/commit/8c3518ab42ecf0aeecc53fa5ee25fa06e875a9d7), [b493e37](https://github.com/tony21675/StoryBuilder/commit/b493e37aa69d62583e989d2e2f92caad3492dfb0), and [1e68f8f](https://github.com/tony21675/StoryBuilder/commit/1e68f8f75a79855516ff3c13f8f74edc1781305d). Regression tests for prompt size, auxiliary-field omission, process reuse, copyable errors, and draft preservation are included in the passing suite.

### Initial laptop verification (completed; see current revision checkpoint)
The author completed the first manual generation after the plain-English idea was passed into the Writer and reported a major improvement. The initial generation still had several Scene 4 execution errors, documented in the latest manual test section above. The current next step is to test StoryBuilder's own revision of that draft. Do not rerun the initial setup ritual or add generic rules without new evidence.

Scene 4 remains the reusable regression example, not a hard-coded special case: Tony offers a warm bubble bath; Maya chooses whether she wants help and retains her privacy; Tony returns Tiffany's rabbit to its original place; Maya dresses privately in the clothes he brings; Tony invites Beth, then invites Jessica, Chloe, and Rick together because they share a household; the scene ends in quiet recovery at the kitchen table. The accepted Scene 3 opening position remains Maya curled against Tony as he holds her on the bed.

### Completed UI request: Clear & Reload Scene Idea

On October 13, 2026, added a **Clear & Reload Scene Idea** button beside **Build Contract from Scene Idea** in the Scene Contract tab. It reloads only the saved Scene Idea for the current scene, leaving generated contract fields and novel data untouched. If the editor differs from the saved idea, it asks before discarding unsaved edits. It blocks reload during contract building or writer generation and warns/reloads the displayed scene if the editor is out of sync with current state.

- Source commits: [c759667](https://github.com/tony21675/StoryBuilder/commit/c75966792d556d71a0d7baa727a950c67c5524e8) and [c15ae58](https://github.com/tony21675/StoryBuilder/commit/c15ae58ba96d34b37cc07928f94b5cf863bb09ef).
- Added regression tests covering replacement after confirmation, cancellation without losing edits, and reload without confirmation when the idea already matches the saved value: [cd311f5](https://github.com/tony21675/StoryBuilder/commit/cd311f5f3bac607a22f2c32fe9ef1c16afbc4af9).
- The Clear & Reload regression tests are included in the full GitHub Actions unit suite, which passed on [commit 1e68f8f](https://github.com/tony21675/StoryBuilder/commit/1e68f8f75a79855516ff3c13f8f74edc1781305d). The local Tkinter/RustDesk clipboard behavior still merits a quick desktop check.

### Validator timeout and prompt-size reduction

The author reported **"Scene contract validation timed out in the Writer tab"** on October 13, 2026. Code inspection confirmed `builder/scene_contract.py::_run_validator` runs a second local llama-cli process with a 300-second timeout, CPU-only by default unless `STORY_LLM_DEVICE` is set. The validation system prompt repeated rules already present in the user prompt, including two duplicate instructions about familial comfort, and the validator received the full current-state object and contract `state_after` payload.

Changes committed for a generic, lighter review:
- [a165a30](https://github.com/tony21675/StoryBuilder/commit/a165a30821b05c6c2c6df6e3955c829634fa4399) shortened the validator system prompt, reduced the validator token budget from 350 to 220, default validation context from 8192 to 6144 (override with `STORY_VALIDATOR_CONTEXT`), compacted the scene-start state to fields relevant to continuity/knowledge, and removed the potentially large `state_after` from the validation prompt.
- [fec364b](https://github.com/tony21675/StoryBuilder/commit/fec364bcf04ee8880a58d599172376c632970fa5) corrected newline separators in the compact prompt.
- [779ae8c](https://github.com/tony21675/StoryBuilder/commit/779ae8c2ba4a5235e456d51966005410786a85ad) added a regression assertion that relevant physical continuity remains in the prompt while unrelated state data does not.

This first validator-prompt reduction was superseded by the low-RAM implementation below, which also reuses the existing WriterEngine and drops auxiliary contract gates. The final code and unit tests passed GitHub Actions on commit [1e68f8f](https://github.com/tony21675/StoryBuilder/commit/1e68f8f75a79855516ff3c13f8f74edc1781305d). Local-model runtime behavior still needs the laptop check described in the completed-implementation section above.

### Low-RAM behavior and contract simplification

The active laptop has 8 GB RAM. Contract generation and validation reuse the WriterEngine when running; the engine is restarted sequentially with a smaller 6144-token context and task-specific output budget so two concurrent copies of the model are not resident. Writer operations that compete for the local model are disabled during contract creation. If Writer is stopped, contract generation starts one standalone process.

Runtime and newly generated contracts use only direction, Required Beats, and Hard Stop (plus retry count). Older data may still physically contain the auxiliary fields, but `SceneContract.from_guidance` and semantic validation discard them, and writer direction no longer emits auxiliary prohibition rules. Rebuilding the current contract is still recommended so the displayed saved contract matches the new schema.

Writer validation errors use the copyable dialog. If a draft was generated but validation timed out/failed, it stays visible and saveable but unaccepted; Accept stays disabled. A timed-out model process is killed to release memory. See the completed implementation section above for the passing CI result and laptop verification plan.

### Durable design rule

The author's instruction was to discuss future significant changes before making them. The core simplification above was later explicitly approved and implemented. Continue to favor the shortest prompt that preserves the intended beats and boundary. Do not add more fields or more verbose rules just to compensate for a single bad generation. Test the generic path and use actual model output as evidence.

## Branch audit and cleanup (October 13, 2026)

Completed. The stale refs from already-merged PRs #10–16 were removed, and the live GitHub branch lists were verified to contain only `main` for both repositories. No replacements should be created.

## Permanent repository and sync safety rules

- Keep exactly one remote branch per repository: `main`. Never create temporary branches or pull requests during ordinary work. Commit verified changes directly on `main`.
- The novel's **Close & Sync Novel** commits local changes before fetching. If the remote and local edits conflict, never choose a side automatically or keep clicking Sync. The app should abort the incomplete rebase safely, preserve the local commit, and show the conflicting file details. Reconcile the actual conflict before trying again.
- If the app ever reports that a rebase is already in progress, use the updated sync handler to abort the interrupted sync safely; do not improvise with hard resets, force-pulls, or deleting local files.
- After any sync incident, check that both repositories are on `main`, their working trees are understood, and GitHub shows only `main` before moving on to story work.
- **Recurring sync failure fixed on October 13, 2026:** `builder/novel_sync.py` previously left Git mid-rebase when a local/remote content conflict occurred. The handler now detects and safely aborts an interrupted rebase before asking for the branch name (because rebase can show detached HEAD), preserves the local commit, rejects non-`main` branches, and aborts a newly failed rebase with a clear message instead of leaving the repository stuck. See [`ddffffa`](https://github.com/tony21675/StoryBuilder/commit/ddffffadb018c73edfc5e21234a5ca161061b94c), [`24b4951`](https://github.com/tony21675/StoryBuilder/commit/24b4951d13852b4fb166dcc9d3ae4b76360ec58e), and the recovery-order test in [`d3776c7`](https://github.com/tony21675/StoryBuilder/commit/d3776c7afb7e992bdf317f7a2ae65b68cba6cab4). `sync.sh` now rejects non-`main` StoryBuilder checkouts. The complete suite passed on the latest source in [run 38398226025](https://github.com/tony21675/StoryBuilder/actions/runs/38398226025).
- **Branch cleanup verified:** the seven stale StoryBuilder branches were all from merged PRs and have been removed. The live GitHub branch lists for both `tony21675/StoryBuilder` and `tony21675/MyNovel` now show exactly one branch each: `main`. A one-time cleanup job was removed after it completed successfully; no permanent branch-deletion automation remains.
- **Close & Sync error popup fixed on October 13, 2026:** `_sync_current_novel()` already used the copyable error window, but `_close_and_sync()` still used Tkinter's ordinary `messagebox.showerror` for `NovelSyncError` and OS/subprocess failures. Both Close & Sync error paths now call `_show_copyable_error()`; the complete details can be selected or copied using **Copy Full Error**. Regression test: [`c55c0e6`](https://github.com/tony21675/StoryBuilder/commit/c55c0e6de01c61ebbc1f2d0d1f69b0499c3b9230). Compile and full tests passed in [run 38398631770](https://github.com/tony21675/StoryBuilder/actions/runs/38398631770).
- **Resolved MyNovel sync conflict (October 13, 2026):** the conflict was `writing_guidance.json`. Tony's local commit `4c433ca` was preserved, reconciled in local merge commit `e224163`, validated, and pushed to GitHub `main`. The final post-push local status was clean and synchronized. This supersedes the earlier `ahead 1, behind 11/12` diagnostic state.
- **Historical app-version diagnosis (resolved):** the earlier traceback showed the old, non-copyable error dialog because the app had been launched before the latest source refresh. Tony refreshed StoryBuilder with `./start.sh`, then the corrected dialog exposed `writing_guidance.json`. No further diagnostic sync attempt is needed.
- **Handoff update coordination:** never update MyNovel handoff files directly on GitHub while the laptop has unpushed novel changes. This session's novel content is now pushed and clean; the handoff-only documentation updates being made now may leave the laptop a few commits behind, but they should be fast-forward-only. At the next session, synchronize these documentation-only updates while the local working tree is clean before editing novel content.

## StoryBuilder changes and verification notes

- Reusable scene-contract reassurance handling was committed in `builder/scene_contract.py` at [`b52b1c9`](https://github.com/tony21675/StoryBuilder/commit/b52b1c98ce786cb676a862b5bd8db0e7a5cb17d5).
- General writer-prompt reassurance handling was committed in `storybuilder.py` at [`a7eaa92`](https://github.com/tony21675/StoryBuilder/commit/a7eaa923af3193836cd81867e12bd5afb84c5fc0).
- Reassurance prompt regression assertions were added at [`05ce6cf`](https://github.com/tony21675/StoryBuilder/commit/05ce6cfe33aa846ea5c2f547b5a047ff2e9e89b1). These changes were committed, but this handoff has no evidence that the tests were executed after the additions. Do not claim they passed until verified.
- Copyable error dialog clipboard handling was changed in [`ce5d563`](https://github.com/tony21675/StoryBuilder/commit/ce5d5637939119021ec181f155a666005ca2dfcb), with a regression test in [`0b1e992`](https://github.com/tony21675/StoryBuilder/commit/0b1e992787936d04b6bf0349cf098645641c09a6). Both the test and live clipboard behavior remain unverified.
- The local writer model is user-configured. Do not switch or delete models as part of the current novel checkpoint.
- After Chapter 2 is finalized, inspect the actual current StoryBuilder source/tests before implementing Scene Planner. Make one testable change at a time and update this handoff after verification.
