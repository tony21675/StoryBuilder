from __future__ import annotations

import os
import re
import subprocess
import threading

import pexpect
import time
from pathlib import Path

from builder.workspace import LLAMA as DEFAULT_LLAMA, MODELS_DIR


WRITER_TIMEOUT = int(os.environ.get("STORY_WRITER_TIMEOUT", "3600"))


class WriterEngine:
    """Persistent local llama-cli session used by StoryBuilder."""

    def __init__(self) -> None:
        self.child = None
        self.lock = threading.RLock()
        self.model_path: Path | None = None
        self.system_prompt = ""
        self.started_at: float | None = None

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

    @staticmethod
    def detect_accelerator() -> str | None:
        """Return the first non-CPU llama.cpp device, unless overridden."""
        override = os.environ.get("STORY_LLM_DEVICE", "").strip()
        if override:
            return override

        try:
            result = subprocess.run(
                [str(DEFAULT_LLAMA), "--list-devices"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None

        if result.returncode != 0:
            return None

        for line in result.stdout.splitlines():
            match = re.match(r"^\\s*([A-Za-z]+\\d+):\\s+(.+)$", line)
            if not match:
                continue
            device = match.group(1)
            label = match.group(2).casefold()
            if "cpu" not in device.casefold() and "cpu" not in label:
                return device

        return None

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

            args.extend([
                "-c", "12288",
                "--reasoning", "off",
                "--repeat-last-n", "256",
                "--repeat-penalty", "1.08",
                "--n-predict", "2000",
                "--system-prompt", system_prompt,
                "--color", "off",
                "--no-display-prompt",
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

    def generate(self, prompt: str) -> str:
        with self.lock:
            if self.child is None or not self.child.isalive():
                raise RuntimeError(
                    "Writer is not running. Start the Writer first."
                )

            # llama-cli's interactive input is line-oriented. Collapse the
            # multi-line author direction into one user turn so embedded newlines
            # are not interpreted as additional commands or prompts.
            single_line_prompt = " ".join(
                line.strip() for line in prompt.replace("\r", "").split("\n") if line.strip()
            )
            self.child.sendline(single_line_prompt)

            try:
                self.child.expect(r"(?m)^> ", timeout=WRITER_TIMEOUT)
            except Exception:
                output = self.child.before or ""
                raise RuntimeError(
                    "The writer failed while generating the scene.\n"
                    + str(output)[-3000:]
                )

            answer = str(self.child.before or "")
            answer = answer.replace("\r", "").strip()

            while answer.startswith("> "):
                answer = answer[2:].lstrip()

            # llama-cli may echo the submitted user turn before returning the model
            # response. Remove that echoed prompt so only prose reaches the editor.
            echoed_prompt = single_line_prompt if "single_line_prompt" in locals() else ""
            if echoed_prompt and answer.startswith(echoed_prompt):
                answer = answer[len(echoed_prompt):].lstrip()

            # Remove llama.cpp timing diagnostics accidentally captured with the response.
            answer = re.sub(r"\\n?\\[ Prompt: [^\\n\\]]+ \\| Generation: [^\\n\\]]+ \\]\\s*$", "", answer).strip()

            if not answer:
                raise RuntimeError("The writer returned an empty response.")

            return answer
