import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from builder.character_context import build_character_card_context_prompt
from builder.scene_preparation import build_scene_preparation_prompt
from minimal_writer import MinimalWriterApp


class CharacterRosterPromptTests(unittest.TestCase):
    def test_complete_roster_is_shared_even_when_card_details_are_scoped(self):
        story_bible = {
            "character_cards": [
                {"name": "Daniel", "role": "Biologist", "personality": ["patient"]},
                {"name": "Morgan", "role": "Geologist", "personality": ["curious"]},
                {"name": "Elena", "role": "Commander", "personality": ["decisive"]},
            ]
        }

        prompt = build_character_card_context_prompt(
            Path("."),
            story_bible,
            "Daniel and Morgan prepare dinner.",
            include_all=False,
        )

        self.assertIn(
            "Registered characters in this novel: Daniel, Morgan, Elena",
            prompt,
        )
        self.assertIn("complete roster of established members", prompt)
        self.assertIn("Do not invent extra members", prompt)
        self.assertIn("[Daniel]", prompt)
        self.assertIn("[Morgan]", prompt)
        self.assertNotIn("[Elena]", prompt)

    def test_prepare_scene_gets_whole_roster_even_when_previous_scene_cast_is_smaller(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            story_bible = {
                "title": "Test Novel",
                "premise": "A small crew shares a remote research station.",
                "character_cards": [
                    {"name": "Daniel", "role": "Biologist"},
                    {"name": "Morgan", "role": "Geologist"},
                    {"name": "Elena", "role": "Commander"},
                    {"name": "Priya", "role": "Medic"},
                ],
            }
            (root / "story_bible.json").write_text(
                json.dumps(story_bible), encoding="utf-8"
            )
            (root / "current_state.json").write_text(
                json.dumps({
                    "chapter": 1,
                    "scene": 1,
                    "scene_completed": True,
                    "scene_cast": ["Daniel", "Morgan"],
                }),
                encoding="utf-8",
            )
            source = root / "Chapter_01_Section_01.txt"
            source.write_text("Daniel and Morgan finished preparing dinner.", encoding="utf-8")

            prompt = build_scene_preparation_prompt(
                root, "Test Novel", 1, 2, source_scene_path=source
            )

        self.assertIn(
            "Registered characters in this novel: Daniel, Morgan, Elena, Priya",
            prompt,
        )
        self.assertIn("Do not invent extra members", prompt)
        self.assertIn("Scene direction:", prompt)
        self.assertIn("Natural endpoint:", prompt)
        self.assertIn("two labeled parts", prompt)
        self.assertIn("rather than continuing into the next activity", prompt)
        self.assertIn("do not repeat these labels, and stop at the natural endpoint", prompt)
        self.assertIn("[Daniel]", prompt)
        self.assertIn("[Morgan]", prompt)
        self.assertNotIn("[Elena]", prompt)
        self.assertNotIn("[Priya]", prompt)

    def test_write_context_receives_roster_guard_for_the_selected_novel(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "story_bible.json").write_text(
                json.dumps({
                    "title": "Test Novel",
                    "character_cards": [
                        {"name": "Daniel"},
                        {"name": "Morgan"},
                        {"name": "Elena"},
                    ],
                    "locations": {},
                }),
                encoding="utf-8",
            )
            app = MinimalWriterApp.__new__(MinimalWriterApp)
            app.novel_var = SimpleNamespace(get=lambda: "Test Novel")
            app.novel_packages = {"Test Novel": root}

            prompt = app._prepare_location_context(
                "Daniel and Morgan finish making dinner."
            )

        self.assertIn(
            "Registered characters in this novel: Daniel, Morgan, Elena",
            prompt,
        )
        self.assertIn("Do not invent extra members", prompt)


if __name__ == "__main__":
    unittest.main()
