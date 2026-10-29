import json
import tempfile
import unittest
from pathlib import Path

from builder.novel_creator import (
    create_novel_package,
    suggest_folder_name,
)
from builder.novel_browser import list_novel_packages, list_scene_chapters


class NovelCreatorTests(unittest.TestCase):
    def test_suggests_a_safe_readable_folder_name(self):
        self.assertEqual(suggest_folder_name("The Long Way Home"), "The-Long-Way-Home")
        self.assertEqual(suggest_folder_name("  !!!  "), "New-Novel")

    def test_creates_a_writer_discoverable_empty_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "MyNovel"

            package = create_novel_package(
                "The Long Way Home",
                novel_root=root,
            )

            self.assertEqual(package, root / "The-Long-Way-Home")
            self.assertEqual(list_novel_packages(root), [package])
            self.assertTrue((package / "Manuscript" / "Chapters").is_dir())
            self.assertEqual(list_scene_chapters(package), [])
            story_bible = json.loads(
                (package / "story_bible.json").read_text(encoding="utf-8")
            )
            self.assertEqual(story_bible["title"], "The Long Way Home")
            self.assertEqual(story_bible["story_format_version"], "1.0")
            self.assertEqual(story_bible["premise"], "")
            self.assertEqual(story_bible["canon_rules"], [])
            self.assertEqual(story_bible["character_cards"], [])

    def test_uses_custom_folder_name_without_changing_novel_title(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = create_novel_package(
                "The Story Title",
                "my-custom-folder",
                novel_root=temporary,
            )
            story_bible = json.loads(
                (package / "story_bible.json").read_text(encoding="utf-8")
            )
            self.assertEqual(package.name, "my-custom-folder")
            self.assertEqual(story_bible["title"], "The Story Title")

    def test_refuses_to_overwrite_an_existing_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            existing = root / "The-Long-Way-Home"
            existing.mkdir()
            marker = existing / "keep.txt"
            marker.write_text("must remain", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                create_novel_package(
                    "The Long Way Home",
                    novel_root=root,
                )

            self.assertEqual(marker.read_text(encoding="utf-8"), "must remain")
            self.assertFalse((existing / "story_bible.json").exists())

    def test_rejects_path_traversal_and_empty_titles(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                create_novel_package("A title", "../outside", novel_root=temporary)
            with self.assertRaises(ValueError):
                create_novel_package("   ", novel_root=temporary)
            with self.assertRaises(ValueError):
                create_novel_package("A title", ".", novel_root=temporary)


if __name__ == "__main__":
    unittest.main()
