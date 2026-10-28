from __future__ import annotations

import json
import os
import queue
import re
import shutil
import signal
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
    WRITER_NOTES_CONTEXT_TOKENS,
    WRITER_NOTES_FILENAME,
    WRITER_NOTES_MAX_TOKENS,
    WRITER_NOTES_SYSTEM_PROMPT,
    WRITER_NOTES_TIMEOUT_SECONDS,
    build_writer_notes_review_prompt,
    collect_recent_accepted_scenes,
    collect_initial_seed_scenes,
    merge_writer_notes,
    normalize_writer_notes,
    parse_writer_notes_response,
    save_writer_notes,
    writer_notes_auto_update_enabled,
)
from builder.scene_plan import load_scene_idea_from_plan
from builder.scene_planner import (
    generate_scene_planner_reply, prepare_scene_plan_proposal, read_story_plan_file,
    save_scene_plan_file, update_scene_plan_markdown, validate_scene_plan_fields,
)
from builder.validator import validate_package
from builder.writer_engine import WriterEngine
from builder.prompt_trace import (
    PromptTrace, default_prompt_trace_path, load_prompt_trace_enabled, save_prompt_trace_enabled,
)
from builder.prompt_trace_sync import upload_prompt_trace
from builder.manuscript import ManuscriptManager
from builder.continuity_context import (
    build_historical_relevance_query,
    build_scene_relevance_query,
    context_size_report,
    estimate_tokens_from_chars,
    select_active_character_knowledge,
    select_relevant_records,
)
from builder.writer_context_budget import (
    WriterContextBudgetError,
    conservative_token_estimate,
    fit_writer_context_files,
)
from builder.scene_flow import review_chapter_flow
from builder.novel_sync import NovelSyncError, novel_repo_root, sync_novel_repository
from builder.app_sync import StoryBuilderSyncError, sync_storybuilder_repository
from builder.state_manager import (
    ENDING_STATE_SYSTEM_PROMPT,
    MAIN_PLOT_SYSTEM_PROMPT,
    StateManager,
    build_state_change_summary,
    combine_state_patches,
    remove_prior_chapter_opening_markers,
    reviewed_state_preview_to_patch,
)
from builder.scene_contract import SceneContract, extract_authored_scene_sections, extract_scene_header_metadata
from builder.scene_idea_suggestion import generate_scene_idea_suggestion
from builder.state_review import (
    get_state_patch_value,
    set_state_patch_value,
    apply_state_text_replacement,
    review_state_proposal,
)
from builder.focused_revision import (
    apply_focused_replacement,
    propose_focused_replacement,
    revise_selected_passage,
)
from builder.scene_completion import (
    completion_notice_is_success,
    generate_scene_with_completion_check,
    review_findings_match,
    review_scene_draft,
)
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
        self.prompt_trace_enabled = load_prompt_trace_enabled()
        self.active_prompt_trace = None
        self.writer_thread = None
        self.writer_notes_update_in_progress = False
        self.generated_scene = ""
        # Non-empty when the current draft cannot safely be accepted due to a
        # generation or automated completion-review failure.
        self.writer_scene_accept_block_reason = ""
        self.accepted_scene = ""
        self.accepted_scene_context = None
        self.focused_revision_history = []
        self.validator_review_in_progress = False
        self.validator_review_state = None
        self.validator_review_dialog = None
        self.validator_review_dialog_state = None
        self.generated_scene_review_context = None
        # Keep each generated scene tied to the chapter/scene and exact start
        # state that produced it. Never file prose under a later UI selection.
        self.generated_scene_context: tuple[int, int] | None = None
        self.generated_scene_start_state: dict | None = None
        self.writer_generation_context: tuple[int, int] | None = None
        self.writer_generation_start_state: dict | None = None
        self.writer_generation_in_progress = False
        self.scene_contract_editor_key: tuple[int, int] | None = None
        self.scene_contract_building = False
        self.scene_idea_suggestion_in_progress = False
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
        self._terminal_interrupt_pending = False
        self._previous_sigint_handler = None
        try:
            # Ctrl+C must enter the same safe save/sync flow as closing the window.
            # The signal handler only records a flag; Tk work happens in its poll callback.
            self._previous_sigint_handler = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, self._on_terminal_interrupt_signal)
            self.after(250, self._poll_terminal_interrupt)
        except (ValueError, tk.TclError):
            # signal.signal is only available on the main thread. Normal window-close
            # protection remains enabled if initialization ever occurs elsewhere.
            self._previous_sigint_handler = None
        self.protocol("WM_DELETE_WINDOW", self._close_and_sync_app)
        self._load_startup_novel()

    def _on_terminal_interrupt_signal(self, _signum, _frame):
        """Request a safe shutdown without calling Tk from a signal handler."""
        self._terminal_interrupt_pending = True

    def _terminal_shutdown_is_busy(self):
        """Whether a running task must settle before the terminal-exit request is handled."""
        return any((
            getattr(self, "writer_generation_in_progress", False),
            self.__dict__.get("focused_revision_in_progress", False),
            self.__dict__.get("validator_review_in_progress", False),
            self.__dict__.get("writer_notes_update_in_progress", False),
            self.__dict__.get("scene_planner_request_in_progress", False),
            getattr(self, "scene_contract_building", False),
            self.__dict__.get("state_analysis_in_progress", False),
            self.__dict__.get("scene_idea_suggestion_in_progress", False),
        ))

    def _poll_terminal_interrupt(self):
        """Route terminal Ctrl+C through the UI's save-and-sync shutdown flow."""
        try:
            if self._terminal_interrupt_pending and not self._terminal_shutdown_is_busy():
                self._terminal_interrupt_pending = False
                self.writer_status.configure(
                    text="Ctrl+C received. Saving and synchronizing the novel before closing..."
                )
                self._close_and_sync_app()
            elif self._terminal_interrupt_pending:
                self.writer_status.configure(
                    text="Ctrl+C received. Waiting for the active task to stop before safely saving and synchronizing..."
                )
            if self.winfo_exists():
                self.after(250, self._poll_terminal_interrupt)
        except tk.TclError:
            return

    def _build_ui(self):
        toolbar = ttk.Frame(self, padding=8)
        toolbar.pack(fill="x")
        for label, command in [
            ("New Novel", self._new_novel),
            ("Open Novel", self._open_novel),
            ("Save Novel", self._save),
            ("Save As", self._save_as),
            ("Validate", self._validate),
        ]:
            ttk.Button(toolbar, text=label, command=command).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Sync Novel", command=self._sync_current_novel).pack(side="left", padx=(10, 3))
        ttk.Button(toolbar, text="Close & Sync App", command=self._close_and_sync_app).pack(side="left", padx=3)
        self.path_label = ttk.Label(toolbar, text="Unsaved novel")
        self.path_label.pack(side="right", padx=8)

        self.notebook = CompactTabContainer(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Keep Scene Contract and Writer on separate tabs. This lets authors
        # scroll through the planning controls or the writing/review controls
        # independently, without splitting the short laptop display vertically.
        self._build_scene_contract_tab()
        self._build_writer_tab()
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
        self._build_scene_planner_tab()
        self._build_state_tab()
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
            text='Examples:  Change a character\'s age to 22   •   Set the current chapter to 2   •   Change the story title to My New Story',
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
            text=("Example: Give one character technical expertise and another a relevant service background; "
                  "a third character can contribute useful local connections."),
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

    def _build_scene_contract_tab(self, parent=None, register=True):
        host = parent if parent is not None else self.notebook.pages
        tab = ttk.Frame(host)
        if register:
            self.notebook.add(tab, text="Scene Contract")
        else:
            tab.pack(fill="both", expand=True)

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
            text="Plan and write this scene",
            font=("", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            content,
            text="Review or edit the idea below. StoryBuilder uses it to prepare the scene and preserve continuity.",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(4, 6))

        header = ttk.Frame(content)
        header.pack(fill="x", pady=(0, 6))
        self.scene_contract_scene_label = ttk.Label(
            header,
            text="Chapter 1, Scene 1",
            font=("", 11, "bold"),
        )
        self.scene_contract_scene_label.pack(side="left")

        idea_frame = ttk.Frame(content)
        idea_frame.pack(fill="x", pady=(0, 6))
        ttk.Label(
            idea_frame,
            text="Scene Idea / Author Notes",
            font=("", 11, "bold"),
        ).pack(anchor="w")
        self.scene_idea_text = tk.Text(idea_frame, height=5, wrap="word", undo=True)
        self.scene_idea_text.pack(fill="x", pady=(4, 6))
        # Keep the primary scene-preparation action visible on narrow screens.
        # Two short rows prevent Tk from clipping the final buttons at high display scaling.
        idea_button_row = ttk.Frame(idea_frame)
        idea_button_row.pack(fill="x")
        idea_secondary_button_row = ttk.Frame(idea_frame)
        idea_secondary_button_row.pack(fill="x", pady=(4, 0))

        details_frame = ttk.LabelFrame(content, text="Scene Plan and Continuity Details")
        details_frame.pack(fill="x", pady=(0, 10))
        self.scene_contract_details_frame = details_frame

        continuity_frame = ttk.LabelFrame(details_frame, text="Relevant Continuity (optional)")
        continuity_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(
            continuity_frame,
            text=(
                "List earlier facts, clues, promises, injuries, or conversations this scene specifically needs. "
                "Leave blank for automatic selection. This is a retrieval hint, not a new story beat."
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=8, pady=(6, 3))
        self.scene_continuity_focus_text = tk.Text(
            continuity_frame, height=3, wrap="word", undo=True
        )
        self.scene_continuity_focus_text.pack(fill="x", padx=8, pady=(0, 8))

        self.scene_contract_build_button = ttk.Button(
            idea_button_row,
            text="Prepare Scene...",
            command=self._build_contract_from_scene_idea,
        )
        self.scene_contract_build_button.pack(side="left", padx=(0, 8))

        self.scene_contract_details_toggle_button = ttk.Button(
            idea_button_row,
            text="Hide Scene Details ▾",
            command=self._toggle_scene_details,
        )
        self.scene_contract_details_toggle_button.pack(side="left")

        self.scene_contract_suggest_button = ttk.Button(
            idea_secondary_button_row,
            text="Suggest Idea",
            command=self._suggest_scene_idea,
        )
        self.scene_contract_suggest_button.pack(side="left", padx=(0, 8))

        self.scene_contract_save_idea_button = ttk.Button(
            idea_secondary_button_row,
            text="Save Idea",
            command=self._apply_scene_contract_edits,
        )
        self.scene_contract_save_idea_button.pack(side="left", padx=(0, 8))

        detail_button_row = ttk.Frame(details_frame)
        detail_button_row.pack(fill="x", padx=8, pady=(8, 4))
        self.scene_contract_reload_idea_button = ttk.Button(
            detail_button_row,
            text="Clear & Reload Idea",
            command=self._reload_saved_scene_idea,
        )
        self.scene_contract_reload_idea_button.pack(side="left", padx=(8, 0))
        self.scene_contract_plan_reload_button = ttk.Button(
            detail_button_row,
            text="Load from STORY_PLAN.md",
            command=self._load_scene_idea_from_plan,
        )
        self.scene_contract_plan_reload_button.pack(side="left", padx=(8, 0))
        ttk.Label(
            details_frame,
            text=(
                "Prepare Scene drafts the Beginning / Middle Direction and End / Hard Stop from your idea. "
                "Planned / Required Beats and Author Boundaries are copied only when you explicitly label "
                "those sections in the Scene Idea. Leave them blank when you have no extra must-hit events "
                "or restrictions; the original idea and Current State still guide the scene."
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=8, pady=(3, 8))


        start_frame = ttk.LabelFrame(details_frame, text="Beginning / Current State")
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

        form = ttk.Frame(details_frame, padding=(8, 0, 8, 0))
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

        attempts_row = ttk.Frame(details_frame)
        attempts_row.pack(fill="x", padx=8, pady=(8, 0))
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
        action_row.pack(fill="x", pady=(2, 0))
        self.scene_contract_action_row = action_row
        self.scene_contract_status = ttk.Label(
            action_row,
            text="Edit the Scene Idea, then prepare the scene.",
            anchor="w",
        )
        self.scene_contract_status.pack(side="left", fill="x", expand=True)
        # Keep the generated plan fields visible by default. Hiding them here
        # made the prepared beginning, middle, ending, beats, and boundaries
        # invisible unless the author discovered and clicked Scene Details.

    def _toggle_scene_details(self):
        """Show or hide the optional contract details in the Write workspace."""
        frame = self.__dict__.get("scene_contract_details_frame")
        if frame is None:
            return
        toggle = self.__dict__.get("scene_contract_details_toggle_button")
        if frame.winfo_manager():
            frame.pack_forget()
            if toggle is not None:
                toggle.configure(text="Scene Details ▸")
            return

        action_row = self.__dict__.get("scene_contract_action_row")
        options = {"fill": "x", "pady": (0, 10)}
        if action_row is not None:
            frame.pack(before=action_row, **options)
        else:
            frame.pack(**options)
        if toggle is not None:
            toggle.configure(text="Scene Details ▾")

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

    def _build_writer_tab(self, parent=None, register=True):
        host = parent if parent is not None else self.notebook.pages
        tab = ttk.Frame(host)
        if register:
            self.notebook.add(tab, text="Writer")
        else:
            tab.pack(fill="both", expand=True)

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
            text="Scene Direction (read-only guidance)",
            font=("", 11, "bold"),
        ).pack(side="left")
        self.writer_direction_text = tk.Text(
            content_frame,
            height=7,
            wrap="word",
            state="disabled",
            exportselection=False,
        )
        self.writer_direction_text.pack(fill="x", pady=(4, 8))
        self.writer_direction_text.configure(state="normal")
        self.writer_direction_text.insert(
            "1.0",
            "Write the next scene naturally from the current story state. Follow the active scene guidance and preserve established continuity.",
        )
        self.writer_direction_text.configure(state="disabled")

        button_row = ttk.Frame(content_frame)
        button_row.pack(fill="x", pady=(0, 8))
        self.writer_write_button = ttk.Button(
            button_row,
            text="Write Next Scene",
            command=self._write_next_scene,
        )
        self.writer_write_button.pack(side="left")
        self.writer_preview_context_button = ttk.Button(
            button_row,
            text="Preview Context",
            command=self._preview_writer_context,
        )
        self.writer_preview_context_button.pack(side="left", padx=(8, 0))

        trace_row = ttk.Frame(content_frame)
        trace_row.pack(fill="x", pady=(0, 8))
        self.writer_trace_button = ttk.Button(
            trace_row,
            text="Prompt Trace (On)" if self.prompt_trace_enabled else "Prompt Trace (Off)",
            command=self._toggle_prompt_trace,
        )
        self.writer_trace_button.pack(side="left")
        self.writer_trace_status = ttk.Label(
            trace_row,
            text=(
                "On. Writer generations and State Analysis are captured. The latest trace "
                "overwrites the previous local file and private GitHub trace. Traces contain "
                "story text and prompts."
            ) if self.prompt_trace_enabled else "Off. No prompts are being recorded.",
            wraplength=720,
            justify="left",
        )
        self.writer_trace_status.pack(side="left", padx=(8, 0))

        ttk.Label(
            content_frame,
            text="Generated Scene",
            font=("", 11, "bold"),
        ).pack(anchor="w")
        self.writer_output_text = tk.Text(
            content_frame, height=22, wrap="word", undo=True, exportselection=False
        )
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
                "Focused change: select the exact passage in Generated Scene, then describe one change. "
                "Only that selected passage will be replaced. (Ctrl+Enter to apply.)"
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
            text="Proposed State Changes",
            font=("", 11, "bold"),
        ).pack(side="left")

        ttk.Label(
            content_frame,
            text=(
                "Review the changes in plain English below. The optional correction fields are on this same screen. "
                "The validator may raise concerns one at a time; dismiss false alarms, skip concerns, or apply a focused correction. "
                "Nothing is saved until you click Apply State Update. You do not need to read or edit JSON."
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        # One unified review surface replaces the old Changes / Quick Edits / JSON tabs.
        self.writer_state_review_notebook = None
        self.writer_state_json_tab = None
        self.writer_state_diff_tab = ttk.Frame(content_frame)
        self.writer_state_diff_tab.pack(fill="both", expand=True, pady=(4, 0))
        self.writer_state_quick_tab = self.writer_state_diff_tab

        diff_frame = ttk.Frame(self.writer_state_diff_tab)
        diff_frame.pack(fill="x", expand=False, pady=(0, 8))
        diff_scrollbar = ttk.Scrollbar(diff_frame, orient="vertical")
        self.writer_state_diff_preview = tk.Text(
            diff_frame,
            height=8,
            wrap="word",
            yscrollcommand=diff_scrollbar.set,
            state="disabled",
        )
        diff_scrollbar.configure(command=self.writer_state_diff_preview.yview)
        self.writer_state_diff_preview.pack(side="left", fill="x", expand=True)
        diff_scrollbar.pack(side="right", fill="y")

        ttk.Label(
            self.writer_state_diff_tab,
            text="Optional plain-English corrections",
            font=("", 10, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        ttk.Label(
            self.writer_state_diff_tab,
            text=(
                "Make ordinary corrections here without editing JSON. Edit the ending situation, "
                "then choose a character to review their location, physical state, knowledge, and objective. "
                "Knowledge uses one fact per line. Nothing is saved until you apply the reviewed update."
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(10, 6))

        ttk.Label(
            self.writer_state_diff_tab,
            text="Ending situation for the next scene",
            font=("", 10, "bold"),
        ).pack(anchor="w", padx=10)
        self.writer_state_situation_quick = tk.Text(
            self.writer_state_diff_tab, height=4, wrap="word", undo=True
        )
        self.writer_state_situation_quick.pack(fill="x", padx=10, pady=(3, 8))

        quick_character_row = ttk.Frame(self.writer_state_diff_tab)
        quick_character_row.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Label(quick_character_row, text="Character").pack(side="left")
        self.writer_state_character_selector = ttk.Combobox(
            quick_character_row, state="readonly", width=32
        )
        self.writer_state_character_selector.pack(side="left", padx=(8, 0))
        self.writer_state_character_selector.bind(
            "<<ComboboxSelected>>", self._on_quick_state_character_selected
        )

        ttk.Label(
            self.writer_state_diff_tab,
            text="Character's current location",
            font=("", 10, "bold"),
        ).pack(anchor="w", padx=10)
        self.writer_state_location_quick = tk.Text(
            self.writer_state_diff_tab, height=2, wrap="word", undo=True
        )
        self.writer_state_location_quick.pack(fill="x", padx=10, pady=(3, 5))

        ttk.Label(
            self.writer_state_diff_tab,
            text="Physical position / current activity",
            font=("", 10, "bold"),
        ).pack(anchor="w", padx=10)
        self.writer_state_position_quick = tk.Text(
            self.writer_state_diff_tab, height=2, wrap="word", undo=True
        )
        self.writer_state_position_quick.pack(fill="x", padx=10, pady=(3, 5))

        ttk.Label(
            self.writer_state_diff_tab,
            text="Posture (optional)",
            font=("", 10, "bold"),
        ).pack(anchor="w", padx=10)
        self.writer_state_posture_quick = tk.Text(
            self.writer_state_diff_tab, height=1, wrap="word", undo=True
        )
        self.writer_state_posture_quick.pack(fill="x", padx=10, pady=(3, 5))

        ttk.Label(
            self.writer_state_diff_tab,
            text="Movement (for example, walking or stationary)",
            font=("", 10, "bold"),
        ).pack(anchor="w", padx=10)
        self.writer_state_movement_quick = tk.Text(
            self.writer_state_diff_tab, height=1, wrap="word", undo=True
        )
        self.writer_state_movement_quick.pack(fill="x", padx=10, pady=(3, 5))

        ttk.Label(
            self.writer_state_diff_tab,
            text="What this character knows (one fact per line)",
            font=("", 10, "bold"),
        ).pack(anchor="w", padx=10)
        self.writer_state_knowledge_quick = tk.Text(
            self.writer_state_diff_tab, height=5, wrap="word", undo=True
        )
        self.writer_state_knowledge_quick.pack(fill="x", padx=10, pady=(3, 8))

        ttk.Label(
            self.writer_state_diff_tab,
            text="This character's current objective (leave blank to remove it)",
            font=("", 10, "bold"),
        ).pack(anchor="w", padx=10)
        self.writer_state_objective_quick = tk.Text(
            self.writer_state_diff_tab, height=3, wrap="word", undo=True
        )
        self.writer_state_objective_quick.pack(fill="x", padx=10, pady=(3, 6))

        ttk.Button(
            self.writer_state_diff_tab,
            text="Update Proposed Changes",
            command=self._apply_quick_state_edits_to_preview,
        ).pack(anchor="e", padx=10, pady=(0, 10))


        # Internal serialization only. It is deliberately not packed or displayed.
        self.writer_state_preview = tk.Text(content_frame, height=1, width=1)
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
        scene_plan_text = "\n".join([
            str(guidance_entry.get("scene_idea", "") or ""),
            str(guidance_entry.get("direction", "") or ""),
            str(guidance_entry.get("end_condition", "") or ""),
        ]).strip()
        continuity_focus = str(guidance_entry.get("continuity_focus", "") or "").strip()
        context_query = build_scene_relevance_query(
            scene_cast_names,
            primary_location,
            str(state.get("current_situation", "") or ""),
            scene_plan_text,
            continuity_focus=continuity_focus,
        )
        # State cast and physical continuity refer to the opening only. Include
        # cards/knowledge for additional characters explicitly named in the
        # author-authored plan, but keep their facts attributed to them.
        scene_context_names = set(scene_cast_names)
        scene_context_order = list(dict.fromkeys(scene_cast_names))
        scene_context_name_keys = {str(name).casefold() for name in scene_context_order}

        def add_scene_context_name(raw_name):
            name = str(raw_name or "").strip()
            key = name.casefold()
            if name and key not in scene_context_name_keys:
                scene_context_names.add(name)
                scene_context_order.append(name)
                scene_context_name_keys.add(key)

        planned_cast = guidance_entry.get("cast", [])
        if isinstance(planned_cast, list):
            for name in planned_cast:
                add_scene_context_name(name)
        character_cards_for_context = getattr(self.package, "characters", {})
        if isinstance(character_cards_for_context, dict):
            for filename, data in sorted(character_cards_for_context.items()):
                name = str(data.get("name", "") or "").strip() if isinstance(data, dict) else ""
                if not name:
                    name = Path(str(filename)).stem
                if name and re.search(
                    r"(?<!\\w)" + re.escape(name) + r"(?!\\w)",
                    scene_plan_text,
                    flags=re.IGNORECASE,
                ):
                    add_scene_context_name(name)
        time_data = state.get("time", state.get("time_of_day", ""))
        scene_state = {
            "chapter": int(state.get("chapter", 1) or 1),
            "scene": int(state.get("scene", 1) or 1),
            "location": primary_location,
            "time": time_data,
            "cast": scene_cast_names,
            "current_situation": str(state.get("current_situation", "") or "").strip(),
        }
        if continuity_focus:
            scene_state["continuity_focus"] = continuity_focus
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
            for name in scene_context_order:
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
        active_character_names = set(scene_cast_names)
        if isinstance(getattr(self.package, "characters", {}), dict):
            for filename, data in self.package.characters.items():
                name = str(data.get("name", "") or "").strip() if isinstance(data, dict) else ""
                active_character_names.add(name or Path(str(filename)).stem)
        supporting_name_data = self.package.story_bible.get("supporting_people", {})
        if isinstance(supporting_name_data, dict):
            active_character_names.update(str(name).strip() for name in supporting_name_data if str(name).strip())
        for field in ("location", "physical_state", "character_knowledge", "active_objectives"):
            values = state.get(field, {})
            if isinstance(values, dict):
                active_character_names.update(
                    str(name).strip() for name in values
                    if str(name).strip() and str(name).strip().casefold() != "primary"
                )
        # Select knowledge against the actual scene idea, not the character list,
        # setting, or full current-state snapshot. This prevents an old tea/bath
        # detail from surfacing merely because a scene shares the same kitchen.
        knowledge_query = "\n".join(
            part for part in (scene_plan_text, continuity_focus) if part
        )
        scene_knowledge, knowledge_metrics = select_active_character_knowledge(
            all_scene_knowledge,
            knowledge_query,
            max_items_per_character=4,
            max_total_items=24,
            character_names=sorted(active_character_names),
        )
        files.append((
            "scene_character_knowledge.json",
            json.dumps(scene_knowledge, indent=2, ensure_ascii=False),
        ))

        scene_characters = {}
        # When a scene has no declared cast and the plan names no characters,
        # there is no reliable basis for filtering the story's character cards.
        # Include the available cards so a new story's opening scene can establish
        # its intended cast instead of inventing replacement characters.
        include_all_character_cards = not scene_context_names
        for filename in sorted(self.package.characters):
            data = self.package.characters[filename]
            name = str(data.get("name", "") or "").strip()
            filename_stem = Path(filename).stem.strip()
            if (
                not include_all_character_cards
                and name.casefold() not in {value.casefold() for value in scene_context_names}
                and filename_stem.casefold() not in {value.casefold() for value in scene_context_names}
            ):
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
                if not name_text or name_text.casefold() in {value.casefold() for value in scene_context_names}:
                    continue
                if not re.search(
                    r"(?<!\w)" + re.escape(name_text) + r"(?!\w)",
                    context_query,
                    flags=re.IGNORECASE,
                ):
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
        context_names = set(scene_context_names)
        if isinstance(location_data, dict):
            for name in location_data:
                name_text = str(name).strip()
                if not name_text or name_text.casefold() == "primary" or name_text.casefold() in {value.casefold() for value in scene_context_names}:
                    continue
                if re.search(
                    r"(?<!\w)" + re.escape(name_text) + r"(?!\w)",
                    context_query,
                    flags=re.IGNORECASE,
                ):
                    context_names.add(name_text)

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
                        r"(?<!\w)" + re.escape(name_text) + r"(?!\w)",
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
            relationship_keys = ["relationships", "friendship_dynamics"]
            relationship_keys.extend(
                key for key in character
                if str(key).startswith("relationship_with_")
                and key not in relationship_keys
            )
            for key in relationship_keys:
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
            f"Saved starting-state summary (check against accepted prose/canon): {situation or 'continue from established current conditions.'}",
            "Author-header precedence: An explicit Location or Time in the original Scene Idea's Scene header is authoritative for the planned scene and overrides a broader current-state label.",
            "Opening-cast rule: The current-state cast and physical positions describe only who is present at the start. They do not exclude later arrivals named in the original Scene Idea.",
            "Starting-state summary rule: This saved situation is a generated recap, not proof by itself that every historical claim is established. Check consequential past-event claims against accepted prose, canon, and the Scene Idea. Do not repeat unsupported claims as fact; the Scene Idea can correct a stale recap. Do not replay events confirmed as already completed.",
            "Starting-knowledge rule: When accepted prose, canon, or a clearly supported state detail confirms that one character has already told, informed, warned, shown, or communicated a fact to another, the receiving character already knows it. Do not infer knowledge from an unsupported summary claim.",
            "State evidence rule: Use saved state for starting location, time, physical condition, and character knowledge, but treat it as a fallible summary. Accepted prose, canon, and explicit author intent determine whether consequential past events are established. Do not promote an unsupported state-only claim into story history. Preserve established physical continuity when it is not contradicted by this scene.",
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
            # Use the same endpoint resolution as the contract editor. The
            # saved contract's hard_stop is authoritative when present; legacy
            # top-level hard_stop/end_condition fields are fallback values.
            try:
                saved_contract = SceneContract.from_guidance(guidance, [])
                current_plan_end = str(
                    saved_contract.get("hard_stop", "") or ""
                ).strip()
            except (TypeError, ValueError):
                # Keep direction generation usable when a saved contract needs
                # repair; the plain legacy endpoint fields are still readable.
                current_plan_end = str(
                    guidance.get("hard_stop", "")
                    or guidance.get("end_condition", "")
                    or ""
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
            "Write natural prose only. Use saved state as a starting-continuity summary, but do not treat unsupported historical claims in it as established fact. Accepted prose, canon, and explicit author intent are evidence for established history. Explicit Location and Time values from the original Scene Idea header control planned scene metadata. The opening cast is not the full scene cast; later arrivals specified by the Scene Idea must remain eligible to enter. The original plain-English Scene Idea guides the scene's purpose, direction, and explicit author commitments. It does not prescribe an order unless it clearly specifies a sequence, and it is not a beat-by-beat outline. Keep its named priorities evident through natural, creative staging; honor any explicit endpoint or hard stop. Generated direction is supporting context only."
        )

        # The Writer direction is display-only. Temporarily enable it for
        # internal refreshes, then return it to read-only so it cannot
        # accidentally diverge from the saved Scene Idea/contract.
        self.writer_direction_text.configure(state="normal")
        try:
            self.writer_direction_text.delete("1.0", "end")
            self.writer_direction_text.insert("1.0", "\n".join(lines))
        finally:
            self.writer_direction_text.configure(state="disabled")
        if update_status:
            self.writer_status.configure(text="Scene direction refreshed from the current state and active plan.")

    def _writer_system_prompt(self, files):
        base = """You are the novelist for an ongoing work of fiction. Write a compelling, natural scene, not a checklist.

THE ANCHORS
The author's canon, explicit boundaries, and clearly stated requirements are the firm ground. The original plain-English Scene Idea expresses the scene's purpose and direction; a generated contract or summary supports it but does not replace or narrow it. Treat the Scene Idea as direction, not a line-by-line script.

The Scene Idea also contains the author's deliberate story commitments. Put its concrete beats on the page: specifically named actions, quoted lines or nicknames, relationship milestones, reveals, choices, callbacks, and emotional turns. Do not silently omit one, replace a specific beat with a generic gesture, or assume matching the mood is enough. Let each beat arise naturally in the scene rather than presenting it as a checklist. If a generated contract or summary leaves out or weakens a beat from the original Scene Idea, follow the original idea.

Preserve the direction of agency and emotional causality in each beat: who initiates, comforts, is comforted, expresses gratitude, is thanked, asks, answers, acts, or undergoes the intended emotional change. Those relationships are part of the beat, not interchangeable staging. Do not swap the roles or move a character's gratitude to someone else merely to preserve the mood.

Begin with the saved state for starting location, physical condition, time, and character knowledge, but treat its narrative summary as fallible rather than automatically authoritative. A generated state summary does not prove by itself that every past event it mentions actually occurred. Use accepted manuscript prose, canon, and the original Scene Idea to check consequential claims about prior events. If a claim appears only in a state summary and is not supported by accepted prose, canon, or explicit author intent in the Scene Idea, do not repeat it as established history; leave it out or preserve its uncertainty. The original Scene Idea can explicitly correct a stale or mistaken summary. Do not replay completed events, contradict established facts, or give a character knowledge they have not earned. Knowing that an event happened is not the same as witnessing it. Earlier manuscript excerpts are historical evidence for events, and the RETRIEVED HISTORICAL CONTINUITY ARCHIVE is supporting context. For current physical conditions and explicitly established facts, the current saved state and explicit present-scene direction take precedence; never let a stale excerpt override what is true now. Generated state summaries remain fallible for unsupported historical claims.

Keep explicit author rules marked MUST, NEVER, REQUIRED, or FORBIDDEN. Stable author writing guidance carries recurring style preferences and explicit avoidances. Honor clear prohibitions when relevant. Treat general writing preferences as a tonal compass, not a checklist. Temporary writer notes are suggestions, not canon.

THE CREATIVE JOB
Make the story feel lived in. Invent natural dialogue, small talk, gestures, sensory texture, routines, background activity, incidental characters, plausible shared memories, transitions, and connective actions. Make ordinary creative decisions without waiting for the author to specify every step. Omitted everyday details are opportunities to write, not things forbidden by silence.

Take creative initiative in present-scene action: fresh dialogue, choices, realizations, discoveries, complications, and other developments are welcome when they grow naturally from the characters and story. Be careful with retroactive history. Do not invent consequential past events, promises, encounters, motives, or relationship-defining moments as established fact unless the active novel's canon, accepted manuscript, or Scene Idea supports them. Do not use invented off-page people or actions to explain events without author support. Treat explicit unresolved_questions as open questions, not confirmed answers. Distinguish what characters observe, infer, suspect, and know. Keep theories tentative unless the story's evidence and the Scene Idea establish them. Respect explicit boundaries, preserve corrections established by accepted prose, and do not indirectly introduce events or explanations the author has ruled out. Do not contradict canon or undo settled events. Creative developments are welcome when they fit the story.

CHARACTER IDENTITY, MOVEMENT, REPETITION, AND STORY TIME
Character cards are authoritative for each character's established gender and any recorded pronouns. Preserve them consistently in narration, dialogue tags, and action; never change a character's gender or use contradictory pronouns. If a pronoun might be ambiguous, use the character's name rather than guessing.

Physical movement must fit the established layout. A character remains where the accepted prose leaves them unless a plausible move is shown or established; never jump someone between locations without travel or transition. Keep every relevant character's location consistent in the prose and ending-state records.

Do not repeat completed events, scenes, or reports as if they were happening for the first time. Continue from the actual endpoint of the previous scene and move the story forward. Recap an event only when a character is genuinely telling it to someone who was absent or the recollection has a clear narrative purpose.

Keep danger and consequences proportionate to the situation. Show the warning signs, time, resources, and transitions needed for important outcomes to feel credible. Do not jump from a minor problem to catastrophe without setup or resolve a serious problem without a believable path. Respect the active novel's established geography, travel, communications, available resources, and physical constraints.

Separate observation, theory, and confirmation. Characters may speculate, disagree, test ideas, and make mistakes, but the prose must not quietly turn a hypothesis into an established fact. Keep unresolved questions unresolved. Do not invent hidden motives or causal links between separate events unless the story's evidence supports them.

SHAPE AND VOICE
Write a complete scene with a natural flow of opening, development, and consequence. Every concrete story commitment named in the original Scene Idea must happen on-page, including specific dialogue or nicknames, relationship milestones, and planned emotional turns. Include the important movements named in the idea without mechanically checking off incidental wording. If the scene spans several phases or time, carry it through that arc instead of stopping after the first prominent action. Honor an explicit endpoint or hard stop; do not end too early or cross the boundary into a later scene. If no endpoint is specified, choose the most satisfying natural stopping point.

Let character voice, mood, and author preferences shape the prose without turning them into formulas. Vary rhythm as the moment calls for it. Use dialogue, interior thought, action, direct emotion, and sensory detail in whatever combination makes the scene vivid and believable. Avoid repetition or stock phrasing through good judgment, not mechanical avoidance rules.

Return only natural story prose. Do not include analysis, summary, headings, or commentary.
"""
        parts = [base, "\nSCENE REFERENCE\n"]
        for name, content in files:
            parts.append(f"\n[{name}]\n{content}\n")
        parts.append("\nEND SCENE REFERENCE")
        return "\n".join(parts)

    def _fit_writer_context(self, files, base_prompt="", raise_on_overflow=True):
        """Bound Writer input; preview callers may inspect required context that will not fit."""
        return fit_writer_context_files(
            files,
            prompt_builder=self._writer_system_prompt,
            base_prompt=base_prompt,
            context_window_tokens=int(os.environ.get("STORY_WRITER_CONTEXT", "16384")),
            reserved_output_tokens=int(os.environ.get("STORY_WRITER_MAX_TOKENS", "4000")),
            safety_margin_tokens=int(os.environ.get("STORY_WRITER_CONTEXT_MARGIN", "2400")),
            raise_on_overflow=raise_on_overflow,
        )

    def _toggle_prompt_trace(self):
        """Persistently enable or disable one-operation diagnostic trace capture."""
        if (
            getattr(self, "writer_generation_in_progress", False)
            or self.__dict__.get("focused_revision_in_progress", False)
            or self.__dict__.get("state_analysis_in_progress", False)
        ):
            return
        enabled = not bool(getattr(self, "prompt_trace_enabled", False))
        try:
            save_prompt_trace_enabled(enabled)
        except OSError as exc:
            current = bool(getattr(self, "prompt_trace_enabled", False))
            self.writer_trace_button.configure(
                text="Prompt Trace (On)" if current else "Prompt Trace (Off)"
            )
            self.writer_trace_status.configure(
                text=f"Could not save the trace setting, so it remains {'On' if current else 'Off'}: {exc}"
            )
            return

        self.prompt_trace_enabled = enabled
        if enabled:
            self.writer_trace_button.configure(text="Prompt Trace (On)")
            self.writer_trace_status.configure(
                text=(
                    "On. Each Writer generation and State Analysis is captured. The latest trace "
                    "overwrites the previous local file and private GitHub trace. Captures include "
                    "story text and prompts."
                )
            )
        else:
            self.writer_trace_button.configure(text="Prompt Trace (Off)")
            self.writer_trace_status.configure(
                text="Off. No new prompts or State Analysis responses are being recorded."
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
        validator_review = bool(self.__dict__.get("validator_review_in_progress", False))
        suggesting_idea = bool(self.__dict__.get("scene_idea_suggestion_in_progress", False))
        busy = notes_updating or contract_building or generating or focused_revision or validator_review or suggesting_idea

        self.writer_start_button.configure(
            state="disabled" if running or busy else "normal"
        )
        self.writer_stop_button.configure(
            state="normal" if running and not notes_updating and not contract_building and not focused_revision and not validator_review else "disabled"
        )
        self.writer_write_button.configure(
            state="normal" if running and self.package and not has_pending and not busy else "disabled"
        )
        acceptance_blocked = bool(
            str(self.__dict__.get("writer_scene_accept_block_reason", "") or "").strip()
        )
        self.writer_accept_button.configure(
            state="normal"
            if has_pending and self.package and not busy and not acceptance_blocked
            else "disabled"
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
                state="disabled" if generating or focused_revision or contract_building or notes_updating or suggesting_idea or bool(self.__dict__.get("state_analysis_in_progress", False)) else "normal",
                text="Prompt Trace (On)" if getattr(self, "prompt_trace_enabled", False) else "Prompt Trace (Off)",
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
        elif suggesting_idea:
            status_text = "Generating an editable next-scene suggestion..."
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
        try:
            files, budget_metrics = self._fit_writer_context(files)
        except WriterContextBudgetError as exc:
            self._show_copyable_error("Writer Context Budget", str(exc))
            return
        system_prompt = self._writer_system_prompt(files)
        self.writer_last_context_metrics = {
            **dict(getattr(self, "writer_last_context_metrics", {}) or {}),
            **budget_metrics,
        }
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
        """Seed a blank notebook only when automatic craft-note learning is enabled."""
        # This optional housekeeping restarts llama-cli and must never delay
        # normal writing unless the author explicitly opts in.
        if not writer_notes_auto_update_enabled():
            return False
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
        try:
            files, budget_metrics = self._fit_writer_context(files)
        except WriterContextBudgetError as exc:
            self._show_copyable_error("Writer Context Budget", str(exc))
            return
        system_prompt = self._writer_system_prompt(files)
        self.writer_last_context_metrics = {
            **dict(getattr(self, "writer_last_context_metrics", {}) or {}),
            **budget_metrics,
        }

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

    def _writer_scene_boundary_prompt(self):
        """Add a concise scene brief; core craft guidance lives in the system prompt."""
        return (
            "SCENE INTENT:\n"
            "Write one complete scene from the author's original idea and saved story state. "
            "The idea gives purpose and direction, not a script. Preserve canon, character knowledge, "
            "concrete planned beats and their agency, explicit boundaries, and the intended endpoint. "
            "Use creative judgment for dialogue, emotional progression, pacing, atmosphere, "
            "and connective action. Do not invent unsupported past facts or concrete clues "
            "forbidden by the author. Do not stop early or cross a stated hard stop.\n\n"
            "Write the scene now. Output only the prose."
        )

    def _preview_writer_context(self):
        """Show the assembled prompt context without generating or changing story state."""
        if self.package is None:
            messagebox.showinfo("Writer Context Preview", "Load a novel before previewing Writer context.")
            return
        if getattr(self, "writer_generation_in_progress", False):
            messagebox.showinfo("Writer Context Preview", "Wait for the current Writer task to finish.")
            return

        chapter = int(self.package.current_state.get("chapter", 1) or 1)
        scene = int(self.package.current_state.get("scene", 1) or 1)
        direction = self.writer_direction_text.get("1.0", "end-1c").strip()
        if not direction:
            direction = "Write the next scene naturally from the current story state."
        contract = self._scene_contract(chapter, scene)
        current_state = json.loads(json.dumps(self.package.current_state, ensure_ascii=False))
        guidance_plan = self.package.extra_json.get("writing_guidance.json", {})
        guidance_entry = (
            self._chapter_scene_guidance(guidance_plan, chapter, scene)
            if isinstance(guidance_plan, dict) else None
        )
        continuity_focus = (
            str(guidance_entry.get("continuity_focus", "") or "").strip()
            if isinstance(guidance_entry, dict) else ""
        )

        files = self._writer_package_files()
        historical_archive = {"snippets": [], "text": "", "characters": 0, "estimated_tokens": 0}
        archive_search_error = ""
        try:
            if self.package.path is not None:
                archive_character_names = [
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
                    build_historical_relevance_query(
                        direction,
                        str(guidance_entry.get("scene_idea", "") or "") if isinstance(guidance_entry, dict) else "",
                        str(guidance_entry.get("direction", "") or "") if isinstance(guidance_entry, dict) else "",
                        str(guidance_entry.get("end_condition", "") or "") if isinstance(guidance_entry, dict) else "",
                        continuity_focus,
                    ),
                    before_chapter=chapter,
                    before_scene=scene,
                    character_names=archive_character_names,
                    limit=4,
                    max_chars=2400,
                )
        except Exception as exc:
            archive_search_error = str(exc)

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
            files.append(("historical_continuity_archive.txt", archive_prompt.strip()))

        writer_context = SceneContract.writer_prompt_context(direction, contract)
        base_prompt = writer_context + "\n\n" + self._writer_scene_boundary_prompt()
        try:
            fitted_files, budget_metrics = self._fit_writer_context(
                files, base_prompt=base_prompt, raise_on_overflow=False
            )
        except WriterContextBudgetError as exc:
            self._show_copyable_error("Writer Context Budget", str(exc))
            return

        system_prompt = self._writer_system_prompt(fitted_files)
        prompt_metrics = context_size_report(system_prompt + base_prompt)
        included = budget_metrics["included_reference_files"]
        archive_included = "historical_continuity_archive.txt" in included
        lines = [
            f"READ-ONLY WRITER CONTEXT PREVIEW: Chapter {chapter}, Scene {scene}",
            "",
            "No scene was generated. This preview does not save or alter the manuscript or story state.",
            f"Continuity selection: {'author-pinned focus' if continuity_focus else 'automatic'}",
        ]
        if continuity_focus:
            lines.extend(["", "AUTHOR-PINNED CONTINUITY FOCUS:", continuity_focus])
        if budget_metrics["required_context_over_budget"]:
            lines.extend([
                "",
                "WARNING: Required context exceeds the safe input budget. This is a diagnostic-only preview. "
                "Scene generation remains blocked until the context fits.",
                f"Estimated overage: {budget_metrics['estimated_overage_tokens']:,} conservative tokens.",
            ])
        lines.extend([
            "",
            f"Assembled prompt size: {prompt_metrics['characters']:,} characters.",
            f"Conservative input estimate: {budget_metrics['final_conservative_tokens']:,}/"
            f"{budget_metrics['input_token_budget']:,} tokens of safe input budget.",
            f"Reserved for generation: {budget_metrics['reserved_output_tokens']:,} tokens; "
            f"safety margin: {budget_metrics['safety_margin_tokens']:,} tokens.",
            "Token counts are conservative estimates, not tokenizer-exact measurements.",
            "",
            "REFERENCE FILES INCLUDED:",
            *[f"- {name}" for name in included],
            "",
            "PROMPT SIZE BREAKDOWN:",
            f"- Static Writer instructions: {len(self._writer_system_prompt([])):,} characters "
            f"(about {conservative_token_estimate(self._writer_system_prompt([])):,} estimated tokens).",
            f"- Current Scene Direction/contract: {len(writer_context):,} characters "
            f"(about {conservative_token_estimate(writer_context):,} estimated tokens).",
            *[
                f"- {name}: {len(content):,} characters "
                f"(about {conservative_token_estimate(content):,} estimated tokens)"
                for name, content in sorted(fitted_files, key=lambda item: len(item[1]), reverse=True)[:10]
            ],
            "",
            "FILES PRUNED: " + (", ".join(budget_metrics["pruned_reference_files"]) or "none"),
            "FILES COMPACTED: " + (", ".join(budget_metrics["compacted_reference_files"]) or "none"),
            "",
            f"Historical excerpts retrieved: {len(historical_archive.get('snippets', []))}; "
            f"included in prompt: {'yes' if archive_included else 'no'}.",
        ])
        if archive_search_error:
            lines.append(f"Historical archive search issue: {archive_search_error}")
        knowledge_entry = next(
            (content for name, content in fitted_files if name == "scene_character_knowledge.json"),
            None,
        )
        lines.extend(["", "SELECTED CHARACTER KNOWLEDGE:"])
        if knowledge_entry:
            try:
                knowledge_data = json.loads(knowledge_entry)
                lines.append(json.dumps(knowledge_data, indent=2, ensure_ascii=False) if knowledge_data else "(none selected)")
            except (TypeError, ValueError):
                lines.append(knowledge_entry)
        else:
            lines.append("(The knowledge file was not included after budget fitting.)")
        archive_entry = next(
            (content for name, content in fitted_files if name == "historical_continuity_archive.txt"),
            None,
        )
        lines.extend(["", "RETRIEVED HISTORICAL EXCERPTS:"])
        lines.append(archive_entry if archive_entry else "(No historical excerpts included.)")
        self._show_copyable_error(
            "Writer Context Preview",
            "\n".join(lines),
            summary=(
                "Read-only diagnostic. Close this window to return to StoryBuilder. "
                "No scene prose was generated."
            ),
        )

    def _clear_previous_generated_scene_display(self, preserve_draft=False):
        """Clear the Writer display, optionally retaining the draft for recovery.

        Accepted manuscript files and the accepted-scene cache are untouched.
        During regeneration, keep the previous draft in memory while clearing
        the display for the incoming streamed replacement.
        """
        if not preserve_draft:
            self.generated_scene = ""
            self.writer_scene_accept_block_reason = ""
            self.generated_scene_context = None
            self.generated_scene_start_state = None
            self.focused_revision_history = []

        output = self.__dict__.get("writer_output_text")
        if output is not None:
            output.delete("1.0", "end")

        state_preview = self.__dict__.get("writer_state_preview")
        if state_preview is not None:
            state_preview.delete("1.0", "end")

        diff_preview = self.__dict__.get("writer_state_diff_preview")
        if diff_preview is not None:
            diff_preview.configure(state="normal")
            diff_preview.delete("1.0", "end")
            diff_preview.configure(state="disabled")

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
        if (
            getattr(self, "writer_generation_in_progress", False)
            or self.__dict__.get("focused_revision_in_progress", False)
            or self.__dict__.get("validator_review_in_progress", False)
        ):
            messagebox.showwarning("Writer", "A Writer or validator-review task is already running.")
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

        # Always clear the visible output before streamed text arrives. During
        # regeneration, retain the previous draft in memory for failure recovery.
        self._clear_previous_generated_scene_display(
            preserve_draft=replacing_draft
        )

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
        self.writer_stream_buffer = ""
        self.writer_generation_in_progress = True
        self._update_writer_buttons()

        files = self._writer_package_files()
        model = self.writer_engine.model_path
        author_guidance = self._author_writing_guidance()
        writer_context = SceneContract.writer_prompt_context(direction, contract)
        guidance_plan = self.package.extra_json.get("writing_guidance.json", {})
        guidance_entry = (
            self._chapter_scene_guidance(guidance_plan, chapter, scene)
            if isinstance(guidance_plan, dict) else None
        )
        continuity_focus = (
            str(guidance_entry.get("continuity_focus", "") or "").strip()
            if isinstance(guidance_entry, dict) else ""
        )
        historical_archive = {
            "snippets": [],
            "text": "",
            "characters": 0,
            "estimated_tokens": 0,
        }
        archive_search_error = ""
        try:
            if self.package.path is not None:
                archive_character_names = [
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
                    build_historical_relevance_query(
                        direction,
                        str(guidance_entry.get("scene_idea", "") or "") if isinstance(guidance_entry, dict) else "",
                        str(guidance_entry.get("direction", "") or "") if isinstance(guidance_entry, dict) else "",
                        str(guidance_entry.get("end_condition", "") or "") if isinstance(guidance_entry, dict) else "",
                        continuity_focus,
                    ),
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

        if historical_archive.get("text"):
            files.append(("historical_continuity_archive.txt", archive_prompt.strip()))

        base_prompt = writer_context + "\n\n" + self._writer_scene_boundary_prompt()
        try:
            files, budget_metrics = self._fit_writer_context(files, base_prompt=base_prompt)
        except WriterContextBudgetError as exc:
            self.writer_generation_in_progress = False
            self._update_writer_buttons()
            self._show_copyable_error("Writer Context Budget", str(exc))
            return

        system_prompt = self._writer_system_prompt(files)
        context_budget = context_size_report(system_prompt + base_prompt)
        context_metrics = dict(getattr(self, "writer_last_context_metrics", {}) or {})
        context_metrics.update(budget_metrics)
        archive_kept = "historical_continuity_archive.txt" in budget_metrics["included_reference_files"]
        context_metrics.update({
            "assembled_prompt_characters": context_budget["characters"],
            "assembled_prompt_estimated_tokens": context_budget["estimated_tokens"],
            "historical_archive_characters": int(historical_archive.get("characters", 0) or 0) if archive_kept else 0,
            "historical_archive_estimated_tokens": int(historical_archive.get("estimated_tokens", 0) or 0) if archive_kept else 0,
            "historical_archive_snippets": len(historical_archive.get("snippets", [])) if archive_kept else 0,
            "archive_search_error": archive_search_error,
        })
        self.writer_last_context_metrics = context_metrics
        pruned_sources = ", ".join(budget_metrics["pruned_reference_files"]) or "none"
        compacted_sources = ", ".join(budget_metrics["compacted_reference_files"]) or "none"
        focus_status = "author-pinned continuity used" if continuity_focus else "automatic continuity selection"
        archive_count = context_metrics["historical_archive_snippets"]
        self.writer_status.configure(
            text=(
                f"Writing scene... context {budget_metrics['final_conservative_tokens']:,}/"
                f"{budget_metrics['input_token_budget']:,} safe input tokens; "
                f"{budget_metrics['reserved_output_tokens']:,} output tokens reserved plus "
                f"{budget_metrics['safety_margin_tokens']:,} safety margin. "
                f"Pruned: {pruned_sources}. Compacted: {compacted_sources}. "
                f"{focus_status}; historical excerpts included: {archive_count}."
            )
        )

        prompt_trace = None
        if getattr(self, "prompt_trace_enabled", False):
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
            self.active_prompt_trace = prompt_trace
            self.writer_engine.prompt_trace = prompt_trace
            prompt_trace.record_event(
                "scene_generation_started",
                chapter=chapter,
                scene=scene,
                max_attempts=1,
            )
            self.writer_trace_button.configure(text="Prompt Trace (On)", state="disabled")
            self.writer_trace_status.configure(
                text=(
                    "Capturing this Writer run. The latest trace will overwrite the previous file and "
                    "sync to the private GitHub trace repository when finished. Tracing stays on."
                )
            )

        def on_scene_delta(fragment):
            if not fragment:
                return
            # Keep a recoverable copy in case the model stops after partial output.
            self.writer_stream_buffer = str(
                getattr(self, "writer_stream_buffer", "")
            ) + str(fragment)
            try:
                self.after(
                    0,
                    lambda fragment=str(fragment), target=(chapter, scene):
                        self._append_streamed_scene_chunk(target, fragment),
                )
            except tk.TclError:
                pass

        identity_reference = {}
        character_cards = getattr(self.package, "characters", {})
        if isinstance(character_cards, dict):
            for filename, card in character_cards.items():
                if not isinstance(card, dict):
                    continue
                character_name = str(card.get("name", "") or "").strip() or Path(str(filename)).stem
                identity = {}
                for identity_key in ("gender", "pronouns"):
                    identity_value = str(card.get(identity_key, "") or "").strip()
                    if identity_value:
                        identity[identity_key] = identity_value
                if character_name and identity:
                    identity_reference[character_name] = identity

        def work():
            answer = ""
            trace_result = None
            error = None
            completion_notice = ""
            review_findings = []
            review_context = None
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
                        context_budget=context_metrics,
                    )
                audit_scene_context = writer_context
                if identity_reference:
                    audit_scene_context += (
                        "\n\nAUTHORITATIVE CHARACTER CARD IDENTITY REFERENCE "
                        "(gender and recorded pronouns):\n"
                        + json.dumps(identity_reference, indent=2, ensure_ascii=False)
                    )
                historical_context = archive_prompt.strip() if archive_kept else ""
                review_context = {
                    "model_path": model,
                    "writer_system_prompt": system_prompt,
                    "scene_context": audit_scene_context,
                    "contract": json.loads(json.dumps(contract, ensure_ascii=False)),
                    "current_state": json.loads(json.dumps(current_state, ensure_ascii=False)),
                    "author_guidance": author_guidance,
                    "historical_context": historical_context,
                }
                answer, completion_notice = generate_scene_with_completion_check(
                    engine=self.writer_engine,
                    model_path=model,
                    writer_system_prompt=system_prompt,
                    initial_prompt=base_prompt,
                    scene_context=audit_scene_context,
                    contract=contract,
                    current_state=current_state,
                    author_guidance=author_guidance,
                    historical_context=historical_context,
                    on_draft_delta=on_scene_delta,
                    on_review_findings=lambda items: review_findings.extend(items),
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
                    answer, error, trace_result, completion_notice,
                    review_findings, review_context,
                ),
            )

        self.writer_thread = threading.Thread(target=work, daemon=True)
        self.writer_thread.start()
    def _append_streamed_scene_chunk(self, target, fragment):
        """Append model output to the Writer box on the Tk main thread."""
        if not getattr(self, "writer_generation_in_progress", False):
            return
        if getattr(self, "writer_generation_context", None) != target:
            return
        output = self.__dict__.get("writer_output_text")
        if output is None or not fragment:
            return
        output.insert("end", fragment)
        output.see("end")

    def _finish_generated_scene(
        self, answer, error, trace_result=None, completion_notice="",
        review_findings=None, review_context=None,
    ):
        target = getattr(self, "writer_generation_context", None)
        if trace_result is not None:
            self.active_prompt_trace = None
            if self.__dict__.get("writer_trace_button") is not None:
                self.writer_trace_button.configure(
                    text="Prompt Trace (On)" if getattr(self, "prompt_trace_enabled", False) else "Prompt Trace (Off)"
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
            error_draft = str(answer or "").strip()
            if not error_draft:
                error_draft = str(
                    self.__dict__.get("writer_stream_buffer", "") or ""
                ).strip()
            preserved_draft = bool(error_draft)
            if preserved_draft:
                self.generated_scene = error_draft
                self.writer_scene_accept_block_reason = (
                    "Scene generation failed before a verified completion result was available. "
                    "Regenerate the scene and let the completion check pass before accepting it.\n\n"
                    + str(error)
                )
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
                # No replacement prose arrived. Restore the retained draft for review.
                self.writer_output_text.delete("1.0", "end")
                self.writer_output_text.insert("1.0", self.generated_scene)
                self.writer_status.configure(
                    text="Regeneration failed. Your previous draft remains unchanged."
                )
            else:
                self.writer_scene_accept_block_reason = ""
                self.writer_status.configure(
                    text="Scene generation failed. No scene was accepted or saved."
                )
            return

        self.generated_scene = str(answer or "").strip()
        completion_notice = str(completion_notice or "").strip()
        if not completion_notice:
            completion_notice = (
                "AUTOMATED REVIEW ERROR: no completion-check result was returned. "
                "The original draft was preserved. Regenerate the scene before accepting."
            )
        findings = [dict(item) for item in (review_findings or []) if isinstance(item, dict)]
        self.generated_scene_review_context = review_context if isinstance(review_context, dict) else None
        # Findings are handled one at a time below. Acceptance remains disabled
        # while that interactive queue is open, then becomes the author's choice.
        if findings:
            self.writer_scene_accept_block_reason = ""
        elif not completion_notice_is_success(completion_notice):
            self.writer_scene_accept_block_reason = completion_notice
        else:
            self.writer_scene_accept_block_reason = ""
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
            # Keep the status area readable even when the diagnostic includes a traceback.
            status_text += "\n\n" + str(completion_notice).splitlines()[0]
        self.writer_status.configure(text=status_text)
        if findings:
            self._start_validator_review(findings, completion_notice, review_context)
        elif completion_notice and not completion_notice_is_success(completion_notice):
            self._show_copyable_error(
                "Scene Completion Check",
                str(completion_notice),
                summary=(
                    "The generated scene remains an unaccepted draft. Its automated completion/"
                    "continuity check failed, was skipped, or could not verify the scene. "
                    "Select the report below with Ctrl+A and copy it with Ctrl+C when reporting this problem."
                ),
            )


    def _start_validator_review(self, findings, notice="", review_context=None):
        """Present validator findings sequentially without rewriting the scene automatically."""
        items = [dict(item) for item in (findings or []) if isinstance(item, dict)]
        self.validator_review_state = {
            "queue": items,
            "skipped": [],
            "dismissed": [],
            "applied": [],
            "context": review_context if isinstance(review_context, dict) else None,
            "notice": str(notice or ""),
            "reviewed_count": 0,
            "current": None,
        }
        self.validator_review_in_progress = True
        self.writer_scene_accept_block_reason = ""
        self._update_writer_buttons()
        self.writer_status.configure(
            text=(
                f"Scene generated. Reviewing {len(items)} validator finding(s) one at a time. "
                "The draft remains unaccepted and will not change unless you apply a fix."
            )
        )
        self._show_next_validator_finding()

    def _start_state_validator_review(self, findings, review_context):
        """Open the sequential review for proposed state wording, without applying it."""
        self.validator_review_state = {
            "mode": "state",
            "queue": [dict(item) for item in findings if isinstance(item, dict)],
            "skipped": [],
            "dismissed": [],
            "applied": [],
            "context": review_context if isinstance(review_context, dict) else {},
            "notice": "Proposed state review",
            "reviewed_count": 0,
            "current": None,
            "working_patch": dict(self.pending_state_patch or {}),
        }
        self.validator_review_in_progress = True
        self._update_writer_buttons()
        if hasattr(self, "writer_apply_state_button"):
            self.writer_apply_state_button.configure(state="disabled")
        if hasattr(self, "writer_analyze_button"):
            self.writer_analyze_button.configure(state="disabled")
        self.writer_status.configure(
            text=(
                f"Reviewing {len(findings)} proposed state concern(s) one at a time. "
                "The saved state is unchanged until you approve Apply State Update."
            )
        )
        self._show_next_validator_finding()

    def _finish_state_validator_review(self):
        state = getattr(self, "validator_review_state", None)
        if not isinstance(state, dict) or state.get("mode") != "state":
            return
        candidate_patch = dict(state.get("working_patch") or {})
        try:
            if self.package is None:
                raise ValueError("No novel package is open.")
            StateManager.validate_patch(self.package.current_state, candidate_patch)
        except (TypeError, ValueError) as exc:
            self._show_copyable_error(
                "Proposed State Correction",
                "The corrected proposal failed a safety check. The original proposal remains available and nothing was saved.\n\n"
                + str(exc),
            )
            candidate_patch = dict(self.pending_state_patch or {})

        applied = len(state.get("applied", []))
        dismissed = len(state.get("dismissed", []))
        skipped = len(state.get("skipped", []))
        self.last_validator_review_skipped = list(state.get("skipped", []))
        self.pending_state_patch = candidate_patch
        self.validator_review_in_progress = False
        self.validator_review_state = None
        self._close_validator_review_dialog()

        if self.package is not None and isinstance(self.pending_state_patch, dict):
            reconstructed_state = StateManager.merge_patch(
                self.package.current_state,
                self.pending_state_patch,
            )
            self.writer_state_preview.delete("1.0", "end")
            self.writer_state_preview.insert(
                "1.0", json.dumps(reconstructed_state, indent=2, ensure_ascii=False)
            )
            self._writer_state_reviewed_preview = json.dumps(
                reconstructed_state, sort_keys=True, ensure_ascii=False
            )
            self.writer_state_diff_preview.configure(state="normal")
            self.writer_state_diff_preview.delete("1.0", "end")
            self.writer_state_diff_preview.insert(
                "1.0",
                build_state_change_summary(self.package.current_state, reconstructed_state),
            )
            self.writer_state_diff_preview.configure(state="disabled")
            if "writer_state_situation_quick" in self.__dict__:
                self._refresh_quick_state_editor(reconstructed_state)

        self._update_writer_buttons()
        summary = (
            f"State review finished: {applied} focused correction(s) applied to the proposal, "
            f"{dismissed} concern(s) dismissed, {skipped} skipped. Nothing has been saved."
        )
        if skipped:
            summary += " Skipped concerns remain unresolved; inspect the plain-English changes before applying."
        summary += " Apply State Update only when the proposed state is correct."
        if state.get("last_recheck_warning"):
            summary += " The last recheck could not complete: " + str(state["last_recheck_warning"]).splitlines()[0]
        self.writer_status.configure(text=summary)

    def _recheck_state_validator_review_after_fix(self):
        """Re-run the state audit after an author-approved wording correction."""
        state = getattr(self, "validator_review_state", None)
        dialog_state = getattr(self, "validator_review_dialog_state", None)
        if not isinstance(state, dict) or state.get("mode") != "state":
            return
        context = state.get("context") or {}
        working_patch = dict(state.get("working_patch") or {})
        original_dismissed = list(state.get("dismissed", []))
        original_skipped = list(state.get("skipped", []))
        dialog_state_to_keep = dialog_state

        if isinstance(dialog_state_to_keep, dict):
            for key in ("apply_button", "dismiss_button", "skip_button", "retry_button"):
                try:
                    dialog_state_to_keep[key].configure(state="disabled")
                except Exception:
                    pass
            dialog_state_to_keep["status"].configure(
                text="Focused correction applied to the proposal. Rechecking it now; saved state is unchanged."
            )
        self.writer_status.configure(text="Rechecking the proposed state after your approved correction...")

        def work():
            findings = []
            try:
                findings, warning = review_state_proposal(
                    engine=self.writer_engine,
                    model_path=context.get("model_path") or self.writer_engine.model_path,
                    original_system_prompt=str(context.get("writer_system_prompt") or ""),
                    current_state=context.get("current_state") or {},
                    proposed_patch=working_patch,
                    accepted_scene=str(context.get("accepted_scene") or ""),
                    author_guidance=str(context.get("author_guidance") or ""),
                    scene_idea=str(context.get("scene_context") or ""),
                    prompt_trace=None,
                )
            except Exception as exc:
                findings = []
                warning = "The correction remains only in the proposal. The state check could not finish: " + str(exc).splitlines()[0]
            try:
                self.after(
                    0,
                    lambda: self._finish_state_validator_review_recheck(
                        findings, original_dismissed, original_skipped, dialog_state_to_keep, warning
                    ),
                )
            except tk.TclError:
                pass

        self.writer_thread = threading.Thread(target=work, daemon=True)
        self.writer_thread.start()

    def _finish_state_validator_review_recheck(
        self, findings, original_dismissed, original_skipped, dialog_state, warning=None,
    ):
        state = getattr(self, "validator_review_state", None)
        if not isinstance(state, dict) or state.get("mode") != "state":
            self._close_validator_review_dialog()
            return
        self.validator_review_state["last_recheck_warning"] = warning
        new_items = [dict(item) for item in (findings or []) if isinstance(item, dict)]
        still_skipped = [
            item for item in new_items
            if any(review_findings_match(item, old) for old in original_skipped)
        ]
        self.validator_review_state["skipped"] = still_skipped
        self.validator_review_state["queue"] = [
            item for item in new_items
            if not any(review_findings_match(item, old) for old in original_dismissed)
            and not any(review_findings_match(item, old) for old in still_skipped)
        ]
        self._close_validator_review_dialog()
        self._show_next_validator_finding()

    def _validator_review_supporting_context(self):
        """Supply a compact, read-only slice of canon to the local edit suggester."""
        review_state = getattr(self, "validator_review_state", None) or {}
        context = review_state.get("context") or {}
        contract = context.get("contract") or {}
        state = context.get("current_state") or {}
        relevant_keys = (
            "current_situation", "location", "time_of_day", "physical_state",
            "character_knowledge", "unresolved_questions", "scene_cast",
            "continuity_requirements",
        )
        relevant_state = {
            key: state[key] for key in relevant_keys if key in state
        }
        parts = []
        scene_context = str(context.get("scene_context", "") or "").strip()
        if scene_context:
            parts.append(
                "AUTHOR'S SCENE DIRECTION AND CHARACTER REFERENCE (read-only):\n"
                + scene_context[:6000]
            )
        idea = str(contract.get("author_idea", "") or "").strip()
        if idea:
            parts.append("AUTHOR'S ORIGINAL SCENE IDEA:\n" + idea[:5000])
        historical = str(context.get("historical_context", "") or "").strip()
        if historical:
            parts.append(
                "RELEVANT ACCEPTED MANUSCRIPT CONTEXT (read-only):\n"
                + historical[:4000]
            )
        if relevant_state:
            parts.append(
                "RELEVANT STARTING STATE (read-only):\n"
                + json.dumps(relevant_state, ensure_ascii=False, indent=2)[:6000]
            )
        guidance = str(context.get("author_guidance", "") or "").strip()
        if guidance:
            parts.append("STABLE AUTHOR GUIDANCE (read-only):\n" + guidance[:4000])
        return "\n\n".join(parts)[:12000]

    @staticmethod
    def _set_review_text(widget, value, *, readonly=False):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        if value:
            widget.insert("1.0", str(value))
        if readonly:
            widget.configure(state="disabled")

    def _show_next_validator_finding(self):
        state = getattr(self, "validator_review_state", None)
        if not isinstance(state, dict):
            self._finish_validator_review()
            return

        queue_items = state.get("queue", [])
        if not queue_items:
            skipped = list(state.get("skipped", []))
            if skipped:
                revisit = messagebox.askyesno(
                    "Skipped Validator Findings",
                    (
                        f"You skipped {len(skipped)} finding(s).\n\n"
                        "Choose Yes to review those findings now. Choose No to finish the review "
                        "with those concerns left unresolved and available for your author judgment."
                    ),
                    parent=self,
                )
                if revisit:
                    state["queue"] = skipped
                    state["skipped"] = []
                    self._show_next_validator_finding()
                    return
            self._finish_validator_review()
            return

        finding = queue_items.pop(0)
        state["current"] = finding
        state_mode = state.get("mode") == "state"
        finding_field = str(finding.get("field") or "current_situation") if state_mode else ""
        if state_mode:
            source = get_state_patch_value(state.get("working_patch") or {}, finding_field)
            if not isinstance(source, str):
                source = ""
        else:
            source = self._writer_editor_prose()
        state["source_at_open"] = source
        state["current_patch"] = None

        window = tk.Toplevel(self)
        window.title("Review Proposed State Change" if state_mode else "Review Scene Finding")
        window.transient(self)
        window.geometry("780x690")
        window.minsize(640, 520)
        window.protocol("WM_DELETE_WINDOW", self._skip_validator_review_finding)
        pages = ttk.Notebook(window)
        pages.pack(fill="both", expand=True)
        outer = ttk.Frame(pages, padding=12)
        pages.add(outer, text="Review Finding")

        # Keep review modal while making the complete prose available in a
        # regular read-only field, so Ctrl+A/Ctrl+C work without another button.
        draft_text = None
        if not state_mode:
            draft_page = ttk.Frame(pages, padding=12)
            pages.add(draft_page, text="Full Scene Draft")
            ttk.Label(
                draft_page,
                text="Read-only complete draft. Use Ctrl+A, then Ctrl+C to copy it.",
            ).pack(anchor="w", pady=(0, 8))
            draft_frame = ttk.Frame(draft_page)
            draft_frame.pack(fill="both", expand=True)
            draft_scrollbar = ttk.Scrollbar(draft_frame, orient="vertical")
            draft_text = tk.Text(
                draft_frame,
                wrap="word",
                yscrollcommand=draft_scrollbar.set,
                padx=8,
                pady=8,
                takefocus=True,
            )
            draft_scrollbar.configure(command=draft_text.yview)
            draft_text.pack(side="left", fill="both", expand=True)
            draft_scrollbar.pack(side="right", fill="y")
            draft_text.insert("1.0", source or "(No scene draft is available.)")
            draft_text.configure(state="disabled")
            self._add_context_menu(draft_text)

        reviewed = len(state.get("applied", [])) + len(state.get("dismissed", [])) + len(state.get("skipped", []))
        ttk.Label(
            outer,
            text=f"Finding {reviewed + 1}  ·  {len(queue_items) + 1} currently queued",
            font=("", 11, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text=str(finding.get("title", "Possible issue to review")),
            font=("", 12, "bold"),
        ).pack(anchor="w", pady=(4, 2))
        concern = tk.Text(outer, height=4, wrap="word", exportselection=False)
        concern.pack(fill="x", pady=(0, 7))
        concern.insert("1.0", str(finding.get("message", "")))
        concern.configure(state="disabled")
        self._add_context_menu(concern)

        ttk.Label(
            outer,
            text=("What should change in this proposed state value? (You can edit these instructions)"
                  if state_mode else "What should change? (You can edit these instructions)")
        ).pack(anchor="w")
        request_box = tk.Text(outer, height=3, wrap="word", undo=True, exportselection=False)
        request_box.pack(fill="x", pady=(3, 7))
        request = str(finding.get("edit_request", "") or "").strip()
        if not request:
            request = (
                "Suggest the smallest safe local fix for this concern. Do not invent story facts "
                "or rewrite the surrounding scene."
            )
        request_box.insert("1.0", request)
        self._add_context_menu(request_box)

        ttk.Label(
            outer,
            text=("Proposed state value / passage to correct" if state_mode
                  else "Exact passage the model proposes to replace")
        ).pack(anchor="w")
        target_box = tk.Text(outer, height=3, wrap="word", exportselection=False)
        target_box.pack(fill="x", pady=(3, 7))
        if state_mode and source:
            target_box.insert("1.0", source)
        target_box.configure(state="disabled")
        self._add_context_menu(target_box)

        ttk.Label(
            outer,
            text=("Corrected proposed state text (editable before applying)" if state_mode
                  else "Proposed replacement (editable before applying)")
        ).pack(anchor="w")
        replacement_box = tk.Text(
            outer, height=7, wrap="word", undo=True, exportselection=False
        )
        replacement_box.pack(fill="both", expand=True, pady=(3, 7))
        self._add_context_menu(replacement_box)

        status = ttk.Label(outer, text="Preparing a focused suggestion..." if finding.get("can_suggest", True) else "No automatic suggestion was prepared for this unverified finding. You may request one, dismiss it, or skip it.", wraplength=730, justify="left")
        status.pack(anchor="w", pady=(0, 7))

        button_row = ttk.Frame(outer)
        button_row.pack(fill="x")
        apply_button = ttk.Button(
            button_row, text="Apply Fix",
            command=self._apply_validator_review_fix, state="disabled",
        )
        apply_button.pack(side="left")
        dismiss_button = ttk.Button(
            button_row, text="Dismiss: false alarm",
            command=self._dismiss_validator_review_finding,
        )
        dismiss_button.pack(side="left", padx=(6, 0))
        skip_button = ttk.Button(
            button_row, text="Skip for later",
            command=self._skip_validator_review_finding,
        )
        skip_button.pack(side="left", padx=(6, 0))
        retry_button = ttk.Button(
            button_row, text="Generate suggestion",
            command=self._regenerate_validator_review_suggestion,
        )
        retry_button.pack(side="right")

        self.validator_review_dialog = window
        self.validator_review_dialog_state = {
            "window": window,
            "finding": finding,
            "source": source,
            "draft_text": draft_text,
            "request_box": request_box,
            "target_box": target_box,
            "replacement_box": replacement_box,
            "status": status,
            "apply_button": apply_button,
            "dismiss_button": dismiss_button,
            "skip_button": skip_button,
            "retry_button": retry_button,
            "suggesting": False,
            "patch": None,
        }
        window.grab_set()
        window.focus_set()
        if finding.get("can_suggest", True):
            self._request_validator_review_suggestion()
        else:
            apply_button.configure(state="disabled")
            status.configure(
                text="This finding could not be verified reliably. Requesting a suggestion is optional; review it carefully before applying."
            )

    def _request_validator_review_suggestion(self):
        dialog_state = getattr(self, "validator_review_dialog_state", None)
        state = getattr(self, "validator_review_state", None)
        if not isinstance(dialog_state, dict) or not isinstance(state, dict):
            return
        if dialog_state.get("suggesting"):
            return
        request = dialog_state["request_box"].get("1.0", "end-1c").strip()
        finding = dialog_state["finding"]
        request = (
            request
            + "\n\nValidator finding to assess: "
            + str(finding.get("message", "") or "")
            + "\nThe prose may already satisfy this concern. Make only a minimal local edit if one is warranted."
        ).strip()
        if not request:
            dialog_state["status"].configure(text="Describe the intended correction before requesting a suggestion.")
            return

        engine = self.writer_engine
        context = state.get("context") or {}
        model = context.get("model_path") or getattr(engine, "model_path", None)
        original_system_prompt = str(
            context.get("writer_system_prompt")
            or getattr(engine, "system_prompt", "")
            or ""
        )
        source = dialog_state["source"]
        supporting_context = self._validator_review_supporting_context()
        dialog_state["suggesting"] = True
        dialog_state["status"].configure(text="Preparing a focused suggestion. No prose has been changed.")
        for key in ("apply_button", "dismiss_button", "skip_button", "retry_button"):
            dialog_state[key].configure(state="disabled")

        def work():
            patch = None
            error = None
            restore_error = None
            if model is None:
                error = "The Writer model path is not available."
            else:
                patch, error, restore_error = propose_focused_replacement(
                    engine=engine,
                    model_path=model,
                    original_system_prompt=original_system_prompt,
                    original=source,
                    request=request,
                    supporting_context=supporting_context,
                    max_attempts=2,
                )
            try:
                self.after(
                    0,
                    lambda: self._finish_validator_review_suggestion(
                        dialog_state, patch, error, restore_error
                    ),
                )
            except tk.TclError:
                pass

        self.writer_thread = threading.Thread(target=work, daemon=True)
        self.writer_thread.start()

    def _finish_validator_review_suggestion(self, dialog_state, patch, error, restore_error=None):
        if self.validator_review_dialog_state is not dialog_state:
            return
        dialog_state["suggesting"] = False
        dialog_state["patch"] = patch
        state_label = dialog_state["status"]
        if patch:
            self._set_review_text(
                dialog_state["target_box"], patch.get("target_text", ""), readonly=True
            )
            self._set_review_text(
                dialog_state["replacement_box"], patch.get("replacement_text", "")
            )
            dialog_state["apply_button"].configure(state="normal")
            state_label.configure(
                text="Suggested local change ready. Edit the replacement if needed, then Apply Fix. Nothing changes until you approve it."
            )
        else:
            self._set_review_text(dialog_state["target_box"], "", readonly=True)
            dialog_state["apply_button"].configure(state="disabled")
            state_label.configure(
                text=(
                    "No safe local suggestion could be prepared. You may edit the instructions and try again, "
                    "dismiss the finding, or skip it. "
                    + str(error or "No usable replacement was returned.")
                )
            )
        if restore_error:
            state_label.configure(
                text=state_label.cget("text")
                + " Writer context restoration warning: "
                + str(restore_error)
            )
        for key in ("dismiss_button", "skip_button", "retry_button"):
            dialog_state[key].configure(state="normal")
        dialog_state["retry_button"].configure(
            text="Try another suggestion" if patch else "Generate suggestion"
        )

    def _regenerate_validator_review_suggestion(self):
        dialog_state = getattr(self, "validator_review_dialog_state", None)
        if not isinstance(dialog_state, dict) or dialog_state.get("suggesting"):
            return
        self._set_review_text(dialog_state["target_box"], "", readonly=True)
        self._set_review_text(dialog_state["replacement_box"], "")
        dialog_state["patch"] = None
        dialog_state["apply_button"].configure(state="disabled")
        self._request_validator_review_suggestion()

    def _close_validator_review_dialog(self):
        dialog_state = getattr(self, "validator_review_dialog_state", None)
        window = dialog_state.get("window") if isinstance(dialog_state, dict) else None
        if window is not None:
            try:
                window.grab_release()
            except tk.TclError:
                pass
            try:
                window.destroy()
            except tk.TclError:
                pass
        self.validator_review_dialog = None
        self.validator_review_dialog_state = None

    def _apply_validator_review_fix(self):
        dialog_state = getattr(self, "validator_review_dialog_state", None)
        state = getattr(self, "validator_review_state", None)
        if not isinstance(dialog_state, dict) or not isinstance(state, dict):
            return
        patch = dialog_state.get("patch")
        if not isinstance(patch, dict):
            dialog_state["status"].configure(text="No safe local suggestion is available. Generate one before applying a fix.")
            return
        if state.get("mode") == "state":
            field = str(dialog_state["finding"].get("field") or "current_situation")
            working_patch = state.get("working_patch")
            current_value = get_state_patch_value(working_patch or {}, field)
            if not isinstance(current_value, str) or current_value != dialog_state.get("source"):
                dialog_state["status"].configure(
                    text="The proposed state value changed while this finding was open. No correction was applied."
                )
                dialog_state["apply_button"].configure(state="disabled")
                return
            replacement = dialog_state["replacement_box"].get("1.0", "end-1c")
            response = json.dumps(
                {"target_text": patch.get("target_text", ""), "replacement_text": replacement},
                ensure_ascii=False,
            )
            try:
                revised_value = apply_state_text_replacement(
                    current_value,
                    str(patch.get("target_text", "")),
                    replacement,
                )
                set_state_patch_value(working_patch, field, revised_value)
                StateManager.validate_patch(self.package.current_state, working_patch)
            except (TypeError, ValueError) as exc:
                dialog_state["status"].configure(text="No state correction was applied. " + str(exc))
                return
            state.setdefault("applied", []).append(state.get("current") or {})
            state["current"] = None
            self._update_writer_buttons()
            self._recheck_state_validator_review_after_fix()
            return
        current = self._writer_editor_prose()
        if current != dialog_state.get("source"):
            dialog_state["status"].configure(
                text="The draft changed while this finding was open. The proposed edit was not applied; regenerate the suggestion against the current text."
            )
            dialog_state["apply_button"].configure(state="disabled")
            return
        replacement = dialog_state["replacement_box"].get("1.0", "end-1c")
        response = json.dumps(
            {
                "target_text": patch.get("target_text", ""),
                "replacement_text": replacement,
            },
            ensure_ascii=False,
        )
        try:
            revised = apply_focused_replacement(current, response)
        except ValueError as exc:
            dialog_state["status"].configure(text="No change was applied. " + str(exc))
            return
        history = getattr(self, "focused_revision_history", None)
        if not isinstance(history, list):
            history = []
            self.focused_revision_history = history
        history.append(current)
        self.generated_scene = revised
        self.writer_output_text.delete("1.0", "end")
        self.writer_output_text.insert("1.0", revised)
        state.setdefault("applied", []).append(state.get("current") or {})
        state["current"] = None
        self._update_writer_buttons()

        context = state.get("context")
        if isinstance(context, dict):
            dialog_state["status"].configure(
                text="Focused fix applied. Rechecking the revised scene and remaining findings..."
            )
            for key in ("apply_button", "dismiss_button", "skip_button", "retry_button"):
                dialog_state[key].configure(state="disabled")
            self.writer_status.configure(text="Rechecking the scene after your approved local change...")
            self._recheck_validator_review_after_fix(revised)
        else:
            self._close_validator_review_dialog()
            self._show_next_validator_finding()

    def _dismiss_validator_review_finding(self):
        state = getattr(self, "validator_review_state", None)
        if not isinstance(state, dict):
            return
        finding = state.get("current")
        if finding:
            state.setdefault("dismissed", []).append(finding)
            state["current"] = None
        self._close_validator_review_dialog()
        self._show_next_validator_finding()

    def _skip_validator_review_finding(self):
        dialog_state = getattr(self, "validator_review_dialog_state", None)
        if isinstance(dialog_state, dict) and dialog_state.get("suggesting"):
            return
        state = getattr(self, "validator_review_state", None)
        if not isinstance(state, dict):
            return
        finding = state.get("current")
        if finding:
            state.setdefault("skipped", []).append(finding)
            state["current"] = None
        self._close_validator_review_dialog()
        self._show_next_validator_finding()

    def _recheck_validator_review_after_fix(self, revised):
        state = getattr(self, "validator_review_state", None)
        dialog_state = getattr(self, "validator_review_dialog_state", None)
        if not isinstance(state, dict):
            self._close_validator_review_dialog()
            self._finish_validator_review()
            return
        context = state.get("context") or {}
        engine = self.writer_engine
        original_dismissed = list(state.get("dismissed", []))
        original_skipped = list(state.get("skipped", []))

        def work():
            findings = []
            notice = ""
            error = None
            try:
                findings, notice = review_scene_draft(
                    engine=engine,
                    model_path=context["model_path"],
                    writer_system_prompt=context["writer_system_prompt"],
                    prose=revised,
                    scene_context=context["scene_context"],
                    contract=context["contract"],
                    current_state=context["current_state"],
                    author_guidance=context.get("author_guidance", ""),
                    historical_context=context.get("historical_context", ""),
                )
            except Exception as exc:
                error = str(exc)
            try:
                self.after(
                    0,
                    lambda: self._finish_validator_review_recheck(
                        revised, findings, notice, error,
                        original_dismissed, original_skipped, dialog_state,
                    ),
                )
            except tk.TclError:
                pass

        self.writer_thread = threading.Thread(target=work, daemon=True)
        self.writer_thread.start()

    def _finish_validator_review_recheck(
        self, revised, findings, notice, error,
        original_dismissed, original_skipped, dialog_state,
    ):
        state = getattr(self, "validator_review_state", None)
        if not isinstance(state, dict):
            self._close_validator_review_dialog()
            self._finish_validator_review()
            return
        if self._writer_editor_prose() != revised:
            state["queue"] = [
                {
                    "kind": "unavailable",
                    "title": "Draft changed during recheck",
                    "message": "The visible draft changed during the post-edit review. No text was overwritten; review the current draft manually.",
                    "can_suggest": False,
                    "edit_request": "",
                }
            ] + list(state.get("queue", []))
        elif error:
            state["queue"] = [
                {
                    "kind": "unavailable",
                    "title": "Post-edit review could not complete",
                    "message": "The updated draft could not be fully rechecked: " + str(error).splitlines()[0],
                    "can_suggest": False,
                    "edit_request": "",
                }
            ] + list(state.get("queue", []))
        else:
            new_items = [dict(item) for item in (findings or []) if isinstance(item, dict)]
            still_skipped = [
                item for item in new_items
                if any(review_findings_match(item, old) for old in original_skipped)
            ]
            dismissed_matches = [
                item for item in new_items
                if any(review_findings_match(item, old) for old in original_dismissed)
            ]
            self.validator_review_state["skipped"] = still_skipped
            self.validator_review_state["queue"] = [
                item for item in new_items
                if not any(review_findings_match(item, old) for old in original_dismissed)
                and not any(review_findings_match(item, old) for old in still_skipped)
            ]
            self.validator_review_state["last_recheck_notice"] = notice
        self._close_validator_review_dialog()
        self._show_next_validator_finding()

    def _finish_validator_review(self):
        state = getattr(self, "validator_review_state", None)
        if isinstance(state, dict) and state.get("mode") == "state":
            self._finish_state_validator_review()
            return
        if not isinstance(state, dict):
            self.validator_review_in_progress = False
            self._update_writer_buttons()
            return
        applied = len(state.get("applied", []))
        dismissed = len(state.get("dismissed", []))
        skipped = len(state.get("skipped", []))
        self.last_validator_review_skipped = list(state.get("skipped", []))
        self.validator_review_in_progress = False
        self.writer_scene_accept_block_reason = ""
        self.validator_review_state = None
        self._close_validator_review_dialog()
        self._update_writer_buttons()
        summary = (
            f"Validator review finished: {applied} focused fix(es) applied, "
            f"{dismissed} finding(s) dismissed, {skipped} skipped. "
            "Review the scene and accept it only when you are satisfied."
        )
        if skipped:
            summary += " Skipped findings remain unresolved; acceptance is still your decision."
        self.writer_status.configure(text=summary)

    def _regenerate_generated_scene(self):
        if not self._has_pending_generated_scene():
            return
        if (
            getattr(self, "writer_generation_in_progress", False)
            or self.__dict__.get("focused_revision_in_progress", False)
            or self.__dict__.get("validator_review_in_progress", False)
        ):
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
        if (
            getattr(self, "writer_generation_in_progress", False)
            or self.__dict__.get("focused_revision_in_progress", False)
            or self.__dict__.get("validator_review_in_progress", False)
        ):
            return

        editor = self.writer_output_text
        original = editor.get("1.0", "end-1c")
        if not original.strip():
            messagebox.showwarning("Focused Change", "There is no scene draft to revise.")
            return

        # Keep the widget-local selection when focus moves to the request box/button.
        # Capture its exact source span before starting the asynchronous model call.
        try:
            selected_text = editor.get("sel.first", "sel.last")
            before_text = editor.get("1.0", "sel.first")
        except tk.TclError:
            selected_text = ""
            before_text = ""

        if not selected_text or not selected_text.strip():
            messagebox.showwarning(
                "Focused Change",
                "Select the exact passage you want to change in Generated Scene first, then describe the change below.",
            )
            return

        selection_start = len(before_text)
        selection_end = selection_start + len(selected_text)
        if original[selection_start:selection_end] != selected_text:
            self._show_copyable_error(
                "Focused Change",
                "The selected passage could not be matched to the current editor text. No text was changed. Select the passage again and retry.",
            )
            return
        if selection_start == 0 and selection_end == len(original):
            messagebox.showwarning(
                "Focused Change",
                "Select a passage smaller than the entire scene. Focused Change is intended for a local edit.",
            )
            return

        request = self.writer_revision_request_entry.get("1.0", "end-1c").strip()
        if not request:
            messagebox.showwarning("Focused Change", "Describe the specific change you want.")
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
        before_context = original[max(0, selection_start - 350):selection_start]
        after_context = original[selection_end:selection_end + 350]
        self.focused_revision_in_progress = True
        self.writer_status.configure(text="Preparing a focused edit to the selected passage...")
        self._update_writer_buttons()

        def work():
            revised, error, restore_error = revise_selected_passage(
                engine=engine,
                model_path=model,
                original_system_prompt=original_system_prompt,
                original=original,
                start=selection_start,
                end=selection_end,
                selected_text=selected_text,
                request=request,
                before_context=before_context,
                after_context=after_context,
                max_attempts=2,
            )
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
        if revised is not None:
            try:
                current_editor_text = self.writer_output_text.get("1.0", "end-1c")
            except Exception:
                current_editor_text = self._writer_editor_prose()
            if current_editor_text != original:
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
                text="Focused change applied to the selected passage. All other draft text was preserved; review it again."
            )

    def _undo_focused_scene_change(self):
        history = getattr(self, "focused_revision_history", [])
        if not history or not self._has_pending_generated_scene():
            return
        previous = history.pop()
        self.generated_scene = previous
        self.writer_output_text.delete("1.0", "end")
        self.writer_output_text.insert("1.0", previous)
        self._update_writer_buttons()
        self.writer_status.configure(
            text="Undid the last focused change. The previous draft text has been restored."
        )

    def _reject_generated_scene(self):
        if self.__dict__.get("validator_review_in_progress", False):
            messagebox.showinfo(
                "Validator Review",
                "Finish or dismiss the current finding before rejecting the draft.",
                parent=self,
            )
            return
        if not self.generated_scene.strip():
            return

        if not self._ask_yes_no(
            "Reject Scene",
            "Discard this unaccepted draft or undo edits to the accepted scene? The manuscript file will not be deleted.",
        ):
            return

        accepted = str(self.__dict__.get("accepted_scene", "") or "").strip()
        self.generated_scene = accepted
        self.generated_scene_review_context = None
        self.last_validator_review_skipped = []
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
    def _accept_generated_scene(self):
        if self.__dict__.get("validator_review_in_progress", False):
            messagebox.showinfo(
                "Validator Review",
                "Finish reviewing the current findings before accepting this scene.",
                parent=self,
            )
            return
        block_reason = str(
            self.__dict__.get("writer_scene_accept_block_reason", "") or ""
        ).strip()
        if block_reason:
            self._show_copyable_error(
                "Scene Not Ready to Accept",
                block_reason,
                summary=(
                    "StoryBuilder has blocked acceptance because scene generation or its "
                    "completion/continuity check did not finish successfully. You can regenerate "
                    "the scene, but this version will not be added to the manuscript."
                ),
            )
            return
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
            messagebox.showwarning(
                "Writer",
                f"This temporary scene belongs to Chapter {chapter}, Scene {scene}, but the current state is "
                f"Chapter {current_key[0]}, Scene {current_key[1]}. It was not accepted under the wrong scene number. "
                "The text remains on screen for review. Return to the matching scene or discard it and generate again.",
            )
            return

        start_state = getattr(self, "generated_scene_start_state", None)
        if isinstance(start_state, dict) and start_state != state:
            messagebox.showwarning(
                "Writer",
                "The current story state changed after this prose was generated. The scene was not accepted against "
                "a different starting state. The temporary text remains on screen; restore the starting state or rebuild Writer direction and generate again.",
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
            self.generated_scene_review_context = None
            self.validator_review_state = None
            self.validator_review_in_progress = False
            self.last_validator_review_skipped = []
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
        focus_widget = self.__dict__.get("scene_continuity_focus_text")
        if focus_widget is not None:
            focus_widget.delete("1.0", "end")
        if hasattr(self, "scene_contract_direction_text"):
            self._set_generated_contract_text(self.scene_contract_direction_text, "")
        if hasattr(self, "scene_contract_end_text"):
            self._set_generated_contract_text(self.scene_contract_end_text, "")
        for widget in getattr(self, "scene_contract_texts", {}).values():
            self._set_generated_contract_text(widget, "")
        if hasattr(self, "scene_contract_attempts_var"):
            self.scene_contract_attempts_var.set("3")

    def _scene_contract_editor_has_content(self) -> bool:
        idea_widget = self.__dict__.get("scene_idea_text")
        if idea_widget is not None and idea_widget.get("1.0", "end-1c").strip():
            return True
        focus_widget = self.__dict__.get("scene_continuity_focus_text")
        if focus_widget is not None and focus_widget.get("1.0", "end-1c").strip():
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

        # The reload may replace an unsaved idea that was already reflected in
        # the visible Writer direction. Refresh that derived UI if its preview
        # exists, without rebuilding or replacing the saved scene contract.
        # Use __dict__ directly because Tkinter __getattr__ can recurse on
        # lightweight test instances that have no underlying Tcl interpreter.
        if self.__dict__.get("writer_scene_idea_text") is not None:
            self._refresh_writer_scene_guidance()

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

    def _scene_idea_suggestion_context(
        self,
        chapter: int,
        scene: int,
        previous_scene_prose: str = "",
        previous_chapter: int | None = None,
        previous_scene: int | None = None,
    ) -> dict:
        """Build a compact, read-only context for one editable scene suggestion."""
        if self.package is None:
            raise ValueError("Open a novel before requesting a scene suggestion.")

        state = self.package.current_state
        state_fields = (
            "chapter", "scene", "time_of_day", "time", "location", "scene_cast",
            "current_situation", "physical_state", "active_objectives",
            "active_clues", "new_clues", "unresolved_questions",
        )
        current_state = {
            key: state[key]
            for key in state_fields
            if key in state
        }
        recent_events = state.get("recent_events", [])
        if isinstance(recent_events, list):
            current_state["recent_events"] = recent_events[-8:]

        knowledge = state.get("character_knowledge", {})
        if isinstance(knowledge, dict):
            compact_knowledge = {}
            for name, facts in knowledge.items():
                if isinstance(facts, list):
                    items = facts[-6:]
                elif isinstance(facts, str) and facts.strip():
                    items = [facts]
                else:
                    items = []
                compact_knowledge[str(name)] = [
                    str(item).strip()[:320]
                    for item in items
                    if str(item).strip()
                ]
            if compact_knowledge:
                current_state["character_knowledge"] = compact_knowledge

        story_bible = self.package.story_bible if isinstance(self.package.story_bible, dict) else {}
        overview_keys = {
            "title", "novel_title", "premise", "genre", "setting", "tone",
            "story_arc", "central_conflict", "themes", "planned_ending",
            "ending", "synopsis",
        }
        overview = {}
        for key, value in story_bible.items():
            if str(key).casefold() in overview_keys and value not in (None, "", [], {}):
                if isinstance(value, str):
                    overview[key] = value.strip()[:1800]
                elif isinstance(value, (list, dict, int, float, bool)):
                    overview[key] = value

        character_cards = getattr(self.package, "characters", {})
        character_context = []
        if isinstance(character_cards, dict):
            for filename, card in sorted(character_cards.items()):
                if not isinstance(card, dict):
                    continue
                name = str(card.get("name", "") or Path(str(filename)).stem).strip()
                if not name:
                    continue
                item = {"name": name}
                for field in (
                    "age", "role", "occupation", "specialty", "expertise",
                    "personality", "description", "background",
                ):
                    value = card.get(field)
                    if isinstance(value, (str, int, float)) and str(value).strip():
                        item[field] = str(value).strip()[:320]
                character_context.append(item)

        plan = self.package.extra_json.get("writing_guidance.json", {})
        current_entry = (
            self._chapter_scene_guidance(plan, chapter, scene)
            if isinstance(plan, dict) else None
        )
        if not isinstance(current_entry, dict):
            current_entry = {}
        scene_guidance = {
            key: current_entry[key]
            for key in ("direction", "end_condition", "pacing", "cast", "continuity_focus")
            if current_entry.get(key) not in (None, "", [], {})
        }

        if previous_chapter is None:
            previous_chapter = chapter
        if previous_scene is None:
            previous_scene = max(1, scene - 1)
        previous_entry = (
            self._chapter_scene_guidance(plan, previous_chapter, previous_scene)
            if isinstance(plan, dict) else None
        )
        if not isinstance(previous_entry, dict):
            previous_entry = {}
        previous_guidance = {
            key: previous_entry[key]
            for key in ("scene_idea", "direction", "end_condition")
            if str(previous_entry.get(key, "") or "").strip()
        }

        plan_excerpt = ""
        if self.package.path is not None:
            plan_path = Path(self.package.path) / "STORY_PLAN.md"
            try:
                if plan_path.is_file():
                    plan_excerpt = plan_path.read_text(encoding="utf-8")[:6000]
            except OSError:
                plan_excerpt = ""

        editor_idea = ""
        if hasattr(self, "scene_idea_text"):
            editor_idea = self.scene_idea_text.get("1.0", "end-1c").strip()[:1800]

        return {
            "story_overview": overview,
            "current_state": current_state,
            "character_cards": character_context,
            "story_plan_excerpt": plan_excerpt,
            "current_scene_guidance_without_idea": scene_guidance,
            "previous_scene_guidance": previous_guidance,
            "previous_scene_ending_excerpt": str(previous_scene_prose or "").strip()[-3500:],
            "existing_scene_idea_for_alternative_only": editor_idea,
            "requested_next_scene": {"chapter": chapter, "scene": scene},
        }

    def _suggest_scene_idea(self, automatic: bool = False, previous_scene_prose: str = "",
                            previous_chapter: int | None = None, previous_scene: int | None = None):
        """Generate one suggestion into the editable field without saving it."""
        if self.package is None or not hasattr(self, "scene_idea_text"):
            if not automatic:
                messagebox.showinfo("Suggest Scene Idea", "Open a novel before requesting a suggestion.")
            return
        if self.__dict__.get("scene_idea_suggestion_in_progress", False):
            return
        if (
            self.__dict__.get("scene_planner_request_in_progress", False)
            or getattr(self, "writer_generation_in_progress", False)
            or getattr(self, "scene_contract_building", False)
            or getattr(self, "state_analysis_in_progress", False)
            or self.__dict__.get("change_request_in_progress", False)
        ):
            if not automatic:
                messagebox.showinfo(
                    "Suggest Scene Idea",
                    "Wait for the current StoryBuilder task to finish before requesting a suggestion.",
                )
            return

        state = self.package.current_state
        chapter = int(state.get("chapter", 1) or 1)
        scene = int(state.get("scene", 1) or 1)
        editor_key = getattr(self, "scene_contract_editor_key", None)
        if editor_key != (chapter, scene):
            # Scene completion can advance current_state before the editor is
            # refreshed. For automatic suggestions, reload and continue rather
            # than returning before the suggestion is generated.
            self._refresh_scene_contract_editor()
            editor_key = getattr(self, "scene_contract_editor_key", None)
            if not automatic:
                messagebox.showwarning(
                    "Suggest Scene Idea",
                    "I reloaded the current scene. Check its Scene Idea, then request the suggestion again.",
                )
                return
            if editor_key != (chapter, scene):
                self.scene_contract_status.configure(
                    text="The current scene editor could not be refreshed, so no automatic suggestion was generated."
                )
                return

        existing_text = self.scene_idea_text.get("1.0", "end-1c").strip()
        saved_entry = self._editable_scene_guidance_entry(chapter, scene, create=False) or {}
        resolved_idea, source, _error = self._resolve_scene_idea(chapter, scene, saved_entry)
        if automatic and (existing_text or resolved_idea):
            return
        if not automatic and existing_text and not self._ask_yes_no(
            "Replace Scene Idea with a Suggestion?",
            "StoryBuilder will generate one alternative and place it in the editable Scene Idea box. "
            "Your current text will not be saved or replaced unless the suggestion finishes successfully.\n\n"
            "Continue?",
        ):
            return

        model = getattr(self.writer_engine, "model_path", None)
        if model is None:
            try:
                model = self._selected_writer_model_for_analysis()
            except Exception:
                model = None
        if not model:
            if not automatic:
                messagebox.showwarning(
                    "Suggest Scene Idea",
                    "Select a local writing model before requesting a scene suggestion.",
                )
            else:
                self.scene_contract_status.configure(
                    text="No local writing model is selected, so no automatic scene suggestion was generated."
                )
            return

        try:
            context = self._scene_idea_suggestion_context(
                chapter, scene, previous_scene_prose, previous_chapter, previous_scene
            )
        except Exception as exc:
            if not automatic:
                self._show_copyable_error("Suggest Scene Idea", str(exc))
            else:
                self.scene_contract_status.configure(text=f"Could not prepare a scene suggestion: {exc}")
            return

        self.scene_idea_suggestion_in_progress = True
        if hasattr(self, "scene_contract_suggest_button"):
            self.scene_contract_suggest_button.configure(state="disabled")
        self.scene_contract_status.configure(
            text=f"Generating one editable suggestion for Chapter {chapter}, Scene {scene}..."
        )
        self._update_writer_buttons()
        engine = self.writer_engine

        def work():
            idea = None
            error = None
            was_running = False
            old_system_prompt = ""
            try:
                with engine.lock:
                    child = getattr(engine, "child", None)
                    try:
                        was_running = child is not None and child.isalive()
                    except Exception:
                        was_running = False
                    old_system_prompt = str(getattr(engine, "system_prompt", "") or "")
                    try:
                        idea = generate_scene_idea_suggestion(model, context, engine)
                    finally:
                        if automatic and idea is not None:
                            # The next writing action installs its own task prompt.
                            # Restoring the Writer prompt here would reload the same
                            # model only to replace that prompt again moments later.
                            pass
                        elif was_running and old_system_prompt:
                            engine.reset_context(model, old_system_prompt)
                        else:
                            engine.stop()
            except Exception as exc:
                error = str(exc)
            try:
                self.after(
                    0,
                    lambda: self._finish_scene_idea_suggestion(
                        chapter, scene, editor_key, idea, error, automatic
                    ),
                )
            except tk.TclError:
                pass

        threading.Thread(target=work, daemon=True).start()

    def _finish_scene_idea_suggestion(self, chapter, scene, editor_key, idea, error, automatic):
        self.scene_idea_suggestion_in_progress = False
        if hasattr(self, "scene_contract_suggest_button"):
            self.scene_contract_suggest_button.configure(state="normal")
        self._update_writer_buttons()
        if error:
            self.scene_contract_status.configure(
                text="Scene suggestion failed. Your existing Scene Idea was left unchanged."
            )
            if not automatic:
                self._show_copyable_error("Suggest Scene Idea", error)
            return
        if self.package is None:
            return
        state = self.package.current_state
        current_key = (
            int(state.get("chapter", 1) or 1),
            int(state.get("scene", 1) or 1),
        )
        if current_key != (chapter, scene) or getattr(self, "scene_contract_editor_key", None) != editor_key:
            self.scene_contract_status.configure(
                text="A suggestion finished for an earlier scene and was not inserted. Your current scene is unchanged."
            )
            return
        self.scene_idea_text.delete("1.0", "end")
        self.scene_idea_text.insert("1.0", idea)
        self.scene_idea_text.edit_modified(True)
        # Keep lightweight UI test fixtures compatible; the full application
        # always has these scene-contract preview widgets.
        if (
            self.__dict__.get("scene_contract_direction_text") is not None
            and self.__dict__.get("scene_contract_end_text") is not None
            and self.__dict__.get("scene_contract_texts") is not None
        ):
            self._preview_scene_idea_sections(idea)
        self._refresh_writer_scene_guidance()
        self.scene_contract_status.configure(
            text=(
                f"Suggested Scene Idea and draft plan for Chapter {chapter}, Scene {scene}. "
                "Beginning, Middle, End, Planned Beats, and supported Boundaries are shown above. "
                "Review/edit the idea, then use Save Idea to keep it or Prepare Scene to build and save its contract."
            )
        )

    def _maybe_suggest_next_scene_idea(self, previous_scene_prose: str = "",
                                      previous_chapter: int | None = None,
                                      previous_scene: int | None = None):
        """Auto-suggest only when the next scene has no saved or planned idea."""
        if self.package is None:
            return
        # Tkinter's __getattr__ may recurse when unit tests use a lightweight
        # app stub without a Tk interpreter. The real editable widget lives in
        # __dict__; if it is absent, there is no UI into which we can suggest.
        scene_idea_widget = self.__dict__.get("scene_idea_text")
        if scene_idea_widget is None:
            return
        chapter = int(self.package.current_state.get("chapter", 1) or 1)
        scene = int(self.package.current_state.get("scene", 1) or 1)
        entry = self._editable_scene_guidance_entry(chapter, scene, create=False) or {}
        resolved_idea, _source, _error = self._resolve_scene_idea(chapter, scene, entry)
        editor_text = scene_idea_widget.get("1.0", "end-1c").strip()
        if resolved_idea or editor_text:
            return
        self._suggest_scene_idea(
            automatic=True,
            previous_scene_prose=previous_scene_prose,
            previous_chapter=previous_chapter,
            previous_scene=previous_scene,
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

    def _preview_scene_idea_sections(self, scene_idea: str) -> dict:
        """Show the structured draft fields embedded in a suggested/saved Scene Idea."""
        sections = extract_authored_scene_sections(scene_idea)
        direction_parts = []
        beginning = str(sections.get("beginning", "") or "").strip()
        middle = str(sections.get("middle", "") or "").strip()
        if beginning:
            direction_parts.append("Beginning: " + beginning)
        if middle:
            direction_parts.append("Middle: " + middle)
        self._set_generated_contract_text(
            self.scene_contract_direction_text,
            "\n\n".join(direction_parts),
        )
        self._set_generated_contract_text(
            self.scene_contract_end_text,
            str(sections.get("end", "") or "").strip(),
        )
        for key, widget in self.scene_contract_texts.items():
            self._set_generated_contract_text(
                widget,
                "\n".join(self._contract_list(sections, key)),
            )
        return sections

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
        focus_widget = self.__dict__.get("scene_continuity_focus_text")
        if focus_widget is not None:
            focus_widget.delete("1.0", "end")
            continuity_focus = str(entry.get("continuity_focus", "") or "").strip()
            if continuity_focus:
                focus_widget.insert("1.0", continuity_focus)
        contract_error = None
        # A structured Scene Idea can supply a useful draft even before the
        # author builds/saves a generated contract from it.
        authored_sections = self._preview_scene_idea_sections(scene_idea)
        try:
            contract = SceneContract.from_guidance(entry, [])
        except (TypeError, ValueError) as exc:
            contract = {}
            contract_error = str(exc)

        saved_direction = str(entry.get("direction", "") or "").strip()
        if saved_direction:
            self._set_generated_contract_text(
                self.scene_contract_direction_text,
                saved_direction,
            )

        saved_end = str(contract.get("hard_stop") or entry.get("end_condition") or "").strip()
        if saved_end:
            self._set_generated_contract_text(self.scene_contract_end_text, saved_end)

        for key, widget in self.scene_contract_texts.items():
            values = self._contract_list(contract, key)
            if not values:
                values = self._contract_list(authored_sections, key)
            self._set_generated_contract_text(widget, "\n".join(values))

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

        editor_key = getattr(self, "scene_contract_editor_key", None)
        focus_widget = self.__dict__.get("scene_continuity_focus_text")
        if editor_key == (chapter, scene) and focus_widget is not None:
            continuity_focus = focus_widget.get("1.0", "end-1c").strip()
            if continuity_focus:
                entry["continuity_focus"] = continuity_focus
            else:
                entry.pop("continuity_focus", None)

        self.dirty = True
        if self.package.path is not None:
            self.package.save()
            self.dirty = False
        self._update_path_label()
        return entry

    def _apply_scene_contract_edits(self):
        """Save only the editable Scene Idea; all other contract fields are generated."""
        idea_widget = self.__dict__.get("scene_idea_text")
        if self.package is None or idea_widget is None:
            return

        scene_key = getattr(self, "scene_contract_editor_key", None)
        if isinstance(scene_key, tuple) and len(scene_key) == 2:
            chapter, scene = int(scene_key[0]), int(scene_key[1])
        else:
            chapter = int(self.package.current_state.get("chapter", 1) or 1)
            scene = int(self.package.current_state.get("scene", 1) or 1)

        idea = idea_widget.get("1.0", "end-1c").strip()
        self._save_scene_idea(chapter, scene, idea)
        # Lightweight test stubs may not have the full Writer UI attached.
        # Refresh the real UI when available without making the saved edit
        # depend on display widgets or a Tk interpreter being present.
        if self.__dict__.get("writer_scene_idea_text") is not None:
            self._refresh_writer_scene_guidance()
        if self.__dict__.get("writer_direction_text") is not None:
            self._build_scene_direction()
        self.scene_contract_status.configure(
            text=f"Saved Scene Idea for Chapter {chapter}, Scene {scene}.",
        )
    def _build_contract_from_scene_idea(self):
        if self.__dict__.get("scene_idea_suggestion_in_progress", False):
            messagebox.showwarning("Scene Contract", "Let the scene suggestion finish before generating a scene contract.")
            return
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
            if not self._confirm_discard_unaccepted_writer_text():
                return False

        self.generated_scene = prose
        self.accepted_scene = prose
        self.accepted_scene_context = (chapter, scene)
        self.generated_scene_context = (chapter, scene)
        self.generated_scene_start_state = restored["start_state"]
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

        scene_characters = self._state_analysis_character_candidates(
            story_text,
            completed_chapter,
            completed_scene,
        )
        model = self.writer_engine.model_path
        writer_system_prompt = str(getattr(self.writer_engine, "system_prompt", "") or "")
        author_guidance = self._author_writing_guidance()
        scene_idea_text = str(
            contract.get("author_idea", contract.get("scene_idea", contract.get("direction", "")))
            if isinstance(contract, dict) else contract or ""
        )
        state_review_context = {
            "model_path": model,
            "writer_system_prompt": writer_system_prompt,
            "current_state": current_state,
            "accepted_scene": story_text,
            "author_guidance": author_guidance,
            "scene_context": scene_idea_text,
            "contract": {"author_idea": scene_idea_text},
            "historical_context": "",
        }

        self.state_analysis_in_progress = True
        self.writer_reload_scene_button.configure(state="disabled")
        self.writer_analyze_button.configure(state="disabled")
        self.writer_apply_state_button.configure(state="disabled")
        self.writer_status.configure(text="Analyzing the accepted scene and checking proposed changes...")
        prompt_trace = None
        if self.__dict__.get("prompt_trace_enabled", False):
            try:
                prompt_trace = PromptTrace(
                    chapter=completed_chapter,
                    scene=completed_scene,
                    model_path=model,
                    current_state=current_state,
                    reference_files=[],
                    contract=contract,
                    scene_direction="",
                    author_guidance="",
                    system_prompt=MAIN_PLOT_SYSTEM_PROMPT,
                )
                prompt_trace.record_event(
                    "state_analysis_started",
                    accepted_scene=story_text,
                    scene_characters=scene_characters,
                )
                self.active_prompt_trace = prompt_trace
                self.writer_trace_status.configure(
                    text="Capturing State Analysis. This trace will replace the previous trace and sync to private GitHub."
                )
            except Exception as trace_exc:
                prompt_trace = None
                if self.__dict__.get("writer_trace_status") is not None:
                    self.writer_trace_status.configure(
                        text=f"State Analysis tracing could not start; analysis will continue without tracing: {trace_exc}"
                    )

        def work():
            patch = None
            error = None
            trace_result = None
            review_findings = []
            state_review_warning = None
            try:
                patch = StateManager.propose(
                    model,
                    current_state,
                    story_text,
                    scene_characters=scene_characters,
                    prompt_trace=prompt_trace,
                    main_plot_only=True,
                )
                review_findings, state_review_warning = review_state_proposal(
                    engine=self.writer_engine,
                    model_path=model,
                    original_system_prompt=writer_system_prompt,
                    current_state=current_state,
                    proposed_patch=patch or {},
                    accepted_scene=story_text,
                    author_guidance=author_guidance,
                    scene_idea=scene_idea_text,
                    prompt_trace=prompt_trace,
                )
            except Exception as exc:
                error = str(exc)
            finally:
                if prompt_trace is not None:
                    try:
                        prompt_trace.record_event(
                            "state_analysis_finished",
                            proposed_patch=patch,
                            state_review_findings=review_findings,
                            state_review_warning=state_review_warning,
                            error=error,
                        )
                    except Exception:
                        pass
                    try:
                        trace_path = prompt_trace.finish(
                            status="error" if error else "completed",
                            error=error,
                        )
                    except Exception as exc:
                        trace_path = None
                        trace_error = str(exc)
                    else:
                        trace_error = prompt_trace.save_error
                    upload_result = None
                    if trace_path is not None and not trace_error:
                        try:
                            upload_result = upload_prompt_trace(trace_path)
                        except Exception as exc:
                            upload_result = {"ok": False, "error": str(exc)}
                    trace_result = {
                        "path": str(trace_path) if trace_path is not None else None,
                        "error": trace_error,
                        "upload": upload_result,
                    }

            self.after(
                0,
                lambda: self._finish_state_analysis(
                    patch, error, trace_result, review_findings, state_review_context, state_review_warning
                ),
            )

        self.writer_thread = threading.Thread(
            target=work,
            daemon=True,
        )
        self.writer_thread.start()


    def _finish_state_analysis(self, patch, error, trace_result=None, review_findings=None, review_context=None, state_review_warning=None):
        self.state_analysis_in_progress = False
        if trace_result is not None:
            self.active_prompt_trace = None
            upload = trace_result.get("upload") or {}
            if trace_result.get("path") and upload.get("ok"):
                self.writer_trace_status.configure(
                    text=(
                        f"State Analysis trace synced to private GitHub: {upload.get('url')}. "
                        "The next capture overwrites it."
                    )
                )
            elif trace_result.get("path"):
                self.writer_trace_status.configure(
                    text=(
                        f"State Analysis trace saved locally at {trace_result['path']}; "
                        f"private GitHub sync failed: {upload.get('error') or 'sync did not run'}"
                    )
                )
            else:
                self.writer_trace_status.configure(
                    text="State Analysis trace could not be saved: "
                    + str(trace_result.get("error") or "unknown file error")
                )
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
        self.writer_state_preview.delete("1.0", "end")
        self.writer_state_preview.insert(
            "1.0",
            json.dumps(reconstructed_state, indent=2, ensure_ascii=False),
        )
        self._writer_state_reviewed_preview = json.dumps(
            reconstructed_state, sort_keys=True, ensure_ascii=False
        )
        if "writer_state_situation_quick" in self.__dict__:
            self._refresh_quick_state_editor(reconstructed_state)
        self.writer_status.configure(
            text=(
                "Main-plot summary ready. Nothing has been applied; "
                "review the plain-English change summary before choosing Apply State Update."
            )
        )
        self._update_writer_buttons()
        findings = [dict(item) for item in (review_findings or []) if isinstance(item, dict)]
        if findings:
            self._start_state_validator_review(findings, review_context or {})
        elif state_review_warning:
            self.writer_status.configure(
                text=(
                    "State proposal ready for plain-English review, but the validator reported: "
                    + str(state_review_warning).splitlines()[0]
                    + " Nothing has been saved."
                )
            )



    def _refresh_quick_state_editor(self, state):
        """Populate plain-text correction fields from a proposed ending state."""
        self._quick_edit_state = json.loads(json.dumps(state, ensure_ascii=False))
        self.writer_state_situation_quick.delete("1.0", "end")
        self.writer_state_situation_quick.insert(
            "1.0", str(state.get("current_situation", "") or "")
        )
        names = []
        for field in (
            "scene_cast", "character_knowledge", "active_objectives",
            "location", "physical_state",
        ):
            value = state.get(field, [])
            candidates = (
                value.keys() if isinstance(value, dict)
                else value if isinstance(value, list)
                else []
            )
            for raw_name in candidates:
                name = str(raw_name).strip()
                if field == "location" and name.casefold() == "primary":
                    continue
                if name and name.casefold() not in {item.casefold() for item in names}:
                    names.append(name)
        self.writer_state_character_selector.configure(values=names)
        selected = self.writer_state_character_selector.get().strip()
        if selected not in names:
            selected = names[0] if names else ""
        self.writer_state_character_selector.set(selected)
        self._load_quick_state_character_fields()

    def _save_quick_state_character_fields(self, character_name=None):
        """Store visible text fields for the character whose data is displayed."""
        state = getattr(self, "_quick_edit_state", None)
        if not isinstance(state, dict):
            return
        name = str(
            character_name
            if character_name is not None
            else self.writer_state_character_selector.get()
        ).strip()
        if not name:
            return

        location_widget = self.__dict__.get("writer_state_location_quick")
        location_text = (
            location_widget.get("1.0", "end").strip()
            if location_widget is not None else ""
        )
        if location_text:
            locations = state.setdefault("location", {})
            if not isinstance(locations, dict):
                locations = {}
                state["location"] = locations
            locations[name] = location_text

            physical_states = state.setdefault("physical_state", {})
            if not isinstance(physical_states, dict):
                physical_states = {}
                state["physical_state"] = physical_states
            character_state = physical_states.setdefault(name, {})
            if not isinstance(character_state, dict):
                character_state = {}
                physical_states[name] = character_state
            character_state["location"] = location_text

        physical_states = state.setdefault("physical_state", {})
        if not isinstance(physical_states, dict):
            physical_states = {}
            state["physical_state"] = physical_states
        character_state = physical_states.setdefault(name, {})
        if not isinstance(character_state, dict):
            character_state = {}
            physical_states[name] = character_state

        for widget_name, state_key in (
            ("writer_state_position_quick", "position"),
            ("writer_state_posture_quick", "posture"),
            ("writer_state_movement_quick", "movement"),
        ):
            widget = self.__dict__.get(widget_name)
            if widget is None:
                continue
            value = widget.get("1.0", "end").strip()
            # Blank location/physical fields do not erase existing state.
            # Use a clear value such as "stationary" when that is the intended state.
            if value:
                character_state[state_key] = value

        knowledge_text = self.writer_state_knowledge_quick.get("1.0", "end").strip()
        facts = [line.strip() for line in knowledge_text.splitlines() if line.strip()]
        knowledge = state.setdefault("character_knowledge", {})
        if not isinstance(knowledge, dict):
            knowledge = {}
            state["character_knowledge"] = knowledge
        if facts:
            knowledge[name] = facts
        else:
            knowledge.pop(name, None)

        objective_text = self.writer_state_objective_quick.get("1.0", "end").strip()
        objectives = state.setdefault("active_objectives", {})
        if not isinstance(objectives, dict):
            objectives = {}
            state["active_objectives"] = objectives
        if objective_text:
            objectives[name] = objective_text
        else:
            objectives.pop(name, None)

    def _load_quick_state_character_fields(self):
        """Show one character's own location, physical state, knowledge, and objective."""
        state = getattr(self, "_quick_edit_state", {})
        name = self.writer_state_character_selector.get().strip()

        locations = state.get("location", {})
        location_value = locations.get(name, "") if isinstance(locations, dict) else ""
        physical_states = state.get("physical_state", {})
        character_state = (
            physical_states.get(name, {})
            if isinstance(physical_states, dict) else {}
        )
        if not isinstance(character_state, dict):
            character_state = {}
        if not location_value:
            location_value = character_state.get("location", "")

        for widget_name, value in (
            ("writer_state_location_quick", location_value),
            ("writer_state_position_quick", character_state.get("position", "")),
            ("writer_state_posture_quick", character_state.get("posture", "")),
            ("writer_state_movement_quick", character_state.get("movement", "")),
        ):
            widget = self.__dict__.get(widget_name)
            if widget is None:
                continue
            widget.delete("1.0", "end")
            widget.insert("1.0", str(value or ""))

        knowledge = state.get("character_knowledge", {})
        if not isinstance(knowledge, dict):
            knowledge = {}
        facts = knowledge.get(name, [])
        if isinstance(facts, str):
            facts = [facts]
        if not isinstance(facts, list):
            facts = []
        objectives = state.get("active_objectives", {})
        objective = objectives.get(name, "") if isinstance(objectives, dict) else ""
        self.writer_state_knowledge_quick.delete("1.0", "end")
        self.writer_state_knowledge_quick.insert(
            "1.0", "\n".join(str(item) for item in facts if str(item).strip())
        )
        self.writer_state_objective_quick.delete("1.0", "end")
        self.writer_state_objective_quick.insert("1.0", str(objective or ""))
        # The combobox selection changes before its selection event fires.
        # Track whose data is actually displayed so edits are saved to that
        # character, not mistakenly copied onto the newly selected character.
        self._quick_edit_loaded_character = name

    def _on_quick_state_character_selected(self, _event=None):
        previous_name = getattr(self, "_quick_edit_loaded_character", "")
        if previous_name:
            self._save_quick_state_character_fields(previous_name)
        self._load_quick_state_character_fields()

    def _apply_quick_state_edits_to_preview(self):
        """Fold simple text corrections into the existing proposed-state preview."""
        if self.package is None or not isinstance(self.pending_state_patch, dict):
            self.writer_status.configure(
                text="Analyze the accepted scene before preparing quick state edits."
            )
            return
        try:
            preview_text = self.writer_state_preview.get("1.0", "end").strip()
            state = json.loads(preview_text)
            if not isinstance(state, dict):
                raise ValueError("The ending-state preview must be a JSON object.")
            self._save_quick_state_character_fields()
            quick_state = getattr(self, "_quick_edit_state", {})
            situation = self.writer_state_situation_quick.get("1.0", "end").strip()
            if not situation:
                raise ValueError("The ending situation cannot be blank.")
            state["current_situation"] = situation
            for field in ("character_knowledge", "active_objectives"):
                proposed = quick_state.get(field, {})
                if isinstance(proposed, dict) and proposed:
                    state[field] = proposed
                else:
                    state.pop(field, None)
            for field in ("location", "physical_state"):
                proposed = quick_state.get(field)
                if isinstance(proposed, dict):
                    state[field] = proposed
            StateManager.validate_patch(
                self.package.current_state,
                reviewed_state_preview_to_patch(
                    StateManager.merge_patch(
                        self.package.current_state, self.pending_state_patch
                    ),
                    state,
                ),
            )
        except (TypeError, ValueError) as exc:
            self._show_copyable_error(
                "Quick State Edits",
                "The plain-text corrections were not copied into the proposal. Nothing was saved.\n\n"
                + str(exc),
            )
            return

        self.writer_state_preview.delete("1.0", "end")
        self.writer_state_preview.insert(
            "1.0", json.dumps(state, indent=2, ensure_ascii=False)
        )
        self._writer_state_reviewed_preview = json.dumps(
            state, sort_keys=True, ensure_ascii=False
        )
        self.writer_state_diff_preview.configure(state="normal")
        self.writer_state_diff_preview.delete("1.0", "end")
        self.writer_state_diff_preview.insert(
            "1.0", build_state_change_summary(self.package.current_state, state)
        )
        self.writer_state_diff_preview.configure(state="disabled")
        self.writer_status.configure(
            text=(
                "Your corrections are included in the proposed changes. Review the plain-English summary above, then click "
                "Apply State Update to save them and prepare the next scene."
            )
        )
        self._update_writer_buttons()

    def _refresh_state_review_from_json(self):
        """Validate the internal state buffer and refresh the plain-English change summary."""
        if self.package is None or not isinstance(self.pending_state_patch, dict):
            self.writer_status.configure(
                text="Analyze the accepted scene before refreshing the state review."
            )
            return

        try:
            preview_text = self.writer_state_preview.get("1.0", "end").strip()
            if not preview_text:
                raise ValueError("The ending-state preview is empty.")
            candidate_state = json.loads(preview_text)
            if not isinstance(candidate_state, dict):
                raise ValueError("The ending-state preview must be a JSON object.")
            expected_state = StateManager.merge_patch(
                self.package.current_state,
                self.pending_state_patch,
            )
            preview_edits = reviewed_state_preview_to_patch(
                expected_state,
                candidate_state,
            )
            patch_to_review = combine_state_patches(
                self.pending_state_patch,
                preview_edits,
            )
            StateManager.validate_patch(
                self.package.current_state,
                patch_to_review,
            )
        except (TypeError, ValueError) as exc:
            self._show_copyable_error(
                "Refresh State Review",
                "The review was not refreshed because the preview is invalid. Nothing was saved.\n\n"
                + str(exc),
            )
            return

        self.writer_state_diff_preview.configure(state="normal")
        self.writer_state_diff_preview.delete("1.0", "end")
        self.writer_state_diff_preview.insert(
            "1.0",
            build_state_change_summary(self.package.current_state, candidate_state),
        )
        self.writer_state_diff_preview.configure(state="disabled")
        self._writer_state_reviewed_preview = json.dumps(
            candidate_state, sort_keys=True, ensure_ascii=False
        )
        if "writer_state_situation_quick" in self.__dict__:
            self._refresh_quick_state_editor(candidate_state)
        self.writer_status.configure(
            text=(
                "The proposed changes have been refreshed. Nothing has been applied or saved."
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
            if not isinstance(reviewed_preview, dict):
                raise ValueError("The ending-state preview must be a JSON object.")
            last_reviewed = self.__dict__.get("_writer_state_reviewed_preview")
            if last_reviewed is not None:
                current_serialized = json.dumps(
                    reviewed_preview, sort_keys=True, ensure_ascii=False
                )
                if current_serialized != last_reviewed:
                    messagebox.showwarning(
                        "Review Needs Refresh",
                        "The proposed changes changed after the review was prepared. Nothing has been applied. "
                        "Analyze the accepted scene again to rebuild the proposed changes before applying.",
                    )
                    self.writer_status.configure(
                        text="Analyze the accepted scene again before applying this state update."
                    )
                    self._update_writer_buttons()
                    return
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
                "Correct the proposed value using the plain-English fields, then try again. You do not need to edit JSON.\n\n" + str(exc),
            )
            self._update_writer_buttons()
            return

        try:
            completed_chapter = int(self.package.current_state.get("chapter", 1) or 1)
            completed_scene = int(self.package.current_state.get("scene", 1) or 1)
            completed_prose = str(
                getattr(self, "accepted_scene", "") or self._writer_editor_prose() or ""
            ).strip()

            if not self._confirm_discard_unaccepted_writer_text():
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
            self._quick_edit_state = None
            self._writer_state_reviewed_preview = None
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
            if not self.package.current_state.get("chapter_completed"):
                self._maybe_suggest_next_scene_idea(
                    previous_scene_prose=completed_prose,
                    previous_chapter=completed_chapter,
                    previous_scene=completed_scene,
                )
            # This optional model-driven craft review is disabled by default.
            # Applying a state update must never make the author wait on notebook
            # housekeeping. Enable explicitly with STORYBUILDER_AUTO_WRITER_NOTES=1.
            if completed_prose and writer_notes_auto_update_enabled():
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
            note_runtime_env = {
                key: os.environ.get(key)
                for key in ("STORY_WRITER_CONTEXT", "STORY_WRITER_MAX_TOKENS")
            }
            try:
                with engine.lock:
                    was_running = engine.child is not None and engine.child.isalive()
                    old_system_prompt = str(engine.system_prompt or "")
                    try:
                        # This is a tiny JSON-only housekeeping task, not a
                        # scene-writing pass. Keep its context, output budget,
                        # and runtime duration tightly bounded.
                        os.environ["STORY_WRITER_CONTEXT"] = str(WRITER_NOTES_CONTEXT_TOKENS)
                        os.environ["STORY_WRITER_MAX_TOKENS"] = str(WRITER_NOTES_MAX_TOKENS)
                        engine.reset_context(model, WRITER_NOTES_SYSTEM_PROMPT)
                        response = engine.generate(
                            review_prompt,
                            timeout=WRITER_NOTES_TIMEOUT_SECONDS,
                        )
                        suggestions = parse_writer_notes_response(response)
                        updated_notes, added_count = merge_writer_notes(
                            notes,
                            suggestions,
                            available_labels,
                            scene_label,
                        )
                        save_writer_notes(package_path, updated_notes)
                    finally:
                        # Restore launch settings before restoring the normal
                        # Writer session, so its original context/output limits
                        # are used rather than the tiny notebook-task limits.
                        for key, value in note_runtime_env.items():
                            if value is None:
                                os.environ.pop(key, None)
                            else:
                                os.environ[key] = value
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
            model = self._selected_writer_model_for_analysis()

            self.manuscript_analyze_button.configure(state="disabled")
            self.manuscript_restore_button.configure(state="disabled")
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

        if not self._confirm_discard_unaccepted_writer_text():
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
        self._add_context_menu(report_text)

        status = ttk.Label(outer, text="The accepted manuscript remains unchanged.")
        status.pack(anchor="w", pady=(6, 0))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(8, 0))
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
                    "Review the full error details below. Use Ctrl+A to select all text and Ctrl+C to copy it."
                ),
            )
    def _close_and_sync_app(self):
        """Save/sync the open novel first, sync StoryBuilder, then close safely."""
        if self.__dict__.get("writer_notes_update_in_progress", False):
            messagebox.showwarning(
                "Close & Sync",
                "StoryBuilder is updating temporary writing notes. The app will remain open until that update finishes.",
            )
            return
        if self._closing:
            return
        self._closing = True

        novel_sync_result = ""
        try:
            # Unaccepted Writer text is never added to the manuscript implicitly.
            # The author must explicitly approve discarding it before shutdown.
            if not self._confirm_discard_unaccepted_writer_text():
                self._closing = False
                return

            if self.package is not None:
                if self.package.path is None:
                    if not self._ask_yes_no(
                        "Novel Not Saved or Synced",
                        "This novel has no saved package folder, so it cannot be synchronized to GitHub. "
                        "Close StoryBuilder anyway and leave this unsaved novel behind?",
                    ):
                        self._closing = False
                        return
                    novel_sync_result = (
                        "The current novel was not saved or synchronized because it has no saved package folder."
                    )
                else:
                    if not self._apply_all_edits():
                        self._closing = False
                        return
                    # Save the current accepted manuscript/state and other package data
                    # before touching Git. Never put generated, unaccepted Writer text
                    # into the manuscript as part of this shutdown.
                    self.package.save()
                    self.dirty = False
                    self._update_path_label()

                    if novel_repo_root(self.package.path) is None:
                        if not self._ask_yes_no(
                            "Novel Not Synchronized",
                            "The novel was saved locally, but this folder is not connected to a Git repository. "
                            "It will not be shared with your other computer. Close anyway?",
                        ):
                            self._closing = False
                            return
                        novel_sync_result = (
                            "The novel was saved locally but not synchronized: this folder is not a Git repository."
                        )
                    else:
                        try:
                            novel_sync_result = sync_novel_repository(self.package.path)
                            self._chat("Builder", novel_sync_result)
                        except (NovelSyncError, OSError, subprocess.SubprocessError) as exc:
                            self._show_copyable_error(
                                "Novel Sync Failed",
                                "The novel was saved locally, but GitHub synchronization did not complete. "
                                "StoryBuilder will remain open, and no conflicting remote changes were intentionally overwritten. "
                                "Resolve the sync issue before switching computers.\n\n"
                                + str(exc),
                                summary=(
                                    "Novel saved locally; remote sync failed. The app remains open so you can inspect the error. "
                                    "Do not keep retrying if Git reports a conflict."
                                ),
                            )
                            self._closing = False
                            return

            # App-code sync comes after novel sync. If this fails, the novel's successful
            # sync is still reported, and the UI remains open to handle the app-code error.
            try:
                sync_storybuilder_repository(Path(__file__).resolve().parent)
            except (StoryBuilderSyncError, OSError, subprocess.SubprocessError) as exc:
                self._show_copyable_error(
                    "StoryBuilder Sync Failed",
                    "The novel sync result is shown below. StoryBuilder application sync failed, so the app remains open.\n\n"
                    + (novel_sync_result + "\n\n" if novel_sync_result else "")
                    + str(exc),
                    summary=(
                        "The novel and app use separate Git repositories. Check the result above: the novel may already be synchronized, "
                        "but StoryBuilder code sync did not finish."
                    ),
                )
                self._closing = False
                return

            if novel_sync_result:
                messagebox.showinfo(
                    "Close & Sync",
                    novel_sync_result + "\n\nStoryBuilder application synchronized successfully. Closing now.",
                    parent=self,
                )

            try:
                self.writer_engine.stop()
            except Exception:
                pass

            previous_handler = self.__dict__.get("_previous_sigint_handler")
            if previous_handler is not None:
                try:
                    signal.signal(signal.SIGINT, previous_handler)
                except (ValueError, tk.TclError):
                    pass
            self.destroy()
        except Exception as exc:
            self._show_copyable_error(
                "Close & Sync",
                "StoryBuilder could not complete its safe shutdown. The app remains open. "
                "Review the error and verify novel synchronization before switching computers.\n\n"
                + str(exc),
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
        if not self._confirm_discard_unaccepted_writer_text():
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
        if not self._confirm_discard_unaccepted_writer_text():
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

    def _confirm_discard_unaccepted_writer_text(self) -> bool:
        """Confirm that temporary, unaccepted Writer text may be discarded."""
        if self.package is None:
            return True
        if (
            getattr(self, "writer_generation_in_progress", False)
            or self.__dict__.get("focused_revision_in_progress", False)
            or self.__dict__.get("validator_review_in_progress", False)
        ):
            messagebox.showwarning(
                "Writer",
                "A Writer or validator-review task is still running. Finish the review before changing scenes or closing StoryBuilder.",
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
            "Unaccepted Writer Text",
            (
                f"There is unaccepted Writer text for Chapter {chapter}, Scene {scene}.\n\n"
                "Choose Yes to discard this temporary text and continue.\n"
                "Choose No or Cancel to stay in StoryBuilder and keep working.\n\n"
                "Unaccepted text is not saved as a separate draft file."
            ),
            parent=self,
        )
        if choice is not True:
            return False

        self.generated_scene = accepted
        self.writer_scene_accept_block_reason = ""
        self.focused_revision_history = []
        writer_output_text = self.__dict__.get("writer_output_text")
        if writer_output_text is not None:
            writer_output_text.delete("1.0", "end")
            if accepted:
                writer_output_text.insert("1.0", accepted)
        if not accepted:
            self.generated_scene_context = None
            self.generated_scene_start_state = None
        revision_entry = self.__dict__.get("writer_revision_request_entry")
        if revision_entry is not None:
            revision_entry.delete("1.0", "end")
        writer_state_preview = self.__dict__.get("writer_state_preview")
        if writer_state_preview is not None:
            writer_state_preview.delete("1.0", "end")
        diff_preview = self.__dict__.get("writer_state_diff_preview")
        if diff_preview is not None:
            diff_preview.configure(state="normal")
            diff_preview.delete("1.0", "end")
            diff_preview.configure(state="disabled")
        self._update_writer_buttons()
        self.writer_status.configure(
            text="Unaccepted scene text discarded. The accepted manuscript was not changed."
        )
        return True

    def _prepare_for_scene_change(self, target_chapter: int, target_scene: int) -> bool:
        """Prevent scene switches from silently discarding unaccepted Writer text."""
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
            if prose and prose != accepted and not self._confirm_discard_unaccepted_writer_text():
                return False
            messagebox.showwarning(
                "Finish Current Scene",
                "This scene has been accepted, but its state update has not been applied yet. "
                "Analyze the accepted scene and apply its state update before moving to another scene.",
            )
            return False

        return self._confirm_discard_unaccepted_writer_text()

    def _clear_writer_scene_workspace(self, status: str | None = None) -> None:
        """Clear scene-specific Writer memory after its text is accepted or discarded."""
        self.generated_scene = ""
        self.accepted_scene = ""
        self.accepted_scene_context = None
        self.focused_revision_history = []
        self.generated_scene_context = None
        self.generated_scene_start_state = None
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

        if not self._confirm_discard_unaccepted_writer_text():
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
                "Select the relevant person under Supporting People first.",
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
            # a more specific shared-home label.
            if "home" in primary and "home" in text:
                return True
            if "house" in primary and ("house" in text or "home" in text):
                return True
            if "garage" in primary and "garage" in text:
                return True

            # Otherwise require a meaningful shared place token. Remove
            # actual character-name tokens dynamically, rather than relying on
            # names from one particular novel.
            character_names = [
                str(name)
                for name in location
                if name != "primary"
            ]
            raw_scene_cast = state.get("scene_cast", [])
            if isinstance(raw_scene_cast, list):
                character_names.extend(str(name) for name in raw_scene_cast)
            character_name_tokens = {
                token
                for name in character_names
                for token in re.findall(r"[a-z0-9]+", name.casefold())
            }
            primary_words = {
                word for word in re.findall(r"[a-z0-9]+", primary)
                if len(word) >= 4 and word not in character_name_tokens
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
                text=f"Scene {next_scene} is ready. Use Prepare Scene when its idea is ready.",
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
                    "Use Prepare Scene when its idea is ready."
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
                if prose and prose != accepted and not self._confirm_discard_unaccepted_writer_text():
                    return False
                messagebox.showwarning(
                    "Current Situation",
                    "This scene has been accepted but its state update has not been applied. Finish that step before changing its starting situation.",
                )
                return False

            if not self._confirm_discard_unaccepted_writer_text():
                return False
            if self.generated_scene.strip() or self.accepted_scene.strip():
                self._clear_writer_scene_workspace(
                    "Starting situation changed. Unfinished Writer text was cleared."
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
            if isinstance(child, (tk.Entry, tk.Spinbox, ttk.Entry, ttk.Combobox, ttk.Spinbox)):
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
        widget.bind("<Control-C>", lambda _event: (copy(), "break")[1], add="+")
        widget.bind("<Control-v>", lambda _event: (paste(), "break")[1], add="+")
        widget.bind("<Control-a>", lambda _event: (select_all(), "break")[1], add="+")
        widget.bind("<Control-A>", lambda _event: (select_all(), "break")[1], add="+")

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
                status.configure(text="Text copied. Paste it wherever you need it.")
            except tk.TclError as exc:
                status.configure(text=f"Clipboard copy failed: {exc}")

        # Keep both actions above the expandable text area so they stay visible
        # even on shorter screens or when the diagnostic contains a long traceback.
        action_row = ttk.Frame(outer)
        action_row.pack(fill="x", pady=(0, 8))
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

        status = ttk.Label(outer, text="Use Ctrl+A to select all text, then Ctrl+C to copy it.")
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
                # Clipboard ownership must outlive this transient dialog so
                # the author can answer the prompt, close it, and paste elsewhere.
                self.clipboard_clear()
                self.clipboard_append(selected)
                self.update_idletasks()
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
