from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from builder.state_manager import extract_json_object
from builder.workspace import LLAMA as DEFAULT_LLAMA


VALIDATOR_SYSTEM_PROMPT = """You check a completed fictional scene against its authored scene contract and starting state.

Return only JSON in this shape:
{"pass": true, "missed_beats": [], "violations": [], "notes": ""}

Check only what matters: required actions and facts, required order, explicit prohibitions, character knowledge, the opening physical situation, and the actual ending against hard_stop. Accept natural paraphrases. Do not demand exact wording, invent requirements, nitpick style, or penalize harmless creative details. Do not infer hidden motives or sexual intent from neutral caring gestures. Report only clear, material failures, briefly. Output JSON only.
"""


def _detect_accelerator() -> str | None:
    override = os.environ.get("STORY_LLM_DEVICE", "").strip()
    return override or None


CONTRACT_BUILDER_SYSTEM_PROMPT = """Create a concise scene contract for a fictional novel using the author's scene idea and current story state.

Return only valid JSON in this shape:
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
- Current state is the opening snapshot. Preserve the actual starting situation and do not replay completed events.
- The author's idea controls what happens. Preserve the intended endpoint in one clear hard_stop.
- Use a concise direction, not a scene script.
- Put the few important concrete actions in required_beats, in natural order. Combine related actions instead of splitting them into small checklist items.
- Leave required_facts, required_sequence, forbidden, and forbidden_details empty. Keep all positive must-haves together in required_beats; do not create extra validation gates.
- Do not add events, gestures, motives, revelations, dialogue requirements, or prohibitions the author did not request.
- Leave dialogue, gestures, pacing, and ordinary transitions to the writer. Preserve creative freedom between the required beats.
- max_attempts is 3.
- Output JSON only.
"""


def _run_with_existing_engine(
    engine: Any,
    model: Path,
    system_prompt: str,
    prompt: str,
    *,
    context_size: int,
    max_tokens: int,
    timeout_seconds: int,
    task_name: str,
) -> dict[str, Any]:
    """Run a small model task through the existing writer process, never a second model."""
    saved = {
        key: os.environ.get(key)
        for key in ("STORY_WRITER_CONTEXT", "STORY_WRITER_MAX_TOKENS")
    }
    os.environ["STORY_WRITER_CONTEXT"] = str(context_size)
    os.environ["STORY_WRITER_MAX_TOKENS"] = str(max_tokens)
    try:
        # reset_context stops the writer child before starting the task-specific
        # prompt, so the machine never has two GGUF processes resident together.
        engine.reset_context(model, system_prompt)
        output = engine.generate(prompt, timeout=timeout_seconds)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    result = extract_json_object(output)
    if not isinstance(result, dict):
        raise ValueError(f"{task_name} did not return a JSON object.")
    return result


def _engine_is_running(engine: Any) -> bool:
    child = getattr(engine, "child", None)
    try:
        return child is not None and bool(child.isalive())
    except Exception:
        return False


def _run_contract_builder(model: Path, prompt: str, engine: Any = None) -> dict[str, Any]:
    if engine is not None and _engine_is_running(engine):
        timeout_seconds = max(60, int(os.environ.get("STORY_CONTRACT_TIMEOUT", "300")))
        return _run_with_existing_engine(
            engine,
            model,
            CONTRACT_BUILDER_SYSTEM_PROMPT,
            prompt,
            context_size=int(os.environ.get("STORY_CONTRACT_CONTEXT", "6144")),
            max_tokens=int(os.environ.get("STORY_CONTRACT_MAX_TOKENS", "700")),
            timeout_seconds=timeout_seconds,
            task_name="Scene contract generation",
        )

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
        "-c", os.environ.get("STORY_CONTRACT_CONTEXT", "6144"),
        "--reasoning", "off",
        "--temp", "0.15",
        "--top-k", "10",
        "--top-p", "0.80",
        "--repeat-last-n", "128",
        "--repeat-penalty", "1.08",
        "--n-predict", os.environ.get("STORY_CONTRACT_MAX_TOKENS", "700"),
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


