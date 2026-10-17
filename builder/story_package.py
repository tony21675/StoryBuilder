from __future__ import annotations

import json
import re
import shutil
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from builder.writer_notes import (
    WRITER_NOTES_FILENAME,
    default_writer_notes,
    load_writer_notes,
    normalize_writer_notes,
)

FORMAT_VERSION = "1.0"
CORE_FILES = {"story_bible.json", "current_state.json", WRITER_NOTES_FILENAME}


class StoryPackage:
    """Load, edit, and save a LocalStoryChat-compatible novel package."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else None
        self.story_bible: dict = {}
        self.current_state: dict = {}
        self.characters: dict[str, dict] = {}
        self.extra_json: dict[str, dict] = {}
        self.writer_notes: dict = default_writer_notes()
        self.last_backup_path: Path | None = None

    @classmethod
    def new(cls, title: str = "Untitled") -> "StoryPackage":
        package = cls()
        package.story_bible = {
            "story_format_version": FORMAT_VERSION,
            "title": title,
            "version": "1.0",
            "status": "active",
            "premise": "",
            "canon_rules": [],
            "character_cards": [],
            "relationships": {},
            "locations": {},
            "story_planning": {}
        }
        package.extra_json["writing_guidance.json"] = {
            "purpose": "Author-defined scene direction and reusable scene contracts.",
            "scene_plan": {},
        }
        package.current_state = {
            "story_format_version": FORMAT_VERSION,
            "chapter": 1,
            "scene": 1,
            "scene_completed": False,
            "chapter_completed": False,
            "status": "story_start",
            "time_of_day": "",
            "location": "",
            "scene_cast": [],
            "events": [],
            "continuity_notes": [],
            "physical_state": {}
        }
        return package

    @classmethod
    def load(cls, folder: Path) -> "StoryPackage":
        folder = Path(folder)
        package = cls(folder)

        with (folder / "story_bible.json").open("r", encoding="utf-8") as f:
            package.story_bible = json.load(f)

        state_path = folder / "current_state.json"
        if state_path.exists():
            with state_path.open("r", encoding="utf-8") as f:
                package.current_state = json.load(f)
        else:
            package.current_state = cls.new().current_state

        package.writer_notes = load_writer_notes(folder)

        if not isinstance(package.current_state.get("physical_state"), dict):
            package.current_state["physical_state"] = {}

        package.characters = {}
        listed_cards = package.story_bible.get("character_cards", [])

        # Only files explicitly named in character_cards are loaded as editable
        # character cards. Other root-level JSON files belong to the package's
        # optional modules and must survive a StoryBuilder save unchanged.
        for filename in listed_cards:
            path = folder / filename
            if not path.exists():
                continue
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    package.characters[filename] = data
            except (OSError, json.JSONDecodeError):
                continue

        package.extra_json = {}
        for path in folder.glob("*.json"):
            if path.name in CORE_FILES or path.name in package.characters:
                continue
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    package.extra_json[path.name] = data
            except (OSError, json.JSONDecodeError):
                continue

        return package

    @staticmethod
    def safe_filename(name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9 _-]+", "", name).strip()
        cleaned = re.sub(r"\s+", "_", cleaned)
        return f"{cleaned or 'Character'}.json"

    def promote_supporting_person(self, name: str) -> str:
        """Move a supporting person and any existing JSON data into core character cards."""
        name = str(name or "").strip()
        if not name:
            raise ValueError("Choose a supporting person to promote.")

        supporting = self.story_bible.get("supporting_people", {})
        if not isinstance(supporting, dict):
            raise ValueError("The supporting-people list is not a valid object.")

        supporting_key = next(
            (
                str(key) for key in supporting
                if str(key).strip().casefold() == name.casefold()
            ),
            None,
        )
        if supporting_key is None:
            raise ValueError(f"{name} is not currently listed as a supporting person.")

        if self.character_by_name(name) is not None:
            raise ValueError(f"{name} already has a core character card.")

        filename = self.safe_filename(name)
        matching_character_file = next(
            (key for key in self.characters if key.casefold() == filename.casefold()),
            None,
        )
        if matching_character_file is not None:
            raise ValueError(
                f"A core character file for {name} already exists: {matching_character_file}."
            )

        extra_key = next(
            (key for key in self.extra_json if key.casefold() == filename.casefold()),
            None,
        )
        source_path = None
        if extra_key is not None:
            filename = extra_key
            source = self.extra_json[extra_key]
            if not isinstance(source, dict):
                raise ValueError(f"The existing {filename} file does not contain a JSON object.")
            card = deepcopy(source)
        else:
            if self.path is not None:
                source_path = next(
                    (
                        path for path in self.path.glob("*.json")
                        if path.name.casefold() == filename.casefold()
                    ),
                    None,
                )
            if source_path is not None:
                try:
                    with source_path.open("r", encoding="utf-8") as handle:
                        source = json.load(handle)
                except (OSError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"Could not safely read the existing character file {source_path.name}."
                    ) from exc
                if not isinstance(source, dict):
                    raise ValueError(
                        f"The existing {source_path.name} file does not contain a JSON object."
                    )
                filename = source_path.name
                card = deepcopy(source)
            else:
                details = supporting[supporting_key]
                card = {
                    "name": name,
                    "status": "established",
                    "role": "core character",
                    "age": None,
                    "description": details.strip() if isinstance(details, str) else "",
                    "personality": [],
                    "background": "",
                    "occupation": "",
                }
                if isinstance(details, dict):
                    card.update(deepcopy(details))

        stored_name = str(card.get("name", "") or "").strip()
        if stored_name and stored_name.casefold() != name.casefold():
            raise ValueError(
                f"The existing {filename} file is for {stored_name}, not {name}. "
                "No character data was changed."
            )
        card["name"] = stored_name or name
        if str(card.get("status", "") or "").strip().casefold() in {"", "supporting"}:
            card["status"] = "established"

        # Move the data between the two package collections only after validating
        # the source, so existing character details are not silently overwritten.
        self.characters[filename] = card
        if extra_key is not None:
            self.extra_json.pop(extra_key, None)
        supporting.pop(supporting_key, None)

        cards = self.story_bible.setdefault("character_cards", [])
        if not isinstance(cards, list):
            cards = []
            self.story_bible["character_cards"] = cards
        if filename not in cards:
            cards.append(filename)
        return filename

    def add_character(self, name: str) -> str:
        name = name.strip()
        if not name:
            raise ValueError("Character name cannot be empty.")

        filename = self.safe_filename(name)
        if filename in self.characters or filename in self.extra_json:
            raise ValueError(f"{filename} already exists.")

        self.characters[filename] = {
            "name": name,
            "age": None,
            "description": "",
            "personality": "",
            "background": "",
            "occupation": "",
            "hair": "",
            "eyes": ""
        }
        cards = self.story_bible.setdefault("character_cards", [])
        if filename not in cards:
            cards.append(filename)
        return filename

    def remove_character(self, filename: str) -> None:
        self.characters.pop(filename, None)
        cards = self.story_bible.setdefault("character_cards", [])
        if filename in cards:
            cards.remove(filename)

    def character_by_name(self, name: str):
        wanted = name.strip().casefold()
        for filename, data in self.characters.items():
            if str(data.get("name", "")).casefold() == wanted:
                return filename, data
        return None

    def save(self, folder: Path | None = None) -> Path:
        target = Path(folder) if folder else self.path
        if target is None:
            raise ValueError("Choose a folder before saving.")

        target.mkdir(parents=True, exist_ok=True)
        self.path = target
        self.story_bible["story_format_version"] = FORMAT_VERSION
        self.current_state["story_format_version"] = FORMAT_VERSION
        self.story_bible["character_cards"] = sorted(self.characters)
        self.writer_notes = normalize_writer_notes(self.writer_notes)
        desired_data = {
            "story_bible.json": self.story_bible,
            "current_state.json": self.current_state,
            WRITER_NOTES_FILENAME: self.writer_notes,
            **self.characters,
            **self.extra_json,
        }
        self.last_backup_path = self._backup_changed_json_files(target, desired_data)

        self._write_json_atomic(target / "story_bible.json", self.story_bible)
        self._write_json_atomic(target / "current_state.json", self.current_state)
        self._write_json_atomic(target / WRITER_NOTES_FILENAME, self.writer_notes)

        active = set(self.characters)
        for filename, data in self.characters.items():
            self._write_json_atomic(target / filename, data)

        for filename, data in self.extra_json.items():
            self._write_json_atomic(target / filename, data)

        for path in target.glob("*.json"):
            if path.name in CORE_FILES or path.name in active or path.name in self.extra_json:
                continue
            try:
                path.unlink()
            except OSError:
                pass

        return target

    @staticmethod
    def _json_text(data: dict) -> str:
        return json.dumps(data, indent=2, ensure_ascii=False) + "\n"

    @classmethod
    def _backup_changed_json_files(cls, target: Path, desired_data: dict[str, dict]) -> Path | None:
        """Back up root JSON files this save will change or remove."""
        existing = {path.name: path for path in target.glob("*.json") if path.is_file()}
        desired_names = set(desired_data)
        changed = []
        for filename, path in existing.items():
            if filename not in desired_names:
                changed.append(path)
                continue
            try:
                old_text = path.read_text(encoding="utf-8")
            except OSError as exc:
                raise OSError(f"Cannot read {path} before saving; no files were changed.") from exc
            if old_text != cls._json_text(desired_data[filename]):
                changed.append(path)

        if not changed:
            return None
        backup_root = target / ".storybuilder_backups"
        backup_folder = backup_root / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_folder.mkdir(parents=True, exist_ok=False)
        try:
            for path in changed:
                shutil.copy2(path, backup_folder / path.name)
        except OSError:
            shutil.rmtree(backup_folder, ignore_errors=True)
            raise
        try:
            snapshots = sorted(
                (entry for entry in backup_root.iterdir() if entry.is_dir()),
                key=lambda entry: entry.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            snapshots = []
        for old_snapshot in snapshots[20:]:
            shutil.rmtree(old_snapshot, ignore_errors=True)
        return backup_folder

    @staticmethod
    def _write_json_atomic(path: Path, data: dict) -> None:
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False, prefix=f".{path.name}."
        ) as f:
            f.write(text)
            temp = Path(f.name)
        temp.replace(path)
