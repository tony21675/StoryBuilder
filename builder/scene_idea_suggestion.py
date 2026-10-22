from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from builder.scene_contract import _run_with_existing_engine


SCENE_IDEA_SUGGESTION_SYSTEM_PROMPT = """You are a thoughtful scene-planning partner for an ongoing novel.

Return exactly one valid JSON object with this shape:
{"scene_idea":"A short editable 2-5 sentence scene idea.","beginning":"How the scene opens from the current state.","middle":"The main development or turn in this scene.","end":"The natural stopping point for this scene.","planned_beats":["A meaningful event the scene should include."],"boundaries":["A continuity or scope limit the scene must respect."]}

Give the author a compact scene idea PLUS a practical first-draft plan. The beginning, middle, and end must describe the same scene as the 2-5 sentence idea, not introduce separate events. Make them specific enough to guide writing but brief enough to leave room for original dialogue and staging. Give 2-4 meaningful, event-level planned beats, not a checklist of incidental actions. Identify any real boundaries supported by the current state, accepted story context, or author plan, especially explicit safety limits, facts not yet established, and decisions the prior scene has deferred. Do not invent arbitrary prohibitions. Return an empty boundaries array only when no concrete boundary is supported. Do not repeat the same instruction in multiple beats.

Use the saved situation as a starting summary, not as sole proof that every historical claim is true. Build naturally from established events, current objectives, unresolved questions, character knowledge, physical continuity, the story premise, accepted prose, canon, and any author-written story plan provided. Do not repeat completed events or claim an uncertain hypothesis is fact. If a consequential past-event claim appears only in a generated state summary and is unsupported by accepted prose or canon, do not carry it forward as fact unless the existing Scene Idea explicitly establishes it. The existing Scene Idea and explicit author corrections take precedence over a stale or mistaken summary. Keep open questions open unless the story context establishes their answer. Respect the established genre, tone, author boundaries, and story direction. Do not introduce an unsupported major premise shift or consequential historical fact.

When the opening cast is only a focus list, do not imply everyone else has vanished from the wider story. Let characters contribute according to their established knowledge and abilities. Avoid assigning every character a formal task unless the story context calls for that. Leave room for natural dialogue, choices, and discovery rather than scripting every beat.

The suggestion is guidance only. Do not change the saved state, declare new canon, or make the author's decisions for them. Return JSON only, with no Markdown or commentary.
"""


def build_scene_idea_suggestion_prompt(context: dict[str, Any]) -> str:
    """Serialize the current state and supporting story context for one suggestion."""
    if not isinstance(context, dict):
        raise ValueError("Scene suggestion context must be an object.")
    return (
        "READ-ONLY STORY CONTEXT. Use it to suggest one next scene; do not modify it.\n\n"
        + json.dumps(context, ensure_ascii=False, indent=2)
        + "\n\nSuggest the next scene now. Return JSON with the scene_idea field only."
    )


def normalize_scene_idea_suggestion(value: Any) -> str:
    """Validate and format an editable idea with its matching scene-plan fields."""
    if isinstance(value, dict):
        idea_value = value.get("scene_idea")
        if not isinstance(idea_value, str):
            raise ValueError("The scene suggestion did not contain a text scene_idea value.")
        idea = idea_value.strip()
        if not idea:
            raise ValueError("The model returned an empty scene suggestion.")

        # Keep compatibility with older models/tests that return only scene_idea.
        structured_keys = ("beginning", "middle", "end", "planned_beats", "boundaries")
        if any(key in value for key in structured_keys):
            sections = [idea]
            for key, label in (
                ("beginning", "Beginning"),
                ("middle", "Middle"),
                ("end", "End / Hard Stop"),
            ):
                section_value = value.get(key, "")
                if isinstance(section_value, str) and section_value.strip():
                    sections.append(f"{label}:\\n{section_value.strip()}")

            for key, label in (("planned_beats", "Planned Beats"), ("boundaries", "Boundaries")):
                raw_items = value.get(key, [])
                if raw_items is None:
                    raw_items = []
                if not isinstance(raw_items, list):
                    raise ValueError(f"The scene suggestion field '{key}' must be a list.")
                items = [str(item).strip() for item in raw_items if str(item).strip()]
                if items:
                    sections.append(label + ":\\n" + "\\n".join(f"- {item}" for item in items))
            idea = "\\n\\n".join(sections)
    elif isinstance(value, str):
        idea = value.strip()
    else:
        raise ValueError("The scene suggestion did not contain a text scene_idea value.")

    if not idea:
        raise ValueError("The model returned an empty scene suggestion.")
    if len(idea) > 4000:
        raise ValueError("The scene suggestion was too long. Generate a shorter suggestion.")
    return idea


def generate_scene_idea_suggestion(
    model_path: str | Path,
    context: dict[str, Any],
    engine: Any,
) -> str:
    """Generate a single scene suggestion through StoryBuilder's existing model engine."""
    model = Path(os.path.expanduser(str(model_path))).resolve()
    if not model.is_file() or model.suffix.casefold() != ".gguf":
        raise ValueError("The selected model is not a valid GGUF file.")
    if engine is None:
        raise ValueError("The StoryBuilder writer engine is not available.")

    prompt = build_scene_idea_suggestion_prompt(context)
    raw = _run_with_existing_engine(
        engine,
        model,
        SCENE_IDEA_SUGGESTION_SYSTEM_PROMPT,
        prompt,
        context_size=int(os.environ.get("STORY_SCENE_IDEA_CONTEXT", "8192")),
        max_tokens=int(os.environ.get("STORY_SCENE_IDEA_MAX_TOKENS", "700")),
        timeout_seconds=max(60, int(os.environ.get("STORY_SCENE_IDEA_TIMEOUT", "240"))),
        task_name="Next scene suggestion",
    )
    return normalize_scene_idea_suggestion(raw)
