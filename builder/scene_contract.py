from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from builder.state_manager import extract_json_object
from builder.workspace import LLAMA as DEFAULT_LLAMA


class SceneContractResponseError(ValueError):
    """The validator replied, but its response was not valid JSON or schema."""


class SceneContractValidationUnavailable(RuntimeError):
    """The validator could not produce a readable response after one retry."""


VALIDATOR_SYSTEM_PROMPT = """Review the author's original idea and starting state. Return only JSON:
{"pass": true, "missed_beats": [], "violations": [], "checks": [{"requirement": "", "status": "met", "evidence": ""}], "notes": ""}

Judge meaning, not keywords. Synonyms and paraphrases count. Evidence must be a verbatim quote from COMPLETED SCENE only; never quote the idea, instructions, contract, or state.
Create a SHORT EVENT-LEVEL checklist, usually 4–8 checks total. Each check is one meaningful event or outcome. Group related details from the same event; do not create separate checks for clauses, adjectives, people, objects, or small actions. Keep events separate only when each could be missing independently. Ignore incidental details unless the idea makes them defining, continuity-critical, or a boundary/preference.
Review the whole scene. A check is met only when its main action and defining details are present. Different wording is fine; a different action, object, person, order, or outcome is not. A specified bubble bath is not a shower and still needs its bubbles. Use an exact quote that supports the event. Minor descriptive omissions alone do not fail unless material. Flag unexplained opening continuity mismatches, character-knowledge conflicts, and ignored acknowledged requests. Check acknowledged requests/preferences against later actions. Preserve stated backstory and accept neutral familial comfort. List each missing event once; if any check is missing, pass must be false.
"""

SEMANTIC_RECHECK_SYSTEM_PROMPT = """Independently reassess only the supplied checklist items against the completed scene. Return JSON only:
{"pass": true, "missed_beats": [], "violations": [], "checks": [{"requirement": "", "status": "met", "evidence": ""}], "notes": ""}

The first validator marked these items missing, but that may be a false negative. Judge meaning, not keyword overlap. Synonyms, paraphrases, indirect but clear descriptions, and equivalent actions count. Example: a requirement for a "red car" is met by "the maroon sedan" if context shows it is the same car. The evidence must be a verbatim excerpt from the completed scene, but does not need to repeat the requirement's vocabulary. For each supplied item, use status "met" only when the intended fact/action is actually established; quote the shortest direct excerpt that proves it. Use "missing" only when the scene genuinely omits or materially changes it, and set evidence to an empty string. Preserve specified identity, named people, objects, defining details, order, requests, and outcomes. Do not infer an event that did not occur, and do not create extra requirements. Repeat each supplied requirement unchanged. Assess only the listed items and the completed scene.
"""


def _detect_accelerator() -> str | None:
    override = os.environ.get("STORY_LLM_DEVICE", "").strip()
    return override or None


