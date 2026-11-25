from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from builder.odt_document import read_document
from builder.story_bible_reader import load_story_bible
from builder.character_context import (
    build_character_card_context_prompt,
    build_scene_cast_boundary_prompt,
)
from builder.story_timeline import build_story_timeline_prompt
from builder.scene_handoff import format_scene_handoff, load_scene_handoff\n

_SCENE_FILENAME_RE = re.compile(
    r"^Chapter_(\d+)_Section_(\d+)\.(?:odt|txt)$",
    re.IGNORECASE,
)

def scene_number_from_label(label: str | None) -> int | None:
    """Read the number from a visible Scene NN selector label."""
    match = re.fullmatch(r"Scene\s+(\d+)", str(label or "").strip(), re.IGNORECASE)
    return int(match.group(1)) if match else None


def next_scene_coordinates(
    selected_chapter: int | None,
    selected_scene_path: str | Path | None,
    selected_scene_number: int | None = None,
) -> tuple[int, int]:
    """Return the next scene after the selected scene, or the opening scene."""
    chapter = max(1, int(selected_chapter or 1))
    if selected_scene_path is not None:
        match = _SCENE_FILENAME_RE.fullmatch(Path(selected_scene_path).name)
        if match:
            return int(match.group(1)), int(match.group(2)) + 1
    if selected_scene_number is not None and int(selected_scene_number) >= 1:
        return chapter, int(selected_scene_number) + 1
    return chapter, 1


def resolve_scene_preparation_target(
    selected_chapter: int | None,
    selected_scene_path: str | Path | None,
    selected_scene_number: int | None = None,
    *,
    novel_path: str | Path | None = None,
    pending_destination: tuple[int, int] | None = None,
    pending_novel_path: str | Path | None = None,
    pending_source_scene_path: str | Path | None = None,
) -> tuple[int, int, Path | None, bool]:
    """Reuse an unsaved prepared scene when retrying; otherwise move past the selection."""
    chapter = max(1, int(selected_chapter or 1))
    current_position = (chapter, int(selected_scene_number or 0))

    same_novel = (
        novel_path is not None
        and pending_novel_path is not None
        and Path(novel_path).expanduser() == Path(pending_novel_path).expanduser()
    )
    is_retry = (
        same_novel
        and pending_destination is not None
        and current_position == pending_destination
        and selected_scene_path is None
    )
    if is_retry:
        previous_scene = (
            Path(pending_source_scene_path)
            if pending_source_scene_path is not None
            else None
        )
        return pending_destination[0], pending_destination[1], previous_scene, True

    target_chapter, target_scene = next_scene_coordinates(
        selected_chapter, selected_scene_path, selected_scene_number
    )
    previous_scene = (
        Path(selected_scene_path) if selected_scene_path is not None else None
    )
    return target_chapter, target_scene, previous_scene, False


def _read_current_state(novel_path: Path) -> dict[str, Any]:
    state_path = novel_path / "current_state.json"
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _clean_text(value: Any, limit: int = 600) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip() + "…"
    return text


def _planner_location_value(value: Any, *, depth: int = 0) -> str:
    """Render saved location details as readable Planner reference material."""
    if depth > 5 or value is None:
        return ""
    if isinstance(value, dict):
        entries = []
        for key, nested in value.items():
            rendered = _planner_location_value(nested, depth=depth + 1)
            if rendered:
                label = str(key).replace("_", " ").strip().title()
                entries.append(f"{label}: {rendered}")
        return "; ".join(entries)
    if isinstance(value, list):
        return "; ".join(
            rendered
            for item in value
            if (rendered := _planner_location_value(item, depth=depth + 1))
        )
    if isinstance(value, (str, int, float, bool)):
        return " ".join(str(value).split())
    return ""


