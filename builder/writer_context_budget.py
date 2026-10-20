from __future__ import annotations

import json
import math
import os
from typing import Callable, Any


CONSERVATIVE_CHARS_PER_TOKEN = 3
DEFAULT_CONTEXT_TOKENS = 16384
DEFAULT_OUTPUT_TOKENS = 4000
DEFAULT_SAFETY_MARGIN_TOKENS = 2400

# Optional references are removed in this order. Scene contract/current state,
# opening physical continuity, canon, and stable author guidance are protected.
_DROP_ORDER = (
    "working_writer_notes.json",
    "supporting_people_context.json",
    "scene_relationships.json",
    "offscene_character_anchors.json",
    "relevant_relationship_facts.json",
)
_LOCKED_REFERENCES = {
    "scene_state.json",
    "scene_physical_state.json",
    "author_defined_canon_rules.txt",
    "author_writing_guidance.txt",
}


class WriterContextBudgetError(ValueError):
    """Raised when required scene context cannot fit inside the safe input budget."""


def conservative_token_estimate(text: str, chars_per_token: int = CONSERVATIVE_CHARS_PER_TOKEN) -> int:
    """Conservative, deterministic estimate for safety budgeting, not tokenizer billing."""
    return math.ceil(len(text or "") / max(1, int(chars_per_token)))


def _bounded_value(value: Any, *, depth: int = 0) -> Any:
    """Bound an overlong character-card value while keeping its useful shape."""
    if depth >= 3:
        return value[:240] if isinstance(value, str) else value
    if isinstance(value, str):
        return value[:600]
    if isinstance(value, list):
        return [_bounded_value(item, depth=depth + 1) for item in value[:8]]
    if isinstance(value, dict):
        return {
            str(key): _bounded_value(item, depth=depth + 1)
            for key, item in list(value.items())[:10]
        }
    return value


def compact_character_cards(text: str) -> str | None:
    """Keep scene-useful card fields if full biographies crowd out the scene prompt."""
    try:
        cards = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(cards, dict):
        return None

    useful_hints = (
        "name", "age", "gender", "pronoun", "role", "appearance", "physical",
        "personality", "trait", "voice", "speech", "accent", "relationship",
        "nickname", "family", "clothing", "occupation", "temperament",
    )
    compact: dict[str, Any] = {}
    for character, raw_card in cards.items():
        if not isinstance(raw_card, dict):
            compact[str(character)] = _bounded_value(raw_card)
            continue
        selected = {
            str(key): _bounded_value(value)
            for key, value in raw_card.items()
            if any(hint in str(key).casefold() for hint in useful_hints)
        }
        if not selected:
            selected = {
                str(key): _bounded_value(value)
                for key, value in list(raw_card.items())[:4]
            }
        compact[str(character)] = selected
    rendered = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    return rendered if rendered != text else None


