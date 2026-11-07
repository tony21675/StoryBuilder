from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from builder.story_bible_reader import load_story_bible_character_card


def _clean(value: Any, limit: int = 180) -> str:
    if value is None or isinstance(value, (dict, list)):
        return ""
    text = " ".join(str(value).split())
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def _list_text(value: Any, limit: int = 8) -> str:
    if isinstance(value, str):
        return _clean(value, 300)
    if isinstance(value, list):
        items = [_clean(item, 90) for item in value]
        return ", ".join(item for item in items[:limit] if item)
    return ""


def _combined_list_text(
    card: dict[str, Any], fields: tuple[str, ...], limit: int = 8
) -> str:
    """Combine optional list-like card fields without requiring a fixed schema."""
    values = [_list_text(card.get(field), limit=limit) for field in fields]
    return "; ".join(value for value in values if value)


def _relationships_text(value: Any) -> str:
    if isinstance(value, dict):
        entries = []
        for name, description in list(value.items())[:8]:
            rendered = _clean(description, 140)
            if rendered:
                entries.append(f"{_clean(name, 80)}: {rendered}")
        return "; ".join(entries)
    return _clean(value, 300)


def _name_is_mentioned(name: str, text: str) -> bool:
    parts = [part for part in name.strip().split() if part]
    candidates = {name.strip()}
    if len(parts) > 1:
        candidates.add(parts[0])
        candidates.add(parts[-1])
    return any(
        re.search(
            rf"(?<![\w]){re.escape(candidate)}(?![\w])",
            text,
            flags=re.IGNORECASE,
        )
        for candidate in candidates
        if candidate
    )


def build_character_card_context_prompt(
    novel_path: str | Path,
    story_bible: dict[str, Any],
    prompt: str,
    *,
    supporting_text: str = "",
    include_all: bool = False,
) -> str:
    """Append concise, relevant references for characters in the writing context."""
    entries = story_bible.get("character_cards", [])
    if not isinstance(entries, list) or not entries:
        return str(prompt or "")

    query = "\n".join(
        part for part in (str(prompt or ""), str(supporting_text or "")) if part
    )
    selected: list[dict[str, Any]] = []
    roster_names: list[str] = []
    seen_names: set[str] = set()

    for entry in entries:
        if isinstance(entry, dict):
            card = entry
        elif isinstance(entry, str) and entry.strip():
            try:
                card = load_story_bible_character_card(novel_path, entry.strip())
            except (OSError, UnicodeError, ValueError):
                continue
        else:
            continue

        name = _clean(card.get("name"), 100)
        if not name:
            continue

        normalized_name = name.casefold()
        if normalized_name not in seen_names:
            roster_names.append(name)
            seen_names.add(normalized_name)

        if include_all or _name_is_mentioned(name, query):
            selected.append(card)

    if not roster_names and not selected:
        return str(prompt or "")

    lines: list[str] = []
    if roster_names:
        lines.extend(
            [
                "ESTABLISHED CHARACTER ROSTER",
                "Registered characters in this novel: " + ", ".join(roster_names),
                "Treat this as the complete roster of established members of any recurring crew, team, household, or similar group. Do not invent extra members or add an unlisted person to a group arrival or group scene. Do not describe someone as arriving if the story context already places them in the scene. New characters may still be introduced when the author's direction or established story events genuinely call for them.",
            ]
        )

    if selected:
        lines.extend(
            [
                "CHARACTER REFERENCES",
                "Use each character's documented role, occupation, skills, and background to ground what they know and can do. Do not treat hobbies or general interests as professional qualifications. Characters may ask questions or suggest possibilities outside their specialties, but present those as questions or hypotheses rather than established expertise.",
                "These are established character facts, not a request for romance. Do not invent romantic or sexual attraction that conflicts with a character's stated orientation; friendship, teasing, and affection can remain platonic.",
            ]
        )
    for card in selected:
        name = _clean(card.get("name"), 100)
        lines.append(f"\n[{name}]")
        for field, label in (
            ("role", "Role"),
            ("occupation", "Occupation / department"),
            ("department", "Department"),
            ("age", "Age"),
            ("gender", "Gender"),
            ("sexual_orientation", "Sexual orientation"),
            ("relationship_status", "Relationship status"),
        ):
            value = _clean(card.get(field), 200)
            if value:
                lines.append(f"{label}: {value}")

        background = _combined_list_text(
            card, ("background", "experience"), limit=4
        )
        if background:
            lines.append(f"Background / experience: {background}")

        skills = _combined_list_text(
            card, ("skills", "expertise", "specialties", "technical_skills"),
            limit=10,
        )
        if skills:
            lines.append(f"Skills / expertise: {skills}")

        training = _combined_list_text(
            card, ("training", "qualifications", "certifications"), limit=8
        )
        if training:
            lines.append(f"Training / qualifications: {training}")

        personality = _list_text(card.get("personality"))
        if personality:
            lines.append(f"Personality: {personality}")

        interests = _combined_list_text(card, ("interests", "hobbies"), limit=10)
        if interests:
            lines.append(f"Interests / hobbies: {interests}")

        description = _clean(card.get("description"), 520)
        if description:
            lines.append(f"Additional established notes: {description}")

        relationships = _relationships_text(card.get("relationships"))
        if relationships:
            lines.append(f"Established relationships: {relationships}")

    context = "\n".join(lines)
    prefix = str(prompt or "").rstrip()
    return f"{prefix}\n\n{context}" if prefix else context
