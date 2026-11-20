"""Streaming PCM with PortAudio's DAC time as master clock (no FFplay startup guess)."""

import queue
import subprocess
import threading
import time

RATE = 48000
BLOCK = 1024
CHANNELS = 2


class Audio:
    def __init__(self, path, start, duration):
        import sounddevice as sd

        self.start = start
        self.samples = 0
        self.anchor = None
        self.muted = False
        self.underruns = 0
        self.error = None
        self.blocks = queue.Queue(maxsize=16)
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.stream = None
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
                "0:a:0",
                "-vn",
                "-af",
                "apad",
                "-t",
                str(max(0.01, duration - start)),
                "-ar",
                str(RATE),
                "-ac",
                str(CHANNELS),
                "-f",
                "s16le",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()
        try:
            if not self.ready.wait(10) or self.error:
                raise ValueError(self.error or "Audio decoder startup timed out")
            self.stream = sd.RawOutputStream(
                samplerate=RATE,
                blocksize=BLOCK,
                channels=CHANNELS,
                dtype="int16",
                callback=self._callback,
            )
            self.stream.start()
        except sd.PortAudioError as exc:
            self.close()
            raise ValueError(f"Audio device unavailable: {exc}. Try --mute.") from exc
        except BaseException:
            self.close()
            raise

    def _read(self):
        try:
            while not self.stop.is_set():
                data = self.process.stdout.read(BLOCK * CHANNELS * 2)
                if not data:
                    if self.process.wait() != 0:
                        self.error = "FFmpeg audio decoding failed"
                    break
                data = data.ljust(BLOCK * CHANNELS * 2, b"\0")
                while not self.stop.is_set():
                    try:
                        self.blocks.put(data, timeout=0.05)
                        if self.blocks.qsize() >= 4:
                            self.ready.set()
                        break
                    except queue.Full:
                        pass
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.ready.set()

    def _callback(self, outdata, frames, timing, status):
        if status.output_underflow:
            self.underruns += 1
        try:
            data = self.blocks.get_nowait()
        except queue.Empty:
            outdata[:] = b"\0" * len(outdata)
            self.underruns += 1
            return
        outdata[:] = b"\0" * len(outdata) if self.muted else data
        # One tuple assignment gives the reader a consistent sample/DAC-time snapshot.
        self.anchor = (
            self.start + self.samples / RATE,
            timing.outputBufferDacTime,
            frames / RATE,
            time.monotonic(),
        )
        self.samples += frames

    def position(self):
        anchor = self.anchor
        if anchor is None:
            return self.start
        position, dac_time, length, updated = anchor
        if time.monotonic() - updated > 3:
            raise ValueError(self.error or "Audio output stalled; check the output device")
        return max(self.start, position + min(length, self.stream.time - dac_time))

    def close(self):
        self.stop.set()
        if self.stream is not None:
            self.stream.abort()
            self.stream.close()
            self.stream = None
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.thread.join(timeout=3)
        self.process.stdout.close()
