"""Reusable, light-touch guidance for natural scene craft."""

from __future__ import annotations

import re


_MEDIA_CONTEXT_RE = re.compile(
    r"\b(?:watch(?:ing)?|television|tv|movie|film|screen|phone|radio|broadcast|"
    r"podcast|speaker|music|song|video|stream(?:ing)?|headphones|tablet|computer|display)\b",
    re.IGNORECASE,
)


def build_story_craft_prompt() -> str:
    """Return concise, broad creative guidance shared by planning and writing."""
    return (
        "SCENE CRAFT GUIDANCE\n"
        "Keep scenes natural and lived-in. Let characters and relationships develop at "
        "their own pace. Vary who speaks; not everyone needs a line. Ordinary moments can "
        "matter. Prefer concrete actions and believable detail over overworked description. "
        "Carry forward the previous scene's location and activity unless the author's "
        "direction moves the scene. Follow the author's direction and established continuity."
    )


def build_media_device_prompt(value: str) -> str:
    """Add device/content separation only when the scene actually involves media."""
    if not isinstance(value, str) or not _MEDIA_CONTEXT_RE.search(value):
        return ""
    return (
        "MEDIA AND DEVICE BOUNDARIES\n"
        "Keep content shown or heard through a device separate from the characters' real "
        "surroundings. Characters may react to it, but do not place them inside it unless "
        "the author makes the experience interactive."
    )


__all__ = ["build_media_device_prompt", "build_story_craft_prompt"]
