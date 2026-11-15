import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from builder.openrouter import (
    OPENROUTER_AUTO_MODEL,
    OPENROUTER_CHAT_URL,
    OpenRouterEngine,
    RoutedWriterEngine,
    _normalise_free_models,
    fetch_openrouter_free_models,
    is_openrouter_selection,
    load_cached_openrouter_models,
    load_openrouter_api_key,
    openrouter_model_selection,
    save_cached_openrouter_models,
    save_openrouter_api_key,
    selected_openrouter_model_id,
)
from builder.writer_engine import GenerationInterrupted


class FakeResponse:
    def __init__(self, lines, headers=None):
        self.lines = list(lines)
        self.headers = headers or {}
        self.closed = False

    def __iter__(self):
        return iter(self.lines)

    def close(self):
        self.closed = True


class OpenRouterSelectionTests(unittest.TestCase):
    def test_selection_round_trip(self):
        selection = openrouter_model_selection("provider/model:free")
        self.assertTrue(is_openrouter_selection(selection))
        self.assertEqual(
            selected_openrouter_model_id(selection), "provider/model:free"
        )

    def test_invalid_selections_are_rejected(self):
        for model_id in ("", "model\nname", "model\rname"):
            with self.subTest(model_id=model_id):
                with self.assertRaises(ValueError):
                    openrouter_model_selection(model_id)
        with self.assertRaises(ValueError):
            selected_openrouter_model_id("local.gguf")

    def test_catalogue_keeps_pinned_free_variants_and_automatic_router(self):
        models = _normalise_free_models(
            [
                {"id": "vendor/paid-model", "name": "Paid"},
                {"id": "vendor/free-model:free", "name": "Free"},
                {"id": "vendor/another-free:free"},
                "invalid",
            ]
        )
        ids = {item["id"] for item in models}
        self.assertEqual(
            ids,
            {
                "vendor/free-model:free",
                "vendor/another-free:free",
                OPENROUTER_AUTO_MODEL,
            },
        )
        self.assertEqual(
            next(item for item in models if item["id"] == OPENROUTER_AUTO_MODEL)["name"],
            "Automatic free-model router",
        )

    def test_api_key_is_saved_with_owner_only_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "storybuilder" / "api_key"
            saved = save_openrouter_api_key("sk-or-test-value", path)
            self.assertEqual(saved.read_text(encoding="utf-8").strip(), "sk-or-test-value")
            self.assertEqual(stat.S_IMODE(saved.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(saved.parent.stat().st_mode), 0o700)

    def test_api_key_loader_prefers_environment_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "key"
            save_openrouter_api_key("file-key", path)
            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "environment-key"}):
                with patch("builder.openrouter.openrouter_api_key_path", return_value=path):
                    self.assertEqual(load_openrouter_api_key(), "environment-key")

    def test_catalogue_is_cached_outside_the_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "openrouter_models.json"
            save_cached_openrouter_models(
                [{"id": "vendor/model:free", "name": "Model"}], path
            )
            loaded = load_cached_openrouter_models(path)
            self.assertIn(
                {"id": "vendor/model:free", "name": "Model"}, loaded
            )
            self.assertIn(
                {"id": OPENROUTER_AUTO_MODEL, "name": "Automatic free-model router"},
                loaded,
            )


