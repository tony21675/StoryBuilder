from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from builder.creative_direction import (
    AUDIENCE_OPTIONS,
    GENRE_OPTIONS,
    MOOD_OPTIONS,
    normalize_creative_direction,
)
from builder.story_bible_reader import (
    create_story_bible_character_card,
    load_story_bible,
    load_story_bible_character_card,
    load_story_bible_locations,
    remove_story_bible_character_card_reference,
    save_story_bible_character_card_file,
    save_story_bible_character_cards,
    save_story_bible_locations,
)


_STRING_FIELDS = (
    "role",
    "gender",
    "sexual_orientation",
    "relationship_status",
    "occupation",
    "status",
    "nickname_from_tony",
)
_TEXT_FIELDS = (
    "description",
    "background",
    "story_role",
    "protective_nature",
    "knowledge_rule",
)
_LIST_FIELDS = (
    "personality",
    "hobbies",
    "skills",
    "strengths",
    "weaknesses",
    "goals",
    "future_story_role",
    "social",
)
_APPEARANCE_FIELDS = ("height", "build", "hair", "eyes", "style", "notes")
_STANDARD_FIELDS = {
    "name",
    "age",
    "pronouns",
    *_STRING_FIELDS,
    *_TEXT_FIELDS,
    *_LIST_FIELDS,
    "appearance",
    "relationships",
    "school",
    "school_performance",
}


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return _human_readable(value)
    return str(value)


