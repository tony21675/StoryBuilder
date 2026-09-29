from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from builder.conversation import apply_command
from builder.story_package import StoryPackage
from builder.validator import validate_package


class StoryBuilderApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("StoryBuilder")
        self.geometry("1050x720")
        self.minsize(900, 620)

        self.package: StoryPackage | None = None
        self.character_filename: str | None = None
        self.dirty = False

        self._build_ui()
        self._new_novel()

    def _build_ui(self):
        toolbar = ttk.Frame(self, padding=8)
        toolbar.pack(fill="x")
        for label, command in [
            ("New Novel", self._new_novel),
            ("Open Novel", self._open_novel),
            ("Save", self._save),
            ("Save As / Export", self._save_as),
            ("Validate", self._validate),
        ]:
            ttk.Button(toolbar, text=label, command=command).pack(side="left", padx=3)
        self.path_label = ttk.Label(toolbar, text="Unsaved novel")
        self.path_label.pack(side="right", padx=8)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._build_chat_tab()
        self._build_story_tab()
        self._build_characters_tab()
        self._build_state_tab()

    def _build_chat_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Talk to Builder")

        ttk.Label(tab, text="Tell the builder what to change", font=("", 14, "bold")).pack(anchor="w")
        ttk.Label(
            tab,
            text='Examples:  Change Maya\'s age to 22   •   Set the current chapter to 2   •   Change the story title to The Long Road',
        ).pack(anchor="w", pady=(4, 12))

        self.chat_log = tk.Text(tab, wrap="word", height=24, state="disabled")
        self.chat_log.pack(fill="both", expand=True)

        row = ttk.Frame(tab)
        row.pack(fill="x", pady=(10, 0))
        self.command_entry = ttk.Entry(row)
        self.command_entry.pack(side="left", fill="x", expand=True)
        self.command_entry.bind("<Return>", lambda _e: self._run_command())
        ttk.Button(row, text="Apply Change", command=self._run_command).pack(side="left", padx=(8, 0))
        self._chat("Builder", "Ready. Tell me what you want to change.")

    def _build_story_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Story")

        labels = [("title", "Title"), ("version", "Version"), ("status", "Status")]
        self.story_vars = {}
        for row, (key, label) in enumerate(labels):
            ttk.Label(tab, text=label).grid(row=row, column=0, sticky="w", pady=5)
            var = tk.StringVar()
            ttk.Entry(tab, textvariable=var).grid(row=row, column=1, sticky="ew", pady=5)
            self.story_vars[key] = var

        ttk.Label(tab, text="Premise").grid(row=3, column=0, sticky="nw", pady=5)
        self.premise_text = tk.Text(tab, height=12, wrap="word")
        self.premise_text.grid(row=3, column=1, sticky="nsew", pady=5)

        ttk.Button(tab, text="Apply Story Edits", command=self._apply_story_edits).grid(row=4, column=1, sticky="e", pady=8)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(3, weight=1)

    def _build_characters_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Characters")

        left = ttk.Frame(tab)
        left.pack(side="left", fill="y", padx=(0, 12))
        self.character_list = tk.Listbox(left, width=28, height=28)
        self.character_list.pack(fill="y", expand=True)
        self.character_list.bind("<<ListboxSelect>>", self._select_character)
        ttk.Button(left, text="Add Character", command=self._add_character).pack(fill="x", pady=(8, 3))
        ttk.Button(left, text="Remove Character", command=self._remove_character).pack(fill="x")

        right = ttk.Frame(tab)
        right.pack(side="left", fill="both", expand=True)

        fields = [
            ("name", "Name", False),
            ("age", "Age", False),
            ("description", "Description", True),
            ("personality", "Personality", True),
            ("background", "Background", True),
            ("occupation", "Occupation", False),
            ("hair", "Hair", False),
            ("eyes", "Eyes", False),
        ]
        self.character_vars = {}
        self.character_texts = {}

        for row, (key, label, multiline) in enumerate(fields):
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=5)
            if multiline:
                widget = tk.Text(right, height=4, wrap="word")
                widget.grid(row=row, column=1, sticky="nsew", pady=5)
                self.character_texts[key] = widget
            else:
                var = tk.StringVar()
                ttk.Entry(right, textvariable=var).grid(row=row, column=1, sticky="ew", pady=5)
                self.character_vars[key] = var

        ttk.Button(right, text="Apply Character Edits", command=self._apply_character_edits).grid(
            row=len(fields), column=1, sticky="e", pady=8
        )
        right.columnconfigure(1, weight=1)

    def _build_state_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Current State")

        self.state_vars = {}
        fields = [
            ("chapter", "Chapter"),
            ("scene", "Scene"),
            ("status", "Status"),
            ("time_of_day", "Time of Day"),
            ("location", "Location"),
        ]
        for row, (key, label) in enumerate(fields):
            ttk.Label(tab, text=label).grid(row=row, column=0, sticky="w", pady=5)
            var = tk.StringVar()
            ttk.Entry(tab, textvariable=var, width=60).grid(row=row, column=1, sticky="ew", pady=5)
            self.state_vars[key] = var

        ttk.Label(tab, text="Scene Cast (one name per line)").grid(row=5, column=0, sticky="nw", pady=5)
        self.cast_text = tk.Text(tab, height=7, wrap="word")
        self.cast_text.grid(row=5, column=1, sticky="nsew", pady=5)

        ttk.Label(tab, text="Continuity Notes (one per line)").grid(row=6, column=0, sticky="nw", pady=5)
        self.notes_text = tk.Text(tab, height=7, wrap="word")
        self.notes_text.grid(row=6, column=1, sticky="nsew", pady=5)

        ttk.Button(tab, text="Apply State Edits", command=self._apply_state_edits).grid(row=7, column=1, sticky="e", pady=8)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(5, weight=1)
        tab.rowconfigure(6, weight=1)

    def _new_novel(self):
        self.package = StoryPackage.new()
        self.character_filename = None
        self.dirty = True
        self._refresh_all()
        self._chat("Builder", "New novel created.")

    def _open_novel(self):
        folder = filedialog.askdirectory(title="Open Novel Package")
        if not folder:
            return
        try:
            self.package = StoryPackage.load(Path(folder))
        except Exception as exc:
            messagebox.showerror("Open Novel", f"Could not open that novel package.\n\n{exc}")
            return
        self.character_filename = None
        self.dirty = False
        self._refresh_all()
        self._chat("Builder", f'Opened "{self.package.story_bible.get("title", Path(folder).name)}".')

    def _save(self):
        if self.package is None:
            return
        self._apply_all_edits()
        if self.package.path is None:
            return self._save_as()
        try:
            self.package.save()
            self.dirty = False
            self._update_path_label()
            self._chat("Builder", "Saved.")
        except Exception as exc:
            messagebox.showerror("Save", str(exc))

    def _save_as(self):
        if self.package is None:
            return
        self._apply_all_edits()
        parent = filedialog.askdirectory(title="Choose a folder for the novel package")
        if not parent:
            return
        name = self.package.story_bible.get("title", "Untitled").strip() or "Untitled"
        target = Path(parent) / StoryPackage.safe_filename(name).removesuffix(".json")
        try:
            self.package.save(target)
            self.dirty = False
            self._update_path_label()
            self._chat("Builder", f"Saved novel package to {target}.")
        except Exception as exc:
            messagebox.showerror("Save As / Export", str(exc))

    def _validate(self):
        if self.package is None:
            return
        self._apply_all_edits()
        errors = validate_package(self.package)
        if errors:
            messagebox.showerror("Validation", "Validation found problems:\n\n" + "\n".join(f"• {e}" for e in errors))
        else:
            messagebox.showinfo("Validation", "Package is valid.")

    def _apply_story_edits(self):
        if self.package is None:
            return
        self.package.story_bible["title"] = self.story_vars["title"].get().strip() or "Untitled"
        self.package.story_bible["version"] = self.story_vars["version"].get().strip() or "1.0"
        self.package.story_bible["status"] = self.story_vars["status"].get().strip() or "active"
        self.package.story_bible["premise"] = self.premise_text.get("1.0", "end-1c").strip()
        self.dirty = True
        self._update_path_label()

    def _apply_character_edits(self):
        if self.package is None or self.character_filename is None:
            return
        char = self.package.characters[self.character_filename]
        for key, var in self.character_vars.items():
            value = var.get().strip()
            if key == "age":
                char[key] = int(value) if value.isdigit() else (None if not value else value)
            else:
                char[key] = value
        for key, widget in self.character_texts.items():
            char[key] = widget.get("1.0", "end-1c").strip()
        self.dirty = True

    def _apply_state_edits(self):
        if self.package is None:
            return
        chapter = self.state_vars["chapter"].get().strip()
        scene = self.state_vars["scene"].get().strip()
        self.package.current_state["chapter"] = int(chapter) if chapter.isdigit() else 1
        self.package.current_state["scene"] = int(scene) if scene.isdigit() else 1
        for key in ("status", "time_of_day", "location"):
            self.package.current_state[key] = self.state_vars[key].get().strip()
        self.package.current_state["scene_cast"] = self._lines(self.cast_text)
        self.package.current_state["continuity_notes"] = self._lines(self.notes_text)
        self.dirty = True

    def _apply_all_edits(self):
        self._apply_story_edits()
        self._apply_character_edits()
        self._apply_state_edits()

    def _add_character(self):
        if self.package is None:
            return
        name = simpledialog.askstring("Add Character", "Character name:", parent=self)
        if not name:
            return
        try:
            filename = self.package.add_character(name)
        except ValueError as exc:
            messagebox.showerror("Add Character", str(exc))
            return
        self.character_filename = filename
        self.dirty = True
        self._refresh_characters(filename)
        self._chat("Builder", f"Added {name.strip()}.")

    def _remove_character(self):
        if self.package is None or self.character_filename is None:
            return
        char = self.package.characters[self.character_filename]
        name = char.get("name", self.character_filename)
        if not messagebox.askyesno("Remove Character", f"Remove {name}?"):
            return
        self.package.remove_character(self.character_filename)
        self.character_filename = None
        self.dirty = True
        self._refresh_characters()
        self._chat("Builder", f"Removed {name}.")

    def _select_character(self, _event=None):
        if self.package is None:
            return
        selection = self.character_list.curselection()
        if not selection:
            return
        filenames = sorted(self.package.characters)
        self.character_filename = filenames[selection[0]]
        char = self.package.characters[self.character_filename]

        for key, var in self.character_vars.items():
            value = char.get(key, "")
            var.set("" if value is None else str(value))
        for key, widget in self.character_texts.items():
            widget.delete("1.0", "end")
            widget.insert("1.0", str(char.get(key, "")))

    def _refresh_all(self):
        if self.package is None:
            return
        bible = self.package.story_bible
        self.story_vars["title"].set(bible.get("title", "Untitled"))
        self.story_vars["version"].set(bible.get("version", "1.0"))
        self.story_vars["status"].set(bible.get("status", "active"))
        self.premise_text.delete("1.0", "end")
        self.premise_text.insert("1.0", bible.get("premise", ""))

        self._refresh_characters()
        state = self.package.current_state
        for key in ("chapter", "scene", "status", "time_of_day", "location"):
            self.state_vars[key].set(str(state.get(key, "")))
        self.cast_text.delete("1.0", "end")
        self.cast_text.insert("1.0", "\n".join(map(str, state.get("scene_cast", []))))
        self.notes_text.delete("1.0", "end")
        self.notes_text.insert("1.0", "\n".join(map(str, state.get("continuity_notes", []))))
        self._update_path_label()

    def _refresh_characters(self, select_filename=None):
        self.character_list.delete(0, "end")
        filenames = sorted(self.package.characters) if self.package else []
        selected_index = None
        for index, filename in enumerate(filenames):
            self.character_list.insert("end", self.package.characters[filename].get("name", filename.removesuffix(".json")))
            if filename == select_filename:
                selected_index = index

        if selected_index is not None:
            self.character_list.selection_set(selected_index)
            self.character_list.see(selected_index)
            self._select_character()

    def _run_command(self):
        if self.package is None:
            return
        self._apply_all_edits()
        command = self.command_entry.get().strip()
        if not command:
            return
        self._chat("You", command)
        result = apply_command(self.package, command)
        self._chat("Builder", result.message)
        self.command_entry.delete(0, "end")
        if result.changed:
            self.dirty = True
            self._refresh_all()

    def _chat(self, speaker, message):
        self.chat_log.configure(state="normal")
        self.chat_log.insert("end", f"{speaker}: {message}\n\n")
        self.chat_log.configure(state="disabled")
        self.chat_log.see("end")

    @staticmethod
    def _lines(widget):
        return [line.strip() for line in widget.get("1.0", "end").splitlines() if line.strip()]

    def _update_path_label(self):
        path = "Unsaved novel" if self.package is None or self.package.path is None else str(self.package.path)
        self.path_label.configure(text=path + ("  *" if self.dirty else ""))


if __name__ == "__main__":
    StoryBuilderApp().mainloop()
