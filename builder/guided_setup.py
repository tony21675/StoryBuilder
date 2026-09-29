from __future__ import annotations

import re


class GuidedResult:
    def __init__(self, message: str, complete: bool = False, error: bool = False) -> None:
        self.message = message
        self.complete = complete
        self.error = error


class GuidedSetupSession:
    """Small deterministic interview for building a new novel package.

    The session changes only the StoryPackage. It does not use an LLM, so the
    collected answers remain predictable and editable in the normal tabs.
    """

    def __init__(self) -> None:
        self.active = False
        self.step = "title"
        self.character_filename: str | None = None
        self.character_name: str | None = None

    def start(self, package) -> str:
        self.active = True
        self.step = "title"
        self.character_filename = None
        self.character_name = None
        return "Let's build the novel. First, what is the story title?"

    def stop(self) -> str:
        self.active = False
        self.character_filename = None
        self.character_name = None
        return "Guided setup stopped. Your current changes are still in the novel."

    def handle(self, package, answer: str) -> GuidedResult:
        if not self.active:
            return GuidedResult("Guided setup is not active.", error=True)

        text = answer.strip()

        if self.step == "title":
            if not text:
                return GuidedResult("The story title cannot be empty. What should the novel be called?", error=True)
            package.story_bible["title"] = text.strip('"')
            self.step = "premise"
            return GuidedResult("Got it. Give me the premise in a sentence or two.")

        if self.step == "premise":
            if not text:
                return GuidedResult(
                    "A blank premise is okay, but give me at least a sentence so the package has a starting idea.",
                    error=True,
                )
            package.story_bible["premise"] = text
            self.step = "character_name"
            return GuidedResult(
                "Now let's add the main characters. Enter a character's name, or type done when you're finished."
            )

        if self.step == "character_name":
            if not text:
                return GuidedResult("Enter a character name, or type done.", error=True)
            if text.casefold() == "done":
                self.step = "relationships"
                return GuidedResult(
                    "Characters are set. Now enter established relationships, one per line, like "
                    "Tony-Tiffany: father and daughter. Leave it blank to skip."
                )

            try:
                filename = package.add_character(text)
            except ValueError as exc:
                return GuidedResult(str(exc), error=True)

            self.character_filename = filename
            self.character_name = text
            self.step = "character_age"
            return GuidedResult(f"Character added: {text}. How old are they? Leave it blank if the age is unknown.")

        if self.step == "character_age":
            character = self._current_character(package)
            if character is None:
                self.step = "character_name"
                return GuidedResult("I lost the current character. Enter the next character's name or type done.", error=True)

            if not text:
                character["age"] = None
            else:
                try:
                    character["age"] = int(text)
                except ValueError:
                    return GuidedResult("Age needs to be a whole number, or leave it blank.", error=True)

            self.step = "character_role"
            return GuidedResult("What is this character's role in the story?")

        if self.step == "character_role":
            character = self._current_character(package)
            if character is not None:
                character["role"] = text
            self.step = "character_description"
            return GuidedResult("Give me a brief description of the character, including anything visually important.")

        if self.step == "character_description":
            character = self._current_character(package)
            if character is not None:
                character["description"] = text
            self.step = "character_personality"
            return GuidedResult("What are they like? A few personality traits or a short description is enough.")

        if self.step == "character_personality":
            character = self._current_character(package)
            if character is not None:
                character["personality"] = self._split_values(text)
            self.step = "character_occupation"
            return GuidedResult("What do they do for work or in everyday life? Leave it blank if it is not important.")

        if self.step == "character_occupation":
            character = self._current_character(package)
            if character is not None:
                character["occupation"] = text
            name = self.character_name or "that character"
            self.step = "more_characters"
            return GuidedResult(
                f"{name} is recorded. Add another character? Answer yes or no."
            )

        if self.step == "more_characters":
            choice = self._yes_no(text)
            if choice is None:
                return GuidedResult("Please answer yes or no.", error=True)
            if choice:
                self.character_filename = None
                self.character_name = None
                self.step = "character_name"
                return GuidedResult("Enter the next character's name, or type done.")
            self.step = "relationships"
            return GuidedResult(
                "Characters are set. Now enter established relationships, one per line, like "
                "Tony-Tiffany: father and daughter. Leave it blank to skip."
            )

        if self.step == "relationships":
            package.story_bible["relationships"] = self._parse_pairs(text)
            self.step = "locations"
            return GuidedResult(
                "Now enter established locations, one per line, like home: Tony's house near the edge of town. "
                "Leave it blank to skip."
            )

        if self.step == "locations":
            package.story_bible["locations"] = self._parse_pairs(text)
            self.step = "chapter_scene"
            return GuidedResult(
                "What chapter and scene should the story begin in? Use '1,1' for the normal starting point."
            )

        if self.step == "chapter_scene":
            parts = [part.strip() for part in text.replace("/", ",").split(",") if part.strip()]
            if len(parts) != 2 or not all(part.isdigit() for part in parts):
                return GuidedResult("Use two whole numbers separated by a comma, for example 1,1.", error=True)
            chapter, scene = map(int, parts)
            if chapter < 1 or scene < 1:
                return GuidedResult("Chapter and scene must both be at least 1.", error=True)
            package.current_state["chapter"] = chapter
            package.current_state["scene"] = scene
            self.step = "start_location"
            return GuidedResult("Where does the opening scene take place?")

        if self.step == "start_location":
            package.current_state["location"] = text
            self.step = "time"
            return GuidedResult("What is the time of day? For example: late afternoon.")

        if self.step == "time":
            package.current_state["time_of_day"] = text
            self.step = "cast"
            return GuidedResult(
                "Who is present in the opening scene? Enter names separated by commas."
            )

        if self.step == "cast":
            package.current_state["scene_cast"] = self._split_people(text)
            self.step = "situation"
            return GuidedResult(
                "Finally, describe the current situation at the exact moment the story opens."
            )

        if self.step == "situation":
            package.current_state["current_situation"] = text
            package.current_state.setdefault("status", "story_start")
            package.current_state.setdefault("events", [])
            package.current_state.setdefault("continuity_notes", [])
            self.active = False
            self.character_filename = None
            self.character_name = None
            return GuidedResult(
                "Guided setup is complete. Review the Story, Characters, Relationships, Locations, and Current State tabs, then save the novel.",
                complete=True,
            )

        self.active = False
        return GuidedResult("Guided setup reached an unknown step and was stopped.", complete=True, error=True)

    def _current_character(self, package):
        if self.character_filename is None:
            return None
        return package.characters.get(self.character_filename)

    @staticmethod
    def _split_values(text: str) -> list[str]:
        if not text:
            return []
        parts = re.split(r"[,;]", text)
        return [part.strip() for part in parts if part.strip()]

    @staticmethod
    def _split_people(text: str) -> list[str]:
        if not text:
            return []
        parts = re.split(r"[,\n]", text)
        return [part.strip() for part in parts if part.strip()]

    @staticmethod
    def _parse_pairs(text: str) -> dict[str, str]:
        result: dict[str, str] = {}
        if not text:
            return result
        for line in text.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key and value:
                result[key] = value
        return result

    @staticmethod
    def _yes_no(text: str) -> bool | None:
        if text.casefold() in {"yes", "y", "yeah", "yep", "sure"}:
            return True
        if text.casefold() in {"no", "n", "nope"}:
            return False
        return None
