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


def _reference_value_text(value: Any, *, depth: int = 0) -> str:
    """Render populated character-card values, including nested/custom fields."""
    if depth > 5 or value is None:
        return ""
    if isinstance(value, dict):
        entries = []
        for key, nested in value.items():
            rendered = _reference_value_text(nested, depth=depth + 1)
            if rendered:
                label = str(key).replace("_", " ").strip().title()
                entries.append(f"{label}: {rendered}")
        return "; ".join(entries)
    if isinstance(value, list):
        return "; ".join(
            rendered
            for item in value
            if (rendered := _reference_value_text(item, depth=depth + 1))
        )
    rendered = _clean(value, 2200)
    return rendered


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


def load_character_card_names(
    novel_path: str | Path, story_bible: dict[str, Any]
) -> list[str]:
    """Return the names of valid character cards registered in this novel."""
    entries = story_bible.get("character_cards", [])
    if not isinstance(entries, list):
        return []

    names: list[str] = []
    seen: set[str] = set()
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
        key = name.casefold()
        if name and key not in seen:
            names.append(name)
            seen.add(key)
    return names


def build_scene_cast_boundary_prompt(
    prompt: str, scene_cast: list[str] | None
) -> str:
    """Append the author's binding list of characters allowed in one scene."""
    if scene_cast is None:
        return str(prompt or "")

    names: list[str] = []
    seen: set[str] = set()
    for value in scene_cast:
        name = _clean(value, 100)
        key = name.casefold()
        if name and key not in seen:
            names.append(name)
            seen.add(key)

    if names:
        cast_line = "Allowed characters: " + ", ".join(names) + "."
        participation = (
            "Only the characters listed above may be physically present, appear on-page, "
            "speak, act, interact, enter or leave, or participate in this scene."
        )
    else:
        cast_line = "Allowed characters: none."
        participation = (
            "No character may appear, speak, act, interact, or participate in this scene."
        )

    boundary = (
        "SCENE CAST BOUNDARY (AUTHOR-SELECTED AND BINDING)\n"
        + cast_line
        + "\n"
        + participation
        + " Every unlisted character is excluded, even if mentioned in the previous scene, "
        "continuity notes, Story Bible, relationships, or Author's Direction. Do not bring "
        "an unlisted character into the scene through a cutaway, flashback, phone call, text, "
        "email, or off-page interaction. An unlisted person may be mentioned only as brief "
        "background/status context when necessary; do not depict them acting or participating."
    )
    prefix = str(prompt or "").rstrip()
    return f"{prefix}\n\n{boundary}" if prefix else boundary


