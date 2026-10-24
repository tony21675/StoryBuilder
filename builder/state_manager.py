from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from builder.workspace import LLAMA as DEFAULT_LLAMA

KNOWLEDGE_AUDIT_SYSTEM_PROMPT = """You are a delta auditor for character knowledge in an ongoing fictional novel.

Return ONLY valid JSON in this shape:
{"CharacterName": ["one specific NEW fact learned in this section"], "_superseded_facts": {"CharacterName": ["exact supplied prior fact made obsolete by this section"]}}

This is a DELTA, not a regenerated character profile. The application retains all prior knowledge and merges your additions. For a character who learned nothing new, omit their key or return an empty array. Never copy existing knowledge into the answer.

Rules:
- Use the full completed prose to identify who is physically present, enters, hears relevant dialogue, reads information, or directly observes an event. scene_cast records the opening cast, not every later arrival. A person merely mentioned or elsewhere learns nothing; a character merely discussed does not learn from the conversation.
- Return only facts newly learned in this section. The before-state facts are a small relevance-selected sample, not a complete list; do not infer that an omitted fact is false.
- State each addition as a durable, specific proposition about the world, a person, or an event. Do not summarize cumulative knowledge or repeat the supplied before-state facts.
- A character learns facts they hear in dialogue, directly observe, read, or personally experience. Do not give anyone knowledge they did not receive. When a character directly identifies or explains a discovery in the prose, record that specific discovery in that character's knowledge; if the explanation is heard by other characters, record it for those listeners too. Do not leave a meaningful technical discovery present only in the clue ledger while omitting it from the discoverer's knowledge.
- Preserve distinct consequential details appropriate to the story, including important actions, injuries, observations, technical findings, and other evidence. Do not compress several facts into a vague summary.
- Do not invent motives, identities, locations, evidence, history, or unstated conclusions.
- Knowledge is not an event log. Never list routine scene actions, a character's own actions, or the act of telling/asking/offering as knowledge. A character making tea is an event, not a knowledge fact; a character learning a specific fact from another character is a fact in the learner's knowledge.
- Temporary physical state, location, posture, contact, movement, clothing, and immediate activity belong in physical_state, not cumulative knowledge. Do not add them as new knowledge unless they have independent lasting significance.
- Only supersede an exact fact present in the supplied selected existing-knowledge context, and only when the prose directly contradicts or resolves it. Do not supersede facts merely because the current scene omits them.
- Keep durable observations, discoveries, evidence, and historical knowledge even when the character's interpretation later changes. The _superseded_facts field may remove temporary current-state notes (such as someone currently wearing an outfit or being asleep) and an explicitly replaced current belief/unknown-status note. Do not remove a durable observation just because a later interpretation changes.
- Deduplicate paraphrases of the same observation in your output. Keep independently consequential details separate.
- If there are no valid new facts or supersessions, return {}.
- Output JSON only, without markdown or explanations.
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
    events, conflicts, injuries, discoveries, clues, or other material
    facts that characters need to remember for continuity.
    """
    text_value = re.sub(r"^[-*•\s]+", "", str(value or "").strip()).casefold()
    if not text_value:
        return False

    # "Has told another character that a person is missing" records the act of
    # telling; the consequential fact belongs in the listener's knowledge, not
    # as the speaker's action log.
    if re.match(
        r"^(?:(?:has|have|had)\s+)?(?:told|asked|called|offered|suggested|invited)\b",
        text_value,
    ):
        return True

    # Strip common wrappers generated by small local models before inspecting
    # the actual subject and verb, such as a knowledge prefix around a routine
    # action reported by another character.
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

    # Some models emit a bare verb fragment ("Prepared a drink", "Sat beside a friend")
    # or passive phrasing ("Was guided by another character") instead of naming the actor.
    # Inspect the first meaningful verb after common auxiliaries, but only drop
    # verbs already classified as routine logistics above. Consequential verbs
    # such as striking, injuring, damaging, or physically moving something are deliberately retained.
    fragment_match = re.match(
        r"^(?:(?:has|have|had|is|are|was|were|been|being|does|did)\s+)*(?:now\s+)?([a-z]+)\b",
        candidate,
    )
    if fragment_match and fragment_match.group(1) in ROUTINE_KNOWLEDGE_ACTION_VERBS:
        return True

    for name in sorted(
        (str(item).strip().casefold() for item in character_names if str(item).strip()),
        key=len,
        reverse=True,
    ):
        match = re.match(r"^" + re.escape(name) + r"\s+([a-z]+)\b", candidate)
        if match and match.group(1) in ROUTINE_KNOWLEDGE_ACTION_VERBS:
            return True

    # Some local-model outputs wrap routine actions in a knowledge prefix with pronouns.
    # After unwrapping the knowledge prefix, the grammatical subject is a pronoun.
    pronoun_match = re.match(r"^(?:he|she|they|it)\s+([a-z]+)\b", candidate)
    if pronoun_match and pronoun_match.group(1) in ROUTINE_KNOWLEDGE_ACTION_VERBS:
        return True
    # This wording also appears in routine caregiving logs, while preserving
    # consequential historical statements such as a character giving another person a specific keepsake.
    if re.match(r"^(?:[a-z][a-z '-]+?\s+)?gave\s+(?:her|him|them|[a-z][a-z'-]+)\s+peace\b", candidate):
        return True

    return False


