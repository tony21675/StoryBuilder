from __future__ import annotations

import json
import threading
from typing import Any
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from builder.novel_browser import list_novel_packages
from builder.character_card_editor import CharacterCardEditorWindow
from builder.novel_creator import create_novel_package, suggest_folder_name
from builder.story_bible_reader import (
    load_story_bible,
    save_story_bible_premise,
    save_story_bible_text_field,
    save_story_bible_canon_rules,
    save_story_bible_character_cards,
    load_story_bible_character_card,
    save_story_bible_character_card_file,
    create_story_bible_character_card,
    remove_story_bible_character_card_reference,
)
from builder.novel_git_sync import (
    NovelGitSyncError,
    inspect_novel_repository,
    sync_novel_repository,
)
from builder.workspace import NOVEL_ROOT


class StoryBibleApp:
    """Create novel packages and view or edit selected text fields in a Story Bible."""

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
        self._premise_editor_window: tk.Toplevel | None = None
        self._premise_editor_text: tk.Text | None = None
        self._loaded_setting: str | None = None
        self._setting_editing = False
        self._setting_editor_window: tk.Toplevel | None = None
        self._setting_editor_text: tk.Text | None = None
        self._loaded_canon_rules: list[str] | None = None
        self._canon_rules_editing = False
        self._canon_rules_editor_window: tk.Toplevel | None = None
        self._canon_rules_editor_text: tk.Text | None = None
        self._loaded_character_cards: list[dict[str, Any] | str] | None = None
        self._character_cards_managing = False
        self._character_cards_manager_window: tk.Toplevel | None = None
        self._character_cards_manager_listbox: tk.Listbox | None = None
        self._character_cards_manager_preview: tk.Text | None = None
        self._character_cards_add_button: ttk.Button | None = None
        self._character_cards_edit_button: ttk.Button | None = None
        self._character_cards_remove_button: ttk.Button | None = None
        self._character_card_editor_window: tk.Toplevel | None = None
        self._character_card_name_var: tk.StringVar | None = None
        self._character_card_role_var: tk.StringVar | None = None
        self._character_card_editor_text: tk.Text | None = None
        self._character_card_edit_index: int | None = None
        self._character_card_filename: str | None = None
        self._character_card_editor: CharacterCardEditorWindow | None = None
        self._sync_in_progress = False
        self._view_canvas: tk.Canvas | None = None

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
        # Keep the entire tab in one scrollable surface so lower sections are
        # reachable even when the app window is shorter than the full form.
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        scroll_frame = ttk.Frame(parent)
        scroll_frame.grid(row=0, column=0, sticky="nsew")
        scroll_frame.columnconfigure(0, weight=1)
        scroll_frame.rowconfigure(0, weight=1)

        canvas = tk.Canvas(scroll_frame, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(
            scroll_frame, orient="vertical", command=canvas.yview
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        content = ttk.Frame(canvas)
        content_window = canvas.create_window(
            (0, 0), window=content, anchor="nw"
        )
        content.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(content_window, width=event.width),
        )
        self._view_canvas = canvas
        self.root.bind_all("<MouseWheel>", self._on_view_mousewheel, add="+")
        self.root.bind_all("<Button-4>", self._on_view_mousewheel_linux, add="+")
        self.root.bind_all("<Button-5>", self._on_view_mousewheel_linux, add="+")

        # All tab content is placed inside the canvas window.
        parent = content
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(9, weight=1)

        ttk.Label(
            parent, text="View Story Bible", font=("TkDefaultFont", 16, "bold")
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            parent,
            text=(
                "Load an existing Story Bible below. Premise, Setting, Canon Rules, "
                "and Character Cards have separate editors; other fields remain untouched."
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

        sync_row = ttk.Frame(parent)
        sync_row.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        self.sync_button = ttk.Button(
            sync_row,
            text="Sync Selected Novel to GitHub",
            command=self.sync_selected_novel_to_github,
        )
        self.sync_button.pack(side="left")
        ttk.Label(
            sync_row,
            text="Syncs this novel's own repository after you review a confirmation.",
        ).pack(side="left", padx=(10, 0))

        premise_frame = ttk.LabelFrame(parent, text="Premise", padding=8)
        premise_frame.grid(row=5, column=0, sticky="ew", pady=(0, 10))
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
        self.edit_premise_button.pack(side="left")

        setting_frame = ttk.LabelFrame(parent, text="Setting", padding=8)
        setting_frame.grid(row=6, column=0, sticky="ew", pady=(0, 10))
        setting_frame.columnconfigure(0, weight=1)
        self.setting_text = tk.Text(
            setting_frame,
            wrap="word",
            height=3,
            state="disabled",
            undo=False,
            padx=8,
            pady=6,
        )
        self.setting_text.grid(row=0, column=0, sticky="ew")
        self.setting_text.bind("<Control-a>", self._select_all_setting)
        self.setting_text.bind("<Control-A>", self._select_all_setting)
        self.setting_text.bind("<Control-c>", self._copy_selected_setting)
        self.setting_text.bind("<Control-C>", self._copy_selected_setting)
        self.edit_setting_button = ttk.Button(
            setting_frame,
            text="Edit Setting",
            command=self.start_setting_edit,
            state="disabled",
        )
        self.edit_setting_button.grid(row=1, column=0, sticky="w", pady=(8, 0))

        canon_rules_frame = ttk.LabelFrame(parent, text="Canon Rules", padding=8)
        canon_rules_frame.grid(row=7, column=0, sticky="ew", pady=(0, 10))
        canon_rules_frame.columnconfigure(0, weight=1)
        self.canon_rules_text = tk.Text(
            canon_rules_frame,
            wrap="word",
            height=4,
            state="disabled",
            undo=False,
            padx=8,
            pady=6,
        )
        self.canon_rules_text.grid(row=0, column=0, sticky="ew")
        self.canon_rules_text.bind("<Control-a>", self._select_all_canon_rules)
        self.canon_rules_text.bind("<Control-A>", self._select_all_canon_rules)
        self.canon_rules_text.bind("<Control-c>", self._copy_selected_canon_rules)
        self.canon_rules_text.bind("<Control-C>", self._copy_selected_canon_rules)
        self.edit_canon_rules_button = ttk.Button(
            canon_rules_frame,
            text="Edit Canon Rules",
            command=self.start_canon_rules_edit,
            state="disabled",
        )
        self.edit_canon_rules_button.grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(
            canon_rules_frame,
            text="One rule per line. Blank lines are ignored.",
            foreground="gray",
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))

        character_cards_frame = ttk.LabelFrame(parent, text="Character Cards", padding=8)
        character_cards_frame.grid(row=8, column=0, sticky="ew", pady=(0, 10))
        character_cards_frame.columnconfigure(0, weight=1)
        self.character_cards_text = tk.Text(
            character_cards_frame,
            wrap="word",
            height=3,
            state="disabled",
            undo=False,
            padx=8,
            pady=6,
        )
        self.character_cards_text.grid(row=0, column=0, sticky="ew")
        self.character_cards_text.bind("<Control-a>", self._select_all_character_cards)
        self.character_cards_text.bind("<Control-A>", self._select_all_character_cards)
        self.character_cards_text.bind("<Control-c>", self._copy_selected_character_cards)
        self.character_cards_text.bind("<Control-C>", self._copy_selected_character_cards)
        self.edit_character_cards_button = ttk.Button(
            character_cards_frame,
            text="Manage Character Cards",
            command=self.start_character_cards_manager,
            state="disabled",
        )
        self.edit_character_cards_button.grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(
            character_cards_frame,
            text="Structured cards have Name, Role, and Description. Older text cards remain unchanged.",
            foreground="gray",
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))

        viewer_frame = ttk.Frame(parent)
        viewer_frame.grid(row=9, column=0, sticky="nsew")
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
        ).grid(row=10, column=0, sticky="ew", pady=(8, 0))

    def _view_canvas_contains_pointer(self, event) -> bool:
        canvas = self._view_canvas
        if canvas is None:
            return False
        try:
            if not canvas.winfo_ismapped():
                return False
            left = canvas.winfo_rootx()
            top = canvas.winfo_rooty()
            right = left + canvas.winfo_width()
            bottom = top + canvas.winfo_height()
        except tk.TclError:
            return False
        return left <= event.x_root < right and top <= event.y_root < bottom

    def _on_view_mousewheel(self, event):
        if not self._view_canvas_contains_pointer(event):
            return None
        delta = int(getattr(event, "delta", 0) or 0)
        if delta == 0:
            return "break"
        if abs(delta) >= 120:
            units = -int(delta / 120)
        else:
            units = -1 if delta > 0 else 1
        self._view_canvas.yview_scroll(units, "units")
        return "break"

    def _on_view_mousewheel_linux(self, event):
        if not self._view_canvas_contains_pointer(event):
            return None
        if getattr(event, "num", None) == 4:
            units = -1
        elif getattr(event, "num", None) == 5:
            units = 1
        else:
            return None
        self._view_canvas.yview_scroll(units, "units")
        return "break"

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
        setting = data.get("setting", "")
        self._loaded_setting = setting if isinstance(setting, str) else None
        self._set_setting_text(setting if isinstance(setting, str) else "")
        self._set_story_bible_text(formatted)
        self._set_premise_controls(editable=False)
        self._set_setting_controls(editable=False)
        self._load_canon_rules_from_data(data)
        self._load_character_cards_from_data(data)
        if self._loaded_premise is None:
            self.viewer_status_var.set(
                f"Loaded: {package / 'story_bible.json'}. "
                "Premise is not text, so premise editing is disabled."
            )
        elif self._loaded_setting is None:
            self.viewer_status_var.set(
                f"Loaded: {package / 'story_bible.json'}. "
                "Setting is not text, so setting editing is disabled."
            )
        elif self._loaded_canon_rules is None:
            self.viewer_status_var.set(
                f"Loaded: {package / 'story_bible.json'}. "
                "Canon Rules contain unsupported or multi-line entries, so editing is disabled."
            )
        elif self._loaded_character_cards is None:
            self.viewer_status_var.set(
                f"Loaded: {package / 'story_bible.json'}. "
                "Character Cards contain unsupported data, so editing is disabled."
            )
        else:
            self.viewer_status_var.set(f"Loaded read-only: {package / 'story_bible.json'}")

    def start_premise_edit(self) -> None:
        if self._loaded_novel_path is None or self._loaded_premise is None:
            self.viewer_status_var.set("Load a Story Bible with a text premise first.")
            return
        if (self._premise_editing or self._setting_editing or self._canon_rules_editing
                or self._character_cards_managing):
            return

        self._premise_editing = True
        self._set_premise_controls(editable=True)
        self.novel_combo.configure(state="disabled")
        self.refresh_button.configure(state="disabled")
        self.load_button.configure(state="disabled")

        window = tk.Toplevel(self.root)
        self._premise_editor_window = window
        window.title("Edit Premise")
        window.geometry("720x420")
        window.minsize(540, 320)
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", self.cancel_premise_edit)

        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        ttk.Label(
            frame,
            text=f"Edit the premise for: {self._loaded_novel_path.name}",
            font=("TkDefaultFont", 11, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        editor_frame = ttk.Frame(frame)
        editor_frame.grid(row=1, column=0, sticky="nsew")
        editor_frame.columnconfigure(0, weight=1)
        editor_frame.rowconfigure(0, weight=1)
        editor = tk.Text(
            editor_frame,
            wrap="word",
            state="normal",
            undo=True,
            padx=8,
            pady=8,
        )
        self._premise_editor_text = editor
        scrollbar = ttk.Scrollbar(
            editor_frame, orient="vertical", command=editor.yview
        )
        editor.configure(yscrollcommand=scrollbar.set)
        editor.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        editor.insert("1.0", self._loaded_premise)
        editor.mark_set("insert", "end-1c")
        editor.bind("<Control-a>", self._select_all_premise_editor)
        editor.bind("<Control-A>", self._select_all_premise_editor)
        editor.bind("<Control-c>", self._copy_selected_premise_editor)
        editor.bind("<Control-C>", self._copy_selected_premise_editor)

        button_row = ttk.Frame(frame)
        button_row.grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            button_row, text="Save Premise", command=self.save_premise
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            button_row, text="Cancel Edit", command=self.cancel_premise_edit
        ).pack(side="left")

        ttk.Label(
            frame,
            text="Only the Premise field will be saved. Cancel discards this draft.",
            foreground="gray",
        ).grid(row=3, column=0, sticky="w", pady=(8, 0))

        window.grab_set()
        window.after_idle(editor.focus_set)
        self.viewer_status_var.set(
            "Editing premise in a separate window. Save Premise to keep it, "
            "or Cancel Edit to discard it."
        )

    def save_premise(self) -> None:
        if (
            not self._premise_editing
            or self._loaded_novel_path is None
            or self._premise_editor_text is None
        ):
            self.viewer_status_var.set("Choose Edit Premise before saving.")
            return

        new_premise = self._premise_editor_text.get("1.0", "end-1c")
        try:
            save_story_bible_premise(self._loaded_novel_path, new_premise)
            data = load_story_bible(self._loaded_novel_path)
        except (OSError, ValueError, RuntimeError) as exc:
            self.viewer_status_var.set(f"Premise was not saved:\n{exc}")
            return

        self._loaded_premise = new_premise
        setting = data.get("setting", "")
        self._loaded_setting = setting if isinstance(setting, str) else None
        self._set_story_bible_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        self._set_premise_text(self._loaded_premise or "")
        self._set_setting_text(self._loaded_setting or "")
        self._finish_premise_edit()
        self.viewer_status_var.set(
            f"Saved premise only: {self._loaded_novel_path / 'story_bible.json'}. "
            "Other Story Bible fields were preserved."
        )

    def cancel_premise_edit(self) -> None:
        if not self._premise_editing:
            return
        self._finish_premise_edit()
        self.viewer_status_var.set("Premise edit cancelled; no file changes were made.")

    def _finish_premise_edit(self) -> None:
        self._premise_editing = False
        window = self._premise_editor_window
        self._premise_editor_window = None
        self._premise_editor_text = None
        if window is not None:
            try:
                if window.winfo_exists():
                    window.grab_release()
                    window.destroy()
            except tk.TclError:
                pass

        self._set_premise_text(self._loaded_premise or "")
        self._set_premise_controls(editable=False)
        self.novel_combo.configure(state="readonly")
        self.refresh_button.configure(state="normal")
        self.load_button.configure(state="normal")


    def start_setting_edit(self) -> None:
        if self._loaded_novel_path is None or self._loaded_setting is None:
            self.viewer_status_var.set("Load a Story Bible with a text setting first.")
            return
        if (self._setting_editing or self._premise_editing or self._canon_rules_editing
                or self._character_cards_managing):
            return

        self._setting_editing = True
        self._set_setting_controls(editable=True)
        self.novel_combo.configure(state="disabled")
        self.refresh_button.configure(state="disabled")
        self.load_button.configure(state="disabled")

        window = tk.Toplevel(self.root)
        self._setting_editor_window = window
        window.title("Edit Setting")
        window.geometry("720x420")
        window.minsize(540, 320)
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", self.cancel_setting_edit)

        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        ttk.Label(
            frame,
            text=f"Edit the setting for: {self._loaded_novel_path.name}",
            font=("TkDefaultFont", 11, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        editor_frame = ttk.Frame(frame)
        editor_frame.grid(row=1, column=0, sticky="nsew")
        editor_frame.columnconfigure(0, weight=1)
        editor_frame.rowconfigure(0, weight=1)
        editor = tk.Text(
            editor_frame,
            wrap="word",
            state="normal",
            undo=True,
            padx=8,
            pady=8,
        )
        self._setting_editor_text = editor
        scrollbar = ttk.Scrollbar(
            editor_frame, orient="vertical", command=editor.yview
        )
        editor.configure(yscrollcommand=scrollbar.set)
        editor.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        editor.insert("1.0", self._loaded_setting)
        editor.mark_set("insert", "end-1c")
        editor.bind("<Control-a>", self._select_all_setting_editor)
        editor.bind("<Control-A>", self._select_all_setting_editor)
        editor.bind("<Control-c>", self._copy_selected_setting_editor)
        editor.bind("<Control-C>", self._copy_selected_setting_editor)

        button_row = ttk.Frame(frame)
        button_row.grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            button_row, text="Save Setting", command=self.save_setting
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            button_row, text="Cancel Edit", command=self.cancel_setting_edit
        ).pack(side="left")

        ttk.Label(
            frame,
            text="Only the Setting field will be saved. Cancel discards this draft.",
            foreground="gray",
        ).grid(row=3, column=0, sticky="w", pady=(8, 0))

        window.grab_set()
        window.after_idle(editor.focus_set)
        self.viewer_status_var.set(
            "Editing setting in a separate window. Save Setting to keep it, "
            "or Cancel Edit to discard it."
        )

    def save_setting(self) -> None:
        if (
            not self._setting_editing
            or self._loaded_novel_path is None
            or self._setting_editor_text is None
        ):
            self.viewer_status_var.set("Choose Edit Setting before saving.")
            return

        new_setting = self._setting_editor_text.get("1.0", "end-1c")
        try:
            save_story_bible_text_field(self._loaded_novel_path, "setting", new_setting)
            data = load_story_bible(self._loaded_novel_path)
        except (OSError, ValueError, RuntimeError) as exc:
            self.viewer_status_var.set(f"Setting was not saved:\n{exc}")
            return

        self._loaded_setting = new_setting
        premise = data.get("premise", "")
        self._loaded_premise = premise if isinstance(premise, str) else None
        self._set_story_bible_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        self._set_setting_text(self._loaded_setting)
        self._set_premise_text(self._loaded_premise or "")
        self._finish_setting_edit()
        self.viewer_status_var.set(
            f"Saved setting only: {self._loaded_novel_path / 'story_bible.json'}. "
            "Other Story Bible fields were preserved."
        )

    def cancel_setting_edit(self) -> None:
        if not self._setting_editing:
            return
        self._finish_setting_edit()
        self.viewer_status_var.set("Setting edit cancelled; no file changes were made.")

    def _finish_setting_edit(self) -> None:
        self._setting_editing = False
        window = self._setting_editor_window
        self._setting_editor_window = None
        self._setting_editor_text = None
        if window is not None:
            try:
                if window.winfo_exists():
                    window.grab_release()
                    window.destroy()
            except tk.TclError:
                pass

        self._set_setting_text(self._loaded_setting or "")
        self._set_setting_controls(editable=False)
        self.novel_combo.configure(state="readonly")
        self.refresh_button.configure(state="normal")
        self.load_button.configure(state="normal")

    def _set_setting_controls(self, editable: bool) -> None:
        # The on-page field is always read-only; edits use a dedicated window.
        has_text_setting = (
            self._loaded_novel_path is not None and self._loaded_setting is not None
        )
        self.edit_setting_button.configure(
            state="normal" if has_text_setting and not editable else "disabled"
        )

    def _set_setting_text(self, content: str) -> None:
        self.setting_text.configure(state="normal")
        self.setting_text.delete("1.0", "end")
        self.setting_text.insert("1.0", content)
        self.setting_text.configure(state="disabled")
        self.setting_text.tag_remove("sel", "1.0", "end")

    def _set_premise_controls(self, editable: bool) -> None:
        self._premise_editing = editable
        # The in-page field is always read-only. Typing happens in a dedicated editor.
        self.premise_text.configure(state="disabled")
        has_text_premise = (
            self._loaded_novel_path is not None and self._loaded_premise is not None
        )
        self.edit_premise_button.configure(
            state="normal" if has_text_premise and not editable else "disabled"
        )

    def _set_premise_text(self, content: str) -> None:
        self.premise_text.configure(state="normal")
        self.premise_text.delete("1.0", "end")
        self.premise_text.insert("1.0", content)
        self.premise_text.configure(state="disabled")
        self.premise_text.tag_remove("sel", "1.0", "end")

    def _reset_loaded_story_bible(self) -> None:
        if self._premise_editing:
            self._finish_premise_edit()
        if self._setting_editing:
            self._finish_setting_edit()
        if self._canon_rules_editing:
            self._finish_canon_rules_edit()
        if self._character_cards_managing:
            self.close_character_cards_manager()
        self._loaded_novel_path = None
        self._loaded_novel_label = ""
        self._loaded_premise = None
        self._premise_editing = False
        self._set_premise_text("")
        self._set_premise_controls(editable=False)
        self._loaded_setting = None
        self._setting_editing = False
        self._set_setting_text("")
        self._set_setting_controls(editable=False)
        self._loaded_canon_rules = None
        self._canon_rules_editing = False
        if hasattr(self, "canon_rules_text"):
            self._set_canon_rules_text("")
        if hasattr(self, "edit_canon_rules_button"):
            self._set_canon_rules_controls(editable=False)
        self._loaded_character_cards = None
        if hasattr(self, "character_cards_text"):
            self._set_character_cards_preview("Choose a novel and load its Story Bible.")
        if hasattr(self, "edit_character_cards_button"):
            self._set_character_cards_controls(editable=False)
        if hasattr(self, "novel_combo"):
            self.novel_combo.configure(state="readonly")
        if hasattr(self, "refresh_button"):
            self.refresh_button.configure(state="normal")
        if hasattr(self, "load_button"):
            self.load_button.configure(state="normal")



    def _load_canon_rules_from_data(self, data: dict) -> None:
        value = data.get("canon_rules", [])
        if isinstance(value, list) and all(isinstance(rule, str) for rule in value):
            display_rules = list(value)
            can_edit = all("\n" not in rule and "\r" not in rule for rule in display_rules)
            self._loaded_canon_rules = display_rules if can_edit else None
            preview = self._format_canon_rules_preview(display_rules)
            if not can_edit:
                preview += (
                    "\n\nEditing is disabled because an existing rule spans "
                    "multiple lines. Its saved text has been left untouched."
                )
        else:
            self._loaded_canon_rules = None
            preview = (
                "Canon Rules are not a list of text entries. Editing is disabled "
                "to preserve the existing data."
            )
        self._set_canon_rules_text(preview)
        self._set_canon_rules_controls(editable=False)

    def start_canon_rules_edit(self) -> None:
        if self._loaded_novel_path is None or self._loaded_canon_rules is None:
            self.viewer_status_var.set(
                "Load a Story Bible with a list of single-line Canon Rules first."
            )
            return
        if (self._canon_rules_editing or self._premise_editing or self._setting_editing
                or self._character_cards_managing):
            return

        self._canon_rules_editing = True
        self._set_canon_rules_controls(editable=True)
        self.novel_combo.configure(state="disabled")
        self.refresh_button.configure(state="disabled")
        self.load_button.configure(state="disabled")

        window = tk.Toplevel(self.root)
        self._canon_rules_editor_window = window
        window.title("Edit Canon Rules")
        window.geometry("720x480")
        window.minsize(540, 340)
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", self.cancel_canon_rules_edit)

        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        ttk.Label(
            frame,
            text=(
                f"Edit canon rules for: {self._loaded_novel_path.name}\n"
                "Enter one rule per line. Blank lines are ignored."
            ),
            font=("TkDefaultFont", 11, "bold"),
            justify="left",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        editor_frame = ttk.Frame(frame)
        editor_frame.grid(row=1, column=0, sticky="nsew")
        editor_frame.columnconfigure(0, weight=1)
        editor_frame.rowconfigure(0, weight=1)
        editor = tk.Text(
            editor_frame,
            wrap="word",
            state="normal",
            undo=True,
            padx=8,
            pady=8,
        )
        self._canon_rules_editor_text = editor
        scrollbar = ttk.Scrollbar(
            editor_frame, orient="vertical", command=editor.yview
        )
        editor.configure(yscrollcommand=scrollbar.set)
        editor.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        editor.insert("1.0", "\n".join(self._loaded_canon_rules))
        editor.mark_set("insert", "end-1c")
        editor.bind("<Control-a>", self._select_all_canon_rules_editor)
        editor.bind("<Control-A>", self._select_all_canon_rules_editor)
        editor.bind("<Control-c>", self._copy_selected_canon_rules_editor)
        editor.bind("<Control-C>", self._copy_selected_canon_rules_editor)

        button_row = ttk.Frame(frame)
        button_row.grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            button_row, text="Save Canon Rules", command=self.save_canon_rules
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            button_row, text="Cancel Edit", command=self.cancel_canon_rules_edit
        ).pack(side="left")

        ttk.Label(
            frame,
            text="Only the canon_rules list will be saved. Cancel discards this draft.",
            foreground="gray",
        ).grid(row=3, column=0, sticky="w", pady=(8, 0))

        window.grab_set()
        window.after_idle(editor.focus_set)
        self.viewer_status_var.set(
            "Editing Canon Rules in a separate window. Save Canon Rules to keep them, "
            "or Cancel Edit to discard the draft."
        )

    def save_canon_rules(self) -> None:
        if (
            not self._canon_rules_editing
            or self._loaded_novel_path is None
            or self._canon_rules_editor_text is None
        ):
            self.viewer_status_var.set("Choose Edit Canon Rules before saving.")
            return

        new_rules = [
            line.strip()
            for line in self._canon_rules_editor_text.get("1.0", "end-1c").splitlines()
            if line.strip()
        ]
        try:
            save_story_bible_canon_rules(self._loaded_novel_path, new_rules)
            data = load_story_bible(self._loaded_novel_path)
        except (OSError, ValueError, RuntimeError) as exc:
            self.viewer_status_var.set(f"Canon Rules were not saved:\n{exc}")
            return

        premise = data.get("premise", "")
        self._loaded_premise = premise if isinstance(premise, str) else None
        setting = data.get("setting", "")
        self._loaded_setting = setting if isinstance(setting, str) else None
        self._loaded_canon_rules = new_rules
        self._set_story_bible_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        self._set_premise_text(self._loaded_premise or "")
        self._set_setting_text(self._loaded_setting or "")
        self._set_canon_rules_text(self._format_canon_rules_preview(new_rules))
        self._finish_canon_rules_edit()
        self.viewer_status_var.set(
            f"Saved Canon Rules only: {self._loaded_novel_path / 'story_bible.json'}. "
            "Other Story Bible fields were preserved."
        )

    def cancel_canon_rules_edit(self) -> None:
        if not self._canon_rules_editing:
            return
        self._finish_canon_rules_edit()
        self.viewer_status_var.set(
            "Canon Rules edit cancelled; no file changes were made."
        )

    def _finish_canon_rules_edit(self) -> None:
        self._canon_rules_editing = False
        window = self._canon_rules_editor_window
        self._canon_rules_editor_window = None
        self._canon_rules_editor_text = None
        if window is not None:
            try:
                if window.winfo_exists():
                    window.grab_release()
                    window.destroy()
            except tk.TclError:
                pass

        if self._loaded_canon_rules is not None:
            self._set_canon_rules_text(
                self._format_canon_rules_preview(self._loaded_canon_rules)
            )
        self._set_canon_rules_controls(editable=False)
        self.novel_combo.configure(state="readonly")
        self.refresh_button.configure(state="normal")
        self.load_button.configure(state="normal")

    def _set_canon_rules_controls(self, editable: bool) -> None:
        has_editable_rules = (
            self._loaded_novel_path is not None and self._loaded_canon_rules is not None
        )
        self.edit_canon_rules_button.configure(
            state="normal" if has_editable_rules and not editable else "disabled"
        )

    def _format_canon_rules_preview(self, rules: list[str]) -> str:
        if not rules:
            return "No canon rules have been added yet."
        return "\n\n".join(
            f"{index}. {rule}" for index, rule in enumerate(rules, start=1)
        )

    def _set_canon_rules_text(self, content: str) -> None:
        self.canon_rules_text.configure(state="normal")
        self.canon_rules_text.delete("1.0", "end")
        self.canon_rules_text.insert("1.0", content)
        self.canon_rules_text.configure(state="disabled")
        self.canon_rules_text.tag_remove("sel", "1.0", "end")

    def _select_all_canon_rules(self, _event=None):
        return self._select_all_text(self.canon_rules_text)

    def _copy_selected_canon_rules(self, _event=None):
        return self._copy_selected_text(self.canon_rules_text)

    def _select_all_canon_rules_editor(self, _event=None):
        if self._canon_rules_editor_text is None:
            return "break"
        return self._select_all_text(self._canon_rules_editor_text)

    def _copy_selected_canon_rules_editor(self, _event=None):
        if self._canon_rules_editor_text is None:
            return "break"
        return self._copy_selected_text(self._canon_rules_editor_text)

    def _load_character_cards_from_data(self, data: dict[str, Any]) -> None:
        value = data.get("character_cards", [])
        supported = isinstance(value, list)
        if supported:
            for card in value:
                if isinstance(card, str):
                    continue
                if not isinstance(card, dict):
                    supported = False
                    break
                name = card.get("name")
                if not isinstance(name, str) or not name.strip():
                    supported = False
                    break
                if any(
                    field in card and not isinstance(card[field], str)
                    for field in ("role", "description")
                ):
                    supported = False
                    break

        self._loaded_character_cards = list(value) if supported else None
        if not supported:
            preview = (
                "Character Cards contain an unsupported structure. Editing is disabled "
                "to preserve the existing data."
            )
        elif not value:
            preview = "No character cards have been added yet."
        else:
            lines = []
            for index, card in enumerate(value, start=1):
                card_data, error, filename = self._get_character_card_data(card)
                if card_data is not None:
                    role = card_data.get("role", "")
                    role = role.strip() if isinstance(role, str) else ""
                    label = card_data.get("name", filename or f"Character {index}")
                    label = label + (f" ({role})" if role else "")
                elif filename:
                    label = f"{Path(filename).stem} [could not load]"
                else:
                    label = f"Legacy text note {index}"
                lines.append(f"{index}. {label}")
            preview = "\n".join(lines)
            if any(
                isinstance(card, str) and Path(card).suffix.lower() != ".json"
                for card in value
            ):
                preview += "\n\nOlder plain-text notes remain unchanged."
        self._set_character_cards_preview(preview)
        self._set_character_cards_controls(editable=False)

    def _get_character_card_data(
        self, card: dict[str, Any] | str
    ) -> tuple[dict[str, Any] | None, str | None, str | None]:
        if isinstance(card, dict):
            return card, None, None
        if isinstance(card, str) and Path(card).suffix.lower() == ".json":
            try:
                data = load_story_bible_character_card(self._loaded_novel_path, card)
            except (OSError, ValueError) as exc:
                return None, str(exc), card
            return data, None, card
        return None, None, None

    def _set_character_cards_preview(self, content: str) -> None:
        self.character_cards_text.configure(state="normal")
        self.character_cards_text.delete("1.0", "end")
        self.character_cards_text.insert("1.0", content)
        self.character_cards_text.configure(state="disabled")
        self.character_cards_text.tag_remove("sel", "1.0", "end")

    def _set_character_cards_controls(self, editable: bool) -> None:
        can_manage = (
            self._loaded_novel_path is not None and self._loaded_character_cards is not None
        )
        self.edit_character_cards_button.configure(
            state="normal" if can_manage and not editable else "disabled"
        )

    def _select_all_character_cards(self, _event=None):
        return self._select_all_text(self.character_cards_text)

    def _copy_selected_character_cards(self, _event=None):
        return self._copy_selected_text(self.character_cards_text)

    def start_character_cards_manager(self) -> None:
        if self._loaded_novel_path is None or self._loaded_character_cards is None:
            self.viewer_status_var.set("Load a Story Bible with a supported Character Cards list first.")
            return
        if (self._character_cards_managing or self._premise_editing or self._setting_editing
                or self._canon_rules_editing or self._sync_in_progress):
            return

        self._character_cards_managing = True
        self._set_character_cards_controls(editable=True)
        self.edit_premise_button.configure(state="disabled")
        self.edit_setting_button.configure(state="disabled")
        self.edit_canon_rules_button.configure(state="disabled")
        self.novel_combo.configure(state="disabled")
        self.refresh_button.configure(state="disabled")
        self.load_button.configure(state="disabled")
        self.sync_button.configure(state="disabled")

        window = tk.Toplevel(self.root)
        self._character_cards_manager_window = window
        window.title(f"Character Cards: {self._loaded_novel_path.name}")
        window.geometry("760x560")
        window.minsize(620, 440)
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", self.close_character_cards_manager)

        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=2)
        frame.rowconfigure(1, weight=1)

        ttk.Label(
            frame, text="Character Cards", font=("TkDefaultFont", 14, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        list_frame = ttk.Frame(frame)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        cards_list = tk.Listbox(list_frame, height=12, exportselection=False)
        self._character_cards_manager_listbox = cards_list
        cards_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=cards_list.yview)
        cards_list.configure(yscrollcommand=cards_scroll.set)
        cards_list.grid(row=0, column=0, sticky="nsew")
        cards_scroll.grid(row=0, column=1, sticky="ns")
        cards_list.bind("<<ListboxSelect>>", self._character_card_selection_changed)

        preview_frame = ttk.LabelFrame(frame, text="Selected Character", padding=8)
        preview_frame.grid(row=1, column=1, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        preview = tk.Text(
            preview_frame, wrap="word", state="disabled", undo=False, padx=8, pady=8
        )
        self._character_cards_manager_preview = preview
        preview_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=preview.yview)
        preview.configure(yscrollcommand=preview_scroll.set)
        preview.grid(row=0, column=0, sticky="nsew")
        preview_scroll.grid(row=0, column=1, sticky="ns")
        preview.bind("<Control-a>", lambda _event: self._select_all_text(preview))
        preview.bind("<Control-A>", lambda _event: self._select_all_text(preview))
        preview.bind("<Control-c>", lambda _event: self._copy_selected_text(preview))
        preview.bind("<Control-C>", lambda _event: self._copy_selected_text(preview))

        button_row = ttk.Frame(frame)
        button_row.grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self._character_cards_add_button = ttk.Button(
            button_row, text="Add Character", command=self.add_character_card
        )
        self._character_cards_add_button.pack(side="left", padx=(0, 8))
        self._character_cards_edit_button = ttk.Button(
            button_row, text="Edit Selected", command=self.edit_character_card,
            state="disabled",
        )
        self._character_cards_edit_button.pack(side="left", padx=(0, 8))
        self._character_cards_remove_button = ttk.Button(
            button_row, text="Remove Selected", command=self.remove_character_card,
            state="disabled",
        )
        self._character_cards_remove_button.pack(side="left", padx=(0, 8))
        ttk.Button(
            button_row, text="Close", command=self.close_character_cards_manager
        ).pack(side="left")

        ttk.Label(
            frame,
            text=(
                "Each structured card has a Name, Role, and Description. "
                "Older plain-text cards are shown but kept unchanged."
            ),
            foreground="gray",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))

        self._refresh_character_cards_manager()
        window.grab_set()
        self.viewer_status_var.set(
            "Managing Character Cards. Add, edit, or remove cards explicitly; each save changes only character_cards."
        )

    def _refresh_character_cards_manager(self, selected_index: int | None = None) -> None:
        listbox = self._character_cards_manager_listbox
        if listbox is None or self._loaded_character_cards is None:
            return
        listbox.delete(0, "end")
        for index, card in enumerate(self._loaded_character_cards, start=1):
            card_data, _error, filename = self._get_character_card_data(card)
            if card_data is not None:
                role = card_data.get("role", "")
                role = role.strip() if isinstance(role, str) else ""
                label = card_data.get("name", filename or f"Character {index}")
                label = label + (f" ({role})" if role else "")
            elif filename:
                label = f"{Path(filename).stem} [unavailable]"
            else:
                label = f"Legacy text note {index}"
            listbox.insert("end", label)

        if selected_index is not None and self._loaded_character_cards:
            selected_index = max(0, min(selected_index, len(self._loaded_character_cards) - 1))
            listbox.selection_set(selected_index)
            listbox.activate(selected_index)
            listbox.see(selected_index)
            self._character_card_selection_changed()
        else:
            self._set_character_card_manager_preview("Select a character to view its details.")
            self._set_character_card_manager_buttons(None)

    def _set_character_card_manager_preview(self, content: str) -> None:
        preview = self._character_cards_manager_preview
        if preview is None:
            return
        preview.configure(state="normal")
        preview.delete("1.0", "end")
        preview.insert("1.0", content)
        preview.configure(state="disabled")
        preview.tag_remove("sel", "1.0", "end")

    def _set_character_card_manager_buttons(self, selected_index: int | None) -> None:
        if self._character_cards_add_button is not None:
            self._character_cards_add_button.configure(state="normal")
        can_edit = False
        can_remove = False
        if (
            selected_index is not None
            and self._loaded_character_cards is not None
            and 0 <= selected_index < len(self._loaded_character_cards)
        ):
            card = self._loaded_character_cards[selected_index]
            card_data, _error, filename = self._get_character_card_data(card)
            can_edit = card_data is not None
            can_remove = isinstance(card, dict) or filename is not None
        if self._character_cards_edit_button is not None:
            self._character_cards_edit_button.configure(
                state="normal" if can_edit else "disabled"
            )
        if self._character_cards_remove_button is not None:
            self._character_cards_remove_button.configure(
                state="normal" if can_remove else "disabled"
            )

    def _character_card_selection_changed(self, _event=None) -> None:
        listbox = self._character_cards_manager_listbox
        if listbox is None or self._loaded_character_cards is None:
            return
        selection = listbox.curselection()
        if not selection:
            self._set_character_card_manager_preview("Select a character to view its details.")
            self._set_character_card_manager_buttons(None)
            return
        index = int(selection[0])
        card = self._loaded_character_cards[index]
        card_data, error, filename = self._get_character_card_data(card)
        if card_data is not None:
            heading = f"Source file: {filename}\n\n" if filename else ""
            preview = heading + json.dumps(card_data, indent=2, ensure_ascii=False)
        elif filename:
            preview = (
                f"Could not open character file: {filename}\n\n{error or 'Unknown error'}\n\n"
                "The file and its reference have not been changed. You can remove the reference "
                "from this Story Bible without deleting the source file."
            )
        else:
            preview = (
                "This is an older plain-text note. It is preserved as-is and is not editable "
                "as a structured Character Card.\n\n" + str(card)
            )
        self._set_character_card_manager_preview(preview)
        self._set_character_card_manager_buttons(index)

    def add_character_card(self) -> None:
        self._open_character_card_editor(None)

    def edit_character_card(self) -> None:
        listbox = self._character_cards_manager_listbox
        if listbox is None:
            return
        selection = listbox.curselection()
        if not selection:
            self.viewer_status_var.set("Select a character card to edit.")
            return
        index = int(selection[0])
        if self._loaded_character_cards is None:
            return
        card_data, error, filename = self._get_character_card_data(
            self._loaded_character_cards[index]
        )
        if card_data is None:
            self.viewer_status_var.set(
                f"Character card could not be opened: {error or 'This is a legacy text note.'}"
            )
            return
        self._open_character_card_editor(index, card_data, filename)

    def _open_character_card_editor(
        self,
        edit_index: int | None,
        existing: dict[str, Any] | None = None,
        filename: str | None = None,
    ) -> None:
        if self._character_card_editor_window is not None or self._loaded_character_cards is None:
            return
        self._character_card_edit_index = edit_index
        self._character_card_filename = filename
        title = "Edit Character" if edit_index is not None else "Add Character"
        editor = CharacterCardEditorWindow(
            parent=self._character_cards_manager_window,
            existing=existing or {},
            title=title,
            on_save=self.save_character_card,
            on_cancel=self.cancel_character_card_edit,
        )
        self._character_card_editor = editor
        self._character_card_editor_window = editor.window

    def save_character_card(self, card_data: dict[str, Any] | None = None) -> None:
        if (
            self._character_card_editor_window is None
            or self._loaded_novel_path is None
            or self._loaded_character_cards is None
        ):
            self.viewer_status_var.set("Open Add Character or Edit Selected before saving.")
            return
        if card_data is None:
            if self._character_card_editor is None:
                self.viewer_status_var.set("Character editor is not available.")
                return
            try:
                card_data = self._character_card_editor.build_card()
            except ValueError as exc:
                self.viewer_status_var.set(f"Character was not saved: {exc}")
                return

        selected_index = self._character_card_edit_index
        name = str(card_data.get("name", "")).strip()
        if not name:
            self.viewer_status_var.set("Character was not saved. Enter a name first.")
            return

        try:
            if selected_index is None:
                filename = create_story_bible_character_card(
                    self._loaded_novel_path, card_data
                )
                data = load_story_bible(self._loaded_novel_path)
                selected_index = len(data.get("character_cards", [])) - 1
                result_message = (
                    f"Created {filename}. The new Character Card is stored as its own JSON file."
                )
            elif self._character_card_filename is not None:
                save_story_bible_character_card_file(
                    self._loaded_novel_path,
                    self._character_card_filename,
                    card_data,
                    replace=True,
                )
                data = load_story_bible(self._loaded_novel_path)
                result_message = (
                    f"Saved '{name}' to {self._character_card_filename}. "
                    "Other character details were preserved."
                )
            else:
                cards = list(self._loaded_character_cards)
                if (
                    not 0 <= selected_index < len(cards)
                    or not isinstance(cards[selected_index], dict)
                ):
                    self.viewer_status_var.set(
                        "Character was not saved. Reload the Character Cards list."
                    )
                    return
                updated_card = dict(cards[selected_index])
                updated_card.update(card_data)
                cards[selected_index] = updated_card
                save_story_bible_character_cards(self._loaded_novel_path, cards)
                data = load_story_bible(self._loaded_novel_path)
                result_message = f"Saved character card '{name}'."
        except (OSError, ValueError, RuntimeError) as exc:
            self.viewer_status_var.set(f"Character was not saved:\\n{exc}")
            return

        self._loaded_character_cards = list(data.get("character_cards", []))
        self._load_character_cards_from_data(data)
        self._set_story_bible_text(json.dumps(data, indent=2, ensure_ascii=False) + "\\n")
        self._refresh_character_cards_manager(selected_index)
        self._finish_character_card_editor()
        self.viewer_status_var.set(
            result_message + " Other Story Bible fields were preserved."
        )

    def cancel_character_card_edit(self) -> None:
        if self._character_card_editor_window is None:
            return
        self._finish_character_card_editor()
        self.viewer_status_var.set("Character edit cancelled; no file changes were made.")

    def _finish_character_card_editor(self) -> None:
        window = self._character_card_editor_window
        self._character_card_editor_window = None
        self._character_card_editor = None
        self._character_card_editor_text = None
        self._character_card_name_var = None
        self._character_card_role_var = None
        self._character_card_edit_index = None
        self._character_card_filename = None
        if window is not None:
            try:
                if window.winfo_exists():
                    window.grab_release()
                    window.destroy()
            except tk.TclError:
                pass
        if self._character_cards_manager_window is not None:
            try:
                self._character_cards_manager_window.grab_set()
            except tk.TclError:
                pass
        self._character_card_selection_changed()

    def remove_character_card(self) -> None:
        listbox = self._character_cards_manager_listbox
        cards = self._loaded_character_cards
        if listbox is None or cards is None or self._loaded_novel_path is None:
            return
        selection = listbox.curselection()
        if not selection:
            self.viewer_status_var.set("Select a character card to remove.")
            return
        index = int(selection[0])
        card = cards[index]
        card_data, error, filename = self._get_character_card_data(card)
        if card_data is None and filename is None:
            self.viewer_status_var.set("Older plain-text notes are kept unchanged.")
            return
        name = (
            card_data.get("name", filename or "Character")
            if card_data is not None else Path(filename).stem
        )
        if filename is not None:
            prompt = (
                f"Remove '{name}' from this Story Bible? The reference will be removed, "
                f"but the source file {filename} will remain in the novel folder."
            )
        else:
            prompt = f"Remove '{name}' from this Story Bible?"
        confirmed = messagebox.askyesno(
            "Remove Character Card", prompt, parent=self._character_cards_manager_window
        )
        if not confirmed:
            return
        try:
            if filename is not None:
                remove_story_bible_character_card_reference(
                    self._loaded_novel_path, index, filename
                )
                data = load_story_bible(self._loaded_novel_path)
                result_message = (
                    f"Removed the reference to '{name}'. The file {filename} was kept."
                )
            else:
                updated_cards = list(cards)
                updated_cards.pop(index)
                save_story_bible_character_cards(self._loaded_novel_path, updated_cards)
                data = load_story_bible(self._loaded_novel_path)
                result_message = f"Removed character card '{name}'."
        except (OSError, ValueError, RuntimeError) as exc:
            self.viewer_status_var.set(f"Character card was not removed:\n{exc}")
            return
        self._loaded_character_cards = list(data.get("character_cards", []))
        self._load_character_cards_from_data(data)
        self._set_story_bible_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        next_cards = self._loaded_character_cards or []
        next_index = min(index, len(next_cards) - 1) if next_cards else None
        self._refresh_character_cards_manager(next_index)
        self.viewer_status_var.set(
            result_message + " Other Story Bible fields were preserved."
        )

    def close_character_cards_manager(self) -> None:
        if self._character_card_editor_window is not None:
            self.cancel_character_card_edit()
        window = self._character_cards_manager_window
        self._character_cards_manager_window = None
        self._character_cards_manager_listbox = None
        self._character_cards_manager_preview = None
        self._character_cards_add_button = None
        self._character_cards_edit_button = None
        self._character_cards_remove_button = None
        self._character_cards_managing = False
        if window is not None:
            try:
                if window.winfo_exists():
                    window.grab_release()
                    window.destroy()
            except tk.TclError:
                pass
        self.novel_combo.configure(state="readonly")
        self.refresh_button.configure(state="normal")
        self.load_button.configure(state="normal")
        self.sync_button.configure(state="normal")
        self._set_premise_controls(editable=False)
        self._set_setting_controls(editable=False)
        self._set_canon_rules_controls(editable=False)
        self._set_character_cards_controls(editable=False)

    def sync_selected_novel_to_github(self) -> None:
        """Preview and explicitly confirm syncing only the selected novel repo."""
        if (self._sync_in_progress or self._premise_editing or self._setting_editing
                or self._canon_rules_editing or self._character_cards_managing
                or self._character_card_editor_window is not None):
            return

        label = self.novel_combo.get().strip()
        novel_path = self._novel_paths.get(label)
        if novel_path is None:
            self.viewer_status_var.set("Choose a novel before syncing.")
            return

        # The ongoing fixture is deliberately local-only: never publish test data.
        test_fixture = (Path(NOVEL_ROOT) / "Story-Bible-Save-Test").resolve()
        if Path(novel_path).resolve() == test_fixture:
            self.viewer_status_var.set(
                "Sync blocked: Story-Bible-Save-Test is a local-only test package."
            )
            self._show_copyable_dialog(
                "Test package not syncable",
                "Story-Bible-Save-Test is the local integration-test fixture. "
                "It is intentionally kept out of GitHub and must not be synced or "
                "published as a real novel. Choose one of your real novel packages "
                "to sync between computers.",
            )
            return

        try:
            preview = inspect_novel_repository(novel_path)
        except NovelGitSyncError as exc:
            self.viewer_status_var.set("Novel sync blocked; no Git operation was started.")
            self._show_copyable_dialog("Cannot sync novel", str(exc))
            return

        lines = [
            "Review the target before syncing:",
            "",
            f"Novel folder: {preview.repository}",
            f"Branch: {preview.branch}",
            f"GitHub remote: {preview.remote_url}",
            "",
            "This operates only inside the selected novel's own Git repository.",
            "It fetches and fast-forwards safely when possible, commits listed local "
            "changes, and pushes this existing branch. It does not sync StoryBuilder code.",
            "If local and GitHub histories have diverged, syncing stops without pushing.",
            "Local-only secret/encrypted assets block syncing.",
            "",
        ]
        if preview.local_commits:
            lines.append("Local commits ahead of the last fetched origin branch:")
            shown_commits = preview.local_commits[:10]
            lines.extend(f"  • {commit}" for commit in shown_commits)
            if len(preview.local_commits) > len(shown_commits):
                lines.append(
                    f"  • …and {len(preview.local_commits) - len(shown_commits)} more commit(s)"
                )
            lines.append("")

        if preview.changed_files:
            lines.append("Local file changes that may be committed and pushed:")
            shown_files = preview.changed_files[:20]
            lines.extend(f"  • {path}" for path in shown_files)
            if len(preview.changed_files) > len(shown_files):
                lines.append(
                    f"  • …and {len(preview.changed_files) - len(shown_files)} more file(s)"
                )
        else:
            lines.append(
                "No uncommitted local file changes were detected. The sync will still "
                "fetch remote updates and push this branch if needed."
            )
        lines.extend(
            [
                "",
                "Before switching computers, sync here, then use Sync Selected Novel "
                "to GitHub on the other computer to fetch the latest version.",
                "",
                "Proceed with syncing this novel?",
            ]
        )

        choice = self._show_copyable_dialog(
            "Confirm novel sync",
            "\n".join(lines),
            buttons=("Sync", "Cancel"),
            default_button="Cancel",
        )
        if choice != "Sync":
            self.viewer_status_var.set("Novel sync cancelled; no Git operation started.")
            return

        self._set_sync_busy(True)
        self.viewer_status_var.set(
            f"Syncing {novel_path.name} to GitHub on branch {preview.branch}…"
        )

        def work() -> None:
            try:
                result = sync_novel_repository(novel_path)
            except Exception as exc:
                message = str(exc)
                self.root.after(
                    0, lambda message=message: self._novel_sync_failed(message)
                )
            else:
                self.root.after(
                    0, lambda result=result: self._novel_sync_succeeded(
                        result, novel_path
                    )
                )

        threading.Thread(target=work, daemon=True).start()

    def _set_sync_busy(self, busy: bool) -> None:
        self._sync_in_progress = busy
        general_state = "disabled" if busy else "normal"
        self.novel_combo.configure(state="disabled" if busy else "readonly")
        self.refresh_button.configure(state=general_state)
        self.load_button.configure(state=general_state)
        self.sync_button.configure(state=general_state)
        if busy:
            self.edit_premise_button.configure(state="disabled")
            self.edit_setting_button.configure(state="disabled")
            self.edit_canon_rules_button.configure(state="disabled")
            self.edit_character_cards_button.configure(state="disabled")
        else:
            self._set_premise_controls(editable=False)
            self._set_setting_controls(editable=False)
            self._set_canon_rules_controls(editable=False)
            self._set_character_cards_controls(editable=False)

    def _novel_sync_succeeded(self, result, synced_path: Path) -> None:
        self._set_sync_busy(False)
        self.refresh_novels()
        selected_label = next(
            (
                label
                for label, path in self._novel_paths.items()
                if Path(path).resolve() == Path(synced_path).resolve()
            ),
            None,
        )
        if selected_label is not None:
            self.novel_combo.set(selected_label)
            self.load_selected_story_bible()
        self.viewer_status_var.set(result.message)

    def _novel_sync_failed(self, message: str) -> None:
        self._set_sync_busy(False)
        self.viewer_status_var.set("Novel sync failed. Check the message before retrying.")
        self._show_copyable_dialog("Novel sync failed", message)

    def _show_copyable_dialog(
        self,
        title: str,
        message: str,
        buttons: tuple[str, ...] = ("OK",),
        default_button: str | None = None,
    ) -> str:
        """Show a selectable, scrollable confirmation/error popup."""
        if not buttons:
            raise ValueError("At least one dialog button is required.")
        if default_button not in buttons:
            default_button = "Cancel" if "Cancel" in buttons else (
                "No" if "No" in buttons else buttons[0]
            )

        try:
            self.root.update_idletasks()
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
        except tk.TclError:
            screen_width, screen_height = 1024, 768

        long_message = len(message) > 350 or message.count("\n") > 7
        width = min(860 if long_message else 560, screen_width - 60)
        height = min(640 if long_message else 260, screen_height - 80)
        width, height = max(320, width), max(220, height)
        window = tk.Toplevel(self.root)
        window.title(title)
        window.transient(self.root)
        window.resizable(True, True)
        window.geometry(
            f"{width}x{height}+{max(0, (screen_width-width)//2)}"
            f"+{max(0, (screen_height-height)//2)}"
        )

        outer = ttk.Frame(window, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(
            outer,
            text="Message text: select it and press Ctrl+A, then Ctrl+C to copy.",
        ).pack(anchor="w", pady=(0, 6))

        text_frame = ttk.Frame(outer)
        text_frame.pack(fill="both", expand=True)
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        text_box = tk.Text(text_frame, wrap="word", undo=False, height=8, width=60)
        text_scroll = ttk.Scrollbar(
            text_frame, orient="vertical", command=text_box.yview
        )
        text_box.configure(yscrollcommand=text_scroll.set)
        text_box.grid(row=0, column=0, sticky="nsew")
        text_scroll.grid(row=0, column=1, sticky="ns")
        text_box.insert("1.0", message)
        text_box.bind("<Control-a>", lambda event: self._select_all_text(text_box))
        text_box.bind("<Control-A>", lambda event: self._select_all_text(text_box))
        text_box.bind("<Control-c>", lambda event: self._copy_selected_text(text_box))
        text_box.bind("<Control-C>", lambda event: self._copy_selected_text(text_box))

        def protect_read_only_text(event):
            if event.state & 0x4 and event.keysym.lower() in {"c", "a"}:
                return None
            if event.state & 0x4 and event.keysym.lower() in {"v", "x"}:
                return "break"
            if event.keysym in {
                "BackSpace", "Delete", "Insert", "Return", "KP_Enter", "Tab",
            }:
                return "break"
            if event.char and event.char.isprintable():
                return "break"
            return None

        text_box.bind("<KeyPress>", protect_read_only_text)
        text_box.bind("<<Paste>>", lambda _event: "break")
        text_box.bind("<<Cut>>", lambda _event: "break")
        text_box.bind("<<Clear>>", lambda _event: "break")

        selected = {"button": default_button}

        def finish(button: str) -> None:
            selected["button"] = button
            try:
                window.grab_release()
            except tk.TclError:
                pass
            window.destroy()

        window.protocol(
            "WM_DELETE_WINDOW",
            lambda: finish("Cancel" if "Cancel" in buttons else default_button),
        )
        button_row = ttk.Frame(outer)
        button_row.pack(fill="x", pady=(10, 0))
        for label in buttons:
            ttk.Button(
                button_row, text=label, command=lambda value=label: finish(value)
            ).pack(side="right", padx=(8, 0))

        window.grab_set()
        window.wait_window()
        return selected["button"]

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

    def _select_all_setting(self, _event=None):
        return self._select_all_text(self.setting_text)

    def _copy_selected_setting(self, _event=None):
        return self._copy_selected_text(self.setting_text)

    def _select_all_premise_editor(self, _event=None):
        if self._premise_editor_text is None:
            return "break"
        return self._select_all_text(self._premise_editor_text)

    def _copy_selected_premise_editor(self, _event=None):
        if self._premise_editor_text is None:
            return "break"
        return self._copy_selected_text(self._premise_editor_text)

    def _select_all_setting_editor(self, _event=None):
        if self._setting_editor_text is None:
            return "break"
        return self._select_all_text(self._setting_editor_text)

    def _copy_selected_setting_editor(self, _event=None):
        if self._setting_editor_text is None:
            return "break"
        return self._copy_selected_text(self._setting_editor_text)

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
