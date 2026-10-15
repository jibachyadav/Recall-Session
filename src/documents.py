"""Summarize a PDF, Word or text file: extract the text, then summarize it.

Order of preference: Claude, then the free local AI, then the free offline summary.
"""
import json
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

import config
from src import assistant
from src.free_summary import free_summary

SUPPORTED = {".pdf", ".docx", ".txt", ".md"}
CHUNK_CHARS = 6000        # about 1,500 words per piece sent to the AI
SINGLE_PASS_WORDS = 5000  # up to this length the whole document goes to the AI in one call
MAX_CHUNKS = 40           # a very long book is summarized from its first ~60,000 words


class DocumentError(Exception):
    """The file can't be read: the message is safe to show to the user."""


def _words_per_line(text):
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return sum(len(ln.split()) for ln in lines) / len(lines) if lines else 0.0


def _pdf_text(path):
    """Read a PDF with several readers and keep the most natural-looking text.

    Some PDFs store every word separately, which one reader turns into one word per line;
    another reader (or its layout mode) keeps real lines. The best text has the most words per line."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    if reader.is_encrypted and not reader.decrypt(""):
        raise DocumentError("This PDF is password protected. Remove the password and try again.")
    candidates = []
    for mode in ("layout", None):
        try:
            candidates.append("\n\n".join((p.extract_text(extraction_mode=mode) if mode else p.extract_text()) or ""
                                           for p in reader.pages))
        except Exception:
            pass
    if shutil.which("pdftotext"):
        try:
            out = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True, timeout=60).stdout
            candidates.append(out)
        except Exception:
            pass
    candidates = [c for c in candidates if len(c.split()) >= 5] or candidates
    best = max(candidates, key=_words_per_line) if candidates else ""
    return reflow(best)


_BULLET = re.compile(r"^\s*(?:[-*•▪◦●○■□‣–—]|\(?\d{1,2}[.)]|[a-zA-Z][.)])\s+")


def reflow(text):
    """Join the broken lines inside each paragraph (PDF line breaks), keeping bullets and blank-line paragraphs."""
    paragraphs, current = [], []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if current:
                paragraphs.append(current)
                current = []
            continue
        if current and _BULLET.match(line):
            paragraphs.append(current)
            current = []
        current.append(line)
    if current:
        paragraphs.append(current)
    out = []
    for lines in paragraphs:
        joined = ""
        for line in lines:
            if joined.endswith("-") and not joined.endswith(" -") and line[:1].islower():
                joined = joined[:-1] + line               # hyphenated word split across lines
            else:
                joined = f"{joined} {line}".strip()
        out.append(joined)
    return "\n\n".join(out)


def _strip_latex(text):
    """Drop '{\\displaystyle ...}' blocks (copied math markup) that would clutter summaries."""
    while True:
        i = text.find("{\\displaystyle")
        if i < 0:
            return text
        depth, j = 0, i
        while j < len(text):
            depth += text[j] == "{"
            depth -= text[j] == "}"
            j += 1
            if depth == 0:
                break
        text = text[:i] + text[j:]


def extract_text(path):
    """Return the document's text. Raises DocumentError with a friendly message if it can't be read."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext not in SUPPORTED:
        raise DocumentError(f"I can read PDF, Word (.docx), .txt and .md files, not {ext or 'this type of file'}.")
    try:
        if ext == ".pdf":
            text = _pdf_text(path)
            if len(text.split()) < 20:
                raise DocumentError("This PDF has no readable text: it looks like scanned pictures of pages. "
                                    "I can't read scanned PDFs yet.")
        elif ext == ".docx":
            import docx

            document = docx.Document(str(path))
            parts = [p.text for p in document.paragraphs]
            for table in document.tables:
                parts += [" | ".join(c.text for c in row.cells) for row in table.rows]
            text = "\n".join(parts)
        else:
            text = path.read_text(errors="replace")
    except DocumentError:
        raise
    except FileNotFoundError as e:
        raise DocumentError("I can't find that file. It may have been moved or deleted.") from e
    except Exception as e:
        raise DocumentError(f"I couldn't open this file ({type(e).__name__}). It may be damaged.") from e
    text = _strip_latex(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text.split()) < 5:
        raise DocumentError("This file has almost no text to summarize.")
    return text


def chunk(text, size=CHUNK_CHARS):
    """Split at paragraph / sentence ends so a piece never stops in the middle of a sentence."""
    pieces, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+|\n\n", text):
        if current and len(current) + len(sentence) > size:
            pieces.append(current.strip())
            current = ""
        current += sentence + " "
    if current.strip():
        pieces.append(current.strip())
    return pieces


CHUNK_PROMPT = """Summarize this part of a document for a student. Give the main points as short bullets
and keep the definitions, numbers, names, dates and formulas that matter. Use ONLY facts stated in the text:
never add facts, examples or numbers from your own knowledge, and never guess. Leave out anything unclear.

{text}"""

SINGLE_PROMPT = """Summarize this document for a student, with exactly these three headings:
"### Overview" (2-3 sentences: what the document is and why it matters), "### Main Points" (grouped
bullets, no repeats, keeping the definitions, numbers, names, dates and formulas that matter) and
"### Key Terms" (a short list). Use ONLY facts stated in the text: never add facts or numbers from your own
knowledge and never guess.

{text}"""