STATE_SYSTEM_PROMPT = """You are the continuity manager for an ongoing fictional story.

Return ONLY one valid JSON object containing a PARTIAL UPDATE to the current story state.

Rules:
- Record only changes actually caused by the supplied completed story section.
- The most important output is current_situation: ALWAYS return a concise, factual, non-empty description of what is true at the absolute end of the completed prose. This is an ending-state summary, not a list of events and not a guess about what happens next.
- Follow the final paragraphs when describing ending state. Do not report an earlier intermediate action as the ending if later prose shows the characters in a different place or position.
- Do not return a singular "event" field or character_knowledge; a separate knowledge audit handles character knowledge.
- Return only these transition fields: current_situation, location, physical_state, time_of_day, active_objectives, new_clues, resolved_clues, new_unresolved_questions, resolved_questions, and new_recent_events. Do not return chapter/scene flags, scene_cast, continuity requirements/notes, active_clues, character_knowledge, or unrelated metadata. StoryBuilder processes the temporary resolved/new clue and question fields; new_clues also replaces the previous scene's new_clues list, and newly established clues are reconciled into active_clues.
- Do not return event/event-log fields directly, character_knowledge, scene flags, continuity notes, active_clues, or unrelated metadata. New event additions must use the separate new_recent_events field. New clue and unresolved-question changes must use new_clues, resolved_clues, new_unresolved_questions, and resolved_questions rather than rewriting the complete existing lists.
- Location is a nested state field. When the baseline current_state has a location object, never return character or primary location values at the top level. Normalize any legacy top-level location fields into the location object before returning the patch.
- Strict field shape: location must be an object whose primary and per-character entries are plain text location descriptions. Never put lists, knowledge facts, or nested objects under location. physical_state must be an object describing each character's actual final location, position, posture, contact, movement, and (when explicitly established and continuity-relevant) clothing.
- Do not repeat unchanged fields.
- For changed nested objects, include only changed nested keys.
- For arrays, replace the array only when that array truly changed.
- JSON null in a partial update is an explicit deletion marker for an existing object key; StoryBuilder removes that key instead of storing null. Use it only when the prose establishes that a prior field/item is no longer applicable or an active objective has ended. For example, set a stale physical_state subfield such as position, posture, contact, movement, condition, activity, interaction, a temporarily held object, or temporary clothing to null when it no longer applies and is not replaced by a new value. Set active_objectives.Character to null when that objective is complete, abandoned, or superseded. Do not use null for facts that are merely absent from this scene, and never delete a character's location just because the character is off-screen. Do not put null inside arrays.
- Examine the full completed prose for newly introduced, concrete clues. Include concrete identifying evidence such as a visible injury or mark inflicted during the event, a specific scent, a vehicle detail or movement, a plate detail, a distinctive sound, or a directly observed route. Do not leave an investigative detail only in character_knowledge when it is relevant to finding a person or vehicle. Return new_clues as concise observable facts (use [] when there are none), not interpretations or guessed explanations. Keep one observation's details together: do not invent an additional scent, split one smell into multiple scents, or strengthen a witness's uncertain comparison into certainty. Return resolved_clues only for exact existing active_clues entries that the prose explicitly resolves or disproves. Do not remove an existing clue merely because it is not repeated. The application also requires direct textual evidence of resolution before removing a clue; if no clear resolution occurs in the completed prose, omit it. Do not report a clue as new when the same clue is already in active_clues; the application also filters duplicates.
- Return new_unresolved_questions only for concrete factual unknowns made salient by this scene that remain unanswered. Return resolved_questions only for exact existing unresolved_questions entries answered by the completed prose. Preserve all other existing clues and questions; StoryBuilder will apply additions and explicit removals without asking the model to regenerate the whole historical list.
- Treat current_situation as a live scene-state field, not as a scene-plan instruction. When the completed section ends in a materially different immediate situation, update current_situation to a concise description of that ending state so it can serve as the starting state for the next scene. Never invent a prior diagnosis or hypothesis just to describe a shift in understanding; only say the crew was investigating a pressure leak, blockage, breach, or other specific failure mode if the before-state or completed prose actually establishes it.
- Do not copy scene-plan wording, future-scene instructions, hard stops, or author directions into current_situation.
- When the section crosses a scene boundary, describe what is true at the end of the completed section, not what should happen afterward.
- Never invent future events.
- Never turn an unknown fact into a known fact.
- Character knowledge is handled by a separate knowledge audit. Do not analyze, return, or rewrite character_knowledge in this state proposal.
- Treat continuity_notes as editorial reminders only. They are not authoritative story facts, scene instructions, or character knowledge. Never use them as evidence for what happened, never promote them into permanent facts, and never copy them into a new state update unless the completed prose independently establishes the same fact.
- Treat legacy cast restrictions in continuity_requirements or continuity_notes as stale schema wording for scene membership. In particular, do not interpret "Only characters explicitly listed for a scene are physically present and participating in that scene" as excluding later arrivals. scene_cast identifies the opening cast; actual presence and knowledge are determined by the completed prose and starting context. Do not rewrite continuity_requirements or continuity_notes in this state patch.
- Treat physical_state as a first-class continuity field. It records each character's physical location, position, posture, contact with other characters, movement state, and explicitly established continuity-relevant clothing at the absolute end of the supplied section.
- When the completed prose clearly establishes or changes a character's final physical state, include those changed fields under physical_state for that character. An explicit change from sleepwear to daytime clothing must replace a stale temporary-outfit detail.
- Physical continuity must follow the actual final prose. Read the final paragraphs for every character's last movement or interaction; do not assume a character returns to a previous seat after standing, or infer an unshown movement. No character can jump between locations without a stated or clearly implied transition; keep location and physical_state.location consistent.
- Keep ending-state summaries grounded in what occurred, not in earlier scene beats repeated as if new. Do not make the next scene restart an already completed event.
- During a developing emergency, record the actual readings, warnings, backup response, and current margin as observed; do not turn a first fault into imminent death or describe a root cause that the evidence has not established.
- Preserve uncertainty: a matching material signature can be a clue or hypothesis but does not prove where the material entered, what component failed, or whether it caused the symptoms. Keep those as unresolved questions until the prose confirms them.
- Record only facts established by the supplied story section.
- Determine the resulting state from what is true at the ABSOLUTE END of the completed section, using the final actions and final paragraphs as the primary evidence.
- The current state is the BEFORE-state baseline only. Never copy a before-state location, clothing detail, or situation into the update when the completed prose clearly changes it.
- For any character whose location or immediate situation changes during the section, include that changed character under location even if the before-state already listed a different location. The character's location entry and physical_state.<character>.location must describe the same ending area at comparable granularity. When the prose moves someone from one named area to another, update both fields; a relational position such as leaning over another character is not a substitute for the actual location. Never preserve a before-state location that conflicts with the completed prose.
- Update active_objectives only for characters whose current goal or role is changed or newly established by the accepted prose. Return a partial object with concise replacement text for those characters only; use null for a character whose prior objective is no longer active. If a group has only agreed to help, keep the objective broad and do not invent assignments, leads, investigation steps, or rescue plans. Replace objectives directly contradicted by the scene; use null to remove objectives that are completed, abandoned, or superseded instead of carrying them forward unchanged.
- Return new_recent_events as an array of concise factual event strings newly established in the completed section, in chronological order. Each list item must be a plain JSON string, never an object such as {"event": "..."}. Preserve separate, consequential beats within an interaction instead of collapsing them into a generic emotional summary. In particular, record meaningful quoted relationship milestones such as a first-time nickname and the other character's acceptance or rejection, as well as the surrounding hug or gesture when both matter. Do not repeat events already present in the before-state recent_events list, do not include interpretations or future plans, and use an empty array if no meaningful new events occurred. The application appends these to the existing history and keeps the most recent twelve entries.
- The completed prose is the source of truth for what happened.
- Do not invent motives, identities, locations, evidence, backstory, or other consequential facts.
- The application owns scene navigation and workflow flags. NEVER return the keys chapter, scene, status, scene_completed, chapter_completed, or scene_cast in a state patch; those are updated by StoryBuilder after the reviewed patch is applied.
- Do not rewrite the complete current_state.json.
- Do not output markdown, explanations, notes, or code fences.
"""


