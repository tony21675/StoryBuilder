from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any


_TEXT_FIELDS = {"premise", "setting"}


def _parse_story_bible(content: bytes, bible_path: Path) -> dict[str, Any]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Story Bible is not valid UTF-8 text.") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Story Bible is not valid JSON (line {exc.lineno}, column {exc.colno})."
        ) from exc

    if not isinstance(data, dict):
        raise ValueError("Story Bible must contain a JSON object at its top level.")

    return data


def load_story_bible(novel_path: str | Path) -> dict[str, Any]:
    """Read and validate one package's story_bible.json without modifying it."""
    bible_path = Path(novel_path).expanduser() / "story_bible.json"
    if not bible_path.is_file():
        raise FileNotFoundError(f"No story_bible.json was found at:\n{bible_path}")

    return _parse_story_bible(bible_path.read_bytes(), bible_path)


def _save_story_bible_field(novel_path: str | Path, field_name: str, value: Any) -> Path:
    """Update one approved field, preserving all other data atomically."""
    bible_path = Path(novel_path).expanduser() / "story_bible.json"
    if not bible_path.is_file():
        raise FileNotFoundError(f"No story_bible.json was found at:\n{bible_path}")

    original_bytes = bible_path.read_bytes()
    data = _parse_story_bible(original_bytes, bible_path)
    data[field_name] = value
    output = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    original_mode = stat.S_IMODE(bible_path.stat().st_mode)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", prefix=f".{bible_path.name}.",
                                         suffix=".tmp", dir=bible_path.parent, delete=False) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(output)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.chmod(temporary_path, original_mode)
        if not bible_path.is_file() or bible_path.read_bytes() != original_bytes:
            raise RuntimeError(
                "The Story Bible changed on disk while this edit was being saved. "
                "Cancel this edit, reload the Story Bible, and try again."
            )
        os.replace(temporary_path, bible_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
    return bible_path


def save_story_bible_text_field(novel_path: str | Path, field_name: str, value: str) -> Path:
    """Update one approved text field, preserving all other data atomically."""
    if field_name not in _TEXT_FIELDS:
        allowed = ", ".join(sorted(_TEXT_FIELDS))
        raise ValueError(f"Only these Story Bible text fields can be edited: {allowed}.")
    if not isinstance(value, str):
        raise ValueError(f"{field_name.title()} must be text.")
    return _save_story_bible_field(novel_path, field_name, value)


def save_story_bible_canon_rules(novel_path: str | Path, rules: list[str]) -> Path:
    """Replace only the canon_rules array with single-line text entries."""
    if not isinstance(rules, list) or any(not isinstance(rule, str) for rule in rules):
        raise ValueError("Canon Rules must be a list of text entries.")
    if any("\n" in rule or "\r" in rule for rule in rules):
        raise ValueError("Each Canon Rule must be a single line.")
    return _save_story_bible_field(novel_path, "canon_rules", rules)

def _write_json_file_atomically(
    file_path: Path, original_bytes: bytes, data: dict[str, Any]
) -> Path:
    """Atomically replace a JSON object only if its original bytes are unchanged."""
    output = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    original_mode = stat.S_IMODE(file_path.stat().st_mode)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{file_path.name}.", suffix=".tmp",
            dir=file_path.parent, delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(output)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.chmod(temporary_path, original_mode)
        if not file_path.is_file() or file_path.read_bytes() != original_bytes:
            raise RuntimeError(
                f"{file_path.name} changed on disk while this edit was being saved. "
                "Reload the Story Bible and try again."
            )
        os.replace(temporary_path, file_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
    return file_path


def _resolve_character_card_path(novel_path: str | Path, filename: str) -> Path:
    """Resolve one root-level JSON card filename without allowing path traversal."""
    if not isinstance(filename, str) or not filename:
        raise ValueError("Character card filename must be non-empty text.")
    candidate = Path(filename)
    if candidate.is_absolute() or candidate.name != filename or candidate.suffix.lower() != ".json":
        raise ValueError("Character cards must reference a JSON filename in the novel folder.")
    root = Path(novel_path).expanduser().resolve()
    card_path = (root / candidate).resolve()
    if card_path.parent != root:
        raise ValueError("Character card path must remain inside the novel folder.")
    return card_path


def _validate_character_card_updates(card: dict[str, Any]) -> None:
    name = card.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Character card needs a non-empty name.")
    for field_name in ("role", "description"):
        if field_name in card and not isinstance(card[field_name], str):
            raise ValueError(f"Character card {field_name.title()} must be text.")


def load_story_bible_character_card(
    novel_path: str | Path, filename: str
) -> dict[str, Any]:
    """Load one referenced character JSON file without changing it."""
    card_path = _resolve_character_card_path(novel_path, filename)
    if not card_path.is_file():
        raise FileNotFoundError(f"Character card file was not found: {card_path.name}")
    try:
        content = card_path.read_bytes()
        data = json.loads(content.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError(f"Character card {filename} is not valid UTF-8 text.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Character card {filename} is not valid JSON (line {exc.lineno}, column {exc.colno})."
        ) from exc
    if not isinstance(data, dict):
        raise ValueError(f"Character card {filename} must contain a JSON object.")
    _validate_character_card_updates(data)
    return data


def save_story_bible_character_card_file(
    novel_path: str | Path, filename: str, updates: dict[str, str]
) -> Path:
    """Update Name, Role, and Description in a referenced card, preserving every other key."""
    if not isinstance(updates, dict) or set(updates) - {"name", "role", "description"}:
        raise ValueError("Only Name, Role, and Description can be edited here.")
    for key, value in updates.items():
        if not isinstance(value, str):
            raise ValueError(f"Character card {key.title()} must be text.")
    if "name" in updates and not updates["name"].strip():
        raise ValueError("Character card needs a non-empty name.")
    card_path = _resolve_character_card_path(novel_path, filename)
    if not card_path.is_file():
        raise FileNotFoundError(f"Character card file was not found: {card_path.name}")
    original_bytes = card_path.read_bytes()
    try:
        data = json.loads(original_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Character card {filename} is not valid JSON text.") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Character card {filename} must contain a JSON object.")
    data.update(updates)
    _validate_character_card_updates(data)
    return _write_json_file_atomically(card_path, original_bytes, data)


def create_story_bible_character_card(
    novel_path: str | Path, card: dict[str, str]
) -> str:
    """Create a root-level character JSON file and add its filename to Story Bible."""
    if not isinstance(card, dict) or set(card) - {"name", "role", "description"}:
        raise ValueError("A new Character Card may contain only Name, Role, and Description.")
    if any(not isinstance(value, str) for value in card.values()):
        raise ValueError("Character Card fields must be text.")
    normalized = {
        "name": card.get("name", "").strip(),
        "role": card.get("role", "").strip(),
        "description": card.get("description", ""),
    }
    _validate_character_card_updates(normalized)
    root = Path(novel_path).expanduser().resolve()
    bible_path = root / "story_bible.json"
    if not bible_path.is_file():
        raise FileNotFoundError(f"No story_bible.json was found at:\n{bible_path}")
    original_bible_bytes = bible_path.read_bytes()
    bible = _parse_story_bible(original_bible_bytes, bible_path)
    existing_cards = bible.get("character_cards", [])
    if not isinstance(existing_cards, list) or any(
        not isinstance(item, (str, dict)) for item in existing_cards
    ):
        raise ValueError("Story Bible character_cards must be a list before adding a card.")
    import re
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", normalized["name"]).strip("_-") or "Character"
    used_names = {item.casefold() for item in existing_cards if isinstance(item, str)}
    suffix = 1
    while True:
        filename = f"{stem}.json" if suffix == 1 else f"{stem}_{suffix}.json"
        card_path = _resolve_character_card_path(root, filename)
        if filename.casefold() not in used_names and not card_path.exists():
            break
        suffix += 1
    payload = (json.dumps(normalized, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    temporary_path: Path | None = None
    created_card = False
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{filename}.", suffix=".tmp",
            dir=root, delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(payload)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        try:
            os.link(temporary_path, card_path)
            created_card = True
        except FileExistsError:
            raise RuntimeError(f"Character card file already exists: {filename}")
        finally:
            temporary_path.unlink(missing_ok=True)
            temporary_path = None
        bible["character_cards"] = list(existing_cards) + [filename]
        _write_json_file_atomically(bible_path, original_bible_bytes, bible)
    except Exception:
        if created_card:
            try:
                card_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return filename


def remove_story_bible_character_card_reference(
    novel_path: str | Path, index: int, filename: str
) -> Path:
    """Remove a filename reference only; never delete the character JSON file itself."""
    _resolve_character_card_path(novel_path, filename)
    bible_path = Path(novel_path).expanduser() / "story_bible.json"
    if not bible_path.is_file():
        raise FileNotFoundError(f"No story_bible.json was found at:\n{bible_path}")
    original_bytes = bible_path.read_bytes()
    bible = _parse_story_bible(original_bytes, bible_path)
    cards = bible.get("character_cards", [])
    if not isinstance(cards, list) or not 0 <= index < len(cards) or cards[index] != filename:
        raise RuntimeError("The Character Cards list changed. Reload it before removing a card.")
    updated = list(cards)
    updated.pop(index)
    bible["character_cards"] = updated
    return _write_json_file_atomically(bible_path, original_bytes, bible)

def save_story_bible_character_cards(
    novel_path: str | Path, cards: list[dict[str, Any] | str]
) -> Path:
    """Replace character_cards while preserving legacy string entries and card metadata."""
    if not isinstance(cards, list):
        raise ValueError("Character Cards must be a list.")
    for index, card in enumerate(cards, start=1):
        if isinstance(card, str):
            continue
        if not isinstance(card, dict):
            raise ValueError(f"Character Card {index} must be a text entry or an object.")
        name = card.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Character Card {index} needs a non-empty name.")
        for field_name in ("role", "description"):
            if field_name in card and not isinstance(card[field_name], str):
                raise ValueError(
                    f"Character Card {index} {field_name.title()} must be text."
                )
    return _save_story_bible_field(novel_path, "character_cards", cards)

def save_story_bible_premise(novel_path: str | Path, premise: str) -> Path:
    """Compatibility wrapper for the premise-only editing workflow."""
    return save_story_bible_text_field(novel_path, "premise", premise)
