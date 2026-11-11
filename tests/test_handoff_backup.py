import tempfile
import unittest
from pathlib import Path

from builder.handoff_backup import refresh_handoff_backups


class HandoffBackupTests(unittest.TestCase):
    def test_copies_only_current_app_and_novel_handoffs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "StoryBuilder"
            novels = root / "MyNovel"
            backup = root / "Backups"
            app.mkdir()
            lwh = novels / "The-Long-Way-Home"
            taken = novels / "Taken_at_Dusk"
            summer = novels / "Summer-at-Willow-Bay"
            for folder in (lwh, taken, summer):
                folder.mkdir(parents=True)

            files = {
                app / "WRITER_APP_HANDOFF.md": "writer notes",
                app / "STORY_BIBLE_APP_HANDOFF.md": "bible notes",
                lwh / "HANDOFF_LATEST.md": "Long Way Home handoff",
                lwh / "STORY_DIRECTION.md": "story direction",
                taken / "HANDOFF_LATEST.md": "Taken at Dusk reset warning",
                taken / "STORY_PLAN.md": "story plan",
                summer / "HANDOFF_LATEST.md": "Summer handoff",
            }
            for path, content in files.items():
                path.write_text(content, encoding="utf-8")

            # Existing obsolete mirror files are removed by exact path only.
            retired_app_index = backup / "StoryBuilder" / "CHAT_HANDOFF_LATEST.md"
            retired_lwh_handoff = backup / "The-Long-Way-Home" / "CHAT_HANDOFF_LATEST.md"
            retired_app_index.parent.mkdir(parents=True)
            retired_lwh_handoff.parent.mkdir(parents=True)
            retired_app_index.write_text("obsolete app index", encoding="utf-8")
            retired_lwh_handoff.write_text("obsolete LWH filename", encoding="utf-8")

            # Secret-letter references and protected project assets are outside
            # the pruning list and must remain exactly as they were.
            secret_reference = backup / "Taken-at-Dusk" / "SECRET_LETTERS_HANDOFF.md"
            secret_reference.parent.mkdir(parents=True)
            secret_reference.write_text("leave this reference untouched", encoding="utf-8")
            (taken / "private.enc").write_text("must not be copied", encoding="utf-8")

            messages = refresh_handoff_backups(
                storybuilder_root=app, novel_root=novels, backup_root=backup
            )

            self.assertTrue(any("7 updated" in item for item in messages[:1]))
            expected = {
                "StoryBuilder/WRITER_APP_HANDOFF.md": "writer notes",
                "StoryBuilder/STORY_BIBLE_APP_HANDOFF.md": "bible notes",
                "The-Long-Way-Home/HANDOFF_LATEST.md": "Long Way Home handoff",
                "The-Long-Way-Home/STORY_DIRECTION.md": "story direction",
                "Taken-at-Dusk/HANDOFF_LATEST.md": "Taken at Dusk reset warning",
                "Taken-at-Dusk/STORY_PLAN.md": "story plan",
                "Summer-at-Willow-Bay/HANDOFF_LATEST.md": "Summer handoff",
            }
            for relative, content in expected.items():
                self.assertEqual((backup / relative).read_text(encoding="utf-8"), content)

            self.assertFalse(retired_app_index.exists())
            self.assertFalse(retired_lwh_handoff.exists())
            self.assertEqual(
                secret_reference.read_text(encoding="utf-8"),
                "leave this reference untouched",
            )
            self.assertFalse((backup / "Taken-at-Dusk" / "private.enc").exists())
            self.assertTrue((backup / "README.md").is_file())

    def test_refresh_does_not_remove_other_handoff_or_secret_letter_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "StoryBuilder"
            app.mkdir()
            (app / "WRITER_APP_HANDOFF.md").write_text("writer", encoding="utf-8")
            (app / "STORY_BIBLE_APP_HANDOFF.md").write_text("bible", encoding="utf-8")
            backup = root / "Backups"

            keep = [
                backup / "Taken-at-Dusk" / "SECRET_LETTERS_STORAGE.md",
                backup / "Taken-at-Dusk" / "SECRET_LETTERS_HANDOFF.md",
                backup / "SomeOtherProject" / "HANDOFF.md",
            ]
            for path in keep:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("do not touch", encoding="utf-8")

            refresh_handoff_backups(
                storybuilder_root=app, novel_root=root / "missing", backup_root=backup
            )

            for path in keep:
                self.assertEqual(path.read_text(encoding="utf-8"), "do not touch")

    def test_second_run_does_not_rewrite_unchanged_mirrors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "StoryBuilder"
            app.mkdir()
            (app / "WRITER_APP_HANDOFF.md").write_text("writer notes", encoding="utf-8")
            backup = root / "Backups"

            first = refresh_handoff_backups(
                storybuilder_root=app, novel_root=root / "missing", backup_root=backup
            )
            destination = backup / "StoryBuilder" / "WRITER_APP_HANDOFF.md"
            timestamp = destination.stat().st_mtime_ns
            second = refresh_handoff_backups(
                storybuilder_root=app, novel_root=root / "missing", backup_root=backup
            )

            self.assertTrue(any("UPDATED:" in item for item in first))
            self.assertTrue(any("CURRENT:" in item for item in second))
            self.assertEqual(destination.stat().st_mtime_ns, timestamp)


if __name__ == "__main__":
    unittest.main()
