"""Reusable, light-touch guidance for natural scene craft."""

from __future__ import annotations


def build_story_craft_prompt() -> str:
    """Return broad creative guidance shared by scene planning and writing."""
    return """SCENE CRAFT GUIDANCE (flexible, not a checklist)
Make scenes feel lived-in as well as purposeful. When it suits the story, let activities, choices, and conversation reveal character and allow relationships to develop at their own pace; ordinary moments can matter without a crisis or twist. Vary scene focus and group size naturally; not everyone needs to speak in every group scene. Give characters distinct voices and let dialogue breathe, mixing humor with straightforward talk, awkwardness, disagreement, pauses, and comfortable silence. Avoid making every line a joke, scripted turn-taking, unnecessarily polished banter, technical exposition, or speeches that explain a lesson or theme. Prefer concrete actions and believable details over over-elaborate description or repeated explanations of feelings. Preserve established facts and continuity. Treat this as broad creative guidance, not a formula; follow the author's specific direction and the needs of this story."""


__all__ = ["build_story_craft_prompt"]
