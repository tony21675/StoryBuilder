# StoryBuilder handoff, current checkpoint

Date: November 3, 2026

## Project and workflow

- StoryBuilder: `~/Documents/StoryBuilder`, GitHub `tony21675/StoryBuilder`.
- Active development branch: `redesign/simplified-writing-workflow`.
- Start Minimal Writer: `cd ~/Documents/StoryBuilder && ./start.sh`. It syncs the active StoryBuilder branch and launches `minimal_writer.py`.
- Start Story Bible: `cd ~/Documents/StoryBuilder && bash start_story_bible.sh`.
- Novel packages live under `~/Documents/MyNovel/*`.
- Use `python3`, never `python`, in Linux terminal commands.
- Before a local pull, run `python3 -m pytest -q`; stop and investigate if it fails. If green, pull with `git pull --ff-only`, then run the full suite again. Record only observed results.
- Keep app work incremental and tested. Discuss app or novel changes before making them; author-approved work and handoff-only updates are exceptions.
- Do not change manuscript prose, accepted drafts, novel state, or package data without explicit permission. Preserve backups.
- Avoid giant rule sets, rigid prose constraints, and over-prescriptive writing behavior. The author prefers natural character and story development.

## Current app state

- Story Bible manages novel setup and reference information: title, premise, setting, creative direction, audience/content level, Canon Rules, Character Cards, and locations.
- Character Cards are editable in plain English; only name is required. Canon Rules are stored in the existing `story_bible.json` `canon_rules` array.
- Minimal Writer supports local model loading, Write, Continue, New Session, Prepare Scene, text/ODT editing, Save Draft, Save Draft As, Save New Scene, scene browsing, and selected-passage revision with preview/accept.
- Save New Scene writes to the selected novel's correct chapter path and refuses to overwrite existing ODT/TXT scenes.
- No automatic manuscript or story-state mutation should be introduced without author approval.

## Recent app improvements (November 3, 2026)

### Canon Rules and story timeline

- Prepare Scene and Minimal Writer Write / Continue now receive saved Canon Rules.
- The Long Way Home has a story-time anchor of Day 1 at 16:00 (4:00 PM), late afternoon, Mars outpost local time. Its existing Story Bible Setting and `current_state.json` were updated in separate novel-repository commits: `7e4fe35370471c58ea09d04509a77841a3532e53` and `95cfb81a809366d481f75f5cbe80120fe72c8146`.
- Prepare Scene reads up to 6,000 characters from the selected previous scene and receives the saved timeline anchor. It proposes one coherent editable direction and a natural endpoint, without enforcing a fixed scene outline.
- Minimal Writer uses the saved time and previous-scene context in its prompts, but does not automatically advance/save `current_state.json` when a new scene is saved. Do not claim it automatically advances the clock.

### Shared scene craft and registered character roster

- A compact, reusable scene-craft section is shared by Prepare Scene and Write / Continue. It encourages lived-in scenes, natural variation in group size and dialogue, distinct voices, and ordinary moments while avoiding constant jokes, scripted turn-taking, over-polished banter, and unnecessary exposition.
- Both prompt paths receive the full list of registered character names, even when detailed character-card notes are limited to the characters relevant to the scene. The roster helps prevent invented crew members; it does not prohibit introducing a new character when the author's direction or established events call for one.
- Prepare Scene returns exactly two editable parts in the existing prompt box: **Scene direction** and **Natural endpoint**, followed by the instruction to write manuscript prose only and stop at the endpoint.
- The author live-tested this format. It generated the two labeled parts and used only the six registered crew members in the subsequent dinner scene. This is a useful check, not a guarantee that the model can never make a continuity error.

### Scene-to-scene continuity instruction (November 3, 2026)

- The author approved one small, generic instruction: **When a scene follows an existing scene, continue directly from its final moment. Carry forward the established location, characters present, and ongoing activity; only change time or place when the author's direction calls for that transition.**
- Added this sentence to the existing shared guidance in `builder/story_craft.py`. Because that helper already feeds both Prepare Scene and Minimal Writer's Write / Continue context, the same instruction reaches both paths. No new UI, Story Bible setting, schema, or novel-package file was added.
- Added assertions in `tests/test_story_craft.py` to verify delivery to Prepare Scene and Write / Continue.
- Updated one obsolete assertion in `tests/test_character_context.py`: the intended behavior is to include the full registered-name roster while withholding detailed profiles for unmentioned characters.
- Relevant commits: `fd38ff51e736933d7413c6be27b2f26e60bea6c4` (prompt guidance), `fc3c7437d09496958196aa01e82af4a00b5fc093` (prompt-path tests), and `cb6b3dc29d1bd0e553ec1325e8e0a8888e3e2ded` (roster test alignment).
- Latest verified StoryBuilder branch head: `cb6b3dc29d1bd0e553ec1325e8e0a8888e3e2ded`.
- CI on that head: compile passed. Python pytest reports **633 passed, 1 failed, 77 subtests passed**. The sole remaining failure is the unrelated Tkinter harness test `test_blank_name_does_not_save_or_close_the_editor`, where a fake root is a plain object without `.tk`. The StoryBuilder unittest workflow reports the same lone harness error. The new continuity tests and updated roster test all pass.
- CI runs: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41725096087) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41725096065).
- This latest code has **not yet been pulled or tested locally**. Follow the normal local pre-pull and post-pull test gate before relying on the update in Minimal Writer.