def _human_readable(value: Any, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(value, dict):
        lines = []
        for key, nested in value.items():
            label = str(key).replace("_", " ").title()
            if isinstance(nested, (dict, list)):
                lines.append(f"{prefix}{label}:")
                lines.append(_human_readable(nested, indent + 2))
            else:
                lines.append(f"{prefix}{label}: {_display(nested)}")
        return "\n".join(lines)
    if isinstance(value, list):
        return "\n".join(
            f"{prefix}• {_human_readable(item, indent)}" for item in value
        )
    return f"{prefix}{_display(value)}"


def _scrollable_page(tabs: QTabWidget, title: str) -> tuple[QWidget, QFormLayout]:
    area = QScrollArea()
    area.setWidgetResizable(True)
    page = QWidget()
    form = QFormLayout(page)
    form.setContentsMargins(14, 14, 14, 14)
    form.setVerticalSpacing(10)
    area.setWidget(page)
    tabs.addTab(area, title)
    return page, form


class TextEditorDialog(QDialog):
    """Simple scrollable, selectable plain-text editor."""

    def __init__(self, title: str, label: str, value: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 520)
        self.setMinimumSize(540, 360)
        layout = QVBoxLayout(self)
        heading = QLabel(label)
        heading.setWordWrap(True)
        layout.addWidget(heading)
        self.editor = QPlainTextEdit()
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.editor.setPlainText(value)
        layout.addWidget(self.editor, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class CreativeDirectionDialog(QDialog):
    def __init__(
        self,
        current: dict[str, Any],
        title: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 560)
        self.setMinimumSize(560, 440)
        self.current = normalize_creative_direction(current, strict=False)
        self.genre_checks: dict[str, QCheckBox] = {}
        self.mood_checks: dict[str, QCheckBox] = {}

        outer = QVBoxLayout(self)
        heading = QLabel("Choose only what is useful. These are broad guidance, not scene checklists.")
        heading.setWordWrap(True)
        outer.addWidget(heading)
        columns = QHBoxLayout()
        outer.addLayout(columns, 1)

        genre_area = QScrollArea()
        genre_area.setWidgetResizable(True)
        genre_page = QWidget()
        genre_layout = QVBoxLayout(genre_page)
        for name in GENRE_OPTIONS:
            check = QCheckBox(name)
            check.setChecked(name in self.current["genres"])
            self.genre_checks[name] = check
            genre_layout.addWidget(check)
        genre_layout.addStretch(1)
        genre_area.setWidget(genre_page)
        genre_box = QWidget()
        genre_box_layout = QVBoxLayout(genre_box)
        genre_box_layout.addWidget(QLabel("Genre"))
        genre_box_layout.addWidget(genre_area)
        columns.addWidget(genre_box, 1)

        mood_area = QScrollArea()
        mood_area.setWidgetResizable(True)
        mood_page = QWidget()
        mood_layout = QVBoxLayout(mood_page)
        for name in MOOD_OPTIONS:
            check = QCheckBox(name)
            check.setChecked(name in self.current["moods"])
            self.mood_checks[name] = check
            mood_layout.addWidget(check)
        mood_layout.addStretch(1)
        mood_area.setWidget(mood_page)
        mood_box = QWidget()
        mood_box_layout = QVBoxLayout(mood_box)
        mood_box_layout.addWidget(QLabel("Mood & Tone"))
        mood_box_layout.addWidget(mood_area)
        columns.addWidget(mood_box, 1)

        audience_row = QHBoxLayout()
        audience_row.addWidget(QLabel("Intended audience"))
        self.audience = QComboBox()
        self.audience.addItem("Not specified", "")
        for name in AUDIENCE_OPTIONS:
            self.audience.addItem(name, name)
        index = self.audience.findData(self.current["audience"])
        self.audience.setCurrentIndex(max(0, index))
        audience_row.addWidget(self.audience, 1)
        outer.addLayout(audience_row)

        self.explicit = QCheckBox("Explicit Adult Content (consenting adults only)")
        self.explicit.setChecked(self.current["explicit_adult_content"])
        outer.addWidget(self.explicit)
        self.audience.currentIndexChanged.connect(self._update_explicit_enabled)
        self._update_explicit_enabled()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _update_explicit_enabled(self) -> None:
        is_adult = self.audience.currentData() == "Adult"
        self.explicit.setEnabled(is_adult)
        if not is_adult:
            self.explicit.setChecked(False)

    def _validate_and_accept(self) -> None:
        try:
            self.profile = normalize_creative_direction(
                {
                    "genres": [key for key, item in self.genre_checks.items() if item.isChecked()],
                    "moods": [key for key, item in self.mood_checks.items() if item.isChecked()],
                    "audience": self.audience.currentData() or "",
                    "explicit_adult_content": self.explicit.isChecked(),
                }
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Creative Direction needs attention", str(exc))
            return
        self.accept()


class CharacterCardEditorDialog(QDialog):
    """Plain-English card editor. Unknown and nested fields are carried forward."""

    def __init__(
        self,
        existing: dict[str, Any] | None = None,
        title: str = "Character Card",
        character_names: list[str] | tuple[str, ...] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(850, 760)
        self.setMinimumSize(640, 520)
        self.original = copy.deepcopy(existing or {})
        self.character_names = sorted(
            {name.strip() for name in (character_names or []) if isinstance(name, str) and name.strip()},
            key=str.casefold,
        )
        self.line_fields: dict[str, QLineEdit] = {}
        self.text_fields: dict[str, QPlainTextEdit] = {}
        self.list_fields: dict[str, QPlainTextEdit] = {}
        self.appearance_fields: dict[str, QLineEdit] = {}
        self.relationship_rows: list[tuple[QComboBox, QLineEdit, QWidget]] = []
        self.custom_rows: list[dict[str, Any]] = []

        outer = QVBoxLayout(self)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)

        basic, basic_form = _scrollable_page(self.tabs, "Basic Information")
        self._add_line(basic_form, "name", "Name", self.original.get("name", ""))
        self._add_line(basic_form, "role", "Role", self.original.get("role", ""))
        self._add_line(basic_form, "age", "Age", self.original.get("age", ""))
        self._add_line(basic_form, "gender", "Gender", self.original.get("gender", ""))
        self._add_choice(
            basic_form,
            "sexual_orientation",
            "Sexual Orientation",
            self.original.get("sexual_orientation", ""),
            ("Not specified", "Straight", "Bisexual"),
        )
        self._add_line(
            basic_form, "relationship_status", "Relationship Status",
            self.original.get("relationship_status", ""),
        )
        self._add_line(basic_form, "occupation", "Occupation", self.original.get("occupation", ""))
        self._add_line(basic_form, "status", "Status", self.original.get("status", ""))

        appearance_page, appearance_form = _scrollable_page(self.tabs, "Appearance")
        raw_appearance = self.original.get("appearance", {})
        if isinstance(raw_appearance, str):
            appearance = {"notes": raw_appearance}
        elif isinstance(raw_appearance, dict):
            appearance = raw_appearance
        else:
            appearance = {}
        self.original_appearance = copy.deepcopy(raw_appearance)
        for key in _APPEARANCE_FIELDS:
            widget = QLineEdit(_display(appearance.get(key, "")))
            self.appearance_fields[key] = widget
            appearance_form.addRow(f"{key.replace('_', ' ').title()} (optional)", widget)

        background_page, background_form = _scrollable_page(self.tabs, "Background & Personality")
        self._add_text(background_form, "description", "Description", self.original.get("description", ""), 5)
        self._add_text(background_form, "background", "Background", self.original.get("background", ""), 5)
        self._add_list(background_form, "personality", "Personality", self.original.get("personality", []), 5)
        self._add_list(background_form, "hobbies", "Hobbies", self.original.get("hobbies", []), 4)

        skills_page, skills_form = _scrollable_page(self.tabs, "Skills & Story")
        self._add_list(skills_form, "skills", "Skills", self.original.get("skills", []), 4)
        self._add_list(skills_form, "strengths", "Strengths", self.original.get("strengths", []), 4)
        self._add_list(skills_form, "weaknesses", "Weaknesses", self.original.get("weaknesses", []), 4)
        self._add_list(skills_form, "goals", "Goals and Motivations", self.original.get("goals", []), 4)
        self._add_list(skills_form, "future_story_role", "Future Story Role", self.original.get("future_story_role", []), 4)
        self._add_list(skills_form, "social", "Social and Habits", self.original.get("social", []), 4)
        self._add_text(skills_form, "story_role", "Story Role", self.original.get("story_role", ""), 3)
        self._add_text(skills_form, "protective_nature", "Protective Nature", self.original.get("protective_nature", ""), 3)
        self._add_text(skills_form, "knowledge_rule", "Knowledge Rules", self.original.get("knowledge_rule", ""), 3)
        school = self.original.get("school", {})
        if isinstance(school, str):
            school = {"performance": school}
        if not isinstance(school, dict):
            school = {}
        self.original_school = copy.deepcopy(self.original.get("school", {}))
        self._add_line(skills_form, "school_performance", "School Performance", school.get("performance", ""))
        self._add_line(skills_form, "nickname_from_tony", "Nickname / How Others Address Them", self.original.get("nickname_from_tony", ""))

        relationship_page = QWidget()
        relationship_layout = QVBoxLayout(relationship_page)
        explanation = QLabel(
            "Choose a saved character or type a name. Relationship descriptions are ordinary text."
        )
        explanation.setWordWrap(True)
        relationship_layout.addWidget(explanation)
        self.relationships_container = QVBoxLayout()
        relationship_layout.addLayout(self.relationships_container)
        self._relationship_add_button = QPushButton("Add Relationship")
        self._relationship_add_button.clicked.connect(self._add_relationship_row)
        relationship_layout.addWidget(self._relationship_add_button, 0, Qt.AlignmentFlag.AlignLeft)
        relationship_layout.addStretch(1)
        self.tabs.addTab(relationship_page, "Relationships")
        original_relationships = self.original.get("relationships", {})
        if isinstance(original_relationships, dict):
            for name, description in original_relationships.items():
                self._add_relationship_row(str(name), _display(description))
        elif isinstance(original_relationships, str) and original_relationships.strip():
            self._add_relationship_row("General", original_relationships)

        additional_page = QWidget()
        additional_layout = QVBoxLayout(additional_page)
        note = QLabel(
            "Extra fields are retained when untouched. Nested custom values are shown read-only "
            "so the editor does not accidentally flatten them."
        )
        note.setWordWrap(True)
        additional_layout.addWidget(note)
        self.custom_container = QVBoxLayout()
        additional_layout.addLayout(self.custom_container)
        self._custom_add_button = QPushButton("Add Custom Field")
        self._custom_add_button.clicked.connect(self._add_custom_row)
        additional_layout.addWidget(self._custom_add_button, 0, Qt.AlignmentFlag.AlignLeft)
        additional_layout.addStretch(1)
        self.tabs.addTab(additional_page, "Additional Fields")
        for key, value in self.original.items():
            if key not in _STANDARD_FIELDS:
                self._add_custom_row(key, value, original=True)

        action_row = QHBoxLayout()
        action_row.addWidget(QLabel("Only Name is required. All other fields are optional."))
        action_row.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_card)
        buttons.rejected.connect(self.reject)
        action_row.addWidget(buttons)
        outer.addLayout(action_row)

    def _add_line(self, form: QFormLayout, key: str, label: str, value: Any) -> None:
        edit = QLineEdit(_display(value))
        self.line_fields[key] = edit
        form.addRow(f"{label} (optional)", edit)

    def _add_choice(
        self, form: QFormLayout, key: str, label: str, value: Any,
        choices: tuple[str, ...],
    ) -> None:
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(list(choices))
        current = _display(value).strip()
        if current and combo.findText(current) < 0:
            combo.addItem(current)
        combo.setCurrentText(current or "Not specified")
        self.line_fields[key] = combo  # QComboBox also exposes currentText().
        form.addRow(f"{label} (optional)", combo)

    def _add_text(self, form: QFormLayout, key: str, label: str, value: Any, height: int) -> None:
        edit = QPlainTextEdit(_display(value))
        edit.setMinimumHeight(height * 25)
        edit.setMaximumHeight(height * 42)
        self.text_fields[key] = edit
        form.addRow(f"{label} (optional)", edit)

    def _add_list(self, form: QFormLayout, key: str, label: str, value: Any, height: int) -> None:
        if isinstance(value, list):
            text = "\n".join(_human_readable(item) for item in value)
        elif isinstance(value, str):
            text = value
        else:
            text = ""
        edit = QPlainTextEdit(text)
        edit.setMinimumHeight(height * 25)
        edit.setMaximumHeight(height * 42)
        self.list_fields[key] = edit
        form.addRow(f"{label} (one item per line)", edit)

    def _add_relationship_row(self, name: str = "", description: str = "") -> None:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 2, 0, 2)
        character = QComboBox()
        character.setEditable(True)
        character.addItems(self.character_names)
        character.setCurrentText(name)
        relationship = QLineEdit(description)
        relationship.setPlaceholderText("Relationship description")
        remove = QPushButton("Remove")
        remove.clicked.connect(lambda _checked=False, target=row: self._remove_relationship_row(target))
        layout.addWidget(character, 1)
        layout.addWidget(relationship, 2)
        layout.addWidget(remove)
        self.relationship_rows.append((character, relationship, row))
        self.relationships_container.addWidget(row)

    def _remove_relationship_row(self, target: QWidget) -> None:
        self.relationship_rows = [row for row in self.relationship_rows if row[2] is not target]
        target.deleteLater()

    def _add_custom_row(self, key: str = "", value: Any = "", *, original: bool = False) -> None:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 2, 0, 2)
        key_edit = QLineEdit(key)
        key_edit.setPlaceholderText("Field name")
        nested = isinstance(value, (dict, list))
        value_edit = QLineEdit("" if nested else _display(value))
        value_edit.setPlaceholderText("Value")
        nested_value = copy.deepcopy(value) if nested else None
        if nested:
            value_edit.setReadOnly(True)
            value_edit.setText(_human_readable(value))
        remove = QPushButton("Remove")
        remove.clicked.connect(lambda _checked=False, target=row: self._remove_custom_row(target))
        layout.addWidget(key_edit, 1)
        layout.addWidget(value_edit, 2)
        layout.addWidget(remove)
        item = {
            "key": key_edit,
            "value": value_edit,
            "nested": nested,
            "nested_value": nested_value,
            "original": original,
            "original_key": key if original else None,
            "original_value": copy.deepcopy(value),
            "widget": row,
            "removed": False,
        }
        self.custom_rows.append(item)
        self.custom_container.addWidget(row)

    def _remove_custom_row(self, target: QWidget) -> None:
        for item in self.custom_rows:
            if item["widget"] is target:
                item["removed"] = True
                break
        target.deleteLater()

    def build_card(self) -> dict[str, Any]:
        name = self.line_fields["name"].text().strip()
        if not name:
            raise ValueError("Name is required.")
        result = copy.deepcopy(self.original)
        result["name"] = name

        for key in _STRING_FIELDS:
            widget = self.line_fields[key]
            value = widget.currentText().strip() if isinstance(widget, QComboBox) else widget.text().strip()
            if key == "sexual_orientation" and value == "Not specified":
                value = ""
            if value or key in self.original:
                result[key] = value

        age_text = self.line_fields["age"].text().strip()
        if age_text:
            try:
                result["age"] = int(age_text)
            except ValueError:
                result["age"] = age_text
        elif "age" in self.original:
            result["age"] = ""

        for key, widget in self.text_fields.items():
            value = widget.toPlainText().strip()
            if value or key in self.original:
                result[key] = value

        for key, widget in self.list_fields.items():
            values = [line.strip() for line in widget.toPlainText().splitlines() if line.strip()]
            if values or key in self.original:
                result[key] = values

        raw_appearance = self.original_appearance
        if isinstance(raw_appearance, str):
            appearance = {"notes": raw_appearance}
        elif isinstance(raw_appearance, dict):
            appearance = copy.deepcopy(raw_appearance)
        else:
            appearance = {}
        for key, widget in self.appearance_fields.items():
            value = widget.text().strip()
            if value:
                appearance[key] = value
            elif key in appearance:
                appearance[key] = ""
        if (
            isinstance(raw_appearance, str)
            and appearance.get("notes", "") == raw_appearance
            and all(not appearance.get(key) for key in _APPEARANCE_FIELDS if key != "notes")
        ):
            result["appearance"] = raw_appearance
        elif appearance or "appearance" in self.original:
            result["appearance"] = appearance

        raw_school = self.original_school
        if isinstance(raw_school, str):
            school_data = {"performance": raw_school}
        elif isinstance(raw_school, dict):
            school_data = copy.deepcopy(raw_school)
        else:
            school_data = {}
        performance = self.line_fields["school_performance"].text().strip()
        if performance or "performance" in school_data:
            school_data["performance"] = performance
        if school_data or "school" in self.original:
            if isinstance(raw_school, str) and school_data.get("performance", "") == raw_school and len(school_data) == 1:
                result["school"] = raw_school
            else:
                result["school"] = school_data

        relationships: dict[str, Any] = {}
        original_relationships = self.original.get("relationships", {})
        for character, description, _row in self.relationship_rows:
            character_name = character.currentText().strip()
            text = description.text().strip()
            if not character_name and not text:
                continue
            if not character_name:
                raise ValueError("Enter a character name for each relationship, or remove the blank row.")
            if not text:
                continue
            if isinstance(original_relationships, dict) and character_name in original_relationships:
                old_value = original_relationships[character_name]
                if _display(old_value).strip() == text:
                    relationships[character_name] = copy.deepcopy(old_value)
                else:
                    relationships[character_name] = text
            else:
                relationships[character_name] = text
        if relationships or "relationships" in self.original:
            result["relationships"] = relationships

        custom_names: set[str] = set()
        for item in self.custom_rows:
            original_key = item["original_key"]
            if item["removed"]:
                if original_key:
                    result.pop(original_key, None)
                continue
            key = item["key"].text().strip()
            value = item["value"].text().strip()
            if not key and not value:
                continue
            if not key:
                raise ValueError("Give each custom field a name, or leave the whole row blank.")
            if key in _STANDARD_FIELDS:
                raise ValueError(f"'{key}' is already a standard Character Card field.")
            if key in custom_names:
                raise ValueError(f"The custom field '{key}' appears more than once.")
            custom_names.add(key)
            if original_key and original_key != key:
                result.pop(original_key, None)
            if item["nested"]:
                result[key] = copy.deepcopy(item["nested_value"])
            elif item["original"] and value == _display(item["original_value"]):
                result[key] = copy.deepcopy(item["original_value"])
            elif value:
                result[key] = value
            elif item["original"]:
                result[key] = ""
        return result

    def _accept_card(self) -> None:
        try:
            self.card = self.build_card()
        except ValueError as exc:
            QMessageBox.warning(self, "Character Card needs attention", str(exc))
            return
        self.accept()


