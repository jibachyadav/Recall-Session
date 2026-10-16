"""The home screen: a sidebar with your library, and a list of everything you've recorded or added."""
import tkinter as tk
from tkinter import font as tkfont

import config
from src.sessions import fmt_duration, list_sessions
from src.theme import ACCENT, BG, BORDER, DANGER, DARK_TEXT, INK, MUTED, SIDEBAR, SURFACE, SURFACE_HI, f, mix

HEIGHT_START = 700      # window height when the app opens
WIDTH_START = 1200      # ...and its width
TITLE_PIXELS = 330      # a longer title is cut with "..." so it never runs into the next column
KINDS = [("live", "Live sessions"), ("video", "Videos"), ("document", "Documents")]
LABEL = {"live": "Live session", "video": "Video", "document": "Document"}


def _kind(session):
    """Older sessions saved as \"other\" now belong with the videos."""
    return "video" if session["type"] == "other" else session["type"]


def _bind_all(widget, event, handler):
    widget.bind(event, handler)
    for child in widget.winfo_children():
        _bind_all(child, event, handler)


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


def fit(text, font, pixels):
    """Cut `text` with an ellipsis so that it is at most `pixels` wide in `font`."""
    measure = tkfont.Font(font=font).measure
    if measure(text) <= pixels:
        return text
    while text and measure(text + "…") > pixels:
        text = text[:-1]
    return text.rstrip() + "…"


def ask_name(parent, kind):
    """Small modal window asking for the session name and the spoken language.

    Returns (name, spoken); name is None if cancelled; spoken is "auto", "en", "ne" or "hi"."""
    default = {"live": "Live session", "video": "YouTube video"}[kind]
    heading = {"live": "Name this live class", "video": "Name this video"}[kind]
    color = ACCENT["live"]
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


