"""Step 2: audio recording through ffmpeg (microphone by default, or system audio).

With live=True, ffmpeg also streams raw 16 kHz mono PCM to a pipe so the live
panel can transcribe while the full WAV is still being written.
"""
import subprocess
import threading
import time
from pathlib import Path

import config
from src import osdep

BYTES_PER_SECOND = 16000 * 2  # 16 kHz, 16-bit mono


class Recorder:
    def __init__(self, out_path, live=False, source=None):
        """`source` is one PulseAudio source, or a list of them to be mixed into one recording."""
        self.out_path = Path(out_path)
        self.live = live
        self.source = source or config.AUDIO_SOURCE
        self.sources = list(self.source) if isinstance(self.source, (list, tuple)) else [self.source]
        self.proc = None
        self._t0 = None

    def start(self):
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [osdep.ffmpeg_path(), "-y", "-loglevel", "error"]
        for src in self.sources:
            cmd += ["-f", "pulse", "-i", src]
        wav = ["-ac", "1", "-ar", "16000", str(self.out_path)]
        pipe = ["-ac", "1", "-ar", "16000", "-f", "s16le", "pipe:1"]
        if len(self.sources) == 1:
            cmd += wav + (pipe if self.live else [])
        else:   # several sources (e.g. the teacher's sound + your microphone): mix into one stream
            n = len(self.sources)
            mix = "".join(f"[{i}:a]" for i in range(n)) + f"amix=inputs={n}:duration=longest:normalize=0"
            if self.live:
                cmd += ["-filter_complex", mix + ",asplit=2[a][b]", "-map", "[a]"] + wav + ["-map", "[b]"] + pipe
            else:
                cmd += ["-filter_complex", mix + "[a]", "-map", "[a]"] + wav
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE if self.live else None)
        self._t0 = time.monotonic()
        time.sleep(0.5)  # fail fast if the microphone cannot be opened
        if self.proc.poll() is not None:
            raise RuntimeError(f"ffmpeg could not open audio source {self.source!r}")

    def read_pcm(self, seconds):
        """Block until `seconds` of live audio arrive; shorter/empty bytes at the end."""
        return self.proc.stdout.read(int(seconds * BYTES_PER_SECOND))

    def elapsed(self):
        """Seconds since recording started; flags use this as their timestamp."""
        return time.monotonic() - self._t0

    def stop(self):
        """Finish the recording. If ffmpeg doesn't exit by itself (e.g. its live pipe is full), force it."""
        if self.proc.poll() is None:
            try:
                self.proc.stdin.write(b"q")  # lets ffmpeg finalize the WAV header
                self.proc.stdin.flush()
            except OSError:
                pass
            if self.live and self.proc.stdout:
                threading.Thread(target=self._drain, daemon=True).start()   # unblock ffmpeg if nobody reads
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def _drain(self):
        try:
            while self.proc.stdout.read(65536):
                pass
        except Exception:
            pass


def make_recorder(out_path, live=False, kind="mic"):
    """The right recorder for this computer. kind "mic": the class sound plus your microphone; "system": only the
    sound playing on the computer (a video)."""
    if osdep.IS_WINDOWS:
        from src.record_win import WindowsRecorder
        return WindowsRecorder(out_path, live=live, mic=(kind == "mic"))
    source = [config.SYSTEM_AUDIO_SOURCE, config.AUDIO_SOURCE] if kind == "mic" else config.SYSTEM_AUDIO_SOURCE
    return Recorder(out_path, live=live, source=source)
