"""The home dashboard: start a live class, a video or a document, and browse previous work."""
import tkinter as tk
from datetime import datetime

import config
from src.sessions import fmt_duration, list_sessions
from src.theme import (ACCENT, BG, BORDER, DANGER, DARK_TEXT, INK, MUTED, SURFACE, SURFACE_HI, f, mix,
                       rounded_rect)

CARD_H = 250
HEIGHT_START = 500      # window height when the app opens (it then fits itself to the cards)
HEIGHT_OPEN = 800       # window height while a list is open


def _kind(session):
    """Older sessions saved as \"other\" now belong with the YouTube card."""
    return "video" if session["type"] == "other" else session["type"]


def _bind_all(widget, event, handler):
    widget.bind(event, handler)
    for child in widget.winfo_children():
        _bind_all(child, event, handler)


def _icon(canvas, kind, cx, cy, color, size=26):
    """Draw the glyph for a card (a record ring, a play triangle, or a page)."""
    s = size
    if kind == "video":
        canvas.create_polygon(cx - s * 0.32, cy - s * 0.45, cx - s * 0.32, cy + s * 0.45, cx + s * 0.5, cy,
                              fill=color, outline="")
    elif kind == "document":
        canvas.create_polygon(cx - s * 0.4, cy - s * 0.52, cx + s * 0.1, cy - s * 0.52, cx + s * 0.4, cy - s * 0.22,
                              cx + s * 0.4, cy + s * 0.52, cx - s * 0.4, cy + s * 0.52, fill=color, outline="")
        for dy in (-0.05, 0.17, 0.39):
            canvas.create_line(cx - s * 0.2, cy + s * dy, cx + s * 0.2, cy + s * dy, fill=SURFACE, width=2)
    else:  # live: a ring with a dot
        canvas.create_oval(cx - s * 0.5, cy - s * 0.5, cx + s * 0.5, cy + s * 0.5, outline=color, width=3)
        canvas.create_oval(cx - s * 0.2, cy - s * 0.2, cx + s * 0.2, cy + s * 0.2, fill=color, outline="")


class StartCard(tk.Canvas):
    """A big rounded card. It glows in its colour when the mouse is over it, and starts the session on click."""

    def __init__(self, parent, kind, title, text, on_click):
        super().__init__(parent, height=CARD_H, bg=BG, highlightthickness=0, cursor="hand2")
        self.kind, self.title, self.text, self.on_click = kind, title, text, on_click
        self.color = ACCENT[kind]
        self.hover = False
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", lambda e: self.on_click())

    def _set_hover(self, on):
        self.hover = on
        self.draw()

    def draw(self):
        self.delete("all")
        w, h, c, hov = self.winfo_width(), CARD_H, self.color, self.hover
        if w < 50:
            return
        if hov:  # soft glow: a slightly bigger, faint rounded rectangle behind the card
            rounded_rect(self, 1, 1, w - 1, h - 1, 24, fill=mix(BG, c, 0.22), outline="")
        rounded_rect(self, 4, 4, w - 4, h - 4, 20, fill=SURFACE_HI if hov else SURFACE,
                     outline=c if hov else BORDER, width=2 if hov else 1)
        # icon in a tinted circle
        cx, cy = 52, 56
        self.create_oval(cx - 26, cy - 26, cx + 26, cy + 26, fill=mix(SURFACE, c, 0.2), outline="")
        _icon(self, self.kind, cx, cy, c)
        self.create_text(28, 112, text=self.title, anchor="w", fill=INK, font=f(16, "bold"))
        self.create_text(28, 138, text=self.text, anchor="nw", fill=MUTED, font=f(10), width=w - 56)
        label = "Choose a file" if self.kind == "document" else "Start"
        pill_w = 112 if self.kind == "document" else 84
        x0, y0 = 28, h - 56
        rounded_rect(self, x0, y0, x0 + pill_w, y0 + 34, 17, fill=c if hov else mix(SURFACE, c, 0.18), outline="")
        self.create_text(x0 + pill_w / 2, y0 + 17, text=f"{label}  →", fill=DARK_TEXT if hov else c,
                         font=f(11, "bold"))


class ScrollColumn(tk.Frame):
    """A vertically scrolling list area."""

    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.inner = tk.Frame(self.canvas, bg=BG)
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.win, width=e.width))
        for w in (self.canvas, self.inner):
            w.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-2, "units"))
            w.bind("<Button-5>", lambda e: self.canvas.yview_scroll(2, "units"))


