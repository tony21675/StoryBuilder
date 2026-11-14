from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from builder.writer_engine import GenerationInterrupted, WriterEngine


OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_CHAT_URL = f"{OPENROUTER_API_BASE}/chat/completions"
OPENROUTER_MODELS_URL = f"{OPENROUTER_API_BASE}/models"
OPENROUTER_SELECTION_PREFIX = "openrouter:"
OPENROUTER_AUTO_MODEL = "openrouter/free"
DEFAULT_REMOTE_MAX_TOKENS = 4096


def is_openrouter_selection(value: object) -> bool:
    return isinstance(value, str) and value.startswith(OPENROUTER_SELECTION_PREFIX)


def openrouter_model_selection(model_id: str) -> str:
    model_id = str(model_id or "").strip()
    if not model_id or "\n" in model_id or "\r" in model_id:
        raise ValueError("Choose a valid OpenRouter model ID.")
    return OPENROUTER_SELECTION_PREFIX + model_id


def selected_openrouter_model_id(selection: str) -> str:
    if not is_openrouter_selection(selection):
        raise ValueError("The selected model is not an OpenRouter model.")
    model_id = selection[len(OPENROUTER_SELECTION_PREFIX):].strip()
    if not model_id:
        raise ValueError("The selected OpenRouter model ID is empty.")
    return model_id


def openrouter_config_dir() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
    return config_home / "storybuilder"


