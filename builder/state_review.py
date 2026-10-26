from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from builder.state_manager import extract_json_object


STATE_PROPOSAL_REVIEW_SYSTEM_PROMPT = """You are a careful, deliberately conservative reviewer of proposed story-state changes for a fiction novel. Prefer no finding over a weak or merely debatable finding.

Return JSON only:
{"findings":[{"field":"current_situation","title":"short material concern","message":"plain-English explanation","edit_request":"smallest safe correction request","scene_evidence":"exact short quote from the accepted scene supporting the concern","summary_evidence":"exact short quote from the proposed summary showing related existing coverage, or empty string if none exists"}]}

If the proposal preserves the important ongoing story situation and does not materially distort the accepted scene, return {"findings":[]}.

Review the proposed change against the before-state, the entire accepted scene from beginning to end, and the author's guidance. The before-state is a fallible baseline, not a checklist of details that must all be copied into every new summary. The accepted prose is evidence of what happened and what the latest plan now is.

- For every possible omission, inspect the full accepted scene, including dialogue and actions in the middle. Do not decide that a discovery, clue, ongoing task, or responsibility is absent based only on the opening, ending, or a general impression.
- Match meaning, not just wording. A discovery may be described in different words or occur in a different paragraph from the summary's phrasing.
- Distinguish these separate questions: what happened in the scene; what the proposed summary preserves; and what remains unresolved at scene end. Never claim that the scene does not mention something when the scene explicitly describes or discusses it.
- The proposed main-plot summary is intentionally concise, not a transcript or a character-by-character activity log. Do not demand that it repeat every contributor's name, every intermediate discovery, every log identifier, every diagnostic step, or each previous scene's active task.
- A newer decision or plan in the accepted scene may replace or supersede a prior instruction, investigation, or near-term objective. Do not flag an old instruction as missing merely because the new summary reflects the newer decision. Carry an earlier task forward only when the scene leaves it active and it materially changes the next scene's choices, risks, or action.
- Raise a finding about omitted information only when the detail is both genuinely missing or materially underrepresented in the proposed summary AND important to the continuing main crisis, deadline, available choices, risks, or next investigation. Ask whether leaving it out would likely cause the next scene to repeat events, contradict the accepted ending, lose an essential deadline or decision, or wrongly close an unresolved question. If not, do not flag it.
- A summary may preserve the essential result of several related observations without listing each character's contribution or the exact evidence trail. Do not treat less detail as an error when the central development and its uncertainty are represented.
- Do not require the summary to preserve a detail merely because it appeared in the before-state. Check whether the accepted scene changes, advances, or supersedes it. Do not resurrect an earlier plan when a newer decision is now controlling.
- Check whether an important unresolved danger or deadline from the before-state disappears without being resolved or superseded on the page. A shift in focus alone does not resolve an open danger, but a new concrete decision may change the active plan.
- Preserve uncertainty. Do not turn a projection, estimate, hypothesis, suspicious reading, possible timing match, or unverified clue into a confirmed fact or causal link.
- Do not state that a plan, intention, or requested inspection has already occurred unless the accepted prose shows it happened.
- Do not invent a cause, event, diagnosis, discovery, location, or character knowledge.
- Do not flag a difference merely because wording changed. Judge the whole meaning of the new summary in context, including what has been superseded.
- Every finding MUST include a concise, exact, verbatim excerpt in "scene_evidence" that supports the claimed event or concern. Do not paraphrase or invent this quote. If you cannot quote the accepted scene exactly, do not emit the finding.
- If the proposed summary contains related wording, include its exact excerpt in "summary_evidence". Use an empty string only when the summary genuinely has no related wording. Do not claim information is missing if the quoted summary already preserves its essential meaning.
- The evidence fields are internal grounding for the review. Keep quotes short and exact, without ellipses. Findings with missing, paraphrased, or unsupported evidence will be discarded.
- Report only material concerns in a string field that actually exists in the proposed partial update. For the current main-plot summary, use field "current_situation".
- Do not rewrite the state yourself and do not add a pass/fail gate. Findings are advisory for author review.
- Return no more than three distinct findings. Avoid duplicate findings about the same underlying concern.
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
        + ". Each finding must include an exact scene_evidence quote, and any nonempty summary_evidence must quote the proposed field exactly. The finding is advice, not an instruction to change the state. JSON only."
    )


def _contains_normalized_quote(source: str, quote: str, *, min_chars: int = 12) -> bool:
    """Require a substantial verbatim excerpt while tolerating line-wrap differences."""
    source_text = re.sub(r"\\s+", " ", str(source or "")).strip()
    quote_text = re.sub(r"\\s+", " ", str(quote or "")).strip()
    return bool(
        len(quote_text) >= min_chars
        and len(quote_text) <= 600
        and quote_text in source_text
    )


def parse_state_proposal_review(
    response: str,
    proposed_patch: dict[str, Any],
    *,
    accepted_scene: str = "",
) -> list[dict[str, Any]]:
    """Parse only material findings grounded in verbatim scene/summary evidence."""
    payload = extract_json_object(response, required_keys={"findings"})
    raw_findings = payload.get("findings")
    if not isinstance(raw_findings, list):
        raise ValueError("The state reviewer did not return a findings list.")
    allowed = iter_state_patch_text_fields(proposed_patch)
    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in raw_findings[:3]:
        if not isinstance(raw, dict):
            continue
        field = str(raw.get("field", "") or "").strip()
        title = str(raw.get("title", "") or "").strip()
        message = str(raw.get("message", "") or "").strip()
        scene_evidence = str(raw.get("scene_evidence", "") or "").strip()
        summary_evidence = str(raw.get("summary_evidence", "") or "").strip()
        if field not in allowed or not title or not message:
            continue
        # The review is advisory: unsupported claims are suppressed rather than
        # shown to the author as another correction task.
        if not _contains_normalized_quote(accepted_scene, scene_evidence):
            continue
        if summary_evidence and not _contains_normalized_quote(allowed[field], summary_evidence):
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
            "scene_evidence": scene_evidence[:600],
            "summary_evidence": summary_evidence[:600],
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
        findings = parse_state_proposal_review(
            response, proposed_patch, accepted_scene=accepted_scene
        )
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
