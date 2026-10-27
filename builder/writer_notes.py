from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path
from tempfile import NamedTemporaryFile

from builder.manuscript import ManuscriptManager


WRITER_NOTES_FILENAME = "working_writer_notes.json"
MAX_LEARNED_NOTES = 8
MAX_REVIEWED_SCENES = 100
MAX_EVIDENCE_SCENES = 20

# This model-driven housekeeping is optional and disabled by default because it
# must restart llama-cli and can delay the author's next writing step.
WRITER_NOTES_AUTO_UPDATE_ENV = "STORYBUILDER_AUTO_WRITER_NOTES"
WRITER_NOTES_CONTEXT_TOKENS = 6144
WRITER_NOTES_MAX_TOKENS = 350
WRITER_NOTES_TIMEOUT_SECONDS = 180


def writer_notes_auto_update_enabled() -> bool:
    """Return whether automatic craft-note learning was explicitly enabled."""
    return os.environ.get(WRITER_NOTES_AUTO_UPDATE_ENV, "").strip().casefold() in {
        "1", "true", "yes", "on"
    }

WRITER_NOTES_SYSTEM_PROMPT = """You maintain a small, temporary writing-craft notebook for exactly one novel.

Review the supplied accepted manuscript scenes and existing working notes. Suggest at most two concise, flexible craft observations that would improve future prose for this same book.

Only suggest a note when the same observable craft pattern is supported by at least two distinct supplied accepted scenes. A single awkward line or one scene's necessary style is not enough. If there is no well-supported recurring pattern, return no suggestions.

Notes may cover presentation, pacing, balance of dialogue/action/description, reader orientation, emotional repetition, scene transitions, or the book's demonstrated prose tone. They must remain guidance about HOW to write, not facts about WHAT happens.

Never add plot events, character or relationship facts, worldbuilding, setting details, secrets, motives, future plans, scene beats, or continuity assertions. Those belong in the novel's canon and scene contracts. Do not turn a one-off moment into a rigid rule. Avoid quotas, checklists, or micromanaging sentences. Preserve authorial freedom and the book's demonstrated tone. Do not assume a genre that the supplied scenes do not establish.

Return ONLY valid JSON in this exact shape:
{"suggestions":[{"note":"One concise, flexible craft observation.","evidence_scenes":["Chapter 1, Scene 1","Chapter 1, Scene 2"]}]}

Evidence labels must exactly match scene labels in the supplied input. Each suggestion must cite at least two distinct supplied scenes. Return {"suggestions":[]} when no recurring craft lesson is well-supported. No markdown or explanation.
"""


def default_writer_notes() -> dict:
    """Return a clean learning notebook for a newly created novel."""
    return {
        "format_version": 1,
        "purpose": (
            "Temporary, novel-specific writing-craft observations learned from accepted scenes. "
            "This file is not canon and must never override author directions or scene contracts."
        ),
        "learned_notes": [],
        "reviewed_scenes": [],
    }


def normalize_writer_notes(value) -> dict:
    """Validate notebook shape while preserving useful existing notes."""
    if not isinstance(value, dict):
        value = {}

    result = default_writer_notes()
    notes = value.get("learned_notes", [])
    if isinstance(notes, list):
        cleaned = []
        for item in notes:
            if isinstance(item, str):
                text = item.strip()
                item = {"note": text, "evidence_scenes": [], "last_updated_scene": ""}
            if not isinstance(item, dict):
                continue
            text = re.sub(r"\s+", " ", str(item.get("note", "") or "")).strip()
            if not text or len(text) > 500:
                continue
            evidence = []
            raw_evidence = item.get("evidence_scenes", [])
            if isinstance(raw_evidence, list):
                for scene in raw_evidence:
                    label = str(scene or "").strip()
                    if label and label not in evidence:
                        evidence.append(label)
            cleaned.append({
                "note": text,
                "evidence_scenes": evidence[-MAX_EVIDENCE_SCENES:],
                "last_updated_scene": str(item.get("last_updated_scene", "") or "").strip(),
            })
        result["learned_notes"] = cleaned[:MAX_LEARNED_NOTES]

    reviewed = value.get("reviewed_scenes", [])
    if isinstance(reviewed, list):
        result["reviewed_scenes"] = list(dict.fromkeys(
            str(scene).strip() for scene in reviewed if str(scene).strip()
        ))[-MAX_REVIEWED_SCENES:]
    return result