def _build_planner_location_context(story_bible: dict[str, Any]) -> str:
    """Give Qwen the novel's established places without restricting invention."""
    locations = story_bible.get("locations")
    if not isinstance(locations, dict) or not locations:
        return ""

    lines = [
        "ESTABLISHED LOCATION REFERENCES FROM THIS NOVEL'S STORY BIBLE",
        "These entries describe places already established in this story and provide "
        "geographic and environmental context. They are references, not a restriction on "
        "creative invention or a requirement to include these places. Use them when "
        "relevant; new locations and details remain creative space unless they contradict "
        "established geography or household arrangements.",
    ]
    for name, details in locations.items():
        location_name = " ".join(str(name).split())
        if not location_name:
            continue
        lines.append(f"\n[{location_name}]")
        rendered = _planner_location_value(details)
        if rendered:
            if len(rendered) > 3200:
                rendered = rendered[:3197].rsplit(" ", 1)[0].rstrip() + "…"
            lines.append(rendered)
        else:
            lines.append("No additional details are recorded.")
    return "\n".join(lines)


def _previous_scene_text(path: str | Path | None) -> str:
    """Read the complete immediately preceding saved scene for planning context."""
    if path is None:
        return ""
    return read_document(path).strip()


def _state_matches_scene(
    state: dict[str, Any],
    chapter_number: int,
    scene_number: int,
    source_scene_path: str | Path | None,
) -> bool:
    try:
        state_position = (int(state.get("chapter")), int(state.get("scene")))
    except (TypeError, ValueError):
        return False

    if state_position == (chapter_number, scene_number):
        return True

    # Some packages save the state immediately after completing the previous
    # scene rather than at the start of the next one.
    if source_scene_path is not None:
        match = _SCENE_FILENAME_RE.fullmatch(Path(source_scene_path).name)
        if match:
            source_position = (int(match.group(1)), int(match.group(2)))
            return state_position == source_position and state.get("scene_completed") is True
    return False



def _normalized_scene_plan_section_heading(line: str) -> str:
    """Normalize a plain or Markdown-formatted scene-plan section heading."""
    value = re.sub(r"^\s*#{1,6}\s*", "", str(line or "").strip())
    value = re.sub(r"^\s*[-*+]\s+", "", value).strip()
    value = value.strip("*_").rstrip(":：").strip().strip("*_")
    return re.sub(r"[-_\s]+", " ", value).casefold()


def apply_author_required_beats(
    suggestion: str, author_direction: str | None
) -> str:
    """Place the author's exact direction in the required-beats section.

    Qwen is not trusted to classify or summarize author intent. StoryBuilder
    replaces its required-beat section after generation with the original
    Author's Direction, preserving every requested event and its wording.
    """
    lines = str(suggestion or "").strip().splitlines()
    direction = str(author_direction or "").strip()

    required_index = next(
        (
            index for index, line in enumerate(lines)
            if _normalized_scene_plan_section_heading(line) == "author required beats"
        ),
        None,
    )
    qwen_index = next(
        (
            index for index, line in enumerate(lines)
            if _normalized_scene_plan_section_heading(line)
            == "qwen selected additional beats"
        ),
        None,
    )

    # With no author direction there is nothing to inject. If Qwen did not
    # return a required-beats section, preserve its suggestion unchanged.
    if not direction and required_index is None:
        return "\n".join(lines).strip()

    if required_index is None:
        if qwen_index is not None:
            lines.insert(qwen_index, "AUTHOR-REQUIRED BEATS")
            required_index = qwen_index
            qwen_index += 1
        else:
            lines.extend(["", "AUTHOR-REQUIRED BEATS", "", "QWEN-SELECTED ADDITIONAL BEATS"])
            required_index = len(lines) - 3
            qwen_index = required_index + 2
    elif qwen_index is None:
        trailing = lines[required_index + 1:]
        lines = lines[:required_index + 1] + ["QWEN-SELECTED ADDITIONAL BEATS"] + trailing
        qwen_index = required_index + 1
    elif qwen_index < required_index:
        before_qwen = lines[:qwen_index]
        qwen_material = lines[qwen_index + 1:required_index]
        after_required = lines[required_index + 1:]
        lines = (
            before_qwen
            + ["AUTHOR-REQUIRED BEATS", "QWEN-SELECTED ADDITIONAL BEATS"]
            + qwen_material
            + after_required
        )
        required_index = len(before_qwen)
        qwen_index = required_index + 1

    author_lines = direction.splitlines() if direction else []
    return "\n".join(
        lines[:required_index + 1]
        + (["", *author_lines] if author_lines else [])
        + [""]
        + lines[qwen_index:]
    ).strip()


