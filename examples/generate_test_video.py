"""Generate original geometric animation + tone; no copyrighted media needed."""

import argparse
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np


def generate(destination: Path, seconds=6):
    with tempfile.TemporaryDirectory() as directory:
        silent = Path(directory) / "silent.avi"
        writer = cv2.VideoWriter(str(silent), cv2.VideoWriter_fourcc(*"MJPG"), 24, (320, 180))
        if not writer.isOpened():
            raise RuntimeError("OpenCV MJPEG writer unavailable")
        for index in range(round(seconds * 24)):
            frame = np.full((180, 320, 3), (45, 28, 18), np.uint8)
            x = 45 + int(225 * (0.5 + 0.5 * np.sin(index / 24 * 2)))
            cv2.circle(frame, (x, 85), 30, (240, 195, 110), -1)
            cv2.rectangle(frame, (20, 130), (300, 151), (245, 245, 245), -1)
            cv2.rectangle(
                frame, (20, 130), (20 + int(280 * index / (seconds * 24)), 151), (130, 220, 160), -1
            )
            cv2.putText(
                frame,
                "HITORIGOTSU CLI",
                (28, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            writer.write(frame)
        writer.release()
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(silent),
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=440:duration={seconds}",
                "-c:v",
                "mpeg4",
                "-q:v",
                "3",
                "-c:a",
                "aac",
                "-shortest",
                str(destination),
            ],
            check=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--seconds", type=float, default=6)
    args = parser.parse_args()
    generate(args.output, args.seconds)
