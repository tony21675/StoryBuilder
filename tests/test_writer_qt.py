from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextCursor

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

    def test_finishing_prompt_trace_saves_locally_without_uploading(self):
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
        with patch.object(writer_qt, "upload_prompt_trace") as upload:
            self.window._finish_prompt_trace(trace, status="completed")
        self.assertTrue((self.root / "prompt_trace.json").is_file())
        upload.assert_not_called()
        self.assertIsNone(self.window._last_prompt_trace_upload_result)

    def test_prompt_trace_upload_runs_only_after_manual_button_action(self):
        trace_path = self.root / "prompt_trace.json"
        trace_path.write_text('{"test": true}', encoding="utf-8")
        self.window._last_prompt_trace_path = str(trace_path)
        captured = {}
        upload_result = {
            "ok": True,
            "url": "https://github.com/tony21675/StoryBuilder-Traces/blob/main/prompt_trace.json",
        }

        def capture_task(task, **kwargs):
            captured["task"] = task
            captured["label"] = kwargs.get("label")

        with patch.object(writer_qt, "upload_prompt_trace", return_value=upload_result) as upload:
            with patch.object(self.window, "run_task", side_effect=capture_task):
                self.window.upload_latest_prompt_trace()
            upload.assert_not_called()
            self.assertIn("Uploading prompt trace", captured["label"])
            result = captured["task"](None)
            upload.assert_called_once_with(trace_path)
            self.window._task_kind = "trace_upload"
            self.window.task_succeeded(result)

        self.assertIn("uploaded", self.window.status.text().lower())
        self.assertTrue(self.window._last_prompt_trace_upload_result["ok"])

    def test_exact_revision_replaces_only_the_selected_passage_after_approval(self):
        self.window.output_editor.setPlainText("Keep this. Change this. Keep that.")
        cursor = self.window.output_editor.textCursor()
        cursor.setPosition(11)
        cursor.setPosition(23, QTextCursor.MoveMode.KeepAnchor)
        self.window.output_editor.setTextCursor(cursor)

        class RequestDialog:
            def __init__(self, selected, _parent):
                self.selected = selected
            def exec(self):
                return writer_qt.QDialog.DialogCode.Accepted
            @property
            def use_ai(self):
                return False
            def replacement(self):
                return "Revised wording."

        class ReviewDialog:
            def __init__(self, original, proposed, _parent):
                self.original = original
                self.proposed = proposed
            def exec(self):
                return writer_qt.QDialog.DialogCode.Accepted
            def proposed_text(self):
                return self.proposed

        with patch.object(writer_qt, "RevisionRequestDialog", RequestDialog):
            with patch.object(writer_qt, "RevisionReviewDialog", ReviewDialog):
                self.window.revise_selection()

        self.assertEqual(
            self.window.output_editor.toPlainText(),
            "Keep this. Revised wording. Keep that.",
        )

    def test_revision_is_discarded_if_document_changes_before_approval(self):
        self.window.output_editor.setPlainText("A selected sentence. And more text.")
        self.window._revision_document = "A selected sentence. And more text."
        self.window._revision_start = 0
        self.window._revision_end = len("A selected sentence.")
        self.window._revision_original = "A selected sentence."
        self.window.output_editor.setPlainText("Changed document.")
        with patch.object(writer_qt, "RevisionReviewDialog") as review:
            with patch.object(self.window, "error") as show_error:
                self.window._show_revision_review("Replacement.")
        review.assert_not_called()
        show_error.assert_called_once()
        self.assertEqual(self.window.output_editor.toPlainText(), "Changed document.")

    def test_check_draft_is_advisory_and_does_not_change_text(self):
        original = "A short draft that should remain unchanged."
        self.window.output_editor.setPlainText(original)
        with patch.object(writer_qt, "analyze_draft", return_value=[]) as analyze:
            with patch.object(writer_qt, "DraftReportDialog") as report:
                self.window.check_draft()
        analyze.assert_called_once_with(original)
        report.assert_called_once()
        self.assertEqual(self.window.output_editor.toPlainText(), original)

    def test_save_new_scene_writes_only_under_selected_novel(self):
        self.window.novel_picker.setCurrentText(self.package.name)
        self.window.chapter_picker.setCurrentText("Chapter 01")
        self.window.output_editor.setPlainText("A test scene.")
        self.assertTrue(self.window.save_new_scene())
        scene_dir = self.package / "Manuscript" / "Chapters" / "Chapter_01"
        self.assertTrue((scene_dir / "Chapter_01_Section_01.odt").is_file())
        state_path = self.package / "current_state.json"
        self.assertTrue(state_path.is_file())
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["chapter"], 1)
        self.assertEqual(state["scene"], 1)
        self.assertTrue(state["scene_completed"])
        self.assertEqual(state["status"], "in_progress")

    def test_saving_existing_scene_starts_handoff_extraction(self):
        scene_dir = self.package / "Manuscript" / "Chapters" / "Chapter_01"
        scene_dir.mkdir(parents=True, exist_ok=True)
        target = scene_dir / "Chapter_01_Section_01.odt"
        target.write_text("Existing accepted scene.", encoding="utf-8")
        self.window.novel_picker.setCurrentText(self.package.name)
        self.window.chapter_picker.setCurrentText("Chapter 01")
        if self.window.scene_picker.findText("Scene 01") < 0:
            self.window.scene_picker.addItem("Scene 01")
        self.window.scene_picker.setCurrentText("Scene 01")
        self.window.scene_files["Scene 01"] = target
        self.window.selected_scene_source = target
        self.window.output_editor.setPlainText("Updated accepted scene.")

        with patch.object(self.window, "confirm", return_value=True):
            with patch.object(writer_qt, "save_document", return_value=target):
                with patch.object(self.window, "_start_scene_handoff_update") as extract:
                    self.assertTrue(self.window.save_to_selected_scene())

        extract.assert_called_once_with(
            target, self.package.name, 1, 1, "Updated accepted scene."
        )

    def test_existing_scene_handoff_update_writes_sidecar_without_advancing_state(self):
        from builder.scene_handoff import load_scene_handoff

        scene_dir = self.package / "Manuscript" / "Chapters" / "Chapter_01"
        scene_dir.mkdir(parents=True, exist_ok=True)
        target = scene_dir / "Chapter_01_Section_10.odt"
        target.write_text("Accepted scene text.", encoding="utf-8")
        handoff_payload = {
            "ending": "Mara and Noah leave the shop together.",
            "events": ["They leave the package undisturbed."],
            "character_knowledge": {"Mara": "She noticed the package."},
            "physical_continuity": ["The package remains inside the shop."],
            "unresolved": ["The package's purpose is unknown."],
        }
        fake_engine = SimpleNamespace(
            active_selection=object(),
            clear_context=lambda: None,
            generate=lambda _prompt: json.dumps(handoff_payload),
        )
        self.window.engine = fake_engine
        self.window.loaded_model = Path("/models/test.gguf")
        state_path = self.package / "current_state.json"
        state_path.write_text(
            json.dumps({"chapter": 1, "scene": 9, "scene_completed": True}),
            encoding="utf-8",
        )
        captured = {}

        def capture_task(task, *, label):
            captured["task"] = task
            captured["label"] = label

        with patch.object(self.window, "run_task", side_effect=capture_task):
            self.window._start_scene_handoff_update(
                target,
                self.package.name,
                1,
                10,
                "Accepted scene text.",
            )

        result = captured["task"](lambda _chunk: None)
        self.assertEqual(result["handoff_status"], "created")
        saved_handoff = load_scene_handoff(target, "Accepted scene text.")
        self.assertEqual(saved_handoff["ending"], handoff_payload["ending"])
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["scene"], 9)

    def test_selected_scene_missing_after_confirmation_is_not_recreated(self):
        scene_dir = self.package / "Manuscript" / "Chapters" / "Chapter_01"
        scene_dir.mkdir(parents=True, exist_ok=True)
        target = scene_dir / "Chapter_01_Section_01.odt"
        target.write_text("existing scene")
        self.window.novel_picker.setCurrentText(self.package.name)
        self.window.chapter_picker.setCurrentText("Chapter 01")
        self.window.scene_picker.addItem("Scene 01")
        self.window.scene_picker.setCurrentText("Scene 01")
        self.window.scene_files["Scene 01"] = target
        self.window.selected_scene_source = target
        def remove_during_confirmation(*_args):
            target.unlink()
            return True
        with patch.object(self.window, "confirm", side_effect=remove_during_confirmation):
            with patch.object(writer_qt, "save_document") as save:
                with patch.object(self.window, "error"):
                    self.assertFalse(self.window.save_to_selected_scene())
        save.assert_not_called()
        self.assertFalse(target.exists())

    def test_novel_sync_requires_confirmation_before_running_sync_helper(self):
        self.window.novel_picker.setCurrentText(self.package.name)
        preview = SimpleNamespace(
            repository=self.package,
            branch="main",
            remote_url="git@github.com:example/novel.git",
            local_commits=("abc1234 local commit",),
            changed_files=("story_bible.json",),
        )
        with patch.object(writer_qt, "inspect_novel_repository", return_value=preview):
            with patch.object(self.window, "confirm", return_value=False):
                with patch.object(writer_qt, "sync_novel_repository") as sync:
                    self.window.sync_selected_novel_to_github()
        sync.assert_not_called()
        self.assertIn("cancelled", self.window.status.text().lower())

    def test_openrouter_settings_are_available_as_an_optional_workflow(self):
        self.assertTrue(hasattr(self.window, "openrouter_settings_button"))
        self.assertEqual(self.window.openrouter_settings_button.text(), "OpenRouter Settings")


if __name__ == "__main__":
    unittest.main()
