"""Bounded semantic completion and evidence-backed continuity recovery for scenes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from builder.scene_contract import SceneContract
from builder.state_manager import extract_json_object


AUDIT_CATEGORIES = (
    "timeline_and_event_order",
    "presence_and_character_knowledge",
    "physical_and_location_continuity",
    "unsupported_consequential_details",
    "scene_scope_and_hard_stop",
)

INTEGRITY_AUDIT_SYSTEM_PROMPT = """You are an independent continuity and scene-scope auditor for a novel draft. Do not rewrite the prose.
Return exactly one JSON object with this shape:
{
  "checks": {
    "timeline_and_event_order": {"status":"clear","reason":"brief reason","draft_evidence":"","source_evidence":""},
    "presence_and_character_knowledge": {"status":"clear","reason":"brief reason","draft_evidence":"","source_evidence":""},
    "physical_and_location_continuity": {"status":"clear","reason":"brief reason","draft_evidence":"","source_evidence":""},
    "unsupported_consequential_details": {"status":"clear","reason":"brief reason","draft_evidence":"","source_evidence":""},
    "scene_scope_and_hard_stop": {"status":"clear","reason":"brief reason","draft_evidence":"","source_evidence":""}
  }
}

Review all five categories independently and include every category exactly once. Each status must be "clear", "conflict", or "uncertain". Every check needs a short reason.
- "clear" means you checked the supplied evidence and found no material contradiction in that category.
- "conflict" means you found a material contradiction supported by BOTH a verbatim draft excerpt and a verbatim excerpt from the supplied author idea, starting-state JSON, or stable author guidance.
- "uncertain" means the supplied context does not let you verify the category confidently, or you cannot quote both sides of a possible conflict.
For a conflict, draft_evidence MUST be an exact contiguous substring of the completed scene. source_evidence MUST be an exact contiguous substring of one of the supplied context blocks. Do not paraphrase either evidence field. Never report a conflict without both exact excerpts. If evidence is missing or you are uncertain, mark that category "uncertain", not "conflict". Do not add a pass field or issues list.

Check specifically:
1. Timeline and event order: explicit day, time-of-day, before/after relationships, and whether the draft changes an established time or repeats an event already completed.
2. Presence and character knowledge: who is present or absent, who witnessed an event firsthand, who learned it secondhand, and what the character could know at this point.
3. Physical and location continuity: where people are, movement between locations, established clothing/sleepwear, and explicit privacy requirements such as changing clothes privately.
4. Unsupported consequential details: whether the draft presents a material new clue, injury, action, motive, identity, destination, or event as fact contrary to the context. An ordinary plausible detail is not automatically a problem merely because it is not listed.
5. Scene scope and hard stop: whether the draft goes beyond the specified endpoint, such as beginning a later investigation, assigning detailed tasks, adding training, or resolving something reserved for later.

