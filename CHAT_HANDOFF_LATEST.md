# StoryBuilder handoff, current checkpoint

**Canonical handoff:** This is the sole current session and writing-workflow handoff. Use it for the current project checkpoint; older handoff copies are historical and are not competing sources of current status.

**Scene review:** The former trace/validator workflow has been scrapped. Do not look for saved traces. Review scenes directly from the prose the author shares.


Date: November 4, 2026

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
- Feature implementation and test-alignment commit: `cb6b3dc29d1bd0e553ec1325e8e0a8888e3e2ded`.
- The latest commits after the implementation checkpoint only update this handoff file. The CI runs below validate the code at `cb6b3dc29d1bd0e553ec1325e8e0a8888e3e2ded`; no application code changed afterward.
- CI on that head: compile passed. Python pytest reports **633 passed, 1 failed, 77 subtests passed**. The sole remaining failure is the unrelated Tkinter harness test `test_blank_name_does_not_save_or_close_the_editor`, where a fake root is a plain object without `.tk`. The StoryBuilder unittest workflow reports the same lone harness error. The new continuity tests and updated roster test all pass.
- CI runs: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41725096087) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41725096065).
- This latest code has **not yet been pulled or tested locally**. Follow the normal local pre-pull and post-pull test gate before relying on the update in Minimal Writer.


### Media and device boundary instruction (November 3, 2026)

- Added a compact **MEDIA AND DEVICE BOUNDARIES** section to the shared guidance in `builder/story_craft.py`.
- When characters watch, listen to, read, or view content through a television, radio, phone, computer, screen, speaker, or other device, keep a clear boundary between that content and the story's present scene. Events/settings/actions presented through the device remain content being shown or reported, not the characters' physical surroundings or current activity. Keep characters in their established real-world location. They may react, comment, imagine, compare, discuss what the content tells them, or act on information when the story gives them a reason; do not physically place them inside the depicted or broadcast content unless the author's direction explicitly establishes participation, such as an interactive game or immersive simulation.
- The shared helper already feeds both Prepare Scene and Minimal Writer Write / Continue, so this guidance reaches both paths automatically. The author should not need to repeat a media-boundary reminder in every individual scene prompt.
- Added regression assertions in `tests/test_story_craft.py` to verify the media guidance exists in the shared helper and reaches both Prepare Scene and Write / Continue, including the distinction between not entering the media and still being allowed to act on information.
- Initial implementation commit: `4e22b39a6d3be3b4124ad261e96a05127c498260`; wording refinement: `3828ecbf107218f612f543dcb0a91c52d9d48397`; test/assertion commits: `f908bbc23c7d0e3e3a9bf55b258948329f63fbd3` and `662860839ffafd8c17059df71088075df4758568` (latest application-code branch head before this handoff refresh).
- **Verification status:** no CI result was available for this new commit when this handoff was updated, and it has not been pulled or tested on the user's laptop. Do not claim the new tests have passed. Follow the established pre-pull and post-pull `python3 -m pytest -q` gate before relying on the change locally.


### Prepare Scene: natural downtime correction (November 3, 2026)

