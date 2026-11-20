"""Strict YouTube URLs and local files; never pass arbitrary URLs to FFmpeg."""

import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def video_id(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"} or parsed.username or parsed.password:
        raise ValueError("Expected an http(s) YouTube URL")
    host = parsed.netloc.lower()
    parts = parsed.path.strip("/").split("/")
    if host in {"youtu.be", "www.youtu.be"} and len(parts) == 1:
        key = parts[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        if parsed.path == "/watch":
            key = parse_qs(parsed.query).get("v", [""])[0]
        elif len(parts) == 2 and parts[0] in {"shorts", "embed", "live"}:
            key = parts[1]
        else:
            key = ""
    else:
        key = ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", key):
        raise ValueError("Invalid YouTube video URL (expected one 11-character video ID)")
    return key


def resolve_source(value: str | None, *, offline=False, force=False) -> Path:
    from .cache import Cache
    from .config import load_default
    from .downloader import download

    value = value or load_default()
    if value is None:
        local = Path("hitorigotsu.mp4")
        if local.is_file():
            return local.resolve()
        raise ValueError("No source configured. Use --file PATH or --set-default YOUTUBE_URL.")
    if "://" not in value:
        path = Path(value).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"Video file not found: {path}")
        return path
    key = video_id(value)
    cache = Cache()
    cached = cache.get(key)
    if cached is not None and not force:
        return cached
    if offline:
        raise ValueError(
            "No valid cached video for this source. Download it before using --offline."
        )
    return download(value, cache)
