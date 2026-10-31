from __future__ import annotations

import re
from pathlib import Path

from builder.workspace import NOVEL_ROOT, find_novel_packages


_CHAPTER_RE = re.compile(r"^Chapter_(\d+)$", re.IGNORECASE)
_SCENE_RE = re.compile(
    r"^Chapter_(\d+)_Section_(\d+)\.(odt|txt)$",
    re.IGNORECASE,
)


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
    """List accepted scene documents, preferring ODT over a matching legacy TXT.

    Supporting before/after state JSON files, drafts, and other files are
    deliberately excluded. If both formats exist for a scene, only the ODT
    version is shown so the browser never presents duplicate scene entries.
    """
    target = int(chapter_number)
    chapter_path = next(
        (path for number, path in _chapter_directories(novel_path) if number == target),
        None,
    )
    if chapter_path is None:
        return []

    scenes: dict[int, Path] = {}
    try:
        for child in chapter_path.iterdir():
            match = _SCENE_RE.fullmatch(child.name)
            if not child.is_file() or not match or int(match.group(1)) != target:
                continue
            scene_number = int(match.group(2))
            existing = scenes.get(scene_number)
            if existing is None or child.suffix.casefold() == ".odt":
                scenes[scene_number] = child
    except OSError:
        return []

    return sorted(scenes.items(), key=lambda item: (item[0], item[1].name.casefold()))
