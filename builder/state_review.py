from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from builder.state_manager import extract_json_object


STATE_PROPOSAL_REVIEW_SYSTEM_PROMPT = """You are an independent reviewer of proposed story-state changes for a fiction novel.

Return JSON only:
{"findings":[{"field":"current_situation","title":"short concern","message":"plain-English explanation","edit_request":"smallest safe correction request"}]}

If the proposal is supported and preserves the important ongoing story situation, return {"findings":[]}.

Review the proposed change against the before-state, the complete accepted scene, and the author's guidance. The saved state is a fallible memory aid; the accepted prose is evidence of what actually happened.
- Check whether an important unresolved problem or danger from the before-state disappears from the new summary without being resolved on the page.
- Preserve uncertainty. Do not turn a projection, estimate, hypothesis, suspicious reading, or unverified clue into a confirmed fact.
- Do not state that a plan, intention, or requested inspection has already occurred unless the accepted prose shows it happened.
- Do not invent a cause, event, diagnosis, discovery, location, or character knowledge.
- The summary should carry forward the main plot and meaningful stakes, not every detail of the scene. Do not flag minor omissions or demand a full scene recap.
- Do not flag a difference merely because the wording changed. Judge meaning.
- Report only material concerns in a string field that actually exists in the proposed partial update. For the current main-plot summary, use field "current_situation".
- Do not rewrite the state yourself and do not add a pass/fail gate. Findings are advisory for author review.
- Never claim a value is incorrect merely because a detail is absent from a short summary unless that detail is materially important to the continuing plot.
- Return no more than five distinct findings. Avoid duplicate findings about the same underlying concern.
- Every finding needs a short title, a useful plain-English explanation, and a specific minimal correction request. Do not include suggested JSON or raw code.
"""


