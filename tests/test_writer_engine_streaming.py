import unittest

from builder.writer_engine import _PromptEchoStreamFilter


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


if __name__ == "__main__":
    unittest.main()
