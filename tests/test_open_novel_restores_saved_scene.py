import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from storybuilder import StoryBuilderApp


class FakeText:
    def __init__(self, value=""):
        self.value = value

    def get(self, _start, _end):
        return self.value

    def delete(self, _start, _end):
        self.value = ""

    def insert(self, _index, value):
        self.value = value


class FakeLabel:
    def __init__(self):
        self.options = {}

    def configure(self, **kwargs):
        self.options.update(kwargs)


class OpenNovelRestoresSavedSceneTests(unittest.TestCase):
    def test_open_novel_loads_saved_prose_for_the_live_scene_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            chapter_dir = root / "Manuscript" / "Chapters" / "Chapter_01"
            chapter_dir.mkdir(parents=True)
            accepted_prose = "The accepted Scene 10 prose from the manuscript."
            scene_path = chapter_dir / "Chapter_01_Section_10.txt"
            scene_path.write_text(accepted_prose + "\n", encoding="utf-8")

            state = {
                "chapter": 1,
                "scene": 10,
                "current_situation": "The team is deciding how to isolate Delta-9.",
            }
            before_state_path = scene_path.with_name(
                "Chapter_01_Section_10_before_state.json"
            )
            before_state_path.write_text(
                json.dumps(state, ensure_ascii=False),
                encoding="utf-8",
            )
            package = SimpleNamespace(
                path=root,
                story_bible={"title": "Saved Novel"},
                current_state=state,
            )

            app = StoryBuilderApp.__new__(StoryBuilderApp)
            app.guided_setup = SimpleNamespace(stop=lambda: None)
            app._confirm_discard_unaccepted_writer_text = lambda: True
            app._sync_novel_before_open = lambda _folder: True
            app.writer_engine = SimpleNamespace(stop=lambda: None)
            app._reset_new_novel_assistant = lambda clear_brief=True: None
            app.writer_output_text = FakeText("text from the previous novel")
            app.writer_state_preview = FakeText()
            app.writer_status = FakeLabel()
            app._writer_editor_prose = lambda: ""
            app._update_writer_buttons = lambda: None
            app._refresh_all = lambda: None
            app._refresh_writer_models = lambda: None
            app._chat = lambda _who, _message: None
            app._show_copyable_error = lambda *_args, **_kwargs: self.fail(
                "Open Novel unexpectedly reported an error"
            )

            with (
                patch("storybuilder.filedialog.askdirectory", return_value=str(root)),
                patch("storybuilder.find_novel_packages", return_value=[root]),
                patch("storybuilder.StoryPackage.load", return_value=package),
            ):
                StoryBuilderApp._open_novel(app)

            self.assertEqual(app.generated_scene, accepted_prose)
            self.assertEqual(app.accepted_scene, accepted_prose)
            self.assertEqual(app.generated_scene_context, (1, 10))
            self.assertEqual(app.writer_output_text.value, accepted_prose)
            self.assertIn("Restored saved Chapter 1, Scene 10", app.writer_status.options["text"])


if __name__ == "__main__":
    unittest.main()