def load_writer_notes(novel_path: str | Path) -> dict:
    """Load a novel's working notes, defaulting cleanly for older packages."""
    path = Path(novel_path) / WRITER_NOTES_FILENAME
    if not path.is_file():
        return default_writer_notes()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_writer_notes()
    return normalize_writer_notes(value)


def save_writer_notes(novel_path: str | Path, notes: dict) -> Path:
    """Atomically persist notes inside one novel package."""
    folder = Path(novel_path)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / WRITER_NOTES_FILENAME
    payload = json.dumps(normalize_writer_notes(notes), indent=2, ensure_ascii=False) + "\n"
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=folder, delete=False, prefix=f".{target.name}."
    ) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    temporary.replace(target)
    return target


def collect_recent_accepted_scenes(
    novel_path: str | Path,
    latest_chapter: int,
    latest_scene: int,
    latest_prose: str,
    limit: int = 3,
    per_scene_limit: int = 3200,
) -> list[dict]:
    """Read a few most recent accepted sections, never manuscript drafts."""
    manager = ManuscriptManager(Path(novel_path))
    latest_label = f"Chapter {int(latest_chapter)}, Scene {int(latest_scene)}"
    samples = []
    found_latest = False

    for path in manager.list_scenes():
        numbers = manager.scene_numbers(path)
        if numbers is None:
            chapter_match = re.search(r"Chapter_([0-9]+)", path.parent.name, flags=re.IGNORECASE)
            scene_match = re.search(r"Scene_([0-9]+)", path.stem, flags=re.IGNORECASE)
            if chapter_match and scene_match:
                numbers = (int(chapter_match.group(1)), int(scene_match.group(1)))
            else:
                continue
        try:
            prose = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if not prose:
            continue
        label = f"Chapter {numbers[0]}, Scene {numbers[1]}"
        if label == latest_label:
            prose = str(latest_prose or prose).strip()
            found_latest = True
        if len(prose) > per_scene_limit:
            head_size = per_scene_limit // 2
            tail_size = per_scene_limit - head_size
            prose = (
                prose[:head_size].rstrip()
                + "\n[Middle omitted for the writing-craft review.]\n"
                + prose[-tail_size:].lstrip()
            )
        samples.append({"scene": label, "prose": prose})

    if latest_prose and not found_latest:
        prose = str(latest_prose).strip()
        if len(prose) > per_scene_limit:
            head_size = per_scene_limit // 2
            tail_size = per_scene_limit - head_size
            prose = prose[:head_size].rstrip() + "\n[Middle omitted.]\n" + prose[-tail_size:].lstrip()
        samples.append({"scene": latest_label, "prose": prose})

    return samples[-max(1, int(limit)):]


