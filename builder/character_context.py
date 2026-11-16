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


def _relationships_text(
    value: Any,
    *,
    related_names: list[str] | None = None,
    max_items: int = 8,
) -> str:
    if isinstance(value, dict):
        entries = []
        for name, description in value.items():
            key = _clean(name, 80)
            rendered = _clean(description, 140)
            if not rendered:
                continue
            if related_names is not None:
                relation_text = f"{key} {rendered}"
                if not any(_name_is_mentioned(person, relation_text) for person in related_names):
                    continue
            entries.append(f"{key}: {rendered}")
            if len(entries) >= max(1, int(max_items)):
                break
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
            "Only the listed characters may be physically present, speak, act, interact, "
            "arrive, depart, communicate, or otherwise participate in this scene."
        )
    else:
        cast_line = "Allowed characters: none."
        participation = (
            "No character may appear, speak, act, interact, communicate, or otherwise "
            "participate in this scene."
        )

    boundary = (
        "SCENE CAST BOUNDARY (AUTHOR-SELECTED AND BINDING)\n"
        + cast_line
        + "\n"
        + participation
        + " An unselected character cannot enter, take an action, deliver dialogue, call, "
        "text, email, or appear as an active participant in a cutaway or flashback. "
        "Names and references to unselected people are allowed when needed for the author's "
        "direction or story continuity, including memories, grief, photographs, letters, "
        "and discussion of someone who is absent or deceased. A still photograph or other "
        "static keepsake depicting an absent or deceased person is allowed when the author "
        "requests it; this does not make that person a scene participant. Mentioning someone "
        "does not authorize them to appear, speak, act, or communicate in the scene."
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
    scene_focused: bool = False,
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
    if roster_names and selected_names is None and not scene_focused:
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
        if compact and scene_focused:
            # Scene cards are deliberately small: identity and the traits that
            # help the Writer distinguish this person's behavior and dialogue.
            values = (
                (("age",), "Age", 40),
                (("gender", "pronouns"), "Gender / pronouns", 50),
                (("role",), "Role", 100),
                (("occupation", "department"), "Occupation", 110),
            )
            for fields, label, limit in values:
                raw = next((card.get(field) for field in fields if card.get(field) not in (None, "", [], {})), None)
                rendered = _reference_value_text(raw)
                if rendered:
                    lines.append(f"{label}: {_clean(rendered, limit)}")

            appearance = next(
                (
                    card.get(field)
                    for field in ("appearance", "physical_description", "visual_description", "physical_traits")
                    if card.get(field) not in (None, "", [], {})
                ),
                None,
            )
            if appearance is not None:
                rendered = _reference_value_text(appearance)
                if rendered:
                    lines.append(f"Appearance: {_clean(rendered, 190)}")

            # Carry only important-item facts whose item name is mentioned in
            # the current scene. This preserves physical continuity without
            # dumping every item recorded on a character card.
            important_items = card.get("important_items")
            if isinstance(important_items, dict):
                query_terms = set(re.findall(r"[a-z0-9]+", query.casefold()))
                matched_items = []
                for item_name, item_value in important_items.items():
                    key_terms = [
                        token
                        for token in re.findall(
                            r"[a-z0-9]+", str(item_name).replace("_", " ").casefold()
                        )
                        if len(token) >= 3
                    ]
                    if not key_terms or not all(token in query_terms for token in key_terms):
                        continue
                    rendered = _reference_value_text(item_value)
                    if rendered:
                        label = str(item_name).replace("_", " ").strip().title()
                        matched_items.append(f"{label}: {_clean(rendered, 220)}")
                    if len(matched_items) >= 2:
                        break
                if matched_items:
                    lines.append("Relevant important items: " + "; ".join(matched_items))

            personality = next(
                (
                    card.get(field)
                    for field in ("personality", "personality_traits", "traits", "temperament")
                    if card.get(field) not in (None, "", [], {})
                ),
                None,
            )
            if personality is not None:
                rendered = (
                    _list_text(personality, limit=3)
                    if isinstance(personality, list)
                    else _reference_value_text(personality)
                )
                if rendered:
                    lines.append(f"Personality: {_clean(rendered, 190)}")

            voice = next(
                (
                    card.get(field)
                    for field in ("voice", "speech_style", "speaking_style", "voice_and_speech")
                    if card.get(field) not in (None, "", [], {})
                ),
                None,
            )
            if voice is not None:
                rendered = _reference_value_text(voice)
                if rendered:
                    lines.append(f"Voice: {_clean(rendered, 170)}")

            description = card.get("description")
            if description not in (None, "", [], {}):
                rendered = _reference_value_text(description)
                if rendered:
                    lines.append(f"Defining detail: {_clean(rendered, 200)}")

            scene_people = (
                [_clean(item, 100) for item in selected_names if isinstance(item, str)]
                if selected_names is not None
                else [
                    item for item in roster_names
                    if _name_is_mentioned(item, query)
                ]
            )
            related_names = [
                item for item in scene_people if item.casefold() != name.casefold()
            ]
            relationships = _relationships_text(
                card.get("relationships"), related_names=related_names, max_items=2
            )
            if relationships:
                lines.append(f"Scene relationships: {_clean(relationships, 220)}")

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

_SCENE_CONTEXT_STOP_WORDS = {
    "about", "after", "again", "also", "and", "are", "around", "been", "before",
    "being", "between", "but", "did", "does", "during", "each", "for", "from",
    "had", "has", "have", "her", "him", "his", "into", "its", "just", "like",
    "more", "most", "not", "now", "only", "our", "out", "over", "said", "same",
    "she", "should", "some", "such", "than", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "through", "told", "under",
    "very", "was", "were", "what", "when", "where", "which", "while", "who",
    "will", "with", "would", "you", "your", "scene", "story", "current", "state",
    "character", "chapter", "writer", "direction", "home", "house", "evening",
    "dinner", "table", "group", "people", "everyone", "something", "anything",
}


def _scene_terms(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").casefold())
        if len(token) >= 3 and token not in _SCENE_CONTEXT_STOP_WORDS
    }


def _scene_character_names(
    story_bible: dict[str, Any],
    scene_text: str,
    selected_names: list[str] | None,
) -> list[str]:
    if selected_names is not None:
        source = selected_names
    else:
        source = []
        entries = story_bible.get("character_cards", [])
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict):
                    card = entry
                elif isinstance(entry, str) and entry.strip():
                    card = {"name": Path(entry).stem}
                else:
                    continue
                name = _clean(card.get("name"), 100)
                if name and _name_is_mentioned(name, scene_text):
                    source.append(name)
    result = []
    seen = set()
    for name in source:
        clean = _clean(name, 100)
        key = clean.casefold()
        if clean and key not in seen:
            result.append(clean)
            seen.add(key)
    return result


