import json
import tempfile
import unittest
from pathlib import Path

from builder.novel_creator import create_novel_package
from builder.story_bible_reader import load_story_bible, save_story_bible_premise


class StoryBibleReaderTests(unittest.TestCase):
    def test_loads_story_bible_without_modifying_the_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = create_novel_package("The Long Way Home", novel_root=temporary)
            bible_path = package / "story_bible.json"
            before = bible_path.read_bytes()

            result = load_story_bible(package)

            self.assertEqual(result["title"], "The Long Way Home")
            self.assertEqual(result["premise"], "")
            self.assertEqual(result["character_cards"], [])
            self.assertEqual(bible_path.read_bytes(), before)

    def test_reports_a_missing_story_bible(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(FileNotFoundError, "story_bible.json"):
                load_story_bible(temporary)

    def test_reports_invalid_json_with_location(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            (package / "story_bible.json").write_text(
                '{"title": "unfinished"\n', encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, r"line 2, column 1"):
                load_story_bible(package)

    def test_rejects_non_object_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            (package / "story_bible.json").write_text(
                json.dumps(["not", "a", "story bible"]), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "JSON object"):
                load_story_bible(package)

    def test_save_changes_only_premise_and_preserves_unknown_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = create_novel_package("The Long Way Home", novel_root=temporary)
            bible_path = package / "story_bible.json"
            original = json.loads(bible_path.read_text(encoding="utf-8"))
            original["optional_story_modules"] = []
            original["custom_field"] = {"leave": "exactly as-is"}
            original["canon_rules"] = ["Keep this rule."]
            bible_path.write_text(
                json.dumps(original, indent=2) + "\n", encoding="utf-8"
            )

            save_story_bible_premise(package, "Six astronauts survive an accident.")

            saved = json.loads(bible_path.read_text(encoding="utf-8"))
            expected = dict(original)
            expected["premise"] = "Six astronauts survive an accident."
            self.assertEqual(saved, expected)
            self.assertEqual(saved["custom_field"], {"leave": "exactly as-is"})
            self.assertEqual(saved["optional_story_modules"], [])

    def test_save_uses_the_latest_file_and_preserves_intervening_other_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = create_novel_package("A Novel", novel_root=temporary)
            bible_path = package / "story_bible.json"
            latest = json.loads(bible_path.read_text(encoding="utf-8"))
            latest["title"] = "Title updated elsewhere"
            latest["custom_field"] = ["another editor's addition"]
            bible_path.write_text(json.dumps(latest, indent=2), encoding="utf-8")

            save_story_bible_premise(package, "Updated premise.")

            saved = json.loads(bible_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["title"], "Title updated elsewhere")
            self.assertEqual(saved["custom_field"], ["another editor's addition"])
            self.assertEqual(saved["premise"], "Updated premise.")

    def test_save_rejects_malformed_file_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            bible_path = package / "story_bible.json"
            original = b'{"premise": broken\n'
            bible_path.write_bytes(original)

            with self.assertRaisesRegex(ValueError, "not valid JSON"):
                save_story_bible_premise(package, "Do not overwrite malformed data.")

            self.assertEqual(bible_path.read_bytes(), original)
            self.assertEqual(list(package.iterdir()), [bible_path])

    def test_save_rejects_non_text_premise_without_modifying_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = create_novel_package("A Novel", novel_root=temporary)
            bible_path = package / "story_bible.json"
            original = bible_path.read_bytes()

            with self.assertRaisesRegex(ValueError, "must be text"):
                save_story_bible_premise(package, None)

            self.assertEqual(bible_path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
