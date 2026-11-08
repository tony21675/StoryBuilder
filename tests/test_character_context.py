import json
import tempfile
import unittest
from pathlib import Path

from builder.character_context import build_character_card_context_prompt


class CharacterCardContextTests(unittest.TestCase):
    def make_novel(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        cards = {
            "Tiffany.json": {
                "name": "Tiffany Jones",
                "role": "student",
                "occupation": "High school student",
                "background": "Has helped care for younger relatives and is used to handling busy family routines.",
                "skills": ["organization", "first aid basics"],
                "hobbies": ["drawing", "photography"],
                "description": "Usually quiet in unfamiliar groups, but comfortable with close friends.",
                "gender": "female",
                "sexual_orientation": "Straight",
                "personality": ["shy", "thoughtful"],
                "relationships": {"Maya": "close friend; feels like a sister"},
            },
            "Maya.json": {
                "name": "Maya",
                "role": "student",
                "gender": "female",
                "sexual_orientation": "Bisexual",
                "personality": ["confident", "playful"],
            },
            "Chloe.json": {
                "name": "Chloe",
                "role": "family friend",
                "gender": "female",
                "sexual_orientation": "Straight",
                "personality": ["protective"],
            },
        }
        for filename, card in cards.items():
            (root / filename).write_text(
                json.dumps(card, indent=2), encoding="utf-8"
            )
        bible = {"character_cards": list(cards)}
        return bible

    def test_only_characters_named_in_the_writing_context_are_included(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bible = self.make_novel(root)

            prompt = build_character_card_context_prompt(
                root, bible, "Tiffany and Maya spend the afternoon talking."
            )

        self.assertIn("[Tiffany Jones]", prompt)
        self.assertIn("[Maya]", prompt)
        self.assertIn("Sexual orientation: Straight", prompt)
        self.assertIn("Sexual orientation: Bisexual", prompt)
        self.assertIn("Personality: shy, thoughtful", prompt)
        self.assertIn("Occupation / department: High school student", prompt)
        self.assertIn("Background / experience: Has helped care for younger relatives", prompt)
        self.assertIn("Skills / expertise: organization, first aid basics", prompt)
        self.assertIn("Interests / hobbies: drawing, photography", prompt)
        self.assertIn("Additional established notes: Usually quiet in unfamiliar groups", prompt)
        self.assertIn("Maya: close friend; feels like a sister", prompt)
        self.assertNotIn("[Chloe]", prompt)
        self.assertIn("Do not invent romantic or sexual attraction", prompt)
        self.assertIn("friendship, teasing, and affection can remain platonic", prompt)
        self.assertIn("Do not treat hobbies or general interests as professional qualifications", prompt)
        self.assertIn("questions or hypotheses rather than established expertise", prompt)

    def test_all_cards_can_be_included_for_opening_scene_preparation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bible = self.make_novel(root)

            prompt = build_character_card_context_prompt(
                root, bible, "", include_all=True
            )

        self.assertIn("[Tiffany Jones]", prompt)
        self.assertIn("[Maya]", prompt)
        self.assertIn("[Chloe]", prompt)
        self.assertIn("Skills / expertise: organization, first aid basics", prompt)
        self.assertIn("Interests / hobbies: drawing, photography", prompt)

    def test_compact_mode_keeps_only_short_identity_and_role_facts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bible = self.make_novel(root)

            prompt = build_character_card_context_prompt(
                root, bible, "Tiffany and Maya talk.", compact=True
            )

        self.assertIn("[Tiffany Jones]", prompt)
        self.assertIn("Gender: female", prompt)
        self.assertIn("Occupation / department: High school student", prompt)
        self.assertIn("Skills: organization, first aid basics", prompt)
        self.assertNotIn("Sexual orientation:", prompt)
        self.assertNotIn("Background / experience:", prompt)
        self.assertNotIn("Interests / hobbies:", prompt)
        self.assertNotIn("relationships", prompt.casefold())
        self.assertNotIn("[Chloe]", prompt)

    def test_unmentioned_character_cards_add_roster_without_detailed_profiles(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bible = self.make_novel(root)

            prompt = build_character_card_context_prompt(
                root, bible, "The crew worked through the afternoon."
            )

        self.assertIn("ESTABLISHED CHARACTER ROSTER", prompt)
        self.assertIn(
            "Registered characters in this novel: Tiffany Jones, Maya, Chloe",
            prompt,
        )
        self.assertNotIn("CHARACTER REFERENCES", prompt)
        self.assertNotIn("[Tiffany Jones]", prompt)
        self.assertNotIn("[Maya]", prompt)
        self.assertNotIn("[Chloe]", prompt)
        self.assertNotIn("Sexual orientation:", prompt)
        self.assertNotIn("Personality:", prompt)
        self.assertNotIn("Skills / expertise:", prompt)
        self.assertNotIn("close friend; feels like a sister", prompt)

    def test_embedded_card_objects_use_the_same_professional_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            root.mkdir(exist_ok=True)
            bible = {
                "character_cards": [
                    {
                        "name": "Morgan",
                        "role": "planetary geologist",
                        "occupation": "Science Department, Planetary Geologist",
                        "skills": ["geology", "terrain assessment", "field observation"],
                        "hobbies": ["yoga"],
                    }
                ]
            }

            prompt = build_character_card_context_prompt(
                root, bible, "Morgan joins the discussion."
            )

        self.assertIn("Role: planetary geologist", prompt)
        self.assertIn("Occupation / department: Science Department, Planetary Geologist", prompt)
        self.assertIn("Skills / expertise: geology, terrain assessment, field observation", prompt)
        self.assertIn("Interests / hobbies: yoga", prompt)

    def test_missing_card_file_is_ignored_without_blocking_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bible = {"character_cards": ["Missing.json"]}

            prompt = build_character_card_context_prompt(
                root, bible, "Mara enters the room."
            )

        self.assertEqual(prompt, "Mara enters the room.")


if __name__ == "__main__":
    unittest.main()