class CharacterCardsManagerDialog(QDialog):
    """Manage card references without deleting source card files."""

    def __init__(self, novel_path: str | Path, on_saved=None, parent: QWidget | None = None):
        super().__init__(parent)
        self.novel_path = Path(novel_path)
        self.on_saved = on_saved
        self.setWindowTitle(f"Character Cards: {self.novel_path.name}")
        self.resize(820, 560)
        self.setMinimumSize(620, 420)
        outer = QVBoxLayout(self)
        columns = QHBoxLayout()
        self.cards_list = QListWidget()
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        columns.addWidget(self.cards_list, 1)
        columns.addWidget(self.preview, 2)
        outer.addLayout(columns, 1)
        self.cards_list.currentRowChanged.connect(self._selection_changed)
        buttons = QHBoxLayout()
        for label, handler in (
            ("Add Character", self.add_card),
            ("Edit Selected", self.edit_card),
            ("Remove Reference", self.remove_card),
            ("Close", self.accept),
        ):
            button = QPushButton(label)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        outer.addLayout(buttons)
        note = QLabel("Removing a card removes only its Story Bible reference. The source JSON file is never deleted.")
        note.setWordWrap(True)
        outer.addWidget(note)
        self.data: dict[str, Any] = {}
        self.cards: list[Any] = []
        self.refresh()

    def refresh(self, selected_row: int = 0) -> None:
        try:
            self.data = load_story_bible(self.novel_path)
            raw = self.data.get("character_cards", [])
            if not isinstance(raw, list):
                raise ValueError("Character Cards is not a list. It has been left unchanged.")
            self.cards = copy.deepcopy(raw)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Could not load Character Cards", str(exc))
            self.cards = []
        self.cards_list.clear()
        for item in self.cards:
            if isinstance(item, str):
                label = Path(item).stem if item.lower().endswith(".json") else item
            elif isinstance(item, dict):
                label = str(item.get("name") or "Unnamed Character")
            else:
                label = "Unsupported entry"
            self.cards_list.addItem(label)
        if self.cards:
            self.cards_list.setCurrentRow(max(0, min(selected_row, len(self.cards) - 1)))
        else:
            self.preview.clear()

    def _selected_index(self) -> int:
        return self.cards_list.currentRow()

    def _selected_data(self) -> dict[str, Any]:
        index = self._selected_index()
        if not 0 <= index < len(self.cards):
            raise ValueError("Select a Character Card first.")
        item = self.cards[index]
        if isinstance(item, str) and item.lower().endswith(".json"):
            return load_story_bible_character_card(self.novel_path, item)
        if isinstance(item, dict):
            return copy.deepcopy(item)
        if isinstance(item, str):
            return {"name": item, "description": ""}
        raise ValueError("This Character Card entry uses an unsupported format.")

    def _selection_changed(self, _row: int) -> None:
        try:
            card = self._selected_data()
            self.preview.setPlainText(json.dumps(card, indent=2, ensure_ascii=False))
        except (OSError, ValueError) as exc:
            self.preview.setPlainText(str(exc))

    def _character_names(self) -> list[str]:
        names = []
        for item in self.cards:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                names.append(item["name"])
            elif isinstance(item, str):
                names.append(Path(item).stem if item.lower().endswith(".json") else item)
        return names

    def add_card(self) -> None:
        dialog = CharacterCardEditorDialog(
            title="Add Character Card",
            character_names=self._character_names(),
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            create_story_bible_character_card(self.novel_path, dialog.card)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "Character Card was not added", str(exc))
            return
        if self.on_saved:
            self.on_saved()
        self.refresh(len(self.cards))

    def edit_card(self) -> None:
        index = self._selected_index()
        if not 0 <= index < len(self.cards):
            return
        try:
            existing = self._selected_data()
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Character Card cannot be edited", str(exc))
            return
        dialog = CharacterCardEditorDialog(
            existing=existing,
            title=f"Edit Character: {existing.get('name', 'Character')}",
            character_names=self._character_names(),
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        reference = self.cards[index]
        try:
            if isinstance(reference, str) and reference.lower().endswith(".json"):
                save_story_bible_character_card_file(
                    self.novel_path, reference, dialog.card, replace=True
                )
            else:
                updated = copy.deepcopy(self.cards)
                updated[index] = dialog.card
                save_story_bible_character_cards(self.novel_path, updated)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "Character Card was not saved", str(exc))
            return
        if self.on_saved:
            self.on_saved()
        self.refresh(index)

    def remove_card(self) -> None:
        index = self._selected_index()
        if not 0 <= index < len(self.cards):
            return
        item = self.cards[index]
        label = self.cards_list.item(index).text()
        answer = QMessageBox.question(
            self,
            "Remove Character Card Reference",
            f"Remove '{label}' from this Story Bible? The source character file will not be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            if isinstance(item, str) and item.lower().endswith(".json"):
                remove_story_bible_character_card_reference(self.novel_path, index, item)
            else:
                updated = copy.deepcopy(self.cards)
                updated.pop(index)
                save_story_bible_character_cards(self.novel_path, updated)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "Character Card was not removed", str(exc))
            return
        if self.on_saved:
            self.on_saved()
        self.refresh(max(0, index - 1))


