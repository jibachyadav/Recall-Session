"""Shared transcript layout: flowing paragraphs, flagged moments (yellow), important parts (green)."""
import config

FLAG_STYLE = "background-color:#ffe066"
IMPORTANT_STYLE = "background-color:#b7f0c0"


def is_flagged(start, end, flag_times):
    """True if the speech from start to end overlaps the highlight window of any flag."""
    return any(start <= t + config.FLAG_HIGHLIGHT_AFTER and end >= t - config.FLAG_HIGHLIGHT_BEFORE
               for t in flag_times)


def paragraphs(segments, flag_times=(), important=()):
    """Group segments into paragraphs: [[(text, state), ...], ...]; state is "flag", "important" or None."""
    out, current, words, prev_end = [], [], 0, None
    for i, seg in enumerate(segments):
        gap = None if prev_end is None else seg["start"] - prev_end
        ended = bool(current) and current[-1][0].rstrip().endswith((".", "?", "!"))
        if current and ((gap is not None and gap >= config.PARAGRAPH_GAP_SECONDS) or
                        (words >= config.PARAGRAPH_WORDS and ended) or words >= 2 * config.PARAGRAPH_WORDS):
            out.append(current)
            current, words = [], 0
        state = "flag" if is_flagged(seg["start"], seg["end"], flag_times) else \
            "important" if i in important else None
        current.append((seg["text"], state))
        words += len(seg["text"].split())
        prev_end = seg["end"]
    if current:
        out.append(current)
    return out


def merge_runs(paragraph):
    """Merge neighbouring pieces with the same state: [(text, state), ...]."""
    runs = []
    for text, state in paragraph:
        if runs and runs[-1][1] == state:
            runs[-1] = (f"{runs[-1][0]} {text}", state)
        else:
            runs.append((text, state))
    return runs


def to_markdown(segments, flag_times=(), important=()):
    """Paragraphs as markdown with inline highlights (shown in VS Code's Markdown preview)."""
    style = {"flag": FLAG_STYLE, "important": IMPORTANT_STYLE}
    blocks = []
    for para in paragraphs(segments, flag_times, important):
        blocks.append(" ".join(f'<span style="{style[s]}">{t}</span>' if s else t
                               for t, s in merge_runs(para)))
    return "\n\n".join(blocks)
