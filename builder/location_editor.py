from __future__ import annotations

import copy
from typing import Any, Callable

import tkinter as tk
from tkinter import ttk


_ENTRY_FIELDS = {
    "type": "Type",
    "geography": "Geography",
    "climate": "Climate",
}
_TEXT_FIELDS = {
    "description": "Description",
    "notable_details": "Notable Details",
}
_STANDARD_FIELDS = set(_ENTRY_FIELDS) | set(_TEXT_FIELDS)


class LocationEditorWindow:
    """Plain-English location editor that carries unknown JSON data forward."""

    def __init__(
        self,
        parent: tk.Misc,
        existing: dict[str, Any] | None,
        title: str,
        on_save: Callable[[str, dict[str, Any]], None],
        on_cancel: Callable[[], None],
    ) -> None:
        self.original = copy.deepcopy(existing or {})
        self.on_save = on_save
        self.on_cancel = on_cancel
        self.entry_vars: dict[str, tk.StringVar] = {}
        self.text_widgets: dict[str, tk.Text] = {}
        self.custom_field_rows: list[dict[str, Any]] = []

        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.geometry("740x660")
        self.window.minsize(580, 480)
        self.window.transient(parent.winfo_toplevel())
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)

        outer = ttk.Frame(self.window, padding=10)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        scroll_frame = ttk.Frame(outer)
        scroll_frame.grid(row=0, column=0, sticky="nsew")
        scroll_frame.columnconfigure(0, weight=1)
        scroll_frame.rowconfigure(0, weight=1)
        canvas = tk.Canvas(scroll_frame, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        form = ttk.Frame(canvas, padding=8)
        form.columnconfigure(0, weight=1)
        form_window = canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(form_window, width=event.width),
        )

        row = 0
        ttk.Label(form, text="Name (required)").grid(
            row=row, column=0, sticky="w", pady=(0, 2)
        )
        self.name_var = tk.StringVar(self.window, value="")
        self.name_entry = ttk.Entry(form, textvariable=self.name_var)
        self.name_entry.grid(row=row + 1, column=0, sticky="ew", pady=(0, 10))
        row += 2

        for key, label in _ENTRY_FIELDS.items():
            self._add_entry(form, row, key, label, self.original.get(key, ""))
            row += 2

        for key, label in _TEXT_FIELDS.items():
            self._add_text(form, row, key, label, self.original.get(key, ""))
            row += 2

        custom_frame = ttk.LabelFrame(
            form, text="Additional Information (optional)", padding=8
        )
        custom_frame.grid(row=row, column=0, sticky="ew", pady=(10, 4))
        custom_frame.columnconfigure(0, weight=1)
        ttk.Label(
            custom_frame,
            text=(
                "Add extra details that do not fit the fields above. Existing custom "
                "information is kept unless you deliberately remove it."
            ),
            wraplength=650,
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.custom_fields_frame = ttk.Frame(custom_frame)
        self.custom_fields_frame.grid(row=1, column=0, sticky="ew")
        self.custom_fields_frame.columnconfigure(1, weight=1)
        ttk.Label(self.custom_fields_frame, text="Field name").grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        ttk.Label(self.custom_fields_frame, text="Value").grid(
            row=0, column=1, sticky="w"
        )
        self._next_custom_row = 1
        for key, value in self.original.items():
            if key not in _STANDARD_FIELDS:
                self._add_custom_field_row(key, value, original=True)
        ttk.Button(
            custom_frame, text="Add Field", command=self._add_custom_field_row
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))

        button_row = ttk.Frame(outer)
        button_row.grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            button_row, text="Save Location", command=self.save
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            button_row, text="Cancel Edit", command=self.cancel
        ).pack(side="left")
        ttk.Label(
            outer,
            text="Only this location will be saved. All details except Name are optional.",
            foreground="gray",
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))

        self.window.grab_set()
        self.window.after_idle(self.name_entry.focus_set)

    @staticmethod
    def _display_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return LocationEditorWindow._human_readable_value(value)
        return str(value)

    @staticmethod
    def _human_readable_value(value: Any, indent: int = 0) -> str:
        prefix = " " * indent
        if isinstance(value, dict):
            lines = []
            for key, nested in value.items():
                label = str(key).replace("_", " ").title()
                if isinstance(nested, (dict, list)):
                    lines.append(f"{prefix}{label}:")
                    lines.append(
                        LocationEditorWindow._human_readable_value(nested, indent + 2)
                    )
                else:
                    lines.append(
                        f"{prefix}{label}: {LocationEditorWindow._display_value(nested)}"
                    )
            return "\n".join(lines)
        if isinstance(value, list):
            return "\n".join(
                f"{prefix}• {LocationEditorWindow._human_readable_value(item, indent)}"
                for item in value
            )
        return f"{prefix}{LocationEditorWindow._display_value(value)}"

    def _add_entry(
        self, parent: ttk.Frame, row: int, key: str, label: str, value: Any
    ) -> None:
        ttk.Label(parent, text=f"{label} (optional)").grid(
            row=row, column=0, sticky="w", pady=(4, 2)
        )
        variable = tk.StringVar(self.window, value=self._display_value(value))
        self.entry_vars[key] = variable
        ttk.Entry(parent, textvariable=variable).grid(
            row=row + 1, column=0, sticky="ew", pady=(0, 6)
        )

    def _add_text(
        self, parent: ttk.Frame, row: int, key: str, label: str, value: Any
    ) -> None:
        ttk.Label(parent, text=f"{label} (optional)").grid(
            row=row, column=0, sticky="w", pady=(4, 2)
        )
        editor_frame = ttk.Frame(parent)
        editor_frame.grid(row=row + 1, column=0, sticky="ew", pady=(0, 6))
        editor_frame.columnconfigure(0, weight=1)
        widget = tk.Text(editor_frame, height=4, wrap="word", undo=True, padx=6, pady=5)
        scrollbar = ttk.Scrollbar(editor_frame, orient="vertical", command=widget.yview)
        widget.configure(yscrollcommand=scrollbar.set)
        widget.grid(row=0, column=0, sticky="ew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        widget.insert("1.0", self._display_value(value))
        widget.bind("<Control-a>", lambda _event, target=widget: self._select_all(target))
        widget.bind("<Control-A>", lambda _event, target=widget: self._select_all(target))
        widget.bind("<Control-c>", lambda _event, target=widget: self._copy(target))
        widget.bind("<Control-C>", lambda _event, target=widget: self._copy(target))
        self.text_widgets[key] = widget

    def _add_custom_field_row(
        self, key: str = "", value: Any = "", *, original: bool = False
    ) -> None:
        row_frame = ttk.Frame(self.custom_fields_frame)
        row_frame.grid(row=self._next_custom_row, column=0, sticky="ew", pady=(3, 5))
        row_frame.columnconfigure(1, weight=1)
        key_var = tk.StringVar(self.window, value=key)
        ttk.Entry(row_frame, textvariable=key_var, width=22).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        value_var = tk.StringVar(self.window, value=self._display_value(value))
        nested = isinstance(value, (dict, list))
        if nested:
            ttk.Label(
                row_frame,
                text=self._display_value(value),
                justify="left",
                wraplength=430,
            ).grid(row=0, column=1, sticky="w")
            value_var.set("")
        else:
            ttk.Entry(row_frame, textvariable=value_var).grid(
                row=0, column=1, sticky="ew"
            )
        ttk.Button(
            row_frame,
            text="Remove",
            command=lambda target=row_frame: self._remove_custom_field_row(target),
        ).grid(row=0, column=2, padx=(8, 0))
        self.custom_field_rows.append(
            {
                "key": key_var,
                "value": value_var,
                "nested": nested,
                "original": original,
                "original_key": key if original else None,
                "original_value": copy.deepcopy(value),
                "frame": row_frame,
                "removed": False,
            }
        )
        self._next_custom_row += 1

    def _remove_custom_field_row(self, row_frame: ttk.Frame) -> None:
        for item in self.custom_field_rows:
            if item["frame"] is row_frame:
                item["removed"] = True
                row_frame.destroy()
                break

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

    def build_location(self) -> tuple[str, dict[str, Any]]:
        name = self.name_var.get().strip()
        if not name:
            raise ValueError("Name is required.")

        result = copy.deepcopy(self.original)
        for key, variable in self.entry_vars.items():
            value = variable.get().strip()
            original_value = self.original.get(key)
            if key in self.original and value == self._display_value(original_value):
                continue
            if value or key in self.original:
                result[key] = value
            else:
                result.pop(key, None)

        for key, widget in self.text_widgets.items():
            value = widget.get("1.0", "end-1c").strip()
            original_value = self.original.get(key)
            if key in self.original and value == self._display_value(original_value):
                continue
            if value or key in self.original:
                result[key] = value
            else:
                result.pop(key, None)

        used_keys = set(_STANDARD_FIELDS)
        for item in self.custom_field_rows:
            original_key = item["original_key"]
            if item["removed"]:
                if original_key:
                    result.pop(original_key, None)
                continue

            key = item["key"].get().strip()
            if not key:
                continue
            if key in used_keys and key != original_key:
                raise ValueError(f"Field name '{key}' is already in use.")
            used_keys.add(key)

            if original_key and key != original_key:
                result.pop(original_key, None)

            if item["nested"]:
                result[key] = copy.deepcopy(item["original_value"])
                continue

            value = item["value"].get().strip()
            if (
                original_key == key
                and value == self._display_value(item["original_value"])
            ):
                result[key] = copy.deepcopy(item["original_value"])
            elif value:
                result[key] = value
            elif key in result:
                result[key] = ""

        return name, result

    def save(self) -> None:
        try:
            name, data = self.build_location()
        except ValueError as exc:
            from tkinter import messagebox
            messagebox.showerror("Location needs attention", str(exc), parent=self.window)
            return
        self.on_save(name, data)

    def cancel(self) -> None:
        self.on_cancel()
