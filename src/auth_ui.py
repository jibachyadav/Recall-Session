"""Sign-in screens: log in, register, forgot password, the recovery key page, and the Account page."""
import tkinter as tk
from tkinter import messagebox

import threading

from src import auth, settings
from src.theme import ACCENT, BG, BORDER, DANGER, DARK_TEXT, INK, MUTED, SURFACE, SURFACE_HI, f, mix, rounded_rect

COLOR = ACCENT["live"]
STRENGTH = [("", MUTED), ("Weak", DANGER), ("Okay", "#ffb454"), ("Good", "#9be37a"), ("Strong", ACCENT["document"])]


class AuthFlow:
    def __init__(self, app, on_signed_in):
        self.app = app
        self.root = app.root
        self.on_signed_in = on_signed_in            # called with the user once they are in

    # ------------------------------------------------------------ building blocks
    def _page(self, title, subtitle, width=420):
        """A centred card on the dark background. Returns (frame_to_fill, error_label)."""
        page = tk.Frame(self.root, bg=BG)
        centre = tk.Frame(page, bg=BG)
        centre.place(relx=0.5, rely=0.5, anchor="center")
        logo = tk.Canvas(centre, width=60, height=60, bg=BG, highlightthickness=0)
        rounded_rect(logo, 2, 2, 58, 58, 17, fill=COLOR, outline="")
        rounded_rect(logo, 2, 30, 58, 58, 17, fill=mix(COLOR, ACCENT["video"], 0.45), outline="")
        logo.create_oval(16, 16, 44, 44, outline=DARK_TEXT, width=4)
        logo.create_oval(25, 25, 35, 35, fill=DARK_TEXT, outline="")
        logo.pack()
        tk.Label(centre, text="Recall-Session", font=f(13, "bold"), bg=BG, fg=MUTED).pack(pady=(8, 14))
        card = tk.Frame(centre, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER, width=width)
        card.pack()
        inner = tk.Frame(card, bg=SURFACE)
        inner.pack(padx=34, pady=30)
        tk.Label(inner, text=title, font=f(20, "bold"), bg=SURFACE, fg=INK).pack(anchor="w")
        tk.Label(inner, text=subtitle, font=f(10), bg=SURFACE, fg=MUTED, wraplength=width - 70,
                 justify="left").pack(anchor="w", pady=(2, 16))
        return page, inner

    @staticmethod
    def _field(parent, label, secret=False, value=""):
        tk.Label(parent, text=label, font=f(10, "bold"), bg=SURFACE, fg=MUTED).pack(anchor="w", pady=(8, 3))
        entry = tk.Entry(parent, font=f(12), width=32, show="•" if secret else "", bg=BG, fg=INK,
                         insertbackground=INK, highlightthickness=1, highlightbackground=BORDER,
                         highlightcolor=COLOR, relief="flat")
        entry.insert(0, value)
        entry.pack(fill="x", ipady=8)
        return entry

    @staticmethod
    def _reveal(parent, *entries):
        """A 'Show password' tick box for the given entry fields."""
        var = tk.BooleanVar(value=False)
        tk.Checkbutton(parent, text="Show password", variable=var, bg=SURFACE, fg=MUTED, selectcolor=SURFACE_HI,
                       activebackground=SURFACE, activeforeground=INK, font=f(9), highlightthickness=0,
                       command=lambda: [e.config(show="" if var.get() else "•") for e in entries]
                       ).pack(anchor="w", pady=(6, 0))

    @staticmethod
    def _button(parent, text, command, primary=True):
        b = tk.Button(parent, text=text, command=command, font=f(12, "bold"), pady=9,
                      bg=COLOR if primary else SURFACE_HI, fg=DARK_TEXT if primary else INK,
                      activebackground=mix(COLOR, "#ffffff", 0.2) if primary else BORDER,
                      activeforeground=DARK_TEXT if primary else INK)
        b.pack(fill="x", pady=(14 if primary else 8, 0))
        return b

    @staticmethod
    def _link(parent, text, command, anchor="w"):
        link = tk.Label(parent, text=text, font=f(10, "underline"), bg=SURFACE, fg=COLOR, cursor="hand2")
        link.pack(anchor=anchor, pady=(10, 0))
        link.bind("<Button-1>", lambda e: command())
        return link

    @staticmethod
    def _error(parent):
        label = tk.Label(parent, text="", font=f(10), bg=SURFACE, fg=DANGER, wraplength=330, justify="left")
        label.pack(anchor="w", pady=(10, 0))
        return label

    def _show(self, page, height=700):
        self.app._show(page, self.app._center(760, height))

    # -------------------------------------------------------------------- login
    def show_login(self, username="", notice=""):
        page, box = self._page("Welcome back", "Sign in to see your classes, videos and documents.")
        if notice:
            tk.Label(box, text=notice, font=f(10), bg=SURFACE, fg=ACCENT["document"], wraplength=330,
                     justify="left").pack(anchor="w", pady=(0, 6))
        user = self._field(box, "Username", value=username)
        pw = self._field(box, "Password", secret=True)
        self._reveal(box, pw)
        keep = tk.BooleanVar(value=False)
        tk.Checkbutton(box, text="Keep me signed in on this computer", variable=keep, bg=SURFACE, fg=MUTED,
                       selectcolor=SURFACE_HI, activebackground=SURFACE, activeforeground=INK, font=f(9),
                       highlightthickness=0).pack(anchor="w", pady=(2, 0))
        error = self._error(box)

        def submit(_e=None):
            try:
                signed = auth.login(user.get(), pw.get(), remember=keep.get())
            except auth.AuthError as e:
                error.config(text=str(e))
                pw.delete(0, "end")
                return
            self.on_signed_in(signed)

        btn = self._button(box, "Log in", submit)
        for e in (user, pw):
            e.bind("<Return>", submit)
        self._link(box, "Forgot your password?", lambda: self.show_forgot(user.get()))
        tk.Frame(box, bg=BORDER, height=1).pack(fill="x", pady=(16, 0))
        row = tk.Frame(box, bg=SURFACE)
        row.pack(anchor="w", pady=(12, 0))
        tk.Label(row, text="New here?", font=f(10), bg=SURFACE, fg=MUTED).pack(side="left")
        link = tk.Label(row, text="  Create an account", font=f(10, "bold"), bg=SURFACE, fg=COLOR, cursor="hand2")
        link.pack(side="left")
        link.bind("<Button-1>", lambda e: self.show_register())
        self._show(page)
        (pw if username else user).focus_set()

    # ----------------------------------------------------------------- register
    def show_register(self):
        page, box = self._page("Create your account", "Your classes and documents stay private to your account on this computer.")
        name = self._field(box, "Your name (optional)")
        user = self._field(box, "Username")
        pw = self._field(box, "Password (8 or more characters)", secret=True)
        meter = tk.Label(box, text="", font=f(9, "bold"), bg=SURFACE, fg=MUTED, anchor="w")
        meter.pack(anchor="w", pady=(4, 0))
        pw2 = self._field(box, "Repeat password", secret=True)
        self._reveal(box, pw, pw2)
        error = self._error(box)

        def update_meter(_e=None):
            label, color = STRENGTH[auth.password_strength(pw.get())]
            meter.config(text=f"Strength: {label}" if label else "", fg=color)

        pw.bind("<KeyRelease>", update_meter)

        def submit(_e=None):
            try:
                created, key = auth.register(user.get(), pw.get(), pw2.get(), name.get())
            except auth.AuthError as e:
                error.config(text=str(e))
                return
            username, password = created["username"], pw.get()        # read now: these fields are gone on the next page
            self.show_recovery_key(created, key, then=lambda: self.on_signed_in(auth.login(username, password)))

        self._button(box, "Create account", submit)
        for e in (name, user, pw, pw2):
            e.bind("<Return>", submit)
        row = tk.Frame(box, bg=SURFACE)
        row.pack(anchor="w", pady=(14, 0))
        tk.Label(row, text="Already have an account?", font=f(10), bg=SURFACE, fg=MUTED).pack(side="left")
        link = tk.Label(row, text="  Log in", font=f(10, "bold"), bg=SURFACE, fg=COLOR, cursor="hand2")
        link.pack(side="left")
        link.bind("<Button-1>", lambda e: self.show_login())
        self._show(page, 840)
        (name).focus_set()

    # ------------------------------------------------------------ recovery key
    def show_recovery_key(self, user, key, then, title="Save your recovery key"):
        page, box = self._page(title, "If you ever forget your password, this key is the only way back in. "
                                      "It is shown once, so write it down or save it somewhere safe.")
        shown = tk.Frame(box, bg=BG, highlightthickness=1, highlightbackground=COLOR)
        shown.pack(fill="x", pady=(4, 6))
        tk.Label(shown, text=key, font=("Ubuntu Mono", 22, "bold"), bg=BG, fg=INK).pack(padx=18, pady=16)
        note = tk.Label(box, text="", font=f(10), bg=SURFACE, fg=ACCENT["document"])

        def copy():
            self.root.clipboard_clear()
            self.root.clipboard_append(key)
            note.config(text="Copied to the clipboard.")

        self._button(box, "Copy the key", copy, primary=False)
        note.pack(anchor="w", pady=(6, 0))
        saved = tk.BooleanVar(value=False)
        go = {}

        def toggle():
            go["b"].config(state="normal" if saved.get() else "disabled")

        tk.Checkbutton(box, text="I have saved my recovery key", variable=saved, command=toggle, bg=SURFACE,
                       fg=INK, selectcolor=SURFACE_HI, activebackground=SURFACE, activeforeground=INK, font=f(10),
                       highlightthickness=0).pack(anchor="w", pady=(12, 0))
        go["b"] = self._button(box, "Continue", then)
        go["b"].config(state="disabled")
        self._show(page)

    # ------------------------------------------------------------ forgot password
    def show_forgot(self, username=""):
        page, box = self._page("Reset your password", "Enter your username and the recovery key you saved when you created your account.")
        user = self._field(box, "Username", value=username)
        key = self._field(box, "Recovery key (like 3F9A-0C21-B7D4-9E15)")
        pw = self._field(box, "New password (8 or more characters)", secret=True)
        pw2 = self._field(box, "Repeat new password", secret=True)
        self._reveal(box, pw, pw2)
        error = self._error(box)

        def submit(_e=None):
            try:
                fresh = auth.reset_with_recovery_key(user.get(), key.get(), pw.get(), pw2.get())
            except auth.AuthError as e:
                error.config(text=str(e))
                return
            username = user.get()                                       # read now: this field is gone on the next page
            self.show_recovery_key({"username": username}, fresh, title="Password changed. Save your NEW key",
                                   then=lambda: self.show_login(username, "Password changed. Log in with your new password."))

        self._button(box, "Reset password", submit)
        self._link(box, "← Back to log in", lambda: self.show_login(user.get()))
        self._show(page, 800)
        (key if username else user).focus_set()

    # ------------------------------------------------------------------ AI settings
    def _ai_card(self, body):
        """Row under the account cards: save, test or remove the optional Claude API key."""
        c = tk.Frame(body, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        c.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        inner = tk.Frame(c, bg=SURFACE)
        inner.pack(fill="x", padx=26, pady=22)
        tk.Label(inner, text="AI features (optional)", font=f(14, "bold"), bg=SURFACE, fg=INK).pack(anchor="w")
        tk.Label(inner, text="Add a Claude API key for better summaries and answers. Without one, the app uses its free "
                             "built-in options. The key stays on this computer.", font=f(10), bg=SURFACE, fg=MUTED,
                 wraplength=760, justify="left").pack(anchor="w", pady=(2, 10))
        status = tk.Label(inner, text="", font=f(10, "bold"), bg=SURFACE, wraplength=760, justify="left")
        status.pack(anchor="w")
        row = tk.Frame(inner, bg=SURFACE)
        row.pack(fill="x", pady=(8, 0))
        entry = tk.Entry(row, font=f(11), show="•", bg=BG, fg=INK, insertbackground=INK, highlightthickness=1,
                         highlightbackground=BORDER, highlightcolor=COLOR, relief="flat")
        entry.pack(side="left", fill="x", expand=True, ipady=7)

        def show_state(text=None, color=MUTED):
            if text is None:
                text = f"A key is saved ({settings.key_hint()})." if settings.has_key() else "No key saved. The free options are in use."
            status.config(text=text, fg=color)

        def save():
            try:
                settings.save_key(entry.get())
            except settings.SettingsError as e:
                return show_state(str(e), DANGER)
            entry.delete(0, "end")
            show_state("Key saved. Press Test key to check it.", ACCENT["document"])

        def test():
            if not settings.has_key():
                return show_state("No key saved yet.", DANGER)
            show_state("Testing...", MUTED)
            result = []
            threading.Thread(target=lambda: result.append(settings.test_key()), daemon=True).start()

            def check():
                if not result:
                    return status.after(200, check)
                ok, message = result[0]
                show_state(message, ACCENT["document"] if ok else DANGER)

            check()

        def remove():
            settings.remove_key()
            show_state()

        for text, command, primary in (("Save key", save, True), ("Test key", test, False), ("Remove", remove, False)):
            tk.Button(row, text=text, command=command, font=f(10, "bold"), padx=14, pady=7,
                      bg=COLOR if primary else SURFACE_HI, fg=DARK_TEXT if primary else INK).pack(side="left", padx=(8, 0))
        show_state()

    # ------------------------------------------------------------------ account
    def show_account(self, user, on_back, on_logout):
        page = tk.Frame(self.root, bg=BG)
        top = tk.Frame(page, bg=BG)
        top.pack(fill="x", padx=36, pady=(26, 0))
        tk.Label(top, text="Account", font=f(24, "bold"), bg=BG, fg=INK).pack(side="left")
        tk.Button(top, text="← Back", command=on_back, font=f(11, "bold"), padx=14, pady=6).pack(side="right")
        body = tk.Frame(page, bg=BG)
        body.pack(fill="both", expand=True, padx=36, pady=20)
        body.columnconfigure((0, 1), weight=1, uniform="a")

        def card(col, title):
            c = tk.Frame(body, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
            c.grid(row=0, column=col, sticky="nsew", padx=(0, 10) if col == 0 else (10, 0))
            inner = tk.Frame(c, bg=SURFACE)
            inner.pack(fill="both", padx=26, pady=24)
            tk.Label(inner, text=title, font=f(14, "bold"), bg=SURFACE, fg=INK).pack(anchor="w", pady=(0, 6))
            return inner

        who = card(0, f"{user['name']}")
        tk.Label(who, text=f"Signed in as @{user['username']}", font=f(10), bg=SURFACE, fg=MUTED).pack(anchor="w")
        tk.Label(who, text="Change password", font=f(12, "bold"), bg=SURFACE, fg=INK).pack(anchor="w", pady=(18, 0))
        old = self._field(who, "Current password", secret=True)
        new = self._field(who, "New password", secret=True)
        new2 = self._field(who, "Repeat new password", secret=True)
        msg = tk.Label(who, text="", font=f(10), bg=SURFACE, wraplength=300, justify="left")
        msg.pack(anchor="w", pady=(8, 0))

        def change():
            try:
                auth.change_password(user["username"], old.get(), new.get(), new2.get())
            except auth.AuthError as e:
                return msg.config(text=str(e), fg=DANGER)
            for e in (old, new, new2):
                e.delete(0, "end")
            msg.config(text="Password changed.", fg=ACCENT["document"])

        self._button(who, "Change password", change, primary=False)

        out = card(1, "Sign out")
        tk.Label(out, text="You'll need your password to get back in. Your classes and documents stay saved.",
                 font=f(10), bg=SURFACE, fg=MUTED, wraplength=300, justify="left").pack(anchor="w")
        self._button(out, "Log out", on_logout)
        tk.Label(out, text="Delete account", font=f(12, "bold"), bg=SURFACE, fg=DANGER).pack(anchor="w", pady=(26, 0))
        tk.Label(out, text="This permanently deletes your account and ALL your classes, videos and documents.",
                 font=f(10), bg=SURFACE, fg=MUTED, wraplength=300, justify="left").pack(anchor="w", pady=(2, 0))
        pw = self._field(out, "Your password", secret=True)
        dmsg = tk.Label(out, text="", font=f(10), bg=SURFACE, fg=DANGER, wraplength=300, justify="left")
        dmsg.pack(anchor="w", pady=(8, 0))

        def delete():
            if not messagebox.askyesno("Delete account", "Delete your account and everything in it?\n\nThis cannot be undone.",
                                       icon="warning", default="no"):
                return
            try:
                auth.delete_account(user["username"], pw.get())
            except auth.AuthError as e:
                return dmsg.config(text=str(e))
            on_logout()

        self._ai_card(body)
        b = tk.Button(out, text="Delete my account", command=delete, font=f(11, "bold"), pady=8, bg=DANGER,
                      fg=DARK_TEXT, activebackground=mix(DANGER, "#ffffff", 0.2), activeforeground=DARK_TEXT)
        b.pack(fill="x", pady=(10, 0))
        self.app._show(page, self.app._center(1000, 860))
