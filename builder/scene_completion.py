"""Bounded semantic completion and evidence-backed continuity recovery for scenes."""
from __future__ import annotations

import json
import traceback
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

SHARED_CONTINUITY_RULES = (
    "Use only the active novel's supplied author canon, accepted manuscript, original "
    "Scene Idea, author guidance, and starting-state data as authority. Do not present "
    "unsupported past actions, encounters, maintenance, logs, diagnoses, motives, "
    "off-scene people, or other consequential history as established fact. Treat "
    "current_state[unresolved_questions] as unresolved unless the scene establishes an answer through on-page evidence and the Scene Idea permits that progress. "
    "New observations and discoveries made on-page now are welcome; dialogue and hypotheses may "
    "develop on-page; do not recast them as earlier events without support. Do not "
    "repeat completed events as new action unless a character meaningfully recounts "
    "them to someone who does not know. Continue from the established endpoint. Keep "
    "character movement consistent with the supplied location and physical state; "
    "show plausible transitions when location changes. Use the active novel's "
    "character-card identity reference for names, gender, and pronouns; flag contradictions only when supplied sources support them. Never infer identities from examples "
    "or other novels. Keep emergencies, travel, communications, technology, and "
    "cause-and-effect consistent with that novel's canon and physical constraints. "
    "Distinguish observation, hypothesis, and confirmed explanation. Do not imply "
    "intent, sabotage, conspiracy, or causal connections unless supported by the "
    "active novel's canon or scene evidence."
)


_SUCCESSFUL_COMPLETION_NOTICE_PREFIXES = (
    "AUTOMATED REVIEW: scene-contract validation and the continuity/scope audit reported no issues.",
    "StoryBuilder found an evidence-backed continuity/scope conflict and regenerated the whole scene once. "
    "The revised draft passed follow-up checks;",
    "StoryBuilder regenerated the whole scene to address planned events that appeared missing.",
    "StoryBuilder added one continuation for missing planned events.",
)


def completion_notice_is_success(notice: str | None) -> bool:
    """Return True only for known successful review outcomes, not skipped/uncertain checks."""
    text = str(notice or "").strip()
    return bool(text) and any(
        text.startswith(prefix) for prefix in _SUCCESSFUL_COMPLETION_NOTICE_PREFIXES
    )


def _exception_diagnostic(label: str, exc: Exception) -> str:
    """Preserve the exception message and traceback for the copyable error dialog."""
    detail = str(exc).strip() or "No additional exception message was provided."
    message = f"{label} ({type(exc).__name__}): {detail}"
    stack = traceback.format_exc().strip()
    if stack:
        message += "\n\nDiagnostic traceback:\n" + stack
    return message


