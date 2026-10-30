from __future__ import annotations

import copy
import json
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable


_STRING_FIELDS = (
    "role",
    "gender",
    "pronouns",
    "relationship_status",
    "occupation",
    "status",
    "story_role",
    "protective_nature",
    "knowledge_rule",
    "nickname_from_tony",
)
_TEXT_FIELDS = ("description", "background")
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
    *_STRING_FIELDS,
    *_TEXT_FIELDS,
    *_LIST_FIELDS,
    "appearance",
    "relationships",
}
_TAB_FIELDS = {
    "Basic Information": {"name", "age", *_STRING_FIELDS[:6]},
    "Appearance": {"appearance"},
    "Background & Personality": {*_TEXT_FIELDS, "personality", "hobbies"},
    "Skills & Story": {
        "skills", "strengths", "weaknesses", "goals", "future_story_role",
        "social", "story_role", "protective_nature", "knowledge_rule",
        "nickname_from_tony",
    },
    "Relationships": {"relationships"},
}


class CharacterCardEditorWindow:
    """Optional-field character editor that preserves unrecognized JSON data."""

    def __init__(
        self,
        parent: tk.Misc,
        existing: dict[str, Any] | None,
        title: str,
        on_save: Callable[[dict[str, Any]], None],
        on_cancel: Callable[[], None],
    ) -> None:
        self.original = copy.deepcopy(existing or {})
        self.on_save = on_save
        self.on_cancel = on_cancel
        self.entry_vars: dict[str, tk.StringVar] = {}
        self._name_entry: ttk.Entry | None = None
        self.text_widgets: dict[str, tk.Text] = {}
        self.list_widgets: dict[str, tk.Text] = {}
        self.appearance_vars: dict[str, tk.StringVar] = {}
        self.relationship_rows: list[tuple[tk.StringVar, tk.StringVar, ttk.Frame]] = []
        self.relationships_frame: ttk.Frame | None = None
        self.custom_fields_frame: ttk.Frame | None = None
        self.custom_field_rows: list[dict[str, Any]] = []
        self._next_custom_row = 0

        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.geometry("820x690")
        self.window.minsize(650, 520)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)

        outer = ttk.Frame(self.window, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(outer)
        notebook.grid(row=0, column=0, sticky="nsew")

        basic = self._add_tab(notebook, "Basic Information")
        appearance = self._add_tab(notebook, "Appearance")
        background = self._add_tab(notebook, "Background & Personality")
        skills = self._add_tab(notebook, "Skills & Story")
        relationships = self._add_tab(notebook, "Relationships")
        additional = self._add_tab(notebook, "Additional Fields")

        self._build_basic_tab(basic)
        self._build_appearance_tab(appearance)
        self._build_background_tab(background)
        self._build_skills_tab(skills)
        self._build_relationships_tab(relationships)
        self._build_additional_tab(additional)

        action_row = ttk.Frame(outer)
        action_row.grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Button(action_row, text="Save Character", command=self.save).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(action_row, text="Cancel Edit", command=self.cancel).pack(side="left")
        ttk.Label(
            outer,
            text="Only Name is required. All other fields are optional and may be left blank.",
            foreground="gray",
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))

        self.window.grab_set()
        self.window.after_idle(self._focus_name)

    def _add_tab(self, notebook: ttk.Notebook, title: str) -> ttk.Frame:
        page = ttk.Frame(notebook)
        notebook.add(page, text=title)
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)

        canvas = tk.Canvas(page, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(page, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        content = ttk.Frame(canvas, padding=8)
        content.columnconfigure(0, weight=1)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind(
            "<Configure>",
            lambda _event, target=canvas: target.configure(
                scrollregion=target.bbox("all")
            ),
        )
        canvas.bind(
            "<Configure>",
            lambda event, target=canvas, item=window_id: target.itemconfigure(
                item, width=event.width
            ),
        )
        return content

    def _add_entry(
        self,
        parent: ttk.Frame,
        key: str,
        label: str,
        value: Any = "",
        required: bool = False,
    ) -> int:
        row = self._next_row(parent)
        suffix = " (required)" if required else " (optional)"
        ttk.Label(parent, text=f"{label}{suffix}").grid(
            row=row, column=0, sticky="w", pady=(5, 0)
        )
        variable = tk.StringVar(self.window, value=self._display_scalar(value))
        self.entry_vars[key] = variable
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row + 1, column=0, sticky="ew", pady=(2, 5))
        if key == "name":
            self._name_entry = entry
        self._set_next_row(parent, row + 2)
        return row + 2

    def _add_text(
        self, parent: ttk.Frame, key: str, label: str, value: Any = "", height: int = 4
    ) -> None:
        row = self._next_row(parent)
        ttk.Label(parent, text=f"{label} (optional)").grid(
            row=row, column=0, sticky="w", pady=(5, 0)
        )
        editor_frame = ttk.Frame(parent)
        editor_frame.grid(row=row + 1, column=0, sticky="ew", pady=(2, 5))
        editor_frame.columnconfigure(0, weight=1)
        widget = tk.Text(editor_frame, height=height, wrap="word", undo=True, padx=6, pady=5)
        scrollbar = ttk.Scrollbar(editor_frame, orient="vertical", command=widget.yview)
        widget.configure(yscrollcommand=scrollbar.set)
        widget.grid(row=0, column=0, sticky="ew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        widget.insert("1.0", self._display_text(value))
        self._bind_copy(widget)
        self.text_widgets[key] = widget
        self._set_next_row(parent, row + 2)

    def _add_list(
        self, parent: ttk.Frame, key: str, label: str, value: Any = "", height: int = 5
    ) -> None:
        row = self._next_row(parent)
        ttk.Label(
            parent,
            text=f"{label} (optional, one item per line)",
        ).grid(row=row, column=0, sticky="w", pady=(5, 0))
        editor_frame = ttk.Frame(parent)
        editor_frame.grid(row=row + 1, column=0, sticky="ew", pady=(2, 5))
        editor_frame.columnconfigure(0, weight=1)
        widget = tk.Text(editor_frame, height=height, wrap="word", undo=True, padx=6, pady=5)
        scrollbar = ttk.Scrollbar(editor_frame, orient="vertical", command=widget.yview)
        widget.configure(yscrollcommand=scrollbar.set)
        widget.grid(row=0, column=0, sticky="ew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        widget.insert("1.0", self._display_list(value))
        self._bind_copy(widget)
        self.list_widgets[key] = widget
        self._set_next_row(parent, row + 2)

    def _next_row(self, parent: ttk.Frame) -> int:
        return int(getattr(parent, "_character_editor_row", 0))

    def _set_next_row(self, parent: ttk.Frame, row: int) -> None:
        setattr(parent, "_character_editor_row", row)

    @staticmethod
    def _display_scalar(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return CharacterCardEditorWindow._human_readable_value(value)
        return str(value)

    @staticmethod
    def _display_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return CharacterCardEditorWindow._human_readable_value(value)

    @staticmethod
    def _display_list(value: Any) -> str:
        if isinstance(value, list):
            return "\n".join(
                CharacterCardEditorWindow._human_readable_value(item)
                for item in value
            )
        if isinstance(value, str):
            return value
        return ""

    @staticmethod
    def _bind_copy(widget: tk.Text) -> None:
        widget.bind("<Control-a>", lambda _event, target=widget: CharacterCardEditorWindow._select_all(target))
        widget.bind("<Control-A>", lambda _event, target=widget: CharacterCardEditorWindow._select_all(target))
        widget.bind("<Control-c>", lambda _event, target=widget: CharacterCardEditorWindow._copy(target))
        widget.bind("<Control-C>", lambda _event, target=widget: CharacterCardEditorWindow._copy(target))

    @staticmethod
    def _select_all(widget: tk.Text):
        widget.tag_add("sel", "1.0", "end-1c")
        widget.mark_set("insert", "end-1c")
        widget.see("insert")
        return "break"

    @staticmethod
    def _copy(widget: tk.Text):
        try:
            selected = widget.get("sel.first", "sel.last")
        except tk.TclError:
            return "break"
        widget.clipboard_clear()
        widget.clipboard_append(selected)
        return "break"

    def _focus_name(self) -> None:
        if self._name_entry is not None:
            self._name_entry.focus_set()

    def _build_basic_tab(self, parent: ttk.Frame) -> None:
        self._add_entry(parent, "name", "Name", self.original.get("name", ""), required=True)
        self._add_entry(parent, "role", "Role", self.original.get("role", ""))
        self._add_entry(parent, "age", "Age", self.original.get("age", ""))
        self._add_entry(parent, "gender", "Gender", self.original.get("gender", ""))
        self._add_entry(parent, "pronouns", "Pronouns", self.original.get("pronouns", ""))
        self._add_entry(
            parent, "relationship_status", "Relationship Status",
            self.original.get("relationship_status", ""),
        )
        self._add_entry(
            parent, "occupation", "Occupation", self.original.get("occupation", "")
        )
        self._add_entry(parent, "status", "Status", self.original.get("status", ""))

    def _build_appearance_tab(self, parent: ttk.Frame) -> None:
        appearance = self.original.get("appearance", {})
        if isinstance(appearance, str):
            appearance = {"notes": appearance}
        if not isinstance(appearance, dict):
            appearance = {}
        self.original_appearance = copy.deepcopy(self.original.get("appearance", {}))
        for key in _APPEARANCE_FIELDS:
            row = self._next_row(parent)
            ttk.Label(parent, text=f"{key.replace('_', ' ').title()} (optional)").grid(
                row=row, column=0, sticky="w", pady=(5, 0)
            )
            variable = tk.StringVar(self.window, value=self._display_scalar(appearance.get(key, "")))
            self.appearance_vars[key] = variable
            ttk.Entry(parent, textvariable=variable).grid(
                row=row + 1, column=0, sticky="ew", pady=(2, 5)
            )
            self._set_next_row(parent, row + 2)

    def _build_background_tab(self, parent: ttk.Frame) -> None:
        self._add_text(parent, "description", "Description", self.original.get("description", ""), 5)
        self._add_text(parent, "background", "Background", self.original.get("background", ""), 5)
        self._add_list(parent, "personality", "Personality", self.original.get("personality", []))
        self._add_list(parent, "hobbies", "Hobbies", self.original.get("hobbies", []))

    def _build_skills_tab(self, parent: ttk.Frame) -> None:
        self._add_list(parent, "skills", "Skills", self.original.get("skills", []))
        self._add_list(parent, "strengths", "Strengths", self.original.get("strengths", []))
        self._add_list(parent, "weaknesses", "Weaknesses", self.original.get("weaknesses", []))
        self._add_list(parent, "goals", "Goals and Motivations", self.original.get("goals", []))
        self._add_list(
            parent, "future_story_role", "Future Story Role",
            self.original.get("future_story_role", []),
        )
        self._add_list(parent, "social", "Social and Habits", self.original.get("social", []))
        self._add_text(
            parent, "story_role", "Story Role", self.original.get("story_role", ""), 3
        )
        self._add_text(
            parent, "protective_nature", "Protective Nature",
            self.original.get("protective_nature", ""), 3,
        )
        self._add_text(
            parent, "knowledge_rule", "Knowledge Rules",
            self.original.get("knowledge_rule", ""), 3,
        )
        self._add_entry(
            parent, "nickname_from_tony", "Nickname / How Others Address Them",
            self.original.get("nickname_from_tony", ""),
        )

    def _build_relationships_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            text="Add a row for each person. Both boxes are ordinary text; no special punctuation is needed.",
            wraplength=650,
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        rows_frame = ttk.Frame(parent)
        rows_frame.grid(row=1, column=0, sticky="nsew")
        rows_frame.columnconfigure(1, weight=2)
        self.relationships_frame = rows_frame

        existing = self.original.get("relationships", {})
        if isinstance(existing, dict):
            for character_name, description in existing.items():
                self._add_relationship_row(
                    str(character_name), self._display_text(description)
                )
        elif isinstance(existing, str) and existing.strip():
            self._add_relationship_row("General", existing)

        ttk.Button(
            parent, text="Add Relationship", command=self._add_relationship_row
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))

    def _add_relationship_row(
        self, character_name: str = "", description: str = ""
    ) -> None:
        if self.relationships_frame is None:
            return
        row = ttk.Frame(self.relationships_frame)
        row.grid(
            row=len(self.relationship_rows), column=0, sticky="ew", pady=4
        )
        row.columnconfigure(1, weight=1)
        name_var = tk.StringVar(self.window, value=character_name)
        description_var = tk.StringVar(self.window, value=description)
        ttk.Label(row, text="Character").grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        ttk.Entry(row, textvariable=name_var, width=20).grid(
            row=0, column=1, sticky="ew", padx=(0, 8)
        )
        ttk.Label(row, text="Relationship").grid(
            row=0, column=2, sticky="w", padx=(0, 8)
        )
        ttk.Entry(row, textvariable=description_var, width=34).grid(
            row=0, column=3, sticky="ew", padx=(0, 8)
        )
        ttk.Button(
            row,
            text="Remove",
            command=lambda target=row: self._remove_relationship_row(target),
        ).grid(row=0, column=4)
        self.relationship_rows.append((name_var, description_var, row))

    def _remove_relationship_row(self, row_frame: ttk.Frame) -> None:
        self.relationship_rows = [
            item for item in self.relationship_rows if item[2] is not row_frame
        ]
        row_frame.destroy()
        for index, (_name, _description, frame) in enumerate(self.relationship_rows):
            frame.grid_configure(row=index)


    def _build_additional_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            text=(
                "Add any information that does not fit the other sections. "
                "Use plain field names and ordinary text values. Existing special or nested "
                "information is shown in readable form and kept unchanged."
            ),
            wraplength=650,
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        fields_frame = ttk.Frame(parent)
        fields_frame.grid(row=1, column=0, sticky="nsew")
        fields_frame.columnconfigure(1, weight=1)
        self.custom_fields_frame = fields_frame
        ttk.Label(fields_frame, text="Field name").grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        ttk.Label(fields_frame, text="Value").grid(
            row=0, column=1, sticky="w"
        )
        self._next_custom_row = 1

        known = set(_STANDARD_FIELDS)
        for key, value in self.original.items():
            if key in known:
                continue
            self._add_custom_field_row(key, value, original=True)

        ttk.Button(
            parent, text="Add Custom Field", command=self._add_custom_field_row
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))

    def _add_custom_field_row(
        self, key: str = "", value: Any = "", *, original: bool = False
    ) -> None:
        if self.custom_fields_frame is None:
            return
        row_frame = ttk.Frame(self.custom_fields_frame)
        row_frame.grid(
            row=self._next_custom_row, column=0, sticky="ew", pady=(3, 5)
        )
        row_frame.columnconfigure(1, weight=1)
        key_var = tk.StringVar(self.window, value=key)
        entry = ttk.Entry(row_frame, textvariable=key_var, width=22)
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        value_var = tk.StringVar(self.window)
        nested = isinstance(value, (dict, list))
        if nested:
            display = self._human_readable_value(value)
            ttk.Label(
                row_frame,
                text=display,
                justify="left",
                wraplength=470,
            ).grid(row=0, column=1, sticky="w")
            value_var.set("")
        else:
            value_var.set(self._display_scalar(value))
            ttk.Entry(row_frame, textvariable=value_var).grid(
                row=0, column=1, sticky="ew"
            )
        remove_button = ttk.Button(
            row_frame,
            text="Remove",
            command=lambda target=row_frame: self._remove_custom_field_row(target),
        )
        remove_button.grid(row=0, column=2, padx=(8, 0))
        self.custom_field_rows.append(
            {
                "key": key_var,
                "value": value_var,
                "nested": nested,
                "original": original,
                "frame": row_frame,
                "entry": entry,
                "original_value": copy.deepcopy(value),
                "removed": False,
            }
        )
        self._next_custom_row += 1

    def _remove_custom_field_row(self, frame: ttk.Frame) -> None:
        for item in self.custom_field_rows:
            if item["frame"] is frame:
                item["removed"] = True
                frame.destroy()
                break

    @classmethod
    def _human_readable_value(cls, value: Any, indent: int = 0) -> str:
        prefix = " " * indent
        if isinstance(value, dict):
            lines = []
            for key, nested in value.items():
                if isinstance(nested, (dict, list)):
                    lines.append(f"{prefix}{str(key).replace('_', ' ').title()}:")
                    lines.append(cls._human_readable_value(nested, indent + 2))
                else:
                    lines.append(
                        f"{prefix}{str(key).replace('_', ' ').title()}: {cls._display_scalar(nested)}"
                    )
            return "\\n".join(lines)
        if isinstance(value, list):
            return "\\n".join(
                f"{prefix}• {cls._human_readable_value(item, indent)}"
                for item in value
            )
        return f"{prefix}{cls._display_scalar(value)}"

    def build_card(self) -> dict[str, Any]:
        name = self.entry_vars["name"].get().strip()
        if not name:
            raise ValueError("Name is required.")

        result = copy.deepcopy(self.original)
        result["name"] = name

        for key in _STRING_FIELDS:
            value = self.entry_vars[key].get().strip()
            if value or key in self.original:
                result[key] = value

        age_text = self.entry_vars["age"].get().strip()
        if age_text:
            try:
                result["age"] = int(age_text)
            except ValueError:
                # Keep age flexible (for example, "early thirties" is valid text).
                result["age"] = age_text
        elif "age" in self.original:
            result["age"] = ""

        for key in _TEXT_FIELDS:
            value = self.text_widgets[key].get("1.0", "end-1c").strip()
            if value or key in self.original:
                result[key] = value

        for key in _LIST_FIELDS:
            items = [
                line.strip()
                for line in self.list_widgets[key].get("1.0", "end-1c").splitlines()
                if line.strip()
            ]
            if items or key in self.original:
                result[key] = items

        original_appearance = self.original_appearance
        if isinstance(original_appearance, str):
            appearance = {"notes": original_appearance}
        elif isinstance(original_appearance, dict):
            appearance = copy.deepcopy(original_appearance)
        else:
            appearance = {}
        for key, variable in self.appearance_vars.items():
            value = variable.get().strip()
            if value:
                appearance[key] = value
            elif key in appearance:
                appearance[key] = ""
        if (
            isinstance(original_appearance, str)
            and appearance.get("notes", "") == original_appearance
            and all(
                not appearance.get(key)
                for key in _APPEARANCE_FIELDS
                if key != "notes"
            )
        ):
            result["appearance"] = original_appearance
        elif appearance or "appearance" in self.original:
            result["appearance"] = appearance

        relationships: dict[str, Any] = {}
        original_relationships = self.original.get("relationships", {})
        for name_var, description_var, _frame in self.relationship_rows:
            character_name = name_var.get().strip()
            description = description_var.get().strip()
            if not character_name and not description:
                continue
            if not character_name:
                raise ValueError(
                    "Enter a character name for each relationship, or remove the blank row."
                )
            if not description:
                continue
            if (
                isinstance(original_relationships, dict)
                and character_name in original_relationships
                and self._display_text(original_relationships[character_name]).strip()
                == description
            ):
                relationships[character_name] = copy.deepcopy(
                    original_relationships[character_name]
                )
            else:
                relationships[character_name] = description
        if relationships or "relationships" in self.original:
            result["relationships"] = relationships

        custom_names: set[str] = set()
        for item in self.custom_field_rows:
            key = item["key"].get().strip()
            value = item["value"].get().strip()
            original_key = item["original_key"]
            if item["removed"]:
                if original_key:
                    result.pop(original_key, None)
                continue
            if not key and not value:
                continue
            if not key:
                raise ValueError(
                    "Give each custom field a name, or leave the whole row blank."
                )
            if key in _STANDARD_FIELDS:
                raise ValueError(
                    f"'{key}' is already a standard Character Card field. "
                    "Use its section instead."
                )
            if key in custom_names:
                raise ValueError(f"The custom field '{key}' appears more than once.")
            custom_names.add(key)
            if original_key and original_key != key:
                result.pop(original_key, None)
            if item["nested"]:
                result[key] = copy.deepcopy(item["original_value"])
            else:
                original_value = item["original_value"]
                if item["original"] and value == self._display_scalar(original_value):
                    result[key] = copy.deepcopy(original_value)
                elif value:
                    result[key] = value
                elif item["original"]:
                    result[key] = ""

        return result


    def save(self) -> None:
        try:
            data = self.build_card()
        except ValueError as exc:
            messagebox.showerror("Character Card needs attention", str(exc), parent=self.window)
            return
        self.on_save(data)

    def cancel(self) -> None:
        self.on_cancel()
