from __future__ import annotations

import logging
import os
import queue
import subprocess
import threading
import time
import webbrowser
from datetime import datetime
from importlib import resources
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import qrcode
from PIL import ImageTk

from quickdrop import __version__
from quickdrop.core.storage import app_data_dir
from quickdrop.core.devices import DeviceRegistry
from quickdrop.services.server import ServerController
from quickdrop.services.transfer import TransferManager
from quickdrop.ui.theme import ACCENT, ACCENT_HOVER, BG, BORDER, DANGER, GOOD, MUTED, SIDEBAR, SURFACE, SURFACE_2, TEXT, apply_theme

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception:  # pragma: no cover - normal Tk fallback
    DND_FILES = None
    TkinterDnD = None

GITHUB_REPO = "https://github.com/impreseo/Quick-Drop"
LINKS = {
    "Report a bug": f"{GITHUB_REPO}/issues/new?template=bug.yml",
    "Request a feature": f"{GITHUB_REPO}/issues/new?template=feature.yml",
    "Feedback & Suggestions": f"{GITHUB_REPO}/issues",
    "Check for updates": f"{GITHUB_REPO}/releases/latest",
    "Other Apps & GitHub": "https://github.com/impreseo",
    "Instagram": "https://instagram.com/impreseo",
    "LinkedIn": "https://www.linkedin.com/in/impreseo/",
    "Discord": "https://discord.com/app",
}


def human_size(value: int) -> str:
    size = float(max(0, value))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" or size >= 10 else f"{size:.1f} {unit}"
        size /= 1024
    return f"{value} B"


def open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys_platform() == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def sys_platform() -> str:
    import sys
    return sys.platform


class QuickDropApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"QuickDrop {__version__}")
        self.root.geometry("1180x760")
        self.root.minsize(960, 650)
        self.root.configure(bg=BG)
        apply_theme(root)
        self.manager = TransferManager()
        self.devices = DeviceRegistry(self.manager.data_dir)
        self.server = ServerController(self.manager)
        self.current_page = "Home"
        self.pages: dict[str, tk.Frame] = {}
        self.nav_buttons: dict[str, tk.Button] = {}
        self.ui_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.qr_photo = None
        self.status_var = tk.StringVar(value="Ready")
        self.pin_var = tk.StringVar(value="------")
        self.url_var = tk.StringVar(value="Not connected")
        self.expiry_var = tk.StringVar(value="")
        self._setup_icon()
        self._build_shell()
        self._build_pages()
        self.show_page("Home")
        self._setup_dnd()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.report_callback_exception = self._report_callback_exception
        self.root.after(100, self._poll_ui_queue)
        self.root.after(700, self._tick)
        if self.manager.settings.get("start_server", True):
            self.start_session()

    def _setup_icon(self) -> None:
        try:
            ref = resources.files("quickdrop.assets").joinpath("quickdrop.ico")
            with resources.as_file(ref) as icon_path:
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass

    def _build_shell(self) -> None:
        self.sidebar = tk.Frame(self.root, bg=SIDEBAR, width=224, highlightthickness=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.main = tk.Frame(self.root, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)

        brand = tk.Frame(self.sidebar, bg=SIDEBAR)
        brand.pack(fill="x", padx=18, pady=(22, 18))
        logo = tk.Label(brand, text="Q", bg=ACCENT, fg="white", width=3, height=1,
                        font=("Segoe UI Semibold", 15), padx=2, pady=5)
        logo.pack(side="left")
        tk.Label(brand, text="QuickDrop", bg=SIDEBAR, fg=TEXT,
                 font=("Segoe UI Semibold", 15)).pack(side="left", padx=(10, 0))

        nav = [
            ("CONNECT", ["Home"]),
            ("TRANSFER", ["Send", "Receive", "Quick Text"]),
            ("ACTIVITY", ["History"]),
            ("QUICKDROP", ["Settings", "About & Support"]),
        ]
        for section, items in nav:
            tk.Label(self.sidebar, text=section, bg=SIDEBAR, fg="#67748b",
                     font=("Segoe UI Semibold", 8), anchor="w").pack(fill="x", padx=20, pady=(14, 6))
            for name in items:
                btn = tk.Button(self.sidebar, text=self._nav_text(name), anchor="w", bd=0,
                                bg=SIDEBAR, fg=MUTED, activebackground=SURFACE_2,
                                activeforeground=TEXT, font=("Segoe UI", 10),
                                padx=18, pady=10, cursor="hand2",
                                command=lambda n=name: self.show_page(n))
                btn.pack(fill="x", padx=10, pady=1)
                self.nav_buttons[name] = btn

        footer = tk.Frame(self.sidebar, bg=SIDEBAR)
        footer.pack(side="bottom", fill="x", padx=18, pady=18)
        self.server_dot = tk.Label(footer, text="●", bg=SIDEBAR, fg="#59657a", font=("Segoe UI", 10))
        self.server_dot.pack(side="left")
        self.server_state = tk.Label(footer, text="Server stopped", bg=SIDEBAR, fg=MUTED, font=("Segoe UI", 9))
        self.server_state.pack(side="left", padx=(7, 0))

        top = tk.Frame(self.main, bg=BG, height=70)
        top.pack(fill="x", padx=28, pady=(14, 0))
        top.pack_propagate(False)
        self.page_title = tk.Label(top, text="Home", bg=BG, fg=TEXT, font=("Segoe UI Semibold", 18))
        self.page_title.pack(side="left", pady=13)
        self.top_status = tk.Label(top, textvariable=self.status_var, bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.top_status.pack(side="right", pady=17)
        self.page_host = tk.Frame(self.main, bg=BG)
        self.page_host.pack(fill="both", expand=True, padx=28, pady=(0, 18))

    def _nav_text(self, name: str) -> str:
        icons = {"Home":"⌂", "Send":"↑", "Receive":"↓", "Quick Text":"≡", "History":"◷", "Settings":"⚙", "About & Support":"?"}
        return f"  {icons.get(name, '•')}    {name}"

    def _build_pages(self) -> None:
        self.pages["Home"] = self._build_home()
        self.pages["Send"] = self._build_send()
        self.pages["Receive"] = self._build_receive()
        self.pages["Quick Text"] = self._build_text()
        self.pages["History"] = self._build_history()
        self.pages["Settings"] = self._build_settings()
        self.pages["About & Support"] = self._build_about()

    def _page(self) -> tk.Frame:
        return tk.Frame(self.page_host, bg=BG)

    def _card(self, parent: tk.Misc, **kwargs) -> tk.Frame:
        return tk.Frame(parent, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1, **kwargs)

    def _label(self, parent: tk.Misc, text: str = "", *, size: int = 10, color: str = TEXT,
               weight: str = "normal", bg: str | None = None, **kwargs) -> tk.Label:
        family = "Segoe UI Semibold" if weight == "semibold" else "Segoe UI"
        return tk.Label(parent, text=text, bg=bg or getattr(parent, "cget", lambda _: BG)("bg"), fg=color,
                        font=(family, size), **kwargs)

    def _button(self, parent: tk.Misc, text: str, command, *, primary: bool = False, width: int | None = None) -> tk.Button:
        bg = ACCENT if primary else SURFACE_2
        active = ACCENT_HOVER if primary else "#202c42"
        return tk.Button(parent, text=text, command=command, bd=0, bg=bg, fg=TEXT,
                         activebackground=active, activeforeground=TEXT, padx=15, pady=9,
                         font=("Segoe UI Semibold", 9), cursor="hand2", width=width)

    def _build_home(self) -> tk.Frame:
        page = self._page()
        hero = self._card(page, height=345)
        hero.pack(fill="x", pady=(0, 16)); hero.pack_propagate(False)
        left = tk.Frame(hero, bg=SURFACE)
        left.pack(side="left", fill="both", expand=True, padx=28, pady=25)
        self._label(left, "PRIVATE LOCAL TRANSFER", size=8, color="#9b8cff", weight="semibold").pack(anchor="w")
        self.home_headline = self._label(left, "Ready to connect your phone", size=26, weight="semibold")
        self.home_headline.pack(anchor="w", pady=(7, 5))
        self._label(left, "Same Wi-Fi. No cloud account. No phone app required.", color=MUTED).pack(anchor="w")

        conn = tk.Frame(left, bg=SURFACE)
        conn.pack(fill="x", pady=(24, 8))
        pin_card = tk.Frame(conn, bg="#0b1120", highlightbackground=BORDER, highlightthickness=1)
        pin_card.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._label(pin_card, "CONNECTION PIN", size=8, color=MUTED, weight="semibold", bg="#0b1120").pack(anchor="w", padx=15, pady=(12, 2))
        self._label(pin_card, textvariable=self.pin_var, size=24, weight="semibold", bg="#0b1120").pack(anchor="w", padx=15, pady=(0, 12))
        time_card = tk.Frame(conn, bg="#0b1120", highlightbackground=BORDER, highlightthickness=1)
        time_card.pack(side="left", fill="x", expand=True)
        self._label(time_card, "SESSION", size=8, color=MUTED, weight="semibold", bg="#0b1120").pack(anchor="w", padx=15, pady=(12, 2))
        self._label(time_card, textvariable=self.expiry_var, size=14, weight="semibold", bg="#0b1120").pack(anchor="w", padx=15, pady=(5, 15))

        self._label(left, textvariable=self.url_var, color="#aeb9cc").pack(anchor="w", pady=(8, 10))
        buttons = tk.Frame(left, bg=SURFACE); buttons.pack(anchor="w")
        self.session_btn = self._button(buttons, "Start session", self.toggle_session, primary=True)
        self.session_btn.pack(side="left")
        self._button(buttons, "New PIN", self.new_session).pack(side="left", padx=8)
        self._button(buttons, "Copy address", self.copy_address).pack(side="left")

        qr_wrap = tk.Frame(hero, bg="#0b1120", width=270, height=295, highlightbackground=BORDER, highlightthickness=1)
        qr_wrap.pack(side="right", padx=(5, 24), pady=24); qr_wrap.pack_propagate(False)
        self.qr_label = tk.Label(qr_wrap, text="Start a session\nto show QR", bg="#0b1120", fg=MUTED,
                                 font=("Segoe UI", 10), justify="center")
        self.qr_label.pack(expand=True)
        self._label(qr_wrap, "SCAN WITH PHONE CAMERA", size=8, color=MUTED, weight="semibold", bg="#0b1120").pack(side="bottom", pady=(0, 14))

        stats = tk.Frame(page, bg=BG); stats.pack(fill="x", pady=(0, 16))
        self.stat_labels = {}
        for idx, (key, title, subtitle) in enumerate([
            ("shared", "Shared now", "available to phone"),
            ("sent", "Sent", "completed downloads"),
            ("received", "Received", "files from phone"),
        ]):
            card = self._card(stats, height=95); card.pack(side="left", fill="x", expand=True, padx=(0 if idx == 0 else 6, 0 if idx == 2 else 6)); card.pack_propagate(False)
            value = self._label(card, "0", size=22, weight="semibold"); value.pack(anchor="w", padx=18, pady=(13, 0))
            self._label(card, title, size=9, weight="semibold").pack(anchor="w", padx=18)
            self._label(card, subtitle, size=8, color=MUTED).pack(anchor="w", padx=18)
            self.stat_labels[key] = value

        actions = self._card(page); actions.pack(fill="x")
        self._label(actions, "Quick actions", size=12, weight="semibold").pack(anchor="w", padx=18, pady=(15, 10))
        row = tk.Frame(actions, bg=SURFACE); row.pack(fill="x", padx=18, pady=(0, 16))
        self._button(row, "+ Add files", self.choose_files, primary=True).pack(side="left")
        self._button(row, "+ Add folder", self.choose_folder).pack(side="left", padx=8)
        self._button(row, "Open received", lambda: open_folder(self.manager.inbox)).pack(side="left")
        return page

    def _build_send(self) -> tk.Frame:
        page = self._page()
        top = self._card(page); top.pack(fill="x", pady=(0, 12))
        left = tk.Frame(top, bg=SURFACE); left.pack(side="left", padx=18, pady=14)
        self._label(left, "Share files with your phone", size=13, weight="semibold").pack(anchor="w")
        self._label(left, "Add files or folders. Folders are packaged as ZIP only for this session.", color=MUTED, size=9).pack(anchor="w", pady=(3, 0))
        controls = tk.Frame(top, bg=SURFACE); controls.pack(side="right", padx=14)
        self._button(controls, "Add files", self.choose_files, primary=True).pack(side="left")
        self._button(controls, "Add folder", self.choose_folder).pack(side="left", padx=7)
        self._button(controls, "Remove", self.remove_selected_shared).pack(side="left")

        drop = tk.Frame(page, bg="#0d1422", height=95, highlightbackground=BORDER, highlightthickness=1, cursor="hand2")
        drop.pack(fill="x", pady=(0, 12)); drop.pack_propagate(False)
        self._label(drop, "Drop files here  •  or click to browse", size=11, weight="semibold", bg="#0d1422").pack(expand=True)
        drop.bind("<Button-1>", lambda _: self.choose_files())
        self.send_dropzone = drop

        wrap = self._card(page); wrap.pack(fill="both", expand=True)
        columns = ("name", "type", "size")
        self.shared_tree = ttk.Treeview(wrap, columns=columns, show="headings", selectmode="extended")
        self.shared_tree.heading("name", text="Name"); self.shared_tree.heading("type", text="Type"); self.shared_tree.heading("size", text="Size")
        self.shared_tree.column("name", width=520); self.shared_tree.column("type", width=120); self.shared_tree.column("size", width=120, anchor="e")
        self.shared_tree.pack(fill="both", expand=True, padx=1, pady=1)
        bottom = tk.Frame(page, bg=BG); bottom.pack(fill="x", pady=(10, 0))
        self.send_hint = self._label(bottom, "Start a session to connect a phone.", color=MUTED, size=9); self.send_hint.pack(side="left")
        self._button(bottom, "Clear shared", self.clear_shared).pack(side="right")
        return page

    def _build_receive(self) -> tk.Frame:
        page = self._page()
        top = self._card(page); top.pack(fill="x", pady=(0, 12))
        left = tk.Frame(top, bg=SURFACE); left.pack(side="left", padx=18, pady=14)
        self._label(left, "Files received from phone", size=13, weight="semibold").pack(anchor="w")
        self.receive_path_label = self._label(left, str(self.manager.inbox), size=9, color=MUTED)
        self.receive_path_label.pack(anchor="w", pady=(3, 0))
        buttons = tk.Frame(top, bg=SURFACE); buttons.pack(side="right", padx=14)
        self._button(buttons, "Open folder", lambda: open_folder(self.manager.inbox), primary=True).pack(side="left")
        self._button(buttons, "Change folder", self.change_inbox).pack(side="left", padx=7)

        wrap = self._card(page); wrap.pack(fill="both", expand=True)
        self.receive_tree = ttk.Treeview(wrap, columns=("time", "name", "size", "device"), show="headings")
        for key, title, width in (("time","Time",150),("name","Name",420),("size","Size",100),("device","From",130)):
            self.receive_tree.heading(key, text=title); self.receive_tree.column(key, width=width, anchor="e" if key=="size" else "w")
        self.receive_tree.pack(fill="both", expand=True, padx=1, pady=1)
        return page

    def _build_text(self) -> tk.Frame:
        page = self._page()
        info = self._card(page); info.pack(fill="x", pady=(0, 12))
        self._label(info, "Quick Text", size=13, weight="semibold").pack(anchor="w", padx=18, pady=(14, 2))
        self._label(info, "Move a link, note, code snippet or address between PC and phone without creating a file.", color=MUTED, size=9).pack(anchor="w", padx=18, pady=(0, 14))
        editor = self._card(page); editor.pack(fill="both", expand=True)
        self.text_box = tk.Text(editor, bg="#0a101d", fg=TEXT, insertbackground=TEXT, bd=0, relief="flat",
                                wrap="word", padx=18, pady=18, font=("Consolas", 10), undo=True)
        self.text_box.pack(fill="both", expand=True, padx=1, pady=1)
        row = tk.Frame(page, bg=BG); row.pack(fill="x", pady=(10, 0))
        self.text_status = self._label(row, "Shared text is visible only to the authenticated phone session.", color=MUTED, size=9); self.text_status.pack(side="left")
        self._button(row, "Paste clipboard", self.paste_clipboard).pack(side="right", padx=(7, 0))
        self._button(row, "Copy text", self.copy_quick_text).pack(side="right", padx=(7, 0))
        self._button(row, "Update shared text", self.update_quick_text, primary=True).pack(side="right")
        return page

    def _build_history(self) -> tk.Frame:
        page = self._page()
        head = tk.Frame(page, bg=BG); head.pack(fill="x", pady=(0, 10))
        self._label(head, "Completed transfers are kept locally (latest 500).", color=MUTED, size=9).pack(side="left")
        self._button(head, "Clear history", self.clear_history).pack(side="right")
        wrap = self._card(page); wrap.pack(fill="both", expand=True)
        self.history_tree = ttk.Treeview(wrap, columns=("time","direction","name","size","detail"), show="headings")
        for key,title,width in (("time","Time",145),("direction","Direction",100),("name","Name",390),("size","Size",90),("detail","Device / IP",130)):
            self.history_tree.heading(key,text=title); self.history_tree.column(key,width=width,anchor="e" if key=="size" else "w")
        self.history_tree.pack(fill="both", expand=True, padx=1, pady=1)
        return page

    def _build_settings(self) -> tk.Frame:
        page = self._page()
        card = self._card(page); card.pack(fill="x")
        self._label(card, "Connection", size=13, weight="semibold").grid(row=0, column=0, columnspan=3, sticky="w", padx=18, pady=(17, 12))
        self._label(card, "Session lifetime", color=MUTED).grid(row=1, column=0, sticky="w", padx=18, pady=8)
        self.session_minutes_var = tk.StringVar(value=str(self.manager.settings.get("session_minutes", 30)))
        combo = ttk.Combobox(card, textvariable=self.session_minutes_var, values=("15","30","60","120"), width=12, state="readonly")
        combo.grid(row=1,column=1,sticky="w",padx=10,pady=8)
        self._label(card, "minutes", color=MUTED).grid(row=1,column=2,sticky="w",pady=8)
        self.start_server_var = tk.BooleanVar(value=bool(self.manager.settings.get("start_server", True)))
        check = tk.Checkbutton(card, text="Start a local sharing session when QuickDrop opens", variable=self.start_server_var,
                               bg=SURFACE, fg=TEXT, activebackground=SURFACE, activeforeground=TEXT,
                               selectcolor=SURFACE_2, font=("Segoe UI", 9))
        check.grid(row=2,column=0,columnspan=3,sticky="w",padx=14,pady=(8,16))

        receive = self._card(page); receive.pack(fill="x", pady=14)
        self._label(receive, "Received files", size=13, weight="semibold").pack(anchor="w", padx=18, pady=(17, 6))
        self.settings_inbox_label = self._label(receive, str(self.manager.inbox), color=MUTED, size=9)
        self.settings_inbox_label.pack(anchor="w", padx=18)
        self._button(receive, "Choose folder", self.change_inbox).pack(anchor="w", padx=18, pady=(11, 16))

        permissions = self._card(page); permissions.pack(fill="x", pady=(0, 14))
        self._label(permissions, "Phone permissions", size=13, weight="semibold").grid(row=0,column=0,columnspan=3,sticky="w",padx=18,pady=(17,8))
        self.allow_downloads_var = tk.BooleanVar(value=bool(self.manager.settings.get("allow_downloads", True)))
        self.allow_uploads_var = tk.BooleanVar(value=bool(self.manager.settings.get("allow_uploads", True)))
        self.allow_text_var = tk.BooleanVar(value=bool(self.manager.settings.get("allow_text", True)))
        self.allow_trusted_var = tk.BooleanVar(value=bool(self.manager.settings.get("allow_trusted_devices", True)))
        for row,(label,var) in enumerate((("Allow phone to download shared files",self.allow_downloads_var),("Allow phone uploads to this PC",self.allow_uploads_var),("Allow Quick Text",self.allow_text_var),("Allow remembered/trusted devices",self.allow_trusted_var)), start=1):
            tk.Checkbutton(permissions,text=label,variable=var,bg=SURFACE,fg=TEXT,activebackground=SURFACE,activeforeground=TEXT,selectcolor=SURFACE_2,font=("Segoe UI",9)).grid(row=row,column=0,columnspan=3,sticky="w",padx=14,pady=5)
        self._label(permissions,"Maximum phone upload",color=MUTED).grid(row=5,column=0,sticky="w",padx=18,pady=(8,16))
        self.max_upload_var=tk.StringVar(value=str(self.manager.settings.get("max_upload_mb",2048)))
        ttk.Combobox(permissions,textvariable=self.max_upload_var,values=("100","500","1024","2048","4096","10240"),width=12,state="readonly").grid(row=5,column=1,sticky="w",padx=10,pady=(8,16))
        self._label(permissions,"MB per file",color=MUTED).grid(row=5,column=2,sticky="w",pady=(8,16))

        privacy = self._card(page); privacy.pack(fill="x")
        self._label(privacy, "Privacy & trusted devices", size=13, weight="semibold").pack(anchor="w", padx=18, pady=(17, 6))
        self.trusted_label = self._label(privacy, "", color=MUTED, size=9); self.trusted_label.pack(anchor="w", padx=18)
        self._label(privacy, "QuickDrop accepts private-network clients only. Every session gets a fresh token and PIN. Remembered-device secrets are stored as hashes on the PC.", color=MUTED, size=9, wraplength=760, justify="left").pack(anchor="w", padx=18, pady=(7, 10))
        self._button(privacy, "Forget all trusted devices", self.forget_trusted_devices).pack(anchor="w", padx=18, pady=(0,16))
        self._button(page, "Save settings", self.save_settings, primary=True).pack(anchor="e", pady=(12, 0))
        return page

    def _build_about(self) -> tk.Frame:
        page = self._page()
        hero = self._card(page); hero.pack(fill="x", pady=(0, 12))
        mark = tk.Label(hero, text="Q", bg=ACCENT, fg="white", width=4, height=2, font=("Segoe UI Semibold", 18))
        mark.pack(side="left", padx=20, pady=20)
        text = tk.Frame(hero, bg=SURFACE); text.pack(side="left", fill="x", expand=True, pady=19)
        self._label(text, f"QuickDrop {__version__}", size=18, weight="semibold").pack(anchor="w")
        self._label(text, "Fast private PC ↔ phone transfers over your own local network.", color=MUTED, size=9).pack(anchor="w", pady=(3, 0))
        self._label(hero, "by impreseo", color="#9b8cff", weight="semibold").pack(side="right", padx=20)

        actions = self._card(page); actions.pack(fill="x", pady=(0, 12))
        self._label(actions, "Help improve QuickDrop", size=12, weight="semibold").pack(anchor="w", padx=18, pady=(15, 10))
        row = tk.Frame(actions, bg=SURFACE); row.pack(fill="x", padx=18, pady=(0, 16))
        for i, (label, primary) in enumerate((("Report a bug", True),("Request a feature",False),("Feedback & Suggestions",False),("Check for updates",False))):
            self._button(row, label, lambda l=label: webbrowser.open(LINKS[l]), primary=primary).pack(side="left", padx=(0,8))

        social = self._card(page); social.pack(fill="x")
        self._label(social, "Feedback, Suggestions & Other Apps", size=12, weight="semibold").pack(anchor="w", padx=18, pady=(15, 3))
        self._label(social, "Share feedback, suggest new features, or discover other apps by impreseo:", color=MUTED, size=9).pack(anchor="w", padx=18, pady=(0, 12))
        row2 = tk.Frame(social, bg=SURFACE); row2.pack(fill="x", padx=18, pady=(0, 16))
        for label in ("Other Apps & GitHub","Instagram","LinkedIn"):
            self._button(row2, label, lambda l=label: webbrowser.open(LINKS[l])).pack(side="left", padx=(0,8))
        self._button(row2, "Discord · @impreseo", self.open_discord).pack(side="left")
        self._button(row2, "Open app data / log", lambda: open_folder(app_data_dir())).pack(side="left", padx=(8,0))
        self._button(row2, "Copy handle", lambda: self.copy_to_clipboard("impreseo", "Copied: impreseo")).pack(side="right")
        return page

    def _report_callback_exception(self, exc_type, exc_value, exc_traceback) -> None:
        logging.error("Unhandled UI callback error", exc_info=(exc_type, exc_value, exc_traceback))
        messagebox.showerror("QuickDrop error", f"Something went wrong. A local log was written for troubleshooting.\n\n{exc_value}")

    def _setup_dnd(self) -> None:
        if not DND_FILES or not hasattr(self.root, "drop_target_register"):
            return
        try:
            self.root.drop_target_register(DND_FILES)  # type: ignore[attr-defined]
            self.root.dnd_bind("<<Drop>>", self._on_drop)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _on_drop(self, event) -> None:
        if self.current_page != "Send":
            self.show_page("Send")
        try:
            paths = [Path(x) for x in self.root.tk.splitlist(event.data)]
        except Exception:
            return
        for path in paths:
            if path.is_file():
                try: self.manager.add_file(path)
                except Exception as exc: self.status_var.set(str(exc))
            elif path.is_dir():
                self._add_folder_worker(path)
        self.refresh_dynamic()

    def show_page(self, name: str) -> None:
        for page in self.pages.values():
            page.pack_forget()
        page = self.pages[name]
        page.pack(fill="both", expand=True)
        self.current_page = name
        self.page_title.configure(text=name)
        for nav_name, btn in self.nav_buttons.items():
            selected = nav_name == name
            btn.configure(bg=SURFACE_2 if selected else SIDEBAR, fg=TEXT if selected else MUTED)
        self.refresh_dynamic()

    def start_session(self) -> None:
        try:
            self.server.start()
            self.status_var.set("Local sharing session started")
            self._render_qr()
        except OSError as exc:
            messagebox.showerror("Could not start QuickDrop", f"QuickDrop could not open a local network port.\n\n{exc}")
            self.status_var.set("Server could not start")
        self.refresh_dynamic()

    def stop_session(self) -> None:
        self.server.stop()
        self.qr_photo = None
        self.qr_label.configure(image="", text="Start a session\nto show QR")
        self.status_var.set("Sharing session stopped")
        self.refresh_dynamic()

    def toggle_session(self) -> None:
        self.stop_session() if self.server.running else self.start_session()

    def new_session(self) -> None:
        try:
            self.server.restart_session()
            self._render_qr()
            self.status_var.set("New PIN and session created")
        except OSError as exc:
            messagebox.showerror("Could not restart QuickDrop", str(exc))
        self.refresh_dynamic()

    def _render_qr(self) -> None:
        if not self.server.url:
            return
        image = qrcode.make(self.server.url).convert("RGB").resize((212, 212))
        self.qr_photo = ImageTk.PhotoImage(image)
        self.qr_label.configure(image=self.qr_photo, text="")

    def copy_to_clipboard(self, text: str, status: str = "Copied") -> None:
        self.root.clipboard_clear(); self.root.clipboard_append(text); self.root.update_idletasks(); self.status_var.set(status)

    def copy_address(self) -> None:
        if self.server.url: self.copy_to_clipboard(self.server.url, "Phone address copied")

    def choose_files(self) -> None:
        names = filedialog.askopenfilenames(title="Choose files to share")
        for raw in names:
            try: self.manager.add_file(Path(raw))
            except Exception as exc: messagebox.showerror("Could not add file", str(exc))
        if names:
            self.show_page("Send"); self.status_var.set(f"Added {len(names)} file(s)")

    def choose_folder(self) -> None:
        raw = filedialog.askdirectory(title="Choose folder to share")
        if raw:
            self.show_page("Send")
            self._add_folder_worker(Path(raw))

    def _add_folder_worker(self, path: Path) -> None:
        self.status_var.set(f"Packaging {path.name}…")
        def work():
            try:
                item = self.manager.add_folder(path)
                self.ui_queue.put(("status", f"Added {item.name}"))
            except Exception as exc:
                self.ui_queue.put(("error", f"Could not add folder: {exc}"))
        threading.Thread(target=work, daemon=True, name="QuickDropZip").start()

    def remove_selected_shared(self) -> None:
        selected = self.shared_tree.selection()
        for iid in selected: self.manager.remove_shared(iid)
        if selected: self.status_var.set(f"Removed {len(selected)} item(s)")
        self.refresh_dynamic()

    def clear_shared(self) -> None:
        if self.manager.list_shared() and not messagebox.askyesno("Clear shared files", "Remove all files from this sharing session?\n\nOriginal files will not be deleted."):
            return
        self.manager.clear_shared(); self.status_var.set("Shared list cleared"); self.refresh_dynamic()

    def change_inbox(self) -> None:
        raw = filedialog.askdirectory(initialdir=str(self.manager.inbox), title="Choose received-files folder")
        if not raw: return
        self.manager.inbox = Path(raw).resolve(); self.manager.inbox.mkdir(parents=True, exist_ok=True); self.manager.save_settings()
        self.receive_path_label.configure(text=str(self.manager.inbox)); self.settings_inbox_label.configure(text=str(self.manager.inbox))
        if hasattr(self, "trusted_label"):
            count=len(self.devices.list_public()); self.trusted_label.configure(text=f"{count} trusted device{'s' if count != 1 else ''} currently remembered")
        self.status_var.set("Received-files folder updated")

    def update_quick_text(self) -> None:
        text = self.text_box.get("1.0", "end-1c")
        self.manager.set_quick_text(text); self.text_status.configure(text="Updated — phone can refresh to see this text")
        self.status_var.set("Quick Text updated")

    def copy_quick_text(self) -> None:
        self.copy_to_clipboard(self.text_box.get("1.0", "end-1c"), "Quick Text copied")

    def paste_clipboard(self) -> None:
        try: value = self.root.clipboard_get()
        except tk.TclError: value = ""
        if value:
            self.text_box.delete("1.0", "end"); self.text_box.insert("1.0", value); self.status_var.set("Clipboard pasted")

    def clear_history(self) -> None:
        if not messagebox.askyesno("Clear history", "Clear QuickDrop's local transfer history?\n\nThis does not delete transferred files."):
            return
        self.manager.clear_history()
        self.refresh_dynamic(); self.status_var.set("Transfer history cleared")

    def save_settings(self) -> None:
        self.manager.settings["session_minutes"] = int(self.session_minutes_var.get())
        self.manager.settings["start_server"] = bool(self.start_server_var.get())
        self.manager.settings["allow_downloads"] = bool(self.allow_downloads_var.get())
        self.manager.settings["allow_uploads"] = bool(self.allow_uploads_var.get())
        self.manager.settings["allow_text"] = bool(self.allow_text_var.get())
        self.manager.settings["allow_trusted_devices"] = bool(self.allow_trusted_var.get())
        self.manager.settings["max_upload_mb"] = int(self.max_upload_var.get())
        self.manager.save_settings(); self.status_var.set("Settings saved — session refreshed")
        if self.server.running:
            self.new_session()

    def forget_trusted_devices(self) -> None:
        if not messagebox.askyesno("Forget trusted devices", "Forget every phone remembered by QuickDrop?\n\nThose devices will need the PIN again."):
            return
        self.devices.revoke_all(); self.status_var.set("All trusted devices forgotten"); self.refresh_dynamic()

    def open_discord(self) -> None:
        self.copy_to_clipboard("impreseo", "Discord handle copied: impreseo")
        webbrowser.open(LINKS["Discord"])

    def _poll_ui_queue(self) -> None:
        try:
            while True:
                kind, payload = self.ui_queue.get_nowait()
                if kind == "status": self.status_var.set(str(payload))
                elif kind == "error": messagebox.showerror("QuickDrop", str(payload))
                self.refresh_dynamic()
        except queue.Empty:
            pass
        self.root.after(120, self._poll_ui_queue)

    def _tick(self) -> None:
        self.refresh_dynamic()
        self.root.after(1000, self._tick)

    def refresh_dynamic(self) -> None:
        running = self.server.running
        session = self.server.session
        self.server_dot.configure(fg=GOOD if running else "#59657a")
        self.server_state.configure(text="Sharing on local network" if running else "Server stopped")
        self.session_btn.configure(text="Stop session" if running else "Start session", bg=DANGER if running else ACCENT,
                                   activebackground="#ef7882" if running else ACCENT_HOVER)
        self.pin_var.set(session.pin if session else "------")
        self.url_var.set(self.server.url if running else "Not connected")
        if session:
            seconds = session.remaining_seconds; self.expiry_var.set(f"{seconds // 60:02d}:{seconds % 60:02d} remaining")
            if seconds <= 0 and running:
                self.stop_session(); return
        else:
            self.expiry_var.set("Inactive")
        shared = self.manager.list_shared(); history = self.manager.history()
        sent = sum(1 for row in history if row.get("direction") == "sent")
        received = sum(1 for row in history if row.get("direction") == "received")
        self.stat_labels["shared"].configure(text=str(len(shared))); self.stat_labels["sent"].configure(text=str(sent)); self.stat_labels["received"].configure(text=str(received))
        self.send_hint.configure(text=(f"Phone address: {self.server.url}  •  PIN {session.pin}" if running and session else "Start a session to connect a phone."))
        self._fill_shared(shared); self._fill_history(history); self._fill_received(history)
        if self.root.focus_get() is not self.text_box:
            current = self.text_box.get("1.0", "end-1c")
            if current != self.manager.quick_text:
                self.text_box.delete("1.0", "end"); self.text_box.insert("1.0", self.manager.quick_text)
        self.receive_path_label.configure(text=str(self.manager.inbox)); self.settings_inbox_label.configure(text=str(self.manager.inbox))
        if hasattr(self, "trusted_label"):
            count=len(self.devices.list_public()); self.trusted_label.configure(text=f"{count} trusted device{'s' if count != 1 else ''} currently remembered")

    def _fill_shared(self, items) -> None:
        existing = set(self.shared_tree.get_children()); wanted = {item.id for item in items}
        for iid in existing - wanted: self.shared_tree.delete(iid)
        for item in items:
            values=(item.name, "Folder ZIP" if item.kind=="folder-zip" else "File", human_size(item.size))
            if self.shared_tree.exists(item.id): self.shared_tree.item(item.id, values=values)
            else: self.shared_tree.insert("", "end", iid=item.id, values=values)

    def _fill_history(self, rows: list[dict]) -> None:
        children=self.history_tree.get_children()
        self.history_tree.delete(*children)
        for idx,row in enumerate(rows):
            stamp=datetime.fromtimestamp(row.get("timestamp",0)).strftime("%Y-%m-%d %H:%M")
            self.history_tree.insert("","end",iid=f"h{idx}",values=(stamp,row.get("direction",""),row.get("name",""),human_size(int(row.get("size",0))),row.get("detail","")))

    def _fill_received(self, rows: list[dict]) -> None:
        received=[r for r in rows if r.get("direction")=="received"]
        children=self.receive_tree.get_children()
        self.receive_tree.delete(*children)
        for idx,row in enumerate(received):
            stamp=datetime.fromtimestamp(row.get("timestamp",0)).strftime("%Y-%m-%d %H:%M")
            self.receive_tree.insert("","end",iid=f"r{idx}",values=(stamp,row.get("name",""),human_size(int(row.get("size",0))),row.get("detail","")))

    def close(self) -> None:
        try: self.server.stop()
        finally:
            self.manager.close(); self.root.destroy()


def create_root() -> tk.Tk:
    if TkinterDnD is not None:
        try:
            return TkinterDnD.Tk()
        except Exception:
            pass
    return tk.Tk()


def run() -> None:
    root = create_root()
    QuickDropApp(root)
    root.mainloop()
