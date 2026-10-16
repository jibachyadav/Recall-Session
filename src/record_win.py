"""Windows recording: the teacher's sound (WASAPI loopback) plus your microphone, mixed into one 16 kHz mono stream.

Same interface as the Linux Recorder in record.py (start / read_pcm / elapsed / stop), so the rest of the app is unchanged.
Windows has no ffmpeg input for "what the speakers are playing", so this uses the `pyaudiowpatch` library instead.

The mixing code (_Mixer, _Resampled) knows nothing about Windows and is tested on Linux with fake sound sources;
the part that talks to the sound card (_open_streams) can only be tested on a real Windows computer.
"""
import queue
import threading
import time
import wave
from pathlib import Path

import numpy as np

RATE = 16000
BYTES_PER_SECOND = RATE * 2


class _Resampled:
    """Raw sound from the sound card (any rate, any channel count) -> a growing buffer of 16 kHz mono samples."""

    def __init__(self, rate, channels):
        import av
        self.rate, self.channels = rate, max(1, channels)
        self._resampler = av.AudioResampler(format="s16", layout="mono", rate=RATE)
        self._av = av
        self._lock = threading.Lock()
        self._buf = np.zeros(0, dtype=np.int16)

    def feed(self, raw):
        """raw: bytes of interleaved int16 samples as they come from the sound card."""
        samples = np.frombuffer(raw, dtype=np.int16)
        usable = len(samples) - len(samples) % self.channels
        if usable <= 0:
            return
        mono = samples[:usable].reshape(-1, self.channels).mean(axis=1).astype(np.int16)
        frame = self._av.AudioFrame.from_ndarray(mono.reshape(1, -1), format="s16", layout="mono")
        frame.sample_rate = self.rate
        out = [f.to_ndarray().reshape(-1) for f in self._resampler.resample(frame)]
        if out:
            with self._lock:
                self._buf = np.concatenate([self._buf, *out])

    def take(self, n):
        """Up to n samples (fewer if not that many have arrived)."""
        with self._lock:
            got, self._buf = self._buf[:n], self._buf[n:]
        return got


class _Mixer:
    """Pulls from several sources on a steady clock and sums them. A silent source (loopback sends nothing while
    nothing plays) simply contributes zeros, so the recording never stalls or drifts."""

    def __init__(self, sources, out_wav, live, clock=time.monotonic):
        self.sources, self.live, self.clock = sources, live, clock
        self.wav = wave.open(str(out_wav), "wb")
        self.wav.setnchannels(1); self.wav.setsampwidth(2); self.wav.setframerate(RATE)
        self.pcm = queue.Queue()                 # for the live transcript; None marks the end
        self._produced = 0
        self._t0 = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._t0 = self.clock()
        self._thread.start()

    def step(self):
        """Mix everything that is due by now. Returns the number of samples written."""
        due = int((self.clock() - self._t0) * RATE) - self._produced
        if due <= 0:
            return 0
        total = np.zeros(due, dtype=np.int32)
        for src in self.sources:
            got = src.take(due)
            total[:len(got)] += got
        mixed = np.clip(total, -32768, 32767).astype(np.int16).tobytes()
        self.wav.writeframes(mixed)
        if self.live:
            self.pcm.put(mixed)
        self._produced += due
        return due

    def _run(self):
        while not self._stop.wait(0.1):
            self.step()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=3)
        self.step()
        self.wav.close()
        self.pcm.put(None)


def _open_streams(want_mic):
    """Open the sound card. Returns (list of _Resampled, close function). Windows only."""
    import pyaudiowpatch as pyaudio
    pa = pyaudio.PyAudio()
    sources, streams = [], []

    def open_one(device, loopback):
        src = _Resampled(int(device["defaultSampleRate"]), int(device["maxInputChannels"]))

        def callback(data, frames, info, status):
            src.feed(data)
            return (None, pyaudio.paContinue)

        streams.append(pa.open(format=pyaudio.paInt16, channels=src.channels, rate=src.rate, input=True,
                               input_device_index=device["index"], frames_per_buffer=1024, stream_callback=callback))
        sources.append(src)

    try:
        wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        speakers = pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
        if not speakers.get("isLoopbackDevice"):
            for loop in pa.get_loopback_device_info_generator():
                if speakers["name"] in loop["name"]:
                    speakers = loop
                    break
            else:
                raise RuntimeError("Couldn't find a way to record what your speakers are playing.")
        open_one(speakers, True)
        if want_mic:
            try:
                open_one(pa.get_default_input_device_info(), False)
            except OSError:
                pass            # no microphone: still record the class sound
    except Exception:
        for s in streams:
            s.close()
        pa.terminate()
        raise

    def close():
        for s in streams:
            try:
                s.stop_stream(); s.close()
            except Exception:
                pass
        pa.terminate()

    return sources, close


class WindowsRecorder:
    def __init__(self, out_path, live=False, mic=True):
        self.out_path, self.live, self.mic = Path(out_path), live, mic
        self._mixer = None
        self._close = None
        self._t0 = None
        self._pending = b""

    def start(self):
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            sources, self._close = _open_streams(self.mic)
        except Exception as e:
            raise RuntimeError(f"Couldn't open the audio devices: {e}") from e
        self._mixer = _Mixer(sources, self.out_path, self.live)
        self._mixer.start()
        self._t0 = time.monotonic()

    def read_pcm(self, seconds):
        """Block until `seconds` of sound arrive; shorter/empty bytes once the recording has ended."""
        need = int(seconds * BYTES_PER_SECOND)
        while len(self._pending) < need:
            chunk = self._mixer.pcm.get()
            if chunk is None:
                self._mixer.pcm.put(None)       # let any other reader see the end too
                break
            self._pending += chunk
        out, self._pending = self._pending[:need], self._pending[need:]
        return out

    def elapsed(self):
        return time.monotonic() - self._t0

    def stop(self):
        if self._close:
            self._close()
            self._close = None
        if self._mixer:
            self._mixer.stop()
