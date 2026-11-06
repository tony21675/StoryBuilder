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
- These Story Bible edits were saved locally and the author subsequently confirmed a successful sync of the novel package to its GitHub repository (`main`), with `story_bible.json` as the only local changed file committed and pushed. StoryBuilder code sync and novel-package sync are separate.

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

- **Agreed Chapter 1 direction:** After the crew's first evening and sleep, show an ordinary morning before the major accident. The six wake, shower, get dressed, have coffee and breakfast, then head to their work assignments. Allow the wider approximately 50-person outpost to feel normally active, without turning background personnel into a large new named cast. The life-support failure should happen later while the crew are at work, as a sudden unexpected turning point. Do not add ominous foreshadowing, minor malfunctions, or clues beforehand. Scene 11 is intended to begin with the morning routine, but the number of scenes before the accident remains open and should be determined by natural story development.

### Creative principle: let the story breathe

- The author approved this as a standing creative principle: **"Letting the story breathe without giving it CPR if it coughs."** Do not intervene in every small unexpected development just because it is not exactly what was anticipated. A minor hiccup is not automatically a crisis; an ordinary problem does not have to become an emergency; an unusual discovery does not automatically need to become a plot twist. Let characters live, react, make mistakes, joke, work, rest, and have uneventful moments. Intervene when continuity genuinely breaks or when the prose conflicts with the author's intentions.
- **Prepare Scene tuning target:** The author estimates that roughly 50% of recent Prepare Scene outputs need a tweak, down from about 90% earlier. The desired goal is approximately **1 in 5** needing an unplanned correction. Treat this as a direction-of-travel target, not a reason to overcorrect: accept prompts that are already workable, and only revise when there is a meaningful continuity issue, conflict with author intent, or an avoidable forced event/endpoint. Do not rewrite a prompt merely because a marginally different version can be imagined. This target does **not** discourage deliberate author-directed steering when the author wants a particular event, reveal, transition, or turning point to happen; those are intentional creative choices, not unnecessary corrections.
- Clarification to the earlier foreshadowing guidance: routine problems, maintenance, checks, unusual readings, and scientific discoveries are normal parts of operating a Mars outpost. The crew should investigate relevant things because they live on an unfamiliar planet. Do **not** automatically treat these ordinary events as clues to the later major life-support accident.
- On Mars, **water, food, and oxygen are all critical survival resources** because they cannot simply be obtained from the local environment as on Earth. Life-support-related systems are therefore high-priority systems, not casual or low-importance conveniences. However, not every routine reading, adjustment, or minor issue involving infrastructure indicates a life-threatening failure.
- The crew are a close team living in a confined environment. Shared facilities and ordinary proximity can be depicted naturally without manufacturing embarrassment or conflict. Scene 11's shared shower sequence was discussed; the author does not consider the overlapping use a continuity or comfort problem, and the exact shower order does not need correcting.
- Scene 11's morning work assignments (including Morgan's geological investigation and Daniel/Ryan's equipment checks) were considered plausible ordinary work. The author does not want ordinary work or discovery stripped from the story merely to avoid foreshadowing. Scene 11 was reviewed but the author has not explicitly confirmed its final save/acceptance status.



### Disaster concept under consideration: CO₂ scrubbers and hydroponics

- The author is considering failure of the outpost's **CO₂ scrubbers** as the major life-support disaster. This is a working story direction, not yet confirmed as a new Story Bible Canon Rule. The exact failure mechanism, sequence, affected equipment, and repair solution remain undecided.
- The hydroponics bay can provide a **limited secondary buffer**, not a miracle cure. Healthy plants under adequate lighting and airflow can absorb some CO₂ and release oxygen through net photosynthesis, buying the crew time. The growing area cannot replace full-capacity mechanical CO₂ removal for approximately 50 people indefinitely.
- The dramatic role of the hydroponics bay is to give the crew additional time to investigate, coordinate, and restore proper scrubbing. It should not resolve the emergency by itself or make the mechanical scrubbers expendable.
- Do not add detailed failure mechanics, warning signs, or advance foreshadowing to early scenes. The author will decide when the disaster enters the story and how much technical detail to establish.


### Minimal Writer: assemble chapter and finished novel (November 4, 2026)

