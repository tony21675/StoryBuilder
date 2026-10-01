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
from builder.writer_engine import WriterEngine
from builder.manuscript import ManuscriptManager
from builder.state_manager import StateManager
from builder.workspace import WORKSPACE_ROOT


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
        self.writer_engine = WriterEngine()
        self.writer_thread = None
        self.generated_scene = ""
        self.accepted_scene = ""
        self.pending_state_patch = None
        self.selected_manuscript_path = None
        self.saved_state_candidate = None
        self.selected_manuscript_path = None
        self.saved_state_candidate = None

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
        self._build_writer_tab()
        self._build_manuscript_tab()
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

    def _build_writer_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Writer")

        # The Writer tab contains more controls than a small laptop display can
        # show at once. Keep the tab itself scrollable so the lower analysis and
        # state-update controls remain reachable without requiring full-screen.
        scroll_frame = ttk.Frame(tab)
        scroll_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(scroll_frame, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(
            scroll_frame,
            orient="vertical",
            command=canvas.yview,
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        content_frame = ttk.Frame(canvas, padding=12)
        window_id = canvas.create_window((0, 0), window=content_frame, anchor="nw")

        def update_scroll_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def fit_content_width(event):
            canvas.itemconfigure(window_id, width=event.width)

        content_frame.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", fit_content_width)

        def on_mousewheel(event):
            if event.delta:
                canvas.yview_scroll(int(-event.delta / 120), "units")
            elif event.num == 4:
                canvas.yview_scroll(-3, "units")
            elif event.num == 5:
                canvas.yview_scroll(3, "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel, add="+")
        canvas.bind_all("<Button-4>", on_mousewheel, add="+")
        canvas.bind_all("<Button-5>", on_mousewheel, add="+")

        ttk.Label(
            content_frame,
            text="Local Story Writer",
            font=("", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            content_frame,
            text="Uses the current novel package as the writer's reference. The writer does not change canon by itself.",
        ).pack(anchor="w", pady=(4, 10))

        model_row = ttk.Frame(content_frame)
        model_row.pack(fill="x", pady=(0, 8))
        ttk.Label(model_row, text="Model").pack(side="left")
        self.writer_model_var = tk.StringVar()
        self.writer_model_combo = ttk.Combobox(
            model_row,
            textvariable=self.writer_model_var,
            state="readonly",
            width=72,
        )
        self.writer_model_combo.pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(model_row, text="Refresh Models", command=self._refresh_writer_models).pack(side="left")
        self.writer_start_button = ttk.Button(
            model_row,
            text="Start Writer",
            command=self._start_writer,
        )
        self.writer_start_button.pack(side="left", padx=(8, 3))
        self.writer_stop_button = ttk.Button(
            model_row,
            text="Stop",
            command=self._stop_writer,
        )
        self.writer_stop_button.pack(side="left", padx=3)
        self.writer_clear_context_button = ttk.Button(
            model_row,
            text="Clear Writer Context",
            command=self._clear_writer_context,
        )
        self.writer_clear_context_button.pack(side="left", padx=(8, 3))

        self.writer_status = ttk.Label(content_frame, text="Writer stopped.")
        self.writer_status.pack(anchor="w", pady=(0, 8))

        direction_header = ttk.Frame(content_frame)
        direction_header.pack(fill="x")
        ttk.Label(
            direction_header,
            text="Scene Direction",
            font=("", 11, "bold"),
        ).pack(side="left")
        ttk.Button(
            direction_header,
            text="Build Scene Direction",
            command=self._build_scene_direction,
        ).pack(side="right")
        self.writer_direction_text = tk.Text(content_frame, height=7, wrap="word")
        self.writer_direction_text.pack(fill="x", pady=(4, 8))
        self.writer_direction_text.insert(
            "1.0",
            "Write the next scene naturally from the current story state. Follow the active scene guidance and preserve established continuity.",
        )

        button_row = ttk.Frame(content_frame)
        button_row.pack(fill="x", pady=(0, 8))
        self.writer_write_button = ttk.Button(
            button_row,
            text="Write Next Scene",
            command=self._write_next_scene,
        )
        self.writer_write_button.pack(side="left")
        self.writer_save_draft_button = ttk.Button(
            button_row,
            text="Save Draft",
            command=self._save_generated_draft,
        )
        self.writer_save_draft_button.pack(side="left", padx=(8, 0))
        self.writer_accept_button = ttk.Button(
            button_row,
            text="Accept Scene",
            command=self._accept_generated_scene,
        )
        self.writer_accept_button.pack(side="left", padx=(8, 0))
        self.writer_reject_button = ttk.Button(
            button_row,
            text="Reject Scene",
            command=self._reject_generated_scene,
        )
        self.writer_reject_button.pack(side="left", padx=(8, 0))

        ttk.Label(
            content_frame,
            text="Generated Scene",
            font=("", 11, "bold"),
        ).pack(anchor="w")
        self.writer_output_text = tk.Text(content_frame, height=22, wrap="word", undo=True)
        self.writer_output_text.pack(fill="x", pady=(4, 0))

        state_button_row = ttk.Frame(content_frame)
        state_button_row.pack(fill="x", pady=(8, 0))
        self.writer_analyze_button = ttk.Button(
            state_button_row,
            text="Analyze Accepted Scene",
            command=self._analyze_accepted_scene,
        )
        self.writer_analyze_button.pack(side="left")
        self.writer_apply_state_button = ttk.Button(
            state_button_row,
            text="Apply State Update",
            command=self._apply_state_update,
        )
        self.writer_apply_state_button.pack(side="left", padx=(8, 0))

        proposed_state_header = ttk.Frame(content_frame)
        proposed_state_header.pack(fill="x", pady=(10, 0))
        ttk.Label(
            proposed_state_header,
            text="Proposed State Changes",
            font=("", 11, "bold"),
        ).pack(side="left")

        self.writer_copy_state_button = ttk.Button(
            proposed_state_header,
            text="Copy JSON",
            command=self._copy_proposed_state,
        )
        self.writer_copy_state_button.pack(side="right")

        self.writer_state_preview = tk.Text(content_frame, height=8, wrap="none", undo=True)
        self.writer_state_preview.pack(fill="x", pady=(4, 0))

        self._refresh_writer_models()
        self._update_writer_buttons()

    def _build_manuscript_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Manuscript")

        ttk.Label(
            tab,
            text="Accepted Scenes",
            font=("", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            tab,
            text="Accepted scenes are stored inside the novel package under Manuscript/Chapters.",
        ).pack(anchor="w", pady=(4, 10))

        row = ttk.Frame(tab)
        row.pack(fill="both", expand=True)

        left = ttk.Frame(row)
        left.pack(side="left", fill="y", padx=(0, 12))
        self.manuscript_list = tk.Listbox(
            left,
            width=34,
            height=28,
            exportselection=False,
        )
        self.manuscript_list.pack(fill="y", expand=True)
        self.manuscript_list.bind(
            "<<ListboxSelect>>",
            self._select_manuscript_scene,
        )

        manuscript_button_row = ttk.Frame(left)
        manuscript_button_row.pack(fill="x", pady=(8, 0))

        ttk.Button(
            manuscript_button_row,
            text="Refresh Manuscript",
            command=self._refresh_manuscript,
        ).pack(fill="x")

        # Recovery actions are placed beside the reconstructed-state panel so
        # they remain visible on smaller displays.
        right = ttk.Frame(row)
        right.pack(side="left", fill="both", expand=True)

        self.manuscript_output = tk.Text(
            right,
            wrap="word",
            undo=True,
        )
        self.manuscript_output.pack(fill="both", expand=True)

        recovery_header = ttk.Frame(right)
        recovery_header.pack(fill="x", pady=(10, 0))

        self.manuscript_recovery_status = ttk.Label(
            recovery_header,
            text="Select an accepted section, then analyze its state.",
            anchor="w",
            justify="left",
        )
        self.manuscript_recovery_status.pack(fill="x")

        recovery_actions = ttk.Frame(right)
        recovery_actions.pack(fill="x", pady=(6, 0))

        self.manuscript_analyze_button = ttk.Button(
            recovery_actions,
            text="Analyze Saved Section",
            command=self._analyze_saved_manuscript_scene,
        )
        self.manuscript_analyze_button.pack(side="left")

        self.manuscript_restore_button = ttk.Button(
            recovery_actions,
            text="Restore Reconstructed State",
            command=self._restore_saved_state_candidate,
        )
        self.manuscript_restore_button.pack(side="left", padx=(6, 0))

        self.manuscript_copy_state_button = ttk.Button(
            recovery_actions,
            text="Copy Reconstructed JSON",
            command=self._copy_saved_state_candidate,
        )
        self.manuscript_copy_state_button.pack(side="left", padx=(6, 0))

        ttk.Label(
            right,
            text="Reconstructed State",
            font=("", 11, "bold"),
        ).pack(anchor="w", pady=(8, 0))

        self.manuscript_state_preview = tk.Text(
            right,
            height=16,
            wrap="none",
            undo=True,
        )
        self.manuscript_state_preview.pack(fill="both", expand=True, pady=(4, 0))

        self.manuscript_analyze_button.configure(state="disabled")
        self.manuscript_restore_button.configure(state="disabled")
        self.manuscript_copy_state_button.configure(state="disabled")

    def _refresh_writer_models(self):
        if not hasattr(self, "writer_model_combo"):
            return
        paths = WriterEngine.available_models()
        values = [str(p) for p in paths]
        self.writer_model_combo["values"] = values
        current = self.writer_model_var.get()
        if current in values:
            self.writer_model_var.set(current)
        elif values:
            self.writer_model_var.set(values[0])
        else:
            self.writer_model_var.set("")
        self._update_writer_buttons()

    def _writer_package_files(self):
        if self.package is None:
            return []

        files = []
        for filename in sorted(self.package.characters):
            files.append((
                filename,
                json.dumps(
                    self.package.characters[filename],
                    indent=2,
                    ensure_ascii=False,
                ),
            ))

        files.append((
            "story_bible.json",
            json.dumps(self.package.story_bible, indent=2, ensure_ascii=False),
        ))
        files.append((
            "current_state.json",
            json.dumps(self.package.current_state, indent=2, ensure_ascii=False),
        ))

        # Keep the recurring guidance out of the model context. The relevant
        # scene_plan guidance is extracted by Build Scene Direction instead.
        scene = int(self.package.current_state.get("scene", 1) or 1)
        scene_cast = {
            str(name).casefold()
            for name in self.package.current_state.get("scene_cast", [])
        }

        # Do not place recent manuscript prose into the persistent system
        # prompt. The local base model may copy it instead of continuing the
        # current scene. The immediate ending of the previous accepted scene is
        # supplied in the per-scene user turn instead.
        for module in self.package.story_bible.get("optional_story_modules", []):
            if not isinstance(module, dict):
                continue

            filename = str(module.get("file", "")).strip()
            if not filename:
                continue

            data = self.package.extra_json.get(filename)
            status = str(
                data.get("status", module.get("status", "optional"))
                if isinstance(data, dict)
                else module.get("status", "optional")
            ).casefold()

            if not isinstance(data, dict) or status != "active":
                continue

            # Only load scene-specific module guidance for the current scene.
            # Do not expose an entire active module, which can contain future
            # events, hidden motives, identities, or other information the
            # current scene must not know.
            scene_guidance = data.get("scene_guidance", {})
            current_guidance = None
            if isinstance(scene_guidance, dict):
                current_guidance = scene_guidance.get(str(scene))
                if current_guidance is None:
                    current_guidance = scene_guidance.get(scene)

            if isinstance(current_guidance, dict):
                files.append((
                    filename,
                    json.dumps(
                        {
                            "name": data.get("name", module.get("name", filename)),
                            "scene_guidance": {str(scene): current_guidance},
                        },
                        indent=2,
                        ensure_ascii=False,
                    ),
                ))
                continue

            # Relationship dynamics has no scene-numbered module guidance.
            # Only expose the small portion relevant when Tony or Chloe is
            # actually present in the scene. Scene 1-5 do not need it.
            relationships = data.get("relationships")
            writing_guidance = data.get("writing_guidance")
            if (
                isinstance(relationships, dict)
                and (
                    "tony" in scene_cast
                    or "chloe" in scene_cast
                )
            ):
                relevant = {}
                for key, value in relationships.items():
                    if not isinstance(value, dict):
                        continue
                    key_text = str(key).casefold()
                    if any(person in key_text for person in scene_cast):
                        relevant[key] = value

                compact = {}
                if relevant:
                    compact["relationships"] = relevant
                if isinstance(writing_guidance, dict):
                    compact["writing_guidance"] = writing_guidance

                if compact:
                    files.append((
                        filename,
                        json.dumps(compact, indent=2, ensure_ascii=False),
                    ))

        return files

    def _build_scene_direction(self):
        if self.package is None:
            return

        state = self.package.current_state
        chapter = int(state.get("chapter", 1) or 1)
        scene = int(state.get("scene", 1) or 1)
        location = state.get("location", "")
        time_data = state.get("time", state.get("time_of_day", ""))
        cast = state.get("scene_cast", [])
        situation = str(state.get("current_situation", "") or "").strip()

        lines = [
            f"Continue Chapter {chapter}, Scene {scene} from the exact current story state.",
            "AUTHORITATIVE STATE RULE: The current scene number, primary location, scene cast, and current situation are authoritative for the present scene. If older continuity text or older scene-plan wording conflicts with them, follow the current state instead.",
        ]

        if isinstance(location, dict):
            primary_location = str(location.get("primary", "") or "").strip()
            if primary_location:
                lines.append(f"Current location: {primary_location}.")
        elif location:
            lines.append(f"Current location: {location}.")
        if isinstance(time_data, dict):
            period = str(time_data.get("period", "") or "").strip()
            exact = str(time_data.get("exact_time", "") or "").strip()
            if period:
                lines.append(
                    f"Time: {period}."
                    + (f" Exact time: {exact}." if exact and exact != "not established" else "")
                )
        elif time_data:
            lines.append(f"Time: {time_data}.")
        if cast:
            lines.append("Scene cast: " + ", ".join(map(str, cast)) + ".")
        if situation:
            lines.append(f"Current situation: {situation}")

        found_guidance = False

        # Extract only the current scene's recurring writing guidance. The full
        # writing_guidance.json stays out of the model context to reduce prompt size.
        writing_guidance = self.package.extra_json.get("writing_guidance.json")
        if isinstance(writing_guidance, dict):
            scene_plan = writing_guidance.get("scene_plan", {})
            if isinstance(scene_plan, dict):
                guidance = scene_plan.get(str(scene))
                if guidance is None:
                    guidance = scene_plan.get(scene)
                if isinstance(guidance, dict):
                    found_guidance = True
                    lines.append(
                        "Scene plan guidance (secondary to the current state and any author edits in this direction):"
                    )
                    direction = str(guidance.get("direction", "") or "").strip()
                    if direction:
                        lines.append(f"- Direction: {direction}")
                    end_condition = str(guidance.get("end_condition", "") or "").strip()
                    if end_condition:
                        lines.append(
                            f"- Planned scene boundary: {end_condition}"
                        )
                    pacing = str(guidance.get("pacing", "") or "").strip()
                    if pacing:
                        lines.append(f"- Pacing: {pacing}")

        for module in self.package.story_bible.get("optional_story_modules", []):
            if not isinstance(module, dict):
                continue

            filename = str(module.get("file", "")).strip()
            data = self.package.extra_json.get(filename)
            if not isinstance(data, dict):
                continue

            status = str(data.get("status", module.get("status", "optional"))).casefold()
            if status != "active":
                continue

            scene_guidance = data.get("scene_guidance", {})
            guidance = scene_guidance.get(str(scene))
            if guidance is None:
                guidance = scene_guidance.get(scene)
            if not isinstance(guidance, dict):
                continue

            found_guidance = True
            name = str(data.get("name") or module.get("name") or filename)
            lines.append(f"Active module guidance: {name}")
            for event in guidance.get("required_events", []):
                lines.append(f"- Required beat: {event}")
            end_condition = guidance.get("end_condition")
            if end_condition:
                lines.append(f"- End condition: {end_condition}")
            for item in guidance.get("do_not_advance", []):
                lines.append(f"- Do not advance: {item}")

        if not found_guidance:
            lines.append("No activated scene-specific module guidance was found.")

        lines.append(
            "Write the scene naturally. Use harmless everyday interpersonal details when appropriate, "
            "but do not invent consequential canon or reveal information the characters do not know."
        )

        self.writer_direction_text.delete("1.0", "end")
        self.writer_direction_text.insert("1.0", "\n".join(lines))
        self.writer_status.configure(text="Scene direction built from the current state and active modules.")

    def _writer_system_prompt(self, files):
        base = """You are the local story generation engine for an ongoing fictional novel.

Use the attached files as private reference material. Do not quote or explain the reference files.
Character files establish character identity and knowledge. story_bible.json establishes permanent canon. current_state.json establishes the exact current situation. The generated scene direction provides the relevant writing guidance for this scene. Active story modules provide scene-specific or optional material that has been activated.

Knowledge rules:
- Characters know only what they witnessed, experienced, were told, or could reasonably infer.
- Keep unknown information unknown.
- Do not reveal hidden module information unless the active module or current scene naturally establishes it.
- Do not invent major plot facts, identities, motives, locations, evidence, consequential backstory, or secret knowledge.
- Natural small talk, ordinary memories, harmless feelings, shared experiences, inside jokes, and everyday interpersonal details between established relationships are encouraged.
- Give established friends and family room to actually talk to one another. Prefer natural back-and-forth dialogue and responsive interaction over summarizing that they talked.
- Minor scene-level details may be invented freely when they fit the characters, setting, and established relationships.
- These harmless details do not need to already exist in the reference files.
- Only treat a detail as a continuity problem when it creates a contradiction, reveals information the characters could not know, changes a consequential fact, or crosses an explicit scene boundary.

Character consistency:
- Preserve established character gender, names, and pronouns exactly.
- Before finishing the scene, internally check every character reference and pronoun for consistency.
- Never refer to Tiffany, Maya, Chloe, or another established female character as "he", "him", "his", "boy", or another incompatible masculine reference. Apply the same rule in reverse for established male characters.
- Do not accidentally transfer one character's clothing, scent, possessions, actions, thoughts, or physical traits to another character.
- Preserve established signature scents exactly. In the current novel: Tiffany = coconut and strawberry; Maya = vanilla; Chloe = pineapple. Do not assign one character's established scent to another or invent a conflicting signature scent.
- Only characters in the current scene cast should contribute actions, dialogue, thoughts, or sensory details unless the author direction explicitly permits otherwise.

Writing rules:
- Write only the requested story prose.
- Continue from the exact current state.
- Do not restart earlier scenes.
- Treat explicit AUTHOR DIRECTION as the highest-priority instruction for this scene.
- If the author direction contains a HARD STOP or End condition, obey that boundary exactly. Do not continue past it, even if the scene feels unfinished.
- Only characters listed in the current scene cast should be physically present or actively participating in the scene unless the author direction explicitly says otherwise.
- Do not cut away to or narrate characters outside the current scene cast merely because their location is recorded for continuity.
- Treat off-cast character locations as continuity information only. Do not infer that an off-cast character's home, house, activities, or whereabouts lie along the characters' travel route.
- Do not mention an off-cast character's home or location unless the current scene direction explicitly calls for it or the scene itself naturally establishes it as relevant.
- Preserve requested scene order and emotional beats.
- Treat current_state.current_situation, current_state.scene_cast, and the primary current location as authoritative for the present scene when they conflict with stale continuity wording or older planning text.
- Scene-plan guidance is useful planning context, but it is secondary to explicit author edits and the authoritative current state.
- When the author direction calls for a detailed action, confrontation, kidnapping, escape, or emotional recovery, fully dramatize the event rather than skipping over it or summarizing it. Give important physical and emotional beats enough room to develop, generally allowing roughly 800–1200 words unless the author direction specifies another length.
- For a character with established relevant training or experience, let that background affect their instincts, awareness, choices, and resistance without making them unrealistically invincible. Tiffany may struggle, resist, improvise, and use determination shaped by being raised by a Special Forces father, but she can still be overwhelmed or captured when the scene requires it. Keep action grounded and story-focused rather than providing real-world tactical instructions.
- When a scene is an emotional aftermath or rescue/recovery scene, stay with the characters' interaction long enough for the emotions, reassurance, physical grounding, and relationship dynamics to play out. Do not rush directly to exposition.
- Do not establish an exact date, exact time, season, or other timeline detail unless the current state or author direction establishes it.
- Do not summarize the scene or provide notes.
"""
        parts = [base, "\nAUTHORITATIVE STORY FILES START\n"]
        for name, content in files:
            parts.append(f"\n[Attached File: {name}]\n{content}\n")
        parts.append("\nAUTHORITATIVE STORY FILES END")
        return "\n".join(parts)

    def _update_writer_buttons(self):
        if not hasattr(self, "writer_start_button"):
            return

        running = (
            self.writer_engine.child is not None
            and self.writer_engine.child.isalive()
        )
        has_scene = bool(self.generated_scene.strip())
        has_accepted = bool(self.accepted_scene.strip())
        has_patch = isinstance(self.pending_state_patch, dict)

        self.writer_start_button.configure(
            state="disabled" if running else "normal"
        )
        self.writer_stop_button.configure(
            state="normal" if running else "disabled"
        )
        self.writer_write_button.configure(
            state="normal" if running and self.package else "disabled"
        )
        self.writer_save_draft_button.configure(
            state="normal" if has_scene and self.package else "disabled"
        )
        self.writer_accept_button.configure(
            state="normal" if has_scene and not has_accepted and self.package else "disabled"
        )
        self.writer_reject_button.configure(
            state="normal" if has_scene and not has_accepted and self.package else "disabled"
        )
        if hasattr(self, "writer_clear_context_button"):
            self.writer_clear_context_button.configure(
                state="normal" if running and self.package else "disabled"
            )
        self.writer_analyze_button.configure(
            state="normal" if has_accepted and self.package else "disabled"
        )
        self.writer_apply_state_button.configure(
            state="normal" if has_patch and self.package else "disabled"
        )
        self.writer_status.configure(
            text=(
                f"Writer running: {self.writer_engine.model_path.name}"
                if running and self.writer_engine.model_path
                else "Writer stopped."
            )
        )

    def _start_writer(self):
        if self.package is None:
            messagebox.showerror("Writer", "Open or create a novel first.")
            return

        model = self.writer_model_var.get().strip()
        if not model:
            messagebox.showerror("Writer", "Select a GGUF model first.")
            return

        self._save()
        if self.dirty:
            return

        files = self._writer_package_files()
        system_prompt = self._writer_system_prompt(files)
        self.writer_status.configure(text="Starting writer...")
        self.writer_start_button.configure(state="disabled")

        def work():
            try:
                self.writer_engine.start(model, system_prompt)
                error = None
            except Exception as exc:
                error = str(exc)
            self.after(0, lambda: self._finish_writer_start(error))

        self.writer_thread = threading.Thread(target=work, daemon=True)
        self.writer_thread.start()

    def _finish_writer_start(self, error):
        if error:
            messagebox.showerror("Writer", error)
        self._update_writer_buttons()

    def _stop_writer(self):
        try:
            self.writer_engine.stop()
        finally:
            self._update_writer_buttons()

    def _clear_writer_context(self):
        if self.package is None:
            return

        if self.writer_engine.child is None or not self.writer_engine.child.isalive():
            self.writer_status.configure(text="Writer is not running. Start it before clearing context.")
            self._update_writer_buttons()
            return

        self._save()
        if self.dirty:
            return

        model = self.writer_engine.model_path
        if model is None:
            messagebox.showerror("Writer", "No active writer model is available.")
            return

        files = self._writer_package_files()
        system_prompt = self._writer_system_prompt(files)

        self.writer_clear_context_button.configure(state="disabled")
        self.writer_status.configure(text="Clearing writer context...")

        def work():
            try:
                self.writer_engine.reset_context(model, system_prompt)
                error = None
            except Exception as exc:
                error = str(exc)
            self.after(0, lambda: self._finish_writer_context_reset(error))

        self.writer_thread = threading.Thread(target=work, daemon=True)
        self.writer_thread.start()

    def _finish_writer_context_reset(self, error):
        if error:
            messagebox.showerror("Writer", error)
            self._update_writer_buttons()
            return

        self.writer_status.configure(
            text="Writer context cleared and rebuilt from the current story state."
        )
        self._update_writer_buttons()

    def _write_next_scene(self):
        direction = self.writer_direction_text.get("1.0", "end-1c").strip()
        if not direction:
            direction = "Write the next scene naturally from the current story state."

        self._save()
        if self.dirty:
            return

        self.writer_write_button.configure(state="disabled")
        self.writer_status.configure(text="Writing scene...")

        chapter = int(self.package.current_state.get("chapter", 1) or 1)
        scene = int(self.package.current_state.get("scene", 1) or 1)

        previous_ending = ""
        if self.package.path is not None and scene > 1:
            manager = ManuscriptManager(self.package.path)
            previous_scene_path = manager.scene_path(chapter, scene - 1)
            if previous_scene_path.is_file():
                try:
                    previous_text = previous_scene_path.read_text(encoding="utf-8").strip()
                except OSError:
                    previous_text = ""
                if previous_text:
                    previous_ending = previous_text[-3500:]

        prompt_parts = [
            "AUTHOR DIRECTION:\n",
            direction,
            "\n\n",
        ]
        if previous_ending:
            prompt_parts.extend([
                "PREVIOUS SCENE ENDING (continuation reference only):\n",
                previous_ending,
                "\n\n"
                "Do not repeat, restart, or paraphrase this quoted ending. "
                "Begin Scene "
                + str(scene)
                + " at the point where the previous scene ends and continue forward.\n\n",
            ])
        prompt_parts.extend([
            "IMPORTANT SCENE BOUNDARY:\n",
            "The HARD STOP in the author direction is mandatory. "
            "The scene is not complete until that exact endpoint is reached. "
            "Do not end the scene early. Do not skip ahead beyond the endpoint. "
            "Use enough prose to fully dramatize the requested movement and arrive at the endpoint. "
            "Do not treat a generic word count as a hard limit. Ordinary scenes can be concise, while detailed "
            "action or emotional scenes should be substantially longer when needed, generally around 800 to 1200 "
            "words unless the scene direction specifies another length. Characters outside the scene cast are "
            "continuity-only and should not be mentioned or narrated "
            "unless the author direction explicitly requires it.\n\n"
            "Write the next scene now. Output only the prose."
        ])
        prompt = "".join(prompt_parts)

        def work():
            try:
                answer = self.writer_engine.generate(prompt)
                error = None
            except Exception as exc:
                answer = ""
                error = str(exc)
            self.after(0, lambda: self._finish_generated_scene(answer, error))

        self.writer_thread = threading.Thread(target=work, daemon=True)
        self.writer_thread.start()

    def _finish_generated_scene(self, answer, error):
        if error:
            messagebox.showerror("Writer", error)
            self._update_writer_buttons()
            return

        self.generated_scene = answer.strip()
        self.writer_output_text.delete("1.0", "end")
        self.writer_output_text.insert("1.0", self.generated_scene)
        self.writer_status.configure(
            text="Scene generated. Review it, save a draft if desired, then accept or reject it."
        )
        self._update_writer_buttons()

    def _reject_generated_scene(self):
        if not self.generated_scene.strip():
            return

        if not messagebox.askyesno(
            "Reject Scene",
            "Discard this generated scene? It will not be accepted into the manuscript.",
        ):
            return

        self.generated_scene = ""
        self.writer_output_text.delete("1.0", "end")
        self.writer_status.configure(
            text="Scene rejected. The current story state and manuscript were not changed."
        )
        self._update_writer_buttons()

    def _save_generated_draft(self):
        if not self.package or self.package.path is None or not self.generated_scene.strip():
            return

        try:
            chapter = int(self.package.current_state.get("chapter", 1))
            scene = int(self.package.current_state.get("scene", 1))
            path = ManuscriptManager(self.package.path).save_draft(
                chapter,
                scene,
                self.generated_scene,
            )
            self._refresh_manuscript()
            messagebox.showinfo("Writer", f"Draft saved to:\n\n{path}")
        except Exception as exc:
            messagebox.showerror("Writer", str(exc))

    def _accept_generated_scene(self):
        if not self.package or self.package.path is None or not self.generated_scene.strip():
            return

        edited = self.writer_output_text.get("1.0", "end-1c").strip()
        if edited:
            self.generated_scene = edited

        try:
            chapter = int(self.package.current_state.get("chapter", 1))
            scene = int(self.package.current_state.get("scene", 1))
            manager = ManuscriptManager(self.package.path)
            path = manager.scene_path(chapter, scene)
            if path.exists():
                replace = messagebox.askyesno(
                    "Replace Existing Scene",
                    f"{path.name} already exists. Replace it with this accepted scene?"
                )
                if not replace:
                    return
            path = manager.save_scene(
                chapter,
                scene,
                self.generated_scene,
            )
            # Preserve the exact current state that existed before this accepted
            # section. This provides a durable recovery baseline for later state
            # reconstruction.
            manager.save_state_before(
                chapter,
                scene,
                json.loads(json.dumps(self.package.current_state)),
            )
            self.accepted_scene = self.generated_scene
            self.pending_state_patch = None
            self.writer_state_preview.delete("1.0", "end")
            self._refresh_manuscript()
            self._chat(
                "Builder",
                f"Accepted Scene {scene} and saved it to {path}.",
            )
            self.writer_status.configure(
                text="Scene accepted. You can now analyze it for state changes."
            )
            self._update_writer_buttons()
        except Exception as exc:
            messagebox.showerror("Writer", str(exc))

    def _analyze_accepted_scene(self):
        if (
            not self.package
            or not self.accepted_scene.strip()
            or not self.writer_engine.model_path
        ):
            return

        current_state = dict(self.package.current_state)
        story_text = self.accepted_scene
        model = self.writer_engine.model_path

        self.writer_analyze_button.configure(state="disabled")
        self.writer_apply_state_button.configure(state="disabled")
        self.writer_status.configure(text="Analyzing accepted scene...")

        def work():
            try:
                patch = StateManager.propose(
                    model,
                    current_state,
                    story_text,
                )
                error = None
            except Exception as exc:
                patch = None
                error = str(exc)

            self.after(
                0,
                lambda: self._finish_state_analysis(patch, error),
            )

        self.writer_thread = threading.Thread(
            target=work,
            daemon=True,
        )
        self.writer_thread.start()

    def _finish_state_analysis(self, patch, error):
        if error:
            messagebox.showerror("State Update", error)
            self._update_writer_buttons()
            return

        self.pending_state_patch = patch or {}
        self.writer_state_preview.delete("1.0", "end")
        self.writer_state_preview.insert(
            "1.0",
            json.dumps(self.pending_state_patch, indent=2, ensure_ascii=False),
        )
        self.writer_status.configure(
            text="State update proposed. Review it before applying."
        )
        self._update_writer_buttons()

    def _apply_state_update(self):
        if self.package is None or not isinstance(self.pending_state_patch, dict):
            return

        try:
            completed_chapter = int(self.package.current_state.get("chapter", 1) or 1)
            completed_scene = int(self.package.current_state.get("scene", 1) or 1)

            self.package.current_state = StateManager.merge_patch(
                self.package.current_state,
                self.pending_state_patch,
            )

            # The accepted section is now complete. Advance the package to the
            # next scene so the Writer tab can immediately build the next scene
            # direction without requiring a separate chat command.
            current_chapter = int(self.package.current_state.get("chapter", completed_chapter) or completed_chapter)
            current_scene = int(self.package.current_state.get("scene", completed_scene) or completed_scene)

            if current_chapter == completed_chapter and current_scene == completed_scene:
                self.package.current_state["scene"] = completed_scene + 1
            else:
                # If the continuity manager explicitly advanced the state, keep
                # its chapter/scene decision intact.
                pass

            self.package.current_state["scene_completed"] = False
            self.dirty = True
            self.pending_state_patch = None
            self.generated_scene = ""
            self.accepted_scene = ""
            self.writer_output_text.delete("1.0", "end")
            self.writer_state_preview.delete("1.0", "end")
            self._refresh_all()
            self._save()
            self._chat(
                "Builder",
                f"Scene {completed_scene} is complete. Current scene advanced to "
                f"Chapter {self.package.current_state.get('chapter', current_chapter)}, "
                f"Scene {self.package.current_state.get('scene')} and saved.",
            )
            self.writer_status.configure(
                text="Previous scene saved. Build Scene Direction to begin the next scene."
            )
            self._update_writer_buttons()
        except Exception as exc:
            messagebox.showerror("State Update", str(exc))

    def _copy_proposed_state(self):
        if not hasattr(self, "writer_state_preview"):
            return

        value = self.writer_state_preview.get("1.0", "end-1c").strip()
        if not value:
            return

        try:
            self.clipboard_clear()
            self.clipboard_append(value)
            self.update_idletasks()
            if hasattr(self, "writer_copy_state_button"):
                self.writer_copy_state_button.configure(text="Copied ✓")
                self.after(
                    1200,
                    lambda: self.writer_copy_state_button.configure(text="Copy JSON")
                )
        except tk.TclError:
            pass

    def _selected_manuscript_scene(self):
        if self.package is None or self.package.path is None:
            return None
        selection = self.manuscript_list.curselection()
        if not selection:
            return None
        items = ManuscriptManager(self.package.path).list_scenes()
        index = selection[0]
        if index >= len(items):
            return None
        return items[index]

    def _selected_writer_model_for_analysis(self):
        model = self.writer_engine.model_path
        if model:
            return model
        selected = self.writer_model_var.get().strip()
        if not selected:
            raise ValueError("Select a GGUF model first.")
        return WriterEngine.validate_model(selected)

    def _analyze_saved_manuscript_scene(self):
        path = self._selected_manuscript_scene()
        if path is None or self.package is None or self.package.path is None:
            return

        numbers = ManuscriptManager.scene_numbers(path)
        if numbers is None:
            messagebox.showerror(
                "State Recovery",
                f"Could not determine chapter and scene numbers from {path.name}.",
            )
            return

        try:
            story_text = path.read_text(encoding="utf-8").strip()
            if not story_text:
                raise ValueError("The selected manuscript section is empty.")

            chapter, scene = numbers
            manager = ManuscriptManager(self.package.path)
            baseline = manager.load_state_before(chapter, scene)
            used_fallback = baseline is None
            if baseline is None:
                # Scene 1 currently predates the snapshot feature. For this
                # existing section, the current state is the best available
                # starting point.
                baseline = json.loads(
                    json.dumps(self.package.current_state)
                )

            model = self._selected_writer_model_for_analysis()

            self.manuscript_analyze_button.configure(state="disabled")
            self.manuscript_restore_button.configure(state="disabled")
            self.manuscript_copy_state_button.configure(state="disabled")
            self.manuscript_recovery_status.configure(
                text=f"Analyzing {path.name}..."
            )

            def work():
                try:
                    patch = StateManager.propose(
                        model,
                        baseline,
                        story_text,
                    )
                    candidate = StateManager.merge_patch(
                        baseline,
                        patch,
                    )
                    save_path = manager.save_state_after_candidate(
                        chapter,
                        scene,
                        candidate,
                    )
                    result = {
                        "patch": patch,
                        "candidate": candidate,
                        "save_path": save_path,
                        "used_fallback": used_fallback,
                        "error": None,
                    }
                except Exception as exc:
                    result = {
                        "patch": None,
                        "candidate": None,
                        "save_path": None,
                        "used_fallback": used_fallback,
                        "error": str(exc),
                    }

                self.after(
                    0,
                    lambda result=result: self._finish_saved_state_analysis(result),
                )

            self.writer_thread = threading.Thread(
                target=work,
                daemon=True,
            )
            self.writer_thread.start()

        except Exception as exc:
            messagebox.showerror("State Recovery", str(exc))
            self._update_saved_state_buttons()

    def _finish_saved_state_analysis(self, result):
        error = result.get("error")
        if error:
            messagebox.showerror("State Recovery", error)
            self._update_saved_state_buttons()
            return

        self.saved_state_candidate = result.get("candidate")
        self.manuscript_state_preview.delete("1.0", "end")
        self.manuscript_state_preview.insert(
            "1.0",
            json.dumps(
                self.saved_state_candidate,
                indent=2,
                ensure_ascii=False,
            ),
        )

        save_path = result.get("save_path")
        note = "using the current state as the baseline because no before-state snapshot exists" if result.get("used_fallback") else "using the saved before-state snapshot"
        self.manuscript_recovery_status.configure(
            text=f"Reconstructed state saved to {save_path.name} ({note})."
        )
        self._update_saved_state_buttons()

    def _update_saved_state_buttons(self):
        has_selection = self._selected_manuscript_scene() is not None
        has_candidate = isinstance(self.saved_state_candidate, dict)

        if hasattr(self, "manuscript_analyze_button"):
            self.manuscript_analyze_button.configure(
                state="normal" if has_selection else "disabled"
            )
        if hasattr(self, "manuscript_restore_button"):
            self.manuscript_restore_button.configure(
                state="normal" if has_candidate and self.package else "disabled"
            )
        if hasattr(self, "manuscript_copy_state_button"):
            self.manuscript_copy_state_button.configure(
                state="normal" if has_candidate else "disabled"
            )

    def _restore_saved_state_candidate(self):
        if self.package is None or not isinstance(self.saved_state_candidate, dict):
            return

        if not messagebox.askyesno(
            "Restore Reconstructed State",
            "Replace the current story state with this reconstructed state?\\n\\n"
            "The reconstructed JSON has already been saved as a recovery file.",
        ):
            return

        self.package.current_state = json.loads(
            json.dumps(self.saved_state_candidate)
        )
        self.dirty = True
        self._refresh_all()
        self._save()
        self._chat(
            "Builder",
            "Restored current_state from the selected manuscript section's reconstructed state.",
        )
        self.manuscript_recovery_status.configure(
            text="Reconstructed state restored and saved to current_state.json."
        )
        self._update_saved_state_buttons()

    def _copy_saved_state_candidate(self):
        if not isinstance(self.saved_state_candidate, dict):
            return
        try:
            value = json.dumps(
                self.saved_state_candidate,
                indent=2,
                ensure_ascii=False,
            )
            self.clipboard_clear()
            self.clipboard_append(value)
            self.update_idletasks()
            self.manuscript_copy_state_button.configure(text="Copied ✓")
            self.after(
                1200,
                lambda: self.manuscript_copy_state_button.configure(
                    text="Copy Reconstructed JSON"
                ),
            )
        except tk.TclError:
            pass

    def _refresh_manuscript(self):
        if not hasattr(self, "manuscript_list"):
            return
        self.manuscript_list.delete(0, "end")

        if self.package is None or self.package.path is None:
            return

        for path in ManuscriptManager(self.package.path).list_scenes():
            self.manuscript_list.insert(
                "end",
                str(path.relative_to(self.package.path)),
            )

    def _select_manuscript_scene(self, _event=None):
        if self.package is None or self.package.path is None:
            return

        selection = self.manuscript_list.curselection()
        if not selection:
            return

        items = ManuscriptManager(self.package.path).list_scenes()
        index = selection[0]
        if index >= len(items):
            return

        path = items[index]
        self.selected_manuscript_path = path
        self.saved_state_candidate = None
        self.manuscript_state_preview.delete("1.0", "end")
        self.manuscript_recovery_status.configure(
            text=f"Selected {path.name}. Click Analyze Saved Section to reconstruct its state."
        )
        self._update_saved_state_buttons()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Manuscript", str(exc))
            return

        self.manuscript_output.delete("1.0", "end")
        self.manuscript_output.insert("1.0", text)

    def _close_and_sync(self):
        if self._closing:
            return
        self._closing = True

        try:
            try:
                self.writer_engine.stop()
            except Exception:
                pass

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
        try:
            self.writer_engine.stop()
        except Exception:
            pass
        self.generated_scene = ""
        self.accepted_scene = ""
        self.pending_state_patch = None
        self.package = StoryPackage.new()
        self.character_filename = None
        self.dirty = True
        if hasattr(self, "writer_output_text"):
            self.writer_output_text.delete("1.0", "end")
            self.writer_state_preview.delete("1.0", "end")
        self._refresh_all()
        self._chat("Builder", "New novel created.")

    def _open_novel(self):
        self.guided_setup.stop()
        if hasattr(self, "guided_button"):
            self.guided_button.configure(text="Guided Setup")
        folder = filedialog.askdirectory(
            title="Open Novel Package",
            initialdir=str(WORKSPACE_ROOT),
        )
        if not folder:
            return
        try:
            self.writer_engine.stop()
        except Exception:
            pass
        try:
            self.package = StoryPackage.load(Path(folder))
        except Exception as exc:
            messagebox.showerror("Open Novel", f"Could not open that novel package.\n\n{exc}")
            return
        self.character_filename = None
        self.generated_scene = ""
        self.accepted_scene = ""
        self.pending_state_patch = None
        self.dirty = False
        if hasattr(self, "writer_output_text"):
            self.writer_output_text.delete("1.0", "end")
            self.writer_state_preview.delete("1.0", "end")
        self._refresh_all()
        self._refresh_writer_models()
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
        parent = filedialog.askdirectory(
            title="Choose a folder for the novel package",
            initialdir=str(WORKSPACE_ROOT),
        )
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
        if hasattr(self, "_refresh_manuscript"):
            self._refresh_manuscript()
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
            self.writer_direction_text,
            self.writer_output_text,
            self.writer_state_preview,
            self.manuscript_state_preview,
            self.manuscript_output,
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
            self.writer_direction_text,
            self.writer_output_text,
            self.manuscript_output,
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
