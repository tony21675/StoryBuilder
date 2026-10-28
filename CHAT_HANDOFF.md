# StoryBuilder project handoff

Date: October 28, 2026

## 1. Agreed rebuild direction

The author decided to rebuild the app piece by piece, starting with the simplest useful thing: load a local model and write. Remove the old rule-heavy workflow from the active path. Do not add features back until the current layer has been verified on the author's laptop.

The active rebuild is explicitly authorized. Keep the old app code recoverable for now; do not touch novel repositories or accepted prose.

## 2. Minimal Writer works on the laptop

The normal launcher `./start.sh` runs `sync.sh start`, then starts `minimal_writer.py` with `python3`.

First live smoke test completed on October 28, 2026:
- The Minimal Writer window opened after launch.
- The user loaded their local model, submitted a short scene prompt, and received generated text.
- The user saved the output, then opened the saved text successfully in a separate text editor.

Current minimal UI has:
- GGUF model selector, Refresh, and Load Model.
- An author prompt field plus Write, Continue, and Stop Writing.
- Editable output that streams model text as it is generated.
- Open Text, Save, and Save As.
- Status line and filename/unsaved marker in the window title.

No novel package loader, scene planner, scene contract, continuity context, character cards, validator, state updater, or writer-notes process is invoked by the new UI.

## 3. Direct model path

File: `minimal_writer.py`.

- `load_model_for_writing(engine, model_path)` calls `engine.start(model_path, system_prompt="")`; there is no app-authored system prompt.
- `write_from_prompt(engine, prompt)` passes the prompt straight to `engine.generate(prompt)`.
- Uses the existing `WriterEngine` and `MODELS_DIR` only.
- Runs model loading/generation on a worker thread so the window can remain responsive.
- Streams generated text into the output area as the model writes. The prior document is held in memory during generation and restored if generation fails.
- Do not infer the quality of live generation from CI alone; the real-model smoke test was performed separately.

Default environment:
- Models: `~/Documents/Models/*.gguf`
- llama.cpp: `~/Documents/llama.cpp/build/bin/llama-cli`
- `STORY_MODELS_DIR`, `STORY_LLAMA_PATH`, `STORY_WRITER_CONTEXT`, `STORY_WRITER_MAX_TOKENS` remain available as runtime overrides.

Known limitations: `WriterEngine.generate()` flattens newline characters in the prompt before sending it to the interactive llama.cpp process. Streaming uses the existing prompt-echo filter and is best-effort; after completion, the cleaned final response replaces the live preview. Stop Writing terminates the local `llama-cli` process without waiting for the generation lock, keeps partial streamed text (or restores the previous document if no text arrived), and requires reloading the model. The user tested Stop live and confirmed it works.

## 4. Open Text / Save / Save As

Commit `1954d62be1aebbd62f2f8014201e01cdfe9a6089` adds:
- `Open Text…`: opens a UTF-8 text file into the editable output field.
- `Save`: writes to the current file; for untitled text it launches Save As.
- `Save As…`: writes to a chosen destination and sets that as the current file.
- Title displays the active filename; an asterisk indicates changes compared with the saved text.
- When opening another file or closing, the app offers to save dirty output first.
- Text file helpers round-trip Unicode and newline sequences exactly.

Tests added in `tests/test_minimal_writer.py` cover empty system prompt, direct prompt handoff, text round-trip, and preserving the final-newline state. CI results for code commit `f45e969c1f1bc433f30d7dcb84bfc53049c04ca6`:
- [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40636160718): passed.
- [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40636160677): passed.

The user has confirmed that the real model streams words into the output area while generating. The basic streaming milestone is verified on the laptop; prompt-echo cleanup and failure restoration are useful follow-up checks.

## 5. Live text streaming

