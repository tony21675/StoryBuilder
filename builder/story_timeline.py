"""Compact prompt context for maintaining a story's running timeline."""

from __future__ import annotations

from typing import Any


def build_story_timeline_prompt(value: Any) -> str:
    """Format the last saved in-story time as a continuity anchor."""
    if not isinstance(value, str) or not value.strip():
        return ""

    story_time = " ".join(value.split())
    if len(story_time) > 180:
        story_time = story_time[:177].rstrip() + "..."

    return (
        "STORY TIMELINE\n"
        f"Latest saved in-story time: {story_time}\n"
        "Continue forward from here, using the previous scene to judge elapsed time. "
        "Do not reset the clock or invent an exact hour when the prose does not support one."
    )


def build_current_story_context_prompt(current_state: Any) -> str:
    """Format the current situation and unresolved character objectives for Writer prompts."""
    if not isinstance(current_state, dict):
        return ""

    sections: list[str] = []
    situation = current_state.get("current_situation")
    if isinstance(situation, str) and situation.strip():
        clean_situation = " ".join(situation.split())
        if len(clean_situation) > 1200:
            clean_situation = clean_situation[:1197].rstrip() + "..."
        sections.append(
            "CURRENT STORY SITUATION (continuity context)\n"
            f"Current situation: {clean_situation}"
        )

    objectives = current_state.get("active_objectives")
    if isinstance(objectives, dict):
        objective_lines = []
        for character, objective in objectives.items():
            name = " ".join(str(character).split())
            if not name or not isinstance(objective, str) or not objective.strip():
                continue
            clean_objective = " ".join(objective.split())
            if len(clean_objective) > 1200:
                clean_objective = clean_objective[:1197].rstrip() + "..."
            objective_lines.append(f"- {name}: {clean_objective}")
        if objective_lines:
            sections.append(
                "OUTSTANDING CHARACTER OBJECTIVES (unresolved continuity)\n"
                + "\n".join(objective_lines)
                + "\nTreat each listed objective as unresolved unless the accepted manuscript "
                "explicitly establishes that it was completed. Do not assume it happened "
                "off-page or silently drop it because the current scene does not mention it. "
                "Do not force it into every scene; let it surface or be completed only when "
                "it fits naturally. Do not invent an excuse, outcome, or additional detail."
            )

    return "\n\n".join(sections)
