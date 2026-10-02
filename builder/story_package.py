from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from tempfile import NamedTemporaryFile

FORMAT_VERSION = "1.0"
CORE_FILES = {"story_bible.json", "current_state.json"}


class StoryPackage:
    """Load, edit, and save a LocalStoryChat-compatible novel package."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else None
        self.story_bible: dict = {}
        self.current_state: dict = {}
        self.characters: dict[str, dict] = {}
        self.extra_json: dict[str, dict] = {}

    @classmethod
    def new(cls, title: str = "Untitled") -> "StoryPackage":
        package = cls()
        package.story_bible = {
            "story_format_version": FORMAT_VERSION,
            "title": title,
            "version": "1.0",
            "status": "active",
            "premise": "",
            "character_cards": [],
            "relationships": {},
            "locations": {},
            "story_planning": {}
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

        self._write_json_atomic(target / "story_bible.json", self.story_bible)
        self._write_json_atomic(target / "current_state.json", self.current_state)

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
    def _write_json_atomic(path: Path, data: dict) -> None:
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False, prefix=f".{path.name}."
        ) as f:
            f.write(text)
            temp = Path(f.name)
        temp.replace(path)