def _shrink_knowledge_once(text: str) -> str | None:
    """Remove one lowest-ranked tail fact from the transient active view only."""
    try:
        knowledge = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(knowledge, dict):
        return None
    candidates = [
        (len(values), str(name), name)
        for name, values in knowledge.items()
        if isinstance(values, list) and len(values) > 1
    ]
    if not candidates:
        if any(isinstance(values, list) and values for values in knowledge.values()):
            return json.dumps(
                {name: [] for name, values in knowledge.items() if isinstance(values, list)},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        return None
    _count, _name_text, name = max(candidates)
    knowledge[name] = knowledge[name][:-1]
    return json.dumps(knowledge, ensure_ascii=False, separators=(",", ":"))


def fit_writer_context_files(
    files: list[tuple[str, str]],
    *,
    prompt_builder: Callable[[list[tuple[str, str]]], str],
    base_prompt: str = "",
    context_window_tokens: int | None = None,
    reserved_output_tokens: int | None = None,
    safety_margin_tokens: int | None = None,
    chars_per_token: int = CONSERVATIVE_CHARS_PER_TOKEN,
) -> tuple[list[tuple[str, str]], dict[str, Any]]:
    """Bound the entire Writer input while reserving room for prose and follow-up checks.

    This only prunes a transient prompt view. The persistent novel state, accepted
    manuscript, character cards, writing notes, and historical archive are untouched.
    """
    context_window_tokens = int(
        context_window_tokens if context_window_tokens is not None
        else os.environ.get("STORY_WRITER_CONTEXT", DEFAULT_CONTEXT_TOKENS)
    )
    reserved_output_tokens = int(
        reserved_output_tokens if reserved_output_tokens is not None
        else os.environ.get("STORY_WRITER_MAX_TOKENS", DEFAULT_OUTPUT_TOKENS)
    )
    safety_margin_tokens = int(
        safety_margin_tokens if safety_margin_tokens is not None
        else os.environ.get("STORY_WRITER_CONTEXT_MARGIN", DEFAULT_SAFETY_MARGIN_TOKENS)
    )
    input_token_budget = context_window_tokens - reserved_output_tokens - safety_margin_tokens
    if input_token_budget < 256:
        raise WriterContextBudgetError(
            "Writer context settings leave too little room for input. Increase STORY_WRITER_CONTEXT "
            "or reduce STORY_WRITER_MAX_TOKENS / STORY_WRITER_CONTEXT_MARGIN."
        )

    working = [(str(name), str(content)) for name, content in files]
    original_prompt = prompt_builder(working) + (base_prompt or "")
    original_characters = len(original_prompt)
    original_estimate = conservative_token_estimate(original_prompt, chars_per_token)
    removed: list[str] = []
    compacted: list[str] = []
    reduced_knowledge_facts = 0

    def render() -> str:
        return prompt_builder(working) + (base_prompt or "")

    def find_index(filename: str) -> int | None:
        for index, (name, _content) in enumerate(working):
            if name == filename:
                return index
        return None

    def remove_reference(filename: str) -> bool:
        index = find_index(filename)
        if index is None or filename in _LOCKED_REFERENCES:
            return False
        working.pop(index)
        removed.append(filename)
        return True

    while conservative_token_estimate(render(), chars_per_token) > input_token_budget:
        # First shed incidental notebooks and redundant supporting references.
        dropped = False
        for filename in _DROP_ORDER:
            if remove_reference(filename):
                dropped = True
                break
        if dropped:
            continue

        # Compact character cards before excluding them. Keep names, appearance,
        # personality, voice, relationships, and other scene-writing attributes.
        index = find_index("scene_characters.json")
        if index is not None:
            name, content = working[index]
            compacted_content = compact_character_cards(content)
            if compacted_content and compacted_content != content:
                working[index] = (name, compacted_content)
                compacted.append(name)
                continue
            remove_reference(name)
            continue

        # Selected character knowledge is already relevance-ranked. Drop its
        # lowest-ranked tail facts one at a time only when required for safety.
        index = find_index("scene_character_knowledge.json")
        if index is not None:
            name, content = working[index]
            reduced = _shrink_knowledge_once(content)
            if reduced is not None and reduced != content:
                reduced_knowledge_facts += 1
                working[index] = (name, reduced)
                continue
            remove_reference(name)
            continue

        # Historical excerpts are useful but optional; keep them only when they fit.
        if remove_reference("historical_continuity_archive.txt"):
            continue

        optional = next(
            (name for name, _content in reversed(working) if name not in _LOCKED_REFERENCES),
            None,
        )
        if optional is not None:
            remove_reference(optional)
            continue

        final_prompt = render()
        final_estimate = conservative_token_estimate(final_prompt, chars_per_token)
        raise WriterContextBudgetError(
            "Required Writer context still exceeds the safe input budget after pruning optional references. "
            f"Estimated input: {final_estimate:,} tokens; budget: {input_token_budget:,}. "
            "The current Scene Idea/contract or required author guidance is too large. "
            "Shorten that material; StoryBuilder did not start scene generation."
        )

    final_prompt = render()
    final_estimate = conservative_token_estimate(final_prompt, chars_per_token)
    if final_estimate > input_token_budget:
        raise WriterContextBudgetError(
            f"Writer prompt exceeds the safe input budget ({final_estimate:,} > {input_token_budget:,} estimated tokens)."
        )

    return working, {
        "context_window_tokens": context_window_tokens,
        "reserved_output_tokens": reserved_output_tokens,
        "safety_margin_tokens": safety_margin_tokens,
        "input_token_budget": input_token_budget,
        "chars_per_token_for_budget": max(1, int(chars_per_token)),
        "original_prompt_characters": original_characters,
        "final_prompt_characters": len(final_prompt),
        "original_conservative_tokens": original_estimate,
        "final_conservative_tokens": final_estimate,
        "pruned_reference_files": removed,
        "compacted_reference_files": list(dict.fromkeys(compacted)),
        "reduced_knowledge_facts": reduced_knowledge_facts,
        "included_reference_files": [name for name, _content in working],
    }
