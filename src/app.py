"""The Recall-Session desktop app: Home -> Recording -> Processing -> Result."""
import json
import queue
import shutil
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from datetime import date
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import config
from src import dashboard, llm, quiet, theme
from src.theme import (ACCENT, DANGER, DARK_TEXT, FONT, HIGHLIGHT_FLAG, HIGHLIGHT_KEY, INK, MUTED, SURFACE, SURFACE_HI, mix,
                       render_markdown)
from src.language import save_settings
from src import auth, documents, filechooser, osdep, settings, setup_ui, transcribe, translate
from src.auth_ui import AuthFlow
from src.build_notes import process_session
from src.hotkey_logger import FlagLogger, fmt
from src.live import LiveTranscriber
from src.live_panel import LivePanel
from src.record import Recorder
from src.important import load_important
from src.transcript_view import merge_runs, paragraphs

SOURCES = {
    "mic": ("Live class (online or in the room)", [config.SYSTEM_AUDIO_SOURCE, config.AUDIO_SOURCE]),
    "system": ("Video playing on this computer", config.SYSTEM_AUDIO_SOURCE),
}


def new_session_dir(name):
    slug = "-".join(name.lower().split()) or "class"
    path = config.SESSIONS_DIR / f"{date.today().isoformat()}_{slug}"
    n = 2
    while path.exists():  # never overwrite an earlier recording of the same name
        path = config.SESSIONS_DIR / f"{date.today().isoformat()}_{slug}-{n}"
        n += 1
    path.mkdir(parents=True)
    return path


