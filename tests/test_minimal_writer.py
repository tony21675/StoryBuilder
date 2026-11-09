import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from minimal_writer import (
    CONTINUE_PROMPT,
    MinimalWriterApp,
    build_continue_prompt,
    build_location_context_prompt,
    build_manuscript_generation_prompt,
    build_revision_prompt,
    build_rewrite_scene_prompt,
    continuation_prefix,
    load_model_for_writing,
    read_text_document,
    save_text_document,
    write_from_prompt,
    bind_ctrl_a_select_all,
    select_all_text,
    text_widget_to_markdown,
)


class FakeEngine:
    def __init__(self):
        self.start_calls = []
        self.generate_calls = []
        self.session_history = []
        self.clear_context_calls = 0
        self.stop_calls = 0
        self.clear_context_error = None

    def clear_context(self):
        self.clear_context_calls += 1
        if self.clear_context_error is not None:
            raise self.clear_context_error

    def stop(self):
        self.stop_calls += 1

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

    def delete(self, _start, _end):
        self.text = ""


class FakeStyledOutputBox:
    def __init__(self, text, bold_ranges=(), italic_ranges=(), combined_ranges=()):
        self.text = text
        self.bold_ranges = bold_ranges
        self.italic_ranges = italic_ranges
        self.combined_ranges = combined_ranges

    def get(self, _start, _end):
        return self.text

    def tag_names(self, index):
        offset = int(index.split("+", 1)[1].strip().split()[0])
        tags = []
        if any(start <= offset < end for start, end in self.bold_ranges):
            tags.append("sb_bold")
        if any(start <= offset < end for start, end in self.italic_ranges):
            tags.append("sb_italic")
        if any(start <= offset < end for start, end in self.combined_ranges):
            tags.append("sb_bold_italic")
        return tuple(tags)


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


class FakeRevisionText:
    """Minimal one-line Text widget double for testing marked-range replacement."""

    def __init__(self, text, start, end):
        self.text = text
        self.marks = {"revision_start": start, "revision_end": end}
        self.gravities = {}

    @staticmethod
    def _offset(index):
        if isinstance(index, int):
            return index
        if index.startswith("1."):
            return int(index.split(".", 1)[1])
        raise ValueError(index)

    def get(self, start, end):
        if start == "1.0" and end == "end-1c":
            return self.text
        return self.text[self.marks[start]:self.marks[end]]

    def index(self, index):
        if index in self.marks:
            return f"1.{self.marks[index]}"
        return index

    def mark_set(self, name, index):
        self.marks[name] = self._offset(index)

    def mark_gravity(self, name, gravity):
        self.gravities[name] = gravity

    def mark_unset(self, *names):
        for name in names:
            self.marks.pop(name, None)

    def delete(self, start, end):
        a, b = self.marks[start], self.marks[end]
        self.text = self.text[:a] + self.text[b:]
        for name, pos in list(self.marks.items()):
            if pos >= b:
                self.marks[name] = pos - (b - a)
            elif pos >= a:
                self.marks[name] = a

    def insert(self, index, text):
        pos = self._offset(index)
        self.text = self.text[:pos] + text + self.text[pos:]
        for name, mark_pos in list(self.marks.items()):
            if mark_pos > pos:
                self.marks[name] = mark_pos + len(text)

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


class FakeVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakePicker:
    def __init__(self):
        self.values = []

    def configure(self, **kwargs):
        if "values" in kwargs:
            self.values = list(kwargs["values"])


