"""Content-verified, completed downloads only. Staging directories are never cache hits."""

import hashlib
import json
import re
import shutil
from pathlib import Path

from platformdirs import user_cache_path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Cache:
    def __init__(self, root: Path | None = None):
        self.root = root if root is not None else user_cache_path("hitorigotsu-cli")

    def directory(self, key: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", key):
            raise ValueError("Invalid cache key")
        return self.root / key

    def get(self, key: str) -> Path | None:
        folder = self.directory(key)
        try:
            metadata = json.loads((folder / "complete.json").read_text())
            media = folder / "media.mkv"
            if media.stat().st_size != metadata["size"] or digest(media) != metadata["sha256"]:
                return None
            return media
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def entries(self) -> list[tuple[str, Path | None]]:
        if not self.root.exists():
            return []
        return [
            (p.name, self.get(p.name))
            for p in sorted(self.root.iterdir())
            if p.is_dir() and re.fullmatch(r"[A-Za-z0-9_-]{11}", p.name)
        ]

    def clear(self) -> None:
        for key, _ in self.entries():
            shutil.rmtree(self.directory(key))
