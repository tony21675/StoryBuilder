import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from builder.character_context import build_character_card_context_prompt
from builder.scene_preparation import build_scene_preparation_prompt
from minimal_writer import MinimalWriterApp


class CharacterRosterPromptTests(unittest.TestCase):
    def test_registered_card_names_are_reference_only_when_card_details_are_scoped(self):
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
            "Character cards registered for this novel (reference only): Daniel, Morgan, Elena",
            prompt,
        )
        self.assertNotIn("complete roster of established members", prompt)
        self.assertNotIn("Do not invent extra members", prompt)
        self.assertIn("[Daniel]", prompt)
        self.assertIn("[Morgan]", prompt)
        self.assertNotIn("[Elena]", prompt)

    def test_prepare_scene_gets_registered_card_references_when_previous_scene_cast_is_smaller(self):
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
            "Character cards registered for this novel (reference only): Daniel, Morgan, Elena, Priya",
            prompt,
        )
        self.assertNotIn("Do not invent extra members", prompt)
        self.assertIn("Scene direction:", prompt)
        self.assertNotIn("Natural endpoint:", prompt)
        self.assertNotIn("two labeled parts", prompt)
        self.assertNotIn("final concrete beat", prompt)
        self.assertIn("The ONLY permitted source for AUTHOR-REQUIRED BEATS", prompt)
        self.assertIn("as an AUTHOR-REQUIRED BEAT", prompt)
        self.assertIn("where the scene ends to the Writer", prompt)
        self.assertIn("[Daniel]", prompt)
        self.assertIn("[Morgan]", prompt)
        # Prepare Scene receives all character cards for broader story awareness.
        # This is reference context, not an instruction to include everyone.
        self.assertIn("[Elena]", prompt)
        self.assertIn("[Priya]", prompt)
        self.assertIn("not a cast checklist", prompt)

    def test_write_context_receives_a_short_roster_for_the_selected_novel(self):
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
            "Character cards registered for this novel (reference only): Daniel, Morgan, Elena",
            prompt,
        )
        self.assertNotIn("Do not invent extra members", prompt)


if __name__ == "__main__":
    unittest.main()
