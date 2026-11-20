"""Monotonic fallback clock, frozen across pause, rebased across seek."""

import time


class Clock:
    def __init__(self, position=0.0, now=time.monotonic):
        self.now = now
        self.base = position
        self.anchor = now()
        self.paused = False

    def position(self):
        return self.base if self.paused else self.base + self.now() - self.anchor

    def pause(self, paused):
        self.base = self.position()
        self.anchor = self.now()
        self.paused = paused
