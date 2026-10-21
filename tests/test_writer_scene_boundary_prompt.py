import unittest

from storybuilder import StoryBuilderApp


class WriterSceneBoundaryPromptTests(unittest.TestCase):
    def test_boundary_brief_stays_concise_and_preserves_core_anchors(self):
        prompt = StoryBuilderApp._writer_scene_boundary_prompt(None)

        self.assertIn("original idea and saved story state", prompt)
        self.assertIn("character knowledge", prompt)
        self.assertIn("concrete planned beats and their agency", prompt)
        self.assertIn("explicit boundaries", prompt)
        self.assertIn("intended endpoint", prompt)
        self.assertIn("Do not stop early or cross a stated hard stop", prompt)
        self.assertIn("Write the scene now. Output only the prose.", prompt)

    def test_boundary_brief_does_not_repeat_detailed_clue_examples(self):
        prompt = StoryBuilderApp._writer_scene_boundary_prompt(None)

        self.assertNotIn("suspicious contact", prompt)
        self.assertNotIn("named destination", prompt)
        self.assertNotIn("A friend may suggest", prompt)
        self.assertLess(len(prompt), 1100)


if __name__ == "__main__":
    unittest.main()
