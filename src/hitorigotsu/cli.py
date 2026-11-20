"""Public command-line interface."""

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

from . import __version__


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return number


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def parser():
    result = argparse.ArgumentParser(description="TrueColor terminal video with synchronized audio")
    result.add_argument("source", nargs="?", help="YouTube URL or local video")
    sources = result.add_mutually_exclusive_group()
    sources.add_argument("--file", type=Path, help="local video")
    sources.add_argument("--url", help="YouTube URL")
    result.add_argument("--fps", type=positive, default=24, help="target FPS (default: 24)")
    result.add_argument("--mode", choices=["ascii", "block"], default="block")
    result.add_argument("--width", type=positive_int, help="maximum columns")
    result.add_argument(
        "--cell-aspect",
        type=positive,
        default=0.5,
        help="terminal cell width/height (default: 0.5)",
    )
    for name, help_text in {
        "mute": "start without audio (M enables it)",
        "loop": "repeat until Q",
        "monochrome": "grayscale blocks / uncolored ASCII",
        "offline": "use cache only",
        "force-download": "replace this source's cache",
        "cache-list": "list cached videos",
        "clear-cache": "delete completed video cache",
        "benchmark": "print benchmark JSON",
        "headless": "convert frames without terminal output (for CI/benchmarking)",
    }.items():
        result.add_argument("--" + name, action="store_true", help=help_text)
    result.add_argument("--set-default", metavar="SOURCE", help="save YouTube URL or local path")
    result.add_argument("--duration", type=positive, help="stop after this many wall-clock seconds")
    result.add_argument("--benchmark-output", type=Path, help="write benchmark JSON to a file")
    result.add_argument("--version", action="version", version=__version__)
    return result


def main(argv=None):
    command = parser()
    args = command.parse_args(argv)
    if not 1 <= args.fps <= 240:
        command.error("--fps must be between 1 and 240")
    if args.source and (args.file or args.url):
        command.error("choose a positional source, --file, or --url")
    if args.offline and args.force_download:
        command.error("--offline and --force-download cannot be combined")
    try:
        from .cache import Cache
        from .config import save_default
        from .source import resolve_source, video_id

        if args.set_default:
            value = args.set_default
            if "://" in value:
                video_id(value)
            else:
                path = Path(value).expanduser().resolve()
                if not path.is_file():
                    raise ValueError(f"File not found: {path}")
                value = str(path)
            save_default(value)
            print("Default source saved. Run hitorigotsu to play.")
            return 0
        if args.clear_cache:
            Cache().clear()
            print("Video cache cleared.")
            return 0
        if args.cache_list:
            for key, path in Cache().entries():
                print(f"{key}\t{'valid' if path else 'corrupt/incomplete'}\t{path or ''}")
            return 0
        source = str(args.file) if args.file else args.url or args.source
        if args.url:
            video_id(args.url)
        path = resolve_source(source, offline=args.offline, force=args.force_download)
        from .player import Player

        metrics = Player(path, args).run()
        if args.benchmark or args.benchmark_output:
            report = json.dumps(metrics, indent=2)
            if args.benchmark_output:
                args.benchmark_output.write_text(report + "\n")
            print(report, file=sys.stderr)
        return 0
    except KeyboardInterrupt:
        print("\nPlayback/download cancelled.", file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"hitorigotsu: {exc}", file=sys.stderr)
        return 1