class LocationEditorDialog(QDialog):
    def __init__(
        self,
        existing: dict[str, Any] | None = None,
        name: str = "",
        title: str = "Location",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 650)
        self.setMinimumSize(560, 460)
        self.original = copy.deepcopy(existing or {})
        self.original_name = name
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(12, 12, 12, 12)
        self.name_edit = QLineEdit(name)
        form.addRow("Name (required)", self.name_edit)
        self.entry_edits: dict[str, QLineEdit] = {}
        for key, label in (("type", "Type"), ("geography", "Geography"), ("climate", "Climate")):
            edit = QLineEdit(_display(self.original.get(key, "")))
            self.entry_edits[key] = edit
            form.addRow(f"{label} (optional)", edit)
        self.text_edits: dict[str, QPlainTextEdit] = {}
        for key, label in (("description", "Description"), ("notable_details", "Notable Details")):
            edit = QPlainTextEdit(_display(self.original.get(key, "")))
            edit.setMinimumHeight(105)
            self.text_edits[key] = edit
            form.addRow(f"{label} (optional)", edit)
        scroll.setWidget(page)
        outer.addWidget(scroll, 1)

        extra_box = QWidget()
        extra_layout = QVBoxLayout(extra_box)
        extra_layout.addWidget(QLabel("Additional Information (optional)"))
        self.custom_rows: list[dict[str, Any]] = []
        self.custom_layout = QVBoxLayout()
        extra_layout.addLayout(self.custom_layout)
        add_button = QPushButton("Add Custom Field")
        add_button.clicked.connect(self._add_custom_row)
        extra_layout.addWidget(add_button, 0, Qt.AlignmentFlag.AlignLeft)
        known = {"type", "geography", "climate", "description", "notable_details"}
        for key, value in self.original.items():
            if key not in known:
                self._add_custom_row(key, value, original=True)
        outer.addWidget(extra_box)

        note = QLabel("Only Name is required. Untouched nested or custom details are preserved.")
        note.setWordWrap(True)
        outer.addWidget(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _add_custom_row(self, key: str = "", value: Any = "", *, original: bool = False) -> None:
        row = QWidget()
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 2, 0, 2)
        key_edit = QLineEdit(key)
        key_edit.setPlaceholderText("Field name")
        nested = isinstance(value, (dict, list))
        value_edit = QLineEdit("" if nested else _display(value))
        value_edit.setPlaceholderText("Value")
        if nested:
            value_edit.setReadOnly(True)
            value_edit.setText(_human_readable(value))
        remove = QPushButton("Remove")
        item = {
            "key": key_edit,
            "value": value_edit,
            "nested": nested,
            "original_key": key if original else None,
            "original_value": copy.deepcopy(value),
            "original": original,
            "removed": False,
            "widget": row,
        }
        remove.clicked.connect(lambda _checked=False, target=item: self._remove_custom_row(target))
        line.addWidget(key_edit, 1)
        line.addWidget(value_edit, 2)
        line.addWidget(remove)
        self.custom_rows.append(item)
        self.custom_layout.addWidget(row)

    def _remove_custom_row(self, item: dict[str, Any]) -> None:
        item["removed"] = True
        item["widget"].deleteLater()

    def build_location(self) -> tuple[str, dict[str, Any]]:
        name = self.name_edit.text().strip()
        if not name:
            raise ValueError("Name is required.")
        result = copy.deepcopy(self.original)
        for key, edit in self.entry_edits.items():
            value = edit.text().strip()
            if value or key in self.original:
                result[key] = value
        for key, edit in self.text_edits.items():
            value = edit.toPlainText().strip()
            if value or key in self.original:
                result[key] = value

        used = {"type", "geography", "climate", "description", "notable_details"}
        for item in self.custom_rows:
            old_key = item["original_key"]
            if item["removed"]:
                if old_key:
                    result.pop(old_key, None)
                continue
            key = item["key"].text().strip()
            value = item["value"].text().strip()
            if not key and not value:
                continue
            if not key:
                raise ValueError("Give each custom field a name, or leave the entire row blank.")
            if key in used:
                raise ValueError(f"Field name '{key}' is already in use.")
            used.add(key)
            if old_key and old_key != key:
                result.pop(old_key, None)
            if item["nested"]:
                result[key] = copy.deepcopy(item["original_value"])
            elif item["original"] and value == _display(item["original_value"]):
                result[key] = copy.deepcopy(item["original_value"])
            else:
                result[key] = value
        return name, result

    def _validate_and_accept(self) -> None:
        try:
            self.location_name, self.location_data = self.build_location()
        except ValueError as exc:
            QMessageBox.warning(self, "Location needs attention", str(exc))
            return
        self.accept()


