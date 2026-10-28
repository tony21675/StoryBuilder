import tempfile
import unittest
from pathlib import Path

from minimal_writer import (
    MinimalWriterApp,
    load_model_for_writing,
    read_text_document,
    save_text_document,
    write_from_prompt,
)


class FakeEngine:
    def __init__(self):
        self.start_calls = []
        self.generate_calls = []

    def start(self, model_path, system_prompt):
        self.start_calls.append((model_path, system_prompt))

    def generate(self, prompt, on_delta=None):
        self.generate_calls.append((prompt, on_delta))
        if on_delta is not None:
            on_delta("Generated ")
            on_delta("text")
        return "Generated text"


class FakeOutputBox:
    def __init__(self, text=""):
        self.text = text

    def get(self, _start, _end):
        return self.text

    def delete(self, _start, _end):
        self.text = ""

    def insert(self, _index, text):
        self.text += text

    def edit_modified(self, _value):
        return None


class FakeRoot:
    def __init__(self):
        self.title_text = ""

    def title(self, value):
        self.title_text = value


class FakeStatus:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value


class MinimalWriterTests(unittest.TestCase):
    def test_model_load_uses_no_app_added_system_prompt(self):
        engine = FakeEngine()
        model_path = Path("/models/example.gguf")

        load_model_for_writing(engine, model_path)

        self.assertEqual(engine.start_calls, [(model_path, "")])

    def test_writing_sends_only_the_author_prompt(self):
        engine = FakeEngine()
        prompt = "Write the next scene.\nKeep going naturally."

        answer = write_from_prompt(engine, prompt)

        self.assertEqual(engine.generate_calls, [(prompt, None)])
        self.assertEqual(answer, "Generated text")

    def test_writing_forwards_streamed_text_chunks(self):
        engine = FakeEngine()
        chunks = []

        answer = write_from_prompt(engine, "Write something.", on_delta=chunks.append)

        self.assertEqual(len(engine.generate_calls), 1)
        self.assertEqual(engine.generate_calls[0][0], "Write something.")
        self.assertTrue(callable(engine.generate_calls[0][1]))
        self.assertEqual(chunks, ["Generated ", "text"])
        self.assertEqual("".join(chunks), answer)

    def test_stopping_keeps_partial_text_and_marks_model_unloaded(self):
        app = MinimalWriterApp.__new__(MinimalWriterApp)
        app.output_box = FakeOutputBox("The sound returned, closer this time.")
        app.current_file = Path("/tmp/draft.txt")
        app.saved_output_text = "Earlier draft."
        app._pre_generation_text = "Earlier draft."
        app._pre_generation_file = app.current_file
        app._pre_generation_saved_text = app.saved_output_text
        app.busy = True
        app.writing = True
        app.stop_requested = True
        app.loaded_model = Path("/models/example.gguf")
        app.status_var = FakeStatus()
        app._update_controls = lambda: None

        app._write_stopped()

        self.assertEqual(app._output_text(), "The sound returned, closer this time.")
        self.assertEqual(app.saved_output_text, "Earlier draft.")
        self.assertIsNone(app.loaded_model)
        self.assertFalse(app.busy)
        self.assertFalse(app.writing)
        self.assertIn("Partial text is kept", app.status_var.value)

    def test_stopping_before_first_chunk_restores_previous_text(self):
        app = MinimalWriterApp.__new__(MinimalWriterApp)
        app.root = FakeRoot()
        app.output_box = FakeOutputBox("")
        app.current_file = Path("/tmp/draft.txt")
        app.saved_output_text = "Earlier draft."
        app._pre_generation_text = "Earlier draft."
        app._pre_generation_file = app.current_file
        app._pre_generation_saved_text = app.saved_output_text
        app.busy = True
        app.writing = True
        app.stop_requested = True
        app.loaded_model = Path("/models/example.gguf")
        app.status_var = FakeStatus()
        app._update_controls = lambda: None

        app._write_stopped()

        self.assertEqual(app._output_text(), "Earlier draft.")
        self.assertEqual(app.current_file, Path("/tmp/draft.txt"))
        self.assertEqual(app.saved_output_text, "Earlier draft.")
        self.assertIsNone(app.loaded_model)

    def test_text_file_round_trip_preserves_unicode_and_newlines_exactly(self):
        original = "First paragraph.\n\nMañana, she said, “continue.”\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft.txt"

            saved_path = save_text_document(path, original)
            reopened = read_text_document(saved_path)

        self.assertEqual(saved_path, path.resolve())
        self.assertEqual(reopened, original)

    def test_save_does_not_add_or_remove_a_trailing_newline(self):
        original = "A sentence without a final newline."
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft.txt"

            save_text_document(path, original)

            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
