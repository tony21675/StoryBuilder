import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from story_bible_app import StoryBibleApp


class FakeCombo:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class FakeStatus:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value


class StoryBibleSyncActionTests(unittest.TestCase):
    def make_app(self, label, package):
        app = object.__new__(StoryBibleApp)
        app._sync_in_progress = False
        app._premise_editing = False
        app._setting_editing = False
        app.novel_combo = FakeCombo(label)
        app._novel_paths = {label: Path(package)}
        app.viewer_status_var = FakeStatus()
        app._show_copyable_dialog = Mock(return_value="Cancel")
        return app

    def test_local_test_fixture_is_never_sent_to_git_sync(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = root / "Story-Bible-Save-Test"
            fixture.mkdir()
            (fixture / "story_bible.json").write_text("{}\n", encoding="utf-8")
            label = f"{fixture.name}  [{fixture}]"
            app = self.make_app(label, fixture)

            with (
                patch("story_bible_app.NOVEL_ROOT", root),
                patch("story_bible_app.inspect_novel_repository") as inspect,
                patch("story_bible_app.sync_novel_repository") as sync,
            ):
                app.sync_selected_novel_to_github()

            inspect.assert_not_called()
            sync.assert_not_called()
            self.assertIn("local-only test package", app.viewer_status_var.value)
            app._show_copyable_dialog.assert_called_once()

    def test_cancelled_confirmation_does_not_start_sync(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "The-Long-Way-Home"
            package.mkdir()
            (package / "story_bible.json").write_text("{}\n", encoding="utf-8")
            label = f"{package.name}  [{package}]"
            app = self.make_app(label, package)
            preview = SimpleNamespace(
                repository=package.resolve(),
                branch="main",
                remote_url="https://github.com/example/novel.git",
                local_commits=("abc123 Update draft",),
                changed_files=("story_bible.json",),
            )

            with (
                patch("story_bible_app.inspect_novel_repository", return_value=preview),
                patch("story_bible_app.sync_novel_repository") as sync,
            ):
                app.sync_selected_novel_to_github()

            sync.assert_not_called()
            self.assertEqual(
                app.viewer_status_var.value,
                "Novel sync cancelled; no Git operation started.",
            )
            title, message = app._show_copyable_dialog.call_args.args[:2]
            self.assertEqual(title, "Confirm novel sync")
            self.assertIn("https://github.com/example/novel.git", message)
            self.assertIn("story_bible.json", message)
            self.assertIn("Proceed with syncing this novel?", message)


if __name__ == "__main__":
    unittest.main()
