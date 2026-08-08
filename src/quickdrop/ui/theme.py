from __future__ import annotations

import tkinter as tk
from tkinter import ttk

BG = "#090d16"
SIDEBAR = "#0d1320"
SURFACE = "#111927"
SURFACE_2 = "#162033"
BORDER = "#243149"
TEXT = "#f4f7ff"
MUTED = "#95a1b6"
ACCENT = "#7456f1"
ACCENT_HOVER = "#8167f6"
GOOD = "#3dd68c"
WARN = "#f0b84c"
DANGER = "#ff6b78"


def apply_theme(root: tk.Misc) -> ttk.Style:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10))
    style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=TEXT,
                    rowheight=34, borderwidth=0, relief="flat")
    style.map("Treeview", background=[("selected", "#2a2452")], foreground=[("selected", TEXT)])
    style.configure("Treeview.Heading", background=SURFACE_2, foreground=MUTED,
                    relief="flat", padding=(8, 9), font=("Segoe UI Semibold", 9))
    style.map("Treeview.Heading", background=[("active", SURFACE_2)])
    style.configure("TCombobox", fieldbackground=SURFACE_2, background=SURFACE_2,
                    foreground=TEXT, arrowcolor=TEXT, bordercolor=BORDER)
    style.map("TCombobox", fieldbackground=[("readonly", SURFACE_2)], foreground=[("readonly", TEXT)])
    style.configure("Vertical.TScrollbar", background=SURFACE_2, troughcolor=BG, bordercolor=BG, arrowcolor=MUTED)
    return style
