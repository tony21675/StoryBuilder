from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout,
    QWidget, QGroupBox, QFormLayout, QInputDialog
)

from builder.qt_theme import apply_qt_theme
from builder.workspace import MODELS_DIR, NOVEL_ROOT
from builder.writer_engine import WriterEngine, GenerationInterrupted
from builder.openrouter import (
    RoutedWriterEngine, has_openrouter_api_key, load_cached_openrouter_models,
    is_openrouter_selection, openrouter_model_selection
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
from builder.odt_document import read_document, save_document
from builder.manuscript_assembly import assemble_chapter as assemble_chapter_document, assemble_finished_novel as assemble_finished_novel_document
from minimal_writer import load_model_for_writing, write_from_prompt


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
        self.model_status = QLabel("Only the model needed for the selected task is loaded.")
        model_form.addRow("Prepare Scene model", self.planner_picker)
        writer_row = QHBoxLayout()
        writer_row.addWidget(self.writer_picker, 1)
        writer_row.addWidget(self.refresh_models_button)
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
        self.load_scene_button = QPushButton("Load Scene Copy")
        project_row.addWidget(QLabel("Novel"))
        project_row.addWidget(self.novel_picker, 2)
        project_row.addWidget(self.refresh_novels_button)
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
        output_layout.addWidget(QLabel("Output (editable manuscript)"))
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
        self.load_writer_button.clicked.connect(self.load_writer)
        self.load_scene_button.clicked.connect(self.load_scene_copy)
        self.planner_picker.activated.connect(lambda _index: self.save_model_roles())
        self.writer_picker.activated.connect(lambda _index: self.save_model_roles())
        self.refresh_novels_button.clicked.connect(self.refresh_novels)
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
        self.update_controls()

    def info(self, title: str, message: str):
        QMessageBox.information(self, title, message)

    def error(self, title: str, message: str):
        QMessageBox.critical(self, title, message)

    def confirm(self, title: str, message: str) -> bool:
        return QMessageBox.question(self, title, message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

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
        if getattr(self, "_task_kind", "") == "write":
            if getattr(self, "_generation_mode", "") == "rewrite":
                self.output_editor.setPlainText(getattr(self, "_generation_original", ""))
            elif not self._streamed:
                self.output_editor.setPlainText(getattr(self, "_generation_original", ""))
        self.busy = False
        self.status.setText("Task failed. Existing saved files were not changed.")
        self.update_controls()
        self.error("StoryBuilder task failed", message)

    def task_interrupted(self):
        if getattr(self, "_task_kind", "") == "write" and getattr(self, "_generation_mode", "") == "rewrite":
            self.output_editor.setPlainText(getattr(self, "_generation_original", ""))
        self.busy = False
        self.loaded_model = None
        self.model_status.setText("Stopped. Model will reload on the next task.")
        self.status.setText("Stopped. Any streamed partial text remains in the editor.")
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
        self.novel_picker.setCurrentText(previous if previous in self.novel_packages else "")
        self.novel_picker.blockSignals(False)
        self.on_novel_changed(self.novel_picker.currentText())

    def on_novel_changed(self, name: str):
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
        self._pending_planner_author = author
        self._pending_target = (chapter, scene)
        def work(_emit):
            if self.loaded_model != planner or not self._engine_ready():
                load_model_for_writing(self.engine, planner)
                self.loaded_model = planner
            return write_from_prompt(self.engine, prompt).strip()
        self._task_kind = "prepare"
        self.run_task(work, label=f"Preparing Chapter {chapter:02d}, Scene {scene:02d} with Planner…")

    def _engine_ready(self):
        child = getattr(self.engine, "child", None)
        try:
            return child is not None and child.isalive()
        except Exception:
            return False

    def _writer_context(self, prompt: str, profile: str):
        if profile == "minimal":
            return build_scene_cast_boundary_prompt(prompt, self._active_cast())
        name = self.novel_picker.currentText()
        path = self.novel_packages.get(name)
        if path is None:
            return build_scene_cast_boundary_prompt(prompt, self._active_cast())
        bible = load_story_bible(path)
        sections = [prompt]
        creative = build_creative_direction_prompt(bible.get("creative_direction"))
        if creative:
            sections.append(creative)
        preferences = bible.get("writing_preferences")
        if isinstance(preferences, str) and preferences.strip():
            sections.append("HOW THIS NOVEL SHOULD READ\n" + preferences.strip())
        references = build_story_bible_reference_context(bible)
        if references:
            sections.append(references)
        supporting = prompt + "\n" + self.author_direction.toPlainText()
        character_context = build_character_card_context_prompt(
            path, bible, "", supporting_text=supporting,
            compact=True, selected_names=self._active_cast(), scene_focused=True,
        )
        if character_context:
            sections.append(character_context)
        locations = bible.get("locations", {})
        if isinstance(locations, dict):
            relevant = select_relevant_locations(locations, "", supporting)
            if relevant:
                lines = ["RELEVANT SAVED LOCATIONS"]
                for location, detail in relevant.items():
                    lines.append(f"{location}: {detail}")
                sections.append("\n".join(lines))
        chapter = self.chapter_numbers.get(self.chapter_picker.currentText())
        scene = scene_number_from_label(self.scene_picker.currentText())
        if chapter and scene:
            try:
                prior = build_previous_scene_context_prompt("", path, chapter, scene, max_chars=1400)
                if prior.strip():
                    sections.append(prior)
            except Exception:
                pass
        return build_scene_cast_boundary_prompt("\n\n".join(sections), self._active_cast())

    def _active_cast(self):
        path = self.novel_packages.get(self.novel_picker.currentText())
        if self.scene_cast is None or path is None or self.scene_cast_novel != path.resolve():
            return None
        chapter = self.chapter_numbers.get(self.chapter_picker.currentText())
        scene = scene_number_from_label(self.scene_picker.currentText())
        destination = (chapter, scene) if chapter and scene else None
        if self.scene_cast_destination and destination != self.scene_cast_destination:
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
        self._start_generation(self._writer_context(prompt + "\n\nRewrite the scene as a fresh attempt. Follow the direction and author-required beats.", "balanced"), "rewrite")

    def continue_writing(self):
        if self.busy:
            return
        old = self.output_editor.toPlainText()
        if not old.strip():
            self.info("Nothing to continue", "Write or open a passage first.")
            return
        prompt = "Continue the current passage. Write only new material without repeating it. Develop the moment over several connected paragraphs.\n\nCURRENT PASSAGE:\n" + old
        self._start_generation(self._writer_context(prompt, "balanced"), "continue")

    def _start_generation(self, prompt: str, mode: str):
        writer = self.selected_model("writer")
        if writer is None:
            self.info("Choose a writing model", "Select the manuscript-writing model.")
            return
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
            if self.loaded_model != writer or not self._engine_ready():
                load_model_for_writing(self.engine, writer)
                self.loaded_model = writer
            if mode == "rewrite":
                self.engine.clear_context()
            return write_from_prompt(self.engine, prompt, on_delta=emit)
        self._task_kind = "write"
        self.run_task(work, streaming=True, label=f"{mode.title()} with {writer}…")

    def task_succeeded(self, result):
        kind = getattr(self, "_task_kind", "")
        if kind == "load":
            self.model_status.setText(f"Loaded: {result}")
            self.status.setText("Writing model loaded and ready.")
        elif kind == "prepare":
            suggestion = apply_author_required_beats(str(result or ""), getattr(self, "_pending_planner_author", ""))
            self.prompt_editor.setPlainText(suggestion)
            chapter, scene = self._pending_target
            self.prepared_destination = (chapter, scene)
            self.prepared_novel = self.novel_packages.get(self.novel_picker.currentText())
            self.prepared_source = self.scene_files.get(self.scene_picker.currentText())
            self._select_destination(chapter, scene)
            self.status.setText(f"Prepared Chapter {chapter:02d}, Scene {scene:02d}. Review the direction, then press Write.")
        else:
            self.status.setText("Generation finished. Review and edit the draft before saving.")
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
        novel = self.novel_packages.get(self.novel_picker.currentText())
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
            number = max((n for n, _ in existing), default=0) + 1
            while (folder / f"Chapter_{chapter:02d}_Section_{number:02d}.odt").exists() or (folder / f"Chapter_{chapter:02d}_Section_{number:02d}.txt").exists():
                number += 1
            target = folder / f"Chapter_{chapter:02d}_Section_{number:02d}.odt"
            saved = save_document(target, text)
        except Exception as exc:
            self.error("Could not save new scene", str(exc))
            return False
        self.selected_scene_source = saved
        self.current_file = None
        self.saved_text = text
        self.on_chapter_changed(self.chapter_picker.currentText())
        self.scene_picker.setCurrentText(f"Scene {number:02d}")
        self._select_destination(chapter, number)
        self.status.setText(f"Saved new scene: {saved}")
        return True

    def save_to_selected_scene(self):
        if self.busy or self.selected_scene_source is None:
            self.info("Load a scene first", "Use Load Scene Copy before overwriting a selected manuscript scene.")
            return False
        target = self.scene_files.get(self.scene_picker.currentText())
        if target is None or not target.is_file():
            self.error("Scene unavailable", "The selected manuscript scene no longer exists.")
            return False
        if not self.confirm("Confirm scene overwrite", f"This replaces the existing scene file:\n\n{target}\n\nContinue?"):
            return False
        try:
            save_document(target, self.output_editor.toPlainText())
        except Exception as exc:
            self.error("Could not save scene", str(exc))
            return False
        self.status.setText(f"Updated selected scene: {target}")
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
        for widget in (self.planner_picker, self.writer_picker, self.refresh_models_button, self.refresh_novels_button, self.novel_picker, self.chapter_picker, self.scene_picker, self.cast_button, self.prepare_button, self.write_button, self.minimal_button, self.full_button, self.rewrite_button, self.continue_button, self.new_session_button, self.open_button, self.save_button, self.save_as_button, self.save_new_scene_button, self.save_scene_button, self.assemble_chapter_button, self.assemble_novel_button):
            widget.setEnabled(idle)
        self.load_writer_button.setEnabled(idle and self.selected_model("writer") is not None)
        self.stop_button.setEnabled(self.busy)
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
