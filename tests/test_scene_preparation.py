import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from builder.scene_preparation import (
    build_scene_preparation_prompt,
    next_scene_coordinates,
    scene_number_from_label,
)
from minimal_writer import MinimalWriterApp


class ScenePreparationPromptTests(unittest.TestCase):
    def make_novel(self, root: Path, *, current_state=None, scene_text=None):
        root.mkdir(parents=True, exist_ok=True)
        story_bible = {
            "title": "Quiet Harbor",
            "premise": "A small coastal town faces an unexpected change.",
            "setting": "A working harbor in the present day.",
            "creative_direction": {
                "genres": ["Mystery", "Comedy"],
                "moods": ["Cozy", "Humorous"],
                "audience": "Adult",
                "explicit_adult_content": False,
            },
            "canon_rules": ["A very long rule that must not be sent to the planner."],
            "character_cards": ["Mara.json", "Jonah.json", "Private_Detail.json"],
        }
        (root / "story_bible.json").write_text(
            json.dumps(story_bible, indent=2), encoding="utf-8"
        )
        cards = {
            "Mara.json": {
                "name": "Mara", "role": "harbor pilot", "gender": "female",
                "sexual_orientation": "Straight", "personality": ["confident"],
            },
            "Jonah.json": {
                "name": "Jonah", "role": "mechanic", "gender": "male",
                "sexual_orientation": "Bisexual", "personality": ["quiet", "witty"],
            },
            "Private_Detail.json": {
                "name": "Private Detail", "role": "observer", "gender": "female",
                "sexual_orientation": "Straight", "personality": ["reserved"],
            },
        }
        for filename, card in cards.items():
            (root / filename).write_text(
                json.dumps(card, indent=2), encoding="utf-8"
            )
        if current_state is not None:
            (root / "current_state.json").write_text(
                json.dumps(current_state, indent=2), encoding="utf-8"
            )
        source = None
        if scene_text is not None:
            chapter = root / "Manuscript" / "Chapters" / "Chapter_01"
            chapter.mkdir(parents=True, exist_ok=True)
            source = chapter / "Chapter_01_Section_10.txt"
            source.write_text(scene_text, encoding="utf-8")
        return source

    def test_empty_novel_builds_an_opening_scene_prompt_without_scene_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Empty Novel"
            self.make_novel(root)

            prompt = build_scene_preparation_prompt(
                root, "Empty Novel", 1, 1
            )

            self.assertIn("Chapter 01, Scene 01", prompt)
            self.assertIn("Treat this as the novel's opening scene", prompt)
            self.assertIn("A small coastal town faces an unexpected change.", prompt)
            self.assertIn("A working harbor in the present day.", prompt)
            self.assertNotIn("A very long rule", prompt)
            self.assertNotIn("Private_Detail.json", prompt)
            self.assertIn("Genres: Mystery, Comedy", prompt)
            self.assertIn("Mood and tone: Cozy, Humorous", prompt)
            self.assertIn("Intended audience: Adult", prompt)
            self.assertIn("[Mara]", prompt)
            self.assertIn("[Jonah]", prompt)
            self.assertIn("[Private Detail]", prompt)
            self.assertIn("Sexual orientation: Straight", prompt)
            self.assertIn("Personality: quiet, witty", prompt)
            self.assertIn("not a checklist", prompt)
            self.assertIn("STORY OPENING AND PACING", prompt)
            self.assertIn("not a fixed scene count", prompt.lower())
            self.assertIn("For an ensemble, this may take several scenes", prompt)
            self.assertIn("artificially delay an urgent conflict", prompt.lower())
            self.assertFalse((root / "Manuscript").exists())
            self.assertFalse((root / "current_state.json").exists())

    def test_next_scene_uses_selected_ending_and_only_matching_state_details(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Existing Novel"
            state = {
                "chapter": 1,
                "scene": 11,
                "scene_completed": False,
                "current_situation": "The harbor lights have gone dark, and the ferry is overdue.",
                "location": {"primary": "The north pier"},
                "scene_cast": ["Mara", "Jonah"],
                "unresolved_questions": ["Why has the ferry not arrived?"],
                "active_clues": ["This should not be copied into the planning prompt."],
                "character_knowledge": {"Mara": ["Private knowledge should stay out."]},
            }
            source = self.make_novel(
                root,
                current_state=state,
                scene_text="The bell rang once across the water.\nMara watched the empty channel.",
            )
            original_bible = (root / "story_bible.json").read_bytes()
            original_state = (root / "current_state.json").read_bytes()
            original_scene = source.read_bytes()

            prompt = build_scene_preparation_prompt(
                root, "Existing Novel", 1, 11, source_scene_path=source
            )

            self.assertIn("Chapter 01, Scene 11", prompt)
            self.assertIn("Mara watched the empty channel.", prompt)
            self.assertIn("The harbor lights have gone dark", prompt)
            self.assertIn("The north pier", prompt)
            self.assertIn("Mara, Jonah", prompt)
            self.assertIn("Why has the ferry not arrived?", prompt)
            self.assertIn("[Mara]", prompt)
            self.assertIn("[Jonah]", prompt)
            self.assertNotIn("[Private Detail]", prompt)
            self.assertNotIn("This should not be copied", prompt)
            self.assertNotIn("Private knowledge should stay out", prompt)
            self.assertNotIn("A very long rule", prompt)
            self.assertEqual((root / "story_bible.json").read_bytes(), original_bible)
            self.assertEqual((root / "current_state.json").read_bytes(), original_state)
            self.assertEqual(source.read_bytes(), original_scene)

    def test_unrelated_current_state_is_not_added_to_selected_scene_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Novel"
            state = {
                "chapter": 3,
                "scene": 3,
                "current_situation": "This belongs to a different point in the story.",
                "scene_cast": ["Someone Else"],
            }
            source = self.make_novel(root, current_state=state, scene_text="The selected scene ends here.")

            prompt = build_scene_preparation_prompt(
                root, "Novel", 1, 11, source_scene_path=source
            )

            self.assertNotIn("This belongs to a different point", prompt)
            self.assertNotIn("Someone Else", prompt)
            self.assertIn("The selected scene ends here.", prompt)

    def test_completed_selected_scene_can_supply_its_saved_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Novel"
            state = {
                "chapter": 1,
                "scene": 10,
                "scene_completed": True,
                "current_situation": "The crew has secured the airlock.",
            }
            source = self.make_novel(root, current_state=state, scene_text="The hatch sealed.")

            prompt = build_scene_preparation_prompt(
                root, "Novel", 1, 11, source_scene_path=source
            )

            self.assertIn("The crew has secured the airlock.", prompt)

    def test_missing_story_bible_still_allows_a_basic_opening_scene_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Bare Novel"
            root.mkdir()

            prompt = build_scene_preparation_prompt(root, "Bare Novel", 1, 1)

            self.assertIn("Story: Bare Novel", prompt)
            self.assertIn("opening scene", prompt.lower())


class ScenePreparationDestinationTests(unittest.TestCase):
    def test_new_novel_defaults_to_chapter_one_scene_one(self):
        self.assertEqual(next_scene_coordinates(None, None), (1, 1))

    def test_empty_selected_chapter_defaults_to_its_first_scene(self):
        self.assertEqual(next_scene_coordinates(3, None), (3, 1))

    def test_selected_scene_label_without_a_saved_file_advances(self):
        self.assertEqual(next_scene_coordinates(1, None, 1), (1, 2))
        self.assertEqual(next_scene_coordinates(3, None, 12), (3, 13))

    def test_scene_number_is_read_from_selector_label(self):
        self.assertEqual(scene_number_from_label("Scene 01"), 1)
        self.assertEqual(scene_number_from_label("Scene 12"), 12)
        self.assertIsNone(scene_number_from_label(""))
        self.assertIsNone(scene_number_from_label("Not a scene"))

    def test_selected_text_scene_advances_to_the_next_scene(self):
        self.assertEqual(
            next_scene_coordinates(
                1, Path("Chapter_01_Section_10.txt")
            ),
            (1, 11),
        )

    def test_selected_odt_scene_advances_to_the_next_scene(self):
        self.assertEqual(
            next_scene_coordinates(
                2, Path("Chapter_02_Section_04.odt")
            ),
            (2, 5),
        )


class _FakePicker:
    def __init__(self):
        self.values = []

    def configure(self, **kwargs):
        if "values" in kwargs:
            self.values = list(kwargs["values"])


class _FakeVariable:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _FakeTextBox:
    def __init__(self, value=""):
        self.value = value

    def get(self, *_args):
        return self.value

    def delete(self, *_args):
        self.value = ""

    def insert(self, _index, value):
        self.value = value


class _ImmediateThread:
    def __init__(self, target, daemon=None):
        self.target = target

    def start(self):
        self.target()


class _DeferredThread:
    instances = []

    def __init__(self, target, daemon=None):
        self.target = target
        self.__class__.instances.append(self)

    def start(self):
        return None


class MinimalWriterPrepareSceneTests(unittest.TestCase):
    def make_app(self, novel_path, *, existing_prompt=""):
        app = object.__new__(MinimalWriterApp)
        app.busy = False
        app.writing = False
        app.stop_requested = False
        app.loaded_model = Path("/models/test.gguf")
        app.engine = SimpleNamespace(child=None, clear_context=Mock())
        app.root = SimpleNamespace(after=lambda _delay, callback: callback())
        app.novel_var = SimpleNamespace(get=lambda: "Test Novel")
        app.novel_packages = {"Test Novel": Path(novel_path)}
        app.chapter_var = _FakeVariable()
        app.chapter_numbers = {}
        app.chapter_picker = _FakePicker()
        app.scene_var = _FakeVariable()
        app.scene_picker = _FakePicker()
        app.scene_files = {}
        app.prompt_box = _FakeTextBox(existing_prompt)
        app.status_var = SimpleNamespace(set=Mock())
        app._update_controls = Mock()
        app._showinfo = Mock()
        app._showerror = Mock()
        app._askyesno = Mock(return_value=True)
        app._scene_preparation_destination = (1, 1)
        return app

    def test_prepare_scene_fills_prompt_box_for_an_empty_novel(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Test Novel"
            root.mkdir()
            (root / "story_bible.json").write_text(
                json.dumps({"title": "Test Novel", "premise": "A new beginning."}),
                encoding="utf-8",
            )
            app = self.make_app(root)

            with patch("minimal_writer.write_from_prompt", return_value="A quiet arrival sets the story in motion.") as generate, \
                 patch("minimal_writer.threading.Thread", _ImmediateThread):
                MinimalWriterApp.prepare_scene(app)

            self.assertEqual(app.prompt_box.value, "A quiet arrival sets the story in motion.")
            self.assertEqual(app._scene_preparation_destination, (1, 1))
            self.assertEqual(app.chapter_var.get(), "Chapter 01")
            self.assertEqual(app.chapter_picker.values, ["Chapter 01"])
            self.assertEqual(app.scene_var.get(), "Scene 01")
            self.assertEqual(app.scene_picker.values, ["Scene 01"])
            self.assertEqual(app.scene_files, {})
            self.assertIn("Chapter 01, Scene 01", generate.call_args.args[1])
            app.engine.clear_context.assert_called_once_with()
            self.assertIn("Model conversation cleared", app.status_var.set.call_args.args[0])
            self.assertFalse(app.busy)
            self.assertFalse(app.writing)

    def test_prepare_scene_uses_selected_scene_as_reference_and_advances(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Test Novel"
            root.mkdir()
            (root / "story_bible.json").write_text(
                json.dumps({"title": "Test Novel", "premise": "Keep going."}),
                encoding="utf-8",
            )
            source = root / "Chapter_01_Section_10.txt"
            source.write_text("The last line of Scene 10.", encoding="utf-8")
            app = self.make_app(root, existing_prompt="An old prompt.")
            app.chapter_var = _FakeVariable("Chapter 01")
            app.chapter_numbers = {"Chapter 01": 1}
            app.scene_var = _FakeVariable("Scene 10")
            app.scene_files = {"Scene 10": source}

            with patch("minimal_writer.write_from_prompt", return_value="Begin with the next morning.") as generate, \
                 patch("minimal_writer.threading.Thread", _ImmediateThread):
                MinimalWriterApp.prepare_scene(app)

            self.assertEqual(app._scene_preparation_destination, (1, 11))
            self.assertIn("Chapter 01, Scene 11", generate.call_args.args[1])
            self.assertIn("The last line of Scene 10.", generate.call_args.args[1])
            self.assertEqual(app.prompt_box.value, "Begin with the next morning.")
            self.assertEqual(app.chapter_var.get(), "Chapter 01")
            self.assertEqual(app.scene_var.get(), "Scene 11")
            self.assertIn("Scene 11", app.scene_picker.values)
            self.assertNotIn("Scene 11", app.scene_files)
            confirmation = app._askyesno.call_args.args
            self.assertEqual(confirmation[0], "Replace prompt box text?")
            self.assertIn("preparing Chapter 01, Scene 11", confirmation[1])
            self.assertIn("ONLY the text in the What should it write? box", confirmation[1])
            self.assertIn("will NOT overwrite, save, or modify", confirmation[1])

    def test_prepare_scene_clears_model_context_after_generating_suggestion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Test Novel"
            root.mkdir()
            (root / "story_bible.json").write_text("{}", encoding="utf-8")
            app = self.make_app(root)
            events = []

            def generate(_engine, _prompt):
                events.append("generate")
                return "A quiet afternoon continues."

            def clear_context():
                events.append("clear_context")

            app.engine.clear_context.side_effect = clear_context
            with (
                patch("minimal_writer.write_from_prompt", side_effect=generate),
                patch("minimal_writer.threading.Thread", _ImmediateThread),
            ):
                MinimalWriterApp.prepare_scene(app)

            self.assertEqual(events, ["generate", "clear_context"])
            self.assertEqual(app.prompt_box.value, "A quiet afternoon continues.")
            self.assertIsNotNone(app.loaded_model)
            self.assertIn("Model conversation cleared", app.status_var.set.call_args.args[0])

    def test_prepare_scene_keeps_suggestion_and_requires_reload_if_context_clear_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Test Novel"
            root.mkdir()
            (root / "story_bible.json").write_text("{}", encoding="utf-8")
            app = self.make_app(root)
            app.engine.clear_context.side_effect = RuntimeError("clear failed")

            with (
                patch("minimal_writer.write_from_prompt", return_value="Keep this suggestion."),
                patch("minimal_writer.threading.Thread", _ImmediateThread),
            ):
                MinimalWriterApp.prepare_scene(app)

            self.assertEqual(app.prompt_box.value, "Keep this suggestion.")
            self.assertIsNone(app.loaded_model)
            self.assertIn("Load the model again", app.status_var.set.call_args.args[0])
            self.assertIn("clear failed", app.status_var.set.call_args.args[0])
            self.assertFalse(app.busy)
            self.assertFalse(app.writing)

    def test_cancel_keeps_existing_prompt_and_does_not_call_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Test Novel"
            root.mkdir()
            (root / "story_bible.json").write_text("{}", encoding="utf-8")
            app = self.make_app(root, existing_prompt="My unfinished idea")
            app._askyesno.return_value = False

            with patch("minimal_writer.write_from_prompt") as generate:
                MinimalWriterApp.prepare_scene(app)

            self.assertEqual(app.prompt_box.value, "My unfinished idea")
            generate.assert_not_called()
            self.assertFalse(app.busy)




    def test_prompt_edits_made_during_preparation_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Test Novel"
            root.mkdir()
            (root / "story_bible.json").write_text("{}", encoding="utf-8")
            app = self.make_app(root)
            _DeferredThread.instances.clear()

            with patch("minimal_writer.write_from_prompt", return_value="Generated suggestion."), \
                 patch("minimal_writer.threading.Thread", _DeferredThread):
                MinimalWriterApp.prepare_scene(app)
                app.prompt_box.value = "My newer edits."
                _DeferredThread.instances[-1].target()

            self.assertEqual(app.prompt_box.value, "My newer edits.")
            self.assertFalse(app.busy)
            self.assertFalse(app.writing)
            self.assertIn("Your edits were kept", app.status_var.set.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