COMBINE_PROMPT = """These are summaries of consecutive parts of one document. Combine them into a single
summary for a student with exactly these three headings: "### Overview" (2-3 sentences), "### Main Points"
(grouped bullets, no repeats), "### Key Terms" (a short list). Use ONLY what is stated in the summaries:
never add facts from your own knowledge, and drop anything that contradicts itself.

{text}"""


def _ask(prompt, max_tokens=400, on_token=None, num_ctx=None):
    """Claude if it works, otherwise the bigger free local model (documents favour accuracy over speed)."""
    return assistant.ask(prompt, max_tokens=max_tokens, model=config.DOCUMENT_MODEL, on_token=on_token,
                         num_ctx=num_ctx)


def summarize_text(text, ask=_ask, progress=lambda message: None, on_token=None):
    """Returns (summary_markdown, provider). Falls back to the free offline summary if no AI works.

    A document up to SINGLE_PASS_WORDS is summarized in one call, streamed to `on_token`;
    a longer one is summarized in parts and then combined."""
    source = text
    pieces = chunk(source)[:MAX_CHUNKS]
    try:
        if len(source.split()) <= SINGLE_PASS_WORDS or len(pieces) == 1:
            progress("Reading the document, then writing the summary...")
            return ask(SINGLE_PROMPT.format(text=source[:SINGLE_PASS_WORDS * 8]), max_tokens=700,
                       on_token=on_token, num_ctx=12288)
        parts, provider = [], None
        for i, piece in enumerate(pieces, 1):
            progress(f"Summarizing part {i} of {len(pieces)}...")
            answer, provider = ask(CHUNK_PROMPT.format(text=piece), max_tokens=400)
            parts.append(answer)
        progress("Putting the summary together...")
        joined = "\n\n".join(f"Part {i + 1}:\n{p}" for i, p in enumerate(parts))
        return ask(COMBINE_PROMPT.format(text=joined), max_tokens=900, on_token=on_token)
    except assistant.AIUnavailable:
        pass
    except Exception:
        pass   # a network / server problem must never lose the document
    progress("No AI available: making a basic offline summary...")
    sentences = [{"start": i, "end": i + 1, "text": s}
                 for i, s in enumerate(re.split(r"(?<=[.!?])\s+|\n+", text)) if s.strip()]
    result = free_summary(sentences, by_time=False, offline=False) + \
        "\n\n_Basic summary made offline (no AI): the most important sentences from the document._"
    if on_token:
        on_token(result)
    return result, "offline"


def new_document_session(source_path, title=None):
    """Create sessions/<date>_<name>/ with a copy of the file; returns the folder."""
    source_path = Path(source_path)
    title = title or source_path.stem
    slug = "-".join(re.sub(r"[^a-z0-9]+", " ", title.lower()).split()) or "document"
    base = config.SESSIONS_DIR / f"{date.today().isoformat()}_{slug}"
    session, n = base, 2
    while session.exists():
        session = Path(f"{base}-{n}")
        n += 1
    session.mkdir(parents=True)
    shutil.copy2(source_path, session / f"original{source_path.suffix.lower()}")
    (session / "session.json").write_text(json.dumps({"type": "document", "title": title,
                                                        "file": source_path.name}, indent=2))
    return session


def prepare_document(source_path):
    """Read the file and save it as a session WITHOUT summarizing (that happens when the user presses Summarize).

    Raises DocumentError for a file that can't be read. Returns the session folder."""
    text = extract_text(source_path)
    session = new_document_session(source_path)
    (session / "text.txt").write_text(text)
    meta = json.loads((session / "session.json").read_text())
    meta["words"] = len(text.split())
    (session / "session.json").write_text(json.dumps(meta, indent=2))
    return session


def save_summary(session, summary, provider):
    """Store a finished summary (summary.md + notes_final.md) and note who wrote it."""
    session = Path(session)
    (session / "summary.md").write_text(summary + "\n")
    meta = json.loads((session / "session.json").read_text())
    meta["summarized_by"] = provider
    (session / "session.json").write_text(json.dumps(meta, indent=2))
    (session / "notes_final.md").write_text(
        f"# {meta.get('title', session.name)}\n\n_{meta.get('words', 0):,} words, summarized by {provider}_\n\n"
        f"## Summary\n\n{summary}\n")


def process_document(session, ask=_ask, progress=lambda message: None, on_token=None):
    """Summarize a saved document session and save the result. Returns (summary, provider)."""
    session = Path(session)
    if not (session / "text.txt").exists():       # a session made before 'prepare' existed
        original = next(session.glob("original.*"))
        progress("Reading the document...")
        (session / "text.txt").write_text(extract_text(original))
    text = (session / "text.txt").read_text()
    summary, provider = summarize_text(text, ask, progress, on_token)
    save_summary(session, summary, provider)
    return summary, provider


def repair_text(session):
    """Re-read the original file if the saved text looks broken (e.g. one word per line). Returns True if fixed."""
    session = Path(session)
    text_file = session / "text.txt"
    original = next(session.glob("original.*"), None)
    if not text_file.exists() or original is None or original.suffix.lower() != ".pdf":
        return False
    if _words_per_line(text_file.read_text()) >= 4:
        return False
    try:
        fixed = extract_text(original)
    except DocumentError:
        return False
    if _words_per_line(fixed) <= _words_per_line(text_file.read_text()):
        return False
    text_file.write_text(fixed)
    meta_file = session / "session.json"
    meta = json.loads(meta_file.read_text())
    meta["words"] = len(fixed.split())
    meta_file.write_text(json.dumps(meta, indent=2))
    return True
