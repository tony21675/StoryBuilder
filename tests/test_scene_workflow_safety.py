import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import storybuilder as storybuilder_app
import builder.scene_contract as scene_contract
from builder.scene_contract import CONTRACT_BUILDER_SYSTEM_PROMPT, SceneContract
from builder.manuscript import ManuscriptManager
import builder.novel_sync as novel_sync



class FakeButton:
    def __init__(self):
        self.options = {}

    def configure(self, **kwargs):
        self.options.update(kwargs)


class FakeText:
    def __init__(self, value=""):
        self.value = value
        self.state = "normal"

    def configure(self, **kwargs):
        if "state" in kwargs:
            self.state = kwargs["state"]

    def get(self, _start, _end):
        return self.value

    def delete(self, _start, _end):
        self.value = ""

    def insert(self, _index, value):
        self.value = value


class FakePopupWidget:
    """Small Tk widget stand-in used to test error-dialog clipboard behavior."""

    instances = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.bindings = {}
        self.options = {}
        self.commands = []
        FakePopupWidget.instances.append(self)

    def pack(self, *args, **kwargs):
        pass

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def bind(self, sequence, callback):
        self.bindings[sequence] = callback

    def insert(self, *args, **kwargs):
        pass

    def tag_add(self, *args, **kwargs):
        pass

    def mark_set(self, *args, **kwargs):
        pass

    def see(self, *args, **kwargs):
        pass

    def add_command(self, *args, **kwargs):
        self.commands.append(kwargs)

    def winfo_screenwidth(self):
        return 1200

    def winfo_screenheight(self):
        return 800

    def __getattr__(self, name):
        # Tk geometry, title, focus, menu popup, and other display operations
        # are intentionally inert in this non-GUI regression test.
        return lambda *args, **kwargs: None


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

    def test_clear_previous_generated_scene_display_preserves_accepted_scene(self):
        prose = "The accepted scene remains part of the manuscript."
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.generated_scene = prose
        app.generated_scene_context = (3, 3)
        app.generated_scene_start_state = {"chapter": 3, "scene": 3}
        app.accepted_scene = prose
        app.accepted_scene_context = (3, 3)
        app.focused_revision_history = ["old revision"]
        app.writer_output_text = FakeText(prose)
        app.writer_state_preview = FakeText("old state preview")
        app.writer_state_diff_preview = FakeText("old state diff")

        storybuilder_app.StoryBuilderApp._clear_previous_generated_scene_display(app)

        self.assertEqual(app.generated_scene, "")
        self.assertIsNone(app.generated_scene_context)
        self.assertIsNone(app.generated_scene_start_state)
        self.assertEqual(app.accepted_scene, prose)
        self.assertEqual(app.accepted_scene_context, (3, 3))
        self.assertEqual(app.focused_revision_history, [])
        self.assertEqual(app.writer_output_text.value, "")
        self.assertEqual(app.writer_state_preview.value, "")
        self.assertEqual(app.writer_state_diff_preview.value, "")
        self.assertEqual(app.writer_state_diff_preview.state, "disabled")

    def make_scene_idea_reload_app(self, saved_idea, current_idea, confirm=True):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(
            current_state={"chapter": 2, "scene": 4},
            extra_json={
                "writing_guidance.json": {
                    "chapter_plans": {
                        "2": {
                            "scene_plan": {
                                "4": {"scene_idea": saved_idea}
                            }
                        }
                    }
                }
            },
        )
        app.scene_contract_editor_key = (2, 4)
        app.scene_idea_text = FakeText(current_idea)
        app.scene_contract_status = FakeButton()
        app.scene_contract_building = False
        app.writer_generation_in_progress = False
        app._ask_yes_no = Mock(return_value=confirm)
        app._refresh_scene_contract_editor = Mock()
        return app

    def test_reload_saved_scene_idea_replaces_unsaved_text_only_after_confirmation(self):
        app = self.make_scene_idea_reload_app(
            "Saved scene beats.", "Unsaved revised beats.", confirm=True
        )
        app.scene_contract_direction_text = FakeText("Existing generated direction.")

        app._reload_saved_scene_idea()

        self.assertEqual(app.scene_idea_text.value, "Saved scene beats.")
        self.assertEqual(
            app.scene_contract_direction_text.value,
            "Existing generated direction.",
        )
        app._ask_yes_no.assert_called_once()
        self.assertIn("Discard the current unsaved Scene Idea edits", app._ask_yes_no.call_args.args[1])
        self.assertIn("Reloaded the saved Scene Idea", app.scene_contract_status.options["text"])

    def test_reload_saved_scene_idea_cancel_keeps_editor_text(self):
        app = self.make_scene_idea_reload_app(
            "Saved scene beats.", "Unsaved revised beats.", confirm=False
        )

        app._reload_saved_scene_idea()

        self.assertEqual(app.scene_idea_text.value, "Unsaved revised beats.")
        app._ask_yes_no.assert_called_once()
        self.assertEqual(app.scene_contract_status.options, {})

    def test_reload_saved_scene_idea_without_changes_needs_no_confirmation(self):
        app = self.make_scene_idea_reload_app(
            "Saved scene beats.", "Saved scene beats.", confirm=False
        )

        app._reload_saved_scene_idea()

        self.assertEqual(app.scene_idea_text.value, "Saved scene beats.")
        app._ask_yes_no.assert_not_called()

    def test_pending_draft_can_be_accepted_after_author_review(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.writer_engine = SimpleNamespace(
            child=SimpleNamespace(isalive=lambda: True),
            model_path=Path("/tmp/writer.gguf"),
        )
        app.package = object()
        app.generated_scene = "Complete draft awaiting author review."
        app.accepted_scene = ""
        app.pending_state_patch = None
        # Legacy state must no longer block acceptance in the author-review flow.
        app.writer_validation_failed = True
        app.scene_contract_building = False
        app.__dict__["writer_generation_in_progress"] = False
        app.__dict__["writer_notes_update_in_progress"] = False
        for name in (
            "writer_start_button",
            "writer_stop_button",
            "writer_write_button",
            "writer_save_draft_button",
            "writer_accept_button",
            "writer_reject_button",
            "writer_analyze_button",
            "writer_apply_state_button",
            "writer_clear_context_button",
            "writer_status",
        ):
            setattr(app, name, FakeButton())

        app._update_writer_buttons()

        self.assertEqual(app.writer_save_draft_button.options["state"], "normal")
        self.assertEqual(app.writer_accept_button.options["state"], "normal")
        self.assertEqual(app.writer_reject_button.options["state"], "normal")
    def test_generated_scene_returns_for_author_review_without_validator(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(current_state={"chapter": 2, "scene": 4})
        app.generated_scene = ""
        app.accepted_scene = ""
        app.writer_generation_context = (2, 4)
        app.writer_generation_start_state = {"chapter": 2, "scene": 4}
        app.writer_generation_in_progress = True
        app.writer_engine = SimpleNamespace(child=None, model_path=None)
        app.writer_output_text = FakeText()
        app.writer_status = FakeButton()
        app.scene_contract_building = False
        app.pending_state_patch = None
        app._show_copyable_error = Mock()
        app.__dict__["writer_notes_update_in_progress"] = False
        for name in (
            "writer_start_button",
            "writer_stop_button",
            "writer_write_button",
            "writer_save_draft_button",
            "writer_accept_button",
            "writer_reject_button",
            "writer_analyze_button",
            "writer_apply_state_button",
            "writer_clear_context_button",
        ):
            setattr(app, name, FakeButton())

        draft = "The complete scene that the author wants to review."
        with patch.object(storybuilder_app.messagebox, "showwarning") as showwarning:
            storybuilder_app.StoryBuilderApp._finish_generated_scene(app, draft, None)

        app._show_copyable_error.assert_not_called()
        showwarning.assert_not_called()
        self.assertEqual(app.generated_scene, draft)
        self.assertEqual(app.writer_output_text.value, draft)
        self.assertIn("Review it", app.writer_status.options["text"])
        self.assertEqual(app.writer_save_draft_button.options["state"], "normal")
        self.assertEqual(app.writer_accept_button.options["state"], "normal")
        self.assertEqual(app.writer_reject_button.options["state"], "normal")
    def test_author_can_accept_draft_without_validator_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = {"chapter": 2, "scene": 4}
            prose = "A draft that the author reviewed and chose to keep."
            app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
            app.package = SimpleNamespace(path=Path(tmp), current_state=state)
            app.generated_scene = prose
            app.accepted_scene = ""
            app.generated_scene_context = (2, 4)
            app.generated_scene_start_state = dict(state)
            app.writer_output_text = FakeText(prose)
            app.writer_state_preview = FakeText()
            app.writer_status = FakeButton()
            app.pending_state_patch = None
            app._ask_yes_no = Mock(return_value=False)
            app._refresh_manuscript = Mock()
            app._chat = Mock()
            app._update_writer_buttons = Mock()

            with patch.object(SceneContract, "validate_with_engine") as validator:
                storybuilder_app.StoryBuilderApp._accept_generated_scene(app)

            validator.assert_not_called()
            app._ask_yes_no.assert_not_called()
            self.assertEqual(app.accepted_scene, prose)
            self.assertEqual(app.accepted_scene_context, (2, 4))
            path = ManuscriptManager(Path(tmp)).scene_path(2, 4)
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_text(encoding="utf-8"), prose + "\n")
    def test_writer_generation_error_preserves_unaccepted_draft(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        error_text = (
            "Local model turn timed out after 300 seconds. "
            "The draft remains unaccepted; you can save it and retry."
        )
        draft = "A complete scene generated before a later model error."
        app.package = SimpleNamespace(current_state={"chapter": 2, "scene": 4})
        app.generated_scene = ""
        app.accepted_scene = ""
        app.writer_generation_context = (2, 4)
        app.writer_generation_start_state = {"chapter": 2, "scene": 4}
        app.writer_generation_in_progress = True
        app.writer_output_text = FakeText()
        app.writer_status = FakeButton()
        app._show_copyable_error = Mock()
        app._update_writer_buttons = Mock()

        app._finish_generated_scene(draft, error_text)

        app._show_copyable_error.assert_called_once_with(
            "Writer",
            error_text,
            summary="Scene generation encountered an error. Any draft remains available for your review.",
        )
        self.assertFalse(app.writer_generation_in_progress)
        self.assertEqual(app.generated_scene, draft)
        self.assertEqual(app.writer_output_text.value, draft)
        self.assertIn("remains available for your review", app.writer_status.options["text"])
        app._update_writer_buttons.assert_called_once_with()
    def test_sync_failure_uses_copyable_error_dialog(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
            app.package = SimpleNamespace(
                path=Path(tmp),
                save=lambda: None,
            )
            app.dirty = False
            app._apply_all_edits = lambda: True
            app._update_path_label = lambda: None
            captured_errors = []
            app._show_copyable_error = lambda *args, **kwargs: captured_errors.append(
                (args, kwargs)
            )

            with patch.object(
                storybuilder_app,
                "sync_novel_repository",
                side_effect=storybuilder_app.NovelSyncError("simulated rebase conflict"),
            ):
                storybuilder_app.StoryBuilderApp._sync_current_novel(app)

            self.assertEqual(len(captured_errors), 1)
            args, kwargs = captured_errors[0]
            self.assertEqual(args[0], "Sync Novel")
            self.assertIn("saved locally", args[1])
            self.assertIn("simulated rebase conflict", args[1])
            self.assertIn(
                "GitHub synchronization did not complete",
                kwargs["summary"],
            )

    def test_close_and_sync_failure_uses_copyable_error_dialog(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
            app._closing = False
            app.package = SimpleNamespace(path=Path(tmp))
            app.writer_engine = SimpleNamespace(stop=Mock())
            app.dirty = False
            app._save_unsaved_writer_draft = Mock(return_value=True)
            app._save = Mock()
            app._show_copyable_error = Mock()
            app.destroy = Mock()

            with (
                patch.object(
                    storybuilder_app,
                    "sync_novel_repository",
                    side_effect=storybuilder_app.NovelSyncError("simulated rebase conflict"),
                ),
                patch.object(storybuilder_app.messagebox, "showerror") as showerror,
            ):
                storybuilder_app.StoryBuilderApp._close_and_sync(app)

            app._show_copyable_error.assert_called_once()
            args, kwargs = app._show_copyable_error.call_args
            self.assertEqual(args[0], "Close & Sync")
            self.assertIn("simulated rebase conflict", args[1])
            self.assertIn("Copy Full Error", kwargs["summary"])
            self.assertFalse(app._closing)
            app.destroy.assert_not_called()
            showerror.assert_not_called()

    def test_application_error_popups_use_copyable_dialog(self):
        source = Path(storybuilder_app.__file__).read_text(encoding="utf-8")
        self.assertNotIn("messagebox.showerror(", source)

    def test_copyable_error_dialog_uses_main_window_clipboard(self):
        FakePopupWidget.instances.clear()
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.clipboard_clear = Mock()
        app.clipboard_append = Mock()
        app.update_idletasks = Mock()

        with (
            patch.object(storybuilder_app.tk, "Toplevel", FakePopupWidget),
            patch.object(storybuilder_app.tk, "Text", FakePopupWidget),
            patch.object(storybuilder_app.tk, "Menu", FakePopupWidget),
            patch.object(storybuilder_app.ttk, "Frame", FakePopupWidget),
            patch.object(storybuilder_app.ttk, "Label", FakePopupWidget),
            patch.object(storybuilder_app.ttk, "Scrollbar", FakePopupWidget),
            patch.object(storybuilder_app.ttk, "Button", FakePopupWidget),
        ):
            storybuilder_app.StoryBuilderApp._show_copyable_error(
                app,
                "Sync Novel",
                "The novel repository is not on a normal branch.",
            )

        copy_button = next(
            widget
            for widget in FakePopupWidget.instances
            if widget.kwargs.get("text") == "Copy Full Error"
        )
        text_widget = next(
            widget
            for widget in FakePopupWidget.instances
            if widget.kwargs.get("wrap") == "word"
        )
        self.assertLess(
            FakePopupWidget.instances.index(copy_button),
            FakePopupWidget.instances.index(text_widget),
            "Copy Full Error must be created above the expandable diagnostic text.",
        )
        copy_button.kwargs["command"]()

        app.clipboard_clear.assert_called_once_with()
        app.clipboard_append.assert_called_once_with(
            "The novel repository is not on a normal branch."
        )
        app.update_idletasks.assert_called_once_with()

    def test_unfinished_writer_text_is_saved_to_origin_scene_not_current_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.make_app(tmp, "Scene 1 draft text", context=(2, 1))
            with (
                patch.object(storybuilder_app.messagebox, "askyesnocancel", return_value=True) as ask,
                patch.object(storybuilder_app.messagebox, "showwarning"),
                patch.object(storybuilder_app.messagebox, "showerror"),
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
            self.assertEqual(app.writer_draft_saved_text, "Scene 1 draft text")
            ask.assert_called_once()
            self.assertIn("Choose Yes to Save Draft", ask.call_args.args[1])
            self.assertIn("Choose No to discard", ask.call_args.args[1])
            self.assertIn("Choose Cancel", ask.call_args.args[1])

    def test_unfinished_writer_cancel_keeps_text_and_does_not_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.make_app(tmp, "Attempt to discard", context=(2, 1))
            with patch.object(
                storybuilder_app.messagebox, "askyesnocancel", return_value=None
            ) as ask:
                self.assertFalse(app._save_unsaved_writer_draft())

            draft = (
                Path(tmp)
                / "Manuscript"
                / "Chapters"
                / "Chapter_02"
                / "Chapter_02_Section_01_draft.txt"
            )
            self.assertFalse(draft.exists())
            self.assertEqual(app.generated_scene, "Attempt to discard")
            self.assertEqual(app.writer_output_text.value, "Attempt to discard")
            ask.assert_called_once()

    def test_unfinished_writer_discard_does_not_save_and_clears_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.make_app(tmp, "Attempt to discard", context=(2, 1))
            with patch.object(
                storybuilder_app.messagebox, "askyesnocancel", return_value=False
            ):
                self.assertTrue(app._save_unsaved_writer_draft())

            draft = (
                Path(tmp)
                / "Manuscript"
                / "Chapters"
                / "Chapter_02"
                / "Chapter_02_Section_01_draft.txt"
            )
            self.assertFalse(draft.exists())
            self.assertEqual(app.generated_scene, "")
            self.assertEqual(app.writer_output_text.value, "")
            self.assertIsNone(app.generated_scene_context)
            self.assertIsNone(app.generated_scene_start_state)

    def test_discard_removes_matching_autosaved_draft_but_preserves_different_saved_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.make_app(tmp, "Current attempt", context=(2, 1))
            draft = (
                Path(tmp)
                / "Manuscript"
                / "Chapters"
                / "Chapter_02"
                / "Chapter_02_Section_01_draft.txt"
            )
            draft.parent.mkdir(parents=True)
            draft.write_text("Current attempt\n", encoding="utf-8")
            with patch.object(
                storybuilder_app.messagebox, "askyesnocancel", return_value=False
            ):
                self.assertTrue(app._save_unsaved_writer_draft())
            self.assertFalse(draft.exists())

            app = self.make_app(tmp, "New attempt", context=(2, 1))
            draft.write_text("Previously saved version\n", encoding="utf-8")
            with patch.object(
                storybuilder_app.messagebox, "askyesnocancel", return_value=False
            ):
                self.assertTrue(app._save_unsaved_writer_draft())
            self.assertEqual(draft.read_text(encoding="utf-8"), "Previously saved version\n")
            self.assertEqual(app.generated_scene, "")

    def test_explicitly_saved_draft_does_not_prompt_again_when_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.make_app(tmp, "Saved attempt", context=(2, 1))
            app.writer_draft_saved_text = "Saved attempt"
            with patch.object(
                storybuilder_app.messagebox, "askyesnocancel"
            ) as ask:
                self.assertTrue(app._save_unsaved_writer_draft())
            ask.assert_not_called()

    def test_close_cancel_keeps_storybuilder_open_and_does_not_save_package(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app._closing = False
        app.package = SimpleNamespace(path=Path("/tmp/novel"))
        app.writer_engine = SimpleNamespace(stop=Mock())
        app.dirty = False
        app._save_unsaved_writer_draft = Mock(return_value=False)
        app._save = Mock()
        app.destroy = Mock()

        storybuilder_app.StoryBuilderApp._close_without_sync(app)

        self.assertFalse(app._closing)
        app.writer_engine.stop.assert_not_called()
        app._save.assert_not_called()
        app.destroy.assert_not_called()

    def test_edited_prose_can_be_accepted_without_contract_revalidation(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = {
                "chapter": 2,
                "scene": 1,
                "status": "in_progress",
                "scene_completed": False,
                "current_situation": "Maya has reached Tony but has not told him Tiffany is gone.",
            }
            app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
            app.package = SimpleNamespace(path=Path(tmp), current_state=state)
            app.generated_scene = "Original generated prose"
            app.accepted_scene = ""
            app.generated_scene_context = (2, 1)
            app.generated_scene_start_state = json.loads(json.dumps(state))
            edited_prose = "Edited prose with the requested local change."
            app.writer_output_text = FakeText(edited_prose)
            app.writer_state_preview = FakeText()
            app.writer_status = SimpleLabel()
            app.writer_accept_button = FakeButton()
            app.writer_reject_button = FakeButton()
            app.pending_state_patch = None
            app._refresh_manuscript = lambda: None
            app._chat = lambda *_args, **_kwargs: None
            app._update_writer_buttons = lambda: None
            app._ask_yes_no = Mock(return_value=False)

            with patch.object(SceneContract, "validate_with_engine") as validator:
                storybuilder_app.StoryBuilderApp._accept_generated_scene(app)

            validator.assert_not_called()
            app._ask_yes_no.assert_not_called()
            self.assertEqual(app.accepted_scene, edited_prose)
            path = ManuscriptManager(Path(tmp)).scene_path(2, 1)
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_text(encoding="utf-8"), edited_prose + "\n")
    def test_apply_state_update_saves_end_state_snapshot_before_advancing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = {
                "chapter": 2,
                "scene": 1,
                "status": "in_progress",
                "scene_completed": False,
                "chapter_completed": False,
                "current_situation": "Scene 1 starting situation.",
                "scene_cast": ["Maya", "Tony"],
            }
            guidance = {
                "chapter_plans": {
                    "2": {
                        "scene_plan": {
                            "1": {"cast": ["Maya", "Tony"]},
                            "2": {"cast": ["Maya", "Tony"]},
                        }
                    }
                }
            }
            app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
            app.package = SimpleNamespace(
                path=root,
                current_state=state,
                extra_json={"writing_guidance.json": guidance},
            )
            app.pending_state_patch = {
                "current_situation": (
                    "Maya has told Tony that Tiffany is gone and is too shaken to explain more."
                )
            }
            app.generated_scene = ""
            app.accepted_scene = ""
            app.generated_scene_context = None
            app.generated_scene_start_state = None
            app.writer_generation_context = None
            app.writer_generation_start_state = None
            app.writer_generation_in_progress = False
            app.scene_contract_building = False
            app.writer_output_text = FakeText()
            app.writer_state_preview = FakeText(json.dumps({**state, **app.pending_state_patch}))
            app.writer_status = SimpleLabel()
            app._writer_editor_prose = lambda: ""
            app._save_unsaved_writer_draft = lambda: True
            app._final_planned_scene_for_chapter = lambda _chapter: 4
            app._scene_plan_cast = lambda chapter, scene: ["Maya", "Tony"] if (chapter, scene) == (2, 2) else []
            app._refresh_all = lambda: None
            app._save = lambda: setattr(app, "dirty", False)
            app._build_scene_direction = lambda: None
            app._chat = lambda *_args, **_kwargs: None
            app._update_writer_buttons = lambda: None

            storybuilder_app.StoryBuilderApp._apply_state_update(app)

            snapshot_path = (
                root / "Manuscript" / "Chapters" / "Chapter_02" /
                "Chapter_02_Section_01_after_state.json"
            )
            self.assertTrue(snapshot_path.is_file())
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual((snapshot["chapter"], snapshot["scene"]), (2, 1))
            self.assertEqual(
                snapshot["current_situation"],
                "Maya has told Tony that Tiffany is gone and is too shaken to explain more.",
            )
            self.assertEqual(app.package.current_state["scene"], 2)

    def test_apply_state_update_does_not_auto_finalize_at_the_planned_last_scene(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = {
                "chapter": 2,
                "scene": 2,
                "status": "in_progress",
                "scene_completed": False,
                "chapter_completed": False,
                "current_situation": "Scene 2 starting situation.",
            }
            guidance = {
                "chapter_plans": {
                    "2": {
                        "scene_plan": {
                            "1": {"cast": ["Maya", "Tony"]},
                            "2": {"cast": ["Maya", "Tony"]},
                        }
                    }
                }
            }
            app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
            app.package = SimpleNamespace(
                path=root,
                current_state=state,
                extra_json={"writing_guidance.json": guidance},
            )
            app.pending_state_patch = {"current_situation": "Scene 2 ending situation."}
            app.generated_scene = ""
            app.accepted_scene = ""
            app.generated_scene_context = None
            app.generated_scene_start_state = None
            app.writer_generation_context = None
            app.writer_generation_start_state = None
            app.writer_generation_in_progress = False
            app.scene_contract_building = False
            app.writer_output_text = FakeText()
            app.writer_state_preview = FakeText(json.dumps({**state, **app.pending_state_patch}))
            app.writer_status = SimpleLabel()
            app._writer_editor_prose = lambda: ""
            app._save_unsaved_writer_draft = lambda: True
            app._final_planned_scene_for_chapter = lambda _chapter: 2
            app._scene_plan_cast = lambda _chapter, _scene: []
            app._refresh_all = lambda: None
            app._save = lambda: setattr(app, "dirty", False)
            app._build_scene_direction = lambda: None
            app._chat = lambda *_args, **_kwargs: None
            app._update_writer_buttons = lambda: None

            storybuilder_app.StoryBuilderApp._apply_state_update(app)

            self.assertEqual(app.package.current_state["scene"], 3)
            self.assertFalse(app.package.current_state["scene_completed"])
            self.assertFalse(app.package.current_state["chapter_completed"])

    def test_advance_to_next_scene_ignores_the_planned_scene_limit(self):
        state = {
            "chapter": 2,
            "scene": 2,
            "scene_completed": False,
            "chapter_completed": False,
        }
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(
            path=None,
            current_state=state,
            extra_json={
                "writing_guidance.json": {
                    "chapter_plans": {
                        "2": {"scene_plan": {"1": {}, "2": {}}}
                    }
                }
            },
        )
        app._prepare_for_scene_change = lambda *_args: True
        app._scene_plan_cast = lambda *_args: []
        app._clear_writer_scene_workspace = lambda *_args: None
        app._refresh_all = lambda: None
        app._save = lambda: None
        app._chat = lambda *_args, **_kwargs: None
        app.writer_status = SimpleLabel()
        app._update_writer_buttons = lambda: None

        with patch.object(storybuilder_app.messagebox, "showinfo") as info, patch.object(
            storybuilder_app.messagebox, "showerror"
        ) as error:
            storybuilder_app.StoryBuilderApp._advance_to_next_scene(app)

        self.assertEqual(app.package.current_state["scene"], 3)
        info.assert_not_called()
        error.assert_not_called()

    def test_finalize_chapter_restores_last_accepted_scene_ending_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter_dir = root / "Manuscript" / "Chapters" / "Chapter_02"
            chapter_dir.mkdir(parents=True)
            (chapter_dir / "Chapter_02_Section_02.txt").write_text(
                "Maya recounts what happened to Tiffany.", encoding="utf-8"
            )
            ending = {
                "chapter": 2,
                "scene": 2,
                "status": "in_progress",
                "scene_completed": False,
                "chapter_completed": False,
                "current_situation": "Correct ending state from accepted Scene 2.",
                "scene_cast": ["Maya", "Tony"],
            }
            (chapter_dir / "Chapter_02_Section_02_after_state.json").write_text(
                json.dumps(ending), encoding="utf-8"
            )
            app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
            app.package = SimpleNamespace(
                path=root,
                current_state={
                    "chapter": 2,
                    "scene": 3,
                    "status": "in_progress",
                    "scene_completed": False,
                    "chapter_completed": False,
                    "current_situation": "Should not be kept from the next-scene pointer.",
                    "scene_cast": ["Wrong next-scene cast"],
                },
            )
            persisted = {}
            app.dirty = False
            app.accepted_scene = ""
            app._ask_yes_no = lambda *_args: True
            app._save_unsaved_writer_draft = lambda: True
            app._apply_all_edits = lambda: True
            app._update_path_label = lambda: None
            app._refresh_all = lambda: None
            app._save = lambda: persisted.update(
                state=json.loads(json.dumps(app.package.current_state))
            )
            app._chat = lambda *_args, **_kwargs: None
            app.writer_status = SimpleLabel()
            app.manuscript_recovery_status = SimpleLabel()

            storybuilder_app.StoryBuilderApp._finalize_current_chapter(app)

            final_state = app.package.current_state
            self.assertEqual((final_state["chapter"], final_state["scene"]), (2, 2))
            self.assertTrue(final_state["scene_completed"])
            self.assertTrue(final_state["chapter_completed"])
            self.assertEqual(
                final_state["current_situation"],
                "Correct ending state from accepted Scene 2.",
            )
            self.assertEqual(final_state["scene_cast"], ["Maya", "Tony"])
            self.assertEqual(persisted["state"], final_state)
            self.assertIn("finalized", app.writer_status.text.casefold())

    def test_authored_state_after_is_a_hint_and_does_not_bypass_prose_analysis(self):
        class ImmediateThread:
            def __init__(self, target, daemon=False):
                self.target = target

            def start(self):
                self.target()

        with tempfile.TemporaryDirectory() as tmp:
            state = {
                "chapter": 2,
                "scene": 1,
                "status": "in_progress",
                "scene_completed": False,
                "current_situation": "Maya has reached Tony.",
                "scene_cast": ["Maya", "Tony"],
            }
            app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
            app.package = SimpleNamespace(path=Path(tmp), current_state=state)
            app.accepted_scene = "Maya tells Tony the man hit her, then remains too shaken to say more."
            app.writer_engine = SimpleNamespace(model_path=Path("/tmp/fake-writer.gguf"))
            app.writer_reload_scene_button = FakeButton()
            app.writer_analyze_button = FakeButton()
            app.writer_apply_state_button = FakeButton()
            app.writer_state_preview = FakeText()
            app.writer_status = SimpleLabel()
            app._scene_contract = lambda *_args: {
                "state_after": {
                    "current_situation": "PLANNED BUT NOT PROVEN: Maya gives a full account."
                }
            }
            app._scene_end_guidance = lambda *_args: (
                "EXPECTED END STATE HINT:\n"
                "{\"current_situation\": \"PLANNED BUT NOT PROVEN: Maya gives a full account.\"}"
            )
            app._update_writer_buttons = lambda: None
            app.after = lambda _delay, callback: callback()
            analysis_patch = {
                "current_situation": (
                    "Maya has told Tony the man hit her but remains too shaken to explain more."
                )
            }

            with (
                patch.object(storybuilder_app.threading, "Thread", ImmediateThread),
                patch.object(storybuilder_app.StateManager, "propose", return_value=analysis_patch) as propose,
            ):
                storybuilder_app.StoryBuilderApp._analyze_accepted_scene(app)

            propose.assert_called_once()
            self.assertIn("EXPECTED END STATE HINT", propose.call_args.kwargs["scene_end_guidance"])
            self.assertEqual(app.pending_state_patch, analysis_patch)
            self.assertNotIn("PLANNED BUT NOT PROVEN", app.writer_state_preview.get("1.0", "end"))

    def test_writer_state_analysis_previews_full_reconciled_state_without_applying_it(self):
        before = {
            "chapter": 2,
            "scene": 4,
            "current_situation": "Tony and Maya are in the bedroom.",
            "location": {
                "primary": "Tony's bedroom",
                "Tony": "Tony's bedroom",
                "Maya": "Tony's bedroom",
            },
            "Tony": "At home, awake in his bedroom with Maya.",
            "Maya": "In Tony's bedroom, clinging to Tony.",
            "physical_state": {
                "Tony": {"location": "Tony's bedroom", "position": "on the bed"},
                "Maya": {"location": "Tony's bedroom", "position": "beside Tony"},
            },
            "character_knowledge": {
                "Tony": ["Tony knows Tiffany is missing."],
            },
            "recent_events": ["Tony reassured Maya in the bedroom."],
        }
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(current_state=before)
        app.writer_state_preview = FakeText()
        app.writer_status = SimpleLabel()
        app._update_writer_buttons = Mock()
        patch = {
            "current_situation": (
                "Tony and Maya share a quiet moment over tea at the kitchen table."
            ),
            "location": {
                "primary": "Kitchen",
                "Tony": "Kitchen",
                "Maya": "Kitchen",
            },
            "physical_state": {
                "Tony": {"position": "seated at the kitchen table"},
                "Maya": {"position": "seated opposite Tony at the kitchen table"},
            },
        }

        storybuilder_app.StoryBuilderApp._finish_state_analysis(app, patch, None)

        preview = json.loads(app.writer_state_preview.get("1.0", "end"))
        self.assertEqual(app.pending_state_patch, patch)
        self.assertEqual(preview["location"]["primary"], "Kitchen")
        self.assertEqual(preview["physical_state"]["Tony"]["location"], "Kitchen")
        self.assertEqual(preview["physical_state"]["Maya"]["location"], "Kitchen")
        self.assertNotIn("Tony", preview)
        self.assertNotIn("Maya", preview)
        self.assertEqual(
            preview["character_knowledge"],
            before["character_knowledge"],
        )
        self.assertEqual(preview["recent_events"], before["recent_events"])
        self.assertEqual(app.package.current_state, before)
        self.assertIn("Nothing has been applied", app.writer_status.text)

    def test_generated_contract_text_is_read_only_after_each_programmatic_update(self):
        widget = FakeText("old generated text")

        storybuilder_app.StoryBuilderApp._set_generated_contract_text(
            widget, "new generated text"
        )

        self.assertEqual(widget.value, "new generated text")
        self.assertEqual(widget.state, "disabled")

    def test_saving_scene_idea_does_not_overwrite_generated_contract_fields(self):
        entry = {
            "scene_idea": "old idea",
            "direction": "generated direction",
            "end_condition": "generated hard stop",
            "scene_contract": {"required_beats": ["generated beat"]},
        }
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(
            path=None,
            current_state={"chapter": 2, "scene": 2},
        )
        app.scene_contract_editor_key = (2, 2)
        app.scene_idea_text = FakeText("revised author idea")
        app.scene_contract_status = SimpleLabel()
        app.dirty = False
        app._editable_scene_guidance_entry = lambda *_args, **_kwargs: entry
        app._update_path_label = lambda: None

        storybuilder_app.StoryBuilderApp._apply_scene_contract_edits(app)

        self.assertEqual(entry["scene_idea"], "revised author idea")
        self.assertEqual(entry["direction"], "generated direction")
        self.assertEqual(entry["end_condition"], "generated hard stop")
        self.assertEqual(
            entry["scene_contract"],
            {"required_beats": ["generated beat"]},
        )

    def test_rebuilding_contract_clears_legacy_rules_and_stale_state_hint(self):
        entry = {
            "scene_idea": "author idea",
            "cast": ["Maya", "Tony"],
            "required_beats": ["old beat"],
            "required_events": ["old event"],
            "do_not_advance": ["old boundary"],
            "state_after": {"current_situation": "old ending"},
        }

        storybuilder_app.StoryBuilderApp._clear_stale_generated_scene_contract_fields(entry)

        self.assertEqual(entry["scene_idea"], "author idea")
        self.assertEqual(entry["cast"], ["Maya", "Tony"])
        self.assertNotIn("required_beats", entry)
        self.assertNotIn("required_events", entry)
        self.assertNotIn("do_not_advance", entry)
        self.assertNotIn("state_after", entry)

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

    def test_runtime_contract_keeps_saved_plain_english_scene_idea(self):
        idea = (
            "Tony offers Maya a warm bubble bath. He invites Beth to breakfast, then "
            "Jessica, Chloe, and Rick together without revealing the abduction. He returns "
            "Barnaby to Tiffany's room and later sits with Maya at the kitchen table with tea."
        )
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(
            extra_json={
                "writing_guidance.json": {
                    "chapter_plans": {
                        "2": {
                            "scene_plan": {
                                "4": {
                                    "scene_idea": idea,
                                    "direction": "Tony cares for Maya.",
                                    "end_condition": "Before bedtime.",
                                    "scene_contract": {
                                        "required_beats": [],
                                        "hard_stop": "Before bedtime.",
                                        "max_attempts": 3,
                                    },
                                }
                            }
                        }
                    }
                }
            },
            story_bible={"optional_story_modules": []},
        )

        contract = app._scene_contract(2, 4)
        prompt_context = SceneContract.writer_prompt_context(
            "Chapter 2, Scene 4. Maya is at Tony's home.",
            contract,
        )

        self.assertEqual(contract["author_idea"], idea)
        self.assertIn(idea, prompt_context)
        self.assertIn("AUTHOR'S ORIGINAL PLAIN-ENGLISH SCENE IDEA (PRIMARY INTENT)", prompt_context)

    def test_contract_builder_prioritizes_current_situation_over_stale_physical_state(self):
        self.assertIn(
            "current_situation as the authoritative narrative snapshot",
            CONTRACT_BUILDER_SYSTEM_PROMPT,
        )
        self.assertIn(
            "If they conflict, follow current_situation",
            CONTRACT_BUILDER_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Do not turn the idea into a checklist",
            CONTRACT_BUILDER_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Always return required_beats as an empty list",
            CONTRACT_BUILDER_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Never turn ordinary prose or your own summary into mandatory stops",
            CONTRACT_BUILDER_SYSTEM_PROMPT,
        )


    def test_writer_package_includes_stable_author_writing_guidance(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(
            current_state={
                "chapter": 2,
                "scene": 4,
                "location": {"primary": "Tony's bedroom", "Beth": "next door"},
                "time": "afternoon",
                "scene_cast": ["Tony", "Maya"],
                "current_situation": "Tony is comforting Maya.",
                "physical_state": {},
                "character_knowledge": {},
            },
            writer_notes={},
            characters={},
            story_bible={
                "relationships": {"Tony-Maya": "close family-like friendship"},
                "supporting_people": {"Beth": "Maya's mother"},
                "canon_rules": ["Only Tony and Maya know Tiffany is missing."],
            },
            extra_json={
                "writing_guidance.json": {
                    "recurring_instructions": ["Do not introduce floral scents."],
                    "relationship_freedom": ["Allow ordinary conversation when it fits."],
                    "avoid": ["Do not add a second kidnapper."],
                    "scene_plan": {"4": {"direction": "SCENE-ONLY-CONTEXT"}},
                },
            },
        )

        files = dict(app._writer_package_files())
        self.assertIn("author_writing_guidance.txt", files)
        self.assertIn("Do not introduce floral scents.", files["author_writing_guidance.txt"])
        self.assertIn("Allow ordinary conversation when it fits.", files["author_writing_guidance.txt"])
        self.assertIn("Do not add a second kidnapper.", files["author_writing_guidance.txt"])
        self.assertNotIn("SCENE-ONLY-CONTEXT", files["author_writing_guidance.txt"])

        prompt = app._writer_system_prompt(app._writer_package_files())
        self.assertIn("Do not introduce floral scents.", prompt)
        self.assertIn("Stable author writing guidance", prompt)
        self.assertIn("Honor clear prohibitions when relevant.", prompt)

    def test_writer_context_includes_later_planned_character_card_and_knowledge_without_moving_physical_state(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(
            path=None,
            current_state={
                "chapter": 1,
                "scene": 1,
                "location": {"primary": "Tony's kitchen", "Tony": "Kitchen", "Maya": "Kitchen", "Chloe": "Approaching the house"},
                "time": "morning",
                "scene_cast": ["Tony", "Maya"],
                "current_situation": "Tony and Maya are in the kitchen.",
                "physical_state": {
                    "Tony": {"location": "Kitchen", "position": "standing"},
                    "Maya": {"location": "Kitchen", "position": "sitting"},
                    "Chloe": {"location": "Approaching the house", "position": "outside"},
                },
                "character_knowledge": {
                    "Tony": ["Tony knows Tiffany is his daughter."],
                    "Maya": ["Maya knows Tiffany is missing."],
                    "Chloe": ["Chloe promised to keep Tiffany's identity secret."],
                },
            },
            writer_notes={},
            characters={
                "Tony.json": {"name": "Tony", "personality": "Protective father."},
                "Maya.json": {"name": "Maya", "personality": "Practical friend."},
                "Chloe.json": {"name": "Chloe", "personality": "Community organizer who values loyalty."},
            },
            story_bible={
                "relationships": {"Tony-Maya": "close family-like friendship"},
                "supporting_people": {},
                "canon_rules": [],
            },
            extra_json={
                "writing_guidance.json": {
                    "scene_plan": {
                        "1": {
                            "cast": ["Tony", "Maya"],
                            "scene_idea": "Tony and Maya discuss the search. Chloe arrives and offers help.",
                            "direction": "Let Chloe arrive later in the scene and hear the agreed plan.",
                            "end_condition": "The three begin coordinating.",
                        }
                    }
                }
            },
        )

        files = dict(app._writer_package_files())
        knowledge = json.loads(files["scene_character_knowledge.json"])
        character_cards = json.loads(files["scene_characters.json"])
        physical = json.loads(files["scene_physical_state.json"])

        self.assertIn("Chloe", knowledge)
        self.assertIn("promised to keep", knowledge["Chloe"][0])
        self.assertIn("Chloe", character_cards)
        self.assertEqual(set(physical), {"Tony", "Maya"})
        self.assertNotIn("Chloe", physical)

    def test_writer_system_prompt_prioritizes_scene_idea_without_turning_it_into_a_checklist(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        prompt = app._writer_system_prompt([])

        self.assertIn(
            "The original plain-English Scene Idea expresses the scene's purpose and direction",
            prompt,
        )
        self.assertIn("Treat the Scene Idea as direction, not a line-by-line script.", prompt)
        self.assertIn("Honor an explicit endpoint or hard stop", prompt)
        self.assertIn(
            "carry it through that arc instead of stopping after the first prominent action",
            prompt,
        )
        self.assertIn("Do not replay completed events", prompt)
        self.assertIn("Knowing that an event happened is not the same as witnessing it.", prompt)
        self.assertNotIn(
            "Do not reduce a multi-phase or time-spanning scene to one emphasized action",
            prompt,
        )

    def test_writer_prompt_preserves_anchors_and_encourages_creative_execution(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        prompt = app._writer_system_prompt([])

        self.assertIn("The author's canon, explicit boundaries, and clearly stated requirements are the firm ground.", prompt)
        self.assertIn("Treat general writing preferences as a tonal compass, not a checklist.", prompt)
        self.assertIn(
            "Invent natural dialogue, small talk, gestures, sensory texture, routines, background activity, incidental characters, plausible shared memories, transitions, and connective actions.",
            prompt,
        )
        self.assertIn("Creative developments are welcome when they fit the story.", prompt)
        self.assertIn("Let character voice, mood, and author preferences shape the prose without turning them into formulas.", prompt)
        self.assertNotIn("Respect privacy, dignity, established boundaries, and relationship-specific behavior", prompt)
        self.assertNotIn("Do not add unprompted ominous narration", prompt)

        notes_prompt = app._writer_system_prompt([
            ("working_writer_notes.json", '{"learned_notes":[{"note":"Use selective description and avoid repeating an emotion."}]}')
        ])
        self.assertIn("Temporary writer notes are suggestions, not canon.", notes_prompt)
        self.assertIn("Use selective description and avoid repeating an emotion.", notes_prompt)

    def test_scene_boundary_prompt_encourages_creativity_while_preserving_endpoints(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        prompt = app._writer_scene_boundary_prompt()

        self.assertIn("The idea gives purpose and direction, not a script.", prompt)
        self.assertIn("incidental details, connective actions, and fitting story turns", prompt)
        self.assertIn("do not cross a stated hard stop", prompt)
        self.assertIn("Output only the prose.", prompt)

    def test_semantic_validator_checks_opening_physical_continuity(self):
        current_state = {
            "chapter": 2,
            "scene": 1,
            "current_situation": (
                "Maya is against Tony's chest. Tony is comforting her."
            ),
            "physical_state": {
                "Tony": {
                    "position": "sitting upright against the headboard",
                    "contact": "holding Maya against his chest",
                }
            },
        }
        contract = {
            "direction": "Tony provides a familiar fatherly comfort gesture.",
            "required_beats": ["Tony comforts Maya"],
            "required_facts": [],
            "required_sequence": [],
            "forbidden": [],
            "forbidden_details": [],
            "max_attempts": 3,
        }
        captured = {}

        def fake_validator(_model, prompt):
            captured["prompt"] = prompt
            return {
                "pass": True,
                "missed_beats": [],
                "violations": [],
                "notes": "",
            }

        with patch.object(
            SceneContract,
            "_local_hard_checks",
            return_value={
                "pass": True,
                "missed_beats": [],
                "violations": [],
                "notes": "",
            },
        ), patch("builder.scene_contract._run_validator", side_effect=fake_validator):
            SceneContract.validate_with_engine(
                SimpleNamespace(model_path=Path("/tmp/test-model.gguf")),
                contract,
                current_state,
                "Tony sat on the edge of the bed and held Maya.",
            )

        self.assertIn("Flag unexplained opening continuity mismatches", scene_contract.VALIDATOR_SYSTEM_PROMPT)
        self.assertIn("unexplained opening continuity mismatches", scene_contract.VALIDATOR_SYSTEM_PROMPT)
        self.assertIn("sitting upright against the headboard", captured["prompt"])
        self.assertIn("neutral familial comfort", scene_contract.VALIDATOR_SYSTEM_PROMPT)
        self.assertIn("Tony provides a familiar fatherly comfort gesture.", captured["prompt"])

    def make_save_app(self, package_path, situation, writer_generation=False):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        persisted = {}
        state = {
            "chapter": 2,
            "scene": 1,
            "scene_completed": False,
            "current_situation": "Old saved situation",
        }
        package = SimpleNamespace(path=Path(package_path), current_state=state)
        package.save = lambda: persisted.update(
            current_situation=package.current_state["current_situation"]
        )
        app.package = package
        app.situation_text = FakeText(situation)
        app.generated_scene = ""
        app.accepted_scene = ""
        app.writer_generation_in_progress = writer_generation
        app.scene_contract_building = False
        app.dirty = False
        app._save_unsaved_writer_draft = lambda: True
        app._clear_writer_scene_workspace = lambda *_args: None
        app._update_path_label = lambda: None
        app._build_scene_direction = lambda: None
        app._chat = lambda *_args, **_kwargs: None

        # Isolate the normal save pipeline so the test focuses on whether the
        # Current Situation editor reaches package state before persistence.
        for method_name in (
            "_apply_story_edits",
            "_apply_planning_edits",
            "_apply_scene_contract_edits",
            "_apply_character_edits",
            "_apply_supporting_person_edit",
            "_apply_relationship_edits",
            "_apply_location_edits",
        ):
            setattr(app, method_name, lambda: None)
        app._apply_state_edits = lambda: True
        return app, persisted

    def test_normal_save_applies_and_persists_current_situation(self):
        with tempfile.TemporaryDirectory() as tmp:
            corrected = "Maya is already curled against Tony's chest."
            app, persisted = self.make_save_app(tmp, corrected)

            storybuilder_app.StoryBuilderApp._save(app)

            self.assertEqual(app.package.current_state["current_situation"], corrected)
            self.assertEqual(persisted["current_situation"], corrected)
            self.assertFalse(app.dirty)

    def test_save_is_blocked_if_current_situation_cannot_be_applied_during_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            app, persisted = self.make_save_app(
                tmp,
                "A changed situation that must not be applied during generation.",
                writer_generation=True,
            )
            with patch.object(storybuilder_app.messagebox, "showwarning") as warning:
                storybuilder_app.StoryBuilderApp._save(app)

            warning.assert_called_once()
            self.assertEqual(
                app.package.current_state["current_situation"],
                "Old saved situation",
            )
            self.assertNotIn("current_situation", persisted)


class SimpleLabel:
    def __init__(self):
        self.text = ""

    def configure(self, **kwargs):
        if "text" in kwargs:
            self.text = kwargs["text"]


class SceneResetSafetyTests(unittest.TestCase):
    def make_restore_app(self, package_path, current_state):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        persisted = {}
        package = SimpleNamespace(
            path=Path(package_path),
            current_state=current_state,
            extra_json={},
        )
        package.save = lambda: persisted.update(
            current_state=json.loads(json.dumps(package.current_state))
        )
        app.package = package
        app.dirty = False
        app.writer_generation_in_progress = False
        app.scene_contract_building = False
        app.writer_notes_update_in_progress = False
        app.generated_scene = ""
        app.accepted_scene = ""
        app._save_unsaved_writer_draft = lambda: True
        app._clear_writer_scene_workspace = lambda *_args: None
        app._refresh_all = lambda: None
        app._build_scene_direction = lambda: None
        app._update_path_label = lambda: None
        app._chat = lambda *_args, **_kwargs: None
        return app, persisted

    def test_restore_previous_scene_end_state_resets_pointer_and_restores_situation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter = root / "Manuscript" / "Chapters" / "Chapter_01"
            chapter.mkdir(parents=True)
            (chapter / "Chapter_01_Section_06.txt").write_text(
                "Maya tells Tony Tiffany is gone.", encoding="utf-8"
            )
            saved_end_state = {
                "chapter": 1,
                "scene": 6,
                "status": "story_start",
                "scene_completed": False,
                "chapter_completed": False,
                "current_situation": (
                    "Maya has reached Tony and told him that Tiffany is gone. "
                    "Tony has not yet noticed the slap mark."
                ),
                "scene_cast": ["Maya", "Tony"],
                "physical_state": {"Tony": {"contact": "holding Maya against his chest"}},
            }
            (chapter / "Chapter_01_Section_06_after_state.json").write_text(
                json.dumps(saved_end_state), encoding="utf-8"
            )
            current = {
                "chapter": 2,
                "scene": 1,
                "status": "in_progress",
                "scene_completed": False,
                "current_situation": "STALE: Tony has already noticed the slap mark.",
            }
            app, persisted = self.make_restore_app(root, current)

            with patch.object(
                storybuilder_app.StoryBuilderApp, "_ask_yes_no", return_value=True
            ) as confirm:
                storybuilder_app.StoryBuilderApp._restore_previous_scene_end_state(app)

            restored = app.package.current_state
            self.assertEqual((restored["chapter"], restored["scene"]), (2, 1))
            self.assertEqual(restored["status"], "in_progress")
            self.assertFalse(restored["scene_completed"])
            self.assertFalse(restored["chapter_completed"])
            self.assertIn("has not yet noticed the slap mark", restored["current_situation"])
            self.assertNotIn("STALE:", restored["current_situation"])
            self.assertEqual(restored["physical_state"], saved_end_state["physical_state"])
            self.assertEqual(persisted["current_state"], restored)
            self.assertIn("Chapter 1, Scene 6", confirm.call_args.args[1])

    def test_restore_previous_scene_end_state_cancel_leaves_state_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter = root / "Manuscript" / "Chapters" / "Chapter_01"
            chapter.mkdir(parents=True)
            (chapter / "Chapter_01_Section_06.txt").write_text("Accepted prose", encoding="utf-8")
            (chapter / "Chapter_01_Section_06_after_state.json").write_text(
                json.dumps({
                    "chapter": 1, "scene": 6,
                    "current_situation": "Correct start state.",
                }),
                encoding="utf-8",
            )
            current = {
                "chapter": 2, "scene": 1,
                "current_situation": "Leave this alone.",
                "scene_completed": False,
            }
            app, persisted = self.make_restore_app(root, current)
            original = json.loads(json.dumps(current))

            with patch.object(
                storybuilder_app.StoryBuilderApp, "_ask_yes_no", return_value=False
            ) as confirm:
                storybuilder_app.StoryBuilderApp._restore_previous_scene_end_state(app)

            self.assertEqual(app.package.current_state, original)
            self.assertFalse(persisted)
            confirm.assert_called_once()

    def test_reset_scene_contract_clears_generated_fields_but_preserves_idea(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry = {
                "scene_idea": "Preserve my scene idea.",
                "direction": "Stale direction based on the wrong start state.",
                "end_condition": "Stale end.",
                "scene_contract": {"required_beats": ["Stale beat"]},
                "cast": ["Maya", "Tony"],
            }
            guidance = {"chapter_plans": {"2": {"scene_plan": {"1": entry}}}}
            saved = []
            package = SimpleNamespace(
                path=Path(tmp),
                current_state={"chapter": 2, "scene": 1},
                extra_json={"writing_guidance.json": guidance},
            )
            package.save = lambda: saved.append(True)
            app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
            app.package = package
            app.dirty = False
            app.scene_contract_building = False
            app.writer_generation_in_progress = False
            app.scene_idea_text = FakeText("Preserve my scene idea.")
            app.scene_contract_status = SimpleLabel()
            app._update_path_label = lambda: None
            app._refresh_scene_contract_editor = lambda: None
            app._build_scene_direction = lambda: None
            app._chat = lambda *_args, **_kwargs: None

            with patch.object(
                storybuilder_app.StoryBuilderApp, "_ask_yes_no", return_value=True
            ):
                storybuilder_app.StoryBuilderApp._reset_current_scene_contract(app)

            self.assertEqual(entry["scene_idea"], "Preserve my scene idea.")
            self.assertNotIn("direction", entry)
            self.assertNotIn("end_condition", entry)
            self.assertNotIn("scene_contract", entry)
            self.assertEqual(entry["cast"], ["Maya", "Tony"])
            self.assertEqual(saved, [True])

    def test_clear_writer_context_requires_confirmation(self):
        class Child:
            def isalive(self):
                return True

        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace()
        app.writer_engine = SimpleNamespace(child=Child(), model_path=Path("/tmp/model.gguf"))
        app._save = lambda: self.fail("Save should not run when reset is cancelled.")
        with patch.object(
            storybuilder_app.StoryBuilderApp, "_ask_yes_no", return_value=False
        ) as confirm:
            storybuilder_app.StoryBuilderApp._clear_writer_context(app)
        confirm.assert_called_once()


    def test_writer_direction_prefers_explicit_scene_header_and_labels_opening_cast(self):
        idea = """Breakfast disclosure and the first offers to help

**Scene header:**

CHAPTER 3, SCENE 2
Location: Tony's home
Time: Saturday morning at daybreak

**Starting point:** Beth, Chloe, Jessica, and Rick arrive later for breakfast.
"""
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(
            current_state={
                "chapter": 3,
                "scene": 2,
                "time": {"period": "daybreak / early morning", "exact_time": "not established"},
                "location": {"primary": "Tony's home"},
                "scene_cast": ["Tony", "Maya"],
                "current_situation": "Tony is at home. Maya is asleep in Tiffany's bedroom.",
                "physical_state": {
                    "Tony": {"location": "Tony's bedroom", "position": "near the window"},
                    "Maya": {"location": "Tiffany's bedroom", "position": "on the bed", "posture": "sleeping"},
                },
            },
            extra_json={
                "writing_guidance.json": {
                    "chapter_plans": {
                        "3": {"scene_plan": {"2": {
                            "scene_idea": idea,
                            "direction": "The guests arrive after Tony wakes Maya.",
                            "end_condition": "End as the group begins committing to a private effort.",
                        }}}
                    }
                }
            },
            story_bible={"optional_story_modules": []},
        )
        app.writer_direction_text = FakeText()
        app.writer_status = FakeButton()

        storybuilder_app.StoryBuilderApp._build_scene_direction(app, update_status=False)
        direction = app.writer_direction_text.value

        self.assertIn("Location: Tony's home", direction)
        self.assertIn("Time: Saturday morning at daybreak", direction)
        self.assertNotIn("Time: daybreak / early morning", direction)
        self.assertIn("Opening cast (present at scene start only; not the full scene cast): Tony, Maya", direction)
        self.assertIn("Opening physical continuity (starting positions only):", direction)
        self.assertIn("do not exclude later arrivals named in the original Scene Idea", direction)
        self.assertNotIn("Cast: Tony, Maya", direction)


if __name__ == "__main__":
    unittest.main()


class NovelSyncSafetyTests(unittest.TestCase):
    def test_conflict_aborts_rebase_and_preserves_local_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls = []

            def fake_git(_root, *args):
                calls.append(args)
                if args == ("rev-parse", "--show-toplevel"):
                    return SimpleNamespace(returncode=0, stdout=str(root), stderr="")
                if args == ("branch", "--show-current"):
                    return SimpleNamespace(returncode=0, stdout="main", stderr="")
                if args == ("status",):
                    return SimpleNamespace(
                        returncode=0,
                        stdout="On branch main\\nnothing to commit, working tree clean",
                        stderr="",
                    )
                if args == ("diff", "--name-only", "--diff-filter=U"):
                    return SimpleNamespace(returncode=0, stdout="", stderr="")
                if args == ("status", "--porcelain"):
                    return SimpleNamespace(returncode=0, stdout="", stderr="")
                if args == ("fetch", "--prune", "origin"):
                    return SimpleNamespace(returncode=0, stdout="", stderr="")
                if args == ("pull", "--rebase", "origin", "main"):
                    return SimpleNamespace(
                        returncode=1,
                        stdout="CONFLICT (content): writing_guidance.json",
                        stderr="error: could not apply 4c433ca... Sync novel changes",
                    )
                if args == ("rebase", "--abort"):
                    return SimpleNamespace(returncode=0, stdout="", stderr="")
                if args == ("status", "-sb"):
                    return SimpleNamespace(
                        returncode=0,
                        stdout="## main...origin/main [ahead 1, behind 1]",
                        stderr="",
                    )
                raise AssertionError(f"Unexpected git command: {args}")

            with patch.object(novel_sync, "_run_git", side_effect=fake_git):
                with self.assertRaisesRegex(
                    novel_sync.NovelSyncError,
                    "automatically aborted the incomplete rebase",
                ) as caught:
                    novel_sync.sync_novel_repository(root)

            self.assertIn("Your local commit is preserved on main", str(caught.exception))
            self.assertIn("CONFLICT (content): writing_guidance.json", str(caught.exception))
            self.assertIn("error: could not apply 4c433ca", str(caught.exception))
            self.assertIn(("rebase", "--abort"), calls)
            self.assertNotIn(("push", "origin", "main"), calls)

    def test_recovers_preexisting_rebase_before_branch_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls = []
            status_checks = 0

            def fake_git(_root, *args):
                nonlocal status_checks
                calls.append(args)
                if args == ("rev-parse", "--show-toplevel"):
                    return SimpleNamespace(returncode=0, stdout=str(root), stderr="")
                if args == ("status",):
                    status_checks += 1
                    if status_checks == 1:
                        return SimpleNamespace(
                            returncode=0,
                            stdout="interactive rebase in progress; onto abc123",
                            stderr="",
                        )
                    return SimpleNamespace(
                        returncode=0,
                        stdout="On branch main\nnothing to commit, working tree clean",
                        stderr="",
                    )
                if args == ("rebase", "--abort"):
                    return SimpleNamespace(returncode=0, stdout="", stderr="")
                if args == ("branch", "--show-current"):
                    return SimpleNamespace(returncode=0, stdout="main", stderr="")
                if args == ("diff", "--name-only", "--diff-filter=U"):
                    return SimpleNamespace(returncode=0, stdout="", stderr="")
                if args == ("status", "--porcelain"):
                    return SimpleNamespace(returncode=0, stdout="", stderr="")
                if args == ("fetch", "--prune", "origin"):
                    return SimpleNamespace(returncode=0, stdout="", stderr="")
                if args == ("pull", "--rebase", "origin", "main"):
                    return SimpleNamespace(returncode=0, stdout="Already up to date.", stderr="")
                if args == ("push", "origin", "main"):
                    return SimpleNamespace(returncode=0, stdout="Everything up-to-date", stderr="")
                if args == ("status", "-sb"):
                    return SimpleNamespace(returncode=0, stdout="## main...origin/main", stderr="")
                raise AssertionError(f"Unexpected git command: {args}")

            with patch.object(novel_sync, "_run_git", side_effect=fake_git):
                result = novel_sync.sync_novel_repository(root)

            self.assertIn("Novel synchronized successfully", result)
            self.assertLess(calls.index(("rebase", "--abort")), calls.index(("branch", "--show-current")))

    def test_novel_sync_rejects_non_main_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def fake_git(_root, *args):
                if args == ("rev-parse", "--show-toplevel"):
                    return SimpleNamespace(returncode=0, stdout=str(root), stderr="")
                if args == ("status",):
                    return SimpleNamespace(
                        returncode=0,
                        stdout="On branch feature/test\nnothing to commit, working tree clean",
                        stderr="",
                    )
                if args == ("branch", "--show-current"):
                    return SimpleNamespace(returncode=0, stdout="feature/test", stderr="")
                raise AssertionError(f"Unexpected git command: {args}")

            with patch.object(novel_sync, "_run_git", side_effect=fake_git):
                with self.assertRaisesRegex(
                    novel_sync.NovelSyncError,
                    "single permanent 'main' branch",
                ):
                    novel_sync.sync_novel_repository(root)



    def make_writer_scene_idea_app(self, saved_idea, editor_idea=None):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(
            current_state={
                "chapter": 2,
                "scene": 4,
                "scene_cast": ["Tony", "Maya"],
                "location": {"primary": "Tony and Tiffany's home"},
                "current_situation": "Tony is with Maya.",
            },
            extra_json={
                "writing_guidance.json": {
                    "chapter_plans": {
                        "2": {
                            "scene_plan": {
                                "4": {
                                    "scene_idea": saved_idea,
                                    "direction": "Tony cares for Maya.",
                                    "end_condition": "End at the kitchen table.",
                                    "scene_contract": {
                                        "required_beats": [
                                            "AI-generated beat must not leak into Writer direction."
                                        ]
                                    },
                                }
                            }
                        }
                    }
                }
            },
            story_bible={"optional_story_modules": []},
        )
        app.scene_contract_editor_key = (2, 4)
        app.scene_idea_text = FakeText(saved_idea if editor_idea is None else editor_idea)
        app.writer_scene_idea_text = FakeText()
        app.writer_scene_idea_status = FakeButton()
        app.writer_direction_text = FakeText()
        app.writer_status = FakeButton()
        app._build_scene_direction = Mock()
        return app

    def test_writer_scene_idea_preview_loads_saved_idea_without_building_contract(self):
        idea = "Tony offers Maya a bubble bath, handles breakfast calls, and ends with tea."
        app = self.make_writer_scene_idea_app(idea)

        storybuilder_app.StoryBuilderApp._refresh_writer_scene_guidance(app)

        self.assertEqual(app.writer_scene_idea_text.value, idea)
        self.assertEqual(app.writer_scene_idea_text.state, "disabled")
        self.assertIn("included directly in the Writer prompt", app.writer_scene_idea_status.options["text"])
        app._build_scene_direction.assert_called_once_with(update_status=False)

    def test_writer_scene_idea_preview_shows_unsaved_editor_text(self):
        saved = "Older saved idea."
        edited = "Revised idea with the bubble bath and tea."
        app = self.make_writer_scene_idea_app(saved, edited)

        storybuilder_app.StoryBuilderApp._refresh_writer_scene_guidance(app)

        self.assertEqual(app.writer_scene_idea_text.value, edited)
        self.assertIn("unsaved Scene Idea edits", app.writer_scene_idea_status.options["text"])

    def test_writer_direction_does_not_copy_legacy_generated_required_beats(self):
        idea = "Tony offers Maya a bubble bath and later makes tea."
        app = self.make_writer_scene_idea_app(idea)
        app.writer_status = Mock()

        storybuilder_app.StoryBuilderApp._build_scene_direction(app, update_status=False)

        self.assertNotIn(
            "AI-generated beat must not leak into Writer direction.",
            app.writer_direction_text.value,
        )
        self.assertIn("Scene direction: Tony cares for Maya.", app.writer_direction_text.value)
        app.writer_status.configure.assert_not_called()

    def test_compact_tab_calls_on_show_callback_for_selected_page(self):
        class FakePage:
            def __init__(self):
                self.packed = False

            def pack(self, **_kwargs):
                self.packed = True

            def pack_forget(self):
                self.packed = False

        class FakeVariable:
            def __init__(self):
                self.value = None

            def set(self, value):
                self.value = value

        container = storybuilder_app.CompactTabContainer.__new__(
            storybuilder_app.CompactTabContainer
        )
        container._pages_by_label = {"Writer": FakePage()}
        container._selected_label = None
        container._section_var = FakeVariable()
        callback = Mock()
        container.on_show = callback

        storybuilder_app.CompactTabContainer._show_page(container, "Writer")

        self.assertTrue(container._pages_by_label["Writer"].packed)
        callback.assert_called_once_with("Writer")
