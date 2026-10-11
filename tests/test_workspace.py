import tempfile
import unittest
from pathlib import Path

from builder.workspace import find_novel_packages


class FindNovelPackagesTests(unittest.TestCase):
    def test_finds_legacy_root_level_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "story_bible.json").write_text("{}", encoding="utf-8")
            child = root / "Another_Novel"
            child.mkdir()
            (child / "story_bible.json").write_text("{}", encoding="utf-8")

            self.assertEqual(find_novel_packages(root), [root])

    def test_finds_immediate_child_novel_folders_in_name_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder_name in ("Zulu_Novel", "Taken_at_Dusk", "Alpha_Novel", "Not_A_Novel"):
                folder = root / folder_name
                folder.mkdir()
                if folder_name != "Not_A_Novel":
                    (folder / "story_bible.json").write_text("{}", encoding="utf-8")

            self.assertEqual(
                [path.name for path in find_novel_packages(root)],
                ["Alpha_Novel", "Taken_at_Dusk", "Zulu_Novel"],
            )

    def test_does_not_search_grandchildren(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "Outer" / "Nested_Novel"
            nested.mkdir(parents=True)
            (nested / "story_bible.json").write_text("{}", encoding="utf-8")

            self.assertEqual(find_novel_packages(root), [])

    def test_missing_library_returns_no_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Does_Not_Exist"
            self.assertEqual(find_novel_packages(root), [])


if __name__ == "__main__":
    unittest.main()
