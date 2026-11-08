import tempfile
import unittest
from pathlib import Path

from builder.model_preferences import (
    default_model_roles,
    load_model_roles,
    resolve_model_roles,
    save_model_roles,
)


class ModelPreferenceTests(unittest.TestCase):
    def test_defaults_select_qwen_planner_and_gemma_e4b_writer(self):
        roles = default_model_roles(
            [
                "gemma-4-12B-it-Q4_K_M.gguf",
                "Qwen3.5-4B-Q4_K_M.gguf",
                "01llmfan46--gemma-4-E4B-it-ultra-uncensored-heretic-Q4_K_M.gguf",
            ]
        )
        self.assertEqual(roles["planner"], "Qwen3.5-4B-Q4_K_M.gguf")
        self.assertEqual(
            roles["writer"],
            "01llmfan46--gemma-4-E4B-it-ultra-uncensored-heretic-Q4_K_M.gguf",
        )

    def test_defaults_fall_back_to_first_available_model(self):
        self.assertEqual(
            default_model_roles(["Dolphin.gguf", "Stheno.gguf"]),
            {"planner": "Dolphin.gguf", "writer": "Dolphin.gguf"},
        )

    def test_empty_model_list_has_no_selection(self):
        self.assertEqual(default_model_roles([]), {"planner": "", "writer": ""})

    def test_resolve_keeps_valid_saved_roles_and_replaces_missing_models(self):
        roles = resolve_model_roles(
            ["Qwen3.5-4B.gguf", "Gemma-4-E4B.gguf", "Dolphin.gguf"],
            {"planner": "Dolphin.gguf", "writer": "missing.gguf"},
        )
        self.assertEqual(
            roles, {"planner": "Dolphin.gguf", "writer": "Gemma-4-E4B.gguf"}
        )

    def test_save_and_load_model_roles_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "storybuilder" / "model_roles.json"
            saved_path = save_model_roles(
                planner="Qwen3.5-4B.gguf", writer="Gemma-4-E4B.gguf", path=path
            )
            self.assertEqual(saved_path, path)
            self.assertEqual(
                load_model_roles(path),
                {"planner": "Qwen3.5-4B.gguf", "writer": "Gemma-4-E4B.gguf"},
            )

    def test_invalid_or_missing_preferences_are_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(load_model_roles(Path(temporary) / "missing.json"), {})


if __name__ == "__main__":
    unittest.main()
