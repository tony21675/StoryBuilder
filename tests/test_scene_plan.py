import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import storybuilder as storybuilder_app
from builder.scene_plan import find_scene_idea, load_scene_idea_from_plan


class ScenePlanReaderTests(unittest.TestCase):
    def test_reads_current_chapter_scene_and_stops_at_next_sibling_heading(self):
        plan = """# Story Plan

## CONFIRMED: Chapter 2, aftermath
### Scene 3: The account
- Scene three belongs to chapter two.
### Scene 4: Care and memory
- Scene four should not be included.

## CONFIRMED: Chapter 3, the long night and the private effort
### Scene 1: The long night
- End at daybreak.
### Scene 2: Breakfast disclosure and the first offers to help
- Tony makes breakfast and wakes Maya.
- The guests arrive expecting an ordinary breakfast.
- Tony tells them what happened once everyone is seated.
### Confirmed group roles and direction
- Tony leads the effort.
"""
        idea = find_scene_idea(plan, 3, 2)

        self.assertIsNotNone(idea)
        self.assertIn("Breakfast disclosure and the first offers to help", idea)
        self.assertIn("Tony makes breakfast", idea)
        self.assertIn("once everyone is seated", idea)
        self.assertNotIn("Tony leads the effort", idea)
        self.assertNotIn("Scene three belongs", idea)
        self.assertNotIn("End at daybreak", idea)

    def test_chapter_context_prevents_matching_same_scene_number_in_other_chapter(self):
        plan = """## Chapter 1: Opening
### Scene 2: Old idea
- Wrong chapter.
## Chapter 3: Later
### Scene 2: Correct idea
- Correct chapter.
"""
        idea = find_scene_idea(plan, 3, 2)
        self.assertIn("Correct idea", idea)
        self.assertNotIn("Wrong chapter", idea)

    def test_supports_explicit_chapter_and_scene_heading(self):
        plan = """# Outline
## Upcoming material
### Chapter 4, Scene 5: The turn
- This heading identifies both numbers.
### Scene 6: Another scene
- Not the requested one.
"""
        idea = find_scene_idea(plan, 4, 5)
        self.assertIn("The turn", idea)
        self.assertIn("This heading identifies both numbers", idea)
        self.assertNotIn("Another scene", idea)

    def test_supports_numbered_chapter_scene_heading(self):
        plan = """# Outline
## Planning
### 3.2: Breakfast
- They gather around the table.
### 3.3: First lead
- They start following a lead.
"""
        idea = find_scene_idea(plan, 3, 2)
        self.assertIn("Breakfast", idea)
        self.assertIn("gather around the table", idea)
        self.assertNotIn("First lead", idea)

    def test_does_not_guess_when_scene_is_missing_or_not_in_chapter_context(self):
        plan = """# Outline
### Scene 2: No chapter context
- Should not be guessed.
## Chapter 3: Chapter heading
### Scene 1: Other scene
- Not scene two.
"""
        self.assertIsNone(find_scene_idea(plan, 4, 2))
        self.assertIsNone(find_scene_idea(plan, 3, 2))

    def test_reads_plan_file_from_novel_package_root_case_insensitively(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "story_plan.md").write_text(
                "## Chapter 3\n### Scene 2: Breakfast\n- Coffee is ready.\n",
                encoding="utf-8",
            )
            idea = load_scene_idea_from_plan(tmp, 3, 2)
        self.assertIn("Breakfast", idea)
        self.assertIn("Coffee is ready", idea)

    def test_missing_plan_file_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(load_scene_idea_from_plan(tmp, 3, 2))

    def test_saved_scene_idea_takes_priority_over_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "STORY_PLAN.md").write_text(
                "## Chapter 3\n### Scene 2: Planned idea\n- Plan text.\n",
                encoding="utf-8",
            )
            app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
            app.package = SimpleNamespace(path=Path(tmp))

            idea, source, error = app._resolve_scene_idea(
                3, 2, {"scene_idea": "Tony's saved author notes."}
            )

        self.assertEqual(idea, "Tony's saved author notes.")
        self.assertEqual(source, "saved")
        self.assertIsNone(error)

    def test_plan_is_used_only_when_saved_idea_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "STORY_PLAN.md").write_text(
                "## Chapter 3\n### Scene 2: Planned idea\n- Plan text.\n",
                encoding="utf-8",
            )
            app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
            app.package = SimpleNamespace(path=Path(tmp))

            idea, source, error = app._resolve_scene_idea(3, 2, {})

        self.assertIn("Planned idea", idea)
        self.assertIn("Plan text", idea)
        self.assertEqual(source, "plan")
        self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
