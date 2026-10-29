import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from builder.novel_creator import create_novel_package
from builder.story_bible_reader import load_story_bible
from story_bible_app import StoryBibleApp


class FakeStatus:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value


class FakeEditor:
    def __init__(self, content):
        self.content = content

    def get(self, _start, _end):
        return self.content


class StoryBibleCanonRulesActionTests(unittest.TestCase):
    def test_save_splits_rules_by_line_and_ignores_blank_lines(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = create_novel_package("A Novel", novel_root=temporary)
            app = object.__new__(StoryBibleApp)
            app._canon_rules_editing = True
            app._loaded_novel_path = Path(package)
            app._canon_rules_editor_text = FakeEditor(
                "  Keep the crew together.  \n\nNo faster-than-light travel.\n   \n"
            )
            app.viewer_status_var = FakeStatus()
            app._format_canon_rules_preview = Mock(return_value="1. rule")
            app._set_story_bible_text = Mock()
            app._set_premise_text = Mock()
            app._set_setting_text = Mock()
            app._set_canon_rules_text = Mock()
            app._finish_canon_rules_edit = Mock()

            app.save_canon_rules()

            saved = load_story_bible(package)
            self.assertEqual(
                saved["canon_rules"],
                ["Keep the crew together.", "No faster-than-light travel."],
            )
            self.assertEqual(app._loaded_canon_rules, saved["canon_rules"])
            self.assertIn("Saved Canon Rules only", app.viewer_status_var.value)
            app._finish_canon_rules_edit.assert_called_once()

    def test_cancel_does_not_save_canon_rules(self):
        app = object.__new__(StoryBibleApp)
        app._canon_rules_editing = True
        app.viewer_status_var = FakeStatus()
        app._finish_canon_rules_edit = Mock()

        with patch("story_bible_app.save_story_bible_canon_rules") as save:
            app.cancel_canon_rules_edit()

        save.assert_not_called()
        app._finish_canon_rules_edit.assert_called_once()
        self.assertIn("no file changes", app.viewer_status_var.value)


if __name__ == "__main__":
    unittest.main()
