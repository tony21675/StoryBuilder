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

    def test_writer_system_prompt_enforces_generic_continuity_and_emergency_rules(self):
        prompt = StoryBuilderApp._writer_system_prompt(None, [])
        lower = prompt.casefold()

        for required in (
            "character cards are authoritative for each character's established gender",
            "never jump someone between locations",
            "do not repeat completed events, scenes, or technical reports",
            "pace a life-threatening emergency as a credible chain of events",
            "respect the active novel's established geography",
            "separate observation, theory, and confirmation",
        ):
            with self.subTest(required=required):
                self.assertIn(required.casefold(), lower)

        for novel_specific in (
            "earth cannot send a rescue ship to mars overnight",
            "interplanetary travel takes months",
            "an onboard computer fault sending incorrect signals",
            "zoe's unusual communications readings",
        ):
            with self.subTest(novel_specific=novel_specific):
                self.assertNotIn(novel_specific.casefold(), lower)