- Restored manuscript assembly in the current Minimal Writer, which previously lacked the old StoryBuilder **Assemble Chapter** action. Added two buttons below the novel/chapter/scene selectors: **Assemble Chapter** and **Assemble Finished Novel**.
- **Assemble Chapter** compiles the selected chapter's saved scene documents in numerical order. **Assemble Finished Novel** compiles every chapter that contains saved scenes, with chapter headings in numerical order.
- Both actions read accepted scene files from the selected novel package, including current ODT files and legacy TXT files (when both formats exist for a scene, the scene browser's existing ODT-preference behavior is used). They create formatted ODT copies under `Manuscript/Compiled/`:
  - `Chapter_XX.odt`
  - `{Novel_Title}_Complete_Novel.odt`
- The assembly actions use saved scene files only; unsaved text in the Writer output pane is not included. They do not modify original scene files. Running either action again refreshes/replaces only its generated compiled ODT.
- Assembly logic is in `builder/manuscript_assembly.py`; UI actions and buttons are in `minimal_writer.py`.
- Tests added: `tests/test_manuscript_assembly.py` (five cases: numerical order, ODT/TXT handling, duplicate ODT preference, multi-chapter assembly/empty folders, empty input, refresh without source mutation) and `tests/test_minimal_writer_assembly_actions.py` (four UI action cases).
- Relevant commits: `c4f7fa16bc419c325fd24c70bdadf7682931f4fc` (assembly module), `ffcd88a46c54c1a8263953396b274e9270fe8dea` (assembly helper refinement), `b234641beff1236625c19e33f5f16fffd44e8f85` (assembly tests), `bc26587ee571df0e53435cc414107a4ae83d1f09` (Minimal Writer buttons/actions), `a9e66169bf96f50745261a9f3f03119d41aed8f0` (UI action tests), and `3448da80584cad3d2f7dfaafb573a183b34ab6ea` (test fallback correction).
- Initial GitHub Actions run at `3448da80584cad3d2f7dfaafb573a183b34ab6ea`: compile step passed; all nine new assembly tests passed. The full test suite then failed on two stale assertions expecting earlier Prepare Scene wording, plus the known unrelated Tkinter test-harness error in `test_blank_name_does_not_save_or_close_the_editor` (fake root has no `.tk`).
- Updated only those two stale assertions to match current approved prompt wording: `d165602ba6fd558eb6eef770a3becfc97dfe862f` and `04ef9ae35b8a2f2d5809d5161e74372006987d82`. GitHub Actions on `04ef9ae35b8a2f2d5809d5161e74372006987d82` then completed: compile step passed; pytest reports **642 passed, 1 failed, 77 subtests passed**; unittest reports **643 tests with one error**. Both workflows identify the same single unrelated known Tkinter harness issue in `test_blank_name_does_not_save_or_close_the_editor` (`messagebox.showerror` receives a fake root with no `.tk`). The two stale Prepare Scene assertions now pass, and the new assembly tests pass. Do not claim the full suite is green. The Tkinter harness failure remains untouched.
- The new assembly feature has **not** been pulled or tested on the author's laptop. Follow the established local pre-pull and post-pull `python3 -m pytest -q` gate before relying on it locally.


## Future story-planning board: Mars outpost survival arc (November 4, 2026)

**Status: brainstorming only. These are possibilities to revisit as the story progresses, not new Story Bible Canon Rules, fixed plot commitments, or a predetermined sequence. Keep the author's options open and decide details only when the manuscript reaches them.**

### Current manuscript point

- Chapter 1 ends with **Scene 15**, which the author saved. Delta-Seven is the first confirmed CO₂ scrubber failure. The remaining scrubbers are still operating, but they are not fully compensating for the lost capacity and CO₂ continues to rise. No other scrubber has yet been confirmed failed, and the cause remains unknown.
- The author has moved to **Chapter 2, Scene 1**. Its current direction follows Daniel and Ryan as they coordinate a professional response with higher-level life-support personnel and send a secure advisory package toward Mission Control. At the time of this handoff update, the generated prose has not yet been reviewed or confirmed saved.
- The outpost Computer AI has been added as one continuous Canon Rule in the local Story Bible: facility-wide voice/tablet/workstation access; crew address it as "Computer"; consistent feminine voice, calm conversational manner, recognizes crew members, understands context and follow-ups, monitors systems and assists with information/diagnostics, with human authorization for critical changes. Scenes 1–14 were not rewritten.
- **Novel sync is still outstanding.** The last attempted sync stopped at `git pull --ff-only origin main` with SSH `Permission denied (publickey)`; it reported that local changes were restored and that no commit or push was attempted. The Story Bible AI rule and manuscript changes remain local. The earlier sync review listed `story_bible.json` and Chapter 1 scene files 11–14; Scene 15 was saved afterward and should also be checked in the next sync review. Do not reset, hard-pull, discard, or overwrite these local changes.

### Possible progressive scrubber failure

- Keep the first failure as already written: Delta-Seven loses CO₂ removal efficiency, the Computer reports the trend, and Daniel and Ryan confirm that CO₂ is rising even though the other units remain active.
- A possible later escalation is that **another scrubber begins to fail**, followed perhaps by further losses over time. The failures need not happen all at once. A progressive sequence gives the crew time to investigate, attempt repairs, adjust operations, and discover whether the problem is isolated or broader.
- Do not decide now how many units fail, how far apart the failures occur, whether they share a cause, or what ultimately fixes them. Avoid making every new failure a predictable beat; let the evidence and the crew's actions shape the sequence.

### Possible outpost compartmentalization

- If some parts of the facility can no longer be reliably supported, the crew may eventually isolate affected sections and move occupants into sectors whose environmental systems remain functional.
- This could involve sealing doors or bulkheads, controlling ventilation between zones, reducing the volume of occupied space, and concentrating functioning life-support capacity where people are sheltering.
- The facility's exact environmental-zone layout, isolation capabilities, and practical limits have not been designed yet. Do not assume every corridor or room can be independently sealed until the setting supports it.

### Possible second Mars base and evacuation

- A second human outpost on Mars, located a considerable distance away, is one possible part of the wider setting. It could provide technical assistance and potentially receive evacuees, but its exact location, distance, transport links, spare capacity, and own resource limits are all undecided.
- One possible emergency measure is transferring **about 30 of the original outpost's roughly 50 occupants** to the other base, leaving approximately 20 at the original facility. With a comparable mix of people and activity, reducing the population from 50 to 20 would reduce the crew's CO₂ production by roughly 60 percent. That does not instantly remove CO₂ already accumulated in the atmosphere, and the actual benefit depends on who remains, activity levels, occupied volume, ventilation, and the condition of the remaining scrubbers.
- The receiving base would need sufficient habitable space, air and water capacity, food, medical support, and staffing to take the additional people. The transport method and number of trips remain open questions; do not treat the transfer as simple or immediate.
- The author has established for this planning concept that **the six central characters are heads of their respective departments**, with Elena also serving as overall outpost commander. The six would have to help decide which personnel are essential to keep the original outpost operating and who can transfer. Departmental recommendations should consider minimum staffing, specialist skills, life-support coverage, engineering, medical needs, communications, and the needs of both locations; Elena remains responsible for overall command and coordination.
- This creates potential character and leadership pressure: the six must make difficult personnel-allocation decisions, may disagree about staffing priorities, and may have to weigh volunteers or competing operational needs. These are possible dramatic beats, not predetermined conflicts. The choice is an operational survival decision, not a judgment about whose life matters more.

### Hydroponics as a limited buffer

- The hydroponics bay may buy additional time as a **supplemental biological buffer**, provided the plants are healthy and have adequate lighting, airflow, and operating conditions for net photosynthesis.
- Plants can absorb some CO₂ and release oxygen while photosynthesis exceeds respiration, but the bay is not a miracle cure and cannot replace mechanical CO₂ removal for the outpost indefinitely. Its contribution should be treated as limited and dependent on the actual growing area and conditions.
- The potential value is cumulative: fewer people at the original outpost lower CO₂ production, hydroponics may absorb a portion of the remaining CO₂, and functioning scrubbers continue doing the primary removal work. These measures can buy time; none guarantees safety by itself.

### Inbound supply ship and outside help

- Another possible story element is a cargo/supply ship already traveling from Earth to Mars when the crisis develops, perhaps around halfway between the planets. It could carry replacement components, consumables, and other supplies that may help restore the outpost.
- The ship's actual cargo manifest, compatibility of parts, remaining travel time, ability to alter its mission, and whether its crew can provide useful technical assistance are not decided. Mission Control may be able to check the manifest and coordinate with the ship, but Mars-Earth communication delay means no instant real-time rescue or conversation.
- This creates a possible survival objective: keep the original outpost viable long enough for the ship to arrive and for the needed equipment to be transferred and installed. The ship is a potential lifeline, not a guaranteed solution.

### Possible combined survival strategy

- If the story develops in this direction, several measures could work together: progressively investigate and respond to scrubber failures; isolate sections that cannot be safely supported; consolidate remaining occupants in functioning areas; transfer around 30 people to the distant Mars base if transport and receiving capacity allow; use hydroponics as a limited CO₂/oxygen buffer; and keep the original outpost operating until the inbound ship can deliver useful replacement equipment.
- Keep the engineering, staffing, transport, and timing details open until needed. The author has not fixed a failure count, evacuation date, base distance, ship arrival date, specific crew assignments, or final repair solution. Do not turn these brainstorming notes into mandatory events or add them to Story Bible Canon Rules without the author's later decision.


### Possible national ownership / international coordination (November 4, 2026)

- The author has clarified that the **original Mars outpost is US-owned / US-operated**. Elena is its overall commander, and the secure advisory in Chapter 2 is intended for the US Mission Control organization. The exact agency naming and institutional details can be settled later; do not invent a specific real-world organizational structure unnecessarily.
- A second, distant Mars outpost is being considered as **Japanese-operated**. This is a promising option, but the host country/operator is not yet a final locked decision.
- If the second base is Japanese-operated, treat it as an independent facility with its own commander, personnel, procedures, and life-support constraints. Emergency assistance and any transfer of approximately 30 people would require coordination and agreement between the two outpost commands; Elena cannot unilaterally assign people to the other country's facility.
- This adds a potential international-cooperation dimension to the survival arc. Keep the operational details realistic and respectful; do not rely on national stereotypes or assume the Japanese base automatically has spare capacity. Its ability to accept evacuees, transport arrangements, communications, and resource limits remain undecided.
- These are story-planning notes, not a new Story Bible Canon Rule. The current US ownership is an author clarification; the Japanese second base remains a candidate to revisit.


## Current checkpoint update: Author's Direction for Prepare Scene (November 4, 2026)

### New optional Author's Direction box

- The author approved a small Prepare Scene improvement: an **optional, multiline Author's direction** box placed immediately above the existing **What should it write?** prompt box.
- The label explains: **Leave blank to let Gemma choose what happens next.** The field is genuinely optional. When blank or whitespace-only, the scene preparation prompt receives no extra Author's Direction section and the existing Prepare Scene behavior remains unchanged, using the selected previous scene, story facts, canon, timeline, and general creative guidance.
- When the author enters direction, it is passed into `build_scene_preparation_prompt()` as a distinct, priority steering section. It is combined with the previous-scene context and Story Bible information; Gemma is asked to honor the author's intended event, focus, and outcome while shaping the scene naturally and preserving continuity, rather than substituting an unrelated idea.
- The direction box clears only after a non-empty scene suggestion has successfully been accepted into the existing prompt box. It is not cleared when the author cancels the replace confirmation, generation fails or is stopped, the model returns an empty suggestion, or the author changes either the prompt box or Author's Direction while preparation is running. In that last case, the generated suggestion is discarded and the author's edits are preserved.
- The existing two-part output is unchanged: **Scene direction** and **Natural endpoint**. No manuscript files, Story Bible data, novel state, or saved scenes were changed by this feature.
- Code changes on `redesign/simplified-writing-workflow`:
  - `builder/scene_preparation.py`: optional `author_direction` parameter and conditional priority section; blank direction adds nothing.
  - `minimal_writer.py`: optional three-line text box before the scene prompt, passes direction into preparation, protects edits made during generation, and clears the box only on successful preparation.
  - `tests/test_scene_preparation.py`: tests for direction included with priority, blank direction unchanged, successful use and clearing, cancellation preserving direction, and edits made during generation being kept.
- Relevant commits:
  - `010a8846140e41792b934cd9bb11c6fd835ac615` — prompt builder accepts optional author direction.
  - `4260c024437f7f8cd383e0d4545b1344b9438ba2` — Minimal Writer UI and successful-use behavior.
  - `c1994a9595e870ae43f1481ddca22aa56f5ed4e4` — positions Author's Direction above the generated scene prompt.
  - `fa66dffeab01e59d2edc2679b0cce031c3cf5d59` — adds regression tests; this is the application-code branch head at this update.
- **Verification:** GitHub Actions compile step passed. On commit `fa66dffeab01e59d2edc2679b0cce031c3cf5d59`, the Python pytest workflow reports **646 passed, 1 failed, 77 subtests passed**; the StoryBuilder unittest workflow reports **647 tests with 1 error**. Both failures are the previously known, unrelated Tkinter test-harness issue in `test_blank_name_does_not_save_or_close_the_editor`: its fake root is a plain object without the `.tk` attribute required by `messagebox.showerror`. The new Author's Direction tests passed; the workflow logs show no failures in the new feature tests. Do not claim that the full suite is green.
- **Local laptop status:** These commits are on the GitHub development branch and have **not** been pulled or tested on the author's laptop. The last reported local pre-pull test run used `.venv/bin/python -m pytest -q` and returned **631 passed, 3 failed, 77 subtests passed** (two stale exact-wording assertions plus the known Tkinter harness failure). The author also reported a pre-existing uncommitted local modification to `storybuilder.py`. Do not tell the author to reset, discard, hard-pull, or overwrite it. Do not pull the development branch until the local change is understood/preserved and the agreed test gate has been addressed.

### Novel / Computer AI sync verification (November 4, 2026)

- The author later reported that the novel's GitHub sync completed successfully. We fetched and inspected `story_bible.json` from `tony21675/The-Long-Way-Home` on `main`, confirming the Computer AI Canon Rule is present as one continuous rule and `Computer.json` is registered in the character-card list.
- We separately fetched `Computer.json` from the same branch and verified the card: name **Computer**, role **Central Outpost AI**, non-human facility system, natural feminine voice/personality, facility monitoring and diagnostics, entertainment/music, private personal logs, and help preparing messages to loved ones on Earth with sender approval before transmission.
- GitHub blob SHAs at verification: `story_bible.json` = `2127d1ad7effd976692ac198ca36434553ef1018`; `Computer.json` = `2ab71727291712fd9212d11b49694cd29d5a145a`. The remote tree also showed Chapter 1 Section 15 and Chapter 2 scene files. The author confirmed the novel sync succeeded. Keep novel-package sync separate from StoryBuilder application-code sync.
- The manuscript checkpoint from the current conversation: Chapter 1 ends at **Scene 15**, which the author saved. Chapter 2 is underway; the author confirmed saving the scene after correcting Elena's deadline from 0300 (night) to **the end of the following day shift**, consistent with the six being day crew. Preserve this correction. Do not rewrite accepted scenes.

### How to use Author's Direction

- Use it only when the author has specific steering for the next scene, such as a required event, character focus, interaction, or outcome. Keep instructions brief and let Prepare Scene combine them with continuity.
- When the author has no preference, leave the box empty. Gemma should then choose the next scene from the existing story context and general creative guidance. Do not prompt the author to fill it in every time or treat blank as a missing input.
- The field is temporary and clears after successful preparation, so one scene's steering does not carry into the next scene.

## End-of-session checkpoint: Chapter 2 downtime sequence and Author's Direction test (November 4, 2026)

### Resume point and scene progress

- Immediately before this session, the author had confirmed that **Chapter 2, Scene 6** was saved. Elena's report deadline was corrected to **the end of the following day shift**, not 0300, because the central crew are the day crew and would be asleep at 0300.
- The author then showed the Prepare Scene direction intended for the next scene: Daniel integrates the raw Delta-Seven scrubber data; Ryan discusses current stability parameters with Priya; Morgan briefly asks Daniel about a geological reading; Priya completes her initial monitoring summary.
- The phrase about metrics being within acceptable deviation ranges was potentially ambiguous. The author used the new **Author's Direction** field to clarify that Priya's summary covers **personnel health / monitoring only**. It must not suggest that the whole life-support system, scrubber performance, or CO₂ levels are within acceptable limits. Delta-Seven remains failed and CO₂ remains a concern.
- A subsequent prepared direction began from Priya having completed that personnel-monitoring summary and moved the crew into ordinary late-afternoon downtime. This is consistent with the intended continuity, but the author did not paste the directly steered scene's full generated prose into the chat. Therefore, do not claim that the first Author's Direction test definitively proved the model followed the added instruction while leaving every other element unchanged. The test was attempted; a full fidelity assessment remains open.

### Downtime and bottle-stacking sequence developed tonight

- The next prepared scene shifted the group into casual social time in the Mess Hall / communal staging area rather than keeping every moment inside operational briefings. The shared prose included Daniel's dry commentary, Zoe noticing an amusing detail, Ryan's exaggerated storytelling, and Morgan suggesting a low-stakes bottle-balancing challenge.
- The following prepared direction continued the bottle challenge: Morgan gathered standardized empty water bottles, Ryan enthusiastically arranged his stack, Zoe quietly assessed Daniel's technique, and Priya watched while making amused notes on her handheld slate.
- The generated prose built through several rounds of bottle stacking. While Ryan was boasting about his stack, Morgan picked up a small piece of crumpled packing paper and landed it cleanly in the designated recycling bin without breaking stride. The prose ended on the satisfying impact of the paper hitting the bin.
- The next prepared direction focused on the group's reaction. The generated follow-up showed Ryan stopping mid-boast and blinking, Daniel chuckling, Zoe acknowledging the throw with a small nod, and Priya looking up with a genuine smile. Morgan did not fish for praise; she casually returned to gathering bottles for her own stack.
- **Most recent shared prose / continuity anchor:** the paper toss has landed; Ryan is briefly speechless, Daniel and Zoe appreciate the shot, Priya smiles, and Morgan simply gets back to collecting bottles. The final image is the rhythmic clinking of bottles replacing the brief hush.
- The author was advised to save that final follow-up as written. However, the author did not explicitly confirm the save in chat, and no newer Chapter 2 scene files were visible in the remote novel repository during this handoff update. Treat the local save status and exact new section number as **unverified** until checked in Writer. Do not claim these later scenes have synced to GitHub.
- This sequence is a useful example of allowing the story to breathe: low-stakes competition, casual interaction, and a small skillful moment can carry a scene without inventing a new crisis or forcing a major plot development. Do not over-review or rewrite it for minor differences from the planned endpoint.

### Author's Direction: practical use learned tonight

- The optional field is useful for **small, specific steering**, not just major plot events. For example, when a character seems stressed or has been working too long, the author may suggest that the next scene let them decompress with coffee, music, a video game, a warm shower, or another ordinary personal routine.
- Keep these directions light: suggest the character moment or desired beat and allow Gemma to work it naturally into the next scene. Do not prescribe the entire scene or make the character's stress into a dramatic crisis unless the author intends that.
- These examples are possible character actions, not new Story Bible rules or fixed routines. There is no need to use Author's Direction every time; leave it blank whenever the author is happy to let Gemma choose what happens next.
- The field is temporary and applies to the next scene preparation only. It does not change saved scenes, canon, the Story Bible, or the overall premise.

### Repository verification and next-session handling

- During this handoff update, the remote novel repository `tony21675/The-Long-Way-Home`, branch `main`, was inspected. Its latest commit was `c4e9c34344ac66f94f11f60795897be84dbfb7c8` (2026-11-04 13:23:27 UTC), and the remote tree contained Chapter 2 Sections 1–6 only. No later Chapter 2 section files were present at the time of inspection.
- That remote commit added Chapter 2 Sections 4–6. It therefore confirms the previous Scene 6 checkpoint is backed up remotely, but it does **not** verify tonight's newer downtime/bottle-challenge material. The author may have saved it locally after that sync; this was not independently checked.
- At the next session, first check the Writer scene list / selected novel to establish whether tonight's latest follow-up was saved and what section number it received. If it is saved, continue directly from Morgan returning to collect bottles after the successful paper toss. If it is not saved, recover the draft from the Writer only as needed; do not reconstruct or rewrite accepted prose unnecessarily.
- Novel-package sync and StoryBuilder application-code sync remain separate. Do not pull, reset, or overwrite local StoryBuilder changes as part of manuscript recovery.
- The author successfully used the Author's Direction workflow during this session, so the field was available in the working Writer session. The exact local code revision and any new local test results were not independently verified here. The previous CI and local-test caveats in the app-status section remain in force unless later verified.

### Author clarification on resume point (November 4, 2026, evening)

- The author has now confirmed that **Chapter 2, Scene 10 is the last saved scene locally**. This supersedes the earlier uncertainty in the end-of-session checkpoint about whether tonight's follow-up had been saved.
- Resume with **Chapter 2, Scene 11**. The latest accepted scene ends after Morgan's successful paper toss: Ryan is briefly speechless, Daniel and Zoe appreciate the shot, Priya smiles, and Morgan casually returns to collecting empty bottles for her own stack.
- This is a local save confirmation from the author. The remote novel repository was last inspected before this clarification and contained Chapter 2 Sections 1–6 only; no post-Scene-6 sync has been verified. Do not imply Scene 7–10 are backed up remotely until the novel repo is checked again after sync.

## Minimal Writer: Rewrite Scene action (November 4, 2026)

### Purpose and workflow

- The author identified a workflow gap: when generated prose is too short or misses an important beat, pressing **Prepare Scene** is not the right way to ask for another attempt. Prepare Scene plans the next scene and advances its destination. It does not rewrite the current generated prose.
- Added a separate **Rewrite Scene** button next to **Write** in Minimal Writer.
- **Prepare Scene** remains the planning action for the next scene. **Write** creates the first prose draft from the existing scene prompt. **Rewrite Scene** creates a fresh replacement attempt for the same scene using the existing prompt plus any additional instruction in Author's Direction.
- Rewrite Scene requires a loaded model, non-empty text in **What should it write?**, and an existing visible Output draft. It asks for confirmation before starting. The prompt shown in the scene prompt box remains unchanged.
- The generation-only prompt is built from the original scene prompt plus an **ADDITIONAL AUTHOR'S DIRECTION FOR THIS REWRITE** section. The additional text is treated as a priority clarification for the same scene. Gemma is instructed to preserve the existing location, characters, intended events, and natural endpoint except where the new direction specifically refines them, and to return a complete replacement scene rather than planning or advancing to another scene.
- If Author's Direction is blank, Rewrite Scene still makes a fresh attempt from the existing scene prompt alone.
- Rewrite Scene does **not** change the selected chapter/scene, advance the scene number, modify the scene prompt box, or save/overwrite any manuscript file. The author remains in control of saving the replacement.
- Safety behavior:
  - Cancelling the confirmation leaves the existing draft and instructions untouched and sends nothing to the model.
  - If generation fails, the existing draft is restored by the existing error-recovery path.
  - If the author stops a rewrite, the previous draft is restored even if some replacement tokens had already streamed; a partial rewrite is not left in place.
  - On successful rewrite, the new prose replaces the visible Output draft. Author's Direction is cleared only if it is unchanged from the instruction used to start the rewrite. Any newer edits made while generation was running are preserved.
  - The original prompt in **What should it write?** is never consumed or replaced by this action.
- The confirmation explicitly states that only the visible Output draft will be replaced and that saved manuscript files remain untouched.

### Code and tests

- `minimal_writer.py`:
  - Added `build_rewrite_scene_prompt()` to combine the existing prompt and optional extra guidance without modifying the source prompt.
  - Added the Rewrite Scene UI button and `rewrite_current_scene()` action.
  - Added the rewrite mode status label, success-only instruction clearing, and stop behavior that restores the previous draft.
  - The stop handler uses a safe default generation mode so existing test harnesses and legacy callers that do not set the mode retain their prior behavior.
- `tests/test_minimal_writer.py` adds coverage for:
  - appending the additional direction while preserving the original prompt;
  - blank/whitespace-only guidance leaving the prompt unchanged;
  - sending the current prompt plus Author's Direction under rewrite mode;
  - cancelling without starting generation or altering the draft;
  - successful replacement and clearing unchanged guidance;
  - preserving guidance edited while generation is in progress;
  - restoring the prior draft when a rewrite is stopped after partial output.
- Relevant commits:
  - `2fdea0807e3f84cafe59d581bf0382ac56c73069` — main Rewrite Scene implementation.
  - `2cb7f6ad7f79e5ba527c5a5e24f662ebe253c0a8` — rewrite regression tests.
  - `688b0e6f7b94bb29ec79c3fb741996a5cd15efbc` — fixes newline literals in tests.
  - `dd1ea170ff9025feab48906948e78d3717819c10` — compatibility guard in the stopped-generation handler; latest application-code commit at this checkpoint.
- **GitHub Actions verification on `dd1ea170ff9025feab48906948e78d3717819c10`:**
  - Python pytest: **653 passed, 1 failed, 77 subtests passed**. The sole failure is the previously known unrelated Tkinter test harness issue, `test_blank_name_does_not_save_or_close_the_editor`, where the fake root is a plain object without the `.tk` attribute required by `messagebox.showerror`. All new Rewrite Scene tests passed.
  - StoryBuilder compile/unit workflow: `compileall` passed; 654 unit tests ran, with the same single unrelated Tkinter harness error.
  - Runs: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41969292039) and [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41969292041).
