from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from builder.workspace import LLAMA as DEFAULT_LLAMA


CHARACTER_QUESTIONS = [
    ("Role", "What is this character's role or place in the story?", "ai"),
    ("Age", "How old is this character? Give a whole number, or skip if unknown.", "age"),
    ("Appearance", "Describe this character's physical appearance and normal presentation. Include anything visually important.", "ai"),
    ("Personality", "What is this character like? Describe personality, temperament, and how they usually behave.", "ai"),
    ("Strengths and weaknesses", "What are this character's strengths, weaknesses, insecurities, or recurring struggles?", "ai"),
    ("Background and family", "What important background, family history, upbringing, or life experience should define this character?", "ai"),
    ("Relationships", "Describe the important relationships this character has with other established characters, including how each relationship feels and behaves.", "ai"),
    ("Private feelings", "Are there private feelings, attractions, fears, resentments, hopes, or internal conflicts that other characters may not know about?", "ai"),
    ("Knowledge boundaries", "What does this character know, what do they not know, and are there any facts that must remain private from them?", "ai"),
    ("Habits and cues", "What habits, mannerisms, speech patterns, humor, routines, or small behavioral cues make this character feel distinctive?", "ai"),
    ("Goals and interests", "What does this character want, enjoy, care about, fear losing, or hope to do?", "ai"),
    ("Skills and important details", "What useful skills, limitations, possessions, access, technology, training, or other established details matter to this character?", "ai"),
]

RELATIONSHIP_QUESTIONS = [
    ("Connection", "How would you describe the connection between these two characters?", "ai"),
    ("History", "How long have they known each other, and what shared history matters to the relationship?", "ai"),
    ("Everyday dynamic", "How do they normally behave around each other in ordinary situations?", "ai"),
    ("Trust and boundaries", "What do they trust each other with, and what boundaries or limits exist?", "ai"),
    ("Private side", "Are there private feelings, uncertainties, secrets, or misunderstandings that one character has but the other does not know?", "ai"),
    ("Stress response", "How does this relationship change when one or both characters are frightened, angry, hurt, or under pressure?", "ai"),
    ("Knowledge", "What does each character know about the other, and what important things do they not know?", "ai"),
]

LOCATION_QUESTIONS = [
    ("Purpose", "What is this location and what role does it play in the story?", "ai"),
    ("People", "Who lives here, works here, visits here, or normally uses it?", "ai"),
    ("Layout", "What important rooms, areas, landmarks, objects, or physical features should be established?", "ai"),
    ("Surroundings", "What is nearby, and what does arriving at or leaving this location feel like?", "ai"),
    ("Atmosphere", "What ordinary sights, sounds, smells, routines, or environmental details make this place distinctive?", "ai"),
    ("Access", "Who can enter or access this place, and are there keys, locks, permissions, security measures, or other access rules?", "ai"),
    ("Important details", "Are there any important objects, secrets, technology, hazards, history, or future-relevant details associated with this location?", "ai"),
]


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _extract_object(raw: str) -> dict[str, Any]:
    cleaned = (raw or "").strip()
    decoder = json.JSONDecoder()
    for index, char in enumerate(cleaned):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("The local model did not return a JSON object.")


