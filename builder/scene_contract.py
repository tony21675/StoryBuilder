from __future__ import annotations

import json
import os
import re
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


CONTRACT_BUILDER_SYSTEM_PROMPT = """You are an authoring assistant for a fictional novel scene.

The author will give you a short scene idea and the exact current story state at the start of the scene.

Create a MINIMAL scene contract that protects the author's intent without over-constraining the writer.

Return ONLY valid JSON in exactly this shape:
{
  "direction": "",
  "hard_stop": "",
  "required_beats": [],
  "required_facts": [],
  "required_sequence": [],
  "forbidden": [],
  "forbidden_details": [],
  "max_attempts": 3
}

Rules:
- Use the current story state as the starting point. Do not replay facts or events already completed before the scene starts.
- The author's scene idea is the primary creative instruction.
- Treat the scene idea as a boundary, not just a suggestion. Do not add new story events, revelations, character actions, future developments, or ending conditions that are not directly supported by the author's idea.
- Write a concise "direction" that tells the writer what the scene is about and how it should unfold naturally, using only the actions and intent supported by the author's idea and current state.
- Write a concise "hard_stop" that names ONE clear stopping point directly supported by the author's idea. Do not invent a new event just to create an ending.
- The hard stop must name ONE clear stopping point. Do not offer alternatives, choices, or "or" conditions.
- Use the FEWEST contract requirements necessary.
- Leave required_beats empty unless a specific event is genuinely important to the author's idea.
- Leave required_facts empty unless a specific fact must be explicitly established for continuity or the author's idea.
- Leave required_sequence empty unless the author clearly requires a specific order.
- Do not generate entries for "forbidden" or "forbidden_details". Leave both arrays empty.
- These prohibition fields are author-controlled and may be filled manually after generation when needed.
- Do not invent major plot developments, characters, clues, motives, backstory, injuries, revelations, or future events that the author did not request.
- Do not turn plausible implications into mandatory requirements.
- Do not turn plausible scene variations into prohibitions. If the author did not say "do not do X", do not add "do not do X" merely because X seems less appropriate.
- Do not infer default drama or closure beats such as falling asleep, leaving the room, ending comfort, calling the police, starting a pursuit, discovering a clue, or becoming fully calm unless the author explicitly requests them.
- Do not repeat the entire current state in the contract.
- Preserve creative freedom for dialogue, gestures, pacing, sensory details, ordinary emotions, and harmless everyday interaction.
- Prefer a small number of broad requirements over many narrow checklist items.
- When a scene idea is broad, prefer one or two broad beats rather than several detailed beats.
- A minimal contract may contain only direction and hard_stop. That is preferable to adding speculative beats, facts, sequence steps, or prohibitions.
- Required beats, facts, and sequence steps should only be added when genuinely necessary. Keep them few.
- Prohibitions are never generated automatically. Leave them empty.
- max_attempts must be 3 unless the author clearly asks otherwise.
- Output JSON only. No markdown or explanation.
"""


def _run_contract_builder(model: Path, prompt: str) -> dict[str, Any]:
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
        "-c", os.environ.get("STORY_WRITER_CONTEXT", "8192"),
        "--reasoning", "off",
        "--temp", "0.15",
        "--top-k", "10",
        "--top-p", "0.80",
        "--repeat-last-n", "256",
        "--repeat-penalty", "1.08",
        "--n-predict", "700",
        "--system-prompt", CONTRACT_BUILDER_SYSTEM_PROMPT,
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
        raise TimeoutError("Scene contract generation timed out.") from exc

    if proc.returncode not in (0, None):
        raise RuntimeError(
            "Scene contract generation failed.\n" + (output or "")[-2000:]
        )

    result = extract_json_object(output)
    if not isinstance(result, dict):
        raise ValueError("Scene contract generator did not return an object.")

    return result


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

    raw_pass = result.get("pass", None)
    if isinstance(raw_pass, bool):
        passed = raw_pass
    elif isinstance(raw_pass, str) and raw_pass.strip().casefold() in {"true", "false"}:
        passed = raw_pass.strip().casefold() == "true"
    else:
        raise ValueError("Scene contract validator returned an invalid 'pass' value.")

    missed = result.get("missed_beats", [])
    violations = result.get("violations", [])
    if not isinstance(missed, list):
        raise ValueError("Scene contract validator returned invalid missed_beats data.")
    if not isinstance(violations, list):
        raise ValueError("Scene contract validator returned invalid violations data.")

    notes = str(result.get("notes", "") or "").strip()

    return {
        "pass": passed,
        "missed_beats": [str(x).strip() for x in missed if str(x).strip()],
        "violations": [str(x).strip() for x in violations if str(x).strip()],
        "notes": notes,
    }


