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
- Record only facts established by the supplied story section.
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

    return value if isinstance(value, dict) else None


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
            "\n\nCOMPLETED STORY SECTION:\n",
            completed_text,
        ]

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
            "the completed prose establishes at the end. For each character whose final location or immediate "
            "situation changed, include the changed value under location. Update current_situation to describe "
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

        return patch