def build_scene_relevant_story_bible_reference_context(
    story_bible: dict[str, Any],
    scene_text: str,
    *,
    selected_names: list[str] | None = None,
    max_canon_rules: int = 8,
    max_relationships: int = 8,
) -> str:
    """Select only canon and relationship facts relevant to the current scene.

    The complete Story Bible remains authoritative and unchanged. This function
    creates a temporary, scene-specific view for the Writer.
    """
    if not isinstance(story_bible, dict):
        return ""

    scene_text = str(scene_text or "")
    people = _scene_character_names(story_bible, scene_text, selected_names)
    scene_terms = _scene_terms(scene_text)
    sections: list[str] = []

    raw_rules = story_bible.get("canon_rules")
    if isinstance(raw_rules, str):
        raw_rules = [raw_rules]
    ranked_rules = []
    if isinstance(raw_rules, list):
        for index, raw in enumerate(raw_rules):
            if not isinstance(raw, str) or not raw.strip():
                continue
            rule = " ".join(raw.split())
            name_hits = sum(1 for person in people if _name_is_mentioned(person, rule))
            overlap = len(_scene_terms(rule) & scene_terms)
            score = name_hits * 6 + min(overlap, 4)
            # Name-specific canon is strong evidence. Otherwise require at least
            # two meaningful shared terms to avoid pulling in generic rules.
            if score > 0 and (name_hits or overlap >= 2):
                ranked_rules.append((score, index, rule))
    ranked_rules.sort(key=lambda item: (-item[0], item[1]))
    selected_rules = [item[2] for item in ranked_rules[:max(0, int(max_canon_rules))]]
    if selected_rules:
        sections.append(
            "SCENE-RELEVANT FIXED CANON (facts to preserve, not extra scene beats)\n"
            + "\n".join(f"- {rule[:520]}" for rule in selected_rules)
        )

    raw_relationships = story_bible.get("relationships")
    ranked_relationships = []
    if isinstance(raw_relationships, dict):
        for index, (key, value) in enumerate(raw_relationships.items()):
            label = _clean(key, 100)
            description = _clean(value, 520)
            if not label or not description:
                continue
            relation_text = f"{label}: {description}"
            name_hits = sum(
                1 for person in people if _name_is_mentioned(person, relation_text)
            )
            if name_hits:
                ranked_relationships.append((name_hits, index, relation_text))
    ranked_relationships.sort(key=lambda item: (-item[0], item[1]))
    selected_relationships = [
        item[2] for item in ranked_relationships[:max(0, int(max_relationships))]
    ]
    if selected_relationships:
        sections.append(
            "SCENE-RELEVANT RELATIONSHIPS (factual reference)\n"
            + "\n".join(f"- {item[:620]}" for item in selected_relationships)
        )

    return "\n\n".join(sections)