def session_row(parent, s, on_open, on_delete, selected, on_select):
    color = ACCENT.get(s["type"], ACCENT["live"])
    row = tk.Frame(parent, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER, cursor="hand2")
    row.pack(fill="x", pady=4)
    tk.Frame(row, bg=color, width=4).pack(side="left", fill="y")
    check = tk.Checkbutton(row, variable=selected, command=on_select, bg=SURFACE, activebackground=SURFACE,
                           selectcolor=SURFACE_HI, highlightthickness=0, bd=0, cursor="arrow")
    check.pack(side="left", padx=(10, 0))
    body = tk.Frame(row, bg=SURFACE)
    body.pack(side="left", fill="both", expand=True, padx=12, pady=9)
    tk.Label(body, text=s["title"], font=f(11, "bold"), bg=SURFACE, fg=INK, anchor="w").pack(fill="x")
    detail = f"{s.get('words', 0):,} words" if s["type"] == "document" else fmt_duration(s["duration"])
    meta = f"{s['when']:%b %d, %I:%M %p}  ·  {detail}"
    if s["flags"]:
        meta += f"  ·  {s['flags']} flag{'s' if s['flags'] != 1 else ''}"
    tk.Label(body, text=meta, font=f(9), bg=SURFACE, fg=MUTED, anchor="w").pack(fill="x")

    delete = tk.Label(row, text="✕", font=f(11), bg=SURFACE, fg=MUTED, cursor="hand2", padx=12)
    delete.pack(side="right", fill="y")
    delete.bind("<Enter>", lambda e: delete.config(fg=DANGER))
    delete.bind("<Leave>", lambda e: delete.config(fg=MUTED))
    delete.bind("<Button-1>", lambda e: on_delete([s]))
    tk.Label(row, text="Open  ›" if s["done"] else "Unfinished", font=f(9, "bold"), bg=SURFACE,
             fg=color if s["done"] else MUTED).pack(side="right", padx=4)

    def bind_open(w):
        if w is delete or w is check:
            return
        w.bind("<Button-1>", lambda e: on_open(s["path"]))
        w.bind("<Enter>", lambda e: row.config(highlightbackground=color))
        w.bind("<Leave>", lambda e: row.config(highlightbackground=BORDER))
        for child in w.winfo_children():
            bind_open(child)

    bind_open(row)


def ask_name(parent, kind):
    """Small modal window asking for the session name and the spoken language.

    Returns (name, spoken); name is None if cancelled; spoken is "auto", "en", "ne" or "hi"."""
    default = {"live": "Live session", "video": "YouTube video"}[kind]
    heading = {"live": "Name this live class", "video": "Name this video"}[kind]
    color = ACCENT[kind]
    win = tk.Toplevel(parent)
    win.title("New session")
    win.configure(bg=SURFACE)
    win.transient(parent.winfo_toplevel())
    win.resizable(False, False)
    tk.Label(win, text=heading, font=f(15, "bold"), bg=SURFACE, fg=INK).pack(anchor="w", padx=26, pady=(24, 2))
    tk.Label(win, text="For example: Physics lecture 3, or the video's title.", font=f(10),
             bg=SURFACE, fg=MUTED).pack(anchor="w", padx=26)
    entry = tk.Entry(win, font=f(12), width=34, relief="flat", bg=BG, fg=INK, insertbackground=INK,
                     highlightthickness=1, highlightbackground=BORDER, highlightcolor=color)
    entry.pack(padx=26, pady=(16, 10), ipady=8)
    tk.Label(win, text="What language will be spoken?", font=f(10, "bold"), bg=SURFACE, fg=MUTED
             ).pack(anchor="w", padx=26)
    labels = list(config.SPOKEN_LANGUAGES.values())
    choice = tk.StringVar(value=labels[0])
    menu = tk.OptionMenu(win, choice, *labels)
    menu.config(font=f(11), bg=BG, fg=INK, activebackground=SURFACE_HI, activeforeground=INK, relief="flat",
                highlightthickness=1, highlightbackground=BORDER, anchor="w", width=30, cursor="hand2")
    menu["menu"].config(font=f(11), bg=SURFACE, fg=INK, activebackground=color, activeforeground=DARK_TEXT, relief="flat")
    menu.pack(padx=26, pady=(4, 4), fill="x")
    hint = tk.Label(win, text="", font=f(9), bg=SURFACE, fg=MUTED, wraplength=360, justify="left")
    hint.pack(anchor="w", padx=26, pady=(0, 14))
    notes = {"ne": "Nepali: the live text is skipped. Your full transcript, in Nepali and English, is made after you stop.",
             "hi": "Hindi: live text is shown in English (rough). The Hindi transcript is also saved.",
             "auto": "The app listens and guesses the language. Choosing it yourself is more reliable."}
    codes = {v: k for k, v in config.SPOKEN_LANGUAGES.items()}
    choice.trace_add("write", lambda *_: hint.config(text=notes.get(codes[choice.get()], "")))
    hint.config(text=notes["auto"])
    result = {"name": None, "spoken": "auto"}

    def ok(_event=None):
        result["name"] = entry.get().strip() or default
        result["spoken"] = codes[choice.get()]
        win.destroy()

    row = tk.Frame(win, bg=SURFACE)
    row.pack(fill="x", padx=26, pady=(0, 22))
    tk.Button(row, text="Start recording", command=ok, bg=color, fg=DARK_TEXT, relief="flat",
              font=f(11, "bold"), padx=18, pady=7, activebackground=mix(color, "#ffffff", 0.2),
              activeforeground=DARK_TEXT).pack(side="right")
    tk.Button(row, text="Cancel", command=win.destroy, relief="flat", bg=SURFACE, fg=MUTED,
              font=f(11), padx=12, pady=7, activebackground=SURFACE_HI, activeforeground=INK).pack(side="right", padx=8)
    entry.bind("<Return>", ok)
    win.bind("<Escape>", lambda e: win.destroy())
    win.update_idletasks()
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    win.geometry(f"+{px + (parent.winfo_width() - win.winfo_width()) // 2}+{py + 180}")
    win.grab_set()
    entry.focus_set()
    win.wait_window()
    return result["name"], result["spoken"]


