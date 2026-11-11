from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from builder.creative_direction import build_creative_direction_prompt
from builder.odt_document import read_document
from builder.story_bible_reader import load_story_bible
from builder.character_context import (\n    build_character_card_context_prompt,\n    build_story_bible_reference_context,\n)
from builder.story_timeline import build_story_timeline_prompt


_SCENE_FILENAME_RE = re.compile(
    r"^Chapter_(\d+)_Section_(\d+)\.(?:odt|txt)$",
    re.IGNORECASE,
)

def scene_number_from_label(label: str | None) -> int | None:
    """Read the number from a visible Scene NN selector label."""
    match = re.fullmatch(r"Scene\s+(\d+)", str(label or "").strip(), re.IGNORECASE)
    return int(match.group(1)) if match else None


def next_scene_coordinates(
    selected_chapter: int | None,
    selected_scene_path: str | Path | None,
    selected_scene_number: int | None = None,
) -> tuple[int, int]:
    """Return the next scene after the selected scene, or the opening scene."""
    chapter = max(1, int(selected_chapter or 1))
    if selected_scene_path is not None:
        match = _SCENE_FILENAME_RE.fullmatch(Path(selected_scene_path).name)
        if match:
            return int(match.group(1)), int(match.group(2)) + 1
    if selected_scene_number is not None and int(selected_scene_number) >= 1:
        return chapter, int(selected_scene_number) + 1
    return chapter, 1


def resolve_scene_preparation_target(
    selected_chapter: int | None,
    selected_scene_path: str | Path | None,
    selected_scene_number: int | None = None,
    *,
    novel_path: str | Path | None = None,
    pending_destination: tuple[int, int] | None = None,
    pending_novel_path: str | Path | None = None,
    pending_source_scene_path: str | Path | None = None,
) -> tuple[int, int, Path | None, bool]:
    """Reuse an unsaved prepared scene when retrying; otherwise move past the selection."""
    chapter = max(1, int(selected_chapter or 1))
    current_position = (chapter, int(selected_scene_number or 0))

    same_novel = (
        novel_path is not None
        and pending_novel_path is not None
        and Path(novel_path).expanduser() == Path(pending_novel_path).expanduser()
    )
    is_retry = (
        same_novel
        and pending_destination is not None
        and current_position == pending_destination
        and selected_scene_path is None
    )
    if is_retry:
        previous_scene = (
            Path(pending_source_scene_path)
            if pending_source_scene_path is not None
            else None
        )
        return pending_destination[0], pending_destination[1], previous_scene, True

    target_chapter, target_scene = next_scene_coordinates(
        selected_chapter, selected_scene_path, selected_scene_number
    )
    previous_scene = (
        Path(selected_scene_path) if selected_scene_path is not None else None
    )
    return target_chapter, target_scene, previous_scene, False


def _read_current_state(novel_path: Path) -> dict[str, Any]:
    state_path = novel_path / "current_state.json"
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _clean_text(value: Any, limit: int = 600) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip() + "…"
    return text


def _previous_scene_text(path: str | Path | None) -> str:
    """Read the complete immediately preceding saved scene for planning context."""
    if path is None:
        return ""
    return read_document(path).strip()


def _state_matches_scene(
    state: dict[str, Any],
    chapter_number: int,
    scene_number: int,
    source_scene_path: str | Path | None,
) -> bool:
    try:
        state_position = (int(state.get("chapter")), int(state.get("scene")))
    except (TypeError, ValueError):
        return False

    if state_position == (chapter_number, scene_number):
        return True

    # Some packages save the state immediately after completing the previous
    # scene rather than at the start of the next one.
    if source_scene_path is not None:
        match = _SCENE_FILENAME_RE.fullmatch(Path(source_scene_path).name)
        if match:
            source_position = (int(match.group(1)), int(match.group(2)))
            return state_position == source_position and state.get("scene_completed") is True
    return False


