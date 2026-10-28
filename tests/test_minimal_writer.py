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
        self.clear_context_calls = 0

    def clear_context(self):
        self.clear_context_calls += 1

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

    def test_new_session_keeps_visible_draft_and_file_tracking(self):
        app = MinimalWriterApp.__new__(MinimalWriterApp)
        app.root = FakeRoot()
        app.engine = FakeEngine()
        model_path = Path("/models/example.gguf")
        app.loaded_model = model_path
        app.busy = False
        app.writing = False
        app.stop_requested = False
        visible_text = "Unsaved visible draft that must stay untouched."
        app.output_box = FakeOutputBox(visible_text)
        current_file = Path("/tmp/draft.txt")
        app.current_file = current_file
        saved_text = "Earlier saved draft."
        app.saved_output_text = saved_text
        app.status_var = FakeStatus()
        app._update_controls = lambda: None

        with patch("minimal_writer.threading.Thread", ImmediateThread):
            app.new_session()

        self.assertEqual(app.engine.clear_context_calls, 1)
        self.assertEqual(app._output_text(), visible_text)
        self.assertEqual(app.current_file, current_file)
        self.assertEqual(app.saved_output_text, saved_text)
        self.assertEqual(app.loaded_model, model_path)
        self.assertFalse(app.busy)
        self.assertFalse(app.writing)
        self.assertIn("Visible text was kept", app.status_var.value)


    def test_loading_a_novel_scene_uses_a_copy_and_never_targets_the_source_for_save(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "Chapter_01_Section_10.txt"
            original = "Accepted scene text.\n\nThe ending remains here."
            source.write_text(original, encoding="utf-8")

            app = MinimalWriterApp.__new__(MinimalWriterApp)
            app.busy = False
            app.scene_files = {"Scene 10": source}
            app.scene_var = type("FakeVar", (), {"get": lambda self: "Scene 10"})()
            app.current_file = Path(temporary) / "some-other-draft.txt"
            app.selected_scene_source = None
            app.saved_output_text = "Previous saved draft."
            app.output_box = FakeOutputBox()
            app.status_var = FakeStatus()
            app._confirm_save_pending_changes = lambda: True
            app._update_controls = lambda: None
            app._update_document_title = lambda: None

            app.load_selected_scene_copy()

            self.assertEqual(app._output_text(), original)
            self.assertIsNone(app.current_file)
            self.assertEqual(app.selected_scene_source, source.resolve())
            self.assertEqual(app.saved_output_text, original)
            self.assertEqual(source.read_text(encoding="utf-8"), original)
            self.assertIn("original is untouched", app.status_var.value)
            self.assertIn("Save opens Save As", app.status_var.value)

    def test_save_to_selected_scene_requires_confirmation_and_keeps_save_as_behavior(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "Chapter_01_Section_10.txt"
            original = "Accepted scene text."
            edited = "Accepted scene text, carefully revised."
            source.write_text(original, encoding="utf-8")

            app = MinimalWriterApp.__new__(MinimalWriterApp)
            app.busy = False
            app.selected_scene_source = source.resolve()
            app.scene_files = {"Scene 10": source}
            app.scene_var = type("FakeVar", (), {"get": lambda self: "Scene 10"})()
            app.current_file = None
            app.saved_output_text = original
            app.output_box = FakeOutputBox(edited)
            app.root = FakeRoot()
            app.status_var = FakeStatus()

            with patch("minimal_writer.messagebox.askyesno", return_value=True) as confirm:
                result = app.save_to_selected_scene()

            self.assertTrue(result)
            self.assertEqual(source.read_text(encoding="utf-8"), edited)
            self.assertIn(str(source.resolve()), confirm.call_args.args[1])
            self.assertEqual(app.saved_output_text, edited)
            self.assertEqual(app.selected_scene_source, source.resolve())
            self.assertIsNone(app.current_file)
            self.assertIn("Ordinary Save still opens Save As", app.status_var.value)

            # Explicit scene saving must not attach the regular Save action
            # to the manuscript path.
            app.save_output_as = lambda: True
            self.assertTrue(app.save_output())

    def test_cancel_save_to_selected_scene_leaves_file_and_tracking_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "Chapter_01_Section_10.txt"
            original = "Accepted scene text."
            edited = "Replacement that must not be written."
            source.write_text(original, encoding="utf-8")

            app = MinimalWriterApp.__new__(MinimalWriterApp)
            app.busy = False
            app.selected_scene_source = source.resolve()
            app.scene_files = {"Scene 10": source}
            app.scene_var = type("FakeVar", (), {"get": lambda self: "Scene 10"})()
            app.current_file = None
            app.saved_output_text = original
            app.output_box = FakeOutputBox(edited)
            app.root = FakeRoot()
            app.status_var = FakeStatus()

            with patch("minimal_writer.messagebox.askyesno", return_value=False) as confirm:
                result = app.save_to_selected_scene()

            self.assertFalse(result)
            self.assertEqual(source.read_text(encoding="utf-8"), original)
            self.assertEqual(app.saved_output_text, original)
            self.assertEqual(app.selected_scene_source, source.resolve())
            self.assertFalse(app.status_var.value.startswith("Saved:"))
            self.assertIn("cancelled", app.status_var.value.lower())
            self.assertEqual(confirm.call_count, 1)

    def test_save_to_a_different_selected_scene_warns_and_leaves_loaded_scene_untouched(self):
        with tempfile.TemporaryDirectory() as temporary:
            loaded_source = Path(temporary) / "Chapter_01_Section_01.txt"
            selected_target = Path(temporary) / "Chapter_01_Section_10.txt"
            loaded_original = "Original loaded scene."
            target_original = "Different scene that must be confirmed."
            edited = "Edited text intended for the selected target."
            loaded_source.write_text(loaded_original, encoding="utf-8")
            selected_target.write_text(target_original, encoding="utf-8")

            app = MinimalWriterApp.__new__(MinimalWriterApp)
            app.busy = False
            app.selected_scene_source = loaded_source.resolve()
            app.scene_files = {"Scene 10": selected_target}
            app.scene_var = type("FakeVar", (), {"get": lambda self: "Scene 10"})()
            app.current_file = None
            app.saved_output_text = loaded_original
            app.output_box = FakeOutputBox(edited)
            app.root = FakeRoot()
            app.status_var = FakeStatus()

            with patch("minimal_writer.messagebox.askyesno", return_value=True) as confirm:
                result = app.save_to_selected_scene()

            self.assertTrue(result)
            self.assertIn(str(loaded_source.resolve()), confirm.call_args.args[1])
            self.assertEqual(loaded_source.read_text(encoding="utf-8"), loaded_original)
            self.assertEqual(selected_target.read_text(encoding="utf-8"), edited)
            self.assertEqual(app.selected_scene_source, selected_target.resolve())
            self.assertIsNone(app.current_file)

    def test_cancelled_novel_sync_starts_no_git_operation(self):
        from types import SimpleNamespace

        app = MinimalWriterApp.__new__(MinimalWriterApp)
        novel_path = Path("/tmp/Selected-Novel")
        app.busy = False
        app.novel_var = type("FakeVar", (), {"get": lambda self: "Selected-Novel"})()
        app.novel_packages = {"Selected-Novel": novel_path}
        app.status_var = FakeStatus()
        preview = SimpleNamespace(
            repository=novel_path,
            branch="main",
            remote_url="git@github.com:writer/selected-novel.git",
            changed_files=("Manuscript/scene.txt",),
        )

        with patch("minimal_writer.inspect_novel_repository", return_value=preview):
            with patch("minimal_writer.messagebox.askyesno", return_value=False) as confirm:
                with patch("minimal_writer.sync_novel_repository") as sync:
                    app.sync_selected_novel_to_github()

        self.assertEqual(confirm.call_count, 1)
        self.assertIn(str(novel_path), confirm.call_args.args[1])
        self.assertIn("Manuscript/scene.txt", confirm.call_args.args[1])
        self.assertIn("cancelled", app.status_var.value.lower())
        sync.assert_not_called()

    def test_confirmed_novel_sync_runs_only_after_preview_confirmation(self):
        from types import SimpleNamespace

        app = MinimalWriterApp.__new__(MinimalWriterApp)
        novel_path = Path("/tmp/Selected-Novel")
        app.root = FakeRoot()
        app.busy = False
        app.novel_var = type("FakeVar", (), {
            "get": lambda self: "Selected-Novel",
            "set": lambda self, value: setattr(self, "value", value),
        })()
        app.novel_var.value = "Selected-Novel"
        app.novel_packages = {"Selected-Novel": novel_path}
        app.status_var = FakeStatus()
        app._update_controls = lambda: None
        app.refresh_novels = lambda: None
        app._on_novel_selected = lambda: None
        preview = SimpleNamespace(
            repository=novel_path,
            branch="main",
            remote_url="git@github.com:writer/selected-novel.git",
            changed_files=(),
        )
        result = SimpleNamespace(message="Novel sync test succeeded.")

        with patch("minimal_writer.inspect_novel_repository", return_value=preview):
            with patch("minimal_writer.messagebox.askyesno", return_value=True) as confirm:
                with patch("minimal_writer.sync_novel_repository", return_value=result) as sync:
                    with patch("minimal_writer.threading.Thread", ImmediateThread):
                        app.sync_selected_novel_to_github()

        self.assertEqual(confirm.call_count, 1)
        sync.assert_called_once_with(novel_path)
        self.assertIn("Confirm novel sync", confirm.call_args.args[0])
        self.assertIn("StoryBuilder's code", confirm.call_args.args[1])
        self.assertEqual(app.status_var.value, result.message)
        self.assertFalse(app.busy)

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
