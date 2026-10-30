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


class StoryBibleCharacterCardActionTests(unittest.TestCase):
    def make_app(self, package, *, name, role, description, edit_index=None):
        app = object.__new__(StoryBibleApp)
        app._character_card_editor_window = object()
        app._loaded_novel_path = Path(package)
        app._loaded_character_cards = [
            "Older plain-text card.",
            {
                "name": "Existing",
                "role": "Scout",
                "description": "Original details.",
                "custom_metadata": {"keep": True},
            },
        ]
        app._character_card_name_var = FakeValue(name)
        app._character_card_role_var = FakeValue(role)
        app._character_card_editor = FakeEditor(
            {"name": name, "role": role, "description": description}
        )
        app._character_card_edit_index = edit_index
        app._character_card_filename = None
        app.viewer_status_var = FakeStatus()
        app._load_character_cards_from_data = Mock(
            side_effect=lambda data: setattr(
                app, "_loaded_character_cards", list(data.get("character_cards", []))
            )
        )
        app._set_story_bible_text = Mock()
        app._refresh_character_cards_manager = Mock()
        app._finish_character_card_editor = Mock()
        return app

    def test_add_card_creates_a_json_file_and_preserves_legacy_text_note(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = create_novel_package("A Novel", novel_root=temporary)
            bible_path = Path(package) / "story_bible.json"
            import json
            data = load_story_bible(package)
            data["character_cards"] = ["Older plain-text card."]
            bible_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            app = self.make_app(
                package,
                name="Mara",
                role="Pilot",
                description="A careful flyer.",
            )
            app._loaded_character_cards = ["Older plain-text card."]

            app.save_character_card()

            saved = load_story_bible(package)["character_cards"]
            self.assertEqual(saved[0], "Older plain-text card.")
            self.assertEqual(saved[-1], "Mara.json")
            self.assertEqual(
                load_story_bible_character_card(package, "Mara.json"),
                {
                    "name": "Mara",
                    "role": "Pilot",
                    "description": "A careful flyer.",
                },
            )
            app._finish_character_card_editor.assert_called_once()
            app._refresh_character_cards_manager.assert_called_once_with(1)
            self.assertIn("Created Mara.json", app.viewer_status_var.value)

    def test_edit_card_preserves_metadata_and_all_other_story_bible_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = create_novel_package("A Novel", novel_root=temporary)
            original = load_story_bible(package)
            original["premise"] = "Premise stays."
            original["setting"] = "Setting stays."
            original["canon_rules"] = ["Rule stays."]
            original["custom_field"] = {"nested": "untouched"}
            from pathlib import Path
            bible_path = Path(package) / "story_bible.json"
            import json
            bible_path.write_text(json.dumps(original, indent=2) + "\n", encoding="utf-8")

            app = self.make_app(
                package,
                name="Existing Updated",
                role="Navigator",
                description="Revised details.",
                edit_index=1,
            )

            app.save_character_card()

            saved = load_story_bible(package)
            self.assertEqual(saved["premise"], "Premise stays.")
            self.assertEqual(saved["setting"], "Setting stays.")
            self.assertEqual(saved["canon_rules"], ["Rule stays."])
            self.assertEqual(saved["custom_field"], {"nested": "untouched"})
            card = saved["character_cards"][1]
            self.assertEqual(card["name"], "Existing Updated")
            self.assertEqual(card["role"], "Navigator")
            self.assertEqual(card["description"], "Revised details.")
            self.assertEqual(card["custom_metadata"], {"keep": True})

    def test_blank_name_does_not_save_or_close_the_editor(self):
        app = self.make_app(
            "/not-used", name="  ", role="Pilot", description="Description."
        )
        with patch("story_bible_app.save_story_bible_character_cards") as save:
            app.save_character_card()

        save.assert_not_called()
        app._finish_character_card_editor.assert_not_called()
        self.assertIn("Enter a name", app.viewer_status_var.value)

    def test_cancel_does_not_call_character_card_save(self):
        app = object.__new__(StoryBibleApp)
        app._character_card_editor_window = object()
        app.viewer_status_var = FakeStatus()
        app._finish_character_card_editor = Mock()

        with patch("story_bible_app.save_story_bible_character_cards") as save:
            app.cancel_character_card_edit()

        save.assert_not_called()
        app._finish_character_card_editor.assert_called_once()
        self.assertIn("no file changes", app.viewer_status_var.value)


if __name__ == "__main__":
    unittest.main()
