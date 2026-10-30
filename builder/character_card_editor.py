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
        self.relationships_widget: tk.Text | None = None
        self.custom_fields_widget: tk.Text | None = None

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
        self, parent: ttk.Frame, key: str, label: str, value: Any = ""
    ) -> int:
        row = self._next_row(parent)
        ttk.Label(parent, text=f"{label} (optional)").grid(
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
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    @staticmethod
    def _display_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return json.dumps(value, indent=2, ensure_ascii=False)

    @staticmethod
    def _display_list(value: Any) -> str:
        if isinstance(value, list):
            return "\n".join(str(item) for item in value)
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
        self._add_entry(parent, "name", "Name", self.original.get("name", ""))
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
            text="One relationship per line: Character Name: description. "
            "You can leave this section empty.",
            wraplength=650,
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.relationships_widget = tk.Text(
            parent, height=18, wrap="word", undo=True, padx=8, pady=6
        )
        self.relationships_widget.grid(row=1, column=0, sticky="nsew")
        relationships = self.original.get("relationships", {})
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        if isinstance(relationships, dict):
            lines = []
            for key, value in relationships.items():
                if isinstance(value, str):
                    display = value
                else:
                    display = json.dumps(value, ensure_ascii=False)
                lines.append(f"{key}: {display}")
            self.relationships_widget.insert("1.0", "\n".join(lines))
        elif isinstance(relationships, str):
            self.relationships_widget.insert("1.0", relationships)
        self._bind_copy(self.relationships_widget)
        self._set_next_row(parent, 2)

    def _build_additional_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            text=(
                "Optional custom or less-common fields. Existing data is shown here and "
                "preserved unless you change this JSON object."
            ),
            wraplength=650,
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        known = set(_STANDARD_FIELDS)
        custom = {key: value for key, value in self.original.items() if key not in known}
        self.custom_fields_widget = tk.Text(
            parent, height=22, wrap="none", undo=True, padx=8, pady=6
        )
        custom_scroll = ttk.Scrollbar(parent, orient="vertical", command=self.custom_fields_widget.yview)
        self.custom_fields_widget.configure(yscrollcommand=custom_scroll.set)
        self.custom_fields_widget.grid(row=1, column=0, sticky="nsew")
        custom_scroll.grid(row=1, column=1, sticky="ns")
        self.custom_fields_widget.insert(
            "1.0", json.dumps(custom, indent=2, ensure_ascii=False)
        )
        self._bind_copy(self.custom_fields_widget)
        self._set_next_row(parent, 2)

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
            except ValueError as exc:
                raise ValueError("Age must be a whole number, or left blank.") from exc
        elif "age" in self.original:
            result["age"] = ""

        for key in _TEXT_FIELDS:
            value = self.text_widgets[key].get("1.0", "end-1c")
            if value.strip() or key in self.original:
                result[key] = value.strip()

        for key in _LIST_FIELDS:
            items = [
                line.strip()
                for line in self.list_widgets[key].get("1.0", "end-1c").splitlines()
                if line.strip()
            ]
            if items or key in self.original:
                result[key] = items

        appearance = copy.deepcopy(self.original_appearance)
        if isinstance(appearance, str):
            appearance = {"notes": appearance}
        if not isinstance(appearance, dict):
            appearance = {}
        for key, variable in self.appearance_vars.items():
            value = variable.get().strip()
            if value:
                appearance[key] = value
            elif key in appearance:
                appearance[key] = ""
        if appearance or "appearance" in self.original:
            result["appearance"] = appearance

        relationship_lines = self.relationships_widget.get("1.0", "end-1c").splitlines()
        relationships: dict[str, Any] = {}
        for line in relationship_lines:
            if not line.strip():
                continue
            key, separator, value = line.partition(":")
            if not separator or not key.strip():
                raise ValueError(
                    "Each relationship must use the format Character Name: description."
                )
            raw_value = value.strip()
            try:
                parsed_value = json.loads(raw_value)
            except json.JSONDecodeError:
                parsed_value = raw_value
            relationships[key.strip()] = parsed_value
        if relationships or "relationships" in self.original:
            result["relationships"] = relationships

        custom_text = self.custom_fields_widget.get("1.0", "end-1c").strip()
        try:
            custom = json.loads(custom_text or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Additional Fields must be a valid JSON object (line {exc.lineno}, column {exc.colno})."
            ) from exc
        if not isinstance(custom, dict):
            raise ValueError("Additional Fields must be a JSON object.")
        if set(custom) & _STANDARD_FIELDS:
            raise ValueError(
                "Additional Fields cannot replace standard character fields. "
                "Use the matching tab instead."
            )
        for key in set(self.original) - _STANDARD_FIELDS:
            result.pop(key, None)
        result.update(custom)
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
