from __future__ import annotations

import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText

from builder.appearance import apply_application_appearance
from builder.writer_engine import GenerationInterrupted, WriterEngine
from builder.workspace import MODELS_DIR, NOVEL_ROOT
from builder.continuity_context import (
    build_location_allowlist_prompt,
    select_relevant_locations,
)
from builder.character_context import build_character_card_context_prompt
from builder.story_bible_reader import load_story_bible
from builder.creative_direction import build_creative_direction_prompt
from builder.story_craft import build_story_craft_prompt
from builder.canon_rules import build_canon_rules_prompt
from builder.story_pacing import build_story_opening_pacing_prompt
from builder.story_timeline import (
    build_current_story_context_prompt,
    build_story_timeline_prompt,
)
from builder.scene_preparation import (
    build_scene_preparation_prompt,
    next_scene_coordinates,
    scene_number_from_label,
)
from builder.odt_document import markdown_to_rich_text, read_document, save_document
from builder.manuscript_assembly import (
    assemble_chapter as assemble_chapter_document,
    assemble_finished_novel as assemble_finished_novel_document,
)
from builder.novel_browser import list_novel_packages, list_scene_chapters, list_scene_files
from builder.prose_health import analyze_draft, format_draft_health_report
from builder.novel_git_sync import (
    NovelGitSyncError,
    inspect_novel_repository,
    sync_novel_repository,
)
from builder.prompt_trace import PromptTrace, load_prompt_trace_enabled
from builder.prompt_trace_sync import upload_prompt_trace
from builder.scene_state_update import (
    advance_saved_scene_markers,
    build_saved_scene_state_prompt,
    load_current_state,
    merge_saved_scene_state,
    parse_saved_scene_state_patch,
    write_current_state,
)
from builder.writer_continuity import build_previous_scene_context_prompt


CONTINUE_PROMPT = (
    "Continue the current passage from where it ended. "
    "Write only new material, without repeating the text already written."
)
CONTINUE_CONTEXT_CHARS = 2000


def select_all_text(event):
    """Select all text in a Tk Text-compatible widget for Ctrl+A."""
    widget = event.widget
    widget.tag_add("sel", "1.0", "end-1c")
    widget.mark_set("insert", "1.0")
    widget.see("insert")
    return "break"


def bind_ctrl_a_select_all(widget) -> None:
    """Make Ctrl+A select all text in a Writer text widget."""
    widget.bind("<Control-a>", select_all_text)
    widget.bind("<Control-A>", select_all_text)


