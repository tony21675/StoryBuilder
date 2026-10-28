import unittest
from pathlib import Path
from unittest.mock import patch

from builder.novel_sync import NovelSyncError
from storybuilder import StoryBuilderApp


class FakePackage:
    def __init__(self, events, path=Path("/tmp/novel")):
        self.path = path
        self.events = events

    def save(self):
        self.events.append("save_novel")


class FakeEngine:
    def __init__(self, events):
        self.events = events

    def stop(self):
        self.events.append("stop_writer")


class FakeStatus:
    def configure(self, **kwargs):
        self.text = kwargs.get("text", "")


def make_close_app(events):
    app = StoryBuilderApp.__new__(StoryBuilderApp)
    app._closing = False
    app.package = FakePackage(events)
    app.dirty = True
    app.writer_notes_update_in_progress = False
    app.writer_engine = FakeEngine(events)
    app.writer_status = FakeStatus()
    app._previous_sigint_handler = None
    app._confirm_discard_unaccepted_writer_text = lambda: True
    app._apply_all_edits = lambda: events.append("apply_ui_edits") or True
    app._update_path_label = lambda: events.append("update_path_label")
    app._chat = lambda who, message: events.append(("chat", message))
    app._show_copyable_error = lambda title, message, **kwargs: events.append(("error", title, message))
    app._ask_yes_no = lambda title, message: events.append(("confirm", title, message)) or True
    app.destroy = lambda: events.append("destroy")
    return app


class TerminalShutdownTests(unittest.TestCase):
    def test_sigint_handler_only_marks_shutdown_pending(self):
        app = StoryBuilderApp.__new__(StoryBuilderApp)
        app._terminal_interrupt_pending = False

        StoryBuilderApp._on_terminal_interrupt_signal(app, 2, None)

        self.assertTrue(app._terminal_interrupt_pending)

    def test_terminal_shutdown_waits_for_active_task_then_routes_to_close_flow(self):
        app = StoryBuilderApp.__new__(StoryBuilderApp)
        app._terminal_interrupt_pending = True
        app.writer_status = FakeStatus()
        app._terminal_shutdown_is_busy = lambda: True
        app.winfo_exists = lambda: True
        scheduled = []
        app.after = lambda delay, callback: scheduled.append((delay, callback))
        close_calls = []
        app._close_and_sync_app = lambda: close_calls.append(True)

        StoryBuilderApp._poll_terminal_interrupt(app)

        self.assertTrue(app._terminal_interrupt_pending)
        self.assertEqual(close_calls, [])
        self.assertIn("Waiting for the active task", app.writer_status.text)
        self.assertEqual(len(scheduled), 1)
        self.assertEqual(scheduled[0][0], 250)

    @patch("storybuilder.messagebox.showinfo")
    @patch("storybuilder.sync_storybuilder_repository")
    @patch("storybuilder.sync_novel_repository")
    @patch("storybuilder.novel_repo_root")
    def test_close_saves_and_syncs_novel_before_app_code(
        self, mock_repo_root, mock_sync_novel, mock_sync_app, mock_root, mock_info
    ):
        events = []
        app = make_close_app(events)
        mock_root.return_value = Path("/tmp/novel")
        mock_sync_novel.side_effect = lambda path: events.append("sync_novel") or "Novel synchronized successfully."
        mock_sync_app.side_effect = lambda path: events.append("sync_app")
        mock_root.return_value = Path("/tmp/novel")

        # Use deterministic sync behavior without depending on a real Git checkout.
        mock_repo_root.return_value = Path("/tmp/novel")

        StoryBuilderApp._close_and_sync_app(app)

        self.assertLess(events.index("save_novel"), events.index("sync_novel"))
        self.assertLess(events.index("sync_novel"), events.index("sync_app"))
        self.assertLess(events.index("sync_app"), events.index("stop_writer"))
        self.assertLess(events.index("stop_writer"), events.index("destroy"))
        self.assertTrue(any(isinstance(event, tuple) and event[0] == "chat" for event in events))
        mock_sync_novel.assert_called_once_with(Path("/tmp/novel"))
        mock_sync_app.assert_called_once()
        mock_info.assert_called_once()

    @patch("storybuilder.sync_storybuilder_repository")
    @patch("storybuilder.sync_novel_repository", side_effect=NovelSyncError("remote conflict"))
    @patch("storybuilder.novel_repo_root", return_value=Path("/tmp/novel"))
    def test_novel_sync_failure_keeps_app_open_and_does_not_sync_app_code(
        self, _mock_root, _mock_sync_novel, mock_sync_app
    ):
        events = []
        app = make_close_app(events)

        StoryBuilderApp._close_and_sync_app(app)

        self.assertFalse(app._closing)
        self.assertNotIn("sync_app", events)
        self.assertNotIn("stop_writer", events)
        self.assertNotIn("destroy", events)
        self.assertTrue(any(
            isinstance(event, tuple) and event[0] == "error" and "remote conflict" in event[2]
            for event in events
        ))
        mock_sync_app.assert_not_called()

    @patch("storybuilder.messagebox.showinfo")
    @patch("storybuilder.sync_storybuilder_repository")
    @patch("storybuilder.sync_novel_repository")
    @patch("storybuilder.novel_repo_root", return_value=None)
    def test_non_git_novel_requires_explicit_close_confirmation(
        self, _mock_root, mock_sync_novel, mock_sync_app, _mock_info
    ):
        events = []
        app = make_close_app(events)

        StoryBuilderApp._close_and_sync_app(app)

        self.assertTrue(any(
            isinstance(event, tuple) and event[0] == "confirm"
            and "not connected to a Git repository" in event[2]
            for event in events
        ))
        mock_sync_novel.assert_not_called()
        mock_sync_app.assert_called_once()
        self.assertIn("not synchronized", next(
            event[1] for event in events
            if isinstance(event, tuple) and event[0] == "chat"
        ).lower())


if __name__ == "__main__":
    unittest.main()
