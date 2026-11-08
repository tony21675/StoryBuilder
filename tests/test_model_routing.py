import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from minimal_writer import MinimalWriterApp


class FakeValue:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class ModelRoutingTests(unittest.TestCase):
    def make_app(self):
        app = MinimalWriterApp.__new__(MinimalWriterApp)
        app.models = {
            "Qwen3.5-4B-Q4_K_M.gguf": Path("/models/Qwen3.5-4B-Q4_K_M.gguf"),
            "Gemma-4-E4B.gguf": Path("/models/Gemma-4-E4B.gguf"),
        }
        app.planner_model_var = FakeValue("Qwen3.5-4B-Q4_K_M.gguf")
        app.model_var = FakeValue("Gemma-4-E4B.gguf")
        return app

    def test_planner_and_writer_roles_resolve_independently(self):
        app = self.make_app()
        self.assertEqual(
            app._selected_role_model("planner"),
            Path("/models/Qwen3.5-4B-Q4_K_M.gguf"),
        )
        self.assertEqual(
            app._selected_role_model("writer"),
            Path("/models/Gemma-4-E4B.gguf"),
        )


    def test_runtime_activity_shows_loading_until_selected_model_is_live(self):
        app = self.make_app()
        app.engine = SimpleNamespace(child=None)
        app.loaded_model = None
        app.activity_task_var = FakeValue("")
        app.activity_model_var = FakeValue("")
        app.activity_state_var = FakeValue("")
        qwen = Path("/models/Qwen3.5-4B-Q4_K_M.gguf")

        app._begin_model_activity("Prepare Scene", qwen)

        self.assertEqual(app.activity_task_var.value, "Prepare Scene")
        self.assertEqual(app.activity_model_var.value, qwen.name)
        self.assertEqual(app.activity_state_var.value, "Loading")

        app.loaded_model = qwen
        app.engine.child = SimpleNamespace(isalive=lambda: True)
        self.assertTrue(app._runtime_model_is_ready(qwen))
        app._set_activity_status("Prepare Scene", qwen, "Generating")
        self.assertEqual(app.activity_state_var.value, "Generating")

    def test_idle_activity_reports_the_actual_loaded_model(self):
        app = self.make_app()
        gemma = Path("/models/Gemma-4-E4B.gguf")
        app.engine = SimpleNamespace(child=SimpleNamespace(isalive=lambda: True))
        app.loaded_model = gemma
        app.busy = False
        app.activity_task_var = FakeValue("")
        app.activity_model_var = FakeValue("")
        app.activity_state_var = FakeValue("")

        app._refresh_idle_activity()

        self.assertEqual(app.activity_task_var.value, "Idle")
        self.assertEqual(app.activity_model_var.value, gemma.name)
        self.assertEqual(app.activity_state_var.value, "Ready")

    def test_idle_activity_does_not_claim_a_dead_process_is_loaded(self):
        app = self.make_app()
        gemma = Path("/models/Gemma-4-E4B.gguf")
        app.engine = SimpleNamespace(child=SimpleNamespace(isalive=lambda: False))
        app.loaded_model = gemma
        app.busy = False
        app.activity_task_var = FakeValue("")
        app.activity_model_var = FakeValue("")
        app.activity_state_var = FakeValue("")

        app._refresh_idle_activity()

        self.assertIsNone(app.loaded_model)
        self.assertEqual(app.activity_model_var.value, "None loaded")
        self.assertEqual(app.activity_state_var.value, "Not loaded")

    def test_unknown_role_is_rejected(self):
        with self.assertRaises(ValueError):
            self.make_app()._selected_role_model("editor")

    def test_switching_roles_reloads_only_the_selected_model(self):
        app = self.make_app()
        app.engine = SimpleNamespace(child=None)
        app.loaded_model = Path("/models/Qwen3.5-4B-Q4_K_M.gguf")
        with patch("minimal_writer.load_model_for_writing") as load:
            result = app._ensure_model_loaded(Path("/models/Gemma-4-E4B.gguf"))
        load.assert_called_once_with(app.engine, Path("/models/Gemma-4-E4B.gguf"))
        self.assertEqual(result, Path("/models/Gemma-4-E4B.gguf"))
        self.assertEqual(app.loaded_model, Path("/models/Gemma-4-E4B.gguf"))

    def test_same_loaded_role_does_not_restart_live_engine(self):
        app = self.make_app()
        app.engine = SimpleNamespace(child=SimpleNamespace(isalive=lambda: True))
        app.loaded_model = Path("/models/Gemma-4-E4B.gguf")
        with patch("minimal_writer.load_model_for_writing") as load:
            app._ensure_model_loaded(Path("/models/Gemma-4-E4B.gguf"))
        load.assert_not_called()

    def test_same_model_restarts_if_engine_process_has_exited(self):
        app = self.make_app()
        app.engine = SimpleNamespace(child=SimpleNamespace(isalive=lambda: False))
        app.loaded_model = Path("/models/Gemma-4-E4B.gguf")
        with patch("minimal_writer.load_model_for_writing") as load:
            app._ensure_model_loaded(Path("/models/Gemma-4-E4B.gguf"))
        load.assert_called_once_with(app.engine, Path("/models/Gemma-4-E4B.gguf"))


if __name__ == "__main__":
    unittest.main()
