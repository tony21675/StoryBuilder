import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import storybuilder as storybuilder_app


class FakeButton:
    def __init__(self):
        self.options = {}

    def configure(self, **kwargs):
        self.options.update(kwargs)


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


class FakeListbox:
    def __init__(self, selection=0):
        self.selection = selection

    def curselection(self):
        return (self.selection,)


class ManuscriptCandidateSelectionTests(unittest.TestCase):
    def make_app(self, root):
        chapter = Path(root) / "Manuscript" / "Chapters" / "Chapter_02"
        chapter.mkdir(parents=True)
        first = chapter / "Chapter_02_Section_01.txt"
        second = chapter / "Chapter_02_Section_02.txt"
        first.write_text("Accepted scene one.", encoding="utf-8")
        second.write_text("Accepted scene two.", encoding="utf-8")

        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(
            path=Path(root),
            current_state={"chapter": 2, "scene": 2},
        )
        app.manuscript_list = FakeListbox(0)
        app.selected_manuscript_path = second
        app.saved_state_candidate = {"chapter": 2, "scene": 2, "current_situation": "End of scene two"}
        app.saved_state_candidate_path = second
        app.manuscript_state_preview = FakeText('{"current_situation": "End of scene two"}')
        app.manuscript_recovery_status = FakeLabel()
        app.manuscript_output = FakeText()
        app.manuscript_analyze_button = FakeButton()
        app.manuscript_restore_button = FakeButton()
        app.manuscript_copy_state_button = FakeButton()
        return app, first, second

    def test_clicking_another_scene_preserves_candidate_but_disables_restore_until_reselected(self):
        with tempfile.TemporaryDirectory() as tmp:
            app, first, second = self.make_app(tmp)

            storybuilder_app.StoryBuilderApp._select_manuscript_scene(app)

            self.assertEqual(app.saved_state_candidate_path, second)
            self.assertEqual(
                app.saved_state_candidate["current_situation"],
                "End of scene two",
            )
            self.assertIn("preserved", app.manuscript_recovery_status.options["text"])
            self.assertEqual(app.manuscript_restore_button.options["state"], "disabled")
            self.assertIn("End of scene two", app.manuscript_state_preview.value)

            app.manuscript_list.selection = 1
            storybuilder_app.StoryBuilderApp._select_manuscript_scene(app)

            self.assertEqual(app.saved_state_candidate_path, second)
            self.assertEqual(app.manuscript_restore_button.options["state"], "normal")
            self.assertIn("preview is preserved", app.manuscript_recovery_status.options["text"])


if __name__ == "__main__":
    unittest.main()
