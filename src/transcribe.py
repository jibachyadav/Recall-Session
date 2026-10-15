"""Step 4: speech-to-text with faster-whisper (local, offline after first download)."""
import json
from pathlib import Path

from faster_whisper import BatchedInferencePipeline, WhisperModel

import config
from src.language import save_settings

_models = {}


def get_model(name=None):
    name = name or config.WHISPER_MODEL
    if name not in _models:
        _models[name] = WhisperModel(name, device="cpu", compute_type="int8")
    return _models[name]


_batched = {}


def get_batched(name=None):
    """Batched decoding: roughly 5-9x faster than the plain model on long recordings."""
    name = name or config.WHISPER_MODEL
    if name not in _batched:
        _batched[name] = BatchedInferencePipeline(model=get_model(name))
    return _batched[name]


def transcribe(audio_path, task="transcribe", language=None, terms=""):
    """Return (segments, spoken_language). task="translate" gives English text for any language."""
    # without_timestamps=False keeps sentence-sized segments (needed for flag highlights)
    segments, info = get_batched().transcribe(str(audio_path), task=task, language=language,
                                              batch_size=config.WHISPER_BATCH_SIZE, without_timestamps=False,
                                              initial_prompt=f"Vocabulary: {terms}." if terms.strip() else None)
    return ([{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
             for s in segments], info.language)


def transcribe_session(session_dir):
    """Transcribe recording.wav into English text (translating foreign speech).

    Saves transcript_final.json (English) and, for foreign speech, transcript_original.json.
    """
    session_dir = Path(session_dir)
    audio = session_dir / "recording.wav"
    settings = session_dir / "session.json"
    terms = json.loads(settings.read_text()).get("terms", "") if settings.exists() else ""
    segments, spoken = transcribe(audio, terms=terms)
    if spoken != "en":
        (session_dir / "transcript_original.json").write_text(json.dumps(segments, indent=2))
        segments, _ = transcribe(audio, task="translate", language=spoken, terms=terms)
    (session_dir / "transcript_final.json").write_text(json.dumps(segments, indent=2))
    save_settings(session_dir, spoken_language=spoken)
    return segments
