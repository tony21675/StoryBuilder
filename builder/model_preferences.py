"""Persist separate local-model choices for scene planning and manuscript writing."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable


def model_roles_config_path() -> Path:
    """Return the user-local config path, outside the StoryBuilder repository."""
    explicit = os.environ.get("STORYBUILDER_MODEL_ROLES_FILE", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
    return config_home / "storybuilder" / "model_roles.json"


def default_model_roles(model_names: Iterable[str]) -> dict[str, str]:
    """Choose sensible role defaults when the preferred model files are available."""
    names = sorted(
        (str(name).strip() for name in model_names if str(name).strip()),
        key=str.casefold,
    )
    if not names:
        return {"planner": "", "writer": ""}
    planner = next(
        (name for name in names if "qwen3.5-4b" in name.casefold()), names[0]
    )
    writer = next(
        (name for name in names if "gemma-4-e4b" in name.casefold()),
        next((name for name in names if "gemma-4" in name.casefold()), names[0]),
    )
    return {"planner": planner, "writer": writer}


def load_model_roles(path: str | Path | None = None) -> dict[str, str]:
    """Read saved role names; malformed or missing settings return an empty mapping."""
    config_path = Path(path).expanduser() if path is not None else model_roles_config_path()
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        role: value.strip()
        for role in ("planner", "writer")
        if isinstance((value := data.get(role)), str) and value.strip()
    }


def resolve_model_roles(
    available_model_names: Iterable[str],
    saved_roles: dict[str, str] | None = None,
) -> dict[str, str]:
    """Keep saved selections that exist and fill missing roles from filename defaults."""
    names = {
        str(name).strip() for name in available_model_names if str(name).strip()
    }
    defaults = default_model_roles(names)
    saved = saved_roles if isinstance(saved_roles, dict) else {}
    return {
        role: (
            saved.get(role, "")
            if isinstance(saved.get(role), str) and saved.get(role) in names
            else defaults[role]
        )
        for role in ("planner", "writer")
    }


def save_model_roles(
    *,
    planner: str,
    writer: str,
    path: str | Path | None = None,
) -> Path:
    """Atomically save the chosen model filenames in the user's config directory."""
    config_path = Path(path).expanduser() if path is not None else model_roles_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = config_path.with_name(config_path.name + ".tmp")
    payload = {
        "planner": str(planner or "").strip(),
        "writer": str(writer or "").strip(),
    }
    try:
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_path, config_path)
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
    return config_path
