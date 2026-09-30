from __future__ import annotations

import re

FIELD_ALIASES = {
    "age": "age",
    "occupation": "occupation",
    "job": "occupation",
    "description": "description",
    "personality": "personality",
    "background": "background",
    "hair": "hair",
    "hair color": "hair",
    "eyes": "eyes",
    "eye color": "eyes",
}


class ChangeResult:
    def __init__(self, changed: bool, message: str) -> None:
        self.changed = changed
        self.message = message


def apply_command(package, command: str) -> ChangeResult:
    text = command.strip()
    if not text:
        return ChangeResult(False, "Tell me what you want to change.")

    match = re.fullmatch(
        r"(?:change|set) (?:the )?story title to (.+)",
        text,
        re.IGNORECASE,
    )
    if match:
        title = match.group(1).strip().strip('"')
        package.story_bible["title"] = title
        return ChangeResult(True, f'Story title changed to "{title}".')

    match = re.fullmatch(
        r"(?:change|set) (?:the )?premise to (.+)",
        text,
        re.IGNORECASE,
    )
    if match:
        package.story_bible["premise"] = match.group(1).strip().strip('"')
        return ChangeResult(True, "Story premise updated.")

    match = re.fullmatch(
        r"(?:set|change) (?:the )?(?:current )?chapter to (\d+)",
        text,
        re.IGNORECASE,
    )
    if match:
        package.current_state["chapter"] = int(match.group(1))
        return ChangeResult(True, f"Current chapter set to {match.group(1)}.")

    match = re.fullmatch(
        r"(?:set|change) (?:the )?(?:current )?scene to (\d+)",
        text,
        re.IGNORECASE,
    )
    if match:
        package.current_state["scene"] = int(match.group(1))
        return ChangeResult(True, f"Current scene set to {match.group(1)}.")

    match = re.fullmatch(
        r"(?:change|set) ([A-Za-z][A-Za-z0-9 _'-]*)'s (.+?) to (.+)",
        text,
        re.IGNORECASE,
    )
    if match:
        name, raw_field, value = match.groups()
        found = package.character_by_name(name)
        if found is None:
            return ChangeResult(False, f"I couldn't find a character named {name.strip()}.")

        _, character = found
        field = FIELD_ALIASES.get(raw_field.strip().casefold())
        if field is None:
            field = raw_field.strip().lower().replace(" ", "_")

        value = value.strip().strip('"')
        if field == "age":
            try:
                value_to_store = int(value)
            except ValueError:
                return ChangeResult(False, "Age needs to be a whole number.")
        else:
            value_to_store = value

        character[field] = value_to_store
        return ChangeResult(True, f"{name.strip()}'s {raw_field.strip()} was changed.")

    return ChangeResult(
        False,
        'I did not recognize that change yet. Try "Change Maya\'s age to 22" or use the editor tabs.',
    )
