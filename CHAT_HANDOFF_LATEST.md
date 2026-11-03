# StoryBuilder handoff, current checkpoint

Date: November 3, 2026

## Project and workflow

- StoryBuilder: ~/Documents/StoryBuilder, GitHub tony21675/StoryBuilder.
- Active development branch: redesign/simplified-writing-workflow.
- Start Minimal Writer: cd ~/Documents/StoryBuilder && ./start.sh. It syncs the active branch and launches minimal_writer.py.
- Start Story Bible: cd ~/Documents/StoryBuilder && bash start_story_bible.sh.
- Novel packages live under ~/Documents/MyNovel/*.
- Use python3, never python, in Linux terminal commands.
- Keep app work incremental and tested. Discuss app or novel changes before making them; the author-approved work and handoff-only updates are exceptions.
- Do not change manuscript prose, accepted drafts, novel state, or package data without explicit permission. Preserve backups.
- Avoid giant rule sets, rigid prose constraints, and over-prescriptive writing behavior. The author prefers natural character and story development.

## Current app state

- Story Bible manages novel setup and reference information: title, premise, setting, creative direction, audience/content level, Canon Rules, Character Cards, and locations. Character Cards are editable in plain English; only name is required. Canon Rules are stored in the existing story_bible.json canon_rules array.
- Minimal Writer supports local model loading, Write, Continue, New Session, Prepare Scene, text/ODT editing, Save Draft, Save Draft As, Save New Scene, scene browsing, and selected-passage revision with preview/accept.
- Save New Scene writes directly to the selected novel's correct chapter path and refuses to overwrite existing ODT/TXT scenes.
- No automatic manuscript or story-state mutation should be introduced without author approval.

## Canon Rules prompt integration (November 3, 2026)

- Fixed the missing connection: the Story Bible already saved canon_rules, but Prepare Scene and Minimal Writer Write / Continue previously omitted those rules from model prompts.
- Added builder/canon_rules.py; it formats nonblank saved rules as a compact CANON RULES prompt section.
- Integrated it in builder/scene_preparation.py and MinimalWriterApp._prepare_location_context in minimal_writer.py.
- Added tests/test_canon_rules.py and updated tests/test_scene_preparation.py / tests/test_minimal_writer.py. Both prompt paths are covered by passing tests.
- This is generic across novels; no schema or novel package was changed by the app-side Canon Rules integration.

## Story timeline and Prepare Scene continuity (November 3, 2026)

- The author approved the timeline anchor Day 1 at 16:00 (4:00 PM), late afternoon, Mars outpost local time for The Long Way Home.
- Updated The Long Way Home's existing story_bible.json Setting with a short Story timeline note establishing that starting point and natural forward movement without a rigid schedule. Novel GitHub commit: 7e4fe35370471c58ea09d04509a77841a3532e53.
- Updated its existing current_state.json time_of_day field to Day 1, 16:00 (4:00 PM), late afternoon at the Mars research outpost. Novel GitHub commit: 95cfb81a809366d481f75f5cbe80120fe72c8146.
- No manuscript scene, character card, or other novel file was changed.
- Added builder/story_timeline.py to format a saved in-story time as a prompt anchor. Prepare Scene and actual Write / Continue prompts now receive it.
- Prepare Scene now reads up to 6,000 characters from the selected previous scene (previous limit: 2,200) to preserve more of the ongoing activity and its context.
- Improved Prepare Scene's instructions to continue directly from the previous scene, avoid restarting completed activities or jumping to unrelated tasks, propose one coherent scene direction rather than a menu of alternatives, and avoid manufacturing a mystery/anomaly solely as a hook. This remains flexible guidance, not a fixed outline.
- Updated the existing state-manager prompts so the separate state-update workflow treats time_of_day as a running clock, preserves the last established time, advances the day only when a new day/overnight transition is established, and avoids inventing exact clock times.
- Important workflow distinction: Minimal Writer currently includes the saved time and previous-scene context in prompts, but does not automatically rewrite current_state.json when Save New Scene is clicked. The fixed starting anchor is therefore carried forward as a reference, with elapsed time inferred from the previous scene. The separate state-update workflow can save an updated time when used. Do not claim that Minimal Writer automatically advances/saves the clock.
- Tests added/updated: tests/test_story_timeline.py, tests/test_scene_preparation.py, tests/test_minimal_writer.py, and tests/test_state_manager_validation.py.
- Latest code checkpoint: 08b43c01d8cc54bde6044dcaab116e091b8cc545. Python CI: 627 passed, 1 failed, 77 subtests passed. StoryBuilder unittest CI: 628 tests run, 1 error. Both have only the same pre-existing unrelated test_blank_name_does_not_save_or_close_the_editor Tk harness issue: a fake root lacks .tk. All new timeline, scene-continuity, writer-context, and state-clock tests passed. Runs: https://github.com/tony21675/StoryBuilder/actions/runs/41603324940 and https://github.com/tony21675/StoryBuilder/actions/runs/41603324813.
- Live test still required: pull the StoryBuilder branch, sync the selected novel package from GitHub in Story Bible, then reopen Minimal Writer and prepare Scene 4. The app branch and novel repository are separate syncs.

## Shared scene-craft guidance (November 3, 2026)

- The author approved a small, generic writing-guidance improvement after reviewing the opening scenes of The Long Way Home.
- Added builder/story_craft.py with one compact, reusable prompt section: let scenes feel lived-in as well as purposeful; use natural variety in group size and dialogue; allow ordinary moments, character interaction, pauses, and distinct voices; avoid constant jokes, scripted turn-taking, overly polished banter, unnecessary technical exposition, and explanatory speeches.
- Integrated the same guidance into Prepare Scene and Minimal Writer's shared Write / Continue context builder. It is broad guidance, not a checklist, and does not change Story Bible storage or add a new UI setting.
- No manuscript prose, current_state.json, character cards, or novel-package files were changed.
- The guidance deliberately contains no Mars-specific food assumptions. For The Long Way Home, shelf-stable protein ingredients or nutrient paste can be part of the pantry, while future food choices can also include suitable protein crops or other supplies. Do not make paste the only possible protein source or turn food logistics into a forced plot point.
- Added tests/test_story_craft.py to check the guidance itself and its delivery to both Prepare Scene and Write / Continue. Confirm test results before treating the change as validated.

## Current novel: The Long Way Home

- Local package: ~/Documents/MyNovel/The-Long-Way-Home. GitHub tony21675/The-Long-Way-Home, branch main.
- Premise: Six young, unmarried crew members share life and work at a Mars research outpost. Far from Earth, they build routines, friendships, rivalries, and a sense of home. An unexpected accident eventually threatens the outpost and their survival; the exact failure and repair solution are not predetermined.
- Setting: crewed Mars research outpost in the near future, reasonably credible technology and environment. Story starts Day 1 at 16:00, late afternoon, Mars outpost local time.
- Creative direction: Science Fiction; Humorous, Serious, and Tense; Adult audience; explicit adult content enabled.
- Character Cards are authoritative for the six crew: Daniel Okafor (male, straight), Elena Vasquez (female, straight), Morgan Reed (female, bisexual), Priya Shah (female, straight), Ryan Mercer (male, straight), and Zoe Bennett (female, bisexual). Preserve separate gender and sexual-orientation fields and the traits already saved in each card.
- Canon Rule Accident Timing: the life-support accident is a later major turning point. Early chapters should establish the crew's everyday lives, personalities, friendships, and relationships. Do not repeatedly add ominous hints, unexplained noises, system discrepancies, or minor malfunctions just to foreshadow it. The author determines when the story is ready.
- Fresh restart began November 2, 2026. Scene 1 was saved. Scenes 2 and 3 were generated; check the actual local scene files before assuming they are saved/accepted. Scene 4 was deliberately left unwritten during the repeated anomaly-hook problem.
- Next live check: after syncing both repositories locally, run Prepare Scene for Scene 4. The latest code should include the accident-timing Canon Rule, the starting time anchor, and more previous-scene context. See whether the suggestion continues the evening naturally. The code guarantees the model receives these directions, not that the model will obey them.

## Protected novel data

- Taken_at_Dusk is an important existing novel. Preserve the two encrypted secret letters, related local-only metadata, helper scripts, private key, and /secrets/ ignore rule. Do not decrypt, display, copy, upload, or change them unless explicitly asked.
- Keep disposable test packages local-only and never sync or publish them.