class App:
    def __init__(self):
        self.root = tk.Tk(className="Recall-Session")
        theme.apply(self.root)
        self.root.title("Recall-Session")
        self.frame = None
        self.rec = None
        quiet.restore()  # if an earlier run crashed while muted, put the sounds back
        self.user = None
        self.auth_flow = AuthFlow(self, self.signed_in)
        self.dash_state = {"open": None}  # which category's previous work is expanded
        self.start_up()

    # ---- accounts -----------------------------------------------------------
    def start_up(self):
        """First screen: straight in for someone who chose 'keep me signed in', else log in / register."""
        if not getattr(self, "_setup_done", False) and setup_ui.needed():
            return self.show_setup()
        try:
            osdep.ensure_data_dir()
            osdep.migrate_legacy_data()             # one-time: bring older data from the program folder
            remembered = auth.remembered_user()
            if remembered:
                return self.signed_in(remembered)
            if auth.has_users():
                return self.auth_flow.show_login()
        except auth.AuthError as e:
            messagebox.showerror("Accounts problem", str(e))
            return self.root.after(100, self.root.destroy)
        self.auth_flow.show_register()          # nobody has an account yet

    def show_setup(self):
        """First run only: download the speech models, then carry on to login."""
        def done():
            self._setup_done = True
            self.start_up()
        self._show(setup_ui.build(self.root, done), self._center(560, 520))

    def signed_in(self, user):
        self.user = user
        auth.use(user)                          # from here on, everything is saved in this user's own folder
        self.dash_state["open"] = None
        self.show_home()

    def log_out(self):
        auth.logout()
        self.user = None
        self.dash_state["open"] = None
        self.root.geometry(self._center(760, 700))
        if auth.has_users():
            self.auth_flow.show_login()
        else:
            self.auth_flow.show_register()      # the last account was just deleted

    def show_account(self):
        self.auth_flow.show_account(self.user, self.show_home, self.log_out)

    # ---- screen switching -------------------------------------------------
    def _show(self, frame, geometry):
        if self.frame is not None:
            self.frame.destroy()
        self.frame = frame
        frame.pack(fill="both", expand=True)
        self.root.geometry(geometry)

    def _center(self, w, h):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        return f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}"

    # ---- 1. home (dashboard) ----------------------------------------------
    def show_home(self):
        if self.user is None:               # never show anyone's data without a login
            return self.start_up()
        self._show(dashboard.build(self.root, self.start, self.open_session, self.delete_sessions, self.dash_state,
                                   user=self.user, on_account=self.show_account, on_logout=self.log_out),
                   self._center(dashboard.WIDTH_START, dashboard.HEIGHT_START))

    def delete_sessions(self, sessions):
        """Move the chosen sessions' folders to the Trash (recoverable) after one confirmation."""
        if not sessions:
            return
        what = f"\"{sessions[0]['title']}\"" if len(sessions) == 1 else f"these {len(sessions)} sessions"
        if not messagebox.askyesno("Delete", f"Delete {what}?\n\nRecordings, transcripts and notes "
                                             "move to the Trash, where you can restore them."):
            return
        errors = []
        for s in sessions:
            path = s["path"].resolve()
            if path.parent != config.SESSIONS_DIR.resolve():  # only ever touch folders inside sessions/
                errors.append(f"{s['title']}: outside the sessions folder")
                continue
            try:
                osdep.move_to_trash(path)
            except OSError as e:
                errors.append(f"{s['title']}: {str(e) or 'moving to Trash failed'}")
        if errors:
            messagebox.showerror("Some sessions were not deleted", "\n".join(errors))
        self.show_home()

    # ---- 2. recording -----------------------------------------------------
    def start(self, kind, title, spoken="auto"):
        """kind: "live" (microphone) or "video" (YouTube, Zoom, anything playing on this computer)."""
        if kind == "document":
            return self.start_document()
        if kind != "live" or not config.LIVE_REQUIRE_CALL or not osdep.call_detection_supported():
            return self._begin(kind, title, spoken)       # (on a system that can't detect calls, don't block)
        # A live session needs an online class: a meeting app using the microphone and the speakers.
        app = quiet.call_running()
        if app:
            return self._begin(kind, title, spoken)
        self._wait_for_class(title, spoken)

    def start_document(self):
        """Choose a PDF / Word / text file with the desktop's file chooser, then open it."""
        if getattr(self, "_choosing", False) and time.time() - self._choosing_since < 120:
            return      # a chooser is already open (the lock lifts by itself after 2 minutes, just in case)
        self._choosing, self._choosing_since = True, time.time()
        result = queue.Queue()
        filechooser.choose_document_async(result.put)

        def wait():
            try:
                path = result.get_nowait()
            except queue.Empty:
                return self.root.after(200, wait)
            self._choosing = False      # allow the next click, whatever happened
            if path is None:       # no desktop chooser available: use Tk's own
                path = filedialog.askopenfilename(
                    parent=self.root, title="Choose a PDF, Word or text file",
                    filetypes=[("Documents", "*.pdf *.docx *.txt *.md"), ("All files", "*.*")])
            self._open_document(path)

        wait()

    def _open_document(self, path):
        if not path:
            return
        try:
            session = documents.prepare_document(path)
        except documents.DocumentError as e:
            return messagebox.showinfo("Can't read this file", str(e))
        self.show_document_result(session)

    def _wait_for_class(self, title, spoken):
        """Wait up to LIVE_WAIT_SECONDS for a Zoom/Teams/Meet call; start as soon as one begins."""
        win = tk.Toplevel(self.root)
        win.title("Live session")
        win.transient(self.root)
        win.resizable(False, False)
        win.configure(bg=SURFACE)
        tk.Label(win, text="Waiting for your online class", font=(FONT, 14, "bold"), bg=SURFACE
                 ).pack(anchor="w", padx=24, pady=(22, 2))
        tk.Label(win, text="Join your Zoom, Teams or Meet call. Recording begins by itself as soon as the call is running.",
                 font=(FONT, 10), bg=SURFACE, fg=MUTED, wraplength=360, justify="left"
                 ).pack(anchor="w", padx=24)
        bar = ttk.Progressbar(win, mode="indeterminate", length=360)
        bar.pack(padx=24, pady=16)
        bar.start(12)
        state = {"cancelled": False, "result": queue.Queue()}

        def cancel():
            state["cancelled"] = True
            win.destroy()

        tk.Button(win, text="Cancel", command=cancel, relief="flat", padx=14, pady=4).pack(anchor="e", padx=24, pady=(0, 18))
        win.protocol("WM_DELETE_WINDOW", cancel)
        win.update_idletasks()
        win.geometry(f"+{self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_width()) // 2}"
                     f"+{self.root.winfo_rooty() + 200}")

        def listen():
            deadline = time.time() + config.LIVE_WAIT_SECONDS
            while not state["cancelled"] and time.time() < deadline:
                if quiet.call_running():
                    state["result"].put("call"); return
                time.sleep(1.5)
            state["result"].put(None if not state["cancelled"] else "cancelled")

        threading.Thread(target=listen, daemon=True).start()

        def poll():
            if state["cancelled"] or not win.winfo_exists():
                return
            try:
                result = state["result"].get_nowait()
            except queue.Empty:
                return win.after(300, poll)
            win.destroy()
            if result == "call":
                self._begin("live", title, spoken)
            else:
                messagebox.showinfo("No online class found",
                                    "I couldn't find a Zoom, Teams or Meet call, so nothing was recorded.\n\n"
                                    "Join your class first: the call must be using your microphone and playing "
                                    "sound on this computer. Then press Start again.\n\n"
                                    "Watching a video instead? Use the \"YouTube video\" card.")

        poll()

    def _begin(self, kind, title, spoken):
        source = "mic" if kind == "live" else "system"
        session = new_session_dir(title or kind.title())
        save_settings(session, type=kind, title=title or kind.title(), spoken=spoken)
        self.rec = Recorder(session / "recording.wav", live=True, source=SOURCES[source][1])
        try:
            self.rec.start()
        except RuntimeError as e:
            messagebox.showerror("Cannot record", str(e))
            session.rmdir() if not any(session.iterdir()) else None
            return
        quiet.mute()  # no shutter sound when you flag
        logger = FlagLogger(self.rec, session)
        live = LiveTranscriber(self.rec, "en", spoken=spoken)
        live.start()
        self.live = live
        self.session = session
        panel = LivePanel(self.root, logger, live.events, on_stop=self.stop,
                          context=live.recent_text, elapsed=self.rec.elapsed, teacher=(kind == "live"))
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self._show(panel, f"{config.PANEL_WIDTH}x{sh - 80}+{sw - config.PANEL_WIDTH}+0")
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self.stop)
        self.warned = False
        self.root.after(1000, self._check_limit)

    def _check_limit(self):
        """Warn shortly before MAX_RECORDING_SECONDS, then stop by itself at the limit."""
        if self.frame is None or not isinstance(self.frame, LivePanel):
            return  # already stopped
        left = config.MAX_RECORDING_SECONDS - self.rec.elapsed()
        if left <= 0:
            return self.stop()
        if left <= config.RECORDING_WARNING_SECONDS and not self.warned:
            self.warned = True
            self.frame.status.config(text=f"Recording stops automatically in {int(left // 60) + 1} min")
        self.root.after(1000, self._check_limit)

    def stop(self):
        self.root.attributes("-topmost", False)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        if isinstance(self.frame, LivePanel):  # keep the questions and answers for the notes
            save_json = json.dumps(self.frame.ask.export(), indent=2)
            (self.session / "qa.json").write_text(save_json)
        self.rec.stop()
        quiet.restore()
        self.show_processing()

    # ---- 3. processing ----------------------------------------------------
    def show_processing(self):
        f = tk.Frame(self.root)
        tk.Label(f, text="Making your notes...", font=(FONT, 14, "bold")).pack(pady=(40, 10))
        bar = ttk.Progressbar(f, mode="indeterminate", length=300)
        bar.pack()
        bar.start(12)
        log = tk.Label(f, text="", fg=MUTED, wraplength=420, justify="left")
        log.pack(pady=14, padx=20)
        self._show(f, self._center(480, 220))
        q = queue.Queue()
        threading.Thread(target=lambda: self._work(q), daemon=True).start()

        def poll():
            if not f.winfo_exists():
                return
            try:
                while True:
                    kind, value = q.get_nowait()
                    if kind == "log":
                        log.config(text=value)
                    else:
                        return self.show_result(self.session)
            except queue.Empty:
                pass
            f.after(300, poll)

        poll()

    def _work(self, q):
        try:
            live = getattr(self, "live", None)
            if live is not None:
                q.put(("log", "Finishing the live transcript..."))
                live.save(self.session, complete=live.finish(timeout=30))
                self.live = None
            process_session(self.session, log=lambda m: q.put(("log", m)))
        except Exception as e:
            q.put(("log", f"Error: {e}"))
        q.put(("done", None))

    def open_session(self, session):
        """Open a saved session; if it was never finished (app closed mid-way), finish it first."""
        meta = session / "session.json"
        kind = json.loads(meta.read_text()).get("type") if meta.exists() else None
        if kind == "document":
            return self.show_document_result(session)
        if (session / "notes_final.md").exists():
            return self.show_result(session)
        self.session = session
        self.show_processing()

    def edit_transcript(self, session):
        """Editor: one line per transcript segment. Saving rebuilds the summary, highlights and notes."""
        path = session / "transcript_final.json"
        if not path.exists():
            return messagebox.showinfo("Edit transcript", "This class has no transcript yet.")
        segs = json.loads(path.read_text())
        win = tk.Toplevel(self.root)
        win.title("Edit transcript")
        win.geometry("820x600")
        win.transient(self.root)
        tk.Label(win, text="Fix any mistakes. Keep one line per sentence: don't add or delete lines.",
                 fg=MUTED).pack(anchor="w", padx=12, pady=(10, 4))
        box = ScrolledText(win, wrap="word", font=(FONT, 11), undo=True, padx=8, pady=6)
        box.pack(fill="both", expand=True, padx=12)
        box.insert("1.0", "\n".join(s["text"].replace("\n", " ") for s in segs))
        note = tk.Label(win, text="", fg=DANGER)
        note.pack(anchor="w", padx=12)

        def save():
            lines = box.get("1.0", "end-1c").split("\n")
            if len(lines) != len(segs):
                note.config(text=f"The transcript has {len(segs)} lines but you have {len(lines)}. "
                                 "Put each sentence back on its own line.")
                return
            backup = session / "transcript_before_edit.json"
            if not backup.exists():  # keep the original once
                backup.write_text(path.read_text())
            path.write_text(json.dumps([{**s, "text": t.strip()} for s, t in zip(segs, lines)], indent=2))
            for stale in ("summary.md", "important.json", "explanations.json"):
                (session / stale).unlink(missing_ok=True)
            note.config(text="Saving...", fg=MUTED)
            win.update_idletasks()
            process_session(session, log=lambda m: None)
            win.destroy()
            self.show_result(session)

        row = tk.Frame(win)
        row.pack(fill="x", padx=12, pady=10)
        tk.Button(row, text="Save", command=save, bg=ACCENT["live"], fg=DARK_TEXT, relief="flat",
                  padx=16, pady=4).pack(side="right")
        tk.Button(row, text="Cancel", command=win.destroy, relief="flat", padx=12, pady=4).pack(side="right", padx=8)
        win.grab_set()

    # ---- 4. result --------------------------------------------------------
    def show_document_result(self, session):
        """The document screen: a Summarize button, and two tabs: Summary and Document (the full text)."""
        documents.repair_text(session)          # fixes a document saved earlier with broken line breaks
        meta = json.loads((session / "session.json").read_text())
        f = tk.Frame(self.root)
        top = tk.Frame(f)
        top.pack(fill="x", padx=14, pady=(12, 2))
        tk.Label(top, text=meta.get("title", session.name), font=(FONT, 14, "bold")).pack(side="left")
        tk.Button(top, text="← Dashboard", command=self.show_home).pack(side="right")

        bar = tk.Frame(f)
        bar.pack(fill="x", padx=14, pady=(4, 8))
        has_summary = (session / "summary.md").exists()
        go = tk.Button(bar, text="Summarize again" if has_summary else "Summarize", bg=ACCENT["document"], fg=DARK_TEXT,
                       relief="flat", font=(FONT, 12, "bold"), padx=18, pady=5, activebackground=mix(ACCENT["document"], "#ffffff", 0.2),
                       activeforeground=DARK_TEXT)
        go.pack(side="left")
        status = tk.Label(bar, text=f"{meta.get('words', 0):,} words", fg=MUTED, font=(FONT, 9))
        status.pack(side="left", padx=14)

        tabs = ttk.Notebook(f)
        tabs.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        boxes = {}
        for name in ("Summary", "Document"):
            box = ScrolledText(tabs, wrap="word", font=(FONT, 11), padx=12, pady=10, spacing3=6)
            tabs.add(box, text=name)
            boxes[name] = box
        text_file = session / "text.txt"
        boxes["Document"].insert("1.0", text_file.read_text() if text_file.exists() else "")
        boxes["Document"].config(state="disabled")
        summary_box = boxes["Summary"]
        def show_formatted(text):
            render_markdown(summary_box, text)

        if has_summary:
            show_formatted((session / "summary.md").read_text())
        else:
            summary_box.insert("1.0", "Press Summarize to get a summary of this document.\n\n"
                                      "The Document tab shows the full text.")
            summary_box.config(state="disabled")
        q = queue.Queue()
        state = {"running": False, "started": False}

        def write(text, replace=False):
            summary_box.config(state="normal")
            if replace:
                summary_box.delete("1.0", "end")
            summary_box.insert("end", text)
            summary_box.see("end")
            summary_box.config(state="disabled")

        def work():
            try:
                documents.process_document(session, progress=lambda m: q.put(("status", m)),
                                           on_token=lambda t: q.put(("token", t)))
                q.put(("done", None))
            except Exception as e:
                q.put(("error", f"Something went wrong ({type(e).__name__}). Please try again."))

        def start():
            if state["running"]:
                return
            if (session / "summary.md").exists() and not messagebox.askyesno(
                    "Summarize again", "Make a new summary?\n\nThe current summary will be replaced."):
                return
            for old in ("summary.md", "notes_final.md"):
                (session / old).unlink(missing_ok=True)
            state.update(running=True, started=False)
            go.config(state="disabled", text="Summarizing...")
            tabs.select(0)
            write("Reading the document...\n", replace=True)
            threading.Thread(target=work, daemon=True).start()

        def poll():
            if not f.winfo_exists():
                return
            try:
                while True:
                    kind, value = q.get_nowait()
                    if kind == "status":
                        status.config(text=value)
                    elif kind == "token":
                        if not state["started"]:
                            state["started"] = True
                            write("", replace=True)
                        write(value)
                    else:
                        state["running"] = False
                        go.config(state="normal", text="Summarize again")
                        m = json.loads((session / "session.json").read_text())
                        by = {"Claude": "Claude", "free local AI": "the free local AI", "offline": "the offline summarizer"}
                        if kind == "error":
                            write("\n" + value)
                            status.config(text=f"{m.get('words', 0):,} words")
                        else:
                            show_formatted((session / "summary.md").read_text())   # tidy headings and bullets
                            status.config(text=f"{m.get('words', 0):,} words  ·  summarized by "
                                               f"{by.get(m.get('summarized_by'), 'AI')}")
            except queue.Empty:
                pass
            f.after(150, poll)

        go.config(command=start)
        poll()
        self._show(f, self._center(860, 680))

    def show_result(self, session):
        f = tk.Frame(self.root)
        top = tk.Frame(f)
        top.pack(fill="x", padx=12, pady=10)
        meta = session / "session.json"
        title = (json.loads(meta.read_text()).get("title") if meta.exists() else None) or session.name
        tk.Label(top, text=title, font=(FONT, 13, "bold")).pack(side="left")
        tk.Button(top, text="← Dashboard", command=self.show_home).pack(side="right")
        tk.Button(top, text="Edit transcript", command=lambda: self.edit_transcript(session)).pack(side="right", padx=6)

        key = tk.Frame(f)
        key.pack(fill="x", padx=12)
        for color, label in ((HIGHLIGHT_FLAG, "You flagged it"), (HIGHLIGHT_KEY, "Stressed as important")):
            tk.Label(key, text="   ", bg=color).pack(side="left")
            tk.Label(key, text=label, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=(4, 16))
        info = json.loads(meta.read_text()) if meta.exists() else {}
        language = info.get("spoken_language", "en")
        source = info.get("english_source")
        if language != "en" and source in ("whisper", "none"):
            self._rough_english_bar(f, session, language, source)
        tabs = ttk.Notebook(f)
        tabs.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        def add_tab(title, text="", flag_runs=None):
            box = ScrolledText(tabs, wrap="word", font=(FONT, 11), padx=10, pady=8, spacing3=8)
            box.tag_config("important", background=HIGHLIGHT_KEY, foreground=DARK_TEXT)
            box.tag_config("flag", background=HIGHLIGHT_FLAG, foreground=DARK_TEXT)
            for para in flag_runs or []:
                for chunk, state in merge_runs(para):
                    box.insert("end", chunk + " ", state or "")
                box.insert("end", "\n\n")
            box.insert("end", text)
            box.config(state="disabled")
            tabs.add(box, text=title)
            return box

        summary = session / "summary.md"
        render_markdown(add_tab("Summary", ""),
                        summary.read_text() if summary.exists() else
                        ("There is no summary yet: it needs an English version of the speech.\n\n"
                         "Use the buttons above to make one." if source == "none" else
                         "No summary for this class. The full transcript is in the next tab."))
        log = session / "confusion_log.json"
        flags = json.loads(log.read_text()) if log.exists() else []
        tr = session / "transcript_final.json"
        segs = json.loads(tr.read_text()) if tr.exists() else []
        add_tab("Full transcript", "" if segs else "(no speech was transcribed)",
                paragraphs(segs, [x["timestamp"] for x in flags], load_important(session)))
        original = session / "transcript_original.json"
        if original.exists():                      # Nepali / Hindi: what was actually said, in its own language
            add_tab(f"Original ({config.LANGUAGE_NAMES.get(language, 'original')})", "",
                    paragraphs(json.loads(original.read_text()), [x["timestamp"] for x in flags]))
        add_tab(f"Flagged ({len(flags)})", "\n".join(fmt(x["timestamp"]) for x in flags)
                or "Nothing was flagged.")
        self._show(f, self._center(860, 680))

    def _rough_english_bar(self, parent, session, language, source):
        """A bar above the transcript. source "none": no English yet, make it with Claude or offline.
        source "whisper": the English was made offline and can be wrong; offer a better one."""
        name = config.LANGUAGE_NAMES.get(language, language)
        bar = tk.Frame(parent, bg=mix(SURFACE, "#ffb454", 0.14), highlightthickness=1,
                       highlightbackground=mix(SURFACE, "#ffb454", 0.5))
        bar.pack(fill="x", padx=12, pady=(0, 10))
        if source == "none":
            text = f"This {name} recording has no English version yet. The text below is in {name}."
        else:
            text = (f"The English text was made offline from {name} speech and can be wrong"
                    + (", sometimes very wrong." if language == "ne" else "."))
        tk.Label(bar, text=text, font=(FONT, 10, "bold"), bg=bar["bg"], fg=INK, anchor="w").pack(side="left", padx=12, pady=8)
        note = tk.Label(bar, text="", font=(FONT, 9), bg=bar["bg"], fg=MUTED)
        claude_button = tk.Button(bar, text="Translate with Claude" if source == "none" else "Improve with Claude",
                                  font=(FONT, 10, "bold"), padx=12, pady=4, bg=ACCENT["live"], fg=DARK_TEXT)
        claude_button.pack(side="right", padx=(4, 10), pady=6)
        offline_button = None
        if source == "none":
            offline_button = tk.Button(bar, text="Rough English (offline)", font=(FONT, 10), padx=12, pady=4,
                                       bg=SURFACE_HI, fg=INK)
            offline_button.pack(side="right", padx=4, pady=6)
        note.pack(side="right", padx=4)
        buttons = [b for b in (claude_button, offline_button) if b]

        def run(work, busy_text, busy_button, normal_text):
            """Do `work` in the background with all buttons off; reopen the result when it finishes."""
            for b in buttons:
                b.config(state="disabled")
            busy_button.config(text=busy_text)
            result = queue.Queue()

            def target():
                try:
                    work()
                    process_session(session, log=lambda m: None)          # rebuild summary, highlights and notes
                    result.put(None)
                except Exception as e:
                    result.put(str(e) if isinstance(e, (translate.TranslateError, ValueError))
                               else f"Something went wrong ({type(e).__name__}).")

            threading.Thread(target=target, daemon=True).start()

            def check():
                if not bar.winfo_exists():
                    return
                try:
                    problem = result.get_nowait()
                except queue.Empty:
                    return bar.after(300, check)
                if problem is None:
                    return self.show_result(session)
                for b in buttons:
                    b.config(state="normal")
                busy_button.config(text=normal_text)
                note.config(text="")
                messagebox.showinfo("Couldn't make the English", f"{problem}\n\nNothing was changed.")

            check()

        def improve():
            if not settings.has_key():
                return messagebox.showinfo("Add a Claude key first",
                                           "A better English version needs a Claude API key.\n\n"
                                           "Open Account, then AI features, paste your key and press Save key.")
            note.config(text="This can take a minute")
            run(lambda: translate.retranslate_session(session), "Translating...", claude_button, claude_button.cget("text"))

        def offline():
            import wave
            try:
                with wave.open(str(session / "recording.wav")) as w:
                    note.config(text=transcribe.offline_english_message(w.getnframes() / w.getframerate()))
            except Exception:
                note.config(text="This can take a few minutes")
            run(lambda: transcribe.make_offline_english(session), "Working...", offline_button, "Rough English (offline)")

        if offline_button:
            offline_button.config(command=offline)
        claude_button.config(command=improve)

    def run(self):
        self.root.mainloop()


def main():
    App().run()
