from __future__ import annotations

from pathlib import Path

from builder.novel_browser import list_scene_chapters, list_scene_files
from builder.odt_document import read_document


def previous_saved_scene(
    novel_path: str | Path,
    target_chapter: int,
    target_scene: int,
) -> tuple[int, int, Path] | None:
    """Find the most recent accepted scene strictly before the target coordinates."""
    root = Path(novel_path).expanduser()
    target = (int(target_chapter), int(target_scene))
    candidates: list[tuple[int, int, Path]] = []

    for chapter in list_scene_chapters(root):
        if chapter > target[0]:
            continue
        for scene_number, path in list_scene_files(root, chapter):
            coordinates = (int(chapter), int(scene_number))
            if coordinates < target:
                candidates.append((coordinates[0], coordinates[1], path))

    return max(candidates, key=lambda item: (item[0], item[1])) if candidates else None


def build_previous_scene_context_prompt(
    prompt: str,
    novel_path: str | Path,
    target_chapter: int,
    target_scene: int,
) -> str:
    """Append the full immediately preceding accepted scene as read-only continuity context."""
    source = previous_saved_scene(novel_path, target_chapter, target_scene)
    if source is None:
        return str(prompt or "")

    source_chapter, source_scene, source_path = source
    try:
        previous_text = read_document(source_path).strip()
    except (OSError, UnicodeError, ValueError):
        return str(prompt or "")

    if not previous_text:
        return str(prompt or "")

    continuity_context = (
        "IMMEDIATELY PRECEDING SAVED SCENE (full text, continuity reference only)\n"
        f"Source: Chapter {source_chapter:02d}, Scene {source_scene:02d}\n"
        "Use this accepted scene to maintain continuity of people, place, objects, "
        "conversation, and events. It is context, not text to repeat or summarize. "
        "Begin after its final moment and follow the current scene direction.\n\n"
        f"{previous_text}"
    )
    base = str(prompt or "").rstrip()
    return f"{base}\n\n{continuity_context}" if base else continuity_context
