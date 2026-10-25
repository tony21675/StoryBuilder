import base64
import json
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

from builder.prompt_trace import (
    PromptTrace, default_prompt_trace_path, load_prompt_trace_enabled, save_prompt_trace_enabled,
)
from builder.prompt_trace_sync import upload_prompt_trace


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

    def test_trace_setting_defaults_on_and_persists_user_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings" / "prompt_trace_enabled.json"
            self.assertTrue(load_prompt_trace_enabled(path), "A first run defaults tracing on.")
            save_prompt_trace_enabled(False, path)
            self.assertFalse(load_prompt_trace_enabled(path), "Off survives an application restart.")
            save_prompt_trace_enabled(True, path)
            self.assertTrue(load_prompt_trace_enabled(path), "On survives an application restart.")
            path.write_text("{broken", encoding="utf-8")
            self.assertFalse(load_prompt_trace_enabled(path), "A corrupted setting fails closed.")

    def test_state_analysis_prompts_are_classified_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            ending = "You determine only the actual ending state of a completed scene."
            trace = PromptTrace(
                chapter=1,
                scene=4,
                model_path="writer.gguf",
                current_state={},
                reference_files=[],
                contract={},
                scene_direction="",
                author_guidance="",
                system_prompt=ending,
                path=Path(tmp) / "prompt_trace.json",
            )
            trace.record_session(
                model_path="writer.gguf",
                runtime_binary="llama-cli",
                system_prompt=ending,
                context_size=8192,
                max_tokens=700,
                device=None,
                runtime_options={},
            )
            trace.record_session(
                model_path="writer.gguf",
                runtime_binary="llama-cli",
                system_prompt="You extract only concrete new evidence and events from a completed scene.",
                context_size=8192,
                max_tokens=1100,
                device=None,
                runtime_options={},
            )
            self.assertEqual(
                [item["role"] for item in trace.data["sessions"]],
                ["state_ending_analysis", "state_evidence_analysis"],
            )

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