INTEGRITY_AUDIT_SYSTEM_PROMPT = """You are an independent continuity and scene-scope auditor for a novel draft. Do not rewrite the prose.
Return exactly one JSON object with this shape:
{
  "checks": {
    "timeline_and_event_order": {"status":"clear","basis":"established_fact","reason":"brief reason","draft_evidence":"optional exact scene quote or empty string","source_evidence":"optional exact source quote or empty string"},
    "presence_and_character_knowledge": {"status":"clear","basis":"established_fact","reason":"brief reason","draft_evidence":"optional exact scene quote or empty string","source_evidence":"optional exact source quote or empty string"},
    "physical_and_location_continuity": {"status":"clear","basis":"established_fact","reason":"brief reason","draft_evidence":"optional exact scene quote or empty string","source_evidence":"optional exact source quote or empty string"},
    "unsupported_consequential_details": {"status":"clear","basis":"established_fact","reason":"brief reason","draft_evidence":"optional exact scene quote or empty string","source_evidence":"optional exact source quote or empty string"},
    "scene_scope_and_hard_stop": {"status":"clear","basis":"established_fact","reason":"brief reason","draft_evidence":"optional exact scene quote or empty string","source_evidence":"optional exact source quote or empty string"}
  }
}

Review all five categories independently and include every category exactly once. Each status must be "clear", "conflict", or "uncertain". Every check needs a short reason.
- Every check needs a short reason and a "basis".
- "clear" means you examined the most consequential continuity-relevant claim in the category and found it compatible with the supplied evidence and author boundaries. A clear result is not just a general statement that no conflict was noticed.
- For a clear check, basis MUST be one of:
  * "established_fact": the reason must explain why the draft is compatible with supplied context. For clear results, evidence fields are optional diagnostics and may be empty.
  * "new_present_scene_development": the reason must explain why this is new on-page action, observation, dialogue, or hypothesis, rather than unsupported past history, and why it is compatible with the author's premise. Evidence fields are optional for clear results.
  * "no_material_claim": use only when the category contains no material continuity-relevant claim. Both evidence fields must be empty, and the reason must contain the exact phrase "No material claim in this category."
- "conflict" means a material contradiction supported by BOTH a verbatim draft excerpt and a verbatim excerpt from the supplied author idea, starting-state JSON, stable author guidance, relevant accepted-manuscript excerpts, or the shared continuity rules. Set basis to "contradiction".
- "uncertain" means the supplied context does not let you verify the category confidently, or exact evidence from both sides is unavailable for a claimed conflict. Set basis to "unverified".
- For conflicts, evidence must be exact text from both the completed scene and the supplied context. Clear results are semantic judgments and do not require copied quotations. Never report a conflict without verifiable evidence from both sides. If the semantic status genuinely cannot be determined, mark the category "uncertain". Do not add a pass field or issues list.

Check specifically:
Before declaring a category clear, compare consequential claims against accepted prose and the shared continuity rules. Treat current_state unresolved_questions as open, not as evidence that an answer has already been established. Flag unsupported consequential past events, asserted prior findings, and newly named off-scene people when the draft presents them as established history without support. For conflicts, quote the exact shared rule or source evidence and the exact draft claim.
1. Timeline and event order: explicit day, time-of-day, before/after relationships, and whether the draft changes an established time or repeats an event already completed.
2. Presence and character knowledge: who is present or absent, who witnessed an event firsthand, who learned it secondhand, and what the character could know at this point. Compare all character gender/pronoun references with the authoritative character-card identity reference in source block A; flag contradictory pronouns or gender only when the card supports the conflict.
3. Physical and location continuity: where people are, movement between locations, established physical condition and possessions, and explicitly stated personal boundaries.
4. Unsupported consequential details and explicit author boundaries: check whether the draft invents consequential evidence or events, such as an unestablished witness, contact, object, encounter, destination, motive, identity, or event. An ordinary plausible detail is not automatically a problem merely because it is not listed. If the author explicitly forbids new clues or other additions, honor that boundary. Distinguish reasonable character-based speculation from established fact: a character may suggest a familiar habit, likely routine, or possible type of place based on established knowledge of another character, but that is not proof the event occurred or that the possibility is true. Do not flag general speculation merely because the Scene Idea does not spell it out. Assess whether the scene invents or relies on an unsupported consequential fact, not merely whether a character considers a reasonable possibility.
5. Scene scope and hard stop: whether the draft goes beyond the specified endpoint, such as beginning a later investigation, assigning detailed tasks, adding training, or resolving something reserved for later. Read explicit boundaries as binding constraints, not suggestions; a tentative label does not excuse a prohibited advance.

Authority order: explicit author canon and instructions plus the original Scene Idea; the actual starting-state/current_situation and relevant character/location/knowledge data; then supporting generated directions. Read the relevant entries, not just the first lines. Absence from a short plan alone is not evidence that a detail is false. Preserve creative freedom for ordinary dialogue, plausible gestures, atmosphere, routine choices, and everyday details that fit the active novel. Do not flag style preferences, length, or missing planned beats in this audit; a separate semantic check handles coverage. When source materials genuinely conflict or don't settle a material question, mark uncertain. A missing category, invalid schema, or materially unresolved claim must never count as clear. Optional diagnostic evidence is not required for a clear result; a conflict still requires exact evidence from both sides.
"""


def _restore_writer_context(engine: Any, model_path: str | Path, system_prompt: str) -> bool:
    try:
        engine.reset_context(model_path, system_prompt)
        return True
    except Exception:
        return False


