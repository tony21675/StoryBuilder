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
                "name": "Tiffany",
                "role": "student",
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

        self.assertIn("[Tiffany]", prompt)
        self.assertIn("[Maya]", prompt)
        self.assertIn("Sexual orientation: Straight", prompt)
        self.assertIn("Sexual orientation: Bisexual", prompt)
        self.assertIn("Personality: shy, thoughtful", prompt)
        self.assertIn("Maya: close friend; feels like a sister", prompt)
        self.assertNotIn("[Chloe]", prompt)
        self.assertIn("ordinary friendship need not be romantic", prompt)

    def test_all_cards_can_be_included_for_opening_scene_preparation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bible = self.make_novel(root)

            prompt = build_character_card_context_prompt(
                root, bible, "", include_all=True
            )

        self.assertIn("[Tiffany]", prompt)
        self.assertIn("[Maya]", prompt)
        self.assertIn("[Chloe]", prompt)

    def test_unmentioned_character_cards_do_not_change_the_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bible = self.make_novel(root)

            prompt = build_character_card_context_prompt(
                root, bible, "The crew worked through the afternoon."
            )

        self.assertEqual(prompt, "The crew worked through the afternoon.")

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
