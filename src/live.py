"""Step 5: background live transcription (and rolling "now covering" summary)."""
import json
import queue
import threading
import time

import numpy as np

import config
from src import llm
from src.language import instruction, save_settings, translate
from src.transcribe import get_model


class LiveTranscriber:
    """Events are put on `events`: ("text", start_seconds, text) / ("summary", text)."""

    def __init__(self, recorder, language="en", terms=""):
        self.recorder = recorder
        self.language = language
        self.prompt = f"Vocabulary: {terms}." if terms.strip() else None  # helps Whisper spell technical words
        self._spoken = None  # spoken language, detected on the first chunk with speech
        self.events = queue.Queue()
        self._recent = []  # (start_seconds, text)
        self._shown = set()  # chunk starts already sent to the panel
        self._by_chunk = {}  # chunk start -> its segments; the accurate pass replaces the draft
        self._lock = threading.Lock()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._transcribe_loop, daemon=True)
        self._thread.start()
        if llm.available():
            threading.Thread(target=self._summary_loop, daemon=True).start()

    @property
    def segments(self):
        """Whole-recording transcript so far: [{"start", "end", "text"}, ...] in time order."""
        with self._lock:
            return [seg for start in sorted(self._by_chunk) for seg in self._by_chunk[start]]

    def recent_text(self, seconds):
        """What was said in the last `seconds` of the recording, as one string."""
        segs = self.segments
        if not segs:
            return ""
        horizon = segs[-1]["end"] - seconds
        return " ".join(x["text"] for x in segs if x["end"] >= horizon)

    def _store(self, offset, segs):
        with self._lock:
            self._by_chunk[offset] = [{"start": round(offset + a, 2), "end": round(offset + b, 2), "text": t}
                                      for a, b, t in segs]
            self._recent = [(o, " ".join(x["text"] for x in v)) for o, v in sorted(self._by_chunk.items()) if v]

    def _lag(self, end):
        """Seconds the transcription is behind the audio (0 when unknown)."""
        elapsed = getattr(self.recorder, "elapsed", None)
        return max(0.0, elapsed() - end) if elapsed else 0.0

    def _emit(self, offset, text, end, draft):
        """First sight of a chunk -> "text"; every later version replaces it -> "update"."""
        with self._lock:
            kind = "update" if offset in self._shown else "text"
            self._shown.add(offset)
        self.events.put((kind, offset, text, end, draft))

    def _transcribe_loop(self):
        """Reader thread: grey drafts while you speak. A second thread makes the accurate text."""
        draft = get_model(config.LIVE_DRAFT_MODEL)
        final = get_model(config.LIVE_WHISPER_MODEL)
        if self.language != "en" and not llm.available():
            self.events.put(("status", "Nepali needs ANTHROPIC_API_KEY: showing English"))
        else:
            self.events.put(("status", "listening..."))
        todo = queue.Queue()

        def accurate():
            while True:
                item = todo.get()
                if item is None:
                    return
                offset, audio, end = item
                behind = self._lag(end) >= config.LIVE_MAX_LAG_SECONDS
                model = draft if behind else final      # when behind, settle for the quicker model
                segs = self._segments(model, audio)
                text = " ".join(t for _, _, t in segs).strip()
                if text:
                    self._store(offset, segs)
                    self._emit(offset, text, end, draft=behind and draft is not final)

        worker = threading.Thread(target=accurate, daemon=True)
        worker.start()
        for kind, offset, audio in self._chunks():
            end = offset + len(audio) / 16000
            if kind == "final":
                todo.put((offset, audio, end))
            elif self._lag(end) < config.LIVE_PARTIAL_MAX_LAG_SECONDS:   # grey draft of the sentence so far
                segs = self._segments(draft, audio)
                text = " ".join(t for _, _, t in segs).strip()
                if text:
                    self._emit(offset, text, end, draft=True)
        todo.put(None)
        worker.join()

    def _chunks(self):
        """Yield ("partial"|"final", start_seconds, float32 audio).

        "partial" repeats the growing current chunk every few seconds so text can appear while
        it is being spoken; "final" is the finished chunk, cut at a pause in the speech.
        """
        step = 0.25
        frame_bytes = int(step * 32000)
        buf = bytearray()
        loud = []          # loudness of each 0.25 s frame in buf
        history = []       # recent loudness values, to estimate the background noise level
        start = 0.0
        sent = 0.0         # seconds of the current chunk already shown as a partial
        pcm = lambda b: np.frombuffer(bytes(b), dtype=np.int16).astype(np.float32) / 32768.0
        while True:
            piece = self.recorder.read_pcm(step)
            eof = len(piece) < frame_bytes
            if piece:
                samples = np.frombuffer(piece[:len(piece) // 2 * 2], dtype=np.int16).astype(np.float32)
                rms = float(np.sqrt(np.mean(samples ** 2))) if len(samples) else 0.0
                buf += piece[:len(piece) // 2 * 2]
                loud.append(rms)
                history = (history + [rms])[-400:]
            noise = float(np.percentile(history, 10)) if history else 0.0
            quiet = max(noise * 3, 120)                      # below this counts as a pause
            secs = len(buf) / 32000
            need = max(1, int(config.LIVE_PAUSE_SECONDS / step))
            paused = len(loud) >= need and all(v < quiet for v in loud[-need:])
            if eof:
                if secs >= 0.3:
                    yield "final", start, pcm(buf)
                return
            cut = None
            if secs >= config.LIVE_MAX_CHUNK_SECONDS:        # too long: cut at the quietest moment of the last 3 s
                tail = loud[-12:]
                cut = len(loud) - len(tail) + int(np.argmin(tail)) + 1
            elif secs >= config.LIVE_MIN_CHUNK_SECONDS and paused:
                cut = len(loud)
            if cut:
                n = cut * frame_bytes
                yield "final", start, pcm(buf[:n])
                start += n / 32000
                buf, loud, sent = bytearray(buf[n:]), loud[cut:], 0.0
            elif secs >= 1.0 and secs - sent >= config.LIVE_PARTIAL_STEP_SECONDS and not paused:
                sent = secs
                yield "partial", start, pcm(buf)

    def _segments(self, model, audio):
        """[(start, end, english_text)] for one chunk; foreign speech is translated by Whisper."""
        def run(**kw):
            segs, info = model.transcribe(audio, vad_filter=True, initial_prompt=self.prompt, **kw)
            return [(s.start, s.end, s.text.strip()) for s in segs if s.text.strip()], info

        if self._spoken is None:
            out, info = run()
            if out and info.language_probability > 0.6:
                self._spoken = info.language
            if out and info.language != "en":
                out, _ = run(task="translate", language=info.language)
        else:
            out, _ = run(task="transcribe" if self._spoken == "en" else "translate", language=self._spoken)
        if self.language != "en" and out:  # translated output: keep one segment for the whole chunk
            text = translate(" ".join(t for _, _, t in out), self.language)
            out = [(out[0][0], out[-1][1], text)]
        return out

    def finish(self, timeout=30):
        """Wait for the last chunks to be transcribed. True if the whole recording was covered."""
        if self._thread is not None:
            self._thread.join(timeout)
            return not self._thread.is_alive()
        return False

    def save(self, session_dir, complete):
        """Write transcript_live.json and remember whether it covers the whole recording."""
        segments = self.segments
        (session_dir / "transcript_live.json").write_text(json.dumps(segments, indent=2))
        save_settings(session_dir, live_complete=complete, spoken_language=self._spoken or "en")

    def _summary_loop(self):
        last_seen = 0
        while True:
            time.sleep(config.LIVE_SUMMARY_SECONDS)
            with self._lock:
                if len(self._recent) == last_seen:
                    continue  # nothing new since the last summary
                last_seen = len(self._recent)
                horizon = self._recent[-1][0] - config.LIVE_SUMMARY_CONTEXT_SECONDS
                text = " ".join(t for s, t in self._recent if s >= horizon)
            try:
                line = llm.ask(
                    "This is a live, rough transcript of a lecture in progress. In one short "
                    "line (max 15 words), say what topic is being taught right now." +
                    instruction(self.language) + "\n\n" + text,
                    max_tokens=60)
            except Exception:  # no credit, no internet...: show nothing rather than an error
                continue
            self.events.put(("summary", line))
