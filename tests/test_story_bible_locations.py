import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from builder.location_editor import LocationEditorWindow
from builder.location_manager import LocationManagerWindow
from builder.novel_creator import create_novel_package
from builder.story_bible_reader import (
    load_story_bible,
    load_story_bible_locations,
    save_story_bible_locations,
)


class FakeValue:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class FakeText:
    def __init__(self, value):
        self.value = value

    def get(self, *_args):
        return self.value


class FakeListbox:
    def __init__(self, index=0):
        self.index = index

    def curselection(self):
        return (self.index,)


class LocationStorageTests(unittest.TestCase):
    def make_package(self):
        temporary = tempfile.TemporaryDirectory()
        package = create_novel_package("A Novel", novel_root=temporary.name)
        path = Path(package) / "story_bible.json"
        data = load_story_bible(package)
        data.update({
            "premise": "Premise stays.",
            "setting": "Setting stays.",
            "canon_rules": ["Rule stays."],
            "character_cards": [{"name": "Mara"}],
            "locations": {
                "Mars Outpost": {
                    "type": "Research Station",
                    "description": "A remote science facility.",
                    "custom_notes": {"keep": ["nested", "data"]},
                },
                "Earth": "The original home world.",
            },
            "other_data": {"keep": True},
        })
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return temporary, package, data

    def test_load_and_save_locations_changes_only_that_object(self):
        temporary, package, original = self.make_package()
        try:
            self.assertEqual(load_story_bible_locations(package), original["locations"])
            updated = {"Moon": {"type": "Relay", "climate": "Airless"}}
            save_story_bible_locations(package, updated)
            saved = load_story_bible(package)
            self.assertEqual(saved["locations"], updated)
            for field in ("premise", "setting", "canon_rules", "character_cards", "other_data"):
                self.assertEqual(saved[field], original[field])
        finally:
            temporary.cleanup()

    def test_rejects_invalid_location_container_and_non_json_values(self):
        temporary, package, original = self.make_package()
        try:
            path = Path(package) / "story_bible.json"
            original["locations"] = ["not", "a", "mapping"]
            path.write_text(json.dumps(original, indent=2) + "\n", encoding="utf-8")
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                load_story_bible_locations(package)
            with self.assertRaises(ValueError):
                save_story_bible_locations(package, {"Invalid": {"value": object()}})
            self.assertEqual(path.read_bytes(), before)
        finally:
            temporary.cleanup()

    def test_empty_locations_are_supported(self):
        temporary, package, _original = self.make_package()
        try:
            save_story_bible_locations(package, {})
            self.assertEqual(load_story_bible_locations(package), {})
        finally:
            temporary.cleanup()


class LocationManagerActionTests(unittest.TestCase):
    def make_manager(self, package, locations):
        manager = object.__new__(LocationManagerWindow)
        manager.novel_path = Path(package)
        manager.locations = dict(locations)
        manager.editing_name = None
        manager.editor_window = object()
        manager.window = object()
        manager.listbox = FakeListbox(index=1)
        manager.on_saved = Mock()
        manager.on_close = Mock()
        manager._finish_editor = Mock()
        manager._refresh = Mock()
        return manager

    def test_add_location_with_optional_fields_left_blank(self):
        temporary, package, original = LocationStorageTests().make_package()
        try:
            manager = self.make_manager(package, original["locations"])
            manager.save_location("Lunar Relay", {"type": "Communications Hub"})
            saved = load_story_bible(package)
            self.assertEqual(saved["locations"]["Lunar Relay"], {"type": "Communications Hub"})
            self.assertEqual(saved["locations"]["Mars Outpost"], original["locations"]["Mars Outpost"])
            self.assertEqual(saved["locations"]["Earth"], "The original home world.")
            manager.on_saved.assert_called_once()
            manager._finish_editor.assert_called_once()
            manager._refresh.assert_called_once_with("Lunar Relay")
        finally:
            temporary.cleanup()

    def test_rename_preserves_existing_unknown_nested_values(self):
        temporary, package, original = LocationStorageTests().make_package()
        try:
            manager = self.make_manager(package, original["locations"])
            manager.editing_name = "Mars Outpost"
            revised = dict(original["locations"]["Mars Outpost"])
            revised["description"] = "Revised facility details."
            manager.save_location("Mars Research Base", revised)
            saved = load_story_bible(package)
            self.assertNotIn("Mars Outpost", saved["locations"])
            self.assertEqual(
                saved["locations"]["Mars Research Base"]["custom_notes"],
                {"keep": ["nested", "data"]},
            )
        finally:
            temporary.cleanup()

    def test_duplicate_name_is_rejected_without_writing(self):
        temporary, package, original = LocationStorageTests().make_package()
        try:
            manager = self.make_manager(package, original["locations"])
            with patch("builder.location_manager.messagebox.showerror") as show_error:
                manager.save_location("earth", {})
            self.assertEqual(load_story_bible(package)["locations"], original["locations"])
            show_error.assert_called_once()
            manager._finish_editor.assert_not_called()
        finally:
            temporary.cleanup()

    def test_remove_deletes_only_one_location_entry(self):
        temporary, package, original = LocationStorageTests().make_package()
        try:
            manager = self.make_manager(package, original["locations"])
            with patch("builder.location_manager.messagebox.askyesno", return_value=True):
                manager.remove_location()
            saved = load_story_bible(package)
            self.assertNotIn("Earth", saved["locations"])
            self.assertEqual(saved["locations"]["Mars Outpost"], original["locations"]["Mars Outpost"])
            self.assertEqual(saved["premise"], "Premise stays.")
            manager.on_saved.assert_called_once()
            manager._refresh.assert_called_once_with("Mars Outpost")
        finally:
            temporary.cleanup()


class LocationEditorBuildTests(unittest.TestCase):
    def make_editor(self, name, original=None, entries=None, texts=None, custom=None):
        editor = object.__new__(LocationEditorWindow)
        editor.original = dict(original or {})
        editor.name_var = FakeValue(name)
        editor.entry_vars = {
            key: FakeValue(value) for key, value in (entries or {}).items()
        }
        editor.text_widgets = {
            key: FakeText(value) for key, value in (texts or {}).items()
        }
        editor.custom_field_rows = custom or []
        return editor

    def test_only_name_is_required_and_optional_fields_can_be_blank(self):
        editor = self.make_editor(
            "  Hidden Valley  ",
            entries={"type": "", "geography": "", "climate": ""},
            texts={"description": "", "notable_details": ""},
        )
        name, details = editor.build_location()
        self.assertEqual(name, "Hidden Valley")
        self.assertEqual(details, {})

    def test_existing_unknown_nested_data_is_preserved_when_untouched(self):
        original = {
            "description": "Quiet settlement.",
            "type": "Village",
            "custom": {"population_history": [12, 18]},
        }
        editor = self.make_editor(
            "Village",
            original=original,
            entries={"type": "Village", "geography": "", "climate": ""},
            texts={"description": "Quiet settlement.", "notable_details": ""},
            custom=[{
                "original_key": "custom",
                "key": FakeValue("custom"),
                "value": FakeValue(""),
                "nested": True,
                "original_value": {"population_history": [12, 18]},
                "removed": False,
            }],
        )
        _name, details = editor.build_location()
        self.assertEqual(details, original)


if __name__ == "__main__":
    unittest.main()