def collect_initial_seed_scenes(
    novel_path: str | Path,
    per_scene_limit: int = 3200,
    total_limit: int = 18000,
) -> list[dict]:
    """Sample every accepted scene from the earliest chapter with at least two scenes.

    This one-time startup seed gives the notebook an initial body of evidence.
    Only accepted manuscript files are considered; draft files are excluded by
    ManuscriptManager.list_scenes().
    """
    manager = ManuscriptManager(Path(novel_path))
    chapters: dict[int, list[dict]] = {}

    for path in manager.list_scenes():
        numbers = manager.scene_numbers(path)
        if numbers is None:
            continue
        chapter, scene = numbers
        try:
            prose = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if not prose:
            continue
        chapters.setdefault(chapter, []).append({
            "scene": f"Chapter {chapter}, Scene {scene}",
            "prose": prose,
        })

    selected = []
    for chapter in sorted(chapters):
        if len(chapters[chapter]) >= 2:
            selected = chapters[chapter]
            break
    if not selected:
        return []

    # Keep the whole chapter represented without letting a long chapter flood
    # the model context. Each scene contributes its opening and ending.
    total_budget = max(400, int(total_limit))
    per_scene_budget = max(
        400,
        min(max(400, int(per_scene_limit)), total_budget // len(selected)),
    )
    samples = []
    for item in selected:
        prose = item["prose"]
        if len(prose) > per_scene_budget:
            head_size = per_scene_budget // 2
            tail_size = per_scene_budget - head_size
            prose = (
                prose[:head_size].rstrip()
                + "\n[Middle omitted for the initial writing-craft review.]\n"
                + prose[-tail_size:].lstrip()
            )
        samples.append({"scene": item["scene"], "prose": prose})
    return samples


def build_writer_notes_review_prompt(notes: dict, recent_scenes: list[dict]) -> str:
    """Create the small review task sent after a scene has been accepted and applied."""
    return (
        "Maintain the per-novel temporary writing-craft notebook. Do not rewrite scenes.\n\n"
        "CURRENT NOTEBOOK:\n"
        + json.dumps(normalize_writer_notes(notes), indent=2, ensure_ascii=False)
        + "\n\nRECENT ACCEPTED SCENES, OLDEST FIRST:\n"
        + json.dumps(recent_scenes, indent=2, ensure_ascii=False)
        + "\n\nLook for recurring craft patterns across these accepted scenes. "
        "Suggest only a lesson that is supported by at least two different scene labels. "
        "Do not store canon, plot, character, relationship, or world facts. "
        "It is fine to return no suggestions."
    )


def parse_writer_notes_response(response: str) -> list[dict]:
    """Parse the auditor's JSON result without trusting surrounding commentary."""
    raw = str(response or "").strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("The writing-notes review did not return valid JSON.")
        try:
            payload = json.loads(raw[start:end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError("The writing-notes review returned malformed JSON.") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("suggestions", []), list):
        raise ValueError("The writing-notes review must contain a suggestions list.")
    return [item for item in payload.get("suggestions", []) if isinstance(item, dict)]


def merge_writer_notes(
    current_notes: dict,
    suggestions: list[dict],
    available_scene_labels: list[str],
    reviewed_scene: str,
) -> tuple[dict, int]:
    """Add only multi-scene-supported craft observations, merging duplicates."""
    result = normalize_writer_notes(current_notes)
    available = set(str(label).strip() for label in available_scene_labels if str(label).strip())
    added = 0

    def note_key(text: str) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))

    for suggestion in suggestions:
        text = re.sub(r"\s+", " ", str(suggestion.get("note", "") or "")).strip()
        if not text or len(text) < 18 or len(text) > 350:
            continue
        # Keep factual statements out even if the model accidentally proposes one.
        # Learned entries must read as writing guidance, not canon or plot notes.
        if not re.match(
            r"^(?:when|prefer|avoid|use|let|keep|allow|favor|give|balance|show|describe|write|vary|consider|for scenes)\b",
            text.casefold(),
        ):
            continue

        raw_evidence = suggestion.get("evidence_scenes", [])
        if not isinstance(raw_evidence, list):
            continue
        evidence = list(dict.fromkeys(
            str(label).strip()
            for label in raw_evidence
            if str(label).strip() in available
        ))
        if len(evidence) < 2:
            continue

        key = note_key(text)
        duplicate = None
        for existing in result["learned_notes"]:
            ratio = SequenceMatcher(None, key, note_key(existing["note"])).ratio()
            if key == note_key(existing["note"]) or ratio >= 0.78:
                duplicate = existing
                break

        if duplicate is not None:
            duplicate["evidence_scenes"] = list(dict.fromkeys(
                duplicate.get("evidence_scenes", []) + evidence
            ))[-MAX_EVIDENCE_SCENES:]
            duplicate["last_updated_scene"] = reviewed_scene
            continue

        result["learned_notes"].append({
            "note": text,
            "evidence_scenes": evidence[-MAX_EVIDENCE_SCENES:],
            "last_updated_scene": reviewed_scene,
        })
        added += 1

    result["learned_notes"] = sorted(
        result["learned_notes"],
        key=lambda item: (
            len(item.get("evidence_scenes", [])),
            bool(item.get("last_updated_scene")),
        ),
        reverse=True,
    )[:MAX_LEARNED_NOTES]

    if reviewed_scene:
        result["reviewed_scenes"] = list(dict.fromkeys(
            result["reviewed_scenes"] + [reviewed_scene]
        ))[-MAX_REVIEWED_SCENES:]
    return result, added
