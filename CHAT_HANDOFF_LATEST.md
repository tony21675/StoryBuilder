# StoryBuilder handoff, current checkpoint

Date: October 28, 2026

## Direction

Rebuild StoryBuilder piece by piece. Keep the Writer's direct, uncomplicated local-model writing experience, then restore useful workflow pieces incrementally. The active app now has a read-first novel/chapter/scene browser; the next step is live laptop verification, followed by careful restoration of scene saving and explicit novel-to-GitHub syncing. Keep legacy code recoverable. Never overwrite accepted prose as part of a navigation test, and do not modify novel packages or novel state during app recovery.

## Minimal Writer, confirmed on laptop

- Launched by `./start.sh`.
- The user confirmed local model writing, live text streaming, and opening/saving text files.
- `minimal_writer.py` loads the model with an empty system prompt and sends the author's writing prompt directly to `WriterEngine`.
- **Stop Writing was tested live and the user confirmed it worked.** Stopping terminates the local model process; reload the model before writing again.
- UTF-8 open/save helpers preserve text and final-newline state.
- No novel or saved story state has been changed.

## New piece: Continue

A separate **Continue** action has been implemented and tested live on the laptop. In the user's Tiffany/Kim test, the original passage remained and the continuation followed it without repeating the original. The user inserted “(Continued here)” manually as a visual marker to show me the boundary between Part 1 and Part 2; it was not model-generated text or an app issue.

- **Write** replaces the visible output, but deliberately keeps the current model session/context. The user likes that this lets a changed prompt pick up the story where the prior scene left off, even though the old prose is no longer visible. Do not reset/reload the model on Write unless the user later asks for a fresh-session option.
- **Continue** asks the model for only new material, includes up to the last 2,000 characters of the visible passage as context, and appends the response after a paragraph break. This anchors continuation to the text as edited in the output box.
- The existing passage remains in the output while more words stream in.
- The app's final cleaned response is appended to the saved-visible passage when generation completes.
- If continuation fails, the previous text and file tracking are restored.
- If Stop is pressed during continuation, the previous text plus any streamed continuation is kept. If no new text arrived, the previous document is restored.
- No hidden system prompt or broader writing rules were added.

Automated tests passed on commit `091280b0`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40641857573) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40641857583).

## Latest behavior confirmation

The user tested **Write** after a passage and Continue, then tested again with a changed prompt. Write replaces the visible output but preserves the current model session/context, so the model can carry the story forward from where the prior scene ended. The user explicitly likes this behavior. Keep it as intended: Write = replace visible prose while preserving ongoing model/story context; Continue = append new prose to the visible output. Do not implement a fresh-session reset for Write. A separate explicit “new session” action would be a future option only if requested.

Stop/reload behavior, Continue append behavior, and Write's replace/context-preserving behavior have all been confirmed live on the laptop. The regression test exercises two successive Write actions with changed prompts: visible output is replaced each time, while the fake engine session is not restarted and retains both prompts in its session history. Both CI workflows passed after the test double was completed: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40647067750) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40647067765). This milestone changes tests and documentation only, not runtime behavior.

## Read-only legacy dependency audit (October 28, 2026)

- The active launcher is `start.sh` → `sync.sh start` → `python3 minimal_writer.py`. The launcher does not run the old `storybuilder.py` interface.
- The Minimal Writer's project-code path is `minimal_writer.py` → `builder.writer_engine.WriterEngine` and `builder.workspace.MODELS_DIR`. The engine uses standard-library modules plus `pexpect`, the external `llama-cli` executable, and local GGUF model files.
- `WriterEngine` still has optional prompt-trace hooks, but Minimal Writer does not attach a trace object. The model is started with an empty system prompt. No StoryBuilder-added NSFW filter or writing-rule prompt is present.
- The new `builder.novel_browser` uses the existing package discovery helper plus the configured `NOVEL_ROOT`. Minimal Writer can list novel packages, chapter folders, and numbered manuscript scene text files. It reads only the selected `.txt` scene; it does not load or change `current_state.json`, character cards, before/after state JSON, or other novel data.
- The legacy `storybuilder.py` remains in the repository and imports most of the old workflow modules. Those modules are not active through the Minimal Writer entry point, but they remain dependencies of the preserved legacy interface and/or its tests. Keep them until any removal is deliberately reviewed.
- **Protected Taken at Dusk secret letters: do not remove or alter.** Correction to the initial read-only audit: `builder/secret_letter.py` is not an obsolete cleanup candidate. The first-novel handoff identifies two separate, encrypted, local-only assets: Tiffany's letter at `~/Documents/MyNovel/Taken_at_Dusk/secrets/sarah_letter.enc.b64` and Tony's separate letter at `~/Documents/MyNovel/Taken_at_Dusk/secrets/sarah_tony.enc.json`. Their metadata and supporting files are also local-only and intentionally excluded from GitHub. Preserve both encrypted letters, both metadata files, the helper, verification script, local README, private key, and the `/secrets/` Git-ignore rule. The author has not yet seen the letter contents. Do not decrypt, display, copy, or add their contents to GitHub, handoffs, manuscripts, or StoryBuilder prompts unless the author explicitly asks to reveal them. The audit did not open or decrypt either letter, and nothing was deleted or changed in the novel repository.
- This was a read-only static audit. No application code, model configuration, branch, novel package, accepted prose, or novel state was changed.