def merge_patch(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Apply a recursive partial update; null values explicitly delete stale keys."""
    result = dict(base)

    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            nested = merge_patch(result[key], value)
            if nested:
                result[key] = nested
            else:
                # A recursive deletion can leave a character or state section
                # empty. Prune that shell instead of preserving an empty stale
                # object in the saved state.
                result.pop(key, None)
        else:
            result[key] = value

    return result

def combine_state_patches(
    base_patch: dict[str, Any],
    override_patch: dict[str, Any],
) -> dict[str, Any]:
    """Overlay two partial patches while preserving null deletion markers.

    Unlike merge_patch(), this composes proposals rather than applying them to
    the stored state. A null in the override must survive so the eventual
    state-application step can delete the corresponding saved field.
    """
    result = dict(base_patch)
    for key, value in override_patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = combine_state_patches(result[key], value)
        else:
            result[key] = value
    return result


def extract_json_object(
    text: str,
    *,
    required_keys: set[str] | None = None,
) -> dict[str, Any]:
    """Extract the last complete JSON object from model-runner output.

    Some local CLI versions echo portions of the prompt before the model's
    answer. That prompt can contain a valid JSON before-state, so returning
    the first object can mistakenly validate the baseline instead of the
    model's proposed partial update. Prefer the complete object ending latest;
    nested objects end before their containing object.

    For continuity proposals, required_keys ensures a nested object such as
    {"event": "..."} is never mistaken for the complete state proposal when
    the enclosing JSON is malformed. A valid state proposal ends after all of
    its nested objects, so the last complete object must have the required key.
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
        latest = max(candidates, key=lambda candidate: candidate[0])[1]
        if required_keys and not required_keys.issubset(latest.keys()):
            required = ", ".join(sorted(required_keys))
            raise ValueError(
                "The continuity manager did not return a complete JSON object "
                + "containing required field(s): " + required + "."
            )
        return latest

    if required_keys:
        required = ", ".join(sorted(required_keys))
        raise ValueError(
            "The continuity manager did not return a complete JSON object "
            + "containing required field(s): " + required + "."
        )
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
            value = result[key]
            # A known character's dictionary containing physical-state fields is
            # not a location value; leave it for the physical-state normalizer.
            # Preserve legacy handling of other malformed location values so the
            # bounded recovery path can discard them without losing good fields.
            looks_like_physical_state = (
                isinstance(value, dict)
                and bool(PHYSICAL_STATE_CHARACTER_FIELDS.intersection(value))
            )
            if looks_like_physical_state:
                continue
            location_patch[key] = result.pop(key)
            moved = True

    if moved:
        result["location"] = location_patch

    return result

PHYSICAL_STATE_CHARACTER_FIELDS = {
    "location",
    "position",
    "posture",
    "contact",
    "movement",
    "clothing",
    "condition",
    "activity",
    "interaction",
}


def normalize_physical_state_patch(
    base: dict[str, Any],
    patch: dict[str, Any],
    scene_characters: list[str] | None = None,
) -> dict[str, Any]:
    """Move unambiguously misplaced per-character physical state under physical_state.

    Some local models emit later-arriving characters at the proposal's top level
    instead of nesting them under physical_state. Only known character names
    with a recognizable physical-state object are moved; arbitrary unsupported
    fields are deliberately left in place for validation to reject.
    """
    if not isinstance(patch, dict):
        return patch

    current_physical = patch.get("physical_state", {})
    if not isinstance(current_physical, dict):
        return patch

    known_names: dict[str, str] = {}

    def remember_names(values: Any) -> None:
        if isinstance(values, dict):
            names = values.keys()
        elif isinstance(values, list):
            names = values
        else:
            return
        for raw_name in names:
            name = str(raw_name).strip()
            if name and name.casefold() != "primary":
                known_names.setdefault(name.casefold(), name)

    remember_names(base.get("scene_cast"))
    remember_names(scene_characters)
    for field in ("physical_state", "character_knowledge", "active_objectives", "location"):
        remember_names(base.get(field))

    result = dict(patch)
    physical_patch = dict(current_physical)
    nested_names = {str(name).casefold() for name in physical_patch}
    moved = False
    transition_fields = {
        "current_situation",
        "location",
        "physical_state",
        "time_of_day",
        "active_objectives",
        "new_recent_events",
    }

    for key, value in list(result.items()):
        if key in transition_fields or not isinstance(value, dict):
            continue
        canonical_name = known_names.get(str(key).casefold())
        if canonical_name is None:
            continue
        if not PHYSICAL_STATE_CHARACTER_FIELDS.intersection(value):
            continue
        # If a character already has a nested entry, two competing descriptions
        # are ambiguous. Leave the extra key untouched so normal validation
        # reports it instead of silently choosing one version.
        if canonical_name.casefold() in nested_names:
            continue

        physical_patch[canonical_name] = value
        nested_names.add(canonical_name.casefold())
        result.pop(key, None)
        moved = True

    if moved:
        result["physical_state"] = physical_patch

    return result

def normalize_recent_event_entries(patch: dict[str, Any]) -> dict[str, Any]:
    """Convert exact {"event": "..."} list items to plain event strings.

    Small local models sometimes wrap recent-event strings in single-key
    objects despite the schema instructions. Unwrap only that exact shape;
    leave other malformed entries intact for the validator to reject.
    """
    events = patch.get("new_recent_events")
    if not isinstance(events, list):
        return patch

    normalized: list[Any] = []
    changed = False
    for item in events:
        if (
            isinstance(item, dict)
            and set(item) == {"event"}
            and isinstance(item.get("event"), str)
        ):
            normalized.append(item["event"])
            changed = True
        else:
            normalized.append(item)

    if not changed:
        return patch
    result = dict(patch)
    result["new_recent_events"] = normalized
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




def append_recent_events(
    existing_events: Any,
    new_events: list[str],
    *,
    limit: int = 12,
) -> list[Any]:
    """Append new scene events without rewriting prior history or keeping duplicates."""
    existing = list(existing_events) if isinstance(existing_events, list) else []
    merged = list(existing)

    def event_text(item: Any) -> str:
        if isinstance(item, str):
            return item.strip()
        if isinstance(item, dict):
            return str(item.get("event", "") or "").strip()
        return ""

    def identity(item: Any) -> str:
        return re.sub(r"\s+", " ", event_text(item)).strip().rstrip(".").casefold()

    seen = {identity(item) for item in merged if identity(item)}
    for value in new_events:
        event = str(value or "").strip()
        key = identity(event)
        if not event or not key or key in seen:
            continue
        merged.append({"event": event})
        seen.add(key)

    return merged[-max(1, int(limit)):]


def reconcile_string_items(
    existing_items: Any,
    additions: list[str],
    removals: list[str],
) -> list[Any]:
    """Reconcile cumulative string items while preserving order and explicit history."""
    existing = list(existing_items) if isinstance(existing_items, list) else []
    additions = additions if isinstance(additions, list) else []
    removals = removals if isinstance(removals, list) else []

    def identity(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().rstrip(".!?").casefold()

    removed = {
        identity(value.strip())
        for value in removals
        if isinstance(value, str) and value.strip()
    }
    merged: list[Any] = []
    seen: set[str] = set()

    for item in existing:
        if not isinstance(item, str):
            # Unknown legacy shapes are not safe to rewrite as part of a
            # string-list reconciliation.
            merged.append(item)
            continue
        text_value = item.strip()
        key = identity(text_value)
        if not key or key in removed or key in seen:
            continue
        merged.append(text_value)
        seen.add(key)

    for item in additions:
        if not isinstance(item, str) or not item.strip():
            continue
        text_value = item.strip()
        key = identity(text_value)
        if not key or key in removed or key in seen:
            continue
        merged.append(text_value)
        seen.add(key)

    return merged



def _knowledge_fact_identity(value: str) -> str:
    """Canonicalize low-risk wording variants so the same observation is not stored twice."""
    raw_text = re.sub(r"\s+", " ", value).strip().rstrip(".!?")
    lowered = raw_text.casefold()
    lowered = re.sub(r"\b(?:saw|observed|noticed|witnessed)\b", "observed", lowered)
    lowered = re.sub(r"\b(?:smiled|smiling|laughed|laughing)\b", "appeared-happy", lowered)
    lowered = re.sub(r"\b(?:there|while)\b", "", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    # Merge wording variants of the same person's demeanor before another
    # person moves, without depending on any character's name or story genre.
    if re.search(
        r"\bappeared-happy\b.*\bbefore\b.*\b\w+\b.*\bmov\w*\b",
        lowered,
    ):
        prefix = re.split(r"\bbefore\b", raw_text, maxsplit=1, flags=re.IGNORECASE)[0]
        named_words = re.findall(r"\b[A-Z][A-Za-z'-]+\b", prefix)
        excluded = {
            "saw", "observed", "noticed", "witnessed", "heard", "learned",
            "reported", "while", "before", "after", "then",
        }
        candidates = [
            word for word in named_words
            if word.casefold() not in excluded
        ]
        if candidates:
            return f"{candidates[-1].casefold()}-pre-movement-demeanor"
    lowered = re.sub(r"^(?:know|knows)\s+(?:that\s+)?", "knows ", lowered)
    return lowered


def filter_new_string_items(existing_items: Any, candidates: list[str]) -> list[str]:
    """Return only candidate strings not already present, ignoring case and terminal punctuation."""
    existing = list(existing_items) if isinstance(existing_items, list) else []

    def identity(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().rstrip(".!?").casefold()

    known = {
        identity(item)
        for item in existing
        if isinstance(item, str) and item.strip()
    }
    result: list[str] = []
    for item in candidates if isinstance(candidates, list) else []:
        if not isinstance(item, str) or not item.strip():
            continue
        value = item.strip()
        key = identity(value)
        if key and key not in known:
            result.append(value)
            known.add(key)
    return result


def _clue_identity(value: str) -> str:
    """Build a conservative identity for common paraphrases of the same clue."""
    lowered = value.casefold()
    words = set(re.findall(r"[a-z0-9]+", lowered))

    if (
        words.intersection({"scratch", "scratched", "scratches", "raked", "rake", "clawed"})
        and words.intersection({"cheek", "face"})
    ):
        details = words.intersection({"left", "right", "three", "twice"})
        if words.intersection({"blood", "bleed", "bleeding", "bled"}):
            details.add("blood")
        return "facial-scratch:" + ",".join(sorted(details))

    scent_markers = {
        "smell", "smelled", "smells", "smelling", "scent",
        "odor", "odors", "odour", "odours", "fragrance", "aroma",
    }
    if words.intersection(scent_markers):
        generic_scent_words = scent_markers | {
            "the", "a", "an", "of", "like", "with", "along", "and", "or",
            "was", "were", "is", "are", "has", "had", "from", "there",
            "additional", "another", "extra", "also", "some", "very",
        }
        descriptors = words - generic_scent_words
        if descriptors:
            return "scent:" + ",".join(sorted(descriptors))

    if words.intersection({"van", "vehicle", "car", "truck"}) and words.intersection(
        {"accelerated", "accelerate", "accelerating", "rapidly", "quickly", "speed", "sped", "acceleration"}
    ):
        details = words.intersection({"van", "vehicle", "car", "truck", "rapidly", "quickly", "speed", "accelerated", "accelerating"})
        return "vehicle-movement:" + ",".join(sorted(details))

    if "plate" in words and words.intersection({"license", "number", "registration"}):
        return "vehicle-plate"

    return re.sub(r"\s+", " ", value).strip().rstrip(".!?").casefold()


def filter_new_clue_items(existing_clues: Any, candidates: list[str]) -> list[str]:
    """Filter new-clue reports against the existing ledger and semantic duplicates."""
    known = {
        _clue_identity(item)
        for item in (existing_clues if isinstance(existing_clues, list) else [])
        if isinstance(item, str) and item.strip()
    }
    result: list[str] = []
    for item in candidates if isinstance(candidates, list) else []:
        if not isinstance(item, str) or not item.strip():
            continue
        value = item.strip()
        key = _clue_identity(value)
        if key and key not in known:
            result.append(value)
            known.add(key)
    return result



_CLUE_RESOLUTION_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "for",
    "from", "had", "has", "have", "in", "into", "is", "it", "its",
    "of", "on", "or", "that", "the", "their", "there", "this", "to",
    "was", "were", "with", "during", "after", "before", "small", "main",
    "primary", "known", "sharp", "sharply", "sudden", "suddenly",
}

_CLUE_RESOLUTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:ruled out|disproved|resolved|eliminated|debunked)\b",
        r"\bfalse alarm\b",
        r"\b(?:not|never) (?:the|a|an) (?:actual )?(?:cause|source|fault|failure|leak)\b",
        r"\b(?:was|were|is|are) not (?:the|a|an) (?:actual )?(?:cause|source|fault|failure|leak)\b",
        r"\b(?:wasn't|weren't|isn't|aren't) (?:the|a|an) (?:actual )?(?:cause|source|fault|failure|leak)\b",
        r"\bnot caused by\b",
        r"\bno evidence of\b",
        r"\bno signs? of\b",
        r"\bno (?:actual )?(?:pressure )?(?:leak|fault|failure|cause|source)\b",
        r"\bno longer (?:present|active|visible|detected|operational)\b",
        r"\b(?:returned|restored|switched|turned|went) (?:back )?(?:to )?(?:normal|baseline|steady green|green|off|silent|clear)\b",
    )
)


