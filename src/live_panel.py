"""Recording screen: live transcript, "now covering" line, Flag and Stop buttons."""
import queue
import tkinter as tk
from tkinter import scrolledtext, ttk

import config
from src.theme import ACCENT, DANGER, DARK_TEXT, FONT, HIGHLIGHT_FLAG, HIGHLIGHT_KEY, MUTED
from src.ask_panel import AskTab
from src.hotkey_logger import fmt
from src.important import split_important
from src.transcript_view import is_flagged


class LivePanel(tk.Frame):
    def __init__(self, parent, logger, events, on_stop, wraplength=380, context=None, elapsed=None, teacher=True):
        super().__init__(parent)
        self.logger = logger
        self.events = events
        self.on_stop = on_stop

        # "Now covering" stays hidden until the first line arrives (it needs Claude)
        self.cover = tk.Frame(self)
        tk.Label(self.cover, text="Now covering", font=(FONT, 9), fg=MUTED).pack(anchor="w", padx=10, pady=(10, 0))
        self.summary = tk.Label(self.cover, text="", font=(FONT, 12, "bold"),
                                wraplength=wraplength, justify="left")
        self.summary.pack(anchor="w", padx=10, pady=(0, 8))

        self.status = tk.Label(self, text="", fg=MUTED, anchor="w")
        self.status.pack(side="bottom", fill="x", padx=10)
        row = tk.Frame(self)
        row.pack(side="bottom", fill="x", padx=10, pady=10)
        tk.Button(row, text="⚑  I don't understand  (Flag)", command=self.on_flag, bg=HIGHLIGHT_FLAG, fg=DARK_TEXT,
                  activebackground="#ffe48a", activeforeground=DARK_TEXT, font=(FONT, 12, "bold"),
                  pady=10).pack(side="left", fill="x", expand=True)
        tk.Button(row, text="Stop", command=self.on_stop, font=(FONT, 12, "bold"), padx=18, pady=10,
                  bg=DANGER, fg=DARK_TEXT, activebackground="#ff8a9a", activeforeground=DARK_TEXT
                  ).pack(side="right", padx=(8, 0))
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=10)
        self.text = scrolledtext.ScrolledText(self.tabs, wrap="word", font=(FONT, 11), state="disabled", height=8, padx=12, pady=10, spacing3=4)
        self.text.tag_config("important", background=HIGHLIGHT_KEY, foreground=DARK_TEXT)
        self.text.tag_config("draft", foreground=MUTED)     # rough draft, replaced by the accurate text
        self.text.tag_config("flag", background=HIGHLIGHT_FLAG, foreground=DARK_TEXT)
        self.text.tag_raise("flag")
        self.chunks = {}      # chunk start (s) -> (end_s, n); text positions are Text marks s{n} / e{n}
        self.flag_times = []
        self.words = 0        # words in the current paragraph
        self.tabs.add(self.text, text="Transcript")
        self.ask = AskTab(self.tabs, context or (lambda seconds: ""), elapsed or (lambda: 0.0), self._teacher_asked, teacher)
        self.tabs.add(self.ask, text="Ask")
        self.tabs.bind("<<NotebookTabChanged>>", lambda e: self.tabs.tab(self.ask, text="Ask"))

        self.bind("<f>", lambda e: self.on_flag())
        self.focus_set()
        self.after(200, self.poll)

    def _teacher_asked(self, question):
        """The teacher asked something: point at the Ask tab (and open it, if configured)."""
        self.status.config(text="Teacher asked a question: see the Ask tab")
        if config.ASK_AUTO_SWITCH:
            self.tabs.select(self.ask)
        else:
            self.tabs.tab(self.ask, text="Ask  ●")

    def on_flag(self):
        t, ok = self.logger.flag()
        self.status.config(text=f"Flagged {fmt(t)}" + ("" if ok else " (screenshot failed)"))
        self.flag_times.append(t)
        for start, (end, n) in self.chunks.items():  # highlight speech already on screen
            if is_flagged(start, end, [t]):
                self.text.tag_add("flag", f"s{n}", f"e{n}")

    def _render(self, n, text, start, end, draft):
        """(Re)write chunk n between its marks, with important sentences green and flags yellow."""
        w, a, b = self.text, f"s{n}", f"e{n}"
        w.config(state="normal")
        w.delete(a, b)
        pos = w.index(a)
        for i, (sentence, important) in enumerate(split_important(text)):
            piece = ("" if i == 0 else " ") + sentence
            tags = ("draft",) if draft else (("important",) if important else ())
            w.insert(pos, piece, tags)
            pos = w.index(f"{pos}+{len(piece)}c")
        w.mark_set(b, pos)
        if is_flagged(start, end, self.flag_times):
            w.tag_add("flag", a, b)
        w.config(state="disabled")

    def _add_chunk(self, start, text, end=None, draft=False):
        """Append speech to the running paragraph; new paragraph after ~PARAGRAPH_WORDS."""
        end = end if end is not None else start + config.LIVE_MAX_CHUNK_SECONDS
        w = self.text
        w.config(state="normal")
        before = w.get("1.0", "end-1c")
        if self.words >= config.PARAGRAPH_WORDS and before.rstrip().endswith((".", "?", "!")):
            w.insert("end", "\n\n")
            self.words = 0
        elif before:
            w.insert("end", " ")
        n = len(self.chunks)
        pos = w.index("end-1c")
        for mark in (f"s{n}", f"e{n}"):
            w.mark_set(mark, pos)
            w.mark_gravity(mark, "left")
        self.chunks[start] = (end, n)
        w.config(state="disabled")
        self._render(n, text, start, end, draft)
        self.words += len(text.split())
        w.see("end")

    def _update_chunk(self, start, text, end, draft=False):
        """Replace a chunk's text (a longer draft, or the accurate text) and move its end."""
        if start in self.chunks:
            n = self.chunks[start][1]
            self.chunks[start] = (end, n)
            self._render(n, text, start, end, draft=draft)
            self.text.see("end")

    def poll(self):
        if not self.winfo_exists():
            return
        try:
            while True:
                ev = self.events.get_nowait()
                if ev[0] == "text":
                    draft = ev[4] if len(ev) > 4 else True
                    self._add_chunk(ev[1], ev[2], ev[3] if len(ev) > 3 else None, draft=draft)
                    self.ask.on_speech(ev[1], ev[2], final=not draft)
                elif ev[0] == "update":
                    draft = ev[4] if len(ev) > 4 else False
                    self._update_chunk(ev[1], ev[2], ev[3], draft)
                    self.ask.on_speech(ev[1], ev[2], final=not draft)
                elif ev[0] == "summary":
                    self.summary.config(text=ev[1])
                    self.cover.pack(fill="x", before=self.tabs)
                elif ev[0] == "status":
                    self.status.config(text=ev[1])
        except queue.Empty:
            pass
        self.after(200, self.poll)
