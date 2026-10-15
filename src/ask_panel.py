"""The "Ask" tab in the recording panel: questions for the teacher, and ask-anything."""
import queue
import threading
import tkinter as tk
from tkinter import scrolledtext

import config
from src import assistant
from src.hotkey_logger import fmt

from src.theme import (ACCENT as _ACCENTS, BG, BORDER, DARK_TEXT, FONT, INK, MUTED, SURFACE, mix)

ACCENT = _ACCENTS["live"]
PLACEHOLDER = "#6d7499"
AMBER = "#ffb454"


class AskTab(tk.Frame):
    """context(seconds) -> recent transcript text; elapsed() -> seconds since recording began."""

    def __init__(self, parent, context, elapsed, notify=None, teacher=True):
        """teacher=False (a video has no teacher): only the \"Ask anything\" part is shown."""
        super().__init__(parent, bg=BG)
        self.has_teacher = teacher
        self.context, self.elapsed = context, elapsed
        self.notify = notify or (lambda question: None)   # tells the panel the teacher asked something
        self.teacher = []       # [{"t", "question", "answer", "by"}]
        self._seen = set()      # chunk starts already checked for teacher questions
        self._asked = set()     # normalised questions already answered
        self.q = queue.Queue()
        self.suggestions = []   # [{"t": seconds, "questions": [...], "by": provider}]
        self.qa = []            # [{"t": seconds, "question": ..., "answer": ..., "by": provider}]
        self._busy = {"suggest": False, "ask": False, "teacher": False}
        self._pending = []      # teacher questions waiting for the AI

        # Widgets that always exist (so the rest of the code works); only packed when there is a teacher
        self.teacher_box = tk.Text(self, height=5, wrap="word", font=(FONT, 10), relief="flat", bg=mix(SURFACE, AMBER, 0.12),
                                   state="disabled", padx=8, pady=6)
        self.teacher_box.tag_config("q", font=(FONT, 10, "bold"))
        self.teacher_box.tag_config("by", foreground=MUTED, font=(FONT, 8))
        self._write(self.teacher_box, "If the teacher asks a question, a suggested answer appears here by itself.",
                    replace=True)
        self.questions = tk.Text(self, height=5, wrap="word", font=(FONT, 10), relief="flat", bg=SURFACE,
                                 state="disabled", padx=8, pady=6)
        self._write(self.questions, "Press Suggest during the class. New ideas also appear by themselves "
                                    "every few minutes.", replace=True)
        head = tk.Frame(self, bg=BG)
        self.suggest_btn = tk.Button(head, text="Suggest", command=self.suggest, relief="flat", bg=mix(SURFACE, ACCENT, 0.22),
                                     fg=ACCENT, font=(FONT, 9, "bold"), padx=10)
        self.suggest_btn.pack(side="right")
        tk.Label(head, text="Questions to ask the teacher", font=(FONT, 10, "bold"), bg=BG).pack(side="left")
        if teacher:
            tk.Label(self, text="The teacher asked you", font=(FONT, 10, "bold"), bg=BG, fg=AMBER,
                     anchor="w").pack(fill="x", padx=10, pady=(10, 2))
            self.teacher_box.pack(fill="x", padx=10)
            head.pack(fill="x", padx=10, pady=(12, 2))
            self.questions.pack(fill="x", padx=10)
        else:
            tk.Label(self, text="Ask about the video: type anything you didn't understand and press Enter.",
                     font=(FONT, 9), bg=BG, fg=MUTED, wraplength=360, justify="left", anchor="w"
                     ).pack(fill="x", padx=10, pady=(10, 0))

        row = tk.Frame(self, bg=BG)
        row.pack(side="bottom", fill="x", padx=10, pady=8)
        self.entry = tk.Entry(row, font=(FONT, 11), relief="flat", bg=SURFACE, highlightthickness=1,
                              highlightbackground=BORDER, highlightcolor=ACCENT)
        self.entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.entry.bind("<Return>", lambda e: self.ask())
        self._placeholder_on()
        self.entry.bind("<FocusIn>", lambda e: self._placeholder_off())
        self.entry.bind("<Button-1>", lambda e: self._placeholder_off())
        self.entry.bind("<Key>", lambda e: self._placeholder_off() if e.keysym not in ("Return", "Tab") else None)
        self.entry.bind("<FocusOut>", lambda e: self._placeholder_on())
        self.ask_btn = tk.Button(row, text="Ask", command=self.ask, relief="flat", bg=ACCENT, fg=DARK_TEXT,
                                 font=(FONT, 10, "bold"), padx=14)
        self.ask_btn.pack(side="left", padx=(6, 0))
        tk.Label(self, text="Ask anything", font=(FONT, 10, "bold"), bg=BG, anchor="w").pack(fill="x", padx=10, pady=(12, 2))
        self.answers = scrolledtext.ScrolledText(self, wrap="word", font=(FONT, 10), relief="flat", bg=SURFACE,
                                                 state="disabled", padx=8, pady=6, height=6)
        self.answers.tag_config("q", font=(FONT, 10, "bold"))
        self.answers.tag_config("by", foreground=MUTED, font=(FONT, 8))
        self.answers.pack(fill="both", expand=True, padx=10)
        self.after(300, self._poll)
        self.after(config.LIVE_QUESTIONS_SECONDS * 1000, self._auto)

    # ---- the "Ask here..." hint inside the box ----------------------------
    HINT = "Ask here: type a question, press Enter"

    def _placeholder_on(self):
        if not self.entry.get():
            self.entry.insert(0, self.HINT)
            self.entry.config(fg=PLACEHOLDER)

    def _placeholder_off(self):
        if self.entry.get() == self.HINT and str(self.entry.cget("fg")) == PLACEHOLDER:
            self.entry.delete(0, "end")
            self.entry.config(fg=INK)

    # ---- helpers ----------------------------------------------------------
    @staticmethod
    def _write(widget, text, tag=None, replace=False):
        widget.config(state="normal")
        if replace:
            widget.delete("1.0", "end")
        widget.insert("end", text, tag)
        widget.see("end")
        widget.config(state="disabled")

    def _run(self, kind, work):
        """Run work() in a thread; its result arrives through the queue."""
        def target():
            try:
                self.q.put((kind, work(), None))
            except assistant.AIUnavailable as e:
                self.q.put((kind, None, f"No AI available: {e}"))
            except Exception as e:
                self.q.put((kind, None, f"Something went wrong ({type(e).__name__})."))
        self._busy[kind] = True
        threading.Thread(target=target, daemon=True).start()

    def on_speech(self, chunk_start, text, final=True):
        """Called with every piece of live transcript; spots questions the teacher asks (never for a video).

        A rough draft may be cut off mid-sentence, so from a draft we only accept a clear 'xxx?' question."""
        if not self.has_teacher or chunk_start in self._seen:
            return
        questions = [q for q in assistant.extract_questions(text) if final or q.endswith("?")]
        questions = [q for q in questions
                     if "".join(c for c in q.lower() if c.isalnum()) not in self._asked]
        if not questions:
            return
        self._seen.add(chunk_start)
        for q in questions:
            self._asked.add("".join(c for c in q.lower() if c.isalnum()))
            self._pending.append((self.elapsed(), q))
        self.notify(questions[0])
        self._next_teacher()

    def _next_teacher(self):
        if self._busy["teacher"] or not self._pending:
            return
        t, question = self._pending.pop(0)
        if self.teacher_box.get("1.0", "end-1c").startswith("If the teacher"):
            self._write(self.teacher_box, "", replace=True)
        self._write(self.teacher_box, f"{question}\n", "q")
        self.teacher_box.mark_set("tthinking", "end-1c")
        self.teacher_box.mark_gravity("tthinking", "left")
        self._write(self.teacher_box, "Thinking of an answer...\n")
        text = self.context(config.ASK_CONTEXT_SECONDS)
        self._run("teacher", lambda: (t, question, *assistant.suggest_answer(question, text)))

    # ---- actions ----------------------------------------------------------
    def suggest(self, auto=False):
        if self._busy["suggest"]:
            return
        text = self.context(config.ASK_CONTEXT_SECONDS)
        if not text.strip():
            if not auto:
                self._write(self.questions, "Nothing has been said yet.", replace=True)
            return
        if not auto:
            self.suggest_btn.config(state="disabled", text="Thinking...")
        t = self.elapsed()
        self._run("suggest", lambda: (t, auto, *assistant.suggest_questions(text)))

    def ask(self):
        question = self.entry.get().strip()
        if str(self.entry.cget("fg")) == PLACEHOLDER:
            return   # only the grey hint is showing
        if not question or self._busy["ask"]:
            return
        self.entry.delete(0, "end")
        self.entry.config(fg=INK)
        self.ask_btn.config(state="disabled", text="...")
        self._placeholder_on() if self.focus_get() is not self.entry else None
        self._write(self.answers, f"{question}\n", "q")
        self.answers.mark_set("thinking", "end-1c")        # where the answer will go
        self.answers.mark_gravity("thinking", "left")
        self._write(self.answers, "Thinking...\n")
        t, text = self.elapsed(), self.context(config.ASK_CONTEXT_SECONDS)
        self._run("ask", lambda: (t, question, *assistant.answer(question, text)))

    def _auto(self):
        """With Claude, quietly refresh the teacher questions every few minutes."""
        if not self.winfo_exists() or not self.has_teacher:
            return
        if assistant.claude_works() or (config.ASK_AUTO_LOCAL and assistant.ai_available()):
            self.suggest(auto=True)
        self.after(config.LIVE_QUESTIONS_SECONDS * 1000, self._auto)

    def _poll(self):
        if not self.winfo_exists():
            return
        try:
            while True:
                kind, result, error = self.q.get_nowait()
                self._busy[kind] = False
                if kind == "teacher":
                    self.teacher_box.config(state="normal")
                    self.teacher_box.delete("tthinking", "end-1c")
                    self.teacher_box.config(state="disabled")
                    if error:
                        self._write(self.teacher_box, error + "\n\n")
                    else:
                        t, question, text, by = result
                        self.teacher.append({"t": t, "question": question, "answer": text, "by": by})
                        self._write(self.teacher_box, "→ " + text + "\n")
                        self._write(self.teacher_box, f"suggested by {by}\n\n", "by")
                    self._next_teacher()
                elif kind == "suggest":
                    self.suggest_btn.config(state="normal", text="Suggest")
                    if error:
                        self._write(self.questions, error, replace=True)
                    else:
                        t, auto, questions, by = result
                        if questions:
                            self.suggestions.append({"t": t, "questions": questions, "by": by})
                            self._write(self.questions, "\n".join(f"• {x}" for x in questions)
                                        + f"\n(at {fmt(t)}, by {by})", replace=True)
                        elif not auto:
                            self._write(self.questions, "No questions came back. Try again in a minute.", replace=True)
                else:
                    self.ask_btn.config(state="normal", text="Ask")
                    self.answers.config(state="normal")
                    self.answers.delete("thinking", "end-1c")           # remove the "Thinking..." line
                    self.answers.config(state="disabled")
                    if error:
                        self._write(self.answers, error + "\n\n")
                    else:
                        t, question, text, by = result
                        self.qa.append({"t": t, "question": question, "answer": text, "by": by})
                        self._write(self.answers, text + "\n")
                        self._write(self.answers, f"by {by}\n\n", "by")
        except queue.Empty:
            pass
        self.after(300, self._poll)

    def export(self):
        return {"suggestions": self.suggestions, "qa": self.qa, "teacher": self.teacher}
