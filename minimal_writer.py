from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from builder.writer_engine import GenerationInterrupted, WriterEngine
from builder.workspace import MODELS_DIR


CONTINUE_PROMPT = (
    "Continue the current passage from where it ended. "
    "Write only new material, without repeating the text already written."
)
CONTINUE_CONTEXT_CHARS = 2000


def build_continue_prompt(existing_text: str) -> str:
    """Include the visible passage ending so Continue respects editor changes."""
    passage_ending = existing_text[-CONTINUE_CONTEXT_CHARS:]
    return f"{CONTINUE_PROMPT}\\n\\nPassage ending for context:\\n{passage_ending}"


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
        self.saved_output_text = ""
        self.busy = False
        self.writing = False
        self.stop_requested = False
        self._pre_generation_text = ""
        self._pre_generation_file: Path | None = None
        self._pre_generation_saved_text = ""
        self._generation_mode = "write"
        self._generation_prefix = ""
        self._generation_had_chunks = False

        root.title("StoryBuilder Minimal Writer - Untitled")
        root.geometry("1080x820")
        root.minsize(760, 600)
        root.protocol("WM_DELETE_WINDOW", self.close)

        self.model_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Choose a model, then load it.")
        self._build_widgets()
        self.refresh_models()

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

        ttk.Label(outer, text="What should it write?").pack(anchor="w")
        self.prompt_box = ScrolledText(
            outer, height=8, wrap="word", undo=True, font=("TkDefaultFont", 11)
        )
        self.prompt_box.pack(fill="both", expand=False, pady=(4, 12))

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

        ttk.Label(outer, text="Output (editable)").pack(anchor="w")
        self.output_box = ScrolledText(
            outer, height=22, wrap="word", undo=True, font=("TkDefaultFont", 11)
        )
        self.output_box.pack(fill="both", expand=True, pady=(4, 8))
        self.output_box.bind("<<Modified>>", self._on_output_modified)
        self.output_box.edit_modified(False)

        ttk.Label(
            outer, textvariable=self.status_var, anchor="w", relief="sunken"
        ).pack(fill="x", side="bottom")

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
            messagebox.showinfo(
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
        messagebox.showerror("Could not load model", message)

    def write(self) -> None:
        if self.busy:
            return
        if self.loaded_model is None:
            messagebox.showinfo("Load a model", "Load a model before writing.")
            return

        prompt = self.prompt_box.get("1.0", "end-1c")
        if not prompt.strip():
            messagebox.showinfo("Add a prompt", "Enter what you want the model to write.")
            return

        self._begin_generation(prompt, mode="write")

    def continue_writing(self) -> None:
        if self.busy:
            return
        if self.loaded_model is None:
            messagebox.showinfo("Load a model", "Load a model before continuing.")
            return

        existing_text = self._output_text()
        if not existing_text.strip():
            messagebox.showinfo(
                "Nothing to continue",
                "Write a passage or open a text file before continuing.",
            )
            return

        self._begin_generation(build_continue_prompt(existing_text), mode="continue")

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
        messagebox.showerror("Writing failed", message)

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
        choice = messagebox.askyesnocancel(
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
            messagebox.showerror("Could not open text", str(exc))
            return

        if not self._confirm_save_pending_changes():
            return

        self.current_file = Path(filename).expanduser().resolve()
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
            "initialfile": self.current_file.name if self.current_file else "draft.txt",
        }
        if self.current_file is not None:
            options["initialdir"] = str(self.current_file.parent)
        filename = filedialog.asksaveasfilename(**options)
        if not filename:
            return False
        return self._save_to_path(Path(filename))

    def _save_to_path(self, path: str | Path) -> bool:
        text = self._output_text()
        try:
            saved_path = save_text_document(path, text)
        except (OSError, UnicodeError) as exc:
            messagebox.showerror("Could not save text", str(exc))
            return False

        self.current_file = saved_path
        self.saved_output_text = text
        self.status_var.set(f"Saved: {saved_path}")
        self._update_document_title()
        return True

    def _update_controls(self) -> None:
        idle = not self.busy
        self.model_picker.configure(state="readonly" if idle else "disabled")
        self.refresh_button.configure(state="normal" if idle else "disabled")
        self.load_button.configure(state="normal" if idle else "disabled")
        self.write_button.configure(
            state="normal" if idle and self.loaded_model is not None else "disabled"
        )
        self.continue_button.configure(
            state="normal" if idle and self.loaded_model is not None else "disabled"
        )
        self.open_button.configure(state="normal" if idle else "disabled")
        self.save_button.configure(state="normal" if idle else "disabled")
        self.save_as_button.configure(state="normal" if idle else "disabled")
        stopping = self.stop_requested
        self.stop_button.configure(
            state="normal" if self.busy and self.writing and not stopping else "disabled",
            text="Stopping…" if stopping else "Stop Writing",
        )

    def close(self) -> None:
        if self.busy:
            messagebox.showinfo(
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
