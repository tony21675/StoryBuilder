from __future__ import annotations

import re
from pathlib import Path

from builder.novel_browser import list_scene_chapters, list_scene_files
from builder.odt_document import read_document, save_document


def _read_chapter(novel_path: str | Path, chapter_number: int) -> str:
    """Read saved scene files in numerical order and return one chapter body."""
    scenes = list_scene_files(novel_path, int(chapter_number))
    if not scenes:
        raise ValueError(
            f"No saved scenes were found for Chapter {int(chapter_number):02d}."
        )

    prose: list[str] = []
    for scene_number, scene_path in scenes:
        try:
            text = read_document(scene_path).strip()
        except (OSError, UnicodeError, ValueError) as exc:
            raise OSError(
                f"Could not read Scene {scene_number:02d} "
                f"({scene_path.name}): {exc}"
            ) from exc
        if text:
            prose.append(text)

    if not prose:
        raise ValueError(
            f"Chapter {int(chapter_number):02d} has no saved manuscript prose."
        )

    return f"**CHAPTER {int(chapter_number)}**\n\n" + "\n\n".join(prose)


def _compiled_directory(novel_path: str | Path) -> Path:
    return Path(novel_path).expanduser() / "Manuscript" / "Compiled"


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 _-]+", "", str(value or "")).strip()
    cleaned = re.sub(r"[\s-]+", "_", cleaned)
    return cleaned or "Complete_Novel"


def assemble_chapter(novel_path: str | Path, chapter_number: int) -> Path:
    """Assemble one chapter's saved ODT/TXT scenes into a compiled ODT copy."""
    chapter = int(chapter_number)
    content = _read_chapter(novel_path, chapter)
    target = _compiled_directory(novel_path) / f"Chapter_{chapter:02d}.odt"
    return save_document(target, content)


def assemble_finished_novel(
    novel_path: str | Path,
    title: str | None = None,
) -> Path:
    """Assemble all chapters with saved scenes into one compiled ODT copy."""
    chapters: list[str] = []
    for chapter_number in list_scene_chapters(novel_path):
        # Empty chapter folders are not manuscript content; skip them.
        if not list_scene_files(novel_path, chapter_number):
            continue
        chapters.append(_read_chapter(novel_path, chapter_number))

    if not chapters:
        raise ValueError("No saved manuscript scenes were found to assemble.")

    novel_name = str(
        title
        or Path(novel_path).expanduser().name.replace("-", " ").replace("_", " ")
    ).strip()
    content = f"**{novel_name}**\n\n" + "\n\n".join(chapters)
    target = (
        _compiled_directory(novel_path)
        / f"{_safe_filename(novel_name)}_Complete_Novel.odt"
    )
    return save_document(target, content)
