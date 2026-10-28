# StoryBuilder handoff, current checkpoint

Date: October 28, 2026

## Direction

Rebuild StoryBuilder piece by piece. The active app should load a local model and write without app-added story rules or story-management machinery. Keep legacy code recoverable for now. Do not touch novel packages or accepted prose.

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
- `builder.workspace` still contains legacy novel-discovery helpers, but Minimal Writer uses only `MODELS_DIR`; it does not load novel packages or story state.
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

No novel package loading, scene planning, character cards, continuity system, writing rules, validators, state summaries, automatic reviews, or automatic state changes. Do not delete legacy modules until removal is discussed.

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
- The first live GUI check now passed: clicking **New Session** displayed the expected success status (`New session ready with [model name]. Visible text was kept.`) without an error. This confirms the clear command received its expected confirmation and the visible text was preserved. One final live check remains: submit a completely unrelated prompt with **Write** and verify the previous conversation no longer carries over.

### Next step
- With the model still loaded, enter a completely unrelated prompt and click **Write**. Confirm the response starts fresh rather than carrying over details from the prior story. No code change is needed for this check.