def _greeting():
    hour = datetime.now().hour
    return "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"


def _logo(parent):
    """The app logo: a rounded tile with a recording ring."""
    c = tk.Canvas(parent, width=52, height=52, bg=BG, highlightthickness=0)
    rounded_rect(c, 2, 2, 50, 50, 15, fill=mix(ACCENT["live"], ACCENT["video"], 0.0), outline="")
    rounded_rect(c, 2, 26, 50, 50, 15, fill=mix(ACCENT["live"], ACCENT["video"], 0.45), outline="")
    c.create_oval(14, 14, 38, 38, outline=DARK_TEXT, width=4)
    c.create_oval(22, 22, 30, 30, fill=DARK_TEXT, outline="")
    return c


def build(parent, on_start, on_open, on_delete, state, user=None, on_account=None, on_logout=None):
    """Build the dashboard frame. on_start(kind, title, spoken), on_open(path), on_delete(list_of_sessions).
    `state` ({"open": kind or None}) is kept by the caller so the open list survives a redraw."""
    root = tk.Frame(parent, bg=BG)
    sessions = list_sessions()

    head = tk.Frame(root, bg=BG)
    head.pack(fill="x", padx=40, pady=(30, 0))
    _logo(head).pack(side="left")
    titles = tk.Frame(head, bg=BG)
    titles.pack(side="left", padx=16)
    tk.Label(titles, text="Recall-Session", font=f(26, "bold"), bg=BG, fg=INK).pack(anchor="w")
    tk.Label(titles, text="Capture it. Understand it. Remember it.", font=f(11), bg=BG, fg=MUTED).pack(anchor="w")
    right = tk.Frame(head, bg=BG)
    right.pack(side="right")
    name = f", {user['name'].split()[0]}" if user else ""
    tk.Label(right, text=f"{_greeting()}{name}", font=f(13, "bold"), bg=BG, fg=INK).pack(anchor="e")
    tk.Label(right, text=f"{datetime.now():%A, %B %d}", font=f(10), bg=BG, fg=MUTED).pack(anchor="e")
    if user:
        buttons = tk.Frame(right, bg=BG)
        buttons.pack(anchor="e", pady=(8, 0))
        for text, command in (("Account", on_account), ("Log out", on_logout)):
            b = tk.Label(buttons, text=text, font=f(10, "bold"), bg=SURFACE, fg=INK, padx=12, pady=4, cursor="hand2")
            b.pack(side="left", padx=(6, 0))
            b.bind("<Button-1>", lambda e, c=command: c())
            b.bind("<Enter>", lambda e, b=b: b.config(bg=SURFACE_HI))
            b.bind("<Leave>", lambda e, b=b: b.config(bg=SURFACE))

    main = tk.Frame(root, bg=BG)          # heading + cards: centred in the free space while no list is open
    tk.Label(main, text="What would you like to do?", font=f(12, "bold"), bg=BG, fg=MUTED, anchor="w"
             ).pack(fill="x", padx=40, pady=(0, 10))

    def start(kind):
        if kind == "document":      # the file's own name is the title: no name window
            return on_start("document", "", "")
        name, spoken = ask_name(root, kind)
        if name:
            on_start(kind, name, spoken)

    specs = [("live", "Live session", "An online class on Zoom, Teams or Meet. Records the teacher and your own voice.", "live sessions"),
             ("video", "YouTube video", "A video or recorded lecture playing on this computer. Records its sound.", "videos"),
             ("document", "Document", "Click to choose a PDF, Word or text file from your computer. Reads it and writes a summary.", "documents")]
    cols = tk.Frame(main, bg=BG)
    cols.pack(fill="x", padx=40)
    cols.columnconfigure((0, 1, 2), weight=1, uniform="c")
    area = tk.Frame(root, bg=BG)          # shows the previous work of ONE category at a time
    toggles = {}

    def layout(open_):
        """Cards always stay at the top. The window is just tall enough for them, and grows when a list opens."""
        main.pack_forget()
        area.pack_forget()
        main.pack(fill="x", pady=(24, 0))
        if open_:
            area.pack(fill="both", expand=True, padx=40, pady=(8, 26))
        win = root.winfo_toplevel()
        if win.state() == "normal" and win.winfo_ismapped() and win.winfo_width() > 100:   # (and not before it is shown)
            win.update_idletasks()
            if open_:
                want = HEIGHT_OPEN
            else:                                       # snug: just below the "Previous" bars
                bottom = max((b.winfo_y() + b.winfo_height() for b in toggles.values()), default=0)
                want = main.winfo_y() + cols.winfo_y() + bottom + 30
            win.geometry(f"{win.winfo_width()}x{want}")

    def render():
        for w in area.winfo_children():
            w.destroy()
        for kind, btn in toggles.items():
            active = state["open"] == kind
            n = sum(1 for x in sessions if _kind(x) == kind)
            btn.config(text=f"Previous  ({n})  {'▴' if active else '▾'}",
                       bg=ACCENT[kind] if active else SURFACE, fg=DARK_TEXT if active else ACCENT[kind])
        kind = state["open"]
        layout(bool(kind))
        if not kind:
            return
        title = next(sp[3] for sp in specs if sp[0] == kind)
        items = [x for x in sessions if _kind(x) == kind]
        top = tk.Frame(area, bg=BG)
        top.pack(fill="x", pady=(10, 6))
        tk.Label(top, text=f"Previous {title}", font=f(13, "bold"), bg=BG, fg=ACCENT[kind],
                 anchor="w").pack(side="left")
        col = ScrollColumn(area)
        if not items:
            col.pack(fill="both", expand=True)
            tk.Label(col.inner, text="Nothing here yet.", font=f(10), bg=BG, fg=MUTED).pack(anchor="w", pady=4)
            return

        vars_ = [tk.BooleanVar(value=False) for _ in items]
        all_var = tk.BooleanVar(value=False)
        del_btn = tk.Button(top, text="Delete selected", relief="flat", bg=SURFACE, fg=MUTED,
                            font=f(10, "bold"), padx=14, pady=4, state="disabled", bd=0,
                            command=lambda: on_delete([x for x, v in zip(items, vars_) if v.get()]))
        del_btn.pack(side="right")

        def refresh():
            n = sum(v.get() for v in vars_)
            all_var.set(n == len(vars_))
            del_btn.config(text=f"Delete selected ({n})" if n else "Delete selected",
                           state="normal" if n else "disabled",
                           bg=DANGER if n else SURFACE, fg=DARK_TEXT if n else MUTED,
                           activebackground=mix(DANGER, "#ffffff", 0.2), activeforeground=DARK_TEXT)

        def select_all():
            for v in vars_:
                v.set(all_var.get())
            refresh()

        tk.Checkbutton(top, text="Select all", variable=all_var, command=select_all, bg=BG, selectcolor=SURFACE_HI,
                       activebackground=BG, activeforeground=INK, font=f(10), fg=INK, highlightthickness=0
                       ).pack(side="right", padx=14)
        col.pack(fill="both", expand=True)
        for x, v in zip(items, vars_):
            session_row(col.inner, x, on_open, on_delete, v, refresh)

    def toggle(kind):
        state["open"] = None if state["open"] == kind else kind
        render()

    for i, (kind, title, text, _) in enumerate(specs):
        pad = (0 if i == 0 else 9, 0 if i == 2 else 9)
        StartCard(cols, kind, title, text, lambda k=kind: start(k)).grid(row=0, column=i, sticky="nsew", padx=pad)
        btn = tk.Label(cols, font=f(10, "bold"), cursor="hand2", pady=8, bd=0, bg=SURFACE, fg=ACCENT[kind])
        btn.grid(row=1, column=i, sticky="ew", padx=pad, pady=(12, 0))
        btn.bind("<Button-1>", lambda e, k=kind: toggle(k))
        btn.bind("<Enter>", lambda e, b=btn, k=kind: b.config(bg=SURFACE_HI) if state["open"] != k else None)
        btn.bind("<Leave>", lambda e, b=btn, k=kind: b.config(bg=SURFACE) if state["open"] != k else None)
        toggles[kind] = btn
    render()
    return root
