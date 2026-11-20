# Source review and design decisions

Reviewed 2026-11-20. Public repositories were fetched into temporary directories;
no implementation was copied or vendored.

| Project | Existence / revision | License observed |
|---|---|---|
| [maxcurzi/tplay](https://github.com/maxcurzi/tplay) | `c62dca0da1696e57eb9726cfe08354311587fb7f` | MIT, root LICENSE and Cargo.toml |
| [yym8224961/world.execute-me-ascii](https://github.com/yym8224961/world.execute-me-ascii) | `3409cf081e36fc57bc8fda76c54a4fc9986e8441` | No root license file found; do not assume permission to reuse |
| [DvorakDwarf/Colored-ASCII-Video](https://github.com/DvorakDwarf/Colored-ASCII-Video) | `8dc0cec9dac738400ab7ea06bf352ac526fb703c` | MIT, root LICENSE |

## tplay

Inspected `src/pipeline/image_pipeline.rs`, `src/common/sync.rs`, pipeline/audio
runners and main channel wiring. Rust image resizing and a luminance lookup table
produce ASCII; half-block foreground/background colors double vertical resolution.
Bounded channels separate the pipeline and terminal. Shared playback state makes
audio the master clock, with backends including mpv and rodio.
Adopted the architectural ideas of bounded queues, half blocks and audio-master timing;
implemented independently in Python, FFmpeg, NumPy and PortAudio.

## world.execute-me-ascii

Inspected `player.py` and `AudioClock.swift`. This is a song-specific procedural
terminal MV rather than a generic video-to-ASCII decoder. Swift AVAudioPlayer reports
playback time to Python via a JSON stream; the terminal samples the audio timeline.
It also uses monotonic timing for rendering and controls. The useful principle is
that the audio device owns media time. Avoided its platform-specific helper and all
source/assets because no explicit license was found.

## Colored-ASCII-Video

Inspected `bapple.py` and `downloadVid.py`. OpenCV reads frames, a grayscale ramp
selects characters, and RGB escape sequences color them. ffpyplayer supplies audio;
frame timing uses wall time and a busy loop, with audio paused/resumed around frames.
It queries terminal dimensions but notes aspect/portrait limitations in source.
Kept the understandable frame-to-string approach, but replaced busy waiting and
per-frame audio control with a continuous sample clock, bounded workers and dropping.

## Libraries and tradeoffs

- FFmpeg/ffprobe: stream selection, seeking, codec coverage, VFR normalization,
  rotation and bounded-resolution BGR/PCM pipes. FFmpeg handles decode instead of
  relying on OpenCV's codec-dependent CAP_PROP_POS_MSEC behavior.
  [fps filter documentation](https://ffmpeg.org/ffmpeg-filters.html#fps).
- OpenCV: efficient area resize and synthetic-video creation; headless distribution
  avoids Qt/window dependencies. NumPy handles luminance and glyph lookup in bulk.
- sounddevice/PortAudio: callback output timestamps and device time allow explicit
  latency accounting; FFplay has no simple portable control/clock IPC for pause,
  volume and seeking. [Output stream API](https://python-sounddevice.readthedocs.io/en/latest/api/streams.html).
- yt-dlp Python API: download progress, bounded height selection and FFmpeg remuxing.
  Current YouTube extraction requires an external JS runtime plus EJS;
  [official setup guidance](https://github.com/yt-dlp/yt-dlp/wiki/EJS).
- platformdirs: portable user paths. psutil: portable Python process CPU/RSS metrics.
- argparse, queue, threading, subprocess: standard library instead of a framework.

## Official Hitorigotsu source

The [official anime website](https://www.anime-chiikawa.jp/) lists the ending song,
Hachiware (CV Makoto Tanaka), Nagano and Shugo Tokumaru. Search results also surfaced
fan uploads and time-limited episode postings. A verified, persistent official full-MV
YouTube URL was not established. No search result is promoted to an official default;
the user configures an authorized source. This is a deliberate correctness decision,
not a placeholder URL. Song/character media and lyrics are not redistributed.
