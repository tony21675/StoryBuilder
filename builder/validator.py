from __future__ import annotations

def validate_package(package) -> list[str]:
    errors: list[str] = []
    bible = package.story_bible
    state = package.current_state

    if not bible.get("story_format_version"):
        errors.append("story_bible.json is missing story_format_version.")
    if not bible.get("title"):
        errors.append("Story title is empty.")

    cards = bible.get("character_cards")
    if not isinstance(cards, list):
        errors.append("character_cards must be a list.")
    else:
        for filename in cards:
            if filename not in package.characters:
                errors.append(f"Character card is listed but missing: {filename}")

    if not isinstance(state.get("chapter"), int) or state["chapter"] < 1:
        errors.append("Current State chapter must be an integer greater than 0.")
    if not isinstance(state.get("scene"), int) or state["scene"] < 1:
        errors.append("Current State scene must be an integer greater than 0.")
    if not isinstance(state.get("scene_cast", []), list):
        errors.append("scene_cast must be a list.")
    if not isinstance(state.get("events", []), list):
        errors.append("events must be a list.")
    return errors
