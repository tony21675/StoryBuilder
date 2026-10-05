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

Rules:
- Validate the completed prose against the supplied scene contract.
- Every required beat must be clearly present in the prose.
- Every forbidden event or contradiction must be absent.
- The prose must begin from the supplied starting situation and respect the current character knowledge.
- The prose may use different wording, dialogue, pacing, and harmless details. Do not require exact wording.
- Do not penalize harmless creative variation.
- Do not invent problems that are not stated in the contract.
- If a required beat is only implied weakly, treat it as missed.
- If the prose reveals information to a character before the contract allows it, treat that as a violation.
- If the prose changes an established fact, physical state, relationship, or event sequence covered by the contract, treat that as a violation.
- Pass only when all required beats are satisfied and no contract violation is present.
- Keep missed_beats and violations concise and specific.
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
        "--n-predict", "700",
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
            + "\n\nValidate the prose now."
        )
        return _run_validator(model, prompt)

    @staticmethod
    def feedback(result: dict[str, Any]) -> str:
        missed = [x for x in result.get("missed_beats", []) if str(x).strip()]
        violations = [x for x in result.get("violations", []) if str(x).strip()]
        notes = str(result.get("notes", "") or "").strip()

        lines = [
            "The previous draft did not satisfy the scene contract.",
            "Rewrite the scene from the beginning. Keep the same creative freedom in wording and dialogue, but correct the contract problems.",
        ]
        if missed:
            lines.append("Missed required beats:")
            lines.extend(f"- {item}" for item in missed)
        if violations:
            lines.append("Contract violations:")
            lines.extend(f"- {item}" for item in violations)
        if notes:
            lines.append("Validator note:")
            lines.append(notes)
        return "\n".join(lines)
