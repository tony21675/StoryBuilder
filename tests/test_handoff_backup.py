import tempfile
import unittest
from pathlib import Path

from builder.handoff_backup import refresh_handoff_backups


class HandoffBackupTests(unittest.TestCase):
    def test_copies_only_named_handoffs_to_separate_local_mirror(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "StoryBuilder"
            novels = root / "MyNovel"
            backup = root / "Backups"
            (app).mkdir()
            lwh = novels / "The-Long-Way-Home"
            taken = novels / "Taken_at_Dusk"
            lwh.mkdir(parents=True)
            taken.mkdir(parents=True)

            files = {
                app / "CHAT_HANDOFF_LATEST.md": "app index",
                app / "WRITER_APP_HANDOFF.md": "writer notes",
                app / "STORY_BIBLE_APP_HANDOFF.md": "bible notes",
                lwh / "CHAT_HANDOFF_LATEST.md": "novel handoff",
                lwh / "STORY_DIRECTION.md": "story direction",
                taken / "HANDOFF_LATEST.md": "paused novel",
                taken / "STORY_PLAN.md": "story plan",
                taken / "SECRET_LETTERS_STORAGE.md": "storage reference",
            }
            for path, content in files.items():
                path.write_text(content, encoding="utf-8")
            (lwh / "private.enc").write_text("must not be copied", encoding="utf-8")

            messages = refresh_handoff_backups(
                storybuilder_root=app, novel_root=novels, backup_root=backup
            )

            self.assertTrue(any("8 updated" in item for item in messages[:1]))
            for source, content in files.items():
                relative = source.relative_to(root)
                mirrored = backup / relative
                self.assertEqual(mirrored.read_text(encoding="utf-8"), content)
            self.assertFalse((backup / "The-Long-Way-Home" / "private.enc").exists())
            self.assertTrue((backup / "README.md").is_file())

    def test_second_run_does_not_rewrite_unchanged_mirrors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "StoryBuilder"
            app.mkdir()
            (app / "CHAT_HANDOFF_LATEST.md").write_text("index", encoding="utf-8")
            backup = root / "Backups"

            first = refresh_handoff_backups(
                storybuilder_root=app, novel_root=root / "missing", backup_root=backup
            )
            destination = backup / "StoryBuilder" / "CHAT_HANDOFF_LATEST.md"
            timestamp = destination.stat().st_mtime_ns
            second = refresh_handoff_backups(
                storybuilder_root=app, novel_root=root / "missing", backup_root=backup
            )

            self.assertTrue(any("UPDATED:" in item for item in first))
            self.assertTrue(any("CURRENT:" in item for item in second))
            self.assertEqual(destination.stat().st_mtime_ns, timestamp)


if __name__ == "__main__":
    unittest.main()