def filter_supported_clue_resolutions(
    existing_clues: Any,
    proposed_resolutions: Any,
    completed_text: str,
) -> list[str]:
    """Accept model-proposed clue removals only when the prose supports resolution.

    Clue resolution is deliberately conservative: the proposal must name an
    existing clue exactly, and a sentence in the completed prose must both
    refer to at least two meaningful words from that clue and contain explicit
    resolution language. A clue that simply disappears from a scene, or is
    mentioned while the story moves on, remains active for continuity.
    """
    existing = [
        item.strip()
        for item in (existing_clues if isinstance(existing_clues, list) else [])
        if isinstance(item, str) and item.strip()
    ]
    by_identity = {
        re.sub(r"\s+", " ", item).rstrip(".!?").casefold(): item
        for item in existing
    }
    if not by_identity or not str(completed_text or "").strip():
        return []

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|[\n;]+", str(completed_text or ""))
        if sentence.strip()
    ]
    proposed = proposed_resolutions if isinstance(proposed_resolutions, list) else []
    supported: list[str] = []
    seen: set[str] = set()

    for raw in proposed:
        if not isinstance(raw, str) or not raw.strip():
            continue
        key = re.sub(r"\s+", " ", raw.strip()).rstrip(".!?").casefold()
        stored_clue = by_identity.get(key)
        if not stored_clue or key in seen:
            continue

        clue_words = {
            word for word in re.findall(r"[a-z0-9]+", stored_clue.casefold())
            if len(word) > 2 and word not in _CLUE_RESOLUTION_STOPWORDS
        }
        required_overlap = 1 if len(clue_words) == 1 else 2
        resolved_in_prose = False
        for sentence in sentences:
            if not any(pattern.search(sentence) for pattern in _CLUE_RESOLUTION_PATTERNS):
                continue
            sentence_words = set(re.findall(r"[a-z0-9]+", sentence.casefold()))
            if len(clue_words.intersection(sentence_words)) >= required_overlap:
                resolved_in_prose = True
                break

        if resolved_in_prose:
            supported.append(stored_clue)
            seen.add(key)

    return supported


def recover_clues_from_knowledge(character_knowledge: Any) -> list[str]:
    """Backfill concrete investigative evidence omitted from the active-clue ledger."""
    if not isinstance(character_knowledge, dict):
        return []

    known_names = [str(name).strip() for name in character_knowledge if str(name).strip()]
    evidence_patterns = (
        r"\b(?:license plate|number plate|plate number)\b",
        r"\b(?:smell(?:ed|s|ing)?|scent|odor\w*|odour\w*|fragrance|aroma)\b",
        r"\b(?:scratch(?:ed|es|ing)?|raked?|clawed?)\b.{0,80}\b(?:cheek|face|blood|bleed)\b",
        r"\b(?:cheek|face)\b.{0,80}\b(?:scratch|rake|claw|blood|bleed)\b",
        r"\b(?:tattoo|scar|birthmark|distinctive mark|identifying mark)\b",
        r"\b(?:van|vehicle|car|truck)\b.{0,70}\b(?:accelerat\w*|rapidly|quickly|speed|direction|dark|nondescript|license|plate|damage|dent|make|model|color|colour)\b",
        r"\b(?:accelerat\w*|rapidly|quickly|speed)\b.{0,70}\b(?:van|vehicle|car|truck)\b",
    )

    recovered: list[str] = []
    for values in character_knowledge.values():
        items = values if isinstance(values, list) else [values] if isinstance(values, str) else []
        for raw in items:
            if not isinstance(raw, str) or not raw.strip():
                continue
            candidate = raw.strip()
            if is_routine_action_log_knowledge(candidate, known_names):
                continue

            for _ in range(3):
                previous = candidate
                candidate = re.sub(
                    r"^(?:now\s+)?knows?\s+(?:from\s+.+?\s+)?that\s+",
                    "",
                    candidate,
                    flags=re.IGNORECASE,
                )
                candidate = re.sub(
                    r"^(?:has\s+)?learned\s+(?:from\s+.+?\s+)?that\s+",
                    "",
                    candidate,
                    flags=re.IGNORECASE,
                )
                candidate = re.sub(
                    r"^(?:now\s+)?knows?\s+",
                    "",
                    candidate,
                    flags=re.IGNORECASE,
                )
                candidate = re.sub(
                    r"^(?:observed|saw|noticed|smelled|heard|witnessed)\s+",
                    "",
                    candidate,
                    flags=re.IGNORECASE,
                )
                if candidate == previous:
                    break

            if any(re.search(pattern, candidate, re.IGNORECASE) for pattern in evidence_patterns):
                recovered.append(candidate.strip())

    return filter_new_clue_items([], recovered)


def recover_explicit_unresolved_questions(
    current_state: dict[str, Any],
    resolved_questions: list[str] | None = None,
    completed_text: str = "",
) -> list[str]:
    """Restore concrete open questions directly stated as unknown in the before-state."""
    knowledge = current_state.get("character_knowledge", {})
    if not isinstance(knowledge, dict):
        return []

    facts: list[str] = []
    for values in knowledge.values():
        items = values if isinstance(values, list) else [values] if isinstance(values, str) else []
        facts.extend(str(item).strip() for item in items if str(item).strip())
    lowered = "\n".join(facts).casefold()
    resolved = [str(item).casefold() for item in (resolved_questions or []) if str(item).strip()]
    section = completed_text or ""

    known_names: list[str] = []
    for field in ("character_knowledge", "active_objectives", "location"):
        value = current_state.get(field)
        if isinstance(value, dict):
            known_names.extend(str(name).strip() for name in value if str(name).strip())
    if isinstance(current_state.get("scene_cast"), list):
        known_names.extend(str(name).strip() for name in current_state["scene_cast"] if str(name).strip())
    known_names = list(dict.fromkeys(known_names))

    victim = ""
    # A disappearance or unknown identity alone is not proof of abduction.
    # Scope the event signal to a fact that actually describes taking/capturing
    # someone, so an unrelated missing person is not mistaken for the target.
    abduction_evidence_pattern = re.compile(
        r"\b(?:abduction|abducted|abducting|kidnapped|kidnapping|captiv\w*)\b"
        r"|\b(?:taken|carried off)\b.{0,80}\b(?:by|from)\b",
        re.IGNORECASE,
    )
    abduction_established = any(
        abduction_evidence_pattern.search(fact) for fact in facts
    )
    action_pattern = re.compile(
        r"\b(?:abducted|kidnapped|captured|taken|missing|gone)\b",
        re.IGNORECASE,
    )
    for fact in facts:
        if not abduction_evidence_pattern.search(fact):
            continue
        for action in action_pattern.finditer(fact):
            prefix = fact[:action.start()]
            closest = None
            closest_position = -1
            for name in known_names:
                matches = list(re.finditer(r"\b" + re.escape(name) + r"\b", prefix, re.IGNORECASE))
                if matches and matches[-1].start() > closest_position:
                    closest = name
                    closest_position = matches[-1].start()
            if closest:
                victim = closest
                break
        if victim:
            break

    def removal_covers(topic: str) -> bool:
        for question in resolved:
            if topic == "who" and re.search(r"\b(?:who|identity|name|kidnapper|abductor|suspect)\b", question):
                return True
            if topic == "where" and re.search(r"\b(?:where|destination|location|taken|held)\b", question):
                return True
            if topic == "plate" and re.search(r"\b(?:license|number) plate\b", question):
                return True
        return False

    def identity_answered() -> bool:
        return bool(re.search(
            r"\b(?:kidnapper|abductor|suspect|unidentified man)\s+(?:is|was)\s+(?:identified\s+as\s+)?[A-Z][A-Za-z'-]+\b"
            r"|\b(?:identified|recognized)\s+(?:the\s+)?(?:kidnapper|abductor|man|suspect)\s+as\s+[A-Z][A-Za-z'-]+\b"
            r"|\b(?:name|identity)\s+of\s+(?:the\s+)?(?:kidnapper|abductor|suspect)\s+(?:is|was)\s+[A-Z][A-Za-z'-]+\b",
            section,
        ))

    def destination_answered() -> bool:
        target_pattern = rf"(?:{re.escape(victim)}|her|him|them)" if victim else r"(?:her|him|them)"
        return bool(re.search(
            r"\b(?:took|brought|drove|transported|moved)\s+" + target_pattern +
            r"\s+to\s+(?:the\s+)?[A-Za-z][A-Za-z0-9' -]{1,60}",
            section,
        ))

    def plate_answered() -> bool:
        return bool(re.search(
            r"\b(?:license|number) plate\b.{0,30}\b(?:was|read|showed|displayed|said)\s+[A-Z0-9-]{3,}\b"
            r"|\bplate number\s+[A-Z0-9-]{3,}\b",
            section,
            re.IGNORECASE,
        ))

    questions: list[str] = []
    unknown_identity = bool(re.search(
        r"\b(?:does not know|doesn't know|do not know|don't know)\b.{0,90}\b(?:who|identity|name)\b",
        lowered,
    ))
    if (
        abduction_established
        and unknown_identity
        and not removal_covers("who")
        and not identity_answered()
    ):
        questions.append(
            f"Who abducted {victim}?" if victim else "Who was responsible for the abduction?"
        )

    unknown_destination = bool(re.search(
        r"\b(?:does not know|doesn't know|do not know|don't know)\b.{0,100}\b(?:where|destination|location)\b",
        lowered,
    ))
    if (
        abduction_established
        and unknown_destination
        and not removal_covers("where")
        and not destination_answered()
    ):
        questions.append(
            f"Where was {victim} taken?"
            if victim
            else "Where was the abducted person taken?"
        )

    no_plate = bool(re.search(
        r"\b(?:no|without|lacks?|lack of)\b.{0,50}\b(?:concrete\s+)?(?:license|number) plate\b",
        lowered,
    ))
    vehicle_present = bool(
        re.search(r"\b(?:vehicle|car|van|truck|bus|motorcycle|suv|sedan)\b", lowered)
    )
    if vehicle_present and no_plate and not removal_covers("plate") and not plate_answered():
        questions.append("What was the vehicle's license plate?")

    return filter_new_string_items(current_state.get("unresolved_questions", []), questions)


