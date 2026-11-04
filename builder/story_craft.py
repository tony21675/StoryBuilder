"""Reusable, light-touch guidance for natural scene craft."""

from __future__ import annotations


def build_story_craft_prompt() -> str:
    """Return broad creative guidance shared by scene planning and writing."""
    return """SCENE CRAFT GUIDANCE (flexible, not a checklist)
Make scenes feel lived-in as well as purposeful. When it suits the story, let activities, choices, and conversation reveal character and allow relationships to develop at their own pace; ordinary moments can matter without a crisis or twist. Vary scene focus and group size naturally; not everyone needs to speak in every group scene. Give characters distinct voices and let dialogue breathe, mixing humor with straightforward talk, awkwardness, disagreement, pauses, and comfortable silence. Avoid making every line a joke, scripted turn-taking, unnecessarily polished banter, technical exposition, or speeches that explain a lesson or theme. Prefer concrete actions and believable details over over-elaborate description or repeated explanations of feelings. Preserve established facts and continuity. When a scene follows an existing scene, continue directly from its final moment. Carry forward the established location, characters present, and ongoing activity; only change time or place when the author's direction calls for that transition.

MEDIA AND DEVICE BOUNDARIES (when relevant)
When characters watch, listen to, read, or view content through a television, radio, phone, computer, screen, speaker, or other device, keep a clear boundary between that content and the story's present scene. Events, settings, people, sounds, and actions presented through the device remain media the characters are experiencing; they do not become the characters' physical surroundings or current activity. Keep characters in their established real-world location, and present the media through what they can see or hear from the device. Characters may react, comment, imagine, compare, or be emotionally affected, but do not place them inside the media or make them responsible for its events unless the author's direction explicitly establishes participation, such as an interactive game or immersive simulation.

Treat this as broad creative guidance, not a formula; follow the author's specific direction and the needs of this story."""


__all__ = ["build_story_craft_prompt"]