def blank_author_required_beats_when_unsteered(
    suggestion: str, author_direction: str | None
) -> str:
    """Backward-compatible alias for the deterministic author-beat safeguard."""
    return apply_author_required_beats(suggestion, author_direction)

def _planner_terms(value: str) -> set[str]:
    """Return meaningful words for lightweight scene-context matching."""
    stop_words = {
        "about", "after", "again", "also", "and", "are", "around", "because",
        "been", "before", "being", "between", "but", "did", "does", "during",
        "each", "for", "from", "had", "has", "have", "her", "him", "his",
        "into", "its", "just", "like", "more", "most", "not", "now", "only",
        "our", "out", "over", "said", "same", "she", "should", "some", "such",
        "than", "that", "the", "their", "them", "then", "there", "these",
        "they", "this", "those", "through", "told", "under", "very", "was",
        "were", "what", "when", "where", "which", "while", "who", "will",
        "with", "would", "you", "your", "scene", "story", "chapter",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").casefold())
        if len(token) >= 3 and token not in stop_words
    }


def _planner_previous_excerpt(value: str, limit: int = 1100) -> str:
    """Keep only the end of the preceding scene as a compact continuity anchor."""
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    excerpt = text[-limit:]
    first_space = excerpt.find(" ")
    if 0 <= first_space < 80:
        excerpt = excerpt[first_space + 1:]
    return excerpt.strip()


def _build_planner_relevant_story_context(
    story_bible: dict[str, Any],
    scene_text: str,
    cast_names: list[str],
) -> str:
    """Select a few story facts and relationships that matter to this scene."""
    query_terms = _planner_terms(scene_text)
    sections: list[str] = []

    canon = story_bible.get("canon_rules")
    if isinstance(canon, str):
        canon = [canon]
    ranked_canon = []
    if isinstance(canon, list):
        for index, raw in enumerate(canon):
            if not isinstance(raw, str) or not raw.strip():
                continue
            fact = " ".join(raw.split())
            fact_terms = _planner_terms(fact)
            overlap = len(query_terms & fact_terms)
            name_hits = sum(
                1 for name in cast_names
                if re.search(
                    rf"(?<![\w]){re.escape(name)}(?![\w])",
                    fact,
                    flags=re.IGNORECASE,
                )
            )
            # A character name alone is not enough to drag unrelated plot canon
            # into the Planner. Require at least one scene-specific term too.
            if overlap >= 2 or (overlap >= 1 and name_hits):
                ranked_canon.append((overlap * 3 + name_hits, index, fact))
    ranked_canon.sort(key=lambda item: (-item[0], item[1]))
    chosen_canon = [item[2] for item in ranked_canon[:5]]
    if chosen_canon:
        sections.append(
            "RELEVANT ESTABLISHED FACTS\n"
            + "\n".join(f"- {fact[:420]}" for fact in chosen_canon)
        )

    relationships = story_bible.get("relationships")
    ranked_relationships = []
    if isinstance(relationships, dict):
        for index, (label, raw) in enumerate(relationships.items()):
            description = " ".join(str(raw or "").split())
            relation = f"{label}: {description}"
            matching_people = [
                name for name in cast_names
                if re.search(
                    rf"(?<![\w]){re.escape(name)}(?![\w])",
                    relation,
                    flags=re.IGNORECASE,
                )
            ]
            overlap = len(query_terms & _planner_terms(relation))
            # Include a relationship only when it connects at least two people
            # selected for this scene, or is directly relevant in the author's
            # wording. This avoids sending every relationship in the novel.
            if len(matching_people) >= 2 and overlap >= 1:
                ranked_relationships.append(
                    (len(matching_people) * 3 + overlap, index, relation)
                )
    ranked_relationships.sort(key=lambda item: (-item[0], item[1]))
    chosen_relationships = [item[2] for item in ranked_relationships[:4]]
    if chosen_relationships:
        sections.append(
            "RELEVANT RELATIONSHIPS\n"
            + "\n".join(f"- {relation[:420]}" for relation in chosen_relationships)
        )

    return "\n\n".join(sections)


