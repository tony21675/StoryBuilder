import tempfile
import unittest
from pathlib import Path

from builder.scene_planner import (
    find_story_plan_file,
    read_story_plan_file,
    update_scene_plan_markdown,
    validate_scene_plan_fields,
)


class ScenePlanUpdateTests(unittest.TestCase):
    def test_inserts_missing_scene_after_previous_scene_before_group_notes(self):
        source = """# Story Plan

## CONFIRMED: Chapter 3, the long night

### Scene 1: The long night
- End at daybreak.

### Scene 2: Breakfast disclosure
- The group offers to help.

### Confirmed group roles
- Tony leads.
- Jessica is the computer expert.

## CONFIRMED story constraints
- No police call.
"""
        updated = update_scene_plan_markdown(
            source, 3, 3, "The first steps",
            "**Purpose:** Turn shared concern into an initial, manageable approach.\n\n"
            "**Hard stop:** End before detailed assignments or investigation.",
        )
        self.assertLess(updated.index("### Scene 3: The first steps"), updated.index("### Confirmed group roles"))
        self.assertLess(updated.index("### Confirmed group roles"), updated.index("## CONFIRMED story constraints"))
        self.assertIn("### Scene 1: The long night\n- End at daybreak.", updated)
        self.assertIn("### Scene 2: Breakfast disclosure\n- The group offers to help.", updated)
        self.assertIn("- No police call.", updated)

    def test_replaces_only_requested_scene_and_updates_its_title(self):
        source = """# Story Plan

## Chapter 2
### Scene 1: First scene
- Keep this scene unchanged.

### Scene 2: Old title
- Old plan detail.
- Another old detail.

## Chapter 3
### Scene 1: Next chapter
- Must remain untouched.
"""
        updated = update_scene_plan_markdown(
            source, 2, 2, "Revised scene", "**Purpose:** A new plan.\n\n**Hard stop:** Stop here."
        )
        self.assertIn("### Scene 1: First scene\n- Keep this scene unchanged.", updated)
        self.assertIn("### Scene 2: Revised scene\n\n**Purpose:** A new plan.", updated)
        self.assertNotIn("Old plan detail.", updated)
        self.assertIn("### Scene 1: Next chapter\n- Must remain untouched.", updated)

    def test_duplicate_target_headings_are_rejected(self):
        source = """## Chapter 3
### Scene 2: First copy
- One.

### Scene 2: Duplicate copy
- Two.
"""
        with self.assertRaisesRegex(ValueError, "more than one heading"):
            update_scene_plan_markdown(source, 3, 2, "New title", "**Purpose:** Test.")

    def test_nonempty_plan_without_matching_chapter_heading_is_not_guessed(self):
        source = """# Story Plan
### Scene 1: Unscoped
- Unknown chapter.
"""
        with self.assertRaisesRegex(ValueError, "clear Chapter 3 section"):
            update_scene_plan_markdown(source, 3, 2, "New title", "**Purpose:** Test.")

    def test_empty_plan_creates_a_minimal_chapter_and_scene(self):
        updated = update_scene_plan_markdown("", 4, 1, "The arrival", "**Purpose:** Introduce the group.")
        self.assertTrue(updated.startswith("# Story Plan\n\n## Chapter 4"))
        self.assertIn("### Scene 1: The arrival", updated)
        self.assertIn("**Purpose:** Introduce the group.", updated)

    def test_explicit_chapter_scene_heading_style_is_preserved(self):
        source = """# Story Plan
### Chapter 3, Scene 1: Opening
- Start here.
"""
        updated = update_scene_plan_markdown(source, 3, 1, "New opening", "**Purpose:** Revised.")
        self.assertIn("### Chapter 3, Scene 1: New opening", updated)
        self.assertNotIn("### Scene 1: New opening", updated)

    def test_plan_body_cannot_add_new_markdown_heading(self):
        with self.assertRaisesRegex(ValueError, "contains a Markdown heading"):
            validate_scene_plan_fields(
                "The plan", "Purpose text.\n\n### Another scene\n- Body", chapter=3, scene=2
            )

    def test_scene_prefix_is_removed_from_proposed_title(self):
        proposal = validate_scene_plan_fields(
            "Scene 3: The first steps", "**Purpose:** Start small.", chapter=3, scene=3
        )
        self.assertEqual(proposal["title"], "The first steps")

    def test_story_plan_file_lookup_is_case_insensitive_and_missing_file_is_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lower = root / "story_plan.md"
            lower.write_text("# Existing plan\n", encoding="utf-8")
            path, content = read_story_plan_file(root)
            self.assertEqual(path, lower)
            self.assertEqual(content, "# Existing plan\n")
            lower.unlink()
            missing_path = find_story_plan_file(root)
            self.assertEqual(missing_path, root / "STORY_PLAN.md")
            self.assertFalse(missing_path.exists())


if __name__ == "__main__":
    unittest.main()
