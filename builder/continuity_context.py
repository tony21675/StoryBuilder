from __future__ import annotations

import math
import re
from typing import Any


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP_WORDS = {
    "about", "after", "again", "against", "also", "and", "are", "around", "because",
    "been", "before", "being", "between", "but", "came", "could", "did", "does",
    "during", "each", "from", "get", "got", "had", "has", "have", "her", "hers",
    "him", "his", "into", "its", "just", "know", "knows", "learned", "like", "made",
    "make", "more", "most", "near", "not", "now", "onto", "our", "out", "over",
    "said", "same", "she", "should", "some", "such", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "this", "those", "through", "told",
    "under", "very", "was", "were", "what", "when", "where", "which", "while", "who",
    "will", "with", "would", "you", "your", "scene", "story", "current", "state",
    "character", "chapter", "writer", "direction", "beginning", "ending", "continue",
}
# These are cues for preserving facts in the active prompt, not rules for deleting
# the persistent ledger. They intentionally favor false positives over losing canon.
_PROTECTED_FACT = re.compile(
    r"\b(?:daughter|son|mother|father|wife|husband|partner|sister|brother|"
    r"promis\w*|secret\w*|abduct\w*|kidnap\w*|missing|injur\w*|wound\w*|scar\w*|"
    r"scratch\w*|clue\w*|evidence|license plate|van|witness\w*|threat\w*|boundary|"
    r"nickname|accepted it|trust\w*|betray\w*|letter|emergenc\w*|died|death|birth|"
    r"told (?:him|her|them)|learned from|does not know|doesn't know|unidentified|"
    r"first time|for the first time|relationship|engaged|married|divorc\w*|"
    r"afraid of|allergic|medication|diagnos\w*|timeline|deadline|birthday|anniversary|"
    r"before sunrise|before dawn|after midnight|sunrise|hours later|tomorrow|yesterday|"
    r"attack|assault|violence|shot|stab\w*|strangl\w*|drug\w*|poison\w*|chok\w*|"
    r"blood|bleed\w*|punch\w*|hit by|grabbed|forced|rescued|escaped|police|fingerprint|"
    r"scent|smell\w*|cigarette|cologne|pine needle)\b",
    re.IGNORECASE,
)
_DISPOSABLE_DETAIL = re.compile(
    r"\b(?:soda|pop|cola|soft drink|coffee|tea|juice|water|lemonade|"
    r"breakfast|lunch|dinner|snack|sandwich|pizza|burger|fries|chips|cookie|"
    r"routin\w*|walked to|sat down|stood up|opened the door|closed the door|"
    r"picked up the mug|poured a drink|weather was|sunlight fell|wind moved)\b",
    re.IGNORECASE,
)


def relevance_tokens(value: str) -> set[str]:
    """Return normalized search terms for lightweight lexical context selection."""
    tokens = set()
    for token in _TOKEN_RE.findall(str(value or "").casefold()):
        if len(token) < 3 or token in _STOP_WORDS:
            continue
        if token == "drank":
            token = "drink"
        elif token.endswith("s") and len(token) > 4:
            token = token[:-1]
        elif token.endswith("ed") and len(token) > 5:
            token = token[:-2]
        tokens.add(token)
    return tokens


def is_protected_continuity_fact(value: str) -> bool:
    """Whether a fact has obvious durable/consequential continuity value."""
    return bool(_PROTECTED_FACT.search(str(value or "")))


def is_low_value_detail(value: str) -> bool:
    """Flag routine detail for deprioritization only; never delete it from its source."""
    return bool(_DISPOSABLE_DETAIL.search(str(value or ""))) and not is_protected_continuity_fact(value)


def select_active_character_knowledge(
    knowledge_by_character: dict[str, list[str]],
    query: str,
    *,
    max_items_per_character: int = 18,
    max_total_items: int = 72,
) -> tuple[dict[str, list[str]], dict[str, int]]:
    """Select a bounded, relevant view while leaving the persistent ledger unchanged.

    Protected facts receive a strong priority boost. Routine details are merely
    deprioritized unless the current scene explicitly makes them relevant.
    """
    query_terms = relevance_tokens(query)
    character_terms = set()
    for character in knowledge_by_character:
        character_terms.update(relevance_tokens(str(character)))
    detail_query_terms = query_terms - character_terms
    ranked_by_character: dict[str, list[tuple[float, int, str]]] = {}
    before_items = 0
    before_chars = 0
    for character, raw_values in knowledge_by_character.items():
        if not isinstance(raw_values, list):
            continue
        ranked = []
        for index, raw in enumerate(raw_values):
            value = str(raw or "").strip()
            if not value:
                continue
            before_items += 1
            before_chars += len(value)
            terms = relevance_tokens(value)
            overlap = len(terms & query_terms)
            detail_overlap = len(terms & detail_query_terms)
            protected = is_protected_continuity_fact(value)
            low_value = is_low_value_detail(value)
            recent_bonus = 1.5 if index >= max(0, len(raw_values) - 4) else 0
            score = overlap * 3.0 + recent_bonus + (12.0 if protected else 0.0)
            if low_value and detail_overlap == 0:
                score -= 7.0
            if score <= 0:
                continue
            ranked.append((score, index, value))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        ranked_by_character[str(character)] = ranked[:max_items_per_character]

    selected_by_character: dict[str, list[tuple[int, str]]] = {
        name: [] for name in ranked_by_character
    }
    total = 0
    rank_depth = 0
    character_order = list(ranked_by_character)
    while total < max_total_items:
        added_this_round = False
        for character in character_order:
            ranked = ranked_by_character[character]
            if rank_depth >= len(ranked):
                continue
            _score, index, value = ranked[rank_depth]
            selected_by_character[character].append((index, value))
            total += 1
            added_this_round = True
            if total >= max_total_items:
                break
        if not added_this_round:
            break
        rank_depth += 1

    selected = {
        name: [value for _index, value in sorted(values, key=lambda item: item[0])]
        for name, values in selected_by_character.items()
        if values
    }
    after_chars = sum(len(value) for values in selected.values() for value in values)
    after_items = sum(len(values) for values in selected.values())
    metrics = {
        "before_items": before_items,
        "after_items": after_items,
        "before_chars": before_chars,
        "after_chars": after_chars,
        "before_estimated_tokens": estimate_tokens_from_chars(before_chars),
        "after_estimated_tokens": estimate_tokens_from_chars(after_chars),
        "reduction_percent": round((before_chars - after_chars) * 100 / before_chars, 1)
        if before_chars else 0.0,
    }
    return selected, metrics


def select_relevant_records(
    records: list[dict[str, Any]],
    query: str,
    *,
    text_key: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Rank short advisory records such as writer notes without changing storage."""
    query_terms = relevance_tokens(query)
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        text = str(record.get(text_key, "") or "").strip()
        if not text:
            continue
        overlap = len(relevance_tokens(text) & query_terms)
        if overlap:
            ranked.append((overlap, index, record))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [record for _score, _index, record in ranked[:max(0, int(limit))]]


def estimate_tokens_from_chars(char_count: int) -> int:
    """Approximate tokens from characters only; not a replacement for model tokenization."""
    return math.ceil(max(0, int(char_count)) / 4)


def context_size_report(text: str) -> dict[str, int]:
    """Report reproducible character and rough token counts for a prompt/context string."""
    return {
        "characters": len(text or ""),
        "estimated_tokens": estimate_tokens_from_chars(len(text or "")),
    }
