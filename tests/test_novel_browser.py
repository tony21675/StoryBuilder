import tempfile
import unittest
from pathlib import Path

from builder.novel_browser import list_novel_packages, list_scene_chapters, list_scene_files


class NovelBrowserTests(unittest.TestCase):
    def test_lists_only_immediate_novel_packages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_b = root / "Zebra Novel"
            package_a = root / "Alpha Novel"
            nested = root / "container" / "Nested Novel"

            for package in (package_b, package_a, nested):
                package.mkdir(parents=True)
                (package / "story_bible.json").write_text("{}", encoding="utf-8")

            self.assertEqual(
                list_novel_packages(root),
                [package_a, package_b],
            )

    def test_lists_chapters_and_scene_text_in_numeric_order_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            novel = Path(temporary) / "Mars Novel"
            chapter_one = novel / "Manuscript" / "Chapters" / "Chapter_01"
            chapter_two = novel / "Manuscript" / "Chapters" / "Chapter_02"
            chapter_one.mkdir(parents=True)
            chapter_two.mkdir(parents=True)

            for filename in (
                "Chapter_01_Section_10.txt",
                "Chapter_01_Section_02.txt",
                "Chapter_01_Section_01_before_state.json",
                "notes.txt",
            ):
                (chapter_one / filename).write_text(filename, encoding="utf-8")
            (chapter_two / "Chapter_02_Section_03.txt").write_text(
                "scene three", encoding="utf-8"
            )
            (chapter_two / ".gitkeep").write_text("", encoding="utf-8")

            self.assertEqual(list_scene_chapters(novel), [1, 2])
            self.assertEqual(
                [(number, path.name) for number, path in list_scene_files(novel, 1)],
                [
                    (2, "Chapter_01_Section_02.txt"),
                    (10, "Chapter_01_Section_10.txt"),
                ],
            )
            self.assertEqual(
                [(number, path.name) for number, path in list_scene_files(novel, 2)],
                [(3, "Chapter_02_Section_03.txt")],
            )
            self.assertEqual(list_scene_files(novel, 9), [])


if __name__ == "__main__":
    unittest.main()
