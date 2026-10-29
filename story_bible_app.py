from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from builder.novel_creator import create_novel_package, suggest_folder_name
from builder.workspace import NOVEL_ROOT
from minimal_writer import bind_ctrl_a_select_all


class StoryBibleApp:
    """First stage of Story Bible: create an empty, Writer-compatible novel package."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Story Bible - Create a Novel")
        self.root.geometry("760x440")
        self.root.minsize(620, 400)

        self.title_var = tk.StringVar()
        self.folder_var = tk.StringVar()
        self.status_var = tk.StringVar(
            value="Ready. Creating a package will not overwrite existing files."
        )
        self._folder_manually_edited = False

        outer = ttk.Frame(root, padding=20)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer, text="Story Bible", font=("TkDefaultFont", 18, "bold")
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "Start with a new novel package. Story Bible editing and planning "
                "will be added in later steps."
            ),
            wraplength=700,
        ).pack(anchor="w", pady=(4, 18))

        ttk.Label(outer, text="Novel title").pack(anchor="w")
        self.title_entry = ttk.Entry(outer, textvariable=self.title_var)
        self.title_entry.pack(fill="x", pady=(4, 12))
        self.title_entry.bind("<KeyRelease>", self._suggest_folder_name)

        ttk.Label(outer, text="Folder name (optional)").pack(anchor="w")
        ttk.Entry(outer, textvariable=self.folder_var).pack(fill="x", pady=(4, 3))
        ttk.Label(
            outer,
            text="Leave blank to make a safe folder name from the title.",
            foreground="gray",
        ).pack(anchor="w", pady=(0, 14))

        ttk.Label(outer, text="Novel library").pack(anchor="w")
        root_entry = ttk.Entry(outer)
        root_entry.insert(0, str(NOVEL_ROOT))
        root_entry.configure(state="readonly")
        root_entry.pack(fill="x", pady=(4, 14))

        self.create_button = ttk.Button(
            outer, text="Create Novel Package", command=self.create_novel
        )
        self.create_button.pack(anchor="w")

        ttk.Label(
            outer, textvariable=self.status_var, anchor="w", justify="left",
            wraplength=700,
        ).pack(fill="x", pady=(14, 0))

        self.title_entry.focus_set()

    def _suggest_folder_name(self, _event=None) -> None:
        # Only update the folder field while the author hasn't explicitly typed
        # a custom folder name.
        if not self._folder_manually_edited:
            self.folder_var.set(suggest_folder_name(self.title_var.get()))

    def create_novel(self) -> None:
        title = self.title_var.get()
        folder = self.folder_var.get()
        if not title.strip():
            self.status_var.set("Enter a title for the new novel.")
            self.title_entry.focus_set()
            return
        try:
            package_path = create_novel_package(title, folder)
        except (OSError, ValueError) as exc:
            self.status_var.set("Novel package was not created.")
            messagebox.showerror("Could not create novel", str(exc), parent=self.root)
            return

        self.status_var.set(
            f"Created successfully:\n{package_path}\n\n"
            "The Minimal Writer can find it after you click Refresh Novels. "
            "No files were overwritten."
        )
        self.title_var.set("")
        self.folder_var.set("")
        self._folder_manually_edited = False
        self.title_entry.focus_set()


def main() -> None:
    root = tk.Tk()
    StoryBibleApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
