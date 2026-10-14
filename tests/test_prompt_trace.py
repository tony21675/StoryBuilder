import json
import tempfile
import unittest
from pathlib import Path

from builder.prompt_trace import PromptTrace, default_prompt_trace_path


class PromptTraceTests(unittest.TestCase):
    def make_trace(self, path, scene=4, idea="Write a quiet scene."):
        return PromptTrace(
            chapter=2,
            scene=scene,
            model_path="/home/test/Models/test.gguf",
            current_state={"chapter": 2, "scene": scene, "current_situation": "They are talking."},
            reference_files=[("scene_state.json", '{"chapter": 2}'), ("canon.txt", "Stay in canon.")],
            contract={"author_idea": idea, "required_beats": []},
            scene_direction="Keep the dialogue natural.",
            author_guidance="No floral scents.",
            system_prompt="You write natural prose for an ongoing fictional novel.\n\nRules:\nKeep canon.\n",
            path=path,
        )

    def test_default_trace_path_is_local_and_single_file(self):
        path = default_prompt_trace_path()
        self.assertEqual(path.name, "prompt_trace.json")
        self.assertEqual(path.parent.name, "storybuilder")
        self.assertIn(".local", path.parts)
        self.assertNotIn("Documents", path.parts)

    def test_trace_keeps_exact_original_and_sent_prompts_and_runtime_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prompt_trace.json"
            trace = self.make_trace(path)
            original = "AUTHOR IDEA:\nWrite a quiet scene.\nWrite the scene now."
            sent = "AUTHOR IDEA: Write a quiet scene. Write the scene now."

            self.assertFalse(path.exists(), "Capture stays in memory until the one scene ends.")
            trace.record_session(
                model_path="/home/test/Models/test.gguf",
                runtime_binary="/usr/local/bin/llama-cli",
                system_prompt=trace.primary_system_prompt,
                context_size=16384,
                max_tokens=3000,
                device=None,
                runtime_options={"repeat_penalty": 1.08, "reasoning": "off"},
            )
            call_id = trace.begin_generation(prompt=original, sent_prompt=sent)
            trace.finish_generation(
                call_id=call_id,
                response="Maya nodded.",
                cli_diagnostics="[ Prompt: 750 tokens | Generation: 12 tokens ]",
                duration_seconds=1.25,
            )
            trace.record_event("validator_result", attempt=1, result={"pass": False})

            saved_path = trace.finish(status="completed")
            self.assertEqual(saved_path, path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            call = payload["generation_calls"][0]

            self.assertEqual(call["input_before_runtime_normalization"], original)
            self.assertEqual(call["exact_user_text_sent_to_runtime"], sent)
            self.assertEqual(call["response"], "Maya nodded.")
            self.assertIn("Prompt: 750 tokens", call["cli_diagnostics"])
            self.assertEqual(payload["sessions"][0]["context_size_tokens"], 16384)
            self.assertIn("You write natural prose", next(iter(payload["system_prompts"].values()))["content"])
            self.assertEqual(payload["workflow_events"][0]["event"], "validator_result")
            self.assertEqual(payload["status"], "completed")

    def test_next_capture_overwrites_previous_trace_without_creating_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prompt_trace.json"
            first = self.make_trace(path, scene=3, idea="First scene.")
            first.finish(status="completed")
            first_size = path.stat().st_size

            second = self.make_trace(path, scene=4, idea="Replacement scene.")
            second.finish(status="validation_unavailable", validation_warning="No readable JSON.")
            payload = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(payload["scene"], {"chapter": 2, "scene": 4})
            self.assertEqual(payload["status"], "validation_unavailable")
            self.assertEqual(payload["validation_warning"], "No readable JSON.")
            self.assertNotIn("First scene.", path.read_text(encoding="utf-8"))
            self.assertTrue(path.stat().st_size > 0)
            self.assertEqual(len(list(Path(tmp).glob("*.json"))), 1)
            self.assertGreaterEqual(first_size, 1)

    def test_failed_trace_write_is_reported_without_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocked_path = Path(tmp) / "not-a-directory" / "prompt_trace.json"
            blocked_path.parent.mkdir()
            blocked_path.parent.rmdir()
            blocked_path.parent.write_text("file blocks directory creation", encoding="utf-8")
            trace = self.make_trace(blocked_path)

            self.assertIsNone(trace.finish(status="completed"))
            self.assertTrue(trace.save_error)


if __name__ == "__main__":
    unittest.main()
