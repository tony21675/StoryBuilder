from __future__ import annotations

import json
import queue
import re
import shutil
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from builder.appearance import apply_application_appearance
from builder.conversation import apply_command
from builder.guided_setup import GuidedSetupSession
from builder.story_package import StoryPackage
from builder.change_assistant import (
    apply_change_request_patch,
    normalize_change_patch,
    render_change_preview,
    structure_change_request,
)
from builder.new_novel_assistant import (
    apply_new_novel_proposal,
    build_new_novel_proposal,
    is_blank_new_package,
    normalize_new_novel_proposal,
    render_new_novel_preview,
)
from builder.writer_notes import (
    WRITER_NOTES_FILENAME,
    WRITER_NOTES_SYSTEM_PROMPT,
    build_writer_notes_review_prompt,
    collect_recent_accepted_scenes,
    collect_initial_seed_scenes,
    merge_writer_notes,
    normalize_writer_notes,
    parse_writer_notes_response,
    save_writer_notes,
)
from builder.scene_plan import load_scene_idea_from_plan
from builder.scene_planner import (
    generate_scene_planner_reply, prepare_scene_plan_proposal, read_story_plan_file,
    save_scene_plan_file, update_scene_plan_markdown, validate_scene_plan_fields,
)
from builder.validator import validate_package
from builder.writer_engine import WriterEngine
from builder.prompt_trace import PromptTrace, default_prompt_trace_path
from builder.prompt_trace_sync import upload_prompt_trace
from builder.manuscript import ManuscriptManager
from builder.continuity_context import (
    context_size_report,
    estimate_tokens_from_chars,
    select_active_character_knowledge,
    select_relevant_records,
)
from builder.scene_flow import review_chapter_flow
from builder.novel_sync import NovelSyncError, sync_novel_repository
from builder.state_manager import (
    StateManager,
    build_state_change_summary,
    combine_state_patches,
    remove_prior_chapter_opening_markers,
    reviewed_state_preview_to_patch,
)
from builder.scene_contract import SceneContract, extract_scene_header_metadata
from builder.focused_revision import (
    FOCUSED_REVISION_SYSTEM_PROMPT,
    apply_focused_replacement,
    build_focused_revision_prompt,
)
from builder.scene_completion import generate_scene_with_completion_check
from builder.story_interview import (
    CHARACTER_QUESTIONS,
    RELATIONSHIP_QUESTIONS,
    LOCATION_QUESTIONS,
    apply_interview_patch,
    structure_answer,
)
from builder.workspace import NOVEL_ROOT, WORKSPACE_ROOT, find_novel_packages


