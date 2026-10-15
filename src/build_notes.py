"""Step 8: stitch everything into one notes_final.md, and run the whole post-class pipeline."""
import json
from pathlib import Path

import config
from src import llm
from src.language import load_language, translate_segments
from src.important import important_session, load_important
from src.free_summary import free_summary_session
from src.explain import explain_session, window_text
from src.hotkey_logger import fmt
from src.transcript_view import to_markdown
from src.summarize import summarize_session


def build_notes(session_dir):
    """Write notes_final.md from summary.md, explanations.json, confusion_log.json (all optional)."""
    session_dir = Path(session_dir)

    def load(name, default):
        p = session_dir / name
        return json.loads(p.read_text()) if p.exists() else default

    language = load_language(session_dir)
    transcript = load("transcript_final.json", [])
    shown = load(f"transcript_{language}.json", transcript)  # Nepali transcript if it exists
    flags = load("confusion_log.json", [])
    explanations = {e["timestamp"]: e["explanation"] for e in load("explanations.json", [])}
    summary_path = session_dir / "summary.md"
    summary = summary_path.read_text().strip() if summary_path.exists() else \
        "_No summary yet._"

    lines = [f"# Class notes: {session_dir.name}", "", "## Summary", "", summary, "",
             f"## Flagged moments ({len(flags)})", ""]
    if not flags:
        lines += ["_Nothing was flagged._", ""]
    for f in flags:
        t = f["timestamp"]
        lines += [f"### {fmt(t)}", ""]
        if f.get("screenshot"):
            lines += [f"![screen at {fmt(t)}](screenshots/{f['screenshot']})", ""]
        if t in explanations:
            lines += [explanations[t], ""]
        else:
            lines += ["_No explanation yet. Transcript around this moment:_", "",
                      f"> {window_text(transcript, t) or '(no speech transcribed)'}", ""]
    qa = load("qa.json", {})
    if qa.get("suggestions") or qa.get("qa") or qa.get("teacher"):
        lines += ["## Questions", ""]
        asked = [q for sug in qa.get("suggestions", []) for q in sug["questions"]]
        if asked:
            lines += ["**To ask the teacher**", ""] + [f"- {q}" for q in dict.fromkeys(asked)] + [""]
        for item in qa.get("teacher", []):
            lines += [f"**The teacher asked ({fmt(item['t'])}):** {item['question']}", "",
                      f"Suggested answer: {item['answer']}", f"_suggested by {item['by']}_", ""]
        for item in qa.get("qa", []):
            lines += [f"**You asked ({fmt(item['t'])}):** {item['question']}", "", item["answer"],
                      f"_answered by {item['by']}_", ""]
    lines += ["## Full transcript", "",
              "Yellow = what was being said when you pressed Flag. Green = stressed as important.", "",
              to_markdown(shown, [f["timestamp"] for f in flags], load_important(session_dir)) or "_(no speech was transcribed)_", ""]
    original = load("transcript_original.json", None)
    if original:                                   # Nepali / Hindi: keep what was actually said, in its own language
        name = config.LANGUAGE_NAMES.get(load("session.json", {}).get("spoken_language"), "original language")
        lines += ["", f"## Original transcript ({name})", "",
                  to_markdown(original, [f["timestamp"] for f in flags]) or "_(no speech was transcribed)_", ""]
    path = session_dir / "notes_final.md"
    path.write_text("\n".join(lines))
    return path


def process_session(session_dir, ask=llm.ask, log=print):
    """Transcribe (if needed), summarize + explain (if an API key exists), build the notes."""
    session_dir = Path(session_dir)
    live = session_dir / "transcript_live.json"
    settings = session_dir / "session.json"
    info = json.loads(settings.read_text()) if settings.exists() else {}
    live_ok = live.exists() and info.get("live_complete")
    # The live text is English only. For Nepali or Hindi the after-class pass is needed: it keeps the
    # original-language transcript and makes a better English version.
    english_speech = info.get("spoken", "auto") in ("auto", "en") and info.get("spoken_language", "en") == "en"
    if live_ok and english_speech and config.USE_LIVE_TRANSCRIPT and not (session_dir / "transcript_final.json").exists():
        log("Using the live transcript (instant)...")
        (session_dir / "transcript_final.json").write_text(live.read_text())
    if not (session_dir / "transcript_final.json").exists():
        from src.transcribe import transcribe_session

        log("Transcribing...")
        transcribe_session(session_dir)
    claude_ok = ask is not llm.ask or llm.available()
    if claude_ok:
        try:
            log("Summarizing...")
            summarize_session(session_dir, ask)
            log("Explaining flagged moments...")
            explain_session(session_dir, ask)
        except Exception as e:  # e.g. no API credit: still build the notes from what we have
            log(f"Claude step failed ({type(e).__name__}: {str(e)[:120]}). "
                "Building notes without summary/explanations.")
            claude_ok = False
    if not (session_dir / "summary.md").exists():  # no key, or Claude failed: use the free summary
        log("Making a free offline summary...")
        free_summary_session(session_dir)
    log("Finding important parts...")
    important_session(session_dir, ask, use_ai=claude_ok)
    language = load_language(session_dir)
    if language != "en" and not (session_dir / f"transcript_{language}.json").exists():
        english = json.loads((session_dir / "transcript_final.json").read_text())
        translated = translate_segments(english, language, ask)
        if translated is not english:
            (session_dir / f"transcript_{language}.json").write_text(json.dumps(translated, indent=2))
    path = build_notes(session_dir)
    log(f"Notes: {path}")
    return path
