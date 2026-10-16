"""First-run screen: download the speech models the app needs, with a progress bar.

Shown once, before login, when the required models are not on this computer. The big Nepali/Hindi model is an
opt-in checkbox (1.6 GB); it can also be fetched later, the first time a Nepali or Hindi session is processed."""
import queue
import threading
import tkinter as tk
from tkinter import ttk

from src import models
from src.theme import ACCENT, DARK_TEXT, FONT, INK, MUTED, SURFACE


def needed():
    """True when the required models are missing (so the setup screen must be shown)."""
    return bool(models.missing(models.required()))


def build(root, on_done):
    """Return the frame for the setup screen. on_done() is called when the models are ready or the user skips."""
    f = tk.Frame(root)
    box = tk.Frame(f, bg=SURFACE)
    box.place(relx=0.5, rely=0.5, anchor="center")
    pad = dict(padx=34, anchor="w")
    tk.Label(box, text="Welcome to Recall-Session", font=(FONT, 18, "bold"), bg=SURFACE, fg=INK).pack(pady=(30, 4), **pad)
    tk.Label(box, text="One-time setup: the app needs to download its speech-recognition models. They are stored on "
                       "this computer, so after this, transcription works without internet.",
             font=(FONT, 10), bg=SURFACE, fg=MUTED, wraplength=440, justify="left").pack(pady=(0, 14), **pad)
    todo = models.missing(models.required())
    mb = sum(models.size_mb(n) for n in todo)
    tk.Label(box, text=f"Required: English speech models (about {mb} MB)", font=(FONT, 11, "bold"), bg=SURFACE, fg=INK
             ).pack(**pad)

    big = [n for n in models.optional() if not models.is_downloaded(n)]
    want_big = tk.BooleanVar(value=False)
    if big:
        tk.Checkbutton(box, text=f"Also download the Nepali / Hindi model (about {sum(models.size_mb(n) for n in big)} MB)",
                       variable=want_big, bg=SURFACE, fg=INK, selectcolor=SURFACE, activebackground=SURFACE,
                       activeforeground=INK, font=(FONT, 10)).pack(pady=(8, 0), **pad)
    bar = ttk.Progressbar(box, mode="determinate", length=440, maximum=100)
    status = tk.Label(box, text="", font=(FONT, 10), bg=SURFACE, fg=MUTED, wraplength=440, justify="left")
    buttons = tk.Frame(box, bg=SURFACE)
    state = {"cancel": False, "q": queue.Queue()}

    def finish():
        state["cancel"] = True
        on_done()

    def start():
        start_btn.config(state="disabled", text="Downloading...")
        skip_btn.config(text="Cancel", command=cancel)
        bar.pack(pady=(16, 4), **pad)
        status.pack(pady=(0, 6), **pad)
        names = list(todo) + (big if want_big.get() else [])

        def work():
            try:
                models.download(names, progress=lambda d, t, n: state["q"].put(("p", d, t, n)),
                                cancelled=lambda: state["cancel"])
                state["q"].put(("done",))
            except OSError as e:
                state["q"].put(("error", str(e)))

        threading.Thread(target=work, daemon=True).start()
        poll()

    def cancel():
        state["cancel"] = True
        skip_btn.config(state="disabled", text="Stopping...")

    def poll():
        if not f.winfo_exists():
            return
        try:
            while True:
                msg = state["q"].get_nowait()
                if msg[0] == "p":
                    _, d, t, n = msg
                    bar["value"] = 100 * d / max(t, 1)
                    status.config(text=f"{models.purpose(n).capitalize()}: {d:.0f} of {t:.0f} MB")
                elif msg[0] == "done":
                    return on_done()
                else:
                    status.config(text=msg[1], fg="#e5675d")
                    start_btn.config(state="normal", text="Try again")
                    skip_btn.config(state="normal", text="Skip for now", command=finish)
                    state["cancel"] = False
                    return
        except queue.Empty:
            pass
        f.after(300, poll)

    start_btn = tk.Button(buttons, text="Download and continue", command=start, bg=ACCENT["live"], fg=DARK_TEXT,
                          relief="flat", padx=16, pady=6, font=(FONT, 10, "bold"))
    skip_btn = tk.Button(buttons, text="Skip for now", command=finish, relief="flat", padx=14, pady=6, font=(FONT, 10))
    start_btn.pack(side="left")
    skip_btn.pack(side="left", padx=10)
    buttons.pack(pady=(18, 30), **pad)
    return f