- The author approved a **small correction, not a replacement of the Prepare Scene prompt**. In `builder/scene_preparation.py`, the existing instruction that said a scene "should contribute" through character development, relationships, choices, or events was softened.
- It still asks Gemma to build directly on the previous scene, preserve natural momentum, and provide one coherent direction. It now explicitly says a scene does not need a new task, problem, decision, or change of activity to be worthwhile; ordinary conversation, recreation, observation, shared experiences, and comfortable silence can carry a scene. It also cautions against inventing an activity merely to create a sense of progress.
- Added assertions to `tests/test_scene_preparation.py` to make sure the generated planning prompt includes this flexibility.
- A second small correction clarifies the meaning of **Natural endpoint**: it must be the scene's last, completed beat, not an event that occurs near the end. Prefer a completed action, response, or settled moment; avoid stopping on an unfinished exchange or the beginning of another activity. The prose writer is explicitly told to finish on this beat and stop. This addresses a recent test where Elena's stretch happened, but Gemma continued with Daniel's unfinished thought and left the scene hanging.
- Added regression assertions for the completed-final-beat requirement in `tests/test_scene_preparation.py`.
- This is separate from the shared media/device boundary instruction. The media boundary applies to Prepare Scene and Write / Continue through `builder/story_craft.py`; the downtime correction applies specifically to the Prepare Scene planning instruction.
- Initial implementation commit: `604d91e84212cfe99517bd1a4d29eab13ece72aa`; downtime test commit: `56c6588002ecac2d1139a66d016e89d4940ac364`; endpoint refinement: `7fbe71b2dd8eed2bb4ece99f2cb9b9fc2e65fe8e`; latest test commit / current application-code branch head at this update: `e1d2df612803a6e9bc4c005f2c714dd0f74d4128`.
- **Verification status:** these latest changes have not been pulled or tested on the user's laptop. No CI test result is available for the new commits. Do not describe the prompt adjustment as tested or proven to change Gemma's behavior yet. Follow the existing local pre-pull and post-pull `python3 -m pytest -q` gate.

### Prepare Scene diagnosis / scope

- The earlier Prepare Scene prompt asked: "The scene should contribute through character development, relationships, choices, or events that grow naturally from what is already happening." This could over-cue a small local model to invent a new task or development even when the natural continuation is recreation, conversation, observation, or quiet companionship.
- The user wants to work on the planning prompt before writing another scene, while preserving its current structure and two-part output. Do not replace the full prompt or add a long checklist. Evaluate the small correction in actual Prepare Scene outputs first.
- Other existing instructions remain in place: continue from the previous scene, respect the timeline and canon, avoid invented danger/hooks, produce exactly **Scene direction** and **Natural endpoint**, and leave room for prose to develop naturally.
- The user does not want every scene prompt to be hand-written. General writing guidance should do the routine work; the author only needs to intervene when a specific scene genuinely needs steering.


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

### Cross-chat context and manuscript verification (November 3, 2026)

- The handoff currently contains a useful story summary, but not the full accepted prose of Scenes 1–4. This is insufficient evidence for definitive line-level continuity judgments. When the author shares a new scene, compare references against the actual preceding accepted prose whenever it is available. Do not infer that a reference is wrong merely because it is absent from this condensed handoff.
- The novel repository's GitHub `main` tree currently shows only `Chapter_01_Section_01.odt` through `Chapter_01_Section_03.odt`. The November 3 local work includes later scenes, and the handoff already notes that the latest novel-package changes have not all been verified as synced. **Do not treat the remote MyNovel repository as a complete copy of the active local manuscript.** Do not pull, overwrite, or use it as the definitive chronology source without checking local sync status.
- Scene 5 was regenerated from Scene 4 and shared in chat. It continues in the recreation/media room: Elena opens the movie catalogue, the six crew members banter about what to watch, they settle on a selection, and the opening titles begin. This remains the starting checkpoint for the later movie-night work. The selected entertainment is intended to be a fictional pirate adventure, not a real named movie.
- Scene 5 includes the line, “We’ve survived orbital mechanics, geology nightmares, and a near-catastrophic life support scare.” A previous review called the life-support reference a chronology error because the major life-support accident is planned for later. **That verdict is withdrawn pending comparison with the actual accepted earlier scenes.** Treat this as an unresolved continuity question, not an established error; it may refer to an already-established past incident. Do not change the prose without the author's decision.
- The old trace/validator workflow is scrapped. No trace is expected or required. Review the manuscript text the author shares, using the handoff and actual accepted scenes as context.
- For future chat transitions, carry forward the exact last accepted scene ending, the current unaccepted draft/review status, and any unresolved continuity questions. A premise summary alone is not enough.
### Current movie-night work and exact resume point (November 3, 2026)

