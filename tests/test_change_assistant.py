import json
import tempfile
import unittest
from pathlib import Path

from builder.change_assistant import apply_change_request_patch, normalize_change_patch, render_change_preview
from builder.story_package import StoryPackage


class ChangeAssistantTests(unittest.TestCase):
    def make_package(self):
        package = StoryPackage.new("Test Novel")
        filename = package.add_character("Maya")
        package.characters[filename].update({
            "name": "Maya", "age": 18, "occupation": "Student",
            "background": "Maya has known Tony and Tiffany for years.",
        })
        package.story_bible["canon_rules"] = [
            "Tiffany is 18.",
            "Only one kidnapper is currently established.",
        ]
        package.story_bible["supporting_people"] = {
            "Beth": "Maya's caring mother who lives next door."
        }
        return package, filename

    def test_rules_profile_and_supporting_person_changes_are_applied_after_validation(self):
        package, filename = self.make_package()
        request = "Nobody else learns Tiffany is missing until breakfast. Make Maya more confident later. Add Jessica as the computer expert."
        patch = {
            "canon_rules_add": [
                "Nobody besides Tony and Maya knows Tiffany is missing until breakfast.",
                "Only one kidnapper is currently established.",
            ],
            "characters": {filename: {"background": "Maya begins frightened but grows confident through training."}},
            "supporting_people": {"Jessica": "Jessica is the group's computer expert."},
        }
        normalized = normalize_change_patch(patch, package, request)
        self.assertEqual(len(normalized["canon_rules_add"]), 1)
        preview = render_change_preview(package, normalized)
        self.assertIn("CHARACTER: Maya", preview)
        self.assertIn("SUPPORTING PERSON: Jessica (new entry)", preview)
        self.assertIn("APPROVAL REQUIRED", preview)

        summary = apply_change_request_patch(package, normalized, request_text=request)
        self.assertIn("Nobody besides Tony and Maya knows Tiffany is missing until breakfast.", package.story_bible["canon_rules"])
        self.assertEqual(package.characters[filename]["background"], "Maya begins frightened but grows confident through training.")
        self.assertEqual(package.story_bible["supporting_people"]["Jessica"], "Jessica is the group's computer expert.")
        self.assertIn("canon rule", summary)

    def test_rejects_unknown_character_files(self):
        package, _ = self.make_package()
        with self.assertRaisesRegex(ValueError, "unknown character file"):
            normalize_change_patch({"characters": {"MadeUp.json": {"occupation": "Spy"}}}, package, "Change this character")

    def test_new_supporting_person_must_be_named_in_request(self):
        package, _ = self.make_package()
        with self.assertRaisesRegex(ValueError, "not named in your request"):
            normalize_change_patch({"supporting_people": {"Jessica": "Computer expert"}}, package, "Help the group find a lead.")

    def test_change_assistant_cannot_rename_character(self):
        package, filename = self.make_package()
        with self.assertRaisesRegex(ValueError, "cannot rename"):
            normalize_change_patch({"characters": {filename: {"name": "Different Person"}}}, package, "Change Maya into someone else.")


class StoryPackageBackupTests(unittest.TestCase):
    def test_backups_capture_changed_json_and_no_backup_is_created_when_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "My Novel"
            package = StoryPackage.new("My Novel")
            package.save(folder)
            self.assertIsNone(package.last_backup_path)
            before = (folder / "story_bible.json").read_text(encoding="utf-8")

            package.story_bible["canon_rules"] = ["No police will be called."]
            package.save()
            backup = package.last_backup_path
            self.assertIsNotNone(backup)
            self.assertEqual((backup / "story_bible.json").read_text(encoding="utf-8"), before)
            self.assertEqual(json.loads((folder / "story_bible.json").read_text(encoding="utf-8"))["canon_rules"], ["No police will be called."])

            package.save()
            self.assertIsNone(package.last_backup_path)

    def test_orphan_json_is_backed_up_before_existing_cleanup_removes_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "My Novel"
            package = StoryPackage.new("My Novel")
            package.save(folder)
            orphan = folder / "old_unused.json"
            orphan.write_text('{"keep":"for backup"}\n', encoding="utf-8")
            package.save()
            backup = package.last_backup_path
            self.assertIsNotNone(backup)
            self.assertEqual((backup / "old_unused.json").read_text(encoding="utf-8"), '{"keep":"for backup"}\n')
            self.assertFalse(orphan.exists())


if __name__ == "__main__":
    unittest.main()
