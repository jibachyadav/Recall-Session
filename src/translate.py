"""Turn Nepali / Hindi text into English with Claude (better than Whisper's own rough translation)."""
import re

import config
from src import llm


class TranslateError(Exception):
    """Claude could not translate (no key, no credit, no internet, or an unreadable reply)."""


def to_english(segments, language, ask=llm.ask, batch=30):
    """Return the same segments with English text. Raises TranslateError if it can't be done reliably."""
    if ask is llm.ask and not llm.available():
        raise TranslateError("no Claude key")
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