## Local model inventory from earlier handoffs

The October 17–20, 2026, Taken at Dusk / StoryBuilder testing handoffs recorded these local models:

- **Gemma 4 E4B IT**, exact documented path: `~/Documents/Models/01 gemma-4-E4B_q4_0-it.gguf`. This was reported as the best-performing model in testing and the chosen writing model. The name identifies **E4B**, not E2B; the filename does not itself say “uncensored.”
- **Stheno 8B**. Recorded as another available model; its exact GGUF filename was not documented.
- **Llama 3.1 8B**. Recorded as another available model; its exact GGUF filename was not documented.
- **Gemma 4 E4B IT Ultra Uncensored Heretic GGUF**, Hugging Face source `llmfan46/gemma-4-E4B-it-ultra-uncensored-heretic-GGUF`. The author has now confirmed this model is also available locally. Its exact local GGUF filename and quantization are not yet recorded. The model card describes it as a decensored version of `google/gemma-4-E4B-it` made with Heretic, which targets refusal behavior rather than retraining it for different genres. Do not assume “uncensored” will change its romance-like prose style.

This is a historical handoff record, not a verified live listing of the current laptop directory. The active app scans `~/Documents/Models/*.gguf` by default (unless `STORY_MODELS_DIR` overrides it), so the current dropdown or a local directory listing is the authority on which files are present today. Never delete or replace any model without discussing it first.

## Two-model writing goal (October 28, 2026)

**Temporary hardware correction (October 28, 2026):** The author has access to a 16 GB RAM laptop for the next couple of months only. Older handoffs describe an 8 GB RAM laptop; treat that as the longer-term compatibility constraint unless the author says otherwise. Use the temporary 16 GB machine to test a stronger model, but prefer a practical fallback for an 8 GB system. Model file size is not the full RAM requirement: leave memory for the OS, runtime, KV cache/context, and generation. Do not assume a 5–6 GB quant will work well at the current 16,384-token context without checking memory use.

Keep the existing Gemma 4 E4B model as the general-purpose writer; the author likes its output so far. The author also confirmed the local inventory includes `llmfan46/gemma-4-E4B-it-ultra-uncensored-heretic-GGUF` (exact local filename/quantization still unconfirmed). The Heretic modification targets refusal behavior; do not assume it will change genre/style.

For a second model, the intended use is **explicit adult erotica/porn-style fiction featuring consenting adults**, not romance-novel style. The author is not looking for illegal sexual content. Keep Gemma 4 as the general-purpose writer and do not replace it. Current access to 16 GB RAM is temporary for a couple of months; keep longer-term fit for the previously documented 8 GB laptop in mind. No download or app change without discussion.

