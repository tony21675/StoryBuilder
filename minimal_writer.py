from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from builder.writer_engine import WriterEngine
from builder.workspace import MODELS_DIR


def load_model_for_writing(engine: WriterEngine, model_path: str | Path) -> None:
    """Load the selected local model without adding a writing system prompt."""
    engine.start(model_path, system_prompt="")


def write_from_prompt(engine: WriterEngine, prompt: str) -> str:
    """Send the author's prompt directly to the model without app-generated text."""
    return engine.generate(prompt)


class MinimalWriterApp:
    """A small local-model writing window, with no story-management pipeline."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.engine = WriterEngine()
        self.models: dict[str, Path] = {}
        self.loaded_model: Path | None = None
        self.busy = False

        root.title("StoryBuilder Minimal Writer")
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

        self.save_button = ttk.Button(
            actions, text="Save Output As…", command=self.save_output
        )
        self.save_button.pack(side="left", padx=(8, 0))

        ttk.Label(outer, text="Output (editable)").pack(anchor="w")
        self.output_box = ScrolledText(
            outer, height=22, wrap="word", undo=True, font=("TkDefaultFont", 11)
        )
        self.output_box.pack(fill="both", expand=True, pady=(4, 8))

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
        self.loaded_model = path
        self.status_var.set(f"Loaded: {path.name}")
        self._update_controls()

    def _load_failed(self, message: str) -> None:
        self.busy = False
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

        self.busy = True
        self.output_box.delete("1.0", "end")
        self.status_var.set(f"Writing with {self.loaded_model.name}…")
        self._update_controls()

        def work() -> None:
            try:
                answer = write_from_prompt(self.engine, prompt)
            except Exception as exc:
                message = str(exc)
                self.root.after(0, lambda message=message: self._write_failed(message))
            else:
                self.root.after(0, lambda answer=answer: self._write_succeeded(answer))

        threading.Thread(target=work, daemon=True).start()

    def _write_succeeded(self, answer: str) -> None:
        self.output_box.delete("1.0", "end")
        self.output_box.insert("1.0", answer)
        self.busy = False
        model_name = self.loaded_model.name if self.loaded_model else "model"
        self.status_var.set(f"Finished writing with {model_name}. Edit the output or save it.")
        self._update_controls()

    def _write_failed(self, message: str) -> None:
        self.busy = False
        try:
            still_loaded = self.engine.child is not None and self.engine.child.isalive()
        except Exception:
            still_loaded = False
        if not still_loaded:
            self.loaded_model = None
        self.status_var.set("Writing failed. Reload the model if it is no longer loaded.")
        self._update_controls()
        messagebox.showerror("Writing failed", message)

    def save_output(self) -> None:
        text = self.output_box.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showinfo("Nothing to save", "The output area is empty.")
            return
        filename = filedialog.asksaveasfilename(
            title="Save written text",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="draft.txt",
        )
        if not filename:
            return
        try:
            Path(filename).write_text(text.rstrip() + "\n", encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Could not save text", str(exc))
            return
        self.status_var.set(f"Saved: {filename}")

    def _update_controls(self) -> None:
        idle = not self.busy
        self.model_picker.configure(state="readonly" if idle else "disabled")
        self.refresh_button.configure(state="normal" if idle else "disabled")
        self.load_button.configure(state="normal" if idle else "disabled")
        self.write_button.configure(
            state="normal" if idle and self.loaded_model is not None else "disabled"
        )
        self.save_button.configure(state="normal" if idle else "disabled")

    def close(self) -> None:
        if self.busy:
            messagebox.showinfo(
                "Model is busy",
                "Wait for the current model task to finish before closing.",
            )
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