- **Scene 5 remains the starting checkpoint.** It ends with the six crew members in the recreation/media room after choosing a movie and the opening titles beginning. Scene 4 had already placed everyone in that room, and Scene 5 continues from there.
- The author briefly chose the real film *Pirates of the Caribbean: The Curse of the Black Pearl* as a movie-night selection. This led the local model to recreate detailed movie plot events and repeatedly blur the movie's setting with the astronauts' physical surroundings. **The author decided to abandon the real-film approach.** Return to an unnamed, fictional pirate adventure as background entertainment. Do not bring the real film's characters, plot, or specific scenes into the novel.
- **Scene 6 was reset and regenerated from Scene 5** using the fictional pirate-adventure approach. The current shared draft features a tropical ocean, a wooden sailing ship, and a distant island, with the six crew members reacting and talking while watching. The author explicitly likes natural comments comparing what they see with life on Mars and what they miss from Earth; do not suppress all Mars comparisons in the name of escapism.
- Morgan and Zoe have shown playful warmth and comfortable physical/social interaction. The author is open to this developing into a close friendship or possibly something romantic, but has not decided. Let their relationship emerge naturally. Do not assume bisexuality means attraction to each other or force a romance.
- The author referred to preparing Scene 8 after this reset. A subsequent Prepare Scene direction mistakenly turned the movie's ship approaching an island into a real operational mission: Elena led an approach assessment, Morgan checked tides/anchoring, Daniel pulled up bathymetry, and the crew behaved as though they were aboard a ship or on a bridge. The resulting prose placed the crew in a shipboard setting rather than clearly watching from the recreation room. This is the concrete failure that prompted the new shared media/device boundary instruction above.
- The acceptance/save status of that latest shipboard Scene 8 prose was not explicitly confirmed. Do not silently rewrite, delete, or declare it accepted; ask the author only if a later action truly depends on that status.
- The author does not want every scene prompt to require a custom reminder whenever a character sees or hears something through media. The new shared guidance is intended to handle television, radio, phones, computers, and similar devices automatically. It does not prescribe what the characters must say or react to.
- No fixed number of scenes is required in Chapter 1. Let the movie night and other ordinary moments take the space the story needs; do not force bedtime or rush toward the life-support failure.
- Chapter 1's eventual major life-support failure remains a later, sudden turning point after the crew has gone to sleep and awakened the following morning. Do not repeatedly plant ominous hints, unexplained noises, minor malfunctions, or premature emergencies. The author determines when the story is ready.


## Protected novel data

- `Taken_at_Dusk` is an important existing novel. Preserve its two encrypted secret letters, related local-only metadata, helper scripts, private key, and `/secrets/` ignore rule. Do not decrypt, display, copy, upload, or change them unless explicitly asked.
- Keep disposable test packages local-only and never sync or publish them.


## Current checkpoint (November 4, 2026)

### The Long Way Home: outpost population and command responsibility

- The author updated the existing **Outpost** location in Story Bible, adding to its Description that the permanent Mars facility has approximately **50 personnel**. The six central characters are one crew group within the larger population; other personnel cover command, engineering, life support, power generation, medicine, science, communications, logistics, maintenance, and safety. Most remain background figures unless the story needs them.
- The author also updated the existing **Duty Rotations and Chain of Command** Canon Rule; this was an addition to the existing rule, not a new third rule. It now establishes that Elena is overall commander of the approximately 50-person facility and is responsible for the safety and operation of the whole outpost. Department leads and duty officers manage their areas and personnel; Elena trusts their expertise and does not personally supervise every routine task. She can enjoy personal time while remaining conscious of her overall responsibility.
- The other existing Canon Rule remains unchanged: the major life-support accident is a later turning point, and early chapters should focus on ordinary lives and relationships without repetitive ominous hints or minor malfunctions.
- The author asked whether to establish a daily schedule. We discussed a **loose routine** (work periods, duty rotations, personal time, sleep), but **no separate Crew Daily Routine rule or fixed timetable has been added**. Do not add one without discussion. The intended principle is that the crew work scheduled duties, share watch responsibility, have genuine downtime, and sleep; avoid inventing a task or maintenance event every time a quiet scene needs movement.
- These Story Bible edits were saved locally according to the author's confirmation. Whether the novel package was synced to its GitHub repository after these specific Story Bible edits has **not** been confirmed. StoryBuilder code sync and novel-package sync are separate.

