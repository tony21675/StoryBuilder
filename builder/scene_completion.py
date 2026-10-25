"""Bounded semantic completion and evidence-backed continuity recovery for scenes."""
from __future__ import annotations

import json
import re
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

def _make_review_finding(kind: str, message: str, *, can_suggest: bool = True) -> dict[str, Any]:
    """Normalize a validator/audit observation into an author-review item."""
    text = str(message or "").strip()
    if not text:
        text = "The automated review returned a concern without a usable explanation."
    titles = {
        "continuity": "Possible continuity or scope conflict",
        "validator": "Possible prose or intent issue",
        "coverage": "Possible omission",
        "uncertain": "Review could not verify this point",
        "unavailable": "Automated review did not complete",
        "manual": "Manual review needed",
        "runtime": "Writer session needs attention",
    }
    requests = {
        "continuity": (
            "Review this possible continuity/scope conflict against the author context. "
            "If it is a genuine problem, make the smallest local change that resolves it. "
            "Do not rewrite the scene, add unsupported facts, or force a plot outcome."
        ),
        "validator": (
            "Review this possible issue raised by the scene validator. If it is genuine, "
            "make the smallest local correction needed. Preserve the rest of the prose, "
            "voice, pacing, and author intent. Do not rewrite the scene or invent facts."
        ),
        "coverage": (
            "The validator thinks this planned event may be missing. Check whether the draft "
            "already satisfies the intent in another way. If a local addition or change is "
            "truly needed, make the smallest focused edit that addresses it. Do not rewrite "
            "the scene, force an outcome, or invent facts."
        ),
        "uncertain": "",
        "unavailable": "",
        "manual": "",
        "runtime": "",
    }
    return {
        "kind": str(kind or "validator"),
        "title": titles.get(kind, "Possible issue to review"),
        "message": text,
        "can_suggest": bool(can_suggest),
        "edit_request": (
            requests.get(kind, "Make only the smallest safe local edit needed to address this concern.")
            + ("\nConcern to review: " + text if requests.get(kind) else "")
        ).strip(),
    }


def _normalize_finding_key(message: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(message or "").casefold()).strip()


