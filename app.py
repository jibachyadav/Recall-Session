"""Launch the Recall-Session desktop app:  .venv/bin/python app.py

`app.py --self-test` checks that the packaged program has everything it needs (used by the build scripts)."""
import sys


def self_test():
    """Load every heavy library the way the app does and transcribe one second of silence. No window, no data."""
    import numpy
    import av  # noqa: F401
    import onnxruntime  # noqa: F401
    import anthropic  # noqa: F401
    import pypdf, docx, send2trash  # noqa: F401,E401
    import tkinter
    from src import models
    print("libraries: ok (tk", tkinter.TkVersion, ")")
    from faster_whisper import vad
    print("voice detector file:", "ok" if vad.get_assets_path() else "MISSING")
    name = models.required()[0]
    if models.is_downloaded(name):
        from src import transcribe
        segments, _ = transcribe.get_model(name).transcribe(numpy.zeros(16000, dtype="float32"))
        list(segments)
        print(f"model {name}: ok")
    else:
        print(f"model {name}: not downloaded (skipped)")
    print("SELF-TEST OK")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        from src.app import main
        main()
