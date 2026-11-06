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
from builder.story_craft import build_story_craft_prompt
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
        sections.append(
            "No saved previous scene was selected. Treat this as the novel's opening scene."
        )

    author_direction_text = str(author_direction or "").strip()
    if author_direction_text:
        sections.append(
            "AUTHOR'S DIRECTION (OPTIONAL; FOLLOW THIS STEERING)\n"
            + author_direction_text
            + "\nHonor the author's intended event, focus, and outcome for this scene. "
            "Use the previous scene, established characters, story facts, canon, and "
            "timeline to shape a natural continuation; do not replace the author's "
            "direction with an unrelated scene idea."
        )

    sections.extend(
        [
            "",
            "Build directly on the selected previous scene and the latest established situation. Continue its natural momentum instead of restarting a completed activity or jumping to an unrelated task. Give one coherent, specific scene direction rather than a list of alternatives. The scene may contribute through character development, relationships, choices, or events that grow naturally from what is already happening, but it does not need to introduce a new task, problem, decision, or change of activity. Ordinary conversation, recreation, observation, shared experiences, and comfortable silence can make a scene worthwhile in themselves. Do not invent an activity merely to create a sense of progress; follow the story's natural momentum and the author's direction.",
            "Use the established character roster as authoritative. Do not invent extra members of an established crew, team, household, or similar group. Keep track of who is already present, who is elsewhere, and who is actually arriving.",
            "Use the timeline anchor and the previous scene to maintain the passage of time. Do not invent a mystery, danger, anomaly, or interruption merely to create a hook; let new developments arise from the established story and the author's direction.",
            "Prepare a compact, editable writing direction in exactly two labeled parts: 'Scene direction:' followed by two to four concise sentences describing what should happen next, and 'Natural endpoint:' followed by one sentence describing a clear, concrete final beat that naturally closes this scene.",
            "Choose an endpoint that fits the proposed scene and leaves the next scene free to begin with the next activity. The endpoint must be the last beat of this scene, not merely something that happens near the end. Prefer a completed action, response, or settled moment; avoid ending on an unfinished exchange or the start of another activity. Do not force a cliffhanger, prescribe every beat, or make the endpoint generic. The writer should finish on this beat and stop rather than continuing afterward.",
            "Do not write finished scene prose, dialogue, or a beat-by-beat outline. Leave room for the story and characters to develop naturally. Return only the two labeled parts followed by this exact instruction: 'Write natural manuscript prose only; do not repeat these labels, and stop at the natural endpoint.'",
        ]
    )
    return "\n\n".join(sections)
