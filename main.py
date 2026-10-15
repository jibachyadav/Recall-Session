"""Recall-Session entry point.

Usage:
    python main.py record "<subject>"               # live side panel; Flag button or f flags
    python main.py record "<subject>" --no-panel    # terminal only: f flags, Enter stops
    python main.py record "<subject>" --system-audio  # record what plays (YouTube, Zoom), not the mic
    python main.py record "<subject>" --lang ne     # read in Nepali (en = English); asks if omitted
    python main.py transcribe <session_dir>
    python main.py explain <session_dir>     # needs ANTHROPIC_API_KEY
    python main.py summarize <session_dir>   # needs ANTHROPIC_API_KEY
    python main.py process <session_dir>     # transcribe + summarize + explain + build notes
"""
import sys
from datetime import date

import config
from src import auth
from src import llm
from src.hotkey_logger import FlagLogger, run_until_stop
from src import quiet
from src.language import choose_language, save_settings
from src.record import Recorder


def new_session_dir(subject):
    slug = "-".join(subject.lower().split()) or "class"
    path = config.SESSIONS_DIR / f"{date.today().isoformat()}_{slug}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def record(subject, panel=True, system_audio=False, language=None):
    language = language or choose_language()
    session = new_session_dir(subject)
    save_settings(session, language=language)
    if language != "en" and not llm.available():
        print("\n!! Nepali needs ANTHROPIC_API_KEY, and none is set. You will get English.\n"
              "!! Stop now (Ctrl+C), run: export ANTHROPIC_API_KEY=your_key  and start again.\n")
    source = config.SYSTEM_AUDIO_SOURCE if system_audio else config.AUDIO_SOURCE
    rec = Recorder(session / "recording.wav", live=panel, source=source)
    rec.start()
    quiet.mute()
    logger = FlagLogger(rec, session)
    live = None
    print(f"Recording to {rec.out_path}")
    try:
        if panel:
            from src.live import LiveTranscriber
            import tkinter as tk
            from src.live_panel import LivePanel

            live = LiveTranscriber(rec, language)
            live.start()
            root = tk.Tk()
            root.title("Recall-Session")
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            root.geometry(f"{config.PANEL_WIDTH}x{sh - 80}+{sw - config.PANEL_WIDTH}+0")
            root.attributes("-topmost", True)
            LivePanel(root, logger, live.events, on_stop=root.destroy, context=live.recent_text,
                      elapsed=rec.elapsed).pack(fill="both", expand=True)
            root.after(int(config.MAX_RECORDING_SECONDS * 1000), root.destroy)  # stop at the limit
            root.mainloop()  # returns when the window closes
        else:
            print(f"Press [{config.FLAG_KEY}] when confused, [Enter] to stop.")
            run_until_stop(logger)
    except KeyboardInterrupt:
        pass
    finally:
        rec.stop()
        quiet.restore()
        if live is not None:
            live.save(session, complete=live.finish(timeout=30))
    print(f"Saved {rec.out_path} ({rec.elapsed():.1f}s), {len(logger.flags)} flag(s)")
    process_cmd(session)


def transcribe_cmd(session_dir):
    from src.transcribe import transcribe_session  # imported here: loading Whisper is slow

    segments = transcribe_session(session_dir)
    for seg in segments:
        print(f"[{seg['start']:7.2f} - {seg['end']:7.2f}] {seg['text']}")
    print(f"{len(segments)} segment(s) saved to {session_dir}/transcript_final.json")


def explain_cmd(session_dir):
    from src import llm
    from src.explain import explain_session
    from src.hotkey_logger import fmt

    if not llm.available():
        sys.exit("Set ANTHROPIC_API_KEY first.")
    for item in explain_session(session_dir):
        print(f"\n=== {fmt(item['timestamp'])} ===\n{item['explanation']}")


def summarize_cmd(session_dir):
    from src import llm
    from src.summarize import summarize_session

    if not llm.available():
        sys.exit("Set ANTHROPIC_API_KEY first.")
    print(summarize_session(session_dir))


def process_cmd(session_dir):
    from src.build_notes import process_session

    process_session(session_dir)


def main():
    if auth.has_users():        # the command line saves into a user's own folder, so it needs someone signed in
        user = auth.remembered_user()
        if user is None:
            sys.exit("Open the app, log in and tick 'Keep me signed in on this computer', then try again.")
        auth.use(user)
    config.SESSIONS_DIR.mkdir(exist_ok=True)
    if len(sys.argv) >= 3 and sys.argv[1] == "record":
        flags = sys.argv[3:]
        lang = flags[flags.index("--lang") + 1] if "--lang" in flags and flags.index("--lang") + 1 < len(flags) else None
        if lang is not None and lang not in config.LANGUAGES:
            sys.exit(f"--lang must be one of: {', '.join(config.LANGUAGES)}")
        record(sys.argv[2], panel="--no-panel" not in flags, system_audio="--system-audio" in flags, language=lang)
    elif len(sys.argv) == 3 and sys.argv[1] == "transcribe":
        transcribe_cmd(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "explain":
        explain_cmd(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "summarize":
        summarize_cmd(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "process":
        process_cmd(sys.argv[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
