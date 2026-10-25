from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any


def default_prompt_trace_path() -> Path:
    """Return the single local prompt trace destination."""
    return Path.home() / ".local" / "share" / "storybuilder" / "prompt_trace.json"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_prompt_trace_enabled_path() -> Path:
    """Return the local, non-repository preference path for trace capture."""
    config_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
    root = Path(config_home).expanduser() if config_home else Path.home() / ".config"
    return root / "storybuilder" / "prompt_trace_enabled.json"


def load_prompt_trace_enabled(path: str | Path | None = None) -> bool:
    """Load the persistent trace switch; new installs default to enabled.

    A malformed existing setting fails closed so a damaged preference does not
    unexpectedly resume capturing unpublished story text.
    """
    target = Path(path).expanduser() if path is not None else default_prompt_trace_enabled_path()
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return True
    except OSError:
        return False
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return False
    enabled = payload.get("enabled") if isinstance(payload, dict) else None
    return enabled if isinstance(enabled, bool) else False


def save_prompt_trace_enabled(enabled: bool, path: str | Path | None = None) -> Path:
    """Persist the user's explicit On/Off choice outside the story repositories."""
    target = Path(path).expanduser() if path is not None else default_prompt_trace_enabled_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    try:
        temporary.write_text(
            json.dumps({"enabled": bool(enabled)}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return target


def _json_copy(value: Any) -> Any:
    """Copy JSON-compatible scene data without retaining mutable app objects."""
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _prompt_id(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


class PromptTrace:
    """One-scene, in-memory trace that overwrites one local JSON file on finish."""

    def __init__(
        self,
        *,
        chapter: int,
        scene: int,
        model_path: str | Path | None,
        current_state: dict[str, Any],
        reference_files: list[tuple[str, str]],
        contract: dict[str, Any] | None,
        scene_direction: str,
        author_guidance: str,
        system_prompt: str,
        path: str | Path | None = None,
    ) -> None:
        self.path = Path(path).expanduser() if path is not None else default_prompt_trace_path()
        self.primary_system_prompt = str(system_prompt or "")
        self.primary_system_prompt_id = _prompt_id(self.primary_system_prompt)
        self._started_monotonic = time.monotonic()
        self._call_number = 0
        self._session_number = 0
        self._current_session_id: str | None = None
        self.save_error: str | None = None

        references = []
        for name, content in reference_files:
            text_content = str(content)
            references.append({
                "name": str(name),
                "characters": len(text_content),
                "sha256": hashlib.sha256(text_content.encode("utf-8")).hexdigest(),
            })

        self.data: dict[str, Any] = {
            "format": "storybuilder-prompt-trace",
            "format_version": 1,
            "created_at": _timestamp(),
            "finished_at": None,
            "status": "capturing",
            "trace_file": str(self.path),
            "retention_policy": "This file is overwritten by the next completed one-scene capture.",
            "model_requested": str(model_path) if model_path is not None else None,
            "scene": {"chapter": int(chapter), "scene": int(scene)},
            "inputs": {
                "starting_state": _json_copy(current_state),
                "scene_direction": str(scene_direction or ""),
                "author_guidance": str(author_guidance or ""),
                "contract": _json_copy(contract or {}),
                "reference_files": references,
            },
            "system_prompts": {},
            "sessions": [],
            "generation_calls": [],
            "workflow_events": [],
            "final_error": None,
            "validation_warning": None,
            "trace_save_error": None,
        }
        self._store_system_prompt(
            self.primary_system_prompt,
            self._classify_system_prompt(self.primary_system_prompt, True),
        )

    @staticmethod
    def _classify_system_prompt(prompt: str, is_primary: bool) -> str:
        first_line = prompt.strip().splitlines()[0] if prompt.strip() else ""
        if first_line.startswith("You determine only the actual ending state"):
            return "state_ending_analysis"
        if first_line.startswith("You extract only concrete new evidence and events"):
            return "state_evidence_analysis"
        if first_line.startswith("You are a delta auditor for character knowledge"):
            return "state_knowledge_audit"
        if is_primary:
            return "scene_writer"
        if first_line.startswith("Review original idea/state"):
            return "scene_validator"
        if first_line.startswith("Create a compact, gentle guide"):
            return "scene_contract_builder"
        if first_line.startswith("You write natural prose"):
            return "scene_writer"
        return "auxiliary_model_task"

    def _store_system_prompt(self, prompt: str, role: str) -> str:
        prompt_id = _prompt_id(prompt)
        if prompt_id not in self.data["system_prompts"]:
            self.data["system_prompts"][prompt_id] = {
                "sha256": prompt_id,
                "role": role,
                "characters": len(prompt),
                "content": prompt,
            }
        return prompt_id

    def record_session(
        self,
        *,
        model_path: str | Path,
        runtime_binary: str | Path,
        system_prompt: str,
        context_size: int,
        max_tokens: int,
        device: str | None,
        runtime_options: dict[str, Any],
    ) -> str:
        prompt = str(system_prompt or "")
        role = self._classify_system_prompt(
            prompt, _prompt_id(prompt) == self.primary_system_prompt_id
        )
        prompt_id = self._store_system_prompt(prompt, role)
        self._session_number += 1
        session_id = f"session_{self._session_number:02d}"
        self._current_session_id = session_id
        self.data["sessions"].append({
            "session_id": session_id,
            "role": role,
            "started_at": _timestamp(),
            "model_path": str(model_path),
            "runtime_binary": str(runtime_binary),
            "system_prompt_id": prompt_id,
            "context_size_tokens": int(context_size),
            "max_generation_tokens": int(max_tokens),
            "requested_device": str(device or "CPU/default"),
            "runtime_options": _json_copy(runtime_options),
        })
        return session_id

    def begin_generation(self, *, prompt: str, sent_prompt: str) -> str:
        self._call_number += 1
        call_id = f"call_{self._call_number:02d}"
        self.data["generation_calls"].append({
            "call_id": call_id,
            "session_id": self._current_session_id,
            "role": (
                self.data["sessions"][-1]["role"]
                if self.data["sessions"]
                else "unknown_session"
            ),
            "started_at": _timestamp(),
            "input_before_runtime_normalization": str(prompt),
            "exact_user_text_sent_to_runtime": str(sent_prompt),
            "input_characters_before_normalization": len(str(prompt)),
            "input_characters_sent": len(str(sent_prompt)),
            "input_lines_before_normalization": len(str(prompt).splitlines()),
            "response": None,
            "cli_diagnostics": None,
            "duration_seconds": None,
            "status": "in_progress",
            "error": None,
            "_started_monotonic": time.monotonic(),
        })
        return call_id

    def finish_generation(
        self,
        *,
        call_id: str | None,
        response: str = "",
        status: str = "completed",
        cli_diagnostics: str | None = None,
        duration_seconds: float | None = None,
        error: str | None = None,
    ) -> None:
        if call_id is None:
            return
        call = next(
            (item for item in reversed(self.data["generation_calls"]) if item["call_id"] == call_id),
            None,
        )
        if call is None:
            return
        started = call.pop("_started_monotonic", None)
        if duration_seconds is None and started is not None:
            duration_seconds = max(0.0, time.monotonic() - started)
        call.update({
            "response": str(response or ""),
            "cli_diagnostics": cli_diagnostics,
            "duration_seconds": round(float(duration_seconds), 3) if duration_seconds is not None else None,
            "status": str(status),
            "error": str(error) if error else None,
            "finished_at": _timestamp(),
        })

    def record_event(self, event_type: str, **details: Any) -> None:
        self.data["workflow_events"].append({
            "timestamp": _timestamp(),
            "event": str(event_type),
            "details": _json_copy(details),
        })

    def finish(
        self,
        *,
        status: str,
        error: str | None = None,
        validation_warning: str | None = None,
    ) -> Path | None:
        self.data["finished_at"] = _timestamp()
        self.data["status"] = str(status)
        self.data["final_error"] = str(error) if error else None
        self.data["validation_warning"] = str(validation_warning) if validation_warning else None
        for call in self.data["generation_calls"]:
            call.pop("_started_monotonic", None)
            if call.get("status") == "in_progress":
                call["status"] = "capture_ended_before_response"
        self.data["capture_duration_seconds"] = round(
            max(0.0, time.monotonic() - self._started_monotonic), 3
        )
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Intentionally overwrite the same file. No rotating logs or backups.
            self.path.write_text(
                json.dumps(self.data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            self.save_error = str(exc)
            self.data["trace_save_error"] = self.save_error
            return None
        return self.path
