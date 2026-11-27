from math import ceil
from time import monotonic


class Countdown:
    def __init__(self, seconds=25 * 60, clock=monotonic):
        self.clock = clock
        self.deadline = None
        self.mode = "Work"
        self.durations = {"Work": 25 * 60, "Rest": 5 * 60}
        self.set_duration(seconds)

    def tick(self):
        if self.deadline is None:
            return False
        self.remaining = max(0, ceil(self.deadline - self.clock()))
        if self.remaining:
            return False
        if self.mode == "Work":
            self.mode = "Rest"
            self.durations["Rest"] = 10 * 60 if self.durations["Work"] > 25 * 60 else 5 * 60
        else:
            self.prepare_work()
        self.reset()
        return True

    def prepare_work(self):
        self.durations["Work"] = (25 if self.durations["Rest"] < 10 * 60 else 40) * 60
        self.mode = "Work"

    def start(self):
        if self.deadline is None:
            self.deadline = self.clock() + self.remaining

    def pause(self):
        self.deadline = None

    def reset(self):
        self.deadline = None
        self.remaining = self.durations[self.mode]

    def force_mode(self, mode):
        if self.mode == "Rest" and mode == "Work":
            self.prepare_work()
            self.reset()
        elif mode != self.mode:
            self.durations[mode] = self.durations[self.mode]
            self.mode = mode

    def set_duration(self, seconds, *, mode=None):
        value = max(1, min(359999, seconds))
        if mode is not None:
            self.mode = mode
        self.remaining = self.durations[self.mode] = value
        if self.deadline is not None:
            self.deadline = self.clock() + value

    def adjust(self, delta):
        self.set_duration(self.remaining + delta)
