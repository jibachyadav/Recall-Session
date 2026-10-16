"""Shared look for the whole app: a dark, modern theme."""
import tkinter as tk
from tkinter import ttk

FONT = "Ubuntu Sans"          # installed with Ubuntu; Tk falls back to a default font if it is missing

BG = "#15171c"                # window
SIDEBAR = "#101216"           # the left sidebar on the home screen
SURFACE = "#1c1f26"           # panels, inputs
SURFACE_HI = "#262a33"        # hovered / raised
BORDER = "#2c313b"
INK = "#e8eaee"               # main text
MUTED = "#8e95a2"             # secondary text
DANGER = "#e5675d"
DARK_TEXT = "#101216"         # text on bright accent buttons
# One main colour (blue, the buttons) and a quiet colour per kind of session
ACCENT = {"live": "#5b8def", "video": "#d9a441", "document": "#5fb58a", "other": "#5fb58a"}
HIGHLIGHT_FLAG = "#f2c94c"    # you pressed Flag here
HIGHLIGHT_KEY = "#7fd3a5"     # stressed as important


def f(size=11, weight="normal"):
    return (FONT, size, weight)


def mix(a, b, t):
    """Blend colour a toward colour b by t (0..1), both '#rrggbb'."""
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


def rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    """A rectangle with rounded corners, drawn as one smooth polygon."""
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
           x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


def apply(root):
    """Make every widget created after this dark by default (explicit colours still win)."""
    root.configure(bg=BG)
    o = root.option_add
    o("*Font", f(11))
    o("*Background", BG)
    o("*Foreground", INK)
    o("*Label.Background", BG)
    o("*Label.Foreground", INK)
    o("*Frame.Background", BG)
    o("*Canvas.Background", BG)
    o("*Toplevel.Background", BG)
    o("*Button.Background", SURFACE_HI)
    o("*Button.Foreground", INK)
    o("*Button.ActiveBackground", BORDER)
    o("*Button.ActiveForeground", INK)
    o("*Button.Relief", "flat")
    o("*Button.BorderWidth", 0)
    o("*Button.HighlightThickness", 0)
    o("*Button.Cursor", "hand2")
    o("*Button.disabledForeground", mix(MUTED, BG, 0.4))
    o("*Text.Background", SURFACE)
    o("*Text.Foreground", INK)
    o("*Text.InsertBackground", INK)
    o("*Text.Relief", "flat")
    o("*Text.HighlightThickness", 0)
    o("*Text.SelectBackground", "#3a4380")
    o("*Text.SelectForeground", INK)
    o("*Entry.Background", SURFACE)
    o("*Entry.Foreground", INK)
    o("*Entry.InsertBackground", INK)
    o("*Entry.Relief", "flat")
    o("*Entry.HighlightThickness", 1)
    o("*Entry.HighlightBackground", BORDER)
    o("*Entry.HighlightColor", ACCENT["live"])
    o("*Spinbox.Background", SURFACE)
    o("*Spinbox.Foreground", INK)
    o("*Checkbutton.Background", BG)
    o("*Checkbutton.Foreground", INK)
    o("*Checkbutton.ActiveBackground", BG)
    o("*Checkbutton.ActiveForeground", INK)
    o("*Checkbutton.SelectColor", SURFACE_HI)
    o("*Checkbutton.HighlightThickness", 0)
    o("*Scrollbar.Background", SURFACE_HI)
    o("*Scrollbar.TroughColor", BG)
    o("*Scrollbar.Relief", "flat")
    o("*Scrollbar.BorderWidth", 0)
    o("*Scrollbar.HighlightThickness", 0)

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0),
                    bordercolor=BG, lightcolor=BG, darkcolor=BG)
    style.configure("TNotebook.Tab", background=SURFACE, foreground=MUTED, padding=(18, 8),
                    borderwidth=0, font=f(11, "bold"), bordercolor=BG, lightcolor=SURFACE, darkcolor=SURFACE)
    style.map("TNotebook.Tab", background=[("selected", SURFACE_HI)], foreground=[("selected", INK)],
              lightcolor=[("selected", SURFACE_HI)], darkcolor=[("selected", SURFACE_HI)])
    style.configure("TProgressbar", troughcolor=SURFACE, background=ACCENT["live"], borderwidth=0,
                    lightcolor=ACCENT["live"], darkcolor=ACCENT["live"])
    style.configure("Vertical.TScrollbar", background=SURFACE_HI, troughcolor=BG, borderwidth=0,
                    arrowcolor=MUTED)


def render_markdown(box, text):
    """Show markdown-ish text in a Text widget: headings become titles, '- ' a bullet; leftovers are dropped."""
    box.tag_config("h", font=f(13, "bold"), spacing1=10, spacing3=4, foreground=ACCENT["document"])
    box.tag_config("b", lmargin1=14, lmargin2=28)
    box.config(state="normal")
    box.delete("1.0", "end")
    text = text.replace("\\(", "").replace("\\)", "").replace("\\log", "log").replace("**", "")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            box.insert("end", stripped.lstrip("#").strip() + "\n", "h")
        elif stripped.startswith(("- ", "* ")):
            box.insert("end", "•  " + stripped[2:] + "\n", "b")
        else:
            box.insert("end", line + "\n")
    box.config(state="disabled")
