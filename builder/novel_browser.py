from __future__ import annotations

import re
from pathlib import Path

from builder.workspace import NOVEL_ROOT, find_novel_packages


_CHAPTER_RE = re.compile(r"^Chapter_(\d+)$", re.IGNORECASE)
_SCENE_RE = re.compile(r"^Chapter_(\d+)_Section_(\d+)\.txt$", re.IGNORECASE)


def list_novel_packages(novel_root: str | Path | None = None) -> list[Path]:
    """Return the configured one-level-deep novel packages."""
    return find_novel_packages(Path(novel_root) if novel_root is not None else NOVEL_ROOT)


def _chapter_directories(novel_path: str | Path) -> list[tuple[int, Path]]:
    chapters_root = Path(novel_path).expanduser() / "Manuscript" / "Chapters"
    if not chapters_root.is_dir():
        return []

    chapters: list[tuple[int, Path]] = []
    try:
        for child in chapters_root.iterdir():
            match = _CHAPTER_RE.fullmatch(child.name)
            if child.is_dir() and match:
                chapters.append((int(match.group(1)), child))
    except OSError:
        return []

    return sorted(chapters, key=lambda item: (item[0], item[1].name.casefold()))


def list_scene_chapters(novel_path: str | Path) -> list[int]:
    """List chapter numbers that have a matching Manuscript/Chapters folder."""
    return sorted({number for number, _path in _chapter_directories(novel_path)})


def list_scene_files(novel_path: str | Path, chapter_number: int) -> list[tuple[int, Path]]:
    """List accepted scene text files for one chapter, ordered by scene number.

    Supporting before/after state JSON files and other files are deliberately
    excluded. This browser only reads a scene's plain-text manuscript file.
    """
    target = int(chapter_number)
    chapter_path = next(
        (path for number, path in _chapter_directories(novel_path) if number == target),
        None,
    )
    if chapter_path is None:
        return []

    scenes: list[tuple[int, Path]] = []
    try:
        for child in chapter_path.iterdir():
            match = _SCENE_RE.fullmatch(child.name)
            if child.is_file() and match and int(match.group(1)) == target:
                scenes.append((int(match.group(2)), child))
    except OSError:
        return []

    return sorted(scenes, key=lambda item: (item[0], item[1].name.casefold()))
