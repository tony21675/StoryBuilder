from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText

from builder.writer_engine import GenerationInterrupted, WriterEngine
from builder.workspace import MODELS_DIR, NOVEL_ROOT
from builder.novel_browser import list_novel_packages, list_scene_chapters, list_scene_files
from builder.novel_git_sync import (
    NovelGitSyncError,
    inspect_novel_repository,
    sync_novel_repository,
)


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


def build_revision_prompt(selected_text: str, instruction: str) -> str:
    """Ask the model to revise only the selected passage, following the author's instruction."""
    return (
        "Revise only the selected passage according to the author's instruction. "
        "Return only the revised passage, with no commentary, label, or explanation. "
        "Do not continue beyond the passage. Preserve its intended meaning and events "
        "unless the instruction explicitly asks for a change.\\n\\n"
        f"Author's instruction:\\n{instruction.strip()}\\n\\n"
        f"Selected passage to revise:\\n{selected_text}"
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

        ttk.Label(outer, text="What should it write?").pack(anchor="w")
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
            actions, text="Save", command=self.save_output
        )
        self.save_button.pack(side="left", padx=(8, 0))

        self.save_as_button = ttk.Button(
            actions, text="Save As…", command=self.save_output_as
        )
        self.save_as_button.pack(side="left", padx=(8, 0))

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
        self.output_box = ScrolledText(
            outer, height=22, wrap="word", undo=True, font=("TkDefaultFont", 11)
        )
        self.output_box.pack(fill="both", expand=True, pady=(4, 8))
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
            if not self._revision_target_is_unchanged():
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
            start = self.output_box.index(self._revision_start_mark)
            proposed_text = proposal_box.get("1.0", "end-1c")
            self.output_box.delete(self._revision_start_mark, self._revision_end_mark)
            self.output_box.insert(start, proposed_text)
            self.output_box.mark_set("insert", start)
            self.output_box.see("insert")
            self.output_box.edit_modified(False)
            self._discard_revision()
            dialog.destroy()
            self.status_var.set("Revision applied to selected passage. Save when ready.")
            self._update_document_title()
            self._update_controls()

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
                f"No saved scene text files found for {self.chapter_var.get() or 'this chapter'}. "
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
            text = read_text_document(source)
        except (OSError, UnicodeError) as exc:
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

        self._begin_generation(prompt, mode="write")

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

        self._begin_generation(build_continue_prompt(existing_text), mode="continue")

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

    def _begin_generation(self, prompt: str, mode: str) -> None:
        # Keep the previous document recoverable so errors or an immediate Stop
        # do not destroy the author's text.
        self._pre_generation_text = self._output_text()
        self._pre_generation_file = self.current_file
        self._pre_generation_saved_text = self.saved_output_text
        self._generation_mode = mode
        self._generation_had_chunks = False
        if mode == "continue":
            self._generation_prefix = continuation_prefix(self._pre_generation_text)
            self._set_output_text(self._generation_prefix)
        else:
            self._generation_prefix = ""
            self._set_output_text("")

        self.busy = True
        self.writing = True
        self.stop_requested = False
        action = "Continuing" if mode == "continue" else "Writing"
        self.status_var.set(f"{action} with {self.loaded_model.name}…")
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
            try:
                answer = write_from_prompt(self.engine, prompt, on_delta=stream_delta)
            except GenerationInterrupted:
                self.root.after(0, self._write_stopped)
            except Exception as exc:
                message = str(exc)
                self.root.after(0, lambda message=message: self._write_failed(message))
            else:
                self.root.after(0, lambda answer=answer: self._write_succeeded(answer))

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
        action = "continuing" if self._generation_mode == "continue" else "writing"
        self.status_var.set(f"Finished {action} with {model_name}. Edit the output or save it.")
        self._update_controls()

    def _write_stopped(self) -> None:
        # Keep any words already streamed. If none arrived before Stop was
        # pressed, restore the document that was open before generation.
        if not self._generation_had_chunks:
            self._restore_pre_generation_output()
        self._finish_stopped()

    def _finish_stopped(self) -> None:
        self.busy = False
        self.writing = False
        self.loaded_model = None
        self.stop_requested = False
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
        return self.output_box.get("1.0", "end-1c")

    def _set_output_text(self, text: str) -> None:
        self.output_box.delete("1.0", "end")
        self.output_box.insert("1.0", text)
        self.output_box.edit_modified(False)
        self._update_document_title()

    def _on_output_modified(self, _event=None) -> None:
        if self.output_box.edit_modified():
            self.output_box.edit_modified(False)
            self._update_document_title()

    def _update_document_title(self) -> None:
        label = self.current_file.name if self.current_file is not None else "Untitled"
        dirty = self._output_text() != self.saved_output_text
        marker = "*" if dirty else ""
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
            "title": "Open text",
            "filetypes": [("Text files", "*.txt"), ("All files", "*.*")],
        }
        if self.current_file is not None:
            options["initialdir"] = str(self.current_file.parent)
        filename = filedialog.askopenfilename(**options)
        if not filename:
            return

        try:
            text = read_text_document(filename)
        except (OSError, UnicodeError) as exc:
            self._showerror("Could not open text", str(exc))
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
        options = {
            "title": "Save text as",
            "defaultextension": ".txt",
            "filetypes": [("Text files", "*.txt"), ("All files", "*.*")],
            "initialfile": (
                self.current_file.name if self.current_file
                else self.selected_scene_source.name if self.selected_scene_source
                else "draft.txt"
            ),
        }
        if self.current_file is not None:
            options["initialdir"] = str(self.current_file.parent)
        filename = filedialog.asksaveasfilename(**options)
        if not filename:
            return False
        return self._save_to_path(Path(filename))

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
            saved_path = save_text_document(target, text)
        except (OSError, UnicodeError) as exc:
            self._showerror("Could not save scene", str(exc))
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
            saved_path = save_text_document(path, text)
        except (OSError, UnicodeError) as exc:
            self._showerror("Could not save text", str(exc))
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
                state="normal" if idle and bool(self.scene_files) else "disabled"
            )
            self.sync_novel_button.configure(
                state=(
                    "normal"
                    if idle and self.novel_var.get().strip() in self.novel_packages
                    else "disabled"
                )
            )
        self.load_button.configure(state="normal" if idle else "disabled")
        self.write_button.configure(
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
        self.save_scene_button.configure(
            state=(
                "normal"
                if idle
                and self.selected_scene_source is not None
                and bool(self.scene_files)
                else "disabled"
            )
        )
        self.revise_selection_button.configure(state="normal" if idle else "disabled")
        stopping = self.stop_requested
        self.stop_button.configure(
            state="normal" if self.busy and self.writing and not stopping else "disabled",
            text="Stopping…" if stopping else "Stop Writing",
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
