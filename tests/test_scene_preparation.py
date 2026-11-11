import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from builder.odt_document import read_document
from builder.novel_browser import list_scene_files
from builder.scene_preparation import (
    build_scene_preparation_prompt,
    next_scene_coordinates,
    resolve_scene_preparation_target,
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
            "canon_rules": ["The harbor pilot does not leave the harbor during winter storms."],
            "relationships": {"Mara-Jonah": "Longtime friends and colleagues."},
            "writing_preferences": "Let Chapter One take its time and introduce the people before the mystery escalates.",
            "character_cards": ["Mara.json", "Jonah.json", "Private_Detail.json"],
        }
        (root / "story_bible.json").write_text(
            json.dumps(story_bible, indent=2), encoding="utf-8"
        )
        cards = {
            "Mara.json": {
                "name": "Mara", "role": "harbor pilot",
                "occupation": "Harbor Operations, Pilot",
                "background": "Experienced harbor pilot who knows local channels and winter conditions.",
                "skills": ["navigation", "tide assessment", "small-vessel handling"],
                "hobbies": ["sailing", "woodworking"],
                "gender": "female", "sexual_orientation": "Straight",
                "personality": ["confident"],
            },
            "Jonah.json": {
                "name": "Jonah", "role": "mechanic",
                "skills": ["engine maintenance", "mechanical troubleshooting"],
                "gender": "male", "sexual_orientation": "Bisexual",
                "personality": ["quiet", "witty"],
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
            self.assertIn("This is the opening scene; no previous scene has been saved.", prompt)
            self.assertNotIn("PREVIOUS SCENE CONTINUITY", prompt)
            self.assertIn("A small coastal town faces an unexpected change.", prompt)
            self.assertIn("FIXED CANON", prompt)
            self.assertIn("A working harbor in the present day.", prompt)
            self.assertIn("The harbor pilot does not leave the harbor during winter storms.", prompt)
            self.assertIn("Mara-Jonah: Longtime friends and colleagues.", prompt)
            self.assertIn("Let Chapter One take its time", prompt)
            self.assertNotIn("Private_Detail.json", prompt)
            self.assertIn("Genres: Mystery, Comedy", prompt)
            self.assertIn("Mystery guidance:", prompt)
            self.assertIn("Mood and tone: Cozy, Humorous", prompt)
            self.assertIn("Intended audience: Adult", prompt)
            self.assertIn("Adult audience guidance:", prompt)
            self.assertIn("Explicit adult content is not enabled", prompt)
            self.assertNotIn("Adventure guidance:", prompt)
            self.assertIn("[Mara]", prompt)
            self.assertIn("[Jonah]", prompt)
            self.assertIn("[Private Detail]", prompt)
            self.assertIn("Sexual orientation: Straight", prompt)
            self.assertIn("Occupation / department: Harbor Operations, Pilot", prompt)
            self.assertIn(
                "Background / experience: Experienced harbor pilot",
                prompt,
            )
            self.assertIn(
                "Skills / expertise: navigation, tide assessment, small-vessel handling",
                prompt,
            )
            self.assertIn("Interests / hobbies: sailing, woodworking", prompt)
            self.assertIn(
                "Skills / expertise: engine maintenance, mechanical troubleshooting",
                prompt,
            )
            self.assertIn("Personality: quiet, witty", prompt)
            self.assertIn("CHARACTER REFERENCES", prompt)
            self.assertIn("Do not treat hobbies or general interests as professional qualifications", prompt)
            self.assertNotIn("SCENE CRAFT GUIDANCE", prompt)
            self.assertNotIn("STORY OPENING AND PACING", prompt)
            self.assertNotIn("supplementary guidance", prompt)
            self.assertNotIn("A quiet or ordinary moment is valid scene material", prompt)
            self.assertIn("Return one concise 'Scene direction:'", prompt)
            self.assertIn("one destination scene only", prompt)
            self.assertIn("Do not combine distinct time/place setups", prompt)
            self.assertIn("separate Prepare Scene request", prompt)
            self.assertIn("every concrete event, action, or moment explicitly requested", prompt)
            self.assertIn("as an AUTHOR-REQUIRED BEAT", prompt)
            self.assertIn("must happen in this destination scene", prompt)
            self.assertIn("do not omit, soften, replace, or defer", prompt)
            self.assertIn("QWEN-SELECTED ADDITIONAL BEATS", prompt)
            self.assertIn("zero, one, or as many", prompt)
            self.assertIn("There is no quota or cap", prompt)
            self.assertIn("where the scene ends to the Writer", prompt)
            self.assertNotIn("Natural endpoint:", prompt)
            self.assertNotIn("stop at the natural endpoint", prompt.casefold())
            self.assertFalse((root / "Manuscript").exists())
            self.assertFalse((root / "current_state.json").exists())

    def test_scene_preparation_includes_location_details_as_open_reference_material(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Novel with Locations"
            self.make_novel(root)
            bible_path = root / "story_bible.json"
            bible = json.loads(bible_path.read_text(encoding="utf-8"))
            bible["locations"] = {
                "Supply Closet": {},
                "Recreation Room": {
                    "type": "room",
                    "description": "A simple recreation space.",
                    "geography": "Inside the community center, off the main hall.",
                    "notable_details": ["A worn couch", "A folding game table"],
                },
            }
            bible_path.write_text(json.dumps(bible), encoding="utf-8")

            prompt = build_scene_preparation_prompt(
                root, "Novel with Locations", 1, 1
            )

        self.assertIn("ESTABLISHED LOCATION REFERENCES FROM THIS NOVEL'S STORY BIBLE", prompt)
        self.assertIn("not a closed location list", prompt)
        self.assertIn("Supply Closet", prompt)
        self.assertIn("Recreation Room", prompt)
        self.assertIn("A simple recreation space.", prompt)
        self.assertIn("Inside the community center, off the main hall.", prompt)
        self.assertIn("A worn couch", prompt)
        self.assertIn("A folding game table", prompt)
        self.assertNotIn("a demand to use every location", prompt)

    def test_planner_receives_all_story_bible_canon_and_relationship_entries(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Comprehensive Novel"
            self.make_novel(root)
            bible_path = root / "story_bible.json"
            bible = json.loads(bible_path.read_text(encoding="utf-8"))
            bible["premise"] = "Premise opening. " + ("premise detail " * 70) + "Premise ending retained."
            bible["setting"] = "Household and setting opening. " + ("setting detail " * 70) + "Setting ending retained."
            bible["canon_rules"] = [
                f"Canon entry {index}: preserve this established fact."
                for index in range(1, 15)
            ]
            bible["relationships"] = {
                f"Connection {index}": f"Established relationship detail {index}."
                for index in range(1, 19)
            }
            bible_path.write_text(json.dumps(bible), encoding="utf-8")

            prompt = build_scene_preparation_prompt(
                root, "Comprehensive Novel", 1, 1,
                author_direction="Have Mara receive a message.",
            )

        self.assertIn("Premise ending retained.", prompt)
        self.assertIn("Setting ending retained.", prompt)
        self.assertIn("Canon entry 14", prompt)
        self.assertIn("Connection 18: Established relationship detail 18.", prompt)

    def test_author_direction_events_are_required_beats_and_qwen_can_add_its_own(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Directed Novel"
            source = self.make_novel(root, scene_text="The crew finished their diagnostics.")
            direction = "Have Mission Control acknowledge the advisory and request updated readings."

            prompt = build_scene_preparation_prompt(
                root, "Directed Novel", 1, 2,
                source_scene_path=source,
                author_direction=direction,
            )

            self.assertIn("AUTHOR'S DIRECTION", prompt)
            self.assertIn(direction, prompt)
            self.assertIn("AUTHOR-REQUIRED BEAT", prompt)
            self.assertIn("Only events the author directly requested", prompt)
            self.assertIn("do not promote your own ideas", prompt)
            self.assertIn("QWEN-SELECTED ADDITIONAL BEATS", prompt)
            # A Planner request that names no character still receives every card.
            self.assertIn("[Mara]", prompt)
            self.assertIn("[Jonah]", prompt)
            self.assertIn("[Private Detail]", prompt)
            self.assertIn("Experienced harbor pilot", prompt)
            self.assertIn("Longtime friends and colleagues", prompt)
            self.assertIn("There is no quota or cap", prompt)
            self.assertLess(
                prompt.index("AUTHOR'S DIRECTION"),
                prompt.index("AUTHOR-REQUIRED BEAT"),
            )

    def test_blank_author_direction_adds_no_extra_direction_section(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Unsteered Novel"
            source = self.make_novel(root, scene_text="The crew finished their diagnostics.")

            prompt = build_scene_preparation_prompt(
                root, "Unsteered Novel", 1, 2,
                source_scene_path=source,
                author_direction="  \n ",
            )

            self.assertNotIn(
                "AUTHOR'S DIRECTION", prompt
            )

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
                "active_objectives": {
                    "Daniel": "Deliver the report Elena requested before the end of the workday."
                },
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
            self.assertIn("PREVIOUS SCENE CONTINUITY", prompt)
            self.assertIn(
                "Let the new scene feel like a natural continuation of the same story",
                prompt,
            )
            self.assertIn("time, place, and focus may change when it makes sense", prompt)
            self.assertNotIn("Continue directly from the final moment", prompt)
            self.assertNotIn("Begin the Scene direction by", prompt)
            self.assertIn("The harbor lights have gone dark", prompt)
            self.assertIn("The north pier", prompt)
            self.assertIn("Mara, Jonah", prompt)
            self.assertIn("Why has the ferry not arrived?", prompt)
            self.assertNotIn("OUTSTANDING CHARACTER OBJECTIVES", prompt)
            self.assertNotIn(
                "Daniel: Deliver the report Elena requested before the end of the workday.",
                prompt,
            )
            self.assertIn("[Mara]", prompt)
            self.assertIn("[Jonah]", prompt)
            self.assertNotIn("[Private Detail]", prompt)
            self.assertNotIn("This should not be copied", prompt)
            self.assertNotIn("Private knowledge should stay out", prompt)
            self.assertIn("The harbor pilot does not leave the harbor during winter storms.", prompt)
            self.assertIn("Mara-Jonah: Longtime friends and colleagues.", prompt)
            self.assertIn("Let Chapter One take its time", prompt)
            self.assertEqual((root / "story_bible.json").read_bytes(), original_bible)
            self.assertEqual((root / "current_state.json").read_bytes(), original_state)
            self.assertEqual(source.read_bytes(), original_scene)

    def test_long_previous_scene_is_included_in_full_without_truncation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Novel"
            opening = "THE OPENING DETAIL THAT MUST SURVIVE."
            middle = "AN IMPORTANT DETAIL FROM THE MIDDLE OF THE SCENE."
            ending = "THE FINAL MOMENT OF THE PREVIOUS SCENE."
            scene_text = (
                opening
                + "\n\n"
                + ("intervening prose " * 180)
                + middle
                + (" more intervening prose" * 180)
                + "\n\n"
                + ending
            )
            source = self.make_novel(root, scene_text=scene_text)

            prompt = build_scene_preparation_prompt(
                root, "Novel", 1, 11, source_scene_path=source
            )

            self.assertIn("IMMEDIATELY PRECEDING SAVED SCENE (full continuity reference)", prompt)
            self.assertIn(opening, prompt)
            self.assertIn(middle, prompt)
            self.assertIn(ending, prompt)
            self.assertIn(scene_text, prompt)

    def test_story_time_anchor_is_available_when_saved_state_position_is_older(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Novel"
            state = {
                "chapter": 1,
                "scene": 1,
                "status": "story_start",
                "time_of_day": "Day 1, 16:00 (4:00 PM), late afternoon at the Mars outpost.",
                "current_situation": "This old opening situation must not be treated as current.",
                "scene_cast": [],
            }
            earlier_activity = "The crew finished dinner and started a board game.\n"
            scene_text = earlier_activity + ("The game continued with friendly conversation. " * 65)
            source = self.make_novel(root, current_state=state, scene_text=scene_text)

            prompt = build_scene_preparation_prompt(
                root, "Novel", 1, 11, source_scene_path=source
            )

            self.assertIn("Latest saved in-story time: Day 1, 16:00", prompt)
            self.assertIn("The game continued with friendly conversation.", prompt)
            self.assertNotIn("This old opening situation must not be treated as current.", prompt)
            self.assertIn("Return one concise 'Scene direction:'", prompt)
            self.assertNotIn("Natural endpoint:", prompt)
            self.assertNotIn("STORY OPENING AND PACING", prompt)
            self.assertLess(len(scene_text), 6000)

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


    def test_pending_prepared_scene_retry_keeps_destination_and_previous_scene(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Novel"
            root.mkdir()
            previous = root / "Chapter_02_Section_19.odt"
            pending_scene = root / "Chapter_02_Section_20.odt"

            retry = resolve_scene_preparation_target(
                2,
                None,
                20,
                novel_path=root,
                pending_destination=(2, 20),
                pending_novel_path=root,
                pending_source_scene_path=previous,
            )
            after_save = resolve_scene_preparation_target(
                2,
                pending_scene,
                20,
                novel_path=root,
                pending_destination=(2, 20),
                pending_novel_path=root,
                pending_source_scene_path=previous,
            )

        self.assertEqual(retry, (2, 20, previous, True))
        self.assertEqual(after_save, (2, 21, pending_scene, False))

    def test_pending_scene_is_not_reused_for_a_different_novel_or_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Novel"
            other_novel = Path(temp) / "Other Novel"
            root.mkdir()
            other_novel.mkdir()
            previous = root / "Chapter_02_Section_19.odt"

            different_novel = resolve_scene_preparation_target(
                2,
                None,
                20,
                novel_path=other_novel,
                pending_destination=(2, 20),
                pending_novel_path=root,
                pending_source_scene_path=previous,
            )
            different_selection = resolve_scene_preparation_target(
                2,
                previous,
                19,
                novel_path=root,
                pending_destination=(2, 20),
                pending_novel_path=root,
                pending_source_scene_path=previous,
            )

        self.assertEqual(different_novel, (2, 21, None, False))
        self.assertEqual(different_selection, (2, 20, previous, False))


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
    def make_app(self, novel_path, *, existing_prompt="", author_direction=""):
        app = object.__new__(MinimalWriterApp)
        app.busy = False
        app.writing = False
        app.stop_requested = False
        app.loaded_model = Path("/models/test.gguf")
        app.engine = SimpleNamespace(
            child=SimpleNamespace(isalive=lambda: True),
            clear_context=Mock(),
        )
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
        app.author_direction_box = _FakeTextBox(author_direction)
        app.status_var = SimpleNamespace(set=Mock())
        app._update_controls = Mock()
        app._showinfo = Mock()
        app._showerror = Mock()
        app._askyesno = Mock(return_value=True)
        app._scene_preparation_destination = (1, 1)
        app._scene_preparation_original_author_direction = ""
        app._scene_preparation_source_scene_path = None
        app._prepared_scene_destination = None
        app._prepared_scene_novel_path = None
        app._prepared_scene_source_scene_path = None
        app._prepared_author_required_direction = ""
        app._scene_preparation_required_author_direction = ""
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
            self.assertIn("Planner conversation cleared", app.status_var.set.call_args.args[0])
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

    def test_prepare_scene_retry_keeps_same_scene_and_previous_scene_context(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Test Novel"
            chapter = root / "Manuscript" / "Chapters" / "Chapter_01"
            chapter.mkdir(parents=True)
            (root / "story_bible.json").write_text("{}", encoding="utf-8")
            source = chapter / "Chapter_01_Section_10.txt"
            source.write_text("The accepted ending of Scene 10.", encoding="utf-8")

            app = self.make_app(root)
            app.chapter_var = _FakeVariable("Chapter 01")
            app.chapter_numbers = {"Chapter 01": 1}
            app.scene_var = _FakeVariable("Scene 10")
            app.scene_files = {"Scene 10": source}

            with (
                patch(
                    "minimal_writer.write_from_prompt",
                    side_effect=("First suggestion.", "Second suggestion."),
                ) as generate,
                patch("minimal_writer.threading.Thread", _ImmediateThread),
            ):
                MinimalWriterApp.prepare_scene(app)
                self.assertEqual(app.scene_var.get(), "Scene 11")
                self.assertEqual(app._prepared_scene_destination, (1, 11))

                app.author_direction_box.value = (
                    "Have Daniel walk over to Elena and talk to her about the overdue report."
                )
                MinimalWriterApp.prepare_scene(app)

            self.assertEqual(generate.call_count, 2)
            first_prompt = generate.call_args_list[0].args[1]
            retry_prompt = generate.call_args_list[1].args[1]
            self.assertIn("Chapter 01, Scene 11", first_prompt)
            self.assertIn("The accepted ending of Scene 10.", first_prompt)
            self.assertNotIn("PREVIOUS PREPARED DIRECTION TO REFINE", first_prompt)
            self.assertIn("Chapter 01, Scene 11", retry_prompt)
            self.assertIn("The accepted ending of Scene 10.", retry_prompt)
            self.assertIn("PREVIOUS PREPARED DIRECTION TO REFINE", retry_prompt)
            self.assertIn("First suggestion.", retry_prompt)
            self.assertIn("Refine the previous direction rather than starting over.", retry_prompt)
            self.assertIn("walk over to Elena", retry_prompt)
            self.assertEqual(app._scene_preparation_destination, (1, 11))
            self.assertEqual(app._prepared_scene_destination, (1, 11))
            self.assertEqual(app.scene_var.get(), "Scene 11")
            self.assertEqual(app.prompt_box.value, "Second suggestion.")
            self.assertEqual(app.author_direction_box.value, "")

    def test_prepare_scene_uses_and_clears_author_direction_after_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Test Novel"
            root.mkdir()
            (root / "story_bible.json").write_text("{}", encoding="utf-8")
            direction = "Have Mission Control acknowledge the report, without offering a solution."
            app = self.make_app(root, author_direction=direction)

            with (
                patch(
                    "minimal_writer.write_from_prompt",
                    side_effect=("Earth acknowledges receipt.", "A fuller direction."),
                ) as generate,
                patch("minimal_writer.threading.Thread", _ImmediateThread),
            ):
                MinimalWriterApp.prepare_scene(app)

                self.assertEqual(app._prepared_author_required_direction, direction)
                self.assertEqual(app.author_direction_box.value, "")

                # Retrying the same prepared scene must retain the original required event
                # even though the visible Author's Direction box was cleared.
                MinimalWriterApp.prepare_scene(app)

            self.assertIn(direction, generate.call_args_list[0].args[1])
            self.assertIn(direction, generate.call_args_list[1].args[1])
            self.assertEqual(app._prepared_author_required_direction, direction)
            self.assertEqual(app.prompt_box.value, "A fuller direction.")
            self.assertEqual(app.author_direction_box.value, "")

    def test_author_direction_edits_during_preparation_are_kept(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Test Novel"
            root.mkdir()
            (root / "story_bible.json").write_text("{}", encoding="utf-8")
            app = self.make_app(root, author_direction="Use the original direction.")
            _DeferredThread.instances.clear()

            with (
                patch("minimal_writer.write_from_prompt", return_value="Generated suggestion."),
                patch("minimal_writer.threading.Thread", _DeferredThread),
            ):
                MinimalWriterApp.prepare_scene(app)
                app.author_direction_box.value = "A new direction typed while preparing."
                _DeferredThread.instances[-1].target()

            self.assertEqual(app.prompt_box.value, "")
            self.assertEqual(
                app.author_direction_box.value,
                "A new direction typed while preparing.",
            )
            self.assertIn("Your edits were kept", app.status_var.set.call_args.args[0])

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
            self.assertIn("Planner conversation cleared", app.status_var.set.call_args.args[0])

    def test_prepare_scene_keeps_suggestion_and_loads_writer_on_write_if_context_clear_fails(self):
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
            self.assertIn(
                "selected writing model will load automatically when you press Write",
                app.status_var.set.call_args.args[0],
            )
            self.assertIn("clear failed", app.status_var.set.call_args.args[0])
            self.assertFalse(app.busy)
            self.assertFalse(app.writing)

    def test_cancel_keeps_existing_prompt_and_does_not_call_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Test Novel"
            root.mkdir()
            (root / "story_bible.json").write_text("{}", encoding="utf-8")
            app = self.make_app(
                root,
                existing_prompt="My unfinished idea",
                author_direction="Have Earth respond in this scene.",
            )
            app._askyesno.return_value = False

            with patch("minimal_writer.write_from_prompt") as generate:
                MinimalWriterApp.prepare_scene(app)

            self.assertEqual(app.prompt_box.value, "My unfinished idea")
            self.assertEqual(
                app.author_direction_box.value, "Have Earth respond in this scene."
            )
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


class MinimalWriterSaveNewSceneTests(unittest.TestCase):
    def make_app(self, novel_path, *, scene_label="Scene 02", output="A finished scene."):
        app = object.__new__(MinimalWriterApp)
        app.busy = False
        app.current_file = None
        app.selected_scene_source = None
        app.saved_output_text = ""
        app.novel_var = _FakeVariable("The Long Way Home")
        app.novel_packages = {"The Long Way Home": Path(novel_path)}
        app.chapter_var = _FakeVariable("Chapter 01")
        app.chapter_numbers = {"Chapter 01": 1}
        app.scene_var = _FakeVariable(scene_label)
        app.scene_picker = _FakePicker()
        app.scene_files = {}
        app.status_var = SimpleNamespace(set=Mock())
        app._output_text = Mock(return_value=output)
        app._update_controls = Mock()
        app._update_document_title = Mock()
        app._showinfo = Mock()
        app._showerror = Mock()
        return app

    def test_save_new_scene_uses_selected_novel_chapter_and_scene_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "The Long Way Home"
            (root / "Manuscript" / "Chapters" / "Chapter_01").mkdir(parents=True)
            app = self.make_app(root, scene_label="Scene 02", output="Scene two prose.")
            app._prepared_scene_destination = (1, 2)
            app._prepared_scene_novel_path = root

            saved = MinimalWriterApp.save_new_scene(app)

            target = (
                root / "Manuscript" / "Chapters" / "Chapter_01"
                / "Chapter_01_Section_02.odt"
            )
            self.assertTrue(saved)
            self.assertTrue(target.is_file())
            self.assertEqual(read_document(target), "Scene two prose.")
            self.assertEqual(app.scene_var.get(), "Scene 02")
            self.assertEqual(app.scene_files["Scene 02"], target)
            self.assertEqual(app.selected_scene_source, target.resolve())
            self.assertIsNone(app._prepared_scene_destination)
            self.assertIsNone(app._prepared_scene_novel_path)
            self.assertIsNone(app._prepared_scene_source_scene_path)
            self.assertIn("Saved new scene:", app.status_var.set.call_args.args[0])
            self.assertFalse(app._showerror.called)

    def test_save_new_scene_appends_after_existing_scene_when_dropdown_points_at_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "The Long Way Home"
            chapter = root / "Manuscript" / "Chapters" / "Chapter_01"
            chapter.mkdir(parents=True)
            (chapter / "Chapter_01_Section_01.txt").write_text(
                "Already accepted.", encoding="utf-8"
            )
            app = self.make_app(root, scene_label="Scene 01", output="Next scene prose.")

            saved = MinimalWriterApp.save_new_scene(app)

            target = chapter / "Chapter_01_Section_02.odt"
            self.assertTrue(saved)
            self.assertTrue(target.is_file())
            self.assertEqual(read_document(target), "Next scene prose.")
            self.assertEqual(app.scene_var.get(), "Scene 02")
            self.assertEqual(sorted(n for n, _ in list_scene_files(root, 1)), [1, 2])

    def test_save_new_scene_never_overwrites_existing_odt_or_txt_scene(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "The Long Way Home"
            chapter = root / "Manuscript" / "Chapters" / "Chapter_01"
            chapter.mkdir(parents=True)
            existing = chapter / "Chapter_01_Section_02.txt"
            existing.write_text("Keep this accepted scene.", encoding="utf-8")
            app = self.make_app(root, scene_label="Scene 02")

            saved = MinimalWriterApp.save_new_scene(app)

            target = chapter / "Chapter_01_Section_03.odt"
            self.assertTrue(saved)
            self.assertEqual(existing.read_text(encoding="utf-8"), "Keep this accepted scene.")
            self.assertTrue(target.is_file())
            self.assertEqual(app.scene_var.get(), "Scene 03")

    def test_save_new_scene_refuses_empty_output_and_preserves_manuscript(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "The Long Way Home"
            chapter = root / "Manuscript" / "Chapters" / "Chapter_01"
            chapter.mkdir(parents=True)
            app = self.make_app(root, output="   ")

            saved = MinimalWriterApp.save_new_scene(app)

            self.assertFalse(saved)
            self.assertEqual(list(chapter.iterdir()), [])
            self.assertTrue(app._showinfo.called)


if __name__ == "__main__":
    unittest.main()