def build(parent, on_start, on_open, on_delete, state, user=None, on_account=None, on_logout=None):
    """Build the home screen. on_start(kind, title, spoken), on_open(path), on_delete(list_of_sessions).

    `state["open"]` (None or a kind) is the sidebar filter; the caller keeps it so it survives a redraw."""
    root = tk.Frame(parent, bg=BG)
    sessions = list_sessions()

    def start(kind):
        if kind == "document":      # the file's own name is the title: no name window
            return on_start("document", "", "")
        name, spoken = ask_name(root, kind)
        if name:
            on_start(kind, name, spoken)

    # ------------------------------------------------------------------ sidebar
    side = tk.Frame(root, bg=SIDEBAR, width=216)
    side.pack(side="left", fill="y")
    side.pack_propagate(False)
    tk.Label(side, text="Recall-Session", font=f(14, "bold"), bg=SIDEBAR, fg=INK, anchor="w"
             ).pack(fill="x", padx=20, pady=(24, 20))
    nav = tk.Frame(side, bg=SIDEBAR)
    nav.pack(fill="x")
    nav_rows = {}

    def set_filter(key):
        state["open"] = key
        render()

    for key, text in [(None, "All")] + KINDS:
        count = len(sessions) if key is None else sum(1 for s in sessions if _kind(s) == key)
        row = tk.Frame(nav, bg=SIDEBAR, cursor="hand2")
        row.pack(fill="x")
        bar = tk.Frame(row, bg=SIDEBAR, width=3)
        bar.pack(side="left", fill="y")
        dot = tk.Label(row, text="●" if key else " ", font=f(8), bg=SIDEBAR, fg=ACCENT.get(key, MUTED))
        dot.pack(side="left", padx=(14, 8), pady=8)
        name_label = tk.Label(row, text=text, font=f(11), bg=SIDEBAR, fg=MUTED, anchor="w")
        name_label.pack(side="left")
        count_label = tk.Label(row, text=str(count), font=f(10), bg=SIDEBAR, fg=MUTED)
        count_label.pack(side="right", padx=18)
        nav_rows[key] = (row, bar, dot, name_label, count_label)
        _bind_all(row, "<Button-1>", lambda e, k=key: set_filter(k))
        _bind_all(row, "<Enter>", lambda e, k=key: nav_rows[k][0].config(bg=SURFACE_HI) if state["open"] != k else None)
        _bind_all(row, "<Leave>", lambda e, k=key: render_nav())

    def render_nav():
        for key, (row, bar, dot, name_label, count_label) in nav_rows.items():
            active = state["open"] == key
            bg = SURFACE_HI if active else SIDEBAR
            for w in (row, dot, name_label, count_label):
                w.config(bg=bg)
            bar.config(bg=ACCENT["live"] if active else SIDEBAR)
            name_label.config(fg=INK if active else MUTED, font=f(11, "bold") if active else f(11))

    if user:
        foot = tk.Frame(side, bg=SIDEBAR)
        foot.pack(side="bottom", fill="x", pady=(0, 18))
        tk.Frame(foot, bg=BORDER, height=1).pack(fill="x", padx=18, pady=(0, 14))
        tk.Label(foot, text=user["name"], font=f(11, "bold"), bg=SIDEBAR, fg=INK, anchor="w"
                 ).pack(fill="x", padx=20)
        tk.Label(foot, text=f"@{user['username']}", font=f(9), bg=SIDEBAR, fg=MUTED, anchor="w"
                 ).pack(fill="x", padx=20, pady=(0, 8))
        links = tk.Frame(foot, bg=SIDEBAR)
        links.pack(fill="x", padx=20)
        for text, command in (("Account", on_account), ("Log out", on_logout)):
            link = tk.Label(links, text=text, font=f(10), bg=SIDEBAR, fg=MUTED, cursor="hand2")
            link.pack(side="left", padx=(0, 16))
            link.bind("<Button-1>", lambda e, c=command: c())
            link.bind("<Enter>", lambda e, w=link: w.config(fg=INK))
            link.bind("<Leave>", lambda e, w=link: w.config(fg=MUTED))

    # --------------------------------------------------------------------- main
    main = tk.Frame(root, bg=BG)
    main.pack(side="left", fill="both", expand=True)
    top = tk.Frame(main, bg=BG)
    top.pack(fill="x", padx=32, pady=(24, 0))
    title = tk.Label(top, text="", font=f(20, "bold"), bg=BG, fg=INK)
    title.pack(side="left")

    new_button = tk.Menubutton(top, text="+  New", font=f(11, "bold"), bg=ACCENT["live"], fg=DARK_TEXT, relief="flat",
                               padx=16, pady=7, activebackground=mix(ACCENT["live"], "#ffffff", 0.2),
                               activeforeground=DARK_TEXT, cursor="hand2", direction="below")
    new_menu = tk.Menu(new_button, tearoff=0, bg=SURFACE, fg=INK, activebackground=ACCENT["live"],
                       activeforeground=DARK_TEXT, relief="flat", font=f(11), bd=0)
    for kind, text in (("live", "Live session"), ("video", "YouTube video"), ("document", "Document…")):
        new_menu.add_command(label=text, command=lambda k=kind: start(k))
    new_button.config(menu=new_menu)
    new_button.pack(side="right")

    query = tk.StringVar()
    search = tk.Entry(top, textvariable=query, font=f(11), width=24, bg=SURFACE, fg=INK, insertbackground=INK,
                      relief="flat", highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT["live"])
    search.pack(side="right", padx=14, ipady=6)
    placeholder = {"on": False}

    def show_placeholder(_e=None):
        if not search.get():
            placeholder["on"] = True
            search.insert(0, "Search")
            search.config(fg=MUTED)

    def hide_placeholder(_e=None):
        if placeholder["on"]:
            placeholder["on"] = False
            search.delete(0, "end")
            search.config(fg=INK)

    search.bind("<FocusIn>", hide_placeholder)
    search.bind("<FocusOut>", show_placeholder)
    show_placeholder()
    body = tk.Frame(main, bg=BG)
    body.pack(fill="both", expand=True, padx=32, pady=(16, 20))

    def current_items():
        text = "" if placeholder["on"] else query.get().strip().lower()
        wanted = state["open"]
        return [s for s in sessions if (wanted is None or _kind(s) == wanted) and text in s["title"].lower()]

    def render():
        render_nav()
        title.config(text=dict([(None, "All")] + KINDS)[state["open"]] if state["open"] else "All sessions")
        for w in body.winfo_children():
            w.destroy()
        items = current_items()
        if not items:
            searching = (not placeholder["on"]) and query.get().strip()
            empty = tk.Frame(body, bg=BG)
            empty.pack(anchor="w", pady=30)
            tk.Label(empty, text=f"Nothing matches \"{query.get().strip()}\"." if searching else
                     "Nothing here yet.", font=f(12, "bold"), bg=BG, fg=INK).pack(anchor="w")
            if not searching:
                tk.Label(empty, text="Use  + New  to record a live class or a video, or to add a document.",
                         font=f(11), bg=BG, fg=MUTED).pack(anchor="w", pady=(4, 0))
            return

        selected = [tk.BooleanVar(value=False) for _ in items]
        all_var = tk.BooleanVar(value=False)
        head = tk.Frame(body, bg=BG)
        head.pack(fill="x")
        columns(head)
        check_all = tk.Checkbutton(head, variable=all_var, bg=BG, selectcolor=SURFACE_HI, activebackground=BG,
                                   highlightthickness=0, bd=0, cursor="arrow")
        check_all.grid(row=0, column=0, padx=(8, 0))
        for col, text in ((1, "NAME"), (2, "TYPE"), (3, "DATE"), (4, "SIZE")):
            tk.Label(head, text=text, font=f(8, "bold"), bg=BG, fg=MUTED, anchor="w").grid(row=0, column=col, sticky="w")
        delete = tk.Label(head, text="", font=f(10, "bold"), bg=BG, fg=DANGER, cursor="hand2")
        delete.grid(row=0, column=5, sticky="e", padx=(0, 8))
        tk.Frame(body, bg=BORDER, height=1).pack(fill="x", pady=(8, 0))
        column = ScrollColumn(body)
        column.pack(fill="both", expand=True)

        def refresh():
            n = sum(v.get() for v in selected)
            all_var.set(n == len(selected))
            delete.config(text=f"Delete {n}" if n else "")

        def toggle_all():
            for v in selected:
                v.set(all_var.get())
            refresh()

        check_all.config(command=toggle_all)
        delete.bind("<Button-1>", lambda e: on_delete([s for s, v in zip(items, selected) if v.get()])
                    if any(v.get() for v in selected) else None)
        for s, var in zip(items, selected):
            add_row(column.inner, s, var, refresh)

    def columns(frame):
        """Same column widths for the header and every row, so they line up."""
        frame.columnconfigure(1, weight=1)
        for col, width in {0: 44, 2: 116, 3: 160, 4: 140, 5: 90}.items():
            frame.columnconfigure(col, minsize=width)

    def add_row(parent_frame, s, var, on_select):
        kind = _kind(s)
        row = tk.Frame(parent_frame, bg=BG, cursor="hand2")
        row.pack(fill="x")
        columns(row)
        check = tk.Checkbutton(row, variable=var, command=on_select, bg=BG, selectcolor=SURFACE_HI,
                               activebackground=BG, highlightthickness=0, bd=0, cursor="arrow")
        check.grid(row=0, column=0, padx=(8, 0), pady=11)
        tk.Label(row, text=fit(s["title"], f(11, "bold"), TITLE_PIXELS), font=f(11, "bold"), bg=BG, fg=INK,
                 anchor="w").grid(row=0, column=1, sticky="w", padx=(0, 14))
        kind_cell = tk.Frame(row, bg=BG)
        kind_cell.grid(row=0, column=2, sticky="w")
        tk.Label(kind_cell, text="●", font=f(8), bg=BG, fg=ACCENT[kind]).pack(side="left")
        tk.Label(kind_cell, text=" " + LABEL[kind], font=f(10), bg=BG, fg=MUTED).pack(side="left")
        when = f"{s['when']:%b} {s['when'].day}, {s['when']:%I:%M %p}".replace(" 0", " ")
        tk.Label(row, text=when, font=f(10), bg=BG, fg=MUTED, anchor="w").grid(row=0, column=3, sticky="w")
        size = f"{s.get('words', 0):,} words" if kind == "document" else fmt_duration(s["duration"])
        if s["flags"]:
            size += f" · {s['flags']} flag{'s' if s['flags'] != 1 else ''}"
        tk.Label(row, text=size, font=f(10), bg=BG, fg=MUTED, anchor="w").grid(row=0, column=4, sticky="w")
        tk.Label(row, text="" if s["done"] else "Unfinished", font=f(9, "bold"), bg=BG, fg=ACCENT["video"],
                 anchor="e").grid(row=0, column=5, sticky="e", padx=(0, 8))
        tk.Frame(parent_frame, bg=BORDER, height=1).pack(fill="x")

        def paint(color):
            for w in [row] + list(row.winfo_children()) + list(kind_cell.winfo_children()):
                try:
                    w.config(bg=color)
                except tk.TclError:
                    pass
            check.config(activebackground=color)

        def bind_open(w):
            if w is check:
                return
            w.bind("<Button-1>", lambda e: on_open(s["path"]))
            w.bind("<Enter>", lambda e: paint(SURFACE))
            w.bind("<Leave>", lambda e: paint(BG))
            for child in w.winfo_children():
                bind_open(child)

        bind_open(row)

    query.trace_add("write", lambda *_: render())
    render()
    return root
