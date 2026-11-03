import unittest

from builder.story_timeline import build_story_timeline_prompt


class StoryTimelinePromptTests(unittest.TestCase):
    def test_formats_saved_story_time_as_a_forward_moving_anchor(self):
        prompt = build_story_timeline_prompt(
            "Day 1, 16:00 (4:00 PM), late afternoon at the Mars outpost."
        )

        self.assertIn("STORY TIMELINE", prompt)
        self.assertIn("Latest saved in-story time: Day 1, 16:00", prompt)
        self.assertIn("not as an instruction to reset every new scene", prompt)
        self.assertIn("Keep time moving forward", prompt)
        self.assertIn("Do not repeat activities", prompt)

    def test_empty_or_unsupported_time_adds_no_prompt_text(self):
        self.assertEqual(build_story_timeline_prompt(""), "")
        self.assertEqual(build_story_timeline_prompt(None), "")
        self.assertEqual(build_story_timeline_prompt(1600), "")

    def test_long_time_description_is_bounded(self):
        prompt = build_story_timeline_prompt("D" * 500)

        self.assertLess(len(prompt), 600)
        self.assertIn("...", prompt)


if __name__ == "__main__":
    unittest.main()
