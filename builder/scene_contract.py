from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from builder.state_manager import extract_json_object
from builder.workspace import LLAMA as DEFAULT_LLAMA


VALIDATOR_SYSTEM_PROMPT = """You are a strict scene-contract validator for an ongoing fictional novel.

Return ONLY valid JSON in this exact shape:
{
  "pass": true,
  "missed_beats": [],
  "violations": [],
  "notes": ""
}

Validation standard:
- Treat the authored scene contract as a hard specification for the scene's story facts, event order, character knowledge, and stopping point.
- Treat the supplied current story state as authoritative for the scene's starting situation.
- Creative variation is allowed ONLY in wording, dialogue phrasing, gestures, harmless sensory detail, ordinary emotion, and other details that do not change or weaken a required fact or event.
- Do not require exact wording when the same required fact or event is clearly and explicitly established.
- Do not accept a required fact merely because it is vaguely implied, suggested, or replaced by a broader statement.
- When a required fact names a specific action, cause, object, injury, person, location, or sequence, that specific element must be explicitly established.
- Do not silently substitute a different action that feels similar. For example, "tried to stop him" does not automatically satisfy a requirement that a character struck the attacker from behind.
- When a contract gives a specific physical result, do not treat a materially different physical result as an equivalent. For example, a temporary red mark is not equivalent to bleeding, a scrape, a cut, a handprint, or a lasting wound unless the contract explicitly allows those variations.
- Required sequence matters. A scene can fail even when all individual events appear somewhere in the prose if they happen in the wrong order.
- The hard stop matters. The scene must stop at the authored ending state. Do not pass a scene that jumps beyond the stopping point, even if the required ending state also appears earlier.
- Character knowledge matters. Do not allow a character to know a fact before the character learns it in the scene.
- If a forbidden detail or contradiction occurs, mark a violation even when the rest of the scene is good.
- If a required beat, required fact, sequence step, or hard-stop condition is missing or only weakly implied, mark it as missed.
- If the contract specifies a character's established wording or address preferences, treat violations as contract violations when they materially contradict the supplied character guidance.
- Do not penalize harmless creative detail that is not constrained by the contract.
- Pass ONLY when every required beat and required fact is explicitly satisfied, the required sequence is preserved, the hard stop is satisfied, and no forbidden or contradictory detail appears.
- Keep missed_beats and violations concise and specific. Name the missing fact or wrong event rather than giving generic criticism.
- Output JSON only. No markdown or explanation outside the JSON.
"""


def _detect_accelerator() -> str | None:
    override = os.environ.get("STORY_LLM_DEVICE", "").strip()
    return override or None


def _run_validator(model: Path, prompt: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(DEFAULT_LLAMA.parent) + (
        ":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else ""
    )

    device = _detect_accelerator()
    args = [str(DEFAULT_LLAMA), "-m", str(model)]
    if device:
        args.extend(["--device", device, "-ngl", "all"])
    else:
        args.extend(["-ngl", "0", "--device", "none"])

    args.extend([
        "-c", "8192",
        "--reasoning", "off",
        "--temp", "0.05",
        "--top-k", "10",
        "--top-p", "0.70",
        "--repeat-last-n", "256",
        "--repeat-penalty", "1.08",
        "--n-predict", "350",
        "--system-prompt", VALIDATOR_SYSTEM_PROMPT,
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
        output, _ = proc.communicate(timeout=300)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        output, _ = proc.communicate()
        raise TimeoutError("Scene contract validation timed out.") from exc

    if proc.returncode not in (0, None):
        raise RuntimeError(
            "Scene contract validation failed.\n" + (output or "")[-2000:]
        )

    result = extract_json_object(output)
    if not isinstance(result, dict):
        raise ValueError("Scene contract validator did not return an object.")

    passed = bool(result.get("pass", False))
    missed = result.get("missed_beats", [])
    violations = result.get("violations", [])
    notes = str(result.get("notes", "") or "").strip()

    return {
        "pass": passed,
        "missed_beats": [str(x).strip() for x in missed] if isinstance(missed, list) else [],
        "violations": [str(x).strip() for x in violations] if isinstance(violations, list) else [],
        "notes": notes,
    }


class SceneContract:
    """Validate a generated scene against an authored scene contract."""

    @staticmethod
    def validate(
        model_path: str | Path,
        contract: dict[str, Any],
        current_state: dict[str, Any],
        prose: str,
    ) -> dict[str, Any]:
        if not isinstance(contract, dict) or not contract:
            return {"pass": True, "missed_beats": [], "violations": [], "notes": ""}

        model = Path(os.path.expanduser(str(model_path))).resolve()
        if not model.is_file() or model.suffix.casefold() != ".gguf":
            raise ValueError("The selected model is not a valid GGUF file.")

        prompt = (
            "SCENE CONTRACT:\n"
            + json.dumps(contract, indent=2, ensure_ascii=False)
            + "\n\nCURRENT STORY STATE AT SCENE START:\n"
            + json.dumps(current_state, indent=2, ensure_ascii=False)
            + "\n\nCOMPLETED STORY PROSE:\n"
            + prose.strip()
            + "\n\nValidation instructions:\n"
            "1. Check every required beat.\n"
            "2. Check every required fact explicitly, including its named action/cause/result.\n"
            "3. Check any required sequence in order.\n"
            "4. Check every forbidden detail or contradictory fact.\n"
            "5. Check character knowledge and prevent premature knowledge leaks.\n"
            "6. Check the hard-stop condition against the actual end of the prose.\n"
            "7. Do not replace missing specifics with vague wording merely because the scene feels similar.\n"
            "8. Pass only if ALL of those checks succeed.\n\n"
            "Validate the prose now."
        )
        return _run_validator(model, prompt)

    @staticmethod
    def feedback(result: dict[str, Any]) -> str:
        missed = [x for x in result.get("missed_beats", []) if str(x).strip()]
        violations = [x for x in result.get("violations", []) if str(x).strip()]
        notes = str(result.get("notes", "") or "").strip()

        lines = [
            "The previous draft did not satisfy the scene contract.",
            "Rewrite the scene from the beginning. Keep the same creative freedom in wording and dialogue, but correct every missing or incorrect contract item.",
            "Required facts must be explicit. Do not replace a specific required action, cause, injury, or ending event with a vague substitute.",
        ]
        if missed:
            lines.append("Missed required beats or facts:")
            lines.extend(f"- {item}" for item in missed)
        if violations:
            lines.append("Contract violations:")
            lines.extend(f"- {item}" for item in violations)
        if notes:
            lines.append("Validator note:")
            lines.append(notes)
        return "\n".join(lines)
