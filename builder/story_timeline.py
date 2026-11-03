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
        "STORY TIMELINE (running continuity)\n"
        f"Latest saved in-story time: {story_time}\n"
        "Treat this as the last recorded point on the story clock, not as an instruction "
        "to reset every new scene to that time. Use the preceding scene and its established "
        "activities to work out how much time has passed and what part of the day comes next. "
        "Keep time moving forward; account for realistic duration, meals, shifts, recreation, "
        "and sleep without imposing a fixed schedule. When the prose does not support an exact "
        "clock time, use a broad time-of-day description rather than inventing a precise hour. "
        "Do not repeat activities the previous scene clearly completed."
    )
