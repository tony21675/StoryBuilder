import tempfile
import unittest
from pathlib import Path

from builder.manuscript import ManuscriptManager


class ManuscriptSceneRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.manager = ManuscriptManager(Path(self.temp_dir.name) / "Novel")
        self.state = {
            "chapter": 2,
            "scene": 4,
            "scene_completed": False,
            "current_situation": "Maya is ready for a quiet cup of tea.",
            "location": {"primary": "Kitchen"},
            "physical_state": {"Tony": {"posture": "seated"}},
        }
        self.prose = "Maya settled at the kitchen table. Tony brought her tea."

    def test_loads_exact_current_scene_when_saved_baseline_matches(self):
        path = self.manager.save_scene(2, 4, self.prose)
        self.manager.save_state_before(2, 4, self.state)

        restored = self.manager.load_scene_for_state_review(2, 4, self.state)

        self.assertIsNotNone(restored)
        self.assertEqual(restored["path"], path)
        self.assertEqual(restored["text"], self.prose)
        self.assertEqual(restored["start_state"], self.state)

    def test_refuses_scene_when_saved_baseline_differs_from_current_state(self):
        self.manager.save_scene(2, 4, self.prose)
        before = dict(self.state)
        before["current_situation"] = "An earlier situation."
        self.manager.save_state_before(2, 4, before)

        with self.assertRaisesRegex(ValueError, "does not match the current story state"):
            self.manager.load_scene_for_state_review(2, 4, self.state)

    def test_returns_none_when_current_scene_has_no_saved_prose(self):
        self.assertIsNone(self.manager.load_scene_for_state_review(2, 4, self.state))

    def test_uses_current_state_when_legacy_scene_has_no_before_snapshot(self):
        self.manager.save_scene(2, 4, self.prose)

        restored = self.manager.load_scene_for_state_review(2, 4, self.state)

        self.assertIsNotNone(restored)
        self.assertEqual(restored["start_state"], self.state)
        self.assertIsNot(restored["start_state"], self.state)


if __name__ == "__main__":
    unittest.main()