def clean_knowledge_action_logs(
    base_knowledge: Any,
    proposed_knowledge: Any,
    character_names: list[str] | None = None,
) -> dict[str, list[Any]]:
    """Remove routine action logs deterministically, even if the LLM audit fails."""
    base = base_knowledge if isinstance(base_knowledge, dict) else {}
    proposed = proposed_knowledge if isinstance(proposed_knowledge, dict) else {}
    all_names = list(dict.fromkeys(
        [str(name).strip() for name in [*base.keys(), *proposed.keys(), *(character_names or [])] if str(name).strip()]
    ))

    def as_list(value: Any) -> list[Any]:
        if isinstance(value, list):
            return list(value)
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def identity(value: str) -> str:
        return _knowledge_fact_identity(value)

    changed: dict[str, list[Any]] = {}
    for name in all_names:
        original = as_list(base.get(name, []))
        candidate = as_list(proposed.get(name, original))
        cleaned: list[Any] = []
        seen: set[str] = set()
        for item in candidate:
            if not isinstance(item, str):
                cleaned.append(item)
                continue
            value = item.strip()
            if not value or is_routine_action_log_knowledge(value, all_names):
                continue
            key = identity(value)
            if key not in seen:
                cleaned.append(value)
                seen.add(key)
        if cleaned != original:
            changed[name] = cleaned
    return changed


def build_state_analysis_context(
    current_state: dict[str, Any],
    scene_characters: list[str] | None = None,
) -> dict[str, Any]:
    """Build a compact baseline for state transitions; the full state remains app-owned."""
    fields = (
        "chapter", "scene", "scene_cast", "current_situation", "time", "time_of_day",
        "location", "physical_state", "active_objectives", "active_clues",
        "unresolved_questions", "recent_events",
    )
    context: dict[str, Any] = {}
    supplied = scene_characters or current_state.get("scene_cast", [])
    names = {str(name).casefold() for name in supplied if str(name).strip()}
    names.update(str(name).casefold() for name in current_state.get("scene_cast", []) if str(name).strip())
    for field in fields:
        if field not in current_state:
            continue
        value = current_state[field]
        if field in {"location", "physical_state", "active_objectives"} and isinstance(value, dict):
            filtered = {}
            for name, item in value.items():
                if field == "location" and str(name).casefold() == "primary":
                    filtered[name] = item
                elif str(name).casefold() in names:
                    filtered[name] = item
            context[field] = filtered
        elif field == "recent_events" and isinstance(value, list):
            context[field] = value[-8:]
        else:
            context[field] = value
    return context


def _knowledge_relevance_tokens(text: str) -> set[str]:
    stop_words = {
        "about", "after", "again", "against", "also", "and", "are", "around", "because",
        "been", "before", "being", "between", "but", "came", "could", "did", "does",
        "during", "each", "from", "get", "got", "had", "has", "have", "her", "hers",
        "him", "his", "into", "its", "just", "know", "knows", "learned", "like", "made",
        "make", "more", "most", "near", "not", "now", "onto", "our", "out", "over",
        "said", "same", "she", "should", "some", "such", "than", "that", "the", "their",
        "them", "then", "there", "these", "they", "this", "those", "through", "told",
        "under", "very", "was", "were", "what", "when", "where", "which", "while", "who",
        "will", "with", "would", "you", "your",
    }
    return {
        token for token in re.findall(r"[a-z0-9]+", str(text).casefold())
        if len(token) >= 3 and token not in stop_words
    }


def select_relevant_knowledge_context(
    knowledge_by_character: dict[str, list[str]],
    story_text: str,
    *,
    max_items_per_character: int = 8,
    max_total_items: int = 36,
) -> dict[str, list[str]]:
    """Select bounded prior context while retaining the complete knowledge ledger in app state."""
    story_tokens = _knowledge_relevance_tokens(story_text)
    ranked: list[tuple[int, int, str, str]] = []
    for character, values in knowledge_by_character.items():
        if not isinstance(values, list):
            continue
        for index, raw in enumerate(values):
            value = str(raw).strip()
            if not value:
                continue
            tokens = _knowledge_relevance_tokens(value)
            overlap = len(tokens.intersection(story_tokens))
            recency_bonus = 2 if index >= max(0, len(values) - 3) else 0
            temporary_bonus = 3 if re.search(
                r"\b(?:asleep|sleeping|wearing|holding|carrying|sitting|standing|lying|inside the van|in the bathroom|in the bedroom|at the kitchen table)\b",
                value,
                re.IGNORECASE,
            ) else 0
            ranked.append((overlap + recency_bonus + temporary_bonus, index, str(character), value))

    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    selected: dict[str, list[tuple[int, str]]] = {}
    for _score, index, character, value in ranked:
        if len(selected.get(character, [])) >= max_items_per_character:
            continue
        if sum(len(items) for items in selected.values()) >= max_total_items:
            break
        selected.setdefault(character, []).append((index, value))
    return {
        character: [value for _index, value in sorted(values, key=lambda item: item[0])]
        for character, values in selected.items()
    }


def _display_diff_value(value: Any, max_chars: int = 360) -> str:
    """Format one state value compactly for human change review."""
    text_value = value.strip() if isinstance(value, str) else json.dumps(
        value, ensure_ascii=False, sort_keys=True
    )
    text_value = re.sub(r"\s+", " ", text_value).strip()
    if len(text_value) > max_chars:
        text_value = text_value[:max_chars - 1].rstrip() + "…"
    return text_value


