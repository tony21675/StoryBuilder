from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import writer_qt
from builder.novel_creator import create_novel_package


class WriterQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.previous_root = writer_qt.NOVEL_ROOT
        writer_qt.NOVEL_ROOT = self.root
        self.package = create_novel_package("Qt Writer Test", novel_root=self.root)
        (self.package / "Manuscript" / "Chapters" / "Chapter_01").mkdir(parents=True, exist_ok=True)
        self.window = writer_qt.WriterQtWindow()

    def tearDown(self):
        try:
            self.window.engine.stop()
        except Exception:
            pass
        self.window.close()
        writer_qt.NOVEL_ROOT = self.previous_root
        self.temp_dir.cleanup()

    def test_lists_existing_novel_without_auto_loading(self):
        self.assertEqual(self.window.novel_picker.count(), 1)
        self.assertEqual(self.window.novel_picker.currentText(), "")

    def test_novel_selection_loads_chapter_selector(self):
        self.window.novel_picker.setCurrentText(self.package.name)
        self.assertEqual(self.window.novel_picker.currentText(), self.package.name)

    def test_author_direction_is_a_separate_editor(self):
        self.window.author_direction.setPlainText("Keep the required event.")
        self.assertEqual(self.window.author_direction.toPlainText(), "Keep the required event.")

    def test_empty_scene_cast_remains_distinct_from_unselected_cast(self):
        self.window.novel_picker.setCurrentText(self.package.name)
        self.window.scene_cast = []
        self.window.scene_cast_novel = self.package.resolve()
        self.assertEqual(self.window._active_cast(), [])

    def test_prompt_trace_captures_story_files_and_author_direction(self):
        self.window.novel_picker.setCurrentText(self.package.name)
        self.window.chapter_picker.setCurrentText("Chapter 01")
        with patch.object(writer_qt, "load_prompt_trace_enabled", return_value=True):
            trace = self.window._start_prompt_trace(
                "planner input",
                model_path=Path("/models/qwen.gguf"),
                attach=False,
                chapter_number=1,
                scene_number=1,
                scene_direction="existing direction",
                author_guidance="Required event",
            )
        self.assertIsNotNone(trace)
        self.assertEqual(trace.data["inputs"]["scene_direction"], "existing direction")
        self.assertEqual(trace.data["inputs"]["author_guidance"], "Required event")
        self.assertIn("story_bible.json", [item["name"] for item in trace.data["inputs"]["reference_files"]])

    def test_writer_context_uses_resolved_scene_for_author_required_beats(self):
        self.window.novel_picker.setCurrentText(self.package.name)
        self.window.chapter_picker.setCurrentText("Chapter 01")
        self.window.scene_picker.setCurrentText("Scene 02")
        self.window.prepared_novel = self.package
        self.window.prepared_destination = (1, 1)
        self.window._prepared_author_required_direction = "Tony reads Sarah's letter."
        captured = {}
        def record_direction(prompt, direction):
            captured["direction"] = direction
            return prompt
        with patch.object(writer_qt, "build_author_required_direction_prompt", side_effect=record_direction):
            with patch.object(writer_qt, "build_scene_cast_boundary_prompt", side_effect=lambda prompt, _cast: prompt):
                prompt = self.window._writer_context(
                    "Chapter 01, Scene 01\nA quiet opening.",
                    "minimal",
                )
        self.assertEqual(captured["direction"], "Tony reads Sarah's letter.")
        self.assertIn("Scene 01", prompt)

    def test_writer_success_restores_result_when_runtime_did_not_stream(self):
        self.window._task_kind = "write"
        self.window._generation_mode = "write"
        self.window._generation_original = "Previous draft"
        self.window._streamed = False
        self.window.busy = True
        self.window.task_succeeded("Final model response.")
        self.assertEqual(self.window.output_editor.toPlainText(), "Final model response.")
        self.assertFalse(self.window.busy)

    def test_prepared_trace_is_claimed_only_for_same_novel_and_scene(self):
        self.window.novel_picker.setCurrentText(self.package.name)
        self.window.chapter_picker.setCurrentText("Chapter 01")
        trace = self.window._start_prompt_trace(
            "planner input",
            model_path=Path("/models/qwen.gguf"),
            attach=False,
            chapter_number=1,
            scene_number=1,
        )
        self.window.prepared_novel = self.package
        self.window.prepared_destination = (1, 1)
        self.window._prepared_author_required_direction = "Author beat"
        self.window.prompt_editor.setPlainText("Final planner direction")
        self.window.author_direction.setPlainText("Author beat")
        self.window._pending_scene_prompt_trace = trace
        with patch.object(writer_qt, "load_prompt_trace_enabled", return_value=True):
            claimed = self.window._claim_prepared_scene_prompt_trace("write", (1, 1))
        self.assertIs(claimed, trace)
        self.assertIsNone(self.window._pending_scene_prompt_trace)
        event = trace.data["workflow_events"][-1]
        self.assertEqual(event["event"], "prepared_direction_sent_to_writer")
        self.assertEqual(event["details"]["final_scene_direction"], "Final planner direction")
        self.assertEqual(event["details"]["final_author_required_direction"], "Author beat")

    def test_finishing_prompt_trace_saves_locally_and_attempts_upload(self):
        trace = writer_qt.PromptTrace(
            chapter=1,
            scene=1,
            model_path="test-model",
            current_state={},
            reference_files=[],
            contract={},
            scene_direction="test",
            author_guidance="",
            system_prompt="",
            path=self.root / "prompt_trace.json",
        )
        with patch.object(writer_qt, "upload_prompt_trace", return_value={"ok": True, "url": "https://example.invalid/trace"}) as upload:
            self.window._finish_prompt_trace(trace, status="completed")
        self.assertTrue((self.root / "prompt_trace.json").is_file())
        upload.assert_called_once()
        self.assertTrue(self.window._last_prompt_trace_upload_result["ok"])

    def test_save_new_scene_writes_only_under_selected_novel(self):
        self.window.novel_picker.setCurrentText(self.package.name)
        self.window.chapter_picker.setCurrentText("Chapter 01")
        self.window.output_editor.setPlainText("A test scene.")
        self.assertTrue(self.window.save_new_scene())
        scene_dir = self.package / "Manuscript" / "Chapters" / "Chapter_01"
        self.assertTrue((scene_dir / "Chapter_01_Section_01.odt").is_file())


if __name__ == "__main__":
    unittest.main()
