from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from builder.continuity_context import build_location_allowlist_prompt
from builder.odt_document import read_document
from builder.story_bible_reader import load_story_bible
from builder.canon_rules import build_canon_rules_prompt
from builder.creative_direction import build_creative_direction_prompt
from builder.story_craft import build_media_device_prompt, build_story_craft_prompt
from builder.character_context import build_character_card_context_prompt
from builder.story_pacing import build_story_opening_pacing_prompt
from builder.story_timeline import (
    build_current_story_context_prompt,
    build_story_timeline_prompt,
)


_SCENE_FILENAME_RE = re.compile(
    r"^Chapter_(\d+)_Section_(\d+)\.(?:odt|txt)$",
    re.IGNORECASE,
)
_PREVIOUS_SCENE_CHARS = 6000


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
    author_direction: str | None = None,
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
    author_direction_text = str(author_direction or "").strip()
    sections = [
        "Help the author prepare a starting direction for the next scene. This is planning, not scene prose.",
        f"Destination: Chapter {int(chapter_number):02d}, Scene {int(scene_number):02d}.",
        f"Story: {title}",
    ]
    if (int(chapter_number), int(scene_number)) == (1, 1):
        sections.append(build_story_opening_pacing_prompt())

    premise = _clean_text(story_bible.get("premise"))
    setting = _clean_text(story_bible.get("setting"))
    if premise:
        sections.append(f"Premise: {premise}")
    if setting:
        sections.append(f"Setting: {setting}")
    location_allowlist, _location_names = build_location_allowlist_prompt(
        story_bible.get("locations", {})
    )
    sections.append(location_allowlist)
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

    craft_note = build_story_craft_prompt()
    if craft_note:
        sections.append(craft_note)
    media_note = build_media_device_prompt(author_direction_text)
    if media_note:
        sections.append(media_note)

    timeline_note = build_story_timeline_prompt(current_state.get("time_of_day"))
    if timeline_note:
        sections.append(timeline_note)

    if include_state:
        story_context = build_current_story_context_prompt(current_state)
        if story_context:
            sections.append(story_context)

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
            "Selected previous scene context (including its ending, for continuity):\n"
            + previous_ending
        )
    else:
        if (int(chapter_number), int(scene_number)) == (1, 1):
            sections.append("No saved previous scene was selected. Treat this as the novel's opening scene.")
        else:
            sections.append("No saved previous scene text was selected.")

    if author_direction_text:
        sections.append("AUTHOR'S DIRECTION\n" + author_direction_text)

    sections.extend(
        [
            "",
            "Follow the author's direction and continue naturally from the previous scene. A quiet or ordinary moment is valid scene material.",
            "Return exactly two labeled parts: 'Scene direction:' in two to four concise sentences, and 'Natural endpoint:' in one sentence naming the final concrete beat. Stop at that beat.",
            "Do not write manuscript prose or dialogue. Return only those two parts, followed by this exact instruction: 'Write natural manuscript prose only; do not repeat these labels, and stop at the natural endpoint.'",
        ]
    )
    return "\n\n".join(sections)