def _audit_prompt(scene_context, current_state, author_guidance, prose, historical_context=""):
    serialized_state = json.dumps(current_state, ensure_ascii=False, separators=(",", ":"))
    return (
        "AUTHOR'S ORIGINAL SCENE IDEA, SUPPORTING DIRECTION, AND CHARACTER-CARD IDENTITY REFERENCE (source block A):\n"
        + str(scene_context or "").strip()
        + "\n\nSTARTING STORY STATE JSON (source block B; inspect relevant fields including current_situation, "
        "location, time, character_knowledge, recent_events, physical_state, continuity_requirements, scene_cast, and current_state[unresolved_questions]):\n"
        + serialized_state
        + "\n\nSTABLE AUTHOR GUIDANCE (source block C):\n"
        + str(author_guidance or "").strip()
        + "\n\nACCEPTED MANUSCRIPT EXCERPTS (source block D; historical evidence, not current physical state):\n"
        + (str(historical_context or "").strip() or "(no retrieved accepted excerpts included)")
        + "\n\nSHARED CONTINUITY RULES (source block E):\n"
        + SHARED_CONTINUITY_RULES
        + "\n\nCOMPLETED SCENE TO AUDIT:\n"
        + str(prose or "").strip()
        + "\n\nRequired category keys: timeline_and_event_order, presence_and_character_knowledge, physical_and_location_continuity, unsupported_consequential_details, scene_scope_and_hard_stop.\nAudit all five required categories. Check for unsupported consequential facts, including unestablished people, objects, encounters, leads, destinations, motives, identities, diagnoses, or events, and for any violation of an explicit author boundary. Distinguish reasonable character-based speculation from established fact: a character may offer a tentative possibility or inference based on established knowledge, but that does not establish the possibility as true. Do not treat ordinary brainstorming as a continuity conflict unless the draft presents or relies on it as fact. Apply boundaries to the actual degree of scene progress and detail. For any conflict, draft_evidence must be an exact quote "
        "from the completed scene and source_evidence an exact quote from source block A, B, C, D, or E. A direct correction or rejection in accepted manuscript evidence establishes that the earlier hypothesis was not accepted as fact unless later evidence superseded it. Apply the shared continuity rules to unsupported retroactive claims and unresolved questions. Check author boundaries against indirect framing as well as explicit claims; do not seed an explanation or event the author has ruled out through suggestive side details. Preserve neutral observations and compatible character speculation. "
        "If a category's semantic status genuinely cannot be determined, mark it uncertain. Do not mark a clear result uncertain solely because an exact quotation was not reproduced. JSON only; no prose outside the object."
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
    current_state, author_guidance, prose, historical_context=""
):
    """Run a five-part evidence-backed audit; ambiguous results fail closed."""
    serialized_state = json.dumps(current_state, ensure_ascii=False, separators=(",", ":"))
    source_material = (
        str(scene_context or "") + "\n" + serialized_state + "\n" + str(author_guidance or "") + "\n" + str(historical_context or "") + "\n" + SHARED_CONTINUITY_RULES
    )
    draft_text = str(prose or "")
    try:
        engine.reset_context(model_path, INTEGRITY_AUDIT_SYSTEM_PROMPT)
        raw_text = engine.generate(
            _audit_prompt(scene_context, current_state, author_guidance, draft_text, historical_context=historical_context)
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
        basis = str(item.get("basis", "") or "").strip().casefold()
        reason = str(item.get("reason", "") or "").strip()
        draft_evidence = str(item.get("draft_evidence", "") or "").strip()
        source_evidence = str(item.get("source_evidence", "") or "").strip()
        if status not in {"clear", "conflict", "uncertain"} or not reason:
            uncertain.append(f"{category}: missing a valid status or reason.")
            continue
        normalized[category] = {
            "status": status,
            "basis": basis,
            "reason": reason,
            "draft_evidence": draft_evidence,
            "source_evidence": source_evidence,
        }
        if status == "uncertain":
            uncertain.append(f"{category}: {reason}")
        elif status == "clear":
            if basis == "no_material_claim":
                if draft_evidence or source_evidence:
                    uncertain.append(
                        f"{category}: no_material_claim basis must have empty evidence fields and explicitly say no material claim is present."
                    )
            elif basis == "established_fact":
                # A clear verdict is semantic. A paraphrased or omitted quote
                # must not overturn it.
                pass
            elif basis == "new_present_scene_development":
                # The reason and basis carry the semantic judgment. Evidence
                # strings are advisory for a clear result, not a pass gate.
                pass
            else:
                uncertain.append(
                    f"{category}: clear result lacked a recognized evidence basis."
                )
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


def _build_missing_beats_regeneration_prompt(initial_prompt, missing_beats):
    missing = "\n".join(f"- {beat}" for beat in missing_beats)
    return (
        str(initial_prompt or "").strip()
        + "\n\nONE BOUNDED FULL-SCENE RETRY FOR POSSIBLY MISSING PLANNED EVENTS:\n"
        + "The first draft may have omitted or underplayed these author-intended events:\n"
        + missing
        + "\n\nWrite one complete replacement scene from the original author intent and starting state. "
        "This is a replacement for the first draft, not a continuation. Never append a second telling "
        "of the scene to the original. Include the listed event or events naturally when they fit the "
        "established story and author boundaries. Preserve valid continuity, do not invent clues or "
        "consequential past actions, honor the hard stop, and output only the complete scene prose."
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
    historical_context: str = "", on_draft_delta=None,
) -> tuple[str, str]:
    """Check coverage plus evidence-backed continuity; perform at most one safe recovery.

    Optional on_draft_delta receives the initial prose as it streams from the model.
    Review/recovery calls remain non-streaming because they can replace the full draft.
    """
    if callable(on_draft_delta):
        draft = str(engine.generate(initial_prompt, on_delta=on_draft_delta) or "").strip()
    else:
        draft = str(engine.generate(initial_prompt) or "").strip()
    if not draft:
        return draft, (
            "AUTOMATED REVIEW SKIPPED: no draft prose was returned, so the completion and continuity checks did not run."
        )
    if not str((contract or {}).get("author_idea", "") or "").strip():
        return draft, (
            "AUTOMATED REVIEW SKIPPED: no saved author Scene Idea was present in the runtime contract, "
            "so the completion and continuity checks did not run. Review this draft manually and save "
            "the Scene Idea before generating another scene."
        )

    try:
        review = SceneContract.validate_with_engine(
            engine=engine, contract=contract, current_state=current_state,
            prose=draft, author_guidance=author_guidance, model_path=model_path,
        )
    except Exception as exc:
        restored = _restore_writer_context(engine, model_path, writer_system_prompt)
        note = _exception_diagnostic("Scene completion check failed", exc)
        note += "\n\nThe original draft was preserved."
        if not restored:
            note += "\nRestart Writer before the next scene."
        return draft, note

    try:
        audit = _run_scene_integrity_audit(
            engine=engine, model_path=model_path, writer_system_prompt=writer_system_prompt,
            scene_context=scene_context, current_state=current_state,
            author_guidance=author_guidance, prose=draft,
            historical_context=historical_context,
        )
    except Exception as exc:
        _restore_writer_context(engine, model_path, writer_system_prompt)
        return draft, (
            _exception_diagnostic("Continuity/scope audit failed", exc)
            + "\n\nThe original draft was preserved."
        )

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
                historical_context=historical_context,
            )
        except Exception as exc:
            _restore_writer_context(engine, model_path, writer_system_prompt)
            return draft, (
                _exception_diagnostic("The full-scene retry could not be verified", exc)
                + "\n\nOriginal draft preserved."
            )
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
            return draft, (
                "AUTOMATED REVIEW: scene-contract validation and the continuity/scope audit reported no issues. "
                "This is a screening result, not a guarantee; review facts, uncertainty, and author boundaries before accepting."
            )
        return draft, (
            "AUTOMATED REVIEW: no issues were reported, but Writer could not be restored. "
            "Restart Writer before the next scene."
        )

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
        return draft, "Planned events are missing, but the retry limit prevents a full-scene retry. Original draft preserved."
    if not _restore_writer_context(engine, model_path, writer_system_prompt):
        return draft, "Planned events are missing, but Writer could not be restored. Original draft preserved."
    try:
        replacement = str(
            engine.generate(_build_missing_beats_regeneration_prompt(initial_prompt, missed[:8])) or ""
        ).strip()
    except Exception as exc:
        _restore_writer_context(engine, model_path, writer_system_prompt)
        return draft, (
            _exception_diagnostic("Full-scene retry for missing planned events failed", exc)
            + "\n\nOriginal draft preserved."
        )
    if not replacement:
        _restore_writer_context(engine, model_path, writer_system_prompt)
        return draft, "The full-scene retry returned no prose. Original draft preserved."
    try:
        replacement_review = SceneContract.validate_with_engine(
            engine=engine, contract=contract, current_state=current_state,
            prose=replacement, author_guidance=author_guidance, model_path=model_path,
        )
        replacement_audit = _run_scene_integrity_audit(
            engine=engine, model_path=model_path, writer_system_prompt=writer_system_prompt,
            scene_context=scene_context, current_state=current_state,
            author_guidance=author_guidance, prose=replacement,
            historical_context=historical_context,
        )
    except Exception as exc:
        _restore_writer_context(engine, model_path, writer_system_prompt)
        return draft, (
            _exception_diagnostic("The full-scene retry could not be verified", exc)
            + "\n\nOriginal draft preserved."
        )
    if (
        replacement_review.get("pass") is True
        and not _clean_findings(replacement_review, "missed_beats")
        and not _clean_findings(replacement_review, "violations")
        and _integrity_status(replacement_audit) == "clear"
    ):
        return replacement, (
            "StoryBuilder regenerated the whole scene to address planned events that appeared missing. "
            "The replacement draft passed follow-up checks; review it before accepting."
        )
    _restore_writer_context(engine, model_path, writer_system_prompt)
    return draft, "The full-scene retry did not pass every follow-up check. Original draft preserved for review."
