import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from builder.scene_flow import build_transition_prompt, review_chapter_flow


class SceneFlowPromptTests(unittest.TestCase):
    def test_prompt_uses_end_of_previous_and_start_of_next_scene(self):
        previous = "BEGIN_PREVIOUS " + ("middle " * 1200) + "END_PREVIOUS"
        following = "START_NEXT " + ("next " * 1200) + "END_NEXT"

        prompt = build_transition_prompt(
            "Chapter_02_Section_01.txt",
            previous,
            "Chapter_02_Section_02.txt",
            following,
            context_chars=700,
        )

        self.assertIn("END_PREVIOUS", prompt)
        self.assertIn("START_NEXT", prompt)
        self.assertNotIn("Review the transition", prompt[-80:])
        self.assertIn("Do not fill intentional gaps with invented events", prompt)
        self.assertLess(len(prompt), len(previous) + len(following))

    def test_prompt_requires_both_scenes_to_contain_prose(self):
        with self.assertRaisesRegex(ValueError, "Both accepted scenes"):
            build_transition_prompt("Scene 1", "Text", "Scene 2", " ")

    def test_review_chapter_flow_checks_each_adjacent_pair_without_editing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "Chapter_02_Section_01.txt"
            second = root / "Chapter_02_Section_02.txt"
            third = root / "Chapter_02_Section_03.txt"
            first.write_text("Scene one ends with Maya reaching Tony.", encoding="utf-8")
            second.write_text("Scene two starts with Tony comforting Maya.", encoding="utf-8")
            third.write_text("Scene three starts with Maya explaining the van.", encoding="utf-8")
            originals = {
                path: path.read_text(encoding="utf-8")
                for path in (first, second, third)
            }
            progress = []

            with patch(
                "builder.scene_flow._run_transition_review",
                side_effect=["First transition review", "Second transition review"],
            ) as reviewer:
                report = review_chapter_flow(
                    Path("/tmp/fake-writer.gguf"),
                    [first, second, third],
                    progress=lambda done, total, message: progress.append(
                        (done, total, message)
                    ),
                )

            self.assertEqual(reviewer.call_count, 2)
            prompts = [call.args[1] for call in reviewer.call_args_list]
            self.assertIn("Scene one ends with Maya reaching Tony.", prompts[0])
            self.assertIn("Scene two starts with Tony comforting Maya.", prompts[0])
            self.assertIn("Scene two starts with Tony comforting Maya.", prompts[1])
            self.assertIn("Scene three starts with Maya explaining the van.", prompts[1])
            self.assertIn("First transition review", report)
            self.assertIn("Second transition review", report)
            self.assertIn("No manuscript files were changed", report)
            self.assertEqual([entry[:2] for entry in progress], [(1, 2), (2, 2)])
            self.assertEqual(
                {path: path.read_text(encoding="utf-8") for path in originals},
                originals,
            )

    def test_review_requires_at_least_two_nonempty_scenes(self):
        with tempfile.TemporaryDirectory() as tmp:
            only_scene = Path(tmp) / "Chapter_01_Section_01.txt"
            only_scene.write_text("Just one scene.", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "(?i)at least two"):
                review_chapter_flow(Path("/tmp/fake-writer.gguf"), [only_scene])


if __name__ == "__main__":
    unittest.main()
