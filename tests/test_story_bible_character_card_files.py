import json
import tempfile
import unittest
from pathlib import Path

from builder.novel_creator import create_novel_package
from builder.story_bible_reader import (
    create_story_bible_character_card,
    load_story_bible,
    load_story_bible_character_card,
    remove_story_bible_character_card_reference,
    save_story_bible_character_card_file,
)


class StoryBibleCharacterCardFileTests(unittest.TestCase):
    def make_package_with_reference(self, temporary):
        package = create_novel_package("A Novel", novel_root=temporary)
        bible_path = package / "story_bible.json"
        data = load_story_bible(package)
        data["character_cards"] = ["Daniel_Okafor.json"]
        data["premise"] = "Keep this premise."
        data["setting"] = "Keep this setting."
        data["canon_rules"] = ["Keep this rule."]
        data["extra_bible_field"] = {"leave": "untouched"}
        bible_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        card = {
            "name": "Daniel Okafor",
            "role": "biologist and life-support specialist",
            "status": "established",
            "age": 28,
            "gender": "male",
            "personality": ["patient", "analytical"],
            "skills": ["biology", "life-support monitoring"],
            "appearance": {"height": "6 ft", "eyes": "brown"},
            "relationships": {"Elena": "trusted colleague"},
            "custom_field": {"nested": [1, 2, 3]},
        }
        (package / "Daniel_Okafor.json").write_text(
            json.dumps(card, indent=2) + "\n", encoding="utf-8"
        )
        return package, card

    def test_loads_referenced_card_file_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            package, expected = self.make_package_with_reference(temporary)
            card_path = package / "Daniel_Okafor.json"
            before = card_path.read_bytes()

            loaded = load_story_bible_character_card(package, "Daniel_Okafor.json")

            self.assertEqual(loaded, expected)
            self.assertEqual(card_path.read_bytes(), before)

    def test_edit_updates_basic_fields_and_preserves_all_other_card_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            package, original = self.make_package_with_reference(temporary)

            save_story_bible_character_card_file(
                package,
                "Daniel_Okafor.json",
                {
                    "name": "Daniel Okafor",
                    "role": "Senior biologist",
                    "description": "A steady specialist.",
                },
            )

            saved_card = load_story_bible_character_card(package, "Daniel_Okafor.json")
            expected = dict(original)
            expected["role"] = "Senior biologist"
            expected["description"] = "A steady specialist."
            self.assertEqual(saved_card, expected)
            saved_bible = load_story_bible(package)
            self.assertEqual(saved_bible["character_cards"], ["Daniel_Okafor.json"])
            self.assertEqual(saved_bible["premise"], "Keep this premise.")
            self.assertEqual(saved_bible["setting"], "Keep this setting.")
            self.assertEqual(saved_bible["canon_rules"], ["Keep this rule."])
            self.assertEqual(saved_bible["extra_bible_field"], {"leave": "untouched"})

    def test_rejects_path_traversal_and_never_reads_outside_novel_folder(self):
        with tempfile.TemporaryDirectory() as temporary:
            package, _original = self.make_package_with_reference(temporary)
            outside = Path(temporary) / "outside.json"
            outside.write_text(json.dumps({"name": "Outside"}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "JSON filename in the novel folder"):
                load_story_bible_character_card(package, "../outside.json")

    def test_new_card_is_separate_json_file_with_reference_in_story_bible(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = create_novel_package("A Novel", novel_root=temporary)
            original = load_story_bible(package)
            original["premise"] = "Preserve premise."
            (package / "story_bible.json").write_text(
                json.dumps(original, indent=2) + "\n", encoding="utf-8"
            )

            filename = create_story_bible_character_card(
                package,
                {
                    "name": "Mara Vale",
                    "role": "Pilot",
                    "description": "A careful flyer.",
                },
            )

            self.assertEqual(filename, "Mara_Vale.json")
            self.assertTrue((package / filename).is_file())
            self.assertEqual(
                load_story_bible_character_card(package, filename),
                {
                    "name": "Mara Vale",
                    "role": "Pilot",
                    "description": "A careful flyer.",
                },
            )
            saved_bible = load_story_bible(package)
            self.assertEqual(saved_bible["character_cards"], [filename])
            self.assertEqual(saved_bible["premise"], "Preserve premise.")

    def test_duplicate_card_names_get_a_new_filename_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = create_novel_package("A Novel", novel_root=temporary)
            first = create_story_bible_character_card(
                package, {"name": "Mara", "role": "Pilot", "description": "First."}
            )
            second = create_story_bible_character_card(
                package, {"name": "Mara", "role": "Medic", "description": "Second."}
            )

            self.assertEqual(first, "Mara.json")
            self.assertEqual(second, "Mara_2.json")
            self.assertEqual(
                load_story_bible_character_card(package, first)["description"], "First."
            )
            self.assertEqual(
                load_story_bible_character_card(package, second)["description"], "Second."
            )

    def test_remove_drops_only_reference_and_keeps_source_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            package, original = self.make_package_with_reference(temporary)
            card_path = package / "Daniel_Okafor.json"
            before = card_path.read_bytes()

            remove_story_bible_character_card_reference(
                package, 0, "Daniel_Okafor.json"
            )

            self.assertEqual(load_story_bible(package)["character_cards"], [])
            self.assertTrue(card_path.is_file())
            self.assertEqual(card_path.read_bytes(), before)

    def test_remove_rejects_stale_index_without_changing_anything(self):
        with tempfile.TemporaryDirectory() as temporary:
            package, _original = self.make_package_with_reference(temporary)
            bible_path = package / "story_bible.json"
            before = bible_path.read_bytes()

            with self.assertRaisesRegex(RuntimeError, "list changed"):
                remove_story_bible_character_card_reference(
                    package, 4, "Daniel_Okafor.json"
                )

            self.assertEqual(bible_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
