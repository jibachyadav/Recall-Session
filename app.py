"""Launch the Recall-Session desktop app:  .venv/bin/python app.py

`app.py --self-test` checks that the packaged program has everything it needs (used by the build scripts)."""
import sys


def self_test():
    """Load every heavy library the way the app does and transcribe one second of silence. No window, no data.
    Exits with a non-zero code on failure. Lines are also appended to the file named by RECALL_SELFTEST_LOG (the Windows
    program has no console to print to)."""
    import os
    log_path = os.environ.get("RECALL_SELFTEST_LOG")

    def say(text):
        print(text)
        if log_path:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(text + "\n")

    try:
        _self_test(say)
    except Exception as e:
        say(f"SELF-TEST FAILED: {type(e).__name__}: {e}")
        sys.exit(1)


def _self_test(say):
    import numpy
    import av  # noqa: F401
    import onnxruntime  # noqa: F401
    import anthropic  # noqa: F401
    import pypdf, docx, send2trash  # noqa: F401,E401
    import tkinter
    from src import models
    say(f"libraries: ok (tk {tkinter.TkVersion})")
    from faster_whisper import vad
    say("voice detector file: " + ("ok" if vad.get_assets_path() else "MISSING"))
    name = models.required()[0]
    if models.is_downloaded(name):
        from src import transcribe
        segments, _ = transcribe.get_model(name).transcribe(numpy.zeros(16000, dtype="float32"))
        list(segments)
        say(f"model {name}: ok")
    else:
        say(f"model {name}: not downloaded (skipped)")
    say("SELF-TEST OK")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        from src.app import main
        main()
