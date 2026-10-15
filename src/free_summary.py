"""Free offline summary: picks the most important sentences. No AI, no key, no internet.

Rougher than a Claude summary: it quotes sentences from the transcript instead of
rewriting them.
"""
import json
import re
from collections import Counter
from pathlib import Path

import config
from src.hotkey_logger import fmt

STOPWORDS = set("""a about above after again all also am an and any are as at be because been before being
below between both but by can could did do does doing down during each few for from further had has have
having he her here hers him his how i if in into is it its itself just let me more most my no nor not now
of off on once only or other our out over own same she should so some such than that the their them then
there these they this those through to too under until up us very was we were what when where which while
who whom why will with would you your yours yeah okay ok um uh like going gonna really get got say said
don didn doesn isn wasn won can't cannot one thing things know see look right well want think actually""".split())


def _sentences(transcript):
    """[(start_seconds, sentence)], sentences re-joined across segment breaks."""
    out, buf, buf_start = [], "", None
    for seg in transcript:
        if buf_start is None:
            buf_start = seg["start"]
        buf = f"{buf} {seg['text']}".strip()
        parts = re.split(r"(?<=[.!?])\s+", buf)
        for sentence in parts[:-1]:
            out.append((buf_start, sentence))
            buf_start = seg["end"]
        buf = parts[-1]
    if buf:
        out.append((buf_start if buf_start is not None else 0, buf))
    return out


def _words(text):
    words = re.findall(r"[a-zA-Z][a-zA-Z'-]+", text.lower())
    words = [re.sub(r"'(s|re|ll|ve|d|m|t)$", "", w) for w in words]  # we're -> we, that's -> that
    return [w for w in words if w not in STOPWORDS and len(w) > 2]


def _top(sentences, freq, n):
    """Indices of the n best sentences by average word importance, in original order."""
    scored = []
    for i, (_, s) in enumerate(sentences):
        words = _words(s)
        n_words = len(s.split())
        if not words or n_words < 6 or n_words > 45:
            continue
        scored.append((sum(freq[w] for w in words) / (len(words) ** 0.5), i))
    return sorted(i for _, i in sorted(scored, reverse=True)[:n])


def free_summary(transcript, by_time=True, offline=True):
    sentences = _sentences(transcript)
    if len(sentences) < 3:
        return "_The transcript is too short to summarize._"
    freq = Counter(w for _, s in sentences for w in _words(s))
    lines = ["_Basic summary made offline (no AI): the most important sentences from the "
             "transcript. For a written summary, add Claude API credit._", ""] if offline else []

    terms = [w for w, _ in freq.most_common(10)]
    lines += ["## Key terms", "", ", ".join(terms), ""]

    overview = _top(sentences, freq, max(3, min(6, len(sentences) // 8)))
    lines += ["## Main points", ""] + [f"- {sentences[i][1]}" for i in overview] + [""]

    last = sentences[-1][0]
    if by_time and last > config.FREE_SUMMARY_SECTION_SECONDS:
        lines += ["## By time", ""]
        start = 0.0
        while start <= last:
            idx = [i for i, (t, _) in enumerate(sentences)
                   if start <= t < start + config.FREE_SUMMARY_SECTION_SECONDS]
            sub = [sentences[i] for i in idx]
            if len(sub) >= 3:
                lines.append(f"**{fmt(start)}**")
                lines += [f"- {sub[j][1]}" for j in _top(sub, freq, 2)]
                lines.append("")
            start += config.FREE_SUMMARY_SECTION_SECONDS
    return "\n".join(lines).strip()


def free_summary_session(session_dir):
    session_dir = Path(session_dir)
    transcript = json.loads((session_dir / "transcript_final.json").read_text())
    text = free_summary(transcript)
    (session_dir / "summary.md").write_text(text + "\n")
    return text
