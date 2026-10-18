from __future__ import annotations

import json
import os
import re
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

from builder.workspace import LLAMA as DEFAULT_LLAMA

MAX_BRIEF_LENGTH = 12000
MAX_CHARACTERS = 12
MAX_SUPPORTING_PEOPLE = 16
MAX_LOCATIONS = 16
PLAN_TEXT = ("genre", "tone", "core_conflict", "opposition", "setting", "important_elements")
PLAN_LIST = ("themes", "open_questions")
CHAR_TEXT = ("role", "description", "background", "occupation", "knowledge_rule")


def _extract_object(raw: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for i, char in enumerate((raw or "").strip()):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(raw.strip()[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            for key in ("starter_package", "proposal", "novel"):
                if isinstance(value.get(key), dict):
                    return value[key]
            return value
    raise ValueError("The local model did not return a usable JSON object.")


def _text(value: Any, label: str, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text.")
    value = value.strip()
    if required and not value:
        raise ValueError(f"The proposal is missing {label}.")
    return value


def _text_list(value: Any, label: str) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        source = re.split(r"[\n,;]+", value)
    elif isinstance(value, list):
        source = value
    else:
        raise ValueError(f"{label} must be a list of text items.")
    result, seen = [], set()
    for item in source:
        if not isinstance(item, str):
            raise ValueError(f"Every {label} item must be text.")
        item = item.strip()
        if item and item.casefold() not in seen:
            result.append(item)
            seen.add(item.casefold())
    return result


def _string_map(value: Any, label: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object.")
    return {
        _text(key, f"{label} key", True): _text(item, f"{label} value", True)
        for key, item in value.items()
    }


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 _-]+", "", name).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return f"{cleaned or 'Character'}.json"


def normalize_new_novel_proposal(raw: dict[str, Any], *, author_brief: str) -> dict[str, Any]:
    """Validate and normalize a reviewable starter package without changing canon."""
    if not isinstance(raw, dict):
        raise ValueError("The starter-package proposal must be a JSON object.")
    for wrapper in ("starter_package", "proposal", "novel"):
        if isinstance(raw.get(wrapper), dict):
            raw = raw[wrapper]
            break
    allowed = {
        "title", "premise", "story_planning", "canon_rules", "characters",
        "supporting_people", "relationships", "locations", "opening",
        "suggestions", "open_questions", "potential_conflicts",
    }
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError("Unsupported starter-package fields: " + ", ".join(sorted(map(str, unknown))))
    brief = (author_brief or "").strip()
    if not brief:
        raise ValueError("Enter a plain-English description of the novel first.")
    if len(brief) > MAX_BRIEF_LENGTH:
        raise ValueError(f"Keep the description under {MAX_BRIEF_LENGTH:,} characters.")

    title = _text(raw.get("title"), "a title", True)
    premise = _text(raw.get("premise"), "a premise", True)
    if len(title) > 120:
        raise ValueError("The proposed title is too long. Shorten it and try again.")

    plan_raw = raw.get("story_planning", {})
    if not isinstance(plan_raw, dict):
        raise ValueError("Story planning must be an object.")
    extra = set(plan_raw) - (set(PLAN_TEXT) | set(PLAN_LIST))
    if extra:
        raise ValueError("Unsupported story-planning fields: " + ", ".join(sorted(map(str, extra))))
    plan = {}
    for key in PLAN_TEXT:
        value = plan_raw.get(key, "")
        if isinstance(value, list):
            value = "; ".join(_text_list(value, key))
        plan[key] = _text(value, f"story planning field {key}")
    for key in PLAN_LIST:
        plan[key] = _text_list(plan_raw.get(key, []), key)
    questions = plan["open_questions"] + _text_list(raw.get("open_questions", []), "open_questions")
    plan["open_questions"] = _text_list(questions, "open_questions")

    rules = _text_list(raw.get("canon_rules", []), "canon_rules")
    chars_raw = raw.get("characters")
    if not isinstance(chars_raw, list) or not chars_raw:
        raise ValueError("The proposal must include at least one character card.")
    if len(chars_raw) > MAX_CHARACTERS:
        raise ValueError(f"Limit the proposal to {MAX_CHARACTERS} core characters.")

    chars, names, filenames = [], set(), set()
    for index, entry in enumerate(chars_raw, 1):
        if not isinstance(entry, dict):
            raise ValueError(f"Character card {index} must be an object.")
        name = _text(entry.get("name"), f"name for character card {index}", True)
        if name.casefold() in names:
            raise ValueError(f"The proposal repeats the character name {name}.")
        filename = _safe_filename(name).casefold()
        if filename in filenames:
            raise ValueError(f"Two character names would create the same file name: {filename}.")
        names.add(name.casefold())
        filenames.add(filename)

        age = entry.get("age")
        if age in ("", "unknown", "Unknown", "not decided", "Not decided"):
            age = None
        elif isinstance(age, str) and age.strip().isdigit():
            age = int(age.strip())
        elif age is not None and (isinstance(age, bool) or not isinstance(age, int)):
            raise ValueError(f"{name}'s age must be a whole number or left unknown.")
        if age is not None and not 0 <= age <= 120:
            raise ValueError(f"{name}'s age must be between 0 and 120, or left unknown.")

        card = {"name": name, "status": "established", "age": age}
        for key in CHAR_TEXT:
            card[key] = _text(entry.get(key, ""), f"{name}'s {key}")
        card["personality"] = _text_list(entry.get("personality", []), f"{name}'s personality")
        appearance = entry.get("appearance", {})
        if isinstance(appearance, str):
            appearance = {"description": appearance.strip()} if appearance.strip() else {}
        card["appearance"] = _string_map(appearance, f"{name}'s appearance")
        card["relationships"] = _string_map(entry.get("relationships", {}), f"{name}'s relationships")
        card["important_items"] = _string_map(entry.get("important_items", {}), f"{name}'s important items")
        standard = {"name", "status", "age", *CHAR_TEXT, "personality", "appearance", "relationships", "important_items"}
        for key in set(entry) - standard:
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"{name}'s card contains an invalid field name.")
            try:
                json.dumps(entry[key], ensure_ascii=False)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name}'s {key} field cannot be saved as JSON.") from exc
            card[key] = deepcopy(entry[key])
        card["status"] = _text(entry.get("status", "established"), f"{name}'s status") or "established"
        chars.append(card)

    supporting_raw = raw.get("supporting_people", {})
    if supporting_raw is None:
        supporting_raw = {}
    if not isinstance(supporting_raw, dict):
        raise ValueError("Supporting people must be an object.")
    supporting = {}
    for name, details in supporting_raw.items():
        clean_name = _text(name, "supporting-person name", True)
        if clean_name.casefold() in names:
            raise ValueError(f"{clean_name} appears as both a core character and a supporting person.")
        try:
            json.dumps(details, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"The details for supporting person {clean_name} cannot be saved as JSON.") from exc
        supporting[clean_name] = deepcopy(details)
    if len(supporting) > MAX_SUPPORTING_PEOPLE:
        raise ValueError(f"Limit the proposal to {MAX_SUPPORTING_PEOPLE} supporting people.")

    relationships = _string_map(raw.get("relationships", {}), "Relationships")
    locations = _string_map(raw.get("locations", {}), "Locations")
    if len(locations) > MAX_LOCATIONS:
        raise ValueError(f"Limit the proposal to {MAX_LOCATIONS} locations.")

    opening_raw = raw.get("opening", {}) or {}
    if not isinstance(opening_raw, dict):
        raise ValueError("The opening scene proposal must be an object.")
    open_keys = {"chapter", "scene", "time_of_day", "location", "scene_cast", "current_situation", "continuity_notes"}
    extra_opening = set(opening_raw) - open_keys
    if extra_opening:
        raise ValueError("Unsupported opening-state fields: " + ", ".join(sorted(map(str, extra_opening))))
    opening = {}
    for key in ("chapter", "scene"):
        value = opening_raw.get(key, 1)
        if isinstance(value, str) and value.strip().isdigit():
            value = int(value.strip())
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 10000:
            raise ValueError(f"Opening {key} must be a positive whole number.")
        opening[key] = value
    opening["time_of_day"] = _text(opening_raw.get("time_of_day", ""), "opening time of day")
    opening["location"] = _text(opening_raw.get("location", ""), "opening location")
    opening["scene_cast"] = _text_list(opening_raw.get("scene_cast", []), "opening scene cast")
    opening["current_situation"] = _text(opening_raw.get("current_situation", ""), "opening current situation")
    opening["continuity_notes"] = _text_list(opening_raw.get("continuity_notes", []), "opening continuity notes")
    known_people = names | {name.casefold() for name in supporting}
    opening["scene_cast"] = [name for name in opening["scene_cast"] if name.casefold() in known_people]

    return {
        "title": title,
        "premise": premise,
        "story_planning": plan,
        "canon_rules": rules,
        "characters": chars,
        "supporting_people": supporting,
        "relationships": relationships,
        "locations": locations,
        "opening": opening,
        "suggestions": _text_list(raw.get("suggestions", []), "suggestions"),
        "potential_conflicts": _text_list(raw.get("potential_conflicts", []), "potential_conflicts"),
    }


def build_new_novel_proposal(model_path: str | Path, *, author_brief: str) -> dict[str, Any]:
    """Ask the selected local GGUF model for a complete draft starter package."""
    brief = (author_brief or "").strip()
    if not brief:
        raise ValueError("Describe the novel in plain English first.")
    if len(brief) > MAX_BRIEF_LENGTH:
        raise ValueError(f"Keep the description under {MAX_BRIEF_LENGTH:,} characters.")
    model = Path(os.path.expanduser(str(model_path))).resolve()
    if model.suffix.casefold() != ".gguf" or not model.is_file():
        raise ValueError("The selected model is not a valid GGUF file.")
    if not DEFAULT_LLAMA.is_file():
        raise FileNotFoundError(f"llama-cli not found: {DEFAULT_LLAMA}")

    system_prompt = (
        "You are StoryBuilder's new-novel development partner. Turn the author's plain-English description "
        "into a useful DRAFT starter package. The author owns canon. Preserve all stated facts, names, relationships, "
        "secrets, and boundaries. Do not contradict them. This is a proposal, never automatically saved. Do not invent "
        "major twists, deaths, crimes, romance, villains, or irreversible events the author did not describe. You may "
        "suggest modest appearance, personality, location, or supporting details, but list notable inventions in "
        "suggestions. Leave unknown ages and uncertain facts blank. Never turn guesses into canon rules. Keep the "
        "package compact and practical, normally no more than 6 core characters."
    )
    shape = {
        "title": "short title",
        "premise": "one or two sentence premise based on the author's idea",
        "story_planning": {
            "genre": "genre or blend", "tone": "tone or blank",
            "core_conflict": "central conflict", "opposition": "known opposing force or blank",
            "setting": "setting or blank", "important_elements": "key objects or organizations",
            "themes": ["themes"], "open_questions": ["undecided details"],
        },
        "canon_rules": ["only permanent rules explicitly stated by the author"],
        "characters": [{
            "name": "character name", "role": "story role", "age": None,
            "description": "short description", "personality": ["traits"],
            "background": "known background, blank if unknown", "occupation": "known job or blank",
            "appearance": {"build": "", "hair": "", "eyes": "", "style": ""},
            "relationships": {"other character": "relationship"},
            "important_items": {}, "knowledge_rule": "explicit knowledge boundaries or blank",
        }],
        "supporting_people": {"name": "brief role"},
        "relationships": {"pair or group": "relationship in plain English"},
        "locations": {"location name": "useful established or proposed details"},
        "opening": {
            "chapter": 1, "scene": 1, "time_of_day": "", "location": "",
            "scene_cast": ["names"], "current_situation": "opening situation before scene events",
            "continuity_notes": ["opening constraints stated in the brief"],
        },
        "suggestions": ["notable creative additions for author review"],
        "potential_conflicts": ["only actual contradictions inside the brief"],
    }
    prompt = (
        "AUTHOR'S STORY DESCRIPTION:\n" + brief
        + "\n\nCreate a compact starter package in this JSON shape; use no other top-level fields:\n"
        + json.dumps(shape, indent=2, ensure_ascii=False)
        + "\n\nRules:\n"
        "- Keep explicit author facts separate from creative suggestions.\n"
        "- Do not add an unmentioned secret, major reveal, romance, death, crime, or villain.\n"
        "- Preserve all author-named character names and stated traits.\n"
        "- If no character names are given, propose up to three central names and mention this in suggestions.\n"
        "- Do not invent precise ages, jobs, eye colors, family ties, skills, or history without support.\n"
        "- Give cards useful concise details, using empty fields or null for unknowns.\n"
        "- current_situation is the opening situation before the scene's events, not its ending state.\n"
        "- Return valid JSON only. No Markdown, fences, commentary, or unsupported fields."
    )
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(DEFAULT_LLAMA.parent) + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    device = os.environ.get("STORY_LLM_DEVICE", "").strip()
    args = [
        str(DEFAULT_LLAMA), "-m", str(model),
        "-ngl", "all" if device else "0", "--device", device or "none",
        "-c", "8192", "--reasoning", "off", "--temp", "0.20",
        "--top-k", "20", "--top-p", "0.85", "--repeat-last-n", "256",
        "--repeat-penalty", "1.08", "--n-predict", "3200",
        "--system-prompt", system_prompt, "--prompt", prompt, "--color", "off",
        "--no-display-prompt", "--simple-io", "--single-turn",
    ]
    proc = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
        text=True, encoding="utf-8", errors="replace",
    )
    try:
        output, _ = proc.communicate(timeout=600)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        output, _ = proc.communicate()
        raise TimeoutError("The New Novel Assistant timed out.") from exc
    if proc.returncode not in (0, None):
        raise RuntimeError("The local model failed while preparing the starter package.\n" + (output or "")[-3000:])
    return _extract_object(output)


def is_blank_new_package(package) -> bool:
    """True only for an untouched StoryPackage.new() workspace."""
    if package is None or getattr(package, "path", None) is not None:
        return False
    bible = getattr(package, "story_bible", {})
    if not isinstance(bible, dict):
        return False
    if str(bible.get("title", "Untitled")).strip() not in {"", "Untitled"}:
        return False
    if str(bible.get("premise", "") or "").strip() or getattr(package, "characters", {}):
        return False
    if bible.get("character_cards", []):
        return False
    if any(bible.get(key) for key in ("canon_rules", "relationships", "locations", "supporting_people")):
        return False
    planning = bible.get("story_planning", {})
    if not isinstance(planning, dict) or any(v not in (None, "", [], {}) for v in planning.values()):
        return False
    state = getattr(package, "current_state", {})
    if not isinstance(state, dict):
        return False
    return not any((
        state.get("chapter", 1) != 1, state.get("scene", 1) != 1,
        state.get("status", "story_start") != "story_start",
        state.get("time_of_day", ""), state.get("location", ""),
        state.get("scene_cast", []), state.get("events", []),
        state.get("continuity_notes", []), state.get("current_situation", ""),
    ))


def apply_new_novel_proposal(package, proposal: dict[str, Any]) -> str:
    """Apply an approved proposal only to an untouched new package."""
    if not is_blank_new_package(package):
        raise ValueError("This assistant only builds into an untouched New Novel workspace. No existing novel data was changed.")
    normalized = normalize_new_novel_proposal(
        proposal, author_brief=str(proposal.get("premise", "") if isinstance(proposal, dict) else "")
    )
    bible = package.story_bible
    bible["title"] = normalized["title"]
    bible["premise"] = normalized["premise"]
    bible["canon_rules"] = list(normalized["canon_rules"])
    bible["relationships"] = deepcopy(normalized["relationships"])
    bible["locations"] = deepcopy(normalized["locations"])
    bible["supporting_people"] = deepcopy(normalized["supporting_people"])
    bible["story_planning"] = deepcopy(normalized["story_planning"])
    for card in normalized["characters"]:
        filename = package.add_character(card["name"])
        package.characters[filename].update(deepcopy(card))
    opening = normalized["opening"]
    package.current_state.update({
        "chapter": opening["chapter"], "scene": opening["scene"],
        "scene_completed": False, "chapter_completed": False, "status": "story_start",
        "time_of_day": opening["time_of_day"], "location": opening["location"],
        "scene_cast": list(opening["scene_cast"]), "events": [],
        "continuity_notes": list(opening["continuity_notes"]),
        "current_situation": opening["current_situation"], "physical_state": {},
    })
    return (
        f"starter package with {len(normalized['characters'])} character card(s), "
        f"{len(normalized['relationships'])} relationship(s), {len(normalized['locations'])} location(s), "
        f"{len(normalized['canon_rules'])} canon rule(s), and "
        f"{len(normalized['story_planning'].get('open_questions', []))} open question(s)"
    )


def _display(value: Any) -> str:
    if value is None or value == "" or value == [] or value == {}:
        return "(not established)"
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_display(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "; ".join(str(item) for item in value) or "(not established)"
    return str(value)


def render_new_novel_preview(proposal: dict[str, Any]) -> str:
    """Display a plain-English review instead of raw JSON."""
    lines = [
        "NEW NOVEL STARTER PACKAGE", "AI-PROPOSED DRAFT. Nothing has been applied yet.",
        "", f"TITLE: {proposal['title']}", "", "PREMISE", proposal["premise"], "", "STORY FOUNDATION",
    ]
    plan = proposal["story_planning"]
    for key, label in (
        ("genre", "Genre"), ("tone", "Tone"), ("core_conflict", "Core conflict"),
        ("opposition", "Opposition"), ("setting", "Setting"),
        ("important_elements", "Important elements"), ("themes", "Themes"),
    ):
        value = _display(plan.get(key))
        if value != "(not established)":
            lines.append(f"{label}: {value}")
    for i, card in enumerate(proposal["characters"], 1):
        lines.extend([
            "", f"CHARACTER {i}: {card['name']}",
            f"Role: {_display(card.get('role'))}", f"Age: {_display(card.get('age'))}",
            f"Description: {_display(card.get('description'))}", f"Appearance: {_display(card.get('appearance'))}",
            f"Personality: {_display(card.get('personality'))}", f"Background: {_display(card.get('background'))}",
            f"Occupation: {_display(card.get('occupation'))}", f"Relationships: {_display(card.get('relationships'))}",
            f"Important items: {_display(card.get('important_items'))}",
            f"Knowledge boundaries: {_display(card.get('knowledge_rule'))}",
        ])
    for label, key in (("SUPPORTING PEOPLE", "supporting_people"), ("RELATIONSHIPS", "relationships"), ("LOCATIONS", "locations"), ("CANON RULES", "canon_rules")):
        values = proposal.get(key, {})
        if values:
            lines.extend(["", label])
            if isinstance(values, dict):
                lines.extend(f"- {name}: {_display(value)}" for name, value in values.items())
            else:
                lines.extend(f"- {value}" for value in values)
    opening = proposal["opening"]
    lines.extend([
        "", "OPENING STATE", f"Chapter {opening['chapter']}, Scene {opening['scene']}",
        f"Time: {_display(opening.get('time_of_day'))}", f"Location: {_display(opening.get('location'))}",
        f"Cast: {_display(opening.get('scene_cast'))}",
        f"Starting situation: {_display(opening.get('current_situation'))}",
    ])
    if plan.get("open_questions"):
        lines.extend(["", "DETAILS LEFT OPEN FOR YOU TO DECIDE"])
        lines.extend(f"- {question}" for question in plan["open_questions"])
    if proposal.get("suggestions"):
        lines.extend(["", "CREATIVE SUGGESTIONS TO REVIEW"])
        lines.extend(f"- {suggestion}" for suggestion in proposal["suggestions"])
    if proposal.get("potential_conflicts"):
        lines.extend(["", "POSSIBLE CONTRADICTIONS TO REVIEW"])
        lines.extend(f"! {issue}" for issue in proposal["potential_conflicts"])
    lines.extend([
        "", "REVIEW NOTE",
        "This is a proposal, not established canon. Review the details, reject it, or revise your description and prepare another proposal.",
        "Approve only when the package matches the story you want to write.",
    ])
    return "\n".join(lines)
