"""Compact scene-to-scene continuity handoffs.

Handoffs are supporting notes derived from accepted manuscript text. They are kept
separate from canon and are invalidated when their source scene changes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HANDOFF_VERSION = 1
HANDOFF_FIELDS = (
    "ending",
    "events",
    "character_knowledge",
    "physical_continuity",
    "unresolved",
)


def scene_fingerprint(scene_text: str) -> str:
    return hashlib.sha256(str(scene_text or "").encode("utf-8")).hexdigest()


def handoff_path(scene_path: str | Path) -> Path:
    source = Path(scene_path)
    return source.with_name(source.name + ".continuity.json")


def normalize_handoff(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    cleaned: dict[str, Any] = {}
    for key in HANDOFF_FIELDS:
        item = value.get(key)
        if key == "ending":
            if isinstance(item, str) and item.strip():
                cleaned[key] = item.strip()
        else:
            if isinstance(item, list):
                cleaned[key] = [str(entry).strip() for entry in item if str(entry).strip()]
            elif isinstance(item, dict):
                cleaned[key] = {
                    str(name).strip(): str(detail).strip()
                    for name, detail in item.items()
                    if str(name).strip() and str(detail).strip()
                }
    return cleaned if cleaned.get("ending") else None


def load_scene_handoff(scene_path: str | Path, scene_text: str) -> dict[str, Any] | None:
    """Load only a handoff whose source fingerprint matches the current accepted scene."""
    target = handoff_path(scene_path)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("version") != HANDOFF_VERSION:
        return None
    if data.get("source_sha256") != scene_fingerprint(scene_text):
        return None
    return normalize_handoff(data.get("handoff"))


def save_scene_handoff(scene_path: str | Path, scene_text: str, handoff: dict[str, Any]) -> Path:
    """Save a validated handoff beside the scene, without modifying manuscript text."""
    normalized = normalize_handoff(handoff)
    if normalized is None:
        raise ValueError("A handoff must contain a non-empty ending description.")
    target = handoff_path(scene_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": HANDOFF_VERSION,
        "source_sha256": scene_fingerprint(scene_text),
        "handoff": normalized,
    }
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def build_handoff_extraction_prompt(chapter: int, scene: int, accepted_scene: str) -> str:
    """Request a factual continuity record from the accepted manuscript."""
    text = str(accepted_scene or "").strip()
    if not text:
        raise ValueError("The accepted scene is empty.")
    return (
        "Extract a compact continuity handoff from the ACCEPTED SCENE below. "
        "Describe only facts actually established by the manuscript. Do not treat "
        "the original prompt, guesses, or implied possibilities as facts. If a detail "
        "is uncertain, leave it out. Keep character knowledge separate. Do not invent "
        "events or resolve mysteries.\n\n"
        f"Source: Chapter {int(chapter):02d}, Scene {int(scene):02d}.\n\n"
        "Return one JSON object with exactly these fields:\n"
        "{\n"
        '  "ending": "where, when, who is present, and the final action or moment",\n'
        '  "events": ["important events in order"],\n'
        '  "character_knowledge": {"Character": "what they know, saw, said, or suspect"},\n'
        '  "physical_continuity": ["important object positions, conditions, or changes"],\n'
        '  "unresolved": ["open questions, promises, unfinished actions, or threads"]\n'
        "}\n\n"
        "Use concise factual entries. Avoid prose flourishes and redundant details. "
        "The accepted scene is the sole evidence source.\n\n"
        "ACCEPTED SCENE:\n"
        + text
    )


def parse_handoff_response(response: str) -> dict[str, Any] | None:
    """Parse JSON handoff output, allowing a surrounding Markdown code fence."""
    raw = str(response or "").strip()
    if not raw:
        return None
    raw = raw.removeprefix("```json").removeprefix("```").strip()
    if raw.endswith("```"):
        raw = raw[:-3].strip()
    try:
        return normalize_handoff(json.loads(raw))
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            return normalize_handoff(json.loads(raw[start:end + 1]))
        except json.JSONDecodeError:
            return None


def format_scene_handoff(handoff: dict[str, Any], chapter: int, scene: int) -> str:
    normalized = normalize_handoff(handoff)
    if normalized is None:
        return ""
    lines = [
        "SCENE-TO-SCENE CONTINUITY HANDOFF (facts extracted from the accepted prior scene)",
        f"Source: Chapter {int(chapter):02d}, Scene {int(scene):02d}",
        "Use this as continuity reference, not as instructions to repeat the scene. "
        "Story Bible canon and current author direction remain authoritative.",
        "ENDING / STARTING POINT:",
        normalized["ending"],
    ]
    for field, heading in (
        ("events", "EVENTS IN ORDER"),
        ("character_knowledge", "CHARACTER KNOWLEDGE"),
        ("physical_continuity", "PHYSICAL CONTINUITY"),
        ("unresolved", "UNRESOLVED THREADS"),
    ):
        items = normalized.get(field)
        if not items:
            continue
        lines.append(heading)
        if isinstance(items, dict):
            lines.extend(f"- {name}: {detail}" for name, detail in items.items())
        else:
            lines.extend(f"- {item}" for item in items)
    return "\n".join(lines)
