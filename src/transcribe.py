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


def model_for(language):
    """The model used for the final transcript of a given spoken language."""
    return config.FINAL_MODEL_FOR.get(language, config.WHISPER_MODEL)


def transcribe(audio_path, task="transcribe", language=None, terms="", model=None):
    """Return (segments, spoken_language). task="translate" gives English text for any language."""
    # without_timestamps=False keeps sentence-sized segments (needed for flag highlights)
    segments, info = get_batched(model).transcribe(str(audio_path), task=task, language=language,
                                              batch_size=config.WHISPER_BATCH_SIZE, without_timestamps=False,
                                              initial_prompt=f"Vocabulary: {terms}." if terms.strip() else None)
    return ([{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
             for s in segments], info.language)


def transcribe_session(session_dir):
    """Transcribe recording.wav. Returns the ENGLISH transcript (what summaries, highlights and questions use).

    Spoken English: one pass. Spoken Nepali / Hindi (chosen in the name window, or detected): the original-language
    transcript is also kept in transcript_original.json, and the English version comes from Claude when it works,
    otherwise from Whisper's own (rough) translation. session.json records how the English was made.
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
        except Exception:                                                        # no key / credit / internet: rough offline version
            segments, _ = transcribe(audio, task="translate", language=spoken, terms=terms)
            english_source = "whisper"
    (session_dir / "transcript_final.json").write_text(json.dumps(segments, indent=2))
    save_settings(session_dir, spoken_language=spoken, english_source=english_source)
    return segments
