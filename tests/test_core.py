import json
from types import SimpleNamespace

import numpy as np
import pytest

from hitorigotsu.cache import Cache, digest
from hitorigotsu.cli import main, parser
from hitorigotsu.controls import Controls
from hitorigotsu.renderer import fit_size, render
from hitorigotsu.source import video_id
from hitorigotsu.synchronizer import Clock


@pytest.mark.parametrize(
    "url",
    [
        "https://youtu.be/BaW_jenozKc",
        "https://youtube.com/watch?v=BaW_jenozKc",
        "https://www.youtube.com/shorts/BaW_jenozKc",
    ],
)
def test_url(url):
    assert video_id(url) == "BaW_jenozKc"


@pytest.mark.parametrize(
    "url",
    [
        "https://youtube.com.evil.test/watch?v=BaW_jenozKc",
        "file:///tmp/a",
        "https://youtu.be/../hello",
        "https://user@youtube.com/watch?v=BaW_jenozKc",
        "https://youtube.com/playlist?list=abc",
    ],
)
def test_reject_url(url):
    with pytest.raises(ValueError):
        video_id(url)


def test_geometry_and_colors():
    cols, rows = fit_size(1920, 1080, 100, 30)
    assert cols <= 99 and rows <= 29
    assert abs(cols * 0.5 / rows - 1920 / 1080) < 0.05
    assert fit_size(1920, 1080, 100, 30, width=50)[0] == 50
    pixels = np.array([[[0, 0, 255]], [[255, 0, 0]]], dtype=np.uint8)
    ansi = render(pixels, 1, 1)
    assert "38;2;255;0;0m" in ansi and "48;2;0;0;255m" in ansi and "▀" in ansi
    white = np.full((4, 4, 3), 255, np.uint8)
    assert render(white, 4, 2).count("38;2;") == 2
    assert "@@@@" in render(white, 4, 1, "ascii", True)
    assert "38;2" not in render(white, 4, 1, "ascii", True)


def test_clock_pause():
    now = [0.0]
    clock = Clock(now=lambda: now[0])
    now[0] = 3
    clock.pause(True)
    now[0] = 20
    assert clock.position() == 3
    clock.pause(False)
    now[0] = 22
    assert clock.position() == 5


def test_fragmented_keys():
    keys = Controls()
    assert keys.feed("\x1b[") == []
    assert keys.feed("C mQ") == ["right", " ", "m", "q"]


def test_cache_integrity(tmp_path):
    cache = Cache(tmp_path)
    key = "BaW_jenozKc"
    folder = cache.directory(key)
    folder.mkdir()
    media = folder / "media.mkv"
    media.write_bytes(b"fake video")
    assert cache.get(key) is None
    (folder / "complete.json").write_text(
        json.dumps({"size": media.stat().st_size, "sha256": digest(media)})
    )
    assert cache.get(key) == media
    media.write_bytes(b"bad! video")
    assert cache.get(key) is None
    cache.clear()
    assert not folder.exists()
    with pytest.raises(ValueError):
        cache.directory("../../oops")


@pytest.mark.parametrize(
    "args", [["--fps", "nan"], ["--fps", "0"], ["--width", "-1"], ["--duration", "inf"]]
)
def test_invalid_options(args):
    with pytest.raises(SystemExit):
        parser().parse_args(args)


def test_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "missing.mp4"), "--mute"]) == 1
    assert "not found" in capsys.readouterr().err


def test_audio_clock_and_mute():
    import queue

    from hitorigotsu.audio import BLOCK, CHANNELS, RATE, Audio

    audio = Audio.__new__(Audio)
    audio.blocks = queue.Queue()
    audio.blocks.put(b"\x01" * (BLOCK * CHANNELS * 2))
    audio.start, audio.samples, audio.anchor = 5, 0, None
    audio.muted, audio.underruns = True, 0
    audio.stream = SimpleNamespace(time=10.01)
    output = bytearray(BLOCK * CHANNELS * 2)
    audio._callback(
        output,
        BLOCK,
        SimpleNamespace(outputBufferDacTime=10),
        SimpleNamespace(output_underflow=False),
    )
    assert not any(output)
    assert audio.position() == pytest.approx(5.01)
    audio.stream.time = 100
    assert audio.position() == pytest.approx(5 + BLOCK / RATE)
    audio._callback(
        output,
        BLOCK,
        SimpleNamespace(outputBufferDacTime=100),
        SimpleNamespace(output_underflow=False),
    )
    assert audio.underruns == 1


def test_audio_clock_accounts_for_queued_output():
    import time

    from hitorigotsu.audio import Audio

    audio = Audio.__new__(Audio)
    audio.start = 0
    audio.anchor = (1.0, 10.0, 0.02, time.monotonic())
    audio.stream = SimpleNamespace(time=9.9)
    assert audio.position() == pytest.approx(0.9)


def test_config_roundtrip(tmp_path, monkeypatch):
    import hitorigotsu.config as config

    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "config.json")
    assert config.load_default() is None
    config.save_default("https://youtu.be/BaW_jenozKc")
    assert config.load_default() == "https://youtu.be/BaW_jenozKc"
    (tmp_path / "config.json").write_text("not-json")
    with pytest.raises(ValueError, match="Invalid configuration"):
        config.load_default()
