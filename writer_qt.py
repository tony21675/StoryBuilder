from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QCloseEvent, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout,
    QWidget, QGroupBox, QFormLayout, QInputDialog, QTabWidget, QLineEdit
)

from builder.qt_theme import apply_qt_theme
from builder.workspace import MODELS_DIR, NOVEL_ROOT
from builder.writer_engine import WriterEngine, GenerationInterrupted
from builder.openrouter import (
    RoutedWriterEngine, has_openrouter_api_key, load_cached_openrouter_models,
    is_openrouter_selection, openrouter_model_selection, fetch_openrouter_free_models,
    load_openrouter_api_key, save_openrouter_api_key, delete_openrouter_api_key,
    save_cached_openrouter_models,
)
from builder.model_preferences import load_model_roles, resolve_model_roles, save_model_roles
from builder.novel_browser import list_novel_packages, list_scene_chapters, list_scene_files
from builder.scene_preparation import build_scene_preparation_prompt, apply_author_required_beats, scene_number_from_label, resolve_scene_preparation_target
from builder.story_bible_reader import load_story_bible
from builder.character_context import (
    load_character_card_names, build_character_card_context_prompt,
    build_scene_cast_boundary_prompt, build_story_bible_reference_context
)
from builder.creative_direction import build_creative_direction_prompt
from builder.continuity_context import select_relevant_locations
from builder.writer_continuity import build_previous_scene_context_prompt
from builder.scene_handoff import (\n    build_handoff_extraction_prompt, parse_handoff_response, save_scene_handoff,\n)\nfrom builder.odt_document import read_document, save_document
from builder.manuscript_assembly import assemble_chapter as assemble_chapter_document, assemble_finished_novel as assemble_finished_novel_document
from builder.prompt_trace import PromptTrace, load_prompt_trace_enabled
from builder.prompt_trace_sync import upload_prompt_trace
from builder.prose_health import analyze_draft, format_draft_health_report
from builder.scene_state_update import (
    load_current_state, advance_saved_scene_markers, write_current_state,
    build_saved_scene_state_prompt, parse_saved_scene_state_patch,
    merge_saved_scene_state,
)
from builder.novel_git_sync import inspect_novel_repository, sync_novel_repository, NovelGitSyncError
from minimal_writer import (
    load_model_for_writing, write_from_prompt, build_author_required_direction_prompt,
    build_single_scene_scope_prompt, build_rewrite_scene_prompt, build_continue_prompt,
    build_revision_prompt, build_location_context_prompt,
    resolve_generation_scene_destination,
)


class TaskWorker(QThread):
    chunk = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)
    interrupted = Signal()

    def __init__(self, task: Callable, *, streaming: bool = False):
        super().__init__()
        self.task = task
        self.streaming = streaming

    def run(self):
        try:
            result = self.task(self.chunk.emit if self.streaming else None)
        except GenerationInterrupted:
            self.interrupted.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)


