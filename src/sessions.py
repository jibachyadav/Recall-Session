"""Read saved sessions for the dashboard."""
import json
import wave
from datetime import datetime
from pathlib import Path

import config


def _duration(session):
    try:
        with wave.open(str(session / "recording.wav")) as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        return 0.0


def list_sessions():
    """Newest first: [{path, title, type, when, duration, flags, summary}]."""
    out = []
    if not config.SESSIONS_DIR.exists():
        return out
    for d in config.SESSIONS_DIR.iterdir():
        if not d.is_dir():
            continue
        meta = json.loads((d / "session.json").read_text()) if (d / "session.json").exists() else {}
        original = next(d.glob("original.*"), None)
        if meta.get("type") == "document" and original:
            out.append({"path": d, "title": meta.get("title") or d.name, "type": "document",
                        "when": datetime.fromtimestamp(original.stat().st_mtime), "duration": 0.0, "flags": 0,
                        "words": meta.get("words", 0), "summary": (d / "summary.md").exists(),
                        "done": True})
            continue
        if not (d / "recording.wav").exists():
            continue
        log = d / "confusion_log.json"
        when = datetime.fromtimestamp((d / "recording.wav").stat().st_mtime)
        out.append({
            "path": d,
            "title": meta.get("title") or d.name.split("_", 1)[-1].replace("-", " ").title(),
            "type": meta.get("type", "live"),
            "when": when,
            "duration": _duration(d),
            "flags": len(json.loads(log.read_text())) if log.exists() else 0,
            "summary": (d / "summary.md").exists(),
            "done": (d / "notes_final.md").exists(),
        })
    return sorted(out, key=lambda s: s["when"], reverse=True)


def fmt_duration(seconds):
    m = int(seconds // 60)
    return f"{m // 60}h {m % 60}m" if m >= 60 else f"{m}m" if m else f"{int(seconds)}s"
