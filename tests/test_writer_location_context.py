import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from builder.continuity_context import select_relevant_locations
from minimal_writer import MinimalWriterApp, build_location_context_prompt


class RelevantLocationSelectionTests(unittest.TestCase):
    def setUp(self):
        self.locations = {
            "Tony and Tiffany's House": {
                "type": "Family Home",
                "description": "A two-story house with a large kitchen.",
            },
            "Beth and Maya's House": "A smaller house near the park.",
            "Chloe, Jessica, and Rick's House": {
                "description": "A renovated farmhouse with a wide porch.",
            },
            "Homecoming House": {"description": "An unrelated location."},
        }

    def test_selects_primary_and_other_complete_names_mentioned_in_scene(self):
        selected = select_relevant_locations(
            self.locations,
            " tony and Tiffany's House ",
            "They later travel to Chloe, Jessica, and Rick's House.",
        )
        self.assertEqual(
            list(selected),
            ["Tony and Tiffany's House", "Chloe, Jessica, and Rick's House"],
        )
        self.assertEqual(
            selected["Tony and Tiffany's House"],
            self.locations["Tony and Tiffany's House"],
        )

    def test_does_not_use_partial_or_unrelated_name_matches(self):
        selected = select_relevant_locations(
            self.locations,
            "",
            "Tiffany mentions the homecoming plans and a house nearby.",
        )
        self.assertEqual(selected, {})

    def test_supports_legacy_string_and_structured_location_entries(self):
        selected = select_relevant_locations(
            self.locations,
            "Beth and Maya's House",
            "",
        )
        self.assertEqual(
            selected,
            {"Beth and Maya's House": "A smaller house near the park."},
        )

    def test_invalid_container_returns_no_locations(self):
        self.assertEqual(
            select_relevant_locations(["not", "a", "mapping"], "House", "House"),
            {},
        )

    def test_unsupported_entry_values_are_not_sent_to_writer(self):
        selected = select_relevant_locations(
            {"Known Place": ["unsupported"], "Another Place": {"description": "Known."}},
            "Known Place",
            "Another Place",
        )
        self.assertEqual(selected, {"Another Place": {"description": "Known."}})


class BuildLocationPromptTests(unittest.TestCase):
    def test_prompt_contains_only_relevant_named_locations(self):
        locations = {
            "Tony and Tiffany's House": {
                "type": "Family Home",
                "description": "The kitchen opens into the dining room.",
            },
            "Chloe, Jessica, and Rick's House": "A renovated farmhouse.",
            "Beth and Maya's House": {"description": "Not part of this scene."},
        }
        prompt, names = build_location_context_prompt(
            "Scene Header\nLocation: Tony and Tiffany's House\n\n"
            "Later, they visit Chloe, Jessica, and Rick's House.",
            locations,
        )
        self.assertEqual(
            names,
            ["Tony and Tiffany's House", "Chloe, Jessica, and Rick's House"],
        )
        self.assertIn("The kitchen opens into the dining room.", prompt)
        self.assertIn("A renovated farmhouse.", prompt)
        self.assertNotIn("Not part of this scene.", prompt)

    def test_prompt_is_unchanged_when_no_location_name_matches(self):
        original = "Write a quiet conversation at home."
        prompt, names = build_location_context_prompt(
            original,
            {"Tony and Tiffany's House": {"description": "Saved details."}},
        )
        self.assertEqual(prompt, original)
        self.assertEqual(names, [])

    def test_supporting_passage_can_identify_location_for_continue(self):
        prompt, names = build_location_context_prompt(
            "Continue the current passage.",
            {"Tony and Tiffany's House": {"description": "The familiar kitchen."}},
            supporting_text="Tony and Tiffany's House was quiet after midnight.",
        )
        self.assertEqual(names, ["Tony and Tiffany's House"])
        self.assertIn("The familiar kitchen.", prompt)


class MinimalWriterLocationIntegrationTests(unittest.TestCase):
    def make_app(self, novel_path):
        app = object.__new__(MinimalWriterApp)
        app.novel_var = SimpleNamespace(get=lambda: "Demo Novel")
        app.novel_packages = {"Demo Novel": Path(novel_path)}
        app.last_location_context_names = []
        return app

    def make_package(self):
        temporary = tempfile.TemporaryDirectory()
        path = Path(temporary.name)
        story_bible = {
            "title": "Demo Novel",
            "locations": {
                "Tony and Tiffany's House": {
                    "description": "The kitchen has a broad island.",
                },
                "Beth and Maya's House": {
                    "description": "A small blue house near the park.",
                },
            },
        }
        (path / "story_bible.json").write_text(
            json.dumps(story_bible, indent=2),
            encoding="utf-8",
        )
        return temporary, path

    def test_writer_reads_locations_from_selected_novel_without_modifying_story_bible(self):
        temporary, novel_path = self.make_package()
        try:
            story_bible_path = novel_path / "story_bible.json"
            original = story_bible_path.read_bytes()
            app = self.make_app(novel_path)
            prompt = MinimalWriterApp._prepare_location_context(
                app,
                "Scene Header\nLocation: Tony and Tiffany's House",
            )
            self.assertIn("The kitchen has a broad island.", prompt)
            self.assertEqual(
                app.last_location_context_names,
                ["Tony and Tiffany's House"],
            )
            self.assertEqual(story_bible_path.read_bytes(), original)
        finally:
            temporary.cleanup()

    def test_write_adds_only_locations_named_in_new_prompt(self):
        temporary, novel_path = self.make_package()
        try:
            app = self.make_app(novel_path)
            app.busy = False
            app.loaded_model = Path("/models/test.gguf")
            app.prompt_box = SimpleNamespace(
                get=lambda *_args: (
                    "Scene Header\nLocation: Tony and Tiffany's House\n\n"
                    "They talk in the kitchen."
                )
            )
            app._begin_generation = Mock()
            app._showinfo = Mock()

            MinimalWriterApp.write(app)

            generated_prompt, mode = app._begin_generation.call_args.args
            self.assertIn("The kitchen has a broad island.", generated_prompt)
            self.assertNotIn("A small blue house near the park.", generated_prompt)
            self.assertEqual(mode, "write")
        finally:
            temporary.cleanup()

    def test_continue_uses_scene_idea_and_existing_passage_to_select_locations(self):
        temporary, novel_path = self.make_package()
        try:
            app = self.make_app(novel_path)
            app.busy = False
            app.loaded_model = Path("/models/test.gguf")
            app.prompt_box = SimpleNamespace(
                get=lambda *_args: (
                    "Scene Header\nLocation: Tony and Tiffany's House"
                )
            )
            app._output_text = lambda: (
                "Tony and Tiffany's House was quiet. Later, they drive to Beth and Maya's House."
            )
            app._begin_generation = Mock()
            app._showinfo = Mock()

            MinimalWriterApp.continue_writing(app)

            generated_prompt, mode = app._begin_generation.call_args.args
            self.assertIn("The kitchen has a broad island.", generated_prompt)
            self.assertIn("A small blue house near the park.", generated_prompt)
            self.assertEqual(
                app.last_location_context_names,
                ["Tony and Tiffany's House", "Beth and Maya's House"],
            )
            self.assertEqual(mode, "continue")
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
