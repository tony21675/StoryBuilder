from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from builder.workspace import LLAMA as DEFAULT_LLAMA

KNOWLEDGE_AUDIT_SYSTEM_PROMPT = """You are a character-knowledge auditor for an ongoing fictional novel.

Return ONLY valid JSON. The normal shape is:
{"CharacterName": ["complete fact known after the section", "another complete fact known after the section"]}
When a prior fact is explicitly superseded by the completed prose, you may additionally include:
"_superseded_facts": {"CharacterName": ["exact prior fact that is now false or obsolete"]}
Older callers may only consume the character-name arrays, so keep those arrays complete and valid.

Rules:
- Audit only the supplied scene cast.
- Return each current-scene character's COMPLETE cumulative knowledge after the completed section.
- Preserve every valid fact already known before the section, then add every fact newly learned during the completed prose.
- A character learns information they hear from another character's dialogue, directly observe, read, or personally experience.
- When one character tells another a consequential fact, the listener knows that fact after the conversation.
- Do not give information to characters who did not hear, observe, read, or experience it.
- Preserve specific consequential facts. Do not replace several distinct facts with a vague summary.
- If a before-state item says a character does not know a fact, and the completed prose shows that character now learns it, remove the obsolete negative statement and record the actual knowledge instead.
- Never omit a valid prior fact merely because the completed section does not repeat it. The application also preserves prior facts as a safeguard against incomplete model output.
- Only when the completed prose directly corrects, contradicts, or resolves a prior fact, list that exact prior fact under the optional "_superseded_facts" object for its character. Do not list a fact as superseded merely because it was omitted from your knowledge summary.
- If you do not find any prior fact that is explicitly superseded, omit the "_superseded_facts" object and use the normal character-name arrays.
- Do not keep contradictory positive and negative knowledge statements when the completed prose resolves the contradiction.
- Read the entire completed section, not only its ending.
- Never infer future events, motives, hidden information, or unstated conclusions.
- Return knowledge facts and beliefs only, not a log of actions performed in the scene.
- Do not record routine scene actions such as calling or inviting friends, suggesting a bath, helping someone sit up, guiding someone to a bathroom, closing a door, brewing tea, offering a mug, or lowering someone into a bath. These are scene events, not cumulative knowledge.
- Do not record a character's act of telling, asking, offering, or suggesting something as that character's knowledge. Record the consequential fact learned by the listener instead. For example, write "Tony knows from Maya that Tiffany is missing", not "Maya told Tony that Tiffany is missing".
- Never list a character's own actions as things that character knows. For example, "Tony helped Maya into the bath" is an event, not a knowledge fact.
- Preserve consequential facts from important events, including the abduction, violence, injuries, identifying details, and clues. Do not delete those facts just because they describe actions.
- A valid entry states what the character knows about the world, another person, or an event, such as "Tony knows from Maya that Tiffany is missing."
- Preserve character knowledge separately from location, physical_state, current_situation, and event history.
- If a character learned nothing, return that character's before-state knowledge unchanged.
- Output JSON only. No markdown, commentary, or explanations.
"""


ROUTINE_KNOWLEDGE_ACTION_VERBS = {
    "asked", "asks", "asking",
    "called", "calls", "calling", "phoned", "texted", "emailed",
    "closed", "closes", "closing", "opened", "opens", "opening",
    "helped", "helps", "helping", "guided", "guides", "guiding",
    "lowered", "lowers", "lowering", "offered", "offers", "offering",
    "suggested", "suggests", "suggesting", "brewed", "brews", "brewing",
    "invited", "invites", "inviting", "reassured", "reassures", "reassuring",
    "comforted", "comforts", "comforting", "carried", "carries", "carrying",
    "moved", "moves", "moving", "settled", "settles", "settling",
    "prepared", "prepares", "preparing", "placed", "places", "placing",
    "handed", "hands", "handing", "wiped", "wipes", "wiping",
    "brushed", "brushes", "brushing", "stroked", "strokes", "stroking",
    "entered", "enters", "entering", "left", "leaves", "leaving",
    "returned", "returns", "returning", "walked", "walks", "walking",
    "sat", "sits", "sitting", "stood", "stands", "standing",
    "told", "tells", "telling", "said", "says", "saying",
    "described", "describes", "describing", "explained", "explains", "explaining",
    "mentioned", "mentions", "mentioning",
}


