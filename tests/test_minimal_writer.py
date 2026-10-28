import tempfile
import unittest
from pathlib import Path

from minimal_writer import (
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

        self.assertEqual(engine.generate_calls, [("Write something.", chunks.append)])
        self.assertEqual(chunks, ["Generated ", "text"])
        self.assertEqual("".join(chunks), answer)

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
