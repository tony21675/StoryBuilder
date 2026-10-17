import tempfile
import unittest
from pathlib import Path

from builder.story_package import StoryPackage


class PromoteSupportingPersonTests(unittest.TestCase):
    def test_promotes_existing_json_without_losing_character_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = StoryPackage.new("Test Novel")
            package.story_bible["supporting_people"] = {"Beth": "Maya's mother"}
            package.extra_json["Beth.json"] = {
                "name": "Beth",
                "status": "supporting",
                "role": "Maya's mother",
                "personality": ["warm", "caring"],
                "story_role": "Lightly used supporting character.",
            }
            package.save(root)

            loaded = StoryPackage.load(root)
            self.assertIn("Beth.json", loaded.extra_json)

            filename = loaded.promote_supporting_person("Beth")

            self.assertEqual(filename, "Beth.json")
            self.assertIn(filename, loaded.characters)
            self.assertNotIn(filename, loaded.extra_json)
            self.assertNotIn("Beth", loaded.story_bible["supporting_people"])
            self.assertIn(filename, loaded.story_bible["character_cards"])
            self.assertEqual(loaded.characters[filename]["personality"], ["warm", "caring"])
            self.assertEqual(loaded.characters[filename]["story_role"], "Lightly used supporting character.")
            self.assertEqual(loaded.characters[filename]["status"], "established")

            loaded.save()
            reloaded = StoryPackage.load(root)
            self.assertIn(filename, reloaded.characters)
            self.assertNotIn(filename, reloaded.extra_json)
            self.assertNotIn("Beth", reloaded.story_bible["supporting_people"])
            self.assertTrue((root / filename).is_file())

    def test_promotes_supporting_person_when_no_json_card_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = StoryPackage.new("Test Novel")
            package.story_bible["supporting_people"] = {
                "Jessica": "Chloe's mother and a close family friend."
            }
            package.save(root)

            loaded = StoryPackage.load(root)
            filename = loaded.promote_supporting_person("Jessica")

            self.assertEqual(filename, "Jessica.json")
            self.assertEqual(loaded.characters[filename]["name"], "Jessica")
            self.assertEqual(
                loaded.characters[filename]["description"],
                "Chloe's mother and a close family friend.",
            )
            self.assertNotIn("Jessica", loaded.story_bible["supporting_people"])

    def test_refuses_to_promote_a_character_that_is_already_core(self):
        package = StoryPackage.new("Test Novel")
        package.characters["Beth.json"] = {"name": "Beth"}
        package.story_bible["character_cards"] = ["Beth.json"]
        package.story_bible["supporting_people"] = {"Beth": "Maya's mother"}

        with self.assertRaisesRegex(ValueError, "already has a core character card"):
            package.promote_supporting_person("Beth")

        self.assertIn("Beth", package.story_bible["supporting_people"])
        self.assertIn("Beth.json", package.characters)


if __name__ == "__main__":
    unittest.main()
