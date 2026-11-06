import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from builder.scene_preparation import build_scene_preparation_prompt
from builder.story_craft import build_media_device_prompt, build_story_craft_prompt
from minimal_writer import MinimalWriterApp


class StoryCraftPromptTests(unittest.TestCase):
    def test_shared_guidance_is_short_and_not_tied_to_one_novel(self):
        prompt = build_story_craft_prompt()

        self.assertIn("SCENE CRAFT GUIDANCE", prompt)
        self.assertIn("ordinary moments can matter", prompt.lower())
        self.assertIn("Vary who speaks", prompt)
        self.assertIn("supplementary guidance", prompt)
        self.assertLess(len(prompt), 600)
        self.assertNotIn("MEDIA AND DEVICE BOUNDARIES", prompt)
        self.assertNotIn("Mars", prompt)
        self.assertNotIn("nutrient paste", prompt)
        self.assertNotIn("cattle", prompt)

    def test_media_guidance_is_only_returned_when_the_scene_uses_a_device(self):
        self.assertEqual(build_media_device_prompt("The crew talks over dinner."), "")

        prompt = build_media_device_prompt("They watch a film on the television.")

        self.assertIn("MEDIA AND DEVICE BOUNDARIES", prompt)
        self.assertIn("separate from the characters' real surroundings", prompt)

    def test_prepare_scene_uses_short_craft_guidance_without_unrelated_media_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "story_bible.json").write_text(
                json.dumps({
                    "title": "Test Novel",
                    "premise": "A small group faces an unfamiliar challenge.",
                    "setting": "A remote research station.",
                }),
                encoding="utf-8",
            )

            prompt = build_scene_preparation_prompt(root, "Test Novel", 1, 1)

        self.assertIn("SCENE CRAFT GUIDANCE", prompt)
        self.assertIn("ordinary moments can matter", prompt.lower())
        self.assertIn("supplementary guidance", prompt)
        self.assertNotIn("MEDIA AND DEVICE BOUNDARIES", prompt)

    def test_previous_scene_device_mention_does_not_trigger_media_guidance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "story_bible.json").write_text(
                json.dumps({"title": "Test Novel", "locations": {}}),
                encoding="utf-8",
            )
            previous = root / "Chapter_01_Section_01.txt"
            previous.write_text(
                "The crew watched a film on the television.", encoding="utf-8"
            )

            prompt = build_scene_preparation_prompt(
                root, "Test Novel", 1, 2, source_scene_path=previous
            )

        self.assertNotIn("MEDIA AND DEVICE BOUNDARIES", prompt)

    def test_author_direction_device_mention_triggers_media_guidance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "story_bible.json").write_text(
                json.dumps({"title": "Test Novel", "locations": {}}),
                encoding="utf-8",
            )

            prompt = build_scene_preparation_prompt(
                root,
                "Test Novel",
                1,
                1,
                author_direction="The crew watches a film on the television.",
            )

        self.assertIn("MEDIA AND DEVICE BOUNDARIES", prompt)

    def test_writer_context_adds_media_guidance_only_when_relevant(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "story_bible.json").write_text(
                json.dumps({
                    "title": "Test Novel",
                    "creative_direction": {},
                    "locations": {},
                }),
                encoding="utf-8",
            )
            app = MinimalWriterApp.__new__(MinimalWriterApp)
            app.novel_var = SimpleNamespace(get=lambda: "Test Novel")
            app.novel_packages = {"Test Novel": root}

            ordinary = app._prepare_location_context("Continue the current scene.")
            media = app._prepare_location_context(
                "The crew watches a film on the screen."
            )

        self.assertNotIn("MEDIA AND DEVICE BOUNDARIES", ordinary)
        self.assertIn("MEDIA AND DEVICE BOUNDARIES", media)
        self.assertNotIn("STORY OPENING AND PACING", ordinary)


if __name__ == "__main__":
    unittest.main()
