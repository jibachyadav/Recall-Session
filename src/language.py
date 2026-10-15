"""Output language: the language you read in the panel and notes (English or Nepali).

Speech in any language is translated to English by Whisper (offline). Nepali output is
then produced from the English text with Claude, so it needs ANTHROPIC_API_KEY.
"""
import json
import sys
from pathlib import Path

import config
from src import llm

SETTINGS = "session.json"


def choose_language():
    """Ask which language to read in; non-interactive shells get the default."""
    if not sys.stdin.isatty() or len(config.LANGUAGES) == 1:
        return config.DEFAULT_LANGUAGE  # nothing to ask when only one language is enabled
    codes = list(config.LANGUAGES)
    print("Show text in which language?")
    for i, code in enumerate(codes, 1):
        print(f"  {i}) {config.LANGUAGES[code]}")
    while True:
        answer = input(f"Choose [1-{len(codes)}] (Enter = {config.LANGUAGES[config.DEFAULT_LANGUAGE]}): ").strip()
        if not answer:
            return config.DEFAULT_LANGUAGE
        if answer.isdigit() and 1 <= int(answer) <= len(codes):
            return codes[int(answer) - 1]


def save_settings(session_dir, **values):
    path = Path(session_dir) / SETTINGS
    data = json.loads(path.read_text()) if path.exists() else {}
    data.update(values)
    path.write_text(json.dumps(data, indent=2))


def load_language(session_dir):
    path = Path(session_dir) / SETTINGS
    if path.exists():
        return json.loads(path.read_text()).get("language", config.DEFAULT_LANGUAGE)
    return config.DEFAULT_LANGUAGE


def instruction(lang):
    """Sentence appended to prompts so Claude answers in the chosen language."""
    return "" if lang == "en" else f"\n\nWrite your entire answer in {config.LANGUAGES[lang]}."


def translate(text, lang, ask=llm.ask):
    """Translate English text to `lang`; returns the text unchanged if not possible."""
    if lang == "en" or not text.strip() or (ask is llm.ask and not llm.available()):
        return text
    try:
        return ask("Translate this lecture text from English into "
                   f"{config.LANGUAGES[lang]}. Keep technical terms, code and numbers "
                   f"accurate. Reply with the translation only.\n\n{text}", max_tokens=1000)
    except Exception:  # never break live transcription over a translation failure
        return text


def translate_segments(segments, lang, ask=llm.ask, batch=40):
    """Translate transcript segments in numbered batches; falls back to English per batch."""
    if lang == "en" or (ask is llm.ask and not llm.available()):
        return segments
    out = []
    for i in range(0, len(segments), batch):
        part = segments[i:i + batch]
        numbered = "\n".join(f"{n}|{s['text']}" for n, s in enumerate(part, 1))
        try:
            reply = ask(f"Translate each numbered lecture line from English into {config.LANGUAGES[lang]}. "
                        "Keep technical terms, code and numbers accurate. Reply with exactly the "
                        f"same numbered lines in the format N|translation, nothing else.\n\n{numbered}",
                        max_tokens=4000)
            parsed = {}
            for line in reply.splitlines():
                num, _, text = line.partition("|")
                if num.strip().isdigit() and text.strip():
                    parsed[int(num)] = text.strip()
        except Exception:
            parsed = {}
        out += [{**s, "text": parsed.get(n, s["text"])} for n, s in enumerate(part, 1)]
    return out
