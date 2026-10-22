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

    def test_writer_system_prompt_enforces_continuity_and_emergency_rules(self):
        prompt = StoryBuilderApp._writer_system_prompt(None, [])

        for required in (
            "Character cards are authoritative for each character's established gender",
            "never jump someone between locations",
            "Do not repeat completed events, scenes, or technical reports",
            "Pace a life-threatening emergency as a credible chain of events",
            "interplanetary travel takes months",
            "an onboard computer fault sending incorrect signals",
        ):
            with self.subTest(required=required):
                self.assertIn(required.casefold(), prompt.casefold())


if __name__ == "__main__":
    unittest.main()
