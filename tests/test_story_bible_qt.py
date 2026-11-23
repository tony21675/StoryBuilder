from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import story_bible_qt
from builder.novel_creator import create_novel_package
from builder.qt_story_bible_editors import CharacterCardEditorDialog, LocationEditorDialog


class StoryBibleQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.previous_root = story_bible_qt.NOVEL_ROOT
        story_bible_qt.NOVEL_ROOT = self.root
        self.package = create_novel_package(
            "Qt Migration Test",
            novel_root=self.root,
        )
        self.window = story_bible_qt.StoryBibleQtWindow()

    def tearDown(self):
        self.window.close()
        story_bible_qt.NOVEL_ROOT = self.previous_root
        self.temp_dir.cleanup()

    def test_window_lists_and_loads_existing_story_bible(self):
        self.assertEqual(self.window.novel_selector.count(), 1)
        self.window.load_selected_story_bible()
        self.assertEqual(self.window.loaded_novel_path, self.package)
        self.assertIn('"title": "Qt Migration Test"', self.window.json_preview.toPlainText())

    def test_create_novel_uses_selected_documents_library_root(self):
        self.window.title_input.setText("A New Qt Novel")
        self.window.create_novel()
        created = self.root / "A-New-Qt-Novel"
        self.assertTrue((created / "story_bible.json").is_file())
        self.assertTrue((created / "Manuscript" / "Chapters").is_dir())

    def test_field_save_changes_only_selected_story_bible_field(self):
        bible_path = self.package / "story_bible.json"
        data = json.loads(bible_path.read_text(encoding="utf-8"))
        data["custom_package_data"] = {"keep": [1, 2, 3]}
        bible_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        self.window.load_selected_story_bible()
        self.window._save_text_field("premise", "A premise saved by the Qt editor.")

        saved = json.loads(bible_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["premise"], "A premise saved by the Qt editor.")
        self.assertEqual(saved["custom_package_data"], {"keep": [1, 2, 3]})
        self.assertEqual(saved["setting"], "")

    def test_character_editor_preserves_unknown_and_nested_fields(self):
        existing = {
            "name": "Mara",
            "age": 31,
            "appearance": {"hair": "dark", "custom_detail": {"kept": True}},
            "relationships": {"Noah": "friend"},
            "future_custom_data": {"tags": ["one", "two"]},
        }
        dialog = CharacterCardEditorDialog(existing=existing)
        dialog.line_fields["name"].setText("Mara Vale")
        result = dialog.build_card()

        self.assertEqual(result["name"], "Mara Vale")
        self.assertEqual(result["age"], 31)
        self.assertEqual(result["appearance"]["custom_detail"], {"kept": True})
        self.assertEqual(result["future_custom_data"], {"tags": ["one", "two"]})
        self.assertEqual(result["relationships"]["Noah"], "friend")
        dialog.close()

    def test_character_editor_allows_optional_fields_to_remain_blank(self):
        dialog = CharacterCardEditorDialog(existing={"name": "New Character"})
        result = dialog.build_card()
        self.assertEqual(result["name"], "New Character")
        self.assertNotIn("age", result)
        dialog.close()

    def test_location_editor_preserves_unknown_nested_details(self):
        existing = {
            "type": "town",
            "description": "A quiet place.",
            "custom_detail": {"roads": ["north", "south"]},
        }
        dialog = LocationEditorDialog(existing=existing, name="Willow Bay")
        dialog.name_edit.setText("Willow Bay Updated")
        name, result = dialog.build_location()

        self.assertEqual(name, "Willow Bay Updated")
        self.assertEqual(result["type"], "town")
        self.assertEqual(result["custom_detail"], {"roads": ["north", "south"]})
        dialog.close()

    def test_cancelled_editor_does_not_write_story_bible(self):
        bible_path = self.package / "story_bible.json"
        before = bible_path.read_bytes()
        dialog = CharacterCardEditorDialog(existing={"name": "No Save"})
        dialog.reject()
        self.assertEqual(bible_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
