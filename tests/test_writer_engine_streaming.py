import unittest
from pathlib import Path

from builder.writer_engine import (
    _PromptEchoStreamFilter,
    WriterEngine,
    encode_prompt_for_cli,
)


class PromptEchoStreamFilterTests(unittest.TestCase):
    def test_removes_chunked_wrapped_prompt_echo_and_streams_story_text(self):
        prompt = "LONG PROMPT WITH MORE THAN ONE WORD"
        pieces = []
        stream = _PromptEchoStreamFilter(prompt, pieces.append)

        stream.write("> LONG PROMPT WITH ")
        self.assertEqual(pieces, [])
        stream.write("MORE\r\n THAN ONE WORD\r\nThe scene begins.")
        stream.finish()

        self.assertEqual("".join(pieces), "The scene begins.")

    def test_streams_immediately_when_no_prompt_echo_is_present(self):
        pieces = []
        stream = _PromptEchoStreamFilter("LONG PROMPT", pieces.append)

        stream.write("The kitchen ")
        self.assertEqual(pieces, ["The kitchen "])
        stream.write("warmed around them.")
        stream.finish()

        self.assertEqual("".join(pieces), "The kitchen warmed around them.")

    def test_does_not_emit_an_incomplete_prompt_echo_on_finish(self):
        pieces = []
        stream = _PromptEchoStreamFilter("A LONG PROMPT", pieces.append)

        stream.write("> A LONG")
        stream.finish()

        self.assertEqual(pieces, [])


class ClearContextTests(unittest.TestCase):
    def test_clear_context_uses_cli_command_and_keeps_model_process(self):
        class FakeChild:
            def __init__(self):
                self.before = ""
                self.sent = []
                self.killed = False
                self.wait = None

            def isalive(self):
                return True

            def sendline(self, value):
                self.sent.append(value)

            def expect(self, pattern, timeout):
                self.wait = (pattern, timeout)
                self.before = "Chat history cleared.\\r\\n"
                return 0

            def kill(self, _signal):
                self.killed = True

        engine = WriterEngine()
        child = FakeChild()
        engine.child = child
        model_path = engine.model_path = __import__("pathlib").Path("/models/example.gguf")

        engine.clear_context()

        self.assertEqual(child.sent, ["/clear"])
        self.assertEqual(child.wait[0], r"(?m)^> ")
        self.assertEqual(child.wait[1], 30)
        self.assertFalse(child.killed)
        self.assertIs(engine.child, child)
        self.assertEqual(engine.model_path, model_path)

    def test_clear_context_stops_unconfirmed_cli_session(self):
        class FakeChild:
            before = "Unexpected CLI response."

            def isalive(self):
                return True

            def sendline(self, _value):
                pass

            def expect(self, _pattern, timeout):
                return 0

            def kill(self, _signal):
                self.killed = True

        engine = WriterEngine()
        child = FakeChild()
        child.killed = False
        engine.child = child

        with self.assertRaisesRegex(RuntimeError, "Could not clear"):
            engine.clear_context()

        self.assertTrue(child.killed)
        self.assertIsNone(engine.child)


class PromptEncodingTests(unittest.TestCase):
    def test_preserves_real_line_breaks_and_literal_backslash_sequences(self):
        prompt = "First paragraph.\n\nLiteral sequence: \\n\nPath: C:\\models"
        cli_input = encode_prompt_for_cli(prompt)

        self.assertEqual(cli_input, prompt + "/")
        self.assertEqual(cli_input.count("\n"), prompt.count("\n"))
        self.assertIn(r"Literal sequence: \n", cli_input)
        self.assertIn(r"Path: C:\models", cli_input)
        self.assertTrue(cli_input.endswith("/"))

    def test_normalizes_line_endings_before_multiline_submission(self):
        self.assertEqual(
            encode_prompt_for_cli("First\r\nSecond\rThird"),
            "First\nSecond\nThird/",
        )

    def test_generate_sends_raw_multiline_prompt_and_returns_clean_prose(self):
        prompt = "Scene setup.\n\nKeep this literal sequence: \\n\nLast line."
        expected_cli_input = encode_prompt_for_cli(prompt)
        chunks = []

        class FakeChild:
            def __init__(self):
                self.logfile_read = None
                self.before = ""
                self.sent = None

            def isalive(self):
                return True

            def sendline(self, value):
                self.sent = value

            def expect(self, _pattern, timeout):
                self.before = f"> {self.sent}\r\nThe scene starts.\nA second paragraph."
                if self.logfile_read is not None:
                    self.logfile_read.write(self.before)

        engine = WriterEngine()
        child = FakeChild()
        engine.child = child

        answer = engine.generate(prompt, on_delta=chunks.append)

        self.assertEqual(child.sent, expected_cli_input)
        self.assertIn("\n\n", child.sent)
        self.assertIn(r"Keep this literal sequence: \n", child.sent)
        self.assertEqual(answer, "The scene starts.\nA second paragraph.")
        self.assertEqual("".join(chunks), answer)

if __name__ == "__main__":
    unittest.main()
