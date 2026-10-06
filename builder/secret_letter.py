from pathlib import Path
import base64
import json
import subprocess
import zlib

_PASSPHRASE = "9bc89b6e6180ac8e537bdd44ccb80072b5fe68521303ce8d8b28fa33f279a38c"
_SECRET_RELATIVE_PATH = Path("secrets") / "sarah_letter.enc.b64"


class SarahLetterSealed(Exception):
    """Raised when the Sarah letter is requested before its reveal point."""


def is_sarah_letter_revealed(current_state: dict) -> bool:
    reveals = current_state.get("secret_reveals", {})
    return isinstance(reveals, dict) and reveals.get("sarah_letter") == "revealed"


def load_sarah_letter(novel_root: Path, current_state: dict) -> str:
    """Return Sarah's letter only after the story explicitly unlocks it.

    The plaintext is decrypted in memory and is never written to disk.
    """
    if not is_sarah_letter_revealed(current_state):
        raise SarahLetterSealed("Sarah's letter is still sealed.")

    sealed_path = Path(novel_root) / _SECRET_RELATIVE_PATH
    if not sealed_path.exists():
        raise FileNotFoundError(f"Sealed letter asset not found: {sealed_path}")

    encoded = sealed_path.read_text(encoding="ascii").strip()
    encrypted = base64.b64decode(encoded)

    try:
        decrypted = subprocess.run(
            [
                "openssl",
                "enc",
                "-d",
                "-aes-256-cbc",
                "-pbkdf2",
                "-iter",
                "200000",
                "-pass",
                f"pass:{_PASSPHRASE}",
            ],
            input=encrypted,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=10,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("Unable to open the sealed Sarah letter.") from exc

    try:
        return zlib.decompress(decrypted).decode("utf-8")
    except (zlib.error, UnicodeDecodeError) as exc:
        raise RuntimeError("The sealed Sarah letter is corrupted or invalid.") from exc


def sealed_letter_status() -> dict:
    return {
        "id": "sarah_letter",
        "status": "sealed",
        "reveal_condition": "current_state.secret_reveals.sarah_letter == 'revealed'",
    }