def review_findings_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Conservatively match repeated findings after a local edit/re-review."""
    left_text = _normalize_finding_key(str(left.get("message", "")))
    right_text = _normalize_finding_key(str(right.get("message", "")))
    if not left_text or not right_text:
        return False
    if left_text == right_text:
        return True
    stop_words = {"the", "and", "that", "this", "with", "from", "into", "for", "but", "was", "were", "may", "possible", "issue", "concern"}
    left_words = {word for word in left_text.split() if word not in stop_words and len(word) > 2}
    right_words = {word for word in right_text.split() if word not in stop_words and len(word) > 2}
    if min(len(left_words), len(right_words)) < 4:
        return False
    overlap = len(left_words & right_words) / min(len(left_words), len(right_words))
    return overlap >= 0.75


def collect_review_findings(
    review: dict[str, Any] | None,
    audit: dict[str, Any] | None,
    *,
    validator_error: str | None = None,
    audit_error: str | None = None,
) -> list[dict[str, Any]]:
    """Combine validator and audit observations into a deduplicated author-review queue."""
    findings: list[dict[str, Any]] = []

    def add(kind: str, message: str, *, can_suggest: bool = True) -> None:
        finding = _make_review_finding(kind, message, can_suggest=can_suggest)
        if not any(review_findings_match(finding, existing) for existing in findings):
            findings.append(finding)

    audit_status = _integrity_status(audit) if audit is not None else "uncertain"
    if audit is not None:
        if audit_status == "conflict":
            issues = _clean_findings(audit, "issues")
            for issue in issues:
                add("continuity", issue)
            if not issues:
                add("uncertain", "The continuity/scope auditor reported a conflict but supplied no verifiable finding.", can_suggest=False)
        elif audit_status == "uncertain":
            details = _clean_findings(audit, "details")
            for detail in details:
                add("uncertain", detail, can_suggest=False)
            if not details:
                add("uncertain", "The continuity/scope audit could not verify all required categories.", can_suggest=False)

    if review is not None:
        for issue in _clean_findings(review, "violations"):
            add("validator", issue)
        for omission in _clean_findings(review, "missed_beats"):
            add("coverage", omission)
        if review.get("pass") is not True and not _clean_findings(review, "violations") and not _clean_findings(review, "missed_beats"):
            note = str(review.get("notes", "") or "").strip()
            add("validator", note or "The scene validator did not confirm the planned endpoint.", can_suggest=bool(note))

    if validator_error:
        add("unavailable", validator_error.splitlines()[0], can_suggest=False)
    if audit_error:
        add("unavailable", audit_error.splitlines()[0], can_suggest=False)

    return findings


def review_scene_draft(
    *,
    engine: Any,
    model_path: str | Path,
    writer_system_prompt: str,
    scene_context: str,
    contract: dict[str, Any],
    current_state: dict[str, Any],
    author_guidance: str = "",
    historical_context: str = "",
) -> tuple[list[dict[str, Any]], str]:
    """Review an existing draft and return actionable findings; never rewrite prose."""
    if not str((contract or {}).get("author_idea", "") or "").strip():
        finding = _make_review_finding(
            "manual",
            "No saved author Scene Idea was present, so automated coverage and continuity review did not run.",
            can_suggest=False,
        )
        _restore_writer_context(engine, model_path, writer_system_prompt)
        return [finding], "AUTOMATED REVIEW: a manual review is needed because no saved Scene Idea was available."

    review = None
    audit = None
    validator_error = None
    audit_error = None
    try:
        review = SceneContract.validate_with_engine(
            engine=engine,
            contract=contract,
            current_state=current_state,
            prose=str(scene_context and "" or "") + "",
            author_guidance=author_guidance,
            model_path=model_path,
        )
    except Exception as exc:
        validator_error = _exception_diagnostic("Scene completion check failed", exc)

    # The draft is supplied separately below; keeping this helper explicit makes
    # post-edit rechecks use the exact current editor contents.
    prose = str(contract.get("_review_prose", "") or "")
    if not prose.strip():
        prose = str(getattr(engine, "_validator_review_prose", "") or "")
    if not prose.strip():
        # The caller sets this transiently immediately around this helper. This
        # fallback protects tests/callers that supply an empty draft explicitly.
        prose = ""

    if review is not None:
        pass

    try:
        audit = _run_scene_integrity_audit(
            engine=engine,
            model_path=model_path,
            writer_system_prompt=writer_system_prompt,
            scene_context=scene_context,
            current_state=current_state,
            author_guidance=author_guidance,
            prose=prose,
            historical_context=historical_context,
        )
    except Exception as exc:
        audit_error = _exception_diagnostic("Continuity/scope audit failed", exc)

    findings = collect_review_findings(
        review,
        audit,
        validator_error=validator_error,
        audit_error=audit_error,
    )
    restored = _restore_writer_context(engine, model_path, writer_system_prompt)
    if not restored:
        findings.append(_make_review_finding(
            "runtime",
            "Writer could not restore its normal context after review. Restart Writer before the next model task.",
            can_suggest=False,
        ))

    if findings:
        note = (
            f"AUTOMATED REVIEW: {len(findings)} possible finding(s) need your review. "
            "No prose was changed automatically; review each finding and choose whether to apply a focused fix, dismiss it, or skip it."
        )
    else:
        note = (
            "AUTOMATED REVIEW: scene-contract validation and the continuity/scope audit reported no issues. "
            "This is a screening result, not a guarantee; review facts, uncertainty, and author boundaries before accepting."
        )
    if validator_error:
        note += " The validator did not complete."
    if audit_error:
        note += " The continuity/scope audit did not complete."
    return findings, note


def generate_scene_with_completion_check(
    *, engine: Any, model_path: str | Path, writer_system_prompt: str,
    initial_prompt: str, scene_context: str, contract: dict[str, Any],
    current_state: dict[str, Any], author_guidance: str = "",
    historical_context: str = "", on_draft_delta=None, on_review_findings=None,
) -> tuple[str, str]:
    """Generate a complete scene once, then return review findings for author decisions.

    The validators no longer trigger an automatic full-scene retry. They identify
    concerns; a separate UI flow proposes focused edits that the author must approve.
    """
    if callable(on_draft_delta):
        draft = str(engine.generate(initial_prompt, on_delta=on_draft_delta) or "").strip()
    else:
        draft = str(engine.generate(initial_prompt) or "").strip()
    if not draft:
        return draft, (
            "AUTOMATED REVIEW SKIPPED: no draft prose was returned, so the completion and continuity checks did not run."
        )

    # review_scene_draft consumes the exact current draft. Store it only for the
    # duration of this call so the reviewer doesn't need to reconstruct it.
    setattr(engine, "_validator_review_prose", draft)
    try:
        findings, notice = review_scene_draft(
            engine=engine,
            model_path=model_path,
            writer_system_prompt=writer_system_prompt,
            scene_context=scene_context,
            contract=contract,
            current_state=current_state,
            author_guidance=author_guidance,
            historical_context=historical_context,
        )
    finally:
        try:
            delattr(engine, "_validator_review_prose")
        except Exception:
            pass
    if callable(on_review_findings):
        on_review_findings(findings)
    return draft, notice