## Current novel: The Long Way Home

- Local package: `~/Documents/MyNovel/The-Long-Way-Home`. GitHub: `tony21675/The-Long-Way-Home`, branch `main`.
- Premise: Six young, unmarried crew members share life and work at a Mars research outpost. Far from Earth, they build routines, friendships, rivalries, and a sense of home. An unexpected accident eventually threatens the outpost and their survival; the exact failure and repair solution are not predetermined.
- Setting: crewed Mars research outpost in the near future, reasonably credible technology and environment. Story starts Day 1 at 16:00, late afternoon, Mars outpost local time.
- Creative direction: Science Fiction; Humorous, Serious, and Tense; Adult audience; explicit adult content enabled.
- The six authoritative crew cards are: Daniel Okafor (male, straight), Elena Vasquez (female, straight), Morgan Reed (female, bisexual), Priya Shah (female, straight), Ryan Mercer (male, straight), and Zoe Bennett (female, bisexual). Preserve the separate gender and sexual-orientation fields and the traits already saved in each card.
- Canon Rule: the life-support accident is a later major turning point. Early chapters should establish the crew's everyday lives, personalities, friendships, and relationships. Do not repeatedly add ominous hints, unexplained noises, system discrepancies, or minor malfunctions just to foreshadow it. The author determines when the story is ready.

### Chapter 1 manuscript checkpoint

- Fresh restart began November 2, 2026.
- Scene 1: Daniel and Morgan preparing dinner. It was recovered from the November 3 sync safety stash, restored to active Chapter 1 Section 1, and committed/pushed to the novel repository. The temporary recovery folder is `~/Documents/The-Long-Way-Home-Recovery`; the stash was intentionally retained until the restored scene was synced. Do not restore the three obsolete backup scenes that were removed from the recovery folder.
- Scene 2: Daniel and Morgan preparing dinner in the galley, with the other four crew arriving only when the meal is ready.
- Scene 3: the six crew together at dinner. The first generation included an unlisted character (Liam) and was discarded; a later generation with only the six established crew was accepted and saved.
- Scene 4: post-dinner cleanup and the movie-night decision. Saved on November 3. It includes the six crew, connects directly to Scene 3, and ends with Elena offering to pull up the movie catalogue. **At the end of Scene 4, the crew is already in the media/recreation room.**
- Scene 1's final line mentions nutrient paste because it was written before the pantry was expanded. This is intentional historical continuity; do not change it solely because the pantry details were later updated.
- The Story Bible locations **Crew Quarters** and **Bathroom and Hygiene Facilities** were added and saved locally on November 3. Crew Quarters describes six individual private bedrooms along a shared corridor, each with a sleeping berth, storage, desk/workspace, and room for personal touches. Bathroom and Hygiene Facilities describes shared private toilet compartments, enclosed shower stalls, sinks, mirrors, toiletry storage, and appropriate water conservation/recycling. Keep individual bedroom decor open for the story. The novel repository sync status for these latest location edits has not been verified; StoryBuilder code sync and novel sync are separate operations.

### Scene 5 and pacing: exact resume point

- Scene 5 is the next writing task. The author reviewed an initial generated draft and caught a continuity error: it restarted with the crew cleaning a communal area/kitchen, despite Scene 4 already ending with everyone in the media/recreation room and Elena offering to open the movie catalogue. **That Scene 5 draft is not accepted canon. Do not accept or reuse its backward location reset or repeated cleanup.**
- The author approved one small general continuity rule (above) so each new scene begins at the previous scene's final moment unless the author's direction explicitly calls for a transition.
- Regenerate/prepare Scene 5 from saved Scene 4 after the new StoryBuilder continuity change is pulled and locally checked. It should continue with the crew already in the media room, browsing and choosing a movie, with natural conversation and character interaction. A fitting endpoint is the group choosing a movie and settling in to watch it together.
- Do **not** force everyone to bed in Scene 5. The author explicitly rejected rushing the evening toward bedtime. Movie night may take more scenes if the story naturally wants them.
- There is no required number of scenes per chapter. Chapter 1 may take 6 scenes, 12 scenes, or however many the story needs. Do not aim for a quota or compress enjoyable ordinary moments to reach the plot event.
- Chapter 1 ultimately ends with the sudden, unexpected major life-support failure after the crew has gone to sleep and awakened the following morning. Before that, let the crew's ordinary life, relationships, movie night, bedtime, and morning routines develop naturally. Do not repeatedly seed ominous hints or minor malfunctions. The exact failure and repair solution remain open for the author to decide.

## Protected novel data

- `Taken_at_Dusk` is an important existing novel. Preserve its two encrypted secret letters, related local-only metadata, helper scripts, private key, and `/secrets/` ignore rule. Do not decrypt, display, copy, upload, or change them unless explicitly asked.
- Keep disposable test packages local-only and never sync or publish them.