def is_routine_action_log_knowledge(
    value: str,
    character_names: list[str],
) -> bool:
    """Identify routine actions mistakenly stored as cumulative knowledge.

    This deliberately targets routine scene logistics, not consequential
    events such as the kidnapping, strikes, injuries, clues, or other material
    facts that characters need to remember for continuity.
    """
    text_value = re.sub(r"^[-*•\s]+", "", str(value or "").strip()).casefold()
    if not text_value:
        return False

    # "Has told Tony that Tiffany is gone" records the act of telling; the
    # consequential fact belongs in Tony's knowledge, not as Maya's action log.
    if re.match(
        r"^(?:(?:has|have|had)\s+)?(?:told|asked|called|offered|suggested|invited)\b",
        text_value,
    ):
        return True

    # Strip common wrappers generated by small local models before inspecting
    # the actual subject and verb: "Know that Tony called..." and
    # "Now knows from Maya that Tony helped...".
    candidate = text_value
    for _ in range(2):
        unwrapped = re.sub(
            r"^(?:(?:now\s+)?knows?\s+(?:from\s+.+?\s+)?that\s+|"
            r"(?:has\s+)?learned\s+that\s+)",
            "",
            candidate,
        )
        unwrapped = re.sub(
            r"^(?:[a-z][a-z '-]+?\s+)?knows?\s+(?:from\s+.+?\s+)?that\s+",
            "",
            unwrapped,
        )
        if unwrapped == candidate:
            break
        candidate = unwrapped

    for name in sorted(
        (str(item).strip().casefold() for item in character_names if str(item).strip()),
        key=len,
        reverse=True,
    ):
        match = re.match(r"^" + re.escape(name) + r"\s+([a-z]+)\b", candidate)
        if match and match.group(1) in ROUTINE_KNOWLEDGE_ACTION_VERBS:
            return True

    # Some local-model outputs wrap routine actions as "Know from Tony that he helped...".
    # After unwrapping the knowledge prefix, the grammatical subject is a pronoun.
    pronoun_match = re.match(r"^(?:he|she|they|it)\s+([a-z]+)\b", candidate)
    if pronoun_match and pronoun_match.group(1) in ROUTINE_KNOWLEDGE_ACTION_VERBS:
        return True
    # This wording also appears in routine caregiving logs, while preserving
    # consequential historical statements such as "Tony gave Tiffany Barnaby".
    if re.match(r"^(?:[a-z][a-z '-]+?\s+)?gave\s+(?:her|him|maya|tony)\s+peace\b", candidate):
        return True

    return False


STATE_SYSTEM_PROMPT = """You are the continuity manager for an ongoing fictional story.

Return ONLY one valid JSON object containing a PARTIAL UPDATE to the current story state.

Rules:
- Record only changes actually caused by the supplied completed story section.
- The most important output is current_situation: ALWAYS return a concise, factual, non-empty description of what is true at the absolute end of the completed prose. This is an ending-state summary, not a list of events and not a guess about what happens next.
- Follow the final paragraphs when describing ending state. Do not report an earlier intermediate action as the ending if later prose shows the characters in a different place or position.
- Do not return a singular "event" field. Do not return character_knowledge; a separate knowledge audit handles that field.
- Return only these ending-state fields: current_situation, location, physical_state, and time_of_day. Do not return event/event-log fields, character_knowledge, scene flags, continuity notes, or unrelated metadata.
- Location is a nested state field. When the baseline current_state has a location object, never return character or primary location values at the top level. Normalize any legacy top-level location fields into the location object before returning the patch.
- Strict field shape: location must be an object whose primary and per-character entries are plain text location descriptions. Never put lists, knowledge facts, or nested objects under location. physical_state must be an object describing each character's actual final position, posture, contact, and movement where established by the prose.
- Do not repeat unchanged fields.
- For changed nested objects, include only changed nested keys.
- For arrays, replace the array only when that array truly changed.
- Treat current_situation as a live scene-state field, not as a scene-plan instruction. When the completed section ends in a materially different immediate situation, update current_situation to a concise description of that ending state so it can serve as the starting state for the next scene.
- Do not copy scene-plan wording, future-scene instructions, hard stops, or author directions into current_situation.
- When the section crosses a scene boundary, describe what is true at the end of the completed section, not what should happen afterward.
- Never invent future events.
- Never turn an unknown fact into a known fact.
- Character knowledge is handled by a separate knowledge audit. Do not analyze, return, or rewrite character_knowledge in this state proposal.
- Treat continuity_notes as editorial reminders only. They are not authoritative story facts, scene instructions, or character knowledge. Never use them as evidence for what happened, never promote them into permanent facts, and never copy them into a new state update unless the completed prose independently establishes the same fact.
- Treat physical_state as a first-class continuity field. It records each character's physical location, position, posture, contact with other characters, and movement state at the absolute end of the supplied section.
- When the completed prose clearly establishes or changes a character's final physical state, include those changed fields under physical_state for that character.
- Physical continuity must follow the actual final prose. Do not move or reposition a character in physical_state merely because a new scene could logically use a different arrangement.
- Record only facts established by the supplied story section.
- Determine the resulting state from what is true at the ABSOLUTE END of the completed section, using the final actions and final paragraphs as the primary evidence.
- The current state is the BEFORE-state baseline only. Never copy a before-state location or situation into the update when the completed section clearly changes it.
- For any character whose location or immediate situation changes during the section, include that changed character under location even if the before-state already listed a different location.
- Use the supplied scene end guidance only to clarify the intended scene boundary. The actual completed prose is authoritative for what happened.
- Do not invent motives, identities, locations, evidence, backstory, or other consequential facts.
- The application owns scene navigation and workflow flags. NEVER return the keys chapter, scene, status, scene_completed, chapter_completed, or scene_cast in a state patch; those are updated by StoryBuilder after the reviewed patch is applied.
- Do not rewrite the complete current_state.json.
- Do not output markdown, explanations, notes, or code fences.
"""


