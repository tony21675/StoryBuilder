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
- Never invent future events.
- Never turn an unknown fact into a known fact.
- Keep character knowledge limited to what each character could actually know.
- Record only facts established by the supplied story section.
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
    def _detect_accelerator() -> str | None:
        """Use CPU unless acceleration is explicitly requested."""
        override = os.environ.get("STORY_LLM_DEVICE", "").strip()
        return override or None

    @staticmethod
    def propose(
        model_path: str | Path,
        current_state: dict[str, Any],
        story_text: str,
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

        prompt = (
            "CURRENT STATE BEFORE THIS SECTION:\n"
            + json.dumps(current_state, indent=2, ensure_ascii=False)
            + "\n\nCOMPLETED STORY SECTION:\n"
            + story_text.strip()
            + "\n\nReturn ONLY the changed fields as a JSON object. Return {} if nothing changed."
        )

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
        return remove_unchanged(current_state, patch)
