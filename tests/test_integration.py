import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hitorigotsu.cli import parser
from hitorigotsu.decoder import Decoder, probe
from hitorigotsu.player import Player

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg unavailable")
    path = tmp_path_factory.mktemp("media") / "test.mp4"
    script = Path(__file__).parents[1] / "examples/generate_test_video.py"
    spec = importlib.util.spec_from_file_location("generate", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.generate(path, seconds=2)
    return path


def test_decoder_seek_bounded_and_close(video):
    media = probe(video)
    assert media.audio and 1.9 <= media.duration <= 2.1
    decoder = Decoder(video, media, 24, 1)
    try:
        first = decoder.frames.get(timeout=5)
        assert first[0] == 1
        assert first[1].shape == (180, 320, 3)
        assert decoder.frames.maxsize == 4
    finally:
        decoder.close()
    assert not decoder.thread.is_alive()
    assert decoder.process.poll() is not None


def test_headless_and_controls(video):
    options = parser().parse_args(["--mute", "--headless", "--benchmark", "--duration", "1"])
    player = Player(video, options)
    report = player.run()
    assert report["frames"] >= 5
    assert report["av_drift_mean_ms"] is None
    assert report["peak_sampled_rss_mib"] > 0
    try:
        player.restart(0)
        player.control(" ")
        assert player.paused
        position = player.position()
        assert player.position() == position
        player.control("r")
        assert player.position() == 0
        player.control("right")
        assert player.position() <= player.media.duration
        player.control(" ")
        assert not player.paused
        assert player.control("q") is False
    finally:
        player.close_audio()
        player.decoder.close()


def test_slow_render_drops_frames(video, monkeypatch):
    import time

    import hitorigotsu.player as module

    original = module.render

    def slow(*args):
        time.sleep(0.09)
        return original(*args)

    monkeypatch.setattr(module, "render", slow)
    report = Player(video, parser().parse_args(["--mute", "--headless"])).run()
    assert report["dropped_frames"] > 0
    assert report["elapsed_s"] < 4


@pytest.mark.skipif(os.name == "nt", reason="POSIX PTY integration test")
@pytest.mark.parametrize("exit_key", [b"q", b"\x03"])
def test_terminal_restored_on_quit(video, exit_key):
    import fcntl
    import pty
    import select
    import struct
    import termios
    import time

    master, slave = pty.openpty()
    original = termios.tcgetattr(slave)
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
    proc = subprocess.Popen(
        [sys.executable, "-m", "hitorigotsu", "--file", str(video), "--mute", "--loop"],
        stdin=slave,
        stdout=slave,
        stderr=slave,
    )
    data = b""
    try:
        deadline = time.monotonic() + 10
        while b"\xe2\x96\x80" not in data and time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                data += os.read(master, 65536)
        # Exercise dynamic resize before exiting, including raw Ctrl+C input.
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 16, 60, 0, 0))
        if exit_key == b"\x03":
            # This PTY has no controlling foreground process group; deliver SIGINT explicitly.
            import signal

            proc.send_signal(signal.SIGINT)
        else:
            os.write(master, exit_key)
        while proc.poll() is None and time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                data += os.read(master, 65536)
        proc.wait(timeout=2)
        while select.select([master], [], [], 0)[0]:
            data += os.read(master, 65536)
        assert proc.returncode == (130 if exit_key == b"\x03" else 0)
        assert b"\x1b[?1049h" in data and b"\x1b[?1049l" in data
        assert b"\x1b[?25h" in data
        restored = termios.tcgetattr(slave)
        # macOS sets the transient PENDIN (retype pending input) flag on tcsetattr.
        restored[3] &= ~getattr(termios, "PENDIN", 0)
        original[3] &= ~getattr(termios, "PENDIN", 0)
        assert restored == original
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        os.close(master)
        os.close(slave)


@pytest.mark.network
@pytest.mark.skipif(not os.getenv("HITORIGOTSU_E2E_URL"), reason="opt-in authorized YouTube URL")
def test_youtube_e2e(tmp_path, monkeypatch):
    import hitorigotsu.cache as cache_module
    from hitorigotsu.cache import Cache
    from hitorigotsu.downloader import download
    from hitorigotsu.source import resolve_source, video_id

    url = os.environ["HITORIGOTSU_E2E_URL"]
    cache = Cache(tmp_path)
    monkeypatch.setattr(cache_module, "user_cache_path", lambda _: tmp_path)
    path = download(url, cache)
    assert cache.get(video_id(url)) == path
    assert resolve_source(url, offline=True) == path
    # Audio output is intentional here; requires a real device.
    result = Player(path, parser().parse_args(["--headless", "--duration", "3"])).run()
    assert result["frames"] > 0
    assert result["av_drift_mean_ms"] is not None
    (tmp_path / "e2e.json").write_text(json.dumps(result))


@pytest.mark.skipif(not os.getenv("HITORIGOTSU_AUDIO_TEST"), reason="opt-in real audio device")
def test_real_audio_controls(video):
    import time

    from hitorigotsu.audio import Audio

    player = Player(video, parser().parse_args(["--headless"]))
    try:
        player.restart(0)
        assert isinstance(player.audio, Audio)
        time.sleep(0.3)
        assert player.position() > 0.05
        player.control(" ")
        frozen = player.position()
        time.sleep(0.1)
        assert player.position() == frozen and player.audio is None
        player.control("left")
        assert player.position() == 0
        player.control(" ")
        assert player.audio is not None
        player.control("m")
        assert player.audio.muted
        player.control("m")
        assert not player.audio.muted
        player.control("r")
        assert player.position() < 0.2
        process = player.audio.process
        thread = player.audio.thread
    finally:
        player.close_audio()
        if player.decoder:
            player.decoder.close()
    assert process.poll() is not None and not thread.is_alive()
