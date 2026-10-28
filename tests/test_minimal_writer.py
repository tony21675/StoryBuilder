import unittest
from pathlib import Path

from minimal_writer import load_model_for_writing, write_from_prompt


class FakeEngine:
    def __init__(self):
        self.start_calls = []
        self.generate_calls = []

    def start(self, model_path, system_prompt):
        self.start_calls.append((model_path, system_prompt))

    def generate(self, prompt):
        self.generate_calls.append(prompt)
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

        self.assertEqual(engine.generate_calls, [prompt])
        self.assertEqual(answer, "Generated text")


if __name__ == "__main__":
    unittest.main()