def _run_validator(model: Path, prompt: str, engine: Any = None) -> dict[str, Any]:
    if engine is not None and _engine_is_running(engine):
        timeout_seconds = max(60, int(os.environ.get("STORY_VALIDATOR_TIMEOUT", "300")))
        return _run_with_existing_engine(
            engine,
            model,
            VALIDATOR_SYSTEM_PROMPT,
            prompt,
            context_size=int(os.environ.get("STORY_VALIDATOR_CONTEXT", "6144")),
            max_tokens=int(os.environ.get("STORY_VALIDATOR_MAX_TOKENS", "220")),
            timeout_seconds=timeout_seconds,
            task_name="Scene contract validation",
        )

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
        "-c", os.environ.get("STORY_VALIDATOR_CONTEXT", "6144"),
        "--reasoning", "off",
        "--temp", "0.05",
        "--top-k", "10",
        "--top-p", "0.70",
        "--repeat-last-n", "128",
        "--repeat-penalty", "1.08",
        "--n-predict", "220",
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
    timeout_seconds = max(60, int(os.environ.get("STORY_VALIDATOR_TIMEOUT", "300")))
    try:
        output, _ = proc.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        output, _ = proc.communicate()
        raise TimeoutError(
            f"Scene contract validation timed out after {timeout_seconds} seconds. "
            "The draft remains unaccepted; you can save it and retry."
        ) from exc

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


_AUTHOR_SECTION_ALIASES = {
    "beginning": "beginning",
    "opening": "beginning",
    "start": "beginning",
    "middle": "middle",
    "progression": "middle",
    "end": "end",
    "ending": "end",
    "hard stop": "end",
    "required": "required_beats",
    "required beat": "required_beats",
    "required beats": "required_beats",
    "must include": "required_beats",
}


def extract_authored_scene_sections(scene_idea: str) -> dict[str, Any]:
    """Extract clearly labeled author sections so generation cannot silently omit them."""
    collected: dict[str, list[str]] = {}
    active_section: str | None = None

    for raw_line in str(scene_idea or "").splitlines():
        line = raw_line.strip()
        if not line:
            if active_section:
                collected.setdefault(active_section, []).append("")
            continue

        header = line.lstrip("#").strip()
        header = header.strip("*_ ").strip()
        inline_value = ""
        candidate = header.casefold()
        if ":" in header:
            heading, inline_value = header.split(":", 1)
            candidate = heading.strip().strip("*_ ").casefold()
        section = _AUTHOR_SECTION_ALIASES.get(candidate)

        # A heading without a colon must be a standalone label. This avoids
        # treating ordinary prose beginning with "End" or "Required" as a label.
        standalone_heading = ":" not in header and not inline_value
        if section and (not standalone_heading or candidate in _AUTHOR_SECTION_ALIASES):
            active_section = section
            collected.setdefault(active_section, [])
            if inline_value.strip():
                collected[active_section].append(inline_value.strip())
            continue

        if active_section:
            collected.setdefault(active_section, []).append(line)

    sections: dict[str, Any] = {}
    for key in ("beginning", "middle", "end"):
        value = "\n".join(collected.get(key, [])).strip()
        if value:
            sections[key] = value

    required_beats = []
    for raw_item in collected.get("required_beats", []):
        item = re.sub(r"^\s*(?:[-*•]+|\d+[.)])\s*", "", str(raw_item)).strip()
        if item:
            required_beats.append(item)
    if required_beats:
        sections["required_beats"] = required_beats

    return sections


def _append_author_section(direction: str, label: str, text: str) -> str:
    """Keep explicit opening/progression intent when the model compresses it away."""
    direction = str(direction or "").strip()
    text = str(text or "").strip()
    if not text or text.casefold() in direction.casefold():
        return direction
    addition = f"Author-defined {label}: {text}"
    return f"{direction}\n\n{addition}".strip() if direction else addition


