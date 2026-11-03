# StoryBuilder handoff, current checkpoint

Date: November 3, 2026

## Project and workflow

- StoryBuilder repository: ~/Documents/StoryBuilder, GitHub tony21675/StoryBuilder.
- Active development branch: redesign/simplified-writing-workflow. Keep the repository on this branch during current development.
- Launch Minimal Writer with: cd ~/Documents/StoryBuilder && ./start.sh. It syncs the active branch and launches minimal_writer.py.
- Launch Story Bible with: cd ~/Documents/StoryBuilder && bash start_story_bible.sh.
- Novel packages live under ~/Documents/MyNovel/*; do not use other locations for novel projects.
- Use python3, never python, in Linux terminal commands.
- Keep app work incremental and test each change. Discuss app or novel changes before making them; handoff-only updates do not need permission.
- Never alter manuscript prose, novel state, or novel package data without explicit permission. Preserve accepted drafts and backups.
- Avoid long terminal instructions. Do not add large rule sets, rigid prose constraints, or over-prescriptive writing behavior. The user's preference is to let stories and characters develop naturally.

## Current StoryBuilder state

StoryBuilder has two companion apps:

- Story Bible manages novel setup and reference data: title, premise, setting, genre/mood/audience direction, explicit-adult setting, canon rules, Character Cards, and locations. Character Cards are plain-English editable forms; only the name is required. Canon Rules are stored in the existing canon_rules array in story_bible.json.
- Minimal Writer handles local-model loading, Write, Continue, New Session, Prepare Scene, text/ODT editing, Save Draft, Save Draft As, Save New Scene, opening saved scenes, and selected-passage revision with preview/accept. Prepare Scene selects a prospective scene destination. Save New Scene writes directly to the correct chapter folder and does not overwrite existing ODT/TXT scenes.

## Latest app fix: Canon Rules now reach the model (November 3, 2026)

- Previous behavior had a real gap: Story Bible saved canon_rules correctly, but Prepare Scene and Minimal Writer Write / Continue never included those saved rules in their model prompts.
- Added builder/canon_rules.py with a shared formatter. It renders nonblank rules as a compact CANON RULES section; empty or unsupported values add nothing.
- Integrated it into builder/scene_preparation.py and MinimalWriterApp._prepare_location_context in minimal_writer.py. Both scene planning and actual writing now receive the same Canon Rules from the selected novel's Story Bible.
- No Story Bible storage schema, UI, manuscript, or novel-package files were changed by this app fix.
- Tests added/updated: tests/test_canon_rules.py, tests/test_scene_preparation.py, and tests/test_minimal_writer.py. The new formatter tests and both prompt-integration tests passed.
- Latest tested code commit: 714e409c90ec8141d74b0a63b31bbd1332c228d1. Python CI: 623 passed, 1 failed, 77 subtests passed. StoryBuilder unittest CI: 624 tests run, 1 error. The only failure is the existing unrelated test_blank_name_does_not_save_or_close_the_editor Tk test-harness problem: its fake root has no .tk attribute. Do not describe the full CI as green.
- CI runs: https://github.com/tony21675/StoryBuilder/actions/runs/41600277173 and https://github.com/tony21675/StoryBuilder/actions/runs/41600277280.
- The handoff was updated after this implementation. To test locally, close Minimal Writer and run cd ~/Documents/StoryBuilder && ./start.sh so it pulls the latest development branch.

## Current novel: The Long Way Home

- Local package: ~/Documents/MyNovel/The-Long-Way-Home. GitHub: tony21675/The-Long-Way-Home, branch main.
- Premise: Six young, unmarried crew members share life and work at a research outpost on Mars. Far from Earth, they build routines, friendships, rivalries, and a sense of home while handling the challenges of living on another planet. Their lives are eventually disrupted by an unexpected accident that threatens the outpost and their survival. The story follows their everyday lives, developing relationships, and their struggle to overcome whatever comes their way.
- Setting: a crewed Mars research outpost in the near future, with credible technology and environment. The exact failure and repair solution are not predetermined.
- Story Bible direction: Science Fiction; Humorous, Serious, and Tense moods; Adult audience; explicit adult content enabled.
- Character Cards are the source of truth for the six crew: Daniel Okafor (male, straight), Elena Vasquez (female, straight), Morgan Reed (female, bisexual), Priya Shah (female, straight), Ryan Mercer (male, straight), and Zoe Bennett (female, bisexual). Their personality details and other card fields are saved in their individual JSON files. Keep orientation separate from gender.
- The author added and synced one Canon Rule named Accident Timing: the life-support accident is a later major turning point; early chapters should establish everyday life, personalities, friendships, and relationships; do not repeatedly add ominous hints, unexplained noises, system discrepancies, or minor malfunctions just to foreshadow it; the author decides when the story is ready.
- Recent restart: The novel was reset for a fresh opening on November 2, 2026. Scene 1 was saved. Scenes 2 and 3 were generated during testing; verify the actual scene list/files locally before assuming either is saved/accepted. Scene 4 is deliberately unwritten because Prepare Scene continued proposing a technical anomaly.
- Next test after pulling StoryBuilder: reopen the novel in Minimal Writer and run Prepare Scene for Scene 4. Confirm the existing Accident Timing rule appears to influence the suggestion. The new code guarantees the model receives the rule; it cannot guarantee the model will obey it. Do not add more rules or change the novel unless the author asks.

## Protected novel and data

- Taken_at_Dusk is an important existing novel. Preserve the two encrypted secret letters, related local-only metadata, helper scripts, private key, and /secrets/ ignore rule. Do not decrypt, display, copy, upload, or change them unless explicitly asked.
- Keep disposable tests out of real novel packages. Use only an explicitly approved local-only test package for Story Bible save/edit checks; never sync or publish such a fixture.
