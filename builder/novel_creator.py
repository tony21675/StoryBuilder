from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from builder.workspace import NOVEL_ROOT


def suggest_folder_name(title: str) -> str:
    """Return a readable, safe folder-name suggestion from a novel title."""
    candidate = re.sub(r"[^\w.-]+", "-", str(title).strip(), flags=re.UNICODE)
    candidate = candidate.strip(" .-_")
    return candidate or "New-Novel"


def _validate_folder_name(folder_name: str) -> str:
    name = str(folder_name).strip()
    if not name or name in {".", ".."}:
        raise ValueError("Enter a folder name, or leave it blank to use the title.")
    if name.startswith("."):
        raise ValueError("The folder name cannot start with a dot.")
    if any(character in name for character in ("/", "\\", "\0")):
        raise ValueError("Use a folder name only, not a path or separator.")
    if Path(name).is_absolute() or Path(name).name != name:
        raise ValueError("Use a single folder name, not a path.")
    return name


def create_novel_package(
    title: str,
    folder_name: str | None = None,
    novel_root: str | Path | None = None,
) -> Path:
    """Create a new empty novel package the Minimal Writer can discover.

    The new package includes story_bible.json and Manuscript/Chapters/.
    Existing paths are never overwritten. If initialization fails after the new
    directory is created, only that newly created directory is removed.
    """
    clean_title = str(title).strip()
    if not clean_title:
        raise ValueError("Enter a title for the new novel.")

    requested_name = str(folder_name or "").strip()
    safe_name = _validate_folder_name(
        requested_name if requested_name else suggest_folder_name(clean_title)
    )

    root = Path(novel_root if novel_root is not None else NOVEL_ROOT).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = (root / safe_name).resolve()
    if target.parent != root:
        raise ValueError("The novel folder must be directly inside the novel library.")
    if target.exists():
        raise FileExistsError(
            f"A file or folder already exists at this location:\n{target}\n\n"
            "Choose another folder name. Existing content was not changed."
        )

    target.mkdir()
    try:
        story_bible = {
            "story_format_version": "1.0",
            "title": clean_title,
            "version": "1.0",
            "status": "active",
            "premise": "",
            "setting": "",
            "canon_rules": [],
            "character_cards": [],
            "relationships": {},
            "locations": {},
            "story_planning": {},
        }
        (target / "story_bible.json").write_text(
            json.dumps(story_bible, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (target / "Manuscript" / "Chapters").mkdir(parents=True)
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise

    return target
