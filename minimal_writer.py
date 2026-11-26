from __future__ import annotations

import json
import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText

from builder.appearance import apply_application_appearance
from builder.creative_direction import build_creative_direction_prompt
from builder.writer_engine import GenerationInterrupted, WriterEngine
from builder.openrouter import (
    RoutedWriterEngine,
    delete_openrouter_api_key,
    fetch_openrouter_free_models,
    has_openrouter_api_key,
    is_openrouter_selection,
    load_cached_openrouter_models,
    load_openrouter_api_key,
    openrouter_model_selection,
    save_cached_openrouter_models,
    save_openrouter_api_key,
    selected_openrouter_model_id,
)
from builder.workspace import MODELS_DIR, NOVEL_ROOT
from builder.continuity_context import relevance_tokens, select_relevant_locations
from builder.character_context import (
    build_character_card_context_prompt,
    build_scene_cast_boundary_prompt,
    build_scene_relevant_story_bible_reference_context,
    build_story_bible_reference_context,
    load_character_card_names,
)
from builder.story_bible_reader import load_story_bible
from builder.story_timeline import build_story_timeline_prompt
from builder.scene_preparation import (
    apply_author_required_beats,
    build_scene_preparation_prompt,
    resolve_scene_preparation_target,
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
from builder.prompt_trace import (
    PromptTrace, default_prompt_trace_path, load_prompt_trace_enabled,
)
from builder.prompt_trace_sync import upload_prompt_trace
from builder.model_preferences import (
    load_model_roles,
    resolve_model_roles,
    save_model_roles,
)
from builder.scene_state_update import (
    advance_saved_scene_markers,
    advance_to_next_chapter,
    build_saved_scene_state_prompt,
    load_current_state,
    merge_saved_scene_state,
    parse_saved_scene_state_patch,
    write_current_state,
)
from builder.writer_continuity import build_previous_scene_context_prompt


CONTINUE_PROMPT = (
    "Continue the current passage from where it ended. "
    "Write only new material, without repeating the text already written. "
    "Write a complete continuation of several connected paragraphs, developing the moment "
    "rather than stopping after a single paragraph. Follow where the story leads."
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
        "Treat this as supplementary guidance for the same scene, not a replacement "
        "scene plan or a request to prepare or advance to another scene. Use it to refine "
        "or add detail while preserving the existing scene's location, characters, intended "
        "events unless the author explicitly asks to change them. "
        "Write a complete replacement scene as natural manuscript prose only."
    )


def build_author_required_direction_prompt(
    prompt: str,
    author_direction: str,
) -> str:
    """Carry the author's original requested events into the Writer as mandatory."""
    original = str(prompt or "").rstrip()
    direction = str(author_direction or "").strip()
    if not direction:
        return original
    if direction in original:
        direction_reference = (
            "The original direction is already included above. Use that exact text as "
            "the authoritative source; do not reinterpret it as optional."
        )
    else:
        direction_reference = "ORIGINAL AUTHOR'S DIRECTION\n" + direction

    requirements = (
        "AUTHOR PRIORITY: REQUIRED EVENTS AND BEATS\n"
        + direction_reference
        + "\n\nEvery concrete event, action, or moment the author explicitly requests "
        "must actually happen in this scene. Do not merely mention it, imply it happened "
        "off-page, substitute another event, omit it, or defer it to a later scene. "
        "The original author direction remains authoritative even if the Planner's "
        "summary leaves something out or phrases it weakly. Preserve the author's other "
        "stated boundaries and preferences too.\n\n"
        "QWEN'S ADDITIONAL BEATS\n"
        "These are secondary creative additions, not authority over the author. Include "
        "only additions that fit naturally and are fully compatible with every part and "
        "the requested order of the original Author's Direction, the selected Scene Cast, "
        "and fixed canon. Do not use an additional beat to repeat, replace, reorder, "
        "weaken, delay, or contradict an author-requested event. If an additional beat "
        "conflicts with the author's direction or cast selection, omit that beat. "
        "Compatible additions may enrich the scene, but they are never a reason to change "
        "what the author asked to happen."
    )
    return f"{original}\n\n{requirements}" if original else requirements


def build_single_scene_scope_prompt(
    prompt: str,
    chapter_number: int | None = None,
    scene_number: int | None = None,
) -> str:
    """Keep one manuscript generation focused on its selected scene."""
    destination = "one manuscript scene"
    if chapter_number is not None and scene_number is not None:
        try:
            destination = (
                f"Chapter {int(chapter_number):02d}, Scene {int(scene_number):02d}"
            )
        except (TypeError, ValueError):
            pass

    scope = (
        "ONE-SCENE SCOPE\n"
        f"Write only {destination}.\n"
        "Keep the prose within that single scene. Do not combine distinct time/place "
        "setups that function as separate scenes, start a second scene, add a second "
        "scene heading, or use a scene break to jump ahead. Treat a later, separate "
        "scene setup as material for a future generation unless the author explicitly "
        "asks to include it in this same scene. Let this scene unfold and end naturally; "
        "do not force a prescribed ending or checklist."
    )
    original = str(prompt or "").rstrip()
    return f"{original}\n\n{scope}" if original else scope


def scene_coordinates_from_prompt(prompt: str) -> tuple[int, int] | None:
    """Read an explicit Chapter NN, Scene NN heading from a prepared scene prompt.

    The prompt heading is more authoritative than the scene picker when an
    unsaved prepared scene is being rewritten or the picker has fallen back to
    the last saved scene after an app restart.
    """
    header_pattern = re.compile(
        r"^\s*(?:#+\s*)?(?:Scene direction:\s*)?"
        r"Chapter\s+(\d+)\s*[,;]\s*Scene\s+(\d+)\b",
        re.IGNORECASE,
    )
    for line in str(prompt or "").splitlines()[:5]:
        match = header_pattern.match(line.strip())
        if match:
            chapter_number, scene_number = map(int, match.groups())
            if chapter_number >= 1 and scene_number >= 1:
                return chapter_number, scene_number
    return None


def resolve_generation_scene_destination(
    prompt: str,
    selected_chapter: int | None,
    selected_scene_label: str | None,
) -> tuple[int, int] | None:
    """Prefer the explicit scene named in the prompt over a stale UI selection."""
    explicit_destination = scene_coordinates_from_prompt(prompt)
    if explicit_destination is not None:
        return explicit_destination
    scene_number = scene_number_from_label(selected_scene_label)
    if selected_chapter is None or scene_number is None:
        return None
    chapter_number = int(selected_chapter)
    if chapter_number < 1:
        return None
    return chapter_number, int(scene_number)


def build_location_context_prompt(
    prompt: str,
    locations: dict,
    supporting_text: str = "",
) -> tuple[str, list[str]]:
    """Add brief details only for saved locations named in the current scene."""
    query = "\n".join(
        part for part in (str(prompt or ""), str(supporting_text or "")) if part
    )
    selected = select_relevant_locations(locations, "", query)
    if not selected:
        return str(prompt or ""), []

    lines = ["BRIEF DETAILS FOR PLACES NAMED IN THIS SCENE"]
    for name, details in selected.items():
        if isinstance(details, str):
            values = [("Description", details)]
        else:
            values = [
                (label, details.get(field))
                for field, label in (
                    ("type", "Type"),
                    ("description", "Description"),
                    ("notable_details", "Notable details"),
                )
                if details.get(field) not in (None, "", [], {})
            ]

        place_lines = []
        remaining = 650
        for label, value in values:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            value = " ".join(str(value).split())
            if not value or remaining <= 0:
                continue
            if len(value) > remaining:
                value = value[: max(0, remaining - 1)].rstrip() + "…"
            place_lines.append(f"{label}: {value}")
            remaining -= len(value)
        if place_lines:
            lines.append(f"\n[{name}]")
            lines.extend(place_lines)

    if len(lines) == 1:
        return str(prompt or ""), list(selected)
    context = "\n".join(lines)
    base_prompt = str(prompt or "").rstrip()
    enriched = f"{base_prompt}\n\n{context}" if base_prompt else context
    return enriched, list(selected)


def _scene_context_is_relevant(candidate: str, scene_text: str) -> bool:
    """Keep only handoff notes with a clear name or vocabulary connection to this scene."""
    value = " ".join(str(candidate or "").split())
    query = " ".join(str(scene_text or "").split())
    if not value or not query:
        return False
    if value.casefold() in query.casefold() or query.casefold() in value.casefold():
        return True
    return len(relevance_tokens(value) & relevance_tokens(query)) >= 2


def _short_context_text(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    shortened = text[: max(1, limit - 1)].rsplit(" ", 1)[0].rstrip()
    return shortened + "…"


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
        self.engine = RoutedWriterEngine()
        self.models: dict[str, Path | str] = {}
        self.loaded_model: Path | str | None = None
        self.current_file: Path | None = None
        self.selected_scene_source: Path | None = None
        self.saved_output_text = ""
        self.novel_packages: dict[str, Path] = {}
        self._active_novel_path: Path | None = None
        self.last_location_context_names: list[str] = []
        self._scene_cast_names: list[str] | None = None
        self._scene_cast_novel_path: Path | None = None
        self._scene_cast_destination: tuple[int, int] | None = None
        self._scene_preparation_destination = (1, 1)
        self._scene_preparation_original_prompt = ""
        self._scene_preparation_original_author_direction = ""
        self._scene_preparation_novel_path: Path | None = None
        self._scene_preparation_source_scene_path: Path | None = None
        self._prepared_scene_destination: tuple[int, int] | None = None
        self._prepared_scene_novel_path: Path | None = None
        self._prepared_scene_source_scene_path: Path | None = None
        self._prepared_author_required_direction = ""
        self._scene_preparation_required_author_direction = ""
        self._pending_scene_prompt_trace = None
        self._active_scene_preparation_trace = None
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
        self._last_prompt_trace_path = str(default_prompt_trace_path())
        self._last_prompt_trace_upload_result = None
        self._trace_upload_busy = False

        root.title("StoryBuilder Minimal Writer - Untitled")
        root.geometry("1080x820")
        root.minsize(760, 600)
        root.protocol("WM_DELETE_WINDOW", self.close)
        apply_application_appearance(root)

        # The existing selector is the manuscript-writing model.
        self.model_var = tk.StringVar()
        self.planner_model_var = tk.StringVar()
        self.status_var = tk.StringVar(
            value="Choose separate models for Prepare Scene and manuscript writing."
        )
        self.scene_cast_summary_var = tk.StringVar(
            value="Not selected. Choose who may appear in this scene."
        )
        self.activity_task_var = tk.StringVar(value="Idle")
        self.activity_model_var = tk.StringVar(value="None loaded")
        self.activity_state_var = tk.StringVar(value="Not loaded")
        self._activity_model_path: Path | None = None
        self._build_widgets()
        self.refresh_models()
        self.refresh_novels()

    def _build_widgets(self) -> None:
        # Keep the complete writing form accessible on shorter laptop displays.
        # The canvas scrolls the form; the text editors retain their own internal
        # scrollbars for navigating longer prompt and manuscript content.
        page = ttk.Frame(self.root)
        page.pack(fill="both", expand=True)

        style = ttk.Style(self.root)
        canvas_background = style.lookup("TFrame", "background") or self.root.cget("background")
        self.main_canvas = tk.Canvas(
            page,
            borderwidth=0,
            highlightthickness=0,
            background=canvas_background,
        )
        self.main_scrollbar = ttk.Scrollbar(
            page, orient="vertical", command=self.main_canvas.yview
        )
        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)
        self.main_scrollbar.pack(side="right", fill="y")
        self.main_canvas.pack(side="left", fill="both", expand=True)

        outer = ttk.Frame(self.main_canvas, padding=12)
        self._main_canvas_window = self.main_canvas.create_window(
            (0, 0), window=outer, anchor="nw"
        )

        def update_scroll_region(_event=None) -> None:
            self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

        def fit_content_width(event) -> None:
            self.main_canvas.itemconfigure(
                self._main_canvas_window, width=max(1, event.width)
            )

        outer.bind("<Configure>", update_scroll_region)
        self.main_canvas.bind("<Configure>", fit_content_width)

        planner_model_row = ttk.Frame(outer)
        planner_model_row.pack(fill="x", pady=(0, 4))

        ttk.Label(planner_model_row, text="Prepare Scene model", width=20).pack(
            side="left", padx=(0, 8)
        )
        self.planner_model_picker = ttk.Combobox(
            planner_model_row,
            textvariable=self.planner_model_var,
            state="readonly",
            width=56,
        )
        self.planner_model_picker.pack(side="left", fill="x", expand=True)
        self.planner_model_picker.bind(
            "<<ComboboxSelected>>", self._on_planner_model_selected
        )

        writer_model_row = ttk.Frame(outer)
        writer_model_row.pack(fill="x", pady=(0, 2))

        ttk.Label(writer_model_row, text="Writing model", width=20).pack(
            side="left", padx=(0, 8)
        )
        self.model_picker = ttk.Combobox(
            writer_model_row,
            textvariable=self.model_var,
            state="readonly",
            width=56,
        )
        self.model_picker.pack(side="left", fill="x", expand=True)
        self.model_picker.bind(
            "<<ComboboxSelected>>", self._on_writer_model_selected
        )

        self.refresh_button = ttk.Button(
            writer_model_row, text="Refresh", command=self.refresh_models
        )
        self.refresh_button.pack(side="left", padx=(8, 0))
        self.openrouter_button = ttk.Button(
            writer_model_row,
            text="OpenRouter Settings",
            command=self.open_openrouter_settings,
        )
        self.openrouter_button.pack(side="left", padx=(8, 0))

        self.load_button = ttk.Button(
            writer_model_row, text="Load Writer", command=self.load_selected_model
        )
        self.load_button.pack(side="left", padx=(8, 0))

        ttk.Label(
            outer,
            text="Only the model needed for the selected task is loaded.",
        ).pack(anchor="w", pady=(0, 4))

        activity_frame = ttk.LabelFrame(
            outer, text="Current Activity", padding=(8, 6)
        )
        activity_frame.pack(fill="x", pady=(0, 10))
        for column, weight in enumerate((2, 3, 1)):
            activity_frame.columnconfigure(column, weight=weight)

        for column, (heading, variable) in enumerate(
            (
                ("Task", self.activity_task_var),
                ("Model for this task", self.activity_model_var),
                ("Runtime state", self.activity_state_var),
            )
        ):
            cell = ttk.Frame(activity_frame)
            cell.grid(row=0, column=column, sticky="nsew", padx=(0, 10))
            ttk.Label(cell, text=heading).pack(anchor="w")
            ttk.Label(
                cell,
                textvariable=variable,
                font=("TkDefaultFont", 10, "bold"),
                wraplength=340,
                justify="left",
            ).pack(anchor="w", fill="x")

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
        self.chapter_picker.pack(side="left", padx=(0, 6))
        self.chapter_picker.bind("<<ComboboxSelected>>", self._on_chapter_selected)
        self.new_chapter_button = ttk.Button(
            novel_row, text="New Chapter", command=self.create_next_chapter
        )
        self.new_chapter_button.pack(side="left", padx=(0, 12))

        ttk.Label(novel_row, text="Scene").pack(side="left", padx=(0, 6))
        self.scene_var = tk.StringVar()
        self.scene_picker = ttk.Combobox(
            novel_row, textvariable=self.scene_var, state="readonly", width=10
        )
        self.scene_picker.pack(side="left", padx=(0, 8))
        self.scene_picker.bind("<<ComboboxSelected>>", self._on_scene_selected)
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

        scene_cast_row = ttk.Frame(outer)
        scene_cast_row.pack(fill="x", pady=(0, 8))
        self.scene_cast_button = ttk.Button(
            scene_cast_row,
            text="Select Scene Cast",
            command=self.select_scene_cast,
        )
        self.scene_cast_button.pack(side="left", padx=(0, 8))
        ttk.Label(
            scene_cast_row,
            textvariable=self.scene_cast_summary_var,
            wraplength=760,
        ).pack(side="left", fill="x", expand=True)

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

        minimal_test_row = ttk.Frame(outer)
        minimal_test_row.pack(fill="x", pady=(0, 8))
        self.minimal_test_button = ttk.Button(
            minimal_test_row,
            text="Test Minimal Prompt",
            command=self.write_minimal_test,
        )
        self.minimal_test_button.pack(side="left", padx=(0, 8))
        self.full_context_button = ttk.Button(
            minimal_test_row,
            text="Write Full Context",
            command=self.write_full_context,
        )
        self.full_context_button.pack(side="left", padx=(0, 8))
        ttk.Label(
            minimal_test_row,
            text=(
                "Write uses compact scene-specific context. Minimal skips all automatic "
                "references; Full Context keeps the original broad context as a fallback."
            ),
            wraplength=760,
        ).pack(side="left", fill="x", expand=True)

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(0, 8))

        self.write_button = ttk.Button(
            actions, text="Write (Balanced)", command=self.write
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

        trace_controls = ttk.Frame(outer)
        trace_controls.pack(fill="x", pady=(0, 8))
        self.upload_trace_button = ttk.Button(
            trace_controls,
            text="Upload Prompt Trace",
            command=self.upload_latest_prompt_trace,
            state="disabled",
        )
        self.upload_trace_button.pack(side="left", padx=(0, 8))
        ttk.Label(
            trace_controls,
            text="Prompt traces stay on this computer until you choose to upload them.",
        ).pack(side="left", fill="x", expand=True)

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
                if self._selected_role_model("writer") is None:
                    self._showinfo(
                        "Choose a writing model",
                        "Select a writing model before asking the AI to revise the selected passage. "
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
        prompt = self._prepare_creative_direction_context(prompt)
        writer_model = self._selected_role_model("writer")
        if writer_model is None:
            self._showinfo("Choose a writing model", "Select a model for manuscript writing first.")
            return

        self.busy = True
        self.writing = True
        self.stop_requested = False
        self.status_var.set(f"Revising selected text with {self._activity_model_label(writer_model)}…")
        self._begin_model_activity("Revise Passage", writer_model)
        try:
            self.output_box.configure(state="disabled")
        except tk.TclError:
            pass
        self._update_controls()

        def work() -> None:
            try:
                self._ensure_model_loaded(writer_model)
                self._schedule_activity_status(
                    "Revise Passage", writer_model, "Generating"
                )
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
        self._set_activity_status(
            "Revise Passage", getattr(self, "_activity_model_path", None), "Stopped"
        )
        self.status_var.set(
            "Revision stopped. The original passage was kept. The selected writing model will load automatically next time."
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
        self._set_activity_status(
            "Revise Passage", getattr(self, "_activity_model_path", None), "Error"
        )
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
        self._set_activity_status(
            "Revise Passage", getattr(self, "_activity_model_path", None), "Finished"
        )
        self._update_controls()

        candidate = answer.strip()
        if not candidate:
            self._discard_revision()
            self._set_activity_status(
                "Revise Passage", getattr(self, "_activity_model_path", None), "Error"
            )
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

    def open_openrouter_settings(self) -> None:
        """Manage the remote API key and refresh the cached free-model catalogue."""
        if self.busy:
            return

        window = tk.Toplevel(self.root)
        window.title("OpenRouter Settings")
        window.geometry("650x340")
        window.minsize(520, 300)
        window.transient(self.root)

        outer = ttk.Frame(window, padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(
            outer,
            text=(
                "OpenRouter model access is optional. Your local GGUF models remain "
                "available and continue running on this computer."
            ),
            wraplength=600,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            outer,
            text=(
                "Remote-use privacy: the current prompt, relevant Story Bible/context "
                "included by StoryBuilder, and generated response are sent through "
                "OpenRouter to the selected model provider. Review the provider's "
                "privacy terms and keep strictly local material out of remote prompts."
            ),
            wraplength=600,
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        ttk.Label(outer, text="OpenRouter API key").pack(anchor="w")
        key_row = ttk.Frame(outer)
        key_row.pack(fill="x", pady=(4, 8))
        key_var = tk.StringVar()
        key_entry = ttk.Entry(key_row, textvariable=key_var, show="*", width=52)
        key_entry.pack(side="left", fill="x", expand=True)
        ttk.Label(
            outer,
            text=(
                "Get a key at openrouter.ai/keys. A saved key stays in your user "
                "configuration folder with owner-only file permissions. "
                "OPENROUTER_API_KEY can also be used instead."
            ),
            wraplength=600,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        status_var = tk.StringVar(
            value=(
                "An API key is configured."
                if has_openrouter_api_key()
                else "No API key configured yet."
            )
        )
        ttk.Label(
            outer, textvariable=status_var, wraplength=600, justify="left"
        ).pack(anchor="w", pady=(0, 10))

        button_row = ttk.Frame(outer)
        button_row.pack(fill="x", side="bottom")
        refresh_button = ttk.Button(button_row, text="Save Key & Refresh Free Models")
        refresh_button.pack(side="left")
        remove_button = ttk.Button(button_row, text="Remove Saved Key")
        remove_button.pack(side="left", padx=(8, 0))
        ttk.Button(button_row, text="Close", command=window.destroy).pack(
            side="right"
        )

        def refresh_catalog() -> None:
            entered_key = key_var.get().strip()
            if entered_key:
                try:
                    save_openrouter_api_key(entered_key)
                except (OSError, ValueError) as exc:
                    self._showerror("Could not save OpenRouter key", str(exc))
                    return
                key_var.set("")

            api_key = load_openrouter_api_key()
            if not api_key:
                status_var.set(
                    "Add an OpenRouter API key first, then refresh the free-model list."
                )
                return

            refresh_button.configure(state="disabled")
            status_var.set("Contacting OpenRouter and refreshing the free-model list…")

            def refresh_failed(message: str) -> None:
                try:
                    refresh_button.configure(state="normal")
                except tk.TclError:
                    return
                status_var.set(
                    "The model list could not be refreshed. The previous cache was kept."
                )
                self._showerror("OpenRouter refresh failed", message)

            def refresh_succeeded(models: list[dict[str, str]]) -> None:
                try:
                    refresh_button.configure(state="normal")
                    self.refresh_models()
                except tk.TclError:
                    return
                free_count = sum(
                    1 for item in models if str(item.get("id", "")).endswith(":free")
                )
                status_var.set(
                    f"Model list refreshed. {free_count} pinned free models plus "
                    "the automatic free-model router are available in both selectors."
                )

            def work() -> None:
                try:
                    models = fetch_openrouter_free_models(api_key)
                    save_cached_openrouter_models(models)
                except Exception as exc:
                    message = str(exc)
                    self.root.after(
                        0, lambda message=message: refresh_failed(message)
                    )
                else:
                    self.root.after(
                        0, lambda models=models: refresh_succeeded(models)
                    )

            threading.Thread(target=work, daemon=True).start()

        def remove_key() -> None:
            try:
                delete_openrouter_api_key()
            except OSError as exc:
                self._showerror("Could not remove saved key", str(exc))
                return
            self.refresh_models()
            status_var.set(
                "Saved key removed. Any OPENROUTER_API_KEY environment variable remains active."
                if has_openrouter_api_key()
                else "Saved OpenRouter key removed. Local models are unchanged."
            )

        refresh_button.configure(command=refresh_catalog)
        remove_button.configure(command=remove_key)
        key_entry.focus_set()

    def refresh_models(self) -> None:
        """Refresh local GGUF files and append the last cached OpenRouter free catalogue."""
        try:
            paths = WriterEngine.available_models()
        except Exception as exc:
            self.status_var.set(f"Could not list local models: {exc}")
            return

        previous_writer = self.model_var.get().strip()
        previous_planner = self.planner_model_var.get().strip()
        local_models = {path.name: path for path in paths}
        self.models = dict(local_models)
        self.openrouter_models = load_cached_openrouter_models()
        self.openrouter_model_labels: dict[str, str] = {}

        if has_openrouter_api_key():
            for item in self.openrouter_models:
                model_id = str(item.get("id") or "").strip()
                if not model_id:
                    continue
                label = f"OpenRouter · {item.get('name') or model_id} [{model_id}]"
                selection = openrouter_model_selection(model_id)
                self.models[label] = selection
                self.openrouter_model_labels[model_id] = label

        names = list(self.models)
        self.model_picker.configure(values=names)
        self.planner_model_picker.configure(values=names)

        saved_roles = load_model_roles()
        defaults = resolve_model_roles(list(local_models), saved_roles)

        def restored_selection(role: str, previous: str, default: str) -> str:
            if previous in self.models:
                return previous
            saved = str(saved_roles.get(role) or "").strip()
            if is_openrouter_selection(saved):
                return next(
                    (
                        label for label, value in self.models.items()
                        if value == saved
                    ),
                    default,
                )
            if saved in local_models:
                return saved
            return default

        self.model_var.set(
            restored_selection("writer", previous_writer, defaults["writer"])
        )
        self.planner_model_var.set(
            restored_selection("planner", previous_planner, defaults["planner"])
        )

        if not names:
            self.status_var.set(f"No GGUF models found in {MODELS_DIR}.")
        elif not self.openrouter_model_labels and not has_openrouter_api_key():
            self.status_var.set(
                "Local models are ready. Add an OpenRouter key in OpenRouter Settings "
                "to enable optional remote models."
            )
        self._update_controls()

    def _selected_role_model(self, role: str) -> Path | str | None:
        """Resolve the selected local path or OpenRouter ID for one model role."""
        if role == "planner":
            variable = getattr(self, "planner_model_var", None)
        elif role == "writer":
            variable = getattr(self, "model_var", None)
        else:
            raise ValueError(f"Unknown model role: {role}")
        if variable is None:
            return getattr(self, "loaded_model", None)
        return getattr(self, "models", {}).get(variable.get().strip())

    def _ensure_model_loaded(self, model_path: str | Path) -> str | Path:
        """Load the selected local or remote model, replacing the previous backend."""
        target: str | Path
        if is_openrouter_selection(model_path):
            target = str(model_path)
        else:
            target = Path(model_path).expanduser().resolve()

        if getattr(self, "loaded_model", None) == target:
            if not hasattr(self.engine, "child"):
                return target
            child = getattr(self.engine, "child", None)
            try:
                if child is not None and child.isalive():
                    return target
            except Exception:
                pass
        load_model_for_writing(self.engine, target)
        self.loaded_model = target
        return target

    def _runtime_model_is_ready(self, model_path: str | Path | None) -> bool:
        """Return true only when this exact local or remote model is configured."""
        if model_path is None:
            return False
        if is_openrouter_selection(model_path):
            target: str | Path = str(model_path)
            if getattr(self, "loaded_model", None) != target:
                return False
        else:
            try:
                target = Path(model_path).expanduser().resolve()
                loaded = getattr(self, "loaded_model", None)
                if loaded is None or (
                    is_openrouter_selection(loaded)
                    or Path(loaded).expanduser().resolve() != target
                ):
                    return False
            except (OSError, TypeError, ValueError):
                return False

        engine = getattr(self, "engine", None)
        if engine is None or not hasattr(engine, "child"):
            return True
        child = getattr(engine, "child", None)
        try:
            return child is not None and child.isalive()
        except Exception:
            return False

    @staticmethod
    def _activity_model_label(model_path: str | Path | None) -> str:
        if model_path is None:
            return "None loaded"
        if is_openrouter_selection(model_path):
            name = f"OpenRouter · {selected_openrouter_model_id(str(model_path))}"
        else:
            name = Path(model_path).name
            if "--" in name:
                name = name.rsplit("--", 1)[-1]
        if len(name) > 64:
            name = f"{name[:30]}…{name[-30:]}"
        return name

    def _set_activity_status(
        self,
        task: str,
        model_path: str | Path | None,
        state: str,
    ) -> None:
        """Update the prominent task/model/runtime display from the UI thread."""
        self._activity_model_path = (
            str(model_path)
            if is_openrouter_selection(model_path)
            else Path(model_path).expanduser().resolve()
            if model_path is not None
            else None
        )
        for attribute, value in (
            ("activity_task_var", str(task)),
            ("activity_model_var", self._activity_model_label(model_path)),
            ("activity_state_var", str(state)),
        ):
            variable = getattr(self, attribute, None)
            setter = getattr(variable, "set", None)
            if callable(setter):
                setter(value)

    def _begin_model_activity(self, task: str, model_path: str | Path) -> None:
        state = (
            "Generating"
            if self._runtime_model_is_ready(model_path)
            else "Loading"
        )
        self._set_activity_status(task, model_path, state)

    def _schedule_activity_status(
        self, task: str, model_path: str | Path | None, state: str
    ) -> None:
        """Schedule a status change safely when called from a worker thread."""
        try:
            self.root.after(
                0,
                lambda: self._set_activity_status(task, model_path, state),
            )
        except tk.TclError:
            pass

    def _refresh_idle_activity(self) -> None:
        """Show the actually loaded model while idle, not merely the selected model."""
        if getattr(self, "busy", False):
            return
        loaded = getattr(self, "loaded_model", None)
        if loaded is not None and self._runtime_model_is_ready(loaded):
            self._set_activity_status("Idle", loaded, "Ready")
        else:
            self.loaded_model = None
            self._set_activity_status("Idle", None, "Not loaded")

    def _role_selection_token(self, role: str) -> str:
        variable = (
            self.planner_model_var if role == "planner" else self.model_var
        )
        label = variable.get().strip()
        selected = getattr(self, "models", {}).get(label)
        if isinstance(selected, Path):
            return selected.name
        if is_openrouter_selection(selected):
            return str(selected)
        return label

    def _save_model_role_selection(self) -> None:
        try:
            save_model_roles(
                planner=self._role_selection_token("planner"),
                writer=self._role_selection_token("writer"),
            )
        except OSError as exc:
            self.status_var.set(
                f"Model selection is active, but could not be saved for next launch: {exc}"
            )

    def _on_planner_model_selected(self, _event=None) -> None:
        self._save_model_role_selection()
        name = self.planner_model_var.get().strip()
        if name:
            self.status_var.set(
                f"Prepare Scene will use {name}. It loads automatically when needed."
            )
        self._update_controls()
        self._refresh_idle_activity()

    def _on_writer_model_selected(self, _event=None) -> None:
        self._save_model_role_selection()
        name = self.model_var.get().strip()
        if name:
            self.status_var.set(
                f"Writing will use {name}. It loads automatically when needed."
            )
        self._update_controls()
        self._refresh_idle_activity()

    def load_selected_model(self) -> None:
        if self.busy:
            return
        path = self._selected_role_model("writer")
        if path is None:
            self._showinfo(
                "Choose a writing model",
                f"No writing model is selected. Check {MODELS_DIR} or configure OpenRouter.",
            )
            return

        self.busy = True
        self.writing = False
        self.stop_requested = False
        model_label = self._activity_model_label(path)
        self.status_var.set(f"Loading {model_label}…")
        self._set_activity_status("Load Writer", path, "Loading")
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

    def _load_succeeded(self, path: str | Path) -> None:
        self.busy = False
        self.writing = False
        self.stop_requested = False
        self.loaded_model = path
        label = self._activity_model_label(path)
        self._set_activity_status("Load Writer", path, "Ready")
        self.status_var.set(f"Loaded: {label}")
        self._update_controls()

    def _load_failed(self, message: str) -> None:
        self.busy = False
        self.writing = False
        self.stop_requested = False
        self.loaded_model = None
        self._set_activity_status(
            "Load Writer", getattr(self, "_activity_model_path", None), "Error"
        )
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

        # Preserve an existing selection, but never pick a novel automatically.
        selected = previous if previous in self.novel_packages else ""
        self.novel_var.set(selected)
        self._on_novel_selected()
        if not names:
            self.status_var.set(f"No novel packages found in {NOVEL_ROOT}.")
        elif not selected:
            self.status_var.set("Choose a novel to load its chapters and scenes.")
        self._update_controls()

    def _on_novel_selected(self, _event=None) -> None:
        """Populate chapter and scene pickers, isolating each model session by novel."""
        novel_path = self.novel_packages.get(self.novel_var.get().strip())
        self._handle_novel_context_change(novel_path)

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
            if novel_path is None:
                self.status_var.set("No novel selected. Choose a novel to load its chapters and scenes.")
            else:
                self.status_var.set(
                    f"No Manuscript/Chapters folders found for {novel_path.name}."
                )
            self._update_controls()
            return

        current = self.chapter_var.get().strip()
        self.chapter_var.set(current if current in self.chapter_numbers else labels[0])
        self._on_chapter_selected()

    def create_next_chapter(self) -> bool:
        """Complete the latest saved chapter and create the next chapter at Scene 01."""
        if self.busy:
            return False

        novel_name = self.novel_var.get().strip()
        novel_path = self.novel_packages.get(novel_name)
        chapter_number = self.chapter_numbers.get(self.chapter_var.get().strip())
        if novel_path is None or chapter_number is None:
            self._showinfo("Choose a chapter", "Select a novel and chapter first.")
            return False

        chapters = list_scene_chapters(novel_path)
        if not chapters or chapter_number != max(chapters):
            self._showinfo(
                "Choose the latest chapter",
                "New Chapter can only complete the latest chapter in this novel. "
                "Select the last chapter before continuing.",
            )
            return False

        saved_scenes = list_scene_files(novel_path, chapter_number)
        if not saved_scenes:
            self._showinfo(
                "No saved scenes",
                f"Chapter {chapter_number:02d} has no saved scenes to complete. "
                "Save at least one scene first.",
            )
            return False
        final_scene, final_scene_path = saved_scenes[-1]

        if self._output_text() != getattr(self, "saved_output_text", ""):
            self._showinfo(
                "Unsaved draft",
                "The Output pane has unsaved changes. Save or clear that draft before "
                "starting a new chapter. Nothing has been changed.",
            )
            return False

        next_chapter = int(chapter_number) + 1
        chapters_root = Path(novel_path).expanduser() / "Manuscript" / "Chapters"
        next_folder = chapters_root / f"Chapter_{next_chapter:02d}"
        if next_folder.exists():
            self._showinfo(
                "Chapter already exists",
                f"{next_folder} already exists. Select that chapter from the Chapter list instead.",
            )
            return False

        state_path = Path(novel_path).expanduser() / "current_state.json"
        try:
            current_state = load_current_state(state_path)
            next_state = advance_to_next_chapter(
                current_state, chapter_number, final_scene
            )
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            self._showerror("Could not prepare next chapter", str(exc))
            return False

        message = (
            f"Mark Chapter {chapter_number:02d} complete through Scene {final_scene:02d} "
            f"and start Chapter {next_chapter:02d}, Scene 01?\n\n"
            f"StoryBuilder will create {next_folder.name} and move current_state.json "
            f"to Chapter {next_chapter:02d}, Scene 01. Chapter {chapter_number:02d}, "
            f"Scene {final_scene:02d} remains the continuity reference.\n\n"
            "No manuscript scene will be edited or deleted."
        )
        if not self._askyesno("Create next chapter", message):
            self.status_var.set("New Chapter cancelled. No files or story state changed.")
            return False

        try:
            next_folder.mkdir(parents=False, exist_ok=False)
            write_current_state(state_path, next_state)
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            try:
                next_folder.rmdir()
            except OSError:
                pass
            self._showerror("Could not create next chapter", str(exc))
            return False

        self._discard_scene_prompt_trace()
        self._clear_prepared_scene_target()
        self._clear_scene_cast_selection()
        self.prompt_box.delete("1.0", "end")
        self.author_direction_box.delete("1.0", "end")
        self.selected_scene_source = None

        self.chapter_numbers = {
            f"Chapter {number:02d}": number
            for number in list_scene_chapters(novel_path)
        }
        self.chapter_picker.configure(values=list(self.chapter_numbers))
        next_label = f"Chapter {next_chapter:02d}"
        self.chapter_var.set(next_label)
        self._on_chapter_selected()
        self.scene_picker.configure(values=["Scene 01"])
        self.scene_var.set("Scene 01")
        self._prepared_scene_destination = (next_chapter, 1)
        self._prepared_scene_novel_path = Path(novel_path).expanduser().resolve()
        self._prepared_scene_source_scene_path = final_scene_path.resolve()
        self._prepared_author_required_direction = ""
        self.status_var.set(
            f"Chapter {chapter_number:02d} completed through Scene {final_scene:02d}. "
            f"Ready for Chapter {next_chapter:02d}, Scene 01. The previous chapter's "
            "last saved scene remains the continuity reference."
        )
        self._update_document_title()
        self._update_controls()
        return True

    def _handle_novel_context_change(self, novel_path: Path | None) -> None:
        """Clear novel-specific directions and model history only when selection changes."""
        previous = getattr(self, "_active_novel_path", None)
        selected = (
            Path(novel_path).expanduser().resolve()
            if novel_path is not None else None
        )
        if previous == selected:
            return

        self._active_novel_path = selected
        self._clear_novel_specific_directions()
        self._reset_model_context_for_novel_switch()

    def _clear_novel_specific_directions(self) -> None:
        """Discard pending directions from the previous novel, not manuscript text."""
        self._discard_scene_prompt_trace()
        for attribute in ("prompt_box", "author_direction_box"):
            widget = getattr(self, attribute, None)
            if widget is not None:
                widget.delete("1.0", "end")

        self._clear_prepared_scene_target()
        self._scene_preparation_destination = None
        self._scene_preparation_original_prompt = ""
        self._scene_preparation_original_author_direction = ""
        self._scene_preparation_required_author_direction = ""
        self._scene_preparation_novel_path = None
        self._scene_preparation_source_scene_path = None
        self._preparing_scene = False
        self.last_location_context_names = []
        self._clear_scene_cast_selection()

    def _clear_scene_cast_selection(self) -> None:
        self._scene_cast_names = None
        self._scene_cast_novel_path = None
        self._scene_cast_destination = None
        summary = getattr(self, "scene_cast_summary_var", None)
        if summary is not None:
            summary.set("Not selected. Choose who may appear in this scene.")

    def _active_scene_cast(
        self, expected_destination: tuple[int, int] | None = None
    ) -> list[str] | None:
        names = getattr(self, "_scene_cast_names", None)
        if names is None:
            return None
        selected_path = getattr(self, "_scene_cast_novel_path", None)
        novel_name = getattr(getattr(self, "novel_var", None), "get", lambda: "")().strip()
        current_path = getattr(self, "novel_packages", {}).get(novel_name)
        if current_path is None or selected_path is None:
            return None
        if Path(current_path).expanduser().resolve() != Path(selected_path).expanduser().resolve():
            return None

        destination = getattr(self, "_scene_cast_destination", None)
        if destination is not None:
            if expected_destination is None:
                chapter_number = getattr(self, "chapter_numbers", {}).get(
                    getattr(getattr(self, "chapter_var", None), "get", lambda: "")().strip()
                )
                scene_number = scene_number_from_label(
                    getattr(getattr(self, "scene_var", None), "get", lambda: "")()
                )
                expected_destination = (
                    (int(chapter_number), int(scene_number))
                    if chapter_number is not None and scene_number is not None
                    else None
                )
            if expected_destination != destination:
                return None
        return list(names)

    def _update_scene_cast_summary(self) -> None:
        summary = getattr(self, "scene_cast_summary_var", None)
        if summary is None:
            return
        names = getattr(self, "_scene_cast_names", None)
        if names is None:
            summary.set("Not selected. Choose who may appear in this scene.")
        elif names:
            summary.set("Allowed: " + ", ".join(names))
        else:
            summary.set("No characters selected. This scene will have no character appearances.")

    def _choose_scene_cast(self, novel_path: str | Path) -> list[str] | None:
        """Show the registered character roster and return the author's selection."""
        try:
            story_bible = load_story_bible(novel_path)
            names = load_character_card_names(novel_path, story_bible)
        except (OSError, UnicodeError, ValueError) as exc:
            self._showerror("Could not load character roster", str(exc))
            return None

        if not names:
            self._showinfo(
                "No character cards found",
                "This novel has no readable character cards registered in its Story Bible.",
            )
            return None

        window = tk.Toplevel(self.root)
        window.title("Select Scene Cast")
        window.transient(self.root)
        window.resizable(True, True)
        window.geometry("440x520")
        window.grab_set()

        ttk.Label(
            window,
            text=(
                "Select only the characters allowed to appear in this scene. "
                "Anyone left unselected is excluded from the scene."
            ),
            wraplength=400,
            justify="left",
        ).pack(fill="x", padx=12, pady=(12, 8))

        list_frame = ttk.Frame(window, padding=(12, 0))
        list_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        roster = tk.Listbox(
            list_frame,
            selectmode=tk.EXTENDED,
            exportselection=False,
            height=min(18, max(5, len(names))),
            width=42,
        )
        roster.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        roster.configure(yscrollcommand=scrollbar.set)
        scrollbar.configure(command=roster.yview)

        selected_before = (
            set(self._scene_cast_names or [])
            if getattr(self, "_scene_cast_novel_path", None) is not None
            and Path(self._scene_cast_novel_path).expanduser().resolve()
            == Path(novel_path).expanduser().resolve()
            else set()
        )
        for index, name in enumerate(names):
            roster.insert("end", name)
            if name in selected_before:
                roster.selection_set(index)

        quick_row = ttk.Frame(window, padding=(12, 8))
        quick_row.pack(fill="x")
        ttk.Button(
            quick_row,
            text="Select All",
            command=lambda: roster.selection_set(0, "end"),
        ).pack(side="left")
        ttk.Button(
            quick_row,
            text="Clear",
            command=lambda: roster.selection_clear(0, "end"),
        ).pack(side="left", padx=(8, 0))

        result: dict[str, list[str] | None] = {"names": None}

        def accept() -> None:
            result["names"] = [names[index] for index in roster.curselection()]
            window.destroy()

        def cancel() -> None:
            window.destroy()

        action_row = ttk.Frame(window, padding=(12, 0, 12, 12))
        action_row.pack(fill="x")
        ttk.Button(action_row, text="Cancel", command=cancel).pack(side="right")
        ttk.Button(action_row, text="Use Selected", command=accept).pack(
            side="right", padx=(0, 8)
        )
        window.protocol("WM_DELETE_WINDOW", cancel)
        self.root.wait_window(window)
        return result["names"]

    def select_scene_cast(self) -> None:
        """Let the author choose the only characters allowed in the active scene."""
        if self.busy:
            return
        novel_name = self.novel_var.get().strip()
        novel_path = self.novel_packages.get(novel_name)
        if novel_path is None:
            self._showinfo("Choose a novel", "Select a novel before choosing its scene cast.")
            return
        names = self._choose_scene_cast(novel_path)
        if names is None:
            return
        chapter_number = self.chapter_numbers.get(self.chapter_var.get().strip())
        selected_scene_label = self.scene_var.get().strip()
        selected_scene_number = scene_number_from_label(selected_scene_label)
        selected_scene_path = self.scene_files.get(selected_scene_label)
        if chapter_number is None:
            self._showinfo(
                "Choose a chapter",
                "Select a chapter before choosing the cast for its next scene.",
            )
            return
        target_chapter, target_scene, _source, _retry = resolve_scene_preparation_target(
            chapter_number,
            selected_scene_path,
            selected_scene_number,
            novel_path=novel_path,
            pending_destination=getattr(self, "_prepared_scene_destination", None),
            pending_novel_path=getattr(self, "_prepared_scene_novel_path", None),
            pending_source_scene_path=getattr(
                self, "_prepared_scene_source_scene_path", None
            ),
        )
        self._scene_cast_names = names
        self._scene_cast_novel_path = Path(novel_path).expanduser().resolve()
        self._scene_cast_destination = (int(target_chapter), int(target_scene))
        self._update_scene_cast_summary()
        self.status_var.set(
            "Scene cast selected. Only those characters will be supplied to the models."
        )

    def _reset_model_context_for_novel_switch(self) -> None:
        """Clear the live model conversation before writing for another novel."""
        model_path = getattr(self, "loaded_model", None)
        selected_name = self.novel_var.get().strip()
        if model_path is None:
            self._set_activity_status("Switch Novel", None, "Not loaded")
            self.status_var.set(
                f"Selected {selected_name or 'no novel'}. Old scene directions cleared; "
                "no model session was loaded. Manuscript text was kept."
            )
            return

        self.busy = True
        self.writing = False
        self.stop_requested = False
        self.status_var.set(
            f"Clearing the previous model conversation before switching to "
            f"{selected_name or 'no novel'}…"
        )
        self._set_activity_status("Switch Novel", model_path, "Loading")
        self._update_controls()

        def work() -> None:
            try:
                self.engine.clear_context()
            except Exception as exc:
                # A failed clear must never leave a reusable session containing
                # the previous novel's conversation.
                try:
                    self.engine.stop()
                except Exception:
                    pass
                message = str(exc)
                self.root.after(
                    0,
                    lambda message=message, model_path=model_path:
                        self._novel_context_reset_failed(model_path, message),
                )
            else:
                self.root.after(
                    0,
                    lambda model_path=model_path, selected_name=selected_name:
                        self._novel_context_reset_succeeded(model_path, selected_name),
                )

        threading.Thread(target=work, daemon=True).start()

    def _novel_context_reset_succeeded(
        self, model_path: str | Path, selected_name: str
    ) -> None:
        self.busy = False
        self.writing = False
        self.stop_requested = False
        self._set_activity_status("Switch Novel", model_path, "Finished")
        self.status_var.set(
            f"Selected {selected_name or 'no novel'}. Model conversation cleared. "
            "Your manuscript text and file tracking were kept."
        )
        self._update_controls()

    def _novel_context_reset_failed(
        self, model_path: str | Path, message: str
    ) -> None:
        self.loaded_model = None
        self.busy = False
        self.writing = False
        self.stop_requested = False
        self._set_activity_status("Switch Novel", model_path, "Error")
        self.status_var.set(
            "Previous model history could not be cleared, so the model was stopped. "
            "It will start with a fresh session the next time you write."
        )
        self._update_controls()
        self._showerror(
            "Model session stopped for safety",
            "StoryBuilder could not confirm that the previous novel's conversation "
            "was cleared. The model was stopped to prevent that history from carrying "
            f"into another novel. It will reload fresh when needed.\n\nDetails: {message}",
        )

    def _on_chapter_selected(self, _event=None) -> None:
        """Populate the scene picker using only numbered manuscript text files."""
        novel_path = self.novel_packages.get(self.novel_var.get().strip())
        chapter_number = self.chapter_numbers.get(self.chapter_var.get().strip())
        pending_destination = getattr(self, "_prepared_scene_destination", None)
        cast_destination = getattr(self, "_scene_cast_destination", None)
        if cast_destination is not None and chapter_number != cast_destination[0]:
            self._clear_scene_cast_selection()
        if pending_destination is not None and chapter_number != pending_destination[0]:
            self._clear_prepared_scene_target()
        self.scene_files = {};
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

    def _clear_prepared_scene_target(self) -> None:
        """Forget a rejected or saved unsaved scene destination."""
        self._prepared_scene_destination = None
        self._prepared_scene_novel_path = None
        self._prepared_scene_source_scene_path = None
        self._prepared_author_required_direction = ""

    def _on_scene_selected(self, _event=None) -> None:
        """Discard scene-specific planning and cast choices when another scene is selected."""
        chapter_number = self.chapter_numbers.get(self.chapter_var.get().strip())
        scene_number = scene_number_from_label(self.scene_var.get().strip())
        selected_destination = (chapter_number, scene_number)

        cast_destination = getattr(self, "_scene_cast_destination", None)
        if cast_destination is not None and selected_destination != cast_destination:
            self._clear_scene_cast_selection()

        pending_destination = getattr(self, "_prepared_scene_destination", None)
        if pending_destination is not None and selected_destination != pending_destination:
            self._clear_prepared_scene_target()

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
        planner_model = self._selected_role_model("planner")
        if planner_model is None:
            self._showinfo(
                "Choose a planner model",
                "Select a model for Prepare Scene before preparing a scene.",
            )
            return

        novel_name = self.novel_var.get().strip()
        novel_path = self.novel_packages.get(novel_name)
        if novel_path is None:
            self._showinfo("Choose a novel", "Select a novel before preparing a scene.")
            return

        chapter_number = self.chapter_numbers.get(self.chapter_var.get().strip())
        selected_scene_label = self.scene_var.get().strip()
        selected_scene_number = scene_number_from_label(selected_scene_label)
        selected_scene_path = self.scene_files.get(selected_scene_label)
        (
            target_chapter,
            target_scene,
            source_scene,
            is_retry,
        ) = resolve_scene_preparation_target(
            chapter_number,
            selected_scene_path,
            selected_scene_number,
            novel_path=novel_path,
            pending_destination=getattr(self, "_prepared_scene_destination", None),
            pending_novel_path=getattr(self, "_prepared_scene_novel_path", None),
            pending_source_scene_path=getattr(
                self, "_prepared_scene_source_scene_path", None
            ),
        )
        scene_destination = (int(target_chapter), int(target_scene))
        selected_cast = getattr(self, "_scene_cast_names", None)
        selected_cast_path = getattr(self, "_scene_cast_novel_path", None)
        selected_cast_destination = getattr(self, "_scene_cast_destination", None)
        if (
            selected_cast is None
            or selected_cast_path is None
            or Path(selected_cast_path).expanduser().resolve()
            != Path(novel_path).expanduser().resolve()
            or (
                selected_cast_destination is not None
                and selected_cast_destination != scene_destination
            )
        ):
            selected_cast = self._choose_scene_cast(novel_path)
            if selected_cast is None:
                return
            self._scene_cast_names = selected_cast
            self._scene_cast_novel_path = Path(novel_path).expanduser().resolve()

        self._scene_cast_destination = scene_destination
        self._update_scene_cast_summary()

        existing_prompt = self.prompt_box.get("1.0", "end-1c")
        visible_author_direction = self.author_direction_box.get(
            "1.0", "end-1c"
        ).strip()
        prior_required_direction = (
            str(getattr(self, "_prepared_author_required_direction", "") or "").strip()
            if is_retry else ""
        )
        if prior_required_direction and visible_author_direction:
            author_direction = prior_required_direction
            if visible_author_direction not in prior_required_direction:
                author_direction += (
                    "\n\nAdditional author direction for this scene:\n"
                    + visible_author_direction
                )
        else:
            author_direction = prior_required_direction or visible_author_direction
        try:
            planning_prompt = build_scene_preparation_prompt(
                novel_path,
                novel_name,
                target_chapter,
                target_scene,
                source_scene_path=source_scene,
                author_direction=author_direction,
                previous_direction=existing_prompt if is_retry else None,
                scene_cast=list(selected_cast),
            )
        except (OSError, UnicodeError, ValueError) as exc:
            self._showerror("Could not prepare scene", str(exc))
            return

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

        pending_trace = getattr(self, "_pending_scene_prompt_trace", None)
        can_extend_pending_trace = (
            pending_trace is not None
            and getattr(self, "_prepared_scene_novel_path", None) == novel_path
            and getattr(self, "_prepared_scene_destination", None)
            == (target_chapter, target_scene)
        )
        if can_extend_pending_trace:
            planner_trace = pending_trace
            self._pending_scene_prompt_trace = None
        else:
            self._discard_scene_prompt_trace()
            planner_trace = self._start_prompt_trace(
                planning_prompt,
                model_path=planner_model,
                attach=False,
                chapter_number=target_chapter,
                scene_number=target_scene,
                scene_direction=existing_prompt,
                author_guidance=author_direction,
            )
        self._active_scene_preparation_trace = planner_trace
        if planner_trace is not None:
            planner_trace.record_event(
                "scene_preparation_attempt_started",
                target_chapter=target_chapter,
                target_scene=target_scene,
                retry=bool(is_retry),
                source_scene=Path(source_scene).name if source_scene else None,
                author_direction=author_direction,
            )

        self._scene_preparation_destination = (target_chapter, target_scene)
        self._scene_preparation_novel_path = novel_path
        self._scene_preparation_source_scene_path = source_scene
        self._scene_preparation_original_prompt = existing_prompt
        self._scene_preparation_original_author_direction = visible_author_direction
        self._scene_preparation_required_author_direction = author_direction
        self._preparing_scene = True
        self.busy = True
        self.writing = True
        self.stop_requested = False
        self.status_var.set(
            f"Preparing Chapter {target_chapter:02d}, Scene {target_scene:02d} "
            f"for {novel_name} with {self._activity_model_label(planner_model)}…"
        )
        self._begin_model_activity("Prepare Scene", planner_model)
        self._update_controls()

        def work() -> None:
            trace_attached = False
            try:
                self._ensure_model_loaded(planner_model)
                attach_trace = getattr(self.engine, "attach_prompt_trace", None)
                if planner_trace is not None and callable(attach_trace):
                    try:
                        attach_trace(planner_trace, role="scene_planner")
                    except TypeError:
                        # Keep tracing compatible with lightweight test doubles.
                        attach_trace(planner_trace)
                    trace_attached = True
                self._schedule_activity_status(
                    "Prepare Scene", planner_model, "Generating"
                )
                suggestion = write_from_prompt(self.engine, planning_prompt).strip()
            except GenerationInterrupted:
                self.root.after(
                    0,
                    lambda trace=planner_trace: self._prepare_scene_stopped(trace),
                )
            except Exception as exc:
                message = str(exc)
                self.root.after(
                    0,
                    lambda message=message, trace=planner_trace:
                        self._prepare_scene_failed(message, trace),
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
                    lambda suggestion=suggestion, error=context_reset_error,
                    trace=planner_trace:
                        self._prepare_scene_succeeded(suggestion, error, trace),
                )
            finally:
                if trace_attached:
                    detach_trace = getattr(self.engine, "detach_prompt_trace", None)
                    if callable(detach_trace):
                        try:
                            detach_trace(planner_trace)
                        except Exception:
                            pass

        threading.Thread(target=work, daemon=True).start()

    def _prepare_scene_succeeded(
        self,
        suggestion: str,
        context_reset_error: str | None = None,
        trace=None,
    ) -> None:
        if self.stop_requested:
            self._discard_scene_prompt_trace(trace)
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
            self._discard_scene_prompt_trace(trace)
            self._preparing_scene = False
            self.busy = False
            self.writing = False
            self.stop_requested = False
            self._set_activity_status(
                "Prepare Scene", getattr(self, "_activity_model_path", None), "Finished"
            )
            self.status_var.set(
                "The prompt or author's direction was edited while Scene Preparation "
                "was running. Your edits were kept; prepare again if you still need a suggestion."
            )
            self._update_controls()
            return
        if not suggestion.strip():
            self._discard_scene_prompt_trace(trace)
            self._preparing_scene = False
            self.busy = False
            self.writing = False
            self.stop_requested = False
            self._set_activity_status(
                "Prepare Scene", getattr(self, "_activity_model_path", None), "Error"
            )
            self.status_var.set("Scene preparation returned no suggestion. Your prompt was kept.")
            self._update_controls()
            self._showerror(
                "No scene suggestion",
                "The model returned an empty suggestion. The existing prompt was not changed.",
            )
            return

        suggestion = apply_author_required_beats(
            suggestion,
            getattr(self, "_scene_preparation_required_author_direction", ""),
        )
        self.prompt_box.delete("1.0", "end")
        self.prompt_box.insert("1.0", suggestion.strip())
        self.author_direction_box.delete("1.0", "end")
        chapter_number, scene_number = self._scene_preparation_destination
        self._prepared_scene_destination = self._scene_preparation_destination
        self._prepared_scene_novel_path = self._scene_preparation_novel_path
        self._prepared_scene_source_scene_path = (
            self._scene_preparation_source_scene_path
        )
        self._prepared_author_required_direction = str(
            getattr(self, "_scene_preparation_required_author_direction", "") or ""
        ).strip()
        if trace is not None:
            trace.data["inputs"]["scene_direction"] = suggestion.strip()
            trace.record_event(
                "scene_preparation_result_accepted",
                scene_direction=suggestion.strip(),
                target_chapter=chapter_number,
                target_scene=scene_number,
            )
            self._pending_scene_prompt_trace = trace
        if getattr(self, "_active_scene_preparation_trace", None) is trace:
            self._active_scene_preparation_trace = None
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
            self._set_activity_status(
                "Prepare Scene", getattr(self, "_activity_model_path", None), "Error"
            )
            self.status_var.set(
                f"Prepared Chapter {chapter_number:02d}, Scene {scene_number:02d}. "
                "The suggestion was kept, but planner history could not be cleared. "
                "The selected writing model will load automatically when you press Write. "
                f"Details: {context_reset_error}"
            )
        else:
            self._set_activity_status(
                "Prepare Scene", getattr(self, "_activity_model_path", None), "Finished"
            )
            self.status_var.set(
                f"Prepared Chapter {chapter_number:02d}, Scene {scene_number:02d}. "
                "Planner conversation cleared. Press Prepare Scene to try another "
                "suggestion for this same scene, or edit it and press Write. "
                "The selected writing model will load automatically for manuscript generation. "
                "Saving the scene advances to the next number."
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

    def _prepare_scene_failed(self, message: str, trace=None) -> None:
        self._discard_scene_prompt_trace(trace)
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
        self._set_activity_status(
            "Prepare Scene", getattr(self, "_activity_model_path", None), "Error"
        )
        self.status_var.set("Scene preparation failed. Your existing prompt was kept.")
        self._update_controls()
        self._showerror("Scene preparation failed", message)

    def _prepare_scene_stopped(self, trace=None) -> None:
        self._discard_scene_prompt_trace(trace)
        self._preparing_scene = False
        self.busy = False
        self.writing = False
        self.loaded_model = None
        self.stop_requested = False
        self._set_activity_status(
            "Prepare Scene", getattr(self, "_activity_model_path", None), "Stopped"
        )
        self.status_var.set(
            "Scene preparation stopped. Your existing prompt was kept. "
            "The selected planner model will load automatically next time."
        )
        self._update_controls()

    def write(self) -> None:
        if self.busy:
            return
        prompt = self.prompt_box.get("1.0", "end-1c")
        if not prompt.strip():
            self._showinfo("Add a prompt", "Enter what you want the model to write.")
            return

        prompt = self._prepare_balanced_writer_context(prompt)
        prompt = self._prepare_previous_scene_context(prompt, max_chars=1400)
        self._begin_generation(prompt, mode="write")

    def write_full_context(self) -> None:
        """Use the original broad context builder as an explicit fallback."""
        if self.busy:
            return
        prompt = self.prompt_box.get("1.0", "end-1c")
        if not prompt.strip():
            self._showinfo("Add a prompt", "Enter what you want the model to write.")
            return
        prompt = self._prepare_location_context(prompt)
        prompt = self._prepare_previous_scene_context(prompt)
        self._begin_generation(prompt, mode="write", context_profile="full")

    def write_minimal_test(self) -> None:
        """Run one scene-generation test without automatic novel-context additions."""
        if self.busy:
            return
        prompt = self.prompt_box.get("1.0", "end-1c")
        if not prompt.strip():
            self._showinfo(
                "Add a prompt",
                "Enter or prepare a scene direction before running the minimal test.",
            )
            return

        # Do not carry a location label from an earlier, fully enriched request.
        self.last_location_context_names = []
        self._begin_generation(prompt, mode="write", context_profile="minimal")

    def rewrite_current_scene(self) -> None:
        """Regenerate the visible scene using its existing prompt and extra guidance."""
        if self.busy:
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
                "The selected writing model will use the existing What should it write? prompt, with "
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
        prompt = self._prepare_balanced_writer_context(prompt, supporting_text=author_direction)
        prompt = self._prepare_previous_scene_context(prompt, max_chars=1400)
        self._rewrite_original_author_direction = author_direction
        self._begin_generation(prompt, mode="rewrite")

    def continue_writing(self) -> None:
        if self.busy:
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
        prompt = self._prepare_balanced_writer_context(
            prompt,
            "\n".join(part for part in (scene_idea, existing_text) if part),
        )
        self._begin_generation(prompt, mode="continue")

    def _prepare_creative_direction_context(self, prompt: str) -> str:
        """Attach the selected novel's creative profiles and writing preferences."""
        original = str(prompt or "")
        novel_var = getattr(self, "novel_var", None)
        get_value = getattr(novel_var, "get", None)
        if not callable(get_value):
            return original

        novel_name = str(get_value() or "").strip()
        novel_packages = getattr(self, "novel_packages", {})
        if not isinstance(novel_packages, dict):
            return original
        novel_path = novel_packages.get(novel_name)
        if novel_path is None:
            return original

        try:
            story_bible = load_story_bible(novel_path)
        except (OSError, UnicodeError, ValueError):
            return original

        sections: list[str] = []
        creative_guidance = build_creative_direction_prompt(
            story_bible.get("creative_direction")
        )
        if creative_guidance:
            sections.append(creative_guidance)

        writing_preferences = story_bible.get("writing_preferences")
        if isinstance(writing_preferences, str) and writing_preferences.strip():
            sections.append(
                "HOW THIS NOVEL SHOULD READ\n"
                "The following optional preferences were written by the author for this novel. "
                "Use them as flexible creative guidance, not as a rigid checklist:\n"
                + writing_preferences.strip()
            )

        if not sections:
            return original
        guidance = "\n\n".join(sections)
        return f"{original.rstrip()}\n\n{guidance}" if original.strip() else guidance

    def _prepare_previous_scene_context(
        self, prompt: str, *, max_chars: int | None = None
    ) -> str:
        """Add the immediately preceding accepted scene or a concise ending excerpt."""
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
            prompt,
            novel_path,
            chapter_number,
            scene_number,
            max_chars=max_chars,
        )

    def _prepare_balanced_writer_context(
        self, prompt: str, supporting_text: str = ""
    ) -> str:
        """Build a small, scene-specific view of canon, people, and current continuity."""
        self.last_location_context_names = []
        novel_var = getattr(self, "novel_var", None)
        packages = getattr(self, "novel_packages", {})
        if novel_var is None or not isinstance(packages, dict):
            self.last_writer_context_summary = {"available": False}
            return str(prompt or "")

        novel_path = packages.get(novel_var.get().strip())
        if novel_path is None:
            self.last_writer_context_summary = {"available": False}
            return str(prompt or "")

        try:
            story_bible = load_story_bible(novel_path)
        except (OSError, UnicodeError, ValueError):
            self.last_writer_context_summary = {"available": False}
            return str(prompt or "")

        current_state = {}
        try:
            state_path = Path(novel_path) / "current_state.json"
            current_state = json.loads(state_path.read_text(encoding="utf-8"))
            if not isinstance(current_state, dict):
                current_state = {}
        except (OSError, UnicodeError, ValueError):
            current_state = {}

        author_box = getattr(self, "author_direction_box", None)
        author_text = (
            author_box.get("1.0", "end-1c").strip()
            if author_box is not None else ""
        )
        scene_text = "\n".join(
            part for part in (str(prompt or ""), str(supporting_text or ""), author_text)
            if part
        )
        selected_cast = self._active_scene_cast()

        sections = [str(prompt or "").rstrip()]
        canon_context = build_scene_relevant_story_bible_reference_context(
            story_bible, scene_text, selected_names=selected_cast
        )
        if canon_context:
            sections.append(canon_context)

        current_location = current_state.get("location")
        primary_location = (
            current_location.get("primary")
            if isinstance(current_location, dict) else ""
        )
        if isinstance(primary_location, str) and primary_location.strip():
            location_text = _short_context_text(primary_location, 140)
            if location_text.casefold() not in scene_text.casefold():
                sections.append("CURRENT STORY LOCATION\n" + location_text)

        timeline_note = build_story_timeline_prompt(current_state.get("time_of_day"))
        if timeline_note:
            sections.append(timeline_note)

        situation = current_state.get("current_situation")
        if isinstance(situation, str) and _scene_context_is_relevant(situation, scene_text):
            sections.append(
                "CURRENT SITUATION\n" + _short_context_text(situation, 360)
            )

        continuity_notes = current_state.get("continuity_notes")
        relevant_notes = []
        if isinstance(continuity_notes, list):
            for note in continuity_notes:
                if not isinstance(note, str) or not note.strip():
                    continue
                if _scene_context_is_relevant(note, scene_text):
                    relevant_notes.append(_short_context_text(note, 240))
                if len(relevant_notes) >= 3:
                    break
        if relevant_notes:
            sections.append(
                "RELEVANT CONTINUITY\n"
                + "\n".join(f"- {note}" for note in relevant_notes)
            )

        character_context = build_character_card_context_prompt(
            novel_path,
            story_bible,
            "\n\n".join(part for part in sections if part),
            supporting_text=scene_text,
            compact=True,
            selected_names=selected_cast,
            scene_focused=True,
        )
        sections = [character_context] if character_context else sections

        locations = story_bible.get("locations", {})
        enriched, names = build_location_context_prompt(
            "\n\n".join(part for part in sections if part),
            locations if isinstance(locations, dict) else {},
            supporting_text=scene_text,
        )
        self.last_location_context_names = names

        # Keep overall author style and genre as a small hint, not a second
        # instruction document with profile descriptions.
        writing_preferences = story_bible.get("writing_preferences")
        if isinstance(writing_preferences, str) and writing_preferences.strip():
            preference = _short_context_text(writing_preferences, 320)
            enriched = f"{enriched.rstrip()}\n\nBRIEF AUTHOR STYLE PREFERENCE\n{preference}"

        creative = story_bible.get("creative_direction")
        if isinstance(creative, dict):
            genres = creative.get("genres", [])
            moods = creative.get("moods", [])
            audience = creative.get("audience", "")
            profile_parts = []
            if isinstance(genres, list):
                profile_parts.extend(str(item).strip() for item in genres if str(item).strip())
            if isinstance(moods, list):
                profile_parts.extend(str(item).strip() for item in moods if str(item).strip())
            if isinstance(audience, str) and audience.strip():
                profile_parts.append(audience.strip())
            if profile_parts:
                enriched = (
                    f"{enriched.rstrip()}\n\n"
                    "NOVEL TONE\n" + ", ".join(dict.fromkeys(profile_parts[:6]))
                )

        self.last_writer_context_summary = {
            "available": True,
            "characters": [
                name for name in load_character_card_names(novel_path, story_bible)
                if re.search(
                    r"(?<![\w])" + re.escape(name.split()[0]) + r"(?![\w])",
                    scene_text,
                    flags=re.IGNORECASE,
                )
            ],
            "canon_context_included": bool(canon_context),
            "current_situation_included": bool(
                isinstance(situation, str) and _scene_context_is_relevant(situation, scene_text)
            ),
            "continuity_notes_included": len(relevant_notes),
            "locations_included": list(names),
        }
        return enriched

    def _prepare_location_context(self, prompt: str, supporting_text: str = "") -> str:
        """Add only brief, relevant facts needed to ground this writing request."""
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
            return prompt

        current_state = {}
        try:
            state_path = Path(novel_path) / "current_state.json"
            current_state = json.loads(state_path.read_text(encoding="utf-8"))
            if not isinstance(current_state, dict):
                current_state = {}
        except (OSError, UnicodeError, ValueError):
            current_state = {}

        context_parts = [str(prompt or "").rstrip()]
        story_reference = build_story_bible_reference_context(story_bible)
        if story_reference:
            context_parts.append(story_reference)

        timeline_note = build_story_timeline_prompt(
            current_state.get("time_of_day")
        )
        if timeline_note:
            context_parts.append(timeline_note)

        situation = current_state.get("current_situation")
        if isinstance(situation, str) and situation.strip():
            situation = " ".join(situation.split())
            if len(situation) > 600:
                situation = situation[:597].rsplit(" ", 1)[0].rstrip() + "…"
            context_parts.append("CURRENT STORY SITUATION\n" + situation)

        continuity_notes = current_state.get("continuity_notes")
        if isinstance(continuity_notes, list):
            notes = [
                " ".join(str(note).split())[:500]
                for note in continuity_notes
                if isinstance(note, str) and note.strip()
            ][:6]
            if notes:
                context_parts.append(
                    "CURRENT CONTINUITY NOTES\n"
                    + "\n".join(f"- {note}" for note in notes)
                )

        character_supporting_text = str(supporting_text or "")
        selected_scene_cast = self._active_scene_cast()
        prior_scene_cast = current_state.get("scene_cast", [])
        if selected_scene_cast is None and isinstance(prior_scene_cast, list):
            cast_names = [
                str(name).strip()
                for name in prior_scene_cast
                if isinstance(name, str) and name.strip()
            ]
            if cast_names:
                character_supporting_text = "\n".join(
                    part for part in (
                        character_supporting_text,
                        " ".join(cast_names),
                    ) if part
                )

        include_all = (
            selected_scene_cast is None
            and current_state.get("status") == "story_start"
            and not prior_scene_cast
        )
        compact_prompt = "\n\n".join(part for part in context_parts if part)
        compact_prompt = build_character_card_context_prompt(
            novel_path,
            story_bible,
            compact_prompt,
            supporting_text=character_supporting_text,
            include_all=include_all,
            compact=True,
            selected_names=selected_scene_cast,
        )

        locations = story_bible.get("locations", {})
        enriched, names = build_location_context_prompt(
            compact_prompt,
            locations if isinstance(locations, dict) else {},
            supporting_text=supporting_text,
        )
        self.last_location_context_names = names
        return enriched

    def new_session(self) -> None:
        """Clear model conversation context while preserving the visible draft."""
        if self.busy:
            return
        writer_model = self._selected_role_model("writer")
        if writer_model is None:
            self._showinfo(
                "Choose a writing model",
                "Select a writing model before starting a new session.",
            )
            return

        self.busy = True
        self.writing = False
        self.stop_requested = False
        self.status_var.set(f"Starting a new writer session with {self._activity_model_label(writer_model)}…")
        self._set_activity_status(
            "New Session",
            writer_model,
            "Ready" if self._runtime_model_is_ready(writer_model) else "Loading",
        )
        self._update_controls()

        def work() -> None:
            try:
                self._ensure_model_loaded(writer_model)
                self._schedule_activity_status("New Session", writer_model, "Ready")
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
        model_name = self._activity_model_label(self.loaded_model) if self.loaded_model else "model"
        self._set_activity_status(
            "New Session", getattr(self, "_activity_model_path", None), "Finished"
        )
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
        self._set_activity_status(
            "New Session", getattr(self, "_activity_model_path", None), "Error"
        )
        self.status_var.set("New session failed. Reload the model if needed.")
        self._update_controls()
        self._showerror("Could not start a new session", message)

    def _discard_scene_prompt_trace(self, trace=None) -> None:
        """Detach and forget an unused planner trace without saving or uploading it."""
        if trace is None:
            trace = getattr(self, "_active_scene_preparation_trace", None)
        if trace is None:
            trace = getattr(self, "_pending_scene_prompt_trace", None)
        if trace is None:
            return

        detach_trace = getattr(
            getattr(self, "engine", None), "detach_prompt_trace", None
        )
        if callable(detach_trace):
            try:
                detach_trace(trace)
            except Exception:
                pass
        for attribute in (
            "_active_scene_preparation_trace",
            "_pending_scene_prompt_trace",
        ):
            if getattr(self, attribute, None) is trace:
                setattr(self, attribute, None)

    def _prepared_author_required_direction_for_current_scene(
        self, expected_destination: tuple[int, int] | None = None
    ) -> str:
        """Return required author direction only for its matching novel and scene."""
        direction = str(
            getattr(self, "_prepared_author_required_direction", "") or ""
        ).strip()
        if not direction:
            return ""

        novel_name = getattr(
            getattr(self, "novel_var", None), "get", lambda: ""
        )().strip()
        novel_path = getattr(self, "novel_packages", {}).get(novel_name)
        prepared_path = getattr(self, "_prepared_scene_novel_path", None)
        destination = getattr(self, "_prepared_scene_destination", None)
        if expected_destination is None:
            chapter_label = getattr(
                getattr(self, "chapter_var", None), "get", lambda: ""
            )().strip()
            chapter_number = getattr(self, "chapter_numbers", {}).get(chapter_label)
            scene_number = scene_number_from_label(
                getattr(getattr(self, "scene_var", None), "get", lambda: "")()
            )
            expected_destination = (
                (int(chapter_number), int(scene_number))
                if chapter_number is not None and scene_number is not None
                else None
            )
        if (
            novel_path is None
            or prepared_path is None
            or expected_destination is None
            or destination != expected_destination
        ):
            return ""
        try:
            same_novel = (
                Path(novel_path).expanduser().resolve()
                == Path(prepared_path).expanduser().resolve()
            )
        except (OSError, TypeError, ValueError):
            return ""
        return direction if same_novel else ""

    def _claim_prepared_scene_prompt_trace(
        self, mode: str, expected_destination: tuple[int, int] | None = None
    ):
        """Reuse the planner trace only for the same novel and prepared scene."""
        trace = getattr(self, "_pending_scene_prompt_trace", None)
        if trace is None:
            return None
        try:
            tracing_enabled = load_prompt_trace_enabled()
        except Exception:
            tracing_enabled = False
        if not tracing_enabled:
            self._discard_scene_prompt_trace(trace)
            return None

        novel_var = getattr(self, "novel_var", None)
        novel_packages = getattr(self, "novel_packages", {})
        chapter_var = getattr(self, "chapter_var", None)
        scene_var = getattr(self, "scene_var", None)
        novel_name = novel_var.get().strip() if novel_var is not None else ""
        novel_path = novel_packages.get(novel_name)
        if expected_destination is None:
            chapter_label = chapter_var.get().strip() if chapter_var is not None else ""
            chapter_number = getattr(self, "chapter_numbers", {}).get(chapter_label)
            scene_number = (
                scene_number_from_label(scene_var.get().strip())
                if scene_var is not None else None
            )
            expected_destination = (
                (int(chapter_number), int(scene_number))
                if chapter_number is not None and scene_number is not None
                else None
            )
        else:
            expected_destination = (
                int(expected_destination[0]),
                int(expected_destination[1]),
            )
        prepared_path = getattr(self, "_prepared_scene_novel_path", None)
        try:
            same_novel = (
                novel_path is not None
                and prepared_path is not None
                and Path(novel_path).expanduser().resolve()
                == Path(prepared_path).expanduser().resolve()
            )
        except (OSError, TypeError, ValueError):
            same_novel = False

        if (
            not same_novel
            or expected_destination is None
            or getattr(self, "_prepared_scene_destination", None)
            != expected_destination
        ):
            self._discard_scene_prompt_trace(trace)
            return None

        self._pending_scene_prompt_trace = None
        direction_box = getattr(self, "prompt_box", None)
        author_box = getattr(self, "author_direction_box", None)
        final_direction = (
            direction_box.get("1.0", "end-1c") if direction_box is not None else ""
        )
        final_author_guidance = (
            author_box.get("1.0", "end-1c").strip() if author_box is not None else ""
        )
        trace.record_event(
            "prepared_direction_sent_to_writer",
            generation_mode=str(mode),
            final_scene_direction=final_direction,
            final_author_guidance=final_author_guidance,
            final_author_required_direction=(
                self._prepared_author_required_direction_for_current_scene()
            ),
        )
        return trace

    def _start_prompt_trace(
        self,
        prompt: str,
        model_path: str | Path | None = None,
        *,
        attach: bool = True,
        chapter_number: int | None = None,
        scene_number: int | None = None,
        scene_direction: str | None = None,
        author_guidance: str | None = None,
    ):
        """Arm a local scene capture without affecting normal writing."""
        try:
            if not load_prompt_trace_enabled():
                return None
        except Exception:
            return None

        novel_name = getattr(getattr(self, "novel_var", None), "get", lambda: "")().strip()
        novel_path = getattr(self, "novel_packages", {}).get(novel_name)
        selected_chapter = (
            chapter_number
            if chapter_number is not None
            else getattr(self, "chapter_numbers", {}).get(
                getattr(getattr(self, "chapter_var", None), "get", lambda: "")().strip(),
                1,
            )
        )
        selected_scene = (
            scene_number
            if scene_number is not None
            else scene_number_from_label(
                getattr(getattr(self, "scene_var", None), "get", lambda: "")()
            ) or 1
        )

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
        captured_scene_direction = (
            scene_direction
            if scene_direction is not None
            else prompt_box.get("1.0", "end-1c")
            if prompt_box is not None
            else str(prompt or "")
        )
        captured_author_guidance = (
            author_guidance
            if author_guidance is not None
            else direction_box.get("1.0", "end-1c").strip()
            if direction_box is not None
            else ""
        )
        trace = PromptTrace(
            chapter=int(selected_chapter or 1),
            scene=int(selected_scene),
            model_path=(
                str(model_path)
                if is_openrouter_selection(model_path)
                else Path(model_path).expanduser().resolve()
                if model_path is not None
                else getattr(self, "loaded_model", None)
            ),
            current_state=current_state,
            reference_files=reference_files,
            contract={},
            scene_direction=captured_scene_direction,
            author_guidance=captured_author_guidance,
            system_prompt=(
                "" if model_path is not None
                else getattr(self.engine, "system_prompt", "")
            ),
        )
        if attach:
            attach_trace = getattr(self.engine, "attach_prompt_trace", None)
            if not callable(attach_trace):
                return None
            try:
                attach_trace(trace)
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
        if saved_path:
            self._last_prompt_trace_path = str(saved_path)
        detach = getattr(self.engine, "detach_prompt_trace", None)
        if callable(detach):
            try:
                detach(trace)
            except Exception:
                pass

    def upload_latest_prompt_trace(self) -> None:
        """Upload the latest local trace only after the author clicks the button."""
        if self.busy or getattr(self, "_trace_upload_busy", False):
            return
        trace_path = Path(
            getattr(self, "_last_prompt_trace_path", None) or default_prompt_trace_path()
        ).expanduser()
        if not trace_path.is_file():
            self.status_var.set(
                "No saved prompt trace is available yet. Complete a scene generation first."
            )
            return

        self._trace_upload_busy = True
        if hasattr(self, "upload_trace_button"):
            self.upload_trace_button.configure(state="disabled")
        self.status_var.set("Uploading prompt trace to your private GitHub repository…")

        def worker() -> None:
            try:
                result = upload_prompt_trace(trace_path)
            except Exception as exc:
                result = {"ok": False, "error": str(exc)[:700]}

            def finish_upload() -> None:
                self._trace_upload_busy = False
                self._last_prompt_trace_upload_result = result
                if result.get("ok"):
                    url = str(result.get("url") or "").strip()
                    message = "Prompt trace uploaded to the private GitHub trace repository."
                    if url:
                        message += f" {url}"
                    self.status_var.set(message)
                else:
                    detail = str(result.get("error") or "Unknown upload error")
                    self.status_var.set(
                        "Prompt trace upload failed. The local trace is still available. "
                        + detail
                    )
                self._update_controls()

            try:
                self.root.after(0, finish_upload)
            except Exception:
                self._trace_upload_busy = False

        try:
            threading.Thread(target=worker, daemon=True).start()
        except Exception as exc:
            self._trace_upload_busy = False
            self.status_var.set(
                "Could not start prompt trace upload. The local trace is still available. "
                + str(exc)
            )
            self._update_controls()

    def _begin_generation(
        self, prompt: str, mode: str, *, context_profile: str = "balanced"
    ) -> None:
        # An explicit scene heading in the prepared direction wins over the
        # picker. The picker can still point to the last saved scene when an
        # unsaved scene is being rewritten or its target was restored from text.
        chapter_label = getattr(
            getattr(self, "chapter_var", None), "get", lambda: ""
        )().strip()
        selected_chapter = getattr(self, "chapter_numbers", {}).get(chapter_label)
        scene_label = getattr(
            getattr(self, "scene_var", None), "get", lambda: ""
        )()
        generation_destination = resolve_generation_scene_destination(
            prompt, selected_chapter, scene_label
        )
        chapter_number, scene_number = (
            generation_destination
            if generation_destination is not None
            else (None, None)
        )
        prepared_author_direction = (
            self._prepared_author_required_direction_for_current_scene(
                generation_destination
            )
        )
        visible_author_direction = getattr(
            getattr(self, "author_direction_box", None), "get", lambda *_args: ""
        )("1.0", "end-1c").strip()
        required_directions = []
        for direction in (prepared_author_direction, visible_author_direction):
            if direction and direction not in required_directions:
                required_directions.append(direction)
        author_required_direction = "\n\n".join(required_directions)
        prompt = build_author_required_direction_prompt(
            prompt, author_required_direction
        )
        prompt = build_single_scene_scope_prompt(
            prompt, chapter_number=chapter_number, scene_number=scene_number
        )
        if context_profile == "full":
            prompt = self._prepare_creative_direction_context(prompt)
        scene_cast = self._active_scene_cast(generation_destination)
        if scene_cast is not None:
            prompt = build_scene_cast_boundary_prompt(prompt, scene_cast)
        writer_model = self._selected_role_model("writer")
        if writer_model is None:
            self._showinfo(
                "Choose a writing model",
                "Select a model for manuscript writing before generating prose.",
            )
            return

        # Keep the previous document recoverable so errors or an immediate Stop
        # do not destroy the author's text.
        self._pre_generation_text = self._output_text()
        self._pre_generation_file = self.current_file
        self._pre_generation_saved_text = self.saved_output_text
        self._generation_mode = mode
        self._generation_had_chunks = False
        self._last_prompt_trace_path = str(default_prompt_trace_path())
        self._last_prompt_trace_upload_result = None
        prompt_trace = self._claim_prepared_scene_prompt_trace(
            mode, expected_destination=generation_destination
        )
        if prompt_trace is None:
            prompt_trace = self._start_prompt_trace(
                prompt,
                model_path=writer_model,
                attach=False,
                chapter_number=chapter_number,
                scene_number=scene_number,
                author_guidance=author_required_direction,
            )
        if prompt_trace is not None and context_profile in {"balanced", "minimal", "full"}:
            try:
                if context_profile == "minimal":
                    prompt_trace.record_event(
                        "minimal_writer_context_test",
                        skipped_context=[
                            "Story Bible canon and relationship references",
                            "automatic character-card context",
                            "automatic location context",
                            "current-state situation and continuity notes",
                            "previous accepted scene text",
                            "novel-wide creative direction and writing preferences",
                        ],
                        retained_context=[
                            "visible scene direction",
                            "author-required direction protection",
                            "one-scene scope",
                            "explicit scene-cast boundary when selected",
                        ],
                    )
                elif context_profile == "balanced":
                    prompt_trace.record_event(
                        "balanced_writer_context",
                        context_summary=getattr(self, "last_writer_context_summary", {}),
                        previous_scene_excerpt_char_limit=1400,
                        retained_context=[
                            "scene-mentioned character cards in compact form",
                            "scene-relevant canon and relationship facts",
                            "relevant current situation and continuity notes",
                            "named locations and brief descriptions",
                            "short previous-scene ending excerpt",
                            "brief novel style and tone hints",
                        ],
                        skipped_context=[
                            "unrelated character biographies and full roster",
                            "unrelated canon and relationships",
                            "unrelated locations and continuity notes",
                            "full previous-scene text",
                            "long creative-profile instructions",
                        ],
                    )
                else:
                    prompt_trace.record_event(
                        "full_writer_context_fallback",
                        context_summary="Original broad context builder retained for fallback.",
                    )
            except Exception:
                pass
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
        self.status_var.set(f"{action} with {self._activity_model_label(writer_model)}…{location_note}")
        task_name = {
            "write": "Write",
            "continue": "Continue",
            "rewrite": "Rewrite Scene",
        }.get(mode, "Write")
        self._begin_model_activity(task_name, writer_model)
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
                self._ensure_model_loaded(writer_model)
                if mode == "rewrite":
                    # A replacement draft must not inherit earlier failed
                    # drafts or chat turns from the same persistent local session.
                    self.engine.clear_context()
                self._schedule_activity_status(task_name, writer_model, "Generating")
                attach_trace = getattr(self.engine, "attach_prompt_trace", None)
                if prompt_trace is not None and callable(attach_trace):
                    try:
                        try:
                            attach_trace(prompt_trace, role="scene_writer")
                        except TypeError:
                            attach_trace(prompt_trace)
                    except Exception:
                        pass
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
        model_name = self._activity_model_label(self.loaded_model) if self.loaded_model else "model"
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
        self._set_activity_status(
            {
                "continue": "Continue",
                "rewrite": "Rewrite Scene",
            }.get(self._generation_mode, "Write"),
            getattr(self, "_activity_model_path", None) or self.loaded_model,
            "Finished",
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
        self._set_activity_status(
            {
                "continue": "Continue",
                "rewrite": "Rewrite Scene",
            }.get(getattr(self, "_generation_mode", "write"), "Write"),
            getattr(self, "_activity_model_path", None),
            "Stopped",
        )
        if was_rewrite:
            self.status_var.set(
                "Rewrite stopped. The previous draft was restored. "
                "Load the model again before continuing."
            )
        else:
            self.status_var.set(
                "Writing stopped. Partial text is kept. The selected writing model will load automatically next time."
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
        self._set_activity_status(
            {
                "continue": "Continue",
                "rewrite": "Rewrite Scene",
            }.get(getattr(self, "_generation_mode", "write"), "Write"),
            getattr(self, "_activity_model_path", None),
            "Error",
        )
        self.status_var.set("Writing failed. The selected writing model will load automatically on the next attempt if needed.")
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

        self._set_activity_status(
            "Update Scene State",
            getattr(self, "_activity_model_path", None) or self.loaded_model,
            "Error" if error or reset_error else "Finished",
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
            self._set_activity_status("Update Scene State", None, "Not loaded")
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
        self._set_activity_status(
            "Update Scene State", model_path, "Generating"
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
        chapter_number = getattr(self, "chapter_numbers", {}).get(chapter_label)
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

        self._clear_prepared_scene_target()
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
        self.planner_model_picker.configure(state="readonly" if idle else "disabled")
        self.refresh_button.configure(state="normal" if idle else "disabled")
        if hasattr(self, "openrouter_button"):
            self.openrouter_button.configure(state="normal" if idle else "disabled")
        if hasattr(self, "novel_picker"):
            self.novel_picker.configure(state="readonly" if idle else "disabled")
            self.refresh_novels_button.configure(state="normal" if idle else "disabled")
            self.chapter_picker.configure(state="readonly" if idle else "disabled")
            self.scene_picker.configure(state="readonly" if idle else "disabled")
            if hasattr(self, "new_chapter_button"):
                selected_novel_path = self.novel_packages.get(self.novel_var.get().strip())
                selected_chapter = self.chapter_numbers.get(self.chapter_var.get().strip())
                available_chapters = list_scene_chapters(selected_novel_path) if selected_novel_path else []
                has_saved_scenes = bool(
                    selected_novel_path is not None
                    and selected_chapter is not None
                    and list_scene_files(selected_novel_path, selected_chapter)
                )
                self.new_chapter_button.configure(
                    state=(
                        "normal"
                        if idle and has_saved_scenes and available_chapters
                        and selected_chapter == max(available_chapters)
                        else "disabled"
                    )
                )
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
        has_planner_model = self._selected_role_model("planner") is not None
        has_writer_model = self._selected_role_model("writer") is not None
        self.load_button.configure(
            state="normal" if idle and has_writer_model else "disabled"
        )
        if hasattr(self, "scene_cast_button"):
            has_selected_novel = self.novel_var.get().strip() in self.novel_packages
            self.scene_cast_button.configure(
                state="normal" if idle and has_selected_novel else "disabled"
            )
        if hasattr(self, "prepare_scene_button"):
            has_selected_novel = (
                self.novel_var.get().strip() in self.novel_packages
            )
            self.prepare_scene_button.configure(
                state=(
                    "normal"
                    if idle and has_planner_model and has_selected_novel
                    else "disabled"
                )
            )
        self.write_button.configure(
            state="normal" if idle and has_writer_model else "disabled"
        )
        if hasattr(self, "minimal_test_button"):
            self.minimal_test_button.configure(
                state="normal" if idle and has_writer_model else "disabled"
            )
        if hasattr(self, "full_context_button"):
            self.full_context_button.configure(
                state="normal" if idle and has_writer_model else "disabled"
            )
        if hasattr(self, "rewrite_scene_button"):
            self.rewrite_scene_button.configure(
                state="normal" if idle and has_writer_model else "disabled"
            )
        self.continue_button.configure(
            state="normal" if idle and has_writer_model else "disabled"
        )
        self.new_session_button.configure(
            state="normal" if idle and has_writer_model else "disabled"
        )
        if hasattr(self, "upload_trace_button"):
            trace_path = Path(
                getattr(self, "_last_prompt_trace_path", None) or default_prompt_trace_path()
            ).expanduser()
            self.upload_trace_button.configure(
                state=(
                    "normal"
                    if idle
                    and not getattr(self, "_trace_upload_busy", False)
                    and trace_path.is_file()
                    else "disabled"
                )
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