def merge_patch(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)

    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_patch(result[key], value)
        else:
            result[key] = value

    return result


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract the last complete JSON object from model-runner output.

    Some local CLI versions echo portions of the prompt before the model's
    answer. That prompt can contain a valid JSON before-state, so returning
    the first object can mistakenly validate the baseline instead of the
    model's proposed partial update. Prefer the complete object ending latest
    in the output; nested objects end before their containing object.
    """
    decoder = json.JSONDecoder()
    candidates: list[tuple[int, dict[str, Any]]] = []

    for index, char in enumerate(text or ""):
        if char != "{":
            continue
        try:
            obj, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            candidates.append((index + end, obj))

    if candidates:
        return max(candidates, key=lambda candidate: candidate[0])[1]

    raise ValueError("The continuity manager did not return a JSON object.")


def extract_expected_end_state(scene_end_guidance: str) -> dict[str, Any] | None:
    """Extract the structured expected end-state hint from scene guidance."""
    marker = "EXPECTED END STATE HINT"
    if marker not in scene_end_guidance:
        return None

    payload = scene_end_guidance.split(marker, 1)[1]
    if payload.startswith(" ("):
        payload = payload.split("):", 1)[1]
    elif payload.startswith(":"):
        payload = payload[1:]
    payload = payload.strip()
    try:
        value = json.loads(payload)
    except json.JSONDecodeError:
        return None

    if not isinstance(value, dict):
        return None

    # Scene guidance may carry temporary writing notes alongside the intended
    # ending state. Those notes must never be promoted into permanent story
    # continuity or handed to the writer as established facts.
    value.pop("continuity_notes", None)
    value.pop("scene_constraints", None)
    value.pop("scene_guidance", None)
    return value


def normalize_location_patch(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy top-level location fields into the nested location object."""
    if not isinstance(base.get("location"), dict):
        return patch

    location_patch = patch.get("location")
    if not isinstance(location_patch, dict):
        location_patch = {}

    top_level_location_keys = {"primary"}
    top_level_location_keys.update(str(name) for name in base["location"].keys())

    moved = False
    result = dict(patch)
    for key in list(result.keys()):
        if key == "location":
            continue
        if key in top_level_location_keys:
            location_patch[key] = result.pop(key)
            moved = True

    if moved:
        result["location"] = location_patch

    return result


