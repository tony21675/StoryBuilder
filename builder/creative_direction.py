from __future__ import annotations

from typing import Any


GENRE_OPTIONS = (
    "Adventure",
    "Comedy",
    "Crime",
    "Drama",
    "Fantasy",
    "Historical",
    "Horror",
    "Literary",
    "Mystery",
    "Romance",
    "Science Fiction",
    "Suspense",
    "Thriller",
    "Western",
)

MOOD_OPTIONS = (
    "Cozy",
    "Dark",
    "Emotional",
    "Gritty",
    "Hopeful",
    "Humorous",
    "Lighthearted",
    "Melancholy",
    "Serious",
    "Tense",
    "Whimsical",
)

AUDIENCE_OPTIONS = ("Children's", "Middle Grade", "Young Adult", "Adult")

DEFAULT_CREATIVE_DIRECTION = {
    "genres": [],
    "moods": [],
    "audience": "",
    "explicit_adult_content": False,
}


def _normalize_choices(
    value: Any, allowed: tuple[str, ...], label: str, *, strict: bool
) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        if strict:
            raise ValueError(f"{label} must be a list of selections.")
        return []
    selected: list[str] = []
    for item in value:
        if not isinstance(item, str) or item not in allowed:
            if strict:
                raise ValueError(f"{label} contains an unsupported selection: {item!r}.")
            continue
        if item not in selected:
            selected.append(item)
    return selected


def normalize_creative_direction(
    value: Any, *, strict: bool = True
) -> dict[str, Any]:
    """Return the supported, JSON-friendly creative direction fields."""
    if value is None:
        value = {}
    if not isinstance(value, dict):
        if strict:
            raise ValueError("Creative Direction must be a collection of selections.")
        value = {}

    genres = _normalize_choices(
        value.get("genres", []), GENRE_OPTIONS, "Genres", strict=strict
    )
    moods = _normalize_choices(
        value.get("moods", []), MOOD_OPTIONS, "Mood & Tone", strict=strict
    )

    audience = value.get("audience", "")
    if audience is None:
        audience = ""
    if not isinstance(audience, str) or audience not in ("", *AUDIENCE_OPTIONS):
        if strict:
            raise ValueError("Audience contains an unsupported selection.")
        audience = ""

    explicit = value.get("explicit_adult_content", False)
    if not isinstance(explicit, bool):
        if strict:
            raise ValueError("Explicit Adult Content must be true or false.")
        explicit = False
    if explicit and audience != "Adult":
        if strict:
            raise ValueError(
                "Explicit Adult Content can only be selected for an Adult audience."
            )
        explicit = False

    return {
        "genres": genres,
        "moods": moods,
        "audience": audience,
        "explicit_adult_content": explicit,
    }


def format_creative_direction_preview(value: Any) -> str:
    """Format selections for a readable, compact Story Bible preview."""
    profile = normalize_creative_direction(value, strict=False)
    lines: list[str] = []
    if profile["genres"]:
        lines.append("Genres: " + ", ".join(profile["genres"]))
    if profile["moods"]:
        lines.append("Mood & tone: " + ", ".join(profile["moods"]))
    if profile["audience"]:
        lines.append("Audience: " + profile["audience"])
    if profile["explicit_adult_content"]:
        lines.append("Content level: Explicit adult content (consenting adults only)")
    return "\n".join(lines) if lines else "Not specified."


def build_creative_direction_prompt(value: Any) -> str:
    """Create a light-touch creative note for local writing and planning prompts."""
    profile = normalize_creative_direction(value, strict=False)
    lines: list[str] = []
    if profile["genres"]:
        lines.append("Genres: " + ", ".join(profile["genres"]))
    if profile["moods"]:
        lines.append("Mood and tone: " + ", ".join(profile["moods"]))
    if profile["audience"]:
        lines.append("Intended audience: " + profile["audience"])
    if profile["explicit_adult_content"]:
        lines.append(
            "Explicit adult content is permitted when it suits the story; "
            "any sexual content must involve consenting adults."
        )
    if not lines:
        return ""
    return (
        "CREATIVE DIRECTION (loose guidance, not a checklist)\n"
        + "\n".join(lines)
        + "\nLet these choices influence the overall flavor without forcing "
        "every genre or mood into every scene. Let the scene and characters "
        "develop naturally."
    )