CONTRACT_BUILDER_SYSTEM_PROMPT = """Create a compact, gentle guide from the author's plain-English scene idea and current story state.

Return only JSON:
{"direction":"","hard_stop":"","required_beats":[],"max_attempts":3}

Use current_situation as the authoritative narrative snapshot for what has already happened. If they conflict, follow current_situation and preserve physical_state details not contradicted. The full original plain-English idea is also given directly to the Writer; it provides the scene's direction, key intentions, and natural endpoint.

Do not turn the idea into a checklist. Keep direction brief and high-level. Always return required_beats as an empty list; the application carries forward only beats the author explicitly labels in the original Scene Idea. Never turn ordinary prose or your own summary into mandatory stops. When the idea gives a clear endpoint, put that endpoint in hard_stop. Preserve it even when expressed as a temporal boundary or a passage-of-time boundary rather than a final action. Do not replace such an endpoint with the most prominent action mentioned earlier. If no endpoint is clear, leave hard_stop empty rather than inventing one.

Do not invent events or rules. Leave the Writer freedom over natural dialogue, gestures, pacing, transitions, and connective actions. max_attempts is 3. Output JSON only.
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

    try:
        result = extract_json_object(output)
    except ValueError as exc:
        raise SceneContractResponseError(
            f"{task_name} did not return a valid JSON object."
        ) from exc
    if not isinstance(result, dict):
        raise SceneContractResponseError(
            f"{task_name} did not return a JSON object."
        )
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


def _run_validator(
    model: Path,
    prompt: str,
    engine: Any = None,
    *,
    system_prompt: str = VALIDATOR_SYSTEM_PROMPT,
) -> dict[str, Any]:
    if engine is not None and _engine_is_running(engine):
        timeout_seconds = max(60, int(os.environ.get("STORY_VALIDATOR_TIMEOUT", "300")))
        return _run_with_existing_engine(
            engine,
            model,
            system_prompt,
            prompt,
            context_size=int(os.environ.get("STORY_VALIDATOR_CONTEXT", "6144")),
            max_tokens=int(os.environ.get("STORY_VALIDATOR_MAX_TOKENS", "1500")),
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
        "--n-predict", os.environ.get("STORY_VALIDATOR_MAX_TOKENS", "1500"),
        "--system-prompt", system_prompt,
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

    try:
        result = extract_json_object(output)
    except ValueError as exc:
        raise SceneContractResponseError(
            "Scene-contract validator did not return a valid JSON object."
        ) from exc
    if not isinstance(result, dict):
        raise SceneContractResponseError(
            "Scene-contract validator did not return a JSON object."
        )

    raw_pass = result.get("pass", None)
    if isinstance(raw_pass, bool):
        passed = raw_pass
    elif isinstance(raw_pass, str) and raw_pass.strip().casefold() in {"true", "false"}:
        passed = raw_pass.strip().casefold() == "true"
    else:
        raise SceneContractResponseError("Scene contract validator returned an invalid 'pass' value.")

    missed = result.get("missed_beats", [])
    violations = result.get("violations", [])
    if not isinstance(missed, list):
        raise SceneContractResponseError("Scene contract validator returned invalid missed_beats data.")
    if not isinstance(violations, list):
        raise SceneContractResponseError("Scene contract validator returned invalid violations data.")

    notes = str(result.get("notes", "") or "").strip()

    normalized_result = {
        "pass": passed,
        "missed_beats": [str(x).strip() for x in missed if str(x).strip()],
        "violations": [str(x).strip() for x in violations if str(x).strip()],
        "notes": notes,
    }
    checks = result.get("checks")
    if checks is not None:
        if not isinstance(checks, list):
            raise SceneContractResponseError(
                "Scene contract validator returned invalid checks data."
            )
        normalized_result["checks"] = checks
    return normalized_result


def _evidence_occurs_in_prose(prose: str, evidence: str) -> bool:
    """Require validator evidence to be a verbatim excerpt from the completed scene."""
    def normalize(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip().casefold()

    normalized_evidence = normalize(evidence)
    return bool(normalized_evidence and normalized_evidence in normalize(prose))


def _normalize_check_status(value: Any) -> str | None:
    """Normalize common model wording without accepting ambiguous validation labels."""
    status = re.sub(r"[\s_-]+", " ", str(value or "").strip().casefold())
    status = re.sub(r"[.!:;]+$", "", status).strip()
    if status in {"met", "present", "satisfied", "fulfilled", "passed", "pass", "true"}:
        return "met"
    if status in {
        "missing", "missed", "not met", "not present", "unmet", "not satisfied",
        "not fulfilled", "partially met", "partially satisfied", "absent", "omitted",
        "not found", "failed", "fail", "false",
    }:
        return "missing"
    return None


def _semantic_recheck_checks(
    model: Path,
    engine: Any,
    prose: str,
    checks: list[dict[str, str]],
    *,
    batch_size: int = 6,
) -> list[dict[str, str]]:
    """Reassess a suspicious wall of missing checks in small, meaning-focused batches."""
    reviewed: list[dict[str, str]] = []
    for offset in range(0, len(checks), batch_size):
        batch = checks[offset:offset + batch_size]
        requirements = [item["requirement"] for item in batch]
        base_prompt = (
            "SEMANTIC COVERAGE RECHECK. The first pass marked this batch missing. "
            "Reassess each item independently; do not assume the first result was right. "
            "Compare meaning, not keyword overlap. A 'red car' can be described as a "
            "'maroon sedan' and still satisfy the requirement when the context supports it. "
            "The evidence quote must be copied exactly from the completed scene, but it does "
            "not have to reuse the requirement's wording. Keep the requirement unchanged. "
            "If the meaning is present through a clear paraphrase, mark met. If a defining "
            "detail or the action itself is absent or materially different, mark missing. "
            "Return one check for each item in the order supplied, using the exact requirement text.\n\n"
            "CHECKLIST ITEMS TO REASSESS:\n"
            + json.dumps(requirements, ensure_ascii=False)
            + "\n\nCOMPLETED SCENE (the only evidence source):\n"
            + prose.strip()
            + '\n\nReturn one complete JSON object with this shape: '
            + '{"pass": true, "missed_beats": [], "violations": [], '
              '"checks": [{"requirement": "", "status": "met", "evidence": ""}], "notes": ""}. '
              'For this focused recheck, the "checks" array is the result that matters.'
        )
        validation_prompt = base_prompt
        response_correction_used = False
        evidence_correction_used = False
        accepted: list[dict[str, str]] | None = None
        for _attempt in range(3):
            try:
                active_engine = engine if _engine_is_running(engine) else None
                raw = _run_validator(
                    Path(model),
                    validation_prompt,
                    engine=active_engine,
                    system_prompt=SEMANTIC_RECHECK_SYSTEM_PROMPT,
                )
                raw_checks = raw.get("checks") if isinstance(raw, dict) else None
                if not isinstance(raw_checks, list) or len(raw_checks) != len(batch):
                    raise SceneContractResponseError(
                        "Semantic recheck did not return one check per supplied requirement."
                    )
                candidate: list[dict[str, str]] = []
                ungrounded: list[str] = []
                malformed = False
                for index, item in enumerate(raw_checks):
                    if not isinstance(item, dict):
                        malformed = True
                        break
                    status = _normalize_check_status(item.get("status"))
                    evidence = str(item.get("evidence", "") or "").strip()
                    if status is None:
                        malformed = True
                        break
                    requirement = requirements[index]
                    if status == "met" and not _evidence_occurs_in_prose(prose, evidence):
                        ungrounded.append(requirement)
                    candidate.append({
                        "requirement": requirement,
                        "status": status,
                        "evidence": evidence if status == "met" else "",
                    })
                if malformed:
                    raise SceneContractResponseError(
                        "Semantic recheck returned an invalid requirement status."
                    )
                if ungrounded:
                    if not evidence_correction_used:
                        evidence_correction_used = True
                        validation_prompt = (
                            base_prompt
                            + "\n\nEVIDENCE CORRECTION REQUIRED. A met check had a quote "
                            "that was not copied verbatim from the completed scene. Reassess "
                            "this batch, keep each requirement unchanged, and quote exact prose "
                            "only. If no direct quote proves the full requirement, mark it missing "
                            "with empty evidence.\n\nVERBATIM EVIDENCE SOURCE:\n"
                            + prose.strip()
                        )
                        continue
                    raise SceneContractValidationUnavailable(
                        "The focused semantic recheck could not ground its evidence in the completed scene. "
                        "The generated draft is preserved but remains unvalidated."
                    )
                accepted = candidate
                break
            except SceneContractResponseError as exc:
                if not response_correction_used:
                    response_correction_used = True
                    validation_prompt = (
                        base_prompt
                        + "\n\nCORRECTION REQUIRED: "
                        + str(exc)
                        + " Return one complete JSON object only, with exactly one check per "
                          "supplied requirement. Use the exact requirement text and a JSON "
                          "status of met or missing. For met checks, evidence must be an exact "
                          "quote from the completed scene."
                    )
                    continue
                raise SceneContractValidationUnavailable(
                    "The focused semantic recheck returned an unreadable or malformed response. "
                    "The generated draft is preserved but remains unvalidated."
                ) from exc
        if accepted is None:
            raise SceneContractValidationUnavailable(
                "The focused semantic recheck did not produce a usable result. "
                "The generated draft is preserved but remains unvalidated."
            )
        reviewed.extend(accepted)
    return reviewed


def _capitalized_names(text: str) -> set[str]:
    """Find likely character names without treating sentence starters as people."""
    sentence_words = {
        "After", "All", "Also", "Although", "And", "Author", "Before", "But",
        "Chapter", "Current", "Do", "End", "He", "Here", "If", "In", "It",
        "Keep", "Later", "Let", "Neither", "No", "Only", "Priority", "Required",
        "Scene", "She", "Supporting", "The", "Their", "Then", "There", "These",
        "They", "This", "Those", "Treat", "Use", "We", "When", "While", "You",
    }
    return {
        name for name in re.findall(r"\b[A-Z][a-z]+\b", str(text or ""))
        if name not in sentence_words
    }


def _compact_validator_guidance(
    guidance: str,
    author_idea: str,
    scene_cast: list[str],
    *,
    max_chars: int = 1600,
) -> str:
    """Keep only guidance relevant to the current idea instead of crowding the validator."""
    source = str(guidance or "").strip()
    if len(source) <= max_chars:
        return source

    names = {str(name).strip() for name in scene_cast if str(name).strip()}
    names.update(_capitalized_names(author_idea))
    stopwords = {
        "about", "after", "again", "also", "being", "before", "begins", "bring",
        "calls", "cannot", "character", "characters", "comes", "could", "does",
        "during", "each", "ending", "everything", "explicit", "first", "from",
        "gets", "give", "given", "gives", "going", "have", "having", "into",
        "later", "leave", "lets", "make", "makes", "making", "maybe", "moment",
        "natural", "ordinary", "other", "over", "preserve", "scene", "should",
        "since", "small", "some", "story", "such", "that", "their", "there",
        "these", "they", "this", "those", "through", "time", "very", "while",
        "with", "without", "would", "your",
    }
    idea_terms = {
        word.casefold() for word in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", author_idea)
        if word.casefold() not in stopwords
    }

    candidates: list[tuple[int, int, str]] = []
    for index, line in enumerate(source.splitlines()):
        line = line.strip()
        if not line or not line.startswith(("-", "*")):
            continue
        folded = line.casefold()
        name_hits = sum(
            1 for name in names
            if re.search(r"(?<!\w)" + re.escape(name.casefold()) + r"(?!\w)", folded)
        )
        line_words = {
            word.casefold() for word in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", line)
        }
        topic_hits = len(idea_terms & line_words)
        score = name_hits * 8 + min(topic_hits, 8)
        if any(phrase in folded for phrase in (
            "current story state", "only characters explicitly listed",
            "do not import details from discarded drafts",
            "do not introduce floral scents",
        )):
            score += 12
        if score:
            candidates.append((score, index, line))

    chosen: set[int] = set()
    used = 0
    for _score, index, line in sorted(candidates, key=lambda item: (-item[0], item[1])):
        addition = len(line) + (1 if used else 0)
        if used + addition <= max_chars:
            chosen.add(index)
            used += addition
    if not chosen:
        return source[:max_chars].rsplit("\n", 1)[0]

    return "\n".join(
        line.strip()
        for index, line in enumerate(source.splitlines())
        if index in chosen
    )


def _compact_validation_state(
    current_state: dict[str, Any],
    scene_cast: list[str],
    author_idea: str,
) -> dict[str, Any]:
    """Retain the scene opening and relevant character knowledge, not the full state dump."""
    relevant_names = {str(name).strip() for name in scene_cast if str(name).strip()}
    relevant_names.update(_capitalized_names(author_idea))
    keys = (
        "chapter", "scene", "status", "scene_completed", "location", "time",
        "time_of_day", "scene_cast", "current_situation", "physical_state",
        "character_knowledge", "active_objectives",
    )
    compact: dict[str, Any] = {}
    for key in keys:
        if key not in current_state:
            continue
        value = current_state[key]
        if key in {"location", "physical_state", "character_knowledge", "active_objectives"} and isinstance(value, dict):
            # Older scene states may not have a scene_cast field. Preserve their
            # supplied continuity data rather than accidentally stripping it all.
            if not scene_cast:
                compact[key] = dict(value)
            elif key == "location":
                compact[key] = {
                    name: detail for name, detail in value.items()
                    if name == "primary" or name in relevant_names
                }
            elif key in {"character_knowledge", "active_objectives"}:
                # Only participating characters' knowledge/objectives affect this scene's dialogue.
                compact[key] = {
                    name: detail for name, detail in value.items()
                    if name in relevant_names and name in scene_cast
                }
            else:
                compact[key] = {
                    name: detail for name, detail in value.items()
                    if name in relevant_names
                }
        else:
            compact[key] = value
    return compact


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
    # An inline End / HARD STOP paragraph is a complete endpoint. A following
    # blank-line-separated author note should not leak into the Writer's End
    # field merely because it has no heading of its own.
    active_end_is_inline = False

    for raw_line in str(scene_idea or "").splitlines():
        line = raw_line.strip()
        if not line:
            if active_section == "end" and active_end_is_inline:
                active_section = None
                active_end_is_inline = False
            elif active_section:
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
        if section is None and "/" in candidate:
            # Labels such as "End / HARD STOP" name one section using two
            # equivalent terms. Accept slash-combinations only when every
            # component resolves to the same section; "Beginning / Middle"
            # remains intentionally ambiguous and is not collapsed.
            components = [part.strip() for part in candidate.split("/") if part.strip()]
            component_sections = [_AUTHOR_SECTION_ALIASES.get(part) for part in components]
            if (
                len(components) > 1
                and all(component_sections)
                and len(set(component_sections)) == 1
            ):
                section = component_sections[0]

        # A heading without a colon must be a standalone label. This avoids
        # treating ordinary prose beginning with "End" or "Required" as a label.
        standalone_heading = ":" not in header and not inline_value
        if section and (not standalone_heading or candidate in _AUTHOR_SECTION_ALIASES):
            active_section = section
            active_end_is_inline = section == "end" and bool(inline_value.strip())
            collected.setdefault(active_section, [])
            if inline_value.strip():
                # In Markdown headings like "**End / HARD STOP:** End here",
                # the closing emphasis marker sits at the start of inline_value.
                # Strip that formatting residue so it does not reach Writer.
                clean_inline_value = re.sub(r"^[*_]{1,3}\s*", "", inline_value).strip()
                if clean_inline_value:
                    collected[active_section].append(clean_inline_value)
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
    def has_saved_contract(guidance: dict[str, Any] | None) -> bool:
        """Return whether a guidance entry contains a meaningful saved contract.

        This deliberately ignores the author Scene Idea by itself: a plain-idea
        scene with no generated fields can be built without an overwrite warning.
        """
        if not isinstance(guidance, dict):
            return False

        for key in ("direction", "end_condition", "hard_stop"):
            if str(guidance.get(key, "") or "").strip():
                return True

        contract = guidance.get("scene_contract")
        if not isinstance(contract, dict):
            return False

        if str(contract.get("hard_stop", "") or "").strip():
            return True

        for key in (
            "required_beats",
            "required_facts",
            "required_sequence",
            "forbidden",
            "forbidden_details",
        ):
            values = contract.get(key)
            if isinstance(values, list) and any(str(value).strip() for value in values):
                return True

        return False

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
            "BUILD A MINIMAL SCENE CONTRACT.\n\n"
            "AUTHOR SCENE IDEA:\n"
            + idea
            + "\n\nCURRENT STORY STATE AT SCENE START:\n"
            + json.dumps(contract_state, ensure_ascii=False, separators=(",", ":"))
            + "\n\nCreate the contract now. Keep it minimal.\n"
        )

        if engine is not None and _engine_is_running(engine):
            raw = _run_contract_builder(model, prompt, engine=engine)
        else:
            raw = _run_contract_builder(model, prompt)

        authored_sections = extract_authored_scene_sections(idea)
        result = {
            "direction": str(raw.get("direction", "") or "").strip(),
            "hard_stop": str(raw.get("hard_stop", "") or "").strip(),
            # Model-generated beat lists must never become mandatory. Only the
            # author's clearly labeled Required Beats are carried into the contract.
            "required_beats": list(authored_sections.get("required_beats", [])),
            "max_attempts": raw.get("max_attempts", 3),
        }

        for key in ("required_beats",):
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
        """Build the small runtime contract from positive beats and one ending."""
        source = guidance if isinstance(guidance, dict) else {}
        explicit = source.get("scene_contract")
        if "scene_contract" in source and explicit is not None and not isinstance(explicit, dict):
            raise ValueError("Scene guidance 'scene_contract' must be an object.")

        contract = dict(explicit) if isinstance(explicit, dict) else {}
        if isinstance(contract.get("required_beats"), list):
            # Avoid mutating the author's saved list when active module beats
            # are merged into this working copy.
            contract["required_beats"] = list(contract["required_beats"])

        # Auxiliary fields are intentionally ignored by the runtime contract.
        # Shorter prompts with one set of positive beats have worked better with
        # the author's local model than multiple overlapping validation gates.
        for key in (
            "required_facts",
            "required_sequence",
            "forbidden",
            "forbidden_details",
            "state_after",
            "local_hard_checks",
            "author_idea",
        ):
            contract.pop(key, None)

        # Preserve the author's exact plain-English paragraph as source material
        # for the Writer and validator. Never rely on the model's summary to carry it.
        author_idea = str(source.get("scene_idea", "") or "").strip()
        if author_idea:
            contract["author_idea"] = author_idea
            # Previously generated contract beats are not author requirements.
            # Re-derive the mandatory list from clearly labeled author input so
            # old saved contracts cannot keep enforcing an AI-written checklist.
            contract["required_beats"] = list(
                extract_authored_scene_sections(author_idea).get("required_beats", [])
            )

        def append_beats(values: Any) -> None:
            if not isinstance(values, list):
                return
            existing = contract.setdefault("required_beats", [])
            if not isinstance(existing, list):
                existing = []
                contract["required_beats"] = existing
            seen = {
                str(item).strip().casefold()
                for item in existing
                if str(item).strip()
            }
            for value in values:
                item = str(value).strip()
                if item and item.casefold() not in seen:
                    existing.append(item)
                    seen.add(item.casefold())

        # Legacy/generated event lists are usable only when there is no
        # original Scene Idea from which to determine author intent. When an
        # idea exists, its explicit Required Beats above are authoritative.
        if not author_idea:
            append_beats(source.get("required_beats"))
            append_beats(source.get("required_events"))

        if not contract.get("hard_stop"):
            end_condition = source.get("hard_stop") or source.get("end_condition")
            if end_condition:
                contract["hard_stop"] = str(end_condition).strip()

        if "max_attempts" not in contract and "max_attempts" in source:
            contract["max_attempts"] = source["max_attempts"]

        for module in module_guidance or []:
            if not isinstance(module, dict):
                continue

            nested = module.get("scene_contract")
            if isinstance(nested, dict):
                append_beats(nested.get("required_beats"))
                if not contract.get("hard_stop") and nested.get("hard_stop"):
                    contract["hard_stop"] = str(nested["hard_stop"]).strip()

            # Active modules may contribute positive events, but their
            # forbidden/do_not_advance and auxiliary fields are not gates.
            append_beats(module.get("required_events"))
            if not contract.get("hard_stop"):
                end_condition = module.get("hard_stop") or module.get("end_condition")
                if end_condition:
                    contract["hard_stop"] = str(end_condition).strip()

        # Keep only the fields that are useful for the writer and validator.
        contract = {
            key: contract[key]
            for key in ("author_idea", "direction", "required_beats", "hard_stop", "max_attempts")
            if key in contract
        }
        if not contract:
            return {}

        errors = SceneContract.lint(contract)
        if errors:
            raise ValueError(
                "Invalid scene contract:\n- " + "\n- ".join(errors)
            )
        return contract

    @staticmethod
    def writer_prompt_context(direction: str, contract: dict[str, Any]) -> str:
        """Put the author's Scene Idea first; generated summaries only support it."""
        parts = []
        author_idea = str(contract.get("author_idea", "") or "").strip()
        if author_idea:
            parts.append(
                "AUTHOR'S ORIGINAL PLAIN-ENGLISH SCENE IDEA (PRIMARY INTENT):\n"
                + author_idea
            )

        direction_text = str(direction or "").strip()
        if direction_text:
            parts.append(
                "CURRENT SCENE CONTEXT AND CONTINUITY (SUPPORTING ONLY):\n"
                + direction_text
            )

        supporting_contract = {
            key: contract[key]
            for key in ("required_beats", "hard_stop")
            if key in contract and contract[key] not in (None, "", [])
        }
        if supporting_contract:
            parts.append(
                "COMPACT SUPPORTING CONTRACT (SECONDARY):\n"
                + json.dumps(supporting_contract, ensure_ascii=False, separators=(",", ":"))
            )

        if author_idea:
            parts.append(
                "Priority: Treat the Scene Idea as the primary source for intended direction, key actions, "
                "important moments, and endpoint. It is not a word-for-word prose checklist. Generated "
                "direction and contract are supporting hints and must not overrule or contradict the author's intent. "
                "AUTHOR ACTION FIDELITY: Concrete actions and objects the idea specifies as intended choices "
                "must keep their identity. Do not replace one with a materially different alternative just "
                "because it serves the same broad purpose: a bubble bath is not a shower, and an explicitly "
                "required robe is not a towel. Natural dialogue, gestures, pacing, transitions, and connective "
                "details remain creative choices. Treat wording such as 'can' or 'may' as permission when the "
                "idea presents an option, not as an extra hard requirement."
            )

        # Place these reminders close to the actual write request. A compact
        # contract may focus on one notable action, but that focus must not
        # replace the author's intended whole scene.
        parts.append(
            "SCENE SCOPE AND EVENT PROVENANCE:\n"
            "Treat the author's original Scene Idea as the scope of the whole scene. A concise generated "
            "direction may emphasize one action, but it must not shrink a broader scene to that action. "
            "When the idea calls for continuing thought, transition, or development beyond a highlighted "
            "moment, do not stop at that moment. If an explicit endpoint is named, including a time or "
            "passage-of-time boundary, carry the scene through to it. Let intervening time pass naturally "
            "through relevant thought, small actions, or transitions; do not pad the scene, invent "
            "consequential events, or continue past the endpoint into the next scene. Use a natural "
            "stopping point only when the idea leaves the endpoint open.\n"
            "Knowing that an event happened is not the same as witnessing it. Only present sights, sounds, "
            "smells, dialogue, or actions as a character's personal memory if the story establishes that the "
            "character was present and witnessed them. If the character learned about an event second-hand, "
            "frame references as what they were told or can reasonably infer; never transfer another character's "
            "eyewitness experience."
        )
        return "\n\n".join(parts)

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
        author_guidance: str = "",
        model_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Validate the scene contract plus stable author guidance, when relevant."""
        if not isinstance(contract, dict) or not contract:
            return {"pass": True, "missed_beats": [], "violations": [], "notes": ""}

        # The active contract is deliberately minimal. Ignore legacy or
        # generated auxiliary fields so they cannot become extra validation gates.
        contract = {
            key: contract[key]
            for key in ("author_idea", "direction", "required_beats", "hard_stop", "max_attempts")
            if key in contract
        }
        if not contract:
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

        # Automatic validation is intentionally limited to the minimal
        # contract fields above. No auxiliary regex or prohibition gates run.

        # Only semantic requirements belong in the validator prompt. The
        # local_hard_checks section is implementation detail, not prose
        # wording that the model should be forced to reproduce.
        semantic_contract = {
            key: contract[key]
            for key in ("author_idea", "direction", "required_beats", "hard_stop")
            if key in contract
        }
        requires_coverage = bool(str(semantic_contract.get("author_idea", "") or "").strip())

        # Keep only state fields needed to verify opening continuity and knowledge.
        # Large unrelated state/history payloads make local validation slower.
        raw_scene_cast = current_state.get("scene_cast", [])
        scene_cast = (
            [str(name).strip() for name in raw_scene_cast if str(name).strip()]
            if isinstance(raw_scene_cast, list)
            else []
        )
        author_idea = str(semantic_contract.get("author_idea", "") or "").strip()
        validation_state = _compact_validation_state(
            current_state, scene_cast, author_idea
        )

        stable_guidance_text = _compact_validator_guidance(
            author_guidance, author_idea, scene_cast
        )
        guidance_section = (
            "\n\nRELEVANT AUTHOR GUIDANCE (compact excerpt; idea and state remain authoritative):\n"
            + stable_guidance_text
            if stable_guidance_text
            else ""
        )
        supporting_contract = {
            key: value for key, value in semantic_contract.items()
            if key != "author_idea"
        }
        idea_section = (
            "AUTHOR'S ORIGINAL SCENE IDEA (PRIMARY VALIDATION SOURCE):\n"
            + author_idea
            + "\n\n"
            if author_idea
            else ""
        )

        prompt = (
            idea_section
            + "VALIDATOR TASK:\n"
            + "Validate against the author's original idea, relevant author guidance, and starting state. "
            + "The idea is primary; generated hints are secondary. "
            + "Treat Required Beats as narrative-level goals, not a word-for-word checklist. "
            + "A specified bubble bath replaced with a shower is a material substitution; preserve defining objects, source locations, order, and history. "
            + "Check explicit requests, preferences, boundaries, or needs against later actions; flag ignored acknowledgments. "
            + "Report material omissions, substitutions, sequence/location errors, or ignored requests. "
            + "If the main action occurs but only a purely incidental detail is missing, do not fail for that alone; optional details may go in notes. "
            + "Search the whole scene for paraphrases before marking missing. Judge meaning, not keywords. Evidence must be verbatim scene prose, but need not reuse requirement words. "
            + "Do not fail for a minor descriptive or phrasing omission when the intended event, character knowledge, and endpoint remain intact unless a defining action, object, location, or acknowledged request changes. "
            + "Create a SHORT event-level checklist, usually 4–8 checks. Group related details; do not make micro-checks for each clause, adjective, person, object, or small action. Separate events only when their outcomes can be missing independently. "
            + "Judge each event against the entire scene, using meaning rather than keyword overlap. Fail only for a missing or materially changed event, its defining detail, an explicit boundary/request, or the scene endpoint; minor descriptive omissions alone do not fail. "
            + "For each event check, provide requirement, status, and a direct quote from COMPLETED SCENE only. It must support the event; never quote the idea or state. If absent or materially different, mark missing with empty evidence. "
            + "If an author idea is present, return a concise non-empty event checklist; pass must be false if any event check is missing. Report material continuity or character-knowledge conflicts separately as violations. "
            + "Return JSON only in this shape: "
            + '{"pass": true, "missed_beats": [], "violations": [], "checks": [{"requirement": "", "status": "met", "evidence": ""}], "notes": ""}'
            + guidance_section
            + "\n\nSUPPORTING SCENE DIRECTION AND CONTRACT (SECONDARY):\n"
            + json.dumps(supporting_contract, ensure_ascii=False, separators=(",", ":"))
            + "\n\nSTARTING STATE (relevant fields only):\n"
            + json.dumps(validation_state, ensure_ascii=False, separators=(",", ":"))
            + "\n\nCOMPLETED SCENE:\n"
            + prose.strip()
        )

        model = model_path if model_path is not None else getattr(engine, "model_path", None)
        if model is None:
            raise RuntimeError("The active writer model is unavailable for scene validation.")
        model = Path(model).expanduser()

        validation_prompt = prompt
        normalized_result = None
        # Schema/shape failures and ungrounded evidence are independent failure modes.
        # A correction for one must not consume the correction budget for the other.
        response_correction_used = False
        evidence_correction_used = False
        for validator_attempt in range(3):
            try:
                if _engine_is_running(engine):
                    raw_result = _run_validator(
                        Path(model), validation_prompt, engine=engine
                    )
                else:
                    raw_result = _run_validator(Path(model), validation_prompt)

                # Keep the public API stable even when validators are mocked or
                # alternate engines return JSON booleans as strings.
                if not isinstance(raw_result, dict):
                    raise SceneContractResponseError(
                        "Scene-contract validator returned an invalid result object."
                    )

                raw_pass = raw_result.get("pass", None)
                if isinstance(raw_pass, bool):
                    passed = raw_pass
                elif isinstance(raw_pass, str) and raw_pass.strip().casefold() in {"true", "false"}:
                    passed = raw_pass.strip().casefold() == "true"
                else:
                    raise SceneContractResponseError(
                        "Scene-contract validator returned an invalid 'pass' value."
                    )

                missed = raw_result.get("missed_beats", [])
                violations = raw_result.get("violations", [])
                if not isinstance(missed, list):
                    raise SceneContractResponseError(
                        "Scene-contract validator returned invalid missed_beats data."
                    )
                if not isinstance(violations, list):
                    raise SceneContractResponseError(
                        "Scene-contract validator returned invalid violations data."
                    )

                checks = raw_result.get("checks")
                if requires_coverage and (not isinstance(checks, list) or not checks):
                    raise SceneContractResponseError(
                        "Scene-contract validator did not return a concise event-level checklist."
                    )
                if checks is not None and not isinstance(checks, list):
                    raise SceneContractResponseError(
                        "Scene-contract validator returned invalid checks data."
                    )

                normalized_checks = []
                ungrounded_evidence = []
                for item in checks or []:
                    if not isinstance(item, dict):
                        raise SceneContractResponseError(
                            "Scene-contract validator returned an invalid check item."
                        )
                    requirement = str(item.get("requirement", "") or "").strip()
                    status = _normalize_check_status(item.get("status"))
                    evidence = str(item.get("evidence", "") or "").strip()
                    if not requirement or status is None:
                        raise SceneContractResponseError(
                            "Scene-contract validator returned an invalid requirement check."
                        )
                    # A claimed "met" result must cite the completed scene itself.
                    # Evidence copied from instructions, idea, or state is not grounded.
                    if status == "met" and not _evidence_occurs_in_prose(prose, evidence):
                        ungrounded_evidence.append(requirement)
                    normalized_checks.append({
                        "requirement": requirement,
                        "status": status,
                        "evidence": evidence if status == "met" else "",
                    })

                # If the event-level checklist is overwhelmingly marked missing, independently
                # recheck it in small batches before asking the writer to revise a scene.
                missing_count = sum(item["status"] == "missing" for item in normalized_checks)
                should_semantically_recheck = (
                    not ungrounded_evidence
                    and requires_coverage
                    and len(normalized_checks) >= 4
                    and missing_count / len(normalized_checks) >= 0.75
                )
                if should_semantically_recheck:
                    normalized_checks = _semantic_recheck_checks(
                        Path(model), engine, prose, normalized_checks
                    )
                    missed = [
                        item["requirement"]
                        for item in normalized_checks
                        if item["status"] == "missing"
                    ]
                    passed = not missed and not violations

                if ungrounded_evidence:
                    if not evidence_correction_used:
                        evidence_correction_used = True
                        validation_prompt = (
                            prompt
                            + "\n\nTARGETED EVIDENCE CORRECTION REQUIRED:\n"
                            + "Your previous response marked one or more checks met using evidence that does not occur verbatim in the completed scene. Reassess the entire scene. For every met check, quote only exact text from the following EVIDENCE SOURCE. The author's idea, validator instructions, supporting direction/contract, and starting state are not scene prose and must never be quoted as evidence. If no exact quote from the EVIDENCE SOURCE directly supports the full requirement, use status 'missing' and evidence empty. Do not rewrite the scene. Return only the requested JSON object.\n\n"
                            + "EVIDENCE SOURCE (only this passage may be quoted):\n"
                            + prose.strip()
                        )
                        continue
                    raise SceneContractValidationUnavailable(
                        "Scene-contract validation is unavailable because the validator again supplied evidence "
                        "that does not appear verbatim in the completed scene. The generated draft is preserved "
                        "but has not been semantically validated. Review it carefully before deciding whether "
                        "to accept it."
                    )

                normalized_result = {
                    "pass": passed,
                    "missed_beats": [
                        str(item).strip() for item in missed if str(item).strip()
                    ],
                    "violations": [
                        str(item).strip() for item in violations if str(item).strip()
                    ],
                    "notes": str(raw_result.get("notes", "") or "").strip(),
                    "_checks": normalized_checks,
                }
                break
            except SceneContractResponseError as exc:
                if not response_correction_used:
                    response_correction_used = True
                    validation_prompt = (
                        prompt
                        + "\n\nCORRECTION REQUIRED: Your previous response failed this validation: "
                        + str(exc)
                        + ". The original idea and starting state are included earlier in this prompt; "
                        "do not claim they are absent. Re-evaluate those supplied inputs and the entire scene. "
                        "Return ONLY one complete JSON object with this shape: "
                        + '{"pass": true, "missed_beats": [], "violations": [], "checks": [{"requirement": "", "status": "met", "evidence": ""}], "notes": ""}'
                        + ". Use a JSON boolean for pass, arrays of strings for missed_beats "
                        "and violations, a checks array of requirement/status/evidence objects, "
                        "and a string for notes. For a supplied author idea, "
                        "use a short checklist of 4-8 meaningful scene events, group related details within each event, and use verbatim scene evidence. Do not use "
                        "Markdown fences or include any text before or after the JSON object."
                    )
                    continue
                raise SceneContractValidationUnavailable(
                    "Scene-contract validation could not be completed because the validator "
                    "returned an unreadable or malformed response twice. The generated draft "
                    "is preserved but has not been semantically validated. Review it carefully "
                    "before deciding whether to accept it."
                ) from exc

        if normalized_result is None:
            raise SceneContractValidationUnavailable(
                "Scene-contract validation did not return a usable result. The generated draft "
                "is preserved but has not been semantically validated."
            )

        passed = normalized_result["pass"]
        normalized_missed = normalized_result["missed_beats"]
        normalized_violations = normalized_result["violations"]
        notes = normalized_result["notes"]

        def _normalize_requirement(value: str) -> str:
            value = re.sub(
                r"^Author-intent requirement not evidenced:\s*",
                "",
                str(value or ""),
                flags=re.IGNORECASE,
            )
            return re.sub(r"\s+", " ", value).strip(" .!?").casefold()

        existing_missed = {_normalize_requirement(item) for item in normalized_missed}
        for check in normalized_result.get("_checks", []):
            if check["status"] == "missing":
                requirement = check["requirement"]
                if _normalize_requirement(requirement) not in existing_missed:
                    message = f"Author-intent requirement not evidenced: {requirement}"
                    normalized_missed.append(message)
                    existing_missed.add(_normalize_requirement(requirement))

        # A validator response is internally inconsistent if it reports material
        # omissions/violations but still says pass=true. Never allow that result
        # to bypass the focused-revision loop.
        if passed and (normalized_missed or normalized_violations):
            passed = False
            consistency_note = "The validator reported material omissions or violations, so this draft cannot pass yet."
            notes = f"{notes} {consistency_note}".strip()

        return {
            "pass": passed,
            "missed_beats": normalized_missed,
            "violations": normalized_violations,
            "notes": notes,
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
            "The draft needs a focused revision.",
            "Address only the clear, material issue(s) listed below. Keep the parts of the draft that already work, including its voice, dialogue, pacing, and creative choices.",
            "Weave listed omissions into natural prose; do not turn the scene into an outline, add unrelated actions, or rewrite unaffected passages.",
        ]
        if missed:
            lines.append("Important omission(s) to address:")
            lines.extend(f"- {item}" for item in missed)
        if violations:
            lines.append("Material continuity issue(s) to correct:")
            lines.extend(f"- {item}" for item in violations)
        if notes:
            lines.append("Validator note:")
            lines.append(notes)
        return "\n".join(lines)


    @staticmethod
    def revision_prompt(base_prompt: str, previous_draft: str, feedback: str) -> str:
        """Build a focused revision prompt that preserves the previous draft as source material."""
        draft = str(previous_draft or "").strip()
        if not draft:
            return base_prompt.rstrip() + "\n\n" + str(feedback or "").strip()
        return (
            base_prompt.rstrip()
            + "\n\nFOCUSED REVISION\n"
            "Use the previous draft below as your starting point. Keep its successful prose, "
            "dialogue, pacing, and natural creative choices. Change only what is needed to fix "
            "the clear material issue(s) described after the draft. Preserve the identity of concrete "
            "actions and objects specified by the author's idea, including defining details and meaningful "
            "relationships; if feedback identifies one that was omitted or substituted, restore the intended "
            "choice rather than a near-equivalent. Add any "
            "missing explicit Required Beats named in the revision guidance, woven into natural prose "
            "rather than an outline or checklist. Do not rewrite unaffected passages. Return the complete "
            "revised scene only.\n\n"
            "PREVIOUS DRAFT:\n"
            + draft
            + "\n\nREVISION GUIDANCE:\n"
            + str(feedback or "").strip()
        )
