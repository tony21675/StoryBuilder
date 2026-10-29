from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from builder.novel_browser import list_novel_packages
from builder.novel_creator import create_novel_package, suggest_folder_name
from builder.story_bible_reader import load_story_bible, save_story_bible_premise
from builder.workspace import NOVEL_ROOT


class StoryBibleApp:
    """Create novel packages and view or edit the premise of a Story Bible."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Story Bible")
        self.root.geometry("840x740")
        self.root.minsize(700, 600)

        self.title_var = tk.StringVar()
        self.folder_var = tk.StringVar()
        self.create_status_var = tk.StringVar(
            value="Ready. Creating a package will not overwrite existing files."
        )
        self.viewer_status_var = tk.StringVar(value="Choose a novel to view its Story Bible.")
        self._folder_manually_edited = False
        self._novel_paths: dict[str, Path] = {}
        self._loaded_novel_path: Path | None = None
        self._loaded_novel_label = ""
        self._loaded_premise: str | None = None
        self._premise_editing = False

        outer = ttk.Frame(root, padding=12)
        outer.pack(fill="both", expand=True)
        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill="both", expand=True)

        create_tab = ttk.Frame(self.tabs, padding=18)
        view_tab = ttk.Frame(self.tabs, padding=18)
        self.tabs.add(create_tab, text="Create Novel")
        self.tabs.add(view_tab, text="View Story Bible")

        self._build_create_tab(create_tab)
        self._build_view_tab(view_tab)
        self.refresh_novels()
        self.title_entry.focus_set()

    def _build_create_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent, text="Create a Novel Package", font=("TkDefaultFont", 16, "bold")
        ).pack(anchor="w")
        ttk.Label(
            parent,
            text=(
                "Start a new novel with an empty Story Bible and the manuscript folder "
                "structure used by the Writer."
            ),
            wraplength=740,
        ).pack(anchor="w", pady=(4, 18))

        ttk.Label(parent, text="Novel title").pack(anchor="w")
        self.title_entry = ttk.Entry(parent, textvariable=self.title_var)
        self.title_entry.pack(fill="x", pady=(4, 12))
        self.title_entry.bind("<KeyRelease>", self._suggest_folder_name)

        ttk.Label(parent, text="Folder name (optional)").pack(anchor="w")
        folder_entry = ttk.Entry(parent, textvariable=self.folder_var)
        folder_entry.pack(fill="x", pady=(4, 3))
        folder_entry.bind("<KeyRelease>", self._mark_folder_custom)
        ttk.Label(
            parent,
            text="Leave blank to make a safe folder name from the title.",
            foreground="gray",
        ).pack(anchor="w", pady=(0, 14))

        ttk.Label(parent, text="Novel library").pack(anchor="w")
        root_entry = ttk.Entry(parent)
        root_entry.insert(0, str(NOVEL_ROOT))
        root_entry.configure(state="readonly")
        root_entry.pack(fill="x", pady=(4, 14))

        self.create_button = ttk.Button(
            parent, text="Create Novel Package", command=self.create_novel
        )
        self.create_button.pack(anchor="w")

        ttk.Label(
            parent,
            textvariable=self.create_status_var,
            anchor="w",
            justify="left",
            wraplength=740,
        ).pack(fill="x", pady=(14, 0))

    def _build_view_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(5, weight=1)

        ttk.Label(
            parent, text="View Story Bible", font=("TkDefaultFont", 16, "bold")
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            parent,
            text=(
                "Load an existing Story Bible below. The first editable field is Premise; "
                "other fields remain untouched."
            ),
            wraplength=760,
        ).grid(row=1, column=0, sticky="w", pady=(4, 12))

        ttk.Label(parent, text="Novel library").grid(row=2, column=0, sticky="w")
        path_row = ttk.Frame(parent)
        path_row.grid(row=3, column=0, sticky="ew", pady=(4, 10))
        path_row.columnconfigure(0, weight=1)

        self.novel_combo = ttk.Combobox(path_row, state="readonly")
        self.novel_combo.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.novel_combo.bind("<<ComboboxSelected>>", self._novel_selection_changed)
        self.refresh_button = ttk.Button(
            path_row, text="Refresh Novels", command=self.refresh_novels
        )
        self.refresh_button.grid(row=0, column=1, padx=(0, 8))
        self.load_button = ttk.Button(
            path_row, text="Load Story Bible", command=self.load_selected_story_bible
        )
        self.load_button.grid(row=0, column=2)

        premise_frame = ttk.LabelFrame(parent, text="Premise", padding=8)
        premise_frame.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        premise_frame.columnconfigure(0, weight=1)
        self.premise_text = tk.Text(
            premise_frame,
            wrap="word",
            height=4,
            state="disabled",
            undo=True,
            padx=8,
            pady=6,
        )
        self.premise_text.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.premise_text.bind("<Control-a>", self._select_all_premise)
        self.premise_text.bind("<Control-A>", self._select_all_premise)
        self.premise_text.bind("<Control-c>", self._copy_selected_premise)
        self.premise_text.bind("<Control-C>", self._copy_selected_premise)
        premise_buttons = ttk.Frame(premise_frame)
        premise_buttons.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.edit_premise_button = ttk.Button(
            premise_buttons, text="Edit Premise", command=self.start_premise_edit,
            state="disabled",
        )
        self.edit_premise_button.pack(side="left", padx=(0, 8))
        self.save_premise_button = ttk.Button(
            premise_buttons, text="Save Premise", command=self.save_premise,
            state="disabled",
        )
        self.save_premise_button.pack(side="left", padx=(0, 8))
        self.cancel_premise_button = ttk.Button(
            premise_buttons, text="Cancel Edit", command=self.cancel_premise_edit,
            state="disabled",
        )
        self.cancel_premise_button.pack(side="left")

        viewer_frame = ttk.Frame(parent)
        viewer_frame.grid(row=5, column=0, sticky="nsew")
        viewer_frame.columnconfigure(0, weight=1)
        viewer_frame.rowconfigure(0, weight=1)

        self.story_bible_text = tk.Text(
            viewer_frame,
            wrap="word",
            state="disabled",
            undo=False,
            padx=10,
            pady=8,
        )
        scrollbar = ttk.Scrollbar(
            viewer_frame, orient="vertical", command=self.story_bible_text.yview
        )
        self.story_bible_text.configure(yscrollcommand=scrollbar.set)
        self.story_bible_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Keep the JSON viewer read-only while allowing normal selection/copy.
        self.story_bible_text.bind("<Control-a>", self._select_all_story_bible)
        self.story_bible_text.bind("<Control-A>", self._select_all_story_bible)
        self.story_bible_text.bind("<Control-c>", self._copy_selected_story_bible)
        self.story_bible_text.bind("<Control-C>", self._copy_selected_story_bible)

        ttk.Label(
            parent,
            textvariable=self.viewer_status_var,
            anchor="w",
            justify="left",
            wraplength=760,
        ).grid(row=6, column=0, sticky="ew", pady=(8, 0))

    def _suggest_folder_name(self, _event=None) -> None:
        if not self._folder_manually_edited:
            self.folder_var.set(suggest_folder_name(self.title_var.get()))

    def _mark_folder_custom(self, _event=None) -> None:
        self._folder_manually_edited = True

    def create_novel(self) -> None:
        title = self.title_var.get()
        folder = self.folder_var.get()
        if not title.strip():
            self.create_status_var.set("Enter a title for the new novel.")
            self.title_entry.focus_set()
            return
        try:
            package_path = create_novel_package(title, folder)
        except (OSError, ValueError) as exc:
            self.create_status_var.set("Novel package was not created.")
            messagebox.showerror("Could not create novel", str(exc), parent=self.root)
            return

        self.create_status_var.set(
            f"Created successfully:\n{package_path}\n\n"
            "Open View Story Bible and click Refresh Novels to load it. "
            "No files were overwritten."
        )
        self.title_var.set("")
        self.folder_var.set("")
        self._folder_manually_edited = False
        self.title_entry.focus_set()

    def refresh_novels(self) -> None:
        packages = list_novel_packages(NOVEL_ROOT)
        self._novel_paths = {}
        labels = []
        for package in packages:
            label = f"{package.name}  [{package}]"
            self._novel_paths[label] = package
            labels.append(label)

        self.novel_combo.configure(values=labels)
        self._reset_loaded_story_bible()
        self._set_story_bible_text("Choose a novel above, then click Load Story Bible.")
        if labels:
            self.novel_combo.set(labels[0])
            self.viewer_status_var.set(
                f"Found {len(labels)} novel package(s). "
                "Select one and click Load Story Bible."
            )
        else:
            self.novel_combo.set("")
            self.viewer_status_var.set(
                f"No novel packages with story_bible.json were found in {NOVEL_ROOT}."
            )

    def _novel_selection_changed(self, _event=None) -> None:
        self._reset_loaded_story_bible()
        self.novel_combo.configure(state="readonly")
        self._set_story_bible_text("Click Load Story Bible to display this novel's file.")
        self.viewer_status_var.set("Novel selected. The Story Bible has not been loaded yet.")

    def load_selected_story_bible(self) -> None:
        package = self._novel_paths.get(self.novel_combo.get())
        if package is None:
            self.viewer_status_var.set("Choose a novel first.")
            return

        try:
            data = load_story_bible(package)
            formatted = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        except (OSError, ValueError) as exc:
            self._reset_loaded_story_bible()
            self._set_story_bible_text(f"Could not load Story Bible:\n\n{exc}\n")
            self.viewer_status_var.set(
                "Story Bible could not be loaded. The file was not changed."
            )
            return

        self._loaded_novel_path = package
        self._loaded_novel_label = self.novel_combo.get()
        premise = data.get("premise", "")
        self._loaded_premise = premise if isinstance(premise, str) else None
        self._set_premise_text(premise if isinstance(premise, str) else "")
        self._set_story_bible_text(formatted)
        self._set_premise_controls(editable=False)
        if self._loaded_premise is None:
            self.viewer_status_var.set(
                f"Loaded: {package / 'story_bible.json'}. "
                "Premise is not text, so premise editing is disabled."
            )
        else:
            self.viewer_status_var.set(f"Loaded read-only: {package / 'story_bible.json'}")

    def start_premise_edit(self) -> None:
        if self._loaded_novel_path is None or self._loaded_premise is None:
            self.viewer_status_var.set("Load a Story Bible with a text premise first.")
            return
        self._premise_editing = True
        self.premise_text.configure(state="normal")
        self.premise_text.focus_set()
        self.edit_premise_button.configure(state="disabled")
        self.save_premise_button.configure(state="normal")
        self.cancel_premise_button.configure(state="normal")
        self.novel_combo.configure(state="disabled")
        self.refresh_button.configure(state="disabled")
        self.load_button.configure(state="disabled")
        self.viewer_status_var.set(
            "Editing Premise. Choose Save Premise to write only this field, "
            "or Cancel Edit to discard your changes."
        )

    def save_premise(self) -> None:
        if not self._premise_editing or self._loaded_novel_path is None:
            self.viewer_status_var.set("Choose Edit Premise before saving.")
            return

        new_premise = self.premise_text.get("1.0", "end-1c")
        try:
            save_story_bible_premise(self._loaded_novel_path, new_premise)
            data = load_story_bible(self._loaded_novel_path)
        except (OSError, ValueError, RuntimeError) as exc:
            self.viewer_status_var.set(f"Premise was not saved:\n{exc}")
            return

        self._loaded_premise = new_premise
        self._set_story_bible_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        self._set_premise_text(new_premise)
        self._finish_premise_edit()
        self.viewer_status_var.set(
            f"Saved premise only: {self._loaded_novel_path / 'story_bible.json'}. "
            "Other Story Bible fields were preserved."
        )

    def cancel_premise_edit(self) -> None:
        if not self._premise_editing:
            return
        self._set_premise_text(self._loaded_premise or "")
        self._finish_premise_edit()
        self.viewer_status_var.set("Premise edit cancelled; no file changes were made.")

    def _finish_premise_edit(self) -> None:
        self._premise_editing = False
        self._set_premise_text(self._loaded_premise or "")
        self._set_premise_controls(editable=False)
        self.novel_combo.configure(state="readonly")
        self.refresh_button.configure(state="normal")
        self.load_button.configure(state="normal")

    def _set_premise_controls(self, editable: bool) -> None:
        self._premise_editing = editable
        self.premise_text.configure(state="normal" if editable else "disabled")
        has_text_premise = self._loaded_novel_path is not None and self._loaded_premise is not None
        self.edit_premise_button.configure(
            state="normal" if has_text_premise and not editable else "disabled"
        )
        self.save_premise_button.configure(state="normal" if editable else "disabled")
        self.cancel_premise_button.configure(state="normal" if editable else "disabled")

    def _set_premise_text(self, content: str) -> None:
        self.premise_text.configure(state="normal")
        self.premise_text.delete("1.0", "end")
        self.premise_text.insert("1.0", content)
        self.premise_text.configure(state="normal" if self._premise_editing else "disabled")
        self.premise_text.tag_remove("sel", "1.0", "end")

    def _reset_loaded_story_bible(self) -> None:
        self._loaded_novel_path = None
        self._loaded_novel_label = ""
        self._loaded_premise = None
        self._premise_editing = False
        self._set_premise_text("")
        self._set_premise_controls(editable=False)
        if hasattr(self, "novel_combo"):
            self.novel_combo.configure(state="readonly")
        if hasattr(self, "refresh_button"):
            self.refresh_button.configure(state="normal")
        if hasattr(self, "load_button"):
            self.load_button.configure(state="normal")

    def _set_story_bible_text(self, content: str) -> None:
        self.story_bible_text.configure(state="normal")
        self.story_bible_text.delete("1.0", "end")
        self.story_bible_text.insert("1.0", content)
        self.story_bible_text.configure(state="disabled")
        self.story_bible_text.tag_remove("sel", "1.0", "end")

    def _select_all_story_bible(self, _event=None):
        return self._select_all_text(self.story_bible_text)

    def _copy_selected_story_bible(self, _event=None):
        return self._copy_selected_text(self.story_bible_text)

    def _select_all_premise(self, _event=None):
        return self._select_all_text(self.premise_text)

    def _copy_selected_premise(self, _event=None):
        return self._copy_selected_text(self.premise_text)

    def _select_all_text(self, widget: tk.Text):
        widget.tag_add("sel", "1.0", "end-1c")
        widget.mark_set("insert", "1.0")
        widget.see("1.0")
        return "break"

    def _copy_selected_text(self, widget: tk.Text):
        try:
            selected = widget.get("sel.first", "sel.last")
        except tk.TclError:
            return "break"
        self.root.clipboard_clear()
        self.root.clipboard_append(selected)
        return "break"


def main() -> None:
    root = tk.Tk()
    StoryBibleApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
