import tempfile
import unittest
from pathlib import Path

from builder.manuscript_assembly import assemble_chapter, assemble_finished_novel
from builder.odt_document import read_document, save_document


class ManuscriptAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.novel_path = Path(self.temp_dir.name) / "The-Long-Way-Home"
        self.chapters_path = self.novel_path / "Manuscript" / "Chapters"
        self.chapters_path.mkdir(parents=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _chapter_dir(self, number):
        path = self.chapters_path / f"Chapter_{number:02d}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_scene(self, chapter, scene, text, suffix=".odt"):
        path = self._chapter_dir(chapter) / (
            f"Chapter_{chapter:02d}_Section_{scene:02d}{suffix}"
        )
        if suffix == ".odt":
            save_document(path, text)
        else:
            path.write_text(text, encoding="utf-8")
        return path

    def test_assemble_chapter_uses_scene_number_order_and_writes_odt(self):
        self._write_scene(1, 10, "Tenth scene.")
        self._write_scene(1, 2, "Second scene.", suffix=".txt")
        self._write_scene(1, 1, "First scene.")

        target = assemble_chapter(self.novel_path, 1)

        self.assertEqual(
            target,
            self.novel_path / "Manuscript" / "Compiled" / "Chapter_01.odt",
        )
        self.assertTrue(target.is_file())
        assembled = read_document(target)
        self.assertIn("**CHAPTER 1**", assembled)
        self.assertLess(assembled.index("First scene."), assembled.index("Second scene."))
        self.assertLess(assembled.index("Second scene."), assembled.index("Tenth scene."))
        self.assertTrue(
            (self.chapters_path / "Chapter_01" / "Chapter_01_Section_01.odt").is_file()
        )

    def test_assemble_chapter_prefers_odt_when_txt_duplicate_exists(self):
        self._write_scene(1, 1, "ODT version.")
        self._write_scene(1, 1, "Old TXT version.", suffix=".txt")

        target = assemble_chapter(self.novel_path, 1)
        assembled = read_document(target)

        self.assertIn("ODT version.", assembled)
        self.assertNotIn("Old TXT version.", assembled)

    def test_assemble_finished_novel_includes_all_nonempty_chapters_in_order(self):
        self._write_scene(2, 1, "Chapter two prose.")
        self._write_scene(1, 2, "Chapter one, scene two.")
        self._write_scene(1, 1, "Chapter one, scene one.")
        self._chapter_dir(3)  # Empty chapter directories are ignored.

        target = assemble_finished_novel(self.novel_path, "The Long Way Home")

        self.assertEqual(
            target,
            self.novel_path
            / "Manuscript"
            / "Compiled"
            / "The_Long_Way_Home_Complete_Novel.odt",
        )
        assembled = read_document(target)
        self.assertIn("**The Long Way Home**", assembled)
        self.assertLess(assembled.index("CHAPTER 1"), assembled.index("CHAPTER 2"))
        self.assertLess(
            assembled.index("Chapter one, scene one."),
            assembled.index("Chapter one, scene two."),
        )
        self.assertLess(
            assembled.index("Chapter one, scene two."),
            assembled.index("Chapter two prose."),
        )

    def test_assembly_fails_clearly_when_no_saved_scenes_exist(self):
        with self.assertRaisesRegex(ValueError, "No saved scenes"):
            assemble_chapter(self.novel_path, 1)
        with self.assertRaisesRegex(ValueError, "No saved manuscript scenes"):
            assemble_finished_novel(self.novel_path)

    def test_reassembling_refreshes_generated_copy_without_changing_scenes(self):
        source = self._write_scene(1, 1, "Original scene.")
        target = assemble_chapter(self.novel_path, 1)
        save_document(source, "Revised scene.")

        refreshed_target = assemble_chapter(self.novel_path, 1)

        self.assertEqual(target, refreshed_target)
        assembled = read_document(refreshed_target)
        self.assertIn("Revised scene.", assembled)
        self.assertNotIn("Original scene.", assembled)
        self.assertEqual(read_document(source), "Revised scene.")


if __name__ == "__main__":
    unittest.main()
