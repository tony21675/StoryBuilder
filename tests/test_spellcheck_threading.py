import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import storybuilder
from storybuilder import StoryBuilderApp


class DummyText:
    def __init__(self, value):
        self.value = value

    def get(self, *_args):
        return self.value


class ImmediateThread:
    """Run a worker inline so its thread-to-queue behavior is testable."""

    def __init__(self, target, args=(), daemon=None):
        self.target = target
        self.args = args
        self.daemon = daemon

    def start(self):
        self.target(*self.args)


class SpellcheckThreadSafetyTests(unittest.TestCase):
    def test_background_worker_queues_result_without_calling_tk(self):
        widget = DummyText("This has teh typo.")
        results = queue.Queue()

        def forbidden_after(*_args, **_kwargs):
            raise AssertionError("Background spell-check worker called Tkinter")

        app = SimpleNamespace(
            _spellcheck_jobs={},
            spellcheck_available=True,
            _spellcheck_results=results,
            after=forbidden_after,
        )

        with (
            patch.object(storybuilder.threading, "Thread", ImmediateThread),
            patch.object(
                storybuilder.subprocess,
                "run",
                return_value=SimpleNamespace(stdout="teh\n"),
            ),
        ):
            StoryBuilderApp._spellcheck_widget(app, widget)

        queued_widget, source_text, misspelled = results.get_nowait()
        self.assertIs(queued_widget, widget)
        self.assertEqual(source_text, "This has teh typo.")
        self.assertEqual(misspelled, {"teh"})

    def test_main_thread_poller_applies_results_and_reschedules(self):
        widget = DummyText("This has teh typo.")
        results = queue.Queue()
        results.put((widget, "This has teh typo.", {"teh"}))
        applying_threads = []
        scheduled = []

        def apply_result(_widget, _source_text, _misspelled):
            applying_threads.append(threading.get_ident())

        def fake_after(delay_ms, callback):
            scheduled.append((delay_ms, callback))
            return "poll-job"

        app = SimpleNamespace(
            _spellcheck_results=results,
            _spellcheck_poll_job=None,
            _closing=False,
            _apply_spellcheck_result=apply_result,
            after=fake_after,
        )
        caller_thread = threading.get_ident()

        StoryBuilderApp._poll_spellcheck_results(app)

        self.assertEqual(applying_threads, [caller_thread])
        self.assertEqual(len(scheduled), 1)
        self.assertEqual(scheduled[0][0], 100)
        self.assertTrue(callable(scheduled[0][1]))
        self.assertEqual(app._spellcheck_poll_job, "poll-job")
        self.assertTrue(results.empty())


if __name__ == "__main__":
    unittest.main()
