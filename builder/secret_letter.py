from __future__ import annotations

import base64
import os
import subprocess
import zlib
from pathlib import Path


class SarahLetterSealed(Exception):
    """Raised when the Sarah letter is requested before its reveal point."""


def is_sarah_letter_revealed(current_state: dict) -> bool:
    reveals = current_state.get("secret_reveals", {})
    return isinstance(reveals, dict) and reveals.get("sarah_letter") == "revealed"


def load_sarah_letter(novel_root: Path, current_state: dict) -> str:
    """Return Sarah's letter only after the story explicitly unlocks it.

    The plaintext is decrypted only in memory and is never written to disk.
    The decryption passphrase is supplied externally through the environment.
    """
    if not is_sarah_letter_revealed(current_state):
        raise SarahLetterSealed("Sarah's letter is still sealed.")

    passphrase = os.environ.get("SARAH_LETTER_PASSPHRASE")
    if not passphrase:
        raise RuntimeError("Sarah's letter passphrase is not configured.")

    sealed_path = Path(novel_root) / "secrets" / "sarah_letter.enc.b64"
    if not sealed_path.exists():
        raise FileNotFoundError(f"Sealed letter asset not found: {sealed_path}")

    encoded = sealed_path.read_text(encoding="ascii").strip()
    encrypted = base64.b64decode(encoded)

    try:
        return subprocess.run(
            [
                "openssl",
                "enc",
                "-d",
                "-aes-256-cbc",
                "-pbkdf2",
                "-iter",
                "200000",
                "-pass",
                f"pass:{passphrase}",
            ],
            input=encrypted,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=10,
        ).stdout.decode("utf-8")
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired, UnicodeDecodeError) as exc:
        raise RuntimeError("Unable to open the sealed Sarah letter.") from exc


def sealed_letter_status() -> dict:
    return {
        "id": "sarah_letter",
        "status": "sealed",
        "reveal_condition": "current_state.secret_reveals.sarah_letter == 'revealed'",
        "passphrase_source": "environment variable SARAH_LETTER_PASSPHRASE",
    }
