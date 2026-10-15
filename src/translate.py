"""Turn Nepali / Hindi text into English with Claude (better than Whisper's own rough translation)."""
import json
import re
from pathlib import Path

import config
from src import llm
from src.language import save_settings


class TranslateError(Exception):
    """Claude could not translate (no key, no credit, no internet, or an unreadable reply)."""


def to_english(segments, language, ask=None, batch=30):
    """Return the same segments with English text. Raises TranslateError if it can't be done reliably."""
    if ask is None:
        if not llm.available():
            raise TranslateError("no Claude key")
        ask = llm.ask
    name = config.LANGUAGE_NAMES.get(language, language)
    out = []
    for i in range(0, len(segments), batch):
        part = segments[i:i + batch]
        numbered = "\n".join(f"{n}|{s['text']}" for n, s in enumerate(part, 1))
        try:
            reply = ask(f"Translate each numbered lecture line from {name} into clear, natural English. The text is "
                        "speech-to-text, so it may contain mistakes: translate what the speaker most likely meant. "
                        "Keep technical terms, names, code and numbers. Reply with exactly the same numbered lines in "
                        f"the format N|translation, nothing else.\n\n{numbered}", max_tokens=4000)
        except Exception as e:
            raise TranslateError(str(e)[:120]) from e
        parsed = {}
        for line in reply.splitlines():
            num, _, text = line.partition("|")
            if num.strip().isdigit() and text.strip():
                parsed[int(num)] = text.strip()
        if len(parsed) < len(part) * 0.8:          # most lines must come back, or the reply is not trustworthy
            raise TranslateError("the translation came back incomplete")
        out += [{**s, "text": parsed.get(n, s["text"])} for n, s in enumerate(part, 1)]
    return out


def retranslate_session(session_dir, ask=None):
    """Redo the English version of a Nepali / Hindi session with Claude (after the offline one was rough).

    Keeps the user's previous English in transcript_before_retranslate.json and removes the outputs that were built
    from it (summary, highlights, explanations, notes) so the caller can rebuild them. Raises TranslateError."""
    session_dir = Path(session_dir)
    original = session_dir / "transcript_original.json"
    info_file = session_dir / "session.json"
    if not original.exists():
        raise TranslateError("This session has no original-language transcript to translate.")
    language = (json.loads(info_file.read_text()) if info_file.exists() else {}).get("spoken_language", "ne")
    english = to_english(json.loads(original.read_text()), language, ask)           # raises before anything is changed
    final = session_dir / "transcript_final.json"
    backup = session_dir / "transcript_before_retranslate.json"
    if final.exists() and not backup.exists():
        backup.write_text(final.read_text())
    final.write_text(json.dumps(english, indent=2))
    save_settings(session_dir, english_source="claude")
    for stale in ("summary.md", "important.json", "explanations.json", "notes_final.md"):
        (session_dir / stale).unlink(missing_ok=True)
    return english
