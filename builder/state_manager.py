from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from builder.workspace import LLAMA as DEFAULT_LLAMA

STATE_SYSTEM_PROMPT = """You are the continuity manager for an ongoing fictional story.

Return ONLY one valid JSON object containing a PARTIAL UPDATE to the current story state.

Rules:
- Record only changes actually caused by the supplied completed story section.
- Do not repeat unchanged fields.
- For changed nested objects, include only changed nested keys.
- For arrays, replace the array only when that array truly changed.
- Treat current_situation as a live scene-state field, not as a scene-plan instruction. When the completed section ends in a materially different immediate situation, update current_situation to a concise description of that ending state so it can serve as the starting state for the next scene.
- Do not copy scene-plan wording, future-scene instructions, hard stops, or author directions into current_situation.
- When the section crosses a scene boundary, describe what is true at the end of the completed section, not what should happen afterward.
- Never invent future events.
- Never turn an unknown fact into a known fact.
- Keep character knowledge limited to what each character could actually know.
- Update character_knowledge when a character actually learns a new consequential fact during the completed section, including facts learned through another character's dialogue, a direct observation, or an event that character personally experiences.
- Perform an explicit knowledge audit for every current-scene character. Compare the BEFORE-state knowledge with the entire completed prose and add only facts that became known during this section.
- For dialogue, treat information as learned by the characters who actually hear it. A speaker does not gain new knowledge merely by saying something they already know. Do not give information to characters who were not present, did not hear it, and did not witness it.
- Knowledge updates do not depend on a location or physical-state change. A character can learn important facts while remaining physically stationary.
- Preserve specific newly learned facts rather than replacing them with a vague summary such as "learned what happened." If several distinct facts are communicated, retain the distinct facts.
- Read the entire completed section for knowledge changes. Do not rely only on the final paragraph or final excerpt.
- Never infer that a character learned a fact merely because the narrator states it. The character must reasonably perceive, hear, read, or experience the information in the scene.
- Treat continuity_notes as editorial reminders only. They are not authoritative story facts, scene instructions, or character knowledge. Never use them as evidence for what happened, never promote them into permanent facts, and never copy them into a new state update unless the completed prose independently establishes the same fact.
- Treat physical_state as a first-class continuity field. It records each character's physical location, position, posture, contact with other characters, and movement state at the absolute end of the supplied section.
- When the completed prose clearly establishes or changes a character's final physical state, include those changed fields under physical_state for that character.
- Physical continuity must follow the actual final prose. Do not move or reposition a character in physical_state merely because a new scene could logically use a different arrangement.
- Record only facts established by the supplied story section.
- Preserve consequential action ownership and causal links. When a completed section establishes multiple important actions in sequence, keep them as separate ordered events in recent_events rather than collapsing them into vague summaries. Do not replace a specific action such as a character striking, grabbing, turning, throwing, or being injured with a generic description such as "tried to help" or "a struggle occurred."
- Preserve the established order of consequential events when updating recent_events. Do not reorder, merge, or omit a consequential action merely to make the summary shorter.
- Determine the resulting state from what is true at the ABSOLUTE END of the completed section, using the final actions and final paragraphs as the primary evidence.
- The current state is the BEFORE-state baseline only. Never copy a before-state location or situation into the update when the completed section clearly changes it.
- For any character whose location or immediate situation changes during the section, include that changed character under location even if the before-state already listed a different location.
- Use the supplied scene end guidance only to clarify the intended scene boundary. The actual completed prose is authoritative for what happened.
- Do not invent motives, identities, locations, evidence, backstory, or other consequential facts.
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
    decoder = json.JSONDecoder()

    for index, char in enumerate(text or ""):
        if char != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj

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


class StateManager:
    """Turns accepted prose into a reviewable current_state patch."""

    @staticmethod
    def merge_patch(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        return merge_patch(base, patch)

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
        """Run a focused pass that extracts only newly learned character facts."""
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
            "You are auditing character knowledge after a completed section of an ongoing fictional novel.\n\n"
            "Return ONLY one JSON object mapping character names to lists of NEW facts that character learned "
            "during this section. Return {} when nobody learned anything new.\n\n"
            "Rules:\n"
            "- Audit only characters in the supplied scene cast.\n"
            "- Compare the BEFORE knowledge with the completed prose.\n"
            "- Treat dialogue, direct observation, reading, and personal experience as valid ways to learn facts.\n"
            "- A listener learns consequential facts that another character actually tells them.\n"
            "- Do not give facts to characters who were not present, did not hear them, and did not witness them.\n"
            "- Return only genuinely NEW facts. Do not repeat facts already known before the section.\n"
            "- Preserve specific consequential details. Do not collapse several learned facts into a vague summary.\n"
            "- Use only facts explicitly established by the completed prose. Do not infer future events, motives, "
            "hidden knowledge, or unstated conclusions.\n"
            "- Output valid JSON only.\n\n"
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
            "--n-predict", "700",
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
        except subprocess.TimeoutExpired:
            proc.kill()
            output, _ = proc.communicate()
            return {}
        if proc.returncode not in (0, None):
            return {}

        raw = extract_json_object(output)
        result: dict[str, list[str]] = {}
        for name in cast:
            values = raw.get(name)
            if not isinstance(values, list):
                continue
            cleaned = [str(item).strip() for item in values if str(item).strip()]
            if cleaned:
                result[name] = cleaned
        return result

    @staticmethod
    def _merge_knowledge_delta(
        current_state: dict[str, Any],
        patch: dict[str, Any],
        delta: dict[str, list[str]],
    ) -> None:
        """Append newly learned facts without replacing existing knowledge."""
        base_knowledge = current_state.get("character_knowledge", {})
        if not isinstance(base_knowledge, dict):
            base_knowledge = {}

        proposed = patch.get("character_knowledge", {})
        if not isinstance(proposed, dict):
            proposed = {}

        combined: dict[str, list[str]] = {}
        for source in (base_knowledge, proposed):
            for name, values in source.items():
                if isinstance(values, list):
                    bucket = combined.setdefault(str(name), [])
                    for value in values:
                        text_value = str(value).strip()
                        if text_value and text_value not in bucket:
                            bucket.append(text_value)
                elif isinstance(values, str) and values.strip():
                    combined.setdefault(str(name), []).append(values.strip())

        for name, values in delta.items():
            bucket = combined.setdefault(name, [])
            for value in values:
                if value not in bucket:
                    bucket.append(value)

        changed: dict[str, list[str]] = {}
        for name, values in combined.items():
            before_values = base_knowledge.get(name, []) if isinstance(base_knowledge, dict) else []
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

        # Give the continuity model an explicit before-state knowledge audit so
        # dialogue-based learning is evaluated separately from physical state.
        cast = [
            str(name).strip()
            for name in current_state.get("scene_cast", [])
            if str(name).strip()
        ]
        knowledge_before = {}
        existing_knowledge = current_state.get("character_knowledge", {})
        if isinstance(existing_knowledge, dict):
            for name in cast:
                values = existing_knowledge.get(name)
                if values is None:
                    for key, candidate in existing_knowledge.items():
                        if str(key).casefold() == name.casefold():
                            values = candidate
                            break
                if isinstance(values, list):
                    knowledge_before[name] = [
                        str(item).strip()
                        for item in values
                        if str(item).strip()
                    ]
                elif isinstance(values, str) and values.strip():
                    knowledge_before[name] = [values.strip()]

        if knowledge_before:
            prompt_parts.extend([
                "\n\nCHARACTER KNOWLEDGE BEFORE THIS SECTION:\n",
                json.dumps(knowledge_before, indent=2, ensure_ascii=False),
            ])

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
            "Return ONLY the changed fields as a JSON object. Return {} if nothing changed."
        ])
        prompt = "".join(prompt_parts)

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
            "--prompt", prompt,
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

        patch = extract_json_object(output)
        if not isinstance(patch, dict):
            raise ValueError("Continuity analysis did not return an object.")

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
        except Exception:
            pass

        # A structured state_after is an authored scene outcome. When it is
        # present, use it to anchor the proposed ending state rather than
        # allowing the language model to veto or overwrite the known scene
        # transition. Any other model-derived changes are preserved.
        if end_guidance:
            expected_end_state = extract_expected_end_state(end_guidance)
            if expected_end_state:
                authored_patch = remove_unchanged(
                    current_state,
                    expected_end_state,
                )
                patch = merge_patch(patch, authored_patch)

                # Keep legacy top-level location fields synchronized with the
                # authoritative nested location object when those fields still
                # exist in older story packages.
                expected_location = expected_end_state.get("location")
                if isinstance(expected_location, dict):
                    legacy_location_patch = {}
                    if "primary" in current_state and "primary" in expected_location:
                        legacy_location_patch["primary"] = expected_location["primary"]
                    for name, value in expected_location.items():
                        if name == "primary":
                            continue
                        if name in current_state:
                            legacy_location_patch[name] = value
                    patch = merge_patch(patch, legacy_location_patch)

        return patch
