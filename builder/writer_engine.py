from __future__ import annotations

import os
import re
import signal
import subprocess
import threading

import pexpect
import time
from pathlib import Path

from builder.workspace import LLAMA as DEFAULT_LLAMA, MODELS_DIR


WRITER_TIMEOUT = int(os.environ.get("STORY_WRITER_TIMEOUT", "3600"))


def encode_prompt_for_cli(prompt: str) -> str:
    """Encode a possibly multiline prompt as one llama-cli input line.

    llama-cli decodes escaped input before tokenization. Escape existing
    backslashes first so literal sequences such as \\n remain literal, then
    encode actual line breaks as \\n sequences for the CLI to restore.
    """
    normalized = str(prompt).replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\\", "\\\\").replace("\n", "\\n")


class GenerationInterrupted(RuntimeError):
    """Raised when the author stops an active generation."""


class _PromptEchoStreamFilter:
    """Stream model output while removing an echoed interactive prompt."""

    def __init__(self, prompt: str, callback):
        self.prompt = str(prompt or "")
        self.callback = callback
        self.buffer = ""
        self.finished = False
        self.skip_initial_linebreaks = False
        self.candidates = tuple(
            candidate for candidate in (self.prompt, "> " + self.prompt)
            if candidate
        )

    @staticmethod
    def _consume_visible_chars(raw: str, count: int) -> str:
        """Consume count characters while ignoring terminal line-wrap newlines."""
        index = 0
        consumed = 0
        while index < len(raw) and consumed < count:
            if raw[index] not in "\r\n":
                consumed += 1
            index += 1
        return raw[index:]

    def _emit(self, value: str) -> None:
        if not value:
            return
        try:
            self.callback(value)
        except Exception:
            # UI streaming is best-effort and must never break model generation.
            pass

    def _emit_after_echo(self, value: str) -> None:
        if self.skip_initial_linebreaks:
            value = value.lstrip("\r\n")
            if not value:
                return
            self.skip_initial_linebreaks = False
        self._emit(value)

    def write(self, value) -> int:
        value = str(value or "")
        if not value:
            return 0
        if self.finished:
            self._emit_after_echo(value)
            return len(value)

        self.buffer += value
        raw = self.buffer
        trimmed = raw.lstrip("\r\n")
        normalized = trimmed.replace("\r", "").replace("\n", "")

        # The terminal may wrap a long echoed prompt. Ignore those wrap newlines
        # while matching, then remove the same prefix from the original text.
        for candidate in self.candidates:
            if normalized.startswith(candidate):
                remainder = self._consume_visible_chars(trimmed, len(candidate))
                self.buffer = ""
                self.finished = True
                self.skip_initial_linebreaks = True
                self._emit_after_echo(remainder)
                return len(value)

        # Wait while the data could still be the beginning of an echoed prompt.
        if any(candidate.startswith(normalized) for candidate in self.candidates):
            return len(value)

        # This was generated prose, not the submitted prompt. Match the old
        # response cleanup's optional "> " prefix without delaying the stream.
        self.finished = True
        self.buffer = ""
        generated = trimmed
        if generated.startswith("> "):
            generated = generated[2:]
        self.skip_initial_linebreaks = False
        self._emit(generated)
        return len(value)

    def flush(self) -> None:
        # pexpect may call flush after each read. Do not prematurely flush the
        # ambiguous prompt prefix; write() keeps accumulating it until resolved.
        return None

    def finish(self) -> None:
        """Release any remaining non-prompt text when generation exits."""
        if self.finished or not self.buffer:
            return
        raw = self.buffer
        trimmed = raw.lstrip("\r\n")
        normalized = trimmed.replace("\r", "").replace("\n", "")
        # If the remainder is only a prefix of the echoed input, don't display it
        # as though it were story prose after a failed/partial model turn.
        if any(candidate.startswith(normalized) for candidate in self.candidates):
            self.buffer = ""
            return
        if trimmed.startswith("> "):
            trimmed = trimmed[2:]
        self.buffer = ""
        self.finished = True
        self._emit(trimmed)


