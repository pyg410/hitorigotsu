"""Owns terminal state and one-write-per-frame output, including exceptional exit."""

import os
import shutil
import sys


class Terminal:
    def __init__(self, headless=False):
        self.headless = headless
        self.saved = None
        self.windows = None

    def __enter__(self):
        if self.headless:
            return self
        if not sys.stdout.isatty() or not sys.stdin.isatty():
            raise ValueError(
                "Playback needs an interactive terminal; use --headless for benchmarks"
            )
        try:
            if os.name == "nt":
                import ctypes
                from ctypes import wintypes

                kernel = ctypes.windll.kernel32
                kernel.GetStdHandle.restype = wintypes.HANDLE
                kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
                kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
                handle = kernel.GetStdHandle(-11)
                mode = wintypes.DWORD()
                if not kernel.GetConsoleMode(handle, ctypes.byref(mode)):
                    raise ValueError("Windows VT console is unavailable")
                self.windows = (kernel, handle, mode.value)
                if not kernel.SetConsoleMode(handle, mode.value | 4):
                    raise ValueError("Cannot enable Windows virtual terminal output")
            else:
                import termios
                import tty

                self.saved = termios.tcgetattr(sys.stdin)
                tty.setcbreak(sys.stdin.fileno())
            sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[2J\x1b[H")
            sys.stdout.flush()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def size(self):
        return shutil.get_terminal_size((100, 30))

    def draw(self, text):
        if not self.headless:
            sys.stdout.write("\x1b[H" + text + "\x1b[0m\x1b[J")
            sys.stdout.flush()

    def __exit__(self, *_):
        try:
            if not self.headless:
                sys.stdout.write("\x1b[0m\x1b[?25h\x1b[?1049l")
                sys.stdout.flush()
        finally:
            if self.saved is not None:
                import termios

                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.saved)
            if self.windows is not None:
                kernel, handle, mode = self.windows
                kernel.SetConsoleMode(handle, mode)