class PromptTraceSyncTests(unittest.TestCase):
    class Response:
        def __init__(self, payload):
            self.payload = json.dumps(payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return self.payload

    @staticmethod
    def http_404(url):
        return HTTPError(url, 404, "Not Found", None, BytesIO(b'{"message":"Not Found"}'))

    def make_trace_file(self, directory):
        path = Path(directory) / "prompt_trace.json"
        path.write_text(
            json.dumps({"format": "storybuilder-prompt-trace", "scene": {"chapter": 2, "scene": 4}}),
            encoding="utf-8",
        )
        return path

    def test_upload_creates_private_trace_as_a_root_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = self.make_trace_file(tmp)
            calls = []

            def fake_urlopen(request, timeout=20):
                method = request.get_method()
                url = request.full_url
                payload = json.loads(request.data) if request.data else None
                calls.append((method, url, payload))
                if method == "GET" and url.endswith("/repos/owner/traces"):
                    return self.Response({"private": True, "default_branch": "main"})
                if method == "GET" and url.endswith("/git/ref/heads/main"):
                    raise self.http_404(url)
                if method == "PUT" and url.endswith("/contents/prompt_trace.json"):
                    return self.Response({
                        "content": {
                            "path": "prompt_trace.json",
                            "html_url": "https://github.com/owner/traces/blob/main/prompt_trace.json",
                        },
                        "commit": {
                            "sha": "root-commit-sha",
                            "html_url": "https://github.com/owner/traces/commit/root-commit-sha",
                        },
                    })
                raise AssertionError(f"Unexpected GitHub request: {method} {url}")

            with patch.dict(
                os.environ,
                {"STORYBUILDER_TRACE_GITHUB_TOKEN": "test-token"},
                clear=True,
            ), patch("builder.prompt_trace_sync.urlopen", side_effect=fake_urlopen):
                result = upload_prompt_trace(trace_path, repository="owner/traces")

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["url"], "https://github.com/owner/traces/blob/main/prompt_trace.json")
            self.assertTrue(any(method == "PUT" and url.endswith("/contents/prompt_trace.json") for method, url, _ in calls))
            self.assertFalse(any(url.endswith("/git/commits") or url.endswith("/git/refs") for _, url, _ in calls))
            init_payload = next(payload for method, url, payload in calls if method == "PUT" and url.endswith("/contents/prompt_trace.json"))
            self.assertNotIn("branch", init_payload)
            self.assertEqual(json.loads(base64.b64decode(init_payload["content"])), {
                "format": "storybuilder-prompt-trace",
                "scene": {"chapter": 2, "scene": 4},
            })
            self.assertNotIn("test-token", repr(calls))

    def test_update_replaces_branch_with_new_root_and_rejects_extra_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = self.make_trace_file(tmp)
            calls = []

            def fake_urlopen(request, timeout=20):
                method = request.get_method()
                url = request.full_url
                payload = json.loads(request.data) if request.data else None
                calls.append((method, url, payload))
                if method == "GET" and url.endswith("/repos/owner/traces"):
                    return self.Response({"private": True, "default_branch": "main"})
                if method == "GET" and url.endswith("/git/ref/heads/main"):
                    return self.Response({"object": {"sha": "old-commit"}})
                if method == "GET" and url.endswith("/git/commits/old-commit"):
                    return self.Response({"tree": {"sha": "old-tree"}})
                if method == "GET" and "/git/trees/old-tree?" in url:
                    return self.Response({"tree": [{"path": "prompt_trace.json", "type": "blob"}]})
                if method == "POST" and url.endswith("/git/blobs"):
                    return self.Response({"sha": "new-blob"})
                if method == "POST" and url.endswith("/git/trees"):
                    return self.Response({"sha": "new-tree"})
                if method == "POST" and url.endswith("/git/commits"):
                    return self.Response({"sha": "new-root-commit"})
                if method == "PATCH" and url.endswith("/git/refs/heads/main"):
                    return self.Response({"ref": "refs/heads/main"})
                raise AssertionError(f"Unexpected GitHub request: {method} {url}")

            with patch.dict(
                os.environ,
                {"STORYBUILDER_TRACE_GITHUB_TOKEN": "test-token"},
                clear=True,
            ), patch("builder.prompt_trace_sync.urlopen", side_effect=fake_urlopen):
                result = upload_prompt_trace(trace_path, repository="owner/traces")

            self.assertTrue(result["ok"], result)
            patch_request = next(item for item in calls if item[0] == "PATCH")
            self.assertTrue(patch_request[1].endswith("/git/refs/heads/main"))
            self.assertTrue(patch_request[2]["force"])
            commit_payload = next(payload for method, url, payload in calls if method == "POST" and url.endswith("/git/commits"))
            self.assertEqual(commit_payload["parents"], [])

    def test_default_repository_is_owned_by_authenticated_github_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = self.make_trace_file(tmp)
            calls = []

            def fake_urlopen(request, timeout=20):
                method = request.get_method()
                url = request.full_url
                calls.append((method, url))
                if method == "GET" and url.endswith("/user"):
                    return self.Response({"login": "sample-owner"})
                if method == "GET" and url.endswith("/repos/sample-owner/StoryBuilder-Traces"):
                    return self.Response({"private": True, "default_branch": "main"})
                if method == "GET" and url.endswith("/git/ref/heads/main"):
                    raise self.http_404(url)
                if method == "PUT" and url.endswith("/contents/prompt_trace.json"):
                    return self.Response({
                        "content": {
                            "path": "prompt_trace.json",
                            "html_url": "https://github.com/sample-owner/StoryBuilder-Traces/blob/main/prompt_trace.json",
                        },
                        "commit": {"html_url": "https://github.com/sample-owner/StoryBuilder-Traces/commit/root"},
                    })
                raise AssertionError(f"Unexpected GitHub request: {method} {url}")

            with patch.dict(
                os.environ,
                {"STORYBUILDER_TRACE_GITHUB_TOKEN": "test-token"},
                clear=True,
            ), patch("builder.prompt_trace_sync.urlopen", side_effect=fake_urlopen):
                result = upload_prompt_trace(trace_path)

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["repository"], "sample-owner/StoryBuilder-Traces")
            self.assertTrue(any(url.endswith("/user") for _, url in calls))

    def test_upload_is_refused_if_repository_is_not_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = self.make_trace_file(tmp)
            calls = []

            def fake_urlopen(request, timeout=20):
                calls.append((request.get_method(), request.full_url))
                return self.Response({"private": False, "default_branch": "main"})

            with patch.dict(
                os.environ,
                {"STORYBUILDER_TRACE_GITHUB_TOKEN": "test-token"},
                clear=True,
            ), patch("builder.prompt_trace_sync.urlopen", side_effect=fake_urlopen):
                result = upload_prompt_trace(trace_path, repository="owner/traces")

            self.assertFalse(result["ok"])
            self.assertIn("not confirmed private", result["error"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0], "GET")

    def test_upload_refuses_to_replace_unrelated_repository_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = self.make_trace_file(tmp)
            calls = []

            def fake_urlopen(request, timeout=20):
                method = request.get_method()
                url = request.full_url
                calls.append((method, url))
                if method == "GET" and url.endswith("/repos/owner/traces"):
                    return self.Response({"private": True, "default_branch": "main"})
                if method == "GET" and url.endswith("/git/ref/heads/main"):
                    return self.Response({"object": {"sha": "old-commit"}})
                if method == "GET" and url.endswith("/git/commits/old-commit"):
                    return self.Response({"tree": {"sha": "old-tree"}})
                if method == "GET" and "/git/trees/old-tree?" in url:
                    return self.Response({
                        "tree": [
                            {"path": "prompt_trace.json", "type": "blob"},
                            {"path": "README.md", "type": "blob"},
                        ]
                    })
                raise AssertionError(f"Unexpected write after safety check: {method} {url}")

            with patch.dict(
                os.environ,
                {"STORYBUILDER_TRACE_GITHUB_TOKEN": "test-token"},
                clear=True,
            ), patch("builder.prompt_trace_sync.urlopen", side_effect=fake_urlopen):
                result = upload_prompt_trace(trace_path, repository="owner/traces")

            self.assertFalse(result["ok"])
            self.assertIn("other than prompt_trace.json", result["error"])
            self.assertFalse(any(method in {"POST", "PATCH"} for method, _ in calls))

    def test_upload_reports_missing_auth_without_network_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = self.make_trace_file(tmp)
            with patch.dict(os.environ, {}, clear=True), patch(
                "builder.prompt_trace_sync.shutil.which", return_value=None
            ), patch("builder.prompt_trace_sync.urlopen") as http:
                result = upload_prompt_trace(trace_path, repository="owner/traces")

            self.assertFalse(result["ok"])
            self.assertIn("GitHub CLI", result["error"])
            http.assert_not_called()


if __name__ == "__main__":
    unittest.main()
