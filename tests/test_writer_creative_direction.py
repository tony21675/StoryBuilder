import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from minimal_writer import MinimalWriterApp


class WriterCreativeDirectionTests(unittest.TestCase):
    def make_app(self, selected_name, packages):
        app = object.__new__(MinimalWriterApp)
        app.novel_var = SimpleNamespace(get=lambda: selected_name)
        app.novel_packages = packages
        return app

    def make_novel(self, root, creative_direction):
        root.mkdir(parents=True, exist_ok=True)
        path = root / "story_bible.json"
        path.write_text(
            json.dumps({
                "title": root.name,
                "creative_direction": creative_direction,
            }, indent=2),
            encoding="utf-8",
        )
        return path

    def test_writer_uses_only_the_selected_novels_profiles(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project_one = root / "Project One"
            project_two = root / "Project Two"
            bible_one = self.make_novel(project_one, {
                "genres": ["Mystery"],
                "moods": ["Tense"],
                "audience": "Adult",
                "explicit_adult_content": False,
            })
            bible_two = self.make_novel(project_two, {
                "genres": ["Fantasy"],
                "moods": ["Hopeful"],
                "audience": "Children's",
                "explicit_adult_content": False,
            })
            original_one = bible_one.read_bytes()
            original_two = bible_two.read_bytes()
            app = self.make_app(
                "Project One",
                {"Project One": project_one, "Project Two": project_two},
            )

            first_prompt = app._prepare_creative_direction_context("Write the next scene.")
            self.assertIn("Mystery guidance:", first_prompt)
            self.assertIn("Intended audience: Adult", first_prompt)
            self.assertIn("Explicit adult content is not enabled", first_prompt)
            self.assertNotIn("Fantasy guidance:", first_prompt)
            self.assertNotIn("do not use profanity", first_prompt.lower())

            app.novel_var = SimpleNamespace(get=lambda: "Project Two")
            second_prompt = app._prepare_creative_direction_context("Write the next scene.")
            self.assertIn("Fantasy guidance:", second_prompt)
            self.assertIn("Intended audience: Children's", second_prompt)
            self.assertIn("do not use profanity", second_prompt.lower())
            self.assertNotIn("Mystery guidance:", second_prompt)
            self.assertNotIn("Adult audience guidance:", second_prompt)

            self.assertEqual(bible_one.read_bytes(), original_one)
            self.assertEqual(bible_two.read_bytes(), original_two)

    def test_writer_uses_only_the_selected_novels_writing_preferences(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project_one = root / "Project One"
            project_two = root / "Project Two"
            project_one.mkdir()
            project_two.mkdir()
            preferences_one = (
                "Use natural, conversational prose. Trust the reader to remember "
                "what has already been established."
            )
            preferences_two = (
                "Use restrained, unsettling descriptions and build suspense gradually."
            )
            for project, preferences in (
                (project_one, preferences_one),
                (project_two, preferences_two),
            ):
                (project / "story_bible.json").write_text(
                    json.dumps({
                        "title": project.name,
                        "creative_direction": {
                            "genres": [],
                            "moods": [],
                            "audience": "Adult",
                            "explicit_adult_content": False,
                        },
                        "writing_preferences": preferences,
                    }, indent=2),
                    encoding="utf-8",
                )

            app = self.make_app(
                "Project One",
                {"Project One": project_one, "Project Two": project_two},
            )
            first_prompt = app._prepare_creative_direction_context("Write the next scene.")
            self.assertIn("HOW THIS NOVEL SHOULD READ", first_prompt)
            self.assertIn("natural, conversational prose", first_prompt)
            self.assertIn("Trust the reader", first_prompt)
            self.assertNotIn("restrained, unsettling descriptions", first_prompt)

            app.novel_var = SimpleNamespace(get=lambda: "Project Two")
            second_prompt = app._prepare_creative_direction_context("Write the next scene.")
            self.assertIn("restrained, unsettling descriptions", second_prompt)
            self.assertNotIn("natural, conversational prose", second_prompt)
            self.assertNotIn("Trust the reader", second_prompt)

    def test_blank_writing_preferences_add_no_extra_writer_guidance(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "Project"
            self.make_novel(project, {
                "genres": [],
                "moods": [],
                "audience": "Adult",
                "explicit_adult_content": False,
            })
            app = self.make_app("Project", {"Project": project})

            prompt = app._prepare_creative_direction_context("Write the scene.")

            self.assertNotIn("HOW THIS NOVEL SHOULD READ", prompt)

    def test_explicit_setting_reaches_writer_as_separate_permission(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "Adult Project"
            self.make_novel(project, {
                "genres": [],
                "moods": [],
                "audience": "Adult",
                "explicit_adult_content": True,
            })
            app = self.make_app("Adult Project", {"Adult Project": project})

            prompt = app._prepare_creative_direction_context("Write the scene.")

            self.assertIn("Intended audience: Adult", prompt)
            self.assertIn("Explicit adult content is permitted", prompt)
            self.assertIn("consenting adults", prompt)
            self.assertNotIn("Explicit adult content is not enabled", prompt)

    def test_missing_or_malformed_selected_story_bible_does_not_break_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "Project"
            project.mkdir()
            (project / "story_bible.json").write_text("{broken", encoding="utf-8")
            app = self.make_app("Project", {"Project": project})

            self.assertEqual(
                app._prepare_creative_direction_context("Write normally."),
                "Write normally.",
            )

    def test_no_selected_project_adds_no_project_specific_context(self):
        app = self.make_app("", {})

        self.assertEqual(
            app._prepare_creative_direction_context("Write normally."),
            "Write normally.",
        )


if __name__ == "__main__":
    unittest.main()