def _build_planner_location_context(
    story_bible: dict[str, Any],
    scene_text: str = "",
    current_location: str = "",
) -> str:
    """Include only established locations clearly connected to this scene."""
    locations = story_bible.get("locations")
    if not isinstance(locations, dict) or not locations:
        return ""

    search_text = f"{scene_text}\n{current_location}"
    search_terms = _planner_terms(search_text)
    selected = []
    for name, details in locations.items():
        location_name = " ".join(str(name).replace("_", " ").split())
        if not location_name:
            continue
        key_terms = _planner_terms(location_name)
        overlap = len(key_terms & search_terms)
        if location_name.casefold() in search_text.casefold() or overlap >= min(2, len(key_terms)):
            rendered = _planner_location_value(details)
            if len(rendered) > 520:
                rendered = rendered[:517].rsplit(" ", 1)[0].rstrip() + "…"
            selected.append((overlap, location_name, rendered))
    selected.sort(key=lambda item: (-item[0], item[1]))
    if not selected:
        return ""

    lines = ["RELEVANT LOCATION"]
    for _overlap, name, details in selected[:2]:
        lines.append(f"- {name}: {details or 'No additional details recorded.'}")
    return "\n".join(lines)


def build_scene_preparation_prompt(
    novel_path: str | Path,
    novel_name: str,
    chapter_number: int,
    scene_number: int,
    source_scene_path: str | Path | None = None,
    author_direction: str | None = None,
    previous_direction: str | None = None,
    scene_cast: list[str] | None = None,
) -> str:
    """Build a compact, scene-focused request for the Planner."""
    root = Path(novel_path).expanduser()
    try:
        story_bible = load_story_bible(root)
    except FileNotFoundError:
        story_bible = {}

    current_state = _read_current_state(root)
    include_state = _state_matches_scene(
        current_state, int(chapter_number), int(scene_number), source_scene_path
    )

    previous_text = _previous_scene_text(source_scene_path)
    saved_handoff = (
        load_scene_handoff(source_scene_path, previous_text)
        if source_scene_path and previous_text
        else None
    )
    previous_ending = (
        format_scene_handoff(
            saved_handoff,
            int(chapter_number) if int(chapter_number) else 1,
            int(scene_number) if int(scene_number) else 1,
        )
        if saved_handoff
        else _planner_previous_excerpt(previous_text)
    )
    title = _clean_text(story_bible.get("title"), limit=100) or _clean_text(
        novel_name, limit=100
    )
    author_direction_text = str(author_direction or "").strip()
    previous_direction_text = _clean_text(previous_direction, limit=900)

    primary_location = ""
    situation = ""
    continuity_notes: list[str] = []
    unresolved_questions: list[str] = []
    state_cast: list[str] = []
    if include_state:
        situation = _clean_text(current_state.get("current_situation"), limit=420)
        location_value = current_state.get("location")
        if isinstance(location_value, dict):
            primary_location = _clean_text(location_value.get("primary"), limit=120)
        elif isinstance(location_value, str):
            primary_location = _clean_text(location_value, limit=120)

        raw_notes = current_state.get("continuity_notes")
        if isinstance(raw_notes, list):
            continuity_notes = [
                _clean_text(note, limit=260)
                for note in raw_notes
                if isinstance(note, str) and note.strip()
            ]

        raw_questions = current_state.get("unresolved_questions")
        if isinstance(raw_questions, list):
            unresolved_questions = [
                _clean_text(question, limit=140)
                for question in raw_questions
                if isinstance(question, str) and question.strip()
            ][:1]

        raw_cast = current_state.get("scene_cast")
        if isinstance(raw_cast, list):
            state_cast = [
                _clean_text(name, limit=80)
                for name in raw_cast
                if isinstance(name, str) and name.strip()
            ][:6]

    cast_names = (
        [_clean_text(name, limit=80) for name in scene_cast if isinstance(name, str) and name.strip()]
        if scene_cast is not None
        else state_cast
    )
    cast_names = list(dict.fromkeys(name for name in cast_names if name))

    scene_reference_text = "\n".join(
        part for part in (
            author_direction_text,
            previous_direction_text,
            previous_ending,
            situation,
            primary_location,
        ) if part
    )
    sections = [
        "Prepare one scene direction for the author. This is planning, not manuscript prose.",
        f"Destination: Chapter {int(chapter_number):02d}, Scene {int(scene_number):02d}.",
        f"Story: {title}",
    ]

    premise = _clean_text(story_bible.get("premise"), limit=850)
    setting = _clean_text(story_bible.get("setting"), limit=900)
    if premise:
        sections.append(f"Story premise: {premise}")
    if setting:
        sections.append(f"Setting: {setting}")

    if cast_names:
        sections.append("SELECTED SCENE CAST\n" + ", ".join(cast_names))

    relevant_story = _build_planner_relevant_story_context(
        story_bible, scene_reference_text, cast_names
    )
    if relevant_story:
        sections.append(relevant_story)

    location_context = _build_planner_location_context(
        story_bible, scene_reference_text, primary_location
    )
    if location_context:
        sections.append(location_context)

    timeline_note = build_story_timeline_prompt(current_state.get("time_of_day"))
    if timeline_note:
        sections.append(timeline_note)

    if include_state:
        if situation:
            sections.append("CURRENT SCENE SITUATION\n" + situation)
        if primary_location:
            sections.append("CURRENT LOCATION\n" + primary_location)
        if continuity_notes:
            note_terms = _planner_terms(scene_reference_text)
            relevant_notes = [
                note for note in continuity_notes
                if len(_planner_terms(note) & note_terms) >= 1
                or any(
                    re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", note, re.IGNORECASE)
                    for name in cast_names
                )
            ][:3]
            if relevant_notes:
                sections.append(
                    "RELEVANT CONTINUITY NOTES\n"
                    + "\n".join(f"- {note}" for note in relevant_notes)
                )
        if unresolved_questions:
            question_terms = _planner_terms(unresolved_questions[0])
            if len(question_terms & _planner_terms(scene_reference_text)) >= 1:
                sections.append("OPEN QUESTION\n" + unresolved_questions[0])

    character_supporting_text = "\n".join(
        part for part in (
            " ".join(cast_names),
            scene_reference_text,
        ) if part
    )
    character_context = build_character_card_context_prompt(
        root,
        story_bible,
        "",
        supporting_text=character_supporting_text,
        include_all=False,
        compact=True,
        comprehensive=False,
        selected_names=cast_names if scene_cast is not None or cast_names else None,
        scene_focused=True,
    )
    if character_context:
        sections.append(character_context)

    if previous_ending:
        sections.append(
            "PREVIOUS SCENE ENDING (continuity only; earlier material omitted)\n"
            + previous_ending
        )
    elif (int(chapter_number), int(scene_number)) == (1, 1):
        sections.append("This is the opening scene; no previous scene has been saved.")

    if previous_direction_text:
        sections.append(
            "PREVIOUS PREPARED DIRECTION TO REFINE\n"
            + previous_direction_text
            + "\nRefine the previous direction rather than starting over."
        )

    if author_direction_text:
        sections.append("AUTHOR'S DIRECTION\n" + author_direction_text)

    sections.extend([
        "PLANNING GUARDRAILS\n"
        "Preserve established facts, relationships, households, schedules, and important possessions. "
        "Use only the selected cast. Do not replay events already completed, add another scene, or move "
        "past the requested scene's natural endpoint. Unknown details remain unknown; do not turn guesses "
        "into established backstory or memories.",
        "RETURN FORMAT\n"
        "Return a short 'Scene direction:' paragraph of 2–4 sentences describing where this scene "
        "starts, its broad movement, and where it naturally stops. Then include "
        "'AUTHOR-REQUIRED BEATS' as an empty heading only; StoryBuilder inserts the author's exact "
        "direction there. Do not repeat or paraphrase the author's direction anywhere in your reply. "
        "Then include 'QWEN-SELECTED ADDITIONAL BEATS' with zero to three short bullets only if you "
        "have genuinely useful additions not already requested. Otherwise leave that section empty. "
        "Use plain novel-planning language, not screenplay format, script labels, camera directions, "
        "scripted dialogue, finished prose, or separate Setting/Tone/Atmosphere essays. Leave ordinary "
        "dialogue, gestures, staging, and connective prose to the Writer.",
    ])

    if scene_cast is not None:
        sections.append(build_scene_cast_boundary_prompt("", scene_cast))

    return "\n\n".join(part for part in sections if part)