**Leading research candidate for the temporary 16 GB machine:** `Mantis2024/Dirty-Muse-Writer-v01-Uncensored-Erotica-NSFW`, a 9B Gemma 2 based GGUF specifically named and presented for uncensored erotica. A `Q4_K_M` file is documented at about 5.76 GB; quantizer documentation also lists `Q4_K_S` around 5.6 GB and smaller Q3 options. It is the most directly targeted candidate found so far, but creator labels are not proof of quality or style. It may need a reduced context (start lower than the app's 16,384 default) to leave RAM for the operating system and runtime. [GGUF model card](https://huggingface.co/Nazmiven/muse_model) and [imatrix quantization details](https://huggingface.co/mradermacher/Dirty-Muse-Writer-v01-Uncensored-Erotica-NSFW-i1-GGUF).

**Smaller alternative for comparison:** `mradermacher/eroticv1-GGUF`, with `Q4_K_M` documented around 4.92 GB, also supports llama.cpp GGUF loading. Its smaller weights may be easier to use on the 8 GB machine later, but quality and fit to the desired prose style are untested. [Model and quant list](https://huggingface.co/mradermacher/eroticv1-GGUF/tree/main).

`DavidAU/Qwen3-4B-Gemini-TripleX-High-Reasoning-Thinking-Heretic-Uncensored-GGUF` remains a small general creative-writing alternative that advertises all-genres fiction and erotica, but it is less specifically targeted than Dirty Muse. Test actual prose before choosing. None of these models has been downloaded or approved yet.

## Out of scope

The initial novel integration is limited to read-only package/chapter/scene browsing and loading a scene as a copy. No loading/changing story state, character cards, scene planning, continuity system, writing rules, validators, state summaries, automatic reviews, automatic state changes, direct save to the selected manuscript, or novel-to-GitHub syncing yet. Do not delete legacy modules until removal is discussed.

## Protected novel checkpoint

- Local: `~/Documents/MyNovel/The-Long-Way-Home`.
- Remote: `tony21675/The-Long-Way-Home`, branch `main`.
- Accepted Chapter 1 Scene 10 prose: `Manuscript/Chapters/Chapter_01/Chapter_01_Section_10.txt`.
- Remote `current_state.json` remains at Scene 10; the after-state file is absent.
- Do not modify or regenerate Scene 10 during Minimal Writer work.

## Working rules

Use `python3`, never `python`, in Linux terminal commands. Keep StoryBuilder on `redesign/simplified-writing-workflow` for now; do not switch or delete branches blindly. Discuss app or novel changes before making them, except handoff-only updates. Preserve accepted prose. Keep terminal steps short.


## Minimal Writer current checkpoint: New Session upgrade (October 28, 2026)

### Confirmed working before this upgrade
- Active branch: `redesign/simplified-writing-workflow`. Launch locally with `cd ~/Documents/StoryBuilder && ./start.sh`. It synchronizes the current branch and opens `minimal_writer.py`.
- Live multiline-prompt tests passed: real paragraph boundaries remain distinct; `C:\\models\\drafts\\scene.txt` retains single backslashes; literal `\\n` stays literal; longer generated prose has no prompt echo and keeps requested paragraph breaks.
- Ctrl+A is explicitly bound in the prompt and output boxes, and the user confirmed it works in both. The code/test commit was `c7fd9d932013f99fced5d0c35bf62fe7cb6ee14c`; both CI workflows passed: [Python #326](https://github.com/tony21675/StoryBuilder/actions/runs/40693875261), [StoryBuilder #591](https://github.com/tony21675/StoryBuilder/actions/runs/40693875342).
- The author tested Qwen3-4B TripleX with a basic story prompt only to see whether it loads and generates. Its visible thinking section was merely an observation; no model/display changes requested.

### Current approved upgrade: New Session
- The author approved a **New Session** button to clear only model conversation history while keeping the visible draft, prompt field, current filename, saved-text tracking, and loaded model intact.
- The first live test failed with an error ending in `/clear`. The likely cause was that `clear_context()` sent `/clear` without the trailing `/` end-of-turn marker required by the app's `--multiline-input` input path. The safety fallback correctly stopped the uncertain CLI session instead of claiming it had cleared.
- Fixed `WriterEngine.clear_context()` to submit `encode_prompt_for_cli("/clear")`, the same encoder used for author prompts. Added a regression assertion that the command is submitted as `/clear/`. Code fix commit: `3934c2ba012fbe0509e0fc1fa5ed72554fd62076`; test commit: `d20c525c7189f3af9644af626b7097d397edf4a4`.
- Both CI workflows passed on code/test commit `8af69ec9ca59332f944ff9ca6c51cf5114f13cd3`: [Python tests #334](https://github.com/tony21675/StoryBuilder/actions/runs/40770183208) and [StoryBuilder tests #599](https://github.com/tony21675/StoryBuilder/actions/runs/40770183212).
- Live laptop verification passed end to end. Clicking **New Session** displayed the expected success status and preserved the visible draft. The author then clicked **Write** with a wholly unrelated lighthouse story prompt; it replaced the previous visible story, and the author confirmed the two stories were not alike at all. This verifies the model did not carry over the previous conversation context.

### Next step
- New Session is verified. Continue Writer-first development: agree on the next improvement, then make one focused, tested change at a time. Keep the separate Story Bible app on hold until the Writer is where the author wants it.


## Novel browser milestone: read-first navigation (October 28, 2026)

- Implemented in code/test commit `bf4e4f81709466f450739cdcb38906736e171dd0`: `builder/novel_browser.py`, `minimal_writer.py`, and tests.
- Minimal Writer now lists packages under `STORY_NOVEL_ROOT` (default `~/Documents/MyNovel`), lets the author choose chapter and scene, and provides **Load Scene Copy**.
- The browser identifies numbered manuscript text files under `Manuscript/Chapters/Chapter_XX/` and ignores supporting JSON files when populating scenes.
- Safety: scene load sets `current_file=None`, remembers the selected source for the default Save As name only, and leaves `saved_output_text` equal to the loaded text. Thus **Save** goes to **Save As**, not directly to the accepted scene. Saving a copy then uses the normal file save flow.
- Both CI workflows passed: [Python tests #342](https://github.com/tony21675/StoryBuilder/actions/runs/40773141944), [StoryBuilder tests #607](https://github.com/tony21675/StoryBuilder/actions/runs/40773141964).
- **Live GUI verification passed on October 28, 2026.** The author supplied a screenshot showing `The-Long-Way-Home`, Chapter 01, Scene 10 selected and the actual Scene 10 prose loaded in the editable output area. The status bar explicitly says the original is untouched and Save opens Save As.
- The author then clicked **Save**. The operating-system save dialog requested a destination and filename; after the author selected them, the dialog closed and the app's status bar reported that the file was saved. This confirms the Save As path completed without touching the selected manuscript. The destination file was not separately reopened for byte-level verification.
- No edits were made to the loaded prose, and the accepted novel manuscript and story state remain untouched.
- **Implemented:** a separate **Save to Selected Scene** button in commit `8d84737cb2f73d26af612f1fe4ea0f6edbdfd515`; confirmation and cancellation regression tests in `61085d5cde7080968c4540d53b9071d9714ccfe1`.
- The button is enabled only after **Load Scene Copy** and when a scene target is available. It displays the full target path and asks for explicit confirmation. If the selected target differs from the scene originally loaded, the confirmation also displays the originally loaded path.
- Cancel leaves the file and save tracking untouched. A successful direct scene save updates the saved-text tracking but deliberately leaves `current_file=None`, so the ordinary **Save** button still opens Save As instead of silently attaching itself to the manuscript.
- Both automated workflows passed on the code/test commit: [Python tests #348](https://github.com/tony21675/StoryBuilder/actions/runs/40774810127) and [StoryBuilder tests #613](https://github.com/tony21675/StoryBuilder/actions/runs/40774810099).
- **Live confirmation/cancel test passed on the laptop, October 28, 2026.** The author loaded The-Long-Way-Home / Chapter 01 / Scene 10, clicked **Save to Selected Scene**, checked the prompt to replace Scene 10, clicked **No**, and the Writer reported: `Save to Selected Scene cancelled; no file changed.` The accepted Scene 10 was not overwritten.
- **Live confirmed-write test passed on the laptop, October 28, 2026.** A disposable package was created at `~/Documents/MyNovel/StoryBuilder_Save_Test_20261028` with one test scene at `Manuscript/Chapters/Chapter_01/Chapter_01_Section_01.txt`. The author replaced the scene text, confirmed **Save to Selected Scene**, received the saved status, then used `cat` to verify the file contents were exactly `Disposable scene save test: CONFIRMED WRITE WORKED.` This verifies both confirmation and actual file write against the intended disposable target. No accepted novel was modified.
- The author removed only the explicitly created disposable package with `rm -r ~/Documents/MyNovel/StoryBuilder_Save_Test_20261028`; the command returned without an error. Cleanup is complete.
- Consider the first complete live validation of direct scene saving passed. The real The-Long-Way-Home Scene 10 was loaded only for the cancellation test; the confirmed-write test used the separate disposable package, and the accepted manuscript was not overwritten.
- The novel-to-GitHub sync has now been implemented and automated-tested in the later checkpoint below. Its laptop confirmation dialog is the next live check; cancel it on the first pass so no remote write occurs yet.
 
## Possible app split (October 28, 2026)

- The author clarified the question was specifically whether Minimal Writer should have a **New Novel** button or only browse/open existing novels. Do not record the app split as a fully approved product decision yet.
- Current Minimal Writer supports browsing/opening existing local novel packages and writing/editing their scene prose.
- Recommendation for discussion: keep Writer focused on writing/editing and let the future **Story Bible** companion app create new novel packages (story bible, characters, outline/plan, and required folder structure). If we follow that plan, a New Novel button in Writer is not needed initially.
- Keep the Story Bible app on hold while Writer is developed and tested first. Revisit a Writer-side New Novel shortcut later if it proves useful.


## Novel-to-GitHub sync milestone (October 28, 2026)

- Implemented in `builder/novel_git_sync.py` and wired into `minimal_writer.py` as a separate **Sync Novel to GitHub** button. This is separate from the StoryBuilder code sync in `start.sh` / `sync.sh`; it does not run automatically when Writer starts or closes.
- The button works only on the selected package, and its confirmation shows the full local folder, current branch, sanitized `origin` URL, local file changes, and commits currently ahead of the last fetched upstream. If the Writer pane has unsaved edits, the dialog warns that those edits are not part of Git sync until saved to a file.
- Safety checks require the selected folder to be a novel package and the root of its own Git repository, with an `origin` remote and the current branch tracking `origin/<current-branch>`. It creates no branches, does not guess a remote, and blocks detached HEAD, unfinished Git operations, unresolved conflicts, and changed local-only secret/encrypted paths such as `secrets/` or encrypted key/letter files.
- After explicit confirmation, the helper temporarily stashes local changes, fetches and uses `git pull --ff-only` to bring in remote updates, restores the stash, rechecks safety, commits local novel changes if needed, and pushes only the selected novel's current branch. If histories diverge, the sync stops without committing or pushing. If stash restoration fails, the safety stash is preserved and the user is told to check the working tree. If a push fails after local commit, that commit is preserved.
- Automated tests use disposable local Git repositories, not the author's real novels. They cover preview and branch/upstream checks, local commit/push, fast-forwarding remote changes, refusal when histories diverge while restoring local untracked work, and blocking protected secret paths. UI tests verify that canceling starts no Git operation and that the dialog shows pending files/commits and warns about unsaved editor text.
- Both automated workflows passed on the latest code/test commit `8b151330a65911daa5d00aa81c103d75ea664598`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40776820228) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40776820088).
- **Live laptop sync passed on October 28, 2026.** The author launched Writer, selected `The-Long-Way-Home`, clicked **Sync Novel to GitHub**, accepted the confirmation, and Writer reported that the novel was synced.
- The author then ran `git -C ~/Documents/MyNovel/The-Long-Way-Home status -sb`. Output was `## main...origin/main`, with no modified/untracked paths or ahead/behind counts. This corroborates that the local `main` working tree is clean and aligned with its recorded `origin/main` after the sync. No further Git command or file mutation was made in the verification step.
- This was an intentional first real novel sync, with the user confirming they clicked **Yes**. Continue to keep syncing manual and explicit. Before any future sync, the UI should continue to show the selected folder, branch, remote, changes and pending commits, and warn if visible editor text has not been saved to a file.


## Copyable popup milestone (October 28, 2026)

- Implemented in `minimal_writer.py` as a common popup dialog used for all information messages, errors, and confirmation prompts. Long messages use a scrollable, resizable text box capped to the available screen size instead of a native message box that can run top-to-bottom.
- The message text can be selected with the mouse or with **Ctrl+A**, then copied with **Ctrl+C**. The text area blocks editing/paste/cut while allowing selection and copying. The clipboard owner is the main app window so copied text persists when the popup closes.
- Existing confirmation choices remain **Yes / No / Cancel** as appropriate. Safety-sensitive confirmations default to the non-destructive option: No for Yes/No, Cancel for Yes/No/Cancel.
- README documents the new popup behavior. No novel package, manuscript, or story state was changed.
- Automated workflows passed on code/test commit `da8c966cc1dce65bbd03767ce76872bab212d69e`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40778101321) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40778101292).
- Next: on laptop, launch with `cd ~/Documents/StoryBuilder && ./start.sh`, click **Sync Novel to GitHub** for `The-Long-Way-Home`, and verify the long confirmation is contained in a scrollable text box. Click inside the message, press **Ctrl+A**, then **Ctrl+C** to copy. Click **Cancel** for this check so it performs no Git operation. Also verify short messages remain compact and confirmation buttons still work.