def build_state_change_summary(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    max_changes: int = 80,
) -> str:
    """Report only changed state paths; unchanged canon is deliberately hidden."""
    categories = {
        "Situation and time": {"current_situation", "time", "time_of_day"},
        "Locations and physical state": {"location", "physical_state"},
        "Objectives": {"active_objectives"},
        "Character knowledge": {"character_knowledge"},
        "Investigative leads": {"active_clues", "new_clues", "unresolved_questions"},
        "Recent events": {"recent_events"},
    }
    order = list(categories) + ["Other state changes"]
    changes: dict[str, list[str]] = {name: [] for name in order}
    ignored_managed = {"chapter", "scene", "status", "scene_completed", "chapter_completed"}
    found = 0

    def category(path: str) -> str:
        root = path.split(".", 1)[0].split("[", 1)[0]
        return next((key for key, fields in categories.items() if root in fields), "Other state changes")

    def identity(value: Any) -> str:
        if isinstance(value, dict) and "event" in value:
            value = value.get("event", "")
        if isinstance(value, str):
            return re.sub(r"\s+", " ", value).strip().rstrip(".!?").casefold()
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def add(path: str, kind: str, value: Any = None, old: Any = None) -> None:
        nonlocal found
        if found >= max_changes:
            return
        line = f"{kind} {path}"
        if kind == "Changed":
            line += f"\n    Before: {_display_diff_value(old)}\n    After:  {_display_diff_value(value)}"
        elif kind in {"Added", "Removed"}:
            line += f": {_display_diff_value(value)}"
        changes[category(path)].append(line)
        found += 1

    def compare(path: str, old: Any, new: Any, old_exists: bool = True, new_exists: bool = True) -> None:
        if found >= max_changes or (old_exists and new_exists and old == new):
            return
        if not old_exists:
            if isinstance(new, dict) and new:
                for key, value in new.items():
                    compare(f"{path}.{key}" if path else str(key), None, value, False, True)
            elif isinstance(new, list):
                for value in new:
                    add(path, "Added", value)
            else:
                add(path, "Added", new)
            return
        if not new_exists:
            if isinstance(old, dict) and old:
                for key, value in old.items():
                    compare(f"{path}.{key}" if path else str(key), value, None, True, False)
            elif isinstance(old, list):
                for value in old:
                    add(path, "Removed", value)
            else:
                add(path, "Removed", old)
            return
        if isinstance(old, dict) and isinstance(new, dict):
            for key in dict.fromkeys([*old.keys(), *new.keys()]):
                compare(
                    f"{path}.{key}" if path else str(key),
                    old.get(key), new.get(key), key in old, key in new,
                )
            return
        if isinstance(old, list) and isinstance(new, list):
            old_map: dict[str, Any] = {}
            new_map: dict[str, Any] = {}
            for value in old:
                old_map.setdefault(identity(value), value)
            for value in new:
                new_map.setdefault(identity(value), value)
            removed = [value for key, value in old_map.items() if key not in new_map]
            added = [value for key, value in new_map.items() if key not in old_map]
            if not removed and not added and old != new:
                add(path, "Changed", new, old)
            else:
                for value in removed:
                    add(path, "Removed", value)
                for value in added:
                    add(path, "Added", value)
            return
        add(path, "Changed", new, old)

    all_keys = [key for key in dict.fromkeys([*before.keys(), *after.keys()]) if key not in ignored_managed]
    for key in all_keys:
        compare(str(key), before.get(key), after.get(key), key in before, key in after)
        if found >= max_changes:
            break
    lines = [
        "PROPOSED ENDING-STATE CHANGES",
        "Only differences are shown. Fields not listed remain unchanged.",
        "",
    ]
    wrote = False
    for group in order:
        if changes[group]:
            wrote = True
            lines.append(group.upper())
            lines.extend(f"  {item}" for item in changes[group])
            lines.append("")
    if not wrote:
        lines.append("No state changes detected. Check whether that is expected before applying.")
    if found >= max_changes:
        lines.append(f"Output capped at {max_changes} changes. Inspect Full State JSON for more.")
    lines.append("Full State JSON is available in the advanced tab if a correction is needed.")
    return "\n".join(lines).strip()


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
    "active_clues",
    "new_clues",
    "unresolved_questions",
}


END_STATE_PROPOSAL_FIELDS = {
    "current_situation",
    "location",
    "physical_state",
    "time_of_day",
    "active_objectives",
    "new_clues",
    "resolved_clues",
    "new_unresolved_questions",
    "resolved_questions",
    "new_recent_events",
}


