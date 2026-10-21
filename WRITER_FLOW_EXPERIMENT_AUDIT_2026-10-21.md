# Writer Flow Experiment Audit and Next Steps
Date: 2026-10-21

## Purpose

Keep the next StoryBuilder test simple. The goal is to find out whether a leaner scene brief lets the model write a scene that flows naturally, without burying the story under a checklist of instructions.

This is an audit and test plan only. It does not change the novel package, its manuscript, its guidance, or the application code beyond the separate experiment already on this branch.

## Current state

- Experiment branch: `experiment/leaner-scene-boundary`
- Draft PR: https://github.com/tony21675/StoryBuilder/pull/45
- The experiment shortens the Writer scene-boundary brief. It does not change the main Writer system prompt, scene contract, validator, sampling settings, or the novel's story guidance.
- Local verification on this branch passed:
  - `python3 -m compileall -q builder storybuilder.py tests`
  - `python3 -m unittest discover -s tests -v`
  - Result: 304 tests passed.
- Passing tests establish that the code and expectations are internally consistent. They do not establish that the prose is better. A live writing comparison is still needed.
- The experiment has not been merged into `main`.

## What we learned from the writing

The strongest lesson from Chapter 1 was that adding more and more rules made the model lose the story. Results improved when the prompt made the story and natural scene development more important than mechanically following an instruction list.

The next test should therefore change as little as possible. Do not try to repair every old Chapter 2/3 plan, state file, draft, and continuity artifact before testing the prompt.

## Recommended test

1. Keep the real novel package at `~/Documents/MyNovel/Taken_at_Dusk` untouched during the experiment.
2. Keep the existing disposable package at `~/Documents/MyNovel_creative_test/Taken_at_Dusk` untouched until a separate fresh test copy is ready.
3. Create a new disposable copy for the experiment. Do not delete or overwrite either existing folder.
4. Give the test copy only the minimum story context needed for the test: the accepted end of Chapter 1, the relevant established facts about the abduction, and the intended direction for the next scene.
5. Start from the moment Maya tells Tony, “Tiffany is gone.” Let Tony try to understand what happened. Maya can explain in fragments as stress and memory allow. Preserve canon and character knowledge, but do not dictate every beat, gesture, line, or emotional reaction.
6. Run the same scene once with the existing brief and once with the leaner brief, if practical. Keep the story context and generation settings the same so the comparison is meaningful.
7. Compare the results for continuity, natural dialogue, pacing, emotional credibility, and whether the scene advances without repetitive reactions or a forced checklist feel.
8. Do not merge PR #45 based only on unit-test results. Decide after reviewing actual generated prose.

## Character guidance to preserve

Maya's feelings for Tony should emerge through natural, cumulative behavior. Under extreme stress, with her guard down, she may unintentionally let slip that she loves him. Do not force the confession into a particular scene, prescribe its exact words or timing, or dictate Tony's reaction. Let the moment and consequences develop naturally. Tony should notice and understand only what he plausibly could.

Chloe's feelings for Tony remain uncertain and may develop gradually. Do not force a confession or make every interaction romantic.

## Chapter 2 direction for the test

Continue immediately from the accepted ending of Chapter 1. Maya has just told Tony, “Tiffany is gone.” Tony is shocked and urgently needs to understand what happened to his daughter. Maya witnessed the abduction and is struggling to explain it. Let their conversation unfold naturally, with Tony asking questions as he begins to understand what Maya saw. Preserve established canon, character knowledge, and the actual events of the abduction. Maya may recall events imperfectly or in fragments. Tony must learn what happened through Maya, not through knowledge he could not have witnessed himself. Keep the focus on the characters, their relationship, and the immediate aftermath. Let the scene develop at its own pace. Do not force repeated emotional reactions, prescribed gestures, or a rigid sequence of beats. Allow the story to move forward naturally once the opening conversation has run its course.

This is a test direction, not a demand to rewrite the chapter plan or manuscript now.

## Safety and scope

- Do not format drives, reset repositories, run destructive cleanup, or delete existing backups.
- Do not use `git reset --hard`, force-push, or discard local work.
- Do not edit the real novel package as part of this prompt experiment.
- When testing the app against a disposable package, launch directly with `STORY_NOVEL_ROOT=...` and close with plain **Close**, not **Close & Sync**, to avoid triggering novel synchronization.
- Keep the test small. If the setup starts turning into a large repair project, stop and reduce the test to one controlled scene comparison.

## Decision after the test

- If the leaner brief produces clearly more natural prose without losing continuity, keep the experiment for review and consider merging it.
- If the result is mixed or worse, revise or abandon the experiment. Do not add another large stack of rules to compensate before understanding the result.
