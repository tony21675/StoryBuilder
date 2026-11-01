import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from builder.novel_creator import create_novel_package
from builder.story_bible_reader import load_story_bible, load_story_bible_character_card
from story_bible_app import StoryBibleApp


class FakeStatus:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value


class FakeValue:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class FakeEditor:
    def __init__(self, content):
        self.content = content

    def build_card(self):
        return dict(self.content)


class FakeListbox:
    def __init__(self, index=0):
        self.index = index
        self.items = []

    def curselection(self):
        return (self.index,)

    def delete(self, *_args):
        self.items = []

    def insert(self, _where, value):
        self.items.append(value)


class StoryBibleCharacterCardFileActionTests(unittest.TestCase):
    def make_package(self):
        temporary = tempfile.TemporaryDirectory()
        package = create_novel_package("A Novel", novel_root=temporary.name)
        card = {
            "name": "Daniel Okafor",
            "role": "Biologist",
            "status": "established",
            "age": 28,
            "personality": ["patient", "analytical"],
            "skills": ["biology", "life-support monitoring"],
            "custom_notes": {"keep": "these details"},
        }
        (Path(package) / "Daniel_Okafor.json").write_text(
            json.dumps(card, indent=2) + "\n", encoding="utf-8"
        )
        data = load_story_bible(package)
        data["character_cards"] = ["Daniel_Okafor.json"]
        data["premise"] = "Premise remains."
        (Path(package) / "story_bible.json").write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )
        return temporary, package, card

    def make_app(self, package):
        app = object.__new__(StoryBibleApp)
        app._loaded_novel_path = Path(package)
        app._loaded_character_cards = ["Daniel_Okafor.json"]
        app._character_cards_manager_listbox = FakeListbox()
        app._character_cards_manager_preview = object()
        app._set_character_card_manager_preview = Mock()
        app._set_character_card_manager_buttons = Mock()
        app.viewer_status_var = FakeStatus()
        return app

    def test_character_name_options_use_referenced_card_files_and_embedded_cards(self):
        temporary, package, _expected = self.make_package()
        try:
            (Path(package) / "Zoe_Bennett.json").write_text(
                json.dumps({"name": "Zoe Bennett", "role": "Communications"}),
                encoding="utf-8",
            )
            app = self.make_app(package)
            app._loaded_character_cards = [
                "Daniel_Okafor.json",
                "Zoe_Bennett.json",
                {"name": "Maya Chen", "role": "Medic"},
                "Older plain-text note.",
                "Missing.json",
            ]

            self.assertEqual(
                app._character_names_for_editor(),
                ["Daniel Okafor", "Maya Chen", "Zoe Bennett"],
            )
        finally:
            temporary.cleanup()

    def test_opening_editor_passes_available_character_names(self):
        temporary, package, _expected = self.make_package()
        try:
            (Path(package) / "Zoe_Bennett.json").write_text(
                json.dumps({"name": "Zoe Bennett"}),
                encoding="utf-8",
            )
            app = self.make_app(package)
            app._loaded_character_cards = [
                "Daniel_Okafor.json",
                "Zoe_Bennett.json",
            ]
            app._character_cards_manager_window = object()
            app._character_card_editor_window = None
            with patch("story_bible_app.CharacterCardEditorWindow") as editor_class:
                editor_class.return_value.window = object()
                app._open_character_card_editor(None)

            editor_class.assert_called_once()
            self.assertEqual(
                editor_class.call_args.kwargs["character_names"],
                ["Daniel Okafor", "Zoe Bennett"],
            )
        finally:
            temporary.cleanup()

    def test_opening_referenced_card_displays_its_full_json_details(self):
        temporary, package, expected = self.make_package()
        try:
            app = self.make_app(package)

            app._character_card_selection_changed()

            preview = app._set_character_card_manager_preview.call_args.args[0]
            self.assertIn("Source file: Daniel_Okafor.json", preview)
            self.assertIn('"personality"', preview)
            self.assertIn('"skills"', preview)
            self.assertIn('"custom_notes"', preview)
            self.assertIn("Daniel Okafor", preview)
            self.assertNotIn("older plain-text character card", preview)
        finally:
            temporary.cleanup()

    def test_edit_selected_passes_referenced_file_data_to_editor(self):
        temporary, package, expected = self.make_package()
        try:
            app = self.make_app(package)
            app._open_character_card_editor = Mock()

            app.edit_character_card()

            app._open_character_card_editor.assert_called_once_with(
                0, expected, "Daniel_Okafor.json"
            )
        finally:
            temporary.cleanup()

    def test_save_edits_referenced_json_and_preserves_other_character_fields(self):
        temporary, package, expected = self.make_package()
        try:
            app = self.make_app(package)
            app._character_card_editor_window = object()
            updated_card = dict(expected)
            updated_card.update(
                {
                    "name": "Daniel Okafor",
                    "role": "Senior Biologist",
                    "description": "A newly updated description.",
                }
            )
            app._character_card_editor = FakeEditor(updated_card)
            app._character_card_edit_index = 0
            app._character_card_filename = "Daniel_Okafor.json"
            app._set_character_cards_preview = Mock()
            app._set_character_cards_controls = Mock()
            app._set_story_bible_text = Mock()
            app._refresh_character_cards_manager = Mock()
            app._finish_character_card_editor = Mock()

            save_succeeded = app.save_character_card()

            self.assertTrue(save_succeeded)
            refreshed_preview = app._set_character_cards_preview.call_args.args[0]
            self.assertIn("Daniel Okafor (Senior Biologist)", refreshed_preview)
            saved = load_story_bible_character_card(package, "Daniel_Okafor.json")
            self.assertEqual(saved["role"], "Senior Biologist")
            self.assertEqual(saved["description"], "A newly updated description.")
            self.assertEqual(saved["personality"], expected["personality"])
            self.assertEqual(saved["skills"], expected["skills"])
            self.assertEqual(saved["custom_notes"], expected["custom_notes"])
            bible = load_story_bible(package)
            self.assertEqual(bible["character_cards"], ["Daniel_Okafor.json"])
            self.assertEqual(bible["premise"], "Premise remains.")
            app._finish_character_card_editor.assert_called_once()
        finally:
            temporary.cleanup()

    def test_file_card_save_failure_is_shown_over_editor_and_keeps_editor_open(self):
        temporary, package, expected = self.make_package()
        try:
            app = self.make_app(package)
            editor_window = object()
            updated_card = dict(expected)
            updated_card["role"] = "Senior Biologist"
            app._character_card_editor_window = editor_window
            app._character_card_editor = FakeEditor(updated_card)
            app._character_card_edit_index = 0
            app._character_card_filename = "Daniel_Okafor.json"
            app._finish_character_card_editor = Mock()

            with (
                patch(
                    "story_bible_app.save_story_bible_character_card_file",
                    side_effect=OSError("permission denied"),
                ),
                patch("story_bible_app.messagebox.showerror") as showerror,
            ):
                save_succeeded = app.save_character_card()

            self.assertFalse(save_succeeded)
            showerror.assert_called_once()
            self.assertIs(showerror.call_args.kwargs["parent"], editor_window)
            self.assertIn("permission denied", showerror.call_args.args[1])
            self.assertIn("permission denied", app.viewer_status_var.value)
            self.assertIs(app._character_card_editor_window, editor_window)
            app._finish_character_card_editor.assert_not_called()
            self.assertEqual(
                load_story_bible_character_card(package, "Daniel_Okafor.json")["role"],
                "Biologist",
            )
        finally:
            temporary.cleanup()

    def test_file_card_save_readback_mismatch_is_reported_and_editor_stays_open(self):
        temporary, package, expected = self.make_package()
        try:
            app = self.make_app(package)
            editor_window = object()
            updated_card = dict(expected)
            updated_card["role"] = "Senior Biologist"
            app._character_card_editor_window = editor_window
            app._character_card_editor = FakeEditor(updated_card)
            app._character_card_edit_index = 0
            app._character_card_filename = "Daniel_Okafor.json"
            app._finish_character_card_editor = Mock()

            with (
                patch(
                    "story_bible_app.save_story_bible_character_card_file",
                    return_value=Path(package) / "Daniel_Okafor.json",
                ),
                patch("story_bible_app.messagebox.showerror") as showerror,
            ):
                app.save_character_card()

            showerror.assert_called_once()
            self.assertIs(showerror.call_args.kwargs["parent"], editor_window)
            self.assertIn("verification failed", showerror.call_args.args[1].lower())
            self.assertIs(app._character_card_editor_window, editor_window)
            app._finish_character_card_editor.assert_not_called()
            self.assertEqual(
                load_story_bible_character_card(package, "Daniel_Okafor.json")["role"],
                "Biologist",
            )
        finally:
            temporary.cleanup()

    def test_remove_drops_file_reference_but_keeps_character_file(self):
        temporary, package, expected = self.make_package()
        try:
            app = self.make_app(package)
            app._character_cards_manager_window = object()
            app._loaded_character_cards = ["Daniel_Okafor.json"]
            app._load_character_cards_from_data = Mock(
                side_effect=lambda data: setattr(
                    app, "_loaded_character_cards", list(data["character_cards"])
                )
            )
            app._set_story_bible_text = Mock()
            app._refresh_character_cards_manager = Mock()

            with patch("story_bible_app.messagebox.askyesno", return_value=True):
                app.remove_character_card()

            self.assertEqual(load_story_bible(package)["character_cards"], [])
            self.assertEqual(
                load_story_bible_character_card(package, "Daniel_Okafor.json"),
                expected,
            )
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