def build_scene_preparation_prompt(
    novel_path: str | Path,
    novel_name: str,
    chapter_number: int,
    scene_number: int,
    source_scene_path: str | Path | None = None,
    author_direction: str | None = None,
    previous_direction: str | None = None,
) -> str:
    """Build a lean planning request with only the current scene's useful context."""
    root = Path(novel_path).expanduser()
    try:
        story_bible = load_story_bible(root)
    except FileNotFoundError:
        story_bible = {}

    current_state = _read_current_state(root)
    include_state = _state_matches_scene(
        current_state, int(chapter_number), int(scene_number), source_scene_path
    )
    previous_ending = _previous_scene_text(source_scene_path)

    title = _clean_text(story_bible.get("title"), limit=120) or _clean_text(
        novel_name, limit=120
    )
    author_direction_text = str(author_direction or "").strip()
    previous_direction_text = _clean_text(previous_direction, limit=1200)
    sections = [
        "Help the author prepare a natural direction for the next scene. This is planning, not manuscript prose.",
        f"Destination: Chapter {int(chapter_number):02d}, Scene {int(scene_number):02d}.",
        f"Story: {title}",
    ]

    premise = _clean_text(story_bible.get("premise"), limit=600)
    setting = _clean_text(story_bible.get("setting"), limit=600)
    if premise:
        sections.append(f"Premise: {premise}")
    if setting:
        sections.append(f"Setting: {setting}")

    story_reference = build_story_bible_reference_context(
        story_bible, include_preferences=True
    )
    if story_reference:
        sections.append(story_reference)

    creative_direction = build_creative_direction_prompt(
        story_bible.get("creative_direction")
    )
    if creative_direction:
        sections.append(creative_direction)

    cast_names: list[str] = []
    timeline_note = build_story_timeline_prompt(current_state.get("time_of_day"))
    if timeline_note:
        sections.append(timeline_note)

    if include_state:
        situation = _clean_text(current_state.get("current_situation"), limit=600)
        if situation:
            sections.append("CURRENT STORY SITUATION\n" + situation)

        continuity_notes = current_state.get("continuity_notes")
        if isinstance(continuity_notes, list):
            notes = [
                _clean_text(note, limit=500)
                for note in continuity_notes
                if isinstance(note, str) and note.strip()
            ][:6]
            if notes:
                sections.append(
                    "CURRENT CONTINUITY NOTES\n" + "\n".join(f"- {note}" for note in notes)
                )

        locations = current_state.get("location")
        if isinstance(locations, dict):
            primary_location = _clean_text(locations.get("primary"), limit=120)
            if primary_location:
                sections.append(f"Current location: {primary_location}")

        cast_value = current_state.get("scene_cast")
        if isinstance(cast_value, list):
            cast_names = [
                _clean_text(name, limit=80)
                for name in cast_value
                if isinstance(name, str) and name.strip()
            ][:8]
            if cast_names:
                sections.append("People currently involved: " + ", ".join(cast_names))

        questions = current_state.get("unresolved_questions")
        if isinstance(questions, list):
            open_questions = [
                _clean_text(question, limit=160)
                for question in questions
                if isinstance(question, str) and question.strip()
            ][:2]
            if open_questions:
                sections.append("Still unresolved: " + " ".join(open_questions))

    character_query = "\n".join(
        part for part in (
            " ".join(cast_names),
            previous_ending,
            author_direction_text,
        ) if part
    )
    character_context = build_character_card_context_prompt(
        root,
        story_bible,
        "",
        supporting_text=character_query,
        include_all=not bool(character_query),
        compact=True,
    )
    if character_context:
        sections.append(character_context)

    if previous_ending:
        sections.append(
            "IMMEDIATELY PRECEDING SAVED SCENE (full continuity reference)\n" + previous_ending
        )
        sections.append(
            "PREVIOUS SCENE CONTINUITY\n"
            "Use the previous scene as context, not as a template. "
            "Let the new scene feel like a natural continuation of the same story; "
            "time, place, and focus may change when it makes sense."
        )
    elif (int(chapter_number), int(scene_number)) == (1, 1):
        sections.append("This is the opening scene; no previous scene has been saved.")

    if previous_direction_text:
        sections.append(
            "PREVIOUS PREPARED DIRECTION TO REFINE\n" + previous_direction_text
        )
        sections.append(
            "Refine the previous direction rather than starting over."
        )

    if author_direction_text:
        sections.append("AUTHOR'S DIRECTION\n" + author_direction_text)

    sections.extend(
        [
            "Use the scene context as a starting point. Gaps are creative space; develop plausible details and interactions without treating every unknown as a prohibition.",
            "Return one concise 'Scene direction:' that expresses the author's intent for this scene. "
            "Treat events the author explicitly asks to happen as intended events, not optional possibilities. "
            "Leave how they unfold and where the scene ends to the Writer. Do not write manuscript prose.",
        ]
    )
    return "\n\n".join(part for part in sections if part)