- **Local laptop status:** This implementation was made on GitHub branch `redesign/simplified-writing-workflow`. The current local laptop revision was not inspected or changed during this task, and no local tests were run. Earlier handoff notes record an uncommitted local change to `storybuilder.py` and a failing pre-pull test run. Do not tell the author to hard-pull, reset, overwrite, or discard local work. Before using the new button locally, first inspect local `git status` and reconcile/preserve the existing local change, then use the agreed test gate. Do not claim the new button is already installed on the laptop until verified.

### Local installation confirmation: Rewrite Scene (November 4, 2026, evening)

- The author safely fetched and inspected the local StoryBuilder repository before pulling. Local branch was `redesign/simplified-writing-workflow`; the only local working-tree change was `M storybuilder.py`.
- `git diff -- storybuilder.py` confirmed this was **only a file-mode change** from `100644` to `100755`; no source-code lines were modified. The executable permission was intentionally preserved.
- After fetching, the branch was six commits behind `origin/redesign/simplified-writing-workflow`. The incoming file list was limited to `CHAT_HANDOFF_LATEST.md`, `minimal_writer.py`, and `tests/test_minimal_writer.py`.
- The pre-pull full local suite reported **646 passed, 1 failed, 77 subtests passed**. The one failure was the known Tkinter harness case `test_blank_name_does_not_save_or_close_the_editor`; it was deselected for the follow-up test gate, which passed: **646 passed, 1 deselected, 77 subtests passed**.
- The author then ran `git pull --ff-only origin redesign/simplified-writing-workflow`; it completed as a successful fast-forward from `2f2548b` to `7732063`, bringing down the Rewrite Scene implementation, tests, and handoff update.
- Post-pull `git status --short --branch` showed the local branch aligned with `origin/redesign/simplified-writing-workflow`, with only the original `M storybuilder.py` mode change still present. The local change was preserved; no reset, stash, or discard was used.
- Post-pull full local pytest: **653 passed, 1 failed, 77 subtests passed**. The sole failure is again `test_blank_name_does_not_save_or_close_the_editor`, where the test's fake Tk root has no `.tk` attribute when `messagebox.showerror` is called. The Rewrite Scene tests are included among the passing tests.
- **Status:** Rewrite Scene code and its regression tests are now pulled onto the author's laptop. The known Tkinter harness failure remains unrelated and unchanged. The original executable-permission modification to `storybuilder.py` remains local and must not be discarded automatically.


