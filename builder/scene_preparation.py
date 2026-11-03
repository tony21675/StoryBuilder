from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from builder.odt_document import read_document
from builder.story_bible_reader import load_story_bible
from builder.canon_rules import build_canon_rules_prompt
from builder.creative_direction import build_creative_direction_prompt
from builder.character_context import build_character_card_context_prompt
from builder.story_pacing import build_story_opening_pacing_prompt


_SCENE_FILENAME_RE = re.compile(
    r"^Chapter_(\d+)_Section_(\d+)\.(?:odt|txt)$",
    re.IGNORECASE,
)
_PREVIOUS_SCENE_CHARS = 2200


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


def _read_current_state(novel_path: Path) -> dict[str, Any]:
    state_path = novel_path / "current_state.json"
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _clean_text(value: Any, limit: int = 1200) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip() + "…"
    return text


def _previous_scene_ending(path: str | Path | None) -> str:
    if path is None:
        return ""
    text = read_document(path).strip()
    if len(text) > _PREVIOUS_SCENE_CHARS:
        text = text[-_PREVIOUS_SCENE_CHARS:]
        first_break = text.find("\n")
        if 0 <= first_break < 240:
            text = text[first_break + 1 :]
    return text.strip()


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
) -> str:
    """Build a compact, read-only planning request for one scene starter."""
    root = Path(novel_path).expanduser()
    try:
        story_bible = load_story_bible(root)
    except FileNotFoundError:
        story_bible = {}

    current_state = _read_current_state(root)
    include_state = _state_matches_scene(
        current_state, int(chapter_number), int(scene_number), source_scene_path
    )
    previous_ending = _previous_scene_ending(source_scene_path)

    title = _clean_text(story_bible.get("title")) or _clean_text(novel_name)
    sections = [
        "Help the author prepare a starting direction for the next scene. This is planning, not scene prose.",
        f"Destination: Chapter {int(chapter_number):02d}, Scene {int(scene_number):02d}.",
        f"Story: {title}",
        build_story_opening_pacing_prompt(),
    ]

    premise = _clean_text(story_bible.get("premise"))
    setting = _clean_text(story_bible.get("setting"))
    if premise:
        sections.append(f"Premise: {premise}")
    if setting:
        sections.append(f"Setting: {setting}")
    canon_rules_note = build_canon_rules_prompt(story_bible.get("canon_rules"))
    if canon_rules_note:
        sections.append(canon_rules_note)
    cast_names: list[str] = []
    if include_state:
        cast_value = current_state.get("scene_cast")
        if isinstance(cast_value, list):
            cast_names = [str(name).strip() for name in cast_value if str(name).strip()]
    character_context = build_character_card_context_prompt(
        root,
        story_bible,
        " ".join(cast_names),
        include_all=not cast_names,
    )
    if character_context:
        sections.append(character_context)

    creative_note = build_creative_direction_prompt(
        story_bible.get("creative_direction")
    )
    if creative_note:
        sections.append(creative_note)

    if include_state:
        situation = _clean_text(current_state.get("current_situation"))
        if situation:
            sections.append(f"Current situation: {situation}")

        locations = current_state.get("location")
        if isinstance(locations, dict):
            primary_location = _clean_text(locations.get("primary"), limit=240)
            if primary_location:
                sections.append(f"Current main location: {primary_location}")

        cast = current_state.get("scene_cast")
        if isinstance(cast, list):
            names = [
                _clean_text(name, limit=100)
                for name in cast
                if isinstance(name, str) and name.strip()
            ][:8]
            if names:
                sections.append("People currently involved: " + ", ".join(names))

        questions = current_state.get("unresolved_questions")
        if isinstance(questions, list):
            open_questions = [
                _clean_text(question, limit=220)
                for question in questions
                if isinstance(question, str) and question.strip()
            ][:3]
            if open_questions:
                sections.append(
                    "Still unresolved: " + " ".join(open_questions)
                )

    if previous_ending:
        sections.append(
            "Ending of the selected previous scene (for continuity):\n"
            + previous_ending
        )
    else:
        sections.append(
            "No saved previous scene was selected. Treat this as the novel's opening scene."
        )

    sections.extend(
        [
            "",
            "Use this context for orientation, not as a checklist. Suggest a natural situation to begin this scene and a promising direction it could take.",
            "Write only a few concise, editable sentences for the author. Do not write the finished scene or dialogue, do not make a beat-by-beat outline, and leave unresolved matters open. Leave room for the story and characters to develop naturally.",
            "Return only the scene starter, with no heading or explanation.",
        ]
    )
    return "\n\n".join(sections)
