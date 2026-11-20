"""Nonblocking keyboard input with fragmented ANSI escape sequence support."""

import os
import sys


class Controls:
    def __init__(self):
        self.pending = ""

    def poll(self):
        if not sys.stdin.isatty():
            return []
        if os.name == "nt":
            import msvcrt

            text = ""
            while msvcrt.kbhit():
                char = msvcrt.getwch()
                if char in ("\x00", "\xe0"):
                    char = {"K": "\x1b[D", "M": "\x1b[C", "H": "\x1b[A", "P": "\x1b[B"}.get(
                        msvcrt.getwch(), ""
                    )
                text += char
        else:
            import select

            text = ""
            while select.select([sys.stdin], [], [], 0)[0]:
                data = os.read(sys.stdin.fileno(), 64)
                if not data:
                    break
                text += data.decode(errors="ignore")
        return self.feed(text)

    def feed(self, text):
        self.pending += text
        keys = []
        while self.pending:
            if self.pending.startswith("\x1b"):
                if len(self.pending) < 3:
                    break
                sequence, self.pending = self.pending[:3], self.pending[3:]
                key = {"\x1b[A": "up", "\x1b[B": "down", "\x1b[C": "right", "\x1b[D": "left"}.get(
                    sequence
                )
                if key:
                    keys.append(key)
            else:
                keys.append(self.pending[0].lower())
                self.pending = self.pending[1:]
        return keys
