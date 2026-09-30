from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from builder.workspace import LLAMA as DEFAULT_LLAMA, MODELS_DIR


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

            args = [
                str(DEFAULT_LLAMA),
                "-m", str(model),
                "-ngl", "0",
                "--device", "none",
                "-c", "12288",
                "--reasoning", "off",
                "--repeat-last-n", "256",
                "--repeat-penalty", "1.08",
                "--n-predict", "2000",
                "--system-prompt", system_prompt,
                "--color", "off",
                "--no-display-prompt",
                "--simple-io",
            ]

            child = pexpect.spawn(
                args[0],
                args[1:],
                env=env,
                encoding="utf-8",
                timeout=180,
            )

            try:
                child.expect_exact("> ", timeout=180)
                child.timeout = 900
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

            self.child.sendline(prompt)

            try:
                self.child.expect_exact("> ", timeout=900)
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

            if not answer:
                raise RuntimeError("The writer returned an empty response.")

            return answer
