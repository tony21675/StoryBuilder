import inspect
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
        if _index == "end":
            self.value += value
        else:
            self.value = value

    def see(self, _index):
        pass


class FakePopupWidget:
    """Small Tk widget stand-in used to test error-dialog clipboard behavior."""

    instances = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.bindings = {}
        self.options = {}
        self.commands = []
        self.insertions = []
        FakePopupWidget.instances.append(self)

    def pack(self, *args, **kwargs):
        pass

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def bind(self, sequence, callback):
        self.bindings[sequence] = callback

    def insert(self, *args, **kwargs):
        self.insertions.append(args)

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
    def test_structured_scene_idea_populates_plan_preview_without_saving(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.scene_contract_direction_text = FakeText()
        app.scene_contract_end_text = FakeText()
        app.scene_contract_texts = {
            "required_beats": FakeText(),
            "boundaries": FakeText(),
        }
        idea = (
            "Daniel reports a temperature projection while Elena keeps the inspection external.\n\n"
            "Beginning:\nDaniel presents the projection and its uncertainty.\n\n"
            "Middle:\nElena leads an external inspection while Ryan and Zoe check signal timing.\n\n"
            "End / Hard Stop:\nStop after the crew records observations; the cause remains unknown.\n\n"
            "Planned Beats:\n- Daniel explains the projection.\n- The team records visible conditions.\n\n"
            "Boundaries:\n- Keep the hatch closed until external and sensor causes are assessed."
        )

        sections = storybuilder_app.StoryBuilderApp._preview_scene_idea_sections(app, idea)

        self.assertIn("Beginning: Daniel presents the projection", app.scene_contract_direction_text.value)
        self.assertIn("Middle: Elena leads an external inspection", app.scene_contract_direction_text.value)
        self.assertIn("cause remains unknown", app.scene_contract_end_text.value)
        self.assertEqual(app.scene_contract_texts["required_beats"].value,
                         "Daniel explains the projection.\nThe team records visible conditions.")
        self.assertEqual(app.scene_contract_texts["boundaries"].value,
                         "Keep the hatch closed until external and sensor causes are assessed.")
        self.assertEqual(len(sections["required_beats"]), 2)
        self.assertEqual(app.scene_contract_end_text.state, "disabled")

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

    def test_clear_previous_generated_scene_display_can_preserve_draft(self):
        prose = "The existing draft must remain available during regeneration."
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.generated_scene = prose
        app.generated_scene_context = (3, 3)
        app.generated_scene_start_state = {"chapter": 3, "scene": 3}
        app.focused_revision_history = ["existing revision"]
        app.writer_output_text = FakeText(prose)
        app.writer_state_preview = FakeText("old state preview")
        app.writer_state_diff_preview = FakeText("old state diff")

        storybuilder_app.StoryBuilderApp._clear_previous_generated_scene_display(
            app, preserve_draft=True
        )

        self.assertEqual(app.generated_scene, prose)
        self.assertEqual(app.generated_scene_context, (3, 3))
        self.assertEqual(app.generated_scene_start_state, {"chapter": 3, "scene": 3})
        self.assertEqual(app.focused_revision_history, ["existing revision"])
        self.assertEqual(app.writer_output_text.value, "")
        self.assertEqual(app.writer_state_preview.value, "")
        self.assertEqual(app.writer_state_diff_preview.value, "")
        self.assertEqual(app.writer_state_diff_preview.state, "disabled")

    def test_streamed_writer_text_appends_only_for_active_scene_generation(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.writer_generation_in_progress = True
        app.writer_generation_context = (3, 4)
        app.writer_output_text = FakeText("Opening sentence. ")
        
        storybuilder_app.StoryBuilderApp._append_streamed_scene_chunk(
            app, (3, 4), "Next sentence."
        )
        self.assertEqual(app.writer_output_text.value, "Opening sentence. Next sentence.")

        storybuilder_app.StoryBuilderApp._append_streamed_scene_chunk(
            app, (3, 3), "Stale text."
        )
        self.assertEqual(app.writer_output_text.value, "Opening sentence. Next sentence.")

        app.writer_generation_in_progress = False
        storybuilder_app.StoryBuilderApp._append_streamed_scene_chunk(
            app, (3, 4), "Late text."
        )
        self.assertEqual(app.writer_output_text.value, "Opening sentence. Next sentence.")

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

    def test_reload_saved_scene_idea_refreshes_writer_when_preview_exists(self):
        app = self.make_scene_idea_reload_app(
            "Saved scene beats.", "Saved scene beats.", confirm=False
        )
        app.writer_scene_idea_text = FakeText("Writer preview")
        app._refresh_writer_scene_guidance = Mock()

        app._reload_saved_scene_idea()

        app._refresh_writer_scene_guidance.assert_called_once_with()
        self.assertEqual(app.scene_idea_text.value, "Saved scene beats.")

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

    def test_pending_draft_is_not_acceptable_after_completion_check_failure(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.writer_engine = SimpleNamespace(
            child=SimpleNamespace(isalive=lambda: True),
            model_path=Path("/tmp/writer.gguf"),
        )
        app.package = object()
        app.generated_scene = "Complete draft awaiting author review."
        app.accepted_scene = ""
        app.pending_state_patch = None
        # This explicit failed-check result, not a generic legacy flag, blocks acceptance.
        app.writer_validation_failed = True
        app.writer_scene_accept_block_reason = (
            "Scene completion check failed (SceneContractValidationUnavailable)."
        )
        app.scene_contract_building = False
        app.__dict__["writer_generation_in_progress"] = False
        app.__dict__["writer_notes_update_in_progress"] = False
        for name in (
            "writer_start_button",
            "writer_stop_button",
            "writer_write_button",
            "writer_accept_button",
            "writer_reject_button",
            "writer_analyze_button",
            "writer_apply_state_button",
            "writer_clear_context_button",
            "writer_status",
        ):
            setattr(app, name, FakeButton())

        app._update_writer_buttons()

        self.assertEqual(app.writer_accept_button.options["state"], "disabled")
        self.assertEqual(app.writer_reject_button.options["state"], "normal")
    def test_draft_without_completion_result_is_preserved_but_not_acceptable(self):
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

        app._show_copyable_error.assert_called_once()
        args, kwargs = app._show_copyable_error.call_args
        self.assertEqual(args[0], "Scene Completion Check")
        self.assertIn("no completion-check result was returned", args[1])
        showwarning.assert_not_called()
        self.assertEqual(app.generated_scene, draft)
        self.assertEqual(app.writer_output_text.value, draft)
        self.assertEqual(app.writer_accept_button.options["state"], "disabled")
        self.assertEqual(app.writer_reject_button.options["state"], "normal")
    def test_failed_completion_check_opens_copyable_report_popup(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        draft = "Draft preserved after the completion check failed."
        notice = (
            "Scene completion check failed (SceneContractValidationUnavailable): validator unavailable\n\n"
            "Diagnostic traceback:\nTraceback (most recent call last):\nRuntimeError: validator unavailable\n\n"
            "The original draft was preserved."
        )
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

        storybuilder_app.StoryBuilderApp._finish_generated_scene(
            app, draft, None, None, notice
        )

        app._show_copyable_error.assert_called_once_with(
            "Scene Completion Check",
            notice,
            summary=(
                "The generated scene remains an unaccepted draft. Its automated completion/"
                "continuity check failed, was skipped, or could not verify the scene. "
                "Select the report below with Ctrl+A and copy it with Ctrl+C when reporting this problem."
            ),
        )
        self.assertEqual(app.generated_scene, draft)
        self.assertIn("Scene completion check failed", app.writer_status.options["text"])
        self.assertNotIn("Diagnostic traceback:", app.writer_status.options["text"])
        self.assertEqual(app.writer_scene_accept_block_reason, notice)

    def test_successful_completion_check_does_not_open_popup(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        draft = "Draft scene after a clean review."
        notice = (
            "AUTOMATED REVIEW: scene-contract validation and the continuity/scope audit reported no issues. "
            "This is a screening result, not a guarantee."
        )
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

        storybuilder_app.StoryBuilderApp._finish_generated_scene(
            app, draft, None, None, notice
        )

        app._show_copyable_error.assert_not_called()
        self.assertEqual(app.generated_scene, draft)
        self.assertIn("AUTOMATED REVIEW:", app.writer_status.options["text"])

    def test_advisory_validator_findings_open_review_without_blocking_acceptance(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        draft = "A complete scene with a possible coverage concern."
        notice = (
            "AUTOMATED REVIEW: 1 possible finding(s) need your review. "
            "No prose was changed automatically."
        )
        finding = {
            "kind": "coverage",
            "title": "Possible omission",
            "message": "The decision point may be missing.",
            "can_suggest": True,
            "edit_request": "Suggest a minimal local fix.",
        }
        context = {
            "model_path": Path("/tmp/writer.gguf"),
            "writer_system_prompt": "writer prompt",
            "contract": {"author_idea": "A scene ends with a decision point."},
            "current_state": {"chapter": 2, "scene": 4},
        }
        app.package = SimpleNamespace(current_state={"chapter": 2, "scene": 4})
        app.generated_scene = ""
        app.accepted_scene = ""
        app.writer_generation_context = (2, 4)
        app.writer_generation_start_state = {"chapter": 2, "scene": 4}
        app.writer_generation_in_progress = True
        app.writer_output_text = FakeText()
        app.writer_status = FakeButton()
        app.writer_revision_request_entry = FakeText()
        app._show_copyable_error = Mock()
        app._update_writer_buttons = Mock()
        app._start_validator_review = Mock()

        storybuilder_app.StoryBuilderApp._finish_generated_scene(
            app, draft, None, None, notice, [finding], context
        )

        self.assertEqual(app.generated_scene, draft)
        self.assertEqual(app.writer_output_text.value, draft)
        self.assertEqual(app.writer_scene_accept_block_reason, "")
        self.assertEqual(app.generated_scene_review_context, context)
        app._start_validator_review.assert_called_once_with([finding], notice, context)
        app._show_copyable_error.assert_not_called()
        app._update_writer_buttons.assert_called_once()

    def test_advisory_validator_findings_open_review_without_blocking_acceptance(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        draft = "A complete scene with a possible coverage concern."
        notice = (
            "AUTOMATED REVIEW: 1 possible finding(s) need your review. "
            "No prose was changed automatically."
        )
        finding = {
            "kind": "coverage",
            "title": "Possible omission",
            "message": "The decision point may be missing.",
            "can_suggest": True,
            "edit_request": "Suggest a minimal local fix.",
        }
        context = {
            "model_path": Path("/tmp/writer.gguf"),
            "writer_system_prompt": "writer prompt",
            "contract": {"author_idea": "A scene ends with a decision point."},
            "current_state": {"chapter": 2, "scene": 4},
        }
        app.package = SimpleNamespace(current_state={"chapter": 2, "scene": 4})
        app.generated_scene = ""
        app.accepted_scene = ""
        app.writer_generation_context = (2, 4)
        app.writer_generation_start_state = {"chapter": 2, "scene": 4}
        app.writer_generation_in_progress = True
        app.writer_output_text = FakeText()
        app.writer_status = FakeButton()
        app.writer_revision_request_entry = FakeText()
        app._show_copyable_error = Mock()
        app._update_writer_buttons = Mock()
        app._start_validator_review = Mock()

        storybuilder_app.StoryBuilderApp._finish_generated_scene(
            app, draft, None, None, notice, [finding], context
        )

        self.assertEqual(app.generated_scene, draft)
        self.assertEqual(app.writer_output_text.value, draft)
        self.assertEqual(app.writer_scene_accept_block_reason, "")
        self.assertEqual(app.generated_scene_review_context, context)
        app._start_validator_review.assert_called_once_with([finding], notice, context)
        app._show_copyable_error.assert_not_called()
        app._update_writer_buttons.assert_called_once()

    @patch.object(storybuilder_app.messagebox, "showinfo")
    def test_accept_handler_waits_until_validator_review_is_finished(self, showinfo):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.validator_review_in_progress = True
        app.writer_scene_accept_block_reason = ""
        storybuilder_app.StoryBuilderApp._accept_generated_scene(app)
        showinfo.assert_called_once()
        self.assertIn("Finish reviewing", showinfo.call_args.args[1])
        self.assertNotIn("package", app.__dict__)

    def test_accept_handler_refuses_draft_after_completion_check_failure(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.writer_scene_accept_block_reason = (
            "Scene completion check failed (SceneContractValidationUnavailable)."
        )
        app._show_copyable_error = Mock()

        storybuilder_app.StoryBuilderApp._accept_generated_scene(app)

        app._show_copyable_error.assert_called_once_with(
            "Scene Not Ready to Accept",
            app.writer_scene_accept_block_reason,
            summary=(
                "StoryBuilder has blocked acceptance because scene generation or its "
                "completion/continuity check did not finish successfully. You can regenerate "
                "the scene, but this version will not be added to the manuscript."
            ),
        )
        self.assertNotIn("package", app.__dict__)

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
        self.assertIn("Scene generation failed", app.writer_scene_accept_block_reason)
        app._update_writer_buttons.assert_called_once_with()

    def test_partial_stream_is_preserved_if_generation_errors(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        partial = "A partial scene that streamed into the Writer box."
        app.package = SimpleNamespace(current_state={"chapter": 2, "scene": 4})
        app.generated_scene = ""
        app.accepted_scene = ""
        app.writer_stream_buffer = partial
        app.writer_generation_context = (2, 4)
        app.writer_generation_start_state = {"chapter": 2, "scene": 4}
        app.writer_generation_in_progress = True
        app.writer_output_text = FakeText(partial)
        app.writer_status = FakeButton()
        app._show_copyable_error = Mock()
        app._update_writer_buttons = Mock()

        app._finish_generated_scene("", "Model generation timed out.")

        self.assertFalse(app.writer_generation_in_progress)
        self.assertEqual(app.generated_scene, partial)
        self.assertEqual(app.writer_output_text.value, partial)
        self.assertIn("remains available for your review", app.writer_status.options["text"])
        app._update_writer_buttons.assert_called_once_with()

    def test_failed_regeneration_restores_previous_draft_when_no_new_text_arrives(self):
        previous = "The previous draft must survive a failed regeneration."
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(current_state={"chapter": 2, "scene": 4})
        app.generated_scene = previous
        app.generated_scene_context = (2, 4)
        app.generated_scene_start_state = {"chapter": 2, "scene": 4}
        app.writer_stream_buffer = ""
        app.writer_generation_context = (2, 4)
        app.writer_generation_start_state = {"chapter": 2, "scene": 4}
        app.writer_generation_in_progress = True
        app.writer_output_text = FakeText("")
        app.writer_status = FakeButton()
        app._show_copyable_error = Mock()
        app._update_writer_buttons = Mock()
        app._has_pending_generated_scene = lambda: bool(app.generated_scene)

        app._finish_generated_scene("", "Model generation timed out.")

        self.assertFalse(app.writer_generation_in_progress)
        self.assertEqual(app.generated_scene, previous)
        self.assertEqual(app.writer_output_text.value, previous)
        self.assertIn(
            "previous draft remains unchanged",
            app.writer_status.options["text"],
        )
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

    def test_close_and_sync_app_failure_uses_copyable_error_dialog_without_novel_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
            app._closing = False
            app.package = SimpleNamespace(path=Path(tmp))
            app.writer_engine = SimpleNamespace(stop=Mock())
            app.dirty = False
            app._confirm_discard_unaccepted_writer_text = Mock(return_value=True)
            app._apply_all_edits = Mock()
            app._ask_yes_no = Mock(return_value=True)
            app._show_copyable_error = Mock()
            app.destroy = Mock()

            with (
                patch.object(
                    storybuilder_app,
                    "sync_storybuilder_repository",
                    side_effect=storybuilder_app.StoryBuilderSyncError("simulated app branch conflict"),
                ),
                patch.object(storybuilder_app, "sync_novel_repository") as sync_novel,
                patch.object(storybuilder_app.messagebox, "showerror") as showerror,
            ):
                storybuilder_app.StoryBuilderApp._close_and_sync_app(app)

            app._show_copyable_error.assert_called_once()
            args, kwargs = app._show_copyable_error.call_args
            self.assertEqual(args[0], "Close & Sync App")
            self.assertIn("simulated app branch conflict", args[1])
            self.assertIn("novel was not saved or synced", args[1])
            self.assertIn("Ctrl+A", kwargs["summary"])
            self.assertFalse(app._closing)
            app.writer_engine.stop.assert_not_called()
            app.destroy.assert_not_called()
            sync_novel.assert_not_called()
            showerror.assert_not_called()

    def test_close_syncs_only_app_and_never_saves_or_syncs_novel(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
            app._closing = False
            package = SimpleNamespace(path=Path(tmp), save=Mock())
            app.package = package
            app.writer_engine = SimpleNamespace(stop=Mock())
            app.dirty = False
            app._confirm_discard_unaccepted_writer_text = Mock(return_value=True)
            app._apply_all_edits = Mock()
            app._ask_yes_no = Mock(return_value=True)
            app._save = Mock()
            app.destroy = Mock()

            with (
                patch.object(
                    storybuilder_app,
                    "sync_storybuilder_repository",
                    return_value="StoryBuilder application synchronized successfully.",
                ) as sync_app,
                patch.object(storybuilder_app, "sync_novel_repository") as sync_novel,
            ):
                storybuilder_app.StoryBuilderApp._close_and_sync_app(app)

            sync_app.assert_called_once_with(Path(storybuilder_app.__file__).resolve().parent)
            sync_novel.assert_not_called()
            package.save.assert_not_called()
            app._save.assert_not_called()
            app.writer_engine.stop.assert_called_once_with()
            app.destroy.assert_called_once_with()

    def test_close_can_be_canceled_to_preserve_unsaved_novel_changes(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app._closing = False
        app.package = SimpleNamespace(path=Path("/tmp/novel"))
        app.writer_engine = SimpleNamespace(stop=Mock())
        app.dirty = True
        app._confirm_discard_unaccepted_writer_text = Mock(return_value=True)
        app._apply_all_edits = Mock()
        app._ask_yes_no = Mock(return_value=False)
        app.destroy = Mock()

        with patch.object(storybuilder_app, "sync_storybuilder_repository") as sync_app:
            storybuilder_app.StoryBuilderApp._close_and_sync_app(app)

        self.assertFalse(app._closing)
        app._ask_yes_no.assert_called_once()
        self.assertIn("will not save or sync the novel", app._ask_yes_no.call_args.args[1])
        app.writer_engine.stop.assert_not_called()
        sync_app.assert_not_called()
        app.destroy.assert_not_called()

    def test_application_error_popups_use_copyable_dialog(self):
        source = Path(storybuilder_app.__file__).read_text(encoding="utf-8")
        self.assertNotIn("messagebox.showerror(", source)

    def test_separate_draft_saving_feature_is_removed(self):
        source = Path(storybuilder_app.__file__).read_text(encoding="utf-8")
        self.assertNotIn("writer_save_draft_button", source)
        self.assertNotIn("def _save_generated_draft", source)
        self.assertNotIn("_save_unsaved_writer_draft", source)
        self.assertNotIn("ManuscriptManager(self.package.path).save_draft", source)
        manuscript_source = (
            Path(storybuilder_app.__file__).parent / "builder" / "manuscript.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("def save_draft", manuscript_source)
        self.assertIn("def _confirm_discard_unaccepted_writer_text", source)

    def test_scene_validator_popup_exposes_full_draft_in_selectable_tab(self):
        FakePopupWidget.instances.clear()
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        draft = "First paragraph.\n\nSecond paragraph with the complete scene ending."
        app.generated_scene = "stale fallback draft"
        app.writer_output_text = FakeText(draft)
        app._add_context_menu = Mock()
        app.validator_review_in_progress = True
        app.validator_review_state = {
            "queue": [{
                "kind": "coverage",
                "title": "Possible omission",
                "message": "The team decision may be missing.",
                "can_suggest": False,
            }],
            "skipped": [],
            "dismissed": [],
            "applied": [],
            "context": {},
            "notice": "Review",
            "reviewed_count": 0,
            "current": None,
        }

        with (
            patch.object(storybuilder_app.tk, "Toplevel", FakePopupWidget),
            patch.object(storybuilder_app.tk, "Text", FakePopupWidget),
            patch.object(storybuilder_app.ttk, "Frame", FakePopupWidget),
            patch.object(storybuilder_app.ttk, "Label", FakePopupWidget),
            patch.object(storybuilder_app.ttk, "Button", FakePopupWidget),
            patch.object(storybuilder_app.ttk, "Notebook", FakePopupWidget),
            patch.object(storybuilder_app.ttk, "Scrollbar", FakePopupWidget),
        ):
            storybuilder_app.StoryBuilderApp._show_next_validator_finding(app)

        draft_text = app.validator_review_dialog_state["draft_text"]
        self.assertIn(
            draft,
            "\n".join(str(part) for insertion in draft_text.insertions for part in insertion),
        )
        app._add_context_menu.assert_any_call(draft_text)
        self.assertFalse(any(
            widget.kwargs.get("text") == "Copy Draft Prose"
            for widget in FakePopupWidget.instances
        ))
        self.assertIsNotNone(app.validator_review_dialog)
        self.assertTrue(app.validator_review_in_progress)

    def test_error_dialog_text_is_selectable_without_a_copy_button(self):
        FakePopupWidget.instances.clear()
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)

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

        text_widget = next(
            widget for widget in FakePopupWidget.instances
            if widget.kwargs.get("width") == 76
        )
        self.assertIn("<Control-a>", text_widget.bindings)
        self.assertIn("<Control-c>", text_widget.bindings)
        labels = [widget.kwargs.get("text") for widget in FakePopupWidget.instances]
        self.assertNotIn("Copy Full Error", labels)

    def test_unaccepted_writer_text_is_discarded_without_creating_a_draft_file    def test_unaccepted_writer_text_is_discarded_without_creating_a_draft_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.make_app(tmp, "Temporary scene text", context=(2, 1))
            app.writer_status = FakeButton()
            app._update_writer_buttons = Mock()
            with patch.object(
                storybuilder_app.messagebox, "askyesnocancel", return_value=True
            ) as ask:
                self.assertTrue(app._confirm_discard_unaccepted_writer_text())

            draft = (
                Path(tmp)
                / "Manuscript"
                / "Chapters"
                / "Chapter_02"
                / "Chapter_02_Section_01_draft.txt"
            )
            self.assertFalse(draft.exists())
            self.assertFalse((Path(tmp) / "Manuscript").exists())
            self.assertEqual(app.generated_scene, "")
            self.assertEqual(app.writer_output_text.value, "")
            self.assertIsNone(app.generated_scene_context)
            self.assertIsNone(app.generated_scene_start_state)
            self.assertIn("Unaccepted scene text discarded", app.writer_status.options["text"])
            ask.assert_called_once()
            self.assertIn("Choose Yes to discard", ask.call_args.args[1])
            self.assertIn("Choose No or Cancel to stay", ask.call_args.args[1])
            app._update_writer_buttons.assert_called_once()

    def test_canceling_unaccepted_text_keeps_it_visible_without_saving(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.make_app(tmp, "Keep this text on screen", context=(2, 1))
            app._update_writer_buttons = Mock()
            with patch.object(
                storybuilder_app.messagebox, "askyesnocancel", return_value=None
            ) as ask:
                self.assertFalse(app._confirm_discard_unaccepted_writer_text())

            self.assertEqual(app.generated_scene, "Keep this text on screen")
            self.assertEqual(app.writer_output_text.value, "Keep this text on screen")
            self.assertFalse((Path(tmp) / "Manuscript").exists())
            ask.assert_called_once()
            app._update_writer_buttons.assert_not_called()

    def test_unchanged_accepted_text_needs_no_discard_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.make_app(
                tmp, "Already accepted prose", context=(2, 1), accepted="Already accepted prose"
            )
            app._update_writer_buttons = Mock()
            with patch.object(
                storybuilder_app.messagebox, "askyesnocancel"
            ) as ask:
                self.assertTrue(app._confirm_discard_unaccepted_writer_text())
            ask.assert_not_called()
            self.assertEqual(app.writer_output_text.value, "Already accepted prose")
            self.assertFalse((Path(tmp) / "Manuscript").exists())

    def test_scene_contract_and_writer_are_separate_primary_tabs(self):
        source = inspect.getsource(storybuilder_app.StoryBuilderApp._build_ui)

        contract_call = source.index("self._build_scene_contract_tab()")
        writer_call = source.index("self._build_writer_tab()")
        chat_call = source.index("self._build_chat_tab()")

        self.assertLess(contract_call, writer_call)
        self.assertLess(writer_call, chat_call)
        self.assertNotIn("_build_write_workspace()", source)

    def test_scene_plan_details_are_visible_when_workspace_opens(self):
        source = inspect.getsource(storybuilder_app.StoryBuilderApp._build_scene_contract_tab)
        self.assertIn('text="Hide Scene Details ▾"', source)
        self.assertNotIn("self.scene_contract_details_frame.pack_forget()", source)

    def test_scene_details_toggle_shows_and_hides_optional_contract_fields(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)

        class FakeDetailsFrame:
            def __init__(self):
                self.manager = ""
                self.pack_options = None
                self.pack_forget_calls = 0

            def winfo_manager(self):
                return self.manager

            def pack(self, **kwargs):
                self.manager = "pack"
                self.pack_options = kwargs

            def pack_forget(self):
                self.manager = ""
                self.pack_forget_calls += 1

        frame = FakeDetailsFrame()
        action_row = object()
        toggle = FakeButton()
        app.scene_contract_details_frame = frame
        app.scene_contract_action_row = action_row
        app.scene_contract_details_toggle_button = toggle

        storybuilder_app.StoryBuilderApp._toggle_scene_details(app)
        self.assertEqual(frame.manager, "pack")
        self.assertIs(frame.pack_options["before"], action_row)
        self.assertEqual(toggle.options["text"], "Scene Details ▾")

        storybuilder_app.StoryBuilderApp._toggle_scene_details(app)
        self.assertEqual(frame.manager, "")
        self.assertEqual(frame.pack_forget_calls, 1)
        self.assertEqual(toggle.options["text"], "Scene Details ▸")

    def test_window_close_syncs_app_and_has_no_close_and_sync_novel_button(self):
        source = Path(storybuilder_app.__file__).read_text(encoding="utf-8")
        self.assertIn(
            'self.protocol("WM_DELETE_WINDOW", self._close_and_sync_app)',
            source,
        )
        self.assertIn('text="Close & Sync App"', source)
        self.assertIn('text="Sync Novel"', source)
        self.assertNotIn('text="Close & Sync Novel"', source)
        self.assertNotIn('self._close_without_sync', source)
        self.assertNotIn('self._close_and_sync(', source)

    def test_close_cancel_keeps_storybuilder_open_without_saving_or_syncing(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app._closing = False
        app.package = SimpleNamespace(path=Path("/tmp/novel"))
        app.writer_engine = SimpleNamespace(stop=Mock())
        app.dirty = False
        app._confirm_discard_unaccepted_writer_text = Mock(return_value=False)
        app._apply_all_edits = Mock()
        app._ask_yes_no = Mock(return_value=True)
        app._save = Mock()
        app.destroy = Mock()

        with patch.object(storybuilder_app, "sync_storybuilder_repository") as sync_app:
            storybuilder_app.StoryBuilderApp._close_and_sync_app(app)

        self.assertFalse(app._closing)
        app.writer_engine.stop.assert_not_called()
        app._save.assert_not_called()
        app._apply_all_edits.assert_not_called()
        sync_app.assert_not_called()
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
            app._confirm_discard_unaccepted_writer_text = lambda: True
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
            app._confirm_discard_unaccepted_writer_text = lambda: True
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
            app._confirm_discard_unaccepted_writer_text = lambda: True
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
            app._scene_end_guidance = lambda *_args: self.fail(
                "Post-scene analysis must not calculate or pass Scene End Guidance."
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
            self.assertNotIn("scene_end_guidance", propose.call_args.kwargs)
            self.assertEqual(propose.call_args.args[2], app.accepted_scene)
            self.assertEqual(app.pending_state_patch, analysis_patch)
            self.assertNotIn("PLANNED BUT NOT PROVEN", app.writer_state_preview.get("1.0", "end"))

    def test_quick_state_edits_update_plain_preview_without_editing_json(self):
        before = {
            "chapter": 1,
            "scene": 4,
            "status": "in_progress",
            "scene_completed": False,
            "chapter_completed": False,
            "current_situation": "The manifold temperature is rising.",
            "character_knowledge": {
                "Daniel": [
                    "The manifold temperature continues to rise."
                ]
            },
            "active_objectives": {
                "Daniel": "Track the manifold temperature.",
                "Zoe": "Monitor communications independently.",
            },
        }
        expected = json.loads(json.dumps(before))
        expected["current_situation"] = "Proposed short summary."
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(current_state=before)
        app.pending_state_patch = {"current_situation": "Proposed short summary."}
        app.writer_state_preview = FakeText(json.dumps(expected))
        app.writer_state_situation_quick = FakeText(
            "Pressure remains stable; the trace is unverified and the cause remains unknown."
        )

        class FakeCharacterSelector:
            def get(self):
                return "Daniel"

        app.writer_state_character_selector = FakeCharacterSelector()
        app.writer_state_knowledge_quick = FakeText(
            "The manifold temperature continues to rise.\n"
            "The silicate-like trace is not proof of contamination or its source."
        )
        app.writer_state_objective_quick = FakeText(
            "Track the temperature trend and estimate the remaining operating margin."
        )
        app._quick_edit_state = json.loads(json.dumps(expected))
        app.writer_state_diff_preview = FakeText()
        app.writer_status = SimpleLabel()
        app._update_writer_buttons = lambda: None

        storybuilder_app.StoryBuilderApp._apply_quick_state_edits_to_preview(app)

        preview = json.loads(app.writer_state_preview.get("1.0", "end"))
        self.assertIn("trace is unverified", preview["current_situation"])
        self.assertEqual(
            preview["character_knowledge"]["Daniel"],
            [
                "The manifold temperature continues to rise.",
                "The silicate-like trace is not proof of contamination or its source.",
            ],
        )
        self.assertEqual(
            preview["active_objectives"]["Daniel"],
            "Track the temperature trend and estimate the remaining operating margin.",
        )
        self.assertEqual(
            preview["active_objectives"]["Zoe"],
            "Monitor communications independently.",
        )
        self.assertEqual(app.package.current_state, before)
        self.assertIn("proposed changes", app.writer_status.text.casefold())
        self.assertIn("apply state update", app.writer_status.text.casefold())
        self.assertNotIn("json", app.writer_status.text.casefold())

    def test_quick_state_character_switch_preserves_each_characters_own_data(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app._quick_edit_state = {
            "character_knowledge": {
                "Daniel": ["Daniel knows the manifold is heating."],
                "Zoe": ["Zoe sees unexplained communications bursts."],
            },
            "active_objectives": {
                "Daniel": "Monitor the manifold temperature.",
                "Zoe": "Analyze the communications bursts.",
            },
            "location": {
                "Daniel": "near the environmental hub",
                "Zoe": "at the comms console",
            },
            "physical_state": {
                "Daniel": {
                    "location": "near the environmental hub",
                    "position": "checking the tablet",
                    "posture": "focused",
                    "movement": "stationary",
                },
                "Zoe": {
                    "location": "at the comms console",
                    "position": "examining burst timings",
                    "posture": "analytical",
                    "movement": "stationary",
                },
            },
        }

        class FakeCharacterSelector:
            def get(self):
                # Tk has already changed this to Zoe when the selection event fires.
                return "Zoe"

        app.writer_state_character_selector = FakeCharacterSelector()
        app.writer_state_knowledge_quick = FakeText(
            "Daniel knows the manifold is heating.\n"
            "Daniel's spectral trace remains unverified."
        )
        app.writer_state_objective_quick = FakeText(
            "Track the temperature trend and report changes."
        )
        app.writer_state_location_quick = FakeText("at the maintenance hatch")
        app.writer_state_position_quick = FakeText("beginning chamber pressurization")
        app.writer_state_posture_quick = FakeText("focused")
        app.writer_state_movement_quick = FakeText("working the controls")
        app._quick_edit_loaded_character = "Daniel"

        storybuilder_app.StoryBuilderApp._on_quick_state_character_selected(app)

        self.assertEqual(
            app._quick_edit_state["character_knowledge"]["Daniel"],
            [
                "Daniel knows the manifold is heating.",
                "Daniel's spectral trace remains unverified.",
            ],
        )
        self.assertEqual(
            app._quick_edit_state["character_knowledge"]["Zoe"],
            ["Zoe sees unexplained communications bursts."],
        )
        self.assertEqual(
            app._quick_edit_state["active_objectives"]["Daniel"],
            "Track the temperature trend and report changes.",
        )
        self.assertEqual(
            app._quick_edit_state["active_objectives"]["Zoe"],
            "Analyze the communications bursts.",
        )
        self.assertEqual(
            app.writer_state_knowledge_quick.value,
            "Zoe sees unexplained communications bursts.",
        )
        self.assertEqual(
            app.writer_state_objective_quick.value,
            "Analyze the communications bursts.",
        )
        self.assertEqual(app.writer_state_location_quick.value, "at the comms console")
        self.assertEqual(app.writer_state_position_quick.value, "examining burst timings")
        self.assertEqual(
            app._quick_edit_state["location"]["Daniel"],
            "at the maintenance hatch",
        )
        self.assertEqual(
            app._quick_edit_state["location"]["Zoe"],
            "at the comms console",
        )
        self.assertEqual(
            app._quick_edit_state["physical_state"]["Daniel"]["position"],
            "beginning chamber pressurization",
        )
        self.assertEqual(
            app._quick_edit_state["physical_state"]["Zoe"]["position"],
            "examining burst timings",
        )
        self.assertEqual(app._quick_edit_loaded_character, "Zoe")

    def test_quick_state_edits_update_location_and_physical_state_in_preview(self):
        before = {
            "chapter": 1,
            "scene": 4,
            "status": "in_progress",
            "scene_completed": False,
            "chapter_completed": False,
            "current_situation": "The crew is responding to the scrubber anomaly.",
            "location": {
                "primary": "Mars research outpost communal mess area",
                "Daniel": "near the environmental hub",
            },
            "physical_state": {
                "Daniel": {
                    "location": "near the environmental hub",
                    "position": "checking the temperature tablet",
                    "posture": "focused",
                    "movement": "stationary",
                }
            },
            "character_knowledge": {
                "Daniel": ["The manifold temperature is rising."]
            },
            "active_objectives": {
                "Daniel": "Monitor the manifold temperature."
            },
        }
        expected = json.loads(json.dumps(before))
        expected["current_situation"] = "The crew is checking the scrubber housing."
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(current_state=before)
        app.pending_state_patch = {
            "current_situation": expected["current_situation"]
        }
        app.writer_state_preview = FakeText(json.dumps(expected))
        app.writer_state_situation_quick = FakeText(expected["current_situation"])

        class FakeCharacterSelector:
            def get(self):
                return "Daniel"

        app.writer_state_character_selector = FakeCharacterSelector()
        app.writer_state_location_quick = FakeText("at the sealed maintenance hatch")
        app.writer_state_position_quick = FakeText("beginning partial chamber pressurization")
        app.writer_state_posture_quick = FakeText("firm and alert")
        app.writer_state_movement_quick = FakeText("operating the pressurization controls")
        app.writer_state_knowledge_quick = FakeText(
            "The manifold temperature is rising."
        )
        app.writer_state_objective_quick = FakeText(
            "Continue monitoring the manifold temperature."
        )
        app._quick_edit_state = json.loads(json.dumps(expected))
        app.writer_state_diff_preview = FakeText()
        app.writer_status = SimpleLabel()
        app._update_writer_buttons = lambda: None

        storybuilder_app.StoryBuilderApp._apply_quick_state_edits_to_preview(app)

        preview = json.loads(app.writer_state_preview.get("1.0", "end"))
        self.assertEqual(
            preview["location"]["Daniel"],
            "at the sealed maintenance hatch",
        )
        self.assertEqual(
            preview["physical_state"]["Daniel"]["location"],
            "at the sealed maintenance hatch",
        )
        self.assertEqual(
            preview["physical_state"]["Daniel"]["position"],
            "beginning partial chamber pressurization",
        )
        self.assertEqual(
            preview["physical_state"]["Daniel"]["posture"],
            "firm and alert",
        )
        self.assertEqual(
            preview["physical_state"]["Daniel"]["movement"],
            "operating the pressurization controls",
        )
        self.assertIn("at the sealed maintenance hatch", app.writer_state_diff_preview.value)
        self.assertEqual(app.package.current_state, before)

    def test_refresh_state_review_from_json_rebuilds_change_list(self):
        before = {
            "chapter": 1,
            "scene": 4,
            "status": "in_progress",
            "scene_completed": False,
            "chapter_completed": False,
            "current_situation": "The original situation.",
            "location": {
                "primary": "Mars research outpost communal mess area",
                "Daniel": "near the environmental hub",
            },
            "physical_state": {
                "Daniel": {
                    "location": "near the environmental hub",
                    "position": "checking the tablet",
                }
            },
        }
        candidate = json.loads(json.dumps(before))
        candidate["current_situation"] = "The proposed situation."
        candidate["location"]["Daniel"] = "at the sealed maintenance hatch"
        candidate["physical_state"]["Daniel"]["location"] = "at the sealed maintenance hatch"
        candidate["physical_state"]["Daniel"]["position"] = "beginning partial pressurization"
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(current_state=before)
        app.pending_state_patch = {"current_situation": "The proposed situation."}
        app.writer_state_preview = FakeText(json.dumps(candidate))
        app.writer_state_diff_preview = FakeText()
        app.writer_status = SimpleLabel()
        app._update_writer_buttons = lambda: None

        storybuilder_app.StoryBuilderApp._refresh_state_review_from_json(app)

        self.assertIn("sealed maintenance hatch", app.writer_state_diff_preview.value)
        self.assertIn("beginning partial pressurization", app.writer_state_diff_preview.value)
        self.assertEqual(
            app._writer_state_reviewed_preview,
            json.dumps(candidate, sort_keys=True, ensure_ascii=False),
        )
        self.assertEqual(app.package.current_state, before)
        self.assertIn("Nothing has been applied", app.writer_status.text)

    def test_apply_state_update_blocks_unreviewed_advanced_json_changes(self):
        before = {
            "chapter": 1,
            "scene": 4,
            "status": "in_progress",
            "scene_completed": False,
            "chapter_completed": False,
            "current_situation": "The original situation.",
        }
        original_preview = json.loads(json.dumps(before))
        original_preview["current_situation"] = "The proposed situation."
        edited_preview = json.loads(json.dumps(original_preview))
        edited_preview["location"] = {
            "primary": "Mars mess area",
            "Daniel": "at the maintenance hatch",
        }
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(current_state=before)
        app.pending_state_patch = {"current_situation": "The proposed situation."}
        app.writer_state_preview = FakeText(json.dumps(edited_preview))
        app.writer_status = SimpleLabel()
        app._writer_state_reviewed_preview = json.dumps(
            original_preview, sort_keys=True, ensure_ascii=False
        )
        app._update_writer_buttons = lambda: None

        with patch.object(storybuilder_app.messagebox, "showwarning") as warning:
            storybuilder_app.StoryBuilderApp._apply_state_update(app)

        warning.assert_called_once()
        self.assertEqual(app.package.current_state, before)
        self.assertIn("Nothing has been applied", warning.call_args.args[1])
        self.assertIn("Analyze the accepted scene again", warning.call_args.args[1])
        self.assertNotIn("JSON", warning.call_args.args[1])

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
        self.assertIn("Preserve the direction of agency and emotional causality in each beat", prompt)
        self.assertIn("Separate observation, theory, and confirmation.", prompt)
        self.assertIn("Respect explicit boundaries", prompt)
        self.assertIn("The Scene Idea also contains the author's deliberate story commitments.", prompt)
        self.assertIn("quoted lines or nicknames, relationship milestones", prompt)
        self.assertIn("Every concrete story commitment named in the original Scene Idea must happen on-page", prompt)
        self.assertIn("Take creative initiative in present-scene action", prompt)
        self.assertIn(
            "Do not invent consequential past events, promises, encounters, motives, or relationship-defining moments as established fact",
            prompt,
        )
        self.assertNotIn("maintenance event, log result, prior encounter,", prompt)
        self.assertIn("Do not use invented off-page people or actions to explain events without author support.", prompt)
        self.assertIn("Keep theories tentative unless the story's evidence and the Scene Idea establish them.", prompt)
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
        self.assertIn("original idea and saved story state", prompt)
        self.assertIn("canon, character knowledge", prompt)
        self.assertIn("concrete planned beats and their agency", prompt)
        self.assertIn("explicit boundaries", prompt)
        self.assertIn("intended endpoint", prompt)
        self.assertIn("Use creative judgment for dialogue, emotional progression, pacing, atmosphere, and connective action.", prompt)
        self.assertIn("Do not invent unsupported past facts or concrete clues forbidden by the author.", prompt)
        self.assertIn("Do not stop early or cross a stated hard stop.", prompt)
        self.assertIn("Output only the prose.", prompt)
        self.assertNotIn("A friend may suggest", prompt)
        self.assertNotIn("Preserve who initiates, gives or receives comfort", prompt)
        self.assertLess(len(prompt), 1100)

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

        self.assertIn("Check opening continuity", scene_contract.VALIDATOR_SYSTEM_PROMPT)
        self.assertIn("character knowledge", scene_contract.VALIDATOR_SYSTEM_PROMPT)
        self.assertIn("sitting upright against the headboard", captured["prompt"])
        self.assertIn("established relationship facts", scene_contract.VALIDATOR_SYSTEM_PROMPT)
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
        app._confirm_discard_unaccepted_writer_text = lambda: True
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
        app._confirm_discard_unaccepted_writer_text = lambda: True
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
                        stdout="On branch main\nnothing to commit, working tree clean",
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
        self.assertEqual(app.writer_direction_text.state, "disabled")
        app.writer_status.configure.assert_not_called()

    def test_writer_direction_uses_saved_contract_hard_stop_when_end_condition_missing(self):
        idea = "Tony offers Maya a bubble bath and later makes tea."
        app = self.make_writer_scene_idea_app(idea)
        entry = (
            app.package.extra_json["writing_guidance.json"]["chapter_plans"]["2"]
            ["scene_plan"]["4"]
        )
        entry.pop("end_condition")
        entry["scene_contract"]["hard_stop"] = "End after they sit together at the kitchen table."
        app.writer_status = Mock()

        storybuilder_app.StoryBuilderApp._build_scene_direction(app, update_status=False)

        self.assertIn(
            "End: End after they sit together at the kitchen table.",
            app.writer_direction_text.value,
        )

    def test_contract_prompt_treats_stated_scene_outcome_as_endpoint(self):
        self.assertIn(
            "make that stated outcome the stopping point",
            CONTRACT_BUILDER_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Leave hard_stop empty only when the idea gives no defensible outcome",
            CONTRACT_BUILDER_SYSTEM_PROMPT,
        )

    def test_separate_tabs_keep_one_primary_scene_preparation_button(self):
        contract_source = inspect.getsource(
            storybuilder_app.StoryBuilderApp._build_scene_contract_tab
        )
        writer_source = inspect.getsource(
            storybuilder_app.StoryBuilderApp._build_writer_tab
        )

        self.assertIn('text="Prepare Scene..."', contract_source)
        self.assertNotIn('text="Generate / Replace Contract..."', contract_source)
        self.assertNotIn('text="Build Scene Direction"', writer_source)

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
