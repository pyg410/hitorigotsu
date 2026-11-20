"""FFmpeg normalizes PTS/VFR to requested FPS; one worker feeds a bounded queue."""

import json
import math
import queue
import subprocess
import threading
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import numpy as np

from .downloader import require_ffmpeg


@dataclass
class Media:
    width: int
    height: int
    duration: float
    audio: bool
    video_stream: int = 0


def probe(path: Path) -> Media:
    require_ffmpeg()
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True,
        timeout=30,
    )
    if result.returncode:
        raise ValueError("Unreadable media: " + result.stderr.decode(errors="replace")[-1000:])
    data = json.loads(result.stdout)
    videos = [
        s
        for s in data["streams"]
        if s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic")
    ]
    if not videos:
        raise ValueError("Source contains no video stream")
    video = videos[0]
    duration = float(video.get("duration") or data.get("format", {}).get("duration") or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("A finite, seekable video duration is required")
    # Decode capped square pixels: bounded memory even for local 4K input.
    width, height = int(video["width"]), int(video["height"])
    try:
        sar = float(Fraction(video.get("sample_aspect_ratio", "1:1").replace(":", "/")))
    except (ValueError, ZeroDivisionError):
        sar = 1.0
    width *= sar if sar > 0 else 1.0
    rotation = next(
        (side.get("rotation", 0) for side in video.get("side_data_list", []) if "rotation" in side),
        0,
    )
    if abs(rotation) % 180 == 90:
        width, height = height, width
    scale = min(1.0, 640 / max(width, height))
    return Media(
        max(2, round(width * scale)),
        max(2, round(height * scale)),
        duration,
        any(s["codec_type"] == "audio" for s in data["streams"]),
        video["index"],
    )


class Decoder:
    def __init__(self, path, media, fps, start=0.0):
        self.frames = queue.Queue(maxsize=4)
        self.stop = threading.Event()
        self.error = None
        self.process = subprocess.Popen(
            [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-ss",
                f"{start:.6f}",
                "-i",
                str(path),
                "-map",
                f"0:{media.video_stream}",
                "-an",
                "-vf",
                f"fps={fps},scale={media.width}:{media.height},setsar=1",
                "-pix_fmt",
                "bgr24",
                "-f",
                "rawvideo",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.thread = threading.Thread(target=self._read, args=(media, fps, start), daemon=True)
        self.thread.start()

    def _put(self, value):
        while not self.stop.is_set():
            try:
                self.frames.put(value, timeout=0.05)
                return
            except queue.Full:
                pass

    def _read(self, media, fps, start):
        try:
            size, index = media.width * media.height * 3, 0
            while not self.stop.is_set():
                data = self.process.stdout.read(size)
                if len(data) != size:
                    break
                frame = np.frombuffer(data, np.uint8).reshape(media.height, media.width, 3)
                self._put((start + index / fps, frame))
                index += 1
            if not self.stop.is_set() and self.process.wait() != 0:
                self.error = ValueError("FFmpeg video decoding failed")
        except Exception as exc:
            self.error = exc
        finally:
            self._put(None)

    def close(self):
        self.stop.set()
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.thread.join(timeout=3)
        self.process.stdout.close()