class SceneContract:
    """Validate generated prose against a reusable author-defined scene contract."""

    @staticmethod
    def generate_from_idea(
        model_path: str | Path,
        current_state: dict[str, Any],
        scene_idea: str,
        engine: Any = None,
    ) -> dict[str, Any]:
        """Generate a minimal draft contract from an author scene idea."""
        idea = str(scene_idea or "").strip()
        if not idea:
            raise ValueError("Enter a scene idea first.")

        model = Path(os.path.expanduser(str(model_path))).resolve()
        if not model.is_file() or model.suffix.casefold() != ".gguf":
            raise ValueError("The selected model is not a valid GGUF file.")

        contract_state = {
            key: current_state[key]
            for key in (
                "chapter",
                "scene",
                "status",
                "scene_completed",
                "location",
                "time",
                "time_of_day",
                "scene_cast",
                "current_situation",
                "physical_state",
                "character_knowledge",
            )
            if key in current_state
        }
        prompt = (
            "BUILD A MINIMAL SCENE CONTRACT.\\n\\n"
            "AUTHOR SCENE IDEA:\\n"
            + idea
            + "\\n\\nCURRENT STORY STATE AT SCENE START:\\n"
            + json.dumps(contract_state, ensure_ascii=False, separators=(",", ":"))
            + "\\n\\nCreate the contract now. Keep it minimal.\\n"
        )

        if engine is not None and _engine_is_running(engine):
            raw = _run_contract_builder(model, prompt, engine=engine)
        else:
            raw = _run_contract_builder(model, prompt)

        authored_sections = extract_authored_scene_sections(idea)
        result = {
            "direction": str(raw.get("direction", "") or "").strip(),
            "hard_stop": str(raw.get("hard_stop", "") or "").strip(),
            "required_beats": raw.get("required_beats", []),
            # Keep generated requirements in one simple place. The model often
            # turns auxiliary fields into brittle extra gates; concrete author
            # requirements belong in required_beats unless the author adds an
            # explicit structured requirement through a future UI.
            "required_facts": [],
            "required_sequence": [],
            # Do not generate hidden extra prohibitions.
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

        # The model drafts a concise contract, but clearly labeled author
        # sections remain authoritative if the model omits or compresses them.
        result["direction"] = _append_author_section(
            result["direction"], "beginning", authored_sections.get("beginning", "")
        )
        result["direction"] = _append_author_section(
            result["direction"], "progression", authored_sections.get("middle", "")
        )
        if authored_sections.get("end"):
            result["hard_stop"] = authored_sections["end"]

        for beat in authored_sections.get("required_beats", []):
            if beat.casefold() not in {
                str(existing).strip().casefold()
                for existing in result["required_beats"]
            }:
                result["required_beats"].append(beat)

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
                "direction",
                "required_beats",
                "required_facts",
                "required_sequence",
                "forbidden",
                "forbidden_details",
                "hard_stop",
            )
            if key in contract
        }

        # Keep only state fields needed to verify opening continuity and knowledge.
        # Large unrelated state/history payloads make local validation slower.
        validation_state = {
            key: current_state[key]
            for key in (
                "chapter",
                "scene",
                "status",
                "scene_completed",
                "location",
                "time",
                "time_of_day",
                "scene_cast",
                "current_situation",
                "physical_state",
                "character_knowledge",
                "active_objectives",
            )
            if key in current_state
        }

        prompt = (
            "Validate this completed scene against the supplied contract and starting state. "
            "Return JSON only in this shape: "
            '{"pass": true, "missed_beats": [], "violations": [], "notes": ""}\n\n'
            "SCENE CONTRACT:\n"
            + json.dumps(semantic_contract, ensure_ascii=False, separators=(",", ":"))
            + "\n\nSTARTING STATE (relevant fields only):\n"
            + json.dumps(validation_state, ensure_ascii=False, separators=(",", ":"))
            + "\n\nCOMPLETED SCENE:\n"
            + prose.strip()
        )

        model = getattr(engine, "model_path", None)
        if model is None:
            raise RuntimeError("The active writer model is unavailable for scene validation.")

        if _engine_is_running(engine):
            raw_result = _run_validator(Path(model), prompt, engine=engine)
        else:
            raw_result = _run_validator(Path(model), prompt)
        # Keep the public API stable even when validators are mocked or an
        # alternate engine returns JSON booleans as strings.
        if not isinstance(raw_result, dict):
            raise ValueError("Scene contract validator returned an invalid result object.")

        raw_pass = raw_result.get("pass", None)
        if isinstance(raw_pass, bool):
            passed = raw_pass
        elif isinstance(raw_pass, str) and raw_pass.strip().casefold() in {"true", "false"}:
            passed = raw_pass.strip().casefold() == "true"
        else:
            raise ValueError("Scene contract validator returned an invalid 'pass' value.")

        missed = raw_result.get("missed_beats", [])
        violations = raw_result.get("violations", [])
        if not isinstance(missed, list):
            raise ValueError("Scene contract validator returned invalid missed_beats data.")
        if not isinstance(violations, list):
            raise ValueError("Scene contract validator returned invalid violations data.")

        return {
            "pass": passed,
            "missed_beats": [str(item).strip() for item in missed if str(item).strip()],
            "violations": [str(item).strip() for item in violations if str(item).strip()],
            "notes": str(raw_result.get("notes", "") or "").strip(),
        }


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
