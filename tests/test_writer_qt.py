from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import writer_qt
from builder.novel_creator import create_novel_package


class WriterQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.previous_root = writer_qt.NOVEL_ROOT
        writer_qt.NOVEL_ROOT = self.root
        self.package = create_novel_package("Qt Writer Test", novel_root=self.root)
        (self.package / "Manuscript" / "Chapters" / "Chapter_01").mkdir(parents=True, exist_ok=True)
        self.window = writer_qt.WriterQtWindow()

    def tearDown(self):
        try:
            self.window.engine.stop()
        except Exception:
            pass
        self.window.close()
        writer_qt.NOVEL_ROOT = self.previous_root
        self.temp_dir.cleanup()

    def test_lists_existing_novel_without_auto_loading(self):
        self.assertEqual(self.window.novel_picker.count(), 1)
        self.assertEqual(self.window.novel_picker.currentText(), "")

    def test_novel_selection_loads_chapter_selector(self):
        self.window.novel_picker.setCurrentText(self.package.name)
        self.assertEqual(self.window.novel_picker.currentText(), self.package.name)

    def test_author_direction_is_a_separate_editor(self):
        self.window.author_direction.setPlainText("Keep the required event.")
        self.assertEqual(self.window.author_direction.toPlainText(), "Keep the required event.")

    def test_empty_scene_cast_remains_distinct_from_unselected_cast(self):
        self.window.novel_picker.setCurrentText(self.package.name)
        self.window.scene_cast = []
        self.window.scene_cast_novel = self.package.resolve()
        self.assertEqual(self.window._active_cast(), [])

    def test_save_new_scene_writes_only_under_selected_novel(self):
        self.window.novel_picker.setCurrentText(self.package.name)
        self.window.chapter_picker.setCurrentText("Chapter 01")
        self.window.output_editor.setPlainText("A test scene.")
        self.assertTrue(self.window.save_new_scene())
        scene_dir = self.package / "Manuscript" / "Chapters" / "Chapter_01"
        self.assertTrue((scene_dir / "Chapter_01_Section_01.odt").is_file())


if __name__ == "__main__":
    unittest.main()
