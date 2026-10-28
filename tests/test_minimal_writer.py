import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from minimal_writer import (
    CONTINUE_PROMPT,
    MinimalWriterApp,
    build_continue_prompt,
    continuation_prefix,
    load_model_for_writing,
    read_text_document,
    save_text_document,
    write_from_prompt,
    bind_ctrl_a_select_all,
    select_all_text,
)


class FakeEngine:
    def __init__(self):
        self.start_calls = []
        self.generate_calls = []
        self.session_history = []

    def start(self, model_path, system_prompt):
        self.start_calls.append((model_path, system_prompt))
        self.session_history = []

    def generate(self, prompt, on_delta=None):
        self.generate_calls.append((prompt, on_delta))
        self.session_history.append(prompt)
        if on_delta is not None:
            on_delta("Generated ")
            on_delta("text")
        return "Generated text"


class FakeSelectableText:
    def __init__(self):
        self.bindings = {}
        self.tags = []
        self.marks = []
        self.seen = []

    def bind(self, sequence, callback):
        self.bindings[sequence] = callback

    def tag_add(self, *args):
        self.tags.append(args)

    def mark_set(self, *args):
        self.marks.append(args)

    def see(self, index):
        self.seen.append(index)


class FakePromptBox:
    def __init__(self, text=""):
        self.text = text

    def get(self, _start, _end):
        return self.text


class ImmediateThread:
    """Run a worker immediately so UI generation paths are easy to test."""

    def __init__(self, target, daemon=None):
        self.target = target

    def start(self):
        self.target()


class FakeOutputBox:
    def __init__(self, text=""):
        self.text = text

    def get(self, _start, _end):
        return self.text

    def delete(self, _start, _end):
        self.text = ""

    def insert(self, _index, text):
        self.text += text

    def see(self, _index):
        pass

    def edit_modified(self, _value):
        return None


class FakeRoot:
    def __init__(self):
        self.title_text = ""

    def title(self, value):
        self.title_text = value

    def after(self, _delay, callback):
        callback()


class FakeStatus:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value