def openrouter_api_key_path() -> Path:
    explicit = os.environ.get("STORYBUILDER_OPENROUTER_KEY_FILE", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return openrouter_config_dir() / "openrouter_api_key"


def openrouter_models_cache_path() -> Path:
    return openrouter_config_dir() / "openrouter_models.json"


def load_openrouter_api_key() -> str:
    """Read the API key from the environment first, then the private user config file."""
    environment_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if environment_key:
        return environment_key
    try:
        return openrouter_api_key_path().read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""


def has_openrouter_api_key() -> bool:
    return bool(load_openrouter_api_key())


def save_openrouter_api_key(api_key: str, path: str | Path | None = None) -> Path:
    """Save a key outside the repository with owner-only directory and file permissions."""
    key = str(api_key or "").strip()
    if not key or "\n" in key or "\r" in key:
        raise ValueError("Enter a valid OpenRouter API key.")
    target = Path(path).expanduser() if path is not None else openrouter_api_key_path()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        target.parent.chmod(0o700)
    except OSError:
        pass
    temporary = target.with_name(target.name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(key + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, target)
        target.chmod(0o600)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
    return target


def delete_openrouter_api_key(path: str | Path | None = None) -> None:
    target = Path(path).expanduser() if path is not None else openrouter_api_key_path()
    try:
        target.unlink()
    except FileNotFoundError:
        pass


def _normalise_free_models(items: object) -> list[dict[str, str]]:
    models: dict[str, dict[str, str]] = {}
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id") or "").strip()
            # Keep the stable, explicitly free variants. Other zero-priced
            # catalogue entries can require a funded account.
            if not model_id.endswith(":free"):
                continue
            name = str(item.get("name") or model_id).strip()
            models[model_id] = {"id": model_id, "name": name}
    models[OPENROUTER_AUTO_MODEL] = {
        "id": OPENROUTER_AUTO_MODEL,
        "name": "Automatic free-model router",
    }
    return sorted(
        models.values(),
        key=lambda item: (
            item["id"] == OPENROUTER_AUTO_MODEL,
            item["name"].casefold(),
            item["id"].casefold(),
        ),
    )


def fetch_openrouter_free_models(
    api_key: str | None = None, *, timeout: int = 30
) -> list[dict[str, str]]:
    """Fetch the current :free chat model catalogue from OpenRouter."""
    key = str(api_key or load_openrouter_api_key()).strip()
    if not key:
        raise RuntimeError(
            "OpenRouter is not configured. Add an API key in OpenRouter Settings."
        )
    request = urllib.request.Request(
        OPENROUTER_MODELS_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "StoryBuilder/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=max(1, int(timeout))) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            body = json.loads(exc.read().decode("utf-8"))
            detail = str((body.get("error") or {}).get("message") or "")
        except Exception:
            pass
        message = f"OpenRouter model-list request failed (HTTP {exc.code})."
        if detail:
            message += f"\n{detail}"
        raise RuntimeError(message) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach OpenRouter: {exc.reason}") from exc
    except (UnicodeError, ValueError) as exc:
        raise RuntimeError("OpenRouter returned an unreadable model catalogue.") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise RuntimeError("OpenRouter returned an unexpected model-catalogue response.")
    return _normalise_free_models(payload["data"])


def load_cached_openrouter_models(
    path: str | Path | None = None,
) -> list[dict[str, str]]:
    target = Path(path).expanduser() if path is not None else openrouter_models_cache_path()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError):
        return _normalise_free_models([])
    items = payload.get("models") if isinstance(payload, dict) else None
    return _normalise_free_models(items)


def save_cached_openrouter_models(
    models: list[dict[str, str]], path: str | Path | None = None
) -> Path:
    target = Path(path).expanduser() if path is not None else openrouter_models_cache_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    normalised = _normalise_free_models(models)
    temporary = target.with_name(target.name + ".tmp")
    try:
        temporary.write_text(
            json.dumps({"models": normalised}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
    return target


class _RemoteSessionMarker:
    """Small compatibility marker for the Writer UI's existing runtime indicator."""

    def __init__(self, engine: "OpenRouterEngine") -> None:
        self.engine = engine

    def isalive(self) -> bool:
        return self.engine.model_id is not None


class OpenRouterEngine:
    """Stateless, streaming OpenRouter chat-completions backend."""

    def __init__(self) -> None:
        self.model_id: str | None = None
        self.system_prompt = ""
        self.started_at: float | None = None
        self.prompt_trace = None
        self._lock = threading.RLock()
        self._interrupt_lock = threading.Lock()
        self._active_response = None
        self._cancel_generation_requested = False
        self._session_marker = _RemoteSessionMarker(self)

    @property
    def child(self):
        return self._session_marker if self.model_id is not None else None

    def _trace_record(self, method_name: str, **details):
        trace = self.prompt_trace
        if trace is None:
            return None
        try:
            return getattr(trace, method_name)(**details)
        except Exception:
            return None

    def attach_prompt_trace(self, trace, *, role: str = "scene_writer") -> None:
        with self._lock:
            self.prompt_trace = trace
            if self.model_id is None:
                return
            try:
                trace.record_session(
                    model_path=f"openrouter:{self.model_id}",
                    runtime_binary=OPENROUTER_CHAT_URL,
                    system_prompt=self.system_prompt,
                    context_size=0,
                    max_tokens=int(os.environ.get(
                        "STORY_OPENROUTER_MAX_TOKENS", str(DEFAULT_REMOTE_MAX_TOKENS)
                    )),
                    device="Remote provider",
                    runtime_options={
                        "backend": "OpenRouter",
                        "model_id": self.model_id,
                        "streaming": True,
                        "conversation_state": "stateless; each request contains only its supplied prompt",
                    },
                    role=role,
                )
            except Exception:
                pass

    def detach_prompt_trace(self, trace) -> None:
        with self._lock:
            if self.prompt_trace is trace:
                self.prompt_trace = None

    def start(self, model_id: str, system_prompt: str = "") -> None:
        selected = str(model_id or "").strip()
        if not selected or "\n" in selected or "\r" in selected:
            raise ValueError("Choose a valid OpenRouter model ID.")
        if not load_openrouter_api_key():
            raise RuntimeError(
                "No OpenRouter API key is saved. Open OpenRouter Settings and add your key."
            )
        with self._lock:
            self.stop()
            self.model_id = selected
            self.system_prompt = str(system_prompt or "")
            self.started_at = time.time()
            with self._interrupt_lock:
                self._cancel_generation_requested = False

    def clear_context(self, timeout: int = 30) -> None:
        """Remote calls are stateless; there is no retained chat history to clear."""
        del timeout
        if self.model_id is None:
            raise RuntimeError("OpenRouter is not selected. Load a remote model first.")

    def interrupt_generation(self) -> bool:
        """Cancel a streaming response without waiting for the generation lock."""
        with self._interrupt_lock:
            self._cancel_generation_requested = True
            response = self._active_response
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
        return True

    def stop(self) -> None:
        with self._interrupt_lock:
            self._cancel_generation_requested = True
            response = self._active_response
            self._active_response = None
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
        with self._lock:
            self.model_id = None
            self.system_prompt = ""
            self.started_at = None
            self.prompt_trace = None
            with self._interrupt_lock:
                self._cancel_generation_requested = False

    @staticmethod
    def _response_error(payload: object) -> str:
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                return str(error.get("message") or error.get("code") or "Unknown provider error")
            if error:
                return str(error)
        return "OpenRouter returned a provider error."

    def generate(self, prompt: str, timeout: int | None = None, on_delta=None) -> str:
        with self._lock:
            model_id = self.model_id
            if not model_id:
                raise RuntimeError("OpenRouter is not loaded. Select and load a remote model first.")
            with self._interrupt_lock:
                if self._cancel_generation_requested:
                    self._cancel_generation_requested = False
                    raise GenerationInterrupted("Generation stopped by the author.")

            api_key = load_openrouter_api_key()
            if not api_key:
                raise RuntimeError(
                    "The OpenRouter API key is missing. Add it again in OpenRouter Settings."
                )

            max_tokens = max(
                1,
                int(os.environ.get(
                    "STORY_OPENROUTER_MAX_TOKENS", str(DEFAULT_REMOTE_MAX_TOKENS)
                )),
            )
            messages = []
            if self.system_prompt.strip():
                messages.append({"role": "system", "content": self.system_prompt})
            messages.append({"role": "user", "content": str(prompt)})
            request_body = {
                "model": model_id,
                "messages": messages,
                "stream": True,
                "max_tokens": max_tokens,
            }
            request = urllib.request.Request(
                OPENROUTER_CHAT_URL,
                data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                    "User-Agent": "StoryBuilder/1.0",
                    "X-Title": "StoryBuilder",
                },
                method="POST",
            )
            call_id = self._trace_record(
                "begin_generation",
                prompt=prompt,
                sent_prompt=str(prompt),
            )
            started = time.monotonic()
            answer_parts: list[str] = []
            status = "completed"
            error_message = None
            response = None
            try:
                request_timeout = (
                    int(timeout) if timeout is not None
                    else int(os.environ.get("STORY_OPENROUTER_TIMEOUT", "300"))
                )
                response = urllib.request.urlopen(
                    request, timeout=max(1, request_timeout)
                )
                with self._interrupt_lock:
                    self._active_response = response
                    interrupted = self._cancel_generation_requested
                if interrupted:
                    raise GenerationInterrupted("Generation stopped by the author.")

                for raw_line in response:
                    with self._interrupt_lock:
                        if self._cancel_generation_requested:
                            raise GenerationInterrupted("Generation stopped by the author.")
                    try:
                        line = raw_line.decode("utf-8").strip()
                    except AttributeError:
                        line = str(raw_line).strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        if data == "[DONE]":
                            break
                        continue
                    try:
                        chunk = json.loads(data)
                    except ValueError:
                        continue
                    if chunk.get("error"):
                        raise RuntimeError(self._response_error(chunk))
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    choice = choices[0] if isinstance(choices[0], dict) else {}
                    if choice.get("finish_reason") == "error":
                        raise RuntimeError(self._response_error(chunk))
                    delta = choice.get("delta") or {}
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        answer_parts.append(content)
                        if callable(on_delta):
                            try:
                                on_delta(content)
                            except Exception:
                                pass

                answer = "".join(answer_parts)
                if not answer.strip():
                    raise RuntimeError(
                        "OpenRouter returned no text. The selected model may be unavailable "
                        "or may have returned only non-text output."
                    )
                return answer
            except GenerationInterrupted:
                status = "interrupted"
                error_message = "Stopped by the author."
                raise
            except urllib.error.HTTPError as exc:
                status = "failed"
                detail = ""
                try:
                    payload = json.loads(exc.read().decode("utf-8"))
                    detail = self._response_error(payload)
                except Exception:
                    pass
                error_message = f"OpenRouter request failed (HTTP {exc.code})."
                if detail:
                    error_message += f"\n{detail}"
                raise RuntimeError(error_message) from exc
            except urllib.error.URLError as exc:
                with self._interrupt_lock:
                    interrupted = self._cancel_generation_requested
                if interrupted:
                    status = "interrupted"
                    error_message = "Stopped by the author."
                    raise GenerationInterrupted(error_message) from exc
                status = "failed"
                error_message = f"Could not reach OpenRouter: {exc.reason}"
                raise RuntimeError(error_message) from exc
            except Exception as exc:
                with self._interrupt_lock:
                    interrupted = self._cancel_generation_requested
                if interrupted:
                    status = "interrupted"
                    error_message = "Stopped by the author."
                    raise GenerationInterrupted(error_message) from exc
                status = "failed"
                error_message = str(exc)
                raise
            finally:
                if response is not None:
                    try:
                        response.close()
                    except Exception:
                        pass
                with self._interrupt_lock:
                    if self._active_response is response:
                        self._active_response = None
                    if status == "interrupted":
                        self._cancel_generation_requested = False
                self._trace_record(
                    "finish_generation",
                    call_id=call_id,
                    response="".join(answer_parts),
                    status=status,
                    error=error_message,
                    duration_seconds=time.monotonic() - started,
                )


class RoutedWriterEngine:
    """Keep local llama.cpp and OpenRouter behind one compatible Writer interface."""

    def __init__(
        self,
        local_engine: WriterEngine | None = None,
        remote_engine: OpenRouterEngine | None = None,
    ) -> None:
        self.local_engine = local_engine or WriterEngine()
        self.remote_engine = remote_engine or OpenRouterEngine()
        self.active_backend: str | None = None
        self.active_selection: str | Path | None = None

    @property
    def child(self):
        if self.active_backend == "openrouter":
            return self.remote_engine.child
        if self.active_backend == "local":
            return self.local_engine.child
        return None

    @property
    def model_path(self):
        if self.active_backend == "local":
            return self.local_engine.model_path
        return None

    @property
    def system_prompt(self) -> str:
        if self.active_backend == "openrouter":
            return self.remote_engine.system_prompt
        if self.active_backend == "local":
            return self.local_engine.system_prompt
        return ""

    @property
    def started_at(self):
        if self.active_backend == "openrouter":
            return self.remote_engine.started_at
        if self.active_backend == "local":
            return self.local_engine.started_at
        return None

    def start(self, model_selection: str | Path, system_prompt: str = "") -> None:
        if is_openrouter_selection(model_selection):
            model_id = selected_openrouter_model_id(str(model_selection))
            self.local_engine.stop()
            self.remote_engine.start(model_id, system_prompt=system_prompt)
            self.active_backend = "openrouter"
        else:
            self.remote_engine.stop()
            self.local_engine.start(model_selection, system_prompt=system_prompt)
            self.active_backend = "local"
        self.active_selection = model_selection

    def generate(self, prompt: str, timeout: int | None = None, on_delta=None) -> str:
        if self.active_backend == "openrouter":
            return self.remote_engine.generate(prompt, timeout=timeout, on_delta=on_delta)
        if self.active_backend == "local":
            return self.local_engine.generate(prompt, timeout=timeout, on_delta=on_delta)
        raise RuntimeError("No model is loaded. Select and load a Planner or Writer model first.")

    def clear_context(self, timeout: int = 30) -> None:
        if self.active_backend == "openrouter":
            self.remote_engine.clear_context(timeout=timeout)
        elif self.active_backend == "local":
            self.local_engine.clear_context(timeout=timeout)
        else:
            raise RuntimeError("No model is loaded.")

    def interrupt_generation(self) -> bool:
        if self.active_backend == "openrouter":
            return self.remote_engine.interrupt_generation()
        if self.active_backend == "local":
            return self.local_engine.interrupt_generation()
        return True

    def stop(self) -> None:
        try:
            self.remote_engine.stop()
        finally:
            self.local_engine.stop()
            self.active_backend = None
            self.active_selection = None

    def reset_context(self, model_selection: str | Path, system_prompt: str) -> None:
        self.start(model_selection, system_prompt)

    def attach_prompt_trace(self, trace, *, role: str = "scene_writer") -> None:
        if self.active_backend == "openrouter":
            self.remote_engine.attach_prompt_trace(trace, role=role)
        elif self.active_backend == "local":
            self.local_engine.attach_prompt_trace(trace, role=role)

    def detach_prompt_trace(self, trace) -> None:
        self.local_engine.detach_prompt_trace(trace)
        self.remote_engine.detach_prompt_trace(trace)
