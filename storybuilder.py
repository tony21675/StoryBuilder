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
from builder.scene_contract import SceneContract
from builder.story_interview import (
    CHARACTER_QUESTIONS,
    RELATIONSHIP_QUESTIONS,
    LOCATION_QUESTIONS,
    apply_interview_patch,
    structure_answer,
)
from builder.workspace import NOVEL_ROOT, WORKSPACE_ROOT


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
        self._scroll_canvases = []
        self.spellcheck_available = shutil.which("aspell") is not None
        self._spellcheck_jobs = {}
        self.writer_engine = WriterEngine()
        self.writer_thread = None
        self.generated_scene = ""
        self.accepted_scene = ""
        self.pending_state_patch = None
        self.selected_manuscript_path = None
        self.saved_state_candidate = None
        self.interview_active = False
        self.interview_index = 0
        self.interview_pending_patch = None
        self.interview_pending_answer = ""
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
        ttk.Button(toolbar, text="Close", command=self._close_without_sync).pack(side="left", padx=(10, 3))
        ttk.Button(toolbar, text="Close & Sync", command=self._close_and_sync).pack(side="left", padx=3)
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
        self._build_story_interview_tab()
        self._build_scene_contract_tab()
        self._build_state_tab()
        self._build_writer_tab()
        self._build_manuscript_tab()
        self._install_context_menus()
        self._install_mousewheel_scrolling()
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

        ttk.Label(left, text="Core Characters", font=("", 11, "bold")).pack(anchor="w")
        self.character_list = tk.Listbox(left, width=28, height=16, exportselection=False)
        self.character_list.pack(fill="y", expand=True, pady=(4, 6))
        self.character_list.bind("<<ListboxSelect>>", self._select_character)
        ttk.Button(left, text="Add Character", command=self._add_character).pack(fill="x", pady=(0, 3))
        ttk.Button(left, text="Remove Character", command=self._remove_character).pack(fill="x")

        ttk.Label(left, text="Supporting People", font=("", 11, "bold")).pack(anchor="w", pady=(14, 2))
        ttk.Label(
            left,
            text="Stored in story_bible.json as supporting people rather than full character cards.",
            wraplength=190,
            justify="left",
        ).pack(anchor="w", pady=(0, 4))
        self.supporting_people_list = tk.Listbox(left, width=28, height=8, exportselection=False)
        self.supporting_people_list.pack(fill="y")
        self.supporting_people_list.bind("<<ListboxSelect>>", self._select_supporting_person)

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

        ttk.Separator(right, orient="horizontal").grid(
            row=len(fields) + 1, column=0, columnspan=2, sticky="ew", pady=(8, 8)
        )
        ttk.Label(
            right,
            text="Supporting Person Details",
            font=("", 11, "bold"),
        ).grid(row=len(fields) + 2, column=0, columnspan=2, sticky="w")
        self.supporting_person_text = tk.Text(right, height=7, wrap="word", undo=True)
        self.supporting_person_text.grid(
            row=len(fields) + 3,
            column=0,
            columnspan=2,
            sticky="nsew",
            pady=(4, 0),
        )
        ttk.Button(
            right,
            text="Apply Supporting Person Edit",
            command=self._apply_supporting_person_edit,
        ).grid(row=len(fields) + 4, column=1, sticky="e", pady=8)

        right.columnconfigure(1, weight=1)
        right.rowconfigure(len(fields) + 3, weight=1)

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


    def _build_story_interview_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Story Interview")

        scroll_frame = ttk.Frame(tab)
        scroll_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(scroll_frame, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._scroll_canvases.append(canvas)

        content = ttk.Frame(canvas, padding=12)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def update_scroll_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def fit_content_width(event):
            canvas.itemconfigure(window_id, width=event.width)

        content.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", fit_content_width)

        ttk.Label(
            content,
            text="Guided Story Interview",
            font=("", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            content,
            text=(
                "Answer naturally, the way you would explain the story to a person. "
                "Simple answers are handled directly. For richer answers, the local LLM "
                "turns your answer into a proposed JSON change that you approve before it becomes canon."
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        target_row = ttk.Frame(content)
        target_row.pack(fill="x", pady=(0, 10))

        ttk.Label(target_row, text="Interview").pack(side="left")
        self.interview_mode_var = tk.StringVar(value="Character")
        self.interview_mode_combo = ttk.Combobox(
            target_row,
            textvariable=self.interview_mode_var,
            values=("Character", "Relationship", "Location"),
            state="readonly",
            width=16,
        )
        self.interview_mode_combo.pack(side="left", padx=(8, 14))
        self.interview_mode_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._refresh_interview_targets(reset=True),
        )

        ttk.Label(target_row, text="Target").pack(side="left")
        self.interview_target_var = tk.StringVar()
        self.interview_target_combo = ttk.Combobox(
            target_row,
            textvariable=self.interview_target_var,
            state="readonly",
            width=48,
        )
        self.interview_target_combo.pack(side="left", fill="x", expand=True, padx=(8, 8))
        self.interview_target_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._start_story_interview(),
        )

        ttk.Button(
            target_row,
            text="Refresh",
            command=lambda: self._refresh_interview_targets(reset=False),
        ).pack(side="left")

        self.interview_question_label = ttk.Label(
            content,
            text="Select a target to begin.",
            font=("", 12, "bold"),
            wraplength=900,
            justify="left",
        )
        self.interview_question_label.pack(anchor="w", pady=(2, 4))

        self.interview_prompt_label = ttk.Label(
            content,
            text="",
            wraplength=900,
            justify="left",
        )
        self.interview_prompt_label.pack(anchor="w", pady=(0, 10))

        ttk.Label(
            content,
            text="Your Answer",
            font=("", 11, "bold"),
        ).pack(anchor="w")
        self.interview_answer_text = tk.Text(
            content,
            height=9,
            wrap="word",
            undo=True,
        )
        self.interview_answer_text.pack(fill="x", pady=(4, 8))

        answer_row = ttk.Frame(content)
        answer_row.pack(fill="x")
        self.interview_process_button = ttk.Button(
            answer_row,
            text="Process Answer",
            command=self._process_story_interview_answer,
        )
        self.interview_process_button.pack(side="left")
        self.interview_skip_button = ttk.Button(
            answer_row,
            text="Skip",
            command=self._skip_story_interview_question,
        )
        self.interview_skip_button.pack(side="left", padx=(8, 0))
        self.interview_stop_button = ttk.Button(
            answer_row,
            text="Stop Interview",
            command=self._stop_story_interview,
        )
        self.interview_stop_button.pack(side="left", padx=(8, 0))

        ttk.Label(
            content,
            text="AI Proposed Changes",
            font=("", 11, "bold"),
        ).pack(anchor="w", pady=(14, 0))
        self.interview_proposed_text = tk.Text(
            content,
            height=12,
            wrap="none",
            state="disabled",
        )
        self.interview_proposed_text.pack(fill="both", expand=True, pady=(4, 8))

        proposal_row = ttk.Frame(content)
        proposal_row.pack(fill="x")
        self.interview_approve_button = ttk.Button(
            proposal_row,
            text="Approve Changes",
            command=self._approve_story_interview_patch,
        )
        self.interview_approve_button.pack(side="left")
        self.interview_reject_button = ttk.Button(
            proposal_row,
            text="Reject Changes",
            command=self._reject_story_interview_patch,
        )
        self.interview_reject_button.pack(side="left", padx=(8, 0))
        self.interview_status = ttk.Label(
            content,
            text="",
            wraplength=900,
            justify="left",
        )
        self.interview_status.pack(anchor="w", fill="x", pady=(8, 0))

        self.interview_mode_combo.set("Character")
        self._refresh_interview_targets(reset=True)
        self._update_story_interview_buttons()

    def _build_scene_contract_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Scene Contract")

        scroll_frame = ttk.Frame(tab)
        scroll_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(scroll_frame, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._scroll_canvases.append(canvas)
        content = ttk.Frame(canvas, padding=12)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def update_scroll_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def fit_content_width(event):
            canvas.itemconfigure(window_id, width=event.width)

        content.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", fit_content_width)

        ttk.Label(
            content,
            text="Author-Controlled Scene Contract",
            font=("", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            content,
            text=(
                "Define the rails, not every sentence. The writer may vary the middle, "
                "dialogue, gestures, and harmless details while the contract protects the "
                "required story beats and ending."
            ),
        ).pack(anchor="w", pady=(4, 8))

        header = ttk.Frame(content)
        header.pack(fill="x", pady=(0, 8))
        self.scene_contract_scene_label = ttk.Label(
            header,
            text="Chapter 1, Scene 1",
            font=("", 11, "bold"),
        )
        self.scene_contract_scene_label.pack(side="left")

        ttk.Button(
            header,
            text="Load Current Scene",
            command=self._refresh_scene_contract_editor,
        ).pack(side="right")

        start_frame = ttk.LabelFrame(content, text="Beginning / Current State")
        start_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(
            start_frame,
            text=(
                "The scene begins from Current State. Change that state on the Current State tab "
                "instead of duplicating it here."
            ),
            justify="left",
        ).pack(anchor="w", padx=8, pady=(6, 4))
        self.scene_contract_start_text = tk.Text(
            start_frame,
            height=6,
            wrap="word",
            state="disabled",
        )
        self.scene_contract_start_text.pack(fill="x", padx=8, pady=(0, 8))

        form = ttk.Frame(content)
        form.pack(fill="both", expand=True)

        self.scene_contract_direction_text = tk.Text(form, height=4, wrap="word", undo=True)
        self.scene_contract_end_text = tk.Text(form, height=4, wrap="word", undo=True)
        self.scene_contract_texts = {
            "required_beats": tk.Text(form, height=5, wrap="word", undo=True),
            "required_facts": tk.Text(form, height=4, wrap="word", undo=True),
            "required_sequence": tk.Text(form, height=4, wrap="word", undo=True),
            "forbidden": tk.Text(form, height=4, wrap="word", undo=True),
            "forbidden_details": tk.Text(form, height=4, wrap="word", undo=True),
        }

        fields = [
            ("direction", "Middle / Scene Direction", self.scene_contract_direction_text),
            ("end", "Ending / Hard Stop", self.scene_contract_end_text),
            ("required_beats", "Required Beats (one per line)", self.scene_contract_texts["required_beats"]),
            ("required_facts", "Required Facts (one per line)", self.scene_contract_texts["required_facts"]),
            ("required_sequence", "Required Sequence (one per line, in order)", self.scene_contract_texts["required_sequence"]),
            ("forbidden", "Forbidden / Do Not Advance (one per line)", self.scene_contract_texts["forbidden"]),
            ("forbidden_details", "Forbidden Details (one per line)", self.scene_contract_texts["forbidden_details"]),
        ]

        for row, (_key, label, widget) in enumerate(fields):
            ttk.Label(form, text=label).grid(
                row=row,
                column=0,
                sticky="nw",
                padx=(0, 10),
                pady=4,
            )
            widget.grid(row=row, column=1, sticky="nsew", pady=4)

        for row in range(len(fields)):
            form.rowconfigure(row, weight=1 if row in (0, 1, 2) else 0)
        form.columnconfigure(1, weight=1)

        attempts_row = ttk.Frame(content)
        attempts_row.pack(fill="x", pady=(8, 0))
        ttk.Label(attempts_row, text="Automatic attempts").pack(side="left")
        self.scene_contract_attempts_var = tk.StringVar(value="3")
        ttk.Spinbox(
            attempts_row,
            from_=1,
            to=5,
            textvariable=self.scene_contract_attempts_var,
            width=6,
        ).pack(side="left", padx=(8, 12))
        ttk.Label(
            attempts_row,
            text="The validator rejects failed drafts and automatically retries up to this limit.",
        ).pack(side="left")

        action_row = ttk.Frame(content)
        action_row.pack(fill="x", pady=(10, 0))
        ttk.Button(
            action_row,
            text="Apply Contract",
            command=self._apply_scene_contract_from_button,
        ).pack(side="left")
        ttk.Button(
            action_row,
            text="Validate Contract",
            command=self._validate_scene_contract,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            action_row,
            text="Build Writer Direction",
            command=self._build_writer_direction_from_contract,
        ).pack(side="left", padx=(8, 0))
        self.scene_contract_status = ttk.Label(
            action_row,
            text="",
            anchor="w",
        )
        self.scene_contract_status.pack(side="left", fill="x", expand=True, padx=(12, 0))

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
        self._scroll_canvases.append(canvas)
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

        manuscript_button_row = ttk.Frame(left)
        manuscript_button_row.pack(fill="x", pady=(0, 8))

        ttk.Button(
            manuscript_button_row,
            text="Refresh Manuscript",
            command=self._refresh_manuscript,
        ).pack(fill="x")

        ttk.Button(
            manuscript_button_row,
            text="Finalize Chapter",
            command=self._finalize_current_chapter,
        ).pack(fill="x", pady=(6, 0))

        ttk.Button(
            manuscript_button_row,
            text="Assemble Chapter",
            command=self._assemble_current_chapter,
        ).pack(fill="x", pady=(6, 0))

        ttk.Button(
            manuscript_button_row,
            text="Assemble Entire Novel",
            command=self._assemble_entire_novel,
        ).pack(fill="x", pady=(6, 0))

        self.manuscript_list = tk.Listbox(
            left,
            width=34,
            height=22,
            exportselection=False,
        )
        self.manuscript_list.pack(fill="both", expand=True)
        self.manuscript_list.bind(
            "<<ListboxSelect>>",
            self._select_manuscript_scene,
        )

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

        state = self.package.current_state
        scene_cast_names = [
            str(name).strip()
            for name in state.get("scene_cast", [])
            if str(name).strip()
        ]
        scene_cast = {name.casefold() for name in scene_cast_names}

        files = []

        # Keep the persistent writer context compact. The model only needs
        # the current scene state, the cards for characters actually present,
        # and relationships that matter to those characters.
        location = state.get("location", "")
        primary_location = (
            str(location.get("primary", "") or "").strip()
            if isinstance(location, dict)
            else str(location or "").strip()
        )
        time_data = state.get("time", state.get("time_of_day", ""))
        scene_state = {
            "chapter": int(state.get("chapter", 1) or 1),
            "scene": int(state.get("scene", 1) or 1),
            "location": primary_location,
            "time": time_data,
            "cast": scene_cast_names,
            "current_situation": str(state.get("current_situation", "") or "").strip(),
        }
        files.append((
            "scene_state.json",
            json.dumps(scene_state, indent=2, ensure_ascii=False),
        ))

        # Do not send shared recent-event or clue lists into the writer context.
        # Those records may describe events witnessed by one character but not known
        # by another character in the current scene. Character knowledge is supplied
        # separately and is the authoritative information boundary.

        # Physical state is persisted separately from the prose so the writer
        # can preserve exact starting positions, posture, contact, and movement
        # across scene boundaries without requiring the author to restate them
        # in every scene direction.
        physical_state = state.get("physical_state", {})
        scene_physical_state = {}
        if isinstance(physical_state, dict):
            for name in scene_cast_names:
                values = physical_state.get(name)
                if values is None:
                    for key, candidate in physical_state.items():
                        if str(key).casefold() == name.casefold():
                            values = candidate
                            break
                if isinstance(values, dict):
                    scene_physical_state[name] = values
        files.append((
            "scene_physical_state.json",
            json.dumps(scene_physical_state, indent=2, ensure_ascii=False),
        ))

        # Character knowledge is separate from the shared world state. This
        # prevents one character from inheriting facts that only another
        # character has learned.
        character_knowledge = state.get("character_knowledge", {})
        scene_knowledge = {}
        if isinstance(character_knowledge, dict):
            for name in scene_cast_names:
                values = character_knowledge.get(name)
                if values is None:
                    for key, candidate in character_knowledge.items():
                        if str(key).casefold() == name.casefold():
                            values = candidate
                            break
                if isinstance(values, list):
                    scene_knowledge[name] = [
                        str(item).strip()
                        for item in values
                        if str(item).strip()
                    ]
                elif isinstance(values, str) and values.strip():
                    scene_knowledge[name] = [values.strip()]
        files.append((
            "scene_character_knowledge.json",
            json.dumps(scene_knowledge, indent=2, ensure_ascii=False),
        ))

        scene_characters = {}
        for filename in sorted(self.package.characters):
            data = self.package.characters[filename]
            name = str(data.get("name", "") or "").strip()
            filename_stem = Path(filename).stem.strip()
            if name.casefold() not in scene_cast and filename_stem.casefold() not in scene_cast:
                continue
            scene_characters[name or filename_stem] = data

        if scene_characters:
            files.append((
                "scene_characters.json",
                json.dumps(scene_characters, indent=2, ensure_ascii=False),
            ))

        # Include canon cards for named people who are explicitly present in
        # the scene state but are not part of the scene cast. This gives the
        # writer enough information to reference an off-scene person accurately
        # without bringing that person into the scene.
        offscene_characters = {}
        location_data = state.get("location", {})
        if isinstance(location_data, dict):
            referenced_names = {
                str(name).casefold()
                for name in location_data
                if name != "primary"
            }
            for filename in sorted(self.package.characters):
                data = self.package.characters[filename]
                name = str(data.get("name", "") or "").strip()
                filename_stem = Path(filename).stem.strip()
                if (
                    name
                    and name.casefold() in referenced_names
                    and name.casefold() not in scene_cast
                ) or (
                    filename_stem.casefold() in referenced_names
                    and filename_stem.casefold() not in scene_cast
                ):
                    offscene_characters[name or filename_stem] = data

        if offscene_characters:
            files.append((
                "offscene_canon_characters.json",
                json.dumps(offscene_characters, indent=2, ensure_ascii=False),
            ))

        relationships = self.package.story_bible.get("relationships", {})
        if isinstance(relationships, dict):
            relevant = {}
            for key, value in relationships.items():
                if not isinstance(value, dict):
                    continue
                key_text = str(key).casefold()
                if any(name in key_text for name in scene_cast):
                    relevant[key] = value
            if relevant:
                files.append((
                    "scene_relationships.json",
                    json.dumps(relevant, indent=2, ensure_ascii=False),
                ))

        # Do not place recent manuscript prose or active module plans into the
        # persistent system prompt. Those belong in the per-scene direction
        # and short continuation handoff.
        return files

    def _story_interview_questions(self):
        mode = self.interview_mode_var.get().strip()
        if mode == "Relationship":
            return RELATIONSHIP_QUESTIONS
        if mode == "Location":
            return LOCATION_QUESTIONS
        return CHARACTER_QUESTIONS

    def _interview_targets(self, mode):
        if self.package is None:
            return []

        if mode == "Character":
            return sorted(self.package.characters)

        if mode == "Location":
            locations = self.package.story_bible.get("locations", {})
            if not isinstance(locations, dict):
                return []
            return sorted(
                str(key)
                for key in locations
                if str(key).strip()
            )

        relationships = self.package.story_bible.get("relationships", {})
        targets = []
        if isinstance(relationships, dict):
            targets.extend(
                str(key)
                for key in relationships
                if str(key).strip()
            )

        names = []
        for filename, data in self.package.characters.items():
            name = str(data.get("name", "") or "").strip()
            if name:
                names.append((name, filename))

        existing = {"-".join(part.strip() for part in str(pair).split("-", 2)) for pair in targets}
        for index, (left_name, _left_file) in enumerate(names):
            for right_name, _right_file in names[index + 1:]:
                pair = f"{left_name}-{right_name}"
                if pair not in existing:
                    targets.append(pair)
        return sorted(set(targets), key=str.casefold)

    def _refresh_interview_targets(self, reset=True):
        if not hasattr(self, "interview_target_combo"):
            return

        mode = self.interview_mode_var.get().strip() or "Character"
        values = self._interview_targets(mode)
        current = self.interview_target_var.get().strip()

        self.interview_target_combo["values"] = values
        if values:
            if not reset and current in values:
                self.interview_target_var.set(current)
            else:
                self.interview_target_var.set(values[0])
            self._start_story_interview(reset=reset)
        else:
            self.interview_target_var.set("")
            self.interview_active = False
            self.interview_index = 0
            self.interview_pending_patch = None
            self.interview_question_label.configure(text="No targets exist for this interview type yet.")
            self.interview_prompt_label.configure(text="Create the first item in the appropriate tab, then return here.")
            self._clear_interview_proposal()
            self._update_story_interview_buttons()

    def _start_story_interview(self, reset=True):
        if self.package is None or not hasattr(self, "interview_question_label"):
            return

        if reset or not getattr(self, "interview_active", False):
            self.interview_index = 0

        target = self.interview_target_var.get().strip()
        if not target:
            self.interview_active = False
            self._update_story_interview_buttons()
            return

        self.interview_active = True
        self.interview_pending_patch = None
        self.interview_pending_answer = ""
        self._clear_interview_proposal()
        self._show_story_interview_question()

    def _show_story_interview_question(self):
        questions = self._story_interview_questions()
        if not questions:
            return

        if self.interview_index >= len(questions):
            self.interview_active = False
            self.interview_question_label.configure(text="Interview complete.")
            self.interview_prompt_label.configure(
                text="All questions in this interview have been covered. Save the novel to write the approved changes to disk."
            )
            self._update_story_interview_buttons()
            return

        title, prompt, _kind = questions[self.interview_index]
        target = self.interview_target_var.get().strip()
        display_target = target

        if self.interview_mode_var.get() == "Character" and self.package:
            data = self.package.characters.get(target, {})
            display_target = str(data.get("name", "") or target)

        self.interview_question_label.configure(
            text=(
                f"{display_target}  •  {title}  "
                f"({self.interview_index + 1} of {len(questions)})"
            )
        )
        self.interview_prompt_label.configure(text=prompt)
        self.interview_answer_text.delete("1.0", "end")
        self._update_story_interview_buttons()

    def _current_story_interview_data(self):
        if self.package is None:
            return {}

        mode = self.interview_mode_var.get().strip()
        target = self.interview_target_var.get().strip()

        if mode == "Character":
            return {
                "character_file": target,
                "character": self.package.characters.get(target, {}),
            }

        if mode == "Location":
            locations = self.package.story_bible.get("locations", {})
            return {
                "location_id": target,
                "location": locations.get(target, ""),
            }

        relationships = self.package.story_bible.get("relationships", {})
        pair_value = relationships.get(target, "") if isinstance(relationships, dict) else ""

        names = [part.strip() for part in target.split("-", 1)]
        characters = {}
        if len(names) == 2:
            wanted = {name.casefold() for name in names}
            for filename, data in self.package.characters.items():
                name = str(data.get("name", "") or "").strip()
                if name.casefold() in wanted:
                    characters[filename] = data

        return {
            "relationship_key": target,
            "relationship": pair_value,
            "characters": characters,
        }

    def _process_story_interview_answer(self):
        if not self.interview_active or self.interview_pending_patch is not None:
            return

        questions = self._story_interview_questions()
        if self.interview_index >= len(questions):
            return

        title, prompt, kind = questions[self.interview_index]
        answer = self.interview_answer_text.get("1.0", "end-1c").strip()
        if not answer:
            messagebox.showwarning("Story Interview", "Give an answer, or click Skip.")
            return

        if kind == "age":
            try:
                age = int(answer)
            except ValueError:
                messagebox.showerror("Story Interview", "Age must be a whole number, or click Skip.")
                return
            if age < 0:
                messagebox.showerror("Story Interview", "Age cannot be negative.")
                return

            target = self.interview_target_var.get().strip()
            character = self.package.characters.get(target) if self.package else None
            if character is None:
                return
            character["age"] = age
            self.dirty = True
            self._refresh_all()
            self._chat("Builder", f"Interview updated {character.get('name', target)}'s age to {age}.")
            self._advance_story_interview()
            return

        writer_running = (
            self.writer_engine.child is not None
            and self.writer_engine.child.isalive()
        )
        if writer_running:
            messagebox.showwarning(
                "Story Interview",
                "Stop the Writer before using the LLM interview so the laptop does not load two copies of the model at once.",
            )
            return

        model = self.writer_engine.model_path
        if model is None:
            selected = self.writer_model_var.get().strip()
            if not selected:
                messagebox.showerror(
                    "Story Interview",
                    "Select a GGUF model in the Writer tab first.",
                )
                return
            try:
                model = WriterEngine.validate_model(selected)
            except Exception as exc:
                messagebox.showerror("Story Interview", str(exc))
                return

        self.interview_process_button.configure(state="disabled")
        self.interview_status.configure(text="The local LLM is structuring your answer. It will not change canon yet.")

        mode_map = {
            "Character": "character",
            "Relationship": "relationship",
            "Location": "location",
        }
        target_kind = mode_map.get(self.interview_mode_var.get().strip(), "character")
        target = self.interview_target_var.get().strip()
        existing = self._current_story_interview_data()

        def work():
            try:
                patch = structure_answer(
                    model,
                    target_kind=target_kind,
                    target_name=target,
                    question=prompt,
                    answer=answer,
                    existing_data=existing,
                )
                error = None
            except Exception as exc:
                patch = None
                error = str(exc)

            self.after(
                0,
                lambda patch=patch, error=error: self._finish_story_interview_structure(
                    patch, error, answer
                ),
            )

        self.writer_thread = threading.Thread(target=work, daemon=True)
        self.writer_thread.start()

    def _finish_story_interview_structure(self, patch, error, answer):
        if error:
            messagebox.showerror("Story Interview", error)
            self.interview_status.configure(text="The answer was not applied.")
            self._update_story_interview_buttons()
            return

        if not isinstance(patch, dict) or not patch:
            messagebox.showinfo(
                "Story Interview",
                "The local LLM could not find a safe structured change in that answer. Nothing was changed.",
            )
            self.interview_status.configure(
                text="No change proposed. You can reword the answer or skip the question."
            )
            self._update_story_interview_buttons()
            return

        self.interview_pending_patch = patch
        self.interview_pending_answer = answer
        self._set_interview_proposal(patch)
        self.interview_status.configure(
            text="Review the proposed JSON changes. Nothing is canon until you approve them."
        )
        self._update_story_interview_buttons()

    def _approve_story_interview_patch(self):
        patch = self.interview_pending_patch
        if not isinstance(patch, dict) or self.package is None:
            return

        mode_map = {
            "Character": "character",
            "Relationship": "relationship",
            "Location": "location",
        }
        target_kind = mode_map.get(self.interview_mode_var.get().strip(), "character")
        target = self.interview_target_var.get().strip()

        try:
            apply_interview_patch(
                self.package,
                patch,
                target_kind=target_kind,
                target_name=target,
            )
        except Exception as exc:
            messagebox.showerror("Story Interview", str(exc))
            return

        self.dirty = True
        self._refresh_all()
        self._chat("Builder", f"Approved interview changes for {target}.")
        self.interview_pending_patch = None
        self.interview_pending_answer = ""
        self._clear_interview_proposal()
        self._advance_story_interview()

    def _reject_story_interview_patch(self):
        if self.interview_pending_patch is None:
            return
        self.interview_pending_patch = None
        self.interview_pending_answer = ""
        self._clear_interview_proposal()
        self.interview_status.configure(
            text="Proposed changes rejected. Your answer was not applied."
        )
        self.interview_answer_text.delete("1.0", "end")
        self._update_story_interview_buttons()

    def _skip_story_interview_question(self):
        if not self.interview_active or self.interview_pending_patch is not None:
            return
        self.interview_answer_text.delete("1.0", "end")
        self._advance_story_interview()

    def _advance_story_interview(self):
        self.interview_index += 1
        self._clear_interview_proposal()
        self.interview_status.configure(text="Answer accepted into the working novel. Continue when ready.")
        self._show_story_interview_question()

    def _stop_story_interview(self):
        self.interview_active = False
        self.interview_pending_patch = None
        self.interview_pending_answer = ""
        self._clear_interview_proposal()
        self.interview_question_label.configure(text="Interview stopped.")
        self.interview_prompt_label.configure(
            text="Your approved changes remain in the working novel. Save when ready."
        )
        self._update_story_interview_buttons()

    def _set_interview_proposal(self, patch):
        self.interview_proposed_text.configure(state="normal")
        self.interview_proposed_text.delete("1.0", "end")
        self.interview_proposed_text.insert(
            "1.0",
            json.dumps(patch, indent=2, ensure_ascii=False),
        )
        self.interview_proposed_text.configure(state="disabled")

    def _clear_interview_proposal(self):
        if not hasattr(self, "interview_proposed_text"):
            return
        self.interview_proposed_text.configure(state="normal")
        self.interview_proposed_text.delete("1.0", "end")
        self.interview_proposed_text.configure(state="disabled")

    def _update_story_interview_buttons(self):
        if not hasattr(self, "interview_process_button"):
            return

        active = bool(getattr(self, "interview_active", False))
        pending = isinstance(getattr(self, "interview_pending_patch", None), dict)
        has_package = self.package is not None

        self.interview_process_button.configure(
            state="normal" if active and not pending and has_package else "disabled"
        )
        self.interview_skip_button.configure(
            state="normal" if active and not pending else "disabled"
        )
        self.interview_stop_button.configure(
            state="normal" if active else "disabled"
        )
        self.interview_approve_button.configure(
            state="normal" if pending and has_package else "disabled"
        )
        self.interview_reject_button.configure(
            state="normal" if pending else "disabled"
        )

    def _build_scene_direction(self):
        if self.package is None:
            return

        state = self.package.current_state
        chapter = int(state.get("chapter", 1) or 1)
        scene = int(state.get("scene", 1) or 1)
        location = state.get("location", "")
        time_data = state.get("time", state.get("time_of_day", ""))
        cast = [str(name) for name in state.get("scene_cast", []) if str(name).strip()]
        situation = str(state.get("current_situation", "") or "").strip()

        if isinstance(location, dict):
            primary_location = str(location.get("primary", "") or "").strip()
        else:
            primary_location = str(location or "").strip()

        if isinstance(time_data, dict):
            time_text = str(time_data.get("period", "") or "").strip()
            exact = str(time_data.get("exact_time", "") or "").strip()
            if exact and exact != "not established":
                time_text = f"{time_text} ({exact})"
        else:
            time_text = str(time_data or "").strip()

        lines = [
            f"CHAPTER {chapter}, SCENE {scene}",
            f"Location: {primary_location or 'not established'}",
            f"Time: {time_text or 'not established'}",
            "Cast: " + ", ".join(cast),
            f"Current state: {situation or 'continue from the exact current state.'}",
            "Starting-state rule: The current situation above has already happened before this scene begins. Do not replay completed revelations or make characters rediscover facts explicitly stated there.",
            "Starting-knowledge rule: When the current situation says one character has already told, informed, warned, shown, or communicated a fact to another, the receiving character already knows that fact and dialogue should reflect that knowledge.",
        ]

        # Physical state is the automatic handoff from the previous accepted
        # scene. Show only current-scene characters so unrelated positions do
        # not leak into the direction.
        physical_state = state.get("physical_state", {})
        if isinstance(physical_state, dict):
            physical_lines = []
            for name in cast:
                values = physical_state.get(name)
                if values is None:
                    for key, candidate in physical_state.items():
                        if str(key).casefold() == name.casefold():
                            values = candidate
                            break
                if not isinstance(values, dict):
                    values = {}

                details = []
                for key in ("location", "position", "posture", "contact", "movement"):
                    value = str(values.get(key, "") or "").strip()
                    if value:
                        details.append(f"{key}: {value}")
                if details:
                    physical_lines.append(f"{name}: " + "; ".join(details))

            if physical_lines:
                lines.append("Physical continuity:\n" + "\n".join(physical_lines))

        # Current situation defines where the scene starts. The current scene
        # plan defines what should happen from that starting point. Keep both:
        # suppressing the plan when a situation exists hides the actual scene
        # action and leaves the writer with only a starting-state description.
        current_plan_end = None
        plan = self.package.extra_json.get("writing_guidance.json")
        if isinstance(plan, dict):
            guidance = self._chapter_scene_guidance(plan, chapter, scene)
            if isinstance(guidance, dict):
                current_plan_end = str(
                    guidance.get("end_condition", "") or ""
                ).strip()
                direction = str(guidance.get("direction", "") or "").strip()
                pacing = str(guidance.get("pacing", "") or "").strip()
                if direction:
                    lines.append(f"Scene direction: {direction}")
                if pacing:
                    lines.append(f"Pacing: {pacing}")
                scene_contract = guidance.get("scene_contract", {})
                if isinstance(scene_contract, dict) and scene_contract:
                    required = scene_contract.get("required_beats", [])
                    forbidden = scene_contract.get("forbidden", [])
                    if isinstance(required, list) and required:
                        lines.append("Required story beats: " + " | ".join(
                            str(item).strip() for item in required if str(item).strip()
                        ))
                    if isinstance(forbidden, list) and forbidden:
                        lines.append("Do not: " + " | ".join(
                            str(item).strip() for item in forbidden if str(item).strip()
                        ))

        module_endings = []
        module_beats = []
        module_do_not = []

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
            guidance = scene_guidance.get(str(scene)) if isinstance(scene_guidance, dict) else None
            if guidance is None and isinstance(scene_guidance, dict):
                guidance = scene_guidance.get(scene)
            if not isinstance(guidance, dict):
                continue

            module_end = str(guidance.get("end_condition", "") or "").strip()
            if module_end:
                module_endings.append(module_end)

            if not situation and not current_plan_end:
                events = guidance.get("required_events", [])
                for event in events if isinstance(events, list) else []:
                    event_text = str(event).strip()
                    if event_text:
                        module_beats.append(event_text)

                no_advance = guidance.get("do_not_advance", [])
                if isinstance(no_advance, list):
                    for item in no_advance:
                        item_text = str(item).strip()
                        if item_text:
                            module_do_not.append(item_text)

        # Prefer one authoritative endpoint. The recurring scene plan and
        # active module often express the same boundary in different words;
        # showing both only makes the compact direction noisier and can look
        # like two separate requirements to the model.
        end_texts = []
        if current_plan_end:
            end_texts.append(current_plan_end)
        elif module_endings:
            end_texts.append(module_endings[0])
        seen_endings = set()
        for end_text in end_texts:
            key = " ".join(end_text.casefold().split())
            if key in seen_endings:
                continue
            seen_endings.add(key)
            lines.append(f"End: {end_text}")

        if module_beats:
            lines.append("Beats: " + " | ".join(module_beats))
        if module_do_not:
            lines.append("Do not: " + " | ".join(module_do_not))

        lines.append(
            "Write natural prose only. Current state and this scene direction are authoritative."
        )

        self.writer_direction_text.delete("1.0", "end")
        self.writer_direction_text.insert("1.0", "\n".join(lines))
        self.writer_status.configure(text="Scene direction built from the current state and active plan.")

    def _writer_system_prompt(self, files):
        base = """You write natural prose for an ongoing fictional novel.

Rules:
1. Current scene state and scene direction are authoritative.
2. The current_situation in scene_state.json is the exact narrative and physical starting point for this scene. Treat statements that are already completed there as already true before writing begins. Do not replay them as new events.
3. Treat explicit knowledge transfers already completed in current_situation as established knowledge at scene start. If it says one character has told, informed, warned, shown, or otherwise communicated a fact to another character, the receiving character already knows that fact.
4. Never make a character discover, ask whether, or react as though new something that the current_situation explicitly says they already know. They may ask for clarification or additional details that have not yet been established.
5. A character only knows what that character has established or naturally learns. Never transfer another character's knowledge. When character_knowledge and current_situation appear to conflict, the explicit completed event in current_situation is the newer scene-start fact and controls the opening of the scene.
6. Begin from the exact physical and narrative starting state provided. Do not replay the previous scene.
7. Follow the scene direction in order and complete its requested actions before reaching its ending.
8. Let characters make their own choices when the scene gives them a choice.
9. Write believable dialogue, actions, emotions, and ordinary interaction. Show feelings through the scene instead of repeatedly explaining them.
10. Prefer dramatization over summary. Let characters reveal personality, relationships, emotions, shared history, and decisions through dialogue, actions, reactions, and interaction whenever practical. Use narration to support the scene rather than repeatedly summarizing what the characters said, did, or felt. Do not force dialogue into moments that naturally call for quiet observation, internal thought, or description.
11. When an off-scene character is mentioned or referenced, use the supplied off-scene canon reference and current scene state to preserve established routines, family roles, schedules, and other known facts. Do not invent a different routine or explanation for why that person is where they are. Do not pull an off-scene character into the scene unless the current state or scene direction explicitly does so.
12. Do not invent consequential facts, motives, future events, hidden knowledge, or unnecessary story details.
11. Respect privacy, dignity, and established character boundaries.
12. Do not use childlike nicknames for established adult characters unless that nickname is explicitly established.
13. Respect the scene endpoint exactly. Do not stop early or continue past it.
14. Output only natural story prose.
"""
        parts = [base, "\nSCENE REFERENCE\n"]
        for name, content in files:
            parts.append(f"\n[{name}]\n{content}\n")
        parts.append("\nEND SCENE REFERENCE")
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
        try:
            contract = self._scene_contract(chapter, scene)
            if contract:
                lint_errors = SceneContract.lint(contract)
                if lint_errors:
                    raise ValueError(
                        "Invalid scene contract:\n- " + "\n- ".join(lint_errors)
                    )
        except (TypeError, ValueError) as exc:
            messagebox.showerror("Scene Contract", str(exc))
            self._update_writer_buttons()
            return

        current_state = json.loads(
            json.dumps(self.package.current_state, ensure_ascii=False)
        )

        # Rebuild the writer context before every scene attempt. The writer
        # should never carry a previous scene's conversational memory into a
        # new scene.
        files = self._writer_package_files()
        system_prompt = self._writer_system_prompt(files)
        model = self.writer_engine.model_path

        prompt_parts = [
            "AUTHOR DIRECTION:\n",
            direction,
            "\n\n",
        ]

        if contract:
            prompt_parts.extend([
                "AUTHORITATIVE SCENE CONTRACT:\n",
                json.dumps(contract, indent=2, ensure_ascii=False),
                "\n\n",
            ])

        prompt_parts.extend([
            "IMPORTANT SCENE BOUNDARY:\n",
            "The scene contract and current story state are authoritative. "
            "Do not replay the previous scene. Do not reveal information to a character before that "
            "character naturally learns it in this scene. Do not invent consequential facts. "
            "Complete the required beats and reach the contract's ending without adding a different plot. "
            "Creative variation is allowed in dialogue, wording, gestures, emotions, ordinary interaction, "
            "and other harmless details.\n\n"
            "Write the scene now. Output only the prose."
        ])
        base_prompt = "".join(prompt_parts)

        def work():
            try:
                if model is None:
                    raise RuntimeError("The Writer model is not available.")

                max_attempts = SceneContract.max_attempts(contract) if contract else 1
                feedback = ""
                answer = ""

                # Start one fresh writer session for the scene. A retry only
                # restarts the writer after a failed validation, avoiding an
                # unnecessary model reload before the first attempt.
                self.writer_engine.reset_context(model, system_prompt)

                for attempt in range(1, max_attempts + 1):
                    attempt_prompt = base_prompt
                    if feedback:
                        attempt_prompt += "\n\n" + feedback + "\n"
                    answer = self.writer_engine.generate(attempt_prompt)

                    if not contract:
                        break

                    result = SceneContract.validate_with_engine(
                        self.writer_engine,
                        contract,
                        current_state,
                        answer,
                    )
                    if result.get("pass"):
                        break

                    feedback = SceneContract.feedback(result)
                    if attempt == max_attempts:
                        raise RuntimeError(
                            "The writer could not produce a scene that satisfies the scene contract "
                            f"after {max_attempts} attempts.\n\n{feedback}"
                        )

                    # Only rejected drafts need a brand-new writer context.
                    # This keeps retry feedback from accumulating prior prose.
                    self.writer_engine.reset_context(model, system_prompt)

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


    def _editable_scene_guidance_entry(
        self,
        chapter: int,
        scene: int,
        create: bool = False,
    ) -> dict | None:
        """Return the author-owned guidance entry without merging active modules."""
        if not self.package:
            return None

        plan = self.package.extra_json.get("writing_guidance.json")
        if not isinstance(plan, dict):
            if not create:
                return None
            plan = {
                "purpose": "Author-defined scene direction and reusable scene contracts."
            }
            self.package.extra_json["writing_guidance.json"] = plan

        chapter_plans = plan.get("chapter_plans")
        if isinstance(chapter_plans, dict):
            chapter_entry = chapter_plans.get(str(chapter))
            if chapter_entry is None:
                chapter_entry = chapter_plans.get(chapter)
            if isinstance(chapter_entry, dict):
                scene_plan = chapter_entry.get("scene_plan")
                if not isinstance(scene_plan, dict):
                    if not create:
                        return None
                    scene_plan = {}
                    chapter_entry["scene_plan"] = scene_plan
                entry = scene_plan.get(str(scene))
                if entry is None:
                    entry = scene_plan.get(scene)
                if isinstance(entry, dict):
                    return entry
                if create:
                    entry = {}
                    scene_plan[str(scene)] = entry
                    return entry
                return None

        # Preserve the legacy Chapter 1 layout already used by current novels.
        if chapter == 1 and isinstance(plan.get("scene_plan"), dict):
            scene_plan = plan["scene_plan"]
            entry = scene_plan.get(str(scene))
            if entry is None:
                entry = scene_plan.get(scene)
            if isinstance(entry, dict):
                return entry
            if create:
                entry = {}
                scene_plan[str(scene)] = entry
                return entry
            return None

        if not create:
            return None

        chapter_plans = plan.setdefault("chapter_plans", {})
        chapter_entry = chapter_plans.setdefault(str(chapter), {})
        scene_plan = chapter_entry.setdefault("scene_plan", {})
        return scene_plan.setdefault(str(scene), {})

    def _scene_contract_start_summary(self) -> str:
        if not self.package:
            return ""

        state = self.package.current_state
        location = state.get("location", "")
        if isinstance(location, dict):
            location_text = str(location.get("primary", "") or "").strip()
        else:
            location_text = str(location or "").strip()

        time_data = state.get("time", state.get("time_of_day", ""))
        if isinstance(time_data, dict):
            time_text = str(time_data.get("period", "") or "").strip()
            exact = str(time_data.get("exact_time", "") or "").strip()
            if exact and exact != "not established":
                time_text = f"{time_text} ({exact})"
        else:
            time_text = str(time_data or "").strip()

        cast = [
            str(name).strip()
            for name in state.get("scene_cast", [])
            if str(name).strip()
        ]
        situation = str(state.get("current_situation", "") or "").strip()

        lines = [
            f"Chapter: {int(state.get('chapter', 1) or 1)}",
            f"Scene: {int(state.get('scene', 1) or 1)}",
            f"Location: {location_text or 'not established'}",
            f"Time: {time_text or 'not established'}",
            "Cast: " + (", ".join(cast) if cast else "not established"),
            f"Current situation: {situation or 'not established'}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _contract_list(contract: dict, key: str) -> list[str]:
        value = contract.get(key, [])
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _refresh_scene_contract_editor(self):
        if not hasattr(self, "scene_contract_start_text") or self.package is None:
            return

        chapter = int(self.package.current_state.get("chapter", 1) or 1)
        scene = int(self.package.current_state.get("scene", 1) or 1)
        self.scene_contract_scene_label.configure(
            text=f"Chapter {chapter}, Scene {scene}"
        )

        start = self._scene_contract_start_summary()
        self.scene_contract_start_text.configure(state="normal")
        self.scene_contract_start_text.delete("1.0", "end")
        self.scene_contract_start_text.insert("1.0", start)
        self.scene_contract_start_text.configure(state="disabled")

        entry = self._editable_scene_guidance_entry(chapter, scene, create=False) or {}
        contract_error = None
        try:
            contract = SceneContract.from_guidance(entry, [])
        except (TypeError, ValueError) as exc:
            contract = {}
            contract_error = str(exc)

        self.scene_contract_direction_text.delete("1.0", "end")
        self.scene_contract_direction_text.insert(
            "1.0",
            str(entry.get("direction", "") or ""),
        )

        self.scene_contract_end_text.delete("1.0", "end")
        self.scene_contract_end_text.insert(
            "1.0",
            str(contract.get("hard_stop") or entry.get("end_condition") or ""),
        )

        for key, widget in self.scene_contract_texts.items():
            widget.delete("1.0", "end")
            widget.insert(
                "1.0",
                "\n".join(self._contract_list(contract, key)),
            )

        attempts = contract.get("max_attempts", 3)
        self.scene_contract_attempts_var.set(str(attempts))
        if contract_error:
            self.scene_contract_status.configure(
                text=f"Contract needs attention: {contract_error}",
            )
        else:
            self.scene_contract_status.configure(
                text="Loaded author contract for the current scene.",
            )

    def _collect_scene_contract_editor(self) -> tuple[str, str, dict]:
        if self.package is None or not hasattr(self, "scene_contract_direction_text"):
            raise ValueError("Scene contract editor is not available.")

        direction = self.scene_contract_direction_text.get("1.0", "end-1c").strip()
        end_text = self.scene_contract_end_text.get("1.0", "end-1c").strip()

        contract = {}
        for key, widget in self.scene_contract_texts.items():
            values = self._lines(widget)
            if values:
                contract[key] = values

        raw_attempts = self.scene_contract_attempts_var.get().strip()
        if raw_attempts:
            try:
                attempts = int(raw_attempts)
            except ValueError as exc:
                raise ValueError(
                    "Automatic attempts must be an integer from 1 to 5."
                ) from exc
        else:
            attempts = 3

        contract["max_attempts"] = attempts
        if end_text:
            contract["hard_stop"] = end_text

        SceneContract.validate_shape(contract)
        lint_errors = SceneContract.lint(contract)
        if lint_errors:
            raise ValueError(
                "Invalid scene contract:\n- " + "\n- ".join(lint_errors)
            )

        return direction, end_text, contract

    def _validate_scene_contract(self):
        if self.package is None:
            return

        chapter = int(self.package.current_state.get("chapter", 1) or 1)
        scene = int(self.package.current_state.get("scene", 1) or 1)

        try:
            _direction, end_text, contract = self._collect_scene_contract_editor()
        except (TypeError, ValueError) as exc:
            self.scene_contract_status.configure(text="Contract invalid.")
            messagebox.showerror("Scene Contract", str(exc))
            return

        self.scene_contract_status.configure(
            text="Current editor contents are structurally valid.",
        )
        messagebox.showinfo(
            "Scene Contract",
            (
                f"Chapter {chapter}, Scene {scene} contract is valid.\n\n"
                f"Required beats: {len(contract.get('required_beats', []))}\n"
                f"Required facts: {len(contract.get('required_facts', []))}\n"
                f"Sequence steps: {len(contract.get('required_sequence', []))}\n"
                f"Forbidden rules: {len(contract.get('forbidden', []))}\n"
                f"Ending defined: {'yes' if end_text else 'no'}\n"
                f"Automatic attempts: {SceneContract.max_attempts(contract)}"
            ),
        )

    def _apply_scene_contract_from_button(self):
        try:
            self._apply_scene_contract_edits()
        except (TypeError, ValueError) as exc:
            self.scene_contract_status.configure(text="Contract not saved.")
            messagebox.showerror("Scene Contract", str(exc))

    def _apply_scene_contract_edits(self):
        if self.package is None or not hasattr(self, "scene_contract_direction_text"):
            return

        chapter = int(self.package.current_state.get("chapter", 1) or 1)
        scene = int(self.package.current_state.get("scene", 1) or 1)

        direction, end_text, contract = self._collect_scene_contract_editor()

        entry = self._editable_scene_guidance_entry(chapter, scene, create=True)
        if entry is None:
            raise ValueError("Could not create scene guidance for this scene.")

        if direction:
            entry["direction"] = direction
        else:
            entry.pop("direction", None)

        if end_text:
            entry["end_condition"] = end_text
        else:
            entry.pop("end_condition", None)

        # Store the authored contract only. Active story modules stay outside it
        # and are merged by _scene_contract at generation time.
        entry["scene_contract"] = contract

        self.dirty = True
        self._update_path_label()
        self.scene_contract_status.configure(
            text=f"Saved author contract for Chapter {chapter}, Scene {scene}.",
        )

    def _build_writer_direction_from_contract(self):
        try:
            self._apply_scene_contract_edits()
            self._build_scene_direction()
        except Exception as exc:
            messagebox.showerror("Scene Contract", str(exc))

    @staticmethod
    def _chapter_scene_guidance(
        plan: dict,
        chapter: int,
        scene: int,
    ) -> dict | None:
        """Return guidance for a specific chapter and scene."""
        if not isinstance(plan, dict):
            return None

        chapter_plans = plan.get("chapter_plans", {})
        if isinstance(chapter_plans, dict):
            chapter_entry = chapter_plans.get(str(chapter))
            if chapter_entry is None:
                chapter_entry = chapter_plans.get(chapter)
            if isinstance(chapter_entry, dict):
                scene_plan = chapter_entry.get("scene_plan", {})
                if isinstance(scene_plan, dict):
                    entry = scene_plan.get(str(scene))
                    if entry is None:
                        entry = scene_plan.get(scene)
                    if isinstance(entry, dict):
                        return entry

        # Backward-compatible support for the original Chapter 1 guidance
        # stored directly under scene_plan.
        if chapter == 1:
            scene_plan = plan.get("scene_plan", {})
            if isinstance(scene_plan, dict):
                entry = scene_plan.get(str(scene))
                if entry is None:
                    entry = scene_plan.get(scene)
                if isinstance(entry, dict):
                    return entry

        return None

    def _scene_plan_cast(self, chapter: int, scene: int) -> list[str]:
        """Return the explicitly defined cast for a planned scene."""
        try:
            guidance = self.package.extra_json.get("writing_guidance.json", {}) if self.package else {}
            entry = self._chapter_scene_guidance(guidance, chapter, scene) or {}
            if not isinstance(entry, dict):
                return []
            cast = entry.get("cast", [])
            if not isinstance(cast, list):
                return []
            return [str(name).strip() for name in cast if str(name).strip()]
        except Exception:
            return []

    def _scene_end_guidance(self, chapter: int, scene: int) -> str:
        """Return the saved end condition and optional expected ending state."""
        try:
            guidance = self.package.extra_json.get("writing_guidance.json", {}) if self.package else {}
            entry = self._chapter_scene_guidance(guidance, chapter, scene) or {}
            if not isinstance(entry, dict):
                return ""

            parts = []
            end_condition = str(entry.get("end_condition", "") or "").strip()
            if end_condition:
                parts.append("END CONDITION:\n" + end_condition)

            state_after = entry.get("state_after")
            if isinstance(state_after, dict):
                parts.append(
                    "EXPECTED END STATE HINT (VERIFY AGAINST THE COMPLETED PROSE):\n"
                    + json.dumps(state_after, indent=2, ensure_ascii=False)
                )

            return "\n\n".join(parts)
        except Exception:
            return ""

    def _scene_contract(self, chapter: int, scene: int) -> dict:
        """Build the reusable contract for the current scene.

        Explicit scene_contract data remains authoritative, while legacy
        end_condition/required_events/do_not_advance fields and active module
        guidance are folded in automatically.
        """
        if not self.package:
            return {}

        guidance = self.package.extra_json.get("writing_guidance.json", {})
        entry = self._chapter_scene_guidance(guidance, chapter, scene) or {}
        if not isinstance(entry, dict):
            entry = {}

        module_guidance = []
        modules = self.package.story_bible.get("optional_story_modules", [])
        if isinstance(modules, list):
            for module in modules:
                if not isinstance(module, dict):
                    continue
                if str(module.get("status", "")).casefold() != "active":
                    continue
                filename = str(module.get("file", "") or "").strip()
                if not filename:
                    continue
                data = self.package.extra_json.get(filename, {})
                if not isinstance(data, dict):
                    continue
                scene_guidance = data.get("scene_guidance", {})
                if not isinstance(scene_guidance, dict):
                    continue
                module_entry = scene_guidance.get(str(scene))
                if module_entry is None:
                    module_entry = scene_guidance.get(scene)
                if isinstance(module_entry, dict):
                    module_guidance.append(module_entry)

        return SceneContract.from_guidance(entry, module_guidance)


    def _analyze_accepted_scene(self):
        if not self.package or not self.accepted_scene.strip():
            return

        current_state = dict(self.package.current_state)
        story_text = self.accepted_scene
        completed_chapter = int(current_state.get("chapter", 1) or 1)
        completed_scene = int(current_state.get("scene", 1) or 1)
        contract = self._scene_contract(completed_chapter, completed_scene)
        fixed_state_after = contract.get("state_after") if isinstance(contract, dict) else None

        if isinstance(fixed_state_after, dict):
            self.pending_state_patch = json.loads(
                json.dumps(fixed_state_after, ensure_ascii=False)
            )
            self.writer_state_preview.delete("1.0", "end")
            self.writer_state_preview.insert(
                "1.0",
                json.dumps(self.pending_state_patch, indent=2, ensure_ascii=False),
            )
            self.writer_status.configure(
                text="Scene contract state loaded. No AI state reconstruction is needed."
            )
            self._update_writer_buttons()
            return

        if not self.writer_engine.model_path:
            return

        scene_end_guidance = self._scene_end_guidance(completed_chapter, completed_scene)
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
                    scene_end_guidance=scene_end_guidance,
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

            # If this is the final planned scene in the current writing
            # guidance, close the chapter instead of inventing a Scene N+1.
            final_planned_scene = self._final_planned_scene_for_chapter(
                current_chapter
            )
            if final_planned_scene is None:
                final_planned_scene = completed_scene

            if current_chapter == completed_chapter and current_scene == completed_scene:
                if completed_scene >= final_planned_scene:
                    self.package.current_state["scene_completed"] = True
                    self.package.current_state["chapter_completed"] = True
                else:
                    self.package.current_state["scene"] = completed_scene + 1
                    self.package.current_state["scene_completed"] = False
            else:
                # If the continuity manager explicitly advanced the state, keep
                # its chapter/scene decision intact.
                self.package.current_state["scene_completed"] = False

            # When the next scene has an explicit cast in writing guidance,
            # load that cast for the newly advanced scene instead of carrying
            # the completed scene's cast forward.
            if not self.package.current_state.get("chapter_completed"):
                next_scene_cast = self._scene_plan_cast(
                    int(self.package.current_state.get("chapter", completed_chapter) or completed_chapter),
                    int(self.package.current_state.get("scene", completed_scene + 1) or completed_scene + 1),
                )
                if next_scene_cast:
                    self.package.current_state["scene_cast"] = next_scene_cast

            self.dirty = True
            self.pending_state_patch = None
            self.generated_scene = ""
            self.accepted_scene = ""
            self.writer_output_text.delete("1.0", "end")
            self.writer_state_preview.delete("1.0", "end")
            self._refresh_all()
            self._save()
            if self.package.current_state.get("chapter_completed"):
                self._chat(
                    "Builder",
                    f"Chapter {completed_chapter} is complete. Scene {completed_scene} "
                    "was saved as the final scene of the chapter.",
                )
                self.writer_status.configure(
                    text="Chapter complete. Set the next chapter and scene when you are ready to continue."
                )
            else:
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

            chapter = int(self.package.current_state.get("chapter", chapter) or chapter)
            scene_end_guidance = self._scene_end_guidance(chapter, scene)
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
                        scene_end_guidance=scene_end_guidance,
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

    def _manuscript_target_chapter(self) -> int:
        selected = self._selected_manuscript_scene()
        if selected is not None:
            numbers = ManuscriptManager.scene_numbers(selected)
            if numbers is not None:
                return numbers[0]
        if self.package is None:
            return 1
        return int(self.package.current_state.get("chapter", 1) or 1)

    def _final_planned_scene_for_chapter(self, chapter: int) -> int | None:
        if self.package is None:
            return None

        guidance = self.package.extra_json.get("writing_guidance.json", {})
        if not isinstance(guidance, dict):
            return None

        chapter_plans = guidance.get("chapter_plans", {})
        if isinstance(chapter_plans, dict):
            chapter_entry = chapter_plans.get(str(chapter))
            if chapter_entry is None:
                chapter_entry = chapter_plans.get(chapter)
            if isinstance(chapter_entry, dict):
                scene_plan = chapter_entry.get("scene_plan", {})
                if isinstance(scene_plan, dict):
                    planned = []
                    for key in scene_plan:
                        try:
                            planned.append(int(key))
                        except (TypeError, ValueError):
                            continue
                    if planned:
                        return max(planned)

        if chapter == 1:
            scene_plan = guidance.get("scene_plan", {})
            if isinstance(scene_plan, dict):
                planned = []
                for key in scene_plan:
                    try:
                        planned.append(int(key))
                    except (TypeError, ValueError):
                        continue
                if planned:
                    return max(planned)

        return None

    def _finalize_current_chapter(self):
        if self.package is None or self.package.path is None:
            return

        chapter = int(self.package.current_state.get("chapter", 1) or 1)
        scene = int(self.package.current_state.get("scene", 1) or 1)
        manager = ManuscriptManager(self.package.path)
        scene_paths = manager.chapter_scene_paths(chapter)

        if not scene_paths:
            messagebox.showwarning(
                "Finalize Chapter",
                f"No accepted manuscript sections were found for Chapter {chapter}.",
            )
            return

        latest_scene = max(
            numbers[1]
            for path in scene_paths
            if (numbers := ManuscriptManager.scene_numbers(path)) is not None
        )
        planned_final = self._final_planned_scene_for_chapter(chapter)

        if scene < latest_scene:
            messagebox.showwarning(
                "Finalize Chapter",
                f"Current state is on Scene {scene}, but Chapter {chapter} already contains "
                f"accepted material through Scene {latest_scene}. Finalize from the latest scene "
                "after restoring the correct current state.",
            )
            return

        if planned_final is not None and scene < planned_final:
            messagebox.showwarning(
                "Finalize Chapter",
                f"Scene {scene} is not the final planned scene for the current guidance. "
                f"Scene {planned_final} is the final planned scene.",
            )
            return

        if self.package.current_state.get("chapter_completed"):
            messagebox.showinfo(
                "Finalize Chapter",
                f"Chapter {chapter} is already marked complete.",
            )
            return

        if not messagebox.askyesno(
            "Finalize Chapter",
            f"Mark Chapter {chapter}, Scene {scene}, as complete?\n\n"
            "This will not create a new scene or advance to the next chapter.",
        ):
            return

        self.package.current_state["scene_completed"] = True
        self.package.current_state["chapter_completed"] = True
        self.dirty = True
        self._save()
        self._refresh_all()
        self._chat(
            "Builder",
            f"Chapter {chapter} is finalized. Scene {scene} remains the final scene "
            "and the story is ready for the next chapter when you choose to continue.",
        )
        self.manuscript_recovery_status.configure(
            text=f"Chapter {chapter} finalized. It remains at Scene {scene} until the next chapter is started."
        )

    def _assemble_current_chapter(self):
        if self.package is None or self.package.path is None:
            return

        chapter = self._manuscript_target_chapter()
        manager = ManuscriptManager(self.package.path)
        try:
            target = manager.compile_chapter(chapter)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Assemble Chapter", str(exc))
            return

        self.manuscript_recovery_status.configure(
            text=f"Chapter {chapter} assembled to {target.name}.",
        )
        self._chat("Builder", f"Chapter {chapter} assembled to {target.relative_to(self.package.path)}.")

    def _assemble_entire_novel(self):
        if self.package is None or self.package.path is None:
            return

        manager = ManuscriptManager(self.package.path)
        title = str(self.package.story_bible.get("title", "Complete_Novel") or "Complete_Novel").strip()
        try:
            target = manager.compile_novel(title)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Assemble Entire Novel", str(exc))
            return

        self.manuscript_recovery_status.configure(
            text=f"Entire novel assembled to {target.name}.",
        )
        self._chat("Builder", f"Entire novel assembled to {target.relative_to(self.package.path)}.")

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

    def _close_without_sync(self):
        if self._closing:
            return
        self._closing = True

        try:
            try:
                self.writer_engine.stop()
            except Exception:
                pass

            # Save all current editor contents locally, but never run the GitHub sync.
            self._save()
            if self.dirty:
                # Save was cancelled or failed, so do not close and risk losing work.
                self._closing = False
                return

            self.destroy()
        except Exception as exc:
            messagebox.showerror(
                "Close",
                f"The novel was saved locally, but the app could not close cleanly.\n\n{exc}\n\nThe app will remain open."
            )
            self._closing = False

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
        self.interview_active = False
        self.interview_index = 0
        self.interview_pending_patch = None
        self.interview_pending_answer = ""
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
            initialdir=str(NOVEL_ROOT.parent),
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
        self.interview_active = False
        self.interview_index = 0
        self.interview_pending_patch = None
        self.interview_pending_answer = ""
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
        self._apply_scene_contract_edits()
        self._apply_character_edits()
        self._apply_supporting_person_edit()
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
        self.supporting_people_list.selection_clear(0, "end")
        self.supporting_person_text.delete("1.0", "end")
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

    def _refresh_supporting_people(self, select_name=None):
        if not hasattr(self, "supporting_people_list"):
            return

        self.supporting_people_list.delete(0, "end")
        people = self.package.story_bible.get("supporting_people", {}) if self.package else {}
        if not isinstance(people, dict):
            people = {}

        names = sorted(
            (str(name) for name in people if str(name).strip()),
            key=str.casefold,
        )
        selected_index = None

        for index, name in enumerate(names):
            self.supporting_people_list.insert("end", name)
            if name == select_name:
                selected_index = index

        if selected_index is not None:
            self.supporting_people_list.selection_clear(0, "end")
            self.supporting_people_list.selection_set(selected_index)
            self.supporting_people_list.see(selected_index)
            self._select_supporting_person()
        elif not names:
            self.supporting_person_text.delete("1.0", "end")


    def _select_supporting_person(self, _event=None):
        if self.package is None or not hasattr(self, "supporting_people_list"):
            return

        selection = self.supporting_people_list.curselection()
        if not selection:
            return

        people = self.package.story_bible.get("supporting_people", {})
        if not isinstance(people, dict):
            return

        names = sorted(
            (str(name) for name in people if str(name).strip()),
            key=str.casefold,
        )
        index = selection[0]
        if index < 0 or index >= len(names):
            return

        name = names[index]
        self.character_list.selection_clear(0, "end")
        self.character_filename = None

        for var in self.character_vars.values():
            var.set("")
        for widget in self.character_texts.values():
            widget.delete("1.0", "end")

        self.supporting_person_text.delete("1.0", "end")
        self.supporting_person_text.insert(
            "1.0",
            str(people.get(name, "") or ""),
        )


    def _apply_supporting_person_edit(self):
        if self.package is None or not hasattr(self, "supporting_people_list"):
            return

        selection = self.supporting_people_list.curselection()
        if not selection:
            return

        people = self.package.story_bible.setdefault("supporting_people", {})
        if not isinstance(people, dict):
            people = {}
            self.package.story_bible["supporting_people"] = people

        names = sorted(
            (str(name) for name in people if str(name).strip()),
            key=str.casefold,
        )
        index = selection[0]
        if index < 0 or index >= len(names):
            return

        name = names[index]
        value = self.supporting_person_text.get("1.0", "end-1c").strip()
        if value:
            people[name] = value

        self.dirty = True
        self._update_path_label()


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
        if hasattr(self, "scene_contract_start_text"):
            self._refresh_scene_contract_editor()
        if hasattr(self, "interview_target_combo"):
            self._refresh_interview_targets(reset=False)
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
            self.character_list.insert(
                "end",
                self.package.characters[filename].get("name", filename.removesuffix(".json")),
            )
            if filename == select_filename:
                selected_index = index

        if selected_index is not None:
            self.character_list.selection_clear(0, "end")
            self.character_list.selection_set(selected_index)
            self.character_list.see(selected_index)
            self._select_character()

        self._refresh_supporting_people()


    def _refresh_supporting_people(self, select_name=None):
        if not hasattr(self, "supporting_people_list"):
            return

        self.supporting_people_list.delete(0, "end")
        people = self.package.story_bible.get("supporting_people", {}) if self.package else {}
        if not isinstance(people, dict):
            people = {}

        selected_index = None
        for index, name in enumerate(sorted(people, key=str.casefold)):
            self.supporting_people_list.insert("end", name)
            if name == select_name:
                selected_index = index

        if selected_index is not None:
            self.supporting_people_list.selection_clear(0, "end")
            self.supporting_people_list.selection_set(selected_index)
            self.supporting_people_list.see(selected_index)
            self._select_supporting_person()
        elif not selected_index and self.supporting_people_list.size() == 0:
            self.supporting_person_text.delete("1.0", "end")


    def _select_supporting_person(self, _event=None):
        if self.package is None:
            return

        selection = self.supporting_people_list.curselection()
        if not selection:
            return

        people = self.package.story_bible.get("supporting_people", {})
        if not isinstance(people, dict):
            return

        names = sorted(people, key=str.casefold)
        index = selection[0]
        if index < 0 or index >= len(names):
            return

        name = names[index]
        self.character_list.selection_clear(0, "end")
        self.character_filename = None

        for var in self.character_vars.values():
            var.set("")
        for widget in self.character_texts.values():
            widget.delete("1.0", "end")

        self.supporting_person_text.delete("1.0", "end")
        self.supporting_person_text.insert("1.0", str(people.get(name, "") or ""))


    def _apply_supporting_person_edit(self):
        if self.package is None or not hasattr(self, "supporting_people_list"):
            return

        selection = self.supporting_people_list.curselection()
        if not selection:
            return

        people = self.package.story_bible.setdefault("supporting_people", {})
        if not isinstance(people, dict):
            people = {}
            self.package.story_bible["supporting_people"] = people

        names = sorted(people, key=str.casefold)
        index = selection[0]
        if index < 0 or index >= len(names):
            return

        name = names[index]
        value = self.supporting_person_text.get("1.0", "end-1c").strip()
        if value:
            people[name] = value
        else:
            people.pop(name, None)

        self.dirty = True
        self._update_path_label()


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
            self.interview_answer_text,
            self.supporting_person_text,
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
        # Discover every Text and Entry widget so every current and future tab
        # gets the same right-click clipboard behavior.
        widgets = self._find_text_widgets(self)
        widgets.extend(self._find_entry_widgets(self))

        seen = set()
        for widget in widgets:
            widget_id = str(widget)
            if widget_id in seen:
                continue
            seen.add(widget_id)
            self._add_context_menu(widget)

    @staticmethod
    def _find_text_widgets(root):
        widgets = []
        for child in root.winfo_children():
            if isinstance(child, tk.Text):
                widgets.append(child)
            widgets.extend(StoryBuilderApp._find_text_widgets(child))
        return widgets

    @staticmethod
    def _find_entry_widgets(root):
        entries = []
        for child in root.winfo_children():
            if isinstance(child, ttk.Entry):
                entries.append(child)
            entries.extend(StoryBuilderApp._find_entry_widgets(child))
        return entries

    def _install_mousewheel_scrolling(self):
        """Route mouse-wheel input to the widget currently under the pointer."""
        self.bind_all("<MouseWheel>", self._handle_mousewheel, add="+")
        self.bind_all("<Button-4>", self._handle_mousewheel, add="+")
        self.bind_all("<Button-5>", self._handle_mousewheel, add="+")

    @staticmethod
    def _mousewheel_units(event):
        if getattr(event, "num", None) == 4:
            return -3
        if getattr(event, "num", None) == 5:
            return 3

        delta = getattr(event, "delta", 0)
        if delta > 0:
            return -3
        if delta < 0:
            return 3
        return 0

    def _handle_mousewheel(self, event):
        units = self._mousewheel_units(event)
        if not units:
            return

        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except tk.TclError:
            widget = None

        if widget is None:
            return

        # Native entry widgets keep their normal mouse-wheel behavior.
        if isinstance(widget, (ttk.Entry, ttk.Combobox, ttk.Spinbox)):
            return

        # First try the Text/Listbox directly under the pointer.
        target = widget
        while target is not None:
            if isinstance(target, (tk.Text, tk.Listbox)):
                try:
                    before = target.yview()
                    target.yview_scroll(units, "units")
                    after = target.yview()
                    if before != after:
                        return "break"
                except tk.TclError:
                    pass
                break

            if isinstance(target, tk.Canvas):
                try:
                    target.yview_scroll(units, "units")
                    return "break"
                except tk.TclError:
                    return

            try:
                parent_name = target.winfo_parent()
                if not parent_name:
                    break
                target = target.nametowidget(parent_name)
            except (tk.TclError, KeyError, AttributeError):
                break

        # If a text widget is already at an edge, scroll its containing canvas.
        target = widget
        while target is not None:
            if isinstance(target, tk.Canvas):
                try:
                    target.yview_scroll(units, "units")
                    return "break"
                except tk.TclError:
                    return
            try:
                parent_name = target.winfo_parent()
                if not parent_name:
                    break
                target = target.nametowidget(parent_name)
            except (tk.TclError, KeyError, AttributeError):
                break

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
