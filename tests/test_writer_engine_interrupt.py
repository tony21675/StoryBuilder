import signal
import threading
import unittest

from builder.writer_engine import GenerationInterrupted, WriterEngine


class FakeChild:
    def __init__(self):
        self.killed_with = None
        self.terminated = None

    def kill(self, sig):
        self.killed_with = sig

    def terminate(self, force=False):
        self.terminated = force


class WriterEngineInterruptTests(unittest.TestCase):
    def test_interrupt_does_not_wait_for_generation_lock(self):
        engine = WriterEngine()
        child = FakeChild()
        engine.child = child
        engine._active_generation_child = child
        engine.lock.acquire()
        result = []
        thread = threading.Thread(
            target=lambda: result.append(engine.interrupt_generation()),
            daemon=True,
        )

        try:
            thread.start()
            thread.join(timeout=1)
            completed_without_generation_lock = not thread.is_alive()
        finally:
            engine.lock.release()
            thread.join(timeout=1)

        self.assertTrue(completed_without_generation_lock)
        self.assertEqual(result, [True])
        self.assertEqual(child.killed_with, signal.SIGKILL)
        self.assertIsNone(engine.child)
        self.assertTrue(engine._cancel_generation_requested)

    def test_stop_requested_before_generation_worker_starts_is_handled(self):
        engine = WriterEngine()
        engine._cancel_generation_requested = True

        with self.assertRaises(GenerationInterrupted):
            engine.generate("Write a short passage.")

        self.assertFalse(engine._cancel_generation_requested)


if __name__ == "__main__":
    unittest.main()
