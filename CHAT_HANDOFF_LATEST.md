# Writing project handoff index

**Updated:** November 11, 2026

This index covers writing projects only. Each application and novel has one authoritative handoff. The project repositories remain the source of truth; local mirror copies are maintained separately.

## Active handoffs

### Writing applications

- [Writer App](WRITER_APP_HANDOFF.md) — Minimal Writer code, launch, sync behavior, local handoff backups, features, known app issues, and testing.
- [Story Bible App](STORY_BIBLE_APP_HANDOFF.md) — the separate Story Bible application, its code, launch, sync behavior, local handoff backups, known issues, and testing.

These are two separate applications with separate launchers. They share the `tony21675/StoryBuilder` repository and its single current branch, `redesign/simplified-writing-workflow`. That branch is the GitHub default and the only branch. Keep its name for now: sync helpers explicitly block `main`, and some workflow/test triggers still refer to this branch. There is no additional branch clutter to clean up.

### Novels

- [The Long Way Home](https://github.com/tony21675/The-Long-Way-Home/blob/main/CHAT_HANDOFF_LATEST.md) — current novel priority. Chapter 1 Scenes 01–15 are accepted. Chapter 2 Scene 01 is saved and accepted; Scene 02 is next. The current broad author-approved direction is in [STORY_DIRECTION.md](https://github.com/tony21675/The-Long-Way-Home/blob/main/STORY_DIRECTION.md).
- [Taken at Dusk](https://github.com/tony21675/MyNovel/blob/main/HANDOFF_LATEST.md) — intentionally on hold until *The Long Way Home* is finished. Its branch reconciliation is deferred until the author resumes it.

A novel's own package is the source for its canon and manuscript: its Story Bible, character cards, locations, current state, and accepted scene files. Do not copy one novel's information into another novel's handoff.

### Future story planning

Future novel premises and unstarted concepts are kept separately in the private ChatGPT Library at `/Writing/FUTURE_STORY_PLANNING.md`. This is a parking record, not an active novel or software-project plan. The second-Mars-base fragment has now been connected by the author to *The Long Way Home*: the Japanese-owned base is part of that novel's crisis direction, not a separate standalone concept unless the author later defines a different story. The spacecraft-in-transit fragment remains separate and incomplete.

## Latest Writer app change — November 7, 2026

StoryBuilder now has a two-role model setup for trial:
- Prepare Scene uses a separately selected planner model (defaults to Qwen3.5-4B when available).
- Write, Continue, Rewrite Scene, AI passage revision, and New Session use a separately selected manuscript-writing model (defaults to Gemma 4 E4B when available).
- Both roles share one WriterEngine process and load sequentially. Switching tasks stops the previous llama-cli process before loading the selected role. Model filenames are saved in the user's config directory, outside the repository.
- llama.cpp is started with explicit Jinja chat-template handling and reasoning disabled.
- This first integration is for local testing; model assignments and creative quality remain provisional until Tony tests the updated Writer locally on The Long Way Home.

Author-approved creative philosophy: gaps in canon are creative space, not automatic prohibitions. Encourage plausible inventions, new technical details, character interactions and plot developments. Protect basic survival logic and major established story foundations, but do not smother the models with rigid lists of restrictions. The author chooses which inventions become canon.

StoryBuilder's Writer and Prepare Scene requests use short current-state context, brief facts for relevant characters, named location details, and the full text of the immediately preceding saved scene. A shared Markdown profile library now supplies only the selected novel's genre and intended-audience guidance; its full profile library is never sent. Each novel stores only its selected labels and separate explicit-content setting in its own Story Bible. The Story Bible remains the source of each novel's canon.

The lean-context update passed both GitHub Actions workflows on commit `1c5ad3c9d2b633ae9a08a3941227f414e4cc0484`: Python Tests reports 697 passed and 77 subtests passed; StoryBuilder tests reports 697 passed. Tony still needs to pull the update and run the suite locally. No novel manuscript, Story Bible, character-card, or model files were changed.

New Writer/Story Bible milestone: reusable genre and audience profiles now live outside Python in shared Markdown resource folders. Both Prepare Scene and manuscript writing receive only the profiles selected for the active novel. The existing Explicit Adult Content checkbox remains separate from audience selection and is connected to an explicit permission boundary. Both GitHub Actions workflows passed after this milestone; local laptop verification was confirmed for the two app interfaces. The Writer now also starts with no novel selected and clears old direction fields and model conversation history when the selected novel changes, while preserving the visible manuscript and its file tracking. Both workflows passed for the isolation change as well; local GUI verification of switching is pending.

Separate open issue: Prepare Scene retry still does not pass its previous generated direction back into the planner. Do not treat that behavior as fixed.

## Repository and verification checkpoint

- The obsolete nested `StoryBuilder/` checkout and its Git submodule pointer have been removed. The active Writer and Story Bible remain in the outer repository; no `.gitmodules` file or nested `StoryBuilder/` tree remains.
- Before the lean-context update, the full local suite passed 696 tests. The prompt-reduction source and tests passed both CI workflows on commit `1c5ad3c9d2b633ae9a08a3941227f414e4cc0484` (697 tests passed in each workflow; Python Tests also reports 77 subtests passed). Tony's local pull and full-suite run remain pending.
- The focused local handoff-backup tests previously passed (2 tests).


## Latest five-scene Writer trial — November 9, 2026

A disposable test novel was reset and five scenes were generated and reviewed without changing code, prompts, or model settings. The Writer met the requested natural endpoints in 3 of 5 scenes. It often carried immediate details forward, but Scene 4 skipped the approaching footsteps at the end of Scene 3 and restarted an earlier pump-inspection moment. Scene directions were frequently repeated as explanatory narration instead of dramatized. Scene 4 also introduced an unrequested physical/romantic beat that Scene 5 then carried forward.

**Working conclusion:** Keep the full previous-scene context change. This test does not prove the exact prompt payload or establish that continuity is fixed. The next discussion should focus on how scene directions become manuscript prose. No additional shared prompt rules, code changes, or model changes have been approved.

## Local handoff backups

StoryBuilder includes `backup_handoffs.py` and `builder/handoff_backup.py`. The Writer and Story Bible launchers refresh a local mirror after the StoryBuilder pull, and successful app or novel GitHub syncs refresh it again.

- Default local mirror: `~/Documents/Project_Handoff_Backups`
- Includes the StoryBuilder index and app handoffs, *The Long Way Home* handoff and story direction, and *Taken at Dusk* handoff/reference documents when present locally.
- Contains only named Markdown handoff/planning files. It does not copy manuscripts, credentials, encrypted assets, or secret-letter files.
- Run manually with `python3 ~/Documents/StoryBuilder/backup_handoffs.py`.
- GitHub repositories remain authoritative; the local mirror is an independent emergency copy.

## Rules that prevent handoff drift

1. Each writing application has one active technical handoff.
2. Each novel has one active novel handoff and, when useful, one separate broad story-direction file.
3. Future story concepts have one separate planning record.
4. Do not duplicate current status across documents. Link to the authoritative record instead.
5. After a meaningful milestone, update the relevant handoff after the milestone finishes. Include source-data checkpoints and verification status; do not use self-referential commit markers.
6. Clearly label generated prose as pending review until the author accepts it and it is saved in the manuscript.
7. Never delete an archive or overwrite local work as part of handoff maintenance.
8. When sources disagree, record the conflict and pause. Do not choose a version by guessing.
9. Preserve the working branch and its autosync behavior unless branch migration is deliberately coordinated and tested.

**Latest Writer context change:** Prepare Scene and manuscript Write/Rewrite now receive the entire immediately preceding saved scene instead of the former 1,800/2,000-character tail excerpts. Regression tests cover long scenes. Both GitHub Actions workflows passed on commit `c96281a191fb08e1438fc5b5c09b6a829b216bfb`. A five-scene live manuscript trial was completed on the laptop; it showed useful immediate detail carry-over but inconsistent chronological continuity and persistent scene-direction echoing. The test did not capture the runtime prompt, so it cannot prove the exact previous-scene payload.

**Project status:** The Long Way Home's broad crisis direction has been reconstructed from the author's latest decisions. Chapter 2 Scene 01 is saved and accepted; Scene 02 is next. The Writer's lean-context update is locally verified by Tony (697 tests and 77 subtests passed). The latest genericity cleanup removes the shared Computer/dialogue instruction, removes the complete-roster and blanket romance constraints from shared character context, and makes the active post-save ending-state prompt neutral across story types. Character names and story facts continue to come from the selected novel's own files. Both GitHub Actions workflows passed on source/test commit `b7166475842c3e452ef002c6fb4290caa9938fd1`; Tony's local test of this cleanup is pending. The November 9 scene-flow update removes mandatory `Natural endpoint:` output and Writer endpoint enforcement. Author-requested events remain intended events, while the Writer decides how they unfold and where each scene ends. The full previous scene remains available as context, with no requirement to begin in the next second or stay in the same place. Both GitHub Actions workflows passed on commit `48e0edff4bad52aa1bf3a039dc7c8cb2764465c5`: Python tests report 710 passed and 77 subtests passed; StoryBuilder tests report 710 passed. Local pull and live retest are pending. The Summer at Willow Bay test package is reset to Chapter 1, Scene 1 for a repeat of the same five-scene test. Prepare Scene's retry-direction behavior remains a separate known issue. *Taken at Dusk* remains on hold.


## Writer diagnostic tracing update — November 9, 2026

The diagnostic capture now joins Prepare Scene and manuscript generation for one prepared scene. It records the planner's exact input and raw generated direction, the final direction and additional author guidance present when Write is pressed, and the Writer's exact assembled input and prose response. Planner and Writer runtime sessions are labelled separately.

The pending trace stays in memory until prose generation finishes, then replaces the one existing trace file locally and in the private trace repository. Retries for the same scene append to the same capture. Novel switches, a different scene destination, or an abandoned/failed planner result discard the pending capture rather than letting it cross into another scene. No writing behavior, model choices, or prompts were changed. Focused tests were added; CI verification is pending.


## Reader-first working standard — November 9, 2026

This is the author's current, preferred way to develop and evaluate the project. It supersedes earlier trial notes wherever their evaluation approach conflicts.

- Review manuscript prose first as an ordinary reader, without looking at scene directions, planner output, prompts, or traces. Ask whether the story flows naturally from scene to scene, makes sense, and gives the reader people and events they can follow and care about.
- Put the reader's experience ahead of the story's underlying "bone structure." Continuity matters when a reader can feel a contradiction, repetition, confusing transition, unearned character shift, or other break in immersion. Do not turn every scene into a structural audit.
- A fictional story does not need every technical, scientific, logistical, or factual detail to be perfect. Allow imaginative license and ordinary imperfection. Correct a detail when it distracts or damages the reader's experience, not merely because it could be more exact.
- Do not expect every scene to resolve a prescribed beat or end at a planned point. Let scenes have the length, focus, and ending that suit the story. The next scene should carry the story forward coherently from what actually happened.
- Treat overwritten prose, repeated thematic ideas, rapid relationship progression, and similar tendencies as editorial observations. Fix only what materially weakens the reading experience; do not chase perfection.
- Scene-direction adherence and trace inspection are separate diagnostic tasks. Use them when the author specifically asks to assess prompt execution or investigate a technical issue, not as the default way to judge whether a story works.
- Do not make code, prompt, model, or workflow changes from a minor draft imperfection. Discuss a proposed change with the author first. Keep the one-change-at-a-time approach.

The November 9 *Summer at Willow Bay* five-scene retest was also read independently, as if the reviewer had never seen the directions. The story was judged coherent and readable overall, with a clear progression from Mara's arrival as an outsider to growing involvement in Willow Bay and a developing connection with Noah. The most noticeable reader-facing continuity bump was Scene 5 briefly replaying the wagon being freed, already resolved in Scene 4. Other observations (some repeated thematic explanation, ornate prose, and a slightly quick increase in physical familiarity) were editorial refinements rather than failures of story flow. No forced endpoint should be reintroduced on the basis of this test. The novel is on hold after Scene 5 pending the author's next decision.


## Per-novel writing preferences — implemented November 10, 2026

Story Bible now has an optional **How This Novel Should Read** text field, stored in each novel's own `story_bible.json` as `writing_preferences`. It is separate from genre, mood/tone, audience, explicit-content settings, and canon. New novels start blank; older novels load with a blank value; editing preserves the rest of the Story Bible.

The Writer appends only the selected novel's non-empty preferences to manuscript-writing context as flexible creative guidance. As of November 11, selected-novel writing preferences also enter Prepare Scene / Planner prompts as flexible guidance. No global prose style is hard-coded.

Both GitHub Actions workflows passed on commit `4fbeea85d80d95dbe125b5c18f2415e5b8584e49`: Python tests report 714 passed and 77 subtests passed; StoryBuilder tests report 714 passed. Local app pull and GUI testing remain pending. See the [Story Bible App handoff](STORY_BIBLE_APP_HANDOFF.md) and [Writer App handoff](WRITER_APP_HANDOFF.md) for details.

## AI-assisted story planning discussion — November 10, 2026

**Status: Design discussion only. No implementation or prompt changes have been approved.**

The author wants to brainstorm freely in ordinary language, without having to write or format a traditional outline. The planning AI should help sort ideas, identify relationships or conflicts, and arrange the author's ideas into a coherent overall story direction and broad chapter roadmap. Keep distinctions clear between:
- **Confirmed:** decisions the author has approved.
- **Proposed:** ideas the author is considering.
- **Open:** questions not yet decided.
- **Needs placement:** ideas worth retaining but not yet assigned to a story phase or chapter.

Nothing becomes official story direction until the author approves it.

This builds on the existing two-model Writer architecture, not a new model arrangement: Qwen already handles Prepare Scene/planning, and Gemma writes manuscript prose. The proposed evolution is to expand Qwen's role into an interactive story organizer that can help with brainstorming, overall story roadmaps, chapter roadmaps, and concise chapter-specific writing packets. Keep the current sequential model loading; only one model should be loaded at a time on the author's 16 GB laptop.

Gemma should receive only what it needs for the current chapter: its broad direction, current situation, relevant characters and their knowledge, essential established facts, necessary continuity from prior events, and any genuinely important boundaries. Do not send unrelated chapter histories or future revelations just because they exist in the overall plan. Preserve the immediate previous-scene context where it helps continuity.

**Creative philosophy:** broad direction, not a scene checklist. Do not require a fixed number of scenes, prescribed scene beats, or forced scene endings. The prior checklist-heavy approach repeatedly failed and made writing mechanical. Let Gemma decide how scenes unfold and where they naturally end while respecting approved story direction and important canon.

Persistent project files should hold the story's memory; do not depend on the small local models remembering an entire novel in conversation. Use an interactive propose/review/approve workflow to compensate for small-model limitations.

**Next design discussion:** an author-friendly brainstorming/idea bank, an overall story roadmap, broad chapter roadmaps, and a chapter-preparation step that assembles only the relevant information for Gemma. Review the current implementation before proposing code changes. Keep StoryBuilder generic, with each novel's planning material isolated inside its own project package. No code, prompt, model, or schema change has been authorized yet.

*Taken at Dusk* was used as an example during this discussion. Its repository remains on hold under its existing handoff; do not resume branch reconciliation or edit its canon/manuscript as part of this StoryBuilder design discussion.

## Deferred *Taken at Dusk* future-arc note — November 10, 2026

A separate, non-authoritative planning note preserving the author's discussion of *Taken at Dusk*'s two-part ending and longer-term rescue mission is saved in the ChatGPT Library at `/Writing/Taken_at_Dusk_Future_Arc_Notes.md`. It is intentionally outside the on-hold `tony21675/MyNovel` repository. When the author resumes *Taken at Dusk*, reconcile the note with the existing `STORY_PLAN.md` and `kidnapping.json`; do not alter the novel's held branches, manuscript, state, or canon before then.


## Story Bible canon now reaches planning and writing — November 11, 2026

The first clean *Taken at Dusk* package exposed a context-assembly defect: compact character references omitted ages and relationship status, and the Writer did not pass the novel's `relationships` or `canon_rules` fields into either Prepare Scene or manuscript generation. Current-state continuity notes were also omitted. The package data was present and editable, but the model was not receiving those facts.

**Implemented on `redesign/simplified-writing-workflow`:**
- Compact character references now include age and relationship status. An intentionally blank status is sent as “Not established,” not guessed.
- Prepare Scene receives the selected novel's fixed canon, established relationships, and optional writing preferences.
- Manuscript writing receives the selected novel's fixed canon and established relationships, in addition to its existing creative direction and writing preferences.
- Both planning and writing receive current-state continuity notes.
- Relationship references are explicitly described as factual background, not an instruction to place everyone in every scene. Fixed canon is explicitly not a scene checklist.

This is deliberately a small memory/context fix, not a validator or a new set of global writing rules. Each novel supplies its own canon. The Writer retains freedom over ordinary scenes, dialogue, locations, connective events, pacing, and scene endings.

**Verification on commit `798c3e94e83d84249779ee73c4d5005420b5902f`:** Python tests passed (716 passed, 77 subtests passed); StoryBuilder tests passed (716 passed). GitHub Actions:
- https://github.com/tony21675/StoryBuilder/actions/runs/42985828904
- https://github.com/tony21675/StoryBuilder/actions/runs/42985828913

Local GUI pull and live model testing remain pending. The updated *Taken at Dusk* package starts at Chapter 1, Scene 1 and keeps most of Chapter 1 for readers to know the seven core characters before the abduction.


## One generation, one scene — implemented November 11, 2026

Prepare Scene now asks for a direction for only the selected Chapter/Scene destination. It should not combine distinct time/place setups that function as separate scenes. A later setup can be prepared as its own scene.

The manuscript Writer adds a **ONE-SCENE SCOPE** to every Write, Continue, and Rewrite Scene generation. When the chapter and scene selectors are available, the scope names that exact destination. It keeps a generation within one scene and treats a distinct later setup as material for a separate generation, unless the author explicitly asks to include it in the same scene. This does not impose a fixed ending, required beats, a chapter scene count, or a validator.

The planner-to-writer diagnostic trace is unchanged and remains enabled by default. The final scoped Writer prompt is included in the captured prompt because the scope is added before trace setup. Existing local trace saving and upload to the private, single-file GitHub trace repository remain in place; each generation attempt finishes and uploads the latest `prompt_trace.json`, replacing the previous latest trace rather than building repository history. Upload failures still leave the local trace available.

**Verification:** Focused regression tests were added for planner scope, Writer scope, and the selected scene destination. GitHub Actions verification and the author's local pull/live test are pending.

## Author-required beats and Qwen-selected additions — implemented November 11, 2026

Prepare Scene now asks Qwen to produce a scene direction with two clearly separated beat groups:

- **AUTHOR-REQUIRED BEATS:** Every concrete event, action, or moment explicitly requested in the author's direction. Qwen must preserve all of them as required in the selected scene; it cannot omit, soften, replace, or defer them.
- **QWEN-SELECTED ADDITIONAL BEATS:** Qwen uses its own storytelling judgment to choose any number, including none. There is no quota or cap, and it should not pad a scene just to add beats.

The Writer receives the original Author's Direction separately from Qwen's summary. This is deliberate redundancy: Gemma must enact the original author-requested events in the current scene even if Qwen accidentally omits or weakens one in its summary. Qwen's own additional beats are carried into the prose naturally, but cannot displace or delay the author's required events.

The original direction is retained in memory for the matching prepared novel/Chapter/Scene, including when Prepare Scene is retried after the visible Author's Direction box has been cleared. It is discarded when the author switches novels or scenes, or saves the new scene, so it cannot leak into another destination.

The planner-to-writer trace remains active and unchanged in its upload flow. The trace now also records the final original author-required direction sent to the Writer. The assembled Writer prompt includes both the original required direction and Qwen's beat plan before it is traced, saved locally, and uploaded to the existing private GitHub trace repository. The uploader still keeps only the latest trace and retains the local copy if upload fails.

**Regression coverage added:** Planner instructions distinguish required author beats from any number of Qwen additions; the original direction survives planner retries; the Writer receives and prioritizes the original direction; prepared directions are scoped to the matching novel and scene; and the trace records the original required direction.

**Automated verification:** Both workflows passed on source/test commit `38be429bf89a7947262d6795b327f4b88f871f31`:
- [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/42996117903): 722 tests passed.
- [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/42996117774): 722 passed and 77 subtests passed.

The author's local pull and live Writer test are still pending.
