"""Bounded semantic completion and continuity recovery for generated scenes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from builder.scene_contract import SceneContract
from builder.state_manager import extract_json_object


INTEGRITY_AUDIT_SYSTEM_PROMPT = """You are an independent continuity and scope auditor. Do not write or rewrite prose.
Return JSON only: {"pass": true, "issues": []}.
Compare the scene with the author's Scene Idea, supporting direction, starting state, and stable author guidance.
Flag only material, evidence-based issues: timeline/event-order contradictions; characters shown present, witnessing, or knowing something that context rules out; consequential new actions/clues/claims when the author has restricted invention; explicit "do not"/"no one calls"/later-scene boundaries broken; or the hard stop materially exceeded.
Consult all supplied context before deciding something is unsupported. Do not treat absence from a short scene plan alone as proof a fact is false. Ordinary atmosphere, plausible gestures, dialogue, routine cooking details, and familiar household scents in a character's own home are not violations merely because they are not spelled out in the plan. Do not review missing beats or style preferences here. When uncertain, do not invent a violation. Each issue must briefly identify the material conflict. If any issue exists, pass=false and list each major issue once. Output valid JSON only.
"""


def _restore_writer_context(engine: Any, model_path: str | Path, system_prompt: str) -> bool:
    try:
        engine.reset_context(model_path, system_prompt)
        return True
    except Exception:
        return False


def _audit_prompt(scene_context, current_state, author_guidance, prose):
    return (
        "AUTHOR'S SCENE IDEA AND SUPPORTING DIRECTION:\n" + str(scene_context or "").strip()
        + "\n\nSTARTING STORY STATE:\n"
        + json.dumps(current_state, ensure_ascii=False, separators=(",", ":"))
        + "\n\nSTABLE AUTHOR GUIDANCE:\n" + str(author_guidance or "").strip()
        + "\n\nCOMPLETED SCENE TO AUDIT:\n" + str(prose or "").strip()
        + '\n\nReturn JSON only: {"pass": true, "issues": []}.'
    )


def _run_scene_integrity_audit(
    *, engine, model_path, writer_system_prompt, scene_context,
    current_state, author_guidance, prose
):
    """Audit continuity/scope and restore the persistent Writer prompt."""
    try:
        engine.reset_context(model_path, INTEGRITY_AUDIT_SYSTEM_PROMPT)
        raw = extract_json_object(
            engine.generate(_audit_prompt(scene_context, current_state, author_guidance, prose))
        )
    finally:
        if not _restore_writer_context(engine, model_path, writer_system_prompt):
            raise RuntimeError("Could not restore Writer after the integrity audit.")
    if not isinstance(raw, dict):
        raise ValueError("Integrity audit did not return a JSON object.")
    value = raw.get("pass")
    if isinstance(value, bool):
        passed = value
    elif isinstance(value, str) and value.strip().casefold() in {"true", "false"}:
        passed = value.strip().casefold() == "true"
    else:
        raise ValueError("Integrity audit returned an invalid pass value.")
    issues = raw.get("issues", [])
    if not isinstance(issues, list):
        raise ValueError("Integrity audit returned invalid issues.")
    issues = [str(x).strip() for x in issues if str(x).strip()]
    return {"pass": passed and not issues, "issues": issues}


def _clean_findings(review, field):
    raw = review.get(field, []) if isinstance(review, dict) else []
    return [str(x).strip() for x in raw if str(x).strip()] if isinstance(raw, list) else []


def _build_continuation_prompt(scene_context, existing_draft, missing_beats):
    missing = "\n".join(f"- {beat}" for beat in missing_beats)
    return (
        "CONTINUE THE EXISTING SCENE. DO NOT REWRITE IT.\n\n"
        "AUTHOR INTENT AND SUPPORTING CONTEXT:\n" + str(scene_context or "").strip()
        + "\n\nSEMANTIC REVIEW: These author-intended events appear missing:\n" + missing
        + "\n\nSCENE ALREADY WRITTEN (preserve verbatim; do not repeat or revise):\n"
        + str(existing_draft or "").strip()
        + "\n\nContinue directly after the final sentence, writing only new prose. Carry the scene "
        "naturally through its remaining phases to the stated hard stop. Do not jump beyond the "
        "endpoint, invent clues/events, or turn the list into a checklist. Do not force any item "
        "that conflicts with established facts or author intent."
    )


def _build_regeneration_prompt(initial_prompt, issues):
    findings = "\n".join(f"- {x}" for x in issues[:10])
    return (
        str(initial_prompt or "").strip()
        + "\n\nONE BOUNDED FULL-SCENE RETRY:\nAn independent review found these material conflicts:\n"
        + findings
        + "\nWrite the entire scene anew from the original author intent and starting state. Correct "
        "the conflicts rather than explaining them or appending to the prior version. Do not carry "
        "forward a claim merely because the previous attempt stated it. Preserve valid context, keep "
        "event chronology and character knowledge accurate, honor the hard stop, and do not introduce "
        "replacement clues or consequential actions. Output only complete scene prose."
    )


def generate_scene_with_completion_check(
    *, engine: Any, model_path: str | Path, writer_system_prompt: str,
    initial_prompt: str, scene_context: str, contract: dict[str, Any],
    current_state: dict[str, Any], author_guidance: str = "",
) -> tuple[str, str]:
    """Check coverage plus continuity; perform no more than one bounded recovery."""
    draft = str(engine.generate(initial_prompt) or "").strip()
    if not draft or not str((contract or {}).get("author_idea", "") or "").strip():
        return draft, ""

    try:
        review = SceneContract.validate_with_engine(
            engine=engine, contract=contract, current_state=current_state,
            prose=draft, author_guidance=author_guidance, model_path=model_path,
        )
    except Exception as exc:
        restored = _restore_writer_context(engine, model_path, writer_system_prompt)
        note = f"Scene completion check failed ({type(exc).__name__}); the original draft was preserved."
        if not restored:
            note += " Restart Writer before the next scene."
        return draft, note

    try:
        audit = _run_scene_integrity_audit(
            engine=engine, model_path=model_path, writer_system_prompt=writer_system_prompt,
            scene_context=scene_context, current_state=current_state,
            author_guidance=author_guidance, prose=draft,
        )
    except Exception as exc:
        _restore_writer_context(engine, model_path, writer_system_prompt)
        return draft, f"Continuity/scope audit failed ({type(exc).__name__}); the original draft was preserved."

    validator_issues = _clean_findings(review, "violations")
    audit_issues = _clean_findings(audit, "issues")
    issues = validator_issues + [
        x for x in audit_issues if x.casefold() not in {v.casefold() for v in validator_issues}
    ]
    if issues:
        try:
            limit = SceneContract.max_attempts(contract)
        except (TypeError, ValueError):
            limit = 3
        if limit < 2:
            _restore_writer_context(engine, model_path, writer_system_prompt)
            return draft, "A material continuity/scope issue was found, but the scene's retry limit prevents a full retry. Original draft preserved."
        if not _restore_writer_context(engine, model_path, writer_system_prompt):
            return draft, "A material continuity/scope issue was found, but Writer could not be restored. Original draft preserved."
        try:
            revised = str(engine.generate(_build_regeneration_prompt(initial_prompt, issues)) or "").strip()
            if not revised:
                return draft, "The full-scene retry returned no prose. Original draft preserved."
            revised_review = SceneContract.validate_with_engine(
                engine=engine, contract=contract, current_state=current_state,
                prose=revised, author_guidance=author_guidance, model_path=model_path,
            )
            revised_audit = _run_scene_integrity_audit(
                engine=engine, model_path=model_path, writer_system_prompt=writer_system_prompt,
                scene_context=scene_context, current_state=current_state,
                author_guidance=author_guidance, prose=revised,
            )
        except Exception as exc:
            _restore_writer_context(engine, model_path, writer_system_prompt)
            return draft, f"The full-scene retry could not be verified ({type(exc).__name__}). Original draft preserved."
        if (
            revised_review.get("pass") is True
            and not _clean_findings(revised_review, "missed_beats")
            and not _clean_findings(revised_review, "violations")
            and revised_audit.get("pass") is True
        ):
            return revised, "StoryBuilder found a material continuity/scope issue and regenerated the whole scene once. The revised draft passed follow-up checks; review it before accepting."
        _restore_writer_context(engine, model_path, writer_system_prompt)
        return draft, "The full-scene retry did not pass all follow-up checks. Original draft preserved for review."

    if audit.get("pass") is not True:
        _restore_writer_context(engine, model_path, writer_system_prompt)
        return draft, "The independent review could not confirm continuity/scope. Original draft preserved for review."

    if review.get("pass") is True:
        if _restore_writer_context(engine, model_path, writer_system_prompt):
            return draft, ""
        return draft, "Completion review passed, but Writer could not be restored. Restart Writer before the next scene."

    missed = _clean_findings(review, "missed_beats")
    if not missed:
        _restore_writer_context(engine, model_path, writer_system_prompt)
        return draft, "The planned endpoint was not confirmed. Original draft preserved for review."

    try:
        limit = SceneContract.max_attempts(contract)
    except (TypeError, ValueError):
        limit = 3
    if limit < 2:
        _restore_writer_context(engine, model_path, writer_system_prompt)
        return draft, "Planned events are missing, but the retry limit disables continuation. Original draft preserved."
    if not _restore_writer_context(engine, model_path, writer_system_prompt):
        return draft, "Planned events are missing, but Writer could not be restored. Original draft preserved."
    try:
        continuation = str(engine.generate(_build_continuation_prompt(scene_context, draft, missed[:8])) or "").strip()
    except Exception as exc:
        _restore_writer_context(engine, model_path, writer_system_prompt)
        return draft, f"Continuation failed ({type(exc).__name__}). Original draft preserved."
    if not continuation:
        _restore_writer_context(engine, model_path, writer_system_prompt)
        return draft, "No continuation was returned. Original draft preserved."
    combined = draft.rstrip() + "\n\n" + continuation.lstrip()
    try:
        combined_audit = _run_scene_integrity_audit(
            engine=engine, model_path=model_path, writer_system_prompt=writer_system_prompt,
            scene_context=scene_context, current_state=current_state,
            author_guidance=author_guidance, prose=combined,
        )
    except Exception as exc:
        _restore_writer_context(engine, model_path, writer_system_prompt)
        return draft, f"The continuation could not be audited ({type(exc).__name__}). Original draft preserved."
    if combined_audit.get("pass") is not True:
        _restore_writer_context(engine, model_path, writer_system_prompt)
        return draft, "The continuation introduced a possible continuity/scope conflict. Original draft preserved."
    return combined, "StoryBuilder added one continuation for missing planned events. Original prose was preserved; review the complete scene before accepting."
