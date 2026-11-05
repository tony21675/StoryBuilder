import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from builder.scene_state_update import (
    advance_saved_scene_markers,
    build_saved_scene_state_prompt,
    load_current_state,
    merge_saved_scene_state,
    parse_saved_scene_state_patch,
    write_current_state,
)
from minimal_writer import MinimalWriterApp


class FakeStatus:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value


class FakeRoot:
    def after(self, _delay, callback):
        callback()


class ImmediateThread:
    def __init__(self, target, daemon=None):
        self.target = target

    def start(self):
        self.target()


class FakeStateEngine:
    def __init__(self, response):
        self.response = response
        self.clear_context_calls = 0
        self.prompts = []

    def clear_context(self):
        self.clear_context_calls += 1

    def generate(self, prompt):
        self.prompts.append(prompt)
        return self.response


class SavedSceneStateUpdateTests(unittest.TestCase):
    def setUp(self):
        self.starting_state = {
            "story_format_version": "1.0",
            "chapter": 1,
            "scene": 1,
            "status": "story_start",
            "time_of_day": "Day 2, nighttime at the Mars research outpost.",
            "location": "",
            "scene_cast": [],
            "events": [],
            "continuity_notes": [],
        }

    def test_scene_markers_advance_without_guessing_story_time(self):
        updated = advance_saved_scene_markers(self.starting_state, 2, 19)

        self.assertEqual(updated["chapter"], 2)
        self.assertEqual(updated["scene"], 19)
        self.assertEqual(updated["status"], "in_progress")
        self.assertTrue(updated["scene_completed"])
        self.assertFalse(updated["chapter_completed"])
        self.assertEqual(
            updated["time_of_day"],
            "Day 2, nighttime at the Mars research outpost.",
        )
        self.assertEqual(self.starting_state["chapter"], 1)

    def test_prompt_uses_existing_day_night_baseline_and_saved_scene_ending(self):
        prose = (
            "Opening paragraph from earlier in the scene.\n\n"
            "The crew remained together in the Recreation Room.\n\n"
            "Elena stretched her neck and let out a quiet sigh."
        )
        prompt = build_saved_scene_state_prompt(
            advance_saved_scene_markers(self.starting_state, 2, 20),
            2,
            20,
            prose,
        )

        self.assertIn("Day 2, nighttime at the Mars research outpost.", prompt)
        self.assertIn("SAVED SCENE: Chapter 02, Scene 20", prompt)
        self.assertIn("Elena stretched her neck", prompt)
        self.assertIn("current_situation", prompt)
        self.assertIn("time_of_day", prompt)
        self.assertIn("Do not run a scene comparison or review.", prompt)

    def test_parse_and_merge_apply_only_supported_ending_state_fields(self):
        marked = advance_saved_scene_markers(self.starting_state, 2, 20)
        response = json.dumps({
            "current_situation": "The crew is winding down in the Recreation Room.",
            "time_of_day": "Day 2, late night at the Mars research outpost.",
            "status": "story_start",
            "chapter": 1,
            "unrelated": "ignore this",
        })

        patch = parse_saved_scene_state_patch(marked, response)
        updated = merge_saved_scene_state(marked, patch, 2, 20)

        self.assertEqual(
            set(patch),
            {"current_situation", "time_of_day"},
        )
        self.assertEqual(updated["chapter"], 2)
        self.assertEqual(updated["scene"], 20)
        self.assertTrue(updated["scene_completed"])
        self.assertEqual(updated["status"], "in_progress")
        self.assertEqual(
            updated["time_of_day"],
            "Day 2, late night at the Mars research outpost.",
        )
        self.assertEqual(
            updated["scene_cast"],
            self.starting_state["scene_cast"],
        )

    def test_invalid_state_response_does_not_create_a_patch(self):
        marked = advance_saved_scene_markers(self.starting_state, 2, 20)
        with self.assertRaises(ValueError):
            parse_saved_scene_state_patch(marked, "The time is later now.")

    def test_current_state_is_written_and_read_as_one_json_object(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "current_state.json"
            expected = advance_saved_scene_markers(self.starting_state, 2, 19)

            write_current_state(path, expected)
            actual = load_current_state(path)

        self.assertEqual(actual, expected)

    def test_writer_save_update_uses_one_pass_without_a_scene_comparison(self):
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "current_state.json"
            state_path.write_text(
                json.dumps(self.starting_state),
                encoding="utf-8",
            )
            engine = FakeStateEngine(json.dumps({
                "current_situation": "The six crew members are settling down after charades.",
                "time_of_day": "Day 2, late night at the Mars research outpost.",
            }))

            app = MinimalWriterApp.__new__(MinimalWriterApp)
            app.engine = engine
            app.loaded_model = Path("/models/test.gguf")
            app.root = FakeRoot()
            app.status_var = FakeStatus()
            app.busy = False
            app.writing = False
            app.stop_requested = False
            app._update_controls = lambda: None

            with patch("minimal_writer.threading.Thread", ImmediateThread):
                app._start_saved_scene_state_update(
                    temporary,
                    "The Long Way Home",
                    2,
                    20,
                    "The crew remained in the Recreation Room.\n\n"
                    "Elena stretched her neck and let out a quiet sigh.",
                )

            updated = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual(engine.clear_context_calls, 2)
        self.assertEqual(len(engine.prompts), 1)
        self.assertIn("Day 2, nighttime at the Mars research outpost.", engine.prompts[0])
        self.assertEqual(updated["chapter"], 2)
        self.assertEqual(updated["scene"], 20)
        self.assertTrue(updated["scene_completed"])
        self.assertEqual(
            updated["time_of_day"],
            "Day 2, late night at the Mars research outpost.",
        )
        self.assertIn("updated its ending state", app.status_var.value)

    def test_failed_analysis_keeps_saved_scene_markers_and_previous_time(self):
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "current_state.json"
            state_path.write_text(
                json.dumps(self.starting_state),
                encoding="utf-8",
            )
            app = MinimalWriterApp.__new__(MinimalWriterApp)
            app.engine = FakeStateEngine("not valid JSON")
            app.loaded_model = Path("/models/test.gguf")
            app.root = FakeRoot()
            app.status_var = FakeStatus()
            app.busy = False
            app.writing = False
            app.stop_requested = False
            app._update_controls = lambda: None

            with patch("minimal_writer.threading.Thread", ImmediateThread):
                app._start_saved_scene_state_update(
                    temporary,
                    "The Long Way Home",
                    2,
                    20,
                    "The crew remained in the Recreation Room.",
                )

            updated = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual(updated["chapter"], 2)
        self.assertEqual(updated["scene"], 20)
        self.assertTrue(updated["scene_completed"])
        self.assertEqual(
            updated["time_of_day"],
            "Day 2, nighttime at the Mars research outpost.",
        )
        self.assertIn("analysis failed", app.status_var.value)


if __name__ == "__main__":
    unittest.main()
