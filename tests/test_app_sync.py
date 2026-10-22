import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from builder.app_sync import StoryBuilderSyncError, sync_storybuilder_repository


class AppSyncTests(unittest.TestCase):
    def make_app_root(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "storybuilder.py").write_text("# app root", encoding="utf-8")
        (root / "builder").mkdir()
        return root

    def fake_git(self, root, *, dirty=False, branch="redesign/simplified-writing-workflow",
                 upstream=None, pull_code=0, unmerged=""):
        upstream = upstream or f"origin/{branch}"
        calls = []

        def run(command, cwd=None, text=None, capture_output=None, timeout=None, check=None):
            args = command[1:]
            calls.append(args)
            stdout = ""
            stderr = ""
            code = 0
            if args == ["rev-parse", "--show-toplevel"]:
                stdout = str(root)
            elif args == ["status"]:
                stdout = f"On branch {branch}\nworking tree {'not clean' if dirty else 'clean'}\n"
            elif args == ["branch", "--show-current"]:
                stdout = branch + "\n"
            elif args == ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]:
                stdout = upstream + "\n"
            elif args == ["diff", "--name-only", "--diff-filter=U"]:
                stdout = unmerged
            elif args == ["status", "--porcelain"]:
                stdout = " M storybuilder.py\n" if dirty else ""
            elif args == ["add", "-A"]:
                pass
            elif args == ["diff", "--cached", "--quiet"]:
                code = 1 if dirty else 0
            elif args and args[0] == "commit":
                pass
            elif args == ["fetch", "--prune", "origin"]:
                pass
            elif args == ["pull", "--ff-only", "origin", branch]:
                code = pull_code
                if code:
                    stderr = "fatal: Not possible to fast-forward, aborting."
            elif args == ["push", "origin", branch]:
                pass
            elif args == ["status", "-sb"]:
                stdout = f"## {branch}...origin/{branch}\n"
            else:
                raise AssertionError(f"Unexpected git command: {args}")
            return subprocess.CompletedProcess(command, code, stdout, stderr)

        return run, calls

    def test_clean_sync_uses_current_development_branch_and_never_merges_main(self):
        root = self.make_app_root()
        fake, calls = self.fake_git(root)
        with patch("builder.app_sync.subprocess.run", side_effect=fake):
            result = sync_storybuilder_repository(root)

        self.assertIn("application synchronized successfully", result)
        self.assertIn(["pull", "--ff-only", "origin", "redesign/simplified-writing-workflow"], calls)
        self.assertIn(["push", "origin", "redesign/simplified-writing-workflow"], calls)
        self.assertFalse(any("main" in call for call in calls))

    def test_dirty_app_files_are_committed_before_fetch_and_push(self):
        root = self.make_app_root()
        fake, calls = self.fake_git(root, dirty=True)
        with patch("builder.app_sync.subprocess.run", side_effect=fake):
            sync_storybuilder_repository(root)

        self.assertIn(["add", "-A"], calls)
        self.assertTrue(any(call and call[0] == "commit" for call in calls))
        self.assertLess(calls.index(["commit", next(x for x in calls if x[0] == "commit")[1]]), calls.index(["fetch", "--prune", "origin"]))

    def test_diverged_remote_stops_without_push(self):
        root = self.make_app_root()
        fake, calls = self.fake_git(root, dirty=True, pull_code=1)
        with patch("builder.app_sync.subprocess.run", side_effect=fake):
            with self.assertRaisesRegex(StoryBuilderSyncError, "No push was attempted"):
                sync_storybuilder_repository(root)
        self.assertNotIn(["push", "origin", "redesign/simplified-writing-workflow"], calls)

    def test_refuses_main_branch(self):
        root = self.make_app_root()
        fake, calls = self.fake_git(root, branch="main")
        with patch("builder.app_sync.subprocess.run", side_effect=fake):
            with self.assertRaisesRegex(StoryBuilderSyncError, "blocked syncing"):
                sync_storybuilder_repository(root)
        self.assertNotIn(["push", "origin", "main"], calls)

    def test_refuses_unmerged_conflict_files(self):
        root = self.make_app_root()
        fake, calls = self.fake_git(root, unmerged="storybuilder.py\n")
        with patch("builder.app_sync.subprocess.run", side_effect=fake):
            with self.assertRaisesRegex(StoryBuilderSyncError, "unresolved conflict files"):
                sync_storybuilder_repository(root)
        self.assertNotIn(["push", "origin", "redesign/simplified-writing-workflow"], calls)


if __name__ == "__main__":
    unittest.main()