class OpenRouterCatalogueRequestTests(unittest.TestCase):
    def test_catalogue_fetch_uses_bearer_auth_and_returns_free_models(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(
                    {
                        "data": [
                            {"id": "vendor/model:free", "name": "Free model"},
                            {"id": "vendor/paid", "name": "Paid model"},
                        ]
                    }
                ).encode("utf-8")

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = request.header_items()
            captured["timeout"] = timeout
            return Response()

        with patch("builder.openrouter.urllib.request.urlopen", side_effect=fake_urlopen):
            models = fetch_openrouter_free_models("test-key")

        self.assertEqual(captured["url"], "https://openrouter.ai/api/v1/models")
        headers = {key.lower(): value for key, value in captured["headers"]}
        self.assertEqual(headers["authorization"], "Bearer test-key")
        self.assertEqual(captured["timeout"], 30)
        self.assertEqual(
            [item["id"] for item in models if item["id"].endswith(":free")],
            ["vendor/model:free"],
        )


class OpenRouterEngineTests(unittest.TestCase):
    def test_start_requires_an_api_key(self):
        engine = OpenRouterEngine()
        with patch("builder.openrouter.load_openrouter_api_key", return_value=""):
            with self.assertRaisesRegex(RuntimeError, "API key"):
                engine.start("vendor/model:free")

    def test_streaming_generation_sends_only_supplied_prompt(self):
        engine = OpenRouterEngine()
        with patch("builder.openrouter.load_openrouter_api_key", return_value="test-key"):
            engine.start("vendor/model:free")

        pieces = []
        response = FakeResponse(
            [
                b'data: {"choices":[{"delta":{"content":"The first "}}]}\n',
                b'data: {"choices":[{"delta":{"content":"paragraph."}}]}\n',
                b"data: [DONE]\n",
            ]
        )
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["headers"] = {
                key.lower(): value for key, value in request.header_items()
            }
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return response

        with patch("builder.openrouter.load_openrouter_api_key", return_value="test-key"):
            with patch("builder.openrouter.urllib.request.urlopen", side_effect=fake_urlopen):
                answer = engine.generate("Write only this scene.", on_delta=pieces.append)

        self.assertEqual(answer, "The first paragraph.")
        self.assertEqual("".join(pieces), answer)
        self.assertEqual(captured["url"], OPENROUTER_CHAT_URL)
        self.assertEqual(captured["body"]["model"], "vendor/model:free")
        self.assertNotIn("reasoning", captured["body"])
        self.assertTrue(captured["body"]["stream"])
        self.assertEqual(
            captured["body"]["messages"],
            [{"role": "user", "content": "Write only this scene."}],
        )
        self.assertEqual(captured["headers"]["authorization"], "Bearer test-key")
        self.assertTrue(response.closed)

    def test_ling_32_flash_disables_thinking_for_scene_text_generation(self):
        engine = OpenRouterEngine()
        with patch("builder.openrouter.load_openrouter_api_key", return_value="test-key"):
            engine.start("inclusionai/ling-3.2-flash:free")

        response = FakeResponse([
            b'data: {"choices":[{"delta":{"content":"The scene begins."},"finish_reason":null}]}\\n',
            b'data: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"completion_tokens":4}}\\n',
            b"data: [DONE]\\n",
        ])
        captured = {}

        def fake_urlopen(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return response

        with patch("builder.openrouter.load_openrouter_api_key", return_value="test-key"):
            with patch("builder.openrouter.urllib.request.urlopen", side_effect=fake_urlopen):
                answer = engine.generate("Write the scene.")

        self.assertEqual(answer, "The scene begins.")
        self.assertEqual(captured["body"]["reasoning"], {"enabled": False})
        self.assertTrue(response.closed)

    def test_empty_reasoning_only_stream_records_finish_and_usage_diagnostics(self):
        engine = OpenRouterEngine()
        with patch("builder.openrouter.load_openrouter_api_key", return_value="test-key"):
            engine.start("inclusionai/ling-3.2-flash:free")

        class FakeTrace:
            def __init__(self):
                self.finished = None

            def record_session(self, **_details):
                pass

            def begin_generation(self, **_details):
                return "call_01"

            def finish_generation(self, **details):
                self.finished = details

        trace = FakeTrace()
        engine.attach_prompt_trace(trace)
        response = FakeResponse([
            b'data: {"choices":[{"delta":{"reasoning":"thinking without final text"}}]}\\n',
            b'data: {"choices":[{"delta":{},"finish_reason":"length","native_finish_reason":"length"}],"usage":{"completion_tokens":4096,"completion_tokens_details":{"reasoning_tokens":4096}}}\\n',
            b"data: [DONE]\\n",
        ], headers={"X-Generation-Id": "gen-test-123"})

        with patch("builder.openrouter.load_openrouter_api_key", return_value="test-key"):
            with patch("builder.openrouter.urllib.request.urlopen", return_value=response):
                with self.assertRaisesRegex(RuntimeError, "output-token limit while generating reasoning"):
                    engine.generate("Write the scene.")

        self.assertTrue(response.closed)
        metadata = trace.finished["response_metadata"]
        self.assertEqual(metadata["generation_id"], "gen-test-123")
        self.assertEqual(metadata["finish_reason"], "length")
        self.assertEqual(metadata["native_finish_reason"], "length")
        self.assertEqual(metadata["reasoning_delta_chunks"], 1)
        self.assertGreater(metadata["reasoning_characters_observed"], 0)
        self.assertEqual(metadata["usage"]["completion_tokens"], 4096)
        self.assertEqual(metadata["usage"]["completion_tokens_details"]["reasoning_tokens"], 4096)

    def test_system_prompt_is_forwarded_when_provided(self):
        engine = OpenRouterEngine()
        with patch("builder.openrouter.load_openrouter_api_key", return_value="test-key"):
            engine.start("vendor/model:free", system_prompt="Write natural prose.")

        response = FakeResponse(
            [
                b'data: {"choices":[{"delta":{"content":"Done."}}]}\n',
                b"data: [DONE]\n",
            ]
        )
        captured = {}

        def fake_urlopen(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return response

        with patch("builder.openrouter.load_openrouter_api_key", return_value="test-key"):
            with patch("builder.openrouter.urllib.request.urlopen", side_effect=fake_urlopen):
                engine.generate("Write the scene.")

        self.assertEqual(
            captured["body"]["messages"],
            [
                {"role": "system", "content": "Write natural prose."},
                {"role": "user", "content": "Write the scene."},
            ],
        )

    def test_remote_new_session_does_not_need_a_server_side_clear(self):
        engine = OpenRouterEngine()
        with patch("builder.openrouter.load_openrouter_api_key", return_value="test-key"):
            engine.start("vendor/model:free")
            engine.clear_context()
        self.assertEqual(engine.model_id, "vendor/model:free")

    def test_cancel_requested_before_network_call_raises_generation_interrupted(self):
        engine = OpenRouterEngine()
        with patch("builder.openrouter.load_openrouter_api_key", return_value="test-key"):
            engine.start("vendor/model:free")
        engine.interrupt_generation()
        with self.assertRaises(GenerationInterrupted):
            engine.generate("Write the scene.")
        self.assertFalse(engine._cancel_generation_requested)

    def test_stream_cancellation_is_reported_as_generation_interrupted(self):
        engine = OpenRouterEngine()
        with patch("builder.openrouter.load_openrouter_api_key", return_value="test-key"):
            engine.start("vendor/model:free")

        class InterruptingResponse(FakeResponse):
            def __iter__(self):
                engine._cancel_generation_requested = True
                raise OSError("response closed")

        response = InterruptingResponse([])
        with patch("builder.openrouter.load_openrouter_api_key", return_value="test-key"):
            with patch(
                "builder.openrouter.urllib.request.urlopen", return_value=response
            ):
                with self.assertRaises(GenerationInterrupted):
                    engine.generate("Write the scene.")
        self.assertTrue(response.closed)
        self.assertFalse(engine._cancel_generation_requested)


class RoutedWriterEngineTests(unittest.TestCase):
    class LocalEngine:
        def __init__(self):
            self.child = None
            self.started = []
            self.generated = []
            self.cleared = 0
            self.stopped = 0

        def start(self, model, system_prompt=""):
            self.started.append((model, system_prompt))
            self.child = object()

        def generate(self, prompt, timeout=None, on_delta=None):
            self.generated.append(prompt)
            if on_delta:
                on_delta("local")
            return "local"

        def clear_context(self, timeout=30):
            self.cleared += 1

        def stop(self):
            self.stopped += 1
            self.child = None

        def interrupt_generation(self):
            return True

        @property
        def model_path(self):
            return self.started[-1][0] if self.started else None

        @property
        def system_prompt(self):
            return self.started[-1][1] if self.started else ""

        @property
        def started_at(self):
            return 1

        def attach_prompt_trace(self, *_args, **_kwargs):
            pass

        def detach_prompt_trace(self, *_args):
            pass

    class RemoteEngine:
        def __init__(self):
            self.model_id = None
            self.child = None
            self.started = []
            self.generated = []
            self.cleared = 0
            self.stopped = 0

        def start(self, model, system_prompt=""):
            self.started.append((model, system_prompt))
            self.model_id = model
            self.child = object()

        def generate(self, prompt, timeout=None, on_delta=None):
            self.generated.append(prompt)
            if on_delta:
                on_delta("remote")
            return "remote"

        def clear_context(self, timeout=30):
            self.cleared += 1

        def stop(self):
            self.stopped += 1
            self.model_id = None
            self.child = None

        def interrupt_generation(self):
            return True

        @property
        def system_prompt(self):
            return self.started[-1][1] if self.started else ""

        @property
        def started_at(self):
            return 2

        def attach_prompt_trace(self, *_args, **_kwargs):
            pass

        def detach_prompt_trace(self, *_args):
            pass

    def test_switches_between_remote_and_local_without_replacing_local_backend(self):
        local = self.LocalEngine()
        remote = self.RemoteEngine()
        engine = RoutedWriterEngine(local, remote)

        engine.start("openrouter:vendor/model:free")
        self.assertEqual(engine.active_backend, "openrouter")
        self.assertEqual(remote.started, [("vendor/model:free", "")])
        self.assertEqual(local.stopped, 1)
        self.assertEqual(engine.generate("Remote prompt."), "remote")
        engine.clear_context()
        self.assertEqual(remote.cleared, 1)

        engine.start(Path("/models/local.gguf"))
        self.assertEqual(engine.active_backend, "local")
        self.assertEqual(local.started, [(Path("/models/local.gguf"), "")])
        self.assertEqual(remote.stopped, 1)
        self.assertEqual(engine.generate("Local prompt."), "local")
        engine.stop()
        self.assertIsNone(engine.active_backend)
        self.assertEqual(local.stopped, 2)
        self.assertEqual(remote.stopped, 2)


if __name__ == "__main__":
    unittest.main()