def show_copyable_dialog(
    parent: tk.Misc,
    title: str,
    message: str,
    buttons: tuple[str, ...] = ("OK",),
    default_button: str | None = None,
) -> str:
    """Show a screen-sized, scrollable, selectable message and return the button chosen."""
    if not buttons:
        raise ValueError("At least one dialog button is required.")

    if default_button not in buttons:
        if "Cancel" in buttons:
            default_button = "Cancel"
        elif "No" in buttons:
            default_button = "No"
        else:
            default_button = buttons[0]

    message = str(message)
    line_count = message.count("\n") + 1
    long_message = len(message) > 350 or line_count > 7
    desired_width = 860 if long_message else 560
    desired_height = 640 if long_message else 250

    try:
        parent.update_idletasks()
        screen_width = parent.winfo_screenwidth()
        screen_height = parent.winfo_screenheight()
    except tk.TclError:
        screen_width, screen_height = 1024, 768

    width = max(320, min(desired_width, screen_width - 60))
    height = max(220, min(desired_height, screen_height - 80))
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)

    window = tk.Toplevel(parent)
    window.title(title)
    window.transient(parent)
    window.resizable(True, True)
    window.geometry(f"{width}x{height}+{x}+{y}")

    outer = ttk.Frame(window, padding=12)
    outer.pack(fill="both", expand=True)
    ttk.Label(
        outer,
        text="Message text: select it and press Ctrl+A, then Ctrl+C to copy.",
    ).pack(anchor="w", pady=(0, 6))

    text_box = ScrolledText(
        outer,
        wrap="word",
        undo=False,
        font=("TkDefaultFont", 10),
        height=8,
        width=60,
    )
    text_box.pack(fill="both", expand=True)
    text_box.insert("1.0", message)
    # Keep the widget enabled so the user can mouse-select and copy text.
    # Block editing keystrokes and paste/cut operations instead of disabling it,
    # because a disabled Text widget may not accept focus for keyboard shortcuts.
    text_box.configure(state="normal")
    bind_ctrl_a_select_all(text_box)

    def protect_read_only_text(event):
        key = event.keysym
        control_down = bool(event.state & 0x4)
        if control_down and key.lower() in {"v", "x"}:
            return "break"
        if key in {
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

    def copy_selection(_event=None):
        try:
            selected = text_box.get("sel.first", "sel.last")
        except tk.TclError:
            return "break"
        try:
            # Keep the clipboard owner on the main application window so the
            # copied text remains available after this popup closes.
            parent.clipboard_clear()
            parent.clipboard_append(selected)
            parent.update_idletasks()
        except tk.TclError:
            pass
        return "break"

    text_box.bind("<Control-c>", copy_selection)
    text_box.bind("<Control-C>", copy_selection)

    result = {"button": default_button}

    def finish(button: str) -> None:
        result["button"] = button
        try:
            window.grab_release()
        except tk.TclError:
            pass
        window.destroy()

    button_row = ttk.Frame(outer)
    button_row.pack(fill="x", pady=(10, 0))
    for button_label in buttons:
        ttk.Button(
            button_row,
            text=button_label,
            command=lambda label=button_label: finish(label),
        ).pack(side="right", padx=(6, 0))

    window.bind("<Return>", lambda _event: finish(default_button))
    window.bind("<Escape>", lambda _event: finish("Cancel" if "Cancel" in buttons else ("No" if "No" in buttons else buttons[0])))
    window.protocol(
        "WM_DELETE_WINDOW",
        lambda: finish("Cancel" if "Cancel" in buttons else ("No" if "No" in buttons else buttons[0])),
    )
    try:
        window.grab_set()
    except tk.TclError:
        pass
    text_box.focus_set()
    parent.wait_window(window)
    return result["button"]


def build_continue_prompt(existing_text: str) -> str:
    """Include the visible passage ending so Continue respects editor changes."""
    passage_ending = existing_text[-CONTINUE_CONTEXT_CHARS:]
    return f"{CONTINUE_PROMPT}\n\nPassage ending for context:\n{passage_ending}"


def build_rewrite_scene_prompt(scene_prompt: str, author_direction: str = "") -> str:
    """Combine the unchanged scene prompt with optional extra guidance for a rewrite."""
    original = str(scene_prompt or "").strip()
    direction = str(author_direction or "").strip()
    if not direction:
        return original
    return (
        f"{original}\n\n"
        "ADDITIONAL AUTHOR'S DIRECTION FOR THIS REWRITE\n"
        f"{direction}\n\n"
        "Treat this as a priority clarification for the same scene, not a request to "
        "prepare or advance to another scene. Preserve the existing scene's location, "
        "characters, intended events, and natural endpoint except where this additional "
        "direction specifically refines them. Write a complete replacement scene as "
        "natural manuscript prose only."
    )


def build_location_context_prompt(
    prompt: str,
    locations: dict,
    supporting_text: str = "",
) -> tuple[str, list[str]]:
    """Add the complete saved-location allowlist plus details for named locations."""
    query = "\n".join(
        part for part in (str(prompt or ""), str(supporting_text or "")) if part
    )
    selected = select_relevant_locations(locations, "", query)
    allowlist, _available_names = build_location_allowlist_prompt(locations)
    context_parts = [allowlist]

    if selected:
        lines = [
            "SAVED LOCATION REFERENCES FOR THIS SCENE",
            "Use these details only for the places named below. Keep each place's details separate.",
        ]
        for name, details in selected.items():
            lines.append(f"\n[{name}]")
            if isinstance(details, str):
                if details.strip():
                    lines.append(f"Description: {details.strip()}")
                continue

            for key, value in details.items():
                if value is None or value == "":
                    continue
                label = str(key).replace("_", " ").strip().capitalize()
                if isinstance(value, (dict, list)):
                    rendered = json.dumps(value, ensure_ascii=False, indent=2)
                    lines.append(f"{label}:\n" + "\n".join(
                        f"  {line}" for line in rendered.splitlines()
                    ))
                else:
                    lines.append(f"{label}: {value}")
        context_parts.append("\n".join(lines))

    context = "\n\n".join(part for part in context_parts if part)
    base_prompt = str(prompt or "").rstrip()
    enriched = f"{base_prompt}\n\n{context}" if base_prompt else context
    return enriched, list(selected)


def build_revision_prompt(selected_text: str, instruction: str) -> str:
    """Ask the model to revise only the selected passage, following the author's instruction."""
    return (
        "Revise only the selected passage according to the author's instruction. "
        "Return only the revised passage, with no commentary, label, or explanation. "
        "Do not continue beyond the passage. Preserve its intended meaning and events "
        "unless the instruction explicitly asks for a change.\n\n"
        f"Author's instruction:\n{instruction.strip()}\n\n"
        f"Selected passage to revise:\n{selected_text}"
    )


def continuation_prefix(text: str) -> str:
    """Return the current passage plus one paragraph boundary for appended text."""
    if not text:
        return ""
    if text.endswith("\n\n"):
        return text
    if text.endswith("\n"):
        return text + "\n"
    return text + "\n\n"


def load_model_for_writing(engine: WriterEngine, model_path: str | Path) -> None:
    """Load the selected local model without adding a writing system prompt."""
    engine.start(model_path, system_prompt="")


def write_from_prompt(engine: WriterEngine, prompt: str, on_delta=None) -> str:
    """Send the author's prompt directly to the model, optionally streaming output."""
    return engine.generate(prompt, on_delta=on_delta)


def read_text_document(path: str | Path) -> str:
    """Read a UTF-8 text document without altering its contents."""
    return Path(path).expanduser().read_text(encoding="utf-8")


def save_text_document(path: str | Path, text: str) -> Path:
    """Save text exactly as provided and return its resolved file path."""
    target = Path(path).expanduser().resolve()
    target.write_text(str(text), encoding="utf-8")
    return target


def text_widget_to_markdown(widget: tk.Text) -> str:
    """Serialize editor text and its bold/italic tags back to portable Markdown."""
    plain = widget.get("1.0", "end-1c")
    tag_names = getattr(widget, "tag_names", None)
    if not callable(tag_names) or not plain:
        return plain

    output: list[str] = []
    offset = 0
    while offset < len(plain):
        if plain[offset] == "\n":
            output.append("\n")
            offset += 1
            continue

        try:
            tags = set(tag_names(f"1.0 + {offset} chars"))
        except tk.TclError:
            return plain
        bold = "sb_bold" in tags or "sb_bold_italic" in tags
        italic = "sb_italic" in tags or "sb_bold_italic" in tags
        style = "bold_italic" if bold and italic else "bold" if bold else "italic" if italic else None

        end = offset + 1
        while end < len(plain) and plain[end] != "\n":
            try:
                next_tags = set(tag_names(f"1.0 + {end} chars"))
            except tk.TclError:
                return plain
            next_bold = "sb_bold" in next_tags or "sb_bold_italic" in next_tags
            next_italic = "sb_italic" in next_tags or "sb_bold_italic" in next_tags
            next_style = (
                "bold_italic" if next_bold and next_italic
                else "bold" if next_bold
                else "italic" if next_italic
                else None
            )
            if next_style != style:
                break
            end += 1

        value = plain[offset:end]
        marker = "***" if style == "bold_italic" else "**" if style == "bold" else "*" if style == "italic" else ""
        output.append(f"{marker}{value}{marker}" if marker else value)
        offset = end

    return "".join(output)


class MinimalWriterApp:
    """A small local-model writing window, with no story-management pipeline."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.engine = WriterEngine()
        self.models: dict[str, Path] = {}
        self.loaded_model: Path | None = None
        self.current_file: Path | None = None
        self.selected_scene_source: Path | None = None
        self.saved_output_text = ""
        self.novel_packages: dict[str, Path] = {}
        self.last_location_context_names: list[str] = []
        self._scene_preparation_destination = (1, 1)
        self._scene_preparation_original_prompt = ""
        self._scene_preparation_original_author_direction = ""
        self._scene_preparation_novel_path: Path | None = None
        self._preparing_scene = False
        self.chapter_numbers: dict[str, int] = {}
        self.scene_files: dict[str, Path] = {}
        self.busy = False
        self.writing = False
        self.stop_requested = False
        self._pre_generation_text = ""
        self._pre_generation_file: Path | None = None
        self._pre_generation_saved_text = ""
        self._generation_mode = "write"
        self._generation_prefix = ""
        self._generation_had_chunks = False
        self._revision_start_mark = "storybuilder_revision_start"
        self._revision_end_mark = "storybuilder_revision_end"
        self._revision_original = ""
        self._revision_active = False

        root.title("StoryBuilder Minimal Writer - Untitled")
        root.geometry("1080x820")
        root.minsize(760, 600)
        root.protocol("WM_DELETE_WINDOW", self.close)
        apply_application_appearance(root)

        self.model_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Choose a model, then load it.")
        self._build_widgets()
        self.refresh_models()
        self.refresh_novels()

    def _build_widgets(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        model_row = ttk.Frame(outer)
        model_row.pack(fill="x", pady=(0, 10))

        ttk.Label(model_row, text="Local model").pack(side="left", padx=(0, 8))
        self.model_picker = ttk.Combobox(
            model_row,
            textvariable=self.model_var,
            state="readonly",
            width=46,
        )
        self.model_picker.pack(side="left", fill="x", expand=True)

        self.refresh_button = ttk.Button(
            model_row, text="Refresh", command=self.refresh_models
        )
        self.refresh_button.pack(side="left", padx=(8, 0))

        self.load_button = ttk.Button(
            model_row, text="Load Model", command=self.load_selected_model
        )
        self.load_button.pack(side="left", padx=(8, 0))

        # Novel browsing is deliberately read-first. Loading a scene puts a
        # copy in the editor and does not make the accepted manuscript the Save target.
        novel_row = ttk.Frame(outer)
        novel_row.pack(fill="x", pady=(0, 10))
        ttk.Label(novel_row, text="Novel").pack(side="left", padx=(0, 6))
        self.novel_var = tk.StringVar()
        self.novel_picker = ttk.Combobox(
            novel_row, textvariable=self.novel_var, state="readonly", width=24
        )
        self.novel_picker.pack(side="left", padx=(0, 6))
        self.novel_picker.bind("<<ComboboxSelected>>", self._on_novel_selected)
        self.refresh_novels_button = ttk.Button(
            novel_row, text="Refresh Novels", command=self.refresh_novels
        )
        self.refresh_novels_button.pack(side="left", padx=(0, 12))

        ttk.Label(novel_row, text="Chapter").pack(side="left", padx=(0, 6))
        self.chapter_var = tk.StringVar()
        self.chapter_picker = ttk.Combobox(
            novel_row, textvariable=self.chapter_var, state="readonly", width=12
        )
        self.chapter_picker.pack(side="left", padx=(0, 12))
        self.chapter_picker.bind("<<ComboboxSelected>>", self._on_chapter_selected)

        ttk.Label(novel_row, text="Scene").pack(side="left", padx=(0, 6))
        self.scene_var = tk.StringVar()
        self.scene_picker = ttk.Combobox(
            novel_row, textvariable=self.scene_var, state="readonly", width=10
        )
        self.scene_picker.pack(side="left", padx=(0, 8))
        self.load_scene_button = ttk.Button(
            novel_row, text="Load Scene Copy", command=self.load_selected_scene_copy
        )
        self.load_scene_button.pack(side="left")

        assembly_row = ttk.Frame(outer)
        assembly_row.pack(fill="x", pady=(0, 8))
        self.assemble_chapter_button = ttk.Button(
            assembly_row,
            text="Assemble Chapter",
            command=self.assemble_current_chapter,
        )
        self.assemble_chapter_button.pack(side="left")
        self.assemble_novel_button = ttk.Button(
            assembly_row,
            text="Assemble Finished Novel",
            command=self.assemble_finished_novel,
        )
        self.assemble_novel_button.pack(side="left", padx=(8, 0))
        ttk.Label(
            assembly_row,
            text="Creates ODT copies from saved scenes; unsaved editor text is not included.",
        ).pack(side="left", padx=(10, 0))

        sync_row = ttk.Frame(outer)
        sync_row.pack(fill="x", pady=(0, 10))
        self.sync_novel_button = ttk.Button(
            sync_row,
            text="Sync Novel to GitHub",
            command=self.sync_selected_novel_to_github,
        )
        self.sync_novel_button.pack(side="left")
        ttk.Label(
            sync_row,
            text="Uploads only the selected novel repository, not StoryBuilder code.",
        ).pack(side="left", padx=(10, 0))

        author_direction_header = ttk.Frame(outer)
        author_direction_header.pack(fill="x")
        ttk.Label(
            author_direction_header, text="Author's direction (optional)"
        ).pack(side="left", anchor="w")
        ttk.Label(
            author_direction_header,
            text="Leave blank to let Gemma choose what happens next.",
        ).pack(side="left", padx=(8, 0))
        self.author_direction_box = ScrolledText(
            outer, height=3, wrap="word", undo=True, font=("TkDefaultFont", 10)
        )
        self.author_direction_box.pack(fill="x", expand=False, pady=(4, 8))
        bind_ctrl_a_select_all(self.author_direction_box)

        prompt_header = ttk.Frame(outer)
        prompt_header.pack(fill="x")
        ttk.Label(prompt_header, text="What should it write?").pack(side="left", anchor="w")
        self.prepare_scene_button = ttk.Button(
            prompt_header, text="Prepare Scene", command=self.prepare_scene
        )
        self.prepare_scene_button.pack(side="right")
        self.prompt_box = ScrolledText(
            outer, height=8, wrap="word", undo=True, font=("TkDefaultFont", 11)
        )
        self.prompt_box.pack(fill="both", expand=False, pady=(4, 12))
        bind_ctrl_a_select_all(self.prompt_box)

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(0, 8))

        self.write_button = ttk.Button(
            actions, text="Write", command=self.write
        )
        self.write_button.pack(side="left")

        self.rewrite_scene_button = ttk.Button(
            actions, text="Rewrite Scene", command=self.rewrite_current_scene
        )
        self.rewrite_scene_button.pack(side="left", padx=(8, 0))

        self.continue_button = ttk.Button(
            actions, text="Continue", command=self.continue_writing
        )
        self.continue_button.pack(side="left", padx=(8, 0))

        self.new_session_button = ttk.Button(
            actions, text="New Session", command=self.new_session
        )
        self.new_session_button.pack(side="left", padx=(8, 0))

        self.stop_button = ttk.Button(
            actions, text="Stop Writing", command=self.stop_writing, state="disabled"
        )
        self.stop_button.pack(side="left", padx=(8, 0))

        self.open_button = ttk.Button(
            actions, text="Open Text…", command=self.open_text
        )
        self.open_button.pack(side="left", padx=(8, 0))

        self.save_button = ttk.Button(
            actions, text="Save Draft", command=self.save_output
        )
        self.save_button.pack(side="left", padx=(8, 0))

        self.save_as_button = ttk.Button(
            actions, text="Save Draft As…", command=self.save_output_as
        )
        self.save_as_button.pack(side="left", padx=(8, 0))

        self.save_new_scene_button = ttk.Button(
            actions, text="Save New Scene", command=self.save_new_scene
        )
        self.save_new_scene_button.pack(side="left", padx=(8, 0))

        self.save_scene_button = ttk.Button(
            actions, text="Save to Selected Scene", command=self.save_to_selected_scene
        )
        self.save_scene_button.pack(side="left", padx=(8, 0))

        output_header = ttk.Frame(outer)
        output_header.pack(fill="x")
        ttk.Label(output_header, text="Output (editable)").pack(side="left", anchor="w")
        self.revise_selection_button = ttk.Button(
            output_header, text="Revise Selection", command=self.revise_selection
        )
        self.revise_selection_button.pack(side="right")
        self.check_draft_button = ttk.Button(
            output_header,
            text="Check Draft",
            command=self.check_draft,
            state="disabled",
        )
        self.check_draft_button.pack(side="right", padx=(0, 8))
        self.output_box = ScrolledText(
            outer, height=22, wrap="word", undo=True, font=("TkDefaultFont", 11)
        )
        self.output_box.pack(fill="both", expand=True, pady=(4, 8))
        self.output_box.tag_configure(
            "sb_bold", font=("TkDefaultFont", 11, "bold")
        )
        self.output_box.tag_configure(
            "sb_italic", font=("TkDefaultFont", 11, "italic")
        )
        self.output_box.tag_configure(
            "sb_bold_italic", font=("TkDefaultFont", 11, "bold", "italic")
        )
        bind_ctrl_a_select_all(self.output_box)
        self.output_box.bind("<<Modified>>", self._on_output_modified)
        self.output_box.edit_modified(False)

        ttk.Label(
            outer, textvariable=self.status_var, anchor="w", relief="sunken"
        ).pack(fill="x", side="bottom")

    def _showinfo(self, title: str, message: str) -> None:
        show_copyable_dialog(self.root, title, message, buttons=("OK",))

    def _showerror(self, title: str, message: str) -> None:
        show_copyable_dialog(self.root, title, message, buttons=("OK",))

    def _askyesno(self, title: str, message: str) -> bool:
        return show_copyable_dialog(
            self.root, title, message, buttons=("Yes", "No"), default_button="No"
        ) == "Yes"

    def _askyesnocancel(self, title: str, message: str) -> bool | None:
        choice = show_copyable_dialog(
            self.root,
            title,
            message,
            buttons=("Yes", "No", "Cancel"),
            default_button="Cancel",
        )
        if choice == "Yes":
            return True
        if choice == "No":
            return False
        return None

    def revise_selection(self) -> None:
        """Open a small dialog to revise or exactly replace the selected passage."""
        if self.busy:
            return
        try:
            start = self.output_box.index("sel.first")
            end = self.output_box.index("sel.last")
            selected = self.output_box.get(start, end)
        except tk.TclError:
            self._showinfo(
                "Select a passage",
                "Highlight the sentence or paragraph you want to change in the output, "
                "then click Revise Selection.",
            )
            return

        if not selected.strip():
            self._showinfo("Select a passage", "Select some non-blank text to revise.")
            return

        self._revision_original = selected
        self.output_box.mark_set(self._revision_start_mark, start)
        self.output_box.mark_gravity(self._revision_start_mark, "right")
        self.output_box.mark_set(self._revision_end_mark, end)
        self.output_box.mark_gravity(self._revision_end_mark, "left")
        self._revision_active = True
        self._open_revision_dialog(selected)

    def _open_revision_dialog(self, selected_text: str) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Revise Selected Passage")
        dialog.transient(self.root)
        dialog.resizable(True, True)
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        width = min(820, max(440, screen_width - 80))
        height = min(700, max(480, screen_height - 80))
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        outer = ttk.Frame(dialog, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Passage you selected").pack(anchor="w")
        source_box = ScrolledText(
            outer, height=4, wrap="word", font=("TkDefaultFont", 10)
        )
        source_box.pack(fill="x", pady=(4, 10))
        source_box.insert("1.0", selected_text)
        source_box.configure(state="disabled")

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)
        ai_frame = ttk.Frame(notebook, padding=8)
        replace_frame = ttk.Frame(notebook, padding=8)
        notebook.add(ai_frame, text="Revise with AI")
        notebook.add(replace_frame, text="Replace with exact text")

        ttk.Label(
            ai_frame,
            text="Describe the change in plain English. Only the selected passage is revised.",
        ).pack(anchor="w", pady=(0, 5))
        instruction_box = ScrolledText(
            ai_frame, height=8, wrap="word", undo=True, font=("TkDefaultFont", 11)
        )
        instruction_box.pack(fill="both", expand=True)
        bind_ctrl_a_select_all(instruction_box)

        ttk.Label(
            replace_frame,
            text="Enter the exact wording to use instead. Leave it empty to delete the selection.",
        ).pack(anchor="w", pady=(0, 5))
        replacement_box = ScrolledText(
            replace_frame, height=8, wrap="word", undo=True, font=("TkDefaultFont", 11)
        )
        replacement_box.pack(fill="both", expand=True)
        bind_ctrl_a_select_all(replacement_box)

        def cancel() -> None:
            self._discard_revision()
            dialog.destroy()

        def preview() -> None:
            if notebook.index("current") == 0:
                if self.loaded_model is None:
                    self._showinfo(
                        "Load a model",
                        "Load a model before asking the AI to revise the selected passage. "
                        "Exact text replacement does not require a model.",
                    )
                    return
                instruction = instruction_box.get("1.0", "end-1c").strip()
                if not instruction:
                    self._showinfo(
                        "Add an instruction",
                        "Describe what you want changed in the selected passage.",
                    )
                    return
                prompt = build_revision_prompt(selected_text, instruction)
                prompt = self._prepare_location_context(prompt, selected_text)
                dialog.destroy()
                self._begin_revision_generation(prompt)
            else:
                replacement = replacement_box.get("1.0", "end-1c")
                dialog.destroy()
                self._show_revision_review(self._revision_original, replacement)

        button_row = ttk.Frame(outer)
        button_row.pack(fill="x", pady=(10, 0))
        ttk.Button(button_row, text="Cancel", command=cancel).pack(side="right")
        ttk.Button(
            button_row, text="Preview", command=preview
        ).pack(side="right", padx=(0, 8))
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        dialog.bind("<Escape>", lambda _event: cancel())
        dialog.grab_set()
        instruction_box.focus_set()
        self.root.wait_window(dialog)

    def _begin_revision_generation(self, prompt: str) -> None:
        """Generate a proposal without changing the current passage."""
        self.busy = True
        self.writing = True
        self.stop_requested = False
        self.status_var.set(f"Revising selected text with {self.loaded_model.name}…")
        try:
            self.output_box.configure(state="disabled")
        except tk.TclError:
            pass
        self._update_controls()

        def work() -> None:
            try:
                answer = write_from_prompt(self.engine, prompt)
            except GenerationInterrupted:
                self.root.after(0, self._revision_stopped)
            except Exception as exc:
                message = str(exc)
                self.root.after(
                    0, lambda message=message: self._revision_failed(message)
                )
            else:
                self.root.after(0, lambda answer=answer: self._revision_ready(answer))

        threading.Thread(target=work, daemon=True).start()

    def _enable_revision_editor(self) -> None:
        try:
            self.output_box.configure(state="normal")
        except tk.TclError:
            pass

    def _revision_stopped(self) -> None:
        self.busy = False
        self.writing = False
        self.stop_requested = False
        self.loaded_model = None
        self._enable_revision_editor()
        self._discard_revision()
        self.status_var.set(
            "Revision stopped. The original passage was kept. Load the model again to continue."
        )
        self._update_controls()

    def _revision_failed(self, message: str) -> None:
        self.busy = False
        self.writing = False
        self.stop_requested = False
        try:
            still_loaded = self.engine.child is not None and self.engine.child.isalive()
        except Exception:
            still_loaded = False
        if not still_loaded:
            self.loaded_model = None
        self._enable_revision_editor()
        self._discard_revision()
        self.status_var.set("Revision failed. The original passage was kept.")
        self._update_controls()
        self._showerror("Revision failed", message)

    def _revision_ready(self, answer: str) -> None:
        if self.stop_requested:
            self._revision_stopped()
            return
        self.busy = False
        self.writing = False
        self.stop_requested = False
        self._enable_revision_editor()
        self._update_controls()

        candidate = answer.strip()
        if not candidate:
            self._discard_revision()
            self.status_var.set("Revision returned no text. The original passage was kept.")
            self._showerror(
                "Empty revision",
                "The model returned an empty revision, so the selected text was not changed.",
            )
            return
        if not self._revision_target_is_unchanged():
            self._discard_revision()
            self.status_var.set("Revision discarded because the selected text changed.")
            self._showerror(
                "Selection changed",
                "The selected passage changed while the revision was running. "
                "The proposal was discarded to avoid replacing the wrong text.",
            )
            return
        self._show_revision_review(self._revision_original, candidate)

    def _revision_target_is_unchanged(self) -> bool:
        if not self._revision_active:
            return False
        try:
            current = self.output_box.get(
                self._revision_start_mark, self._revision_end_mark
            )
        except tk.TclError:
            return False
        return current == self._revision_original

    def _apply_revision_candidate(self, proposed_text: str) -> bool:
        """Replace only the still-unchanged marked passage and retain normal save tracking."""
        if not self._revision_target_is_unchanged():
            return False
        start = self.output_box.index(self._revision_start_mark)
        self.output_box.delete(self._revision_start_mark, self._revision_end_mark)
        plain, spans = markdown_to_rich_text(proposed_text)
        self.output_box.insert(start, plain)
        inserted_end = self.output_box.index(f"{start} + {len(plain)} chars")
        try:
            for tag in ("sb_bold", "sb_italic", "sb_bold_italic"):
                self.output_box.tag_remove(tag, start, inserted_end)
            for span_start, span_end, style in spans:
                self.output_box.tag_add(
                    f"sb_{style}",
                    f"{start} + {span_start} chars",
                    f"{start} + {span_end} chars",
                )
        except (AttributeError, tk.TclError):
            # Lightweight test doubles may not implement Tk text tags.
            pass
        self.output_box.mark_set("insert", start)
        self.output_box.see("insert")
        self.output_box.edit_modified(False)
        self._discard_revision()
        self.status_var.set("Revision applied to selected passage. Save when ready.")
        self._update_document_title()
        self._update_controls()
        return True

    def _show_revision_review(self, original: str, proposal: str) -> None:
        """Preview proposed wording; change the document only on explicit approval."""
        if not self._revision_target_is_unchanged():
            self._discard_revision()
            self.status_var.set("Revision discarded because the selected text changed.")
            self._showerror(
                "Selection changed",
                "The selected passage has changed. Nothing was replaced. Select it again and retry.",
            )
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Review Passage Change")
        dialog.transient(self.root)
        dialog.resizable(True, True)
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        width = min(820, max(440, screen_width - 80))
        height = min(720, max(480, screen_height - 80))
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        outer = ttk.Frame(dialog, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Original passage (unchanged so far)").pack(anchor="w")
        original_box = ScrolledText(
            outer, height=5, wrap="word", font=("TkDefaultFont", 10)
        )
        original_box.pack(fill="x", pady=(4, 10))
        original_box.insert("1.0", original)
        original_box.configure(state="disabled")

        ttk.Label(
            outer,
            text="Proposed replacement (you can make final edits here)",
        ).pack(anchor="w")
        proposal_box = ScrolledText(
            outer, height=9, wrap="word", undo=True, font=("TkDefaultFont", 11)
        )
        proposal_box.pack(fill="both", expand=True, pady=(4, 8))
        proposal_box.insert("1.0", proposal)
        bind_ctrl_a_select_all(proposal_box)

        def dismiss() -> None:
            self._discard_revision()
            self.status_var.set("Kept original passage; no text was changed.")
            dialog.destroy()
            self._update_controls()

        def use_revision() -> None:
            proposed_text = proposal_box.get("1.0", "end-1c")
            if not self._apply_revision_candidate(proposed_text):
                self._discard_revision()
                dialog.destroy()
                self.status_var.set(
                    "Revision not applied because the selected text changed."
                )
                self._showerror(
                    "Selection changed",
                    "The original selection is no longer unchanged. The proposal was not applied.",
                )
                self._update_controls()
                return
            dialog.destroy()

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Keep Original", command=dismiss).pack(side="right")
        ttk.Button(
            buttons, text="Use Revision", command=use_revision
        ).pack(side="right", padx=(0, 8))
        dialog.protocol("WM_DELETE_WINDOW", dismiss)
        dialog.bind("<Escape>", lambda _event: dismiss())
        dialog.grab_set()
        proposal_box.focus_set()
        self.root.wait_window(dialog)

    def _discard_revision(self) -> None:
        """Forget selection marks without changing the text in the editor."""
        try:
            self.output_box.mark_unset(
                self._revision_start_mark, self._revision_end_mark
            )
        except (AttributeError, tk.TclError):
            pass
        self._revision_active = False
        self._revision_original = ""

    def refresh_models(self) -> None:
        try:
            paths = WriterEngine.available_models()
        except Exception as exc:
            self.status_var.set(f"Could not list models: {exc}")
            return

        previous = self.model_var.get()
        self.models = {path.name: path for path in paths}
        names = list(self.models)
        self.model_picker.configure(values=names)

        if previous in self.models:
            self.model_var.set(previous)
        elif self.loaded_model is not None and self.loaded_model.name in self.models:
            self.model_var.set(self.loaded_model.name)
        elif names:
            self.model_var.set(names[0])
        else:
            self.model_var.set("")
            self.status_var.set(f"No GGUF models found in {MODELS_DIR}.")
        self._update_controls()

    def load_selected_model(self) -> None:
        if self.busy:
            return
        name = self.model_var.get().strip()
        path = self.models.get(name)
        if path is None:
            self._showinfo(
                "Choose a model", f"No model is selected. Check {MODELS_DIR}."
            )
            return

        self.busy = True
        self.writing = False
        self.stop_requested = False
        self.status_var.set(f"Loading {path.name}…")
        self._update_controls()

        def work() -> None:
            try:
                load_model_for_writing(self.engine, path)
            except Exception as exc:
                message = str(exc)
                self.root.after(0, lambda message=message: self._load_failed(message))
            else:
                self.root.after(0, lambda: self._load_succeeded(path))

        threading.Thread(target=work, daemon=True).start()

    def _load_succeeded(self, path: Path) -> None:
        self.busy = False
        self.writing = False
        self.stop_requested = False
        self.loaded_model = path
        self.status_var.set(f"Loaded: {path.name}")
        self._update_controls()

    def _load_failed(self, message: str) -> None:
        self.busy = False
        self.writing = False
        self.stop_requested = False
        self.loaded_model = None
        self.status_var.set("Model load failed.")
        self._update_controls()
        self._showerror("Could not load model", message)


    def refresh_novels(self) -> None:
        """Refresh the local novel library without opening or changing a package."""
        previous = self.novel_var.get().strip() if hasattr(self, "novel_var") else ""
        try:
            paths = list_novel_packages(NOVEL_ROOT)
        except Exception as exc:
            self.status_var.set(f"Could not list novels: {exc}")
            return

        self.novel_packages = {path.name: path for path in paths}
        names = list(self.novel_packages)
        self.novel_picker.configure(values=names)

        if not names:
            self.novel_var.set("")
            self.chapter_var.set("")
            self.chapter_numbers = {}
            self.chapter_picker.configure(values=[])
            self.scene_var.set("")
            self.scene_files = {}
            self.scene_picker.configure(values=[])
            self.status_var.set(f"No novel packages found in {NOVEL_ROOT}.")
            self._update_controls()
            return

        self.novel_var.set(previous if previous in self.novel_packages else names[0])
        self._on_novel_selected()

    def _on_novel_selected(self, _event=None) -> None:
        """Populate the chapter picker for the selected novel."""
        novel_path = self.novel_packages.get(self.novel_var.get().strip())
        self.chapter_numbers = {}
        if novel_path is not None:
            numbers = list_scene_chapters(novel_path)
            self.chapter_numbers = {f"Chapter {number:02d}": number for number in numbers}

        labels = list(self.chapter_numbers)
        self.chapter_picker.configure(values=labels)
        if not labels:
            self.chapter_var.set("")
            self.scene_var.set("")
            self.scene_files = {}
            self.scene_picker.configure(values=[])
            if novel_path is not None:
                self.status_var.set(
                    f"No Manuscript/Chapters folders found for {novel_path.name}."
                )
            self._update_controls()
            return

        current = self.chapter_var.get().strip()
        self.chapter_var.set(current if current in self.chapter_numbers else labels[0])
        self._on_chapter_selected()

    def _on_chapter_selected(self, _event=None) -> None:
        """Populate the scene picker using only numbered manuscript text files."""
        novel_path = self.novel_packages.get(self.novel_var.get().strip())
        chapter_number = self.chapter_numbers.get(self.chapter_var.get().strip())
        self.scene_files = {}
        if novel_path is not None and chapter_number is not None:
            scenes = list_scene_files(novel_path, chapter_number)
            self.scene_files = {
                f"Scene {scene_number:02d}": path for scene_number, path in scenes
            }

        labels = list(self.scene_files)
        self.scene_picker.configure(values=labels)
        current = self.scene_var.get().strip()
        if labels:
            self.scene_var.set(current if current in self.scene_files else labels[0])
            self.status_var.set(
                f"Selected {self.novel_var.get()} / {self.chapter_var.get()} / "
                f"{self.scene_var.get()}. Load Scene Copy to read it without targeting "
                "the accepted manuscript for Save."
            )
        else:
            self.scene_var.set("")
            self.status_var.set(
                f"No saved scene documents found for {self.chapter_var.get() or 'this chapter'}. "
                "You can still use the Writer normally."
            )
        self._update_controls()

    def load_selected_scene_copy(self) -> None:
        """Load a selected accepted scene as a copy; Save will use Save As."""
        if self.busy:
            return
        source = self.scene_files.get(self.scene_var.get().strip())
        if source is None:
            self._showinfo(
                "Choose a scene",
                "Select a novel, chapter, and scene that has a saved text file.",
            )
            return

        try:
            text = read_document(source)
        except (OSError, UnicodeError, ValueError) as exc:
            self._showerror("Could not load scene", str(exc))
            return

        if not self._confirm_save_pending_changes():
            return

        self.current_file = None
        self.selected_scene_source = source.resolve()
        self.saved_output_text = text
        self._set_output_text(text)
        self.status_var.set(
            f"Loaded scene copy from {source}. The original is untouched; Save opens Save As."
        )
        self._update_controls()

    def assemble_current_chapter(self) -> None:
        """Create an ODT copy of the selected chapter's saved scenes."""
        if self.busy:
            return

        novel_name = self.novel_var.get().strip()
        novel_path = self.novel_packages.get(novel_name)
        chapter_number = self.chapter_numbers.get(self.chapter_var.get().strip())
        if novel_path is None or chapter_number is None:
            self._showinfo(
                "Choose a chapter",
                "Select a novel and chapter before assembling a chapter document.",
            )
            return

        try:
            target = assemble_chapter_document(novel_path, chapter_number)
        except (OSError, UnicodeError, ValueError) as exc:
            self.status_var.set("Chapter assembly failed.")
            self._showerror("Could not assemble chapter", str(exc))
            return

        self.status_var.set(
            f"Assembled Chapter {int(chapter_number):02d}: {target}"
        )
        self._showinfo(
            "Chapter assembled",
            f"Chapter {int(chapter_number):02d} was assembled from its saved scenes.\n\n"
            f"ODT document:\n{target}\n\n"
            "The original scene files were not changed.",
        )

    def assemble_finished_novel(self) -> None:
        """Create one ODT copy containing every chapter with saved scenes."""
        if self.busy:
            return

        novel_name = self.novel_var.get().strip()
        novel_path = self.novel_packages.get(novel_name)
        if novel_path is None:
            self._showinfo(
                "Choose a novel",
                "Select a novel before assembling the finished manuscript.",
            )
            return

        try:
            story_bible = load_story_bible(novel_path)
            title = str(story_bible.get("title") or novel_name).strip()
        except (OSError, UnicodeError, ValueError):
            title = novel_name.replace("-", " ").replace("_", " ").strip()

        try:
            target = assemble_finished_novel_document(novel_path, title)
        except (OSError, UnicodeError, ValueError) as exc:
            self.status_var.set("Finished novel assembly failed.")
            self._showerror("Could not assemble finished novel", str(exc))
            return

        self.status_var.set(f"Assembled finished novel: {target}")
        self._showinfo(
            "Finished novel assembled",
            f"{title} was assembled from all chapters with saved scenes.\n\n"
            f"ODT document:\n{target}\n\n"
            "The original scene files were not changed.",
        )

    def sync_selected_novel_to_github(self) -> None:
        """Preview and explicitly confirm syncing only the selected novel repo."""
        if self.busy:
            return

        name = self.novel_var.get().strip()
        novel_path = self.novel_packages.get(name)
        if novel_path is None:
            self._showinfo(
                "Choose a novel",
                "Select an existing novel package before syncing it to GitHub.",
            )
            return

        try:
            preview = inspect_novel_repository(novel_path)
        except NovelGitSyncError as exc:
            self.status_var.set("Novel sync blocked; no push was attempted.")
            self._showerror("Cannot sync novel", str(exc))
            return

        lines = [
            "Review the target before syncing:",
            "",
            f"Novel folder: {preview.repository}",
            f"Branch: {preview.branch}",
            f"GitHub remote: {preview.remote_url}",
            "",
            "This sync will only operate inside this novel's Git repository.",
            "It will fetch and fast-forward safely if possible, commit the listed local "
            "changes, and push this branch. It will not sync StoryBuilder's code.",
            "If local and GitHub branches have diverged, syncing stops without pushing.",
            "Local-only secret/encrypted assets in the Git change list block syncing.",
            "",
        ]
        if hasattr(self, "output_box") and self._output_text() != self.saved_output_text:
            lines.extend(
                [
                    "WARNING: The Writer pane contains unsaved edits.",
                    "Those edits are not included in this Git sync until you save them to a file.",
                    "",
                ]
            )

        if preview.local_commits:
            lines.append(
                "Local commits currently ahead of the last fetched origin branch "
                "(these may be pushed; the list can change after fetching):"
            )
            shown_commits = preview.local_commits[:10]
            lines.extend(f"  • {commit}" for commit in shown_commits)
            if len(preview.local_commits) > len(shown_commits):
                lines.append(
                    f"  • …and {len(preview.local_commits) - len(shown_commits)} more commit(s)"
                )
            lines.append("")

        if preview.changed_files:
            lines.append("Local file changes to include in the commit:")
            shown_files = preview.changed_files[:15]
            lines.extend(f"  • {path}" for path in shown_files)
            if len(preview.changed_files) > len(shown_files):
                lines.append(
                    f"  • …and {len(preview.changed_files) - len(shown_files)} more file(s)"
                )
        else:
            lines.append(
                "No uncommitted local file changes detected. This will still check for "
                "safe fast-forward updates from GitHub and push the selected branch if needed."
            )
        lines.extend(["", "Proceed with syncing this novel to GitHub?"])

        if not self._askyesno(
            "Confirm novel sync", "\n".join(lines)
        ):
            self.status_var.set("Novel sync cancelled; no Git operation started.")
            return

        self.busy = True
        self.status_var.set(f"Syncing {name} to GitHub on branch {preview.branch}…")
        self._update_controls()

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
                    0, lambda result=result: self._novel_sync_succeeded(result)
                )

        threading.Thread(target=work, daemon=True).start()

    def _novel_sync_succeeded(self, result) -> None:
        self.busy = False
        selected_name = self.novel_var.get().strip()
        # The fast-forward may have brought in new chapter or scene files.
        self.refresh_novels()
        if selected_name in self.novel_packages:
            self.novel_var.set(selected_name)
            self._on_novel_selected()
        self.status_var.set(result.message)
        self._update_controls()

    def _novel_sync_failed(self, message: str) -> None:
        self.busy = False
        self.status_var.set("Novel sync failed. Check the message before retrying.")
        self._update_controls()
        self._showerror("Novel sync failed", message)

    def prepare_scene(self) -> None:
        """Ask the loaded local model for a concise starter in the prompt box."""
        if self.busy:
            return
        if self.loaded_model is None:
            self._showinfo("Load a model", "Load a model before preparing a scene.")
            return

        novel_name = self.novel_var.get().strip()
        novel_path = self.novel_packages.get(novel_name)
        if novel_path is None:
            self._showinfo("Choose a novel", "Select a novel before preparing a scene.")
            return

        chapter_number = self.chapter_numbers.get(self.chapter_var.get().strip())
        selected_scene_label = self.scene_var.get().strip()
        selected_scene_number = scene_number_from_label(selected_scene_label)
        source_scene = self.scene_files.get(selected_scene_label)
        target_chapter, target_scene = next_scene_coordinates(
            chapter_number, source_scene, selected_scene_number
        )
        try:
            planning_prompt = build_scene_preparation_prompt(
                novel_path,
                novel_name,
                target_chapter,
                target_scene,
                source_scene_path=source_scene,
                author_direction=self.author_direction_box.get(
                    "1.0", "end-1c"
                ).strip(),
            )
        except (OSError, UnicodeError, ValueError) as exc:
            self._showerror("Could not prepare scene", str(exc))
            return

        existing_prompt = self.prompt_box.get("1.0", "end-1c")
        if existing_prompt.strip() and not self._askyesno(
            "Replace prompt box text?",
            (
                f"You selected {self.chapter_var.get().strip() or f'Chapter {target_chapter:02d}'}, "
                f"{selected_scene_label or 'no saved scene'}. Prepare Scene is preparing "
                f"Chapter {target_chapter:02d}, Scene {target_scene:02d}.\n\n"
                "This will replace ONLY the text in the What should it write? box. "
                "It will NOT overwrite, save, or modify the selected scene or any manuscript file.\n\n"
                "Your existing prompt text will stay untouched if you cancel. Continue?"
            ),
        ):
            return

        self._scene_preparation_destination = (target_chapter, target_scene)
        self._scene_preparation_novel_path = novel_path
        self._scene_preparation_original_prompt = existing_prompt
        self._scene_preparation_original_author_direction = (
            self.author_direction_box.get("1.0", "end-1c").strip()
        )
        self._preparing_scene = True
        self.busy = True
        self.writing = True
        self.stop_requested = False
        self.status_var.set(
            f"Preparing Chapter {target_chapter:02d}, Scene {target_scene:02d} "
            f"for {novel_name}…"
        )
        self._update_controls()

        def work() -> None:
            try:
                suggestion = write_from_prompt(self.engine, planning_prompt).strip()
            except GenerationInterrupted:
                self.root.after(0, self._prepare_scene_stopped)
            except Exception as exc:
                message = str(exc)
                self.root.after(
                    0, lambda message=message: self._prepare_scene_failed(message)
                )
            else:
                context_reset_error = None
                try:
                    # Prepare Scene is a planning-only turn. Clear that turn from
                    # the persistent model session so Write starts with clean chat
                    # history while the suggestion remains in the prompt box.
                    self.engine.clear_context()
                except Exception as exc:
                    context_reset_error = str(exc)
                self.root.after(
                    0,
                    lambda suggestion=suggestion, error=context_reset_error:
                        self._prepare_scene_succeeded(suggestion, error),
                )

        threading.Thread(target=work, daemon=True).start()

    def _prepare_scene_succeeded(
        self, suggestion: str, context_reset_error: str | None = None
    ) -> None:
        if self.stop_requested:
            self._prepare_scene_stopped()
            return
        current_prompt = self.prompt_box.get("1.0", "end-1c")
        original_prompt = getattr(self, "_scene_preparation_original_prompt", "")
        current_author_direction = self.author_direction_box.get(
            "1.0", "end-1c"
        ).strip()
        original_author_direction = getattr(
            self, "_scene_preparation_original_author_direction", ""
        )
        if (
            current_prompt != original_prompt
            or current_author_direction != original_author_direction
        ):
            self._preparing_scene = False
            self.busy = False
            self.writing = False
            self.stop_requested = False
            self.status_var.set(
                "The prompt or author's direction was edited while Scene Preparation "
                "was running. Your edits were kept; prepare again if you still need a suggestion."
            )
            self._update_controls()
            return
        if not suggestion.strip():
            self._preparing_scene = False
            self.busy = False
            self.writing = False
            self.stop_requested = False
            self.status_var.set("Scene preparation returned no suggestion. Your prompt was kept.")
            self._update_controls()
            self._showerror(
                "No scene suggestion",
                "The model returned an empty suggestion. The existing prompt was not changed.",
            )
            return

        self.prompt_box.delete("1.0", "end")
        self.prompt_box.insert("1.0", suggestion.strip())
        self.author_direction_box.delete("1.0", "end")
        chapter_number, scene_number = self._scene_preparation_destination
        self._select_scene_destination(
            chapter_number, scene_number, self._scene_preparation_novel_path
        )
        self._preparing_scene = False
        self.busy = False
        self.writing = False
        self.stop_requested = False
        if context_reset_error:
            # Keep the prepared suggestion, but do not leave the UI claiming
            # that a model session with uncleared planning history is usable.
            self.loaded_model = None
            self.status_var.set(
                f"Prepared Chapter {chapter_number:02d}, Scene {scene_number:02d}. "
                "The suggestion was kept, but model history could not be cleared. "
                "Load the model again before pressing Write. "
                f"Details: {context_reset_error}"
            )
        else:
            self.status_var.set(
                f"Prepared Chapter {chapter_number:02d}, Scene {scene_number:02d}. "
                "Model conversation cleared. Edit the suggestion, then press Write."
            )
        self._update_controls()

    def _select_scene_destination(
        self, chapter_number: int, scene_number: int, novel_path: Path | None
    ) -> None:
        """Show a prepared destination even when its chapter or scene is not saved yet."""
        chapter_label = f"Chapter {int(chapter_number):02d}"
        scene_label = f"Scene {int(scene_number):02d}"

        chapter_numbers = dict(getattr(self, "chapter_numbers", {}))
        chapter_numbers[chapter_label] = int(chapter_number)
        self.chapter_numbers = chapter_numbers
        chapter_labels = sorted(
            chapter_numbers,
            key=lambda label: (chapter_numbers[label], label.casefold()),
        )
        self.chapter_picker.configure(values=chapter_labels)
        self.chapter_var.set(chapter_label)

        saved_scenes = (
            list_scene_files(novel_path, chapter_number)
            if novel_path is not None else []
        )
        self.scene_files = {
            f"Scene {number:02d}": path for number, path in saved_scenes
        }
        scene_numbers = sorted(
            {number for number, _path in saved_scenes} | {int(scene_number)}
        )
        scene_labels = [f"Scene {number:02d}" for number in scene_numbers]
        self.scene_picker.configure(values=scene_labels)
        self.scene_var.set(scene_label)

    def _prepare_scene_failed(self, message: str) -> None:
        self._preparing_scene = False
        self.busy = False
        self.writing = False
        self.stop_requested = False
        try:
            child = getattr(self.engine, "child", None)
            still_loaded = child is not None and child.isalive()
        except Exception:
            still_loaded = False
        if not still_loaded:
            self.loaded_model = None
        self.status_var.set("Scene preparation failed. Your existing prompt was kept.")
        self._update_controls()
        self._showerror("Scene preparation failed", message)

    def _prepare_scene_stopped(self) -> None:
        self._preparing_scene = False
        self.busy = False
        self.writing = False
        self.loaded_model = None
        self.stop_requested = False
        self.status_var.set(
            "Scene preparation stopped. Your existing prompt was kept. "
            "Load the model again before continuing."
        )
        self._update_controls()

    def write(self) -> None:
        if self.busy:
            return
        if self.loaded_model is None:
            self._showinfo("Load a model", "Load a model before writing.")
            return

        prompt = self.prompt_box.get("1.0", "end-1c")
        if not prompt.strip():
            self._showinfo("Add a prompt", "Enter what you want the model to write.")
            return

        prompt = self._prepare_location_context(prompt)
        prompt = self._prepare_previous_scene_context(prompt)
        self._begin_generation(prompt, mode="write")

    def rewrite_current_scene(self) -> None:
        """Regenerate the visible scene using its existing prompt and extra guidance."""
        if self.busy:
            return
        if self.loaded_model is None:
            self._showinfo("Load a model", "Load a model before rewriting a scene.")
            return

        scene_prompt = self.prompt_box.get("1.0", "end-1c")
        if not scene_prompt.strip():
            self._showinfo(
                "No scene direction",
                "Prepare or enter the scene direction in What should it write? first.",
            )
            return

        previous_draft = self._output_text()
        if not previous_draft.strip():
            self._showinfo(
                "No scene draft",
                "Write the scene first. Rewrite Scene replaces an existing draft with a fresh attempt.",
            )
            return

        author_direction = self.author_direction_box.get(
            "1.0", "end-1c"
        ).strip()
        if not self._askyesno(
            "Rewrite current scene?",
            (
                "Gemma will use the existing What should it write? prompt, with "
                "Author's Direction added as extra guidance. The visible Output draft "
                "will be replaced only after you confirm.\n\n"
                "The scene prompt, selected scene number, and saved manuscript files "
                "will not be changed. If you cancel, stop generation, or generation "
                "fails, the current draft will be restored."
            ),
        ):
            self.status_var.set("Rewrite cancelled. The current draft was kept.")
            return

        prompt = build_rewrite_scene_prompt(scene_prompt, author_direction)
        prompt = self._prepare_location_context(prompt)
        prompt = self._prepare_previous_scene_context(prompt)
        self._rewrite_original_author_direction = author_direction
        self._begin_generation(prompt, mode="rewrite")

    def continue_writing(self) -> None:
        if self.busy:
            return
        if self.loaded_model is None:
            self._showinfo("Load a model", "Load a model before continuing.")
            return

        existing_text = self._output_text()
        if not existing_text.strip():
            self._showinfo(
                "Nothing to continue",
                "Write a passage or open a text file before continuing.",
            )
            return

        prompt = build_continue_prompt(existing_text)
        prompt_box = getattr(self, "prompt_box", None)
        scene_idea = (
            prompt_box.get("1.0", "end-1c")
            if prompt_box is not None else ""
        )
        prompt = self._prepare_location_context(
            prompt,
            "\n".join(part for part in (scene_idea, existing_text) if part),
        )
        self._begin_generation(prompt, mode="continue")

    def _prepare_previous_scene_context(self, prompt: str) -> str:
        """Add the immediately preceding accepted scene for grounded continuity."""
        novel_name = getattr(getattr(self, "novel_var", None), "get", lambda: "")().strip()
        novel_path = getattr(self, "novel_packages", {}).get(novel_name)
        chapter_number = getattr(self, "chapter_numbers", {}).get(
            getattr(getattr(self, "chapter_var", None), "get", lambda: "")().strip()
        )
        scene_number = scene_number_from_label(
            getattr(getattr(self, "scene_var", None), "get", lambda: "")()
        )
        if novel_path is None or chapter_number is None or scene_number is None:
            return str(prompt or "")
        return build_previous_scene_context_prompt(
            prompt, novel_path, chapter_number, scene_number
        )

    def _prepare_location_context(self, prompt: str, supporting_text: str = "") -> str:
        """Attach the selected novel's creative direction and relevant saved locations."""
        self.last_location_context_names = []
        novel_var = getattr(self, "novel_var", None)
        novel_packages = getattr(self, "novel_packages", {})
        if novel_var is None or not isinstance(novel_packages, dict):
            return prompt
        novel_name = novel_var.get().strip()
        novel_path = novel_packages.get(novel_name)
        if novel_path is None:
            return prompt

        try:
            story_bible = load_story_bible(novel_path)
        except (OSError, UnicodeError, ValueError):
            # Story Bible context is optional: an absent or malformed file must
            # never prevent ordinary writing or modify the novel package.
            return prompt

        craft_note = build_story_craft_prompt()
        if craft_note:
            prompt = f"{str(prompt).rstrip()}\n\n{craft_note}"

        canon_rules_note = build_canon_rules_prompt(story_bible.get("canon_rules"))
        if canon_rules_note:
            prompt = f"{str(prompt).rstrip()}\n\n{canon_rules_note}"

        pacing_note = build_story_opening_pacing_prompt()
        prompt = f"{str(prompt).rstrip()}\n\n{pacing_note}"

        creative_note = build_creative_direction_prompt(
            story_bible.get("creative_direction")
        )
        if creative_note:
            prompt = f"{str(prompt).rstrip()}\n\n{creative_note}"

        character_supporting_text = str(supporting_text or "")
        include_all_character_cards = False
        try:
            state_path = Path(novel_path) / "current_state.json"
            current_state = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(current_state, dict):
                timeline_note = build_story_timeline_prompt(current_state.get("time_of_day"))
                if timeline_note:
                    prompt = f"{str(prompt).rstrip()}\n\n{timeline_note}"
                story_context_note = build_current_story_context_prompt(current_state)
                if story_context_note:
                    prompt = f"{str(prompt).rstrip()}\n\n{story_context_note}"
                cast_names = []
                scene_cast = current_state.get("scene_cast", [])
                if isinstance(scene_cast, list):
                    cast_names = [
                        str(name).strip()
                        for name in scene_cast
                        if isinstance(name, str) and name.strip()
                    ]
                    if cast_names:
                        character_supporting_text = "\n".join(
                            part for part in (character_supporting_text, " ".join(cast_names))
                            if part
                        )
                if not cast_names and current_state.get("status") == "story_start":
                    include_all_character_cards = True
        except (OSError, UnicodeError, ValueError):
            pass

        prompt = build_character_card_context_prompt(
            novel_path,
            story_bible,
            prompt,
            supporting_text=character_supporting_text,
            include_all=include_all_character_cards,
        )

        locations = story_bible.get("locations", {})
        enriched, names = build_location_context_prompt(
            prompt,
            locations if isinstance(locations, dict) else {},
            supporting_text=supporting_text,
        )
        self.last_location_context_names = names
        return enriched

    def new_session(self) -> None:
        """Clear model conversation context while preserving the visible draft."""
        if self.busy:
            return
        if self.loaded_model is None:
            self._showinfo("Load a model", "Load a model before starting a new session.")
            return

        self.busy = True
        self.writing = False
        self.stop_requested = False
        self.status_var.set(f"Starting a new session with {self.loaded_model.name}…")
        self._update_controls()

        def work() -> None:
            try:
                self.engine.clear_context()
            except Exception as exc:
                message = str(exc)
                self.root.after(0, lambda message=message: self._new_session_failed(message))
            else:
                self.root.after(0, self._new_session_succeeded)

        threading.Thread(target=work, daemon=True).start()

    def _new_session_succeeded(self) -> None:
        self.busy = False
        self.writing = False
        self.stop_requested = False
        model_name = self.loaded_model.name if self.loaded_model else "model"
        self.status_var.set(
            f"New session ready with {model_name}. Visible text was kept."
        )
        self._update_controls()

    def _new_session_failed(self, message: str) -> None:
        self.busy = False
        self.writing = False
        self.stop_requested = False
        try:
            still_loaded = self.engine.child is not None and self.engine.child.isalive()
        except Exception:
            still_loaded = False
        if not still_loaded:
            self.loaded_model = None
        self.status_var.set("New session failed. Reload the model if needed.")
        self._update_controls()
        self._showerror("Could not start a new session", message)

    def _start_prompt_trace(self, prompt: str):
        """Arm a local, one-generation capture without affecting normal writing."""
        try:
            if not load_prompt_trace_enabled():
                return None
        except Exception:
            return None

        novel_name = getattr(getattr(self, "novel_var", None), "get", lambda: "")().strip()
        novel_path = getattr(self, "novel_packages", {}).get(novel_name)
        chapter_number = getattr(self, "chapter_numbers", {}).get(
            getattr(getattr(self, "chapter_var", None), "get", lambda: "")().strip(),
            1,
        )
        scene_number = scene_number_from_label(
            getattr(getattr(self, "scene_var", None), "get", lambda: "")()
        ) or 1

        current_state = {}
        reference_files = []
        if novel_path is not None:
            for filename in ("story_bible.json", "current_state.json"):
                path = Path(novel_path) / filename
                try:
                    content = path.read_text(encoding="utf-8")
                except (OSError, UnicodeError):
                    continue
                reference_files.append((filename, content))
                if filename == "current_state.json":
                    try:
                        parsed = json.loads(content)
                    except (TypeError, ValueError):
                        parsed = {}
                    if isinstance(parsed, dict):
                        current_state = parsed

        prompt_box = getattr(self, "prompt_box", None)
        direction_box = getattr(self, "author_direction_box", None)
        scene_direction = (
            prompt_box.get("1.0", "end-1c") if prompt_box is not None else str(prompt or "")
        )
        author_guidance = (
            direction_box.get("1.0", "end-1c").strip()
            if direction_box is not None else ""
        )
        trace = PromptTrace(
            chapter=int(chapter_number or 1),
            scene=int(scene_number),
            model_path=getattr(self, "loaded_model", None),
            current_state=current_state,
            reference_files=reference_files,
            contract={},
            scene_direction=scene_direction,
            author_guidance=author_guidance,
            system_prompt=getattr(self.engine, "system_prompt", ""),
        )
        attach = getattr(self.engine, "attach_prompt_trace", None)
        if not callable(attach):
            return None
        try:
            attach(trace)
        except Exception:
            return None
        return trace

    def _finish_prompt_trace(
        self, trace, *, status: str, error: str | None = None
    ) -> None:
        self._last_prompt_trace_upload_result = None
        if trace is None:
            return
        saved_path = None
        try:
            saved_path = trace.finish(status=status, error=error)
        except Exception:
            saved_path = None
        self._last_prompt_trace_path = str(saved_path) if saved_path else None
        if saved_path:
            try:
                self._last_prompt_trace_upload_result = upload_prompt_trace(saved_path)
            except Exception as exc:
                # Remote diagnostics are optional. Keep the local trace and never
                # turn a completed writing operation into a failure if upload fails.
                self._last_prompt_trace_upload_result = {
                    "ok": False,
                    "error": str(exc)[:700],
                }
        detach = getattr(self.engine, "detach_prompt_trace", None)
        if callable(detach):
            try:
                detach(trace)
            except Exception:
                pass

    def _begin_generation(self, prompt: str, mode: str) -> None:
        # Keep the previous document recoverable so errors or an immediate Stop
        # do not destroy the author's text.
        self._pre_generation_text = self._output_text()
        self._pre_generation_file = self.current_file
        self._pre_generation_saved_text = self.saved_output_text
        self._generation_mode = mode
        self._generation_had_chunks = False
        self._last_prompt_trace_path = None
        self._last_prompt_trace_upload_result = None
        prompt_trace = self._start_prompt_trace(prompt)
        if mode == "continue":
            self._generation_prefix = continuation_prefix(self._pre_generation_text)
            self._set_output_text(self._generation_prefix)
        else:
            self._generation_prefix = ""
            self._set_output_text("")

        self.busy = True
        self.writing = True
        self.stop_requested = False
        action = {
            "continue": "Continuing",
            "rewrite": "Rewriting",
        }.get(mode, "Writing")
        location_names = getattr(self, "last_location_context_names", [])
        location_note = (
            f" Saved locations: {', '.join(location_names)}."
            if location_names else ""
        )
        self.status_var.set(f"{action} with {self.loaded_model.name}…{location_note}")
        self._update_controls()

        def stream_delta(chunk: str) -> None:
            # WriterEngine calls this from the worker thread. Tk widgets must
            # only be touched on the UI thread.
            if chunk:
                try:
                    self.root.after(0, lambda chunk=chunk: self._append_streamed_chunk(chunk))
                except tk.TclError:
                    pass

        def work() -> None:
            trace_status = "completed"
            trace_error = None
            callback = None
            try:
                answer = write_from_prompt(self.engine, prompt, on_delta=stream_delta)
            except GenerationInterrupted as exc:
                trace_status = "interrupted"
                trace_error = str(exc)
                callback = self._write_stopped
            except Exception as exc:
                trace_status = "failed"
                trace_error = str(exc)
                message = str(exc)
                callback = lambda message=message: self._write_failed(message)
            else:
                callback = lambda answer=answer: self._write_succeeded(answer)
            finally:
                self._finish_prompt_trace(
                    prompt_trace, status=trace_status, error=trace_error
                )
            if callback is not None:
                self.root.after(0, callback)

        threading.Thread(target=work, daemon=True).start()

    def stop_writing(self) -> None:
        if not self.busy or not self.writing or self.stop_requested:
            return
        self.stop_requested = True
        self.status_var.set("Stopping generation…")
        self._update_controls()
        self.engine.interrupt_generation()

    def _append_streamed_chunk(self, chunk: str) -> None:
        if not self.busy:
            return
        self.output_box.insert("end", chunk)
        self._generation_had_chunks = True
        self.output_box.see("end")
        self.output_box.edit_modified(False)
        self._update_document_title()

    def _restore_pre_generation_output(self) -> None:
        self.current_file = self._pre_generation_file
        self.saved_output_text = self._pre_generation_saved_text
        self._set_output_text(self._pre_generation_text)

    def _write_succeeded(self, answer: str) -> None:
        # Use the cleaned response as canonical text. Continue keeps the passage
        # that was already in the editor and appends only the new response.
        final_text = (
            self._generation_prefix + answer
            if self._generation_mode == "continue"
            else answer
        )
        self._set_output_text(final_text)
        if self.stop_requested:
            self._finish_stopped()
            return
        self.busy = False
        self.writing = False
        model_name = self.loaded_model.name if self.loaded_model else "model"
        action = {
            "continue": "continuing",
            "rewrite": "rewriting",
        }.get(self._generation_mode, "writing")
        rewrite_note = ""
        if self._generation_mode == "rewrite":
            direction_box = getattr(self, "author_direction_box", None)
            original_direction = getattr(
                self, "_rewrite_original_author_direction", None
            )
            if direction_box is not None and original_direction is not None:
                current_direction = direction_box.get("1.0", "end-1c").strip()
                if current_direction == original_direction:
                    direction_box.delete("1.0", "end")
                else:
                    rewrite_note = " New Author's Direction edits were kept."
        location_names = getattr(self, "last_location_context_names", [])
        location_note = (
            f" Location context: {', '.join(location_names)}."
            if location_names else ""
        )
        trace_path = getattr(self, "_last_prompt_trace_path", None)
        trace_note = f" Prompt trace saved locally: {trace_path}." if trace_path else ""
        upload_result = getattr(self, "_last_prompt_trace_upload_result", None)
        upload_note = ""
        if isinstance(upload_result, dict):
            if upload_result.get("ok"):
                upload_url = str(upload_result.get("url") or "").strip()
                upload_note = " Latest trace uploaded to the private GitHub trace repository."
                if upload_url:
                    upload_note += f" {upload_url}"
            else:
                upload_error = str(upload_result.get("error") or "Unknown upload error").strip()
                upload_note = (
                    " GitHub trace upload failed; the local trace is still saved. "
                    f"{upload_error}"
                )
        self.status_var.set(
            f"Finished {action} with {model_name}.{location_note}{rewrite_note}"
            f"{trace_note}{upload_note} Edit the output or save it."
        )
        self._update_controls()

    def _write_stopped(self) -> None:
        # Keep any words already streamed. If none arrived before Stop was
        # pressed, restore the document that was open before generation.
        if not self._generation_had_chunks:
            self._restore_pre_generation_output()
        self._finish_stopped()

    def _finish_stopped(self) -> None:
        was_rewrite = getattr(self, "_generation_mode", "write") == "rewrite"
        if was_rewrite:
            self._restore_pre_generation_output()
        self.busy = False
        self.writing = False
        self.loaded_model = None
        self.stop_requested = False
        partial_text = self._output_text()
        self._set_output_text(partial_text)
        if was_rewrite:
            self.status_var.set(
                "Rewrite stopped. The previous draft was restored. "
                "Load the model again before continuing."
            )
        else:
            self.status_var.set(
                "Writing stopped. Partial text is kept. Load the model again to continue."
            )
        self._update_controls()

    def _write_failed(self, message: str) -> None:
        if self.stop_requested:
            self._write_stopped()
            return
        self._restore_pre_generation_output()
        self.busy = False
        self.writing = False
        try:
            still_loaded = self.engine.child is not None and self.engine.child.isalive()
        except Exception:
            still_loaded = False
        if not still_loaded:
            self.loaded_model = None
        self.stop_requested = False
        self.status_var.set("Writing failed. Reload the model if it is no longer loaded.")
        self._update_controls()
        self._showerror("Writing failed", message)

    def _output_text(self) -> str:
        return text_widget_to_markdown(self.output_box)

    def _set_output_text(self, text: str) -> None:
        plain, spans = markdown_to_rich_text(text)
        self.output_box.delete("1.0", "end")
        self.output_box.insert("1.0", plain)
        for tag in ("sb_bold", "sb_italic", "sb_bold_italic"):
            try:
                self.output_box.tag_remove(tag, "1.0", "end")
            except (AttributeError, tk.TclError):
                pass
        for start, end, style in spans:
            try:
                self.output_box.tag_add(
                    f"sb_{style}",
                    f"1.0 + {start} chars",
                    f"1.0 + {end} chars",
                )
            except (AttributeError, tk.TclError):
                pass
        self.output_box.edit_modified(False)
        self._update_document_title()
        self._update_check_draft_control()

    def _on_output_modified(self, _event=None) -> None:
        if self.output_box.edit_modified():
            self.output_box.edit_modified(False)
            self._update_document_title()
            self._update_check_draft_control()

    def _update_check_draft_control(self) -> None:
        button = getattr(self, "check_draft_button", None)
        if button is None:
            return
        has_draft = bool(self._output_text().strip()) if hasattr(self, "output_box") else False
        button.configure(
            state="normal" if not getattr(self, "busy", False) and has_draft else "disabled"
        )

    def check_draft(self) -> None:
        """Run a manual, advisory check against the current Output text only."""
        if getattr(self, "busy", False):
            return
        original = self._output_text()
        if not original.strip():
            self.status_var.set("There is no draft text to check.")
            self._update_check_draft_control()
            return

        findings = analyze_draft(original)
        report = format_draft_health_report(findings)
        count = len(findings)
        self.status_var.set(
            "Draft check complete: "
            + (f"{count} possible finding(s)." if count else "no obvious mechanical issues found.")
            + " No text was changed."
        )
        self._showinfo("Draft Check", report)

    def _update_document_title(self) -> None:
        label = self.current_file.name if self.current_file is not None else "Untitled"
        dirty = self._output_text() != self.saved_output_text
        marker = "*" if dirty else ""
        if hasattr(self, "root"):
            self.root.title(f"StoryBuilder Minimal Writer - {label}{marker}")

    def _confirm_save_pending_changes(self) -> bool:
        if self._output_text() == self.saved_output_text:
            return True
        choice = self._askyesnocancel(
            "Unsaved changes",
            "Save changes to the current text before continuing?",
        )
        if choice is None:
            return False
        if choice:
            return self.save_output()
        return True

    def open_text(self) -> None:
        if self.busy:
            return
        options = {
            "title": "Open document",
            "filetypes": [
                ("LibreOffice Writer documents", "*.odt"),
                ("Plain text documents", "*.txt"),
            ],
        }
        if self.current_file is not None:
            options["initialdir"] = str(self.current_file.parent)
        filename = filedialog.askopenfilename(**options)
        if not filename:
            return

        try:
            text = read_document(filename)
        except (OSError, UnicodeError, ValueError) as exc:
            self._showerror("Could not open document", str(exc))
            return

        if not self._confirm_save_pending_changes():
            return

        self.current_file = Path(filename).expanduser().resolve()
        self.selected_scene_source = None
        self.saved_output_text = text
        self._set_output_text(text)
        self.status_var.set(f"Opened: {self.current_file}")
        self._update_document_title()

    def save_output(self) -> bool:
        if self.busy:
            return False
        if self.current_file is None:
            return self.save_output_as()
        return self._save_to_path(self.current_file)

    def save_output_as(self) -> bool:
        if self.busy:
            return False
        source_path = self.current_file or self.selected_scene_source
        default_name = (
            source_path.with_suffix(".odt").name
            if source_path is not None else "draft.odt"
        )
        options = {
            "title": "Save document as",
            "defaultextension": ".odt",
            "filetypes": [
                ("LibreOffice Writer documents", "*.odt"),
                ("Plain text documents", "*.txt"),
            ],
            "initialfile": default_name,
        }
        if self.current_file is not None:
            options["initialdir"] = str(self.current_file.parent)
        filename = filedialog.asksaveasfilename(**options)
        if not filename:
            return False
        return self._save_to_path(Path(filename))

    def _finish_saved_scene_state_update(
        self,
        novel_name: str,
        chapter_number: int,
        scene_number: int,
        story_time: str,
        error: str | None,
        reset_error: str | None,
    ) -> None:
        """Report the result of the optional post-save ending-state update."""
        self.busy = False
        self.writing = False
        self.stop_requested = False

        if error:
            message = (
                f"Saved new scene: {novel_name} / Chapter {chapter_number:02d} / "
                f"Scene {scene_number:02d}. The scene position was recorded, but "
                "the ending-state analysis failed; existing story details were preserved. "
                + str(error).splitlines()[0]
            )
        else:
            message = (
                f"Saved new scene and updated its ending state: {novel_name} / "
                f"Chapter {chapter_number:02d} / Scene {scene_number:02d}."
            )
            if story_time:
                message += f" Story time: {story_time}."

        if reset_error:
            try:
                child = getattr(self.engine, "child", None)
                if child is None or not child.isalive():
                    self.loaded_model = None
            except Exception:
                self.loaded_model = None
            message += (
                " The model session could not be cleared after the state update; "
                "reload the model before writing again."
            )

        self.status_var.set(message)
        self._update_controls()

    def _start_saved_scene_state_update(
        self,
        novel_path: str | Path,
        novel_name: str,
        chapter_number: int,
        scene_number: int,
        scene_text: str,
    ) -> None:
        """Record the saved scene, then update only its supported ending-state facts."""
        state_path = Path(novel_path).expanduser() / "current_state.json"
        try:
            current_state = load_current_state(state_path)
            marked_state = advance_saved_scene_markers(
                current_state, chapter_number, scene_number
            )
            write_current_state(state_path, marked_state)
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            self.status_var.set(
                f"Scene saved, but current_state.json could not be updated: {exc}"
            )
            self._update_controls()
            return

        model_path = getattr(self, "loaded_model", None)
        if model_path is None:
            self.status_var.set(
                f"Saved new scene: {novel_name} / Chapter {chapter_number:02d} / "
                f"Scene {scene_number:02d}. Scene progress was recorded; load a model "
                "to analyze the ending time and situation."
            )
            self._update_controls()
            return

        self.busy = True
        self.writing = False
        self.stop_requested = False
        self.status_var.set(
            f"Scene saved. Updating the story state from the ending of "
            f"Chapter {chapter_number:02d}, Scene {scene_number:02d}…"
        )
        self._update_controls()

        def work() -> None:
            error = None
            reset_error = None
            story_time = ""
            try:
                before_state = load_current_state(state_path)
                prompt = build_saved_scene_state_prompt(
                    before_state,
                    chapter_number,
                    scene_number,
                    scene_text,
                )
                # Use the already-loaded model, but isolate this short state task
                # from prior writing turns and clear its JSON response afterward.
                self.engine.clear_context()
                response = self.engine.generate(prompt)
                patch = parse_saved_scene_state_patch(
                    before_state,
                    response,
                    scene_characters=(
                        before_state.get("scene_cast")
                        if isinstance(before_state.get("scene_cast"), list)
                        else None
                    ),
                )
                updated_state = merge_saved_scene_state(
                    before_state,
                    patch,
                    chapter_number,
                    scene_number,
                )
                write_current_state(state_path, updated_state)
                story_time = str(updated_state.get("time_of_day", "") or "")
            except Exception as exc:
                error = str(exc)
            finally:
                try:
                    self.engine.clear_context()
                except Exception as exc:
                    reset_error = str(exc)

            try:
                self.root.after(
                    0,
                    lambda: self._finish_saved_scene_state_update(
                        novel_name,
                        chapter_number,
                        scene_number,
                        story_time,
                        error,
                        reset_error,
                    ),
                )
            except tk.TclError:
                pass

        threading.Thread(target=work, daemon=True).start()

    def save_new_scene(self) -> bool:
        """Save the current output as a new numbered ODT scene in the selected novel."""
        if self.busy:
            return False

        novel_name = self.novel_var.get().strip()
        novel_path = self.novel_packages.get(novel_name)
        if novel_path is None:
            self._showinfo("Choose a novel", "Select a novel before saving a scene.")
            return False

        chapter_label = self.chapter_var.get().strip()
        chapter_number = self.chapter_numbers.get(chapter_label)
        if chapter_number is None or int(chapter_number) < 1:
            self._showinfo(
                "Choose a chapter",
                "Select a chapter before saving a new scene.",
            )
            return False

        text = self._output_text()
        if not text.strip():
            self._showinfo("Nothing to save", "Write or open scene text before saving.")
            return False

        chapter_number = int(chapter_number)
        chapter_path = (
            Path(novel_path).expanduser()
            / "Manuscript"
            / "Chapters"
            / f"Chapter_{chapter_number:02d}"
        )
        try:
            chapter_path.mkdir(parents=True, exist_ok=True)
            saved_scenes = list_scene_files(novel_path, chapter_number)
        except OSError as exc:
            self._showerror("Could not prepare chapter folder", str(exc))
            return False

        saved_numbers = {number for number, _path in saved_scenes}
        requested_number = scene_number_from_label(self.scene_var.get().strip())
        if requested_number is None or requested_number in saved_numbers:
            # If the dropdown still points at an accepted scene (for example,
            # after restarting the app), append after the last saved scene.
            scene_number = max(saved_numbers, default=0) + 1
        else:
            # Prepare Scene normally selects the unsaved destination already.
            scene_number = requested_number

        while True:
            filename_stem = (
                f"Chapter_{chapter_number:02d}_Section_{scene_number:02d}"
            )
            target = chapter_path / f"{filename_stem}.odt"
            legacy_txt = chapter_path / f"{filename_stem}.txt"
            if not target.exists() and not legacy_txt.exists():
                break
            scene_number += 1

        scene_label = f"Scene {scene_number:02d}"
        self.scene_var.set(scene_label)
        try:
            saved_path = save_document(target, text)
        except (OSError, UnicodeError, ValueError) as exc:
            self._showerror("Could not save new scene", str(exc))
            return False

        self.selected_scene_source = saved_path
        if self.current_file is None:
            self.saved_output_text = text

        # Refresh the scene list and leave the newly saved scene selected.
        self._on_chapter_selected()
        self.scene_var.set(scene_label)
        self.selected_scene_source = saved_path
        self._update_document_title()
        self._update_controls()
        self._start_saved_scene_state_update(
            novel_path,
            novel_name,
            chapter_number,
            scene_number,
            text,
        )
        return True

    def save_to_selected_scene(self) -> bool:
        """Overwrite the selected existing scene only after explicit confirmation."""
        if self.busy:
            return False
        if self.selected_scene_source is None:
            self._showinfo(
                "Load a scene first",
                "Use Load Scene Copy before saving directly to a novel scene.",
            )
            return False

        target = self.scene_files.get(self.scene_var.get().strip())
        if target is None:
            self._showinfo(
                "Choose a scene",
                "Select the existing novel scene you want to replace.",
            )
            return False

        target = target.expanduser().resolve()
        if not target.is_file():
            self._showerror(
                "Scene file unavailable",
                f"The selected scene file no longer exists:\n\n{target}",
            )
            return False

        loaded_source = self.selected_scene_source.expanduser().resolve()
        warning = (
            "This will replace the contents of this existing scene file with "
            "the text currently in the editor:\n\n"
            f"{target}\n\n"
            "This action changes that file. Cancel to leave it untouched. "
            "The ordinary Save button will still open Save As."
        )
        if loaded_source != target:
            warning += (
                "\n\nNote: this is different from the scene originally loaded:\n"
                f"{loaded_source}"
            )

        if not self._askyesno(
            "Confirm scene overwrite", warning
        ):
            self.status_var.set("Save to Selected Scene cancelled; no file changed.")
            return False

        # Recheck after the confirmation dialog so a removed target is not
        # accidentally recreated by write_text().
        if not target.is_file():
            self._showerror(
                "Scene file unavailable",
                f"The selected scene file no longer exists:\n\n{target}",
            )
            return False

        text = self._output_text()
        try:
            saved_path = save_document(target, text)
        except (OSError, UnicodeError, ValueError) as exc:
            self._showerror("Could not save scene document", str(exc))
            return False

        # Do not attach the ordinary Save button to the manuscript target.
        # The next ordinary Save must still use Save As.
        self.current_file = None
        self.selected_scene_source = saved_path
        self.saved_output_text = text
        self.status_var.set(
            f"Saved selected scene: {saved_path}. Ordinary Save still opens Save As."
        )
        self._update_document_title()
        return True

    def _save_to_path(self, path: str | Path) -> bool:
        text = self._output_text()
        try:
            saved_path = save_document(path, text)
        except (OSError, UnicodeError, ValueError) as exc:
            self._showerror("Could not save document", str(exc))
            return False

        self.current_file = saved_path
        self.selected_scene_source = None
        self.saved_output_text = text
        self.status_var.set(f"Saved: {saved_path}")
        self._update_document_title()
        return True

    def _update_controls(self) -> None:
        idle = not self.busy
        self.model_picker.configure(state="readonly" if idle else "disabled")
        self.refresh_button.configure(state="normal" if idle else "disabled")
        if hasattr(self, "novel_picker"):
            self.novel_picker.configure(state="readonly" if idle else "disabled")
            self.refresh_novels_button.configure(state="normal" if idle else "disabled")
            self.chapter_picker.configure(state="readonly" if idle else "disabled")
            self.scene_picker.configure(state="readonly" if idle else "disabled")
            self.load_scene_button.configure(
                state=(
                    "normal"
                    if idle and self.scene_var.get().strip() in self.scene_files
                    else "disabled"
                )
            )
            self.sync_novel_button.configure(
                state=(
                    "normal"
                    if idle and self.novel_var.get().strip() in self.novel_packages
                    else "disabled"
                )
            )
            if hasattr(self, "assemble_chapter_button"):
                selected_novel_path = self.novel_packages.get(
                    self.novel_var.get().strip()
                )
                selected_chapter = self.chapter_numbers.get(
                    self.chapter_var.get().strip()
                )
                has_chapter_scenes = bool(
                    selected_novel_path is not None
                    and selected_chapter is not None
                    and list_scene_files(selected_novel_path, selected_chapter)
                )
                has_novel_scenes = bool(
                    selected_novel_path is not None
                    and any(
                        list_scene_files(selected_novel_path, chapter_number)
                        for chapter_number in self.chapter_numbers.values()
                    )
                )
                self.assemble_chapter_button.configure(
                    state="normal" if idle and has_chapter_scenes else "disabled"
                )
                self.assemble_novel_button.configure(
                    state="normal" if idle and has_novel_scenes else "disabled"
                )
        self.load_button.configure(state="normal" if idle else "disabled")
        if hasattr(self, "prepare_scene_button"):
            has_selected_novel = (
                self.novel_var.get().strip() in self.novel_packages
            )
            self.prepare_scene_button.configure(
                state=(
                    "normal"
                    if idle and self.loaded_model is not None and has_selected_novel
                    else "disabled"
                )
            )
        self.write_button.configure(
            state="normal" if idle and self.loaded_model is not None else "disabled"
        )
        if hasattr(self, "rewrite_scene_button"):
            self.rewrite_scene_button.configure(
                state="normal" if idle and self.loaded_model is not None else "disabled"
            )
        self.continue_button.configure(
            state="normal" if idle and self.loaded_model is not None else "disabled"
        )
        self.new_session_button.configure(
            state="normal" if idle and self.loaded_model is not None else "disabled"
        )
        self.open_button.configure(state="normal" if idle else "disabled")
        self.save_button.configure(state="normal" if idle else "disabled")
        self.save_as_button.configure(state="normal" if idle else "disabled")
        has_scene_destination = (
            self.novel_var.get().strip() in self.novel_packages
            and self.chapter_var.get().strip() in self.chapter_numbers
        )
        if hasattr(self, "save_new_scene_button"):
            self.save_new_scene_button.configure(
                state="normal" if idle and has_scene_destination else "disabled"
            )
        self.save_scene_button.configure(
            state=(
                "normal"
                if idle
                and self.selected_scene_source is not None
                and self.scene_var.get().strip() in self.scene_files
                else "disabled"
            )
        )
        self.revise_selection_button.configure(state="normal" if idle else "disabled")
        self._update_check_draft_control()
        stopping = self.stop_requested
        self.stop_button.configure(
            state="normal" if self.busy and self.writing and not stopping else "disabled",
            text=(
                "Stopping…" if stopping
                else "Stop Preparing" if getattr(self, "_preparing_scene", False)
                else "Stop Writing"
            ),
        )

    def close(self) -> None:
        if self.busy:
            self._showinfo(
                "Model is busy",
                "Wait for the current model task to finish before closing.",
            )
            return
        if not self._confirm_save_pending_changes():
            return
        try:
            self.engine.stop()
        finally:
            self.root.destroy()


def main() -> None:
    root = tk.Tk()
    MinimalWriterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