def remove_unchanged(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Remove values that are identical to the baseline."""
    result: dict[str, Any] = {}

    for key, value in patch.items():
        if key not in base:
            result[key] = value
            continue

        base_value = base[key]
        if isinstance(value, dict) and isinstance(base_value, dict):
            nested = remove_unchanged(base_value, value)
            if nested:
                result[key] = nested
        elif value != base_value:
            result[key] = value

    return result


OPTIONAL_STATE_PATCH_FIELDS = {
    # These fields are valid even in older packages that predate their storage.
    "current_situation",
    "location",
    "physical_state",
    "time_of_day",
    "character_knowledge",
    "recent_events",
    "active_objectives",
    "continuity_requirements",
}


END_STATE_PROPOSAL_FIELDS = {
    "current_situation",
    "location",
    "physical_state",
    "time_of_day",
}


def validate_state_proposal(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Validate the narrower output contract used by the main continuity pass."""
    if not isinstance(patch, dict):
        raise ValueError("The proposed state update must be a JSON object.")

    unsupported = sorted(set(patch) - END_STATE_PROPOSAL_FIELDS)
    if unsupported:
        raise ValueError(
            "Invalid continuity proposal: unsupported ending-state field(s): "
            + ", ".join(unsupported)
            + ". Return only current_situation, location, physical_state, and time_of_day."
        )

    situation = patch.get("current_situation")
    if not isinstance(situation, str) or not situation.strip():
        raise ValueError(
            "Invalid state update: 'current_situation' is required and must describe the actual end of the scene."
        )

    return validate_state_patch(base, patch)


def validate_state_patch(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Reject malformed state-update structures before preview or application."""
    if not isinstance(base, dict):
        raise ValueError("The current story state must be a JSON object.")
    if not isinstance(patch, dict):
        raise ValueError("The proposed state update must be a JSON object.")

    if "event" in patch:
        raise ValueError(
            "Invalid state update: unsupported singular 'event' field. "
            "Use current_situation to describe the actual end of the scene."
        )

    app_managed_fields = {
        "chapter", "scene", "status", "scene_completed",
        "chapter_completed", "scene_cast", "story_format_version",
    }
    allowed_fields = set(base) | OPTIONAL_STATE_PATCH_FIELDS | app_managed_fields
    unknown_fields = sorted(set(patch) - allowed_fields)
    if unknown_fields:
        raise ValueError(
            "Invalid state update: unsupported field(s): "
            + ", ".join(unknown_fields)
            + ". Return only supported story-state fields; use current_situation for the scene's ending state."
        )
    forbidden_fields = sorted(app_managed_fields.intersection(patch))
    if forbidden_fields:
        raise ValueError(
            "Invalid state update: these fields are controlled by StoryBuilder's "
            "scene workflow and cannot be proposed by the continuity model: "
            + ", ".join(forbidden_fields)
        )

    if "location" in patch:
        location = patch["location"]
        if not isinstance(location, dict):
            raise ValueError("Invalid state update: 'location' must be an object.")
        for field, value in location.items():
            if not isinstance(value, str):
                raise ValueError(
                    f"Invalid state update at 'location.{field}': location entries must be text. "
                    "Character knowledge belongs under 'character_knowledge', not 'location'."
                )

    if "current_situation" in patch and (
        not isinstance(patch["current_situation"], str)
        or not patch["current_situation"].strip()
    ):
        raise ValueError(
            "Invalid state update: 'current_situation' must be non-empty text describing the actual end of the scene."
        )

    if "character_knowledge" in patch:
        knowledge = patch["character_knowledge"]
        if not isinstance(knowledge, dict):
            raise ValueError("Invalid state update: 'character_knowledge' must be an object.")
        for character, facts in knowledge.items():
            if not isinstance(facts, list) or any(not isinstance(fact, str) for fact in facts):
                raise ValueError(
                    f"Invalid state update at 'character_knowledge.{character}': "
                    "each character's knowledge must be a list of text facts."
                )

    if "physical_state" in patch and not isinstance(patch["physical_state"], dict):
        raise ValueError("Invalid state update: 'physical_state' must be an object.")

    return patch


def remove_prior_chapter_opening_markers(
    state: dict[str, Any],
    previous_chapter: int,
    target_chapter: int,
) -> dict[str, Any]:
    """Remove the prior chapter's opening marker from both continuity lists."""
    if not isinstance(state, dict) or int(target_chapter) <= int(previous_chapter):
        return state

    previous = int(previous_chapter)
    opening_marker = re.compile(
        rf"^\s*chapter\s+{previous}\s+(?:begins|starts)(?:\s+here)?[.!]?\s*$",
        re.IGNORECASE,
    )
    restored = dict(state)
    changed = False
    for field in ("continuity_notes", "continuity_requirements"):
        items = state.get(field)
        if not isinstance(items, list):
            continue
        cleaned = [
            item
            for item in items
            if not (isinstance(item, str) and opening_marker.fullmatch(item))
        ]
        if cleaned != items:
            restored[field] = cleaned
            changed = True
    return restored if changed else state


def reconcile_merged_state_locations(
    state: dict[str, Any],
    patch: dict[str, Any],
) -> dict[str, Any]:
    """Keep nested character locations consistent after applying a state patch.

    Some older story states retain character location descriptions as top-level
    keys as well as under location. Once a nested location map exists, the
    nested map is authoritative. If this patch changes a character's location,
    mirror that location into the character's physical_state entry so an older
    physical_state.location cannot contradict the accepted scene ending.
    """
    result = dict(state)
    location = result.get("location")
    if not isinstance(location, dict):
        return result

    # Remove legacy top-level duplicates, but retain unrelated top-level state.
    for name in location:
        if name == "primary":
            continue
        if name in result and isinstance(result[name], str):
            result.pop(name, None)
    if isinstance(result.get("primary"), str):
        result.pop("primary", None)

    location_patch = patch.get("location") if isinstance(patch, dict) else None
    physical_state = result.get("physical_state")
    if not isinstance(location_patch, dict) or not isinstance(physical_state, dict):
        return result

    updated_physical_state = dict(physical_state)
    changed = False
    for name, final_location in location_patch.items():
        if name == "primary" or not isinstance(final_location, str):
            continue
        character_state = physical_state.get(name)
        if not isinstance(character_state, dict):
            continue
        if character_state.get("location") == final_location:
            continue

        updated_character_state = dict(character_state)
        updated_character_state["location"] = final_location
        updated_physical_state[name] = updated_character_state
        changed = True

    if changed:
        result["physical_state"] = updated_physical_state
    return result


class StateManager:
    """Turns accepted prose into a reviewable current_state patch."""

    @staticmethod
    def merge_patch(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        merged = merge_patch(base, patch)
        return reconcile_merged_state_locations(merged, patch)

    @staticmethod
    def validate_patch(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        """Validate a proposed partial update before it can be applied."""
        return validate_state_patch(base, patch)

    @staticmethod
    def _detect_accelerator() -> str | None:
        """Use CPU unless acceleration is explicitly requested."""
        override = os.environ.get("STORY_LLM_DEVICE", "").strip()
        return override or None

    @staticmethod
    def _propose_knowledge_delta(
        model: Path,
        current_state: dict[str, Any],
        story_text: str,
    ) -> dict[str, list[str]]:
        """Run a focused pass that returns cumulative post-scene knowledge."""
        cast = [
            str(name).strip()
            for name in current_state.get("scene_cast", [])
            if str(name).strip()
        ]
        if not cast:
            return {}

        existing = current_state.get("character_knowledge", {})
        knowledge_before = {}
        if isinstance(existing, dict):
            for name in cast:
                values = existing.get(name)
                if values is None:
                    for key, candidate in existing.items():
                        if str(key).casefold() == name.casefold():
                            values = candidate
                            break
                if isinstance(values, list):
                    knowledge_before[name] = [
                        str(item).strip() for item in values if str(item).strip()
                    ]
                elif isinstance(values, str) and values.strip():
                    knowledge_before[name] = [values.strip()]

        audit_prompt = (
            "Audit the entire completed story section and produce the complete cumulative knowledge "
            "for every current-scene character after the section. Preserve all valid before-state facts, "
            "add all facts learned during the section, and remove obsolete negative statements when the "
            "character now knows the corresponding fact. Do not omit a prior fact just because it is not "
            "repeated in this section. If and only if the completed prose directly corrects, contradicts, "
            "or resolves a prior fact, optionally return a top-level \"_superseded_facts\" object mapping "
            "the character name to exact prior fact strings that are no longer current. Older models may "
            "omit this optional field; do not require it for ordinary outputs.\n\n"
            "SCENE CAST:\n"
            + json.dumps(cast, indent=2, ensure_ascii=False)
            + "\n\nCHARACTER KNOWLEDGE BEFORE THIS SECTION:\n"
            + json.dumps(knowledge_before, indent=2, ensure_ascii=False)
            + "\n\nCOMPLETED STORY SECTION:\n"
            + story_text
        )

        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = str(DEFAULT_LLAMA.parent) + (
            ":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else ""
        )

        device = StateManager._detect_accelerator()
        args = [str(DEFAULT_LLAMA), "-m", str(model)]
        if device:
            args.extend(["--device", device, "-ngl", "all"])
        else:
            args.extend(["-ngl", "0", "--device", "none"])

        args.extend([
            "-c", "8192",
            "--reasoning", "off",
            "--temp", "0.10",
            "--top-k", "20",
            "--top-p", "0.80",
            "--repeat-last-n", "256",
            "--repeat-penalty", "1.08",
            "--n-predict", "900",
            "--system-prompt", KNOWLEDGE_AUDIT_SYSTEM_PROMPT,
            "--prompt", audit_prompt,
            "--color", "off",
            "--no-display-prompt",
            "--simple-io",
            "--single-turn",
        ])

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
            raise RuntimeError("Character knowledge audit timed out.") from exc
        if proc.returncode not in (0, None):
            raise RuntimeError(
                "Character knowledge audit failed.\n" + (output or "")[-2000:]
            )

        raw = extract_json_object(output)
        result: dict[str, Any] = {}
        for name in cast:
            values = raw.get(name)
            if not isinstance(values, list):
                continue
            cleaned = [str(item).strip() for item in values if str(item).strip()]
            if cleaned:
                result[name] = cleaned
            elif name in raw:
                result[name] = []

        # Optional and backward-compatible: older models may return only the
        # original character-name-to-list schema. Accept explicit supersession
        # declarations when a model can identify prior facts directly corrected
        # by the completed prose.
        superseded = raw.get("_superseded_facts")
        if isinstance(superseded, dict):
            cleaned_superseded: dict[str, list[str]] = {}
            for name in cast:
                values = superseded.get(name)
                if isinstance(values, list):
                    facts = [str(item).strip() for item in values if str(item).strip()]
                    if facts:
                        cleaned_superseded[name] = facts
            if cleaned_superseded:
                result["_superseded_facts"] = cleaned_superseded
        return result

    @staticmethod
    def _merge_knowledge_delta(
        current_state: dict[str, Any],
        patch: dict[str, Any],
        delta: dict[str, Any],
    ) -> None:
        """Merge audited knowledge while guarding against omitted prior facts."""
        scene_characters = [
            str(name).strip()
            for name in current_state.get("scene_cast", [])
            if str(name).strip()
        ]

        def normalize_knowledge(
            values: list[str],
            owner: str = "",
        ) -> list[str]:
            cleaned = []
            learned_facts = [
                str(value).strip()
                for value in values
                if str(value).strip().casefold().startswith(("learned ", "now knows ", "knows "))
            ]
            has_new_detail_knowledge = any(
                "learned " in fact.casefold()
                or "now knows " in fact.casefold()
                for fact in learned_facts
            )
            for value in values:
                text_value = str(value).strip()
                if not text_value:
                    continue
                if is_routine_action_log_knowledge(text_value, scene_characters):
                    continue
                # A broad negative such as "does not know the details" becomes
                # stale when this audit has also established newly learned
                # details. Preserve other negative knowledge statements because
                # they may still be true.
                lowered = text_value.casefold()
                if (
                    has_new_detail_knowledge
                    and lowered.startswith(("does not know", "doesn't know"))
                    and "detail" in lowered
                ):
                    continue
                if text_value not in cleaned:
                    cleaned.append(text_value)
            return cleaned
        base_knowledge = current_state.get("character_knowledge", {})
        if not isinstance(base_knowledge, dict):
            base_knowledge = {}

        proposed = patch.get("character_knowledge", {})
        if not isinstance(proposed, dict):
            proposed = {}

        changed: dict[str, list[str]] = {}

        # Preserve non-scene character knowledge exactly as it was.
        combined = dict(base_knowledge)

        superseded_payload = delta.get("_superseded_facts", {})
        if not isinstance(superseded_payload, dict):
            superseded_payload = {}

        # The audit may omit valid prior facts even when asked for cumulative
        # knowledge. Treat ordinary character arrays as additions and cleanup,
        # not as permission to erase facts that the model failed to repeat.
        # Explicit supersession metadata is optional, so models using the older
        # output schema remain safe and backward-compatible.
        for name, values in delta.items():
            if name == "_superseded_facts":
                continue

            prior_values = base_knowledge.get(name, [])
            if isinstance(prior_values, str):
                prior_values = [prior_values]
            if not isinstance(prior_values, list):
                prior_values = []

            superseded_values = superseded_payload.get(name, [])
            if not isinstance(superseded_values, list):
                superseded_values = []
            superseded_keys = {
                re.sub(r"\\s+", " ", str(value).strip()).casefold()
                for value in superseded_values
                if str(value).strip()
            }

            def is_superseded(value: Any) -> bool:
                key = re.sub(r"\\s+", " ", str(value).strip()).casefold()
                return bool(key and key in superseded_keys)

            proposed_values = values if isinstance(values, list) else []
            prior_values = [value for value in prior_values if not is_superseded(value)]
            proposed_values = [value for value in proposed_values if not is_superseded(value)]
            combined_values = [*prior_values, *proposed_values]
            cleaned = normalize_knowledge(combined_values, name)
            combined[name] = cleaned

        # Preserve any useful model-derived knowledge for scene characters only
        # when the focused audit did not return that character.
        for name, values in proposed.items():
            if name in delta:
                continue
            if isinstance(values, list):
                combined[name] = [
                    str(value).strip()
                    for value in values
                    if str(value).strip()
                ]

        for name, values in combined.items():
            before_values = base_knowledge.get(name, [])
            if isinstance(before_values, str):
                before_values = [before_values]
            if not isinstance(before_values, list):
                before_values = []
            before_clean = [str(v).strip() for v in before_values if str(v).strip()]
            if values != before_clean:
                changed[name] = values

        if changed:
            patch["character_knowledge"] = changed

    @staticmethod
    def propose(
        model_path: str | Path,
        current_state: dict[str, Any],
        story_text: str,
        scene_end_guidance: str | None = None,
    ) -> dict[str, Any]:
        if not story_text.strip():
            raise ValueError("There is no story text to analyze.")

        model = Path(os.path.expanduser(str(model_path))).resolve()
        if not model.is_file() or model.suffix.casefold() != ".gguf":
            raise ValueError("The selected model is not a valid GGUF file.")

        if not DEFAULT_LLAMA.is_file():
            raise FileNotFoundError(
                f"llama-cli not found: {DEFAULT_LLAMA}"
            )

        completed_text = story_text.strip()
        end_guidance = (scene_end_guidance or "").strip()
        final_excerpt = completed_text[-3000:]

        prompt_parts = [
            "CURRENT STATE BEFORE THIS SECTION:\n",
            json.dumps(current_state, indent=2, ensure_ascii=False),
        ]

        prompt_parts.extend([
            "\n\nCOMPLETED STORY SECTION:\n",
            completed_text,
        ])

        if end_guidance:
            prompt_parts.extend([
                "\n\nSCENE END GUIDANCE (REFERENCE ONLY):\n",
                end_guidance,
                "\nUse this only to identify the intended ending boundary. "
                "If an EXPECTED END STATE HINT is present, treat it as a candidate summary of the intended ending, "
                "but verify it against the completed prose. When the prose clearly confirms the hinted ending, use "
                "the hinted changed locations and immediate situation rather than copying the before-state. "
                "Do not copy planned wording or invent anything that did not occur in the completed prose."
            ])

        prompt_parts.extend([
            "\n\nFINAL PART OF COMPLETED STORY SECTION:\n",
            final_excerpt,
            "\n\nDetermine the smallest state update needed AFTER this completed section. "
            "Read the entire section, but give special weight to the final actions and final paragraph. "
            "If the expected ending-state hint agrees with the completed prose, the returned patch should "
            "reflect that ending rather than the initial state. "
            "The current state above describes what was true BEFORE the section and must not override what "
            "the completed prose establishes at the end. For each character whose final location, physical position, contact, or immediate "
            "situation changed, include the changed value under physical_state and/or location as appropriate. Update current_situation to describe "
            "the actual immediate situation at the absolute end of the completed section, not the starting "
            "situation and not what should happen in the next scene. Keep it concise and factual. "
            "Do not copy planning instructions or future events into it. "
            "Always return non-empty current_situation, plus only changed location, physical_state, and/or time_of_day fields. "
            "Do not return character_knowledge, event/event-log fields, scene flags, or other metadata."
        ])
        prompt = "".join(prompt_parts)

        def run_model(prompt_text: str) -> str:
            env = os.environ.copy()
            env["LD_LIBRARY_PATH"] = str(
                DEFAULT_LLAMA.parent
            ) + (
                ":" + env["LD_LIBRARY_PATH"]
                if env.get("LD_LIBRARY_PATH")
                else ""
            )

            device = StateManager._detect_accelerator()
            args = [
                str(DEFAULT_LLAMA),
                "-m", str(model),
            ]
            if device:
                args.extend(["--device", device, "-ngl", "all"])
            else:
                args.extend(["-ngl", "0", "--device", "none"])

            args.extend([
                "-c", "8192",
                "--reasoning", "off",
                "--temp", "0.10",
                "--top-k", "20",
                "--top-p", "0.80",
                "--repeat-last-n", "256",
                "--repeat-penalty", "1.08",
                "--n-predict", "1000",
                "--system-prompt", STATE_SYSTEM_PROMPT,
                "--prompt", prompt_text,
                "--color", "off",
                "--no-display-prompt",
                "--simple-io",
                "--single-turn",
            ])

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
                raise TimeoutError("Continuity analysis timed out.") from exc

            if proc.returncode not in (0, None):
                raise RuntimeError(
                    "Continuity analysis failed.\n"
                    + (output or "")[-3000:]
                )
            return output or ""

        output = run_model(prompt)
        patch = None

        # Local models occasionally place character knowledge lists under
        # location. Reject the malformed proposal, ask for one corrected JSON
        # patch, and strictly validate the corrected response as well.
        for attempt in range(2):
            try:
                candidate = extract_json_object(output)
                # Knowledge is produced by a dedicated audit below. Never let
                # the general state model turn scene actions into "knowledge"
                # or replace cumulative facts with an event log.
                candidate.pop("character_knowledge", None)
                if "location" in candidate and not isinstance(candidate["location"], dict):
                    raise ValueError("Invalid state update: 'location' must be an object.")
                candidate = normalize_location_patch(current_state, candidate)
                validate_state_proposal(current_state, candidate)
                patch = candidate
                break
            except (TypeError, ValueError) as exc:
                if attempt == 1:
                    # If the model repeats the location-shape mistake after the
                    # correction prompt, discard only malformed location values.
                    # This preserves the baseline location instead of guessing,
                    # while allowing independently valid state changes to be reviewed.
                    error_text = str(exc)
                    if (
                        "Invalid state update at 'location." in error_text
                        or "Invalid state update: 'location' must be an object" in error_text
                    ):
                        try:
                            recovered = extract_json_object(output)
                            # Character knowledge is always handled by the
                            # dedicated knowledge audit, never salvaged here.
                            recovered.pop("character_knowledge", None)
                            # Normalize legacy top-level location keys FIRST.
                            # Otherwise a malformed top-level Maya/Tony value can
                            # be moved under location after that field was cleaned.
                            recovered = normalize_location_patch(
                                current_state,
                                recovered,
                            )
                            raw_location = recovered.get("location")
                            if isinstance(raw_location, dict):
                                clean_location = {
                                    name: value
                                    for name, value in raw_location.items()
                                    if isinstance(value, str)
                                }
                                if clean_location:
                                    recovered["location"] = clean_location
                                else:
                                    recovered.pop("location", None)
                            else:
                                recovered.pop("location", None)

                            validate_state_proposal(current_state, recovered)
                            patch = recovered
                            break
                        except (TypeError, ValueError):
                            # Do not salvage if any other part of the proposal
                            # remains malformed. The ordinary error below retains
                            # the full validator detail for diagnosis.
                            pass

                    excerpt = (output or "")[-1800:]
                    raise ValueError(
                        "The continuity model returned an invalid state update even after one "
                        "automatic correction attempt. No state changes were applied.\n\n"
                        f"Validation detail: {exc}\n\nLast model response:\n{excerpt}"
                    ) from exc

                repair_prompt = (
                    prompt
                    + "\n\nAUTOMATIC CORRECTION REQUIRED: your previous JSON proposal was "
                    "rejected by the application's state validator. Correct the same proposal "
                    "using only facts supported by the completed prose. Do not invent new events.\n"
                    + f"VALIDATION ERROR: {exc}\n"
                    + "SCHEMA REMINDER: return ONLY current_situation, location, physical_state, and time_of_day. Do not return event, events, recent_events, character_knowledge, or other fields. "
                    "Always include a non-empty current_situation describing what is true at the absolute end of the completed prose, not an earlier action. "
                    "If supplied, location must be an object with plain-text primary and per-character location descriptions; physical_state must be an object. "
                    "Do not turn actions the characters performed into knowledge facts. Return corrected JSON only.\n"
                    + "PREVIOUS INVALID RESPONSE TO CORRECT:\n"
                    + (output or "")[-3000:]
                )
                output = run_model(repair_prompt)

        if patch is None:
            raise ValueError(
                "The continuity model could not produce a valid state update. "
                "No state changes were applied."
            )

        # Models sometimes repeat unchanged state. Normalize that away so a
        # proposal contains only actual changes.
        patch = remove_unchanged(current_state, patch)

        # Knowledge changes are audited separately because a broad continuity
        # pass can miss facts learned through dialogue when physical state does
        # not change. The focused pass returns only new facts and never replaces
        # the existing knowledge list.
        try:
            knowledge_delta = StateManager._propose_knowledge_delta(
                model,
                current_state,
                completed_text,
            )
            if knowledge_delta:
                StateManager._merge_knowledge_delta(
                    current_state,
                    patch,
                    knowledge_delta,
                )
        except (ValueError, RuntimeError):
            # The main state proposal remains usable if the optional knowledge
            # audit cannot be parsed or completed. Do not fabricate knowledge.
            pass

        # End-state hints are included in the prompt as planning context only.
        # Never merge a planned state directly over facts inferred from accepted
        # prose: a planned event may have been omitted, changed, or not actually
        # occurred in the scene that the author accepted.
        StateManager.validate_patch(current_state, patch)
        return patch