## Story Bible location allowlist for scene planning and writing (November 5, 2026)

### Author-approved behavior

- The author approved a generic location allowlist sourced from each novel's own Story Bible. It must not contain novel-specific names or hard-coded assumptions.
- **A location name alone is sufficient.** For example, a Story Bible entry named `Supply Closet` is a fully approved location even when its description, type, geography, climate, and notable details are all blank.
- The author is comfortable adding more location entries over time. Separate rooms/areas need their own entries; listing a larger facility does not automatically authorize the rooms inside it.
- The intent is to prevent the model from inventing rooms, lounges, offices, corridors, work areas, buildings, facilities, or other places that are not registered in the selected novel's Story Bible.

### Implementation

- Added a shared helper in `builder/continuity_context.py` to return usable saved location names and build a name-only allowlist instruction.
- **Prepare Scene** now receives the complete list of names from the selected novel's Story Bible on every scene-planning request. The instruction treats it as the complete approved list and tells the model not to invent, rename, infer, or subdivide locations. A name-only entry counts as valid without any descriptive details.
- The actual Writer prompt used for Write, Rewrite Scene, and Continue also receives the complete allowlist. Descriptive location details remain selective: they are attached only when the corresponding saved location is explicitly named in the scene prompt/supporting text.
- If no locations are registered, the prompt explicitly says not to invent a place and to leave a needed new location unspecified for the author to add.
- This change is generic across novels. It does not add, change, or populate any Story Bible locations and does not modify manuscript scenes or saved canon.

