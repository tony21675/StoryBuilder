import json
import tempfile
import unittest
from pathlib import Path

from builder.manuscript import ManuscriptManager
from builder.story_package import StoryPackage


class NovelPackageIsolationTests(unittest.TestCase):
    @staticmethod
    def _write_package(root: Path, title: str, character_file: str, character_name: str, scene_idea: str) -> None:
        root.mkdir(parents=True)
        (root / "story_bible.json").write_text(
            json.dumps({
                "title": title,
                "character_cards": [character_file],
                "canon_rules": [],
                "relationships": {},
                "locations": {},
                "story_planning": {},
            }),
            encoding="utf-8",
        )
        (root / "current_state.json").write_text(
            json.dumps({
                "chapter": 1,
                "scene": 1,
                "current_situation": f"{title} starting state.",
                "scene_cast": [character_name],
                "character_knowledge": {character_name: [f"{character_name} belongs to {title}."]},
            }),
            encoding="utf-8",
        )
        (root / character_file).write_text(
            json.dumps({"name": character_name, "description": f"Only from {title}."}),
            encoding="utf-8",
        )
        (root / "writing_guidance.json").write_text(
            json.dumps({"scene_plan": {"1": {"scene_idea": scene_idea}}}),
            encoding="utf-8",
        )

    def test_loading_one_novel_does_not_load_sibling_package_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp)
            mars_path = library / "The-Long-Way-Home"
            old_path = library / "Taken_at_Dusk"
            self._write_package(
                mars_path,
                "The Long Way Home",
                "Daniel_Okafor.json",
                "Daniel Okafor",
                "The crew checks the oxygen scrubber.",
            )
            self._write_package(
                old_path,
                "Taken at Dusk",
                "Tiffany.json",
                "Tiffany",
                "Tiffany is missing.",
            )

            mars = StoryPackage.load(mars_path)
            payload = json.dumps({
                "story_bible": mars.story_bible,
                "current_state": mars.current_state,
                "characters": mars.characters,
                "extra_json": mars.extra_json,
            }, ensure_ascii=False)

            self.assertEqual(mars.path.resolve(), mars_path.resolve())
            self.assertEqual(mars.story_bible["title"], "The Long Way Home")
            self.assertIn("Daniel Okafor", payload)
            self.assertNotIn("Tiffany", payload)
            self.assertNotIn("Taken at Dusk", payload)
            self.assertNotIn("Tiffany.json", mars.characters)

    def test_historical_retrieval_stays_inside_the_selected_novel_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp)
            mars_path = library / "The-Long-Way-Home"
            old_path = library / "Taken_at_Dusk"
            self._write_package(
                mars_path,
                "The Long Way Home",
                "Daniel_Okafor.json",
                "Daniel Okafor",
                "The crew checks the oxygen scrubber.",
            )
            self._write_package(
                old_path,
                "Taken at Dusk",
                "Tiffany.json",
                "Tiffany",
                "Tiffany is missing.",
            )
            mars_chapter = mars_path / "Manuscript" / "Chapters" / "Chapter_01"
            old_chapter = old_path / "Manuscript" / "Chapters" / "Chapter_01"
            mars_chapter.mkdir(parents=True)
            old_chapter.mkdir(parents=True)
            (mars_chapter / "Chapter_01_Section_01.txt").write_text(
                "Daniel compared the scrubber readings with Zoe's telemetry.",
                encoding="utf-8",
            )
            (old_chapter / "Chapter_01_Section_01.txt").write_text(
                "Tiffany was taken by an unidentified man.",
                encoding="utf-8",
            )

            result = ManuscriptManager(mars_path).search_historical_context(
                "Tiffany was taken by an unidentified man.",
                before_chapter=2,
                before_scene=1,
                limit=4,
                max_chars=2400,
            )

            self.assertNotIn("Tiffany", result["text"])
            self.assertNotIn("unidentified man", result["text"])
            self.assertNotIn("Taken at Dusk", result["text"])


if __name__ == "__main__":
    unittest.main()
