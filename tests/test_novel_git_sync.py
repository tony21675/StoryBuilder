import subprocess
import tempfile
import unittest
from pathlib import Path

from builder.novel_git_sync import (
    NovelGitSyncError,
    inspect_novel_repository,
    sync_novel_repository,
)


def git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=str(repository),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AssertionError(
            f"git {' '.join(arguments)} failed in {repository}:\n{result.stderr}"
        )
    return result.stdout.strip()


class NovelGitSyncTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.remote = self.root / "origin.git"
        self.novel = self.root / "The-Test-Novel"
        git(self.root, "init", "--bare", "--initial-branch=main", str(self.remote))
        self.novel.mkdir()
        git(self.novel, "init", "--initial-branch=main")
        git(self.novel, "config", "user.name", "Writer Test")
        git(self.novel, "config", "user.email", "writer-test@example.invalid")
        (self.novel / "story_bible.json").write_text("{}\n", encoding="utf-8")
        git(self.novel, "add", "story_bible.json")
        git(self.novel, "commit", "-m", "Initial novel package")
        git(self.novel, "remote", "add", "origin", str(self.remote))
        git(self.novel, "push", "-u", "origin", "main")

    def tearDown(self):
        self.temporary.cleanup()

    def make_remote_commit(self, filename: str, contents: str) -> None:
        worktree = self.root / "remote-worktree"
        git(self.root, "clone", str(self.remote), str(worktree))
        git(worktree, "config", "user.name", "Remote Test")
        git(worktree, "config", "user.email", "remote-test@example.invalid")
        (worktree / filename).parent.mkdir(parents=True, exist_ok=True)
        (worktree / filename).write_text(contents, encoding="utf-8")
        git(worktree, "add", filename)
        git(worktree, "commit", "-m", f"Remote update: {filename}")
        git(worktree, "push", "origin", "main")

    def read_remote_file(self, path: str) -> str:
        result = subprocess.run(
            ["git", "--git-dir", str(self.remote), "show", f"main:{path}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise AssertionError(f"Remote file {path} was not available:\n{result.stderr}")
        return result.stdout

    def test_preview_identifies_selected_repository_branch_remote_and_changes(self):
        scene = self.novel / "Manuscript" / "Chapters" / "Chapter_01" / "Chapter_01_Section_01.txt"
        scene.parent.mkdir(parents=True)
        scene.write_text("A test scene.\n", encoding="utf-8")

        preview = inspect_novel_repository(self.novel)

        self.assertEqual(preview.repository, self.novel.resolve())
        self.assertEqual(preview.branch, "main")
        self.assertEqual(preview.upstream, "origin/main")
        self.assertEqual(preview.remote_url, str(self.remote))
        self.assertIn("Manuscript/Chapters/Chapter_01/Chapter_01_Section_01.txt", preview.changed_files)

    def test_sync_commits_and_pushes_selected_novel_changes(self):
        scene = self.novel / "Manuscript" / "Chapters" / "Chapter_01" / "Chapter_01_Section_01.txt"
        scene.parent.mkdir(parents=True)
        scene.write_text("Updated scene text from the Writer.\n", encoding="utf-8")

        result = sync_novel_repository(self.novel)

        self.assertTrue(result.committed)
        self.assertEqual(result.branch, "main")
        self.assertIn("Synced", result.message)
        self.assertEqual(
            self.read_remote_file("Manuscript/Chapters/Chapter_01/Chapter_01_Section_01.txt"),
            "Updated scene text from the Writer.\n",
        )
        self.assertEqual(git(self.novel, "status", "--porcelain"), "")

    def test_sync_fast_forwards_remote_before_committing_local_work(self):
        self.make_remote_commit("remote-only.txt", "Remote update.\n")
        (self.novel / "local-only.txt").write_text("Local update.\n", encoding="utf-8")

        result = sync_novel_repository(self.novel)

        self.assertTrue(result.committed)
        self.assertEqual(self.read_remote_file("remote-only.txt"), "Remote update.\n")
        self.assertEqual(self.read_remote_file("local-only.txt"), "Local update.\n")
        self.assertEqual(git(self.novel, "status", "--porcelain"), "")

    def test_sync_refuses_protected_secret_paths_before_stashing_or_pushing(self):
        secret = self.novel / "secrets" / "private-letter.enc.b64"
        secret.parent.mkdir()
        secret.write_text("NEVER UPLOAD THIS TEST SENTINEL\n", encoding="utf-8")
        remote_head_before = subprocess.run(
            ["git", "--git-dir", str(self.remote), "rev-parse", "refs/heads/main"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        with self.assertRaisesRegex(NovelGitSyncError, "Local-only secret"):
            sync_novel_repository(self.novel)

        remote_head_after = subprocess.run(
            ["git", "--git-dir", str(self.remote), "rev-parse", "refs/heads/main"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        self.assertEqual(remote_head_after, remote_head_before)
        self.assertTrue(secret.is_file())

    def test_diverged_remote_blocks_push_and_restores_local_untracked_work(self):
        (self.novel / "local-commit.txt").write_text("Local commit.\n", encoding="utf-8")
        git(self.novel, "add", "local-commit.txt")
        git(self.novel, "commit", "-m", "Local-only commit")
        self.make_remote_commit("remote-commit.txt", "Remote-only commit.\n")
        work_in_progress = self.novel / "work-in-progress.txt"
        work_in_progress.write_text("Keep this local work.\n", encoding="utf-8")

        with self.assertRaisesRegex(NovelGitSyncError, "No commit or push was attempted"):
            sync_novel_repository(self.novel)

        self.assertTrue(work_in_progress.is_file())
        self.assertEqual(
            work_in_progress.read_text(encoding="utf-8"),
            "Keep this local work.\n",
        )
        self.assertEqual(self.read_remote_file("remote-commit.txt"), "Remote-only commit.\n")
        with self.assertRaises(AssertionError):
            self.read_remote_file("local-commit.txt")
        self.assertIn("work-in-progress.txt", git(self.novel, "status", "--porcelain"))

    def test_sync_requires_the_selected_branch_to_track_its_own_origin_branch(self):
        git(self.novel, "branch", "--unset-upstream")

        with self.assertRaisesRegex(NovelGitSyncError, "no upstream configured"):
            inspect_novel_repository(self.novel)


if __name__ == "__main__":
    unittest.main()