class LocationManagerDialog(QDialog):
    def __init__(self, novel_path: str | Path, on_saved=None, parent: QWidget | None = None):
        super().__init__(parent)
        self.novel_path = Path(novel_path)
        self.on_saved = on_saved
        self.setWindowTitle(f"Locations: {self.novel_path.name}")
        self.resize(800, 540)
        self.setMinimumSize(620, 420)
        outer = QVBoxLayout(self)
        columns = QHBoxLayout()
        self.locations_list = QListWidget()
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        columns.addWidget(self.locations_list, 1)
        columns.addWidget(self.preview, 2)
        outer.addLayout(columns, 1)
        self.locations_list.currentRowChanged.connect(self._selection_changed)
        buttons = QHBoxLayout()
        for label, handler in (
            ("Add Location", self.add_location),
            ("Edit Selected", self.edit_location),
            ("Remove Selected", self.remove_location),
            ("Close", self.accept),
        ):
            button = QPushButton(label)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        outer.addLayout(buttons)
        note = QLabel("Removing a location removes only its entry from this Story Bible.")
        note.setWordWrap(True)
        outer.addWidget(note)
        self.locations: dict[str, Any] = {}
        self.refresh()

    def refresh(self, selected_name: str | None = None) -> None:
        try:
            self.locations = copy.deepcopy(load_story_bible_locations(self.novel_path))
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Could not load Locations", str(exc))
            self.locations = {}
        self.locations_list.clear()
        for name in self.locations:
            self.locations_list.addItem(name)
        names = list(self.locations)
        if selected_name in names:
            self.locations_list.setCurrentRow(names.index(selected_name))
        elif names:
            self.locations_list.setCurrentRow(0)
        else:
            self.preview.clear()

    def _selection_changed(self, row: int) -> None:
        names = list(self.locations)
        if not 0 <= row < len(names):
            self.preview.clear()
            return
        name = names[row]
        self.preview.setPlainText(f"Name: {name}\n\n{_human_readable(self.locations[name])}")

    def _save_location(self, original_name: str | None, name: str, details: dict[str, Any]) -> None:
        duplicate = next(
            (current for current in self.locations if current.casefold() == name.casefold() and current != original_name),
            None,
        )
        if duplicate:
            QMessageBox.warning(self, "Location already exists", f"A location named '{duplicate}' already exists.")
            return
        if original_name is not None and original_name not in self.locations:
            QMessageBox.warning(self, "Location was not saved", "The selected entry changed. Reload the Locations manager.")
            return
        updated: dict[str, Any] = {}
        replaced = False
        for current, value in self.locations.items():
            if current == original_name:
                updated[name] = details
                replaced = True
            else:
                updated[current] = value
        if not replaced:
            updated[name] = details
        try:
            save_story_bible_locations(self.novel_path, updated)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "Location was not saved", str(exc))
            return
        if self.on_saved:
            self.on_saved()
        self.refresh(name)

    def add_location(self) -> None:
        dialog = LocationEditorDialog(title="Add Location", parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._save_location(None, dialog.location_name, dialog.location_data)

    def edit_location(self) -> None:
        row = self.locations_list.currentRow()
        names = list(self.locations)
        if not 0 <= row < len(names):
            return
        name = names[row]
        existing = self.locations[name]
        if isinstance(existing, str):
            existing = {"description": existing}
        if not isinstance(existing, dict):
            QMessageBox.warning(self, "Location cannot be edited", "This location uses an unsupported format and was left unchanged.")
            return
        dialog = LocationEditorDialog(existing, name, f"Edit Location: {name}", self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._save_location(name, dialog.location_name, dialog.location_data)

    def remove_location(self) -> None:
        row = self.locations_list.currentRow()
        names = list(self.locations)
        if not 0 <= row < len(names):
            return
        name = names[row]
        answer = QMessageBox.question(
            self,
            "Remove Location",
            f"Remove '{name}' from this Story Bible? Only this location entry will be removed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        updated = dict(self.locations)
        updated.pop(name, None)
        try:
            save_story_bible_locations(self.novel_path, updated)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "Location was not removed", str(exc))
            return
        if self.on_saved:
            self.on_saved()
        remaining = list(updated)
        self.refresh(remaining[min(row, len(remaining) - 1)] if remaining else None)
