"""Step 3: flag confusing moments (terminal key or panel button)."""
import json
import select
import subprocess
import sys
import termios
import tty
from pathlib import Path

import config
from src import osdep


def take_screenshot(path):
    """Capture the full screen; returns False if the capture failed."""
    return osdep.take_screenshot(path)


def fmt(seconds):
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


class FlagLogger:
    """Logs a timestamp + screenshot per flag; saves confusion_log.json each time."""

    def __init__(self, recorder, session_dir):
        self.recorder = recorder
        self.shots = Path(session_dir) / "screenshots"
        self.shots.mkdir(exist_ok=True)
        self.log_path = Path(session_dir) / "confusion_log.json"
        self.flags = []

    def flag(self):
        t = round(self.recorder.elapsed(), 1)
        shot = self.shots / f"{int(t)}.png"
        ok = take_screenshot(shot)
        self.flags.append({"timestamp": t, "screenshot": shot.name if ok else None})
        self.log_path.write_text(json.dumps(self.flags, indent=2))
        return t, ok


def run_until_stop(logger):
    """Terminal mode: block until Enter (or q); FLAG_KEY logs a flag."""
    if not sys.stdin.isatty():
        return  # no keyboard attached: nothing to listen to
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)  # read single keys without waiting for Enter
        while True:
            if logger.recorder.elapsed() >= config.MAX_RECORDING_SECONDS:
                print("  2-hour limit reached: stopping.")
                break
            if not select.select([sys.stdin], [], [], 0.2)[0]:
                continue
            key = sys.stdin.read(1)
            if key in ("\n", "\r", "q"):
                break
            if key == config.FLAG_KEY:
                t, ok = logger.flag()
                print(f"  flagged {fmt(t)}" + ("" if ok else " (screenshot failed)"))
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