Authority order: explicit author canon and instructions plus the original Scene Idea; the actual starting-state/current_situation and relevant character/location/knowledge data; then supporting generated directions. Read the relevant entries, not just the first lines. Absence from a short plan alone is not evidence that a detail is false. Preserve creative freedom for ordinary dialogue, plausible gestures, atmosphere, routine cooking details, and familiar household smells in someone's own home. Do not flag style preferences, length, or missing planned beats in this audit; a separate semantic check handles coverage. When source materials genuinely conflict or don't settle a material question, mark uncertain. A missing category, invalid schema, or unverifiable quote must never count as clear.
"""


def _restore_writer_context(engine: Any, model_path: str | Path, system_prompt: str) -> bool:
    try:
        engine.reset_context(model_path, system_prompt)
        return True
    except Exception:
        return False


def _audit_prompt(scene_context, current_state, author_guidance, prose):
    serialized_state = json.dumps(current_state, ensure_ascii=False, separators=(",", ":"))
    return (
        "AUTHOR'S ORIGINAL SCENE IDEA AND SUPPORTING DIRECTION (source block A):\n"
        + str(scene_context or "").strip()
        + "\n\nSTARTING STORY STATE JSON (source block B; inspect relevant fields including current_situation, "
        "location, time, character_knowledge, recent_events, physical_state, continuity_requirements and scene_cast):\n"
        + serialized_state
        + "\n\nSTABLE AUTHOR GUIDANCE (source block C):\n"
        + str(author_guidance or "").strip()
        + "\n\nCOMPLETED SCENE TO AUDIT:\n"
        + str(prose or "").strip()
        + "\n\nRequired category keys: timeline_and_event_order, presence_and_character_knowledge, physical_and_location_continuity, unsupported_consequential_details, scene_scope_and_hard_stop.\nAudit all five required categories. For any conflict, draft_evidence must be an exact quote "
        "from the completed scene and source_evidence an exact quote from source block A, B, or C. "
        "If even one category cannot be verified, mark it uncertain. JSON only; no prose outside the object."
    )


def _uncertain_audit(details):
    return {
        "pass": False,
        "status": "uncertain",
        "issues": [],
        "details": [str(item).strip() for item in details if str(item).strip()],
    }


def _run_scene_integrity_audit(
    *, engine, model_path, writer_system_prompt, scene_context,
    current_state, author_guidance, prose
):
    """Run a five-part evidence-backed audit; ambiguous results fail closed."""
    serialized_state = json.dumps(current_state, ensure_ascii=False, separators=(",", ":"))
    source_material = (
        str(scene_context or "") + "\n" + serialized_state + "\n" + str(author_guidance or "")
    )
    draft_text = str(prose or "")
    try:
        engine.reset_context(model_path, INTEGRITY_AUDIT_SYSTEM_PROMPT)
        raw_text = engine.generate(
            _audit_prompt(scene_context, current_state, author_guidance, draft_text)
        )
        raw = extract_json_object(raw_text)
    finally:
        if not _restore_writer_context(engine, model_path, writer_system_prompt):
            raise RuntimeError("Could not restore Writer after the integrity audit.")

    if not isinstance(raw, dict) or not isinstance(raw.get("checks"), dict):
        return _uncertain_audit(["The auditor did not return the required five-category checks object."])

    checks = raw["checks"]
    missing = [name for name in AUDIT_CATEGORIES if name not in checks]
    unexpected = [name for name in checks if name not in AUDIT_CATEGORIES]
    if missing or unexpected:
        details = []
        if missing:
            details.append("Missing audit categories: " + ", ".join(missing) + ".")
        if unexpected:
            details.append("Unexpected audit categories: " + ", ".join(str(x) for x in unexpected) + ".")
        return _uncertain_audit(details)

    normalized = {}
    conflicts = []
    uncertain = []
    for category in AUDIT_CATEGORIES:
        item = checks.get(category)
        if not isinstance(item, dict):
            uncertain.append(f"{category}: check was not a JSON object.")
            continue
        status = str(item.get("status", "") or "").strip().casefold()
        reason = str(item.get("reason", "") or "").strip()
        draft_evidence = str(item.get("draft_evidence", "") or "").strip()
        source_evidence = str(item.get("source_evidence", "") or "").strip()
        if status not in {"clear", "conflict", "uncertain"} or not reason:
            uncertain.append(f"{category}: missing a valid status or reason.")
            continue
        normalized[category] = {
            "status": status,
            "reason": reason,
            "draft_evidence": draft_evidence,
            "source_evidence": source_evidence,
        }
        if status == "uncertain":
            uncertain.append(f"{category}: {reason}")
        elif status == "conflict":
            if (
                not draft_evidence
                or not source_evidence
                or draft_evidence not in draft_text
                or source_evidence not in source_material
            ):
                uncertain.append(
                    f"{category}: the reported conflict did not include verifiable, exact excerpts from both sides."
                )
            else:
                conflicts.append(
                    f"{category}: draft evidence {draft_evidence!r}; source evidence {source_evidence!r}; {reason}"
                )

    if uncertain:
        return _uncertain_audit(uncertain)
    if conflicts:
        return {
            "pass": False,
            "status": "conflict",
            "issues": conflicts,
            "details": [
                f"{category}: {normalized[category]['status']} - {normalized[category]['reason']}"
                for category in AUDIT_CATEGORIES
            ],
        }
    return {
        "pass": True,
        "status": "clear",
        "issues": [],
        "details": [
            f"{category}: clear - {normalized[category]['reason']}"
            for category in AUDIT_CATEGORIES
        ],
    }


def _integrity_status(review):
    """Normalize structured audit outcomes; never assume malformed output is clear."""
    if not isinstance(review, dict):
        return "uncertain"
    status = str(review.get("status", "") or "").strip().casefold()
    if status in {"clear", "conflict", "uncertain"}:
        return status
    # Compatibility for older callers/tests; real auditor responses always carry status.
    if review.get("pass") is True and not review.get("issues"):
        return "clear"
    if review.get("pass") is False and review.get("issues"):
        return "conflict"
    return "uncertain"


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
        + "\n\nONE BOUNDED FULL-SCENE RETRY:\nAn independent review found these material conflicts, with direct evidence:\n"
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
    """Check coverage plus evidence-backed continuity; perform at most one safe recovery."""
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

    audit_status = _integrity_status(audit)
    validator_issues = _clean_findings(review, "violations")
    audit_issues = _clean_findings(audit, "issues")

    # Ambiguity in any required audit category is a hard stop: don't retry based
    # on guesses, and don't let the looser semantic validator overrule uncertainty.
    if audit_status == "uncertain":
        _restore_writer_context(engine, model_path, writer_system_prompt)
        detail = "; ".join(_clean_findings(audit, "details")[:2])
        if detail:
            detail = " Details: " + detail[:360]
        return draft, (
            "The continuity/scope audit could not verify every required category. "
            "The original draft was preserved for review rather than regenerated." + detail
        )

    # Only evidence-backed integrity conflicts authorize one whole-scene retry.
    if audit_status == "conflict":
        if not audit_issues:
            _restore_writer_context(engine, model_path, writer_system_prompt)
            return draft, (
                "The audit reported a conflict without verified findings. The original draft was preserved."
            )
        issues = audit_issues + [
            x for x in validator_issues if x.casefold() not in {v.casefold() for v in audit_issues}
        ]
        try:
            limit = SceneContract.max_attempts(contract)
        except (TypeError, ValueError):
            limit = 3
        if limit < 2:
            _restore_writer_context(engine, model_path, writer_system_prompt)
            return draft, (
                "A verified continuity/scope conflict was found, but the scene's retry limit prevents "
                "a full retry. Original draft preserved."
            )
        if not _restore_writer_context(engine, model_path, writer_system_prompt):
            return draft, (
                "A verified continuity/scope conflict was found, but Writer could not be restored. "
                "Original draft preserved."
            )
        try:
            revised = str(engine.generate(_build_regeneration_prompt(initial_prompt, issues)) or "").strip()
            if not revised:
                _restore_writer_context(engine, model_path, writer_system_prompt)
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
            and _integrity_status(revised_audit) == "clear"
        ):
            return revised, (
                "StoryBuilder found an evidence-backed continuity/scope conflict and regenerated the whole "
                "scene once. The revised draft passed follow-up checks; review it before accepting."
            )
        _restore_writer_context(engine, model_path, writer_system_prompt)
        return draft, "The full-scene retry did not pass every follow-up check. Original draft preserved for review."

    # A disagreement between the two reviewers is also ambiguous. In particular,
    # don't rewrite a scene merely because the semantic validator alleges a
    # violation the evidence-backed continuity audit could not substantiate.
    if validator_issues:
        _restore_writer_context(engine, model_path, writer_system_prompt)
        return draft, (
            "The semantic completion review flagged a possible violation, but the evidence-backed audit "
            "did not substantiate it. The original draft was preserved for review."
        )

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
    if _integrity_status(combined_audit) != "clear":
        _restore_writer_context(engine, model_path, writer_system_prompt)
        return draft, "The continuation's continuity/scope checks were not fully clear. Original draft preserved."
    return combined, "StoryBuilder added one continuation for missing planned events. Original prose was preserved; review the complete scene before accepting."