class WriterEngine:
    """Persistent local llama-cli session used by StoryBuilder."""

    def __init__(self) -> None:
        self.child = None
        self.lock = threading.RLock()
        self.model_path: Path | None = None
        self.system_prompt = ""
        self.started_at: float | None = None
        self.prompt_trace = None
        # These fields use a separate lock because generate() holds self.lock
        # while waiting for llama-cli. Stop must not wait for that generation lock.
        self._interrupt_lock = threading.Lock()
        self._active_generation_child = None
        self._cancel_generation_requested = False

    def _trace_record(self, method_name: str, **details):
        """Record diagnostics when armed, without letting tracing disrupt generation."""
        trace = getattr(self, "prompt_trace", None)
        if trace is None:
            return None
        try:
            return getattr(trace, method_name)(**details)
        except Exception as exc:
            try:
                trace.record_event(
                    "trace_capture_error",
                    method=method_name,
                    error=str(exc),
                )
            except Exception:
                pass
            return None

    @staticmethod
    def available_models() -> list[Path]:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        return sorted(
            MODELS_DIR.glob("*.gguf"),
            key=lambda p: p.name.casefold(),
        )

    @staticmethod
    def validate_model(path: str | Path) -> Path:
        model = Path(os.path.expanduser(str(path))).resolve()
        root = MODELS_DIR.resolve()

        try:
            model.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"The selected model must be inside {MODELS_DIR}."
            ) from exc

        if model.suffix.casefold() != ".gguf":
            raise ValueError("Selected model is not a GGUF file.")

        if not model.is_file():
            raise FileNotFoundError(f"Model not found: {model}")

        return model

    def stop(self) -> None:
        with self.lock:
            child = self.child
            self.child = None

            if child is None:
                return

            try:
                child.sendline("/exit")
            except Exception:
                pass

            try:
                child.terminate(force=False)
            except Exception:
                try:
                    child.kill(1)
                except Exception:
                    pass

    def interrupt_generation(self) -> bool:
        """Stop the active turn without waiting for generate() to release its lock.

        llama-cli is terminated to guarantee the model stops. Its in-memory
        session is lost, so the author must reload the model before writing again.
        """
        with self._interrupt_lock:
            self._cancel_generation_requested = True
            child = self._active_generation_child or self.child
            if child is None:
                return True
            if self.child is child:
                self.child = None

        try:
            child.kill(signal.SIGKILL)
        except Exception:
            try:
                child.terminate(force=True)
            except Exception:
                pass
        return True

    @staticmethod
    def detect_accelerator() -> str | None:
        """Use CPU unless acceleration is explicitly requested."""
        override = os.environ.get("STORY_LLM_DEVICE", "").strip()
        return override or None

    def start(self, model_path: str | Path, system_prompt: str) -> None:
        with self.lock:
            model = self.validate_model(model_path)
            self.stop()

            if not DEFAULT_LLAMA.is_file():
                raise FileNotFoundError(
                    f"llama-cli not found: {DEFAULT_LLAMA}"
                )

            env = os.environ.copy()
            env["LD_LIBRARY_PATH"] = str(
                DEFAULT_LLAMA.parent
            ) + (
                ":" + env["LD_LIBRARY_PATH"]
                if env.get("LD_LIBRARY_PATH")
                else ""
            )

            device = self.detect_accelerator()
            args = [
                str(DEFAULT_LLAMA),
                "-m", str(model),
            ]
            if device:
                args.extend(["--device", device, "-ngl", "all"])
            else:
                args.extend(["-ngl", "0", "--device", "none"])

            context_size = int(os.environ.get("STORY_WRITER_CONTEXT", "16384"))
            max_predict = int(os.environ.get("STORY_WRITER_MAX_TOKENS", "3000"))
            args.extend([
                "-c", str(context_size),
                "--reasoning", "off",
                "--repeat-last-n", "256",
                "--repeat-penalty", "1.08",
                "--n-predict", str(max_predict),
                "--system-prompt", system_prompt,
                "--color", "off",
                "--no-display-prompt",
                "--escape",
                "--simple-io",
            ])

            child = pexpect.spawn(
                args[0],
                args[1:],
                env=env,
                encoding="utf-8",
                timeout=180,
            )

            try:
                child.expect(r"(?m)^> ", timeout=WRITER_TIMEOUT)
                child.timeout = WRITER_TIMEOUT
            except Exception:
                output = child.before if child else ""
                try:
                    child.kill(1)
                except Exception:
                    pass
                raise RuntimeError(
                    "llama-cli did not become ready.\n"
                    + str(output)[-2000:]
                )

            self.child = child
            self.model_path = model
            self.system_prompt = system_prompt
            self.started_at = time.time()
            self._trace_record(
                "record_session",
                model_path=model,
                runtime_binary=DEFAULT_LLAMA,
                system_prompt=system_prompt,
                context_size=context_size,
                max_tokens=max_predict,
                device=device,
                runtime_options={
                    "gpu_layers": "all" if device else 0,
                    "reasoning": "off",
                    "repeat_last_n": 256,
                    "repeat_penalty": 1.08,
                    "max_generation_tokens": max_predict,
                    "temperature": "llama.cpp default (not explicitly set by WriterEngine)",
                    "top_k": "llama.cpp default (not explicitly set by WriterEngine)",
                    "top_p": "llama.cpp default (not explicitly set by WriterEngine)",
                },
            )

    def reset_context(self, model_path: str | Path, system_prompt: str) -> None:
        """Restart llama-cli with a fresh conversation context."""
        self.start(model_path, system_prompt)

    def generate(
        self,
        prompt: str,
        timeout: int | None = None,
        on_delta=None,
    ) -> str:
        """Generate one turn; optionally stream story-text deltas as they arrive."""
        with self.lock:
            with self._interrupt_lock:
                if self._cancel_generation_requested:
                    self._cancel_generation_requested = False
                    raise GenerationInterrupted("Generation stopped by the author.")
                child = self.child
                if child is None or not child.isalive():
                    raise RuntimeError(
                        "Writer is not running. Start the Writer first."
                    )
                self._active_generation_child = child

            # The interactive CLI reads one input line at a time. Encode real
            # paragraph breaks as escapes that llama-cli restores before tokenizing.
            # Doubling existing backslashes first preserves literal escape sequences.
            model_prompt = str(prompt).replace("\r\n", "\n").replace("\r", "\n")
            cli_prompt = encode_prompt_for_cli(model_prompt)
            trace_call_id = self._trace_record(
                "begin_generation",
                prompt=prompt,
                sent_prompt=model_prompt,
            )
            generation_started = time.monotonic()
            stream_filter = (
                _PromptEchoStreamFilter(cli_prompt, on_delta)
                if callable(on_delta) else None
            )
            previous_logfile_read = getattr(child, "logfile_read", None)
            turn_timeout = WRITER_TIMEOUT if timeout is None else max(1, int(timeout))
            try:
                if stream_filter is not None:
                    child.logfile_read = stream_filter
                child.sendline(cli_prompt)
                child.expect(r"(?m)^> ", timeout=turn_timeout)
            except pexpect.TIMEOUT as exc:
                output = child.before or ""
                with self._interrupt_lock:
                    interrupted = self._cancel_generation_requested
                if interrupted:
                    self._trace_record(
                        "finish_generation",
                        call_id=trace_call_id,
                        response="",
                        status="interrupted",
                        error="Stopped by the author.",
                        duration_seconds=time.monotonic() - generation_started,
                    )
                    raise GenerationInterrupted("Generation stopped by the author.") from exc
                diagnostics_match = re.search(
                    r"\[ Prompt: .*? \| Generation: .*? \]\s*$",
                    str(output),
                    flags=re.DOTALL,
                )
                self._trace_record(
                    "finish_generation",
                    call_id=trace_call_id,
                    response="",
                    status="timeout",
                    error=str(exc),
                    cli_diagnostics=diagnostics_match.group(0).strip() if diagnostics_match else None,
                    duration_seconds=time.monotonic() - generation_started,
                )
                # A timed-out task can otherwise keep consuming CPU and RAM.
                try:
                    if child is not None:
                        child.kill(1)
                except Exception:
                    pass
                if self.child is child:
                    self.child = None
                raise TimeoutError(
                    f"Local model turn timed out after {turn_timeout} seconds.\n"
                    + str(output)[-2000:]
                ) from exc
            except Exception as exc:
                output = child.before or ""
                with self._interrupt_lock:
                    interrupted = self._cancel_generation_requested
                if interrupted:
                    self._trace_record(
                        "finish_generation",
                        call_id=trace_call_id,
                        response="",
                        status="interrupted",
                        error="Stopped by the author.",
                        duration_seconds=time.monotonic() - generation_started,
                    )
                    raise GenerationInterrupted("Generation stopped by the author.") from exc
                diagnostics_match = re.search(
                    r"\[ Prompt: .*? \| Generation: .*? \]\s*$",
                    str(output),
                    flags=re.DOTALL,
                )
                self._trace_record(
                    "finish_generation",
                    call_id=trace_call_id,
                    response="",
                    status="runtime_error",
                    error=str(exc),
                    cli_diagnostics=diagnostics_match.group(0).strip() if diagnostics_match else None,
                    duration_seconds=time.monotonic() - generation_started,
                )
                raise RuntimeError(
                    "The writer failed while generating the scene.\n"
                    + str(output)[-3000:]
                ) from exc
            finally:
                if stream_filter is not None:
                    try:
                        child.logfile_read = previous_logfile_read
                    except Exception:
                        pass
                    stream_filter.finish()
                with self._interrupt_lock:
                    if self._active_generation_child is child:
                        self._active_generation_child = None
                    self._cancel_generation_requested = False

            raw_output = str(child.before or "")
            diagnostics_match = re.search(
                r"\[ Prompt: .*? \| Generation: .*? \]\s*$",
                raw_output,
                flags=re.DOTALL,
            )
            cli_diagnostics = diagnostics_match.group(0).strip() if diagnostics_match else None
            answer = raw_output
            answer = answer.replace("\r", "").strip()

            while answer.startswith("> "):
                answer = answer[2:].lstrip()

            # llama-cli may echo the submitted user turn before returning the model
            # response. Remove that echoed prompt so only prose reaches the editor.
            echoed_prompt = cli_prompt if "cli_prompt" in locals() else ""
            if echoed_prompt and answer.startswith(echoed_prompt):
                answer = answer[len(echoed_prompt):].lstrip()

            # Remove llama.cpp timing diagnostics accidentally captured with the response.
            answer = re.sub(r"\n?\[ Prompt: .*? \| Generation: .*? \]\s*$", "", answer, flags=re.DOTALL).strip()

            if not answer:
                self._trace_record(
                    "finish_generation",
                    call_id=trace_call_id,
                    response="",
                    status="empty_response",
                    error="The writer returned an empty response.",
                    cli_diagnostics=cli_diagnostics,
                    duration_seconds=time.monotonic() - generation_started,
                )
                raise RuntimeError("The writer returned an empty response.")

            self._trace_record(
                "finish_generation",
                call_id=trace_call_id,
                response=answer,
                status="completed",
                cli_diagnostics=cli_diagnostics,
                duration_seconds=time.monotonic() - generation_started,
            )
            return answer
