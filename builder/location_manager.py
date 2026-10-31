from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable

import tkinter as tk
from tkinter import messagebox, ttk

from builder.location_editor import LocationEditorWindow
from builder.story_bible_reader import (
    load_story_bible,
    save_story_bible_locations,
)


class LocationManagerWindow:
    """Manage one Story Bible's name-keyed locations collection."""

    def __init__(
        self,
        parent: tk.Misc,
        novel_path: str | Path,
        locations: dict[str, Any],
        on_saved: Callable[[dict[str, Any]], None],
        on_close: Callable[[], None],
    ) -> None:
        self.novel_path = Path(novel_path)
        self.locations = copy.deepcopy(locations)
        self.on_saved = on_saved
        self.on_close = on_close
        self.editor: LocationEditorWindow | None = None
        self.editor_window: tk.Toplevel | None = None
        self.editing_name: str | None = None

        self.window = tk.Toplevel(parent)
        self.window.title(f"Locations: {self.novel_path.name}")
        self.window.geometry("760x540")
        self.window.minsize(620, 420)
        self.window.transient(parent.winfo_toplevel())
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        frame = ttk.Frame(self.window, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=2)
        frame.rowconfigure(1, weight=1)

        ttk.Label(
            frame, text="Locations", font=("TkDefaultFont", 14, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        list_frame = ttk.Frame(frame)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.listbox = tk.Listbox(list_frame, height=12, exportselection=False)
        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.listbox.yview
        )
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox.bind("<<ListboxSelect>>", self.selection_changed)

        preview_frame = ttk.LabelFrame(frame, text="Selected Location", padding=8)
        preview_frame.grid(row=1, column=1, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        self.preview = tk.Text(
            preview_frame, wrap="word", state="disabled", undo=False, padx=8, pady=8
        )
        preview_scrollbar = ttk.Scrollbar(
            preview_frame, orient="vertical", command=self.preview.yview
        )
        self.preview.configure(yscrollcommand=preview_scrollbar.set)
        self.preview.grid(row=0, column=0, sticky="nsew")
        preview_scrollbar.grid(row=0, column=1, sticky="ns")
        self.preview.bind("<Control-a>", lambda _event: self._select_all(self.preview))
        self.preview.bind("<Control-A>", lambda _event: self._select_all(self.preview))
        self.preview.bind("<Control-c>", lambda _event: self._copy(self.preview))
        self.preview.bind("<Control-C>", lambda _event: self._copy(self.preview))

        button_row = ttk.Frame(frame)
        button_row.grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self.add_button = ttk.Button(
            button_row, text="Add Location", command=self.add_location
        )
        self.add_button.pack(side="left", padx=(0, 8))
        self.edit_button = ttk.Button(
            button_row, text="Edit Selected", command=self.edit_location,
            state="disabled",
        )
        self.edit_button.pack(side="left", padx=(0, 8))
        self.remove_button = ttk.Button(
            button_row, text="Remove Selected", command=self.remove_location,
            state="disabled",
        )
        self.remove_button.pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="Close", command=self.close).pack(side="left")

        ttk.Label(
            frame,
            text=(
                "Name is required. All other details are optional. Editing changes only "
                "the selected location; removing a location removes only its Story Bible entry."
            ),
            foreground="gray",
            wraplength=700,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))

        self._refresh()
        self.window.grab_set()

    @staticmethod
    def _details_text(name: str, details: dict[str, Any] | str) -> str:
        if isinstance(details, str):
            return f"Name: {name}\n\nDescription:\n{details}"
        labels = {
            "type": "Type",
            "description": "Description",
            "geography": "Geography",
            "climate": "Climate",
            "notable_details": "Notable Details",
        }
        lines = [f"Name: {name}"]
        for key, value in details.items():
            label = labels.get(key, key.replace("_", " ").title())
            display = LocationEditorWindow._human_readable_value(value)
            lines.append(f"{label}:\n{display}")
        if len(lines) == 1:
            lines.append("No optional details have been entered.")
        return "\n\n".join(lines)

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

    def _set_preview(self, content: str) -> None:
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", content)
        self.preview.configure(state="disabled")
        self.preview.tag_remove("sel", "1.0", "end")

    def _set_buttons(self, name: str | None) -> None:
        selected = name is not None and name in self.locations
        self.edit_button.configure(state="normal" if selected else "disabled")
        self.remove_button.configure(state="normal" if selected else "disabled")

    def _refresh(self, selected_name: str | None = None) -> None:
        names = list(self.locations)
        self.listbox.delete(0, "end")
        for name in names:
            self.listbox.insert("end", name)
        if selected_name in names:
            index = names.index(selected_name)
            self.listbox.selection_set(index)
            self.listbox.activate(index)
            self.listbox.see(index)
            self.selection_changed()
        elif names:
            self._set_preview("Select a location to view its details.")
            self._set_buttons(None)
        else:
            self._set_preview("No locations have been added yet.")
            self._set_buttons(None)

    def selection_changed(self, _event=None) -> None:
        selection = self.listbox.curselection()
        if not selection:
            self._set_preview("Select a location to view its details.")
            self._set_buttons(None)
            return
        names = list(self.locations)
        index = int(selection[0])
        if not 0 <= index < len(names):
            self._set_buttons(None)
            return
        name = names[index]
        self._set_preview(self._details_text(name, self.locations[name]))
        self._set_buttons(name)

    def add_location(self) -> None:
        self._open_editor(None, {})

    def edit_location(self) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        names = list(self.locations)
        index = int(selection[0])
        if not 0 <= index < len(names):
            return
        name = names[index]
        details = self.locations[name]
        existing = {"description": details} if isinstance(details, str) else details
        if not isinstance(existing, dict):
            messagebox.showerror(
                "Location cannot be edited",
                "This location uses an unsupported format and was left unchanged.",
                parent=self.window,
            )
            return
        self._open_editor(name, existing)

    def _open_editor(
        self, original_name: str | None, existing: dict[str, Any]
    ) -> None:
        if self.editor_window is not None:
            return
        self.editing_name = original_name
        title = "Edit Location" if original_name is not None else "Add Location"
        self.editor = LocationEditorWindow(
            parent=self.window,
            existing=existing,
            title=title,
            on_save=self.save_location,
            on_cancel=self.cancel_edit,
        )
        self.editor_window = self.editor.window

    def save_location(self, name: str, details: dict[str, Any]) -> None:
        name = name.strip()
        if not name:
            messagebox.showerror(
                "Location needs a name", "Name is required.", parent=self.editor_window
            )
            return
        original_name = self.editing_name
        if original_name is not None and original_name not in self.locations:
            messagebox.showerror(
                "Location was not saved",
                "The selected entry changed. Close and reload the Locations manager.",
                parent=self.editor_window,
            )
            return
        duplicate = next(
            (
                current for current in self.locations
                if current.casefold() == name.casefold() and current != original_name
            ),
            None,
        )
        if duplicate is not None:
            messagebox.showerror(
                "Location already exists",
                f"A location named '{duplicate}' already exists.",
                parent=self.editor_window,
            )
            return

        updated: dict[str, Any] = {}
        replaced = False
        for current_name, current_details in self.locations.items():
            if current_name == original_name:
                updated[name] = details
                replaced = True
            else:
                updated[current_name] = current_details
        if not replaced:
            updated[name] = details

        try:
            save_story_bible_locations(self.novel_path, updated)
            data = load_story_bible(self.novel_path)
        except (OSError, ValueError, RuntimeError) as exc:
            messagebox.showerror(
                "Location was not saved", str(exc), parent=self.editor_window
            )
            return

        self.locations = copy.deepcopy(data["locations"])
        self.on_saved(data)
        self._finish_editor()
        self._refresh(name)

    def cancel_edit(self) -> None:
        if self.editor_window is not None:
            self._finish_editor()

    def _finish_editor(self) -> None:
        window = self.editor_window
        self.editor_window = None
        self.editor = None
        self.editing_name = None
        if window is not None:
            try:
                if window.winfo_exists():
                    window.grab_release()
                    window.destroy()
            except tk.TclError:
                pass
        try:
            self.window.grab_set()
        except tk.TclError:
            pass

    def remove_location(self) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        names = list(self.locations)
        index = int(selection[0])
        if not 0 <= index < len(names):
            return
        name = names[index]
        if not messagebox.askyesno(
            "Remove Location",
            f"Remove '{name}' from this Story Bible? Only this location entry will be removed.",
            parent=self.window,
        ):
            return
        updated = dict(self.locations)
        updated.pop(name, None)
        try:
            save_story_bible_locations(self.novel_path, updated)
            data = load_story_bible(self.novel_path)
        except (OSError, ValueError, RuntimeError) as exc:
            messagebox.showerror("Location was not removed", str(exc), parent=self.window)
            return
        self.locations = copy.deepcopy(data["locations"])
        self.on_saved(data)
        remaining = list(self.locations)
        next_name = remaining[min(index, len(remaining) - 1)] if remaining else None
        self._refresh(next_name)

    def close(self) -> None:
        if self.editor_window is not None:
            self.cancel_edit()
        try:
            if self.window.winfo_exists():
                self.window.grab_release()
                self.window.destroy()
        except tk.TclError:
            pass
        self.on_close()
