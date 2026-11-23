from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from builder.creative_direction import (
    AUDIENCE_OPTIONS,
    DEFAULT_CREATIVE_DIRECTION,
    GENRE_OPTIONS,
    MOOD_OPTIONS,
    format_creative_direction_preview,
    normalize_creative_direction,
)
from builder.novel_browser import list_novel_packages
from builder.novel_creator import create_novel_package, suggest_folder_name
from builder.novel_git_sync import (
    NovelGitSyncError,
    inspect_novel_repository,
    sync_novel_repository,
)
from builder.qt_story_bible_editors import (
    CharacterCardsManagerDialog,
    CreativeDirectionDialog,
    LocationManagerDialog,
    TextEditorDialog,
)
from builder.story_bible_reader import (
    load_story_bible,
    save_story_bible_canon_rules,
    save_story_bible_creative_direction,
    save_story_bible_text_field,
)
from builder.workspace import NOVEL_ROOT
from builder.qt_theme import apply_qt_theme


class NovelSyncWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, novel_path: Path):
        super().__init__()
        self.novel_path = novel_path

    def run(self) -> None:
        try:
            result = sync_novel_repository(self.novel_path)
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)


class StoryBibleQtWindow(QMainWindow):
    """PySide6 presentation layer for the existing Story Bible package tools."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("StoryBuilder | Story Bible")
        self.resize(1040, 860)
        self.setMinimumSize(780, 620)
        self.novel_paths: list[Path] = []
        self.loaded_novel_path: Path | None = None
        self.loaded_data: dict[str, Any] | None = None
        self._folder_was_customized = False
        self.sync_worker: NovelSyncWorker | None = None

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(14, 14, 14, 10)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        self._build_create_tab()
        self._build_view_tab()
        self.statusBar().showMessage(
            f"Ready. Novel library: {NOVEL_ROOT}"
        )
        self.refresh_novels()

    def _scroll_tab(self, title: str) -> tuple[QScrollArea, QVBoxLayout]:
        area = QScrollArea()
        area.setWidgetResizable(True)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        area.setWidget(page)
        self.tabs.addTab(area, title)
        return area, layout

    def _build_create_tab(self) -> None:
        _area, layout = self._scroll_tab("Create Novel")
        heading = QLabel("Create a Novel Package")
        heading.setStyleSheet("font-size: 17pt; font-weight: 650;")
        layout.addWidget(heading)
        intro = QLabel(
            "Create an empty Story Bible and the manuscript folder structure used by the Writer. "
            "No story content is invented and existing folders are never overwritten."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Novel title")
        self.title_input.textChanged.connect(self._suggest_folder)
        form.addRow("Novel title", self.title_input)
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Optional. Generated from the title when blank.")
        self.folder_input.textEdited.connect(self._mark_folder_custom)
        form.addRow("Folder name (optional)", self.folder_input)
        library = QLineEdit(str(NOVEL_ROOT))
        library.setReadOnly(True)
        form.addRow("Novel library", library)
        layout.addLayout(form)

        self.genre_checks: dict[str, QCheckBox] = {}
        self.mood_checks: dict[str, QCheckBox] = {}
        direction_box = QGroupBox("Genre & Mood (optional)")
        direction_layout = QGridLayout(direction_box)
        genre_box = QGroupBox("Genre")
        genre_layout = QGridLayout(genre_box)
        for index, name in enumerate(GENRE_OPTIONS):
            check = QCheckBox(name)
            self.genre_checks[name] = check
            genre_layout.addWidget(check, index // 2, index % 2)
        mood_box = QGroupBox("Mood & Tone")
        mood_layout = QGridLayout(mood_box)
        for index, name in enumerate(MOOD_OPTIONS):
            check = QCheckBox(name)
            self.mood_checks[name] = check
            mood_layout.addWidget(check, index // 2, index % 2)
        direction_layout.addWidget(genre_box, 0, 0)
        direction_layout.addWidget(mood_box, 0, 1)
        audience_row = QHBoxLayout()
        audience_row.addWidget(QLabel("Intended audience"))
        self.create_audience = QComboBox()
        self.create_audience.addItem("Not specified", "")
        for name in AUDIENCE_OPTIONS:
            self.create_audience.addItem(name, name)
        self.create_audience.currentIndexChanged.connect(self._update_create_explicit)
        audience_row.addWidget(self.create_audience, 1)
        direction_layout.addLayout(audience_row, 1, 0, 1, 2)
        self.create_explicit = QCheckBox("Explicit Adult Content (consenting adults only)")
        self.create_explicit.setEnabled(False)
        direction_layout.addWidget(self.create_explicit, 2, 0, 1, 2)
        note = QLabel("These choices guide the novel's overall flavor, not every scene. Leave anything blank when undecided.")
        note.setWordWrap(True)
        direction_layout.addWidget(note, 3, 0, 1, 2)
        layout.addWidget(direction_box)

        self.create_button = QPushButton("Create Novel Package")
        self.create_button.clicked.connect(self.create_novel)
        layout.addWidget(self.create_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.create_status = QLabel(
            "Ready. Creating a package will not overwrite existing files."
        )
        self.create_status.setWordWrap(True)
        layout.addWidget(self.create_status)
        layout.addStretch(1)

    def _build_view_tab(self) -> None:
        _area, layout = self._scroll_tab("View Story Bible")
        heading = QLabel("View and Edit a Novel's Story Bible")
        heading.setStyleSheet("font-size: 17pt; font-weight: 650;")
        layout.addWidget(heading)

        toolbar = QHBoxLayout()
        self.novel_selector = QComboBox()
        self.novel_selector.setMinimumWidth(260)
        self.novel_selector.currentIndexChanged.connect(self._selection_changed)
        toolbar.addWidget(self.novel_selector, 1)
        self.refresh_button = QPushButton("Refresh Novels")
        self.refresh_button.clicked.connect(self.refresh_novels)
        toolbar.addWidget(self.refresh_button)
        self.load_button = QPushButton("Load Story Bible")
        self.load_button.clicked.connect(self.load_selected_story_bible)
        toolbar.addWidget(self.load_button)
        self.sync_button = QPushButton("Sync Selected Novel to GitHub")
        self.sync_button.clicked.connect(self.sync_selected_novel_to_github)
        toolbar.addWidget(self.sync_button)
        layout.addLayout(toolbar)

        self.field_previews: dict[str, QPlainTextEdit] = {}
        self.field_buttons: dict[str, QPushButton] = {}
        self.field_groups: dict[str, QGroupBox] = {}

        self._add_text_preview(layout, "premise", "Premise", "Edit Premise")
        self._add_text_preview(layout, "setting", "Setting", "Edit Setting")
        self._add_text_preview(
            layout, "writing_preferences", "Writing Preferences",
            "Edit Writing Preferences",
        )

        self.creative_group = QGroupBox("Genre & Mood")
        creative_layout = QVBoxLayout(self.creative_group)
        self.creative_preview = QPlainTextEdit()
        self.creative_preview.setReadOnly(True)
        self.creative_preview.setMaximumHeight(90)
        creative_layout.addWidget(self.creative_preview)
        self.edit_creative_button = QPushButton("Edit Genre & Mood")
        self.edit_creative_button.clicked.connect(self.edit_creative_direction)
        creative_layout.addWidget(self.edit_creative_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.creative_group)

        self.canon_group = QGroupBox("Canon Rules")
        canon_layout = QVBoxLayout(self.canon_group)
        self.canon_preview = QPlainTextEdit()
        self.canon_preview.setReadOnly(True)
        self.canon_preview.setMaximumHeight(115)
        canon_layout.addWidget(self.canon_preview)
        self.edit_canon_button = QPushButton("Edit Canon Rules")
        self.edit_canon_button.clicked.connect(self.edit_canon_rules)
        canon_layout.addWidget(self.edit_canon_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.canon_group)

        self.cards_group = QGroupBox("Character Cards")
        cards_layout = QVBoxLayout(self.cards_group)
        self.cards_preview = QPlainTextEdit()
        self.cards_preview.setReadOnly(True)
        self.cards_preview.setMaximumHeight(100)
        cards_layout.addWidget(self.cards_preview)
        self.manage_cards_button = QPushButton("Manage Character Cards")
        self.manage_cards_button.clicked.connect(self.manage_character_cards)
        cards_layout.addWidget(self.manage_cards_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.cards_group)

        self.locations_group = QGroupBox("Locations")
        locations_layout = QVBoxLayout(self.locations_group)
        self.locations_preview = QPlainTextEdit()
        self.locations_preview.setReadOnly(True)
        self.locations_preview.setMaximumHeight(100)
        locations_layout.addWidget(self.locations_preview)
        self.manage_locations_button = QPushButton("Manage Locations")
        self.manage_locations_button.clicked.connect(self.manage_locations)
        locations_layout.addWidget(self.manage_locations_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.locations_group)

        self.json_group = QGroupBox("Complete Story Bible (read-only)")
        json_layout = QVBoxLayout(self.json_group)
        self.json_preview = QPlainTextEdit()
        self.json_preview.setReadOnly(True)
        self.json_preview.setMinimumHeight(260)
        self.json_preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        json_layout.addWidget(self.json_preview)
        json_note = QLabel("Read-only reference view. Use the field-specific editors above to make changes.")
        json_note.setWordWrap(True)
        json_layout.addWidget(json_note)
        layout.addWidget(self.json_group)
        layout.addStretch(1)
        self._set_loaded_controls(False)

    def _add_text_preview(
        self, parent_layout: QVBoxLayout, key: str, title: str, button_text: str
    ) -> None:
        group = QGroupBox(title)
        group_layout = QVBoxLayout(group)
        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        preview.setMaximumHeight(105)
        preview.setPlaceholderText("Not loaded.")
        button = QPushButton(button_text)
        button.clicked.connect(lambda _checked=False, field=key: self.edit_text_field(field))
        group_layout.addWidget(preview)
        group_layout.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)
        parent_layout.addWidget(group)
        self.field_previews[key] = preview
        self.field_buttons[key] = button
        self.field_groups[key] = group

    def _suggest_folder(self, title: str) -> None:
        if not self._folder_was_customized:
            self.folder_input.setText(suggest_folder_name(title))

    def _mark_folder_custom(self, _value: str) -> None:
        self._folder_was_customized = True

    def _update_create_explicit(self) -> None:
        is_adult = self.create_audience.currentData() == "Adult"
        self.create_explicit.setEnabled(is_adult)
        if not is_adult:
            self.create_explicit.setChecked(False)

    def create_novel(self) -> None:
        title = self.title_input.text().strip()
        if not title:
            self.create_status.setText("Enter a title for the new novel.")
            self.title_input.setFocus()
            return
        direction = {
            "genres": [name for name, check in self.genre_checks.items() if check.isChecked()],
            "moods": [name for name, check in self.mood_checks.items() if check.isChecked()],
            "audience": self.create_audience.currentData() or "",
            "explicit_adult_content": self.create_explicit.isChecked(),
        }
        try:
            package = create_novel_package(
                title,
                self.folder_input.text(),
                novel_root=NOVEL_ROOT,
                creative_direction=direction,
            )
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Could not create novel", str(exc))
            self.create_status.setText("Novel package was not created. Existing files were not changed.")
            return
        self.create_status.setText(
            f"Created successfully:\n{package}\n\nOpen View Story Bible and click Refresh Novels. No files were overwritten."
        )
        self.title_input.clear()
        self.folder_input.clear()
        self._folder_was_customized = False
        for check in (*self.genre_checks.values(), *self.mood_checks.values()):
            check.setChecked(False)
        self.create_audience.setCurrentIndex(0)
        self.create_explicit.setChecked(False)
        self.refresh_novels()
        self.statusBar().showMessage(f"Created novel package: {package}", 8000)

    def refresh_novels(self) -> None:
        previous = self._selected_novel_path()
        try:
            packages = list_novel_packages(NOVEL_ROOT)
        except OSError as exc:
            QMessageBox.warning(self, "Could not read novel library", str(exc))
            packages = []
        self.novel_paths = list(packages)
        self.novel_selector.blockSignals(True)
        self.novel_selector.clear()
        for package in packages:
            self.novel_selector.addItem(f"{package.name}  [{package}]", str(package))
        if previous:
            index = self.novel_selector.findData(str(previous))
            if index >= 0:
                self.novel_selector.setCurrentIndex(index)
        self.novel_selector.blockSignals(False)
        self._clear_loaded()
        if packages:
            self.statusBar().showMessage(
                f"Found {len(packages)} novel package(s). Select one and click Load Story Bible."
            )
        else:
            self.statusBar().showMessage(
                f"No novel packages with story_bible.json were found in {NOVEL_ROOT}."
            )

    def _selected_novel_path(self) -> Path | None:
        value = self.novel_selector.currentData()
        return Path(value) if value else None

    def _selection_changed(self, _index: int) -> None:
        self._clear_loaded()
        if self._selected_novel_path():
            self.statusBar().showMessage("Novel selected. Click Load Story Bible to view it.")
        else:
            self.statusBar().showMessage("Choose a novel package.")

    def _clear_loaded(self) -> None:
        self.loaded_novel_path = None
        self.loaded_data = None
        for preview in self.field_previews.values():
            preview.clear()
            preview.setPlaceholderText("Load a Story Bible to view this field.")
        self.creative_preview.clear()
        self.canon_preview.clear()
        self.cards_preview.clear()
        self.locations_preview.clear()
        self.json_preview.clear()
        self._set_loaded_controls(False)

    def _set_loaded_controls(self, enabled: bool) -> None:
        for key, button in self.field_buttons.items():
            button.setEnabled(enabled and isinstance(self.loaded_data.get(key), str) if enabled and self.loaded_data else False)
        self.edit_creative_button.setEnabled(enabled)
        self.edit_canon_button.setEnabled(enabled and isinstance(self.loaded_data.get("canon_rules"), list) if enabled and self.loaded_data else False)
        self.manage_cards_button.setEnabled(enabled and isinstance(self.loaded_data.get("character_cards", []), list) if enabled and self.loaded_data else False)
        self.manage_locations_button.setEnabled(enabled and isinstance(self.loaded_data.get("locations", {}), dict) if enabled and self.loaded_data else False)
        self.sync_button.setEnabled(enabled and self.sync_worker is None)

    def load_selected_story_bible(self) -> None:
        package = self._selected_novel_path()
        if package is None:
            self.statusBar().showMessage("Choose a novel first.")
            return
        try:
            data = load_story_bible(package)
        except (OSError, ValueError) as exc:
            self._clear_loaded()
            QMessageBox.critical(self, "Could not load Story Bible", str(exc))
            self.statusBar().showMessage("Story Bible could not be loaded. No file was changed.")
            return

        self.loaded_novel_path = package
        self.loaded_data = data
        for key, preview in self.field_previews.items():
            value = data.get(key, "")
            preview.setPlainText(value if isinstance(value, str) else f"Cannot edit: {key} is not text.")
        creative = normalize_creative_direction(data.get("creative_direction"), strict=False)
        self.creative_preview.setPlainText(format_creative_direction_preview(creative))

        rules = data.get("canon_rules", [])
        if isinstance(rules, list) and all(isinstance(item, str) for item in rules):
            self.canon_preview.setPlainText(
                "\n".join(f"• {item}" for item in rules) if rules else "No canon rules have been added yet."
            )
        else:
            self.canon_preview.setPlainText("Canon Rules use an unsupported structure. Editing is disabled to preserve the data.")

        cards = data.get("character_cards", [])
        if isinstance(cards, list):
            self.cards_preview.setPlainText(
                "\n".join(
                    str(item.get("name") or "Unnamed Character") if isinstance(item, dict)
                    else (Path(item).stem if isinstance(item, str) and item.lower().endswith(".json") else str(item))
                    for item in cards
                ) or "No Character Cards have been added yet."
            )
        else:
            self.cards_preview.setPlainText("Character Cards use an unsupported structure.")

        locations = data.get("locations", {})
        if isinstance(locations, dict):
            self.locations_preview.setPlainText(
                "\n".join(locations) if locations else "No named locations have been added yet."
            )
        else:
            self.locations_preview.setPlainText("Locations use an unsupported structure.")

        self.json_preview.setPlainText(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        self._set_loaded_controls(True)
        self.statusBar().showMessage(f"Loaded read-only: {package / 'story_bible.json'}")

    def _reload_after_edit(self, success_message: str) -> None:
        current = self.loaded_novel_path
        if current is not None:
            index = self.novel_selector.findData(str(current))
            if index >= 0:
                self.novel_selector.blockSignals(True)
                self.novel_selector.setCurrentIndex(index)
                self.novel_selector.blockSignals(False)
            self.load_selected_story_bible()
            self.statusBar().showMessage(success_message, 9000)

    def _save_text_field(self, field: str, value: str) -> None:
        if self.loaded_novel_path is None:
            return
        try:
            save_story_bible_text_field(self.loaded_novel_path, field, value)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, f"{field.replace('_', ' ').title()} was not saved", str(exc))
            return
        self._reload_after_edit(
            f"Saved {field.replace('_', ' ').title()} only. Other Story Bible fields were preserved."
        )

    def edit_text_field(self, field: str) -> None:
        if self.loaded_novel_path is None or self.loaded_data is None:
            return
        value = self.loaded_data.get(field)
        if not isinstance(value, str):
            QMessageBox.warning(
                self, "Field cannot be edited",
                f"The saved {field.replace('_', ' ')} value is not text. It was left unchanged.",
            )
            return
        title = {
            "premise": "Edit Premise",
            "setting": "Edit Setting",
            "writing_preferences": "How This Novel Should Read",
        }.get(field, f"Edit {field.replace('_', ' ').title()}")
        dialog = TextEditorDialog(
            title,
            f"{title} for: {self.loaded_novel_path.name}",
            value,
            self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._save_text_field(field, dialog.editor.toPlainText())

    def edit_creative_direction(self) -> None:
        if self.loaded_novel_path is None or self.loaded_data is None:
            return
        dialog = CreativeDirectionDialog(
            self.loaded_data.get("creative_direction", DEFAULT_CREATIVE_DIRECTION),
            "Edit Genre & Mood",
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            save_story_bible_creative_direction(self.loaded_novel_path, dialog.profile)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "Creative Direction was not saved", str(exc))
            return
        self._reload_after_edit("Saved Creative Direction only. Other Story Bible fields were preserved.")

    def edit_canon_rules(self) -> None:
        if self.loaded_novel_path is None or self.loaded_data is None:
            return
        rules = self.loaded_data.get("canon_rules", [])
        if not isinstance(rules, list) or not all(isinstance(item, str) for item in rules):
            QMessageBox.warning(self, "Canon Rules cannot be edited", "Canon Rules are not a list of text entries. Existing data was left unchanged.")
            return
        dialog = TextEditorDialog(
            "Edit Canon Rules",
            "Enter one rule per line. Blank lines are ignored.",
            "\n".join(rules),
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        new_rules = [line.strip() for line in dialog.editor.toPlainText().splitlines() if line.strip()]
        try:
            save_story_bible_canon_rules(self.loaded_novel_path, new_rules)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "Canon Rules were not saved", str(exc))
            return
        self._reload_after_edit("Saved Canon Rules only. Other Story Bible fields were preserved.")

    def manage_character_cards(self) -> None:
        if self.loaded_novel_path is None:
            return
        dialog = CharacterCardsManagerDialog(
            self.loaded_novel_path,
            on_saved=lambda: self._reload_after_edit("Character Cards saved."),
            parent=self,
        )
        dialog.exec()
        self.load_selected_story_bible()

    def manage_locations(self) -> None:
        if self.loaded_novel_path is None:
            return
        dialog = LocationManagerDialog(
            self.loaded_novel_path,
            on_saved=lambda: self._reload_after_edit("Locations saved."),
            parent=self,
        )
        dialog.exec()
        self.load_selected_story_bible()

    def sync_selected_novel_to_github(self) -> None:
        if self.sync_worker is not None:
            return
        package = self._selected_novel_path()
        if package is None:
            self.statusBar().showMessage("Choose a novel before syncing.")
            return
        test_fixture = (Path(NOVEL_ROOT) / "Story-Bible-Save-Test").resolve()
        if package.resolve() == test_fixture:
            self.statusBar().showMessage("Sync blocked: Story-Bible-Save-Test is a local-only test package.")
            QMessageBox.warning(
                self, "Novel sync blocked",
                "Story-Bible-Save-Test is a local-only fixture and must never be published.",
            )
            return
        try:
            preview = inspect_novel_repository(package)
        except (NovelGitSyncError, OSError, ValueError) as exc:
            QMessageBox.critical(self, "Novel sync is not ready", str(exc))
            return

        changed = "\n".join(f"  • {path}" for path in preview.changed_files) or "  (none)"
        commits = "\n".join(f"  • {line}" for line in preview.local_commits) or "  (none)"
        message = (
            f"Novel folder:\n{preview.repository}\n\n"
            f"Branch:\n{preview.branch}\n\n"
            f"Upstream:\n{preview.upstream}\n\n"
            f"GitHub remote:\n{preview.remote_url}\n\n"
            f"Local commits ahead:\n{commits}\n\n"
            f"Changed files:\n{changed}\n\n"
            "This action operates only inside the selected novel's Git repository. "
            "It will fast-forward when safe, then commit and push selected-novel changes. "
            "Protected secret/encrypted paths and divergent history block synchronization."
        )
        confirm = QMessageBox(self)
        confirm.setIcon(QMessageBox.Icon.Warning)
        confirm.setWindowTitle("Confirm Novel Sync")
        confirm.setText("Review the exact novel repository and changes before syncing.")
        confirm.setInformativeText(message)
        confirm.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        confirm.setEscapeButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            self.statusBar().showMessage("Novel sync cancelled. No Git operation was started.")
            return

        self.sync_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.load_button.setEnabled(False)
        self.statusBar().showMessage(f"Syncing {package.name} to GitHub...")
        self.sync_worker = NovelSyncWorker(package)
        self.sync_worker.succeeded.connect(self._sync_succeeded)
        self.sync_worker.failed.connect(self._sync_failed)
        self.sync_worker.finished.connect(self._sync_thread_finished)
        self.sync_worker.start()

    def _sync_succeeded(self, result: Any) -> None:
        self.statusBar().showMessage(result.message, 15000)
        self.refresh_novels()
        index = self.novel_selector.findData(str(result.repository))
        if index >= 0:
            self.novel_selector.setCurrentIndex(index)
            self.load_selected_story_bible()
        QMessageBox.information(self, "Novel Sync Complete", result.message)

    def _sync_failed(self, message: str) -> None:
        self.statusBar().showMessage("Novel sync failed. Review the error before retrying.")
        QMessageBox.critical(self, "Novel sync failed", message)

    def _sync_thread_finished(self) -> None:
        worker = self.sync_worker
        self.sync_worker = None
        if worker is not None:
            worker.deleteLater()
        self.refresh_button.setEnabled(True)
        self.load_button.setEnabled(True)
        self.sync_button.setEnabled(self.loaded_novel_path is not None)

    def closeEvent(self, event) -> None:
        if self.sync_worker is not None and self.sync_worker.isRunning():
            QMessageBox.warning(
                self, "Novel sync is still running",
                "Wait for the selected novel's Git operation to finish before closing Story Bible.",
            )
            event.ignore()
            return
        event.accept()


def main() -> int:
    application = QApplication(sys.argv)
    apply_qt_theme(application)
    window = StoryBibleQtWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
