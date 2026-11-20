"""Capture the real CLI in a POSIX PTY, then rasterize its ANSI output with pyte."""

import argparse
import codecs
import fcntl
import os
import pty
import select
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path

import pyte
from PIL import Image, ImageDraw, ImageFont


def rasterize(screen):
    image = Image.new("RGB", (screen.columns * 8, screen.lines * 16), "#101014")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=12)
    names = {"default": "101014", "white": "ffffff", "black": "000000"}
    for row in range(screen.lines):
        for col in range(screen.columns):
            cell = screen.buffer[row][col]
            fg = names.get(cell.fg, cell.fg)
            bg = names.get(cell.bg, cell.bg)
            fg = "#" + fg if len(fg) == 6 else fg
            bg = "#" + bg if len(bg) == 6 else bg
            x, y = col * 8, row * 16
            draw.rectangle((x, y, x + 7, y + 15), fill=bg)
            if cell.data == "▀":
                draw.rectangle((x, y, x + 7, y + 7), fill=fg)
            elif cell.data.strip():
                draw.text((x, y), cell.data, fill=fg, font=font)
    return image


def capture(video, output, mode, audio=False):
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
    command = [
        sys.executable,
        "-m",
        "hitorigotsu",
        "--file",
        str(video),
        "--mode",
        mode,
        "--duration",
        "6",
        "--benchmark-output",
        f"benchmarks/pty-{mode}.json",
    ]
    if not audio:
        command.append("--mute")
    process = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave)
    screen = pyte.Screen(100, 30)
    stream = pyte.Stream(screen)
    decoder = codecs.getincrementaldecoder("utf-8")()
    images, buffer, count = [], "", 0
    deadline = time.monotonic() + 30
    try:
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                buffer += decoder.decode(os.read(master, 65536))
                while "\x1b[H" in buffer:
                    frame, buffer = buffer.split("\x1b[H", 1)
                    stream.feed(frame)
                    if count > 1 and count % 3 == 0:
                        images.append(rasterize(screen))
                    stream.feed("\x1b[H")
                    count += 1
            elif process.poll() is not None:
                break
        if process.poll() is None:
            raise RuntimeError("Capture timed out")
        if process.returncode:
            raise RuntimeError(f"Playback failed: {buffer[-2000:]}")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
        os.close(slave)
    if not images:
        raise RuntimeError("No frames captured")
    images[len(images) // 2].save(output.with_suffix(".png"))
    images[0].save(
        output.with_suffix(".gif"), save_all=True, append_images=images[1:], duration=125, loop=0
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mode", choices=["block", "ascii"], default="block")
    parser.add_argument("--audio", action="store_true")
    args = parser.parse_args()
    capture(args.video, args.output, args.mode, args.audio)