def validate_state_proposal(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Validate ending-state changes and model-only additions to recent events."""
    if not isinstance(patch, dict):
        raise ValueError("The proposed state update must be a JSON object.")

    unsupported = sorted(set(patch) - END_STATE_PROPOSAL_FIELDS)
    if unsupported:
        raise ValueError(
            "Invalid continuity proposal: unsupported transition field(s): "
            + ", ".join(unsupported)
            + ". Return only current_situation, location, physical_state, time_of_day, active_objectives, new_clues, resolved_clues, new_unresolved_questions, resolved_questions, and new_recent_events."
        )

    situation = patch.get("current_situation")
    if not isinstance(situation, str) or not situation.strip():
        raise ValueError(
            "Invalid state update: 'current_situation' is required and must describe the actual end of the scene."
        )

    objectives = patch.get("active_objectives")
    if objectives is not None:
        if not isinstance(objectives, dict):
            raise ValueError("Invalid state update: 'active_objectives' must be an object or null for deletion.")
        for character, objective in objectives.items():
            if objective is not None and (not isinstance(objective, str) or not objective.strip()):
                raise ValueError(
                    f"Invalid state update at 'active_objectives.{character}': objectives must be non-empty text or null to remove a stale objective."
                )

    for field in ("new_clues", "resolved_clues", "new_unresolved_questions", "resolved_questions"):
        if field not in patch:
            continue
        values = patch[field]
        if not isinstance(values, list) or any(
            not isinstance(item, str) or not item.strip() for item in values
        ):
            raise ValueError(
                f"Invalid state update: '{field}' must be a list of non-empty strings (use [] when empty, not null)."
            )

    new_events = patch.get("new_recent_events")
    if "new_recent_events" in patch and (
        not isinstance(new_events, list) or any(
            not isinstance(event, str) or not event.strip()
            for event in new_events
        )
    ):
        raise ValueError(
            "Invalid state update: 'new_recent_events' must be a list of non-empty event strings (use [] when empty, not null)."
        )

    # new_recent_events is model-only and never persisted as a state key.
    persisted_patch = dict(patch)
    for transient_field in (
        "new_recent_events",
        "resolved_clues",
        "new_unresolved_questions",
        "resolved_questions",
    ):
        persisted_patch.pop(transient_field, None)
    validate_state_patch(base, persisted_patch)
    return patch

APP_MANAGED_STATE_FIELDS = {
    "chapter",
    "scene",
    "status",
    "scene_completed",
    "chapter_completed",
    "scene_cast",
    "story_format_version",
}


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

    app_managed_fields = APP_MANAGED_STATE_FIELDS
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
            if value is None:
                continue  # Explicit deletion of a stale location entry.
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
        if knowledge is not None and not isinstance(knowledge, dict):
            raise ValueError("Invalid state update: 'character_knowledge' must be an object or null for deletion.")
        if isinstance(knowledge, dict):
            for character, facts in knowledge.items():
                if facts is None:
                    continue  # Explicitly remove an obsolete character entry.
                if not isinstance(facts, list) or any(not isinstance(fact, str) for fact in facts):
                    raise ValueError(
                        f"Invalid state update at 'character_knowledge.{character}': "
                        "each character's knowledge must be a list of text facts or null for deletion."
                    )

    if "physical_state" in patch and not isinstance(patch["physical_state"], dict):
        raise ValueError("Invalid state update: 'physical_state' must be an object.")

    if "active_objectives" in patch and patch["active_objectives"] is not None:
        objectives = patch["active_objectives"]
        if not isinstance(objectives, dict):
            raise ValueError("Invalid state update: 'active_objectives' must be an object or null for deletion.")
        for character, objective in objectives.items():
            if objective is not None and (not isinstance(objective, str) or not objective.strip()):
                raise ValueError(
                    f"Invalid state update at 'active_objectives.{character}': objectives must be non-empty text or null to delete an obsolete objective."
                )

    if "recent_events" in patch:
        events = patch["recent_events"]
        if not isinstance(events, list):
            raise ValueError("Invalid state update: 'recent_events' must be a list.")
        for index, event in enumerate(events):
            if isinstance(event, str) and event.strip():
                continue
            if isinstance(event, dict) and isinstance(event.get("event"), str) and event["event"].strip():
                continue
            raise ValueError(
                f"Invalid state update at 'recent_events[{index}]': each event must be text or an object with non-empty event text."
            )

    for field in ("active_clues", "new_clues", "unresolved_questions"):
        if field in patch and patch[field] is not None:
            values = patch[field]
            if not isinstance(values, list) or any(
                not isinstance(item, str) or not item.strip() for item in values
            ):
                raise ValueError(
                    f"Invalid state update: '{field}' must be a list of non-empty strings or null for deletion."
                )

    return patch


def reviewed_state_preview_to_patch(
    expected_state: dict[str, Any],
    reviewed_state: dict[str, Any],
) -> dict[str, Any]:
    """Convert edits to the full ending-state preview into a safe partial patch.

    StoryBuilder displays the model patch merged with the current state. Authors
    may correct values in that full JSON before applying it. This helper returns
    only the differences from the displayed baseline, so the normal patch merge
    and application-owned scene navigation remain in force.
    """
    if not isinstance(expected_state, dict):
        raise ValueError("The expected ending-state preview must be a JSON object.")
    if not isinstance(reviewed_state, dict):
        raise ValueError("The reviewed ending-state preview must be a JSON object.")

    for field in APP_MANAGED_STATE_FIELDS:
        expected_has_field = field in expected_state
        reviewed_has_field = field in reviewed_state
        if expected_has_field != reviewed_has_field or (
            expected_has_field and expected_state[field] != reviewed_state[field]
        ):
            raise ValueError(
                f"'{field}' is managed by StoryBuilder and cannot be edited in the "
                "ending-state preview. Restore its original value and try again."
            )

    unchanged = object()

    def diff(before: Any, after: Any, path: str) -> Any:
        if isinstance(before, dict) and isinstance(after, dict):
            changes: dict[str, Any] = {}
            for key in before:
                if key not in after:
                    # JSON merge-patch uses null to explicitly delete nested keys.
                    # This lets authors remove stale state from the full preview.
                    changes[key] = None
            for key, after_value in after.items():
                field_path = f"{path}.{key}" if path else key
                if key not in before:
                    changes[key] = after_value
                    continue
                change = diff(before[key], after_value, field_path)
                if change is unchanged:
                    continue
                if isinstance(change, dict) and not change:
                    continue
                changes[key] = change
            return changes

        if before == after:
            return unchanged
        return after

    patch = diff(expected_state, reviewed_state, "")
    if patch is unchanged:
        patch = {}
    return validate_state_patch(expected_state, patch)


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

    location_patch = patch.get("location") if isinstance(patch, dict) else None

    # Remove legacy top-level duplicates for both retained and explicitly
    # deleted nested names, but retain unrelated top-level state.
    duplicate_names = set(location)
    if isinstance(location_patch, dict):
        duplicate_names.update(location_patch)
    for name in duplicate_names:
        if name == "primary":
            continue
        if name in result and isinstance(result[name], str):
            result.pop(name, None)
    if isinstance(result.get("primary"), str):
        result.pop("primary", None)
    physical_state = result.get("physical_state")
    if not isinstance(location_patch, dict) or not isinstance(physical_state, dict):
        return result

    updated_physical_state = dict(physical_state)
    changed = False
    for name, final_location in location_patch.items():
        if name == "primary":
            continue
        character_state = physical_state.get(name)
        if final_location is None:
            # Removing a location entry must not leave a contradictory nested
            # physical_state.location behind.
            if not isinstance(character_state, dict) or "location" not in character_state:
                continue
            updated_character_state = dict(character_state)
            updated_character_state.pop("location", None)
            if updated_character_state:
                updated_physical_state[name] = updated_character_state
            else:
                updated_physical_state.pop(name, None)
            changed = True
            continue
        if not isinstance(final_location, str) or not isinstance(character_state, dict):
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
        scene_characters: list[str] | None = None,
    ) -> dict[str, Any]:
        """Audit the opening cast plus characters named as possible participants."""
        supplied = scene_characters if isinstance(scene_characters, list) else []
        if not supplied:
            supplied = current_state.get("scene_cast", [])
        cast = []
        seen_names = set()
        for raw_name in [*current_state.get("scene_cast", []), *supplied]:
            name = str(raw_name).strip()
            key = name.casefold()
            if name and key not in seen_names:
                cast.append(name)
                seen_names.add(key)
        if not cast:
            return {}

        existing = current_state.get("character_knowledge", {})
        all_knowledge_before = {}
        if isinstance(existing, dict):
            for name in cast:
                values = existing.get(name)
                if values is None:
                    for key, candidate in existing.items():
                        if str(key).casefold() == name.casefold():
                            values = candidate
                            break
                if isinstance(values, list):
                    all_knowledge_before[name] = [
                        str(item).strip() for item in values if str(item).strip()
                    ]
                elif isinstance(values, str) and values.strip():
                    all_knowledge_before[name] = [values.strip()]
                else:
                    all_knowledge_before[name] = []
        knowledge_before = select_relevant_knowledge_context(
            all_knowledge_before, story_text, max_items_per_character=8, max_total_items=36
        )

        audit_prompt = (
            "Return only knowledge deltas for the supplied section. The application retains all existing "
            "facts automatically, so do not re-emit the cumulative list. Return only new facts for affected "
            "characters and exact supplied prior facts that the prose directly supersedes. This is not a "
            "request to rebuild the character profiles.\n\n"
            "SCENE CAST:\n"
            + json.dumps(cast, indent=2, ensure_ascii=False)
            + "\n\nSELECTED EXISTING KNOWLEDGE CONTEXT (THE APP KEEPS THE FULL LEDGER):\n"
            + json.dumps(knowledge_before, indent=2, ensure_ascii=False)
            + "\n\nSTARTING SITUATION AND LOCATIONS (CONTEXT ONLY):\n"
            + json.dumps(
                {
                    "current_situation": current_state.get("current_situation", ""),
                    "location": build_state_analysis_context(current_state, cast).get("location", {}),
                    "physical_state": build_state_analysis_context(current_state, cast).get("physical_state", {}),
                    "scene_cast_at_opening": current_state.get("scene_cast", []),
                },
                indent=2,
                ensure_ascii=False,
            )
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
        scene_characters: list[str] | None = None,
    ) -> None:
        """Merge audited knowledge while guarding against omitted prior facts."""
        supplied = scene_characters if isinstance(scene_characters, list) else []
        if not supplied:
            supplied = current_state.get("scene_cast", [])
        scene_character_names = [
            str(name).strip() for name in supplied if str(name).strip()
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
            seen_identities: set[str] = set()
            for value in values:
                text_value = str(value).strip()
                if not text_value:
                    continue
                if is_routine_action_log_knowledge(text_value, scene_character_names):
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
                identity = _knowledge_fact_identity(text_value)
                if identity not in seen_identities:
                    cleaned.append(text_value)
                    seen_identities.add(identity)
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
        audited_names = list(dict.fromkeys(
            [
                name for name in delta
                if name != "_superseded_facts"
            ] + [
                str(name) for name in superseded_payload
            ]
        ))
        for name in audited_names:
            values = delta.get(name, [])
            prior_values = base_knowledge.get(name, [])
            if isinstance(prior_values, str):
                prior_values = [prior_values]
            if not isinstance(prior_values, list):
                prior_values = []

            superseded_values = superseded_payload.get(name, [])
            if not isinstance(superseded_values, list):
                superseded_values = []
            superseded_keys = {
                re.sub(r"\s+", " ", str(value).strip()).casefold()
                for value in superseded_values
                if str(value).strip()
            }

            def is_superseded(value: Any) -> bool:
                text_value = re.sub(r"\s+", " ", str(value).strip())
                key = text_value.casefold()
                if not key or key not in superseded_keys:
                    return False
                # Durable observations and discoveries remain in memory even if
                # interpretations change. Permit supersession only for temporary
                # physical statuses or an explicitly obsolete "believes unknown"
                # style status that the audit specifically identified.
                temporary_physical_status = re.match(
                    r"^(?:(?:currently|now)\s+)?(?:is|was|are|were)\s+"
                    r"(?:wearing|asleep|sleeping|sitting|standing|lying|seated|positioned|located)\b",
                    text_value,
                    re.IGNORECASE,
                )
                replaced_unknown_belief = re.match(
                    r"^(?:believes?|thinks?|suspects?)\b.*\b"
                    r"(?:unknown|unidentified|not yet known|not established)\b",
                    text_value,
                    re.IGNORECASE,
                )
                return bool(temporary_physical_status or replaced_unknown_belief)

            proposed_values = values if isinstance(values, list) else []
            prior_values = [value for value in prior_values if not is_superseded(value)]
            proposed_values = [value for value in proposed_values if not is_superseded(value)]
            combined_values = [*prior_values, *proposed_values]
            cleaned = normalize_knowledge(combined_values, name)
            combined[name] = cleaned

        # Preserve any useful model-derived knowledge for scene characters only
        # when the focused audit did not return that character.
        for name, values in proposed.items():
            if name in audited_names:
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
        scene_characters: list[str] | None = None,
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
        # scene_end_guidance remains a compatibility parameter only. The accepted
        # prose and the before-state are the evidence used for state analysis.
        state_context = build_state_analysis_context(current_state, scene_characters)
        prompt_parts = [
            "COMPACT CURRENT-STATE CONTEXT BEFORE THIS SECTION (THE APPLICATION RETAINS THE FULL STATE):\n",
            json.dumps(state_context, indent=2, ensure_ascii=False),
        ]

        prompt_parts.extend([
            "\n\nCOMPLETED STORY SECTION:\n",
            completed_text,
        ])


        prompt_parts.extend([
            "\n\nENDING-STATE EMPHASIS:\n",
            "The full accepted scene text appears above exactly once. Do not rely on a repeated excerpt; inspect the final actions and paragraph in the original scene. ",
            "Determine the smallest state update needed AFTER this completed section. "
            "Read the entire section, but give special weight to the final actions and final paragraph. "
            "The compact current-state context describes what was true BEFORE the section and must not override what "
            "the completed prose establishes at the end. For each character whose final location, physical position, contact, or immediate "
            "situation changed, include the changed value under physical_state and/or location as appropriate. Update current_situation to describe "
            "the actual immediate situation at the absolute end of the completed section, not the starting "
            "situation and not what should happen in the next scene. Keep it concise and factual. "
            "Do not copy planning instructions or future events into it. "
            "Always return non-empty current_situation. Return only changed location, physical_state, time_of_day, and active_objectives fields, plus new_clues (use [] if none), resolved_clues, new_unresolved_questions, resolved_questions, and new_recent_events (use [] if none). "
            "Each new_recent_events item must be a plain JSON string, not an object with an event key. Do not return character_knowledge, active_clues, unresolved_questions directly, recent_events directly, event/event-log fields, scene flags, continuity requirements, or other metadata. For new_clues, include specific sensory/physical/vehicle evidence, preserve witness qualifiers, and never invent an extra scent or split one observation into additional clues. Do not repeat an existing active clue as new. Keep exact first-time nicknames and whether they are accepted or rejected as distinct new_recent_events, not just a generic hug. Include physical_state.clothing when the prose explicitly establishes a continuity-relevant outfit change. "
            "Use null to remove stale object keys as described by the system rules. Update only objectives changed by the completed prose and keep any group commitment broad when no assignments have been made. The compact context omits full character knowledge and editorial reminders; do not treat omitted facts as false."
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

        # Local models occasionally misnest a character's ending physical state
        # at the proposal's top level. Normalize only recognizable objects for
        # known characters; all other unsupported fields remain validation errors.
        parsed_proposal_for_error: dict[str, Any] | None = None
        for attempt in range(2):
            parsed_proposal_for_error = None
            try:
                parsed_candidate = extract_json_object(
                    output,
                    required_keys={"current_situation"},
                )
                # Preserve the exact parsed shape before normalizers change it so
                # a failed proposal can be diagnosed from the error message.
                parsed_proposal_for_error = json.loads(
                    json.dumps(parsed_candidate, ensure_ascii=False)
                )
                candidate = dict(parsed_candidate)
                # Knowledge is produced by a dedicated audit below. Never let
                # the general state model turn scene actions into "knowledge"
                # or replace cumulative facts with an event log.
                candidate.pop("character_knowledge", None)
                if "location" in candidate and not isinstance(candidate["location"], dict):
                    raise ValueError("Invalid state update: 'location' must be an object.")
                candidate = normalize_location_patch(current_state, candidate)
                candidate = normalize_physical_state_patch(
                    current_state,
                    candidate,
                    scene_characters=scene_characters,
                )
                candidate = normalize_recent_event_entries(candidate)
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
                            recovered = extract_json_object(
                                output,
                                required_keys={"current_situation"},
                            )
                            # Character knowledge is always handled by the
                            # dedicated knowledge audit, never salvaged here.
                            recovered.pop("character_knowledge", None)
                            # Normalize legacy top-level location keys FIRST.
                            # Otherwise a malformed top-level character value can be
                            # moved under location after that field was cleaned.
                            recovered = normalize_location_patch(
                                current_state,
                                recovered,
                            )
                            recovered = normalize_physical_state_patch(
                                current_state,
                                recovered,
                                scene_characters=scene_characters,
                            )
                            raw_location = recovered.get("location")
                            if isinstance(raw_location, dict):
                                clean_location = {
                                    name: value
                                    for name, value in raw_location.items()
                                    if isinstance(value, str) or value is None
                                }
                                if clean_location:
                                    recovered["location"] = clean_location
                                else:
                                    recovered.pop("location", None)
                            else:
                                recovered.pop("location", None)

                            recovered = normalize_recent_event_entries(recovered)
                            validate_state_proposal(current_state, recovered)
                            patch = recovered
                            break
                        except (TypeError, ValueError):
                            # Do not salvage if any other part of the proposal
                            # remains malformed. The ordinary error below retains
                            # the full validator detail for diagnosis.
                            pass

                    excerpt = (output or "")[-1200:]
                    if parsed_proposal_for_error is not None:
                        parsed_detail = json.dumps(
                            parsed_proposal_for_error,
                            indent=2,
                            ensure_ascii=False,
                        )
                    else:
                        parsed_detail = "(No complete state-proposal JSON object containing current_situation could be extracted from the model response.)"
                    raise ValueError(
                        "The continuity model returned an invalid state update even after one "
                        "automatic correction attempt. No state changes were applied.\n\n"
                        f"Validation detail: {exc}\n\n"
                        "Parsed proposal before normalization (exact JSON shape):\n"
                        f"{parsed_detail}\n\n"
                        f"Last model response excerpt (last 1200 characters):\n{excerpt}"
                    ) from exc

                repair_prompt = (
                    prompt
                    + "\n\nAUTOMATIC CORRECTION REQUIRED: your previous JSON proposal was "
                    "rejected by the application's state validator. Correct the same proposal "
                    "using only facts supported by the completed prose. Do not invent new events.\n"
                    + f"VALIDATION ERROR: {exc}\n"
                    + "SCHEMA REMINDER: return ONLY current_situation, location, physical_state, time_of_day, active_objectives (partial object; use null to delete stale objectives), new_clues, resolved_clues, new_unresolved_questions, resolved_questions, and new_recent_events. Use [] for empty list outputs. Each new_recent_events item must be a plain JSON string, not an object with an event key. Do not return event, events, recent_events, active_clues, unresolved_questions, character_knowledge, or unrelated metadata. JSON null deletes an explicitly stale object key; never use it for information that is merely unmentioned. "
                    "Always include a non-empty current_situation describing what is true at the absolute end of the completed prose, not an earlier action. "
                    "If supplied, location must be an object with plain-text descriptions or null deletion markers; physical_state must be an object. "
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

        # Consume the transient event-addition field before exposing the patch
        # to preview/apply. Preserve previous history and append only new events.
        new_recent_events = patch.pop("new_recent_events", [])
        new_clues = patch.pop("new_clues", [])
        resolved_clues = patch.pop("resolved_clues", [])
        new_questions = patch.pop("new_unresolved_questions", [])
        resolved_questions = patch.pop("resolved_questions", [])

        # Recover concrete evidence already present in cumulative knowledge but missed
        # by an earlier state pass. Such backfilled evidence is active, but is not
        # incorrectly labeled as newly introduced in this scene.
        previous_clues = current_state.get("active_clues", [])
        resolved_clues = filter_supported_clue_resolutions(
            previous_clues, resolved_clues, completed_text
        )
        recovered_clues = recover_clues_from_knowledge(
            current_state.get("character_knowledge", {})
        )
        known_before_scene = filter_new_clue_items(previous_clues, recovered_clues)
        reportable_new_clues = filter_new_clue_items(
            [*previous_clues, *recovered_clues],
            new_clues,
        )
        reportable_new_clues = filter_new_clue_items(resolved_clues, reportable_new_clues)

        # new_clues is a per-scene report. Replace the previous report even
        # when this scene adds none, so old additions do not linger as "new".
        if "new_clues" in current_state or reportable_new_clues or recovered_clues:
            patch["new_clues"] = reportable_new_clues

        clue_additions = [*known_before_scene, *new_clues]
        if "active_clues" in current_state or clue_additions or resolved_clues:
            updated_clues = reconcile_string_items(previous_clues, clue_additions, resolved_clues)
            updated_clues = filter_new_clue_items(resolved_clues, updated_clues)
            if updated_clues != previous_clues:
                patch["active_clues"] = updated_clues

        previous_questions = current_state.get("unresolved_questions", [])
        recovered_questions = recover_explicit_unresolved_questions(
            current_state,
            resolved_questions=resolved_questions,
            completed_text=completed_text,
        )
        question_additions = [*new_questions, *recovered_questions]
        if "unresolved_questions" in current_state or question_additions or resolved_questions:
            updated_questions = reconcile_string_items(
                previous_questions,
                question_additions,
                resolved_questions,
            )
            if updated_questions != previous_questions:
                patch["unresolved_questions"] = updated_questions

        # Models sometimes repeat unchanged state. Normalize that away so a
        # proposal contains only actual changes, while retaining null tombstones
        # for stale nested keys.
        patch = remove_unchanged(current_state, patch)
        if new_recent_events:
            previous_events = current_state.get("recent_events", [])
            updated_events = append_recent_events(previous_events, new_recent_events)
            if updated_events != previous_events:
                patch["recent_events"] = updated_events

        # Knowledge changes are audited separately because a broad continuity
        # pass can miss facts learned through dialogue when physical state does
        # not change. The focused pass returns only new facts and never replaces
        # the existing knowledge list.
        try:
            knowledge_delta = StateManager._propose_knowledge_delta(
                model,
                current_state,
                completed_text,
                scene_characters=scene_characters,
            )
            if knowledge_delta:
                StateManager._merge_knowledge_delta(
                    current_state,
                    patch,
                    knowledge_delta,
                    scene_characters=scene_characters,
                )
        except (ValueError, RuntimeError):
            # The main state proposal remains usable if the optional knowledge
            # audit cannot be parsed or completed. Do not fabricate knowledge.
            pass

        # Routine scene logistics do not belong in cumulative knowledge. Run this
        # deterministic cleanup regardless of whether the optional knowledge model
        # returned usable JSON; preserve consequential facts and witness evidence.
        cleaned_knowledge = clean_knowledge_action_logs(
            current_state.get("character_knowledge", {}),
            patch.get("character_knowledge", {}),
            character_names=scene_characters,
        )
        if cleaned_knowledge:
            knowledge_patch = patch.get("character_knowledge", {})
            if not isinstance(knowledge_patch, dict):
                knowledge_patch = {}
            knowledge_patch.update(cleaned_knowledge)
            patch["character_knowledge"] = knowledge_patch

        # End-state hints are included in the prompt as planning context only.
        # Never merge a planned state directly over facts inferred from accepted
        # prose: a planned event may have been omitted, changed, or not actually
        # occurred in the scene that the author accepted.
        StateManager.validate_patch(current_state, patch)
        return patch
