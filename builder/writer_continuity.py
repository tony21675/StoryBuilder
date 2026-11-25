from __future__ import annotations

from pathlib import Path

from builder.novel_browser import list_scene_chapters, list_scene_files
from builder.odt_document import read_document
from builder.scene_handoff import format_scene_handoff, load_scene_handoff


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
    *,
    max_chars: int | None = None,
) -> str:
    """Append the prior accepted scene, optionally limited to its ending excerpt."""
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

    handoff = load_scene_handoff(source_path, previous_text)
    if handoff:
        continuity_context = format_scene_handoff(handoff, source_chapter, source_scene)
        base = str(prompt or "").rstrip()
        return f"{base}

{continuity_context}" if base else continuity_context

    excerpt = previous_text
    excerpt_note = "full text"
    if max_chars is not None:
        limit = max(300, int(max_chars))
        if len(excerpt) > limit:
            excerpt = excerpt[-limit:]
            paragraph_start = excerpt.find("\n\n")
            if 0 <= paragraph_start < min(450, limit // 3):
                excerpt = excerpt[paragraph_start + 2:]
            excerpt_note = "brief ending excerpt; earlier scene text omitted"

    continuity_context = (
        f"IMMEDIATELY PRECEDING SAVED SCENE ({excerpt_note}, continuity reference only)\n"
        f"Source: Chapter {source_chapter:02d}, Scene {source_scene:02d}\n"
        "Use this accepted passage only to orient the handoff. Let the next scene feel "
        "like a natural continuation of the same story, starting from what the reader has "
        "just seen. Do not repeat or summarize it.\n\n"
        f"{excerpt}"
    )
    base = str(prompt or "").rstrip()
    return f"{base}\n\n{continuity_context}" if base else continuity_context