class MinimalWriterTests(unittest.TestCase):

    def test_manuscript_prompts_show_work_through_direct_dialogue(self):
        prompt = build_manuscript_generation_prompt("Write natural manuscript prose only.")

        self.assertIn("SHOW THE WORK THROUGH DIALOGUE", prompt)
        self.assertIn("speak directly to one another", prompt)
        self.assertIn("The Computer is a speaking participant", prompt)
        self.assertIn("report important findings aloud", prompt)
        self.assertIn("Screen displays may support its spoken report but must not replace it", prompt)
        self.assertIn("do not replace these interactions with summary narration", prompt)
        self.assertTrue(prompt.startswith("Write natural manuscript prose only."))

    def test_manuscript_guidance_is_added_to_an_empty_prompt(self):
        prompt = build_manuscript_generation_prompt("   ")

        self.assertIn("SHOW THE WORK THROUGH DIALOGUE", prompt)

    def test_manual_draft_check_is_advisory_and_preserves_output_text(self):
        app = MinimalWriterApp.__new__(MinimalWriterApp)
        app.busy = False
        original = "He reached for the switch, but"
        app.output_box = FakeOutputBox(original)
        app.status_var = FakeStatus()
        shown = []
        app._showinfo = lambda title, message: shown.append((title, message))

        app.check_draft()

        self.assertEqual(app._output_text(), original)
        self.assertEqual(len(shown), 1)
        self.assertEqual(shown[0][0], "Draft Check")
        self.assertIn("Possible abrupt ending", shown[0][1])
        self.assertIn("advisory only", shown[0][1])
        self.assertIn("No text was changed", app.status_var.value)

    def test_manual_draft_check_does_nothing_while_writer_is_busy(self):
        app = MinimalWriterApp.__new__(MinimalWriterApp)
        app.busy = True
        app.output_box = FakeOutputBox("A draft that must remain unchanged.")
        app.status_var = FakeStatus()
        shown = []
        app._showinfo = lambda title, message: shown.append((title, message))

        app.check_draft()

        self.assertEqual(shown, [])
        self.assertEqual(app._output_text(), "A draft that must remain unchanged.")

    def test_writer_context_includes_only_named_character_card_facts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bible = {
                "creative_direction": {},
                "locations": {},
                "canon_rules": ["Tiffany and Maya have a sister-like friendship."],
                "character_cards": ["Tiffany.json", "Maya.json", "Chloe.json"],
            }
            (root / "story_bible.json").write_text(
                json.dumps(bible), encoding="utf-8"
            )
            (root / "current_state.json").write_text(
                json.dumps({"time_of_day": "Day 1, 16:00 (4:00 PM), late afternoon."}),
                encoding="utf-8",
            )
            cards = {
                "Tiffany.json": {
                    "name": "Tiffany Jones", "role": "student", "gender": "female",
                    "occupation": "High school student",
                    "background": "Used to helping with busy family routines.",
                    "skills": ["organization", "first aid basics"],
                    "hobbies": ["drawing", "photography"],
                    "sexual_orientation": "Straight",
                    "personality": ["shy", "thoughtful"],
                    "relationships": {"Maya": "like a sister"},
                },
                "Maya.json": {
                    "name": "Maya", "role": "student", "gender": "female",
                    "sexual_orientation": "Bisexual",
                    "personality": ["confident", "playful"],
                },
                "Chloe.json": {
                    "name": "Chloe", "role": "family friend", "gender": "female",
                    "sexual_orientation": "Straight",
                    "personality": ["protective"],
                },
            }
            for filename, card in cards.items():
                (root / filename).write_text(
                    json.dumps(card), encoding="utf-8"
                )

            app = MinimalWriterApp.__new__(MinimalWriterApp)
            app.novel_var = SimpleNamespace(get=lambda: "Test Novel")
            app.novel_packages = {"Test Novel": root}

            prompt = app._prepare_location_context(
                "Continue their conversation.",
                supporting_text="Tiffany looked at Maya and smiled.",
            )

        self.assertIn("[Tiffany Jones]", prompt)
        self.assertIn("[Maya]", prompt)
        self.assertIn("Gender: female", prompt)
        self.assertIn("Occupation / department: High school student", prompt)
        self.assertIn("Skills: organization, first aid basics", prompt)
        self.assertNotIn("[Chloe]", prompt)
        self.assertNotIn("Sexual orientation:", prompt)
        self.assertNotIn("Background / experience:", prompt)
        self.assertNotIn("Interests / hobbies:", prompt)
        self.assertNotIn("Tiffany and Maya have a sister-like friendship.", prompt)
        self.assertNotIn("CANON RULES", prompt)
        self.assertNotIn("SCENE CRAFT GUIDANCE", prompt)
        self.assertIn("STORY TIMELINE", prompt)
        self.assertIn("Latest saved in-story time: Day 1, 16:00", prompt)

    def test_writer_prompt_adds_only_named_location_details(self):
        locations = {
            "Supply Closet": {},
            "Main Galley": {
                "type": "room",
                "description": "A shared meal preparation area.",
            },
        }

        prompt, referenced_names = build_location_context_prompt(
            "Scene direction: The group gathers in the Main Galley.",
            locations,
        )

        self.assertNotIn("APPROVED LOCATIONS FROM THIS NOVEL'S STORY BIBLE", prompt)
        self.assertNotIn("Supply Closet", prompt)
        self.assertIn("[Main Galley]", prompt)
        self.assertIn("Description: A shared meal preparation area.", prompt)
        self.assertEqual(referenced_names, ["Main Galley"])

    def test_writer_context_uses_saved_current_scene_cast(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bible = {
                "creative_direction": {},
                "locations": {},
                "character_cards": ["Maya.json", "Tiffany.json"],
            }
            (root / "story_bible.json").write_text(
                json.dumps(bible), encoding="utf-8"
            )
            (root / "current_state.json").write_text(
                json.dumps({"status": "in_progress", "scene_cast": ["Maya"]}),
                encoding="utf-8",
            )
            (root / "Maya.json").write_text(
                json.dumps({"name": "Maya", "gender": "female", "sexual_orientation": "Bisexual"}),
                encoding="utf-8",
            )
            (root / "Tiffany.json").write_text(
                json.dumps({"name": "Tiffany", "sexual_orientation": "Straight"}),
                encoding="utf-8",
            )
            app = MinimalWriterApp.__new__(MinimalWriterApp)
            app.novel_var = SimpleNamespace(get=lambda: "Test Novel")
            app.novel_packages = {"Test Novel": root}

            prompt = app._prepare_location_context(
                "Continue the conversation.", supporting_text="The room was quiet."
            )

        self.assertIn("[Maya]", prompt)
        self.assertIn("Gender: female", prompt)
        self.assertNotIn("Sexual orientation:", prompt)
        self.assertNotIn("[Tiffany]", prompt)

    def test_writer_context_includes_all_cards_at_fresh_story_start(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bible = {
                "creative_direction": {},
                "locations": {},
                "character_cards": ["Maya.json", "Tiffany.json"],
            }
            (root / "story_bible.json").write_text(
                json.dumps(bible), encoding="utf-8"
            )
            (root / "current_state.json").write_text(
                json.dumps({"status": "story_start", "scene_cast": []}),
                encoding="utf-8",
            )
            (root / "Maya.json").write_text(
                json.dumps({"name": "Maya", "gender": "female", "sexual_orientation": "Bisexual"}),
                encoding="utf-8",
            )
            (root / "Tiffany.json").write_text(
                json.dumps({"name": "Tiffany", "sexual_orientation": "Straight"}),
                encoding="utf-8",
            )
            app = MinimalWriterApp.__new__(MinimalWriterApp)
            app.novel_var = SimpleNamespace(get=lambda: "Test Novel")
            app.novel_packages = {"Test Novel": root}

            prompt = app._prepare_location_context("Begin the opening scene.")

        self.assertIn("[Maya]", prompt)
        self.assertIn("[Tiffany]", prompt)

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

    def test_revision_prompt_targets_only_selected_passage_and_instruction(self):
        selected = "Maya lowered her voice."
        instruction = "Make this sound more tense, but keep the same event."
        prompt = build_revision_prompt(selected, instruction)

        self.assertIn("only the selected passage", prompt.lower())
        self.assertIn("Author's instruction:\n" + instruction, prompt)
        self.assertIn("Selected passage to revise:\n" + selected, prompt)
        self.assertNotIn("rewrite the whole scene", prompt.lower())

    def test_revision_application_changes_only_the_selected_range(self):
        original = "Before. Old sentence. After."
        selected = "Old sentence."
        start = original.index(selected)
        end = start + len(selected)
        app = MinimalWriterApp.__new__(MinimalWriterApp)
        app.output_box = FakeRevisionText(original, start, end)
        app._revision_start_mark = "revision_start"
        app._revision_end_mark = "revision_end"
        app._revision_original = selected
        app._revision_active = True
        app.status_var = FakeStatus()
        app._update_document_title = lambda: None
        app._update_controls = lambda: None

        applied = app._apply_revision_candidate("A different sentence!")

        self.assertTrue(applied)
        self.assertEqual(app._output_text(), "Before. A different sentence! After.")
        self.assertFalse(app._revision_active)
        self.assertIn("applied", app.status_var.value.lower())

    def test_revision_is_refused_if_selected_text_changed(self):
        original = "Before. Old sentence. After."
        selected = "Old sentence."
        start = original.index(selected)
        end = start + len(selected)
        app = MinimalWriterApp.__new__(MinimalWriterApp)
        app.output_box = FakeRevisionText(original, start, end)
        app._revision_start_mark = "revision_start"
        app._revision_end_mark = "revision_end"
        app._revision_original = selected
        app._revision_active = True
        app.status_var = FakeStatus()
        app._update_document_title = lambda: None
        app._update_controls = lambda: None

        app.output_box.text = "Before. Changed sentence. After."
        applied = app._apply_revision_candidate("Unsafe overwrite.")

        self.assertFalse(applied)
        self.assertEqual(app._output_text(), "Before. Changed sentence. After.")

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


    def _make_novel_switch_app(self, temporary, *, loaded_model=True):
        root = Path(temporary)
        novel_a = root / "Novel A"
        novel_b = root / "Novel B"
        novel_a.mkdir()
        novel_b.mkdir()

        app = MinimalWriterApp.__new__(MinimalWriterApp)
        app.root = FakeRoot()
        app.engine = FakeEngine()
        app.loaded_model = Path("/models/example.gguf") if loaded_model else None
        app.busy = False
        app.writing = False
        app.stop_requested = False
        app.novel_packages = {"Novel A": novel_a, "Novel B": novel_b}
        app.novel_var = FakeVar("Novel B")
        app._active_novel_path = novel_a.resolve()
        app.chapter_var = FakeVar("Chapter 01")
        app.scene_var = FakeVar("Scene 01")
        app.chapter_numbers = {"Chapter 01": 1}
        app.scene_files = {}
        app.novel_picker = FakePicker()
        app.chapter_picker = FakePicker()
        app.scene_picker = FakePicker()
        app.prompt_box = FakePromptBox("Old novel scene direction.")
        app.author_direction_box = FakePromptBox("Old novel author guidance.")
        app.output_box = FakeOutputBox("Manuscript draft from Novel A.")
        app.current_file = root / "working-draft.odt"
        app.selected_scene_source = novel_a / "Manuscript" / "scene.odt"
        app.saved_output_text = "Earlier saved manuscript text."
        app._prepared_scene_destination = (1, 4)
        app._prepared_scene_novel_path = novel_a
        app._prepared_scene_source_scene_path = novel_a / "scene.txt"
        app._scene_preparation_destination = (1, 4)
        app._scene_preparation_original_prompt = "Old prompt"
        app._scene_preparation_original_author_direction = "Old direction"
        app._scene_preparation_novel_path = novel_a
        app._scene_preparation_source_scene_path = novel_a / "scene.txt"
        app._preparing_scene = False
        app.last_location_context_names = ["Old Location"]
        app.status_var = FakeStatus()
        app.activity_task_var = FakeStatus()
        app.activity_model_var = FakeStatus()
        app.activity_state_var = FakeStatus()
        app._activity_model_path = None
        app._update_controls = lambda: None
        app._showerror = lambda *args: setattr(app, "shown_error", args)
        return app, novel_a, novel_b

    def test_writer_starts_with_no_novel_selected_after_refresh(self):
        with tempfile.TemporaryDirectory() as temporary:
            app = MinimalWriterApp.__new__(MinimalWriterApp)
            app.novel_var = FakeVar("")
            app.novel_picker = FakePicker()
            app.novel_packages = {}
            app._active_novel_path = None
            app.chapter_var = FakeVar("")
            app.scene_var = FakeVar("")
            app.chapter_numbers = {}
            app.scene_files = {}
            app.chapter_picker = FakePicker()
            app.scene_picker = FakePicker()
            app.status_var = FakeStatus()
            app._update_controls = lambda: None
            novel = Path(temporary) / "First Novel"
            novel.mkdir()

            with patch("minimal_writer.list_novel_packages", return_value=[novel]):
                app.refresh_novels()

            self.assertEqual(app.novel_var.get(), "")
            self.assertEqual(app.novel_picker.values, ["First Novel"])
            self.assertEqual(app.chapter_var.get(), "")
            self.assertEqual(app.scene_var.get(), "")
            self.assertIn("Choose a novel", app.status_var.value)

    def test_switching_novels_clears_directions_and_model_history_but_keeps_manuscript(self):
        with tempfile.TemporaryDirectory() as temporary:
            app, novel_a, novel_b = self._make_novel_switch_app(temporary)
            original_document = app._output_text()
            current_file = app.current_file
            selected_scene_source = app.selected_scene_source
            saved_text = app.saved_output_text

            with patch("minimal_writer.list_scene_chapters", return_value=[1]), patch(
                "minimal_writer.list_scene_files", return_value=[]
            ), patch("minimal_writer.threading.Thread", ImmediateThread):
                app._on_novel_selected()

            self.assertEqual(app._active_novel_path, novel_b.resolve())
            self.assertEqual(app.engine.clear_context_calls, 1)
            self.assertEqual(app.prompt_box.get("1.0", "end-1c"), "")
            self.assertEqual(app.author_direction_box.get("1.0", "end-1c"), "")
            self.assertIsNone(app._prepared_scene_destination)
            self.assertIsNone(app._scene_preparation_destination)
            self.assertEqual(app.last_location_context_names, [])
            self.assertEqual(app._output_text(), original_document)
            self.assertEqual(app.current_file, current_file)
            self.assertEqual(app.selected_scene_source, selected_scene_source)
            self.assertEqual(app.saved_output_text, saved_text)
            self.assertEqual(app.loaded_model, Path("/models/example.gguf"))
            self.assertFalse(app.busy)
            self.assertEqual(app.activity_state_var.value, "Finished")

    def test_refreshing_the_same_novel_does_not_clear_model_history_or_directions(self):
        with tempfile.TemporaryDirectory() as temporary:
            app, novel_a, _novel_b = self._make_novel_switch_app(temporary)
            app.novel_var.set("Novel A")
            app._active_novel_path = novel_a.resolve()
            app.prompt_box.text = "Keep this direction."
            app.author_direction_box.text = "Keep this author guidance."

            with patch("minimal_writer.list_scene_chapters", return_value=[1]), patch(
                "minimal_writer.list_scene_files", return_value=[]
            ):
                app._on_novel_selected()

            self.assertEqual(app.engine.clear_context_calls, 0)
            self.assertEqual(app.prompt_box.text, "Keep this direction.")
            self.assertEqual(app.author_direction_box.text, "Keep this author guidance.")
            self.assertEqual(app._active_novel_path, novel_a.resolve())

    def test_switching_novels_without_a_loaded_model_only_clears_directions(self):
        with tempfile.TemporaryDirectory() as temporary:
            app, _novel_a, novel_b = self._make_novel_switch_app(
                temporary, loaded_model=False
            )

            with patch("minimal_writer.list_scene_chapters", return_value=[1]), patch(
                "minimal_writer.list_scene_files", return_value=[]
            ):
                app._on_novel_selected()

            self.assertEqual(app._active_novel_path, novel_b.resolve())
            self.assertEqual(app.engine.clear_context_calls, 0)
            self.assertEqual(app.prompt_box.text, "")
            self.assertEqual(app.author_direction_box.text, "")
            self.assertEqual(app._output_text(), "Manuscript draft from Novel A.")
            self.assertFalse(app.busy)

    def test_switching_novels_stops_model_if_old_history_cannot_be_cleared(self):
        with tempfile.TemporaryDirectory() as temporary:
            app, _novel_a, _novel_b = self._make_novel_switch_app(temporary)
            app.engine.clear_context_error = RuntimeError("clear command was not confirmed")

            with patch("minimal_writer.list_scene_chapters", return_value=[1]), patch(
                "minimal_writer.list_scene_files", return_value=[]
            ), patch("minimal_writer.threading.Thread", ImmediateThread):
                app._on_novel_selected()

            self.assertEqual(app.engine.clear_context_calls, 1)
            self.assertEqual(app.engine.stop_calls, 1)
            self.assertIsNone(app.loaded_model)
            self.assertFalse(app.busy)
            self.assertEqual(app.activity_state_var.value, "Error")
            self.assertIn("Model session stopped for safety", app.shown_error[0])

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

            with patch("minimal_writer.show_copyable_dialog", return_value="Yes") as confirm:
                result = app.save_to_selected_scene()

            self.assertTrue(result)
            self.assertEqual(source.read_text(encoding="utf-8"), edited)
            self.assertIn(str(source.resolve()), confirm.call_args.args[2])
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

            with patch("minimal_writer.show_copyable_dialog", return_value="No") as confirm:
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

            with patch("minimal_writer.show_copyable_dialog", return_value="Yes") as confirm:
                result = app.save_to_selected_scene()

            self.assertTrue(result)
            self.assertIn(str(loaded_source.resolve()), confirm.call_args.args[2])
            self.assertEqual(loaded_source.read_text(encoding="utf-8"), loaded_original)
            self.assertEqual(selected_target.read_text(encoding="utf-8"), edited)
            self.assertEqual(app.selected_scene_source, selected_target.resolve())
            self.assertIsNone(app.current_file)

    def test_cancelled_novel_sync_starts_no_git_operation(self):
        from types import SimpleNamespace

        app = MinimalWriterApp.__new__(MinimalWriterApp)
        novel_path = Path("/tmp/Selected-Novel")
        app.root = FakeRoot()
        app.busy = False
        app.novel_var = type("FakeVar", (), {"get": lambda self: "Selected-Novel"})()
        app.novel_packages = {"Selected-Novel": novel_path}
        app.status_var = FakeStatus()
        app.output_box = FakeOutputBox("Unsaved writer edits.")
        app.saved_output_text = ""
        preview = SimpleNamespace(
            repository=novel_path,
            branch="main",
            remote_url="git@github.com:writer/selected-novel.git",
            changed_files=("Manuscript/scene.txt",),
            local_commits=("abc1234 Previous novel commit",),
        )

        with patch("minimal_writer.inspect_novel_repository", return_value=preview):
            with patch("minimal_writer.show_copyable_dialog", return_value="No") as confirm:
                with patch("minimal_writer.sync_novel_repository") as sync:
                    app.sync_selected_novel_to_github()

        self.assertEqual(confirm.call_count, 1)
        self.assertIn(str(novel_path), confirm.call_args.args[2])
        self.assertIn("Manuscript/scene.txt", confirm.call_args.args[2])
        self.assertIn("unsaved edits", confirm.call_args.args[2].lower())
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
            local_commits=(),
        )
        result = SimpleNamespace(message="Novel sync test succeeded.")

        with patch("minimal_writer.inspect_novel_repository", return_value=preview):
            with patch("minimal_writer.show_copyable_dialog", return_value="Yes") as confirm:
                with patch("minimal_writer.sync_novel_repository", return_value=result) as sync:
                    with patch("minimal_writer.threading.Thread", ImmediateThread):
                        app.sync_selected_novel_to_github()

        self.assertEqual(confirm.call_count, 1)
        sync.assert_called_once_with(novel_path)
        self.assertIn("Confirm novel sync", confirm.call_args.args[1])
        self.assertIn("StoryBuilder's code", confirm.call_args.args[2])
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

    def test_rewrite_scene_prompt_adds_author_direction_without_mutating_original(self):
        original = (
            "Scene direction: Continue the conversation.\n"
            "Natural endpoint: Elena enters.\n"
            "Write natural manuscript prose only."
        )
        direction = "Let the characters talk for a little longer."
        result = build_rewrite_scene_prompt(original, direction)

        self.assertTrue(result.startswith(original))
        self.assertIn("ADDITIONAL AUTHOR'S DIRECTION FOR THIS REWRITE", result)
        self.assertIn(direction, result)
        self.assertIn("supplementary guidance for the same scene", result)
        self.assertIn("unless the author explicitly asks to change them", result)
        self.assertNotIn("priority clarification", result)
        self.assertIn("complete replacement scene", result)
        self.assertEqual(original.splitlines()[0], "Scene direction: Continue the conversation.")

    def test_rewrite_scene_prompt_without_extra_direction_keeps_original_prompt(self):
        original = "Scene direction: Continue naturally.\nNatural endpoint: Elena enters."
        self.assertEqual(build_rewrite_scene_prompt(original, ""), original)
        self.assertEqual(build_rewrite_scene_prompt(original, "  \n "), original)

    def test_rewrite_action_sends_existing_prompt_with_author_direction(self):
        app = MinimalWriterApp.__new__(MinimalWriterApp)
        app.busy = False
        app.loaded_model = Path("/models/example.gguf")
        scene_prompt = "Scene direction: Let the group talk.\nNatural endpoint: Elena arrives."
        direction = "Give the conversation more room."
        app.prompt_box = FakePromptBox(scene_prompt)
        app.author_direction_box = FakePromptBox(direction)
        app.output_box = FakeOutputBox("Too-short first attempt.")
        app.status_var = FakeStatus()
        app._askyesno = lambda _title, _message: True
        app._prepare_location_context = lambda prompt: prompt
        captured = {}
        app._begin_generation = lambda prompt, mode: captured.update(
            prompt=prompt, mode=mode
        )

        app.rewrite_current_scene()

        self.assertEqual(captured["mode"], "rewrite")
        self.assertTrue(captured["prompt"].startswith(scene_prompt))
        self.assertIn(direction, captured["prompt"])
        self.assertEqual(app.prompt_box.text, scene_prompt)
        self.assertEqual(app.author_direction_box.text, direction)
        self.assertEqual(app._rewrite_original_author_direction, direction)

    def test_cancelled_rewrite_keeps_existing_draft_and_guidance(self):
        app = MinimalWriterApp.__new__(MinimalWriterApp)
        app.busy = False
        app.loaded_model = Path("/models/example.gguf")
        app.prompt_box = FakePromptBox("Scene direction: Same scene.")
        app.author_direction_box = FakePromptBox("Add more dialogue.")
        original = "Existing draft."
        app.output_box = FakeOutputBox(original)
        app.status_var = FakeStatus()
        app._askyesno = lambda _title, _message: False
        app._prepare_location_context = lambda prompt: self.fail(
            "A cancelled rewrite must not prepare or send a prompt."
        )
        app._begin_generation = lambda *_args, **_kwargs: self.fail(
            "A cancelled rewrite must not start generation."
        )

        app.rewrite_current_scene()

        self.assertEqual(app._output_text(), original)
        self.assertEqual(app.author_direction_box.text, "Add more dialogue.")
        self.assertIn("cancelled", app.status_var.value.lower())

    def test_rewrite_success_replaces_draft_and_clears_unchanged_guidance(self):
        app = MinimalWriterApp.__new__(MinimalWriterApp)
        app.root = FakeRoot()
        app.output_box = FakeOutputBox("Old draft.")
        app.current_file = None
        app.saved_output_text = ""
        app.author_direction_box = FakePromptBox("Add more dialogue.")
        app._rewrite_original_author_direction = "Add more dialogue."
        app._generation_mode = "rewrite"
        app._generation_prefix = ""
        app.busy = True
        app.writing = True
        app.stop_requested = False
        app.loaded_model = Path("/models/example.gguf")
        app.status_var = FakeStatus()
        app._update_controls = lambda: None

        app._write_succeeded("Replacement scene.")

        self.assertEqual(app._output_text(), "Replacement scene.")
        self.assertEqual(app.author_direction_box.text, "")
        self.assertIn("rewriting", app.status_var.value.lower())

    def test_rewrite_success_preserves_guidance_edited_during_generation(self):
        app = MinimalWriterApp.__new__(MinimalWriterApp)
        app.root = FakeRoot()
        app.output_box = FakeOutputBox("Old draft.")
        app.current_file = None
        app.saved_output_text = ""
        app.author_direction_box = FakePromptBox("A newer instruction.")
        app._rewrite_original_author_direction = "Original instruction."
        app._generation_mode = "rewrite"
        app._generation_prefix = ""
        app.busy = True
        app.writing = True
        app.stop_requested = False
        app.loaded_model = Path("/models/example.gguf")
        app.status_var = FakeStatus()
        app._update_controls = lambda: None

        app._write_succeeded("Replacement scene.")

        self.assertEqual(app._output_text(), "Replacement scene.")
        self.assertEqual(app.author_direction_box.text, "A newer instruction.")
        self.assertIn("edits were kept", app.status_var.value.lower())

    def test_stopped_rewrite_restores_previous_draft_even_after_partial_output(self):
        app = MinimalWriterApp.__new__(MinimalWriterApp)
        app.root = FakeRoot()
        app.output_box = FakeOutputBox("Partial replacement.")
        app.current_file = Path("/tmp/scene.txt")
        app.saved_output_text = "Saved text before rewrite."
        app._pre_generation_text = "Old visible draft."
        app._pre_generation_file = app.current_file
        app._pre_generation_saved_text = app.saved_output_text
        app._generation_mode = "rewrite"
        app.busy = True
        app.writing = True
        app.stop_requested = True
        app._generation_had_chunks = True
        app.loaded_model = Path("/models/example.gguf")
        app.status_var = FakeStatus()
        app._update_controls = lambda: None

        app._write_stopped()

        self.assertEqual(app._output_text(), "Old visible draft.")
        self.assertEqual(app.current_file, Path("/tmp/scene.txt"))
        self.assertEqual(app.saved_output_text, "Saved text before rewrite.")
        self.assertIn("previous draft was restored", app.status_var.value.lower())
        self.assertIsNone(app.loaded_model)

    def test_write_includes_the_immediately_preceding_saved_scene(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chapter = root / "Manuscript" / "Chapters" / "Chapter_02"
            chapter.mkdir(parents=True)
            previous = chapter / "Chapter_02_Section_19.txt"
            previous.write_text(
                "Morgan finished her charades turn. The group was still laughing.",
                encoding="utf-8",
            )
            (root / "story_bible.json").write_text(
                json.dumps({"creative_direction": {}, "locations": {}, "character_cards": []}),
                encoding="utf-8",
            )
            (root / "current_state.json").write_text(
                json.dumps({
                    "chapter": 2,
                    "scene": 19,
                    "scene_completed": True,
                    "time_of_day": "Day 2, nighttime at the Mars research outpost.",
                    "current_situation": "The crew has finished charades in the Recreation Room.",
                    "active_objectives": {
                        "Daniel": "Deliver the report Elena requested. It remains undelivered."
                    },
                    "scene_cast": ["Daniel", "Elena", "Morgan", "Priya", "Ryan", "Zoe"],
                }),
                encoding="utf-8",
            )

            Value = lambda value: type("Value", (), {"get": lambda self: value})()
            app = MinimalWriterApp.__new__(MinimalWriterApp)
            app.busy = False
            app.loaded_model = Path("/models/example.gguf")
            app.prompt_box = FakePromptBox("Scene direction: Continue the evening.")
            app.novel_var = Value("The Long Way Home")
            app.novel_packages = {"The Long Way Home": root}
            app.chapter_var = Value("Chapter 02")
            app.chapter_numbers = {"Chapter 02": 2}
            app.scene_var = Value("Scene 20")
            captured = {}
            app._begin_generation = lambda prompt, mode: captured.update(
                prompt=prompt, mode=mode
            )

            app.write()

            self.assertEqual(captured["mode"], "write")
            self.assertIn("IMMEDIATELY PRECEDING SAVED SCENE", captured["prompt"])
            self.assertIn("Morgan finished her charades turn.", captured["prompt"])
            self.assertIn("Source: Chapter 02, Scene 19", captured["prompt"])
            self.assertIn("CURRENT STORY SITUATION", captured["prompt"])
            self.assertIn("The crew has finished charades in the Recreation Room.", captured["prompt"])
            self.assertNotIn("OUTSTANDING CHARACTER OBJECTIVES", captured["prompt"])
            self.assertNotIn(
                "Daniel: Deliver the report Elena requested. It remains undelivered.",
                captured["prompt"],
            )
            self.assertNotIn("Do not assume it happened off-page", captured["prompt"])

    def test_prompt_trace_is_armed_for_one_scene_and_finished_locally(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace_path = Path(temporary) / "prompt_trace.json"
            trace = type(
                "Trace",
                (),
                {
                    "finish": lambda self, **kwargs: trace_path,
                },
            )()
            attached = []
            detached = []
            engine = FakeEngine()
            engine.attach_prompt_trace = attached.append
            engine.detach_prompt_trace = detached.append

            Value = lambda value: type("Value", (), {"get": lambda self: value})()
            app = MinimalWriterApp.__new__(MinimalWriterApp)
            app.engine = engine
            app.loaded_model = Path("/models/example.gguf")
            app.prompt_box = FakePromptBox("Scene direction: Continue.")
            app.author_direction_box = FakePromptBox("Keep the mood light.")
            app.novel_var = Value("The Long Way Home")
            app.novel_packages = {"The Long Way Home": Path(temporary)}
            app.chapter_var = Value("Chapter 02")
            app.chapter_numbers = {"Chapter 02": 2}
            app.scene_var = Value("Scene 20")

            with patch("minimal_writer.load_prompt_trace_enabled", return_value=True), patch(
                "minimal_writer.PromptTrace", return_value=trace
            ) as trace_factory:
                result = app._start_prompt_trace("Full enriched prompt")

            self.assertIs(result, trace)
            self.assertEqual(attached, [trace])
            self.assertEqual(trace_factory.call_args.kwargs["chapter"], 2)
            self.assertEqual(trace_factory.call_args.kwargs["scene"], 20)
            self.assertEqual(
                trace_factory.call_args.kwargs["scene_direction"],
                "Scene direction: Continue.",
            )
            self.assertEqual(
                trace_factory.call_args.kwargs["author_guidance"],
                "Keep the mood light.",
            )

            upload_result = {
                "ok": True,
                "repository": "tony21675/StoryBuilder-Traces",
                "url": "https://github.com/tony21675/StoryBuilder-Traces/blob/main/prompt_trace.json",
            }
            with patch(
                "minimal_writer.upload_prompt_trace", return_value=upload_result
            ) as upload:
                app._finish_prompt_trace(trace, status="completed")

            upload.assert_called_once_with(trace_path)
            self.assertEqual(detached, [trace])
            self.assertEqual(app._last_prompt_trace_path, str(trace_path))
            self.assertEqual(app._last_prompt_trace_upload_result, upload_result)

    def test_prompt_trace_upload_failure_keeps_local_trace_available(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace_path = Path(temporary) / "prompt_trace.json"
            trace = type(
                "Trace",
                (),
                {"finish": lambda self, **kwargs: trace_path},
            )()
            app = MinimalWriterApp.__new__(MinimalWriterApp)
            app.engine = FakeEngine()

            failure = {"ok": False, "error": "GitHub CLI is not authenticated."}
            with patch(
                "minimal_writer.upload_prompt_trace", return_value=failure
            ) as upload:
                app._finish_prompt_trace(trace, status="completed")

            upload.assert_called_once_with(trace_path)
            self.assertEqual(app._last_prompt_trace_path, str(trace_path))
            self.assertEqual(app._last_prompt_trace_upload_result, failure)

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
        generated_prompts = [call[0] for call in app.engine.generate_calls]
        expected_author_prompts = [
            "Write the first scene.",
            "Write the next scene, picking up where that left off.",
        ]
        self.assertEqual(len(generated_prompts), len(expected_author_prompts))
        for generated, author_prompt in zip(generated_prompts, expected_author_prompts):
            self.assertTrue(generated.startswith(author_prompt))
            self.assertIn("\n\nSHOW THE WORK THROUGH DIALOGUE", generated)
            self.assertIn("The Computer is a speaking participant", generated)
        self.assertEqual(app.engine.start_calls, starts_after_load)
        self.assertEqual(app.engine.session_history, generated_prompts)

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
        self.assertIn("several connected paragraphs", CONTINUE_PROMPT)
        self.assertIn("rather than stopping after a single paragraph", CONTINUE_PROMPT)

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

    def test_editor_serializes_real_bold_and_italic_tags_to_markdown(self):
        widget = FakeStyledOutputBox(
            "A bold phrase and italic words.",
            bold_ranges=((2, 13),),
            italic_ranges=((18, 30),),
        )
        self.assertEqual(
            text_widget_to_markdown(widget),
            "A **bold phrase** and *italic words*.",
        )

    def test_editor_serializes_combined_bold_italic_tags(self):
        widget = FakeStyledOutputBox(
            "An emphasized phrase.",
            combined_ranges=((3, 20),),
        )
        self.assertEqual(
            text_widget_to_markdown(widget),
            "An ***emphasized phrase***.",
        )

    def test_save_does_not_add_or_remove_a_trailing_newline(self):
        original = "A sentence without a final newline."
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft.txt"

            save_text_document(path, original)

            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