class SceneContract:
    """Validate generated prose against a reusable author-defined scene contract."""

    @staticmethod
    def generate_from_idea(
        model_path: str | Path,
        current_state: dict[str, Any],
        scene_idea: str,
    ) -> dict[str, Any]:
        """Generate a minimal draft contract from an author scene idea."""
        idea = str(scene_idea or "").strip()
        if not idea:
            raise ValueError("Enter a scene idea first.")

        model = Path(os.path.expanduser(str(model_path))).resolve()
        if not model.is_file() or model.suffix.casefold() != ".gguf":
            raise ValueError("The selected model is not a valid GGUF file.")

        prompt = (
            "BUILD A MINIMAL SCENE CONTRACT.\n\n"
            "AUTHOR SCENE IDEA:\n"
            + idea
            + "\n\nCURRENT STORY STATE AT SCENE START:\n"
            + json.dumps(current_state, indent=2, ensure_ascii=False)
            + "\n\nCreate the contract now. Keep it minimal.\n"
        )

        raw = _run_contract_builder(model, prompt)

        result = {
            "direction": str(raw.get("direction", "") or "").strip(),
            "hard_stop": str(raw.get("hard_stop", "") or "").strip(),
            "required_beats": raw.get("required_beats", []),
            "required_facts": raw.get("required_facts", []),
            "required_sequence": raw.get("required_sequence", []),
            # Automatic generation deliberately leaves prohibitions empty.
            # Author can add them manually when a specific boundary is needed.
            "forbidden": [],
            "forbidden_details": [],
            "max_attempts": raw.get("max_attempts", 3),
        }

        for key in (
            "required_beats",
            "required_facts",
            "required_sequence",
            "forbidden",
            "forbidden_details",
        ):
            value = result[key]
            if value is None:
                result[key] = []
            elif not isinstance(value, list):
                raise ValueError(
                    f"Scene contract generator returned invalid {key} data."
                )
            else:
                result[key] = [
                    str(item).strip()
                    for item in value
                    if str(item).strip()
                ]

        if result["max_attempts"] in (None, ""):
            result["max_attempts"] = 3

        SceneContract.validate_shape(result)
        lint_errors = SceneContract.lint(result)
        if lint_errors:
            raise ValueError(
                "Generated scene contract needs attention:\n- "
                + "\n- ".join(lint_errors)
            )

        return result

    @staticmethod
    def max_attempts(contract: dict[str, Any]) -> int:
        """Return a safe retry count for automatic scene generation."""
        raw = contract.get(
            "max_attempts",
            os.environ.get("STORY_SCENE_MAX_ATTEMPTS", "3"),
        )
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("Scene contract max_attempts must be an integer.") from exc
        return max(1, min(5, value))

    @staticmethod
    def validate_shape(contract: dict[str, Any]) -> dict[str, Any]:
        """Validate contract structure before spending model time on it."""
        if not isinstance(contract, dict):
            raise ValueError("Scene contract must be a JSON object.")

        for key in (
            "required_beats",
            "required_facts",
            "required_sequence",
            "forbidden",
            "forbidden_details",
        ):
            if key in contract and contract[key] is not None and not isinstance(contract[key], list):
                raise ValueError(f"Scene contract '{key}' must be a list.")

        if "hard_stop" in contract and contract["hard_stop"] is not None:
            if not isinstance(contract["hard_stop"], str):
                raise ValueError("Scene contract 'hard_stop' must be a string.")

        if "state_after" in contract and contract["state_after"] is not None:
            if not isinstance(contract["state_after"], dict):
                raise ValueError("Scene contract 'state_after' must be an object.")

        local = contract.get("local_hard_checks")
        if local is not None:
            if not isinstance(local, dict):
                raise ValueError("Scene contract 'local_hard_checks' must be an object.")
            for key in ("forbidden_terms", "forbidden_patterns"):
                if key in local and local[key] is not None and not isinstance(local[key], list):
                    raise ValueError(f"Scene contract local hard check '{key}' must be a list.")

        SceneContract.max_attempts(contract)
        return contract

    @staticmethod
    def from_guidance(
        guidance: dict[str, Any] | None,
        module_guidance: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build a contract from scene guidance and active story modules."""
        source = guidance if isinstance(guidance, dict) else {}
        explicit = source.get("scene_contract")
        if "scene_contract" in source and explicit is not None and not isinstance(explicit, dict):
            raise ValueError("Scene guidance 'scene_contract' must be an object.")
        contract = dict(explicit) if isinstance(explicit, dict) else {}

        def add_list(target_key: str, *candidate_keys: str) -> None:
            existing = contract.get(target_key)
            merged = [str(item).strip() for item in existing if str(item).strip()] if isinstance(existing, list) else []
            seen = {item.casefold() for item in merged}
            for candidate in candidate_keys:
                value = source.get(candidate)
                if not isinstance(value, list):
                    continue
                for item in value:
                    item_text = str(item).strip()
                    if item_text and item_text.casefold() not in seen:
                        merged.append(item_text)
                        seen.add(item_text.casefold())
            if merged:
                contract[target_key] = merged

        add_list("required_beats", "required_beats", "required_events")
        add_list("required_facts", "required_facts")
        add_list("required_sequence", "required_sequence")
        add_list("forbidden", "forbidden", "do_not_advance")
        add_list("forbidden_details", "forbidden_details")

        if not contract.get("hard_stop"):
            end_condition = source.get("hard_stop") or source.get("end_condition")
            if end_condition:
                contract["hard_stop"] = str(end_condition).strip()

        if "state_after" not in contract and isinstance(source.get("state_after"), dict):
            contract["state_after"] = source["state_after"]

        if "max_attempts" not in contract and "max_attempts" in source:
            contract["max_attempts"] = source["max_attempts"]

        for module in module_guidance or []:
            if not isinstance(module, dict):
                continue
            nested = module.get("scene_contract")
            if isinstance(nested, dict):
                for key in ("required_beats", "required_facts", "required_sequence", "forbidden"):
                    value = nested.get(key)
                    if isinstance(value, list) and value:
                        existing = contract.get(key, [])
                        if not isinstance(existing, list):
                            existing = []
                        seen = {str(item).strip().casefold() for item in existing if str(item).strip()}
                        for item in value:
                            item_text = str(item).strip()
                            if item_text and item_text.casefold() not in seen:
                                existing.append(item_text)
                                seen.add(item_text.casefold())
                        contract[key] = existing
                if not contract.get("hard_stop") and nested.get("hard_stop"):
                    contract["hard_stop"] = str(nested["hard_stop"]).strip()

            events = module.get("required_events")
            if isinstance(events, list) and events:
                existing = contract.get("required_beats", [])
                if not isinstance(existing, list):
                    existing = []
                seen = {str(item).strip().casefold() for item in existing if str(item).strip()}
                for item in events:
                    item_text = str(item).strip()
                    if item_text and item_text.casefold() not in seen:
                        existing.append(item_text)
                        seen.add(item_text.casefold())
                contract["required_beats"] = existing

            forbidden = module.get("forbidden") or module.get("do_not_advance")
            if isinstance(forbidden, list) and forbidden:
                existing = contract.get("forbidden", [])
                if not isinstance(existing, list):
                    existing = []
                seen = {str(item).strip().casefold() for item in existing if str(item).strip()}
                for item in forbidden:
                    item_text = str(item).strip()
                    if item_text and item_text.casefold() not in seen:
                        existing.append(item_text)
                        seen.add(item_text.casefold())
                contract["forbidden"] = existing

            if not contract.get("hard_stop"):
                end_condition = module.get("hard_stop") or module.get("end_condition")
                if end_condition:
                    contract["hard_stop"] = str(end_condition).strip()

            if "state_after" not in contract and isinstance(module.get("state_after"), dict):
                contract["state_after"] = module["state_after"]

        if not contract:
            return {}

        errors = SceneContract.lint(contract)
        if errors:
            raise ValueError(
                "Invalid scene contract:\n- " + "\n- ".join(errors)
            )
        return contract

    @staticmethod
    def lint(contract: dict[str, Any]) -> list[str]:
        """Return deterministic authoring errors without judging prose."""
        SceneContract.validate_shape(contract)

        errors: list[str] = []
        list_keys = (
            "required_beats",
            "required_facts",
            "required_sequence",
            "forbidden",
            "forbidden_details",
        )

        normalized: dict[str, set[str]] = {}
        for key in list_keys:
            values = contract.get(key, [])
            if not isinstance(values, list):
                continue
            seen: set[str] = set()
            duplicates: list[str] = []
            for item in values:
                item_text = str(item).strip()
                if not item_text:
                    errors.append(f"Scene contract '{key}' contains an empty item.")
                    continue
                item_key = item_text.casefold()
                if item_key in seen:
                    duplicates.append(item_text)
                seen.add(item_key)
            if duplicates:
                errors.append(
                    f"Scene contract '{key}' contains duplicate items: "
                    + ", ".join(repr(item) for item in duplicates)
                )
            normalized[key] = seen

        forbidden = normalized.get("forbidden", set()) | normalized.get("forbidden_details", set())
        required = (
            normalized.get("required_beats", set())
            | normalized.get("required_facts", set())
            | normalized.get("required_sequence", set())
        )
        overlap = sorted(required & forbidden)
        for item in overlap:
            errors.append(
                f"Scene contract contains a requirement and prohibition for the same item: {item!r}."
            )

        local = contract.get("local_hard_checks", {})
        if isinstance(local, dict):
            for key in ("forbidden_patterns", "required_patterns"):
                patterns = local.get(key, [])
                if not isinstance(patterns, list):
                    continue
                for pattern in patterns:
                    pattern_text = str(pattern).strip()
                    if not pattern_text:
                        continue
                    try:
                        re.compile(pattern_text)
                    except re.error as exc:
                        errors.append(
                            f"Invalid scene contract regex in {key}: {pattern_text!r} ({exc})."
                        )

        return errors

    @staticmethod
    def _local_hard_checks(contract: dict[str, Any], prose: str) -> dict[str, Any]:
        """Run only narrow deterministic checks.

        Deterministic checks are limited to explicit forbidden details. Required
        story beats remain semantic requirements so the writer keeps creative
        freedom in how those beats are expressed.
        """
        rules = contract.get("local_hard_checks", {})
        if not isinstance(rules, dict):
            return {"pass": True, "missed_beats": [], "violations": [], "notes": ""}

        violations: list[str] = []

        forbidden_terms = rules.get("forbidden_terms", [])
        text_cf = prose.casefold()
        if isinstance(forbidden_terms, list):
            for term in forbidden_terms:
                term = str(term).strip()
                if not term:
                    continue
                pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"
                if re.search(pattern, text_cf, flags=re.IGNORECASE):
                    violations.append(
                        f"Forbidden detail appears in prose: {term!r}."
                    )

        # Normalize whitespace only for optional forbidden regex checks. This
        # lets a pattern span paragraph/dialogue breaks without imposing exact
        # wording on required story beats.
        normalized_prose = re.sub(r"\s+", " ", prose).strip()

        forbidden_patterns = rules.get("forbidden_patterns", [])
        if isinstance(forbidden_patterns, list):
            for pattern in forbidden_patterns:
                pattern = str(pattern).strip()
                if not pattern:
                    continue
                try:
                    if re.search(pattern, normalized_prose, flags=re.IGNORECASE):
                        violations.append(
                            f"Forbidden contract pattern matched: {pattern!r}."
                        )
                except re.error as exc:
                    raise ValueError(
                        f"Invalid scene contract regex: {pattern!r}"
                    ) from exc

        if violations:
            return {
                "pass": False,
                "missed_beats": [],
                "violations": violations,
                "notes": "Deterministic forbidden-detail checks failed before semantic validation.",
            }

        return {"pass": True, "missed_beats": [], "violations": [], "notes": ""}


    @staticmethod
    def validate_with_engine(
        engine: Any,
        contract: dict[str, Any],
        current_state: dict[str, Any],
        prose: str,
    ) -> dict[str, Any]:
        """Validate scene semantics with a dedicated validator process."""
        if not isinstance(contract, dict) or not contract:
            return {"pass": True, "missed_beats": [], "violations": [], "notes": ""}

        SceneContract.validate_shape(contract)
        lint_errors = SceneContract.lint(contract)
        if lint_errors:
            raise ValueError(
                "Invalid scene contract:\n- " + "\n- ".join(lint_errors)
            )

        if not prose.strip():
            return {
                "pass": False,
                "missed_beats": ["The writer returned no prose."],
                "violations": [],
                "notes": "Generation returned an empty scene.",
            }

        local_result = SceneContract._local_hard_checks(contract, prose)
        if not local_result.get("pass"):
            return local_result

        # Only semantic requirements belong in the validator prompt. The
        # local_hard_checks section is implementation detail, not prose
        # wording that the model should be forced to reproduce.
        semantic_contract = {
            key: contract[key]
            for key in (
                "required_beats",
                "required_facts",
                "required_sequence",
                "forbidden",
                "forbidden_details",
                "hard_stop",
                "state_after",
            )
            if key in contract
        }

        prompt = (
            "VALIDATION MODE. Judge the completed prose against the authored "
            "scene contract. Do not rewrite the scene.\n\n"
            "Return ONLY valid JSON in this exact shape:\n"
            '{"pass": true, "missed_beats": [], "violations": [], "notes": ""}\n\n'
            "IMPORTANT VALIDATION PRINCIPLES:\n"
            "- The writer has creative freedom over wording, dialogue phrasing, "
            "gestures, sensory detail, pacing, and ordinary interaction.\n"
            "- Accept clear paraphrases and natural variations when they preserve "
            "the required story fact or event.\n"
            "- Do NOT require exact wording or a particular sentence structure.\n"
            "- Do NOT treat deterministic regex hints as required wording.\n"
            "- Reject only genuine missing requirements, contradictions, knowledge "
            "leaks, sequence errors, or an incorrect hard stop.\n\n"
            "SCENE CONTRACT:\n"
            + json.dumps(semantic_contract, indent=2, ensure_ascii=False)
            + "\n\nCURRENT STORY STATE AT SCENE START:\n"
            + json.dumps(current_state, indent=2, ensure_ascii=False)
            + "\n\nCOMPLETED STORY PROSE TO VALIDATE:\n"
            + prose.strip()
            + "\n\n"
            "Validate the prose now. Output JSON only."
        )

        model = getattr(engine, "model_path", None)
        if model is None:
            raise RuntimeError("The active writer model is unavailable for scene validation.")

        return _run_validator(Path(model), prompt)


    @staticmethod
    def validate(
        model_path: str | Path,
        contract: dict[str, Any],
        current_state: dict[str, Any],
        prose: str,
    ) -> dict[str, Any]:
        """Legacy standalone validator kept for compatibility."""
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
