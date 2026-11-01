import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from minimal_writer import MinimalWriterApp


class WriterCreativeDirectionTests(unittest.TestCase):
    def test_writer_adds_selected_novels_creative_direction_read_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            novel_path = Path(temporary)
            story_bible = {
                "title": "Mars Mystery",
                "creative_direction": {
                    "genres": ["Science Fiction", "Mystery", "Comedy"],
                    "moods": ["Tense", "Humorous"],
                    "audience": "Adult",
                    "explicit_adult_content": False,
                },
                "locations": {},
                "premise": "A research crew faces a strange accident.",
            }
            bible_path = novel_path / "story_bible.json"
            bible_path.write_text(json.dumps(story_bible, indent=2), encoding="utf-8")
            original = bible_path.read_bytes()

            app = object.__new__(MinimalWriterApp)
            app.novel_var = SimpleNamespace(get=lambda: "Mars Mystery")
            app.novel_packages = {"Mars Mystery": novel_path}
            app.last_location_context_names = []

            prompt = MinimalWriterApp._prepare_location_context(
                app, "Write the next scene."
            )

            self.assertIn("Genres: Science Fiction, Mystery, Comedy", prompt)
            self.assertIn("Mood and tone: Tense, Humorous", prompt)
            self.assertIn("Intended audience: Adult", prompt)
            self.assertNotIn("Explicit adult content is permitted", prompt)
            self.assertEqual(app.last_location_context_names, [])
            self.assertEqual(bible_path.read_bytes(), original)

    def test_writer_allows_explicit_adult_content_only_when_enabled(self):
        with tempfile.TemporaryDirectory() as temporary:
            novel_path = Path(temporary)
            (novel_path / "story_bible.json").write_text(
                json.dumps({
                    "creative_direction": {
                        "genres": [],
                        "moods": [],
                        "audience": "Adult",
                        "explicit_adult_content": True,
                    },
                    "locations": {},
                }),
                encoding="utf-8",
            )
            app = object.__new__(MinimalWriterApp)
            app.novel_var = SimpleNamespace(get=lambda: "Novel")
            app.novel_packages = {"Novel": novel_path}
            app.last_location_context_names = []

            prompt = MinimalWriterApp._prepare_location_context(
                app, "Write the next scene."
            )

            self.assertIn("Explicit adult content is permitted", prompt)
            self.assertIn("consenting adults", prompt)

    def test_writer_ignores_absent_or_malformed_optional_story_bible(self):
        with tempfile.TemporaryDirectory() as temporary:
            novel_path = Path(temporary)
            (novel_path / "story_bible.json").write_text("{broken", encoding="utf-8")
            app = object.__new__(MinimalWriterApp)
            app.novel_var = SimpleNamespace(get=lambda: "Novel")
            app.novel_packages = {"Novel": novel_path}
            app.last_location_context_names = []

            original = "Write normally."
            self.assertEqual(
                MinimalWriterApp._prepare_location_context(app, original),
                original,
            )


if __name__ == "__main__":
    unittest.main()
