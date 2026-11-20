"""Small, atomic user configuration; no unverified official URL is shipped."""

import json
import os
import tempfile
from pathlib import Path

from platformdirs import user_config_path


def config_path() -> Path:
    return user_config_path("hitorigotsu-cli") / "config.json"


def load_default() -> str | None:
    path = config_path()
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text()).get("default_source")
        if value is not None and not isinstance(value, str):
            raise ValueError("default_source must be a string")
        return value
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid configuration {path}: {exc}") from exc


def save_default(source: str) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump({"default_source": source}, stream)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)
