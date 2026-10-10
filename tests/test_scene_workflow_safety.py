import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import storybuilder as storybuilder_app
from builder.scene_contract import CONTRACT_BUILDER_SYSTEM_PROMPT


class FakeText:
    def __init__(self, value=""):
        self.value = value

    def get(self, _start, _end):
        return self.value

    def delete(self, _start, _end):
        self.value = ""

    def insert(self, _index, value):
        self.value = value


class SceneWorkflowSafetyTests(unittest.TestCase):
    def make_app(self, package_path, prose, context=(2, 1), accepted=""):
        # Avoid opening a real Tk window; these tests exercise the file/state
        # safety helpers and replace UI callbacks with harmless fakes.
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(
            path=Path(package_path),
            current_state={"chapter": 2, "scene": 2, "scene_completed": False},
        )
        app.generated_scene = prose
        app.accepted_scene = accepted
        app.generated_scene_context = context
        app.generated_scene_start_state = None
        app.writer_generation_context = None
        app.writer_generation_start_state = None
        app.writer_generation_in_progress = False
        app.scene_contract_building = False
        app.pending_state_patch = None
        app.writer_output_text = FakeText(prose)
        app._refresh_manuscript = lambda: None
        app._chat = lambda *_args, **_kwargs: None
        return app

    def test_unfinished_writer_text_is_saved_to_origin_scene_not_current_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.make_app(tmp, "Scene 1 draft text", context=(2, 1))
            with patch.object(storybuilder_app.messagebox, "showwarning"), patch.object(
                storybuilder_app.messagebox, "showerror"
            ):
                self.assertTrue(app._save_unsaved_writer_draft())

            expected = (
                Path(tmp)
                / "Manuscript"
                / "Chapters"
                / "Chapter_02"
                / "Chapter_02_Section_01_draft.txt"
            )
            wrong_scene = (
                Path(tmp)
                / "Manuscript"
                / "Chapters"
                / "Chapter_02"
                / "Chapter_02_Section_02_draft.txt"
            )
            self.assertEqual(expected.read_text(encoding="utf-8"), "Scene 1 draft text\n")
            self.assertFalse(wrong_scene.exists())

    def test_scene_switch_is_blocked_until_accepted_scene_state_is_applied(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.make_app(
                tmp,
                "Accepted scene",
                context=(2, 1),
                accepted="Accepted scene",
            )
            app.package.current_state = {
                "chapter": 2,
                "scene": 1,
                "scene_completed": False,
            }
            with patch.object(storybuilder_app.messagebox, "showwarning") as warning:
                self.assertFalse(app._prepare_for_scene_change(2, 2))
            warning.assert_called_once()

    def test_contract_builder_prioritizes_current_situation_over_stale_physical_state(self):
        self.assertIn(
            "current_situation as the authoritative narrative snapshot",
            CONTRACT_BUILDER_SYSTEM_PROMPT,
        )
        self.assertIn(
            "If they conflict, follow current_situation",
            CONTRACT_BUILDER_SYSTEM_PROMPT,
        )


if __name__ == "__main__":
    unittest.main()