The Minimal Writer now calls `WriterEngine.generate(prompt, on_delta=...)`. The stream callback schedules text appends onto Tk's UI thread. The completed cleaned answer replaces the preview when the model finishes. The app saves the prior document text and tracking metadata in memory and restores it if generation fails. The user confirmed that the real model streams words into the output as it generates. The user also tested Stop Writing live and confirmed that it stops generation.

## 6. Continue action

The Minimal Writer now includes a **Continue** button, and the user has confirmed the append behavior live on the laptop. **Write** replaces the visible output but preserves the current model session/context, so it can carry the story forward even when the prompt changes. The user tested this after Continue and likes this behavior; do not change Write to reset/reload the model unless they later request a fresh-session option. **Continue** sends a short continuation instruction with up to the last 2,000 characters of the current visible passage, appends a paragraph boundary to the existing output, then streams the response at the end. This anchors it to text the author may have edited. At completion the cleaned response is appended to the prior text. On generation failure, the original document is restored. If stopped, partial streamed continuation stays; if no chunks arrived, the original document is restored.

The user tested a comedic Tiffany/Kim passage: the first passage remained intact and the new writing followed it without repeating the whole original. The “(Continued here)” marker in the pasted sample was added manually by the user to show me where Part 1 ends and Part 2 begins, not generated by the model. Unit tests passed in commit `091280b0`: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40641857573) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40641857583).

The user has confirmed all key behaviors live: **Write** replaces the visible prose while keeping the story context, including with a changed prompt; **Continue** appends new prose to what is visible; Stop halts generation and requires reloading. A regression test exercises two Write actions with different prompts and asserts that output is replaced while the model session is not restarted and retains both prompts. Both CI workflows passed: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/40647067750) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/40647067765). This milestone changes tests and documentation only; the runtime app behavior is unchanged.

## 7. Rebuild boundaries

Do not delete old helper modules yet. They are currently dormant from the new UI's entry point. Once basic model writing and plain text editing are demonstrated reliably on the laptop, discuss and remove unused legacy code in planned pieces, with tests for each change.

Do not add the previous system back by accident. Specifically out of scope unless later requested:
- novel package management
- continuity summaries, clues, character state, or state update
- scene planning, Scene Idea parsing, or scene contracts
- semantic validators or automatic regeneration/review
- writing rules or hidden system prompts
- automatic manuscript file writes

The application should stay a simple writer until further pieces are agreed and proven.

## 8. Protected novel checkpoint: The Long Way Home

- Local: `~/Documents/MyNovel/The-Long-Way-Home`.
- Remote: `tony21675/The-Long-Way-Home`, permanent branch `main`.
- Accepted Chapter 1 Scene 10 is saved at `Manuscript/Chapters/Chapter_01/Chapter_01_Section_10.txt`.
- The remote state pointer remains Chapter 1, Scene 10. `Chapter_01_Section_10_after_state.json` is absent, so no transition to Scene 11 was saved.
- The latest model summary incorrectly sharpened Daniel's uncertain “maybe another hour” estimate into a near-certain critical-failure deadline, turned Morgan's hypothetical structural degradation into a diagnosis, and misdescribed Elena's instructions. The reviewer then returned unsupported claims and was correctly rejected by evidence validation.
- No change to accepted prose or novel state was made. Don't edit `current_state.json` manually, and don't bring old state-analysis workflow into the new Minimal Writer.

## 9. Repo / terminal / collaboration rules

- StoryBuilder repository: `~/Documents/StoryBuilder`.
- Current branch: `redesign/simplified-writing-workflow`; the remote currently has one branch. Long-term goal remains one stable `main` branch after deliberate review and merge; never switch/delete branches blindly.
- Use `python3`, never `python`, in Linux-laptop commands.
- Keep terminal instructions short, one command per step where practical.
- Discuss changes to app or novel packages first, except handoff-only updates.
- Preserve accepted text and saved story state.
- Update and prune handoffs at milestones.

### Local model inventory from earlier handoffs

The October 17–20, 2026, Taken at Dusk / StoryBuilder testing handoffs recorded these local models:

