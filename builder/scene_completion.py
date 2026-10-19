"""Semantically check scene completion and preserve drafts when recovery is unsafe."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from builder.scene_contract import SceneContract


def _restore_writer_context(engine: Any, model_path: str | Path, system_prompt: str) -> bool:
    """Return the persistent engine to its normal Writer context after review."""
    try:
        engine.reset_context(model_path, system_prompt)
    except Exception:
        return False
    return True


def _build_continuation_prompt(
    scene_context: str,
    existing_draft: str,
    missing_beats: list[str],
) -> str:
    """Ask for an append-only continuation toward the author's existing endpoint."""
    missing = "\n".join(f"- {beat}" for beat in missing_beats)
    return (
        "CONTINUE THE EXISTING SCENE. DO NOT REWRITE IT.\n\n"
        "AUTHOR INTENT AND SUPPORTING SCENE CONTEXT:\n"
        + str(scene_context or "").strip()
        + "\n\nSEMANTIC COMPLETION REVIEW: These major author-intended events appear to be "
        "missing from the draft. Continue only with events consistent with the author's idea, "
        "the established starting state, and the scene endpoint.\n"
        + missing
        + "\n\nSCENE ALREADY WRITTEN (preserve it verbatim; do not repeat, summarize, or revise it):\n"
        + str(existing_draft or "").strip()
        + "\n\nTASK: Continue directly after the exact final sentence of the existing scene. "
        "Write only new scene prose, not a heading or an explanation. Carry the scene naturally "
        "through its remaining intended phases to the stated hard stop. Do not jump beyond that "
        "endpoint, invent clues or events, or turn the missing-events list into a mechanical checklist. "
        "Preserve the existing prose unchanged. If an item conflicts with what is already written or "
        "the supplied author intent, do not force it into the continuation."
    )


def generate_scene_with_completion_check(
    *,
    engine: Any,
    model_path: str | Path,
    writer_system_prompt: str,
    initial_prompt: str,
    scene_context: str,
    contract: dict[str, Any],
    current_state: dict[str, Any],
    author_guidance: str = "",
) -> tuple[str, str]:
    """Generate a scene, then append one continuation when semantic review finds omissions.

    The completion check is advisory and bounded. Existing prose is never replaced.
    If validation finds a continuity violation or cannot run, the original draft is
    preserved and the caller receives a visible review notice.
    """
    draft = str(engine.generate(initial_prompt) or "").strip()
    author_idea = str((contract or {}).get("author_idea", "") or "").strip()
    if not draft or not author_idea:
        return draft, ""

    try:
        review = SceneContract.validate_with_engine(
            engine=engine,
            contract=contract,
            current_state=current_state,
            prose=draft,
            author_guidance=author_guidance,
            model_path=model_path,
        )
    except Exception as exc:
        restored = _restore_writer_context(engine, model_path, writer_system_prompt)
        notice = (
            "The scene completion check could not finish "
            f"({type(exc).__name__}). The original draft was preserved for your review."
        )
        if not restored:
            notice += " The Writer session could not be restored; restart Writer before the next scene."
        return draft, notice

    if review.get("pass") is True:
        if _restore_writer_context(engine, model_path, writer_system_prompt):
            return draft, ""
        return draft, (
            "The completion check passed, but the Writer session could not be restored. "
            "The draft is preserved; restart Writer before the next scene."
        )

    raw_missed = review.get("missed_beats", [])
    missed_beats = (
        [str(item).strip() for item in raw_missed if str(item).strip()]
        if isinstance(raw_missed, list)
        else []
    )
    raw_violations = review.get("violations", [])
    violations = (
        [str(item).strip() for item in raw_violations if str(item).strip()]
        if isinstance(raw_violations, list)
        else []
    )

    if violations:
        restored = _restore_writer_context(engine, model_path, writer_system_prompt)
        notice = (
            "The completion check found a continuity concern that an append-only continuation "
            "cannot safely repair. The original draft was preserved for your review."
        )
        if not restored:
            notice += " The Writer session could not be restored; restart Writer before the next scene."
        return draft, notice

    if not missed_beats:
        restored = _restore_writer_context(engine, model_path, writer_system_prompt)
        notice = (
            "The completion check did not confirm the planned endpoint. The original draft "
            "was preserved for your review rather than changed automatically."
        )
        if not restored:
            notice += " The Writer session could not be restored; restart Writer before the next scene."
        return draft, notice

    try:
        allowed_attempts = SceneContract.max_attempts(contract)
    except (TypeError, ValueError):
        allowed_attempts = 3
    if allowed_attempts < 2:
        restored = _restore_writer_context(engine, model_path, writer_system_prompt)
        notice = (
            "The completion check found missing planned events, but automatic continuation "
            "is disabled by this scene's retry limit. The original draft was preserved."
        )
        if not restored:
            notice += " The Writer session could not be restored; restart Writer before the next scene."
        return draft, notice

    if not _restore_writer_context(engine, model_path, writer_system_prompt):
        return draft, (
            "The completion check found missing planned events, but Writer could not be "
            "restarted for continuation. The original draft was preserved."
        )

    try:
        continuation = str(
            engine.generate(
                _build_continuation_prompt(scene_context, draft, missed_beats[:8])
            )
            or ""
        ).strip()
    except Exception as exc:
        restored = _restore_writer_context(engine, model_path, writer_system_prompt)
        notice = (
            "The completion check found missing planned events, but continuation failed "
            f"({type(exc).__name__}). The original draft was preserved for your review."
        )
        if not restored:
            notice += " The Writer session could not be restored; restart Writer before the next scene."
        return draft, notice

    if not continuation:
        return draft, (
            "The completion check found missing planned events, but Writer returned no continuation. "
            "The original draft was preserved for your review."
        )

    combined = draft.rstrip() + "\n\n" + continuation.lstrip()
    notice = (
        "The completion check found missing planned events, so StoryBuilder automatically "
        "continued the draft once. The original prose was preserved. Review the full combined scene "
        "before accepting it."
    )
    return combined, notice
