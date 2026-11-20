"""Audio-clock scheduling, bounded decode pipeline and user controls."""

import queue
import time

import psutil

from .audio import Audio
from .controls import Controls
from .decoder import Decoder, probe
from .renderer import fit_size, render
from .synchronizer import Clock
from .terminal import Terminal


class Player:
    def __init__(self, path, options):
        self.path, self.options = path, options
        self.media = probe(path)
        self.decoder = self.audio = None
        self.clock = Clock()
        self.paused = False
        self.muted = options.mute
        self.pending = None
        self.frames = self.dropped = self.audio_frames = 0
        self.processing = self.rendering = self.drift_total = self.drift_max = 0.0
        self.underruns = 0

    def position(self):
        return self.audio.position() if self.audio else self.clock.position()

    def close_audio(self):
        if self.audio:
            self.underruns += self.audio.underruns
            self.audio.close()
            self.audio = None

    def restart(self, position):
        self.close_audio()
        if self.decoder:
            self.decoder.close()
        position = max(
            0.0, min(position, max(0, self.media.duration - max(0.05, 1 / self.options.fps)))
        )
        self.decoder = Decoder(self.path, self.media, self.options.fps, position)
        try:
            self.pending = self.decoder.frames.get(timeout=10)
        except queue.Empty as exc:
            raise ValueError("Video decoder startup timed out") from exc
        if self.pending is None:
            raise ValueError("No decodable frames at this position")
        self.clock = Clock(position)
        self.clock.paused = self.paused
        if self.media.audio and not self.muted and not self.paused:
            self.audio = Audio(self.path, position, self.media.duration)

    def control(self, key):
        if key in {"q", "\x03"}:
            return False
        if key == " ":
            position = self.position()
            self.paused = not self.paused
            self.restart(position)
        elif key == "m":
            position = self.position()
            self.muted = not self.muted
            if self.audio:
                self.audio.muted = self.muted
            elif not self.muted and self.media.audio and not self.paused:
                self.restart(position)
        elif key == "r":
            self.restart(0)
        elif key in {"left", "right", "up", "down"}:
            self.restart(self.position() + {"left": -5, "right": 5, "up": 30, "down": -30}[key])
        return True

    def run(self):
        process = psutil.Process()
        cpu_start = sum(process.cpu_times()[:2])
        started = time.monotonic()
        peak_rss = process.memory_info().rss
        controls = Controls()
        try:
            with Terminal(self.options.headless) as terminal:
                self.restart(0)
                startup_s = time.monotonic() - started
                started = time.monotonic()
                cpu_start = sum(process.cpu_times()[:2])
                while True:
                    if any(not self.control(key) for key in controls.poll()):
                        break
                    elapsed = time.monotonic() - started
                    if self.options.duration and elapsed >= self.options.duration:
                        break
                    peak_rss = max(peak_rss, process.memory_info().rss)
                    if self.paused:
                        time.sleep(0.01)
                        continue
                    if self.decoder.error:
                        raise self.decoder.error
                    if self.audio and self.audio.error:
                        raise ValueError(self.audio.error)
                    if self.pending is None:
                        try:
                            self.pending = self.decoder.frames.get(timeout=0.01)
                        except queue.Empty:
                            continue
                        if self.pending is None:
                            if self.options.loop:
                                self.restart(0)
                                continue
                            break
                    pts, frame = self.pending
                    now = self.position()
                    if pts > now:
                        time.sleep(min(0.01, pts - now))
                        continue
                    if now - pts >= 1 / self.options.fps:
                        self.dropped += 1
                        self.pending = None
                        continue
                    columns, rows = terminal.size()
                    cols, lines = fit_size(
                        self.media.width,
                        self.media.height,
                        columns,
                        rows,
                        self.options.width,
                        self.options.cell_aspect,
                    )
                    before = time.perf_counter()
                    text = render(frame, cols, lines, self.options.mode, self.options.monochrome)
                    converted = time.perf_counter()
                    terminal.draw(text)
                    rendered = time.perf_counter()
                    self.processing += converted - before
                    self.rendering += rendered - converted
                    drift = abs(self.position() - pts)
                    if self.audio:
                        self.drift_total += drift
                        self.audio_frames += 1
                    self.drift_max = max(self.drift_max, drift)
                    self.frames += 1
                    self.pending = None
        finally:
            elapsed = time.monotonic() - started
            cpu_used = sum(process.cpu_times()[:2]) - cpu_start
            self.close_audio()
            if self.decoder:
                self.decoder.close()
        return {
            "elapsed_s": elapsed,
            "startup_s": startup_s,
            "frames": self.frames,
            "actual_fps": self.frames / elapsed,
            "processing_mean_ms": self.processing * 1000 / max(1, self.frames),
            "rendering_mean_ms": self.rendering * 1000 / max(1, self.frames),
            "dropped_frames": self.dropped,
            "av_drift_mean_ms": self.drift_total * 1000 / self.audio_frames
            if self.audio_frames
            else None,
            "video_clock_error_max_ms": self.drift_max * 1000,
            "cpu_percent": cpu_used / elapsed * 100,
            "peak_sampled_rss_mib": peak_rss / 1024**2,
            "audio_underruns": self.underruns,
            "headless": self.options.headless,
            "note": (
                "CPU/RSS: Python process only. Drift: frame PTS vs DAC clock, not acoustic latency."
            ),
        }