### Tests

- Added tests for name-only location entries, ignored unsupported/blank entries, an empty location list, inclusion of all names in Prepare Scene, and inclusion of the same allowlist in actual Writer prompts while keeping detailed references selective.
- The first GitHub Actions run (`41986830787`) ran 658 tests and identified one outdated assertion in `test_prompt_is_unchanged_when_no_location_name_matches`: the new allowlist is intentionally added even when the current scene does not name a location. The assertion was updated to verify that all approved names appear while unrelated location descriptions remain excluded.
- Corrected GitHub Actions verification on the follow-up commit completed:
  - Python pytest: **657 passed, 1 failed, 77 subtests passed**. The sole failure is the previously known unrelated Tkinter harness test `test_blank_name_does_not_save_or_close_the_editor`, where the fake root lacks `.tk`. All new location-allowlist tests passed. Run: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41986990787).
  - StoryBuilder compile/unit workflow: `compileall` passed; 658 unit tests ran with the same one known Tkinter harness error and no location-allowlist failures. Run: [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41986990814).
- Do not treat the known Tkinter harness failure as introduced by this location change; it has appeared in previous runs before these edits.



### Local installation confirmation: Story Bible location allowlist (November 5, 2026)

- The author fetched and inspected the local StoryBuilder repository before pulling. Local branch was `redesign/simplified-writing-workflow`; the only working-tree change was `M storybuilder.py`.
- `git diff -- storybuilder.py` confirmed the local change is only the executable file-mode change from `100644` to `100755`, with no source-code edits.
- `git fetch origin` showed the branch advanced from `7732063` to `508d3b1`.
- The author inspected the incoming file list. It contained exactly the expected Story Bible location allowlist implementation, tests, and handoff files; `storybuilder.py` was not incoming.
- The author then ran `git pull --ff-only origin redesign/simplified-writing-workflow`. It completed as a fast-forward from `7732063` to `508d3b1`, updating eight files with no conflicts.
- Post-pull `git status --short --branch` confirmed the local branch aligned with `origin/redesign/simplified-writing-workflow`; the only remaining working-tree change was the original `M storybuilder.py` mode modification. It was preserved.
- Local test gate: `.venv/bin/python -m pytest -q -k "not test_blank_name_does_not_save_or_close_the_editor"` passed with **657 passed, 1 deselected, 77 subtests passed in 2.42s**. The deselected test is the previously documented unrelated Tkinter harness issue.
- **Status:** The Story Bible location allowlist feature is installed on the author's laptop and passes the agreed local test gate. The next practical step is a real Writer test: use a novel with only a few saved locations and verify that Prepare Scene and Write/Rewrite stay within that saved list. The author may add minimal location entries such as `Supply Closet` with no descriptive fields; names alone are sufficient.


