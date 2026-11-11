from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from builder.creative_direction import build_creative_direction_prompt
from builder.odt_document import read_document
from builder.story_bible_reader import load_story_bible
from builder.character_context import (
    build_character_card_context_prompt,
    build_story_bible_reference_context,
)
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


def _planner_location_value(value: Any, *, depth: int = 0) -> str:
    """Render saved location details as readable Planner reference material."""
    if depth > 5 or value is None:
        return ""
    if isinstance(value, dict):
        entries = []
        for key, nested in value.items():
            rendered = _planner_location_value(nested, depth=depth + 1)
            if rendered:
                label = str(key).replace("_", " ").strip().title()
                entries.append(f"{label}: {rendered}")
        return "; ".join(entries)
    if isinstance(value, list):
        return "; ".join(
            rendered
            for item in value
            if (rendered := _planner_location_value(item, depth=depth + 1))
        )
    if isinstance(value, (str, int, float, bool)):
        return " ".join(str(value).split())
    return ""


def _build_planner_location_context(story_bible: dict[str, Any]) -> str:
    """Give Qwen the novel's established places without restricting invention."""
    locations = story_bible.get("locations")
    if not isinstance(locations, dict) or not locations:
        return ""

    lines = [
        "ESTABLISHED LOCATION REFERENCES FROM THIS NOVEL'S STORY BIBLE",
        "These entries describe places already established in this story and provide "
        "geographic and environmental context. They are references, not a restriction on "
        "creative invention or a requirement to include these places. Use them when "
        "relevant; new locations and details remain creative space unless they contradict "
        "established geography or household arrangements.",
    ]
    for name, details in locations.items():
        location_name = " ".join(str(name).split())
        if not location_name:
            continue
        lines.append(f"\n[{location_name}]")
        rendered = _planner_location_value(details)
        if rendered:
            if len(rendered) > 3200:
                rendered = rendered[:3197].rsplit(" ", 1)[0].rstrip() + "…"
            lines.append(rendered)
        else:
            lines.append("No additional details are recorded.")
    return "\n".join(lines)


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

    # Qwen plans rather than writes prose, so preserve substantially more of
    # the novel's premise and setting context for its decisions.
    premise = _clean_text(story_bible.get("premise"), limit=3000)
    setting = _clean_text(story_bible.get("setting"), limit=4000)
    if premise:
        sections.append(f"Premise: {premise}")
    if setting:
        sections.append(f"Setting: {setting}")

    story_reference = build_story_bible_reference_context(
        story_bible, include_preferences=True, comprehensive=True
    )
    if story_reference:
        sections.append(story_reference)

    creative_direction = build_creative_direction_prompt(
        story_bible.get("creative_direction")
    )
    if creative_direction:
        sections.append(creative_direction)

    location_context = _build_planner_location_context(story_bible)
    if location_context:
        sections.append(location_context)

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

    character_supporting_text = "\n".join(
        part for part in (
            " ".join(cast_names),
            previous_ending,
            author_direction_text,
        ) if part
    )
    # The Planner needs the whole cast for relationship and household awareness,
    # even when the Author's Direction names only one character.
    character_context = build_character_card_context_prompt(
        root,
        story_bible,
        "",
        supporting_text=character_supporting_text,
        include_all=True,
        compact=False,
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

    sections.append(
        "PLANNER CONTEXT PRIORITIES\n"
        "Treat the Story Bible's fixed canon, established relationships, complete character "
        "references, location references, and current continuity as factual story context. "
        "Preserve established identities, ages, relationships, households, residences, "
        "occupations, schedules when recorded, and important possessions, including who "
        "owns, wears, or carries them. Do not turn affectionate or metaphorical family "
        "language (for example, 'like a daughter' or 'daughter of the heart') into literal "
        "parentage or a shared household when the recorded relationships say otherwise. "
        "Do not move a person or possession to another household or owner for convenience. "
        "These references are for understanding the story, not a cast checklist: do not "
        "include every character or visit every location just because they are listed. "
        "Distinguish household residents from visitors: a close neighbor or family friend "
        "does not become a resident because of the strength of the relationship. For a "
        "domestic scene at someone's home, consider the recorded household members first; "
        "do not casually displace or omit residents without a scene-specific reason. "
        "Preserve any time-of-day marker in an occupation or work routine, such as a night "
        "shift; do not turn it into a daytime shift or invent unrecorded work hours. "
        "Preserve the exact meaning of requested times; distinguish a report/arrival time "
        "from a meeting time or shift start/end."
    )

    sections.extend(
        [
            "Use the scene context as a starting point. Gaps are creative space; develop plausible details and interactions without treating every unknown as a prohibition.",
            "Prepare a direction for this one destination scene only. Do not combine distinct time/place "
            "setups that function as separate scenes; leave a later scene setup for a separate Prepare Scene "
            "request unless the author explicitly asks to include it in this same scene. "
            "Identify every concrete event, action, or moment explicitly requested by the author "
            "as an AUTHOR-REQUIRED BEAT. Only events the author directly requested in the current "
            "AUTHOR'S DIRECTION belong in this section; do not promote your own ideas, inferred "
            "connective actions, or your preferred scene setup into author-required beats. A request "
            "for one event does not authorize you to add other events to the required section. If a "
            "current AUTHOR'S DIRECTION is supplied while refining a previous direction, reclassify "
            "from the current author text rather than copying the previous direction's beat labels. "
            "Every author-required beat must happen in this destination scene; do not omit, soften, "
            "replace, or defer any of them. Keep these distinct from your own additions. If no concrete "
            "event is explicitly requested, say 'None specified' under AUTHOR-REQUIRED BEATS. "
            "Then use your own storytelling judgment to choose any number of QWEN-SELECTED ADDITIONAL BEATS: "
            "zero, one, or as many as you believe will genuinely strengthen this scene. There is no quota or cap; "
            "do not pad the scene just to add beats. These are additions and must never replace an author-required beat. "
            "Return one concise 'Scene direction:' followed by clearly separate AUTHOR-REQUIRED BEATS and "
            "QWEN-SELECTED ADDITIONAL BEATS sections. Leave how they unfold and where the scene ends to the Writer. "
            "Do not write manuscript prose.",
        ]
    )
    return "\n\n".join(part for part in sections if part)
