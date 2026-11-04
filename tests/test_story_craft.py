import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from builder.scene_preparation import build_scene_preparation_prompt
from builder.story_craft import build_story_craft_prompt
from minimal_writer import MinimalWriterApp


class StoryCraftPromptTests(unittest.TestCase):
    def test_shared_guidance_is_light_touch_and_not_tied_to_one_novel(self):
        prompt = build_story_craft_prompt()

        self.assertIn("ordinary moments can matter", prompt)
        self.assertIn("Vary scene focus and group size naturally", prompt)
        self.assertIn("not everyone needs to speak", prompt)
        self.assertIn("let dialogue breathe", prompt)
        self.assertIn("not a formula", prompt)
        self.assertIn("MEDIA AND DEVICE BOUNDARIES", prompt)
        self.assertIn(
            "When characters watch, listen to, read, or view content through a television, radio, phone, computer, screen, speaker, or other device",
            prompt,
        )
        self.assertIn(
            "they do not become the characters' physical surroundings or current activity",
            prompt,
        )
        self.assertIn(
            "unless the author's direction explicitly establishes participation",
            prompt,
        )
        self.assertIn(
            "When a scene follows an existing scene, continue directly from its final moment.",
            prompt,
        )
        self.assertIn(
            "only change time or place when the author's direction calls for that transition",
            prompt,
        )
        self.assertNotIn("Mars", prompt)
        self.assertNotIn("nutrient paste", prompt)
        self.assertNotIn("cattle", prompt)

    def test_prepare_scene_receives_shared_craft_guidance(self):
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

            prompt = build_scene_preparation_prompt(
                root, "Test Novel", 1, 1
            )

        self.assertIn("SCENE CRAFT GUIDANCE", prompt)
        self.assertIn("not everyone needs to speak", prompt)
        self.assertIn("ordinary moments can matter", prompt)
        self.assertIn("MEDIA AND DEVICE BOUNDARIES", prompt)
        self.assertIn("they do not become the characters' physical surroundings or current activity", prompt)
        self.assertIn(
            "When a scene follows an existing scene, continue directly from its final moment.",
            prompt,
        )

    def test_write_and_continue_context_receives_shared_craft_guidance(self):
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

            prompt = app._prepare_location_context(
                "Continue the current scene."
            )

        self.assertIn("SCENE CRAFT GUIDANCE", prompt)
        self.assertIn("let dialogue breathe", prompt)
        self.assertIn("follow the author's specific direction", prompt)
        self.assertIn("MEDIA AND DEVICE BOUNDARIES", prompt)
        self.assertIn("they do not become the characters' physical surroundings or current activity", prompt)
        self.assertIn(
            "When a scene follows an existing scene, continue directly from its final moment.",
            prompt,
        )


if __name__ == "__main__":
    unittest.main()