def build_character_card_context_prompt(
    novel_path: str | Path,
    story_bible: dict[str, Any],
    prompt: str,
    *,
    supporting_text: str = "",
    include_all: bool = False,
    compact: bool = False,
    comprehensive: bool = False,
    selected_names: list[str] | None = None,
) -> str:
    """Append relevant character references, with a lean mode for manuscript writing."""
    entries = story_bible.get("character_cards", [])
    if not isinstance(entries, list) or not entries:
        return str(prompt or "")

    query = "\n".join(
        part for part in (str(prompt or ""), str(supporting_text or "")) if part
    )
    selected: list[dict[str, Any]] = []
    roster_names: list[str] = []
    seen_names: set[str] = set()
    selected_name_keys = {
        _clean(name, 100).casefold()
        for name in (selected_names or [])
        if isinstance(name, str) and _clean(name, 100)
    }

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

        if selected_names is not None:
            if normalized_name in selected_name_keys:
                selected.append(card)
        elif include_all or _name_is_mentioned(name, query):
            selected.append(card)

    if selected_names is not None and not selected:
        return str(prompt or "")
    if not roster_names and not selected:
        return str(prompt or "")

    lines: list[str] = []
    if roster_names and selected_names is None:
        roster_line = (
            "Character cards registered for this novel (reference only): "
            + ", ".join(roster_names)
        )
        if compact:
            lines.append(roster_line)
        else:
            lines.extend(
                [
                    "REGISTERED CHARACTER CARDS",
                    roster_line,
                ]
            )

    if selected:
        if comprehensive:
            lines.extend([
                "COMPLETE CHARACTER CARD REFERENCES",
                "All populated fields from these cards are included as story reference. Preserve established facts, but do not treat the roster as a cast checklist or force every character into every scene. Use recorded expertise and experience accurately; interests and hobbies are not automatically professional qualifications.",
            ])
        elif compact:
            lines.extend([
                "BRIEF CHARACTER REFERENCES",
                "Short factual reminders for the named characters. Use them when helpful; they are not a checklist. Use each character's recorded gender for pronouns; never infer gender from a name. If gender is not recorded, avoid assuming.",
            ])
        else:
            lines.extend(
                [
                    "CHARACTER REFERENCES",
                    "These are factual reference notes, not a checklist. Use each character's recorded gender for pronouns; never infer gender from a name. If gender is not recorded, avoid assuming. Use documented role, occupation, skills, and background to ground what characters know and can do. Do not treat hobbies or general interests as professional qualifications. Characters may ask questions or suggest possibilities outside their specialties, but present those as questions or hypotheses rather than established expertise.",
                ]
            )
    for card in selected:
        name = _clean(card.get("name"), 100)
        lines.append(f"\n[{name}]")
        if comprehensive:
            for field, value in card.items():
                if field == "name":
                    continue
                rendered = _reference_value_text(value)
                if rendered:
                    label = str(field).replace("_", " ").strip().title()
                    lines.append(f"{label}: {rendered}")
            continue
        if compact:
            for field, label in (
                ("age", "Age"),
                ("gender", "Gender"),
                ("relationship_status", "Relationship status"),
                ("role", "Role"),
                ("occupation", "Occupation / department"),
                ("department", "Department"),
            ):
                value = _clean(card.get(field), 160)
                if field == "relationship_status" and not value:
                    value = "Not established"
                if value:
                    lines.append(f"{label}: {value}")

            skills = _combined_list_text(
                card, ("skills", "expertise", "specialties", "technical_skills"),
                limit=4,
            )
            if len(skills) > 280:
                skills = skills[:277].rstrip() + "…"
            if skills:
                lines.append(f"Skills: {skills}")

            personality = _list_text(card.get("personality"), limit=2)
            if len(personality) > 140:
                personality = personality[:137].rstrip() + "…"
            if personality:
                lines.append(f"Personality: {personality}")

            voice = _clean(card.get("voice"), 140)
            if voice:
                lines.append(f"Voice: {voice}")
            continue

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



def build_story_bible_reference_context(
    story_bible: dict[str, Any], *, include_preferences: bool = False,
    comprehensive: bool = False,
) -> str:
    """Pass the novel's small canon and relationship reference to the writing model."""
    if not isinstance(story_bible, dict):
        return ""

    sections: list[str] = []

    rules = story_bible.get("canon_rules")
    if isinstance(rules, str) and rules.strip():
        rules = [rules]
    if isinstance(rules, list):
        rule_limit = None if comprehensive else 12
        rule_text_limit = 1800 if comprehensive else 700
        rule_values = [
            _clean(rule, rule_text_limit)
            for rule in rules
            if isinstance(rule, str) and rule.strip()
        ]
        entries = rule_values if rule_limit is None else rule_values[:rule_limit]
        if entries:
            sections.append(
                "FIXED CANON (preserve these facts; they are not a scene checklist)\n"
                + "\n".join(f"- {entry}" for entry in entries)
            )

    relationships = story_bible.get("relationships")
    if isinstance(relationships, dict):
        entries = []
        relationship_items = (
            relationships.items() if comprehensive
            else list(relationships.items())[:16]
        )
        for name, description in relationship_items:
            key = _clean(name, 100)
            value = _clean(description, 1600 if comprehensive else 650)
            if key and value:
                entries.append(f"{key}: {value}")
        if entries:
            sections.append(
                "ESTABLISHED RELATIONSHIPS (factual reference, not an instruction "
                "to put everyone in every scene)\n"
                + "\n".join(entries)
            )

    if include_preferences:
        preferences = story_bible.get("writing_preferences")
        if isinstance(preferences, str) and preferences.strip():
            sections.append(
                "AUTHOR'S OVERALL STORY APPROACH (flexible creative guidance)\n"
                + preferences.strip()
            )

    return "\n\n".join(sections)
