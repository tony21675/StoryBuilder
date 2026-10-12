from __future__ import annotations

import json
import os
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

from builder.workspace import LLAMA as DEFAULT_LLAMA


PATCH_KEYS = {
    "canon_rules_add", "canon_rules_remove", "characters", "supporting_people",
    "relationships", "locations", "story_planning", "potential_conflicts",
}


def _extract_object(raw: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    cleaned = (raw or "").strip()
    for index, char in enumerate(cleaned):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value.get("proposed_changes", value.get("changes", value))
    raise ValueError("The local model did not return a JSON object.")


def _text_list(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list of text items.")
    result, seen = [], set()
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"Every {label} item must be text.")
        item = item.strip()
        if item and item.casefold() not in seen:
            result.append(item)
            seen.add(item.casefold())
    return result


def _as_rules(value: Any) -> list[str]:
    if isinstance(value, str):
        value = value.splitlines()
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _json_safe(value: Any, label: str) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} contains a value that cannot be saved as JSON.") from exc
    return deepcopy(value)


def _find_key(mapping: dict, name: str) -> str | None:
    wanted = name.strip().casefold()
    for key in mapping:
        if str(key).strip().casefold() == wanted:
            return str(key)
    return None


def normalize_change_patch(patch: dict[str, Any], package, request_text: str) -> dict[str, Any]:
    """Validate an AI proposal without changing the package."""
    if not isinstance(patch, dict):
        raise ValueError("The proposal must be a JSON object.")
    for wrapper in ("proposed_changes", "changes"):
        if isinstance(patch.get(wrapper), dict):
            patch = patch[wrapper]
            break
    unknown = set(patch) - PATCH_KEYS
    if unknown:
        raise ValueError("The model proposed unsupported changes: " + ", ".join(sorted(unknown)))

    request_cf = request_text.casefold()
    result: dict[str, Any] = {}
    rules = _as_rules(package.story_bible.get("canon_rules", []))
    rule_keys = {rule.casefold() for rule in rules}
    additions = [
        rule for rule in _text_list(patch.get("canon_rules_add", []), "canon_rules_add")
        if rule.casefold() not in rule_keys
    ]
    rule_by_key = {rule.casefold(): rule for rule in rules}
    removals = [
        rule_by_key[rule.casefold()]
        for rule in _text_list(patch.get("canon_rules_remove", []), "canon_rules_remove")
        if rule.casefold() in rule_by_key
    ]
    if additions:
        result["canon_rules_add"] = additions
    if removals:
        result["canon_rules_remove"] = removals

    raw_characters = patch.get("characters", {})
    if raw_characters is not None and not isinstance(raw_characters, dict):
        raise ValueError("Character changes must be grouped by character filename.")
    chars = {}
    for raw_filename, values in (raw_characters.items() if isinstance(raw_characters, dict) else []):
        filename = str(raw_filename).strip()
        filename = next((key for key in package.characters if key.casefold() == filename.casefold()), None)
        if filename is None:
            raise ValueError(f"The proposal refers to an unknown character file: {raw_filename}.")
        if not isinstance(values, dict):
            raise ValueError(f"Changes for {filename} must be a field-by-field object.")
        current = package.characters[filename]
        character_name = str(current.get("name", Path(filename).stem)).strip()
        if character_name and character_name.casefold() not in request_cf:
            raise ValueError(f"The proposal tries to change {character_name}, who was not named in your request.")
        values = deepcopy(values)
        proposed_name = values.pop("name", character_name)
        if str(proposed_name).strip().casefold() != character_name.casefold():
            raise ValueError("The Change Assistant cannot rename a character.")
        values.pop("character_cards", None)
        if values:
            chars[filename] = _json_safe(values, f"Character changes for {filename}")
    if chars:
        result["characters"] = chars

    raw_people = patch.get("supporting_people", {})
    if raw_people is not None and not isinstance(raw_people, dict):
        raise ValueError("Supporting-person changes must be grouped by name.")
    existing_people = package.story_bible.get("supporting_people", {})
    if not isinstance(existing_people, dict):
        existing_people = {}
    people = {}
    for raw_name, value in (raw_people.items() if isinstance(raw_people, dict) else []):
        name = str(raw_name).strip()
        if not name:
            raise ValueError("Supporting-person names cannot be empty.")
        existing_key = _find_key(existing_people, name)
        if existing_key is None:
            if name.casefold() not in request_cf:
                raise ValueError(f"The proposal adds {name}, but that person was not named in your request.")
            if package.character_by_name(name) is not None:
                raise ValueError(f"{name} already has a full character card. Update that card instead.")
            target = name
        else:
            target = existing_key
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError(f"The proposed details for {target} cannot be empty.")
        elif not (isinstance(value, dict) and isinstance(existing_people.get(existing_key), dict)):
            raise ValueError(f"The proposed details for {target} must be text.")
        people[target] = _json_safe(value, f"Supporting person {target}")
    if people:
        result["supporting_people"] = people

    for field in ("relationships", "locations"):
        proposed = patch.get(field, {})
        if proposed is not None and not isinstance(proposed, dict):
            raise ValueError(f"{field} changes must be grouped by key.")
        current = package.story_bible.get(field, {})
        if not isinstance(current, dict):
            current = {}
        updates = {}
        for raw_key, value in (proposed.items() if isinstance(proposed, dict) else []):
            key = str(raw_key).strip()
            actual = _find_key(current, key)
            if actual is None and key.casefold() not in request_cf:
                raise ValueError(f"The proposal adds an unrequested {field} entry: {key}.")
            updates[actual or key] = _json_safe(value, f"{field} entry {key}")
        if updates:
            result[field] = updates

    planning = patch.get("story_planning", {})
    if planning is not None and not isinstance(planning, dict):
        raise ValueError("Story-planning changes must be grouped by field.")
    current_planning = package.story_bible.get("story_planning", {})
    if not isinstance(current_planning, dict):
        current_planning = {}
    allowed_planning = {
        "genre", "tone", "core_conflict", "opposition", "setting",
        "important_elements", "themes", "open_questions",
    }
    updates = {}
    for raw_key, value in (planning.items() if isinstance(planning, dict) else []):
        key = str(raw_key).strip()
        if key not in current_planning and key not in allowed_planning and key.casefold() not in request_cf:
            raise ValueError(f"The proposal adds an unrequested planning field: {key}.")
        updates[key] = _json_safe(value, f"Planning field {key}")
    if updates:
        result["story_planning"] = updates

    conflicts = _text_list(patch.get("potential_conflicts", []), "potential_conflicts")
    if conflicts:
        result["potential_conflicts"] = conflicts
    if not (set(result) - {"potential_conflicts"}):
        raise ValueError("The model did not propose any supported changes. Nothing was applied.")
    return result


