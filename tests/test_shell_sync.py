import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ShellSyncTests(unittest.TestCase):
    def test_sync_uses_current_development_branch_and_blocks_main(self):
        script = (ROOT / "sync.sh").read_text(encoding="utf-8")

        self.assertIn('BRANCH="$(git branch --show-current)"', script)
        self.assertIn('if [[ "$BRANCH" == "main" ]]', script)
        self.assertNotIn('if [[ "$BRANCH" != "main" ]]', script)
        self.assertIn('UPSTREAM="$(git rev-parse --abbrev-ref --symbolic-full-name', script)
        self.assertIn('git pull --ff-only "$REMOTE" "$BRANCH"', script)
        self.assertNotIn("git pull --rebase", script)

    def test_start_syncs_before_launching_minimal_writer_with_python3(self):
        script = (ROOT / "start.sh").read_text(encoding="utf-8")

        sync_position = script.index('bash "$SCRIPT_DIR/sync.sh" start')
        launch_position = script.index('exec python3 "$SCRIPT_DIR/minimal_writer.py"')
        self.assertLess(sync_position, launch_position)
        self.assertIn("set -euo pipefail", script)
        self.assertNotIn('exec python3 "$SCRIPT_DIR/storybuilder.py"', script)


if __name__ == "__main__":
    unittest.main()