- **Gemma 4 E4B IT**, exact documented path: `~/Documents/Models/01 gemma-4-E4B_q4_0-it.gguf`. This was reported as the best-performing model in testing and the chosen writing model. The name identifies **E4B**, not E2B; the filename does not itself say “uncensored.”
- **Stheno 8B**. Recorded as another available model; its exact GGUF filename was not documented.
- **Llama 3.1 8B**. Recorded as another available model; its exact GGUF filename was not documented.
- **Gemma 4 E4B IT Ultra Uncensored Heretic GGUF**, Hugging Face source `llmfan46/gemma-4-E4B-it-ultra-uncensored-heretic-GGUF`. The author has now confirmed this model is also available locally. Its exact local GGUF filename and quantization are not yet recorded. The model card describes it as a decensored version of `google/gemma-4-E4B-it` made with Heretic, which targets refusal behavior rather than retraining it for different genres. Do not assume “uncensored” will change its romance-like prose style.

This is a historical handoff record, not a verified live listing of the current laptop directory. The active Minimal Writer scans `~/Documents/Models/*.gguf` by default (unless `STORY_MODELS_DIR` overrides it), so the current dropdown or a local directory listing is the authority on which files are present today. Never delete or replace any model without discussing it first.

## Two-model writing goal (October 28, 2026)

**Temporary hardware correction (October 28, 2026):** The author has access to a 16 GB RAM laptop for the next couple of months only. Older handoffs describe an 8 GB RAM laptop; treat that as the longer-term compatibility constraint unless the author says otherwise. Use the temporary 16 GB machine to test a stronger model, but prefer a practical fallback for an 8 GB system. Model file size is not the full RAM requirement: leave memory for the OS, runtime, KV cache/context, and generation. Do not assume a 5–6 GB quant will work well at the current 16,384-token context without checking memory use.

Keep the existing Gemma 4 E4B model as the general-purpose writer; the author likes its output so far. The author also confirmed the local inventory includes `llmfan46/gemma-4-E4B-it-ultra-uncensored-heretic-GGUF` (exact local filename/quantization still unconfirmed). The Heretic modification targets refusal behavior; do not assume it will change genre/style.

For a second model, the intended use is **explicit adult erotica/porn-style fiction featuring consenting adults**, not romance-novel style. The author is not looking for illegal sexual content. Keep Gemma 4 as the general-purpose writer and do not replace it. Current access to 16 GB RAM is temporary for a couple of months; keep longer-term fit for the previously documented 8 GB laptop in mind. No download or app change without discussion.

