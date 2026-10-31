import json
import unittest
from types import SimpleNamespace

from builder.continuity_context import select_relevant_locations
from storybuilder import StoryBuilderApp


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
        self.assertEqual(
            selected["Chloe, Jessica, and Rick's House"],
            self.locations["Chloe, Jessica, and Rick's House"],
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
        self.assertEqual(select_relevant_locations(["not", "a", "mapping"], "House", "House"), {})

    def test_unsupported_entry_values_are_not_sent_to_writer(self):
        selected = select_relevant_locations(
            {"Known Place": ["unsupported"], "Another Place": {"description": "Known."}},
            "Known Place",
            "Another Place",
        )
        self.assertEqual(selected, {"Another Place": {"description": "Known."}})


class WriterLocationContextIntegrationTests(unittest.TestCase):
    def make_app(self, saved_location, scene_idea, locations):
        app = object.__new__(StoryBuilderApp)
        app.package = SimpleNamespace(
            current_state={
                "chapter": 1,
                "scene": 1,
                "location": {"primary": saved_location},
                "scene_cast": [],
                "current_situation": "",
                "physical_state": {},
                "character_knowledge": {},
                "active_objectives": {},
            },
            extra_json={"writing_guidance.json": {}},
            story_bible={
                "locations": locations,
                "relationships": {},
                "canon_rules": [],
                "optional_story_modules": [],
                "supporting_people": {},
            },
            writer_notes={},
            characters={},
        )
        guidance = {"scene_idea": scene_idea, "direction": "", "end_condition": ""}
        app._chapter_scene_guidance = lambda *_args: guidance
        app._author_writing_guidance = lambda: ""
        return app

    def test_explicit_scene_header_overrides_stale_saved_location(self):
        locations = {
            "Tony and Tiffany's House": {"description": "The current scene's house."},
            "Beth and Maya's House": {"description": "A different house."},
        }
        idea = (
            "Scene Header\n"
            "Location: Tony and Tiffany's House\n\n"
            "Tony and Tiffany's House is quiet as the scene begins."
        )
        app = self.make_app("Beth and Maya's House", idea, locations)
        files = dict(StoryBuilderApp._writer_package_files(app))

        self.assertEqual(
            json.loads(files["scene_locations.json"]),
            {"Tony and Tiffany's House": locations["Tony and Tiffany's House"]},
        )
        self.assertEqual(
            json.loads(files["scene_state.json"])["location"],
            "Tony and Tiffany's House",
        )

    def test_scene_idea_can_supply_multiple_locations_without_loading_others(self):
        locations = {
            "Tony and Tiffany's House": {"description": "The starting house."},
            "Beth and Maya's House": {"description": "Not part of this scene."},
            "Chloe, Jessica, and Rick's House": {"description": "The destination house."},
        }
        idea = (
            "Scene Header\n"
            "Location: Tony and Tiffany's House\n\n"
            "The scene starts at Tony and Tiffany's House. Later, they travel "
            "to Chloe, Jessica, and Rick's House."
        )
        app = self.make_app("Beth and Maya's House", idea, locations)
        files = dict(StoryBuilderApp._writer_package_files(app))

        self.assertEqual(
            list(json.loads(files["scene_locations.json"])),
            ["Tony and Tiffany's House", "Chloe, Jessica, and Rick's House"],
        )
        self.assertNotIn("Beth and Maya's House", files["scene_locations.json"])


if __name__ == "__main__":
    unittest.main()
