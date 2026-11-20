"""yt-dlp Python API, bounded resolution and atomic completion manifests."""

import json
import shutil
import sys
import tempfile
from pathlib import Path

from .cache import Cache, digest
from .source import video_id


def require_ffmpeg() -> None:
    missing = [tool for tool in ("ffmpeg", "ffprobe") if not shutil.which(tool)]
    if missing:
        raise ValueError(f"Missing {', '.join(missing)}. Install FFmpeg and add it to PATH.")


def download(url: str, cache: Cache) -> Path:
    require_ffmpeg()
    import yt_dlp

    key = video_id(url)
    cache.root.mkdir(parents=True, exist_ok=True)

    def progress(status):
        if status["status"] == "downloading":
            done = status.get("downloaded_bytes", 0)
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            label = f"{done / total:.0%}" if total else f"{done // 1024} KiB"
            print(f"\rDownloading {key}: {label}   ", end="", file=sys.stderr, flush=True)
        elif status["status"] == "finished":
            print("\nDownload complete; merging and validating…", file=sys.stderr)

    with tempfile.TemporaryDirectory(prefix="staging-", dir=cache.root) as temporary:
        stage = Path(temporary)
        options = {
            "format": "bv[height<=480]+ba/b[height<=480]",
            "outtmpl": str(stage / "media.%(ext)s"),
            "merge_output_format": "mkv",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": False,
            "progress_hooks": [progress],
            "js_runtimes": {"deno": {}, "node": {}},
            "socket_timeout": 20,
            "retries": 2,
            "postprocessors": [{"key": "FFmpegVideoRemuxer", "preferedformat": "mkv"}],
        }
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={key}", download=True)
        except yt_dlp.utils.DownloadError as exc:
            raise ValueError(
                f"YouTube download failed: {exc}\nCheck access/network and update yt-dlp "
                "(uv tool upgrade hitorigotsu-cli). Restricted/DRM sources are unsupported."
            ) from exc
        media = stage / "media.mkv"
        if not media.is_file():
            raise ValueError("yt-dlp produced no merged media; check FFmpeg/yt-dlp compatibility")
        from .decoder import probe

        probe(media)
        metadata = {
            "id": key,
            "title": info.get("title", key),
            "size": media.stat().st_size,
            "sha256": digest(media),
        }
        (stage / "complete.json").write_text(json.dumps(metadata))
        target = cache.directory(key)
        # Publish media first, manifest last. A mismatched pair is never a valid cache hit.
        target.mkdir(exist_ok=True)
        (target / "complete.json").unlink(missing_ok=True)
        media.replace(target / "media.mkv")
        (stage / "complete.json").replace(target / "complete.json")
    return target / "media.mkv"
