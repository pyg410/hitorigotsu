"""Pure BGR frame → ANSI conversion; no terminal I/O."""

import cv2
import numpy as np

RAMP = np.array(list(" .:-=+*#%@"))


def fit_size(source_width, source_height, columns, rows, width=None, cell_aspect=0.5):
    """Return character dimensions; cell_aspect is cell width / cell height."""
    columns = max(1, min(columns - 1, width or columns))
    rows = max(1, rows - 1)
    ratio = source_width / source_height / cell_aspect
    cols = min(columns, max(1, int(rows * ratio)))
    lines = min(rows, max(1, round(cols / ratio)))
    return cols, lines


def render(frame, columns, rows, mode="block", monochrome=False):
    height = rows * (2 if mode == "block" else 1)
    pixels = cv2.resize(frame, (columns, height), interpolation=cv2.INTER_AREA)[:, :, ::-1]
    if monochrome:
        gray = np.rint(pixels @ np.array([0.2126, 0.7152, 0.0722])).astype(np.uint8)
        pixels = np.repeat(gray[..., None], 3, axis=2)
    if mode == "ascii":
        luminance = pixels @ np.array([0.2126, 0.7152, 0.0722])
        chars = RAMP[np.minimum((luminance * len(RAMP) / 256).astype(int), len(RAMP) - 1)]
    lines = []
    for y in range(rows):
        parts, previous = [], None
        for x in range(columns):
            if mode == "block":
                colors = tuple(map(int, pixels[2 * y, x])) + tuple(map(int, pixels[2 * y + 1, x]))
                if colors != previous:
                    parts.append("\x1b[38;2;{};{};{}m\x1b[48;2;{};{};{}m".format(*colors))
                parts.append("▀")
            else:
                colors = tuple(map(int, pixels[y, x]))
                if colors != previous and not monochrome:
                    parts.append("\x1b[38;2;{};{};{}m".format(*colors))
                parts.append(str(chars[y, x]))
            previous = colors
        lines.append("".join(parts) + "\x1b[0m\x1b[K")
    return "\r\n".join(lines)
