"""Focused ending-state updates for newly saved manuscript scenes.

This module deliberately handles only the ending state supported by accepted prose.
It does not run a scene-to-scene comparison or a separate proposed-state checker.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from builder.state_manager import (
    ENDING_STATE_SYSTEM_PROMPT,
    StateManager,
    extract_json_object,
    normalize_location_patch,
    normalize_physical_state_patch,
    validate_state_proposal,
)


ENDING_STATE_FIELDS = {
    "current_situation",
    "location",
    "physical_state",
    "time_of_day",
}
ENDING_CONTEXT_FIELDS = (
    "chapter",
    "scene",
    "current_situation",
    "time",
    "time_of_day",
    "location",
    "physical_state",
)
ENDING_CONTEXT_CHARS = 6000


def load_current_state(path: str | Path) -> dict[str, Any]:
    """Read a novel's current state, rejecting malformed JSON instead of replacing it."""
    target = Path(path).expanduser()
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(value, dict):
        raise ValueError("current_state.json must contain a JSON object.")
    return value


def advance_saved_scene_markers(
    current_state: dict[str, Any],
    chapter: int,
    scene: int,
) -> dict[str, Any]:
    """Mark the newly saved scene as the last completed scene without guessing story facts."""
    if not isinstance(current_state, dict):
        raise ValueError("The current story state must be a JSON object.")
    updated = dict(current_state)
    updated["chapter"] = int(chapter)
    updated["scene"] = int(scene)
    if str(updated.get("status", "")).strip().casefold() in {"", "story_start"}:
        updated["status"] = "in_progress"
    updated["scene_completed"] = True
    updated["chapter_completed"] = False
    return updated


def _ending_excerpt(accepted_scene: str, max_chars: int = ENDING_CONTEXT_CHARS) -> str:
    text = str(accepted_scene or "").strip()
    if not text:
        raise ValueError("The saved scene contains no prose to analyze.")
    paragraphs = [
        part.strip()
        for part in re.split(r"\n\s*\n", text)
        if part.strip()
    ]
    if not paragraphs:
        return text[-max_chars:]

    selected: list[str] = []
    used = 0
    for paragraph in reversed(paragraphs):
        separator = 2 if selected else 0
        remaining = max_chars - used - separator
        if remaining <= 0:
            break
        if len(paragraph) > remaining:
            selected.insert(0, paragraph[-remaining:])
            break
        selected.insert(0, paragraph)
        used += len(paragraph) + separator
        if len(selected) >= 4:
            break
    return "\n\n".join(selected)


def build_saved_scene_state_prompt(
    current_state: dict[str, Any],
    chapter: int,
    scene: int,
    accepted_scene: str,
) -> str:
    """Build one ending-state request from the latest accepted scene."""
    if not isinstance(current_state, dict):
        raise ValueError("The current story state must be a JSON object.")
    before_state = {
        key: current_state[key]
        for key in ENDING_CONTEXT_FIELDS
        if key in current_state
    }
    excerpt = _ending_excerpt(accepted_scene)
    return (
        ENDING_STATE_SYSTEM_PROMPT
        + f"\n\nSAVED SCENE: Chapter {int(chapter):02d}, Scene {int(scene):02d}."
        + "\n\nBEFORE-STATE CONTEXT (the state before this saved scene):\n"
        + json.dumps(before_state, ensure_ascii=False, indent=2)
        + "\n\nFINAL PARAGRAPHS OF THE SAVED SCENE (evidence for its ending state):\n"
        + excerpt
        + "\n\nReturn one JSON object containing only the ending-state fields supported "
        "by the accepted prose. Do not run a scene comparison or review."
    )


def parse_saved_scene_state_patch(
    current_state: dict[str, Any],
    model_response: str,
    scene_characters: list[str] | None = None,
) -> dict[str, Any]:
    """Parse and validate the focused ending-state proposal without a comparison checker."""
    candidate = extract_json_object(
        str(model_response or ""),
        required_keys={"current_situation"},
    )
    candidate = {
        key: value
        for key, value in candidate.items()
        if key in ENDING_STATE_FIELDS
    }
    candidate = normalize_location_patch(current_state, candidate)
    candidate = normalize_physical_state_patch(
        current_state,
        candidate,
        scene_characters=scene_characters,
    )
    try:
        validate_state_proposal(current_state, candidate)
    except (TypeError, ValueError) as exc:
        # Match the existing bounded recovery for malformed location shapes:
        # keep usable text entries and retain the rest of the valid end-state patch.
        if (
            "Invalid state update at 'location." in str(exc)
            or "'location' must be an object" in str(exc)
        ):
            raw_location = candidate.get("location")
            if isinstance(raw_location, dict):
                clean_location = {
                    key: value
                    for key, value in raw_location.items()
                    if isinstance(value, str) or value is None
                }
                if clean_location:
                    candidate["location"] = clean_location
                else:
                    candidate.pop("location", None)
            else:
                candidate.pop("location", None)
            validate_state_proposal(current_state, candidate)
        else:
            raise
    return candidate


def merge_saved_scene_state(
    current_state: dict[str, Any],
    patch: dict[str, Any],
    chapter: int,
    scene: int,
) -> dict[str, Any]:
    """Merge an accepted ending-state patch and retain app-owned scene markers."""
    validate_state_proposal(current_state, patch)
    updated = StateManager.merge_patch(current_state, patch)
    return advance_saved_scene_markers(updated, chapter, scene)


def write_current_state(path: str | Path, state: dict[str, Any]) -> Path:
    """Write current state atomically so a failed write cannot truncate the last valid file."""
    if not isinstance(state, dict):
        raise ValueError("The current story state must be a JSON object.")
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    try:
        temporary.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return target