### Chapter 1: scene numbering correction and movie-night progress

- The author identified the difference between **Save New Scene** and **Save to Selected Scene** as the likely cause of a duplicate scene number. Save New Scene creates the next numbered scene; Save to Selected Scene overwrites the selected existing scene after confirmation. When replacing a generated scene, load/select the existing target and use Save to Selected Scene; when creating the next scene, use Save New Scene.
- The numbering mismatch was traced to an original Scene 6 attempt using the real film *Pirates of the Caribbean* and a replacement fictional pirate-adventure Scene 6 apparently saved as a new scene rather than replacing the old one. The author synced the novel package and renamed the active later files so the current sequence is back in order. The exact archive location/disposition of the superseded real-film version was not confirmed; do not delete any backup or rename files again without checking.
- Current intended sequence after correction:
  - **Scene 5:** The six crew choose a movie in the recreation room; opening titles begin.
  - **Scene 6:** Replacement version with a fictional pirate adventure, tropical sea, wooden galleon, and island. Crew comments and comparisons to Mars are welcome.
  - **Scene 7:** The fictional ship/island sequence continues, reaching a lush island and sheltered cove.
  - **Scene 8:** The crew continue watching together; the scene reaches the film's ending and closing credits. The author stated that the movie's exact content is not important; crew bonding and learning about the six characters are the real purpose. Do not spend more time policing the film's internal genre or details unless it disrupts the crew's physical reality or their relationships.
- **Scene 9 draft:** After the credits, the crew ease back into conversation. The useful part includes playful comments about the film's impractical vehicles, character banter, and Daniel's dry remark about transport designs not working for sustained Martian travel. The model then drifted into another dinner-planning conversation, which duplicates an earlier dinner scene and should be removed. The author was given in-app selection instructions: select from the paragraph beginning "Elena let out a breath she hadn't realized she was holding..." through the end of that unwanted dinner detour, then delete it, preserving the preceding scene text through Daniel's hovercraft comment. The author was then told to use **Save New Scene** for Scene 9, but an explicit confirmation that the trimmed Scene 9 was saved was not received. Treat the saved status as unconfirmed.
- **Scene 10 draft:** Prepare Scene initially suggested coffee-ground logistics and an invented maintenance cycle. The author preferred a natural wind-down with conversation and then going to quarters for sleep. The generated draft features the crew teasing one another about fictional vehicle designs and Martian life, then saying goodnight and returning to their individual quarters. It closes with the common area quiet and all six settling in for sleep. The author felt Elena's portrayal was broadly right: she can relax and enjoy her crew without turning her command responsibility off completely. Do not overcorrect Elena into either a constant supervisor or someone who forgets she commands the outpost. Scene 10 was shared for review, but explicit save/acceptance confirmation was not received.
- A few personal-history anecdotes appeared in the Scene 10 draft (Morgan nearly tripping over a data cable during training; Ryan's failed nutrient-paste synthesis glowing green). These are unconfirmed invented details, not established canon. Do not treat them as facts until the author accepts them.
- The next major story beat is not automatically the life-support accident just because the crew are going to sleep. Let the author decide how many ordinary scenes or how much elapsed story time occur before the next morning and the later accident. Do not force a fixed number of scenes or rush the turning point.
