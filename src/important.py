"""Find the parts the teacher stresses as important.

Free mode: cue phrases ("this is important", "remember", "will be on the exam"...).
AI mode (needs Claude credit): Claude picks the segments the teacher stresses.
"""
import json
import re
from pathlib import Path

from src import llm

CUES = re.compile(
    r"\b(important|importantly|remember|don'?t forget|note that|keep in mind|key (point|idea|thing|concept)|"
    r"the main (point|idea|thing)|make sure|pay attention|crucial|critical|essential|"
    r"you (need|have|must|should) to (know|understand|remember)|(on|in) the (exam|test|quiz|final|midterm)|"
    r"will be asked|takeaway|take away|in (summary|conclusion)|to summari[sz]e|the definition|is defined as|"
    r"most important|big idea)\b", re.IGNORECASE)


def split_important(text):
    """[(sentence, is_important)] using the free cue phrases."""
    pieces = re.split(r"(?<=[.!?])\s+", text.strip())
    return [(p, bool(CUES.search(p))) for p in pieces if p]


def free_important(segments):
    return {i for i, s in enumerate(segments) if CUES.search(s["text"])}


def ai_important(segments, ask=llm.ask, batch=80):
    """Ask Claude which numbered segments the teacher stresses; returns a set of indices."""
    found = set()
    for i in range(0, len(segments), batch):
        part = segments[i:i + batch]
        numbered = "\n".join(f"{n}|{s['text']}" for n, s in enumerate(part, i))
        reply = ask("Below are numbered lines from a lecture transcript. List the numbers of the lines "
                    "where the teacher states something important: a key idea, definition, rule, "
                    "formula, warning, or something they say to remember or that will be tested. "
                    "Pick only the clearly important ones (at most one in five lines). "
                    "Reply with the numbers only, comma-separated, or NONE.\n\n" + numbered, max_tokens=300)
        found |= {int(n) for n in re.findall(r"\d+", reply) if i <= int(n) < i + len(part)}
    return found


def important_session(session_dir, ask=llm.ask, use_ai=True):
    """Compute and save important.json; returns the set of important segment indices."""
    session_dir = Path(session_dir)
    segments = json.loads((session_dir / "transcript_final.json").read_text())
    source, indices = "free", None
    if use_ai and (ask is not llm.ask or llm.available()):
        try:
            indices, source = ai_important(segments, ask), "ai"
        except Exception:
            indices = None  # fall back to the free cues
    if indices is None:
        indices = free_important(segments)
    (session_dir / "important.json").write_text(json.dumps({"source": source, "indices": sorted(indices)}))
    return indices


def load_important(session_dir):
    path = Path(session_dir) / "important.json"
    return set(json.loads(path.read_text())["indices"]) if path.exists() else set()
