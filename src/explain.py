"""Step 6: explain each flagged moment from the transcript around it + the screenshot."""
import json
from pathlib import Path

import config
from src import llm
from src.hotkey_logger import fmt
from src.language import instruction, load_language

PROMPT = """A student flagged this moment of a lecture as confusing ("I didn't understand this").
Explain it simply and concretely, as a patient tutor would. If a screenshot is attached it shows
what was on their screen at that moment (slide, code, diagram); use it. The flagged moment is at
{when}; the transcript below covers the time around it and may contain speech-to-text errors.

Transcript excerpt:
{excerpt}

Reply with: a 1-2 sentence plain-language answer first, then a short explanation. If the excerpt
is too thin to tell what was confusing, say so briefly instead of guessing."""


def window_text(transcript, t):
    """Join transcript segments within CONTEXT_SECONDS of timestamp t."""
    lo, hi = t - config.CONTEXT_SECONDS, t + config.CONTEXT_SECONDS
    return " ".join(s["text"] for s in transcript if s["end"] >= lo and s["start"] <= hi)


def explain_flag(transcript, flag, session_dir, ask=llm.ask, language="en"):
    t = flag["timestamp"]
    shot = Path(session_dir) / "screenshots" / flag["screenshot"] if flag.get("screenshot") else None
    excerpt = window_text(transcript, t) or "(no speech was transcribed around this moment)"
    prompt = PROMPT.format(when=fmt(t), excerpt=excerpt) + instruction(language)
    return ask(prompt, image_path=shot if shot and shot.exists() else None)


def explain_session(session_dir, ask=llm.ask):
    """Explain every flag in a session; saves explanations.json and returns it."""
    session_dir = Path(session_dir)
    transcript = json.loads((session_dir / "transcript_final.json").read_text())
    log_path = session_dir / "confusion_log.json"
    flags = json.loads(log_path.read_text()) if log_path.exists() else []
    language = load_language(session_dir)
    results = [{"timestamp": f["timestamp"], "explanation": explain_flag(transcript, f, session_dir, ask, language)}
               for f in flags]
    (session_dir / "explanations.json").write_text(json.dumps(results, indent=2))
    return results
