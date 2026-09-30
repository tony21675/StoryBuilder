from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from builder.conversation import apply_command
from builder.guided_setup import GuidedSetupSession
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
        self.guided_setup = GuidedSetupSession()
        self._closing = False
        self.spellcheck_available = shutil.which("aspell") is not None
        self._spellcheck_jobs = {}

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._close_and_sync)
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
        ttk.Button(toolbar, text="Close & Sync", command=self._close_and_sync).pack(side="left", padx=(10, 3))
        self.path_label = ttk.Label(toolbar, text="Unsaved novel")
        self.path_label.pack(side="right", padx=8)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._build_chat_tab()
        self._build_story_tab()
        self._build_characters_tab()
        self._build_relationships_tab()
        self._build_locations_tab()
        self._build_modules_tab()
        self._build_planning_tab()
        self._build_state_tab()
        self._install_context_menus()
        self._install_spellchecking()

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
        self.command_entry.bind("<Return>", self._submit_on_enter)
        self.command_entry.bind("<KP_Enter>", self._submit_on_enter)
        ttk.Button(row, text="Apply Change", command=self._run_command).pack(side="left", padx=(8, 0))
        self.guided_button = ttk.Button(row, text="Guided Setup", command=self._toggle_guided_setup)
        self.guided_button.pack(side="left", padx=(8, 0))
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
            ("role", "Role", False),
            ("age", "Age", False),
            ("description", "Description", True),
            ("personality", "Personality", True),
            ("background", "Background", True),
            ("occupation", "Occupation", False),
            ("appearance", "Appearance", True),
            ("relationships", "Relationships", True),
            ("important_items", "Important Items", True),
            ("knowledge_rule", "Knowledge Rule", True),
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
                entry = ttk.Entry(right, textvariable=var)
                entry.grid(row=row, column=1, sticky="ew", pady=5)
                self.character_vars[key] = var

        ttk.Button(right, text="Apply Character Edits", command=self._apply_character_edits).grid(
            row=len(fields), column=1, sticky="e", pady=8
        )
        right.columnconfigure(1, weight=1)

    def _build_relationships_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Relationships")

        ttk.Label(
            tab,
            text="Established relationships (one per line: Name-Name: relationship)",
            font=("", 11, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            tab,
            text="Edit relationship facts already stored in story_bible.json.",
        ).pack(anchor="w", pady=(4, 10))

        self.relationships_text = tk.Text(tab, wrap="word")
        self.relationships_text.pack(fill="both", expand=True)

        ttk.Button(
            tab,
            text="Apply Relationship Edits",
            command=self._apply_relationship_edits,
        ).pack(anchor="e", pady=(8, 0))

    def _build_locations_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Locations")

        ttk.Label(
            tab,
            text="Established locations (one per line: location_id: description)",
            font=("", 11, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            tab,
            text="Edit location facts already stored in story_bible.json.",
        ).pack(anchor="w", pady=(4, 10))

        self.locations_text = tk.Text(tab, wrap="word")
        self.locations_text.pack(fill="both", expand=True)

        ttk.Button(
            tab,
            text="Apply Location Edits",
            command=self._apply_location_edits,
        ).pack(anchor="e", pady=(8, 0))

    def _build_modules_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Story Modules")

        left = ttk.Frame(tab)
        left.pack(side="left", fill="y", padx=(0, 12))

        ttk.Label(
            left,
            text="Optional Modules",
            font=("", 11, "bold"),
        ).pack(anchor="w")

        self.module_list = tk.Listbox(left, width=32, height=18, exportselection=False)
        self.module_list.pack(fill="y", expand=True, pady=(6, 8))
        self.module_list.bind("<<ListboxSelect>>", self._select_module)

        ttk.Button(left, text="Activate Module", command=lambda: self._set_module_status("active")).pack(
            fill="x", pady=2
        )
        ttk.Button(left, text="Set Optional", command=lambda: self._set_module_status("optional")).pack(
            fill="x", pady=2
        )

        right = ttk.Frame(tab)
        right.pack(side="left", fill="both", expand=True)

        self.module_info = ttk.Label(right, text="Select a module.", justify="left", anchor="w")
        self.module_info.pack(fill="x", pady=(0, 8))

        self.module_text = tk.Text(right, wrap="none", undo=True)
        self.module_text.pack(fill="both", expand=True)

        ttk.Button(
            right,
            text="Apply Module JSON",
            command=self._apply_module_edits,
        ).pack(anchor="e", pady=(8, 0))


    def _build_planning_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Story Planning")

        ttk.Label(
            tab,
            text="Optional story planning",
            font=("", 12, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            tab,
            text="These are planning facts, not requirements. Leave unknown items blank and come back later.",
        ).pack(anchor="w", pady=(4, 10))

        fields = [
            ("genre", "Genre"),
            ("tone", "Tone"),
            ("core_conflict", "Central Conflict"),
            ("opposition", "Opposition / Antagonist"),
            ("setting", "Setting / World"),
            ("important_elements", "Important Elements"),
        ]
        self.planning_vars = {}
        for key, label in fields:
            frame = ttk.Frame(tab)
            frame.pack(fill="x", pady=4)
            ttk.Label(frame, text=label, width=24).pack(side="left", anchor="nw")
            var = tk.StringVar()
            ttk.Entry(frame, textvariable=var).pack(side="left", fill="x", expand=True)
            self.planning_vars[key] = var

        ttk.Label(tab, text="Themes (one per line)").pack(anchor="w", pady=(8, 2))
        self.themes_text = tk.Text(tab, height=5, wrap="word")
        self.themes_text.pack(fill="x")

        ttk.Label(tab, text="Open Questions / Undecided Details (one per line)").pack(anchor="w", pady=(8, 2))
        self.open_questions_text = tk.Text(tab, height=7, wrap="word")
        self.open_questions_text.pack(fill="both", expand=True)

        ttk.Button(tab, text="Apply Story Planning", command=self._apply_planning_edits).pack(anchor="e", pady=(8, 0))

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
            entry = ttk.Entry(tab, textvariable=var, width=60)
            entry.grid(row=row, column=1, sticky="ew", pady=5)
            self.state_vars[key] = var

        ttk.Label(tab, text="Scene Cast (one name per line)").grid(row=5, column=0, sticky="nw", pady=5)
        self.cast_text = tk.Text(tab, height=7, wrap="word")
        self.cast_text.grid(row=5, column=1, sticky="nsew", pady=5)

        ttk.Label(tab, text="Continuity Notes (one per line)").grid(row=6, column=0, sticky="nw", pady=5)
        self.notes_text = tk.Text(tab, height=7, wrap="word")
        self.notes_text.grid(row=6, column=1, sticky="nsew", pady=5)

        ttk.Button(tab, text="Apply State Edits", command=self._apply_state_edits).grid(row=7, column=1, sticky="e", pady=8)
        ttk.Label(tab, text="Current Situation").grid(row=8, column=0, sticky="nw", pady=5)
        self.situation_text = tk.Text(tab, height=5, wrap="word")
        self.situation_text.grid(row=8, column=1, sticky="nsew", pady=5)
        ttk.Button(tab, text="Apply Situation", command=self._apply_situation_edit).grid(row=9, column=1, sticky="e", pady=8)

        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(5, weight=1)
        tab.rowconfigure(6, weight=1)
        tab.rowconfigure(8, weight=1)

    def _close_and_sync(self):
        if self._closing:
            return
        self._closing = True

        try:
            # Save all current editor contents before running the repository sync.
            self._save()
            if self.dirty:
                # Save was cancelled or failed, so do not close and risk losing work.
                self._closing = False
                return

            sync_script = Path(__file__).resolve().parent / "sync.sh"
            if not sync_script.exists():
                messagebox.showerror(
                    "Close & Sync",
                    f"Could not find sync.sh at:\n\n{sync_script}\n\nThe app will remain open."
                )
                self._closing = False
                return

            result = subprocess.run(
                ["bash", str(sync_script), "finish"],
                cwd=sync_script.parent,
                text=True,
                capture_output=True,
                timeout=120,
                check=False,
            )

            if result.returncode != 0:
                details = (result.stderr or result.stdout or "Unknown sync error").strip()
                messagebox.showerror(
                    "Close & Sync",
                    "The novel was saved locally, but GitHub sync failed.\n\n"
                    + details
                    + "\n\nThe app will remain open so you can resolve the problem."
                )
                self._closing = False
                return

            self.destroy()
        except (OSError, subprocess.SubprocessError) as exc:
            messagebox.showerror(
                "Close & Sync",
                f"The novel was saved locally, but the GitHub sync could not be completed.\n\n{exc}\n\nThe app will remain open."
            )
            self._closing = False

    def _new_novel(self):
        self.guided_setup.stop()
        if hasattr(self, "guided_button"):
            self.guided_button.configure(text="Guided Setup")
        self.package = StoryPackage.new()
        self.character_filename = None
        self.dirty = True
        self._refresh_all()
        self._chat("Builder", "New novel created.")

    def _open_novel(self):
        self.guided_setup.stop()
        if hasattr(self, "guided_button"):
            self.guided_button.configure(text="Guided Setup")
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

        description = self.character_texts["description"].get("1.0", "end-1c").strip()
        if description or "description" in char:
            char["description"] = description

        personality = self._parse_multivalue(
            self.character_texts["personality"].get("1.0", "end-1c")
        )
        if personality or "personality" in char:
            char["personality"] = personality

        background = self.character_texts["background"].get("1.0", "end-1c").strip()
        if background or "background" in char:
            char["background"] = background

        appearance = self._parse_key_value_block(
            self.character_texts["appearance"].get("1.0", "end-1c")
        )
        if appearance or "appearance" in char:
            char["appearance"] = appearance

        relationships = self._parse_key_value_block(
            self.character_texts["relationships"].get("1.0", "end-1c")
        )
        if relationships or "relationships" in char:
            char["relationships"] = relationships

        important_items = self._parse_key_value_block(
            self.character_texts["important_items"].get("1.0", "end-1c")
        )
        if important_items or "important_items" in char:
            char["important_items"] = important_items

        knowledge_rule = self.character_texts["knowledge_rule"].get("1.0", "end-1c").strip()
        if knowledge_rule or "knowledge_rule" in char:
            char["knowledge_rule"] = knowledge_rule

        self.dirty = True

    def _apply_relationship_edits(self):
        if self.package is None:
            return
        self.package.story_bible["relationships"] = self._parse_key_value_block(
            self.relationships_text.get("1.0", "end-1c")
        )
        self.dirty = True
        self._update_path_label()

    def _apply_location_edits(self):
        if self.package is None:
            return
        self.package.story_bible["locations"] = self._parse_key_value_block(
            self.locations_text.get("1.0", "end-1c")
        )
        self.dirty = True
        self._update_path_label()

    def _refresh_modules(self, select_file=None):
        self.module_list.delete(0, "end")
        if self.package is None:
            return

        modules = self.package.story_bible.get("optional_story_modules", [])
        selected_index = None

        for index, module in enumerate(modules):
            if not isinstance(module, dict):
                continue
            filename = str(module.get("file", "")).strip()
            if not filename:
                continue
            data = self.package.extra_json.get(filename, {})
            name = str(module.get("name") or data.get("name") or filename)
            status = str(data.get("status", module.get("status", "optional")))
            label = f"{name} [{status}]"
            self.module_list.insert("end", label)
            if filename == select_file:
                selected_index = self.module_list.size() - 1

        if selected_index is not None:
            self.module_list.selection_set(selected_index)
            self.module_list.see(selected_index)
            self._select_module()

    def _selected_module(self):
        if self.package is None:
            return None

        selection = self.module_list.curselection()
        if not selection:
            return None

        modules = [
            module
            for module in self.package.story_bible.get("optional_story_modules", [])
            if isinstance(module, dict) and str(module.get("file", "")).strip()
        ]
        if selection[0] >= len(modules):
            return None
        return modules[selection[0]]

    def _select_module(self, _event=None):
        if self.package is None:
            return

        # Use the listbox selection directly and avoid destructive clearing
        # when a transient selection event fires while the widget is updating.
        selection = self.module_list.curselection()
        if not selection:
            return

        modules = [
            module
            for module in self.package.story_bible.get("optional_story_modules", [])
            if isinstance(module, dict) and str(module.get("file", "")).strip()
        ]
        index = selection[0]
        if index < 0 or index >= len(modules):
            return

        module = modules[index]
        filename = str(module.get("file", "")).strip()
        data = self.package.extra_json.get(filename)
        if not isinstance(data, dict):
            data = {}

        name = str(module.get("name") or data.get("name") or filename)
        status = str(data.get("status", module.get("status", "optional")))
        module_type = str(data.get("type", module.get("type", "story_module")))
        char_files = module.get("character_files", [])

        info = f"File: {filename}\nStatus: {status}\nType: {module_type}"
        if char_files:
            info += "\nCharacter files: " + ", ".join(map(str, char_files))
        self.module_info.configure(text=info)

        self.module_text.delete("1.0", "end")
        self.module_text.insert("1.0", json.dumps(data, indent=2, ensure_ascii=False))

    def _apply_module_edits(self):
        module = self._selected_module()
        if module is None or self.package is None:
            return

        filename = str(module.get("file", "")).strip()
        if not filename:
            return

        raw = self.module_text.get("1.0", "end-1c").strip()
        if not raw:
            messagebox.showerror("Module", "Module JSON cannot be empty.")
            return

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            messagebox.showerror(
                "Module",
                f"Invalid JSON at line {exc.lineno}, column {exc.colno}.\n\n{exc.msg}",
            )
            return

        if not isinstance(data, dict):
            messagebox.showerror("Module", "Module JSON must contain an object at the top level.")
            return

        self.package.extra_json[filename] = data
        self.dirty = True
        self._refresh_modules(select_file=filename)
        self._update_path_label()

    def _set_module_status(self, status):
        module = self._selected_module()
        if module is None or self.package is None:
            return

        filename = str(module.get("file", "")).strip()
        if not filename:
            return

        data = self.package.extra_json.setdefault(filename, {})
        data["status"] = status
        self.dirty = True
        self._refresh_modules(select_file=filename)
        self._update_path_label()


    def _apply_planning_edits(self):
        if self.package is None:
            return
        planning = self.package.story_bible.setdefault("story_planning", {})
        for key, var in self.planning_vars.items():
            value = var.get().strip()
            if value:
                planning[key] = value
            else:
                planning.pop(key, None)

        themes = self._lines(self.themes_text)
        if themes:
            planning["themes"] = themes
        else:
            planning.pop("themes", None)

        questions = self._lines(self.open_questions_text)
        if questions:
            planning["open_questions"] = questions
        else:
            planning.pop("open_questions", None)

        self.dirty = True
        self._update_path_label()

    def _apply_state_edits(self):
        if self.package is None:
            return
        state = self.package.current_state
        chapter = self.state_vars["chapter"].get().strip()
        scene = self.state_vars["scene"].get().strip()
        state["chapter"] = int(chapter) if chapter.isdigit() else 1
        state["scene"] = int(scene) if scene.isdigit() else 1
        state["status"] = self.state_vars["status"].get().strip()

        time_text = self.state_vars["time_of_day"].get().strip()
        if isinstance(state.get("time"), dict):
            state["time"]["period"] = time_text
        else:
            state["time_of_day"] = time_text

        location_text = self.state_vars["location"].get().strip()
        if isinstance(state.get("location"), dict):
            state["location"]["primary"] = location_text
        else:
            state["location"] = location_text

        inferred_cast = self._infer_scene_cast(state)
        entered_cast = self._lines(self.cast_text)
        if "scene_cast" in state or entered_cast != inferred_cast:
            state["scene_cast"] = entered_cast

        entered_notes = self._lines(self.notes_text)
        existing_notes = state.get("continuity_notes")
        if existing_notes is None:
            existing_notes = state.get("continuity_requirements", [])
        if "continuity_notes" in state or entered_notes != list(map(str, existing_notes)):
            state["continuity_notes"] = entered_notes
        self.dirty = True

    def _apply_all_edits(self):
        self._apply_story_edits()
        self._apply_planning_edits()
        self._apply_character_edits()
        self._apply_relationship_edits()
        self._apply_location_edits()
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

        self._set_character_text("description", char.get("description", ""))
        self._set_character_text("background", char.get("background", ""))
        self._set_character_text("knowledge_rule", char.get("knowledge_rule", ""))
        self._set_character_text("personality", self._format_multivalue(char.get("personality", [])))
        self._set_character_text("appearance", self._format_key_value_block(char.get("appearance", {})))
        self._set_character_text("relationships", self._format_key_value_block(char.get("relationships", {})))
        self._set_character_text("important_items", self._format_key_value_block(char.get("important_items", {})))

    def _set_character_text(self, key, value):
        widget = self.character_texts.get(key)
        if widget is None:
            return
        widget.delete("1.0", "end")
        widget.insert("1.0", str(value))

    @staticmethod
    def _format_multivalue(value):
        if isinstance(value, list):
            return "\n".join(str(item) for item in value)
        return str(value or "")

    @staticmethod
    def _parse_multivalue(value):
        return [line.strip() for line in value.splitlines() if line.strip()]

    @staticmethod
    def _format_key_value_block(value):
        if not isinstance(value, dict):
            return str(value or "")
        return "\n".join(f"{key}: {val}" for key, val in value.items())

    @staticmethod
    def _parse_key_value_block(value):
        result = {}
        for line in value.splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            result[key.strip()] = val.strip()
        return result

    def _refresh_all(self):
        if self.package is None:
            return
        bible = self.package.story_bible
        self.story_vars["title"].set(bible.get("title", "Untitled"))
        self.story_vars["version"].set(bible.get("version", "1.0"))
        self.story_vars["status"].set(bible.get("status", "active"))
        self.premise_text.delete("1.0", "end")
        self.premise_text.insert("1.0", bible.get("premise", ""))

        planning = bible.get("story_planning", {})
        if not isinstance(planning, dict):
            planning = {}
        for key, var in self.planning_vars.items():
            var.set(str(planning.get(key, "") or ""))

        self.themes_text.delete("1.0", "end")
        self.themes_text.insert("1.0", "\n".join(map(str, planning.get("themes", []) or [])))

        self.open_questions_text.delete("1.0", "end")
        self.open_questions_text.insert("1.0", "\n".join(map(str, planning.get("open_questions", []) or [])))

        self.relationships_text.delete("1.0", "end")
        self.relationships_text.insert(
            "1.0",
            self._format_key_value_block(bible.get("relationships", {})),
        )

        self.locations_text.delete("1.0", "end")
        self.locations_text.insert(
            "1.0",
            self._format_key_value_block(bible.get("locations", {})),
        )

        self._refresh_characters()
        self._refresh_modules()
        state = self.package.current_state
        self.state_vars["chapter"].set(str(state.get("chapter", "")))
        self.state_vars["scene"].set(str(state.get("scene", "")))
        self.state_vars["status"].set(str(state.get("status", "")))

        time_data = state.get("time", state.get("time_of_day", ""))
        if isinstance(time_data, dict):
            period = time_data.get("period", "")
            exact = time_data.get("exact_time", "")
            time_display = period if not exact or exact == "not established" else f"{period} ({exact})"
        else:
            time_display = str(time_data or "")
        self.state_vars["time_of_day"].set(time_display)

        location_data = state.get("location", "")
        if isinstance(location_data, dict):
            # Only edit the authoritative primary location here. Preserve any
            # per-character location entries already stored in nested state.
            location_display = str(location_data.get("primary", "") or "")
        else:
            location_display = str(location_data or "")
        self.state_vars["location"].set(location_display)
        self.cast_text.delete("1.0", "end")
        scene_cast = state.get("scene_cast")
        if not scene_cast:
            scene_cast = self._infer_scene_cast(state)
        self.cast_text.insert("1.0", "\n".join(map(str, scene_cast)))

        continuity = state.get("continuity_notes")
        if not continuity:
            continuity = state.get("continuity_requirements", [])
        self.notes_text.delete("1.0", "end")
        self.notes_text.insert("1.0", "\n".join(map(str, continuity)))
        self.situation_text.delete("1.0", "end")
        self.situation_text.insert("1.0", str(state.get("current_situation", "")))
        self._update_path_label()

    @staticmethod
    def _infer_scene_cast(state):
        location = state.get("location", {})
        if not isinstance(location, dict):
            return []

        current_situation = str(state.get("current_situation", "") or "").casefold()

        # Respect an explicit statement that someone is not participating in
        # the current scene. This is preferable to guessing from location text.
        excluded = set()
        for name, place in location.items():
            if name == "primary":
                continue
            name_cf = str(name).casefold()
            if (
                f"{name_cf} remains at home" in current_situation
                and "not participating in their scene" in current_situation
            ) or (
                f"{name_cf} is not participating" in current_situation
            ):
                excluded.add(str(name))

        primary = str(location.get("primary", "") or "").casefold()

        def location_matches_primary(person_location):
            text = str(person_location or "").casefold()
            if not text or not primary:
                return False

            # Common natural-language equivalents used by the current state
            # schema. This avoids treating "At home" as a separate place from
            # "Tony and Tiffany's home."
            if "home" in primary and "home" in text:
                return True
            if "house" in primary and ("house" in text or "home" in text):
                return True
            if "garage" in primary and "garage" in text:
                return True

            # Otherwise require a meaningful shared phrase/token.
            primary_words = {
                word for word in re.findall(r"[a-z0-9]+", primary)
                if len(word) >= 4 and word not in {"tony", "tiffany", "maya", "chloe"}
            }
            text_words = set(re.findall(r"[a-z0-9]+", text))
            return bool(primary_words & text_words)

        cast = []
        for name, person_location in location.items():
            if name == "primary" or str(name) in excluded:
                continue
            if not location_matches_primary(person_location):
                cast.append(str(name))

        # If no reliable separation exists, fall back to every explicitly
        # located character rather than inventing a cast list.
        if cast:
            return cast
        return [str(name) for name in location if name != "primary" and str(name) not in excluded]

    def _apply_situation_edit(self):
        if self.package is None:
            return
        self.package.current_state["current_situation"] = self.situation_text.get("1.0", "end-1c").strip()
        self.dirty = True
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


    def _toggle_guided_setup(self):
        if self.package is None:
            return
        if self.guided_setup.active:
            message = self.guided_setup.stop()
            self.guided_button.configure(text="Guided Setup")
            self._chat("Builder", message)
            return

        self._apply_all_edits()
        # Guided setup writes directly to the package. Do not let stale editor
        # selection state cause a later chat answer to overwrite a character.
        self.character_filename = None
        message = self.guided_setup.start(self.package)
        self.guided_button.configure(text="Stop Guided Setup")
        self._chat("Builder", message)

    def _run_command(self):
        if self.package is None:
            return
        self._apply_all_edits()
        command = self.command_entry.get().strip()
        if not command:
            return

        self._chat("You", command)
        self.command_entry.delete(0, "end")

        if self.guided_setup.active:
            result = self.guided_setup.handle(self.package, command)
            self._chat("Builder", result.message)
            if not result.error:
                self.dirty = True
                self._refresh_all()
            if result.complete:
                self.guided_button.configure(text="Guided Setup")
            return

        result = apply_command(self.package, command)
        self._chat("Builder", result.message)
        if result.changed:
            self.dirty = True
            self._refresh_all()

    def _submit_on_enter(self, _event=None):
        self._run_command()
        return "break"

    def _install_spellchecking(self):
        self._spellcheck_text_widgets = [
            self.premise_text,
            *self.character_texts.values(),
            self.cast_text,
            self.notes_text,
            self.relationships_text,
            self.locations_text,
            self.module_text,
            self.situation_text,
            self.themes_text,
            self.open_questions_text,
        ]
        for widget in self._spellcheck_text_widgets:
            widget.tag_configure("misspelled", underline=True)
            widget.bind("<<Modified>>", self._schedule_spellcheck, add="+")
            widget.edit_modified(False)

        if not self.spellcheck_available:
            self._chat(
                "Builder",
                "Live spell check is available when the system 'aspell' program is installed."
            )

    def _schedule_spellcheck(self, event=None):
        widget = event.widget if event is not None else None
        if widget is None or widget not in self._spellcheck_text_widgets:
            return

        try:
            widget.edit_modified(False)
        except tk.TclError:
            return

        job = self._spellcheck_jobs.get(widget)
        if job is not None:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass

        self._spellcheck_jobs[widget] = self.after(450, lambda w=widget: self._spellcheck_widget(w))

    def _spellcheck_widget(self, widget):
        self._spellcheck_jobs.pop(widget, None)
        if not self.spellcheck_available:
            return

        text = widget.get("1.0", "end-1c")
        if not text.strip():
            widget.tag_remove("misspelled", "1.0", "end")
            return

        def check_in_background(source_text):
            try:
                proc = subprocess.run(
                    ["aspell", "--lang=en_US", "list"],
                    input=source_text,
                    text=True,
                    capture_output=True,
                    timeout=2,
                    check=False,
                )
                words = {line.strip().lower() for line in proc.stdout.splitlines() if line.strip()}
            except (OSError, subprocess.SubprocessError):
                words = None

            self.after(0, lambda: self._apply_spellcheck_result(widget, source_text, words))

        threading.Thread(target=check_in_background, args=(text,), daemon=True).start()

    def _apply_spellcheck_result(self, widget, source_text, misspelled):
        try:
            current_text = widget.get("1.0", "end-1c")
        except tk.TclError:
            return

        if current_text != source_text or misspelled is None:
            return

        widget.tag_remove("misspelled", "1.0", "end")

        for match in re.finditer(r"\b[A-Za-z][A-Za-z'-]*\b", source_text):
            word = match.group(0)
            if word.lower() not in misspelled:
                continue
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            widget.tag_add("misspelled", start, end)

    def _install_context_menus(self):
        # Tkinter provides keyboard clipboard shortcuts, but does not create
        # a right-click context menu automatically on Linux. Add one to every
        # text-entry widget used by StoryBuilder.
        widgets = [
            self.premise_text,
            *self.character_texts.values(),
            self.cast_text,
            self.notes_text,
            self.relationships_text,
            self.locations_text,
            self.module_text,
            self.situation_text,
            self.themes_text,
            self.open_questions_text,
        ]

        # Find the Entry widgets associated with StringVars by walking the
        # widget tree. This keeps the data model unchanged.
        widgets.extend(self._find_entry_widgets(self))

        for widget in widgets:
            self._add_context_menu(widget)

    @staticmethod
    def _find_entry_widgets(root):
        entries = []
        for child in root.winfo_children():
            if isinstance(child, ttk.Entry):
                entries.append(child)
            entries.extend(StoryBuilderApp._find_entry_widgets(child))
        return entries

    @staticmethod
    def _add_context_menu(widget):
        menu = tk.Menu(widget, tearoff=0)

        def selection_range():
            try:
                if isinstance(widget, tk.Text):
                    ranges = widget.tag_ranges("sel")
                    if len(ranges) == 2:
                        return ranges[0], ranges[1]
                else:
                    if widget.selection_present():
                        return widget.index("sel.first"), widget.index("sel.last")
            except tk.TclError:
                pass
            return None

        def copy():
            try:
                selected = selection_range()
                if selected is None:
                    return
                start_index, end_index = selected
                value = widget.get(start_index, end_index)
                widget.clipboard_clear()
                widget.clipboard_append(value)
                widget.update_idletasks()
            except tk.TclError:
                pass

        def cut():
            try:
                selected = selection_range()
                if selected is None:
                    return
                start_index, end_index = selected
                value = widget.get(start_index, end_index)
                widget.clipboard_clear()
                widget.clipboard_append(value)
                widget.update_idletasks()
                widget.delete(start_index, end_index)
            except tk.TclError:
                pass

        def paste():
            try:
                value = widget.clipboard_get()
            except tk.TclError:
                return

            try:
                selected = selection_range()
                if selected is not None:
                    start_index, end_index = selected
                    widget.delete(start_index, end_index)
                    widget.insert(start_index, value)
                    if isinstance(widget, tk.Text):
                        widget.mark_set("insert", f"{start_index} + {len(value)} chars")
                    else:
                        widget.icursor(widget.index(start_index) + len(value))
                else:
                    widget.insert("insert", value)
            except tk.TclError:
                pass

        def select_all():
            try:
                if isinstance(widget, tk.Text):
                    widget.tag_add("sel", "1.0", "end-1c")
                    widget.mark_set("insert", "end-1c")
                else:
                    widget.select_range(0, "end")
                    widget.icursor("end")
                widget.focus_set()
            except tk.TclError:
                pass

        menu.add_command(label="Cut", command=cut)
        menu.add_command(label="Copy", command=copy)
        menu.add_command(label="Paste", command=paste)
        menu.add_separator()
        menu.add_command(label="Select All", command=select_all)

        def show_menu(event):
            try:
                # Do not move focus or insertion point here. A right-click
                # must preserve an existing text selection so Paste can replace
                # the highlighted text.
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        widget.bind("<Button-3>", show_menu, add="+")
        widget.bind("<Control-x>", lambda _event: (cut(), "break")[1], add="+")
        widget.bind("<Control-c>", lambda _event: (copy(), "break")[1], add="+")
        widget.bind("<Control-v>", lambda _event: (paste(), "break")[1], add="+")
        widget.bind("<Control-a>", lambda _event: (select_all(), "break")[1], add="+")

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