def _printable(value: Any) -> str:
    if value is None or value == "":
        return "(not set)"
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "; ".join(str(item) for item in value) or "(empty list)"
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_printable(item)}" for key, item in value.items()) or "(empty)"
    return str(value)


def render_change_preview(package, patch: dict[str, Any]) -> str:
    """Create a plain-language before/after review, not a raw JSON display."""
    lines = ["PROPOSED CHANGES", "Nothing has changed yet."]
    if patch.get("potential_conflicts"):
        lines.extend(["", "POSSIBLE CANON CONFLICTS"])
        lines.extend(f"! {item}" for item in patch["potential_conflicts"])
    if patch.get("canon_rules_add"):
        lines.extend(["", "CANON RULES TO ADD", *[f"+ {rule}" for rule in patch["canon_rules_add"]]])
    if patch.get("canon_rules_remove"):
        lines.extend(["", "CANON RULES TO REMOVE", *[f"- {rule}" for rule in patch["canon_rules_remove"]]])
    for filename, fields in patch.get("characters", {}).items():
        current = package.characters[filename]
        lines.extend(["", f"CHARACTER: {current.get('name', Path(filename).stem)}"])
        for field, value in fields.items():
            old = current.get(field)
            new = _deep_merge(old, value) if isinstance(old, dict) and isinstance(value, dict) else value
            lines.extend([f"• {field.replace('_', ' ').title()}", f"  Before: {_printable(old)}", f"  After:  {_printable(new)}"])
    current_people = package.story_bible.get("supporting_people", {})
    if not isinstance(current_people, dict):
        current_people = {}
    for name, value in patch.get("supporting_people", {}).items():
        key = _find_key(current_people, name)
        lines.extend(["", f"SUPPORTING PERSON: {name}" + (" (new entry)" if key is None else "")])
        lines.extend([f"  Before: {_printable(current_people.get(key) if key else None)}", f"  After:  {_printable(value)}"])
    for field, label in (("relationships", "RELATIONSHIP"), ("locations", "LOCATION"), ("story_planning", "STORY PLANNING")):
        current = package.story_bible.get(field, {})
        if not isinstance(current, dict):
            current = {}
        for key, value in patch.get(field, {}).items():
            actual = _find_key(current, key)
            old = current.get(actual) if actual else None
            new = _deep_merge(old, value) if isinstance(old, dict) and isinstance(value, dict) else value
            lines.extend(["", f"{label}: {key}", f"  Before: {_printable(old)}", f"  After:  {_printable(new)}"])
    lines.extend(["", "APPROVAL REQUIRED", "Choose Approve and Save Changes only after reviewing this list."])
    return "\n".join(lines)


