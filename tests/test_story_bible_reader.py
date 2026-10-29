import json
import tempfile
import unittest
from pathlib import Path

from builder.novel_creator import create_novel_package
from builder.story_bible_reader import load_story_bible


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


if __name__ == "__main__":
    unittest.main()