class CompactTabContainer(ttk.Frame):
    """Notebook-style page container with a compact dropdown navigator.

    ttk.Notebook keeps all tabs in one horizontal strip, which can run off
    narrower laptop screens. This container preserves the existing add(page,
    text=...) interface while showing one page at a time through a dropdown.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._page_labels = []
        self._pages_by_label = {}
        self._selected_label = None
        self.on_show = None
        self._section_var = tk.StringVar(self)

        navigation = ttk.Frame(self)
        navigation.pack(fill="x", pady=(0, 6))
        ttk.Label(navigation, text="Go to section:").pack(side="left", padx=(0, 8))
        self.selector = ttk.Combobox(
            navigation,
            textvariable=self._section_var,
            state="readonly",
            width=26,
        )
        self.selector.pack(side="left", fill="x", expand=True)
        self.selector.bind("<<ComboboxSelected>>", self._on_section_selected)

        self.pages = ttk.Frame(self)
        self.pages.pack(fill="both", expand=True)

    def add(self, page, text):
        """Register a page and make the first registered page visible."""
        if text in self._pages_by_label:
            raise ValueError(f"A page named {text!r} is already registered.")
        if page.master is not self.pages:
            raise ValueError("Pages must be created as children of the pages frame.")
        self._page_labels.append(text)
        self._pages_by_label[text] = page
        self.selector.configure(values=tuple(self._page_labels))
        if self._selected_label is None:
            self._show_page(text)

    def _on_section_selected(self, _event=None):
        self._show_page(self._section_var.get())

    def _show_page(self, label):
        page = self._pages_by_label.get(label)
        if page is None:
            return
        if self._selected_label is not None:
            self._pages_by_label[self._selected_label].pack_forget()
        page.pack(fill="both", expand=True)
        self._selected_label = label
        self._section_var.set(label)
        callback = self.on_show
        if callable(callback):
            callback(label)


class StoryBuilderApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.appearance_mode = apply_application_appearance(self)
        self.title("StoryBuilder")
        self.geometry("1050x720")
        self.minsize(900, 620)

        self.package: StoryPackage | None = None
        self.character_filename: str | None = None
        self.dirty = False
        self.guided_setup = GuidedSetupSession()
        self._closing = False
        self.state_analysis_in_progress = False
        self._scroll_canvases = []
        self.spellcheck_available = shutil.which("aspell") is not None
        self._spellcheck_jobs = {}
        # Background spell-check workers publish results here. Only the Tk main
        # thread may consume them and update widgets.
        self._spellcheck_results = queue.Queue()
        self._spellcheck_poll_job = None
        self.writer_engine = WriterEngine()
        self.writer_engine.prompt_trace = None
        self.prompt_trace_armed = False
        self.active_prompt_trace = None
        self.writer_thread = None
        self.writer_notes_update_in_progress = False
        self.generated_scene = ""
        self.accepted_scene = ""
        self.accepted_scene_context = None
        self.focused_revision_history = []
        # Keep each generated scene tied to the chapter/scene and exact start
        # state that produced it. Never file prose under a later UI selection.
        self.generated_scene_context: tuple[int, int] | None = None
        self.generated_scene_start_state: dict | None = None
        self.writer_generation_context: tuple[int, int] | None = None
        self.writer_generation_start_state: dict | None = None
        self.writer_generation_in_progress = False
        self.scene_contract_editor_key: tuple[int, int] | None = None
        self.scene_contract_building = False
        self.pending_state_patch = None
        self.selected_manuscript_path = None
        self.saved_state_candidate = None
        self.saved_state_candidate_path = None
        self.scene_flow_review_in_progress = False
        self.scene_flow_review_thread = None
        self.interview_active = False
        self.interview_index = 0
        self.interview_pending_patch = None
        self.interview_pending_answer = ""
        self.change_pending_patch = None
        self.change_pending_request = ""
        self.change_pending_snapshot = None
        self.change_request_in_progress = False
        self.change_request_thread = None
        self.new_novel_pending_proposal = None
        self.new_novel_pending_brief = ""
        self.new_novel_pending_package = None
        self.new_novel_assistant_in_progress = False
        self.new_novel_assistant_worker_running = False
        self.new_novel_assistant_request_token = 0
        self.new_novel_assistant_results = queue.Queue()
        self.new_novel_assistant_thread = None
        self.selected_manuscript_path = None
        self.saved_state_candidate = None
        self.scene_planner_messages = []
        self.scene_planner_target = None
        self.scene_planner_package_path = None
        self.scene_planner_start_state = None
        self.scene_planner_request_in_progress = False
        self.scene_planner_task_kind = None
        self.scene_planner_pending_proposal = None
        self.scene_planner_thread = None

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._close_and_sync)
        self._load_startup_novel()

    def _build_ui(self):
        toolbar = ttk.Frame(self, padding=8)
        toolbar.pack(fill="x")
        for label, command in [
            ("New Novel", self._new_novel),
            ("Open Novel", self._open_novel),
            ("Save", self._save),
            ("Save As", self._save_as),
            ("Validate", self._validate),
        ]:
            ttk.Button(toolbar, text=label, command=command).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Sync Novel", command=self._sync_current_novel).pack(side="left", padx=(10, 3))
        ttk.Button(toolbar, text="Close", command=self._close_without_sync).pack(side="left", padx=(10, 3))
        ttk.Button(toolbar, text="Close & Sync Novel", command=self._close_and_sync).pack(side="left", padx=3)
        self.path_label = ttk.Label(toolbar, text="Unsaved novel")
        self.path_label.pack(side="right", padx=8)

        self.notebook = CompactTabContainer(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._build_chat_tab()
        self._build_new_novel_assistant_tab()
        self._build_story_tab()
        self._build_canon_tab()
        self._build_change_assistant_tab()
        self._build_characters_tab()
        self._build_relationships_tab()
        self._build_locations_tab()
        self._build_modules_tab()
        self._build_planning_tab()
        self._build_story_interview_tab()
        self._build_scene_contract_tab()
        self._build_scene_planner_tab()
        self._build_state_tab()
        self._build_writer_tab()
        self._build_manuscript_tab()
        self._install_context_menus()
        self._install_mousewheel_scrolling()
        self._install_spellchecking()
        self.notebook.on_show = self._on_main_section_shown

    def _make_scrollable_tab(self, page, padding=12):
        """Place a tab's content in a vertical scrolling area.

        Keep the scrollbar visible so controls below the bottom edge remain
        discoverable on short laptop displays. Existing tabs with custom
        scroll layouts use their own canvas and do not call this helper.
        """
        scroll_frame = ttk.Frame(page)
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
        self._scroll_canvases.append(canvas)

        content = ttk.Frame(canvas, padding=padding)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def update_scroll_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def fit_content_width(event):
            canvas.itemconfigure(window_id, width=event.width)

        content.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", fit_content_width)
        return content

    def _build_chat_tab(self):
        tab = ttk.Frame(self.notebook.pages, padding=12)
        self.notebook.add(tab, text="Talk to Builder")

        ttk.Label(tab, text="Tell the builder what to change", font=("", 14, "bold")).pack(anchor="w")
        ttk.Label(
            tab,
            text='Examples:  Change Maya\'s age to 22   •   Set the current chapter to 2   •   Change the story title to The Long Road',
        ).pack(anchor="w", pady=(4, 12))

        chat_frame = ttk.Frame(tab)
        chat_frame.pack(fill="both", expand=True)
        self.chat_log = tk.Text(chat_frame, wrap="word", height=24, state="disabled")
        chat_scrollbar = ttk.Scrollbar(chat_frame, orient="vertical", command=self.chat_log.yview)
        self.chat_log.configure(yscrollcommand=chat_scrollbar.set)
        chat_scrollbar.pack(side="right", fill="y")
        self.chat_log.pack(side="left", fill="both", expand=True)

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
        page = ttk.Frame(self.notebook.pages)
        self.notebook.add(page, text="Story")
        tab = self._make_scrollable_tab(page)

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

    def _build_canon_tab(self):
        page = ttk.Frame(self.notebook.pages)
        self.notebook.add(page, text="Canon & Rules")
        tab = self._make_scrollable_tab(page)
        ttk.Label(tab, text="Canon and Story Rules", font=("", 14, "bold")).pack(anchor="w")
        ttk.Label(
            tab,
            text=("Enter permanent story facts and rules, one per line. These guide future generated scenes. "
                  "Use Change Assistant for natural-language requests that update rules, characters, supporting people, "
                  "relationships, locations, or planning."),
            wraplength=900, justify="left",
        ).pack(anchor="w", pady=(4, 8))
        self.canon_rules_text = tk.Text(tab, wrap="word", undo=True, height=20)
        self.canon_rules_text.pack(fill="both", expand=True, pady=(0, 8))
        row = ttk.Frame(tab)
        row.pack(fill="x")
        ttk.Button(row, text="Review and Save Rules", command=self._review_and_save_canon_rules).pack(side="left")
        ttk.Button(row, text="Reload Working Canon", command=self._reload_canon_rules_editor).pack(side="left", padx=(8, 0))
        self.canon_rules_status = ttk.Label(row, text="Review changes before they become canon.", wraplength=600, justify="left")
        self.canon_rules_status.pack(side="left", fill="x", expand=True, padx=(12, 0))

    def _build_change_assistant_tab(self):
        page = ttk.Frame(self.notebook.pages)
        self.notebook.add(page, text="Change Assistant")
        tab = self._make_scrollable_tab(page)
        ttk.Label(tab, text="Plain-English Change Assistant", font=("", 14, "bold")).pack(anchor="w")
        ttk.Label(
            tab,
            text=("Describe the change as if talking to a writing partner. The selected local model prepares a readable proposal. "
                  "Nothing changes until you approve it. Stop the Writer first so StoryBuilder does not load two copies of the model."),
            wraplength=900, justify="left",
        ).pack(anchor="w", pady=(4, 8))
        ttk.Label(tab, text="What would you like to change?", font=("", 11, "bold")).pack(anchor="w")
        self.change_request_text = tk.Text(tab, height=5, wrap="word", undo=True)
        self.change_request_text.pack(fill="x", pady=(4, 8))
        ttk.Label(
            tab,
            text=("Example: Make Jessica the computer expert. Rick served in the regular Army, not Special Forces. "
                  "Beth will use her neighborhood connections to help."),
            wraplength=900, justify="left",
        ).pack(anchor="w", pady=(0, 8))
        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=(0, 8))
        self.change_propose_button = ttk.Button(actions, text="Prepare Proposal", command=self._prepare_change_request)
        self.change_propose_button.pack(side="left")
        self.change_approve_button = ttk.Button(actions, text="Approve and Save Changes", command=self._approve_change_request, state="disabled")
        self.change_approve_button.pack(side="left", padx=(8, 0))
        self.change_reject_button = ttk.Button(actions, text="Reject Proposal", command=self._reject_change_request, state="disabled")
        self.change_reject_button.pack(side="left", padx=(8, 0))
        ttk.Label(tab, text="Review the proposed changes", font=("", 11, "bold")).pack(anchor="w")
        self.change_proposal_text = tk.Text(tab, wrap="word", height=15, state="disabled")
        self.change_proposal_text.pack(fill="both", expand=True, pady=(4, 8))
        self.change_assistant_status = ttk.Label(
            tab, text="No proposal pending. Preparing a proposal does not change your novel.",
            wraplength=900, justify="left",
        )
        self.change_assistant_status.pack(anchor="w")

    def _build_new_novel_assistant_tab(self):
        page = ttk.Frame(self.notebook.pages)
        self.notebook.add(page, text="New Novel Assistant")
        tab = self._make_scrollable_tab(page)
        ttk.Label(tab, text="Start a Novel in Plain English", font=("", 14, "bold")).pack(anchor="w")
        ttk.Label(
            tab,
            text=(
                "Describe your idea in a few paragraphs. StoryBuilder will draft the story foundation, character cards, "
                "relationships, locations, rules, open questions, and starting situation. Everything is a proposal until "
                "you approve it. Click New Novel first; this tool never overwrites an existing book."
            ),
            wraplength=900, justify="left",
        ).pack(anchor="w", pady=(4, 10))
        ttk.Label(tab, text="Tell StoryBuilder about the novel", font=("", 11, "bold")).pack(anchor="w")
        self.new_novel_brief_text = tk.Text(tab, height=9, wrap="word", undo=True)
        self.new_novel_brief_text.pack(fill="x", pady=(4, 8))
        ttk.Label(
            tab,
            text=(
                "Include what you already know: premise, people, ages, relationships, secrets, setting, tone, important objects, "
                "and rules. Unknown details can stay unknown; the review separates open questions and suggestions."
            ),
            wraplength=900, justify="left",
        ).pack(anchor="w", pady=(0, 8))
        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=(0, 8))
        self.new_novel_prepare_button = ttk.Button(
            actions, text="Prepare Starter Package", command=self._prepare_new_novel_proposal,
        )
        self.new_novel_prepare_button.pack(side="left")
        self.new_novel_approve_button = ttk.Button(
            actions, text="Approve and Build Package", command=self._approve_new_novel_proposal, state="disabled",
        )
        self.new_novel_approve_button.pack(side="left", padx=(8, 0))
        self.new_novel_reject_button = ttk.Button(
            actions, text="Reject Proposal", command=self._reject_new_novel_proposal, state="disabled",
        )
        self.new_novel_reject_button.pack(side="left", padx=(8, 0))
        ttk.Label(tab, text="Review the proposed starter package", font=("", 11, "bold")).pack(anchor="w")
        self.new_novel_proposal_text = tk.Text(tab, wrap="word", height=19, state="disabled")
        self.new_novel_proposal_text.pack(fill="both", expand=True, pady=(4, 8))
        self.new_novel_assistant_status = ttk.Label(
            tab, text="No proposal pending. Preparing a proposal does not change your novel.",
            wraplength=900, justify="left",
        )
        self.new_novel_assistant_status.pack(anchor="w")

    def _build_characters_tab(self):

        page = ttk.Frame(self.notebook.pages)
        self.notebook.add(page, text="Characters")
        tab = self._make_scrollable_tab(page)

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
        ttk.Button(left, text="Add Supporting Person", command=self._add_supporting_person).pack(fill="x", pady=(4, 3))
        ttk.Button(
            left,
            text="Promote to Core Character",
            command=self._promote_supporting_person,
        ).pack(fill="x", pady=(0, 3))
        ttk.Button(left, text="Remove Supporting Person", command=self._remove_supporting_person).pack(fill="x")

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
        page = ttk.Frame(self.notebook.pages)
        self.notebook.add(page, text="Relationships")
        tab = self._make_scrollable_tab(page)

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
        page = ttk.Frame(self.notebook.pages)
        self.notebook.add(page, text="Locations")
        tab = self._make_scrollable_tab(page)

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
        page = ttk.Frame(self.notebook.pages)
        self.notebook.add(page, text="Story Modules")
        tab = self._make_scrollable_tab(page)

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
        page = ttk.Frame(self.notebook.pages)
        self.notebook.add(page, text="Story Planning")
        tab = self._make_scrollable_tab(page)

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
        tab = ttk.Frame(self.notebook.pages)
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
            text="Current Canon",
            font=("", 11, "bold"),
        ).pack(anchor="w", pady=(4, 0))
        self.interview_current_text = tk.Text(
            content,
            height=7,
            wrap="word",
            state="disabled",
        )
        self.interview_current_text.pack(fill="x", pady=(4, 8))

        ttk.Label(
            content,
            text="Your Answer / Revision",
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
        tab = ttk.Frame(self.notebook.pages)
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
            text="Scene Idea and Generated Contract",
            font=("", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            content,
            text=(
                "The Scene Idea is the part you edit. If this scene has no saved idea, StoryBuilder loads "
                "the matching scene from STORY_PLAN.md when available. Saved Scene Ideas always take "
                "priority, and a plan-loaded idea is not saved until you save it or generate the contract. "
                "Generate / Replace Contract asks the local model for a concise direction and ending. "
                "Items under clearly labeled Required Beats or Planned Beats sections in your Scene Idea become formal "
                "scene-level beats; model-generated suggestions do not become mandatory. Explicit Boundaries "
                "are carried separately as constraints. Separately enabled "
                "modules may supply their own requirements. The original Scene Idea remains the Writer's "
                "primary guidance. If a contract is saved, StoryBuilder asks before replacing its generated fields."
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(4, 8))

        idea_frame = ttk.Frame(content)
        idea_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(
            idea_frame,
            text="Scene Idea / Author Notes",
            font=("", 11, "bold"),
        ).pack(anchor="w")
        self.scene_idea_text = tk.Text(idea_frame, height=5, wrap="word", undo=True)
        self.scene_idea_text.pack(fill="x", pady=(4, 6))
        idea_button_row = ttk.Frame(idea_frame)
        idea_button_row.pack(anchor="w")
        self.scene_contract_build_button = ttk.Button(
            idea_button_row,
            text="Generate / Replace Contract...",
            command=self._build_contract_from_scene_idea,
        )
        self.scene_contract_build_button.pack(side="left")
        self.scene_contract_reload_idea_button = ttk.Button(
            idea_button_row,
            text="Clear & Reload Scene Idea",
            command=self._reload_saved_scene_idea,
        )
        self.scene_contract_reload_idea_button.pack(side="left", padx=(8, 0))
        self.scene_contract_plan_reload_button = ttk.Button(
            idea_button_row,
            text="Load from STORY_PLAN.md",
            command=self._load_scene_idea_from_plan,
        )
        self.scene_contract_plan_reload_button.pack(side="left", padx=(8, 0))
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

        self.scene_contract_direction_text = tk.Text(
            form, height=4, wrap="word", state="disabled"
        )
        self.scene_contract_end_text = tk.Text(
            form, height=4, wrap="word", state="disabled"
        )
        self.scene_contract_texts = {
            "required_beats": tk.Text(form, height=5, wrap="word", state="disabled"),
            "boundaries": tk.Text(form, height=4, wrap="word", state="disabled"),
        }

        fields = [
            ("direction", "Beginning / Middle Direction", self.scene_contract_direction_text),
            ("end", "End / Hard Stop", self.scene_contract_end_text),
            ("required_beats", "Planned / Required Beats (one per line)", self.scene_contract_texts["required_beats"]),
            ("boundaries", "Author Boundaries (one per line)", self.scene_contract_texts["boundaries"]),
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
            form.rowconfigure(row, weight=1)
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
            state="readonly",
        ).pack(side="left", padx=(8, 12))
        ttk.Label(
            attempts_row,
            text="Set by StoryBuilder from the generated contract.",
        ).pack(side="left")

        action_row = ttk.Frame(content)
        action_row.pack(fill="x", pady=(10, 0))
        self.scene_contract_status = ttk.Label(
            action_row,
            text="Edit the Scene Idea, then build the contract.",
            anchor="w",
        )
        self.scene_contract_status.pack(side="left", fill="x", expand=True)

    def _build_scene_planner_tab(self):
        page = ttk.Frame(self.notebook.pages)
        self.notebook.add(page, text="Scene Planner")
        tab = self._make_scrollable_tab(page)
        ttk.Label(tab, text="Plan a Scene Together", font=("", 14, "bold")).pack(anchor="w")
        ttk.Label(
            tab,
            text=("Talk through the scene's purpose, sequence, continuity, and stopping point. "
                  "The local model helps you think; it does not decide canon or change files during conversation. "
                  "Prepare a proposal when ready, review or edit it, then explicitly approve the save."),
            wraplength=900, justify="left",
        ).pack(anchor="w", pady=(4, 8))
        self.scene_planner_target_var = tk.StringVar(value="Open a saved novel to plan a scene.")
        ttk.Label(tab, textvariable=self.scene_planner_target_var, font=("", 11, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(tab, text="Planning conversation", font=("", 11, "bold")).pack(anchor="w")
        log_frame = ttk.Frame(tab)
        log_frame.pack(fill="both", expand=True, pady=(4, 8))
        self.scene_planner_log = tk.Text(log_frame, height=13, wrap="word", state="disabled")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.scene_planner_log.yview)
        self.scene_planner_log.configure(yscrollcommand=log_scroll.set)
        self.scene_planner_log.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")
        ttk.Label(tab, text="Your message", font=("", 11, "bold")).pack(anchor="w")
        self.scene_planner_input_text = tk.Text(tab, height=4, wrap="word", undo=True)
        self.scene_planner_input_text.pack(fill="x", pady=(4, 8))
        self.scene_planner_input_text.bind("<Control-Return>", lambda _event: self._send_scene_planner_message() or "break")
        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=(0, 8))
        self.scene_planner_send_button = ttk.Button(actions, text="Send to Planner", command=self._send_scene_planner_message)
        self.scene_planner_send_button.pack(side="left")
        self.scene_planner_prepare_button = ttk.Button(actions, text="Prepare Plan Proposal", command=self._prepare_scene_planner_proposal)
        self.scene_planner_prepare_button.pack(side="left", padx=(8, 0))
        self.scene_planner_clear_button = ttk.Button(actions, text="Clear Conversation", command=self._clear_scene_planner_conversation)
        self.scene_planner_clear_button.pack(side="left", padx=(8, 0))
        ttk.Label(tab, text="Plan proposal (editable before approval)", font=("", 11, "bold")).pack(anchor="w", pady=(8, 0))
        ttk.Label(
            tab,
            text=("Only this scene section will be inserted or replaced in STORY_PLAN.md. "
                  "Other chapters and scenes are preserved, and the file is checked for changes before saving."),
            wraplength=900, justify="left",
        ).pack(anchor="w", pady=(3, 5))
        title_row = ttk.Frame(tab)
        title_row.pack(fill="x", pady=(0, 5))
        ttk.Label(title_row, text="Scene title", width=14).pack(side="left")
        self.scene_planner_title_var = tk.StringVar()
        self.scene_planner_title_entry = ttk.Entry(title_row, textvariable=self.scene_planner_title_var)
        self.scene_planner_title_entry.pack(side="left", fill="x", expand=True)
        self.scene_planner_proposal_text = tk.Text(tab, height=13, wrap="word", undo=True)
        self.scene_planner_proposal_text.pack(fill="both", expand=True, pady=(4, 8))
        proposal_actions = ttk.Frame(tab)
        proposal_actions.pack(fill="x")
        self.scene_planner_approve_button = ttk.Button(
            proposal_actions, text="Approve & Save Plan", command=self._approve_scene_plan_proposal, state="disabled"
        )
        self.scene_planner_approve_button.pack(side="left")
        self.scene_planner_reject_button = ttk.Button(
            proposal_actions, text="Reject Proposal", command=self._reject_scene_plan_proposal, state="disabled"
        )
        self.scene_planner_reject_button.pack(side="left", padx=(8, 0))
        self.scene_planner_status = ttk.Label(tab, text="No plan changes have been made.", wraplength=900, justify="left")
        self.scene_planner_status.pack(anchor="w", fill="x", pady=(8, 0))
        self._refresh_scene_planner_target()
        self._update_scene_planner_buttons()

    def _build_state_tab(self):
        page = ttk.Frame(self.notebook.pages)
        self.notebook.add(page, text="Current State")
        tab = self._make_scrollable_tab(page)

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

        state_button_row = ttk.Frame(tab)
        state_button_row.grid(row=7, column=1, sticky="e", pady=8)
        ttk.Button(
            state_button_row,
            text="Apply & Save State Edits",
            command=self._apply_state_edits_and_save,
        ).pack(side="left")
        ttk.Button(
            state_button_row,
            text="Restore Previous End State",
            command=self._restore_previous_scene_end_state,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            state_button_row,
            text="Advance to Next Scene",
            command=self._advance_to_next_scene,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            state_button_row,
            text="Start Next Chapter",
            command=self._start_next_chapter,
        ).pack(side="left", padx=(8, 0))

        chapter_action_row = ttk.Frame(tab)
        chapter_action_row.grid(row=8, column=1, sticky="w", pady=(0, 8))
        ttk.Button(
            chapter_action_row,
            text="Finalize Chapter",
            command=self._finalize_current_chapter,
        ).pack(side="left")
        ttk.Label(
            chapter_action_row,
            text="Use after the final accepted scene's state has been applied.",
        ).pack(side="left", padx=(8, 0))

        ttk.Label(tab, text="Current Situation").grid(row=9, column=0, sticky="nw", pady=5)
        self.situation_text = tk.Text(tab, height=5, wrap="word")
        self.situation_text.grid(row=9, column=1, sticky="nsew", pady=5)
        ttk.Button(tab, text="Apply Situation", command=self._apply_situation_edit).grid(row=10, column=1, sticky="e", pady=8)

        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(5, weight=1)
        tab.rowconfigure(6, weight=1)
        tab.rowconfigure(9, weight=1)

    def _build_writer_tab(self):
        tab = ttk.Frame(self.notebook.pages)
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

        idea_frame = ttk.Frame(content_frame)
        idea_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(
            idea_frame,
            text="Original Scene Idea (Primary Intent)",
            font=("", 11, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            idea_frame,
            text=(
                "Read-only preview of the plain-English idea used by the Writer. "
                "Edit it in Scene Contract; it does not need a generated contract."
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(3, 4))
        self.writer_scene_idea_status = ttk.Label(
            idea_frame,
            text="No novel loaded.",
        )
        self.writer_scene_idea_status.pack(anchor="w", pady=(0, 4))
        self.writer_scene_idea_text = tk.Text(
            idea_frame, height=6, wrap="word", state="disabled"
        )
        self.writer_scene_idea_text.pack(fill="x", pady=(0, 4))

        direction_header = ttk.Frame(content_frame)
        direction_header.pack(fill="x")
        ttk.Label(
            direction_header,
            text="Scene Direction (continuity and supporting guidance)",
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

        trace_row = ttk.Frame(content_frame)
        trace_row.pack(fill="x", pady=(0, 8))
        self.writer_trace_button = ttk.Button(
            trace_row,
            text="Trace Next Scene (Off)",
            command=self._toggle_prompt_trace,
        )
        self.writer_trace_button.pack(side="left")
        self.writer_trace_status = ttk.Label(
            trace_row,
            text="Off. No prompts are being recorded.",
            wraplength=720,
            justify="left",
        )
        self.writer_trace_status.pack(side="left", padx=(8, 0))

        ttk.Label(
            content_frame,
            text="Generated Scene",
            font=("", 11, "bold"),
        ).pack(anchor="w")
        self.writer_output_text = tk.Text(content_frame, height=22, wrap="word", undo=True)
        self.writer_output_text.pack(fill="x", pady=(4, 0))

        review_button_row = ttk.Frame(content_frame)
        review_button_row.pack(fill="x", pady=(8, 4))
        self.writer_accept_button = ttk.Button(
            review_button_row,
            text="Accept Scene",
            command=self._accept_generated_scene,
        )
        self.writer_accept_button.pack(side="left")
        self.writer_regenerate_button = ttk.Button(
            review_button_row,
            text="Regenerate Scene",
            command=self._regenerate_generated_scene,
        )
        self.writer_regenerate_button.pack(side="left", padx=(8, 0))
        self.writer_reject_button = ttk.Button(
            review_button_row,
            text="Reject Scene",
            command=self._reject_generated_scene,
        )
        self.writer_reject_button.pack(side="left", padx=(8, 0))

        revision_frame = ttk.Frame(content_frame)
        revision_frame.pack(fill="x", pady=(4, 8))
        ttk.Label(
            revision_frame,
            text=(
                "Focused change: describe one specific change; other text will be preserved. "
                "(Ctrl+Enter to apply.)"
            ),
        ).pack(anchor="w")

        request_input_frame = ttk.Frame(revision_frame)
        request_input_frame.pack(fill="x", pady=(3, 0))
        self.writer_revision_request_entry = tk.Text(
            request_input_frame,
            height=4,
            wrap="word",
            undo=True,
        )
        request_scrollbar = ttk.Scrollbar(
            request_input_frame,
            orient="vertical",
            command=self.writer_revision_request_entry.yview,
        )
        self.writer_revision_request_entry.configure(yscrollcommand=request_scrollbar.set)
        self.writer_revision_request_entry.pack(side="left", fill="x", expand=True)
        request_scrollbar.pack(side="right", fill="y")
        self.writer_revision_request_entry.bind(
            "<Control-Return>",
            lambda _event: self._apply_focused_scene_change() or "break",
        )

        revision_button_row = ttk.Frame(revision_frame)
        revision_button_row.pack(fill="x", pady=(4, 0))
        self.writer_focus_change_button = ttk.Button(
            revision_button_row,
            text="Apply Focused Change",
            command=self._apply_focused_scene_change,
        )
        self.writer_focus_change_button.pack(side="left")
        self.writer_undo_focused_change_button = ttk.Button(
            revision_button_row,
            text="Undo Focused Change",
            command=self._undo_focused_scene_change,
        )
        self.writer_undo_focused_change_button.pack(side="left", padx=(8, 0))

        state_button_row = ttk.Frame(content_frame)
        state_button_row.pack(fill="x", pady=(8, 0))
        self.writer_reload_scene_button = ttk.Button(
            state_button_row,
            text="Reload Saved Scene",
            command=self._load_saved_scene_into_writer,
        )
        self.writer_reload_scene_button.pack(side="left")
        self.writer_analyze_button = ttk.Button(
            state_button_row,
            text="Analyze Accepted Scene",
            command=self._analyze_accepted_scene,
        )
        self.writer_analyze_button.pack(side="left", padx=(8, 0))
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
            text="Proposed Changes (Review Before Apply)",
            font=("", 11, "bold"),
        ).pack(side="left")

        self.writer_copy_state_button = ttk.Button(
            proposed_state_header,
            text="Copy Full JSON",
            command=self._copy_proposed_state,
        )
        self.writer_copy_state_button.pack(side="right")

        ttk.Label(
            content_frame,
            text=(
                "The first tab shows only what this scene changes. Fields not listed are preserved. "
                "Use Full State JSON (Advanced) only when a manual correction is needed. Applying the "
                "proposal merges those edits into the saved state; scene navigation remains app-controlled."
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        self.writer_state_review_notebook = ttk.Notebook(content_frame)
        self.writer_state_review_notebook.pack(fill="both", expand=True, pady=(4, 0))

        self.writer_state_diff_tab = ttk.Frame(self.writer_state_review_notebook)
        self.writer_state_json_tab = ttk.Frame(self.writer_state_review_notebook)
        self.writer_state_review_notebook.add(
            self.writer_state_diff_tab, text="Changes to Review"
        )
        self.writer_state_review_notebook.add(
            self.writer_state_json_tab, text="Full State JSON (Advanced)"
        )

        diff_frame = ttk.Frame(self.writer_state_diff_tab)
        diff_frame.pack(fill="both", expand=True)
        diff_scrollbar = ttk.Scrollbar(diff_frame, orient="vertical")
        self.writer_state_diff_preview = tk.Text(
            diff_frame,
            height=16,
            wrap="word",
            yscrollcommand=diff_scrollbar.set,
            state="disabled",
        )
        diff_scrollbar.configure(command=self.writer_state_diff_preview.yview)
        self.writer_state_diff_preview.pack(side="left", fill="both", expand=True)
        diff_scrollbar.pack(side="right", fill="y")

        json_frame = ttk.Frame(self.writer_state_json_tab)
        json_frame.pack(fill="both", expand=True)
        json_scrollbar = ttk.Scrollbar(json_frame, orient="vertical")
        self.writer_state_preview = tk.Text(
            json_frame,
            height=18,
            wrap="none",
            undo=True,
            yscrollcommand=json_scrollbar.set,
        )
        json_scrollbar.configure(command=self.writer_state_preview.yview)
        self.writer_state_preview.pack(side="left", fill="both", expand=True)
        json_scrollbar.pack(side="right", fill="y")

        self._refresh_writer_models()
        self._update_writer_buttons()

    def _build_manuscript_tab(self):
        page = ttk.Frame(self.notebook.pages)
        self.notebook.add(page, text="Manuscript")
        tab = self._make_scrollable_tab(page)

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
            text="Assemble Chapter",
            command=self._assemble_current_chapter,
        ).pack(fill="x", pady=(6, 0))

        self.manuscript_review_flow_button = ttk.Button(
            manuscript_button_row,
            text="Review Scene Flow",
            command=self._review_scene_flow,
        )
        self.manuscript_review_flow_button.pack(fill="x", pady=(6, 0))

        ttk.Button(
            manuscript_button_row,
            text="Assemble Entire Novel",
            command=self._assemble_entire_novel,
        ).pack(fill="x", pady=(6, 0))

        self.manuscript_flow_status = ttk.Label(
            left,
            text="Review accepted scenes for transition problems without changing the manuscript.",
            wraplength=230,
            justify="left",
        )
        self.manuscript_flow_status.pack(fill="x", pady=(0, 8))

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

    def _author_writing_guidance(self) -> str:
        """Return stable author instructions without mixing in scene-specific planning."""
        if self.package is None:
            return ""

        extra_json = getattr(self.package, "extra_json", {})
        if not isinstance(extra_json, dict):
            return ""
        guidance = extra_json.get("writing_guidance.json", {})
        if not isinstance(guidance, dict):
            return ""

        sections = []
        for label, key in (
            ("Recurring writing instructions", "recurring_instructions"),
            ("Permitted relationship creativity", "relationship_freedom"),
            ("Author-specified avoidances", "avoid"),
        ):
            values = guidance.get(key, [])
            if isinstance(values, str):
                values = [values]
            if not isinstance(values, list):
                continue
            items = [str(value).strip() for value in values if str(value).strip()]
            if items:
                sections.append(
                    label + ":\n" + "\n".join(f"- {item}" for item in items)
                )

        return "\n\n".join(sections)

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

        # Query active context against the author-defined current scene rather
        # than every historical fact in the package. The complete ledgers stay
        # persisted; this is only the transient prompt view.
        location = state.get("location", "")
        primary_location = (
            str(location.get("primary", "") or "").strip()
            if isinstance(location, dict)
            else str(location or "").strip()
        )
        chapter = int(state.get("chapter", 1) or 1)
        scene = int(state.get("scene", 1) or 1)
        guidance_plan = self.package.extra_json.get("writing_guidance.json", {})
        guidance_entry = (
            self._chapter_scene_guidance(guidance_plan, chapter, scene)
            if isinstance(guidance_plan, dict) else None
        )
        if not isinstance(guidance_entry, dict):
            guidance_entry = {}
        context_query = "\n".join([
            *scene_cast_names,
            primary_location,
            str(state.get("current_situation", "") or ""),
            str(guidance_entry.get("scene_idea", "") or ""),
            str(guidance_entry.get("direction", "") or ""),
            str(guidance_entry.get("end_condition", "") or ""),
        ]).strip()
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

        working_notes = normalize_writer_notes(
            getattr(self.package, "writer_notes", {})
        )
        all_learned_notes = [
            item for item in working_notes.get("learned_notes", [])
            if isinstance(item, dict) and item.get("note")
        ]
        # Keep small note sets intact. If the notebook grows, retrieve only
        # scene-relevant craft observations; the persisted notebook is untouched.
        if len(all_learned_notes) > 24:
            prompt_learned_notes = select_relevant_records(
                all_learned_notes, context_query, text_key="note", limit=24
            )
            if not prompt_learned_notes:
                prompt_learned_notes = all_learned_notes[-8:]
        else:
            prompt_learned_notes = all_learned_notes
        if prompt_learned_notes:
            prompt_notes = {
                "learned_notes": [
                    {"note": item["note"]}
                    for item in prompt_learned_notes
                ]
            }
            files.append((
                WRITER_NOTES_FILENAME,
                json.dumps(prompt_notes, indent=2, ensure_ascii=False),
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
        all_scene_knowledge = {}
        if isinstance(character_knowledge, dict):
            for name in scene_cast_names:
                values = character_knowledge.get(name)
                if values is None:
                    for key, candidate in character_knowledge.items():
                        if str(key).casefold() == name.casefold():
                            values = candidate
                            break
                if isinstance(values, list):
                    all_scene_knowledge[name] = [
                        str(item).strip()
                        for item in values
                        if str(item).strip()
                    ]
                elif isinstance(values, str) and values.strip():
                    all_scene_knowledge[name] = [values.strip()]
        scene_knowledge, knowledge_metrics = select_active_character_knowledge(
            all_scene_knowledge,
            context_query,
            max_items_per_character=18,
            max_total_items=72,
        )
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

        # Off-scene characters do not need full character cards in the
        # persistent writer context. Their current location/state is already
        # supplied by scene_state.json and current_situation. A compact anchor
        # preserves that information without spending thousands of tokens on
        # unrelated biography, appearance, secrets, or routines.
        offscene_anchors = {}
        location_data = state.get("location", {})
        if isinstance(location_data, dict):
            for name, location_text in location_data.items():
                if name == "primary":
                    continue

                name_text = str(name).strip()
                if not name_text or name_text.casefold() in scene_cast:
                    continue

                offscene_anchors[name_text] = {
                    "name": name_text,
                    "status": "established",
                    "scene_state": str(location_text or "").strip(),
                }

        if offscene_anchors:
            files.append((
                "offscene_character_anchors.json",
                json.dumps(offscene_anchors, indent=2, ensure_ascii=False),
            ))

        # Include compact relationship facts even when they are stored as
        # simple strings rather than nested dictionaries. These facts are often
        # exactly what the writer needs when an off-scene person is mentioned,
        # such as knowing who a sick friend's mother is.
        relationships = self.package.story_bible.get("relationships", {})
        context_names = set(scene_cast_names)
        if isinstance(location_data, dict):
            context_names.update(
                str(name).strip()
                for name in location_data
                if str(name).strip() and str(name) != "primary"
            )

        if isinstance(relationships, dict):
            relevant_facts = {}
            for key, value in relationships.items():
                if not isinstance(value, (str, int, float, bool, list)):
                    continue
                key_text = str(key).casefold()
                if any(str(name).casefold() in key_text for name in context_names):
                    relevant_facts[key] = value
            if relevant_facts:
                files.append((
                    "relevant_relationship_facts.json",
                    json.dumps(relevant_facts, indent=2, ensure_ascii=False),
                ))

            # Preserve the existing richer relationship objects for scenes that
            # use them. Keep this separate so compact scalar facts do not get
            # filtered out.
            relevant = {}
            for key, value in relationships.items():
                if not isinstance(value, dict):
                    continue
                key_text = str(key).casefold()
                if any(str(name).casefold() in key_text for name in context_names):
                    relevant[key] = value
            if relevant:
                files.append((
                    "scene_relationships.json",
                    json.dumps(relevant, indent=2, ensure_ascii=False),
                ))

        # Supporting people are intentionally kept compact. The writer gets
        # their established names/roles without pulling full off-scene character
        # material into the 8K context.
        supporting_people = self.package.story_bible.get("supporting_people", {})
        supporting_context = {}
        query_text = context_query.casefold()
        if isinstance(supporting_people, dict):
            for name, value in supporting_people.items():
                name_text = str(name).strip()
                if not name_text:
                    continue
                explicitly_relevant = (
                    name_text.casefold() in scene_cast
                    or bool(re.search(
                        r"(?<!\\w)" + re.escape(name_text) + r"(?!\\w)",
                        query_text,
                        flags=re.IGNORECASE,
                    ))
                )
                if not explicitly_relevant:
                    continue
                if isinstance(value, str):
                    supporting_context[name_text] = value
                elif isinstance(value, dict):
                    compact = {
                        key: value[key]
                        for key in ("role", "story_role")
                        if key in value and value[key]
                    }
                    if compact:
                        supporting_context[name_text] = compact
        if supporting_context:
            files.append((
                "supporting_people_context.json",
                json.dumps(supporting_context, indent=2, ensure_ascii=False),
            ))

        # Author-defined canon rules are always supplied as hard constraints.
        canon_rules = self.package.story_bible.get("canon_rules", [])
        if isinstance(canon_rules, str):
            canon_rules = [line.strip() for line in canon_rules.splitlines() if line.strip()]
        if isinstance(canon_rules, list):
            normalized_rules = [str(rule).strip() for rule in canon_rules if str(rule).strip()]
            if normalized_rules:
                files.append(("author_defined_canon_rules.txt", "\n".join(f"- {rule}" for rule in normalized_rules)))

        # Stable author guidance is distinct from the active scene plan. The
        # recurring rules, creative permissions, and avoidances should reach
        # both the prose Writer and semantic validator on every scene.
        author_guidance = self._author_writing_guidance()
        if author_guidance:
            files.append(("author_writing_guidance.txt", author_guidance))

        # Do not place full historical prose in the persistent system prompt.
        # Older accepted prose is searched on demand for the current scene only.
        active_detail_chars = (
            len(json.dumps(scene_knowledge, ensure_ascii=False))
            + len(json.dumps(prompt_learned_notes if all_learned_notes else [], ensure_ascii=False))
            + len(json.dumps(supporting_context, ensure_ascii=False))
        )
        candidate_detail_chars = (
            len(json.dumps(all_scene_knowledge, ensure_ascii=False))
            + len(json.dumps(all_learned_notes, ensure_ascii=False))
            + len(json.dumps(supporting_people if isinstance(supporting_people, dict) else {}, ensure_ascii=False))
        )
        self.writer_last_context_metrics = {
            "knowledge": knowledge_metrics,
            "detail_context_before_chars": candidate_detail_chars,
            "detail_context_after_chars": active_detail_chars,
            "detail_context_before_estimated_tokens": estimate_tokens_from_chars(candidate_detail_chars),
            "detail_context_after_estimated_tokens": estimate_tokens_from_chars(active_detail_chars),
            "detail_context_reduction_percent": round(
                (candidate_detail_chars - active_detail_chars) * 100 / candidate_detail_chars, 1
            ) if candidate_detail_chars else 0.0,
            "active_knowledge_items": sum(len(values) for values in scene_knowledge.values()),
            "candidate_knowledge_items": sum(len(values) for values in all_scene_knowledge.values()),
            "active_writer_notes": len(prompt_learned_notes),
            "candidate_writer_notes": len(all_learned_notes),
            "historical_archive_characters": 0,
            "historical_archive_estimated_tokens": 0,
        }
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
            if hasattr(self, "interview_current_text"):
                self.interview_current_text.configure(state="normal")
                self.interview_current_text.delete("1.0", "end")
                self.interview_current_text.configure(state="disabled")
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

    def _interview_character_current_answer(self, title):
        if self.package is None:
            return ""

        target = self.interview_target_var.get().strip()
        character = self.package.characters.get(target, {})
        if not isinstance(character, dict):
            return ""

        def scalar(value):
            return str(value or "").strip()

        def list_text(value):
            if isinstance(value, list):
                return "\n".join(
                    scalar(item) for item in value if scalar(item)
                )
            return scalar(value)

        def block(label, value):
            if isinstance(value, dict):
                body = self._format_key_value_block(value)
            else:
                body = list_text(value)
            return f"{label}:\n{body}" if body else ""

        if title == "Role":
            return scalar(character.get("role"))

        if title == "Age":
            value = character.get("age")
            return "" if value is None else str(value)

        if title == "Appearance":
            parts = []
            if character.get("appearance"):
                parts.append(block("Appearance", character.get("appearance")))
            for key in ("description",):
                value = scalar(character.get(key))
                if value:
                    parts.append(f"{key.title()}:\n{value}")
            return "\n\n".join(parts)

        if title == "Personality":
            return list_text(character.get("personality"))

        if title == "Strengths and weaknesses":
            parts = [
                block("Strengths", character.get("strengths")),
                block("Weaknesses", character.get("weaknesses")),
                block("Fears", character.get("fears")),
            ]
            return "\n\n".join(part for part in parts if part)

        if title == "Background and family":
            parts = []
            for key in ("background", "family", "family_living_arrangement", "wife"):
                value = character.get(key)
                item = block(key.replace("_", " ").title(), value)
                if item:
                    parts.append(item)
            return "\n\n".join(parts)

        if title == "Relationships":
            parts = []
            for key in ("relationships", "friendship_dynamics", "relationship_with_tony"):
                item = block(key.replace("_", " ").title(), character.get(key))
                if item:
                    parts.append(item)
            return "\n\n".join(parts)

        if title == "Private feelings":
            parts = []
            for key in ("private_feelings", "romance", "internal_conflict", "secret"):
                item = block(key.replace("_", " ").title(), character.get(key))
                if item:
                    parts.append(item)
            return "\n\n".join(parts)

        if title == "Knowledge boundaries":
            parts = []
            for key in ("knowledge_rule", "knowledge", "does_not_know", "known_facts"):
                item = block(key.replace("_", " ").title(), character.get(key))
                if item:
                    parts.append(item)
            return "\n\n".join(parts)

        if title == "Habits and cues":
            return list_text(character.get("personality_cues"))

        if title == "Goals and interests":
            parts = []
            for key in ("goals", "interests", "hobbies", "music", "fears"):
                item = block(key.replace("_", " ").title(), character.get(key))
                if item:
                    parts.append(item)
            return "\n\n".join(parts)

        if title == "Skills and important details":
            parts = []
            for key in ("skills", "self_defense", "important_items", "access", "driving"):
                item = block(key.replace("_", " ").title(), character.get(key))
                if item:
                    parts.append(item)
            return "\n\n".join(parts)

        return ""


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

        current_answer = ""
        if self.interview_mode_var.get().strip() == "Character":
            current_answer = self._interview_character_current_answer(title)

        self.interview_current_text.configure(state="normal")
        self.interview_current_text.delete("1.0", "end")
        self.interview_current_text.insert(
            "1.0",
            current_answer or "(No canon is currently recorded for this question.)",
        )
        self.interview_current_text.configure(state="disabled")

        self.interview_answer_text.delete("1.0", "end")
        if current_answer:
            self.interview_answer_text.insert("1.0", current_answer)

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
        if self.__dict__.get("scene_planner_request_in_progress", False):
            messagebox.showwarning("Scene Planner", "Let the current planning request finish before starting another model task.")
            return
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
                self._show_copyable_error("Story Interview", "Age must be a whole number, or click Skip.")
                return
            if age < 0:
                self._show_copyable_error("Story Interview", "Age cannot be negative.")
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
                self._show_copyable_error(
                    "Story Interview",
                    "Select a GGUF model in the Writer tab first.",
                )
                return
            try:
                model = WriterEngine.validate_model(selected)
            except Exception as exc:
                self._show_copyable_error("Story Interview", str(exc))
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
            self._show_copyable_error("Story Interview", error)
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
            self._show_copyable_error("Story Interview", str(exc))
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

    def _on_main_section_shown(self, label):
        """Refresh the Writer's visible scene guidance when its section is opened."""
        if label == "Writer":
            self._refresh_writer_scene_guidance()

    def _refresh_writer_scene_guidance(self):
        """Show the current author Scene Idea or plan fallback without model calls."""
        if self.package is None or not hasattr(self, "writer_scene_idea_text"):
            return

        state = self.package.current_state
        chapter = int(state.get("chapter", 1) or 1)
        scene = int(state.get("scene", 1) or 1)
        plan = self.package.extra_json.get("writing_guidance.json", {})
        entry = self._chapter_scene_guidance(plan, chapter, scene) or {}
        if not isinstance(entry, dict):
            entry = {}
        saved_idea = str(entry.get("scene_idea", "") or "").strip()
        resolved_idea, resolved_source, idea_error = self._resolve_scene_idea(
            chapter, scene, entry
        )

        # If the author has edited the Scene Idea but has not saved yet, preview
        # that exact text. A blank edit is respected rather than silently restored.
        editor_matches_scene = (
            getattr(self, "scene_contract_editor_key", None) == (chapter, scene)
            and hasattr(self, "scene_idea_text")
        )
        editor_idea = (
            str(self.scene_idea_text.get("1.0", "end-1c") or "").strip()
            if editor_matches_scene
            else saved_idea
        )
        if editor_matches_scene:
            display_idea = editor_idea
            display_source = (
                resolved_source
                if editor_idea == resolved_idea
                else "editor"
            )
        else:
            display_idea = resolved_idea
            display_source = resolved_source

        is_unsaved = editor_matches_scene and editor_idea != saved_idea

        self.writer_scene_idea_text.configure(state="normal")
        self.writer_scene_idea_text.delete("1.0", "end")
        if display_idea:
            self.writer_scene_idea_text.insert("1.0", display_idea)
        self.writer_scene_idea_text.configure(state="disabled")

        if idea_error:
            status = f"Could not read STORY_PLAN.md for Chapter {chapter}, Scene {scene}: {idea_error}"
        elif not display_idea:
            status = (
                f"No saved Scene Idea or matching STORY_PLAN.md section exists for "
                f"Chapter {chapter}, Scene {scene}."
            )
        elif display_source == "plan":
            status = (
                f"Loaded planned Scene Idea from STORY_PLAN.md for Chapter {chapter}, Scene {scene}. "
                "Review it in Scene Contract; it is not saved until you save it or generate the contract."
            )
        elif is_unsaved:
            status = (
                f"Showing unsaved Scene Idea edits for Chapter {chapter}, Scene {scene}. "
                "They will be saved when you save or write the scene."
            )
        else:
            status = (
                f"Loaded Scene Idea for Chapter {chapter}, Scene {scene}. "
                "The original idea is included directly in the Writer prompt."
            )
        self.writer_scene_idea_status.configure(text=status)

        # This only refreshes the local UI. It never generates/replaces a
        # contract and does not overwrite the Writer's displayed status.
        self._build_scene_direction(update_status=False)

    def _build_scene_direction(self, *, update_status=True):
        if self.package is None:
            return

        state = self.package.current_state
        chapter = int(state.get("chapter", 1) or 1)
        scene = int(state.get("scene", 1) or 1)
        location = state.get("location", "")
        time_data = state.get("time", state.get("time_of_day", ""))
        cast = [str(name) for name in state.get("scene_cast", []) if str(name).strip()]
        situation = str(state.get("current_situation", "") or "").strip()

        # Use the same saved Scene Idea shown in the Writer preview. Its
        # explicit scene-wide metadata outranks the broader state snapshot.
        plan = self.package.extra_json.get("writing_guidance.json")
        guidance = (
            self._chapter_scene_guidance(plan, chapter, scene)
            if isinstance(plan, dict)
            else None
        )
        scene_idea = (
            str(guidance.get("scene_idea", "") or "").strip()
            if isinstance(guidance, dict)
            else ""
        )
        scene_header = extract_scene_header_metadata(scene_idea)

        if isinstance(location, dict):
            primary_location = str(location.get("primary", "") or "").strip()
        else:
            primary_location = str(location or "").strip()
        primary_location = scene_header.get("location", primary_location).strip()

        if isinstance(time_data, dict):
            time_text = str(time_data.get("period", "") or "").strip()
            exact = str(time_data.get("exact_time", "") or "").strip()
            if exact and exact != "not established":
                time_text = f"{time_text} ({exact})"
        else:
            time_text = str(time_data or "").strip()
        time_text = scene_header.get("time", time_text).strip()

        lines = [
            f"CHAPTER {chapter}, SCENE {scene}",
            f"Location: {primary_location or 'not established'}",
            f"Time: {time_text or 'not established'}",
            "Opening cast (present at scene start only; not the full scene cast): "
            + (", ".join(cast) if cast else "not established"),
            f"Current state: {situation or 'continue from the exact current state.'}",
            "Author-header precedence: An explicit Location or Time in the original Scene Idea's Scene header is authoritative for the planned scene and overrides a broader current-state label.",
            "Opening-cast rule: The current-state cast and physical positions describe only who is present at the start. They do not exclude later arrivals named in the original Scene Idea.",
            "Starting-state rule: The current situation above has already happened before this scene begins. Do not replay completed revelations or make characters rediscover facts explicitly stated there.",
            "Starting-knowledge rule: When the current situation says one character has already told, informed, warned, shown, or communicated a fact to another, the receiving character already knows that fact and dialogue should reflect that knowledge.",
            "State precedence: Current situation controls completed narrative facts and any physical details it explicitly states. Preserve stored physical continuity for details current situation does not address. Treat a physical-state detail as stale only when directly contradicted by current situation or an explicit action in this scene. Do not replace an established position, posture, contact, or movement merely because current situation does not repeat it.",
        ]

        # Physical state is the automatic handoff from the previous accepted
        # scene. Show only characters present at the opening; this is not a
        # restriction on later arrivals explicitly named in the Scene Idea.
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
                lines.append("Opening physical continuity (starting positions only):\n" + "\n".join(physical_lines))

        # Current situation defines where the scene starts. The current scene
        # plan defines what should happen from that starting point. Keep both:
        # suppressing the plan when a situation exists hides the actual scene
        # action and leaves the writer with only a starting-state description.
        current_plan_end = None
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
            # Required Beats are added to the runtime prompt only after
            # SceneContract.from_guidance filters out old model-generated
            # lists. Never copy the raw saved list into Scene Direction.

        module_endings = []
        module_beats = []

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

        lines.append(
            "Write natural prose only. Current state controls what has already happened, "
            "physical continuity, and character knowledge. Explicit Location and Time values "
            "from the original Scene Idea header control planned scene metadata. The opening "
            "cast is not the full scene cast; later arrivals specified by the Scene Idea must "
            "remain eligible to enter. The original plain-English Scene Idea controls requested "
            "events, order, and ending; generated direction is supporting context only."
        )

        self.writer_direction_text.delete("1.0", "end")
        self.writer_direction_text.insert("1.0", "\n".join(lines))
        if update_status:
            self.writer_status.configure(text="Scene direction built from the current state and active plan.")

    def _writer_system_prompt(self, files):
        base = """You write natural prose for an ongoing fictional novel.

Rules:
Author-defined canon rules supplied in the scene reference are hard constraints across the novel. Stable author writing guidance supplied there is also binding whenever relevant. Preserve the meaning of rules, avoidances, and creative permissions without turning permissive guidance into mandatory beats. Do not contradict, discard, or weaken author-defined constraints unless the author explicitly revises them. They outrank improvisation and optional planning guidance.

1. The original plain-English Scene Idea gives the intended direction, key intentions, and endpoint. Current story state controls what has already happened, physical continuity, and character knowledge. Generated scene direction and compact contract are supporting context only. Follow explicit boundaries and clearly labeled Planned Beats or Required Beats, but do not treat every sentence of the idea as a checklist; use creative judgment for natural execution.
2. The current_situation in scene_state.json is the exact narrative and physical starting point for this scene. Treat statements that are already completed there as already true before writing begins. Do not replay them as new events.
3. Treat explicit knowledge transfers already completed in current_situation as established knowledge at scene start. If it says one character has told, informed, warned, shown, or otherwise communicated a fact to another character, the receiving character already knows that fact.
4. Never make a character discover, ask whether, or react as though new something that the current_situation explicitly says they already know. They may ask for clarification or additional details that have not yet been established.
5. A character only knows what that character has established or naturally learns. Never transfer another character's knowledge. Knowing that an event happened is not the same as witnessing it: do not write sights, sounds, smells, dialogue, or actions as a character's personal memory unless the story establishes that the character witnessed them. When a character learned an event second-hand, frame it as what they were told or can reasonably infer, not as a first-hand sensory memory. When character_knowledge and current_situation appear to conflict, the explicit completed event in current_situation is the newer scene-start fact and controls the opening of the scene.
6. Begin from the exact physical and narrative starting state provided. Do not replay the previous scene. Preserve each explicit physical-continuity detail at the opening, including location, position, posture, contact, and movement, unless current_situation or the scene direction directly requires a change. Let the opening naturally orient the reader to important positions, posture, and contact using a simple concrete detail instead of vague staging, then move forward without repeatedly restating the setup. Silence in current_situation does not cancel physical continuity; treat stored physical details as stale only when there is a genuine contradiction. Prefer what characters say and do over narration when their interaction can carry the moment naturally.
7. Use the Scene Idea to understand the intended movement of the whole scene, its important moments, and its endpoint. Respect order when it is clearly meaningful, but do not mechanically turn descriptive prose into a sequence of checklist items. Complete clearly specified non-negotiable actions; leave ordinary actions, dialogue, gestures, pacing, and transitions to the writer. When the Scene Idea describes a broader stretch of time, interior development, or multiple dramatic moments, do not shrink the whole scene to the single action emphasized by a concise generated direction. When the Scene Idea names an explicit endpoint, including a time or passage-of-time boundary, continue through the intended development until that endpoint; do not stop at an earlier highlighted action. Let elapsed time pass naturally through relevant thoughts, small actions, and transitions. Only when no clear endpoint is stated may you choose a natural stopping point consistent with the idea. Do not pad the scene or invent consequential events merely to make it longer.
8. Let characters make their own choices when the scene gives them a choice.
9. Write clear, natural prose that fits the scene. Prefer concrete actions and specific details over elaborate metaphors, stacked adjectives, and repeated explanations of emotion. In quiet scenes, keep the description restrained. Don't repeat an action, staging detail, or feeling just to emphasize it. Avoid restating one feeling through several descriptions, metaphors, or interpretations. Let the story move forward naturally.
10. Let dialogue and interaction carry scenes whenever the situation allows. Use natural exchanges, interruptions, reactions, and small talk when they fit; do not summarize a conversation that would be stronger played out. When a character cannot speak or the moment is quiet, let actions, pauses, the other character's natural words, and selective description carry it. Do not force dialogue or impose a quota.
11. Give established characters room to breathe and be creative with their shared history. When two characters have known each other for years, they may naturally bring up made-up memories, old jokes, embarrassing moments, traditions, childhood adventures, school incidents, family stories, favorite places, failed plans, harmless arguments, nicknames, routines, or other little experiences they could realistically have shared. These do not need to be prewritten in the canon files. Invent them when they make the conversation feel lived-in and when they do not contradict hard canon, the timeline, character knowledge, established relationships, or explicit scene constraints.
12. Let those invented memories feel specific rather than generic. A useful memory often includes a concrete place, object, mistake, joke, sensory detail, or tiny disagreement that gives the characters something real to react to. Example: one character reminds the other about getting lost on a bike ride, burning pancakes during a sleepover, hiding from a neighbor's sprinkler, arguing over a ridiculous school-project idea, or laughing for ten minutes over an old inside joke. The exact memory is yours to invent when the story leaves room for it.
13. Do not treat creative shared memories as forbidden merely because they are not already written in the reference files. The canon files define hard facts and boundaries, not every harmless thing these characters have ever said or done. Prefer believable invention over sterile repetition of only documented facts.
14. Use invented memories as part of the scene, not as a lore dump. Let one memory spark a response, teasing, correction, laughter, disagreement, affection, or another small exchange, then allow the conversation to wander naturally back to what is happening now.
15. Do not turn shared history into a narrator summary such as "They had been friends for years" or "They talked about their childhood." Whenever practical, let the characters actually talk about one or two specific remembered moments instead. The goal is a lived relationship on the page, not a report about the relationship.
16. Let the rhythm vary naturally. Quiet observation, internal thought, description, or silence is appropriate when the moment calls for it; do not fill every pause with dialogue or description.
17. When an off-scene character is mentioned or referenced, use the supplied off-scene anchor and current scene state to preserve the person's established presence and current situation. Do not invent a different routine or explanation for why that person is where they are. Do not pull an off-scene character into the scene unless the current state or scene direction explicitly does so.
18. Use relevant_relationship_facts.json and supporting_people_context.json for established names and family/relationship roles when an off-scene person is mentioned. These references establish who people are related to, but they do not make those people physically present in the scene.
19. Do not invent consequential facts, motives, future events, hidden knowledge, or unnecessary story details.
20. Do not add unprompted ominous narration, hindsight, thematic warnings, or hints that something bad is about to happen when the current scene gives no reason for it. An ordinary scene should be allowed to remain ordinary. Do not contrast the characters' present happiness with a future event unless that contrast is explicitly part of the current scene direction or established context.
21. Respect privacy, dignity, and established character boundaries. Do not expose a character's private feelings, secrets, or limited knowledge without a valid in-story reason.
22. Ordinary affectionate nicknames are allowed when they fit the established relationship and moment. Do not use childizing terms such as "kid", "kiddo", "little girl", or similar terms for established adult characters unless that term is explicitly established.
23. Respect an explicit endpoint in the original Scene Idea, including a temporal boundary. The generated End/hard-stop is supporting guidance and must not shorten or distort that endpoint. Reach it without rushing past the scene's central moment or continuing into a later scene. If the idea leaves the endpoint open, a natural stopping point is allowed; do not make an incidental detail into an extra stopping condition.
24. Keep relationship-specific behavior consistent with established roles and dynamics. Avoid an incongruous relationship metaphor or a diminishing label for someone being comforted unless the story establishes that framing. When a relationship-specific gesture or exchange could be misunderstood, give one brief, natural cue that makes the relationship or gesture understandable, rather than explaining the same meaning or emotion again. don't turn gentle concern into insistence or pressure unless the scene calls for it.
25. If temporary per-novel working writer notes are supplied, treat them as tentative craft observations learned from accepted sections. Apply them selectively when useful; they are not canon, plot instructions, or superior to current author direction, scene contract, character knowledge, or continuity. Never import note content as an in-story fact.
26. Preserve the emotional cause-and-effect established by author direction and character continuity. When a familiar, trusted care gesture is established as reassuring, let it reassure the character unless the current scene explicitly establishes a different response. Do not invent distress caused by the gesture; connect renewed distress to the authored trigger or remembered event. Do not reverse an established emotional response just to add drama. When a character pauses to regain composure or becomes overwhelmed while trying to speak, and the scene and relationship support comfort, allow the other character to offer brief, natural reassurance, patient words, or a familiar calming gesture. Let the support respond to the person's actual distress without forcing it into every pause, repeating the same reassurance, or rushing the person past the difficult moment. Comfort may help the character continue without instantly removing their fear, grief, or struggle. Follow the scene-specific author direction and hard stop.
27. When a character states a direct request, preference, boundary, or need and another character acknowledges or agrees to it, keep subsequent actions consistent with it unless a clear in-story reason supports a different choice. Do not add an unmotivated contradiction as decorative atmosphere; for example, do not introduce music after agreeing to keep things quiet.
28. Output only natural story prose.
29. Any section labelled RETRIEVED HISTORICAL CONTINUITY ARCHIVE is a searchable excerpt from an earlier accepted scene, included because the current scene may need that detail. It is historical evidence, not the current state. The current saved state and explicit present-scene direction take precedence over stale archived descriptions. Use an archived detail only for the fact it supports; do not infer additional facts from it. If the needed historical detail cannot be found or the source is ambiguous, do not invent a memory or claim certainty. Characters may acknowledge that they do not remember or do not know.

"""
        parts = [base, "\nSCENE REFERENCE\n"]
        for name, content in files:
            parts.append(f"\n[{name}]\n{content}\n")
        parts.append("\nEND SCENE REFERENCE")
        return "\n".join(parts)

    def _toggle_prompt_trace(self):
        """Arm or cancel a one-scene prompt trace; tracing is otherwise off."""
        if getattr(self, "writer_generation_in_progress", False) or self.__dict__.get("focused_revision_in_progress", False):
            return
        self.prompt_trace_armed = not bool(getattr(self, "prompt_trace_armed", False))
        if self.prompt_trace_armed:
            self.writer_trace_button.configure(text="Trace Next Scene (Armed)")
            self.writer_trace_status.configure(
                text=(
                    "Armed for the next scene only. One local JSON trace will be saved "
                    "and synced to the private GitHub trace repository, replacing the "
                    "previous trace on its branch."
                )
            )
        else:
            self.writer_trace_button.configure(text="Trace Next Scene (Off)")
            self.writer_trace_status.configure(
                text="Off. No prompts are being recorded."
            )

    def _has_pending_generated_scene(self):
        """Whether the visible draft is waiting for the author's decision."""
        draft = str(self.__dict__.get("generated_scene", "") or "").strip()
        if not draft:
            return False

        output_widget = self.__dict__.get("writer_output_text")
        visible = (
            output_widget.get("1.0", "end-1c").strip()
            if output_widget is not None
            else draft
        )
        accepted = str(self.__dict__.get("accepted_scene", "") or "").strip()
        draft_context = self.__dict__.get("generated_scene_context")
        accepted_context = self.__dict__.get("accepted_scene_context")
        if draft_context != accepted_context and (draft_context is not None or accepted_context is not None):
            return True
        return visible.strip() != accepted

    def _update_writer_buttons(self):
        if self.__dict__.get("writer_start_button") is None:
            return

        child = getattr(self.writer_engine, "child", None)
        try:
            running = child is not None and child.isalive()
        except Exception:
            running = False
        has_scene = bool(str(getattr(self, "generated_scene", "") or "").strip())
        has_accepted = bool(str(getattr(self, "accepted_scene", "") or "").strip())
        has_pending = self._has_pending_generated_scene()
        has_patch = isinstance(self.pending_state_patch, dict)

        notes_updating = bool(self.__dict__.get("writer_notes_update_in_progress", False))
        contract_building = bool(getattr(self, "scene_contract_building", False))
        generating = bool(getattr(self, "writer_generation_in_progress", False))
        focused_revision = bool(self.__dict__.get("focused_revision_in_progress", False))
        busy = notes_updating or contract_building or generating or focused_revision

        self.writer_start_button.configure(
            state="disabled" if running or busy else "normal"
        )
        self.writer_stop_button.configure(
            state="normal" if running and not notes_updating and not contract_building and not focused_revision else "disabled"
        )
        self.writer_write_button.configure(
            state="normal" if running and self.package and not has_pending and not busy else "disabled"
        )
        self.writer_save_draft_button.configure(
            state="normal" if has_pending and self.package and not busy else "disabled"
        )
        self.writer_accept_button.configure(
            state="normal" if has_pending and self.package and not busy else "disabled"
        )
        self.writer_reject_button.configure(
            state="normal" if has_pending and self.package and not busy else "disabled"
        )
        if self.__dict__.get("writer_regenerate_button") is not None:
            self.writer_regenerate_button.configure(
                state="normal" if running and has_pending and self.package and not busy else "disabled"
            )
        if self.__dict__.get("writer_focus_change_button") is not None:
            self.writer_focus_change_button.configure(
                state="normal" if running and has_pending and self.package and not busy else "disabled"
            )
        if self.__dict__.get("writer_undo_focused_change_button") is not None:
            history = self.__dict__.get("focused_revision_history", [])
            self.writer_undo_focused_change_button.configure(
                state="normal" if has_pending and history and not busy else "disabled"
            )
        if self.__dict__.get("writer_revision_request_entry") is not None:
            self.writer_revision_request_entry.configure(
                state="normal" if running and has_pending and self.package and not busy else "disabled"
            )
        if self.__dict__.get("writer_clear_context_button") is not None:
            self.writer_clear_context_button.configure(
                state="normal" if running and self.package and not busy else "disabled"
            )
        if self.__dict__.get("writer_trace_button") is not None:
            self.writer_trace_button.configure(
                state="disabled" if generating or focused_revision or contract_building or notes_updating else "normal",
                text="Trace Next Scene (Armed)" if getattr(self, "prompt_trace_armed", False) else "Trace Next Scene (Off)",
            )
        analysis_in_progress = bool(self.__dict__.get("state_analysis_in_progress", False))
        if self.__dict__.get("writer_reload_scene_button") is not None:
            self.writer_reload_scene_button.configure(
                state="normal" if self.package and not busy and not analysis_in_progress else "disabled"
            )
        self.writer_analyze_button.configure(
            state="normal" if has_accepted and self.package and not busy and not analysis_in_progress else "disabled"
        )
        self.writer_apply_state_button.configure(
            state="normal" if has_patch and self.package and not notes_updating and not analysis_in_progress else "disabled"
        )

        if focused_revision:
            status_text = "Applying a focused change to the current draft..."
        elif generating:
            status_text = "Writing a new scene draft..."
        elif contract_building:
            status_text = "Using the local model to build Scene Direction..."
        elif notes_updating:
            status_text = "Updating this novel's temporary writing notes from accepted scenes..."
        elif running and self.writer_engine.model_path:
            status_text = f"Writer running: {self.writer_engine.model_path.name}"
        else:
            status_text = "Writer stopped."
        self.writer_status.configure(text=status_text)

    def _start_writer(self, skip_notes_seed=False):
        if self.__dict__.get("scene_planner_request_in_progress", False):
            messagebox.showwarning("Scene Planner", "Let the current planning request finish before starting another model task.")
            return
        if getattr(self, "scene_contract_building", False):
            return
        if self.__dict__.get("writer_notes_update_in_progress", False):
            return
        if self.package is None:
            self._show_copyable_error("Writer", "Open or create a novel first.")
            return

        model = self.writer_model_var.get().strip()
        if not model:
            self._show_copyable_error("Writer", "Select a GGUF model first.")
            return

        self._save()
        if self.dirty:
            return

        if not skip_notes_seed and self._start_initial_writer_notes_scan(model):
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

    def _start_initial_writer_notes_scan(self, model):
        """Seed a blank notebook from a chapter of existing accepted prose."""
        if self.package is None or self.package.path is None:
            return False

        package_path = Path(self.package.path)
        notes = normalize_writer_notes(getattr(self.package, "writer_notes", {}))
        if notes.get("learned_notes") or notes.get("reviewed_scenes"):
            return False

        seed_scenes = collect_initial_seed_scenes(package_path)
        if len(seed_scenes) < 2:
            return False

        available_labels = [item["scene"] for item in seed_scenes]
        scene_label = available_labels[-1]
        review_prompt = build_writer_notes_review_prompt(notes, seed_scenes)
        self.writer_notes_update_in_progress = True
        self._update_writer_buttons()
        self.writer_status.configure(
            text="Scanning accepted scenes for recurring writing-craft patterns before starting the writer..."
        )

        def work():
            updated_notes = None
            added_count = 0
            error = None
            engine = self.writer_engine
            was_running = False
            old_system_prompt = ""
            try:
                with engine.lock:
                    was_running = engine.child is not None and engine.child.isalive()
                    old_system_prompt = str(engine.system_prompt or "")
                    try:
                        engine.reset_context(Path(model), WRITER_NOTES_SYSTEM_PROMPT)
                        response = engine.generate(review_prompt)
                        suggestions = parse_writer_notes_response(response)
                        updated_notes, added_count = merge_writer_notes(
                            notes,
                            suggestions,
                            available_labels,
                            scene_label,
                        )
                        # Every sampled scene was considered, even if no note
                        # was strong enough to keep. This prevents repeated scans.
                        updated_notes["reviewed_scenes"] = list(dict.fromkeys(
                            updated_notes.get("reviewed_scenes", []) + available_labels
                        ))[-100:]
                        save_writer_notes(package_path, updated_notes)
                    finally:
                        if was_running and old_system_prompt:
                            engine.reset_context(Path(model), old_system_prompt)
                        else:
                            engine.stop()
            except Exception as exc:
                error = str(exc)

            try:
                self.after(
                    0,
                    lambda: self._finish_initial_writer_notes_scan(
                        package_path, updated_notes, added_count, error, scene_label
                    ),
                )
            except tk.TclError:
                pass

        threading.Thread(target=work, daemon=True).start()
        return True

    def _finish_initial_writer_notes_scan(
        self, package_path, notes, added_count, error, scene_label
    ):
        self.writer_notes_update_in_progress = False
        package_matches = (
            self.package is not None
            and self.package.path is not None
            and Path(self.package.path).resolve() == Path(package_path).resolve()
        )
        if notes is not None and package_matches:
            self.package.writer_notes = notes

        self._update_writer_buttons()
        if error:
            self._chat(
                "Builder",
                f"Initial writing-notes scan skipped for {scene_label}: {error}. "
                "The writer will start without seeded notes.",
            )
        elif added_count:
            self._chat(
                "Builder",
                f"Initial writing-notes scan reviewed the earliest complete chapter ending at "
                f"{scene_label} and added {added_count} recurring craft observation(s).",
            )
        else:
            self._chat(
                "Builder",
                f"Initial writing-notes scan reviewed the earliest complete chapter ending at "
                f"{scene_label}. No recurring craft lesson was strong enough to add.",
            )

        # The scan is a preflight pass. Continue with fresh prompt content after
        # it finishes, but do not invoke the seed step a second time in this call.
        if package_matches and not self._closing:
            self._start_writer(skip_notes_seed=True)
        else:
            self._update_writer_buttons()

    def _finish_writer_start(self, error):
        if error:
            self._show_copyable_error("Writer", error)
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

        if not self._ask_yes_no(
            "Clear Writer Context",
            "Clear the active model's conversation context and rebuild it from the current saved novel files?\n\n"
            "This does not delete manuscript text or reset Current State. Any helpful details held only in the model's "
            "temporary context will be cleared. Continue?",
        ):
            return

        self._save()
        if self.dirty:
            return

        model = self.writer_engine.model_path
        if model is None:
            self._show_copyable_error("Writer", "No active writer model is available.")
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
            self._show_copyable_error("Writer", error)
            self._update_writer_buttons()
            return

        self.writer_status.configure(
            text="Writer context cleared and rebuilt from the current story state."
        )
        self._update_writer_buttons()

    def _write_next_scene(self, replacing_draft=False):
        if getattr(self, "scene_contract_building", False):
            self.writer_status.configure(
                text="Wait for Scene Contract generation to finish before writing the next scene."
            )
            return
        if self.__dict__.get("writer_notes_update_in_progress", False):
            self.writer_status.configure(
                text="The novel's writing notes are being updated from the last accepted scene."
            )
            return
        if self.package is None:
            self._show_copyable_error("Writer", "Open or create a novel first.")
            return
        if getattr(self, "scene_contract_building", False):
            messagebox.showwarning(
                "Writer",
                "Wait for the current scene contract to finish before generating prose.",
            )
            return
        if getattr(self, "writer_generation_in_progress", False) or self.__dict__.get("focused_revision_in_progress", False):
            messagebox.showwarning("Writer", "A Writer task is already running.")
            return
        if self._has_pending_generated_scene() and not replacing_draft:
            messagebox.showinfo(
                "Review Current Draft",
                "There is already an unaccepted scene draft. Accept it, make a focused change, "
                "or use Regenerate Scene to replace it.",
            )
            return

        direction = self.writer_direction_text.get("1.0", "end-1c").strip()
        if not direction:
            direction = "Write the next scene naturally from the current story state."

        self._save()
        if self.dirty:
            return

        self.writer_write_button.configure(state="disabled")
        self.writer_status.configure(text="Preparing scene context...")

        chapter = int(self.package.current_state.get("chapter", 1) or 1)
        scene = int(self.package.current_state.get("scene", 1) or 1)
        contract = self._scene_contract(chapter, scene)

        current_state = json.loads(
            json.dumps(self.package.current_state, ensure_ascii=False)
        )
        # Capture the exact target before background generation starts.
        self.writer_generation_context = (chapter, scene)
        self.writer_generation_start_state = json.loads(
            json.dumps(current_state, ensure_ascii=False)
        )
        self.writer_generation_in_progress = True
        self._update_writer_buttons()

        files = self._writer_package_files()
        system_prompt = self._writer_system_prompt(files)
        model = self.writer_engine.model_path
        author_guidance = self._author_writing_guidance()
        writer_context = SceneContract.writer_prompt_context(direction, contract)
        historical_archive = {
            "snippets": [],
            "text": "",
            "characters": 0,
            "estimated_tokens": 0,
        }
        archive_search_error = ""
        try:
            if self.package.path is not None:
                archive_character_names = list(scene_cast_names) if "scene_cast_names" in locals() else [
                    str(name).strip()
                    for name in current_state.get("scene_cast", [])
                    if str(name).strip()
                ]
                character_cards = getattr(self.package, "characters", {})
                if isinstance(character_cards, dict):
                    for filename, data in character_cards.items():
                        name = str(data.get("name", "") or "").strip() if isinstance(data, dict) else ""
                        if not name:
                            name = Path(str(filename)).stem
                        archive_character_names.append(name)
                historical_archive = ManuscriptManager(Path(self.package.path)).search_historical_context(
                    "\n".join([
                        writer_context,
                        author_guidance,
                        str(current_state.get("current_situation", "") or ""),
                    ]),
                    before_chapter=chapter,
                    before_scene=scene,
                    character_names=archive_character_names,
                    limit=4,
                    max_chars=2400,
                )
        except Exception as exc:
            # Archive retrieval is advisory; an archive read failure must not
            # block writing or change the canon/state ledger.
            archive_search_error = str(exc)

        archive_prompt = ""
        if historical_archive.get("text"):
            archive_prompt = (
                "\n\nRETRIEVED HISTORICAL CONTINUITY ARCHIVE (READ ONLY; NOT CURRENT STATE):\n"
                "The following excerpts come from earlier accepted manuscript sections. "
                "They were retrieved because their wording overlaps the current scene direction. "
                "Use them only for supported historical details. The current saved state and scene "
                "direction outrank any outdated physical or situational detail. Do not infer anything "
                "that is not stated in an excerpt.\n\n"
                + historical_archive["text"]
            )

        prompt_parts = [
            writer_context,
            archive_prompt,
            "\n\n",
            "SCENE BOUNDARY:\n",
            "The original plain-English Scene Idea defines intended actions, important moments, and endpoint. It is not a line-by-line wording checklist, but concrete actions and objects specified as intended choices must keep their identity; do not replace one with a materially different alternative (a bubble bath is not a shower). Preserve distinctive details that define an intended action and the stated history or relationships that give an object meaning; do not treat them as disposable decoration. If the idea phrases an action as optional, preserve that choice instead of making it a new requirement. Current story state controls what has already happened, physical continuity, and character knowledge; generated direction and contract are secondary hints. Do not replay completed events. Preserve established opening position/contact unless this scene changes them. Use creative freedom for how actions unfold, dialogue, gestures, pacing, transitions, and connective actions.\n\n",
            "Write the scene now. Output only the prose."
        ]
        base_prompt = "".join(prompt_parts)
        context_budget = context_size_report(system_prompt + base_prompt)
        reduction_percent = float(context_metrics.get("detail_context_reduction_percent", 0) or 0)
        self.writer_status.configure(
            text=(
                f"Writing scene... approximately {context_budget['estimated_tokens']:,} prompt tokens "
                f"(character/notes pruning: {reduction_percent:.1f}%; "
                f"historical excerpts: {len(historical_archive.get('snippets', []))})."
            )
        )
        context_metrics = dict(getattr(self, "writer_last_context_metrics", {}) or {})
        context_metrics.update({
            "assembled_prompt_characters": context_budget["characters"],
            "assembled_prompt_estimated_tokens": context_budget["estimated_tokens"],
            "historical_archive_characters": int(historical_archive.get("characters", 0) or 0),
            "historical_archive_estimated_tokens": int(historical_archive.get("estimated_tokens", 0) or 0),
            "historical_archive_snippets": len(historical_archive.get("snippets", [])),
            "archive_search_error": archive_search_error,
        })
        self.writer_last_context_metrics = context_metrics

        prompt_trace = None
        if getattr(self, "prompt_trace_armed", False):
            prompt_trace = PromptTrace(
                chapter=chapter,
                scene=scene,
                model_path=model,
                current_state=current_state,
                reference_files=files,
                contract=contract,
                scene_direction=direction,
                author_guidance=author_guidance,
                system_prompt=system_prompt,
            )
            self.prompt_trace_armed = False
            self.active_prompt_trace = prompt_trace
            self.writer_engine.prompt_trace = prompt_trace
            prompt_trace.record_event(
                "scene_generation_started",
                chapter=chapter,
                scene=scene,
                max_attempts=1,
            )
            self.writer_trace_button.configure(text="Trace Next Scene (Off)", state="disabled")
            self.writer_trace_status.configure(
                text=(
                    "Capturing this scene only. The local trace will be overwritten and "
                    "synced to the private GitHub trace repository when finished."
                )
            )

        def work():
            answer = ""
            trace_result = None
            error = None
            completion_notice = ""
            try:
                if model is None:
                    raise RuntimeError("The Writer model is not available.")

                self.writer_engine.reset_context(model, system_prompt)
                if prompt_trace is not None:
                    prompt_trace.record_event(
                        "writer_attempt_started",
                        attempt=1,
                        max_attempts=1,
                        is_focused_revision=False,
                        prompt_characters=len(base_prompt),
                    )
                answer, completion_notice = generate_scene_with_completion_check(
                    engine=self.writer_engine,
                    model_path=model,
                    writer_system_prompt=system_prompt,
                    initial_prompt=base_prompt,
                    scene_context=writer_context,
                    contract=contract,
                    current_state=current_state,
                    author_guidance=author_guidance,
                )
                if prompt_trace is not None:
                    prompt_trace.record_event(
                        "scene_completion_check",
                        notice=completion_notice,
                        response_characters=len(answer),
                    )
                    prompt_trace.record_event(
                        "writer_attempt_finished",
                        attempt=1,
                        status="generated_for_author_review",
                        response_characters=len(answer),
                    )
            except Exception as exc:
                error = str(exc)
            finally:
                if prompt_trace is not None:
                    trace_path = prompt_trace.finish(
                        status="error" if error else "completed",
                        error=error,
                        validation_warning=None,
                    )
                    upload_result = None
                    if trace_path is not None and not prompt_trace.save_error:
                        try:
                            upload_result = upload_prompt_trace(trace_path)
                        except Exception as exc:
                            upload_result = {"ok": False, "error": str(exc)}
                    trace_result = {
                        "path": str(trace_path) if trace_path is not None else None,
                        "error": prompt_trace.save_error,
                        "upload": upload_result,
                    }
                    if getattr(self.writer_engine, "prompt_trace", None) is prompt_trace:
                        self.writer_engine.prompt_trace = None
            self.after(
                0,
                lambda: self._finish_generated_scene(
                    answer, error, trace_result, completion_notice
                ),
            )

        self.writer_thread = threading.Thread(target=work, daemon=True)
        self.writer_thread.start()
    def _finish_generated_scene(
        self, answer, error, trace_result=None, completion_notice=""
    ):
        target = getattr(self, "writer_generation_context", None)
        if trace_result is not None:
            self.active_prompt_trace = None
            if self.__dict__.get("writer_trace_button") is not None:
                self.writer_trace_button.configure(
                    text="Trace Next Scene (Armed)" if getattr(self, "prompt_trace_armed", False) else "Trace Next Scene (Off)"
                )
            if self.__dict__.get("writer_trace_status") is not None:
                upload = trace_result.get("upload") or {}
                if trace_result.get("path") and upload.get("ok"):
                    self.writer_trace_status.configure(
                        text=(
                            f"Trace saved locally and synced to private GitHub: {upload.get('url')}. "
                            "The next trace replaces it."
                        )
                    )
                elif trace_result.get("path"):
                    upload_error = upload.get("error") or "GitHub sync did not run."
                    self.writer_trace_status.configure(
                        text=(
                            f"Trace saved locally at {trace_result['path']}; "
                            f"private GitHub sync failed: {upload_error}"
                        )
                    )
                else:
                    self.writer_trace_status.configure(
                        text="Scene trace could not be saved: " + str(
                            trace_result.get("error") or "unknown file error"
                        )
                    )

        start_state = getattr(self, "writer_generation_start_state", None)
        self.writer_generation_in_progress = False
        self.writer_generation_context = None
        self.writer_generation_start_state = None

        if error:
            preserved_draft = bool(str(answer or "").strip())
            if preserved_draft:
                self.generated_scene = str(answer).strip()
                self.generated_scene_context = target or (
                    int(self.package.current_state.get("chapter", 1) or 1),
                    int(self.package.current_state.get("scene", 1) or 1),
                )
                self.generated_scene_start_state = start_state
                self.focused_revision_history = []
                self.writer_output_text.delete("1.0", "end")
                self.writer_output_text.insert("1.0", self.generated_scene)
            self._show_copyable_error(
                "Writer",
                error,
                summary="Scene generation encountered an error. Any draft remains available for your review.",
            )
            self._update_writer_buttons()
            if preserved_draft:
                self.writer_status.configure(
                    text="A draft was produced before the error. It remains available for your review."
                )
            elif self._has_pending_generated_scene():
                self.writer_status.configure(
                    text="Regeneration failed. Your previous draft remains unchanged."
                )
            else:
                self.writer_status.configure(
                    text="Scene generation failed. No scene was accepted or saved."
                )
            return

        self.writer_draft_saved_text = None
        self.generated_scene = str(answer or "").strip()
        self.generated_scene_context = target or (
            int(self.package.current_state.get("chapter", 1) or 1),
            int(self.package.current_state.get("scene", 1) or 1),
        )
        self.generated_scene_start_state = start_state or json.loads(
            json.dumps(self.package.current_state, ensure_ascii=False)
        )
        self.focused_revision_history = []
        self.writer_output_text.delete("1.0", "end")
        self.writer_output_text.insert("1.0", self.generated_scene)
        if self.__dict__.get("writer_revision_request_entry") is not None:
            self.writer_revision_request_entry.delete("1.0", "end")
        self._update_writer_buttons()
        status_text = (
            f"Draft generated for Chapter {self.generated_scene_context[0]}, "
            f"Scene {self.generated_scene_context[1]}. Review it, request a focused change, "
            "regenerate it, or accept it when you are satisfied."
        )
        if completion_notice:
            status_text += "\n\n" + completion_notice
        self.writer_status.configure(text=status_text)
    def _regenerate_generated_scene(self):
        if not self._has_pending_generated_scene():
            return
        if getattr(self, "writer_generation_in_progress", False) or self.__dict__.get("focused_revision_in_progress", False):
            return
        if not self._ask_yes_no(
            "Regenerate Scene",
            "Generate a fresh version of this scene? The current draft will remain available "
            "if regeneration fails, but will be replaced if the new draft succeeds.",
        ):
            return
        self._write_next_scene(replacing_draft=True)

    def _apply_focused_scene_change(self):
        if self.package is None or not self._has_pending_generated_scene():
            return
        if getattr(self, "writer_generation_in_progress", False) or self.__dict__.get("focused_revision_in_progress", False):
            return

        original = self._writer_editor_prose()
        request = self.writer_revision_request_entry.get("1.0", "end-1c").strip()
        if not request:
            messagebox.showwarning("Focused Change", "Describe the specific change you want.")
            return
        if not original:
            messagebox.showwarning("Focused Change", "There is no scene draft to revise.")
            return

        engine = self.writer_engine
        model = getattr(engine, "model_path", None)
        child = getattr(engine, "child", None)
        try:
            running = child is not None and child.isalive()
        except Exception:
            running = False
        if model is None or not running:
            messagebox.showwarning("Focused Change", "Start the Writer model before requesting a focused change.")
            return
        original_system_prompt = str(getattr(engine, "system_prompt", "") or "")
        self.focused_revision_in_progress = True
        self.writer_status.configure(text="Preparing a focused edit...")
        self._update_writer_buttons()

        def work():
            revised = None
            error = None
            restore_error = None
            try:
                # A short task-specific prompt keeps the exact draft and patch inside
                # the local model's context window without repeating the full novel bible.
                engine.reset_context(model, FOCUSED_REVISION_SYSTEM_PROMPT)
                correction = None
                previous_response = None
                last_error = None
                for _attempt in range(2):
                    response = engine.generate(
                        build_focused_revision_prompt(
                            original,
                            request,
                            correction=correction,
                            previous_response=previous_response,
                        )
                    )
                    try:
                        revised = apply_focused_replacement(original, response)
                        last_error = None
                        break
                    except ValueError as exc:
                        last_error = str(exc)
                        correction = last_error
                        previous_response = response
                if revised is None:
                    raise ValueError(
                        "The model could not produce a safe, exact-text edit after two attempts. "
                        + str(last_error or "")
                    )
            except Exception as exc:
                error = str(exc)
            finally:
                try:
                    engine.reset_context(model, original_system_prompt)
                except Exception as exc:
                    restore_error = str(exc)

            self.after(
                0,
                lambda: self._finish_focused_scene_change(
                    original, revised, error, restore_error
                ),
            )

        self.writer_thread = threading.Thread(target=work, daemon=True)
        self.writer_thread.start()

    def _finish_focused_scene_change(self, original, revised, error, restore_error=None):
        self.focused_revision_in_progress = False
        if revised is not None and self._writer_editor_prose() != original:
            error = (
                "The visible draft changed while the focused edit was running. "
                "No model edit was applied; your current text was left untouched."
            )

        if error or revised is None:
            self._update_writer_buttons()
            self.writer_status.configure(
                text="Focused change was not applied. Your draft remains unchanged."
            )
            self._show_copyable_error(
                "Focused Change",
                "No text was changed. Review the request and try again.\n\n"
                + str(error or "The model returned no usable replacement."),
            )
            return

        history = getattr(self, "focused_revision_history", None)
        if not isinstance(history, list):
            history = []
            self.focused_revision_history = history
        history.append(original)
        self.generated_scene = revised
        self.writer_draft_saved_text = None
        self.writer_output_text.delete("1.0", "end")
        self.writer_output_text.insert("1.0", revised)
        self.writer_revision_request_entry.delete("1.0", "end")
        self._update_writer_buttons()
        if restore_error:
            self.writer_status.configure(
                text=(
                    "Focused change applied. The draft is preserved, but the Writer session "
                    "could not be restored. Restart the Writer before generating or revising again."
                )
            )
            self._show_copyable_error(
                "Focused Change",
                "The focused edit was applied safely, but StoryBuilder could not restore the normal Writer session. "
                "Restart the Writer before the next model task.\n\n" + str(restore_error),
            )
        else:
            self.writer_status.configure(
                text="Focused change applied to one exact passage. All other draft text was preserved; review it again."
            )

    def _undo_focused_scene_change(self):
        history = getattr(self, "focused_revision_history", [])
        if not history or not self._has_pending_generated_scene():
            return
        previous = history.pop()
        self.generated_scene = previous
        self.writer_draft_saved_text = None
        self.writer_output_text.delete("1.0", "end")
        self.writer_output_text.insert("1.0", previous)
        self._update_writer_buttons()
        self.writer_status.configure(
            text="Undid the last focused change. The previous draft text has been restored."
        )

    def _reject_generated_scene(self):
        if not self.generated_scene.strip():
            return

        if not self._ask_yes_no(
            "Reject Scene",
            "Discard this unaccepted draft or undo edits to the accepted scene? The manuscript file will not be deleted.",
        ):
            return

        accepted = str(self.__dict__.get("accepted_scene", "") or "").strip()
        self.generated_scene = accepted
        self.focused_revision_history = []
        if self.__dict__.get("writer_revision_request_entry") is not None:
            self.writer_revision_request_entry.delete("1.0", "end")
        self.writer_output_text.delete("1.0", "end")
        if accepted:
            self.writer_output_text.insert("1.0", accepted)
        else:
            self.generated_scene_context = None
            self.generated_scene_start_state = None
        self._update_writer_buttons()
        self.writer_status.configure(
            text=(
                "Restored the accepted scene. The manuscript was not changed."
                if accepted
                else "Scene rejected. The current story state and accepted manuscript were not changed."
            ),
        )
    def _save_generated_draft(self):
        if not self.package:
            return

        prose = self._writer_editor_prose()
        if not prose:
            return

        if self.package.path is None:
            messagebox.showwarning(
                "Writer",
                "Save the novel package with Save As / Export before saving a manuscript draft.",
            )
            return

        state = self.package.current_state
        fallback_key = (
            int(state.get("chapter", 1) or 1),
            int(state.get("scene", 1) or 1),
        )
        context = getattr(self, "generated_scene_context", None) or fallback_key
        try:
            chapter, scene = int(context[0]), int(context[1])
            path = ManuscriptManager(self.package.path).save_draft(chapter, scene, prose)
            self.generated_scene = prose
            self.generated_scene_context = (chapter, scene)
            self.writer_draft_saved_text = prose
            self._refresh_manuscript()
            messagebox.showinfo(
                "Writer",
                f"Draft saved for Chapter {chapter}, Scene {scene}:\n\n{path}",
            )
        except Exception as exc:
            self._show_copyable_error("Writer", str(exc))
    def _accept_generated_scene(self):
        if not self.package or not self.generated_scene.strip():
            return
        if self.package.path is None:
            messagebox.showwarning(
                "Writer",
                "Save the novel package with Save As / Export before accepting a manuscript scene.",
            )
            return

        prose = self._writer_editor_prose()
        if not prose:
            messagebox.showwarning("Writer", "There is no scene text to accept.")
            return
        if self.__dict__.get("focused_revision_in_progress", False):
            return

        state = self.package.current_state
        current_key = (
            int(state.get("chapter", 1) or 1),
            int(state.get("scene", 1) or 1),
        )
        context = getattr(self, "generated_scene_context", None) or current_key
        try:
            chapter, scene = int(context[0]), int(context[1])
        except (TypeError, ValueError, IndexError):
            chapter, scene = current_key

        if (chapter, scene) != current_key:
            if prose != str(getattr(self, "accepted_scene", "") or "").strip():
                if not self._save_unsaved_writer_draft():
                    return
            messagebox.showwarning(
                "Writer",
                f"This draft belongs to Chapter {chapter}, Scene {scene}, but the current state is "
                f"Chapter {current_key[0]}, Scene {current_key[1]}. It was not accepted under the wrong scene number. "
                "Return to its original scene or load the saved draft from Manuscript.",
            )
            return

        start_state = getattr(self, "generated_scene_start_state", None)
        if isinstance(start_state, dict) and start_state != state:
            if prose != str(getattr(self, "accepted_scene", "") or "").strip():
                if not self._save_unsaved_writer_draft():
                    return
            messagebox.showwarning(
                "Writer",
                "The current story state changed after this prose was generated. The scene was not accepted against "
                "a different starting state. Restore the scene's starting state or rebuild Writer direction and generate again.",
            )
            return

        self.generated_scene = prose
        try:
            manager = ManuscriptManager(self.package.path)
            path = manager.scene_path(chapter, scene)
            if path.exists():
                replace = self._ask_yes_no(
                    "Replace Existing Scene",
                    f"{path.name} already exists. Replace it with this accepted scene?"
                )
                if not replace:
                    return
            path = manager.save_scene(chapter, scene, prose)
            manager.save_state_before(
                chapter,
                scene,
                json.loads(json.dumps(start_state if isinstance(start_state, dict) else state, ensure_ascii=False)),
            )
            self.accepted_scene = prose
            self.accepted_scene_context = (chapter, scene)
            self.focused_revision_history = []
            self.generated_scene_context = (chapter, scene)
            self.pending_state_patch = None
            self.writer_state_preview.delete("1.0", "end")
            if "writer_state_diff_preview" in self.__dict__:
                self.writer_state_diff_preview.configure(state="normal")
                self.writer_state_diff_preview.delete("1.0", "end")
                self.writer_state_diff_preview.configure(state="disabled")
            self._refresh_manuscript()
            self._chat("Builder", f"Accepted Chapter {chapter}, Scene {scene} and saved it to {path}.")
            self._update_writer_buttons()
            self.writer_status.configure(
                text="Scene accepted. You can now analyze it for state changes."
            )
        except Exception as exc:
            self._show_copyable_error("Writer", str(exc))
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

    @staticmethod
    def _set_generated_contract_text(widget, value: str) -> None:
        """Update a display-only contract field without making it user-editable."""
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        if value:
            widget.insert("1.0", value)
        widget.configure(state="disabled")

    @staticmethod
    def _clear_stale_generated_scene_contract_fields(entry: dict) -> None:
        """Drop obsolete hidden contract/state hints after the author rebuilds from the idea."""
        for key in (
            "required_beats",
            "boundaries",
            "required_facts",
            "required_sequence",
            "forbidden",
            "forbidden_details",
            "required_events",
            "do_not_advance",
            "hard_stop",
            "max_attempts",
            "state_after",
        ):
            entry.pop(key, None)

    def _clear_scene_contract_editor(self):
        """Clear the idea and generated fields while keeping generated fields read-only."""
        if hasattr(self, "scene_idea_text"):
            self.scene_idea_text.delete("1.0", "end")
        if hasattr(self, "scene_contract_direction_text"):
            self._set_generated_contract_text(self.scene_contract_direction_text, "")
        if hasattr(self, "scene_contract_end_text"):
            self._set_generated_contract_text(self.scene_contract_end_text, "")
        for widget in getattr(self, "scene_contract_texts", {}).values():
            self._set_generated_contract_text(widget, "")
        if hasattr(self, "scene_contract_attempts_var"):
            self.scene_contract_attempts_var.set("3")

    def _scene_contract_editor_has_content(self) -> bool:
        if hasattr(self, "scene_idea_text") and self.scene_idea_text.get("1.0", "end-1c").strip():
            return True
        if hasattr(self, "scene_contract_direction_text") and self.scene_contract_direction_text.get("1.0", "end-1c").strip():
            return True
        if hasattr(self, "scene_contract_end_text") and self.scene_contract_end_text.get("1.0", "end-1c").strip():
            return True
        for widget in getattr(self, "scene_contract_texts", {}).values():
            if widget.get("1.0", "end-1c").strip():
                return True
        return False

    def _load_current_scene_contract(self):
        """Reload the saved contract, warning before discarding editor contents."""
        if self.package is None:
            return

        if self._scene_contract_editor_has_content():
            if not self._ask_yes_no(
                "Reload Saved Contract",
                "Discard unsaved Scene Contract editor changes and reload the saved version? "
                "The saved novel data will not be changed.",
            ):
                return

        self._clear_scene_contract_editor()
        self.scene_contract_status.configure(
            text="Loading saved contract..."
        )
        self.update_idletasks()
        self._refresh_scene_contract_editor()
        self.scene_contract_status.configure(
            text="Loaded the saved contract for the current scene. You can edit it or replace it with a new draft.",
        )

    def _reload_saved_scene_idea(self):
        """Reload the saved Scene Idea, or the matching plan section if none is saved."""
        if self.package is None or not hasattr(self, "scene_idea_text"):
            return

        if getattr(self, "scene_contract_building", False) or getattr(
            self, "writer_generation_in_progress", False
        ):
            messagebox.showwarning(
                "Reload Scene Idea",
                "Wait for contract building or scene generation to finish before reloading the Scene Idea.",
            )
            return

        state = self.package.current_state
        chapter = int(state.get("chapter", 1) or 1)
        scene = int(state.get("scene", 1) or 1)
        active_key = (chapter, scene)
        editor_key = getattr(self, "scene_contract_editor_key", None) or active_key
        if editor_key != active_key:
            self._refresh_scene_contract_editor()
            messagebox.showwarning(
                "Reload Scene Idea",
                "The current state and Scene Contract editor were out of sync. I reloaded the current scene. "
                "Please check its Scene Idea before continuing.",
            )
            return

        entry = self._editable_scene_guidance_entry(chapter, scene, create=False) or {}
        loaded_idea, source, error = self._resolve_scene_idea(chapter, scene, entry)
        current_idea = self.scene_idea_text.get("1.0", "end-1c")
        if current_idea.strip() != loaded_idea.strip():
            if source == "saved":
                source_label = "the saved Scene Idea"
            elif source == "plan":
                source_label = "the matching scene section from STORY_PLAN.md"
            elif source == "error":
                source_label = "a blank field because STORY_PLAN.md could not be read"
            else:
                source_label = "a blank field because no saved idea or matching plan section was found"
            if not self._ask_yes_no(
                "Clear & Reload Scene Idea",
                f"Discard the current unsaved Scene Idea edits and reload {source_label} for "
                f"Chapter {chapter}, Scene {scene}?\n\n"
                "The saved novel data and generated contract fields will not be changed.",
            ):
                return

        self.scene_idea_text.delete("1.0", "end")
        if loaded_idea:
            self.scene_idea_text.insert("1.0", loaded_idea)

        if source == "saved":
            status = f"Reloaded the saved Scene Idea for Chapter {chapter}, Scene {scene}."
        elif source == "plan":
            status = (
                f"Loaded the planned Scene Idea from STORY_PLAN.md for Chapter {chapter}, Scene {scene}. "
                "Review it; it is not saved until you save it or generate the contract."
            )
        elif source == "error":
            status = f"Could not read STORY_PLAN.md for Chapter {chapter}, Scene {scene}: {error}"
        else:
            status = (
                f"No saved Scene Idea or matching STORY_PLAN.md section exists for Chapter {chapter}, "
                f"Scene {scene}. The editor is blank."
            )
        self.scene_contract_status.configure(text=status)

    def _load_scene_idea_from_plan(self):
        """Load the current plan section explicitly, even when an older idea is saved."""
        if self.package is None or not hasattr(self, "scene_idea_text"):
            return

        if getattr(self, "scene_contract_building", False) or getattr(
            self, "writer_generation_in_progress", False
        ):
            messagebox.showwarning(
                "Load Scene Idea from Plan",
                "Wait for contract building or scene generation to finish before loading from the plan.",
            )
            return

        state = self.package.current_state
        chapter = int(state.get("chapter", 1) or 1)
        scene = int(state.get("scene", 1) or 1)
        active_key = (chapter, scene)
        editor_key = getattr(self, "scene_contract_editor_key", None) or active_key
        if editor_key != active_key:
            self._refresh_scene_contract_editor()
            messagebox.showwarning(
                "Load Scene Idea from Plan",
                "The current state and Scene Contract editor were out of sync. I reloaded the current scene. "
                "Please check its Scene Idea before continuing.",
            )
            return

        try:
            planned_idea = load_scene_idea_from_plan(
                getattr(self.package, "path", None), chapter, scene
            )
        except OSError as exc:
            self._show_copyable_error(
                "Load Scene Idea from Plan",
                f"Could not read STORY_PLAN.md for Chapter {chapter}, Scene {scene}.\n\n{exc}",
            )
            return

        if not planned_idea or not planned_idea.strip():
            messagebox.showwarning(
                "Load Scene Idea from Plan",
                f"No matching scene section was found in STORY_PLAN.md for Chapter {chapter}, Scene {scene}.\n\n"
                "The current Scene Idea and saved novel data were left unchanged.",
            )
            return

        planned_idea = planned_idea.strip()
        current_idea = self.scene_idea_text.get("1.0", "end-1c")
        if current_idea.strip() != planned_idea:
            if not self._ask_yes_no(
                "Load Scene Idea from Plan",
                f"Replace the text currently in the Scene Idea editor with the matching section from STORY_PLAN.md "
                f"for Chapter {chapter}, Scene {scene}?\n\n"
                "This loads the plan into the editor only. The saved Scene Idea and existing generated contract "
                "will not change until you save the idea or generate/replace the contract.",
            ):
                return

        self.scene_idea_text.delete("1.0", "end")
        self.scene_idea_text.insert("1.0", planned_idea)
        self.scene_contract_status.configure(
            text=(
                f"Loaded the current planned Scene Idea from STORY_PLAN.md for Chapter {chapter}, Scene {scene}. "
                "Review it; it is not saved until you save it or generate the contract. "
                "Any existing generated contract remains unchanged."
            )
        )
        self._refresh_writer_scene_guidance()

    def _reset_current_scene_contract(self):
        """Clear generated contract fields for this scene while keeping its idea."""
        if self.package is None:
            return
        if getattr(self, "scene_contract_building", False) or getattr(
            self, "writer_generation_in_progress", False
        ):
            messagebox.showwarning(
                "Reset Contract",
                "Wait for contract building or scene generation to finish before resetting the contract.",
            )
            return

        chapter = int(self.package.current_state.get("chapter", 1) or 1)
        scene = int(self.package.current_state.get("scene", 1) or 1)
        entry = self._editable_scene_guidance_entry(chapter, scene, create=False)
        if not isinstance(entry, dict):
            self.scene_contract_status.configure(
                text=f"No saved contract exists for Chapter {chapter}, Scene {scene}."
            )
            return

        fields_to_clear = ("direction", "end_condition", "scene_contract")
        if not any(key in entry for key in fields_to_clear):
            self.scene_contract_status.configure(
                text=f"No saved contract fields need resetting for Chapter {chapter}, Scene {scene}."
            )
            return

        if not self._ask_yes_no(
            "Reset Scene Contract",
            f"Clear the saved direction, ending, and generated contract for Chapter {chapter}, Scene {scene}?\n\n"
            "The Scene Idea, character data, manuscript, current story state, and other scenes will be preserved. "
            "You can build a fresh contract from the saved Scene Idea after restoring the correct starting state.\n\n"
            "Are you sure you want to reset this contract?",
        ):
            return

        # Keep the Scene Idea while removing only generated contract fields.
        idea = self.scene_idea_text.get("1.0", "end-1c").strip()
        if idea:
            entry["scene_idea"] = idea
        for key in fields_to_clear:
            entry.pop(key, None)

        self.dirty = True
        try:
            self.package.save()
            self.dirty = False
            self._update_path_label()
            self._refresh_scene_contract_editor()
            self._build_scene_direction()
            self.scene_contract_status.configure(
                text=f"Reset the saved contract for Chapter {chapter}, Scene {scene}. The Scene Idea was preserved."
            )
            self._chat(
                "Builder",
                f"Reset the generated contract for Chapter {chapter}, Scene {scene}; the Scene Idea and manuscript were preserved.",
            )
        except Exception as exc:
            self.dirty = True
            self._show_copyable_error(
                "Reset Scene Contract",
                f"Could not save the reset contract.\n\n{exc}",
            )

    def _resolve_scene_idea(self, chapter: int, scene: int, entry: dict) -> tuple[str, str, str | None]:
        """Prefer a saved author idea, falling back to the matching novel plan section."""
        saved_idea = str(entry.get("scene_idea", "") or "").strip()
        if saved_idea:
            return saved_idea, "saved", None

        package_path = getattr(self.package, "path", None)
        if package_path is None:
            return "", "none", None
        try:
            planned_idea = load_scene_idea_from_plan(package_path, chapter, scene)
        except OSError as exc:
            return "", "error", str(exc)
        if planned_idea:
            return planned_idea.strip(), "plan", None
        return "", "none", None

    def _refresh_scene_contract_editor(self):
        if not hasattr(self, "scene_contract_start_text") or self.package is None:
            return

        chapter = int(self.package.current_state.get("chapter", 1) or 1)
        scene = int(self.package.current_state.get("scene", 1) or 1)
        self.scene_contract_editor_key = (chapter, scene)
        self.scene_contract_scene_label.configure(
            text=f"Chapter {chapter}, Scene {scene}"
        )

        start = self._scene_contract_start_summary()
        self.scene_contract_start_text.configure(state="normal")
        self.scene_contract_start_text.delete("1.0", "end")
        self.scene_contract_start_text.insert("1.0", start)
        self.scene_contract_start_text.configure(state="disabled")

        entry = self._editable_scene_guidance_entry(chapter, scene, create=False) or {}
        scene_idea, idea_source, idea_error = self._resolve_scene_idea(chapter, scene, entry)
        self.scene_idea_text.delete("1.0", "end")
        if scene_idea:
            self.scene_idea_text.insert("1.0", scene_idea)
        contract_error = None
        try:
            contract = SceneContract.from_guidance(entry, [])
        except (TypeError, ValueError) as exc:
            contract = {}
            contract_error = str(exc)

        self._set_generated_contract_text(
            self.scene_contract_direction_text,
            str(entry.get("direction", "") or ""),
        )

        self._set_generated_contract_text(
            self.scene_contract_end_text,
            str(contract.get("hard_stop") or entry.get("end_condition") or ""),
        )

        for key, widget in self.scene_contract_texts.items():
            self._set_generated_contract_text(
                widget,
                "\n".join(self._contract_list(contract, key)),
            )

        attempts = contract.get("max_attempts", 3)
        self.scene_contract_attempts_var.set(str(attempts))
        if hasattr(self, "scene_contract_reload_idea_button"):
            self.scene_contract_reload_idea_button.configure(state="normal")
        if hasattr(self, "scene_contract_plan_reload_button"):
            self.scene_contract_plan_reload_button.configure(state="normal")
        if hasattr(self, "scene_contract_build_button"):
            self.scene_contract_build_button.configure(state="normal")
        if contract_error:
            self.scene_contract_status.configure(
                text=f"Contract needs attention: {contract_error}",
            )
        elif idea_source == "plan":
            self.scene_contract_status.configure(
                text=(
                    f"Loaded planned Scene Idea from STORY_PLAN.md for Chapter {chapter}, Scene {scene}. "
                    "Review it, then generate the contract. It has not been saved yet."
                ),
            )
        elif idea_source == "error":
            self.scene_contract_status.configure(
                text=f"Could not read STORY_PLAN.md for Chapter {chapter}, Scene {scene}: {idea_error}",
            )
        elif idea_source == "none":
            self.scene_contract_status.configure(
                text=(
                    f"No saved Scene Idea or matching STORY_PLAN.md section exists for Chapter {chapter}, "
                    f"Scene {scene}. Enter an idea or add the scene to the plan."
                ),
            )
        else:
            self.scene_contract_status.configure(
                text="Loaded author contract for the current scene.",
            )

    def _collect_scene_contract_editor(self) -> tuple[str, str, dict]:
        if self.package is None or not hasattr(self, "scene_contract_direction_text"):
            raise ValueError("Scene contract editor is not available.")

        scene_idea = self.scene_idea_text.get("1.0", "end-1c").strip()
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

        return scene_idea, direction, end_text, contract

    def _validate_scene_contract(self):
        if self.package is None:
            return

        chapter = int(self.package.current_state.get("chapter", 1) or 1)
        scene = int(self.package.current_state.get("scene", 1) or 1)

        try:
            _scene_idea, _direction, end_text, contract = self._collect_scene_contract_editor()
        except (TypeError, ValueError) as exc:
            self.scene_contract_status.configure(text="Contract invalid.")
            self._show_copyable_error("Scene Contract", str(exc))
            return

        self.scene_contract_status.configure(
            text="Current editor contents are structurally valid.",
        )
        messagebox.showinfo(
            "Scene Contract",
            (
                f"Chapter {chapter}, Scene {scene} contract is valid.\n\n"
                f"Required beats: {len(contract.get('required_beats', []))}\n"
                f"Ending defined: {'yes' if end_text else 'no'}\n"
                f"Automatic attempts: {SceneContract.max_attempts(contract)}"
            ),
        )

    def _apply_scene_contract_from_button(self):
        try:
            self._apply_scene_contract_edits()
        except (TypeError, ValueError) as exc:
            self.scene_contract_status.configure(text="Contract not saved.")
            self._show_copyable_error("Scene Contract", str(exc))

    def _store_scene_contract_entry(
        self,
        chapter: int,
        scene: int,
        scene_idea: str,
        direction: str,
        end_text: str,
        contract: dict,
    ) -> dict:
        """Persist the authored contract under its explicit scene key."""
        entry = self._editable_scene_guidance_entry(chapter, scene, create=True)
        if entry is None:
            raise ValueError(f"Could not create guidance for Chapter {chapter}, Scene {scene}.")

        if scene_idea:
            entry["scene_idea"] = scene_idea
        else:
            entry.pop("scene_idea", None)
        if direction:
            entry["direction"] = direction
        else:
            entry.pop("direction", None)
        if end_text:
            entry["end_condition"] = end_text
        else:
            entry.pop("end_condition", None)
        entry["scene_contract"] = contract
        self.dirty = True
        self._update_path_label()
        return entry

    def _save_scene_idea(self, chapter: int, scene: int, idea: str) -> dict:
        """Persist only the author-editable Scene Idea, never the generated contract display."""
        if self.package is None:
            raise ValueError("No novel package is open.")
        entry = self._editable_scene_guidance_entry(chapter, scene, create=True)
        if entry is None:
            raise ValueError(f"Could not save the Scene Idea for Chapter {chapter}, Scene {scene}.")
        if idea:
            entry["scene_idea"] = idea
        else:
            entry.pop("scene_idea", None)

        self.dirty = True
        if self.package.path is not None:
            self.package.save()
            self.dirty = False
        self._update_path_label()
        return entry

    def _apply_scene_contract_edits(self):
        """Save only the editable Scene Idea; all other contract fields are generated."""
        if self.package is None or not hasattr(self, "scene_idea_text"):
            return

        scene_key = getattr(self, "scene_contract_editor_key", None)
        if isinstance(scene_key, tuple) and len(scene_key) == 2:
            chapter, scene = int(scene_key[0]), int(scene_key[1])
        else:
            chapter = int(self.package.current_state.get("chapter", 1) or 1)
            scene = int(self.package.current_state.get("scene", 1) or 1)

        idea = self.scene_idea_text.get("1.0", "end-1c").strip()
        self._save_scene_idea(chapter, scene, idea)
        self.scene_contract_status.configure(
            text=f"Saved Scene Idea for Chapter {chapter}, Scene {scene}.",
        )
    def _build_contract_from_scene_idea(self):
        if self.__dict__.get("scene_planner_request_in_progress", False):
            messagebox.showwarning("Scene Planner", "Let the current planning request finish before starting generating a scene contract.")
            return
        if getattr(self, "writer_generation_in_progress", False):
            self.scene_contract_status.configure(
                text="Scene generation is using the local model. Build the contract after it finishes."
            )
            return
        if self.__dict__.get("writer_notes_update_in_progress", False):
            self.scene_contract_status.configure(
                text="The writing-notes review is using the local model. Build the next contract after it finishes."
            )
            return
        if self.package is None or not hasattr(self, "scene_idea_text"):
            return

        idea = self.scene_idea_text.get("1.0", "end-1c").strip()
        if not idea:
            self._show_copyable_error("Scene Contract", "Enter a scene idea first.")
            return

        state = self.package.current_state
        active_key = (
            int(state.get("chapter", 1) or 1),
            int(state.get("scene", 1) or 1),
        )
        editor_key = getattr(self, "scene_contract_editor_key", None) or active_key
        if editor_key != active_key:
            self._refresh_scene_contract_editor()
            messagebox.showwarning(
                "Scene Contract",
                "The current state and contract editor were out of sync. I reloaded the current scene's contract. "
                "Please check the scene idea and build it again.",
            )
            return

        try:
            # The Scene Idea is the only author-editable input in this tab.
            # Save it first so cancelling a rebuild does not discard idea edits.
            chapter, scene = active_key
            self._save_scene_idea(chapter, scene, idea)

            existing_entry = (
                self._editable_scene_guidance_entry(chapter, scene, create=False) or {}
            )
            if SceneContract.has_saved_contract(existing_entry):
                confirmed = self._ask_yes_no(
                    "Replace Saved Scene Contract?",
                    (
                        f"A contract is already saved for Chapter {chapter}, Scene {scene}.\n\n"
                        "This action asks the local model to CREATE A NEW CONTRACT. "
                        "Its concise direction and ending may change. Required Beats and Planned Beats explicitly "
                        "labeled in the original Scene Idea are enforced; explicit Boundaries are carried "
                        "separately as constraints. Model-generated suggestions are not turned into mandatory stops. "
                        "Separately enabled modules may supply "
                        "their own requirements. Continuing will replace the saved generated fields.\n\n"
                        "Choose No to keep the existing fields. If your goal is to restore or reload "
                        "previously saved fields, choose No; this button does not restore an earlier version. "
                        "The Scene Idea will still be saved.\n\n"
                        "Generate and replace the saved contract?"
                    ),
                )
                if not confirmed:
                    self._refresh_scene_contract_editor()
                    self.scene_contract_status.configure(
                        text=(
                            f"Scene Idea saved. Contract rebuild canceled; the existing "
                            f"Chapter {chapter}, Scene {scene} contract was kept."
                        )
                    )
                    return

            current_state = json.loads(json.dumps(self.package.current_state, ensure_ascii=False))
            model = self._selected_writer_model_for_analysis()

            self._clear_scene_contract_editor()
            self.scene_idea_text.insert("1.0", idea)
            self.scene_contract_status.configure(
                text=f"Building contract for Chapter {chapter}, Scene {scene}...",
            )
            self.scene_contract_building = True
            self._update_writer_buttons()
            if hasattr(self, "scene_contract_build_button"):
                self.scene_contract_build_button.configure(state="disabled")
            if hasattr(self, "scene_contract_reload_idea_button"):
                self.scene_contract_reload_idea_button.configure(state="disabled")
            self.update_idletasks()

            def work():
                try:
                    result = SceneContract.generate_from_idea(
                        model, current_state, idea, engine=self.writer_engine
                    )
                    error = None
                except Exception as exc:
                    result = None
                    error = str(exc)
                self.after(
                    0,
                    lambda: self._finish_contract_from_scene_idea(
                        idea, result, error, chapter, scene
                    ),
                )

            threading.Thread(target=work, daemon=True).start()
        except Exception as exc:
            self.scene_contract_building = False
            self._update_writer_buttons()
            if hasattr(self, "scene_contract_build_button"):
                self.scene_contract_build_button.configure(state="normal")
            if hasattr(self, "scene_contract_reload_idea_button"):
                self.scene_contract_reload_idea_button.configure(state="normal")
            self._show_copyable_error("Scene Contract", str(exc))
    def _finish_contract_from_scene_idea(self, idea, result, error, chapter=None, scene=None):
        self.scene_contract_building = False
        self._update_writer_buttons()
        if hasattr(self, "scene_contract_build_button"):
            self.scene_contract_build_button.configure(state="normal")
        if hasattr(self, "scene_contract_reload_idea_button"):
            self.scene_contract_reload_idea_button.configure(state="normal")

        if error:
            self.scene_contract_status.configure(
                text="Could not build the contract. The previous saved contract was kept.",
            )
            # Reload the saved entry so an unsuccessful build does not leave
            # the form looking like its existing contract vanished.
            if self.package is not None:
                self._refresh_scene_contract_editor()
            self._show_copyable_error(
                "Scene Contract",
                error,
                summary="Scene Contract generation failed. The previous saved contract was kept.",
            )
            return

        if self.package is None or not isinstance(result, dict):
            self.scene_contract_status.configure(text="No contract was saved because the result was unavailable.")
            return

        state = self.package.current_state
        if chapter is None:
            chapter = int(state.get("chapter", 1) or 1)
        if scene is None:
            scene = int(state.get("scene", 1) or 1)
        chapter, scene = int(chapter), int(scene)

        direction = str(result.get("direction", "") or "").strip()
        end_text = str(result.get("hard_stop", "") or "").strip()
        # Newly generated contracts persist only the agreed minimal fields.
        contract = {
            "required_beats": list(result.get("required_beats", []) or []),
            "boundaries": list(result.get("boundaries", []) or []),
            "max_attempts": result.get("max_attempts", 3) or 3,
        }
        if end_text:
            contract["hard_stop"] = end_text

        try:
            SceneContract.validate_shape(contract)
            lint_errors = SceneContract.lint(contract)
            if lint_errors:
                raise ValueError("Generated contract needs attention:\n- " + "\n- ".join(lint_errors))

            entry = self._editable_scene_guidance_entry(chapter, scene, create=True)
            if entry is None:
                raise ValueError(
                    f"Could not create guidance for Chapter {chapter}, Scene {scene}."
                )
            # A rebuilt idea may change the intended ending. Remove legacy
            # generated rules and any hidden expected state from the old build
            # so those values cannot leak into the new contract or state analysis.
            self._clear_stale_generated_scene_contract_fields(entry)
            self._store_scene_contract_entry(
                chapter, scene, idea, direction, end_text, contract
            )

            persisted = False
            if self.package.path is not None:
                self.package.save()
                self.dirty = False
                persisted = True
            else:
                self.dirty = True
            self._update_path_label()

            active_key = (
                int(self.package.current_state.get("chapter", 1) or 1),
                int(self.package.current_state.get("scene", 1) or 1),
            )
            editor_key = getattr(self, "scene_contract_editor_key", None)
            if active_key == (chapter, scene) and editor_key == (chapter, scene):
                # The contract is now stored, so reload the saved values and
                # build Writer direction in this same operation. Apply Contract
                # and Build Writer Direction remain available for later edits,
                # but are no longer required after every generated contract.
                self._refresh_scene_contract_editor()
                self._build_scene_direction()
                status = (
                    f"Contract saved for Chapter {chapter}, Scene {scene}. Writer direction is ready."
                    if persisted
                    else f"Contract drafted for Chapter {chapter}, Scene {scene}. Save or Save As to persist it."
                )
            else:
                status = (
                    f"Contract saved for Chapter {chapter}, Scene {scene}. The current scene editor was left untouched."
                    if persisted
                    else f"Contract drafted in memory for Chapter {chapter}, Scene {scene}. Save the novel package to persist it."
                )
            self.scene_contract_status.configure(text=status)
        except Exception as exc:
            self.dirty = True
            self._update_path_label()
            self.scene_contract_status.configure(text="Contract generated but could not be saved.")
            self._show_copyable_error("Scene Contract", str(exc))
    def _build_writer_direction_from_contract(self):
        try:
            self._apply_scene_contract_edits()
            self._build_scene_direction()
        except Exception as exc:
            self._show_copyable_error("Scene Contract", str(exc))

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
        """Build a minimal runtime contract from the scene idea and positive beats.

        Legacy auxiliary validation fields are ignored for backwards compatibility.
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


    def _load_saved_scene_into_writer(self, startup=False):
        """Restore the saved accepted section matching the live scene pointer."""
        if self.package is None or self.package.path is None:
            if not startup:
                messagebox.showwarning(
                    "Reload Saved Scene",
                    "Open a saved novel package before reloading a manuscript section.",
                )
            return False

        state = self.package.current_state
        chapter = int(state.get("chapter", 1) or 1)
        scene = int(state.get("scene", 1) or 1)
        try:
            restored = ManuscriptManager(Path(self.package.path)).load_scene_for_state_review(
                chapter,
                scene,
                state,
            )
        except (OSError, ValueError) as exc:
            if startup:
                self.writer_status.configure(text=str(exc))
            else:
                self._show_copyable_error("Reload Saved Scene", str(exc))
            return False

        if restored is None:
            message = (
                f"No saved accepted manuscript prose was found for Chapter {chapter}, "
                f"Scene {scene}. No Writer text was changed."
            )
            if startup:
                self.writer_status.configure(text=message)
            else:
                messagebox.showinfo("Reload Saved Scene", message, parent=self)
            return False

        prose = restored["text"]
        visible = self._writer_editor_prose()
        accepted_before = str(getattr(self, "accepted_scene", "") or "").strip()
        if not startup and visible and visible != accepted_before and visible != prose:
            if not self._save_unsaved_writer_draft():
                return False

        self.generated_scene = prose
        self.accepted_scene = prose
        self.accepted_scene_context = (chapter, scene)
        self.generated_scene_context = (chapter, scene)
        self.generated_scene_start_state = restored["start_state"]
        self.writer_draft_saved_text = None
        self.focused_revision_history = []
        self.pending_state_patch = None
        self.writer_output_text.delete("1.0", "end")
        self.writer_output_text.insert("1.0", prose)
        self.writer_state_preview.delete("1.0", "end")
        if "writer_state_diff_preview" in self.__dict__:
            self.writer_state_diff_preview.configure(state="normal")
            self.writer_state_diff_preview.delete("1.0", "end")
            self.writer_state_diff_preview.configure(state="disabled")
        self._update_writer_buttons()
        self.writer_status.configure(
            text=(
                f"Restored saved Chapter {chapter}, Scene {scene} into Writer. "
                "Review the prose, then analyze its ending state."
            )
        )
        return True

    def _state_analysis_character_candidates(
        self,
        story_text: str,
        chapter: int,
        scene: int,
    ) -> list[str]:
        """Collect the opening cast and known characters named in the accepted prose.

        scene_cast is only the opening cast. Later arrivals must also be available
        to the knowledge audit, which uses the prose and starting locations to
        distinguish participants from characters who are merely mentioned.
        """
        if not self.package:
            return []

        state = getattr(self.package, "current_state", {}) or {}
        names: list[str] = []
        seen: set[str] = set()

        def add_name(value: Any, *, require_mention: bool = False) -> None:
            name = str(value or "").strip()
            if not name:
                return
            if require_mention and not re.search(
                r"(?<!\w)" + re.escape(name) + r"(?!\w)",
                story_text,
                flags=re.IGNORECASE,
            ):
                return
            key = name.casefold()
            if key not in seen:
                names.append(name)
                seen.add(key)

        # Always retain the actual opening cast, then add explicitly planned
        # cast entries and characters whose names appear in the accepted scene.
        opening_cast = state.get("scene_cast", [])
        if isinstance(opening_cast, list):
            for name in opening_cast:
                add_name(name)
        for name in self._scene_plan_cast(chapter, scene):
            add_name(name)

        character_cards = getattr(self.package, "characters", {})
        if isinstance(character_cards, dict):
            for filename, data in character_cards.items():
                name = str(data.get("name", "") or "").strip() if isinstance(data, dict) else ""
                if not name:
                    name = Path(str(filename)).stem
                add_name(name, require_mention=True)

        # Also support established state entries when an older package has no
        # matching character card. These are candidates, not proof of presence.
        for field in ("location", "physical_state", "character_knowledge", "active_objectives"):
            values = state.get(field, {})
            if not isinstance(values, dict):
                continue
            for name in values:
                if str(name).strip().casefold() != "primary":
                    add_name(name, require_mention=True)

        return names

    def _analyze_accepted_scene(self):
        if self.__dict__.get("scene_planner_request_in_progress", False):
            messagebox.showwarning("Scene Planner", "Let the current planning request finish before starting state analysis.")
            return
        if not self.package or not self.accepted_scene.strip():
            return
        if self.__dict__.get("state_analysis_in_progress", False):
            return

        current_state = dict(self.package.current_state)
        story_text = self.accepted_scene
        completed_chapter = int(current_state.get("chapter", 1) or 1)
        completed_scene = int(current_state.get("scene", 1) or 1)
        contract = self._scene_contract(completed_chapter, completed_scene)
        # A planned state_after is an expected-ending hint, not proof that
        # those events occurred. Always analyze the accepted prose itself, even
        # when a scene has authored state guidance. StateManager receives that
        # hint for context but must return only changes supported by the prose.
        if not self.writer_engine.model_path:
            return

        scene_end_guidance = self._scene_end_guidance(completed_chapter, completed_scene)
        scene_characters = self._state_analysis_character_candidates(
            story_text,
            completed_chapter,
            completed_scene,
        )
        model = self.writer_engine.model_path

        self.state_analysis_in_progress = True
        self.writer_reload_scene_button.configure(state="disabled")
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
                    scene_characters=scene_characters,
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
        self.state_analysis_in_progress = False
        if error:
            self.pending_state_patch = None
            if hasattr(self, "writer_state_preview"):
                self.writer_state_preview.delete("1.0", "end")
            if "writer_state_diff_preview" in self.__dict__:
                self.writer_state_diff_preview.configure(state="normal")
                self.writer_state_diff_preview.delete("1.0", "end")
                self.writer_state_diff_preview.configure(state="disabled")
            self._show_copyable_error("State Update", error)
            self._update_writer_buttons()
            return

        try:
            if self.package is None:
                raise ValueError("No novel package is open.")
            StateManager.validate_patch(self.package.current_state, patch or {})
        except (TypeError, ValueError) as exc:
            self.pending_state_patch = None
            if hasattr(self, "writer_state_preview"):
                self.writer_state_preview.delete("1.0", "end")
            self._show_copyable_error(
                "State Update",
                "The proposed state update is malformed and was rejected. "
                "Nothing was applied.\n\n" + str(exc),
            )
            self.writer_status.configure(text="Malformed state update rejected. Analyze the accepted scene again after the underlying issue is fixed.")
            self._update_writer_buttons()
            return

        # Keep the actual partial patch for Apply State Update, but preview
        # the fully merged candidate so the author can inspect preserved fields
        # and location reconciliation before changing canon.
        self.pending_state_patch = patch or {}
        reconstructed_state = StateManager.merge_patch(
            self.package.current_state,
            self.pending_state_patch,
        )
        state_diff = build_state_change_summary(
            self.package.current_state,
            reconstructed_state,
        )
        if "writer_state_diff_preview" in self.__dict__:
            self.writer_state_diff_preview.configure(state="normal")
            self.writer_state_diff_preview.delete("1.0", "end")
            self.writer_state_diff_preview.insert("1.0", state_diff)
            self.writer_state_diff_preview.configure(state="disabled")
        if "writer_state_review_notebook" in self.__dict__ and "writer_state_diff_tab" in self.__dict__:
            self.writer_state_review_notebook.select(self.writer_state_diff_tab)
        self.writer_state_preview.delete("1.0", "end")
        self.writer_state_preview.insert(
            "1.0",
            json.dumps(reconstructed_state, indent=2, ensure_ascii=False),
        )
        self.writer_status.configure(
            text=(
                "Full ending-state preview ready. Nothing has been applied; "
                "review the JSON before choosing Apply State Update."
            )
        )
        self._update_writer_buttons()

    def _apply_state_update(self):
        if self.package is None or not isinstance(self.pending_state_patch, dict):
            return

        try:
            preview_text = self.writer_state_preview.get("1.0", "end").strip()
            if not preview_text:
                raise ValueError("The ending-state preview is empty. Analyze the accepted scene again.")

            reviewed_preview = json.loads(preview_text)
            expected_preview = StateManager.merge_patch(
                self.package.current_state,
                self.pending_state_patch,
            )
            preview_edits = reviewed_state_preview_to_patch(
                expected_preview,
                reviewed_preview,
            )
            # Compose the generated patch with author edits without consuming
            # explicit null deletion markers. Nulls are applied only when the
            # final patch is merged into the saved state.
            patch_to_apply = combine_state_patches(
                self.pending_state_patch,
                preview_edits,
            )
            StateManager.validate_patch(
                self.package.current_state,
                patch_to_apply,
            )
        except (TypeError, ValueError) as exc:
            self._show_copyable_error(
                "State Update",
                "The reviewed ending-state preview is invalid, so no state changes were made. "
                "Correct the JSON and click Apply State Update again.\n\n" + str(exc),
            )
            self._update_writer_buttons()
            return

        try:
            completed_chapter = int(self.package.current_state.get("chapter", 1) or 1)
            completed_scene = int(self.package.current_state.get("scene", 1) or 1)
            completed_prose = str(
                getattr(self, "accepted_scene", "") or self._writer_editor_prose() or ""
            ).strip()

            if not self._save_unsaved_writer_draft():
                return

            self.package.current_state = StateManager.merge_patch(
                self.package.current_state,
                patch_to_apply,
            )

            # Once the first accepted scene has been applied, the story is no
            # longer at its starting point. Preserve any other author-defined
            # status values.
            if str(self.package.current_state.get("status", "")).strip().casefold() == "story_start":
                self.package.current_state["status"] = "in_progress"

            # Capture the actual end state of the completed section before
            # the application advances the live pointer to the next scene.
            completed_end_state = json.loads(
                json.dumps(self.package.current_state, ensure_ascii=False)
            )
            completed_end_state["chapter"] = completed_chapter
            completed_end_state["scene"] = completed_scene
            completed_end_state["scene_completed"] = False
            completed_end_state["chapter_completed"] = False

            # The accepted section is now complete. Advance the package to the
            # next scene so the Writer tab can immediately build the next scene
            # direction without requiring a separate chat command.
            current_chapter = int(self.package.current_state.get("chapter", completed_chapter) or completed_chapter)
            current_scene = int(self.package.current_state.get("scene", completed_scene) or completed_scene)

            # Scene plans guide generation but do not decide when a chapter ends.
            # Applying a scene's analyzed state always leaves the chapter open;
            # only the author's explicit Finalize Chapter action closes it.
            if current_chapter == completed_chapter and current_scene == completed_scene:
                self.package.current_state["scene"] = completed_scene + 1
            # If the continuity manager explicitly advanced the state, keep its
            # chapter/scene decision intact. In either case, completion is manual.
            self.package.current_state["scene_completed"] = False
            self.package.current_state["chapter_completed"] = False

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
            self.accepted_scene_context = None
            self.focused_revision_history = []
            self.generated_scene_context = None
            self.generated_scene_start_state = None
            self.writer_generation_context = None
            self.writer_generation_start_state = None
            self.writer_output_text.delete("1.0", "end")
            self.writer_state_preview.delete("1.0", "end")
            self._refresh_all()
            self._save()
            if self.package.path is not None:
                try:
                    ManuscriptManager(self.package.path).save_state_after_candidate(
                        completed_chapter,
                        completed_scene,
                        completed_end_state,
                    )
                except Exception as snapshot_error:
                    self._show_copyable_error(
                        "State Snapshot",
                        "The state update was saved, but StoryBuilder could not save the "
                        f"recovery snapshot for Chapter {completed_chapter}, Scene {completed_scene}.\n\n"
                        f"{snapshot_error}",
                        summary="The state update was saved, but its recovery snapshot failed.",
                    )
            if not self.package.current_state.get("chapter_completed"):
                # Keep the Writer direction synchronized with the newly
                # advanced state so the next scene is ready without a manual
                # trip to Scene Contract or a separate rebuild button.
                self._build_scene_direction()

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
                    text=(
                        f"Chapter {self.package.current_state.get('chapter', current_chapter)}, "
                        f"Scene {self.package.current_state.get('scene')} is ready. "
                        "Writer direction has been refreshed."
                    )
                )
            if completed_prose:
                self._start_writer_notes_learning(
                    completed_chapter,
                    completed_scene,
                    completed_prose,
                )
            self._update_writer_buttons()
        except Exception as exc:
            self._show_copyable_error("State Update", str(exc))

    def _start_writer_notes_learning(self, chapter, scene, prose):
        """Learn craft notes from several accepted scenes after state application."""
        if self.package is None or self.package.path is None or not str(prose or "").strip():
            return
        if self.__dict__.get("writer_notes_update_in_progress", False):
            return

        package_path = Path(self.package.path)
        scene_label = f"Chapter {int(chapter)}, Scene {int(scene)}"
        notes = normalize_writer_notes(getattr(self.package, "writer_notes", {}))
        if scene_label in notes.get("reviewed_scenes", []):
            return

        model = getattr(self.writer_engine, "model_path", None)
        if model is None and hasattr(self, "writer_model_var"):
            selected_model = self.writer_model_var.get().strip()
            model = Path(selected_model) if selected_model else None
        if model is None:
            return

        recent_scenes = collect_recent_accepted_scenes(
            package_path,
            int(chapter),
            int(scene),
            str(prose),
            limit=3,
        )
        if len(recent_scenes) < 2:
            # Wait until there are at least two accepted sections to compare.
            # No lesson is inferred from a single scene.
            return
        available_labels = [item["scene"] for item in recent_scenes]
        review_prompt = build_writer_notes_review_prompt(notes, recent_scenes)
        self.writer_notes_update_in_progress = True
        self._update_writer_buttons()
        self.writer_status.configure(
            text="Updating this novel's temporary writing notes from accepted scenes..."
        )

        def work():
            updated_notes = None
            added_count = 0
            error = None
            engine = self.writer_engine
            was_running = False
            old_system_prompt = ""
            try:
                with engine.lock:
                    was_running = engine.child is not None and engine.child.isalive()
                    old_system_prompt = str(engine.system_prompt or "")
                    try:
                        engine.reset_context(model, WRITER_NOTES_SYSTEM_PROMPT)
                        response = engine.generate(review_prompt)
                        suggestions = parse_writer_notes_response(response)
                        updated_notes, added_count = merge_writer_notes(
                            notes,
                            suggestions,
                            available_labels,
                            scene_label,
                        )
                        save_writer_notes(package_path, updated_notes)
                    finally:
                        # Restore the writer session if it was already running.
                        # Next scene generation rebuilds the prompt from current
                        # notes and the current scene state in either case.
                        if was_running and old_system_prompt:
                            engine.reset_context(model, old_system_prompt)
                        else:
                            engine.stop()
                error = None
            except Exception as exc:
                error = str(exc)

            try:
                self.after(
                    0,
                    lambda: self._finish_writer_notes_learning(
                        package_path, updated_notes, added_count, error, scene_label
                    ),
                )
            except tk.TclError:
                pass

        threading.Thread(target=work, daemon=True).start()

    def _finish_writer_notes_learning(
        self, package_path, notes, added_count, error, scene_label
    ):
        self.writer_notes_update_in_progress = False
        if (
            notes is not None
            and self.package is not None
            and self.package.path is not None
            and Path(self.package.path).resolve() == Path(package_path).resolve()
        ):
            self.package.writer_notes = notes

        self._update_writer_buttons()
        if error:
            self.writer_status.configure(
                text="The scene remains saved. The automatic writing-notes review did not finish cleanly."
            )
            self._chat("Builder", f"Writing-notes review skipped for {scene_label}: {error}")
        elif added_count:
            self.writer_status.configure(
                text=f"Writing notes updated for this novel with {added_count} recurring craft observation(s)."
            )
            self._chat(
                "Builder",
                f"Updated this novel's temporary writing notes after reviewing accepted scenes ending at {scene_label}.",
            )
        else:
            self.writer_status.configure(
                text="Writing notes reviewed. No new recurring craft lesson was strong enough to add."
            )

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
            self._show_copyable_error(
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
                        "source_path": path,
                        "used_fallback": used_fallback,
                        "error": None,
                    }
                except Exception as exc:
                    result = {
                        "patch": None,
                        "candidate": None,
                        "save_path": None,
                        "source_path": path,
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
            self._show_copyable_error("State Recovery", str(exc))
            self._update_saved_state_buttons()

    def _finish_saved_state_analysis(self, result):
        error = result.get("error")
        if error:
            self._show_copyable_error("State Recovery", error)
            self._update_saved_state_buttons()
            return

        self.saved_state_candidate = result.get("candidate")
        source_path = result.get("source_path")
        self.saved_state_candidate_path = Path(source_path) if source_path else None
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
        source_name = self.saved_state_candidate_path.name if self.saved_state_candidate_path else "selected section"
        note = "using the current state as the baseline because no before-state snapshot exists" if result.get("used_fallback") else "using the saved before-state snapshot"
        self.manuscript_recovery_status.configure(
            text=f"Reconstructed state for {source_name} saved to {save_path.name} ({note})."
        )
        self._update_saved_state_buttons()

    def _update_saved_state_buttons(self):
        selected_path = self._selected_manuscript_scene()
        has_selection = selected_path is not None
        has_candidate = isinstance(self.saved_state_candidate, dict)
        candidate_matches_selection = (
            has_candidate
            and self.saved_state_candidate_path is not None
            and selected_path is not None
            and Path(selected_path) == Path(self.saved_state_candidate_path)
        )

        if hasattr(self, "manuscript_analyze_button"):
            self.manuscript_analyze_button.configure(
                state="normal" if has_selection else "disabled"
            )
        if hasattr(self, "manuscript_restore_button"):
            self.manuscript_restore_button.configure(
                state="normal" if candidate_matches_selection and self.package else "disabled"
            )
        if hasattr(self, "manuscript_copy_state_button"):
            self.manuscript_copy_state_button.configure(
                state="normal" if has_candidate else "disabled"
            )

    def _restore_saved_state_candidate(self):
        if self.package is None or not isinstance(self.saved_state_candidate, dict):
            return
        selected_path = self._selected_manuscript_scene()
        if (
            self.saved_state_candidate_path is None
            or selected_path is None
            or Path(selected_path) != Path(self.saved_state_candidate_path)
        ):
            messagebox.showwarning(
                "Restore Reconstructed State",
                "The reconstructed state belongs to a different manuscript section. Select that section in the left-hand list before restoring it.",
            )
            return

        if not self._ask_yes_no(
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
        """Finalize the last accepted scene only when the author explicitly asks."""
        if self.package is None or self.package.path is None:
            messagebox.showwarning(
                "Finalize Chapter",
                "Save the novel package before finalizing a chapter.",
            )
            return

        if getattr(self, "accepted_scene", "") and not self.package.current_state.get("chapter_completed"):
            messagebox.showwarning(
                "Finish Current Scene",
                "The current scene has been accepted but its state update has not been applied yet. "
                "Analyze the accepted scene and apply its state update before finalizing the chapter.",
            )
            return

        chapter = int(self.package.current_state.get("chapter", 1) or 1)
        current_scene = int(self.package.current_state.get("scene", 1) or 1)
        if self.package.current_state.get("chapter_completed"):
            messagebox.showinfo(
                "Finalize Chapter",
                f"Chapter {chapter} is already finalized.",
            )
            return

        manager = ManuscriptManager(self.package.path)
        scene_paths = manager.chapter_scene_paths(chapter)
        scene_numbers = [
            numbers[1]
            for path in scene_paths
            if (numbers := ManuscriptManager.scene_numbers(path)) is not None
        ]
        if not scene_numbers:
            messagebox.showwarning(
                "Finalize Chapter",
                f"No accepted manuscript sections were found for Chapter {chapter}.",
            )
            return

        latest_scene = max(scene_numbers)
        if current_scene < latest_scene:
            messagebox.showwarning(
                "Finalize Chapter",
                f"Current state is on Scene {current_scene}, but Chapter {chapter} already contains "
                f"accepted material through Scene {latest_scene}. Restore the ending state for the "
                "latest accepted scene before finalizing.",
            )
            return

        saved_end_state = manager.load_state_after(chapter, latest_scene)
        if saved_end_state is None:
            messagebox.showwarning(
                "Finalize Chapter",
                f"Chapter {chapter}, Scene {latest_scene} has no saved ending-state snapshot.\n\n"
                "Open Manuscript, select that accepted scene, click Analyze Saved Section, "
                "then click Restore Reconstructed State. Return here and finalize the chapter.",
            )
            return

        # If the live pointer is already on the last accepted scene, preserve
        # any author-reviewed edits to that end state. If it has moved forward,
        # restore the scene-specific snapshot so next-scene fields do not leak.
        if current_scene == latest_scene:
            end_state = json.loads(json.dumps(self.package.current_state, ensure_ascii=False))
        else:
            end_state = saved_end_state

        if not self._ask_yes_no(
            "Finalize Chapter",
            f"Finalize Chapter {chapter} at its last accepted scene, Scene {latest_scene}?\n\n"
            "This marks the chapter complete, restores that scene's ending state, and prepares "
            "StoryBuilder for Start Next Chapter. The scene plan will not decide chapter length, "
            "and accepted manuscript prose will not be changed.",
        ):
            return

        if not self._save_unsaved_writer_draft():
            return
        # Apply any pending edits before refreshing the form, so canon, character,
        # location, and scene-idea edits are not silently discarded by finalization.
        if not self._apply_all_edits():
            return
        live_state = self.package.current_state
        live_chapter = int(live_state.get("chapter", 1) or 1)
        live_scene = int(live_state.get("scene", 1) or 1)
        if live_chapter != chapter:
            messagebox.showwarning(
                "Finalize Chapter",
                "The active chapter changed while saving pending edits. No chapter was finalized; "
                "check Current State and try again.",
            )
            return
        if current_scene == latest_scene and live_scene == latest_scene:
            end_state = json.loads(json.dumps(live_state, ensure_ascii=False))

        self.package.current_state = json.loads(json.dumps(end_state, ensure_ascii=False))
        self.package.current_state["chapter"] = chapter
        self.package.current_state["scene"] = latest_scene
        self.package.current_state["scene_completed"] = True
        self.package.current_state["chapter_completed"] = True
        self.dirty = True
        self._update_path_label()
        # Refresh before saving so the State editor's chapter/scene controls do
        # not write the previous live pointer back over the restored end state.
        self._refresh_all()
        self._save()
        self._chat(
            "Builder",
            f"Chapter {chapter} finalized at Scene {latest_scene}. "
            "The ending state is saved and the next chapter can now be started.",
        )
        if hasattr(self, "writer_status"):
            self.writer_status.configure(
                text=f"Chapter {chapter} finalized at Scene {latest_scene}. Use Start Next Chapter when ready."
            )
        if hasattr(self, "manuscript_recovery_status"):
            self.manuscript_recovery_status.configure(
                text=f"Chapter {chapter} finalized at its last accepted scene, Scene {latest_scene}."
            )

    def _review_scene_flow(self):
        if self.package is None or self.package.path is None:
            return
        if self.scene_flow_review_in_progress:
            return

        active_thread = getattr(self, "writer_thread", None)
        if (
            (active_thread is not None and active_thread.is_alive())
            or self.writer_generation_in_progress
            or self.scene_contract_building
            or self.writer_notes_update_in_progress
        ):
            self.manuscript_flow_status.configure(
                text="Please let the current writing or state-analysis operation finish before reviewing scene flow."
            )
            return

        chapter = self._manuscript_target_chapter()
        manager = ManuscriptManager(self.package.path)
        paths = manager.chapter_scene_paths(chapter)
        if len(paths) < 2:
            messagebox.showinfo(
                "Review Scene Flow",
                f"Chapter {chapter} needs at least two accepted scenes before its transitions can be reviewed.",
            )
            return

        try:
            model = self._selected_writer_model_for_analysis()
        except Exception as exc:
            self._show_copyable_error("Review Scene Flow", str(exc))
            return

        self.scene_flow_review_in_progress = True
        self.manuscript_review_flow_button.configure(state="disabled")
        self.manuscript_flow_status.configure(
            text=f"Preparing to review {len(paths) - 1} transition(s) in Chapter {chapter}..."
        )

        def update_progress(done: int, total: int, message: str) -> None:
            try:
                self.after(
                    0,
                    lambda d=done, t=total, m=message: self.manuscript_flow_status.configure(
                        text=f"Scene-flow review {d}/{t}: {m}"
                    ),
                )
            except tk.TclError:
                pass

        def work():
            try:
                report = review_chapter_flow(
                    model,
                    paths,
                    progress=update_progress,
                )
                result = {"report": report, "error": None}
            except Exception as exc:
                result = {"report": None, "error": str(exc)}

            try:
                self.after(
                    0,
                    lambda r=result, ch=chapter: self._finish_scene_flow_review(ch, r),
                )
            except tk.TclError:
                pass

        self.scene_flow_review_thread = threading.Thread(
            target=work,
            daemon=True,
        )
        self.scene_flow_review_thread.start()

    def _finish_scene_flow_review(self, chapter: int, result: dict):
        self.scene_flow_review_in_progress = False
        self.manuscript_review_flow_button.configure(state="normal")
        error = result.get("error")
        if error:
            self.manuscript_flow_status.configure(
                text=f"Scene-flow review failed for Chapter {chapter}."
            )
            self._show_copyable_error("Review Scene Flow", error)
            return

        self.manuscript_flow_status.configure(
            text=f"Scene-flow review finished for Chapter {chapter}. Accepted scenes were not changed."
        )
        self._show_scene_flow_report(chapter, result.get("report", ""))

    def _show_scene_flow_report(self, chapter: int, report: str):
        dialog = tk.Toplevel(self)
        dialog.title(f"Chapter {chapter}: Scene Flow Review")
        dialog.transient(self)
        dialog.resizable(True, True)

        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        width = min(980, max(500, screen_width - 48))
        height = min(760, max(360, screen_height - 80))
        dialog.geometry(
            f"{width}x{height}+{max(0, (screen_width-width)//2)}+"
            f"{max(0, (screen_height-height)//2)}"
        )

        outer = ttk.Frame(dialog, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(
            outer,
            text=(
                "Review the findings and optional targeted suggestions below. "
                "This report does not change accepted scenes."
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        text_frame = ttk.Frame(outer)
        text_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical")
        report_text = tk.Text(
            text_frame,
            wrap="word",
            yscrollcommand=scrollbar.set,
            padx=8,
            pady=8,
        )
        scrollbar.configure(command=report_text.yview)
        report_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        report_text.insert("1.0", report or "No review report was returned.")
        report_text.configure(state="disabled")

        status = ttk.Label(outer, text="The accepted manuscript remains unchanged.")
        status.pack(anchor="w", pady=(6, 0))

        def copy_report():
            try:
                dialog.clipboard_clear()
                dialog.clipboard_append(report or "")
                dialog.update_idletasks()
                status.configure(text="Full report copied to the clipboard.")
            except tk.TclError as exc:
                status.configure(text=f"Clipboard copy failed: {exc}")

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(
            buttons,
            text="Copy Full Report",
            command=copy_report,
        ).pack(side="left")
        ttk.Button(
            buttons,
            text="Close",
            command=dialog.destroy,
        ).pack(side="right")

        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.focus_force()

    def _assemble_current_chapter(self):
        if self.package is None or self.package.path is None:
            return

        chapter = self._manuscript_target_chapter()
        manager = ManuscriptManager(self.package.path)
        try:
            target = manager.compile_chapter(chapter)
        except (OSError, ValueError) as exc:
            self._show_copyable_error("Assemble Chapter", str(exc))
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
            self._show_copyable_error("Assemble Entire Novel", str(exc))
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
        if (
            isinstance(self.saved_state_candidate, dict)
            and self.saved_state_candidate_path is not None
        ):
            candidate_name = self.saved_state_candidate_path.name
            selected_name = path.name
            if Path(path) == Path(self.saved_state_candidate_path):
                status_text = (
                    f"Selected {selected_name}. The reconstructed state preview is preserved; "
                    "review it and restore it when ready."
                )
            else:
                status_text = (
                    f"Selected {selected_name}. The reconstructed state for {candidate_name} "
                    "is preserved. Reselect its entry to restore that candidate."
                )
        else:
            status_text = (
                f"Selected {path.name}. Click Analyze Saved Section to reconstruct its state."
            )
        self.manuscript_recovery_status.configure(text=status_text)
        self._update_saved_state_buttons()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            self._show_copyable_error("Manuscript", str(exc))
            return

        self.manuscript_output.delete("1.0", "end")
        self.manuscript_output.insert("1.0", text)

    def _sync_current_novel(self):
        if self.package is None or self.package.path is None:
            messagebox.showwarning(
                "Sync Novel",
                "Save or open a novel package before syncing the novel repository.",
            )
            return

        if not self._apply_all_edits():
            return
        try:
            self.package.save()
            self.dirty = False
            self._update_path_label()
            result = sync_novel_repository(self.package.path)
            self._chat("Builder", result)
            messagebox.showinfo("Sync Novel", result)
        except (NovelSyncError, OSError, subprocess.SubprocessError) as exc:
            self._show_copyable_error(
                "Sync Novel",
                "The novel was saved locally, but GitHub sync failed.\n\n" + str(exc),
                summary=(
                    "The novel was saved locally, but GitHub synchronization did not complete. "
                    "Review or copy the full error details below."
                ),
            )
    def _close_without_sync(self):
        if self.__dict__.get("writer_notes_update_in_progress", False):
            messagebox.showwarning(
                "Close",
                "StoryBuilder is updating the novel's writing notes. The app will remain open until the update is saved.",
            )
            return
        if self._closing:
            return
        self._closing = True

        try:
            if not self._save_unsaved_writer_draft():
                self._closing = False
                return
            try:
                self.writer_engine.stop()
            except Exception:
                pass

            # Save all current editor contents locally, but never run the GitHub sync.
            self._save()
            if self.dirty:
                self._closing = False
                return

            self.destroy()
        except Exception as exc:
            self._show_copyable_error(
                "Close",
                f"The novel was saved locally, but the app could not close cleanly.\n\n{exc}\n\nThe app will remain open."
            )
            self._closing = False
    def _close_and_sync(self):
        if self.__dict__.get("writer_notes_update_in_progress", False):
            messagebox.showwarning(
                "Close & Sync",
                "StoryBuilder is updating the novel's writing notes. The app will remain open until the update is saved.",
            )
            return
        if self._closing:
            return
        self._closing = True

        try:
            if not self._save_unsaved_writer_draft():
                self._closing = False
                return
            try:
                self.writer_engine.stop()
            except Exception:
                pass

            # Save all current editor contents before running the repository sync.
            self._save()
            if self.dirty:
                self._closing = False
                return

            if self.package.path is None:
                messagebox.showwarning(
                    "Close & Sync",
                    "The novel is saved locally but has no project folder yet.\n\n"
                    "Use Save As / Export to place it in its own novel project folder.",
                )
                self._closing = False
                return

            try:
                sync_novel_repository(self.package.path)
            except NovelSyncError as exc:
                self._show_copyable_error(
                    "Close & Sync",
                    "The novel was saved locally, but GitHub sync failed.\n\n"
                    + str(exc)
                    + "\n\nThe app will remain open so you can resolve the problem.",
                    summary=(
                        "The novel is saved locally, but GitHub synchronization did not complete. "
                        "Use Copy Full Error or select the text and press Ctrl+C, then paste the details into chat."
                    ),
                )
                self._closing = False
                return

            self.destroy()
        except (OSError, subprocess.SubprocessError) as exc:
            self._show_copyable_error(
                "Close & Sync",
                "The novel was saved locally, but the GitHub sync could not be completed.\n\n"
                f"{exc}\n\nThe app will remain open.",
                summary=(
                    "The novel is saved locally, but GitHub synchronization did not complete. "
                    "Use Copy Full Error or select the text and press Ctrl+C, then paste the details into chat."
                ),
            )
            self._closing = False
    def _load_startup_novel(self):
        """Open the sole novel automatically, or ask when the library has several."""
        candidates = find_novel_packages(NOVEL_ROOT)
        if not candidates:
            self._new_novel()
            return

        if len(candidates) == 1:
            folder = candidates[0]
        else:
            selected = filedialog.askdirectory(
                title="Choose a novel from the MyNovel library",
                initialdir=str(NOVEL_ROOT),
            )
            if not selected:
                self._new_novel()
                return
            folder = Path(selected).expanduser().resolve()
            allowed = {candidate.resolve() for candidate in candidates}
            if folder not in allowed:
                messagebox.showwarning(
                    "Open Novel",
                    f"Choose a novel folder directly inside {NOVEL_ROOT}.",
                )
                self._new_novel()
                return

        try:
            self.writer_engine.stop()
        except Exception:
            pass
        try:
            self.package = StoryPackage.load(folder)
        except Exception as exc:
            self._show_copyable_error(
                "Open Novel",
                f"Could not open the novel package.\n\n{exc}\n\nStarting with a new unsaved novel instead.",
                summary="The selected novel could not be opened; StoryBuilder is using a new unsaved package.",
            )
            self._new_novel()
            return
        self.character_filename = None
        self.generated_scene = ""
        self.accepted_scene = ""
        self.accepted_scene_context = None
        self.focused_revision_history = []
        self.pending_state_patch = None
        self.interview_active = False
        self.interview_index = 0
        self.interview_pending_patch = None
        self.interview_pending_answer = ""
        self.last_novel_path = folder
        self.dirty = False
        self._refresh_all()
        self._refresh_writer_models()
        # Recover the accepted prose for the live chapter/scene when its saved
        # starting state matches current_state. This keeps restart recovery from
        # silently emptying the Writer before a pending continuity analysis.
        self._load_saved_scene_into_writer(startup=True)
        self._chat(
            "Builder",
            f'Opened "{self.package.story_bible.get("title", folder.name)}".',
        )
    def _new_novel(self):
        if self.__dict__.get("writer_notes_update_in_progress", False):
            messagebox.showwarning(
                "Writing Notes",
                "Finish the current novel's automatic writing-notes update before switching novels.",
            )
            return
        if not self._save_unsaved_writer_draft():
            return
        self.guided_setup.stop()
        self._reset_new_novel_assistant(clear_brief=True)
        if hasattr(self, "guided_button"):
            self.guided_button.configure(text="Guided Setup")
        try:
            self.writer_engine.stop()
        except Exception:
            pass
        self.generated_scene = ""
        self.accepted_scene = ""
        self.accepted_scene_context = None
        self.focused_revision_history = []
        self.generated_scene_context = None
        self.generated_scene_start_state = None
        self.writer_generation_context = None
        self.writer_generation_start_state = None
        self.writer_generation_in_progress = False
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
        if self.__dict__.get("writer_notes_update_in_progress", False):
            messagebox.showwarning(
                "Writing Notes",
                "Finish the current novel's automatic writing-notes update before switching novels.",
            )
            return
        self.guided_setup.stop()
        if hasattr(self, "guided_button"):
            self.guided_button.configure(text="Guided Setup")
        folder = filedialog.askdirectory(
            title="Open Novel from MyNovel",
            initialdir=str(NOVEL_ROOT),
        )
        if not folder:
            return
        selected_folder = Path(folder).expanduser().resolve()
        allowed = {candidate.resolve() for candidate in find_novel_packages(NOVEL_ROOT)}
        if selected_folder not in allowed:
            self._show_copyable_error(
                "Open Novel",
                f"Choose a novel folder directly inside {NOVEL_ROOT}.",
            )
            return
        if not self._save_unsaved_writer_draft():
            return
        try:
            self.writer_engine.stop()
        except Exception:
            pass
        self._reset_new_novel_assistant(clear_brief=True)
        try:
            self.package = StoryPackage.load(selected_folder)
        except Exception as exc:
            self._show_copyable_error("Open Novel", f"Could not open that novel package.\n\n{exc}")
            return
        self.character_filename = None
        self.generated_scene = ""
        self.accepted_scene = ""
        self.accepted_scene_context = None
        self.focused_revision_history = []
        self.generated_scene_context = None
        self.generated_scene_start_state = None
        self.writer_generation_context = None
        self.writer_generation_start_state = None
        self.writer_generation_in_progress = False
        self.pending_state_patch = None
        self.interview_active = False
        self.interview_index = 0
        self.interview_pending_patch = None
        self.interview_pending_answer = ""
        self.last_novel_path = selected_folder
        self.dirty = False
        if hasattr(self, "writer_output_text"):
            self.writer_output_text.delete("1.0", "end")
            self.writer_state_preview.delete("1.0", "end")
        self._refresh_all()
        self._refresh_writer_models()
        self._chat("Builder", f'Opened "{self.package.story_bible.get("title", Path(folder).name)}".')
    def _save(self):
        if self.__dict__.get("writer_notes_update_in_progress", False):
            messagebox.showwarning(
                "Save",
                "StoryBuilder is updating the novel's temporary writing-notes file. Save again when that update finishes.",
            )
            return
        if self.package is None:
            return
        if not self._apply_all_edits():
            return
        if self.package.path is None:
            return self._save_as()
        try:
            self.package.save()
            self.dirty = False
            self._update_path_label()
            self._chat("Builder", "Saved.")
        except Exception as exc:
            self._show_copyable_error("Save", str(exc))

    def _save_as(self):
        if self.__dict__.get("writer_notes_update_in_progress", False):
            messagebox.showwarning(
                "Save As",
                "Finish the automatic writing-notes update before saving this novel.",
            )
            return
        if self.package is None:
            return
        if not self._apply_all_edits():
            return

        name = self.package.story_bible.get("title", "Untitled").strip() or "Untitled"
        folder_name = StoryPackage.safe_filename(name).removesuffix(".json")
        target = NOVEL_ROOT / folder_name
        current_path = (
            Path(self.package.path).expanduser().resolve()
            if self.package.path is not None
            else None
        )
        if target.exists() and current_path != target.resolve():
            self._show_copyable_error(
                "Save As",
                f"A folder for '{name}' already exists here:\n\n{target}\n\n"
                "Open that novel instead, or change the title before saving a new novel.",
            )
            return

        try:
            NOVEL_ROOT.mkdir(parents=True, exist_ok=True)
            self.package.save(target)
            self.last_novel_path = target
            self.dirty = False
            self._update_path_label()
            self._chat("Builder", f"Saved novel package to {target}.")
        except Exception as exc:
            self._show_copyable_error("Save As", str(exc))

    def _validate(self):
        if self.package is None:
            return
        if not self._apply_all_edits():
            return
        errors = validate_package(self.package)
        if errors:
            self._show_copyable_error("Validation", "Validation found problems:\n\n" + "\n".join(f"• {e}" for e in errors))
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
            self._show_copyable_error("Module", "Module JSON cannot be empty.")
            return

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            self._show_copyable_error(
                "Module",
                f"Invalid JSON at line {exc.lineno}, column {exc.colno}.\n\n{exc.msg}",
            )
            return

        if not isinstance(data, dict):
            self._show_copyable_error("Module", "Module JSON must contain an object at the top level.")
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

    def _writer_editor_prose(self) -> str:
        """Return the visible Writer text, with generated text as a recovery fallback."""
        if hasattr(self, "writer_output_text"):
            visible = self.writer_output_text.get("1.0", "end-1c").strip()
            if visible:
                return visible
        return str(getattr(self, "generated_scene", "") or "").strip()

    def _save_unsaved_writer_draft(self) -> bool:
        """Ask before saving or discarding unfinished Writer prose."""
        if self.package is None:
            return True
        if getattr(self, "writer_generation_in_progress", False) or self.__dict__.get("focused_revision_in_progress", False):
            messagebox.showwarning(
                "Writer",
                "A Writer task is still running. Let it finish before changing scenes or closing StoryBuilder.",
            )
            return False
        if self.__dict__.get("scene_planner_request_in_progress", False):
            messagebox.showwarning(
                "Scene Planner",
                "A Scene Planner request is still running. Let it finish before changing novels or closing StoryBuilder.",
            )
            return False
        if getattr(self, "scene_contract_building", False):
            messagebox.showwarning(
                "Scene Contract",
                "A scene contract is still being generated. Let it finish before changing novels or closing StoryBuilder.",
            )
            return False

        prose = self._writer_editor_prose()
        if not prose:
            return True

        accepted = str(getattr(self, "accepted_scene", "") or "").strip()
        if accepted and prose == accepted:
            # Accepted prose already exists in the manuscript.
            return True

        # An explicit Save Draft click marks this exact text as saved. Do not
        # ask again on close unless the author changes the Writer text afterward.
        if self.__dict__.get("writer_draft_saved_text") == prose:
            return True

        state = self.package.current_state
        fallback_key = (
            int(state.get("chapter", 1) or 1),
            int(state.get("scene", 1) or 1),
        )
        context = getattr(self, "generated_scene_context", None) or fallback_key
        try:
            chapter, scene = int(context[0]), int(context[1])
        except (TypeError, ValueError, IndexError):
            chapter, scene = fallback_key

        choice = messagebox.askyesnocancel(
            "Unfinished Writer Draft",
            (
                f"There is unfinished, unaccepted prose for Chapter {chapter}, Scene {scene}.\n\n"
                "Choose Yes to Save Draft before continuing.\n"
                "Choose No to discard this attempt without saving it. If an earlier saved draft "
                "contains different text, it will be kept.\n"
                "Choose Cancel to stay in StoryBuilder and keep the current text."
            ),
            parent=self,
        )
        if choice is None:
            return False

        manager = None
        draft_path = None
        if self.package.path is not None:
            manager = ManuscriptManager(self.package.path)
            target = manager.scene_path(chapter, scene)
            draft_path = target.with_name(target.stem + "_draft.txt")

        if choice is False:
            # Remove a draft file only when it contains exactly the text the
            # author is discarding. Preserve any earlier saved version with
            # different contents.
            if draft_path is not None and draft_path.is_file():
                try:
                    existing = draft_path.read_text(encoding="utf-8").strip()
                    if existing == prose.strip():
                        draft_path.unlink()
                        self._refresh_manuscript()
                except OSError as exc:
                    self._show_copyable_error(
                        "Discard Draft",
                        "StoryBuilder could not safely discard the matching draft file. "
                        "The current text has been kept.\n\n"
                        f"{exc}"
                    )
                    return False

            # If the scene was already accepted, restore its accepted prose;
            # otherwise clear this unaccepted attempt from the Writer.
            self.generated_scene = accepted
            self.writer_draft_saved_text = None
            if hasattr(self, "writer_output_text"):
                self.writer_output_text.delete("1.0", "end")
                if accepted:
                    self.writer_output_text.insert("1.0", accepted)
            if not accepted:
                self.generated_scene_context = None
                self.generated_scene_start_state = None
            return True

        if self.package.path is None or manager is None:
            messagebox.showwarning(
                "Save Draft",
                "There is unfinished Writer text, but this novel has no saved project folder yet. "
                "Use Save As / Export before saving the draft.",
                parent=self,
            )
            return False

        try:
            saved_path = manager.save_draft(chapter, scene, prose)
            self.generated_scene = prose
            self.generated_scene_context = (chapter, scene)
            self.writer_draft_saved_text = prose
            self._refresh_manuscript()
            self._chat(
                "Builder",
                f"Preserved unfinished Writer text as a draft for Chapter {chapter}, Scene {scene}: {saved_path.name}.",
            )
            return True
        except Exception as exc:
            self._show_copyable_error(
                "Save Draft",
                f"StoryBuilder could not preserve the unfinished scene. The current scene was not changed.\n\n{exc}"
            )
            return False

    def _prepare_for_scene_change(self, target_chapter: int, target_scene: int) -> bool:
        """Prevent scene switches from silently discarding or misfiling Writer text."""
        if self.package is None:
            return True

        if self.__dict__.get("focused_revision_in_progress", False):
            messagebox.showwarning(
                "Focused Change",
                "Wait for the focused edit to finish before changing scenes.",
            )
            return False

        state = self.package.current_state
        current_key = (
            int(state.get("chapter", 1) or 1),
            int(state.get("scene", 1) or 1),
        )
        target_key = (int(target_chapter), int(target_scene))
        if current_key == target_key:
            return True

        if getattr(self, "scene_contract_building", False):
            messagebox.showwarning(
                "Scene Contract",
                "A contract is still being generated for the current scene. Let it finish before changing scenes.",
            )
            return False

        accepted = str(getattr(self, "accepted_scene", "") or "").strip()
        if accepted and not state.get("scene_completed", False):
            # Save post-accept edits safely, but do not let navigation skip the
            # accepted scene's state-analysis/apply step.
            prose = self._writer_editor_prose()
            if prose and prose != accepted and not self._save_unsaved_writer_draft():
                return False
            messagebox.showwarning(
                "Finish Current Scene",
                "This scene has been accepted, but its state update has not been applied yet. "
                "Analyze the accepted scene and apply its state update before moving to another scene.",
            )
            return False

        return self._save_unsaved_writer_draft()

    def _clear_writer_scene_workspace(self, status: str | None = None) -> None:
        """Clear scene-specific Writer memory only after its text is safely saved."""
        self.generated_scene = ""
        self.accepted_scene = ""
        self.accepted_scene_context = None
        self.focused_revision_history = []
        self.generated_scene_context = None
        self.generated_scene_start_state = None
        self.writer_draft_saved_text = None
        self.writer_generation_context = None
        self.writer_generation_start_state = None
        self.pending_state_patch = None
        if hasattr(self, "writer_output_text"):
            self.writer_output_text.delete("1.0", "end")
        if hasattr(self, "writer_state_preview"):
            self.writer_state_preview.delete("1.0", "end")
        if status and hasattr(self, "writer_status"):
            self.writer_status.configure(text=status)
        if hasattr(self, "_update_writer_buttons"):
            self._update_writer_buttons()

    def _restore_previous_scene_end_state(self):
        """Restore the current scene's starting baseline from the preceding accepted scene."""
        if self.package is None or self.package.path is None:
            messagebox.showwarning(
                "Restore Previous End State",
                "Save the novel package before restoring a previous scene's ending state.",
            )
            return

        if (
            getattr(self, "writer_generation_in_progress", False)
            or self.__dict__.get("focused_revision_in_progress", False)
            or getattr(self, "scene_contract_building", False)
            or self.__dict__.get("writer_notes_update_in_progress", False)
        ):
            messagebox.showwarning(
                "Restore Previous End State",
                "Wait for the active Writer task, Scene Direction build, or writing-notes review to finish first.",
            )
            return

        state = self.package.current_state
        chapter = int(state.get("chapter", 1) or 1)
        scene = int(state.get("scene", 1) or 1)
        target_key = (chapter, scene)
        manager = ManuscriptManager(Path(self.package.path))

        if state.get("scene_completed") or str(getattr(self, "accepted_scene", "") or "").strip():
            messagebox.showwarning(
                "Restore Previous End State",
                "This scene has already been accepted or marked complete. Its state will not be reset automatically.",
            )
            return

        if any(manager.scene_numbers(path) == target_key for path in manager.list_scenes()):
            messagebox.showwarning(
                "Restore Previous End State",
                f"Accepted manuscript text already exists for Chapter {chapter}, Scene {scene}. "
                "The state was not changed.",
            )
            return

        if scene > 1:
            previous_chapter, previous_scene = chapter, scene - 1
        elif chapter > 1:
            prior_scenes = [
                (numbers[1], path)
                for path in manager.list_scenes()
                if (numbers := manager.scene_numbers(path)) is not None
                and numbers[0] == chapter - 1
            ]
            if not prior_scenes:
                messagebox.showwarning(
                    "Restore Previous End State",
                    f"No accepted scenes were found in Chapter {chapter - 1}. The state was not changed.",
                )
                return
            previous_scene, _previous_path = max(prior_scenes, key=lambda item: item[0])
            previous_chapter = chapter - 1
        else:
            messagebox.showinfo(
                "Restore Previous End State",
                "Chapter 1, Scene 1 has no previous scene to restore from.",
            )
            return

        previous_after_path = manager.state_after_path(previous_chapter, previous_scene)
        if not previous_after_path.is_file():
            messagebox.showwarning(
                "Restore Previous End State",
                f"No saved ending-state snapshot exists for Chapter {previous_chapter}, Scene {previous_scene}. "
                "Nothing was changed.",
            )
            return

        try:
            saved_state = json.loads(previous_after_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._show_copyable_error(
                "Restore Previous End State",
                f"Could not read the previous scene's saved ending state.\n\n{exc}",
            )
            return

        if not isinstance(saved_state, dict):
            self._show_copyable_error(
                "Restore Previous End State",
                "The previous scene's saved ending state is not a JSON object. Nothing was changed.",
            )
            return

        restored_situation = str(saved_state.get("current_situation", "") or "").strip()
        if not restored_situation:
            messagebox.showwarning(
                "Restore Previous End State",
                "The previous scene's saved ending state has no Current Situation. Nothing was changed.",
            )
            return

        preview = restored_situation
        if not self._ask_yes_no(
            "Restore Previous End State",
            f"Restore the starting state for Chapter {chapter}, Scene {scene} from the saved ending state of "
            f"Chapter {previous_chapter}, Scene {previous_scene}?\n\n"
            f"Restored Current Situation:\n{preview}\n\n"
            "This replaces the current state fields and resets the active scene/status flags. "
            "It does not delete manuscript scenes, characters, or the Scene Idea. "
            "Unsaved current-state edits will be replaced.\n\n"
            "Are you sure you want to restore this state?",
        ):
            return

        if not self._save_unsaved_writer_draft():
            return

        old_state = json.loads(json.dumps(state, ensure_ascii=False))
        restored = json.loads(json.dumps(saved_state, ensure_ascii=False))
        restored = remove_prior_chapter_opening_markers(
            restored,
            previous_chapter,
            chapter,
        )
        restored["chapter"] = chapter
        restored["scene"] = scene
        restored["scene_completed"] = False
        restored["chapter_completed"] = False
        restored["status"] = "in_progress"
        planned_cast = self._scene_plan_cast(chapter, scene)
        if planned_cast:
            restored["scene_cast"] = planned_cast

        self.package.current_state = restored
        self.dirty = True
        try:
            self._clear_writer_scene_workspace(
                f"Restored the starting state for Chapter {chapter}, Scene {scene} from Chapter "
                f"{previous_chapter}, Scene {previous_scene}."
            )
            self._refresh_all()
            self._build_scene_direction()
            self.package.save()
            self.dirty = False
            self._update_path_label()
            self._chat(
                "Builder",
                f"Restored Chapter {chapter}, Scene {scene} from the saved ending state of "
                f"Chapter {previous_chapter}, Scene {previous_scene}.",
            )
            writer_status = self.__dict__.get("writer_status")
            if writer_status is not None:
                writer_status.configure(
                    text=f"Starting state restored for Chapter {chapter}, Scene {scene}. "
                    "Reset the old contract, then rebuild it from the preserved Scene Idea."
                )
        except Exception as exc:
            self.package.current_state = old_state
            self.dirty = True
            self._refresh_all()
            self._show_copyable_error(
                "Restore Previous End State",
                f"The state could not be saved, so the in-memory state was rolled back.\n\n{exc}",
            )

    def _apply_state_edits(self):
        if self.package is None:
            return False
        state = self.package.current_state
        old_chapter = int(state.get("chapter", 1) or 1)
        old_scene = int(state.get("scene", 1) or 1)
        chapter_text = self.state_vars["chapter"].get().strip()
        scene_text = self.state_vars["scene"].get().strip()
        target_chapter = int(chapter_text) if chapter_text.isdigit() else 1
        target_scene = int(scene_text) if scene_text.isdigit() else 1
        scene_changed = (target_chapter, target_scene) != (old_chapter, old_scene)

        if scene_changed:
            if not self._prepare_for_scene_change(target_chapter, target_scene):
                self.state_vars["chapter"].set(str(old_chapter))
                self.state_vars["scene"].set(str(old_scene))
                return False
            # Save contract edits to the scene currently displayed before the
            # state change refreshes the editor for the destination scene.
            try:
                self._apply_scene_contract_edits()
            except (TypeError, ValueError) as exc:
                self.state_vars["chapter"].set(str(old_chapter))
                self.state_vars["scene"].set(str(old_scene))
                self._show_copyable_error(
                    "Scene Contract",
                    "The current scene contract could not be saved, so the scene was not changed.\n\n" + str(exc),
                )
                return False

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
        self._update_path_label()

        if scene_changed:
            self._clear_writer_scene_workspace(
                "Scene changed. Any unfinished prose was preserved as a draft in Manuscript."
            )

        # Manual edits to chapter, scene, cast, location, time, or continuity
        # immediately refresh the related contract view and Writer direction.
        if hasattr(self, "_refresh_scene_contract_editor"):
            self._refresh_scene_contract_editor()
        self._build_scene_direction()
        return True

    def _apply_state_edits_and_save(self):
        """Apply Current State form edits and persist the package immediately."""
        if self.package is None:
            return

        was_dirty = bool(self.dirty)
        if not self._apply_state_edits():
            return

        if self.package.path is None:
            self.dirty = True
            self._show_copyable_error(
                "Apply State Edits",
                "The state changes are applied in the open session, but this novel package "
                "has no saved folder yet. Use Save / Save As before closing StoryBuilder.",
            )
            return

        try:
            self.package.save()
            # Do not clear a pre-existing dirty flag here. This button persists
            # the package's current model, but should not imply other pending
            # editor text has also been applied.
            self.dirty = was_dirty
            self._update_path_label()
            self._chat("Builder", "Current State edits applied and saved.")
        except Exception as exc:
            self.dirty = True
            self._show_copyable_error(
                "Apply State Edits",
                "The state changes are applied in memory but could not be saved to disk. "
                "They may be lost if StoryBuilder closes. Resolve the save error before restarting.\n\n"
                + str(exc),
            )

    def _reload_canon_rules_editor(self):
        if self.package is None:
            return
        rules = self.package.story_bible.get("canon_rules", [])
        if isinstance(rules, str):
            rules = [line.strip() for line in rules.splitlines() if line.strip()]
        if not isinstance(rules, list):
            rules = []
        self.canon_rules_text.delete("1.0", "end")
        self.canon_rules_text.insert("1.0", "\n".join(str(rule) for rule in rules if str(rule).strip()))
        self.canon_rules_status.configure(text="Editor reloaded from the current working canon.")

    def _review_and_save_canon_rules(self):
        if self.package is None:
            return
        proposed, seen = [], set()
        for line in self.canon_rules_text.get("1.0", "end-1c").splitlines():
            rule = line.strip()
            if rule and rule.casefold() not in seen:
                proposed.append(rule)
                seen.add(rule.casefold())
        current = self.package.story_bible.get("canon_rules", [])
        if isinstance(current, str):
            current = current.splitlines()
        if not isinstance(current, list):
            current = []
        current = [str(rule).strip() for rule in current if str(rule).strip()]
        current_keys = {rule.casefold() for rule in current}
        proposed_keys = {rule.casefold() for rule in proposed}
        added = [rule for rule in proposed if rule.casefold() not in current_keys]
        removed = [rule for rule in current if rule.casefold() not in proposed_keys]
        if not added and not removed:
            self.canon_rules_status.configure(text="No canon changes to save.")
            messagebox.showinfo("Canon & Rules", "There are no changes to save.")
            return
        review = []
        if added:
            review.extend(["RULES TO ADD", *[f"+ {rule}" for rule in added]])
        if removed:
            if review:
                review.append("")
            review.extend(["RULES TO REMOVE", *[f"- {rule}" for rule in removed]])
        review.extend(["", "These rules guide future generated scenes.", "Accepted manuscript prose will not be edited."])
        if not self._ask_yes_no("Review Canon Changes", "\n".join(review)):
            self.canon_rules_status.configure(text="No changes applied.")
            return
        self.package.story_bible["canon_rules"] = proposed
        self.dirty = True
        self._update_path_label()
        self.canon_rules_status.configure(text="Canon rules approved. Saving now.")
        self._save()

    def _current_change_data(self):
        state = self.package.current_state if self.package is not None else {}
        summary = {
            key: state.get(key)
            for key in ("chapter", "scene", "current_situation", "character_knowledge", "continuity_requirements")
            if key in state
        }
        return {
            "story_bible": json.loads(json.dumps(self.package.story_bible, ensure_ascii=False)),
            "characters": json.loads(json.dumps(self.package.characters, ensure_ascii=False)),
            "current_state_summary": summary,
        }

    def _reset_new_novel_assistant(self, *, clear_brief=False):
        self.new_novel_assistant_request_token += 1
        self.new_novel_pending_proposal = None
        self.new_novel_pending_brief = ""
        self.new_novel_pending_package = None
        self.new_novel_assistant_in_progress = False
        if clear_brief and hasattr(self, "new_novel_brief_text"):
            self.new_novel_brief_text.delete("1.0", "end")
        if hasattr(self, "new_novel_proposal_text"):
            self.new_novel_proposal_text.configure(state="normal")
            self.new_novel_proposal_text.delete("1.0", "end")
            self.new_novel_proposal_text.insert("1.0", "No proposal pending.")
            self.new_novel_proposal_text.configure(state="disabled")
        if hasattr(self, "new_novel_approve_button"):
            self.new_novel_approve_button.configure(state="disabled")
            self.new_novel_reject_button.configure(state="disabled")
            self.new_novel_prepare_button.configure(
                state="disabled" if self.new_novel_assistant_worker_running else "normal"
            )
        if hasattr(self, "new_novel_assistant_status"):
            message = (
                "The previous local-model request is still finishing. Its proposal will be discarded."
                if self.new_novel_assistant_worker_running
                else "No proposal pending. Preparing a proposal does not change your novel."
            )
            self.new_novel_assistant_status.configure(text=message)

    def _prepare_new_novel_proposal(self):
        if self.__dict__.get("scene_planner_request_in_progress", False):
            messagebox.showwarning("Scene Planner", "Let the current planning request finish before starting another model task.")
            return
        if self.package is None:
            self._show_copyable_error("New Novel Assistant", "Click New Novel first.")
            return
        if self.new_novel_assistant_worker_running:
            messagebox.showwarning(
                "New Novel Assistant",
                "The local model is still preparing the previous proposal. Wait for it to finish before starting another, so StoryBuilder does not load two copies.",
            )
            return
        if not self._apply_all_edits():
            return
        if not is_blank_new_package(self.package):
            messagebox.showwarning(
                "New Novel Assistant",
                "This assistant only builds into an untouched New Novel workspace. Click New Novel first. Your existing novel will not be overwritten.",
            )
            return
        brief = self.new_novel_brief_text.get("1.0", "end-1c").strip()
        if not brief:
            messagebox.showwarning("New Novel Assistant", "Describe your story idea in plain English first.")
            return
        if len(brief) > 12000:
            messagebox.showwarning("New Novel Assistant", "Keep the story description under 12,000 characters.")
            return
        writer_running = self.writer_engine.child is not None and self.writer_engine.child.isalive()
        if writer_running:
            messagebox.showwarning(
                "New Novel Assistant",
                "Stop the Writer before preparing a starter package. StoryBuilder uses the same local model and should not load it twice.",
            )
            return
        selected = self.writer_model_var.get().strip()
        model = self.writer_engine.model_path
        try:
            if selected:
                model = WriterEngine.validate_model(selected)
            elif model is not None:
                model = WriterEngine.validate_model(model)
            else:
                raise ValueError("Select a local GGUF model in the Writer tab first.")
        except Exception as exc:
            self._show_copyable_error("New Novel Assistant", str(exc))
            return

        self.new_novel_pending_proposal = None
        self.new_novel_pending_brief = brief
        self.new_novel_pending_package = self.package
        self.new_novel_assistant_request_token += 1
        token = self.new_novel_assistant_request_token
        source_package = self.package
        self.new_novel_assistant_in_progress = True
        self.new_novel_assistant_worker_running = True
        self.new_novel_prepare_button.configure(state="disabled")
        self.new_novel_approve_button.configure(state="disabled")
        self.new_novel_reject_button.configure(state="disabled")
        self.new_novel_assistant_status.configure(
            text="The selected local model is preparing a draft package. Nothing has been applied."
        )
        self.new_novel_proposal_text.configure(state="normal")
        self.new_novel_proposal_text.delete("1.0", "end")
        self.new_novel_proposal_text.insert("1.0", "Preparing the starter package with the selected local model...")
        self.new_novel_proposal_text.configure(state="disabled")

        def work():
            try:
                proposal = build_new_novel_proposal(model, author_brief=brief)
                error = None
            except Exception as exc:
                proposal, error = None, str(exc)
            # Worker thread publishes data only. Tk widgets are updated by the main-thread poller.
            self.new_novel_assistant_results.put((token, proposal, error, brief, source_package))

        self.new_novel_assistant_thread = threading.Thread(target=work, daemon=True)
        self.new_novel_assistant_thread.start()
        self.after(100, self._poll_new_novel_assistant_results)

    def _poll_new_novel_assistant_results(self):
        if self._closing:
            return
        try:
            token, proposal, error, brief, source_package = self.new_novel_assistant_results.get_nowait()
        except queue.Empty:
            if self.new_novel_assistant_worker_running:
                self.after(100, self._poll_new_novel_assistant_results)
            return
        self.new_novel_assistant_worker_running = False
        if token != self.new_novel_assistant_request_token:
            if not self.new_novel_assistant_in_progress:
                self.new_novel_prepare_button.configure(state="normal")
                self.new_novel_assistant_status.configure(
                    text="The previous proposal was discarded because the active novel changed."
                )
            return
        self.new_novel_assistant_in_progress = False
        self.new_novel_prepare_button.configure(state="normal")
        self._finish_new_novel_proposal(proposal, error, brief, source_package)

    def _finish_new_novel_proposal(self, proposal, error, brief, source_package):
        if error:
            self._show_copyable_error("New Novel Assistant", error)
            self.new_novel_assistant_status.configure(text="Proposal failed. Nothing was changed.")
            self.new_novel_proposal_text.configure(state="normal")
            self.new_novel_proposal_text.delete("1.0", "end")
            self.new_novel_proposal_text.insert("1.0", "No proposal was applied.")
            self.new_novel_proposal_text.configure(state="disabled")
            return
        if source_package is not self.package or not is_blank_new_package(self.package):
            self.new_novel_assistant_status.configure(
                text="The active workspace changed while the proposal was prepared. Nothing was applied."
            )
            return
        try:
            normalized = normalize_new_novel_proposal(proposal, author_brief=brief)
            preview = render_new_novel_preview(normalized)
        except Exception as exc:
            self._show_copyable_error(
                "New Novel Assistant",
                "The model's response could not be used safely. Nothing was changed.\n\n" + str(exc),
            )
            self.new_novel_assistant_status.configure(text="No proposal applied. Revise the description or try again.")
            return
        self.new_novel_pending_proposal = normalized
        self.new_novel_pending_brief = brief
        self.new_novel_pending_package = source_package
        self.new_novel_proposal_text.configure(state="normal")
        self.new_novel_proposal_text.delete("1.0", "end")
        self.new_novel_proposal_text.insert("1.0", preview)
        self.new_novel_proposal_text.configure(state="disabled")
        self.new_novel_approve_button.configure(state="normal")
        self.new_novel_reject_button.configure(state="normal")
        self.new_novel_assistant_status.configure(text="Review the proposed package. Nothing has been applied yet.")

    def _approve_new_novel_proposal(self):
        proposal = self.new_novel_pending_proposal
        if not isinstance(proposal, dict) or self.package is None:
            return
        if self.new_novel_pending_package is not self.package or not is_blank_new_package(self.package):
            self._show_copyable_error(
                "New Novel Assistant",
                "The workspace changed after this proposal was prepared. No changes were applied. Start with a blank New Novel workspace and prepare another proposal.",
            )
            self._reset_new_novel_assistant(clear_brief=False)
            return
        try:
            summary = apply_new_novel_proposal(self.package, proposal)
        except Exception as exc:
            self._show_copyable_error("New Novel Assistant", "No changes were applied.\n\n" + str(exc))
            return
        self.dirty = True
        self.new_novel_pending_proposal = None
        self.new_novel_pending_brief = ""
        self.new_novel_pending_package = None
        self.new_novel_approve_button.configure(state="disabled")
        self.new_novel_reject_button.configure(state="disabled")
        self.new_novel_proposal_text.configure(state="normal")
        self.new_novel_proposal_text.delete("1.0", "end")
        self.new_novel_proposal_text.insert("1.0", "Starter package approved and applied to the working novel.")
        self.new_novel_proposal_text.configure(state="disabled")
        self._refresh_all()
        self.new_novel_assistant_status.configure(
            text=f"Built the {summary}. Choose Save to name the novel's folder and save the package."
        )
        self._chat("Builder", f"Approved New Novel Assistant proposal: {summary}.")
        self._save()

    def _reject_new_novel_proposal(self):
        if self.new_novel_pending_proposal is None:
            return
        self.new_novel_pending_proposal = None
        self.new_novel_pending_brief = ""
        self.new_novel_pending_package = None
        self.new_novel_approve_button.configure(state="disabled")
        self.new_novel_reject_button.configure(state="disabled")
        self.new_novel_proposal_text.configure(state="normal")
        self.new_novel_proposal_text.delete("1.0", "end")
        self.new_novel_proposal_text.insert("1.0", "Proposal rejected. Your novel was not changed.")
        self.new_novel_proposal_text.configure(state="disabled")
        self.new_novel_assistant_status.configure(
            text="Proposal rejected. Edit your description and prepare another, or leave the workspace unchanged."
        )

    def _change_assistant_source_signature(self):

        if self.package is None:
            return ""
        return json.dumps({
            "story_bible": self.package.story_bible,
            "characters": self.package.characters,
            "current_state": self.package.current_state,
        }, sort_keys=True, ensure_ascii=False)

    @staticmethod
    def _scene_planner_canonical_path(path):
        if path is None:
            return None
        try:
            return str(Path(path).expanduser().resolve())
        except (OSError, RuntimeError):
            return str(path)

    def _refresh_scene_planner_target(self):
        if "scene_planner_target_var" not in self.__dict__:
            return
        if self.package is None:
            self.scene_planner_target_var.set("Open a saved novel to plan a scene.")
            self.scene_planner_package_path = None
            self.scene_planner_target = None
            self.scene_planner_start_state = None
            self._update_scene_planner_buttons()
            return
        state = self.package.current_state
        current_target = (int(state.get("chapter", 1) or 1), int(state.get("scene", 1) or 1))
        current_path = self._scene_planner_canonical_path(self.package.path)
        active = bool(self.scene_planner_messages or self.scene_planner_pending_proposal or self.scene_planner_request_in_progress)
        if self.scene_planner_target is None or not active:
            self.scene_planner_target = current_target
            self.scene_planner_package_path = current_path
            try:
                self.scene_planner_start_state = json.loads(json.dumps(state, ensure_ascii=False))
            except (TypeError, ValueError):
                self.scene_planner_start_state = dict(state)
        target = self.scene_planner_target or current_target
        label = f"Planning target: Chapter {target[0]}, Scene {target[1]}"
        if current_target != target or current_path != self.scene_planner_package_path:
            label += " (session pinned; clear the conversation to retarget)"
        if current_path is None:
            label += " | Save the novel package first"
        self.scene_planner_target_var.set(label)
        self._update_scene_planner_buttons()

    def _update_scene_planner_buttons(self):
        if "scene_planner_send_button" not in self.__dict__:
            return
        busy = bool(self.scene_planner_request_in_progress)
        saved = bool(self.package is not None and getattr(self.package, "path", None) is not None)
        pending = isinstance(self.scene_planner_pending_proposal, dict)
        self.scene_planner_send_button.configure(state="normal" if saved and not busy and not pending else "disabled")
        self.scene_planner_prepare_button.configure(state="normal" if self.scene_planner_messages and not busy and not pending else "disabled")
        self.scene_planner_clear_button.configure(state="disabled" if busy else "normal")
        self.scene_planner_approve_button.configure(state="normal" if pending and not busy else "disabled")
        self.scene_planner_reject_button.configure(state="normal" if pending and not busy else "disabled")

    def _scene_planner_snapshot(self):
        if self.package is None:
            raise ValueError("Open a novel before planning a scene.")
        if getattr(self.package, "path", None) is None:
            raise ValueError("Save the novel package before using the Scene Planner.")
        if self.scene_planner_target is None:
            self._refresh_scene_planner_target()
        package_path = self._scene_planner_canonical_path(self.package.path)
        if package_path != self.scene_planner_package_path:
            raise ValueError("The open novel changed while this planning conversation was active. Click Clear Conversation to begin a session for the current novel.")
        chapter, scene = self.scene_planner_target
        plan_path, plan_text = read_story_plan_file(self.package.path)
        state = self.scene_planner_start_state or self.package.current_state
        guidance = getattr(self.package, "extra_json", {}).get("writing_guidance.json", {})
        entry = self._chapter_scene_guidance(guidance, chapter, scene) or {}
        context = {
            "story_bible": self.package.story_bible,
            "characters": self.package.characters,
            "current_state": state,
            "saved_scene_idea": str(entry.get("scene_idea", "") or ""),
        }
        return {"package_path": package_path, "plan_path": plan_path, "plan_text": plan_text,
                "chapter": chapter, "scene": scene, "story_context": context}

    def _scene_planner_model_path(self):
        selected = self.writer_model_var.get().strip()
        model = self.writer_engine.model_path
        if selected:
            model = WriterEngine.validate_model(selected)
        elif model is not None:
            model = WriterEngine.validate_model(model)
        else:
            raise ValueError("Select a local GGUF model in the Writer tab first.")
        return model

    def _scene_planner_model_ready(self):
        child = getattr(self.writer_engine, "child", None)
        if child is not None and child.isalive():
            self._show_copyable_error("Scene Planner", "Stop the Writer before using the Scene Planner so StoryBuilder does not load two copies of the local model.")
            return False
        busy_flags = ("writer_generation_in_progress", "scene_contract_building", "state_analysis_in_progress",
                      "scene_flow_review_in_progress", "change_request_in_progress",
                      "new_novel_assistant_in_progress", "writer_notes_update_in_progress")
        if any(bool(getattr(self, name, False)) for name in busy_flags) or bool(self.__dict__.get("focused_revision_in_progress", False)):
            self._show_copyable_error("Scene Planner", "Another StoryBuilder model task is running. Let it finish before starting the Scene Planner.")
            return False
        return True

    def _render_scene_planner_log(self):
        self.scene_planner_log.configure(state="normal")
        self.scene_planner_log.delete("1.0", "end")
        for item in self.scene_planner_messages:
            label = "You" if item.get("role") == "user" else "Scene Planner"
            self.scene_planner_log.insert("end", f"{label}:\n{item.get('content', '').strip()}\n\n")
        self.scene_planner_log.configure(state="disabled")
        self.scene_planner_log.see("end")

    def _send_scene_planner_message(self):
        if self.scene_planner_request_in_progress:
            return
        if isinstance(self.scene_planner_pending_proposal, dict):
            self.scene_planner_status.configure(text="Approve or reject the current proposal before continuing the conversation.")
            return
        message = self.scene_planner_input_text.get("1.0", "end-1c").strip()
        if not message:
            messagebox.showwarning("Scene Planner", "Enter what you want to discuss first.")
            return
        if not self._scene_planner_model_ready():
            return
        try:
            model = self._scene_planner_model_path()
            snap = self._scene_planner_snapshot()
        except Exception as exc:
            self._show_copyable_error("Scene Planner", str(exc))
            return
        messages = [*self.scene_planner_messages, {"role": "user", "content": message}]
        self.scene_planner_request_in_progress = True
        self.scene_planner_task_kind = "conversation"
        self.scene_planner_status.configure(text="The local model is considering the scene. No plan file is being changed.")
        self._update_scene_planner_buttons()
        def work():
            try:
                reply = generate_scene_planner_reply(
                    model, chapter=snap["chapter"], scene=snap["scene"], plan_text=snap["plan_text"],
                    story_context=snap["story_context"], messages=messages,
                )
                error = None
            except Exception as exc:
                reply, error = None, str(exc)
            try:
                self.after(0, lambda reply=reply, error=error: self._finish_scene_planner_turn(message, reply, error))
            except tk.TclError:
                pass
        self.scene_planner_thread = threading.Thread(target=work, daemon=True)
        self.scene_planner_thread.start()

    def _finish_scene_planner_turn(self, user_message, reply, error):
        self.scene_planner_request_in_progress = False
        self.scene_planner_task_kind = None
        if error:
            self.scene_planner_status.configure(text="The conversation turn failed. No plan file was changed. " + str(error))
        else:
            self.scene_planner_messages.extend([
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": str(reply).strip()},
            ])
            self._render_scene_planner_log()
            self.scene_planner_input_text.delete("1.0", "end")
            self.scene_planner_status.configure(text="Conversation updated. Nothing has been saved to STORY_PLAN.md.")
        self._refresh_scene_planner_target()
        self._update_scene_planner_buttons()

    def _prepare_scene_planner_proposal(self):
        if self.scene_planner_request_in_progress:
            return
        if isinstance(self.scene_planner_pending_proposal, dict):
            self.scene_planner_status.configure(text="Reject the current proposal before preparing another one.")
            return
        if not self.scene_planner_messages:
            messagebox.showwarning("Scene Planner", "Start a planning conversation and send at least one message before preparing a proposal.")
            return
        if self.scene_planner_input_text.get("1.0", "end-1c").strip():
            messagebox.showwarning("Scene Planner", "Send your latest message before preparing the plan proposal.")
            return
        if not self._scene_planner_model_ready():
            return
        try:
            model = self._scene_planner_model_path()
            snap = self._scene_planner_snapshot()
        except Exception as exc:
            self._show_copyable_error("Scene Planner", str(exc))
            return
        self.scene_planner_request_in_progress = True
        self.scene_planner_task_kind = "proposal"
        self.scene_planner_status.configure(text="Preparing a reviewable scene-plan proposal. The original plan is still unchanged.")
        self._update_scene_planner_buttons()
        messages = list(self.scene_planner_messages)
        def work():
            try:
                result = prepare_scene_plan_proposal(
                    model, chapter=snap["chapter"], scene=snap["scene"], plan_text=snap["plan_text"],
                    story_context=snap["story_context"], messages=messages,
                )
                error = None
            except Exception as exc:
                result, error = None, str(exc)
            try:
                self.after(0, lambda result=result, error=error: self._finish_scene_planner_proposal(snap, result, error))
            except tk.TclError:
                pass
        self.scene_planner_thread = threading.Thread(target=work, daemon=True)
        self.scene_planner_thread.start()

    def _finish_scene_planner_proposal(self, snap, result, error):
        self.scene_planner_request_in_progress = False
        self.scene_planner_task_kind = None
        if error:
            self.scene_planner_status.configure(text="The proposal could not be prepared. No plan file was changed. " + str(error))
        else:
            self.scene_planner_title_var.set(result["title"])
            self.scene_planner_proposal_text.delete("1.0", "end")
            self.scene_planner_proposal_text.insert("1.0", result["plan_body"])
            self.scene_planner_pending_proposal = {
                "path": snap["plan_path"], "source_text": snap["plan_text"],
                "package_path": snap["package_path"], "chapter": snap["chapter"], "scene": snap["scene"],
            }
            self.scene_planner_status.configure(text=f"Review the proposed plan for Chapter {snap['chapter']}, Scene {snap['scene']}. You may edit it; nothing is saved until you click Approve & Save Plan.")
        self._refresh_scene_planner_target()
        self._update_scene_planner_buttons()

    def _approve_scene_plan_proposal(self):
        pending = self.scene_planner_pending_proposal
        if not isinstance(pending, dict) or self.scene_planner_request_in_progress:
            return
        if self.package is None or getattr(self.package, "path", None) is None:
            self.scene_planner_status.configure(text="No saved novel is open. Nothing was changed.")
            return
        if self._scene_planner_canonical_path(self.package.path) != pending["package_path"]:
            self.scene_planner_status.configure(text="The active novel changed after this proposal was prepared. Nothing was saved. Clear the conversation and prepare a fresh proposal.")
            self.scene_planner_pending_proposal = None
            self._update_scene_planner_buttons()
            return
        chapter, scene = int(pending["chapter"]), int(pending["scene"])
        try:
            fields = validate_scene_plan_fields(
                self.scene_planner_title_var.get(), self.scene_planner_proposal_text.get("1.0", "end-1c"),
                chapter=chapter, scene=scene,
            )
            current_path, current_text = read_story_plan_file(self.package.path)
            if (self._scene_planner_canonical_path(current_path) != self._scene_planner_canonical_path(pending["path"])
                    or current_text != pending["source_text"]):
                self.scene_planner_pending_proposal = None
                self.scene_planner_status.configure(text="STORY_PLAN.md changed after this proposal was prepared. Nothing was saved. Review the current plan and prepare a fresh proposal.")
                self._update_scene_planner_buttons()
                return
            updated = update_scene_plan_markdown(current_text or "", chapter, scene, fields["title"], fields["plan_body"])
            backup_path = save_scene_plan_file(current_path, updated)
        except Exception as exc:
            self._show_copyable_error("Scene Planner", "The plan was not saved. Review the proposal and correct the issue before trying again.\n\n" + str(exc))
            return
        self.scene_planner_pending_proposal = None
        self._refresh_scene_contract_editor()
        self._refresh_writer_scene_guidance()
        backup_note = f" Previous plan backed up locally to {backup_path}." if backup_path is not None else " A new STORY_PLAN.md file was created."
        self.scene_planner_status.configure(
            text=f"Approved plan saved for Chapter {chapter}, Scene {scene} in STORY_PLAN.md."
                 + backup_note
                 + " Any existing saved Scene Idea was preserved; use Scene Contract > Load from STORY_PLAN.md to refresh it."
        )
        self._update_scene_planner_buttons()

    def _reject_scene_plan_proposal(self):
        self.scene_planner_pending_proposal = None
        self.scene_planner_title_var.set("")
        self.scene_planner_proposal_text.delete("1.0", "end")
        self.scene_planner_status.configure(text="Proposal rejected. STORY_PLAN.md and all saved novel data remain unchanged.")
        self._update_scene_planner_buttons()

    def _clear_scene_planner_conversation(self):
        if self.scene_planner_request_in_progress:
            messagebox.showwarning("Scene Planner", "Wait for the current local-model request to finish before clearing the conversation.")
            return
        self.scene_planner_messages = []
        self.scene_planner_pending_proposal = None
        self.scene_planner_title_var.set("")
        self.scene_planner_proposal_text.delete("1.0", "end")
        self.scene_planner_input_text.delete("1.0", "end")
        self.scene_planner_log.configure(state="normal")
        self.scene_planner_log.delete("1.0", "end")
        self.scene_planner_log.configure(state="disabled")
        self.scene_planner_target = None
        self.scene_planner_package_path = None
        self.scene_planner_start_state = None
        self._refresh_scene_planner_target()
        self.scene_planner_status.configure(text="Conversation cleared. The current novel and scene are ready for a new planning session.")
        self._update_scene_planner_buttons()

    def _prepare_change_request(self):
        if self.__dict__.get("scene_planner_request_in_progress", False):
            messagebox.showwarning("Scene Planner", "Let the current planning request finish before starting another model task.")
            return
        if self.package is None:
            self._show_copyable_error("Change Assistant", "Open or create a novel first.")
            return
        if self.change_request_in_progress:
            return
        request = self.change_request_text.get("1.0", "end-1c").strip()
        if not request:
            messagebox.showwarning("Change Assistant", "Describe the change you want to make.")
            return
        writer_running = self.writer_engine.child is not None and self.writer_engine.child.isalive()
        if writer_running:
            messagebox.showwarning("Change Assistant", "Stop the Writer before preparing a proposal.")
            return
        if not self._apply_all_edits():
            return
        selected = self.writer_model_var.get().strip()
        model = self.writer_engine.model_path
        try:
            if selected:
                model = WriterEngine.validate_model(selected)
            elif model is not None:
                model = WriterEngine.validate_model(model)
            else:
                raise ValueError("Select a local GGUF model in the Writer tab first.")
        except Exception as exc:
            self._show_copyable_error("Change Assistant", str(exc))
            return

        existing_data = self._current_change_data()
        signature = self._change_assistant_source_signature()
        self.change_pending_patch = None
        self.change_pending_snapshot = None
        self.change_pending_request = request
        self.change_request_in_progress = True
        self.change_propose_button.configure(state="disabled")
        self.change_approve_button.configure(state="disabled")
        self.change_reject_button.configure(state="disabled")
        self.change_assistant_status.configure(text="The local model is preparing a proposal. No changes have been applied.")
        self.change_proposal_text.configure(state="normal")
        self.change_proposal_text.delete("1.0", "end")
        self.change_proposal_text.insert("1.0", "Preparing a proposal with the selected local model...")
        self.change_proposal_text.configure(state="disabled")

        def work():
            try:
                patch = structure_change_request(model, request=request, existing_data=existing_data)
                error = None
            except Exception as exc:
                patch, error = None, str(exc)
            self.after(
                0,
                lambda patch=patch, error=error, request=request, signature=signature:
                    self._finish_change_request_proposal(patch, error, request, signature),
            )

        self.change_request_thread = threading.Thread(target=work, daemon=True)
        self.change_request_thread.start()

    def _finish_change_request_proposal(self, patch, error, request, signature):
        self.change_request_in_progress = False
        self.change_propose_button.configure(state="normal")
        if error:
            self._show_copyable_error("Change Assistant", error)
            self.change_assistant_status.configure(text="Proposal failed. Nothing was changed.")
            self.change_proposal_text.configure(state="normal")
            self.change_proposal_text.delete("1.0", "end")
            self.change_proposal_text.insert("1.0", "No changes were applied.")
            self.change_proposal_text.configure(state="disabled")
            return
        try:
            normalized = normalize_change_patch(patch, self.package, request)
            preview = render_change_preview(self.package, normalized)
        except Exception as exc:
            self._show_copyable_error("Change Assistant", "The response could not be used safely. Nothing was changed.\n\n" + str(exc))
            self.change_assistant_status.configure(text="No proposal applied. Try rewording the request.")
            return
        self.change_pending_patch = normalized
        self.change_pending_request = request
        self.change_pending_snapshot = signature
        self.change_proposal_text.configure(state="normal")
        self.change_proposal_text.delete("1.0", "end")
        self.change_proposal_text.insert("1.0", preview)
        self.change_proposal_text.configure(state="disabled")
        self.change_approve_button.configure(state="normal")
        self.change_reject_button.configure(state="normal")
        self.change_assistant_status.configure(text="Review the proposed changes. Nothing has been applied yet.")

    def _approve_change_request(self):
        if self.package is None or not isinstance(self.change_pending_patch, dict):
            return
        if not self._apply_all_edits():
            return
        if self.change_pending_snapshot != self._change_assistant_source_signature():
            if not self._ask_yes_no(
                "Novel Changed Since Proposal",
                "Some working story data changed after this proposal was prepared. "
                "Review the proposal and choose Yes only if it still fits the current novel.",
            ):
                return
        conflicts = self.change_pending_patch.get("potential_conflicts", [])
        if conflicts:
            details = "The local model flagged these possible canon conflicts:\n\n"
            details += "\n".join(f"! {item}" for item in conflicts)
            details += "\n\nApprove the proposal anyway?"
            if not self._ask_yes_no("Potential Canon Conflicts", details):
                return
        try:
            summary = apply_change_request_patch(
                self.package, self.change_pending_patch, request_text=self.change_pending_request
            )
        except Exception as exc:
            self._show_copyable_error("Change Assistant", "No changes were applied.\n\n" + str(exc))
            return
        self.dirty = True
        self.change_pending_patch = None
        self.change_pending_snapshot = None
        self.change_pending_request = ""
        self._refresh_all()
        self.change_approve_button.configure(state="disabled")
        self.change_reject_button.configure(state="disabled")
        self.change_assistant_status.configure(text="Approved. Saving changes and backing up replaced JSON files.")
        self._chat("Builder", f"Approved plain-English changes: {summary}")
        self._save()

    def _reject_change_request(self):
        self.change_pending_patch = None
        self.change_pending_snapshot = None
        self.change_pending_request = ""
        self.change_approve_button.configure(state="disabled")
        self.change_reject_button.configure(state="disabled")
        self.change_assistant_status.configure(text="Proposal rejected. Your story data was not changed.")
        self.change_proposal_text.configure(state="normal")
        self.change_proposal_text.delete("1.0", "end")
        self.change_proposal_text.insert("1.0", "No changes were applied.")
        self.change_proposal_text.configure(state="disabled")

    def _add_supporting_person(self):
        if self.package is None:
            return
        name = simpledialog.askstring("Add Supporting Person", "Name:", parent=self)
        if name is None:
            return
        name = name.strip()
        if not name:
            return
        if self.package.character_by_name(name) is not None:
            messagebox.showwarning("Add Supporting Person", f"{name} already has a full character card. Select that character instead.")
            return
        people = self.package.story_bible.setdefault("supporting_people", {})
        if not isinstance(people, dict):
            people = {}
            self.package.story_bible["supporting_people"] = people
        if any(str(existing).casefold() == name.casefold() for existing in people):
            messagebox.showwarning("Add Supporting Person", f"{name} is already listed.")
            return
        people[name] = ""
        self.dirty = True
        self._refresh_supporting_people(select_name=name)
        self._update_path_label()
        self._chat("Builder", f"Added supporting person {name}. Add details, then save.")

    def _promote_supporting_person(self):
        if self.package is None or not hasattr(self, "supporting_people_list"):
            return

        if (
            getattr(self, "writer_generation_in_progress", False)
            or getattr(self, "scene_contract_building", False)
            or getattr(self, "writer_notes_update_in_progress", False)
        ):
            messagebox.showwarning(
                "Promote to Core Character",
                "Wait for the current writing or analysis operation to finish before changing character data.",
            )
            return

        selection = self.supporting_people_list.curselection()
        if not selection:
            messagebox.showinfo(
                "Promote to Core Character",
                "Select Beth, Jessica, or Rick under Supporting People first.",
            )
            return

        people = self.package.story_bible.get("supporting_people", {})
        if not isinstance(people, dict):
            messagebox.showwarning(
                "Promote to Core Character",
                "The supporting-people list is not available.",
            )
            return

        names = sorted(
            (str(name) for name in people if str(name).strip()),
            key=str.casefold,
        )
        index = selection[0]
        if index < 0 or index >= len(names):
            return
        name = names[index]

        if not self._ask_yes_no(
            "Promote to Core Character",
            f"Promote {name} to a core character?\n\n"
            "StoryBuilder will reuse the existing character JSON when available, "
            "preserve its details, add it to the core character cards, and remove "
            "the duplicate supporting-person entry.",
        ):
            return

        # Preserve edits in the supporting-person details box without allowing
        # a blank box to erase the existing description by accident.
        edited_details = self.supporting_person_text.get("1.0", "end-1c").strip()
        existing_details = str(people.get(name, "") or "").strip()
        if edited_details != existing_details:
            people[name] = edited_details

        filename = None
        try:
            filename = self.package.promote_supporting_person(name)
            self.dirty = True
            if self.package.path is not None:
                self.package.save()
                self.dirty = False
            self._refresh_all()
            self._refresh_characters(select_filename=filename)
            self._chat(
                "Builder",
                f"Promoted {name} to a core character. Existing character details were preserved.",
            )
        except Exception as exc:
            # Keep the in-memory change visible if saving failed, and report that
            # the author still needs to save the novel package.
            self.dirty = True
            self._refresh_all()
            if filename:
                self._refresh_characters(select_filename=filename)
            self._show_copyable_error(
                "Promote to Core Character",
                "The promotion could not be fully saved. Review the error and save the novel package before continuing.\n\n"
                + str(exc),
            )

    def _remove_supporting_person(self):
        if self.package is None:
            return
        selection = self.supporting_people_list.curselection()
        if not selection:
            messagebox.showinfo("Remove Supporting Person", "Select a supporting person first.")
            return
        people = self.package.story_bible.get("supporting_people", {})
        if not isinstance(people, dict):
            return
        names = sorted((str(name) for name in people if str(name).strip()), key=str.casefold)
        index = selection[0]
        if index < 0 or index >= len(names):
            return
        name = names[index]
        if not self._ask_yes_no("Remove Supporting Person", f"Remove {name} from the supporting-people list?"):
            return
        people.pop(name, None)
        self.dirty = True
        self._refresh_supporting_people()
        self._update_path_label()
        self._chat("Builder", f"Removed supporting person {name} from the working story data.")

    def _apply_all_edits(self):
        # Current Situation is an editable part of the active story state too.
        # Apply it through its guarded handler before saving any other fields,
        # so ordinary Save / Save As / Sync cannot silently persist a stale value.
        if not self._apply_situation_edit():
            return False
        self._apply_story_edits()
        self._apply_planning_edits()
        self._apply_scene_contract_edits()
        self._apply_character_edits()
        self._apply_supporting_person_edit()
        self._apply_relationship_edits()
        self._apply_location_edits()
        if not self._apply_state_edits():
            return False
        return True

    def _add_character(self):
        if self.package is None:
            return
        name = simpledialog.askstring("Add Character", "Character name:", parent=self)
        if not name:
            return
        try:
            filename = self.package.add_character(name)
        except ValueError as exc:
            self._show_copyable_error("Add Character", str(exc))
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
        if not self._ask_yes_no("Remove Character", f"Remove {name}?"):
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

        canon_rules = bible.get("canon_rules", [])
        if isinstance(canon_rules, str):
            canon_rules = [line.strip() for line in canon_rules.splitlines() if line.strip()]
        if not isinstance(canon_rules, list):
            canon_rules = []
        self.canon_rules_text.delete("1.0", "end")
        self.canon_rules_text.insert("1.0", "\n".join(str(rule) for rule in canon_rules if str(rule).strip()))

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
        if hasattr(self, "writer_scene_idea_text"):
            self._refresh_writer_scene_guidance()
        if "scene_planner_target_var" in self.__dict__:
            self._refresh_scene_planner_target()
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

    def _advance_to_next_scene(self):
        """Advance only after safeguarding the current Writer work."""
        if self.package is None:
            return

        try:
            chapter = int(self.package.current_state.get("chapter", 1) or 1)
            scene = int(self.package.current_state.get("scene", 1) or 1)
            if self.package.current_state.get("chapter_completed"):
                messagebox.showinfo(
                    "Advance Scene",
                    f"Chapter {chapter} is finalized. Use Start Next Chapter to continue.",
                )
                return

            next_scene = scene + 1
            if not self._prepare_for_scene_change(chapter, next_scene):
                return
            next_cast = self._scene_plan_cast(chapter, next_scene)

            self.package.current_state["scene"] = next_scene
            self.package.current_state["scene_completed"] = False
            self.package.current_state["chapter_completed"] = False
            if next_cast:
                self.package.current_state["scene_cast"] = next_cast

            self.dirty = True
            self._clear_writer_scene_workspace(
                f"Scene {next_scene} is ready. The previous scene's unfinished text, if any, was preserved as a draft."
            )
            self._refresh_all()
            self._save()
            self._chat(
                "Builder",
                f"Advanced from Scene {scene} to Scene {next_scene}. "
                "The completed scene's ending state remains the starting continuity for the new scene.",
            )
            self.writer_status.configure(
                text=f"Scene {next_scene} is ready. Build Scene Direction to begin.",
            )
            self._update_writer_buttons()
        except Exception as exc:
            self._show_copyable_error("Advance Scene", str(exc))
    def _start_next_chapter(self):
        """Start Scene 1 of the next chapter without dropping unfinished prose."""
        if self.package is None:
            return

        try:
            current_chapter = int(self.package.current_state.get("chapter", 1) or 1)
            if not self.package.current_state.get("chapter_completed"):
                messagebox.showinfo(
                    "Start Next Chapter",
                    f"Chapter {current_chapter} is not marked complete yet. Finalize the chapter before starting the next one.",
                )
                return

            next_chapter = current_chapter + 1
            next_scene = 1
            next_guidance = self._chapter_scene_guidance(
                self.package.extra_json.get("writing_guidance.json", {}),
                next_chapter,
                next_scene,
            )
            if next_guidance is None:
                proceed = self._ask_yes_no(
                    "Start Next Chapter",
                    f"Chapter {next_chapter} Scene 1 has no scene guidance yet.\n\n"
                    "Starting it will preserve the completed chapter's ending state, but the "
                    "new scene will not have authored scene direction or cast until guidance is added.\n\n"
                    f"Start Chapter {next_chapter} anyway?",
                )
                if not proceed:
                    return

            if not self._prepare_for_scene_change(next_chapter, next_scene):
                return

            self.package.current_state["chapter"] = next_chapter
            self.package.current_state["scene"] = next_scene
            self.package.current_state["scene_completed"] = False
            self.package.current_state["chapter_completed"] = False
            next_cast = self._scene_plan_cast(next_chapter, next_scene)
            if next_cast:
                self.package.current_state["scene_cast"] = next_cast

            self.dirty = True
            self._clear_writer_scene_workspace(
                f"Chapter {next_chapter}, Scene {next_scene} is ready. Unfinished previous text was preserved as a draft."
            )
            self._refresh_all()
            try:
                self.package.save()
                self.dirty = False
                self._update_path_label()
            except Exception as exc:
                raise RuntimeError(
                    f"Could not save the new chapter state: {exc}"
                ) from exc

            self._chat(
                "Builder",
                f"Started Chapter {next_chapter}, Scene {next_scene}. "
                "The previous chapter's ending state is now the starting continuity.",
            )
            self.writer_status.configure(
                text=(
                    f"Chapter {next_chapter}, Scene {next_scene} is ready. "
                    "Build Scene Direction to begin."
                ),
            )
            self._update_writer_buttons()
        except Exception as exc:
            self._show_copyable_error("Start Next Chapter", str(exc))
    def _apply_situation_edit(self):
        if self.package is None:
            return False

        new_situation = self.situation_text.get("1.0", "end-1c").strip()
        old_situation = str(self.package.current_state.get("current_situation", "") or "").strip()
        if new_situation != old_situation:
            if getattr(self, "writer_generation_in_progress", False) or getattr(self, "scene_contract_building", False):
                messagebox.showwarning(
                    "Current Situation",
                    "Wait for the active scene generation to finish before changing the scene's starting state.",
                )
                return False

            accepted = str(getattr(self, "accepted_scene", "") or "").strip()
            if accepted and not self.package.current_state.get("scene_completed", False):
                prose = self._writer_editor_prose()
                if prose and prose != accepted and not self._save_unsaved_writer_draft():
                    return False
                messagebox.showwarning(
                    "Current Situation",
                    "This scene has been accepted but its state update has not been applied. Finish that step before changing its starting situation.",
                )
                return False

            if not self._save_unsaved_writer_draft():
                return False
            if self.generated_scene.strip() or self.accepted_scene.strip():
                self._clear_writer_scene_workspace(
                    "Starting situation changed. Any unfinished prose was preserved as a draft."
                )

        self.package.current_state["current_situation"] = new_situation
        self.dirty = True
        self._update_path_label()
        self._build_scene_direction()
        return True
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

        if not self._apply_all_edits():
            return
        # Guided setup writes directly to the package. Do not let stale editor
        # selection state cause a later chat answer to overwrite a character.
        self.character_filename = None
        message = self.guided_setup.start(self.package)
        self.guided_button.configure(text="Stop Guided Setup")
        self._chat("Builder", message)

    def _run_command(self):
        if self.package is None:
            return
        if not self._apply_all_edits():
            return
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
            self.canon_rules_text,
            self.change_request_text,
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
            self.new_novel_brief_text,
            self.scene_planner_input_text,
            self.scene_planner_proposal_text,
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
        else:
            # Tk callbacks must be scheduled from the Tk main thread.
            self._spellcheck_poll_job = self.after(100, self._poll_spellcheck_results)

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

            # Do not call Tkinter from this worker thread. The main-thread
            # poller below safely delivers the result to the editor.
            self._spellcheck_results.put((widget, source_text, words))

        threading.Thread(target=check_in_background, args=(text,), daemon=True).start()

    def _poll_spellcheck_results(self):
        """Apply queued spell-check results on the Tk main thread."""
        self._spellcheck_poll_job = None
        if self._closing:
            return

        while True:
            try:
                widget, source_text, words = self._spellcheck_results.get_nowait()
            except queue.Empty:
                break
            self._apply_spellcheck_result(widget, source_text, words)

        try:
            self._spellcheck_poll_job = self.after(100, self._poll_spellcheck_results)
        except tk.TclError:
            # The root may be closing between the poll and rescheduling.
            self._spellcheck_poll_job = None

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
        except (tk.TclError, KeyError):
            # ttk.Combobox creates a temporary Tk "popdown" window for its
            # dropdown list. While that window is open, winfo_containing() can
            # return a path that is no longer present in the widget tree.
            # Ignore that wheel event instead of printing a callback traceback.
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
    def _selected_widget_text(widget, start_index, end_index):
        """Return a selected substring from Text or Entry-style widgets."""
        if isinstance(widget, tk.Text):
            return widget.get(start_index, end_index)
        # Entry, ttk.Entry, Combobox, and Spinbox expose get() without index
        # arguments; their selection offsets are indexes into the full value.
        return widget.get()[int(start_index):int(end_index)]

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
                value = StoryBuilderApp._selected_widget_text(
                    widget, start_index, end_index
                )
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
                value = StoryBuilderApp._selected_widget_text(
                    widget, start_index, end_index
                )
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

    def _show_copyable_error(
        self,
        title: str,
        message: str,
        summary: str = "The operation failed. No state changes were applied.",
    ) -> None:
        """Show a scrollable error whose full text can be selected or copied."""
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        dialog.resizable(True, True)

        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        width = min(760, max(340, screen_width - 48))
        height = min(560, max(280, screen_height - 80))
        dialog.geometry(
            f"{width}x{height}+{max(0, (screen_width-width)//2)}+"
            f"{max(0, (screen_height-height)//2)}"
        )

        outer = ttk.Frame(dialog, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(
            outer,
            text=summary,
            wraplength=700,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        def copy_text(value: str) -> None:
            try:
                # Give clipboard ownership to the main application window,
                # not this temporary dialog. Destroying the dialog must not
                # destroy the copied text before it can be pasted elsewhere.
                self.clipboard_clear()
                self.clipboard_append(value)
                self.update_idletasks()
                status.configure(text="Error text copied. Paste it wherever you need it.")
            except tk.TclError as exc:
                status.configure(text=f"Clipboard copy failed: {exc}")

        # Keep both actions above the expandable text area so they stay visible
        # even on shorter screens or when the diagnostic contains a long traceback.
        action_row = ttk.Frame(outer)
        action_row.pack(fill="x", pady=(0, 8))
        ttk.Button(
            action_row,
            text="Copy Full Error",
            command=lambda: copy_text(str(message)),
        ).pack(side="left")
        ttk.Button(
            action_row,
            text="Close",
            command=dialog.destroy,
        ).pack(side="right")

        text_frame = ttk.Frame(outer)
        text_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical")
        error_text = tk.Text(
            text_frame,
            wrap="word",
            yscrollcommand=scrollbar.set,
            padx=8,
            pady=8,
            height=14,
            width=76,
        )
        scrollbar.configure(command=error_text.yview)
        error_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        error_text.insert("1.0", str(message))
        # Keep the text selectable/focusable, but block edits below so keyboard
        # selection and copy work reliably in both local desktop and RustDesk.
        error_text.configure(state="normal", takefocus=True)

        status = ttk.Label(outer, text="Select text to copy, or copy the full error.")
        status.pack(anchor="w", pady=(6, 0))

        def copy_selection(_event=None):
            try:
                selected = error_text.get("sel.first", "sel.last")
            except tk.TclError:
                selected = str(message)
            copy_text(selected)
            return "break"

        def select_all(_event=None):
            error_text.tag_add("sel", "1.0", "end-1c")
            error_text.mark_set("insert", "1.0")
            error_text.see("insert")
            return "break"

        # This is a read-only error viewer: allow selection and copy shortcuts,
        # but prevent accidental edits to the diagnostic text.
        error_text.bind("<Control-c>", copy_selection)
        error_text.bind("<Control-C>", copy_selection)
        error_text.bind("<Control-Insert>", copy_selection)
        error_text.bind("<<Copy>>", copy_selection)
        error_text.bind("<Control-a>", select_all)
        error_text.bind("<Control-A>", select_all)
        error_text.bind("<Key>", lambda _event: "break")

        context_menu = tk.Menu(dialog, tearoff=False)
        context_menu.add_command(label="Copy", command=copy_selection)
        context_menu.add_command(label="Select All", command=select_all)

        def show_context_menu(event):
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()

        error_text.bind("<Button-3>", show_context_menu)

        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.focus_force()

    def _ask_yes_no(self, title: str, message: str) -> bool:
        """Show a readable, scrollable, copyable Yes/No confirmation dialog."""
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        dialog.resizable(True, True)

        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        width = min(760, max(320, screen_width - 48))
        height = min(560, max(260, screen_height - 80))
        dialog.minsize(min(460, width), min(320, height))
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        outer = ttk.Frame(dialog, padding=12)
        outer.pack(fill="both", expand=True)

        message_frame = ttk.Frame(outer)
        message_frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(message_frame, orient="vertical")
        message_text = tk.Text(
            message_frame,
            wrap="word",
            yscrollcommand=scrollbar.set,
            padx=8,
            pady=8,
            takefocus=True,
            height=14,
            width=70,
        )
        scrollbar.configure(command=message_text.yview)
        message_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        message_text.insert("1.0", str(message))
        message_text.configure(state="disabled")

        def copy_selection(_event=None):
            try:
                selected = message_text.get("sel.first", "sel.last")
            except tk.TclError:
                return "break"
            try:
                dialog.clipboard_clear()
                dialog.clipboard_append(selected)
                dialog.update_idletasks()
            except tk.TclError:
                pass
            return "break"

        def select_all(_event=None):
            message_text.tag_add("sel", "1.0", "end-1c")
            message_text.mark_set("insert", "1.0")
            message_text.see("insert")
            return "break"

        message_text.bind("<Control-c>", copy_selection)
        message_text.bind("<Control-C>", copy_selection)
        message_text.bind("<Control-Insert>", copy_selection)
        message_text.bind("<<Copy>>", copy_selection)
        message_text.bind("<Control-a>", select_all)
        message_text.bind("<Control-A>", select_all)

        context_menu = tk.Menu(dialog, tearoff=False)
        context_menu.add_command(label="Copy", command=copy_selection)
        context_menu.add_command(label="Select All", command=select_all)

        def show_context_menu(event):
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()

        message_text.bind("<Button-3>", show_context_menu)

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(10, 0))
        ttk.Label(
            footer,
            text="Tip: Ctrl+A selects all text; Ctrl+C copies the selection.",
        ).pack(side="left", padx=(0, 8))

        answer = {"value": False}

        def finish(value: bool):
            answer["value"] = value
            try:
                dialog.grab_release()
            except tk.TclError:
                pass
            if dialog.winfo_exists():
                dialog.destroy()

        buttons = ttk.Frame(footer)
        buttons.pack(side="right")
        ttk.Button(
            buttons,
            text="No",
            command=lambda: finish(False),
        ).pack(side="right", padx=(6, 0))
        ttk.Button(
            buttons,
            text="Yes",
            command=lambda: finish(True),
        ).pack(side="right")

        dialog.protocol("WM_DELETE_WINDOW", lambda: finish(False))
        dialog.bind("<Escape>", lambda _event: finish(False))
        dialog.update_idletasks()
        try:
            dialog.grab_set()
            message_text.focus_set()
            dialog.wait_window()
        except tk.TclError:
            # If the dialog is closed by the window manager, default to No.
            pass
        return bool(answer["value"])

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