def iter_state_patch_text_fields(patch: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Return only text-valued leaves that are actually present in a proposed patch."""
    result: dict[str, str] = {}
    if not isinstance(patch, dict):
        return result
    for key, value in patch.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            result.update(iter_state_patch_text_fields(value, path))
        elif isinstance(value, str) and value.strip():
            result[path] = value
    return result


def get_state_patch_value(patch: dict[str, Any], path: str) -> Any:
    """Read one dotted field path from a proposed partial state update."""
    value: Any = patch
    for part in str(path or "").split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def set_state_patch_value(patch: dict[str, Any], path: str, value: str) -> None:
    """Update one existing string-valued leaf in a proposed patch, never saved state."""
    parts = str(path or "").split(".")
    if not parts or any(not part for part in parts):
        raise ValueError("The state finding did not identify a valid field.")
    target: Any = patch
    for part in parts[:-1]:
        if not isinstance(target, dict) or part not in target or not isinstance(target[part], dict):
            raise ValueError("The proposed state field no longer exists.")
        target = target[part]
    if not isinstance(target, dict) or not isinstance(target.get(parts[-1]), str):
        raise ValueError("Only an existing text field can receive this focused correction.")
    target[parts[-1]] = str(value)


def apply_state_text_replacement(original: str, target: str, replacement: str) -> str:
    """Replace one unique passage inside one proposed text field; full-field replacement is allowed."""
    original = str(original or "")
    target = str(target or "")
    replacement = str(replacement or "")
    if not original.strip():
        raise ValueError("The proposed state text is empty.")
    if not target.strip():
        raise ValueError("The state correction did not identify a target passage.")
    pieces = re.split(r"(\s+)", target)
    pattern = "".join(r"\s+" if piece and piece.isspace() else re.escape(piece) for piece in pieces)
    matches = list(re.finditer(pattern, original))
    if not matches:
        raise ValueError("The target passage does not appear in the current proposed state text.")
    if len(matches) != 1:
        raise ValueError("The target passage appears more than once in this state field.")
    match = matches[0]
    revised = original[:match.start()] + replacement + original[match.end():]
    if revised == original:
        raise ValueError("The proposed state correction would not change the value.")
    if not revised.strip():
        raise ValueError("A proposed state text field cannot be left empty.")
    return revised


def build_state_proposal_review_prompt(
    current_state: dict[str, Any],
    proposed_patch: dict[str, Any],
    accepted_scene: str,
    *,
    author_guidance: str = "",
    scene_idea: str = "",
) -> str:
    """Prompt an advisory audit of a proposed state transition."""
    before_fields = (
        "chapter", "scene", "current_situation", "time_of_day", "time",
        "unresolved_questions", "active_clues", "active_objectives",
    )
    before = {key: current_state[key] for key in before_fields if key in current_state}
    patch_fields = iter_state_patch_text_fields(proposed_patch)
    if not patch_fields:
        return ""
    return (
        "BEFORE STATE (relevant continuity baseline; not proof that old claims are true):\n"
        + json.dumps(before, ensure_ascii=False, indent=2)
        + "\n\nACCEPTED SCENE (the evidence for events that occurred):\n"
        + str(accepted_scene or "").strip()
        + "\n\nAUTHOR'S ORIGINAL SCENE IDEA / DIRECTION:\n"
        + str(scene_idea or "").strip()
        + "\n\nAUTHOR'S STABLE WRITING GUIDANCE:\n"
        + str(author_guidance or "").strip()
        + "\n\nPROPOSED STATE CHANGES (only these text-valued fields are editable findings):\n"
        + json.dumps(patch_fields, ensure_ascii=False, indent=2)
        + "\n\nPreserve uncertainty explicitly. Review the proposed changes now. Return {\"findings\":[]} if there is no material problem. "
        + "Each finding's field must be one of these paths: "
        + ", ".join(patch_fields)
        + ". The finding is advice, not an instruction to change the state. JSON only."
    )


def parse_state_proposal_review(response: str, proposed_patch: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse findings defensively; an audit cannot target fields outside the proposed patch."""
    payload = extract_json_object(response, required_keys={"findings"})
    raw_findings = payload.get("findings")
    if not isinstance(raw_findings, list):
        raise ValueError("The state reviewer did not return a findings list.")
    allowed = iter_state_patch_text_fields(proposed_patch)
    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in raw_findings[:5]:
        if not isinstance(raw, dict):
            continue
        field = str(raw.get("field", "") or "").strip()
        title = str(raw.get("title", "") or "").strip()
        message = str(raw.get("message", "") or "").strip()
        if field not in allowed or not title or not message:
            continue
        identity = (field.casefold(), message.casefold())
        if identity in seen:
            continue
        seen.add(identity)
        findings.append({
            "kind": "state",
            "field": field,
            "title": title[:180],
            "message": message[:1200],
            "edit_request": str(raw.get("edit_request", "") or "").strip()[:700],
            "can_suggest": True,
        })
    return findings


def review_state_proposal(
    *,
    engine: Any,
    model_path: str | os.PathLike[str],
    original_system_prompt: str,
    current_state: dict[str, Any],
    proposed_patch: dict[str, Any],
    accepted_scene: str,
    author_guidance: str = "",
    scene_idea: str = "",
    prompt_trace: Any | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Return review findings and an optional warning, never mutate the proposal."""
    patch_fields = iter_state_patch_text_fields(proposed_patch)
    if not patch_fields:
        return [], None
    prompt = build_state_proposal_review_prompt(
        current_state,
        proposed_patch,
        accepted_scene,
        author_guidance=author_guidance,
        scene_idea=scene_idea,
    )
    call_id = None
    started = None
    findings: list[dict[str, Any]] = []
    warning = None
    try:
        if prompt_trace is not None:
            prompt_trace.record_event("state_proposal_review_started", fields=list(patch_fields))
        engine.reset_context(model_path, STATE_PROPOSAL_REVIEW_SYSTEM_PROMPT)
        if prompt_trace is not None:
            prompt_trace.record_session(
                model_path=model_path,
                runtime_binary="configured llama-cli",
                system_prompt=STATE_PROPOSAL_REVIEW_SYSTEM_PROMPT,
                context_size=16384,
                max_tokens=1800,
                device=os.environ.get("STORY_LLM_DEVICE", "") or "CPU/default",
                runtime_options={"reasoning": "off", "task": "state_proposal_review"},
            )
            sent = " ".join(line.strip() for line in prompt.splitlines() if line.strip())
            call_id = prompt_trace.begin_generation(prompt=prompt, sent_prompt=sent)
        started = time.monotonic()
        response = engine.generate(prompt, timeout=1800)
        if prompt_trace is not None:
            prompt_trace.finish_generation(
                call_id=call_id,
                response=response,
                status="completed",
                duration_seconds=time.monotonic() - started,
            )
        findings = parse_state_proposal_review(response, proposed_patch)
        if prompt_trace is not None:
            prompt_trace.record_event("state_proposal_review_finished", findings=findings, warning=None)
    except Exception as exc:
        warning = str(exc).strip() or exc.__class__.__name__
        if prompt_trace is not None:
            try:
                prompt_trace.finish_generation(
                    call_id=call_id,
                    response="",
                    status="review_error",
                    error=warning,
                    duration_seconds=(time.monotonic() - started) if started is not None else None,
                )
                prompt_trace.record_event("state_proposal_review_finished", findings=[], warning=warning)
            except Exception:
                pass
        findings = []
    finally:
        try:
            engine.reset_context(model_path, original_system_prompt)
        except Exception as exc:
            restore_warning = "The Writer model context could not be restored after state review: " + str(exc).splitlines()[0]
            warning = (warning + "; " if warning else "") + restore_warning
            findings = []
    return findings, warning