def structure_answer(
    model_path: str | Path,
    *,
    target_kind: str,
    target_name: str,
    question: str,
    answer: str,
    existing_data: dict[str, Any],
) -> dict[str, Any]:
    model = Path(os.path.expanduser(str(model_path))).resolve()
    if model.suffix.casefold() != ".gguf" or not model.is_file():
        raise ValueError("The selected model is not a valid GGUF file.")
    if not DEFAULT_LLAMA.is_file():
        raise FileNotFoundError(f"llama-cli not found: {DEFAULT_LLAMA}")

    system_prompt = (
        "You are the StoryBuilder canon assistant. "
        "Convert the author's natural-language answer into a minimal JSON patch for the existing story data. "
        "The author is the sole source of canon. Never invent facts, motives, relationships, identities, or future events. "
        "Do not delete existing data unless the author explicitly says it is wrong or should be removed. "
        "Use the existing schema when practical, but you may add a useful field when the existing schema has no suitable place. "
        "Preserve private or limited knowledge exactly as the author describes it. "
        "Return ONLY a JSON object containing fields supported by the author's answer."
    )

    prompt = (
        f"TARGET TYPE: {target_kind}\n"
        f"TARGET: {target_name}\n"
        f"QUESTION: {question}\n"
        f"AUTHOR ANSWER: {answer}\n\n"
        "EXISTING DATA:\n"
        + json.dumps(existing_data, indent=2, ensure_ascii=False)
        + "\n\n"
        "PATCH SHAPE:\n"
        "For a character interview, return {\"character\": {...}}. "
        "For a relationship interview, return {\"story_bible\": {\"relationships\": {...}}} "
        "and/or {\"characters\": {\"filename.json\": {...}}}. "
        "For a location interview, return {\"story_bible\": {\"locations\": {\"ID\": \"...\"}}}. "
        "Return only changed or newly established fields."
    )

    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(DEFAULT_LLAMA.parent) + (
        ":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else ""
    )

    device = os.environ.get("STORY_LLM_DEVICE", "").strip()
    args = [
        str(DEFAULT_LLAMA),
        "-m", str(model),
        "-ngl", "all" if device else "0",
        "--device", device or "none",
        "-c", "8192",
        "--reasoning", "off",
        "--temp", "0.10",
        "--top-k", "20",
        "--top-p", "0.80",
        "--repeat-last-n", "256",
        "--repeat-penalty", "1.08",
        "--n-predict", "1000",
        "--system-prompt", system_prompt,
        "--prompt", prompt,
        "--color", "off",
        "--no-display-prompt",
        "--simple-io",
        "--single-turn",
    ]

    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        output, _ = proc.communicate(timeout=600)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        output, _ = proc.communicate()
        raise TimeoutError("The StoryBuilder interview model timed out.") from exc

    if proc.returncode not in (0, None):
        raise RuntimeError(
            "The StoryBuilder interview model failed.\n" + (output or "")[-3000:]
        )

    return _extract_object(output)


def apply_interview_patch(package, patch: dict[str, Any], *, target_kind: str, target_name: str) -> None:
    if not isinstance(patch, dict):
        raise ValueError("Interview patch must be a JSON object.")

    if target_kind == "character":
        character = package.characters.get(target_name)
        if character is None:
            raise ValueError(f"Character file not found: {target_name}.")
        values = patch.get("character", patch)
        if not isinstance(values, dict):
            raise ValueError("Character patch must contain an object.")
        package.characters[target_name] = _deep_merge(character, values)
        return

    if target_kind == "relationship":
        relationships = package.story_bible.setdefault("relationships", {})
        story_values = patch.get("story_bible", {})
        if isinstance(story_values, dict):
            rel_values = story_values.get("relationships", {})
            if isinstance(rel_values, dict):
                relationships.update(rel_values)

        character_values = patch.get("characters", {})
        if isinstance(character_values, dict):
            for filename, updates in character_values.items():
                if filename in package.characters and isinstance(updates, dict):
                    package.characters[filename] = _deep_merge(
                        package.characters[filename], updates
                    )

        if target_name not in relationships:
            fallback = patch.get("relationship")
            if isinstance(fallback, str) and fallback.strip():
                relationships[target_name] = fallback.strip()
        return

    if target_kind == "location":
        locations = package.story_bible.setdefault("locations", {})
        story_values = patch.get("story_bible", {})
        if isinstance(story_values, dict):
            location_values = story_values.get("locations", {})
            if isinstance(location_values, dict):
                locations.update(location_values)

        if target_name not in locations:
            fallback = patch.get("location")
            if isinstance(fallback, str) and fallback.strip():
                locations[target_name] = fallback.strip()
        return

    raise ValueError(f"Unknown interview target type: {target_kind}.")