class MinimalWriterTests(unittest.TestCase):
    def test_ctrl_a_is_bound_and_selects_all_text(self):
        widget = FakeSelectableText()
        bind_ctrl_a_select_all(widget)

        self.assertEqual(
            set(widget.bindings),
            {"<Control-a>", "<Control-A>"},
        )
        for sequence in ("<Control-a>", "<Control-A>"):
            widget.tags.clear()
            widget.marks.clear()
            widget.seen.clear()
            event = type("Event", (), {"widget": widget})()
            self.assertEqual(widget.bindings[sequence](event), "break")
            self.assertEqual(widget.tags, [("sel", "1.0", "end-1c")])
            self.assertEqual(widget.marks, [("insert", "1.0")])
            self.assertEqual(widget.seen, ["insert"])

    def test_select_all_handler_can_be_called_directly(self):
        widget = FakeSelectableText()
        event = type("Event", (), {"widget": widget})()

        self.assertEqual(select_all_text(event), "break")
        self.assertEqual(widget.tags, [("sel", "1.0", "end-1c")])

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

    def test_write_replaces_visible_prose_but_preserves_model_session_context(self):
        app = MinimalWriterApp.__new__(MinimalWriterApp)
        app.root = FakeRoot()
        app.engine = FakeEngine()
        model_path = Path("/models/example.gguf")
        load_model_for_writing(app.engine, model_path)
        starts_after_load = list(app.engine.start_calls)

        app.busy = False
        app.writing = False
        app.stop_requested = False
        app.loaded_model = model_path
        app.prompt_box = FakePromptBox("Write the first scene.")
        app.output_box = FakeOutputBox("Old prose that will be replaced.")
        app.current_file = None
        app.saved_output_text = ""
        app.status_var = FakeStatus()
        app._update_controls = lambda: None

        with patch("minimal_writer.threading.Thread", ImmediateThread):
            app.write()
            self.assertEqual(app._output_text(), "Generated text")

            app.prompt_box.text = "Write the next scene, picking up where that left off."
            app.write()

        self.assertEqual(app._output_text(), "Generated text")
        self.assertEqual(
            [call[0] for call in app.engine.generate_calls],
            [
                "Write the first scene.",
                "Write the next scene, picking up where that left off.",
            ],
        )
        self.assertEqual(app.engine.start_calls, starts_after_load)
        self.assertEqual(
            app.engine.session_history,
            [
                "Write the first scene.",
                "Write the next scene, picking up where that left off.",
            ],
        )

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
        app._generation_had_chunks = True
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
        app._generation_had_chunks = False
        app.loaded_model = Path("/models/example.gguf")
        app.status_var = FakeStatus()
        app._update_controls = lambda: None

        app._write_stopped()

        self.assertEqual(app._output_text(), "Earlier draft.")
        self.assertEqual(app.current_file, Path("/tmp/draft.txt"))
        self.assertEqual(app.saved_output_text, "Earlier draft.")
        self.assertIsNone(app.loaded_model)

    def test_continuation_prefix_preserves_existing_text_and_adds_paragraph_break(self):
        self.assertEqual(continuation_prefix("First passage."), "First passage.\n\n")
        self.assertEqual(continuation_prefix("First passage.\n"), "First passage.\n\n")
        self.assertEqual(continuation_prefix("First passage.\n\n"), "First passage.\n\n")
        self.assertEqual(continuation_prefix(""), "")

    def test_continue_prompt_requests_only_new_material(self):
        self.assertIn("Continue the current passage", CONTINUE_PROMPT)
        self.assertIn("without repeating", CONTINUE_PROMPT)

    def test_continue_prompt_uses_the_visible_passage_ending(self):
        passage = "An opening paragraph.\n\nThe door creaked open."
        prompt = build_continue_prompt(passage)

        self.assertIn(CONTINUE_PROMPT, prompt)
        self.assertIn("The door creaked open.", prompt)
        self.assertIn("Passage ending for context", prompt)

    def test_continue_prompt_limits_added_context_for_long_passages(self):
        passage = "x" * 2500 + "THE_ENDING"
        prompt = build_continue_prompt(passage)

        self.assertIn("THE_ENDING", prompt)
        self.assertNotIn("x" * 2100, prompt)

    def test_continue_action_uses_current_editor_text_as_context(self):
        app = MinimalWriterApp.__new__(MinimalWriterApp)
        app.busy = False
        app.loaded_model = Path("/models/example.gguf")
        app.output_box = FakeOutputBox("Edited ending of the passage.")
        captured = {}
        app._begin_generation = lambda prompt, mode: captured.update(
            prompt=prompt, mode=mode
        )

        app.continue_writing()

        self.assertEqual(captured["mode"], "continue")
        self.assertIn("Edited ending of the passage.", captured["prompt"])

    def test_continue_final_response_is_appended_not_replaced(self):
        existing = "Maya ran into the rain."
        app = MinimalWriterApp.__new__(MinimalWriterApp)
        app.root = FakeRoot()
        app.output_box = FakeOutputBox(continuation_prefix(existing) + "streamed preview")
        app.current_file = None
        app.saved_output_text = ""
        app._generation_mode = "continue"
        app._generation_prefix = continuation_prefix(existing)
        app.busy = True
        app.writing = True
        app.stop_requested = False
        app.loaded_model = Path("/models/example.gguf")
        app.status_var = FakeStatus()
        app._update_controls = lambda: None

        app._write_succeeded("A bell rang behind her.")

        self.assertEqual(
            app._output_text(),
            "Maya ran into the rain.\n\nA bell rang behind her.",
        )
        self.assertFalse(app.busy)
        self.assertFalse(app.writing)

    def test_write_final_response_still_replaces_previous_output(self):
        app = MinimalWriterApp.__new__(MinimalWriterApp)
        app.root = FakeRoot()
        app.output_box = FakeOutputBox("Old passage.\n\nPreview")
        app.current_file = None
        app.saved_output_text = ""
        app._generation_mode = "write"
        app._generation_prefix = ""
        app.busy = True
        app.writing = True
        app.stop_requested = False
        app.loaded_model = Path("/models/example.gguf")
        app.status_var = FakeStatus()
        app._update_controls = lambda: None

        app._write_succeeded("A new scene begins.")

        self.assertEqual(app._output_text(), "A new scene begins.")

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
