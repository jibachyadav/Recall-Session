"""Step 7: whole-class summary. Chunk the transcript, summarize each chunk, then combine."""
import json
from pathlib import Path

import config
from src import llm
from src.language import instruction, load_language

CHUNK_PROMPT = """Summarize this part of a lecture (speech-to-text, may contain errors).
List the main topics in order, key points, and any definitions or formulas, as short bullets.
Do not invent anything that is not in the text.

{text}"""

COMBINE_PROMPT = """These are summaries of consecutive parts of one lecture. Combine them into a
single ordered summary: a 2-3 sentence overview, then bullets for main topics, key points, and
definitions/formulas. Do not invent anything that is not in the summaries.

{text}"""


def chunk_transcript(transcript, chunk_seconds=None):
    """Group segments into chunks of about chunk_seconds of lecture time each."""
    chunk_seconds = chunk_seconds or config.SUMMARY_CHUNK_SECONDS
    chunks, current, chunk_start = [], [], None
    for seg in transcript:
        if chunk_start is None:
            chunk_start = seg["start"]
        if seg["start"] - chunk_start >= chunk_seconds and current:
            chunks.append(" ".join(current))
            current, chunk_start = [], seg["start"]
        current.append(seg["text"])
    if current:
        chunks.append(" ".join(current))
    return chunks


def summarize(transcript, ask=llm.ask, language="en"):
    chunks = chunk_transcript(transcript)
    if not chunks:
        return "(no speech was transcribed)"
    parts = [ask(CHUNK_PROMPT.format(text=c) + instruction(language), max_tokens=800) for c in chunks]
    if len(parts) == 1:
        return parts[0]
    joined = "\n\n".join(f"Part {i + 1}:\n{p}" for i, p in enumerate(parts))
    return ask(COMBINE_PROMPT.format(text=joined) + instruction(language), max_tokens=1500)


def summarize_session(session_dir, ask=llm.ask):
    """Summarize a session's transcript_final.json; saves and returns summary.md text."""
    session_dir = Path(session_dir)
    transcript = json.loads((session_dir / "transcript_final.json").read_text())
    summary = summarize(transcript, ask, load_language(session_dir))
    (session_dir / "summary.md").write_text(summary + "\n")
    return summary