class SceneCastDialog(QDialog):
    def __init__(self, names: list[str], selected: list[str] | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Scene Cast")
        self.resize(430, 520)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select the characters allowed to participate in this scene."))
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        chosen = set(selected or [])
        for name in names:
            item = QListWidgetItem(name)
            self.list_widget.addItem(item)
            if name in chosen:
                item.setSelected(True)
        layout.addWidget(self.list_widget)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_names(self) -> list[str]:
        return [item.text() for item in self.list_widget.selectedItems()]




class RevisionRequestDialog(QDialog):
    """Collect either AI revision instructions or exact replacement wording."""

    def __init__(self, selected_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Revise Selected Passage")
        self.resize(760, 620)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Selected passage (the source remains unchanged until you approve a revision):"))
        self.source_editor = QPlainTextEdit()
        self.source_editor.setPlainText(selected_text)
        self.source_editor.setReadOnly(True)
        self.source_editor.setMaximumHeight(130)
        layout.addWidget(self.source_editor)

        self.tabs = QTabWidget()
        ai_panel = QWidget()
        ai_layout = QVBoxLayout(ai_panel)
        ai_layout.addWidget(QLabel("Describe the changes you want. The AI will revise only this passage."))
        self.instruction_editor = QPlainTextEdit()
        self.instruction_editor.setPlaceholderText("Describe the revision...")
        ai_layout.addWidget(self.instruction_editor, 1)
        replace_panel = QWidget()
        replace_layout = QVBoxLayout(replace_panel)
        replace_layout.addWidget(QLabel("Enter exact replacement text. Leave it empty to delete the selected passage."))
        self.replacement_editor = QPlainTextEdit()
        # Match the original Writer: exact replacement starts blank, and blank means delete.
        replace_layout.addWidget(self.replacement_editor, 1)
        self.tabs.addTab(ai_panel, "Revise with AI")
        self.tabs.addTab(replace_panel, "Replace with Exact Text")
        layout.addWidget(self.tabs, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Preview")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def use_ai(self) -> bool:
        return self.tabs.currentIndex() == 0

    def instruction(self) -> str:
        return self.instruction_editor.toPlainText().strip()

    def replacement(self) -> str:
        return self.replacement_editor.toPlainText()


class RevisionReviewDialog(QDialog):
    """Let the author edit and approve a proposed replacement before insertion."""

    def __init__(self, original: str, proposed: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review Passage Change")
        self.resize(820, 680)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Original passage"))
        self.original_editor = QPlainTextEdit()
        self.original_editor.setPlainText(original)
        self.original_editor.setReadOnly(True)
        self.original_editor.setMaximumHeight(160)
        layout.addWidget(self.original_editor)
        layout.addWidget(QLabel("Proposed replacement (make any final edits before applying)"))
        self.proposal_editor = QPlainTextEdit()
        self.proposal_editor.setPlainText(proposed)
        layout.addWidget(self.proposal_editor, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Use Revision")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def proposed_text(self) -> str:
        return self.proposal_editor.toPlainText()


class DraftReportDialog(QDialog):
    """Show advisory findings in a selectable, copyable, scrollable viewer."""

    def __init__(self, report: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Draft Check")
        self.resize(760, 580)
        layout = QVBoxLayout(self)
        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(report)
        layout.addWidget(editor, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

class WriterQtWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("StoryBuilder Writer · PySide6")
        self.resize(1280, 900)
        self.setMinimumSize(850, 650)

        self.engine = RoutedWriterEngine()
        self.models: dict[str, Path | str] = {}
        self.loaded_model: Path | str | None = None
        self.novel_packages: dict[str, Path] = {}
        self.chapter_numbers: dict[str, int] = {}
        self.scene_files: dict[str, Path] = {}
        self.scene_cast: list[str] | None = None
        self.scene_cast_novel: Path | None = None
        self.scene_cast_destination: tuple[int, int] | None = None
        self.prepared_destination: tuple[int, int] | None = None
        self.prepared_novel: Path | None = None
        self.prepared_source: Path | None = None
        self.selected_scene_source: Path | None = None
        self.current_file: Path | None = None
        self.saved_text = ""
        self.busy = False
        self.worker: TaskWorker | None = None
        self._streamed = False
        self._pending_scene_prompt_trace = None
        self._active_scene_preparation_trace = None
        self._prepared_author_required_direction = ""
        self._scene_preparation_original_prompt = ""
        self._scene_preparation_original_author_direction = ""
        self._scene_preparation_required_author_direction = ""
        self._last_prompt_trace_path = None
        self._last_prompt_trace_upload_result = None
        self._revision_document = ""
        self._revision_start = 0
        self._revision_end = 0
        self._revision_original = ""
        self._saved_scene_state_target = None

        self._build_ui()
        self.refresh_models()
        self.refresh_novels()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        page = QVBoxLayout(central)
        page.setContentsMargins(12, 12, 12, 8)
        page.setSpacing(8)

        model_group = QGroupBox("Models")
        model_form = QFormLayout(model_group)
        self.planner_picker = QComboBox()
        self.writer_picker = QComboBox()
        self.refresh_models_button = QPushButton("Refresh Models")
        self.load_writer_button = QPushButton("Load Writer")
        self.openrouter_settings_button = QPushButton("OpenRouter Settings")
        self.model_status = QLabel("Only the model needed for the selected task is loaded.")
        model_form.addRow("Prepare Scene model", self.planner_picker)
        writer_row = QHBoxLayout()
        writer_row.addWidget(self.writer_picker, 1)
        writer_row.addWidget(self.refresh_models_button)
        writer_row.addWidget(self.openrouter_settings_button)
        writer_row.addWidget(self.load_writer_button)
        writer_widget = QWidget()
        writer_widget.setLayout(writer_row)
        model_form.addRow("Writing model", writer_widget)
        model_form.addRow("Runtime", self.model_status)
        page.addWidget(model_group)

        project_group = QGroupBox("Novel and scene")
        project_row = QHBoxLayout(project_group)
        self.novel_picker = QComboBox()
        self.chapter_picker = QComboBox()
        self.scene_picker = QComboBox()
        self.refresh_novels_button = QPushButton("Refresh Novels")
        self.sync_novel_button = QPushButton("Sync Novel to GitHub")
        self.load_scene_button = QPushButton("Load Scene Copy")
        project_row.addWidget(QLabel("Novel"))
        project_row.addWidget(self.novel_picker, 2)
        project_row.addWidget(self.refresh_novels_button)
        project_row.addWidget(self.sync_novel_button)
        project_row.addWidget(QLabel("Chapter"))
        project_row.addWidget(self.chapter_picker)
        project_row.addWidget(QLabel("Scene"))
        project_row.addWidget(self.scene_picker)
        project_row.addWidget(self.load_scene_button)
        page.addWidget(project_group)

        self.cast_button = QPushButton("Select Scene Cast")
        self.cast_summary = QLabel("No scene cast selected.")
        self.cast_summary.setWordWrap(True)
        cast_row = QHBoxLayout()
        cast_row.addWidget(self.cast_button)
        cast_row.addWidget(self.cast_summary, 1)
        cast_widget = QWidget()
        cast_widget.setLayout(cast_row)
        page.addWidget(cast_widget)

        prompt_split = QSplitter()
        prompt_panel = QWidget()
        prompt_layout = QVBoxLayout(prompt_panel)
        prompt_layout.setContentsMargins(0, 0, 0, 0)
        prompt_layout.addWidget(QLabel("Author's Direction (optional)"))
        self.author_direction = QPlainTextEdit()
        self.author_direction.setPlaceholderText("Your required events and instructions. These are preserved in the prepared beats.")
        self.author_direction.setMaximumHeight(115)
        prompt_layout.addWidget(self.author_direction)
        prompt_header = QHBoxLayout()
        prompt_header.addWidget(QLabel("What should it write?"), 1)
        self.prepare_button = QPushButton("Prepare Scene")
        prompt_header.addWidget(self.prepare_button)
        prompt_layout.addLayout(prompt_header)
        self.prompt_editor = QPlainTextEdit()
        self.prompt_editor.setPlaceholderText("Prepare a scene with the Planner or write your own direction.")
        prompt_layout.addWidget(self.prompt_editor, 1)
        output_panel = QWidget()
        output_layout = QVBoxLayout(output_panel)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_header = QHBoxLayout()
        output_header.addWidget(QLabel("Output (editable manuscript)"), 1)
        self.revise_button = QPushButton("Revise Selection")
        self.check_draft_button = QPushButton("Check Draft")
        output_header.addWidget(self.check_draft_button)
        output_header.addWidget(self.revise_button)
        output_layout.addLayout(output_header)
        self.output_editor = QPlainTextEdit()
        self.output_editor.setPlaceholderText("Generated prose appears here. You can edit it before saving.")
        output_layout.addWidget(self.output_editor, 1)
        prompt_split.addWidget(prompt_panel)
        prompt_split.addWidget(output_panel)
        prompt_split.setSizes([560, 700])
        page.addWidget(prompt_split, 1)

        controls = QHBoxLayout()
        self.write_button = QPushButton("Write (Balanced)")
        self.minimal_button = QPushButton("Test Minimal Prompt")
        self.full_button = QPushButton("Write Full Context")
        self.rewrite_button = QPushButton("Rewrite Scene")
        self.continue_button = QPushButton("Continue")
        self.stop_button = QPushButton("Stop")
        self.new_session_button = QPushButton("New Session")
        for button in (self.write_button, self.minimal_button, self.full_button, self.rewrite_button, self.continue_button, self.stop_button, self.new_session_button):
            controls.addWidget(button)
        page.addLayout(controls)

        file_controls = QHBoxLayout()
        self.open_button = QPushButton("Open Text / ODT")
        self.save_button = QPushButton("Save Draft")
        self.save_as_button = QPushButton("Save Draft As")
        self.save_new_scene_button = QPushButton("Save New Scene")
        self.save_scene_button = QPushButton("Save to Selected Scene")
        self.assemble_chapter_button = QPushButton("Assemble Chapter")
        self.assemble_novel_button = QPushButton("Assemble Finished Novel")
        for button in (self.open_button, self.save_button, self.save_as_button, self.save_new_scene_button, self.save_scene_button, self.assemble_chapter_button, self.assemble_novel_button):
            file_controls.addWidget(button)
        page.addLayout(file_controls)

        self.status = QLabel("Ready.")
        self.status.setWordWrap(True)
        page.addWidget(self.status)

        self.refresh_models_button.clicked.connect(self.refresh_models)
        self.openrouter_settings_button.clicked.connect(self.open_openrouter_settings)
        self.load_writer_button.clicked.connect(self.load_writer)
        self.load_scene_button.clicked.connect(self.load_scene_copy)
        self.planner_picker.activated.connect(lambda _index: self.save_model_roles())
        self.writer_picker.activated.connect(lambda _index: self.save_model_roles())
        self.refresh_novels_button.clicked.connect(self.refresh_novels)
        self.sync_novel_button.clicked.connect(self.sync_selected_novel_to_github)
        self.novel_picker.currentTextChanged.connect(self.on_novel_changed)
        self.chapter_picker.currentTextChanged.connect(self.on_chapter_changed)
        self.scene_picker.currentTextChanged.connect(self.update_controls)
        self.cast_button.clicked.connect(self.choose_scene_cast)
        self.prepare_button.clicked.connect(self.prepare_scene)
        self.write_button.clicked.connect(lambda: self.write("balanced"))
        self.minimal_button.clicked.connect(lambda: self.write("minimal"))
        self.full_button.clicked.connect(lambda: self.write("full"))
        self.rewrite_button.clicked.connect(self.rewrite_scene)
        self.continue_button.clicked.connect(self.continue_writing)
        self.stop_button.clicked.connect(self.stop_task)
        self.new_session_button.clicked.connect(self.new_session)
        self.open_button.clicked.connect(self.open_document)
        self.save_button.clicked.connect(self.save_document)
        self.save_as_button.clicked.connect(self.save_document_as)
        self.save_new_scene_button.clicked.connect(self.save_new_scene)
        self.save_scene_button.clicked.connect(self.save_to_selected_scene)
        self.assemble_chapter_button.clicked.connect(self.assemble_chapter)
        self.assemble_novel_button.clicked.connect(self.assemble_novel)
        self.revise_button.clicked.connect(self.revise_selection)
        self.check_draft_button.clicked.connect(self.check_draft)
        self.output_editor.textChanged.connect(self.update_controls)
        self.update_controls()

    def info(self, title: str, message: str):
        QMessageBox.information(self, title, message)

    def error(self, title: str, message: str):
        QMessageBox.critical(self, title, message)

    def confirm(self, title: str, message: str) -> bool:
        return QMessageBox.question(self, title, message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def open_openrouter_settings(self):
        """Manage the saved remote API key and refresh the cached free catalogue."""
        if self.busy:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("OpenRouter Settings")
        dialog.resize(650, 390)
        layout = QVBoxLayout(dialog)
        privacy = QLabel(
            "OpenRouter is optional. Local GGUF models remain available. When you use a "
            "remote model, the current prompt, StoryBuilder context included in that prompt, "
            "and generated response are sent through OpenRouter to the selected model provider. "
            "Review the provider's privacy terms before using remote models."
        )
        privacy.setWordWrap(True)
        layout.addWidget(privacy)
        layout.addWidget(QLabel("OpenRouter API key"))
        key_editor = QLineEdit()
        key_editor.setEchoMode(QLineEdit.EchoMode.Password)
        key_editor.setPlaceholderText("Paste a key, or leave blank to use the saved/environment key")
        layout.addWidget(key_editor)
        key_note = QLabel(
            "Saved keys use the existing user configuration file with owner-only permissions. "
            "The OPENROUTER_API_KEY environment variable is also supported."
        )
        key_note.setWordWrap(True)
        layout.addWidget(key_note)
        status = QLabel(
            "An API key is configured." if has_openrouter_api_key()
            else "No API key configured."
        )
        status.setWordWrap(True)
        layout.addWidget(status)
        buttons = QHBoxLayout()
        refresh = QPushButton("Save Key & Refresh Free Models")
        remove = QPushButton("Remove Saved Key")
        close = QPushButton("Close")
        buttons.addWidget(refresh)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        buttons.addWidget(close)
        layout.addLayout(buttons)

        self._openrouter_settings_dialog = dialog
        self._openrouter_status_label = status
        self._openrouter_key_editor = key_editor
        self._openrouter_refresh_button = refresh
        self._openrouter_remove_button = remove

        def refresh_catalogue():
            if self.busy:
                return
            entered_key = key_editor.text().strip()
            if entered_key:
                try:
                    save_openrouter_api_key(entered_key)
                except (OSError, ValueError) as exc:
                    self.error("Could not save OpenRouter key", str(exc))
                    return
                key_editor.clear()
            api_key = load_openrouter_api_key()
            if not api_key:
                status.setText("Add an API key first, then refresh the free-model catalogue.")
                return
            refresh.setEnabled(False)
            remove.setEnabled(False)
            status.setText("Contacting OpenRouter and refreshing the free-model catalogue…")

            def work(_emit):
                models = fetch_openrouter_free_models(api_key)
                # The previous cache is left untouched unless the fetch succeeds.
                save_cached_openrouter_models(models)
                return models

            self._task_kind = "openrouter_refresh"
            self.run_task(
                work,
                label="Refreshing OpenRouter free-model catalogue…",
            )

        def remove_saved_key():
            if self.busy:
                return
            try:
                delete_openrouter_api_key()
            except OSError as exc:
                self.error("Could not remove saved OpenRouter key", str(exc))
                return
            self.refresh_models()
            status.setText(
                "Saved key removed. OPENROUTER_API_KEY remains active."
                if has_openrouter_api_key()
                else "Saved OpenRouter key removed. Local models are unchanged."
            )
            key_editor.clear()

        refresh.clicked.connect(refresh_catalogue)
        remove.clicked.connect(remove_saved_key)
        close.clicked.connect(dialog.close)
        dialog.setModal(False)
        dialog.show()

    def refresh_models(self):
        try:
            paths = WriterEngine.available_models()
        except Exception as exc:
            self.status.setText(f"Could not list local models: {exc}")
            return
        previous_writer = self.writer_picker.currentText()
        previous_planner = self.planner_picker.currentText()
        self.models = {path.name: path for path in paths}
        self.openrouter_models = load_cached_openrouter_models()
        if has_openrouter_api_key():
            for item in self.openrouter_models:
                model_id = str(item.get("id") or "").strip()
                if model_id:
                    label = f"OpenRouter · {item.get('name') or model_id} [{model_id}]"
                    self.models[label] = openrouter_model_selection(model_id)
        labels = list(self.models)
        self.writer_picker.clear()
        self.planner_picker.clear()
        self.writer_picker.addItems(labels)
        self.planner_picker.addItems(labels)
        roles = load_model_roles()
        local_names = [path.name for path in paths]
        defaults = resolve_model_roles(local_names, roles)
        def restore(role, previous, default):
            if previous in self.models:
                return previous
            saved = str(roles.get(role) or "").strip()
            if saved in local_names:
                return saved
            for label, value in self.models.items():
                if value == saved and saved:
                    return label
            return default if default in self.models else (labels[0] if labels else "")
        self.writer_picker.setCurrentText(restore("writer", previous_writer, defaults["writer"]))
        self.planner_picker.setCurrentText(restore("planner", previous_planner, defaults["planner"]))
        if not labels:
            self.status.setText(f"No GGUF models found in {MODELS_DIR}.")
        else:
            self.status.setText(f"Found {len(labels)} model option(s).")
        self.update_controls()

    def save_model_roles(self):
        roles = {}
        for role, picker in (("planner", self.planner_picker), ("writer", self.writer_picker)):
            value = self.models.get(picker.currentText())
            if value is not None:
                roles[role] = str(value) if is_openrouter_selection(value) else Path(value).name
        save_model_roles(planner=roles.get("planner", ""), writer=roles.get("writer", ""))

    def load_writer(self):
        model = self.selected_model("writer")
        if model is None or self.busy:
            return
        def work(_emit):
            load_model_for_writing(self.engine, model)
            self.loaded_model = model
            return model
        self._task_kind = "load"
        self.run_task(work, label=f"Loading writing model: {model}")

    def selected_model(self, role: str):
        picker = self.planner_picker if role == "planner" else self.writer_picker
        return self.models.get(picker.currentText())

    def run_task(self, task: Callable, *, streaming=False, label="Working"):
        if self.busy:
            return
        self.busy = True
        self._streamed = False
        self.status.setText(label)
        self.update_controls()
        self.worker = TaskWorker(task, streaming=streaming)
        self.worker.chunk.connect(self.append_chunk)
        self.worker.succeeded.connect(self.task_succeeded)
        self.worker.failed.connect(self.task_failed)
        self.worker.interrupted.connect(self.task_interrupted)
        self.worker.finished.connect(self.worker_finished)
        self.worker.start()

    def append_chunk(self, chunk: str):
        if not chunk:
            return
        self._streamed = True
        cursor = self.output_editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(chunk)
        self.output_editor.setTextCursor(cursor)
        self.output_editor.ensureCursorVisible()

    def task_succeeded(self, result):
        if isinstance(result, str) and result:
            # Worker streaming already delivered incremental text.
            if not self._streamed:
                self.output_editor.setPlainText(result)
        self.busy = False
        self.status.setText("Task finished.")
        self.update_controls()

    def task_failed(self, message: str):
        if getattr(self, "_task_kind", "") == "prepare":
            self._discard_scene_prompt_trace(self._active_scene_preparation_trace)
            self._active_scene_preparation_trace = None
        if getattr(self, "_task_kind", "") == "revision":
            self._clear_revision_state()
        if getattr(self, "_task_kind", "") == "write":
            if getattr(self, "_generation_mode", "") == "rewrite":
                self.output_editor.setPlainText(getattr(self, "_generation_original", ""))
            elif not self._streamed:
                self.output_editor.setPlainText(getattr(self, "_generation_original", ""))
        self.busy = False
        kind = getattr(self, "_task_kind", "")
        trace_note = self._prompt_trace_status_note() if kind == "write" else ""
        error_title = "StoryBuilder task failed"
        if kind == "novel_sync":
            self.status.setText("Novel sync failed. Check the message before retrying.")
            error_title = "Novel sync failed"
        elif kind == "scene_state":
            novel_name, chapter, scene = self._saved_scene_state_target or ("Novel", 1, 1)
            self.status.setText(
                f"Saved new scene: {novel_name} / Chapter {chapter:02d} / Scene {scene:02d}. "
                "The scene position was recorded, but ending-state analysis failed; "
                "existing story details were preserved."
            )
            if self._scene_state_reset_error:
                self.loaded_model = None
                self.model_status.setText("Model session reset failed. Reload the model before writing again.")
            self._scene_state_reset_error = None
            error_title = "Scene ending-state update failed"
        elif kind == "openrouter_refresh":
            if getattr(self, "_openrouter_status_label", None) is not None:
                self._openrouter_status_label.setText(
                    "The catalogue could not be refreshed. The previous cache was kept."
                )
            if getattr(self, "_openrouter_refresh_button", None) is not None:
                self._openrouter_refresh_button.setEnabled(True)
            if getattr(self, "_openrouter_remove_button", None) is not None:
                self._openrouter_remove_button.setEnabled(True)
            self.status.setText("OpenRouter refresh failed. The previous model cache was kept.")
            error_title = "OpenRouter refresh failed"
        elif kind == "revision":
            self.status.setText("Revision failed. The original passage was kept.")
            error_title = "Revision failed"
        else:
            self.status.setText("Task failed. Existing saved files were not changed." + trace_note)
        self.update_controls()
        self.error(error_title, message)

    def task_interrupted(self):
        kind = getattr(self, "_task_kind", "")
        if kind == "prepare":
            self._discard_scene_prompt_trace(self._active_scene_preparation_trace)
            self._active_scene_preparation_trace = None
        if kind == "revision":
            self._clear_revision_state()
        if kind == "write" and getattr(self, "_generation_mode", "") == "rewrite":
            self.output_editor.setPlainText(getattr(self, "_generation_original", ""))
        self.busy = False
        self.loaded_model = None
        self.model_status.setText("Stopped. Model will reload on the next task.")
        if kind == "scene_state":
            novel_name, chapter, scene = self._saved_scene_state_target or ("Novel", 1, 1)
            self.status.setText(
                f"Saved new scene: {novel_name} / Chapter {chapter:02d} / Scene {scene:02d}. "
                "Scene position was recorded; ending-state analysis was stopped and existing story details were kept."
            )
        elif kind == "revision":
            self.status.setText("Revision stopped. The original passage was kept.")
        else:
            trace_note = self._prompt_trace_status_note() if kind == "write" else ""
            self.status.setText("Stopped. Any streamed partial text remains in the editor." + trace_note)
        self.update_controls()

    def worker_finished(self):
        self.worker = None

    def refresh_novels(self):
        previous = self.novel_picker.currentText()
        try:
            paths = list_novel_packages(NOVEL_ROOT)
        except Exception as exc:
            self.status.setText(f"Could not list novels: {exc}")
            return
        self.novel_packages = {path.name: path for path in paths}
        self.novel_picker.blockSignals(True)
        self.novel_picker.clear()
        self.novel_picker.addItems(list(self.novel_packages))
        if previous in self.novel_packages:
            self.novel_picker.setCurrentText(previous)
        else:
            self.novel_picker.setCurrentIndex(-1)
        self.novel_picker.blockSignals(False)
        self.on_novel_changed(self.novel_picker.currentText())

    def on_novel_changed(self, name: str):
        self._discard_scene_prompt_trace()
        self._prepared_author_required_direction = ""
        self.scene_cast = None
        self.scene_cast_novel = None
        self.scene_cast_destination = None
        self.prepared_destination = None
        self.prepared_novel = None
        self.prepared_source = None
        self.author_direction.clear()
        self.prompt_editor.clear()
        self.cast_summary.setText("No scene cast selected.")
        path = self.novel_packages.get(name)
        self.chapter_numbers = {f"Chapter {n:02d}": n for n in list_scene_chapters(path)} if path else {}
        self.chapter_picker.blockSignals(True)
        self.chapter_picker.clear()
        self.chapter_picker.addItems(list(self.chapter_numbers))
        self.chapter_picker.blockSignals(False)
        self.on_chapter_changed(self.chapter_picker.currentText())
        self.update_controls()

    def on_chapter_changed(self, label: str):
        path = self.novel_packages.get(self.novel_picker.currentText())
        number = self.chapter_numbers.get(label)
        self.scene_files = dict((f"Scene {n:02d}", p) for n, p in list_scene_files(path, number)) if path and number else {}
        self.scene_picker.blockSignals(True)
        self.scene_picker.clear()
        self.scene_picker.addItems(list(self.scene_files))
        self.scene_picker.blockSignals(False)
        self.update_controls()

    def choose_scene_cast(self):
        path = self.novel_packages.get(self.novel_picker.currentText())
        if path is None:
            self.info("Choose a novel", "Select a novel first.")
            return
        try:
            bible = load_story_bible(path)
            names = load_character_card_names(path, bible)
        except Exception as exc:
            self.error("Could not load character cards", str(exc))
            return
        if not names:
            self.info("No character cards", "This novel has no registered character cards yet.")
            return
        dialog = SceneCastDialog(names, self.scene_cast, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.scene_cast = dialog.selected_names()
            self.scene_cast_novel = path.resolve()
            chapter = self.chapter_numbers.get(self.chapter_picker.currentText())
            scene = scene_number_from_label(self.scene_picker.currentText())
            self.scene_cast_destination = (chapter, scene) if chapter and scene else None
            self.cast_summary.setText(", ".join(self.scene_cast) if self.scene_cast else "No characters selected.")
        self.update_controls()

    def _resolve_target(self):
        novel_name = self.novel_picker.currentText()
        novel_path = self.novel_packages.get(novel_name)
        chapter = self.chapter_numbers.get(self.chapter_picker.currentText())
        scene_label = self.scene_picker.currentText()
        scene_number = scene_number_from_label(scene_label)
        source = self.scene_files.get(scene_label)
        target_chapter, target_scene, source_scene, retry = resolve_scene_preparation_target(
            chapter, source, scene_number, novel_path=novel_path,
            pending_destination=self.prepared_destination,
            pending_novel_path=self.prepared_novel,
            pending_source_scene_path=self.prepared_source,
        )
        return novel_name, novel_path, target_chapter, target_scene, source_scene, retry

    def sync_selected_novel_to_github(self):
        """Preview and explicitly confirm syncing only the selected novel repository."""
        if self.busy:
            return
        name = self.novel_picker.currentText().strip()
        novel_path = self.novel_packages.get(name)
        if novel_path is None:
            self.info("Choose a novel", "Select an existing novel package before syncing it to GitHub.")
            return
        try:
            preview = inspect_novel_repository(novel_path)
        except NovelGitSyncError as exc:
            self.status.setText("Novel sync blocked; no push was attempted.")
            self.error("Cannot sync novel", str(exc))
            return

        lines = [
            "Review the sync target before proceeding:",
            "",
            f"Novel folder: {preview.repository}",
            f"Branch: {preview.branch}",
            f"GitHub remote: {preview.remote_url}",
            "",
            "This operation is confined to this novel's own Git repository.",
            "It will fetch, fast-forward only when possible, restore any safety stash, "
            "then commit and push this novel branch if needed.",
            "StoryBuilder source code is not part of this operation.",
            "Diverged branches, unresolved operations/conflicts, unexpected upstreams, "
            "and local-only secret/encrypted paths block syncing.",
            "",
        ]
        if self.output_editor.toPlainText() != self.saved_text:
            lines.extend([
                "WARNING: The Writer pane contains unsaved edits.",
                "They will not be included until saved to a file.",
                "",
            ])
        if preview.local_commits:
            lines.append(
                "Local commits ahead of the last fetched origin branch "
                "(the list may change after fetching):"
            )
            shown = preview.local_commits[:10]
            lines.extend(f"  • {item}" for item in shown)
            if len(preview.local_commits) > len(shown):
                lines.append(f"  • …and {len(preview.local_commits) - len(shown)} more commit(s)")
            lines.append("")
        if preview.changed_files:
            lines.append("Local file changes to include in the commit:")
            shown = preview.changed_files[:15]
            lines.extend(f"  • {item}" for item in shown)
            if len(preview.changed_files) > len(shown):
                lines.append(f"  • …and {len(preview.changed_files) - len(shown)} more file(s)")
        else:
            lines.append(
                "No uncommitted file changes detected. The sync will still check for "
                "a safe fast-forward and push the selected branch if needed."
            )
        lines.extend(["", "Proceed with syncing this novel to GitHub?"])
        if not self.confirm("Confirm novel sync", "\n".join(lines)):
            self.status.setText("Novel sync cancelled; no Git operation started.")
            return

        self._task_kind = "novel_sync"

        def work(_emit):
            return sync_novel_repository(novel_path)

        self.run_task(
            work,
            label=f"Syncing {name} to GitHub on branch {preview.branch}…",
        )

    def _discard_scene_prompt_trace(self, trace=None):
        """Detach an unused trace without saving or uploading it."""
        if trace is None:
            trace = self._active_scene_preparation_trace or self._pending_scene_prompt_trace
        if trace is None:
            return
        try:
            self.engine.detach_prompt_trace(trace)
        except Exception:
            pass
        if self._active_scene_preparation_trace is trace:
            self._active_scene_preparation_trace = None
        if self._pending_scene_prompt_trace is trace:
            self._pending_scene_prompt_trace = None

    def _start_prompt_trace(
        self,
        prompt: str,
        model_path: str | Path | None = None,
        *,
        attach: bool = False,
        chapter_number: int | None = None,
        scene_number: int | None = None,
        scene_direction: str | None = None,
        author_guidance: str | None = None,
        role: str = "scene_writer",
    ):
        """Create the same one-scene trace used by the established Writer."""
        try:
            if not load_prompt_trace_enabled():
                return None
        except Exception:
            return None

        novel_path = self.novel_packages.get(self.novel_picker.currentText())
        selected_chapter = chapter_number
        if selected_chapter is None:
            selected_chapter = self.chapter_numbers.get(self.chapter_picker.currentText(), 1)
        selected_scene = scene_number
        if selected_scene is None:
            selected_scene = scene_number_from_label(self.scene_picker.currentText()) or 1

        current_state = {}
        reference_files = []
        if novel_path is not None:
            for filename in ("story_bible.json", "current_state.json"):
                reference_path = Path(novel_path) / filename
                try:
                    content = reference_path.read_text(encoding="utf-8")
                except (OSError, UnicodeError):
                    continue
                reference_files.append((filename, content))
                if filename == "current_state.json":
                    try:
                        parsed = json.loads(content)
                    except (TypeError, ValueError):
                        parsed = {}
                    if isinstance(parsed, dict):
                        current_state = parsed

        captured_direction = (
            scene_direction
            if scene_direction is not None
            else self.prompt_editor.toPlainText()
            if hasattr(self, "prompt_editor")
            else str(prompt or "")
        )
        captured_author = (
            author_guidance
            if author_guidance is not None
            else self.author_direction.toPlainText().strip()
            if hasattr(self, "author_direction")
            else ""
        )
        try:
            requested_model = (
                str(model_path)
                if is_openrouter_selection(model_path)
                else Path(model_path).expanduser().resolve()
                if model_path is not None
                else getattr(self.engine, "model_path", None)
            )
            trace = PromptTrace(
                chapter=int(selected_chapter or 1),
                scene=int(selected_scene or 1),
                model_path=requested_model,
                current_state=current_state,
                reference_files=reference_files,
                contract={},
                scene_direction=captured_direction,
                author_guidance=captured_author,
                system_prompt="" if model_path is not None else self.engine.system_prompt,
            )
        except Exception:
            return None

        if attach:
            try:
                self.engine.attach_prompt_trace(trace, role=role)
            except Exception:
                return None
        return trace

    def _finish_prompt_trace(self, trace, *, status: str, error: str | None = None) -> None:
        self._last_prompt_trace_upload_result = None
        if trace is None:
            return
        saved_path = None
        try:
            saved_path = trace.finish(status=status, error=error)
        except Exception:
            saved_path = None
        self._last_prompt_trace_path = str(saved_path) if saved_path else None
        if saved_path:
            try:
                self._last_prompt_trace_upload_result = upload_prompt_trace(saved_path)
            except Exception as exc:
                self._last_prompt_trace_upload_result = {
                    "ok": False,
                    "error": str(exc)[:700],
                }
        try:
            self.engine.detach_prompt_trace(trace)
        except Exception:
            pass

    def _claim_prepared_scene_prompt_trace(
        self, mode: str, expected_destination: tuple[int, int] | None
    ):
        """Reuse a Planner trace only for the same novel and destination scene."""
        trace = self._pending_scene_prompt_trace
        if trace is None:
            return None
        try:
            tracing_enabled = load_prompt_trace_enabled()
        except Exception:
            tracing_enabled = False
        if not tracing_enabled:
            self._discard_scene_prompt_trace(trace)
            return None

        current_path = self.novel_packages.get(self.novel_picker.currentText())
        prepared_path = self.prepared_novel
        try:
            same_novel = (
                current_path is not None
                and prepared_path is not None
                and Path(current_path).expanduser().resolve()
                == Path(prepared_path).expanduser().resolve()
            )
        except (OSError, TypeError, ValueError):
            same_novel = False
        if (
            not same_novel
            or expected_destination is None
            or self.prepared_destination != expected_destination
        ):
            self._discard_scene_prompt_trace(trace)
            return None

        self._pending_scene_prompt_trace = None
        trace.record_event(
            "prepared_direction_sent_to_writer",
            generation_mode=str(mode),
            final_scene_direction=self.prompt_editor.toPlainText(),
            final_author_guidance=self.author_direction.toPlainText().strip(),
            final_author_required_direction=self._prepared_author_required_direction_for_current_scene(
                expected_destination
            ),
        )
        return trace

    def _prepared_author_required_direction_for_current_scene(
        self, expected_destination: tuple[int, int] | None = None
    ) -> str:
        direction = str(self._prepared_author_required_direction or "").strip()
        if not direction or self.prepared_novel is None or self.prepared_destination is None:
            return ""
        if expected_destination is None:
            chapter = self.chapter_numbers.get(self.chapter_picker.currentText())
            scene = scene_number_from_label(self.scene_picker.currentText())
            expected_destination = (chapter, scene) if chapter and scene else None
        current_path = self.novel_packages.get(self.novel_picker.currentText())
        try:
            if (
                current_path is None
                or expected_destination != self.prepared_destination
                or Path(current_path).expanduser().resolve()
                != Path(self.prepared_novel).expanduser().resolve()
            ):
                return ""
        except (OSError, TypeError, ValueError):
            return ""
        return direction

    def _author_required_direction_for_current_scene(
        self, expected_destination: tuple[int, int] | None = None
    ) -> str:
        directions = []
        for direction in (
            self._prepared_author_required_direction_for_current_scene(expected_destination),
            self.author_direction.toPlainText().strip(),
        ):
            if direction and direction not in directions:
                directions.append(direction)
        return "\n\n".join(directions)

    def _prompt_trace_status_note(self) -> str:
        notes = []
        if self._last_prompt_trace_path:
            notes.append(f"Prompt trace saved locally: {self._last_prompt_trace_path}.")
        result = self._last_prompt_trace_upload_result
        if isinstance(result, dict):
            if result.get("ok"):
                notes.append("Latest trace uploaded to the private GitHub trace repository.")
            else:
                detail = str(result.get("error") or "Unknown upload error").strip()
                notes.append(
                    "Private GitHub trace upload failed; the local trace is retained. "
                    + detail
                )
        return (" " + " ".join(notes)) if notes else ""

    def prepare_scene(self):
        if self.busy:
            return
        planner = self.selected_model("planner")
        if planner is None:
            self.info("Choose a Planner model", "Select the model used for Prepare Scene.")
            return
        novel_name, path, chapter, scene, source, retry = self._resolve_target()
        if path is None:
            self.info("Choose a novel", "Select a novel before preparing a scene.")
            return
        cast = self.scene_cast
        if cast is None or self.scene_cast_novel != path.resolve():
            try:
                bible = load_story_bible(path)
                names = load_character_card_names(path, bible)
            except Exception as exc:
                self.error("Could not load character cards", str(exc))
                return
            dialog = SceneCastDialog(names, None, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            cast = dialog.selected_names()
            self.scene_cast = cast
            self.scene_cast_novel = path.resolve()
        self.scene_cast_destination = (chapter, scene)
        author = self.author_direction.toPlainText().strip()
        old_prompt = self.prompt_editor.toPlainText()
        if old_prompt.strip() and not self.confirm("Replace prompt text?", "Prepare Scene replaces only the prompt editor. It does not change manuscript files. Continue?"):
            return
        try:
            prompt = build_scene_preparation_prompt(
                path, novel_name, chapter, scene, source_scene_path=source,
                author_direction=author, previous_direction=old_prompt if retry else None,
                scene_cast=list(cast or []),
            )
        except Exception as exc:
            self.error("Could not prepare scene", str(exc))
            return

        pending_trace = self._pending_scene_prompt_trace
        try:
            can_extend_pending_trace = (
                pending_trace is not None
                and self.prepared_destination == (chapter, scene)
                and self.prepared_novel is not None
                and Path(self.prepared_novel).expanduser().resolve() == path.resolve()
            )
        except (OSError, TypeError, ValueError):
            can_extend_pending_trace = False
        if can_extend_pending_trace:
            planner_trace = pending_trace
            self._pending_scene_prompt_trace = None
        else:
            self._discard_scene_prompt_trace()
            planner_trace = self._start_prompt_trace(
                prompt,
                model_path=planner,
                attach=False,
                chapter_number=chapter,
                scene_number=scene,
                scene_direction=old_prompt,
                author_guidance=author,
            )
        self._active_scene_preparation_trace = planner_trace
        if planner_trace is not None:
            planner_trace.record_event(
                "scene_preparation_attempt_started",
                target_chapter=chapter,
                target_scene=scene,
                retry=bool(retry),
                source_scene=Path(source).name if source else None,
                author_direction=author,
            )
        self._scene_preparation_original_prompt = old_prompt
        self._scene_preparation_original_author_direction = self.author_direction.toPlainText().strip()
        self._scene_preparation_required_author_direction = author
        self._pending_planner_author = author
        self._pending_target = (chapter, scene)

        def work(_emit):
            trace_attached = False
            try:
                if self.loaded_model != planner or not self._engine_ready():
                    load_model_for_writing(self.engine, planner)
                    self.loaded_model = planner
                if planner_trace is not None:
                    try:
                        self.engine.attach_prompt_trace(planner_trace, role="scene_planner")
                        trace_attached = True
                    except Exception as exc:
                        planner_trace.record_event(
                            "trace_attach_failed", role="scene_planner", error=str(exc)
                        )
                suggestion = write_from_prompt(self.engine, prompt).strip()
                try:
                    self.engine.clear_context()
                except Exception as exc:
                    if planner_trace is not None:
                        planner_trace.record_event(
                            "planner_context_reset_failed", error=str(exc)
                        )
                return suggestion
            finally:
                if trace_attached:
                    try:
                        self.engine.detach_prompt_trace(planner_trace)
                    except Exception:
                        pass

        self._task_kind = "prepare"
        self.run_task(work, label=f"Preparing Chapter {chapter:02d}, Scene {scene:02d} with Planner…")

    def _engine_ready(self):
        child = getattr(self.engine, "child", None)
        try:
            return child is not None and child.isalive()
        except Exception:
            return False

    def _writer_context(self, prompt: str, profile: str):
        selected_chapter = self.chapter_numbers.get(self.chapter_picker.currentText())
        destination = resolve_generation_scene_destination(
            prompt, selected_chapter, self.scene_picker.currentText()
        )
        chapter, scene = destination or (
            selected_chapter,
            scene_number_from_label(self.scene_picker.currentText()),
        )
        author_direction = self._author_required_direction_for_current_scene(destination)
        scene_cast = self._active_cast(destination)

        if profile == "minimal":
            prompt = build_scene_cast_boundary_prompt(prompt, scene_cast)
            prompt = build_author_required_direction_prompt(prompt, author_direction)
            return build_single_scene_scope_prompt(prompt, chapter, scene)

        name = self.novel_picker.currentText()
        path = self.novel_packages.get(name)
        if path is None:
            prompt = build_scene_cast_boundary_prompt(prompt, scene_cast)
            prompt = build_author_required_direction_prompt(prompt, author_direction)
            return build_single_scene_scope_prompt(prompt, chapter, scene)

        bible = load_story_bible(path)
        sections = [prompt]
        creative = build_creative_direction_prompt(bible.get("creative_direction"))
        if creative:
            sections.append(creative)
        preferences = bible.get("writing_preferences")
        if isinstance(preferences, str) and preferences.strip():
            sections.append("HOW THIS NOVEL SHOULD READ\n" + preferences.strip())
        comprehensive = profile == "full"
        references = build_story_bible_reference_context(bible, comprehensive=comprehensive)
        if references:
            sections.append(references)
        supporting = prompt + "\n" + author_direction
        character_context = build_character_card_context_prompt(
            path, bible, "", supporting_text=supporting,
            include_all=comprehensive and scene_cast is None,
            compact=not comprehensive, comprehensive=comprehensive,
            selected_names=scene_cast, scene_focused=not comprehensive,
        )
        if character_context:
            sections.append(character_context)
        locations = bible.get("locations", {})
        if isinstance(locations, dict):
            relevant = locations if comprehensive else select_relevant_locations(locations, "", supporting)
            if relevant:
                lines = ["RELEVANT SAVED LOCATIONS"]
                for location, detail in relevant.items():
                    lines.append(f"{location}: {detail}")
                sections.append("\n".join(lines))
        if chapter and scene:
            try:
                prior = build_previous_scene_context_prompt(
                    "", path, chapter, scene,
                    max_chars=None if comprehensive else 1400,
                )
                if prior.strip():
                    sections.append(prior)
            except Exception:
                pass
        prompt = build_scene_cast_boundary_prompt("\n\n".join(sections), scene_cast)
        prompt = build_author_required_direction_prompt(prompt, author_direction)
        return build_single_scene_scope_prompt(prompt, chapter, scene)

    def _active_cast(self, expected_destination=None):
        path = self.novel_packages.get(self.novel_picker.currentText())
        if self.scene_cast is None or path is None or self.scene_cast_novel != path.resolve():
            return None
        if expected_destination is None:
            chapter = self.chapter_numbers.get(self.chapter_picker.currentText())
            scene = scene_number_from_label(self.scene_picker.currentText())
            expected_destination = (chapter, scene) if chapter and scene else None
        if self.scene_cast_destination and expected_destination != self.scene_cast_destination:
            return None
        return list(self.scene_cast)

    def write(self, profile="balanced"):
        if self.busy:
            return
        raw = self.prompt_editor.toPlainText().strip()
        if not raw:
            self.info("Add a prompt", "Enter or prepare a scene direction first.")
            return
        prompt = self._writer_context(raw, profile)
        mode = "write"
        self._start_generation(prompt, mode)

    def rewrite_scene(self):
        if self.busy:
            return
        prompt = self.prompt_editor.toPlainText().strip()
        old = self.output_editor.toPlainText()
        if not prompt or not old.strip():
            self.info("Nothing to rewrite", "Prepare a scene and write a draft before using Rewrite Scene.")
            return
        if not self.confirm("Rewrite current scene?", "The output editor will be replaced only after you confirm. Saved manuscript files are not changed."):
            return
        rewrite_prompt = build_rewrite_scene_prompt(prompt, self.author_direction.toPlainText())
        self._start_generation(self._writer_context(rewrite_prompt, "balanced"), "rewrite")

    def continue_writing(self):
        if self.busy:
            return
        old = self.output_editor.toPlainText()
        if not old.strip():
            self.info("Nothing to continue", "Write or open a passage first.")
            return
        prompt = build_continue_prompt(old)
        self._start_generation(self._writer_context(prompt, "balanced"), "continue")

    def revise_selection(self):
        """Revise or exactly replace only the currently selected manuscript passage."""
        if self.busy:
            return
        cursor = self.output_editor.textCursor()
        if not cursor.hasSelection():
            self.info(
                "Select a passage",
                "Highlight the sentence or paragraph you want to change, then click Revise Selection.",
            )
            return
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        selected = cursor.selectedText().replace("\u2029", "\n")
        if not selected.strip():
            self.info("Select a passage", "Select some non-blank text to revise.")
            return

        dialog = RevisionRequestDialog(selected, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._revision_document = self.output_editor.toPlainText()
        self._revision_start = start
        self._revision_end = end
        self._revision_original = selected

        if not dialog.use_ai:
            self._show_revision_review(dialog.replacement())
            return

        instruction = dialog.instruction()
        if not instruction:
            self._clear_revision_state()
            self.info("Add an instruction", "Describe what you want changed in the selected passage.")
            return
        writer = self.selected_model("writer")
        if writer is None:
            self._clear_revision_state()
            self.info("Choose a writing model", "Select a writing model before revising a passage.")
            return

        prompt = build_revision_prompt(selected, instruction)
        novel = self.novel_packages.get(self.novel_picker.currentText())
        if novel is not None:
            try:
                bible = load_story_bible(novel)
                locations = bible.get("locations", {})
                if isinstance(locations, dict):
                    prompt, _selected_locations = build_location_context_prompt(
                        prompt, locations, selected
                    )
                creative = build_creative_direction_prompt(bible.get("creative_direction"))
                if creative:
                    prompt = prompt + "\n\n" + creative
            except Exception as exc:
                self._clear_revision_state()
                self.error("Could not prepare revision context", str(exc))
                return

        self._task_kind = "revision"
        self.output_editor.setReadOnly(True)

        def work(_emit):
            if self.loaded_model != writer or not self._engine_ready():
                load_model_for_writing(self.engine, writer)
                self.loaded_model = writer
            return write_from_prompt(self.engine, prompt)

        self.run_task(work, label=f"Revising selected passage with {writer}…")

    def _show_revision_review(self, proposed: str):
        current = self.output_editor.toPlainText()
        if current != self._revision_document:
            self._clear_revision_state()
            self.error(
                "Selection changed",
                "The document changed while the revision was being prepared. "
                "Nothing was replaced. Select the passage again and retry.",
            )
            return

        dialog = RevisionReviewDialog(self._revision_original, proposed, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._clear_revision_state()
            self.status.setText("Kept original passage; no text was changed.")
            return
        current = self.output_editor.toPlainText()
        start = self._revision_start
        end = self._revision_end
        original_document = self._revision_document
        if current != original_document:
            self._clear_revision_state()
            self.error(
                "Selection changed",
                "The document changed while the revision was being reviewed. "
                "Nothing was replaced. Select the passage again and retry.",
            )
            return
        cursor = self.output_editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(dialog.proposed_text())
        self.output_editor.setTextCursor(cursor)
        self._clear_revision_state()
        self.status.setText("Revision applied to selected passage. Save when ready.")

    def _clear_revision_state(self):
        self.output_editor.setReadOnly(False)
        self._revision_document = ""
        self._revision_start = 0
        self._revision_end = 0
        self._revision_original = ""

    def check_draft(self):
        """Run the existing conservative advisory check without modifying the manuscript."""
        if self.busy:
            return
        original = self.output_editor.toPlainText()
        if not original.strip():
            self.status.setText("There is no draft text to check.")
            self.update_controls()
            return
        findings = analyze_draft(original)
        report = format_draft_health_report(findings)
        count = len(findings)
        self.status.setText(
            "Draft check complete: "
            + (f"{count} possible finding(s)." if count else "no obvious mechanical issues found.")
            + " No text was changed."
        )
        DraftReportDialog(report, self).exec()

    def _start_generation(self, prompt: str, mode: str):
        writer = self.selected_model("writer")
        if writer is None:
            self.info("Choose a writing model", "Select the manuscript-writing model.")
            return
        chapter = self.chapter_numbers.get(self.chapter_picker.currentText())
        scene_label = self.scene_picker.currentText()
        destination = resolve_generation_scene_destination(prompt, chapter, scene_label)
        required_author_direction = self._author_required_direction_for_current_scene(destination)
        self._last_prompt_trace_path = None
        self._last_prompt_trace_upload_result = None
        prompt_trace = self._claim_prepared_scene_prompt_trace(mode, destination)
        if prompt_trace is None:
            prompt_trace = self._start_prompt_trace(
                prompt,
                model_path=writer,
                attach=False,
                chapter_number=destination[0] if destination else chapter,
                scene_number=destination[1] if destination else scene_number_from_label(scene_label),
                author_guidance=required_author_direction,
            )
        if prompt_trace is not None:
            prompt_trace.record_event(
                "writer_generation_attempt_started",
                generation_mode=str(mode),
                writer_prompt_characters=len(prompt),
                destination=(
                    {"chapter": destination[0], "scene": destination[1]}
                    if destination else None
                ),
            )

        original = self.output_editor.toPlainText()
        if mode == "continue":
            prefix = original if original.endswith("\n\n") else original + ("\n" if original.endswith("\n") else "\n\n")
            self.output_editor.setPlainText(prefix)
        else:
            prefix = ""
            self.output_editor.clear()
        self._generation_prefix = prefix
        self._generation_original = original
        self._generation_mode = mode
        def work(emit):
            trace_status = "completed"
            trace_error = None
            try:
                if self.loaded_model != writer or not self._engine_ready():
                    load_model_for_writing(self.engine, writer)
                    self.loaded_model = writer
                if prompt_trace is not None:
                    try:
                        self.engine.attach_prompt_trace(prompt_trace, role="scene_writer")
                    except Exception as exc:
                        prompt_trace.record_event(
                            "trace_attach_failed", role="scene_writer", error=str(exc)
                        )
                if mode == "rewrite":
                    self.engine.clear_context()
                return write_from_prompt(self.engine, prompt, on_delta=emit)
            except GenerationInterrupted as exc:
                trace_status = "interrupted"
                trace_error = str(exc)
                raise
            except Exception as exc:
                trace_status = "failed"
                trace_error = str(exc)
                raise
            finally:
                self._finish_prompt_trace(
                    prompt_trace, status=trace_status, error=trace_error
                )
        self._task_kind = "write"
        self.run_task(work, streaming=True, label=f"{mode.title()} with {writer}…")

    def task_succeeded(self, result):
        kind = getattr(self, "_task_kind", "")
        if kind == "novel_sync":
            selected_name = self.novel_picker.currentText()
            sync_message = getattr(result, "message", "Novel sync completed.")
            self.refresh_novels()
            if selected_name in self.novel_packages:
                self.novel_picker.setCurrentText(selected_name)
                self.on_novel_changed(selected_name)
            self.status.setText(sync_message)
        elif kind == "scene_state":
            novel_name, chapter, scene = self._saved_scene_state_target or ("Novel", 1, 1)
            story_time = str((result or {}).get("story_time", "") or "")
            reset_error = self._scene_state_reset_error or (result or {}).get("reset_error")
            message = (
                f"Saved new scene and updated its ending state: {novel_name} / "
                f"Chapter {chapter:02d} / Scene {scene:02d}."
            )
            if story_time:
                message += f" Story time: {story_time}."
            if reset_error:
                message += " The model session could not be cleared after the state update; reload the model before writing again."
                self.loaded_model = None
            self.status.setText(message)
            self._scene_state_reset_error = None
        elif kind == "openrouter_refresh":
            models = list(result or [])
            self.refresh_models()
            free_count = sum(
                1 for item in models
                if str(item.get("id", "")).endswith(":free")
            )
            if getattr(self, "_openrouter_status_label", None) is not None:
                self._openrouter_status_label.setText(
                    f"Catalogue refreshed. {free_count} pinned free models and the "
                    "automatic free-model router are now available in both selectors."
                )
            self.status.setText("OpenRouter model catalogue refreshed.")
            if getattr(self, "_openrouter_refresh_button", None) is not None:
                self._openrouter_refresh_button.setEnabled(True)
            if getattr(self, "_openrouter_remove_button", None) is not None:
                self._openrouter_remove_button.setEnabled(True)
        elif kind == "load":
            self.model_status.setText(f"Loaded: {result}")
            self.status.setText("Writing model loaded and ready.")
        elif kind == "prepare":
            current_prompt = self.prompt_editor.toPlainText()
            current_author = self.author_direction.toPlainText().strip()
            if (
                current_prompt != self._scene_preparation_original_prompt
                or current_author != self._scene_preparation_original_author_direction
            ):
                self._discard_scene_prompt_trace(self._active_scene_preparation_trace)
                self._active_scene_preparation_trace = None
                self.status.setText(
                    "The prompt or Author's Direction changed during preparation. "
                    "Your edits were kept; prepare again to get a new suggestion."
                )
            else:
                suggestion = apply_author_required_beats(
                    str(result or ""), self._pending_planner_author
                )
                self.prompt_editor.setPlainText(suggestion)
                chapter, scene = self._pending_target
                self.prepared_destination = (chapter, scene)
                self.prepared_novel = self.novel_packages.get(self.novel_picker.currentText())
                self.prepared_source = self.scene_files.get(self.scene_picker.currentText())
                self._prepared_author_required_direction = (
                    self._scene_preparation_required_author_direction
                )
                self._select_destination(chapter, scene)
                self._pending_scene_prompt_trace = self._active_scene_preparation_trace
                self._active_scene_preparation_trace = None
                self.status.setText(
                    f"Prepared Chapter {chapter:02d}, Scene {scene:02d}. "
                    "Review the direction, then press Write."
                )
        elif kind == "revision":
            self.busy = False
            self.output_editor.setReadOnly(False)
            proposal = str(result or "").strip()
            if not proposal:
                self._clear_revision_state()
                self.error(
                    "Empty revision",
                    "The model returned no revised text. The original passage was kept.",
                )
                self.status.setText("Revision returned no text. The original passage was kept.")
            else:
                self._show_revision_review(proposal)
        elif kind == "write":
            if isinstance(result, str) and result and not self._streamed:
                if self._generation_mode == "continue":
                    self.output_editor.setPlainText(self._generation_prefix + result)
                else:
                    self.output_editor.setPlainText(result)
            self.status.setText(
                "Generation finished. Review and edit the draft before saving."
                + self._prompt_trace_status_note()
            )
        else:
            self.status.setText("Task finished.")
        self.busy = False
        self.update_controls()

    def _select_destination(self, chapter: int, scene: int):
        chapter_label = f"Chapter {chapter:02d}"
        if chapter_label not in self.chapter_numbers:
            self.chapter_numbers[chapter_label] = chapter
            self.chapter_picker.addItem(chapter_label)
        self.chapter_picker.setCurrentText(chapter_label)
        scene_label = f"Scene {scene:02d}"
        if self.scene_picker.findText(scene_label) < 0:
            self.scene_picker.addItem(scene_label)
        self.scene_picker.setCurrentText(scene_label)

    def stop_task(self):
        if not self.busy:
            return
        self.status.setText("Stopping model task…")
        try:
            self.engine.interrupt_generation()
        except Exception:
            self.engine.stop()

    def new_session(self):
        if self.busy:
            return
        try:
            self.engine.clear_context()
            self.status.setText("Model conversation cleared.")
        except Exception as exc:
            self.error("Could not clear model session", str(exc))
        self.update_controls()

    def open_document(self):
        if self.busy:
            return
        filename, _ = QFileDialog.getOpenFileName(self, "Open document", "", "Documents (*.odt *.txt);;All files (*)")
        if not filename:
            return
        try:
            text = read_document(filename)
        except Exception as exc:
            self.error("Could not open document", str(exc))
            return
        self.current_file = Path(filename).resolve()
        self.selected_scene_source = None
        self.saved_text = text
        self.output_editor.setPlainText(text)
        self.status.setText(f"Opened {self.current_file}")

    def save_document(self):
        if self.busy:
            return False
        if self.current_file is None:
            return self.save_document_as()
        return self._save_to_path(self.current_file)

    def save_document_as(self):
        if self.busy:
            return False
        default = self.current_file.name if self.current_file else "draft.odt"
        filename, _ = QFileDialog.getSaveFileName(self, "Save document as", default, "LibreOffice Writer (*.odt);;Plain text (*.txt)")
        if not filename:
            return False
        return self._save_to_path(Path(filename))

    def _save_to_path(self, path: Path):
        try:
            saved = save_document(path, self.output_editor.toPlainText())
        except Exception as exc:
            self.error("Could not save document", str(exc))
            return False
        self.current_file = saved
        self.selected_scene_source = None
        self.saved_text = self.output_editor.toPlainText()
        self.status.setText(f"Saved {saved}")
        return True

    def load_scene_copy(self):
        label = self.scene_picker.currentText()
        path = self.scene_files.get(label)
        if path is None:
            return
        try:
            text = read_document(path)
        except Exception as exc:
            self.error("Could not load scene", str(exc))
            return
        self.selected_scene_source = path.resolve()
        self.current_file = None
        self.saved_text = text
        self.output_editor.setPlainText(text)
        self.status.setText(f"Loaded a copy of {path.name}. Use Save New Scene or explicitly overwrite the selected scene.")

    def save_new_scene(self):
        if self.busy:
            return False
        novel_name = self.novel_picker.currentText().strip()
        novel = self.novel_packages.get(novel_name)
        chapter = self.chapter_numbers.get(self.chapter_picker.currentText())
        text = self.output_editor.toPlainText()
        if novel is None or chapter is None:
            self.info("Choose a destination", "Select a novel and chapter first.")
            return False
        if not text.strip():
            self.info("Nothing to save", "Write or open scene text first.")
            return False
        folder = novel / "Manuscript" / "Chapters" / f"Chapter_{chapter:02d}"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            existing = list_scene_files(novel, chapter)
            saved_numbers = {number for number, _path in existing}
            requested = scene_number_from_label(self.scene_picker.currentText())
            if requested is None or requested in saved_numbers:
                number = max(saved_numbers, default=0) + 1
            else:
                number = requested
            while (
                (folder / f"Chapter_{chapter:02d}_Section_{number:02d}.odt").exists()
                or (folder / f"Chapter_{chapter:02d}_Section_{number:02d}.txt").exists()
            ):
                number += 1
            target = folder / f"Chapter_{chapter:02d}_Section_{number:02d}.odt"
            saved = save_document(target, text)
        except Exception as exc:
            self.error("Could not save new scene", str(exc))
            return False
        self._discard_scene_prompt_trace()
        self._prepared_author_required_direction = ""
        self.prepared_destination = None
        self.prepared_novel = None
        self.prepared_source = None
        self.selected_scene_source = saved.resolve()
        self.current_file = None
        self.saved_text = text
        self.on_chapter_changed(self.chapter_picker.currentText())
        self._select_destination(chapter, number)
        self.status.setText(f"Saved new scene: {saved}")
        self._start_saved_scene_state_update(novel, novel_name, chapter, number, text)
        return True

    def _start_saved_scene_state_update(
        self, novel_path: str | Path, novel_name: str,
        chapter_number: int, scene_number: int, scene_text: str,
    ):
        """Record the accepted scene position before optionally analyzing its ending."""
        state_path = Path(novel_path).expanduser() / "current_state.json"
        try:
            current_state = load_current_state(state_path)
            marked_state = advance_saved_scene_markers(
                current_state, chapter_number, scene_number
            )
            write_current_state(state_path, marked_state)
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            self.status.setText(
                f"Scene saved, but current_state.json could not be updated: {exc}"
            )
            return

        model_path = self.loaded_model
        if model_path is None or getattr(self.engine, "active_selection", None) is None:
            self.model_status.setText("Scene position recorded. Load a model to analyze the ending state.")
            self.status.setText(
                f"Saved new scene: {novel_name} / Chapter {chapter_number:02d} / "
                f"Scene {scene_number:02d}. Scene progress was recorded; load a model "
                "to analyze the ending time and situation."
            )
            return

        self._saved_scene_state_target = (
            str(novel_name), int(chapter_number), int(scene_number)
        )
        self._task_kind = "scene_state"

        def work(_emit):
            before_state = load_current_state(state_path)
            prompt = build_saved_scene_state_prompt(
                before_state, chapter_number, scene_number, scene_text
            )
            reset_error = None
            try:
                self.engine.clear_context()
                response = self.engine.generate(prompt)
                characters = (
                    before_state.get("scene_cast")
                    if isinstance(before_state.get("scene_cast"), list)
                    else None
                )
                patch = parse_saved_scene_state_patch(
                    before_state, response, scene_characters=characters
                )
                updated_state = merge_saved_scene_state(
                    before_state, patch, chapter_number, scene_number
                )
                write_current_state(state_path, updated_state)
                story_time = str(updated_state.get("time_of_day", "") or "")

                # Create a separate, factual continuity handoff from the full accepted scene.
                handoff_status = "not_created"
                try:
                    scene_path = None
                    for saved_number, saved_path in list_scene_files(Path(novel_path).expanduser(), chapter_number):
                        if int(saved_number) == int(scene_number):
                            scene_path = saved_path
                            break
                    if scene_path is not None and Path(scene_path).is_file():
                        handoff_prompt = build_handoff_extraction_prompt(
                            chapter_number, scene_number, scene_text
                        )
                        self.engine.clear_context()
                        handoff_response = self.engine.generate(handoff_prompt)
                        parsed_handoff = parse_handoff_response(handoff_response)
                        if parsed_handoff:
                            save_scene_handoff(scene_path, scene_text, parsed_handoff)
                            handoff_status = "created"
                        else:
                            handoff_status = "invalid_response"
                    else:
                        handoff_status = "scene_file_not_found"
                except Exception as handoff_exc:
                    handoff_status = f"failed: {handoff_exc}"

                return {
                    "story_time": story_time,
                    "reset_error": None,
                    "handoff_status": handoff_status,
                }
            finally:
                try:
                    self.engine.clear_context()
                except Exception as exc:
                    reset_error = str(exc)
                if reset_error:
                    self._scene_state_reset_error = reset_error

        self._scene_state_reset_error = None
        self.run_task(
            work,
            label=f"Updating ending state from Chapter {chapter_number:02d}, Scene {scene_number:02d}…",
        )


    def save_to_selected_scene(self):
        if self.busy or self.selected_scene_source is None:
            self.info("Load a scene first", "Use Load Scene Copy before overwriting a selected manuscript scene.")
            return False
        target = self.scene_files.get(self.scene_picker.currentText())
        if target is None:
            self.error("Scene unavailable", "Choose an existing manuscript scene to overwrite.")
            return False
        target = target.expanduser().resolve()
        if not target.is_file():
            self.error("Scene unavailable", "The selected manuscript scene no longer exists.")
            return False

        loaded_source = self.selected_scene_source.expanduser().resolve()
        warning = (
            "This replaces the existing scene file with the text currently in the editor:"
            f"\n\n{target}\n\nCancel to leave the file untouched."
        )
        if loaded_source != target:
            warning += f"\n\nThis is different from the scene originally loaded:\n{loaded_source}"
        if not self.confirm("Confirm scene overwrite", warning):
            self.status.setText("Save to Selected Scene cancelled; no file changed.")
            return False

        # Recheck after confirmation to avoid accidentally recreating a removed scene.
        if not target.is_file():
            self.error("Scene unavailable", f"The selected scene file no longer exists:\n\n{target}")
            return False
        text = self.output_editor.toPlainText()
        try:
            saved = save_document(target, text)
        except Exception as exc:
            self.error("Could not save scene", str(exc))
            return False

        # Ordinary Save remains Save As after writing into a manuscript scene.
        self.current_file = None
        self.selected_scene_source = saved.resolve()
        self.saved_text = text
        self.status.setText(f"Updated selected scene: {saved}. Ordinary Save still opens Save As.")
        return True

    def assemble_chapter(self):
        novel = self.novel_packages.get(self.novel_picker.currentText())
        chapter = self.chapter_numbers.get(self.chapter_picker.currentText())
        if novel is None or chapter is None:
            return
        try:
            result = assemble_chapter_document(novel, chapter)
            self.info("Chapter assembled", str(result))
        except Exception as exc:
            self.error("Could not assemble chapter", str(exc))

    def assemble_novel(self):
        novel = self.novel_packages.get(self.novel_picker.currentText())
        if novel is None:
            return
        try:
            result = assemble_finished_novel_document(novel)
            self.info("Novel assembled", str(result))
        except Exception as exc:
            self.error("Could not assemble novel", str(exc))

    def update_controls(self, *_):
        idle = not self.busy
        for widget in (self.planner_picker, self.writer_picker, self.refresh_models_button, self.openrouter_settings_button, self.refresh_novels_button, self.sync_novel_button, self.novel_picker, self.chapter_picker, self.scene_picker, self.cast_button, self.prepare_button, self.write_button, self.minimal_button, self.full_button, self.rewrite_button, self.continue_button, self.new_session_button, self.open_button, self.save_button, self.save_as_button, self.save_new_scene_button, self.save_scene_button, self.assemble_chapter_button, self.assemble_novel_button, self.revise_button, self.check_draft_button):
            widget.setEnabled(idle)
        self.load_writer_button.setEnabled(idle and self.selected_model("writer") is not None)
        self.stop_button.setEnabled(self.busy and getattr(self, "_task_kind", "") != "openrouter_refresh")
        self.sync_novel_button.setEnabled(idle and self.novel_picker.currentText() in self.novel_packages)
        self.load_scene_button.setEnabled(idle and self.scene_picker.currentText() in self.scene_files)
        self.save_scene_button.setEnabled(idle and self.selected_scene_source is not None and self.scene_picker.currentText() in self.scene_files)
        has_target = self.novel_picker.currentText() in self.novel_packages and self.chapter_picker.currentText() in self.chapter_numbers
        self.save_new_scene_button.setEnabled(idle and has_target)
        self.assemble_chapter_button.setEnabled(idle and has_target and bool(self.scene_files))
        self.assemble_novel_button.setEnabled(idle and bool(self.novel_packages.get(self.novel_picker.currentText())))
        self.prepare_button.setEnabled(idle and self.selected_model("planner") is not None and bool(self.novel_picker.currentText()))
        self.write_button.setEnabled(idle and self.selected_model("writer") is not None)
        self.minimal_button.setEnabled(idle and self.selected_model("writer") is not None)
        self.full_button.setEnabled(idle and self.selected_model("writer") is not None)
        self.rewrite_button.setEnabled(idle and self.selected_model("writer") is not None)
        self.continue_button.setEnabled(idle and self.selected_model("writer") is not None)
        self.revise_button.setEnabled(idle)
        self.check_draft_button.setEnabled(idle and bool(self.output_editor.toPlainText().strip()))

    def closeEvent(self, event: QCloseEvent):
        if self.busy:
            self.info("Model is busy", "Stop or wait for the current task before closing.")
            event.ignore()
            return
        try:
            self.engine.stop()
        except Exception:
            pass
        event.accept()


def main():
    app = QApplication(sys.argv)
    apply_qt_theme(app)
    window = WriterQtWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
