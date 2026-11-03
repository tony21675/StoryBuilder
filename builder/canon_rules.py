"""Formatting helpers for story-wide canon guidance."""

from __future__ import annotations

from typing import Any


def build_canon_rules_prompt(value: Any) -> str:
    """Render saved Canon Rules as concise context for planning and writing prompts."""
    if not isinstance(value, list):
        return ""

    rules = [
        " ".join(rule.split())
        for rule in value
        if isinstance(rule, str) and rule.strip()
    ]
    if not rules:
        return ""

    return (
        "CANON RULES (established story facts and author direction)\n"
        "Follow these established story facts and author directions unless the author changes them:\n"
        + "\n".join(f"- {rule}" for rule in rules)
    )