def apply_change_request_patch(package, patch: dict[str, Any], *, request_text: str) -> str:
    """Apply a validated proposal to the in-memory package after approval."""
    patch = normalize_change_patch(patch, package, request_text)
    bible = package.story_bible
    rules = _as_rules(bible.get("canon_rules", []))
    removed = {rule.casefold() for rule in patch.get("canon_rules_remove", [])}
    rules = [rule for rule in rules if rule.casefold() not in removed]
    known = {rule.casefold() for rule in rules}
    for rule in patch.get("canon_rules_add", []):
        if rule.casefold() not in known:
            rules.append(rule)
            known.add(rule.casefold())
    if "canon_rules_add" in patch or "canon_rules_remove" in patch:
        bible["canon_rules"] = rules
    for filename, fields in patch.get("characters", {}).items():
        package.characters[filename] = _deep_merge(package.characters[filename], fields)
    people = bible.setdefault("supporting_people", {})
    if not isinstance(people, dict):
        people = {}
        bible["supporting_people"] = people
    for name, value in patch.get("supporting_people", {}).items():
        if isinstance(people.get(name), dict) and isinstance(value, dict):
            people[name] = _deep_merge(people[name], value)
        else:
            people[name] = deepcopy(value)
    for field in ("relationships", "locations", "story_planning"):
        updates = patch.get(field, {})
        if not updates:
            continue
        destination = bible.setdefault(field, {})
        if not isinstance(destination, dict):
            destination = {}
            bible[field] = destination
        for key, value in updates.items():
            if isinstance(destination.get(key), dict) and isinstance(value, dict):
                destination[key] = _deep_merge(destination[key], value)
            else:
                destination[key] = deepcopy(value)
    counts = []
    rule_count = len(patch.get("canon_rules_add", [])) + len(patch.get("canon_rules_remove", []))
    if rule_count:
        counts.append(f"{rule_count} canon rule change(s)")
    for field, label in (
        ("characters", "character profile(s)"),
        ("supporting_people", "supporting-person entry/entries"),
        ("relationships", "relationship(s)"),
        ("locations", "location(s)"),
        ("story_planning", "planning field(s)"),
    ):
        if patch.get(field):
            counts.append(f"{len(patch[field])} {label}")
    return ", ".join(counts) or "Story data updated"