**Leading research candidate for the temporary 16 GB machine:** `Mantis2024/Dirty-Muse-Writer-v01-Uncensored-Erotica-NSFW`, a 9B Gemma 2 based GGUF specifically named and presented for uncensored erotica. A `Q4_K_M` file is documented at about 5.76 GB; quantizer documentation also lists `Q4_K_S` around 5.6 GB and smaller Q3 options. It is the most directly targeted candidate found so far, but creator labels are not proof of quality or style. It may need a reduced context (start lower than the app's 16,384 default) to leave RAM for the operating system and runtime. [GGUF model card](https://huggingface.co/Nazmiven/muse_model) and [imatrix quantization details](https://huggingface.co/mradermacher/Dirty-Muse-Writer-v01-Uncensored-Erotica-NSFW-i1-GGUF).

**Smaller alternative for comparison:** `mradermacher/eroticv1-GGUF`, with `Q4_K_M` documented around 4.92 GB, also supports llama.cpp GGUF loading. Its smaller weights may be easier to use on the 8 GB machine later, but quality and fit to the desired prose style are untested. [Model and quant list](https://huggingface.co/mradermacher/eroticv1-GGUF/tree/main).

`DavidAU/Qwen3-4B-Gemini-TripleX-High-Reasoning-Thinking-Heretic-Uncensored-GGUF` remains a small general creative-writing alternative that advertises all-genres fiction and erotica, but it is less specifically targeted than Dirty Muse. Test actual prose before choosing. None of these models has been downloaded or approved yet.

## 10. Read-only legacy dependency audit (October 28, 2026)

- The active launcher is `start.sh` → `sync.sh start` → `python3 minimal_writer.py`. The launcher does not run the old `storybuilder.py` interface.
- The Minimal Writer's project-code path is `minimal_writer.py` → `builder.writer_engine.WriterEngine` and `builder.workspace.MODELS_DIR`. The engine uses standard-library modules plus `pexpect`, the external `llama-cli` executable, and local GGUF model files.
- `WriterEngine` still has optional prompt-trace hooks, but Minimal Writer does not attach a trace object. The model is started with an empty system prompt. No StoryBuilder-added NSFW filter or writing-rule prompt is present.
- `builder.workspace` still contains legacy novel-discovery helpers, but Minimal Writer uses only `MODELS_DIR`; it does not load novel packages or story state.
- The legacy `storybuilder.py` remains in the repository and imports most of the old workflow modules. Those modules are not active through the Minimal Writer entry point, but they remain dependencies of the preserved legacy interface and/or its tests. Keep them until any removal is deliberately reviewed.
- **Protected Taken at Dusk secret letters: do not remove or alter.** Correction to the initial read-only audit: `builder/secret_letter.py` is not an obsolete cleanup candidate. The first-novel handoff identifies two separate, encrypted, local-only assets: Tiffany's letter at `~/Documents/MyNovel/Taken_at_Dusk/secrets/sarah_letter.enc.b64` and Tony's separate letter at `~/Documents/MyNovel/Taken_at_Dusk/secrets/sarah_tony.enc.json`. Their metadata and supporting files are also local-only and intentionally excluded from GitHub. Preserve both encrypted letters, both metadata files, the helper, verification script, local README, private key, and the `/secrets/` Git-ignore rule. The author has not yet seen the letter contents. Do not decrypt, display, copy, or add their contents to GitHub, handoffs, manuscripts, or StoryBuilder prompts unless the author explicitly asks to reveal them. The audit did not open or decrypt either letter, and nothing was deleted or changed in the novel repository.
- This was a read-only static audit. No application code, model configuration, branch, novel package, accepted prose, or novel state was changed.




## One-step Writer upgrade: preserve multiline prompts (October 28, 2026)

- The initial escaped-single-line transport failed the live exact-output test: the model output showed the newline separator as literal `\\n` and doubled path backslashes. That output exposed a transport problem, not just a prose-formatting preference.
- Root cause confirmed in llama.cpp's interactive CLI source: `--escape` does not decode escape sequences for interactive user turns. The old regression tests only mocked the escape-encoded payload, so they did not catch this runtime behavior.
- Corrective implementation: send the prompt with actual line breaks, enable `--multiline-input`, and append the CLI's trailing `/` marker to end the multiline turn. The CLI consumes the marker before tokenization. The streaming echo filter now matches multiline input while ignoring terminal line breaks.
- Both CI workflows passed for code/test commit `a44e37d30adb400367c46ca76881a1b786218c54`: [Python tests run #323](https://github.com/tony21675/StoryBuilder/actions/runs/40690286838) and [StoryBuilder tests run #588](https://github.com/tony21675/StoryBuilder/actions/runs/40690286747).
- Live exact-output and longer scene-generation checks passed on the Linux laptop. The scene retained distinct paragraphs, included the exact path `C:\\models\\drafts\\scene.txt` with single backslashes, preserved the literal sequence `\\n`, and showed no echoed prompt. The scene ended before the box was opened.
- Current next change: bind Ctrl+A to Select All in both the prompt and editable output text boxes. This is a focused UI fix; no extra controls or workflow changes. Automated tests are included in the same commit. CI and live shortcut verification are pending. Do not start another feature until Ctrl+A is verified on the laptop.
