import tempfile
import unittest
from pathlib import Path

from builder.writer_continuity import (
    build_previous_scene_context_prompt,
    previous_saved_scene,
)


class PreviousSceneContinuityTests(unittest.TestCase):
    @staticmethod
    def write_scene(root: Path, chapter: int, scene: int, text: str) -> Path:
        folder = root / "Manuscript" / "Chapters" / f"Chapter_{chapter:02d}"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"Chapter_{chapter:02d}_Section_{scene:02d}.txt"
        path.write_text(text, encoding="utf-8")
        return path

    def test_uses_the_immediately_preceding_saved_scene_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_scene(root, 1, 18, "OLDER SCENE MUST NOT BE SELECTED.")
            expected = "SCENE NINETEEN: The six finish their charades game."
            self.write_scene(root, 1, 19, expected)
            self.write_scene(root, 1, 20, "CURRENT TARGET MUST NOT BE INCLUDED.")
            self.write_scene(root, 1, 21, "FUTURE SCENE MUST NOT BE INCLUDED.")

            result = build_previous_scene_context_prompt(
                "Scene direction: Continue the evening.",
                root,
                1,
                20,
            )

            self.assertIn("Source: Chapter 01, Scene 19", result)
            self.assertIn(expected, result)
            self.assertNotIn("OLDER SCENE MUST NOT BE SELECTED", result)
            self.assertNotIn("CURRENT TARGET MUST NOT BE INCLUDED", result)
            self.assertNotIn("FUTURE SCENE MUST NOT BE INCLUDED", result)

    def test_finds_previous_scene_across_chapter_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = self.write_scene(root, 2, 1, "First scene of the new chapter.")
            previous = self.write_scene(root, 1, 16, "Last saved scene of the prior chapter.")

            result = previous_saved_scene(root, 2, 1)

            self.assertEqual(result, (1, 16, previous))
            prompt = build_previous_scene_context_prompt("Start the new day.", root, 2, 1)
            self.assertIn("Source: Chapter 01, Scene 16", prompt)
            self.assertIn("Last saved scene of the prior chapter.", prompt)
            self.assertNotIn("First scene of the new chapter.", prompt)

    def test_no_previous_scene_leaves_prompt_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_scene(root, 1, 3, "A scene later than the target.")
            prompt = "This is the opening scene."

            self.assertEqual(
                build_previous_scene_context_prompt(prompt, root, 1, 1),
                prompt,
            )

    def test_long_previous_scene_is_included_in_full_without_truncation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            opening = "THE OPENING DETAIL THAT MUST SURVIVE."
            middle = "AN IMPORTANT DETAIL FROM THE MIDDLE OF THE SCENE."
            ending = "THE PREVIOUS SCENE'S FINAL MOMENT."
            scene_text = (
                opening
                + "\n\n"
                + ("intervening prose " * 250)
                + middle
                + (" more intervening prose" * 250)
                + "\n\n"
                + ending
            )
            self.write_scene(root, 1, 1, scene_text)

            result = build_previous_scene_context_prompt(
                "Continue.",
                root,
                1,
                2,
            )

            context = result.split("IMMEDIATELY PRECEDING SAVED SCENE", 1)[1]
            self.assertIn(opening, context)
            self.assertIn(middle, context)
            self.assertIn(ending, context)
            self.assertTrue(result.endswith(scene_text))


if __name__ == "__main__":
    unittest.main()
