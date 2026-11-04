import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from minimal_writer import MinimalWriterApp


class FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class FakeStatus:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value


class MinimalWriterAssemblyActionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.novel_path = Path(self.temp_dir.name) / "Example-Novel"
        self.novel_path.mkdir()
        self.app = MinimalWriterApp.__new__(MinimalWriterApp)
        self.app.busy = False
        self.app.novel_var = FakeVar("Example-Novel")
        self.app.novel_packages = {"Example-Novel": self.novel_path}
        self.app.chapter_var = FakeVar("Chapter 02")
        self.app.chapter_numbers = {"Chapter 02": 2}
        self.app.status_var = FakeStatus()
        self.info_messages = []
        self.error_messages = []
        self.app._showinfo = lambda title, message: self.info_messages.append(
            (title, message)
        )
        self.app._showerror = lambda title, message: self.error_messages.append(
            (title, message)
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_assemble_current_chapter_uses_selected_novel_and_chapter(self):
        target = self.novel_path / "Manuscript" / "Compiled" / "Chapter_02.odt"
        with patch("minimal_writer.assemble_chapter_document", return_value=target) as assemble:
            self.app.assemble_current_chapter()

        assemble.assert_called_once_with(self.novel_path, 2)
        self.assertIn(str(target), self.app.status_var.value)
        self.assertEqual(self.info_messages[0][0], "Chapter assembled")
        self.assertIn("original scene files were not changed", self.info_messages[0][1])
        self.assertEqual(self.error_messages, [])

    def test_assemble_finished_novel_uses_story_bible_title(self):
        target = (
            self.novel_path
            / "Manuscript"
            / "Compiled"
            / "Example_Novel_Complete_Novel.odt"
        )
        with (
            patch("minimal_writer.load_story_bible", return_value={"title": "Example Novel"}),
            patch("minimal_writer.assemble_finished_novel_document", return_value=target) as assemble,
        ):
            self.app.assemble_finished_novel()

        assemble.assert_called_once_with(self.novel_path, "Example Novel")
        self.assertIn(str(target), self.app.status_var.value)
        self.assertEqual(self.info_messages[0][0], "Finished novel assembled")
        self.assertEqual(self.error_messages, [])

    def test_assembly_actions_do_nothing_while_writer_is_busy(self):
        self.app.busy = True
        with (
            patch("minimal_writer.assemble_chapter_document") as chapter_assemble,
            patch("minimal_writer.assemble_finished_novel_document") as novel_assemble,
        ):
            self.app.assemble_current_chapter()
            self.app.assemble_finished_novel()

        chapter_assemble.assert_not_called()
        novel_assemble.assert_not_called()
        self.assertEqual(self.info_messages, [])
        self.assertEqual(self.error_messages, [])

    def test_finished_novel_assembly_falls_back_to_novel_name_when_bible_is_unavailable(self):
        target = self.novel_path / "Manuscript" / "Compiled" / "Example_Novel_Complete_Novel.odt"
        with (
            patch("minimal_writer.load_story_bible", side_effect=FileNotFoundError),
            patch("minimal_writer.assemble_finished_novel_document", return_value=target) as assemble,
        ):
            self.app.assemble_finished_novel()

        assemble.assert_called_once_with(self.novel_path, "Example-Novel")
        self.assertEqual(self.error_messages, [])


if __name__ == "__main__":
    unittest.main()
