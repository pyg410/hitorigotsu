# Validation record

Date: 2026-11-20 (Asia/Seoul). Host: macOS 15.3 arm64, Python 3.12.13.
This record distinguishes executed checks from configured future checks.

## Executed locally

- pytest default suite: 27 passed, with opt-in network/device tests skipped when
  their environment variables are absent.
- Full local suite with `HITORIGOTSU_AUDIO_TEST=1`: **28 passed, 1 skipped in 8.79 s**.
  The skipped test is the opt-in network E2E; its two explicit attempts failed as
  recorded below. Real-device pause/resume/seek/mute/restart and cleanup passed.
- Ruff lint and format checks.
- FFmpeg synthetic media generation; actual block and ASCII playback through a
  100×30 POSIX PTY, with GIF/PNG artifacts in `assets/`.
- Real MacBook Pro speaker output via sounddevice/Core Audio. This verifies the
  output API and device clock; no human listening or acoustic loopback measurement
  is claimed.
- Benchmark runs in `benchmarks/`: 192-frame local audio run, zero dropped frames,
  zero audio underruns. Separate PTY-output runs also had no frame drops.
- Independent wheel installation in a fresh virtual environment, help command and
  one-second muted playback of generated media.

Tests cover strict URL parsing, positive/finite CLI arguments, glyph colors and
geometry, repeated escape suppression, monotonic pause, fragmented keys, hash cache
corruption, incomplete-download exclusion, mocked publish/offline reuse, config
roundtrip, queued DAC latency, FFmpeg decode/seek, bounded queue termination, slow
render frame dropping, controls, PTY resize followed by Q/SIGINT and terminal restoration.
On macOS the transient PENDIN flag set by tcsetattr is excluded from the saved-mode
comparison; all persistent terminal settings are compared.

## Real YouTube E2E attempts

The opt-in test calls the actual yt-dlp Python API, then would validate/cache the
merged media and run three seconds of real audio/video rendering. Neither attempt
reached successful download, so the later stages were **not** marked successful.

| URL | Result |
|---|---|
| `https://www.youtube.com/watch?v=BaW_jenozKc` | yt-dlp: “This video is unavailable”; no completed cache |
| `https://www.youtube.com/watch?v=gHKT4uU8Zng` | Metadata extraction reached media download; HTTP 403 Forbidden; no completed cache |

The second URL is a public test video listed in yt-dlp's own YouTube extractor,
not an alleged official Hitorigotsu MV. The retry used yt-dlp 2026.10.26, EJS 0.8.0
and Node 24.13.1. No cookies, alternate identity, proxy or restriction bypass was used.
Failed download staging was removed. A normal mocked API integration covers the
successful cache publication/offline path, but is explicitly not a live E2E result.

## Not yet verified / remaining limits

- Successful YouTube media download → FFmpeg merge → terminal + audio E2E in this
  network environment. Repeat the opt-in test with an authorized accessible URL.
- An authoritative persistent official Hitorigotsu full-MV URL. No default is invented.
- Linux/Windows runtime, audio hardware and terminal behavior. CI is configured,
  but GitHub Actions has not been run in this task.
- Physical output latency, long-duration clock drift, Bluetooth, exotic timestamp
  discontinuities/edit lists, and concurrent mutation of the same cache entry.
- Public GitHub/PyPI publication and PyPI name availability. The source builds locally;
  deployment credentials and trusted-publisher setup belong to the maintainer.

Pause/seek recreate streams and can briefly rebuffer. The video decode queue has
four frames, audio queue sixteen blocks; memory is bounded by these plus FFmpeg's
internal buffers, not by total video length. CPU/RSS metrics explicitly exclude
FFmpeg children. See the README and benchmark notes for semantics.