### Author clarification: connective hallways and corridors (November 5, 2026)

- The author clarified that ordinary hallways, corridors, and connecting passageways are assumed parts of a structure and do not need individual Story Bible entries.
- They may be used briefly and generically for direct movement between approved rooms/locations. They are **not** to become scene destinations or places where characters gather, work, hold meetings, or conduct sustained activity.
- Updated the shared location allowlist instruction for both Prepare Scene and prose generation to include this narrow transit exception. All actual rooms/areas and scene destinations still need their own Story Bible entries.
- Added regression assertions for this distinction, including the no-approved-locations case.
- GitHub Actions verification on the clarified prompt:
  - Python pytest: **657 passed, 1 failed, 77 subtests passed**. The only failure is the same pre-existing Tkinter harness test `test_blank_name_does_not_save_or_close_the_editor`, where the fake root lacks `.tk`. All hallway/corridor exception tests passed. Run: [Python tests](https://github.com/tony21675/StoryBuilder/actions/runs/41992110894).
  - StoryBuilder compile/unit workflow: `compileall` passed; 658 unit tests ran with the same one known Tkinter harness error. No location-rule test failed. Run: [StoryBuilder tests](https://github.com/tony21675/StoryBuilder/actions/runs/41992113538).
- The previous laptop installation checkpoint remains accurate for the prior version; this hallway/corridor clarification still needs to be pulled and tested separately.


## Writer continuity context and one-scene prompt capture (November 5, 2026)

### What was found

- The author reported a sharp drop in scene-to-scene continuity while writing *The Long Way Home*, especially after the charades scene.
- Code inspection at the laptop's previously installed revision confirmed that **Prepare Scene** included up to the last 6,000 characters of the previous saved scene when planning the next scene.
- After planning, Prepare Scene intentionally clears the persistent llama.cpp conversation history. That behavior remains unchanged.
- The actual prose **Write** and **Rewrite Scene** prompts did not include the preceding saved manuscript scene. They included the prepared direction plus Story Bible-derived creative direction, canon, pacing, timeline, character, and location context. Thus the prose model could be told that a game had happened without being shown which game actions, performances, objects, and dialogue had actually occurred. This is a concrete continuity-context gap; it is not proof that it explains every quality change.
- The Writer Engine already contained prompt-trace hooks and builder/prompt_trace.py already implemented a one-scene local capture, but the Minimal Writer did not attach a trace to the active model session. The capture mechanism was therefore not actually being used by the Writer app.

### Changes made on the existing branch

- Added builder/writer_continuity.py. For the selected target chapter/scene, it finds the most recent accepted saved scene with earlier coordinates, including across chapter boundaries. It reads the accepted ODT/TXT scene through the existing scene browser (ODT is preferred where both formats exist), limits the included prose to 6,000 characters, and appends it as explicitly labeled continuity-only context.
- **Write** and **Rewrite Scene** now include that immediately preceding saved scene. The current target scene and any future scenes are excluded. Continue behavior was not changed.
- Connected the existing prompt-trace helper to the actual Writer generation path. A one-generation capture records the exact prompt text submitted to llama.cpp, the model response, active model/session/runtime settings, current-state snapshot, and scene/author-direction metadata. It also records the Writer's configured system prompt (currently blank).
- The trace is local only and is not uploaded or synced. Default file: ~/.local/share/storybuilder/prompt_trace.json. Each completed capture overwrites the previous one-scene trace rather than creating an accumulating log. When a generation completes, the Writer status line reports the trace path.
- Capture obeys the existing local preference switch. If no preference file exists, capture defaults to enabled; an explicit false setting disables it. Preference path: $XDG_CONFIG_HOME/storybuilder/prompt_trace_enabled.json, or ~/.config/storybuilder/prompt_trace_enabled.json when XDG_CONFIG_HOME is unset.
- No model file, sampling setting, system prompt, story prose, Story Bible, or novel package was changed. All code changes are on the existing redesign/simplified-writing-workflow branch; no new branch was created.

### Tests and verification

- Added tests/test_writer_continuity.py for immediately preceding scene selection, chapter-boundary lookup, exclusion of current/future scenes, and bounded context.
- Added Minimal Writer tests confirming Write includes the preceding saved scene and one-scene tracing is armed, finalized locally, and detached.
- Added a Writer Engine test confirming an already-running llama-cli session is recorded when the trace is attached.
- GitHub Actions at commit c90638eff5f8aa17651d88b3a7b1c47cd22c2043:
  - Python pytest: **664 passed, 1 failed, 77 subtests passed**. The only failure is the previously known unrelated Tkinter harness failure in test_blank_name_does_not_save_or_close_the_editor (fake root lacks .tk). All new tests passed. Run: https://github.com/tony21675/StoryBuilder/actions/runs/42026688547
  - StoryBuilder workflow: shell syntax and compileall passed; 665 unit tests ran with the same single known Tkinter harness error. Run: https://github.com/tony21675/StoryBuilder/actions/runs/42026688638
- **Laptop status:** This work has not yet been pulled or tested on the author's laptop. The last confirmed local change remains the intentional storybuilder.py executable-mode change (100644 to 100755). Preserve it. Before pulling, inspect git status --short --branch and git diff -- storybuilder.py; then fetch and inspect incoming paths before using git pull --ff-only origin redesign/simplified-writing-workflow. Run the agreed test gate afterward:
  .venv/bin/python -m pytest -q -k "not test_blank_name_does_not_save_or_close_the_editor".
- After pull, the immediate diagnostic test should be one naturally prepared scene. Then inspect ~/.local/share/storybuilder/prompt_trace.json to confirm the exact previous-scene reference and the final text sent to the model. Do not change model settings until the trace has been reviewed.

## Automatic private prompt-trace upload (November 5, 2026)

- The author requested that each Writer trace be uploaded automatically to GitHub so it can be reviewed without manually attaching the local JSON file.
- The private destination already exists: `tony21675/StoryBuilder-Traces`, with the existing single file `prompt_trace.json`. The public StoryBuilder source repository is not used for manuscript-bearing traces.
- `builder/prompt_trace_sync.py` already implements the upload safely:
  - Uses an explicitly configured `STORYBUILDER_TRACE_GITHUB_TOKEN`, `GH_TOKEN`, or `GITHUB_TOKEN`; otherwise it reads the signed-in token from GitHub CLI (`gh auth token`).
  - Defaults to `<authenticated GitHub username>/StoryBuilder-Traces` unless `STORYBUILDER_TRACE_GITHUB_REPO` is configured.
  - Verifies through GitHub's API that the destination repository is private before uploading.
  - Replaces the same `prompt_trace.json` file on the repository's default branch. The new root commit intentionally does not retain prior branch history. This is not a secure-erasure guarantee for GitHub's underlying object storage.
  - Refuses to upload if the destination contains unrelated files.
- Wired `minimal_writer.py` to call `upload_prompt_trace()` after each successful local trace save, for completed, interrupted, and failed generation captures. The upload runs in the existing generation worker thread. A GitHub upload failure does not fail or discard the local trace or generated prose.
- On successful writing, the status message now distinguishes the local trace file from its private GitHub upload. On upload failure, it reports the problem while confirming the local trace remains saved.
- Added Minimal Writer tests confirming upload is attempted with the saved trace path and that upload failure preserves the local trace.
- No manuscript, Story Bible, model settings, or public repository trace content was changed.
- **Laptop installation:** The automatic upload wiring is committed remotely but must still be pulled onto the laptop. The existing local `storybuilder.py` executable-permission change (mode-only) must be preserved during that update. After pulling, run the agreed test gate, then verify `gh auth status` (or configure a token environment variable) before the next Writer generation.


## Saved-scene ending-state updates (November 5, 2026)

- The author confirmed that *The Long Way Home* is currently at **Day 2, nighttime**. The local `current_state.json` was still at its original `Day 1, 16:00`, Chapter 1, Scene 1, `story_start` record. That stale time and opening status were being sent into Write / Prepare Scene prompts and made the novel appear to be at its beginning.
- Added `builder/scene_state_update.py` and connected it to Minimal Writer's **Save New Scene** action.
- When an ODT scene is successfully saved, Writer first records the saved chapter/scene and marks that scene complete. It then uses the already-loaded model for one focused ending-state pass over the accepted scene's final paragraphs. The pass may update only `current_situation`, `location`, `physical_state`, and `time_of_day`. Time is carried forward unless the accepted prose supports a change; no exact hour is invented from a broad night/evening description.
- The state task clears the model conversation before and after its JSON response so that it cannot contaminate the next prose-generation turn. It does not reload model weights.
- **Explicitly excluded:** no old-to-new scene comparison, no `review_state_proposal`, no `review_chapter_flow`, no separate continuity checker, and no prose validator. The state proposal receives ordinary structural validation before it is written so malformed data cannot damage `current_state.json`.
- State writes are atomic. If analysis fails, the manuscript scene remains saved and the completed chapter/scene pointer is still recorded; existing time and other state details are preserved. The Writer status line reports the failure. If no model is loaded, the scene pointer is recorded but the ending-state details are not analyzed.
- This is deliberately a focused end-state update, not the full legacy clue/knowledge audit. It updates story time, immediate situation, and supported ending location/physical details only.
- Added `tests/test_scene_state_update.py` for story-time preservation, scene markers, prompt construction, patch filtering/validation, atomic state-file writes, and the post-save update/failure paths.
- **One-time local correction still required before the next scene prompt:** update the author's local `current_state.json` baseline to Chapter 2, Scene 19, `in_progress`, `scene_completed: true`, `chapter_completed: false`, and `time_of_day: "Day 2, nighttime at the Mars research outpost."` This uses the author's explicit timeline correction; do not infer a more precise hour. The existing scene 19 remains the latest accepted manuscript scene until Scene 20 is saved.
- The update is committed on the existing `redesign/simplified-writing-workflow` branch. Local laptop pull and test verification are still pending. Preserve the laptop's mode-only `storybuilder.py` change during installation.


### Verification

- Source changes are on `redesign/simplified-writing-workflow`, currently at `c2321f7d65bcc75b3d10e67ccf2479d365b35fb3`.
- Python pytest: **672 passed, 1 failed, 77 subtests passed**. The only failure remains the known unrelated Tkinter test-harness issue in `test_blank_name_does_not_save_or_close_the_editor` (fake root has no `.tk`). All seven new saved-scene state tests passed. Run: https://github.com/tony21675/StoryBuilder/actions/runs/42042893995.
- StoryBuilder workflow: launcher syntax and `compileall` passed; the unit suite ran 673 tests with only the same known Tkinter harness error. Run: https://github.com/tony21675/StoryBuilder/actions/runs/42042894143.

## Outstanding objective continuity in scene planning and prose prompts (November 5, 2026)

- The author identified a continuity loss: Daniel's report to Elena remained undelivered at the end of Chapter 2, Scene 19 and was recorded in `current_state.json` under `active_objectives.Daniel`, but the Writer prompts did not consistently receive outstanding objectives.
- Added a shared prompt formatter in `builder/story_timeline.py` for the saved current situation and non-empty per-character active objectives. It labels objectives as unresolved continuity, says not to assume off-page completion or silently drop an objective because a scene omits it, and also says not to force every objective into every scene. It prohibits inventing excuses or outcomes.
- Prepare Scene now includes this context when its existing current-state position check accepts the saved state. Actual Write, Rewrite Scene, and Continue prompts now include the same context through the shared Writer-context path.
- No old-to-new checker, separate scene reviewer, additional model pass, model setting change, or manuscript/state mutation was added. The change only supplies already-saved state to prompts.
- Regression coverage verifies both Prepare Scene and the final Write prompt include Daniel's report obligation and the unresolved-continuity instruction.
- **Installation status:** Changes are committed on the existing `redesign/simplified-writing-workflow` branch. The author's local branch must still fetch, inspect incoming filenames, pull fast-forward, and run the agreed local pytest gate. Preserve the intentional `storybuilder.py` executable-mode-only change.


## First prompt reduction pass (November 5, 2026)

- The author approved trimming prompt bloat after a recent Writer trace showed a 17,680-character prompt for a straightforward scene.
- Reduced shared scene-craft guidance to a short paragraph about natural scenes, character development, varied participation, concrete detail, and continuity.
- Separated media/device boundaries from general craft guidance. That reminder is now included only when the scene direction or selected previous scene actually mentions media/devices.
- Removed opening-pacing guidance from ordinary Write, Rewrite, and Continue prompts. Prepare Scene receives it only for Chapter 1, Scene 1.
- Shortened the running timeline reminder to the saved time plus a brief instruction to move forward without inventing an exact hour.
- Shortened Prepare Scene's repeated instructions while preserving its two-part editable output: Scene direction and Natural endpoint.
- Kept the substantive story context intact: the author's direction, immediately preceding saved scene, current situation, unresolved objectives, canon rules, approved location list, relevant character references, and creative direction.
- No model settings, manuscript prose, novel-package data, or current_state.json values were changed.
- Added/updated tests for conditional media context, shorter craft/timeline prompts, opening-only pacing context, and the revised Prepare Scene format.
- **Verification:** GitHub Actions for the latest source/test commit were still running when this handoff update was prepared. Record final results after they complete; do not treat earlier intermediate failures as the result for the latest commit.
- **Laptop installation:** Not yet pulled. Before installation, inspect the local branch and preserve the known mode-only storybuilder.py change (100644 to 100755). Run the agreed local test gate after a fast-forward pull.
