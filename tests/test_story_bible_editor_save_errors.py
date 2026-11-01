from pathlib import Path
import unittest
from unittest.mock import patch

from story_bible_app import StoryBibleApp


class FakeStatus:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value


class FakeText:
    def __init__(self, value):
        self.value = value

    def get(self, *_args):
        return self.value


class StoryBibleEditorSaveErrorTests(unittest.TestCase):
    def make_app(self):
        app = object.__new__(StoryBibleApp)
        app._loaded_novel_path = Path("/tmp/story-bible-save-error-test")
        app.viewer_status_var = FakeStatus()
        return app

    def assert_error_dialog(self, showerror, parent, message):
        showerror.assert_called_once()
        self.assertIs(showerror.call_args.kwargs["parent"], parent)
        self.assertIn(message, showerror.call_args.args[1])
        
    def test_premise_save_failure_is_shown_in_premise_editor(self):
        app = self.make_app()
        editor = object()
        app._premise_editing = True
        app._premise_editor_window = editor
        app._premise_editor_text = FakeText("Updated premise.")

        with (
            patch("story_bible_app.save_story_bible_premise", side_effect=OSError("disk full")),
            patch("story_bible_app.messagebox.showerror") as showerror,
        ):
            app.save_premise()

        self.assert_error_dialog(showerror, editor, "disk full")
        self.assertIn("disk full", app.viewer_status_var.value)

    def test_setting_save_failure_is_shown_in_setting_editor(self):
        app = self.make_app()
        editor = object()
        app._setting_editing = True
        app._setting_editor_window = editor
        app._setting_editor_text = FakeText("Updated setting.")

        with (
            patch(
                "story_bible_app.save_story_bible_text_field",
                side_effect=OSError("disk full"),
            ),
            patch("story_bible_app.messagebox.showerror") as showerror,
        ):
            app.save_setting()

        self.assert_error_dialog(showerror, editor, "disk full")
        self.assertIn("disk full", app.viewer_status_var.value)

    def test_canon_rules_save_failure_is_shown_in_canon_rules_editor(self):
        app = self.make_app()
        editor = object()
        app._canon_rules_editing = True
        app._canon_rules_editor_window = editor
        app._canon_rules_editor_text = FakeText("Rule one\\nRule two")

        with (
            patch(
                "story_bible_app.save_story_bible_canon_rules",
                side_effect=OSError("disk full"),
            ),
            patch("story_bible_app.messagebox.showerror") as showerror,
        ):
            app.save_canon_rules()

        self.assert_error_dialog(showerror, editor, "disk full")
        self.assertIn("disk full", app.viewer_status_var.value)


if __name__ == "__main__":
    unittest.main()
