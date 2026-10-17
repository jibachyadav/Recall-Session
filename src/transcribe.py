"""Step 4: speech-to-text with faster-whisper (local, offline after first download)."""
import json
from pathlib import Path

from faster_whisper import BatchedInferencePipeline, WhisperModel

import config
from src import models
from src.language import save_settings

_models = {}


def get_model(name=None):
    name = name or config.WHISPER_MODEL
    if name not in _models:
        _models[name] = WhisperModel(models.local_path(name) or name, device="cpu", compute_type="int8")
    return _models[name]


_batched = {}


def get_batched(name=None):
    """Batched decoding: roughly 5-9x faster than the plain model on long recordings."""
    name = name or config.WHISPER_MODEL
    if name not in _batched:
        _batched[name] = BatchedInferencePipeline(model=get_model(name))
    return _batched[name]


def model_for(language):
    """The model used for the final transcript of a given spoken language."""
    return config.FINAL_MODEL_FOR.get(language, config.WHISPER_MODEL)


def transcribe(audio_path, task="transcribe", language=None, terms="", model=None):
    """Return (segments, spoken_language). task="translate" gives English text for any language."""
    # without_timestamps=False keeps sentence-sized segments (needed for flag highlights)
    big = (model or config.WHISPER_MODEL) in config.LARGE_MODELS
    segments, info = get_batched(model).transcribe(str(audio_path), task=task, language=language,
                                              batch_size=config.LARGE_MODEL_BATCH_SIZE if big else config.WHISPER_BATCH_SIZE,
                                              **({"beam_size": config.LARGE_MODEL_BEAM_SIZE} if big else {}),
                                              without_timestamps=False,
                                              initial_prompt=f"Vocabulary: {terms}." if terms.strip() else None)
    return ([{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
             for s in segments], info.language)


def transcribe_session(session_dir):
    """Transcribe recording.wav. Returns the ENGLISH transcript (what summaries, highlights and questions use).

    Spoken English: one pass. Spoken Nepali / Hindi (chosen in the name window, or detected): the original-language
    transcript is kept in transcript_original.json. The English version comes from Claude when it works; otherwise
    english_source is "none" (made on demand with make_offline_english) or, for Hindi, the English from the live panel.
    """
    session_dir = Path(session_dir)
    audio = session_dir / "recording.wav"
    settings = session_dir / "session.json"
    info = json.loads(settings.read_text()) if settings.exists() else {}
    terms, chosen = info.get("terms", ""), info.get("spoken", "auto")
    language = None if chosen == "auto" else chosen
    segments, detected = transcribe(audio, language=language, terms=terms, model=model_for(language) if language else None)
    spoken = language or detected
    if spoken == "en":
        english_source = None
    else:
        if language is None and model_for(spoken) != config.WHISPER_MODEL:      # detected a language that needs the big model
            segments, _ = transcribe(audio, language=spoken, terms=terms, model=model_for(spoken))
        (session_dir / "transcript_original.json").write_text(json.dumps(segments, indent=2))
        try:
            from src import translate
            segments, english_source = translate.to_english(segments, spoken), "claude"
        except Exception:
            # No Claude. Skip the slow offline translation (about 28% more time, and unreliable for Nepali): the
            # English version is made on demand. The one free exception: Hindi's live panel already made English.
            live = session_dir / "transcript_live.json"
            live_english = json.loads(live.read_text()) if live.exists() and info.get("live_complete") else []
            if spoken == "hi" and live_english:
                segments, english_source = live_english, "whisper"
            else:
                english_source = "none"      # transcript_final.json holds the original text until English is made
    (session_dir / "transcript_final.json").write_text(json.dumps(segments, indent=2))
    save_settings(session_dir, spoken_language=spoken, english_source=english_source)
    return segments


def estimate_message(language, audio_seconds):
    """A sentence telling the user how long the after-class pass will take, or None for quick cases."""
    factor = config.SLOW_PASS_FACTOR.get(language)
    if not factor or audio_seconds < 60:
        return None
    minutes = max(1, round(audio_seconds * factor / 60))
    name = config.LANGUAGE_NAMES.get(language, language)
    return (f"Transcribing {name} speech: about {minutes} minute{'s' if minutes != 1 else ''} for this recording. "
            "This is the slow step; closing other programs makes it faster.")


def make_offline_english(session_dir):
    """Make a rough English version of a Nepali / Hindi session with Whisper's own translation (small model, offline).

    Slow-ish (about 0.12x the recording) and unreliable for Nepali, so it only runs when the user asks. Removes the
    outputs built from the old text, so the caller can rebuild them."""
    session_dir = Path(session_dir)
    info_file = session_dir / "session.json"
    info = json.loads(info_file.read_text()) if info_file.exists() else {}
    language = info.get("spoken_language")
    if not language or language == "en":
        raise ValueError("This session was in English: there is nothing to translate.")
    segments, _ = transcribe(session_dir / "recording.wav", task="translate", language=language)
    (session_dir / "transcript_final.json").write_text(json.dumps(segments, indent=2))
    save_settings(session_dir, english_source="whisper")
    for stale in ("summary.md", "important.json", "explanations.json", "notes_final.md"):
        (session_dir / stale).unlink(missing_ok=True)
    return segments


def offline_english_message(audio_seconds):
    minutes = max(1, round(audio_seconds * config.OFFLINE_ENGLISH_FACTOR / 60))
    return f"about {minutes} minute{'s' if minutes != 1 else ''}"
