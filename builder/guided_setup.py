from __future__ import annotations

import re


class GuidedResult:
    def __init__(self, message: str, complete: bool = False, error: bool = False) -> None:
        self.message = message
        self.complete = complete
        self.error = error


class GuidedSetupSession:
    """Reusable question-driven novel setup.

    Answers are written into the StoryPackage. Most questions are optional:
    blank, "skip", "unknown", and "not decided" leave that item empty so the
    author can return to it later in StoryBuilder.
    """

    SKIP_WORDS = {"skip", "unknown", "not decided", "undecided", "later", "n/a", "na"}

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
        package.story_bible.setdefault("story_planning", {})
        return (
            "Let's build the novel a piece at a time. You can answer any question, "
            "or type skip when you don't know yet. First, what is the story title?"
        )

    def stop(self) -> str:
        self.active = False
        self.character_filename = None
        self.character_name = None
        return "Guided setup stopped. Anything already entered stays in the novel."

    def handle(self, package, answer: str) -> GuidedResult:
        if not self.active:
            return GuidedResult("Guided setup is not active.", error=True)

        text = answer.strip()
        planning = package.story_bible.setdefault("story_planning", {})

        if self.step == "title":
            if not text:
                return GuidedResult("The story title cannot be empty. Enter a title or type skip only if the novel already has one.", error=True)
            package.story_bible["title"] = text.strip('"')
            self.step = "premise"
            return GuidedResult("What is the basic premise or hook? A sentence or two is enough. You can skip it.")

        if self.step == "premise":
            if text and not self._skipped(text):
                package.story_bible["premise"] = text
            self.step = "genre"
            return GuidedResult("What genre or mix of genres is this? For example: thriller, romance, science fiction. You can skip it.")

        if self.step == "genre":
            self._store_optional(planning, "genre", text)
            self.step = "tone"
            return GuidedResult("What overall tone do you want? For example: dark, tense, funny, grounded, hopeful. You can skip it.")

        if self.step == "tone":
            self._store_optional(planning, "tone", text)
            self.step = "themes"
            return GuidedResult("Any themes or ideas you want the novel to explore? Separate several with commas. You can skip it.")

        if self.step == "themes":
            values = self._split_values(text)
            if values:
                planning["themes"] = values
            elif self._skipped(text):
                planning.pop("themes", None)
            self.step = "conflict"
            return GuidedResult("What is the central conflict or problem driving the story? It does not have to be fully figured out yet.")

        if self.step == "conflict":
            self._store_optional(planning, "core_conflict", text)
            self.step = "opposition"
            return GuidedResult("Who or what opposes the protagonist? This can be a person, group, force, or even 'not decided yet'.")

        if self.step == "opposition":
            self._store_optional(planning, "opposition", text)
            self.step = "setting"
            return GuidedResult("What is the story's setting or world? Give the general place, time period, and anything unusual. You can skip it.")

        if self.step == "setting":
            self._store_optional(planning, "setting", text)
            self.step = "important_objects"
            return GuidedResult("Are there important objects, technology, clues, organizations, or other story elements you already know about? You can skip this.")

        if self.step == "important_objects":
            self._store_optional(planning, "important_elements", text)
            self.step = "main_characters"
            return GuidedResult("Now let's build the characters. Add a character's name, or type done when you are finished.")

        if self.step == "main_characters":
            if not text:
                return GuidedResult("Enter a character name, or type done.", error=True)
            if text.casefold() == "done":
                self.step = "relationships"
                return GuidedResult(
                    "Characters are set. Enter established relationships one per line, like "
                    "Tony-Tiffany: father and daughter. You can skip this."
                )
            try:
                filename = package.add_character(text)
            except ValueError as exc:
                return GuidedResult(str(exc), error=True)
            self.character_filename = filename
            self.character_name = text
            self.step = "character_age"
            return GuidedResult(f"{text} added. How old are they? Type skip if you don't know.")

        if self.step == "character_age":
            character = self._current_character(package)
            if character is None:
                self.step = "main_characters"
                return GuidedResult("I lost the current character. Enter the next character's name or type done.", error=True)
            if not self._skipped(text) and text:
                try:
                    character["age"] = int(text)
                except ValueError:
                    return GuidedResult("Age needs to be a whole number, or type skip.", error=True)
            else:
                character["age"] = None
            self.step = "character_role"
            return GuidedResult("What is this character's role in the story? You can skip it.")

        if self.step == "character_role":
            character = self._current_character(package)
            if character is not None:
                character["role"] = "" if self._skipped(text) else text
            self.step = "character_description"
            return GuidedResult("Give me a brief description, including anything visually important. You can skip it.")

        if self.step == "character_description":
            character = self._current_character(package)
            if character is not None:
                character["description"] = "" if self._skipped(text) else text
            self.step = "character_personality"
            return GuidedResult("What are they like? A few personality traits is enough. You can skip it.")

        if self.step == "character_personality":
            character = self._current_character(package)
            if character is not None:
                character["personality"] = [] if self._skipped(text) else self._split_values(text)
            self.step = "character_occupation"
            return GuidedResult("What do they do for work or everyday life? You can skip it.")

        if self.step == "character_occupation":
            character = self._current_character(package)
            if character is not None:
                character["occupation"] = "" if self._skipped(text) else text
            name = self.character_name or "that character"
            self.step = "more_characters"
            return GuidedResult(f"{name} is recorded. Add another character? Answer yes or no.")

        if self.step == "more_characters":
            choice = self._yes_no(text)
            if choice is None:
                return GuidedResult("Please answer yes or no.", error=True)
            if choice:
                self.character_filename = None
                self.character_name = None
                self.step = "main_characters"
                return GuidedResult("Enter the next character's name, or type done.")
            self.step = "relationships"
            return GuidedResult(
                "Characters are set. Enter established relationships one per line, like "
                "Tony-Tiffany: father and daughter. You can skip this."
            )

        if self.step == "relationships":
            values = self._parse_pairs(text)
            if values:
                package.story_bible["relationships"] = values
            elif self._skipped(text):
                package.story_bible["relationships"] = {}
            self.step = "locations"
            return GuidedResult(
                "Now enter established locations one per line, like home: Tony's house near the edge of town. You can skip this."
            )

        if self.step == "locations":
            values = self._parse_pairs(text)
            if values:
                package.story_bible["locations"] = values
            elif self._skipped(text):
                package.story_bible["locations"] = {}
            self.step = "unresolved"
            return GuidedResult(
                "What important story details are still undecided? List questions or unknowns you want to figure out later, or skip."
            )

        if self.step == "unresolved":
            values = self._split_lines(text)
            if values:
                planning["open_questions"] = values
            elif self._skipped(text):
                planning["open_questions"] = []
            self.step = "chapter_scene"
            return GuidedResult("What chapter and scene should the story begin in? Use 1,1 for the normal starting point.")

        if self.step == "chapter_scene":
            if self._skipped(text):
                package.current_state["chapter"] = 1
                package.current_state["scene"] = 1
                self.step = "start_location"
                return GuidedResult("Where does the opening scene take place? You can skip it.")
            parts = [part.strip() for part in text.replace("/", ",").split(",") if part.strip()]
            if len(parts) != 2 or not all(part.isdigit() for part in parts):
                return GuidedResult("Use two whole numbers separated by a comma, for example 1,1, or type skip.", error=True)
            chapter, scene = map(int, parts)
            if chapter < 1 or scene < 1:
                return GuidedResult("Chapter and scene must both be at least 1.", error=True)
            package.current_state["chapter"] = chapter
            package.current_state["scene"] = scene
            self.step = "start_location"
            return GuidedResult("Where does the opening scene take place? You can skip it.")

        if self.step == "start_location":
            if text and not self._skipped(text):
                package.current_state["location"] = text
            self.step = "time"
            return GuidedResult("What is the time of day when the story opens? You can skip it.")

        if self.step == "time":
            if text and not self._skipped(text):
                package.current_state["time_of_day"] = text
            self.step = "cast"
            return GuidedResult("Who is present in the opening scene? Enter names separated by commas, or skip.")

        if self.step == "cast":
            if text and not self._skipped(text):
                package.current_state["scene_cast"] = self._split_people(text)
            self.step = "situation"
            return GuidedResult("Describe the situation at the exact moment the story opens. You can skip it.")

        if self.step == "situation":
            if text and not self._skipped(text):
                package.current_state["current_situation"] = text
            package.current_state.setdefault("status", "story_start")
            package.current_state.setdefault("events", [])
            package.current_state.setdefault("continuity_notes", [])
            self.active = False
            self.character_filename = None
            self.character_name = None
            return GuidedResult(
                "Guided setup is complete. Review the tabs and save the novel. "
                "Anything you skipped can be filled in later."
                , complete=True
            )

        self.active = False
        return GuidedResult("Guided setup reached an unknown step and was stopped.", complete=True, error=True)

    def _current_character(self, package):
        if self.character_filename is None:
            return None
        return package.characters.get(self.character_filename)

    @classmethod
    def _skipped(cls, text: str) -> bool:
        return not text or text.casefold() in cls.SKIP_WORDS

    @classmethod
    def _store_optional(cls, mapping: dict, key: str, text: str) -> None:
        if cls._skipped(text):
            mapping.pop(key, None)
        else:
            mapping[key] = text

    @staticmethod
    def _split_values(text: str) -> list[str]:
        if not text or text.casefold() in GuidedSetupSession.SKIP_WORDS:
            return []
        parts = re.split(r"[,;]", text)
        return [part.strip() for part in parts if part.strip()]

    @staticmethod
    def _split_lines(text: str) -> list[str]:
        if not text or text.casefold() in GuidedSetupSession.SKIP_WORDS:
            return []
        return [line.strip() for line in text.splitlines() if line.strip()]

    @staticmethod
    def _split_people(text: str) -> list[str]:
        if not text or text.casefold() in GuidedSetupSession.SKIP_WORDS:
            return []
        parts = re.split(r"[,\n]", text)
        return [part.strip() for part in parts if part.strip()]

    @staticmethod
    def _parse_pairs(text: str) -> dict[str, str]:
        result: dict[str, str] = {}
        if not text or text.casefold() in GuidedSetupSession.SKIP_WORDS:
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
