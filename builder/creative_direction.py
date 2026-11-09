from __future__ import annotations

from pathlib import Path
from typing import Any


_PROFILE_ROOT = Path(__file__).resolve().parents[1] / "profiles"


def _load_profiles(category: str) -> dict[str, str]:
    """Load reusable, app-wide prompt profiles from Markdown data files."""
    directory = _PROFILE_ROOT / category
    profiles: dict[str, str] = {}
    try:
        paths = sorted(directory.glob("*.md"))
    except OSError:
        return profiles

    for path in paths:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue

        lines = content.splitlines()
        heading_index = next(
            (index for index, line in enumerate(lines) if line.strip()),
            None,
        )
        if heading_index is None:
            continue

        heading = lines[heading_index].strip()
        if not heading.startswith("# "):
            continue

        label = heading[2:].strip()
        description = "\n".join(lines[heading_index + 1 :]).strip()
        if label and description and label not in profiles:
            profiles[label] = description

    return profiles


# Profile files, not Python constants, define the available genre and audience
# choices. Add a Markdown file to extend either list.
GENRE_PROFILES = _load_profiles("genres")
AUDIENCE_PROFILES = _load_profiles("audiences")
GENRE_OPTIONS = tuple(GENRE_PROFILES)
AUDIENCE_OPTIONS = tuple(AUDIENCE_PROFILES)

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
    """Build concise guidance from only the profiles selected for this novel."""
    profile = normalize_creative_direction(value, strict=False)
    lines: list[str] = []

    if profile["genres"]:
        lines.append("Genres: " + ", ".join(profile["genres"]))
        for genre in profile["genres"]:
            guidance = GENRE_PROFILES.get(genre)
            if guidance:
                lines.append(f"{genre} guidance: {guidance}")

    if profile["moods"]:
        lines.append("Mood and tone: " + ", ".join(profile["moods"]))

    if profile["audience"]:
        audience = profile["audience"]
        lines.append(f"Intended audience: {audience}")
        guidance = AUDIENCE_PROFILES.get(audience)
        if guidance:
            lines.append(f"{audience} audience guidance: {guidance}")

    if profile["explicit_adult_content"]:
        lines.append(
            "Explicit adult content is permitted when it serves the story; "
            "any sexual content must involve consenting adults. This is permission, "
            "not a request to include it."
        )
    else:
        lines.append(
            "Explicit adult content is not enabled. Do not include explicit sexual "
            "detail; keep intimacy non-graphic and consistent with the selected audience."
        )

    return (
        "CREATIVE DIRECTION (loose guidance, not a checklist)\n"
        + "\n".join(lines)
        + "\nLet these choices influence the overall flavor without forcing every "
        "genre or mood into every scene. Audience and explicit-content boundaries "
        "take priority over genre and mood conventions."
    )