def structure_change_request(model_path: str | Path, *, request: str, existing_data: dict[str, Any]) -> dict[str, Any]:
    """Ask the local GGUF model for a proposal; do not mutate the novel."""
    request = (request or "").strip()
    if not request:
        raise ValueError("Describe the change you want to make first.")
    model = Path(os.path.expanduser(str(model_path))).resolve()
    if model.suffix.casefold() != ".gguf" or not model.is_file():
        raise ValueError("The selected model is not a valid GGUF file.")
    if not DEFAULT_LLAMA.is_file():
        raise FileNotFoundError(f"llama-cli not found: {DEFAULT_LLAMA}")

    system_prompt = (
        "You are StoryBuilder's change-proposal assistant. Convert the author's natural-language request "
        "into a minimal JSON patch for the supplied story data. The author is the only source of canon. "
        "Never invent people, facts, motives, or future events. Do not delete or rewrite existing facts unless "
        "the author explicitly asks. Never modify manuscript prose, scene state, or accepted scenes. Return only "
        "a JSON object. The app validates the proposal and the author must approve before anything changes."
    )
    patch_shape = {
        "canon_rules_add": ["new hard rule or permanent fact, only if stated by the author"],
        "canon_rules_remove": ["exact existing rule the author explicitly asked to remove"],
        "characters": {"EXACT_EXISTING_FILENAME.json": {"field_to_update": "new value"}},
        "supporting_people": {"existing name or a new person named in the request": "full proposed description"},
        "relationships": {"existing relationship key or a key named in the request": "new relationship fact"},
        "locations": {"existing location key or a key named in the request": "new location fact"},
        "story_planning": {"genre|tone|core_conflict|opposition|setting|important_elements|themes|open_questions": "new value"},
        "potential_conflicts": ["clear conflicts with existing canon not resolved by the request"],
    }
    prompt = (
        f"AUTHOR REQUEST:\n{request}\n\nEXISTING STORY DATA (reference only):\n"
        + json.dumps(existing_data, indent=2, ensure_ascii=False)
        + "\n\nReturn a minimal patch in this exact shape, omitting empty sections:\n"
        + json.dumps(patch_shape, indent=2, ensure_ascii=False)
        + "\n\nRules:\n"
        "- Use exact existing filenames for character edits and never rename characters.\n"
        "- Update only the people and fields the author asked to change. Preserve unrelated details.\n"
        "- Add a supporting-person entry only if the person's name literally appears in AUTHOR REQUEST.\n"
        "- Use canon_rules_add for explicit permanent rules and story-wide restrictions.\n"
        "- potential_conflicts are warnings only; never resolve a conflict by guessing.\n"
        "- Do not return current_state, accepted scenes, arbitrary JSON, or unsupported keys.\n"
        "Return valid JSON only."
    )
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(DEFAULT_LLAMA.parent) + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    device = os.environ.get("STORY_LLM_DEVICE", "").strip()
    args = [
        str(DEFAULT_LLAMA), "-m", str(model),
        "-ngl", "all" if device else "0", "--device", device or "none",
        "-c", "8192", "--reasoning", "off", "--temp", "0.10",
        "--top-k", "20", "--top-p", "0.80", "--repeat-last-n", "256",
        "--repeat-penalty", "1.08", "--n-predict", "1600",
        "--system-prompt", system_prompt, "--prompt", prompt, "--color", "off",
        "--no-display-prompt", "--simple-io", "--single-turn",
    ]
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, text=True, encoding="utf-8", errors="replace")
    try:
        output, _ = proc.communicate(timeout=600)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        output, _ = proc.communicate()
        raise TimeoutError("The Change Assistant timed out.") from exc
    if proc.returncode not in (0, None):
        raise RuntimeError("The local model failed while preparing the proposal.\n" + (output or "")[-3000:])
    return _extract_object(output)
