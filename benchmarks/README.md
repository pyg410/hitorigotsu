# Measured benchmarks / 측정 결과

Measured 2026-11-20 on macOS 15.3 arm64, Python 3.12.13, FFmpeg 9.0.2,
OpenCV 5.1.0, NumPy 2.5.5, sounddevice 0.5.6. Input: original generated
320×180 video at 24 FPS, 8 seconds, 440 Hz tone. PTY: 100×30 cells.
No copyrighted footage was used. These are individual runs, not cross-machine promises.

| Run | Actual FPS | Conversion mean | stdout mean | Drops | A/V mean drift | Python CPU | Sampled RSS |
|---|---:|---:|---:|---:|---:|---:|---:|
| Block, real audio, PTY capture (6 s) | 23.83 | 5.08 ms | 12.65 ms | 0 | 18.84 ms | 13.96% | 52.53 MiB |
| ASCII, mute, PTY capture (6 s) | 24.00 | 3.43 ms | 14.62 ms | 0 | N/A | 8.94% | 45.58 MiB |
| Block, real audio, headless (8 s) | 23.95 | 8.18 ms | 0.0008 ms | 0 | 9.77 ms | 21.06% | 52.33 MiB |

Raw reports: [PTY block](pty-block.json), [PTY ASCII](pty-ascii.json),
[headless audio](local-audio.json). Audio underruns were zero in both audio runs.
The headless run processed 192 frames; PTY block processed 143 within the six-second
limit and ASCII 144. Initial preparation is recorded separately in `startup_s`;
cleanup is excluded. Actual FPS is displayed frames divided by playback wall time.

The PTY capture reader parses ANSI and rasterizes frames, introducing stdout
backpressure. Thus these numbers include the recorder's cost and are not a direct
measurement of any particular terminal emulator. Headless has no stdout work and
uses fallback terminal dimensions; it is not comparable as terminal throughput.
Conversion covers OpenCV resize, NumPy luminance and ANSI assembly, not FFmpeg decode.
The largest measured audio/video clock error was 27.58 ms in the PTY block run.

CPU is process CPU-seconds / elapsed wall-seconds (100% = one core). RSS is the maximum
sampled Python RSS, not OS high-water RSS. Both exclude FFmpeg subprocesses and the
capture process. A/V drift is absolute frame PTS versus PortAudio's device clock after
output flush. No physical loopback/acoustic or compositor timing was measured. Silent
runs report `null`, not a made-up zero A/V drift.

## Reproduce

```sh
uv sync --locked
uv run python examples/generate_test_video.py /tmp/hitorigotsu-demo.mp4 --seconds 8
uv run python examples/capture_demo.py /tmp/hitorigotsu-demo.mp4 assets/demo --audio
uv run python examples/capture_demo.py /tmp/hitorigotsu-demo.mp4 assets/demo-ascii --mode ascii
uv run hitorigotsu --file /tmp/hitorigotsu-demo.mp4 --headless --benchmark \
  --benchmark-output benchmarks/local-audio.json
```

Use a real terminal without `--headless` for your own display benchmark. Add
`--width 80` or lower `--fps` when conversion/stdout is slow. The late-frame scheduler
is separately exercised with deliberately slow rendering in pytest: frames must drop
without stretching the two-second clip into sequential frame-by-frame playback.

한국어: 위 수치는 직접 생성한 영상의 실측 결과입니다. PTY 기록기 비용과 Python 프로세스만의
CPU·메모리를 구분해서 읽어 주세요. 스피커 음향 지연을 측정한 수치가 아니며, YouTube 다운로드
성공을 의미하지 않습니다. 해당 E2E는 HTTP 403으로 완료하지 못했습니다.
