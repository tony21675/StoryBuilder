import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import storybuilder as storybuilder_app


class CurrentStatePersistenceTests(unittest.TestCase):
    def make_app(self, path):
        self.package = SimpleNamespace(path=path, save=Mock())
        self.app = SimpleNamespace(
            package=self.package,
            dirty=False,
            _apply_state_edits=Mock(return_value=True),
            _update_path_label=Mock(),
            _chat=Mock(),
            _show_copyable_error=Mock(),
        )
        return self.app

    def test_apply_state_edits_saves_package_and_reports_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.make_app(Path(tmp))

            storybuilder_app.StoryBuilderApp._apply_state_edits_and_save(app)

            self.package.save.assert_called_once_with()
            app._chat.assert_called_once_with(
                "Builder", "Current State edits applied and saved."
            )
            app._show_copyable_error.assert_not_called()
            app._update_path_label.assert_called_once_with()
            self.assertFalse(app.dirty)

    def test_save_failure_keeps_state_dirty_and_reports_restart_risk(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.make_app(Path(tmp))
            self.package.save.side_effect = OSError("disk full")

            storybuilder_app.StoryBuilderApp._apply_state_edits_and_save(app)

            self.package.save.assert_called_once_with()
            self.assertTrue(app.dirty)
            app._show_copyable_error.assert_called_once()
            title, message = app._show_copyable_error.call_args.args
            self.assertEqual(title, "Apply State Edits")
            self.assertIn("could not be saved to disk", message)
            self.assertIn("disk full", message)
            app._chat.assert_not_called()

    def test_unsaved_package_is_not_misreported_as_saved(self):
        app = self.make_app(None)

        storybuilder_app.StoryBuilderApp._apply_state_edits_and_save(app)

        self.package.save.assert_not_called()
        self.assertTrue(app.dirty)
        title, message = app._show_copyable_error.call_args.args
        self.assertEqual(title, "Apply State Edits")
        self.assertIn("Use Save / Save As", message)

    def test_cancelled_state_edit_does_not_save(self):
        app = self.make_app(Path("/tmp/test-story"))
        app._apply_state_edits.return_value = False

        storybuilder_app.StoryBuilderApp._apply_state_edits_and_save(app)

        self.package.save.assert_not_called()
        app._update_path_label.assert_not_called()
        app._chat.assert_not_called()
        app._show_copyable_error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
