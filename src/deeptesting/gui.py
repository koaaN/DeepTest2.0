from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import parse_qs, urlparse

from .heytap_models import HeyTapDeviceProfile
from .hybrid_verify import HybridVerifier
from .unlock_helper import UnlockHelperError, apply_authorization, inspect_device


APP_DIR = Path.home() / ".config" / "deeptesting"
SETTINGS_PATH = APP_DIR / "gui-settings.json"
TOKEN_PATH = APP_DIR / "auth.json"


class DeepTestingApp(tk.Tk):
    BG = "#0b1020"
    SIDEBAR = "#10182b"
    SURFACE = "#151f34"
    SURFACE_2 = "#1b2841"
    BORDER = "#293a58"
    TEXT = "#f4f7fb"
    MUTED = "#91a0b8"
    ACCENT = "#6c7cff"
    ACCENT_HOVER = "#7e8cff"
    SUCCESS = "#45d483"
    WARNING = "#ffbd5c"
    DANGER = "#ff6b7a"

    def __init__(self) -> None:
        super().__init__()
        self.title("DeepTest 2.0")
        self.geometry("1120x760")
        self.minsize(940, 650)
        self.configure(bg=self.BG)
        self.busy = False
        self.active_operation = ""
        self.last_unlock_code = ""
        self.manual_unlock_code = False
        self.manual_unlock_code_value = ""
        self.current_page = "account"
        self.auto_resume_attempts: set[str] = set()
        self.nav_buttons: dict[str, tk.Button] = {}
        self.pages: dict[str, tk.Frame] = {}
        self.scroll_canvases: dict[str, tk.Canvas] = {}
        self.vars: dict[str, tk.Variable] = {}
        self._load_settings()
        self._style()
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(150, self._update_token_status)
        self.after(300, self._refresh_connected_device)
        if Path(str(self.vars["token_cache"].get())).expanduser().is_file():
            self._show_page("device")
        if not str(self.vars["chip_id"].get()).strip():
            self.after(500, self._detect_chip_id)

    def _load_settings(self) -> None:
        defaults: dict[str, object] = {
            "account_type": "Email",
            "account": "",
            "calling_code": "+86",
            "verification_code": "",
            "ticket": "",
            "host": "",
            "model": "PLK110",
            "udid": "",
            "duid": "",
            "ouid": "",
            "device_id": "",
            "ota_version": "PLK110_11.A.68_0680_202606250030",
            "brand": "OnePlus",
            "operator": "",
            "chip_id": "",
            "os_version": "16",
            "app_version": "17000003",
            "lock_status": "0",
            "api_host": "lk-oneplus-cn.allawntech.com",
            "register_keys": False,
            "token_cache": str(TOKEN_PATH),
            "ticket_stage": "verification",
        }
        try:
            saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                defaults.update(saved)
        except (OSError, json.JSONDecodeError):
            pass
        if not str(defaults.get("udid") or "").strip():
            defaults["udid"] = uuid.uuid4().hex
        for key, value in defaults.items():
            cls = tk.BooleanVar if isinstance(value, bool) else tk.StringVar
            self.vars[key] = cls(value=value)

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Modern.TEntry", fieldbackground=self.SURFACE_2, foreground=self.TEXT,
            insertcolor=self.TEXT, bordercolor=self.BORDER, lightcolor=self.BORDER,
            darkcolor=self.BORDER, padding=(12, 9)
        )
        style.map("Modern.TEntry", bordercolor=[("focus", self.ACCENT)])
        style.configure(
            "Modern.TCombobox", fieldbackground=self.SURFACE_2, background=self.SURFACE_2,
            foreground=self.TEXT, arrowcolor=self.MUTED, bordercolor=self.BORDER,
            lightcolor=self.BORDER, darkcolor=self.BORDER, padding=(10, 8)
        )
        style.map(
            "Modern.TCombobox",
            fieldbackground=[("readonly", self.SURFACE_2)],
            foreground=[("readonly", self.TEXT)],
            bordercolor=[("focus", self.ACCENT)],
        )
        style.configure(
            "Modern.Horizontal.TProgressbar", troughcolor=self.SURFACE,
            background=self.ACCENT, borderwidth=0, thickness=3
        )

    def _build(self) -> None:
        shell = tk.Frame(self, bg=self.BG)
        shell.pack(fill="both", expand=True)

        sidebar = tk.Frame(shell, bg=self.SIDEBAR, width=238)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        brand = tk.Frame(sidebar, bg=self.SIDEBAR)
        brand.pack(fill="x", padx=24, pady=(28, 36))
        tk.Label(
            brand, text="D2", width=2, height=1, bg=self.ACCENT, fg="white",
            font=("DejaVu Sans", 18, "bold")
        ).pack(side="left")
        brand_text = tk.Frame(brand, bg=self.SIDEBAR)
        brand_text.pack(side="left", padx=11)
        tk.Label(
            brand_text, text="DEEPTEST 2.0", bg=self.SIDEBAR, fg=self.TEXT,
            font=("DejaVu Sans", 11, "bold")
        ).pack(anchor="w")
        tk.Label(
            brand_text, text="ONEPLUS UNLOCK CLIENT", bg=self.SIDEBAR, fg=self.MUTED,
            font=("DejaVu Sans", 7)
        ).pack(anchor="w")

        tk.Label(
            sidebar, text="WORKSPACE", bg=self.SIDEBAR, fg="#60708c",
            font=("DejaVu Sans", 8, "bold")
        ).pack(anchor="w", padx=25, pady=(0, 8))
        for key, icon, text in (
            ("account", "1", "Account Login"),
            ("device", "2", "Device & unlock"),
            ("activity", "≡", "Technical log"),
        ):
            button = tk.Button(
                sidebar, text=f"  {icon}    {text}", anchor="w", bd=0, relief="flat",
                bg=self.SIDEBAR, fg=self.MUTED, activebackground=self.SURFACE_2,
                activeforeground=self.TEXT, font=("DejaVu Sans", 10),
                padx=18, pady=13, cursor="hand2", command=lambda page=key: self._show_page(page)
            )
            button.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = button

        token_card = tk.Frame(sidebar, bg=self.SURFACE, highlightthickness=1, highlightbackground=self.BORDER)
        token_card.pack(side="bottom", fill="x", padx=16, pady=18)
        tk.Label(
            token_card, text="AUTHORIZATION", bg=self.SURFACE, fg=self.MUTED,
            font=("DejaVu Sans", 8, "bold")
        ).pack(anchor="w", padx=14, pady=(13, 4))
        self.token_status = tk.Label(
            token_card, text="Checking…", bg=self.SURFACE, fg=self.WARNING,
            font=("DejaVu Sans", 9), justify="left", wraplength=180
        )
        self.token_status.pack(anchor="w", padx=14, pady=(0, 14))

        device_card = tk.Frame(
            sidebar, bg=self.SURFACE, highlightthickness=1, highlightbackground=self.BORDER
        )
        device_card.pack(side="bottom", fill="x", padx=16, pady=(0, 0))
        device_heading = tk.Frame(device_card, bg=self.SURFACE)
        device_heading.pack(fill="x", padx=14, pady=(12, 2))
        tk.Label(
            device_heading, text="CONNECTED DEVICE", bg=self.SURFACE, fg=self.MUTED,
            font=("DejaVu Sans", 8, "bold")
        ).pack(side="left")
        refresh = tk.Button(
            device_heading, text="↻", command=self._refresh_connected_device,
            bd=0, relief="flat", bg=self.SURFACE, fg=self.MUTED,
            activebackground=self.SURFACE_2, activeforeground=self.TEXT,
            font=("DejaVu Sans", 11, "bold"), cursor="hand2", padx=4, pady=0
        )
        refresh.pack(side="right")
        self._show_device_ids = False
        self.connected_device_status = tk.Label(
            device_card, text="○  Checking ADB…", bg=self.SURFACE, fg=self.WARNING,
            font=("DejaVu Sans", 9), justify="left", anchor="w", wraplength=180
        )
        self.connected_device_status.pack(fill="x", padx=14, pady=(4, 13))

        main = tk.Frame(shell, bg=self.BG)
        main.pack(side="left", fill="both", expand=True)
        self._show_sensitive = False
        self.sensitive_button = tk.Button(main, text="Show critical information", command=self._toggle_sensitive,
            bd=0, relief="flat", bg=self.SURFACE_2, fg=self.TEXT, activebackground=self.BORDER,
            font=("DejaVu Sans", 8, "bold"), cursor="hand2", padx=10, pady=5)
        self.sensitive_button.pack(anchor="ne", padx=18, pady=(8, 0))
        self.page_host = tk.Frame(main, bg=self.BG)
        self.page_host.pack(fill="both", expand=True)
        for key in ("account", "device", "activity"):
            page = tk.Frame(self.page_host, bg=self.BG)
            page.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.pages[key] = page
        self._build_account(self.pages["account"])
        self._build_device(self.pages["device"])
        self._build_output(self.pages["activity"])
        self._install_scroll_bindings()

        footer = tk.Frame(main, bg=self.SIDEBAR, height=46)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)
        self.status_dot = tk.Label(footer, text="●", bg=self.SIDEBAR, fg=self.SUCCESS, font=("DejaVu Sans", 9))
        self.status_dot.pack(side="left", padx=(22, 7))
        self.status = tk.Label(
            footer, text="Ready", bg=self.SIDEBAR, fg=self.MUTED, font=("DejaVu Sans", 9)
        )
        self.status.pack(side="left")
        self.progress = ttk.Progressbar(
            footer, mode="indeterminate", style="Modern.Horizontal.TProgressbar", length=130
        )
        self.progress.pack(side="right", padx=22)
        self._show_page("account")

    def _show_page(self, key: str) -> None:
        self.current_page = key
        self.pages[key].tkraise()
        for name, button in self.nav_buttons.items():
            active = name == key
            button.configure(
                bg=self.SURFACE_2 if active else self.SIDEBAR,
                fg=self.TEXT if active else self.MUTED,
                font=("DejaVu Sans", 10, "bold" if active else "normal"),
            )

    def _scroll_page(self, parent: tk.Frame, key: str) -> tk.Frame:
        canvas = tk.Canvas(parent, bg=self.BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=self.BG)
        window = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.scroll_canvases[key] = canvas
        return content

    def _install_scroll_bindings(self) -> None:
        def bind_tree(widget: tk.Misc) -> None:
            widget.bind("<MouseWheel>", self._on_page_scroll, add="+")
            widget.bind("<Button-4>", self._on_page_scroll, add="+")
            widget.bind("<Button-5>", self._on_page_scroll, add="+")
            for child in widget.winfo_children():
                bind_tree(child)

        bind_tree(self.pages["account"])
        bind_tree(self.pages["device"])

    def _on_page_scroll(self, event: tk.Event) -> str | None:
        canvas = self.scroll_canvases.get(self.current_page)
        if canvas is None:
            return None
        if getattr(event, "num", None) == 4:
            units = -3
        elif getattr(event, "num", None) == 5:
            units = 3
        else:
            delta = getattr(event, "delta", 0)
            if not delta:
                return None
            units = -3 if delta > 0 else 3
        canvas.yview_scroll(units, "units")
        return "break"

    def _page_header(self, parent: tk.Frame, eyebrow: str, title: str, description: str) -> None:
        tk.Label(
            parent, text=eyebrow.upper(), bg=self.BG, fg=self.ACCENT,
            font=("DejaVu Sans", 8, "bold")
        ).pack(anchor="w")
        tk.Label(
            parent, text=title, bg=self.BG, fg=self.TEXT,
            font=("DejaVu Sans", 25, "bold")
        ).pack(anchor="w", pady=(5, 4))
        tk.Label(
            parent, text=description, bg=self.BG, fg=self.MUTED,
            font=("DejaVu Sans", 10)
        ).pack(anchor="w", pady=(0, 22))

    def _card(self, parent: tk.Frame, title: str, subtitle: str = "") -> tk.Frame:
        outer = tk.Frame(parent, bg=self.SURFACE, highlightthickness=1, highlightbackground=self.BORDER)
        outer.pack(fill="x", pady=(0, 16))
        heading = tk.Frame(outer, bg=self.SURFACE)
        heading.pack(fill="x", padx=22, pady=(18, 13))
        tk.Label(
            heading, text=title, bg=self.SURFACE, fg=self.TEXT,
            font=("DejaVu Sans", 12, "bold")
        ).pack(anchor="w")
        if subtitle:
            tk.Label(
                heading, text=subtitle, bg=self.SURFACE, fg=self.MUTED,
                font=("DejaVu Sans", 9)
            ).pack(anchor="w", pady=(3, 0))
        body = tk.Frame(outer, bg=self.SURFACE)
        body.pack(fill="x", padx=22, pady=(0, 20))
        body.columnconfigure(1, weight=1)
        return body

    def _field(self, parent: tk.Frame, row: int, label: str, key: str, *, column: int = 0) -> ttk.Entry:
        base = column * 2
        tk.Label(
            parent, text=label.upper(), bg=self.SURFACE, fg=self.MUTED,
            font=("DejaVu Sans", 8, "bold")
        ).grid(row=row, column=base, sticky="w", padx=(0, 12), pady=7)
        entry = ttk.Entry(parent, textvariable=self.vars[key], style="Modern.TEntry")
        entry.grid(row=row, column=base + 1, sticky="ew", pady=7, padx=(0, 14 if column == 0 else 0))
        parent.columnconfigure(base + 1, weight=1)
        return entry

    def _button(
        self, parent: tk.Frame, text: str, command: object, *, primary: bool = False,
        danger: bool = False
    ) -> tk.Button:
        color = self.DANGER if danger else self.ACCENT if primary else self.SURFACE_2
        hover = "#ff7c89" if danger else self.ACCENT_HOVER if primary else self.BORDER
        button = tk.Button(
            parent, text=text, command=command, bd=0, relief="flat", bg=color, fg="white",
            activebackground=hover, activeforeground="white", font=("DejaVu Sans", 9, "bold"),
            padx=17, pady=10, cursor="hand2"
        )
        button.bind("<Enter>", lambda _event: button.configure(bg=hover))
        button.bind("<Leave>", lambda _event: button.configure(bg=color))
        return button

    def _build_account(self, frame: tk.Frame) -> None:
        content = self._scroll_page(frame, "account")
        content.configure(padx=34, pady=28)
        self._page_header(
            content, "Step 1 of 2", "Connect your account",
            "Authorize once, then continue to your connected OnePlus device."
        )
        signin = self._card(content, "HeyTap sign in", "A verification code will be sent to your account.")
        tk.Label(
            signin, text="ACCOUNT TYPE", bg=self.SURFACE, fg=self.MUTED,
            font=("DejaVu Sans", 8, "bold")
        ).grid(row=0, column=0, sticky="w", padx=(0, 12), pady=7)
        account_selector = ttk.Combobox(
            signin, textvariable=self.vars["account_type"], values=("Email", "Phone"),
            state="readonly", style="Modern.TCombobox"
        )
        account_selector.grid(row=0, column=1, sticky="ew", pady=7)
        self._field(signin, 1, "Email or phone", "account")
        self._field(signin, 2, "Calling code", "calling_code")
        self._field(signin, 3, "Verification code", "verification_code")
        self._calling_widgets = signin.grid_slaves(row=2)
        self.vars["account_type"].trace_add("write", lambda *_: self._toggle_calling_code())
        self._toggle_calling_code()
        actions = tk.Frame(signin, bg=self.SURFACE)
        actions.grid(row=4, column=1, sticky="w", pady=(12, 0))
        self._button(actions, "Send code", self._send_code).pack(side="left")
        self._button(actions, "Verify & authorize  →", self._verify, primary=True).pack(side="left", padx=9)
        self._button(
            actions, "Continue saved verification", self._continue_saved_verification
        ).pack(side="left")

        auth = self._card(content, "Saved authorization", "Your secure login token is reused between launches.")
        self._field(auth, 0, "Token cache", "token_cache")
        buttons = tk.Frame(auth, bg=self.SURFACE)
        buttons.grid(row=1, column=1, sticky="w", pady=(10, 0))
        self._button(buttons, "Import JSON", self._import_token).pack(side="left")
        self._button(buttons, "Reauthorize", lambda: self._token_action("biz-auth")).pack(side="left", padx=9)
        self._button(buttons, "Refresh authorization", lambda: self._token_action("primary-refresh"), primary=True).pack(side="left")
        self._button(buttons, "Continue to device  →", lambda: self._show_page("device"), primary=True).pack(side="left", padx=9)

    def _toggle_calling_code(self) -> None:
        visible = str(self.vars["account_type"].get()) == "Phone"
        for widget in getattr(self, "_calling_widgets", []):
            (widget.grid if visible else widget.grid_remove)()

    def _build_device(self, frame: tk.Frame) -> None:
        content = self._scroll_page(frame, "device")
        content.configure(padx=34, pady=28)
        self._page_header(
            content, "Step 2 of 2", "Unlock your device",
            "Confirm the detected values, then follow the unlock workflow in order."
        )
        result = tk.Frame(
            content, bg=self.SURFACE_2, highlightthickness=1, highlightbackground=self.ACCENT
        )
        result.pack(fill="x", pady=(0, 16))
        result_copy = tk.Frame(result, bg=self.SURFACE_2)
        result_copy.pack(side="left", fill="x", expand=True, padx=20, pady=15)
        self.device_result_title = tk.Label(
            result_copy, text="Ready for a device request", bg=self.SURFACE_2, fg=self.TEXT,
            font=("DejaVu Sans", 11, "bold")
        )
        self.device_result_title.pack(anchor="w")
        self.device_result_detail = tk.Label(
            result_copy, text="Start with Check eligibility or Check status.",
            bg=self.SURFACE_2, fg=self.MUTED, font=("DejaVu Sans", 9),
            justify="left", wraplength=600
        )
        self.device_result_detail.pack(anchor="w", pady=(3, 0))
        self.copy_code_button = self._button(result, "Copy unlock code", self._copy_unlock_code, primary=True)
        profile = self._card(content, "Target device", "Values are saved locally between sessions.")
        fields = [
            ("Device GUID (UDID)", "udid"),
            ("Model", "model"),
            ("OTA version", "ota_version"),
            ("Chip ID", "chip_id"),
            ("Brand", "brand"),
            ("Operator", "operator"),
            ("OS version", "os_version"),
            ("App version", "app_version"),
            ("Client lock status", "lock_status"),
            ("API host", "api_host"),
        ]
        for index, (label, key) in enumerate(fields):
            entry = self._field(profile, index // 2, label, key, column=index % 2)
            if key == "chip_id":
                entry.configure(show="•")
                self._chip_entry = entry
        check = tk.Checkbutton(
            profile, text="Register fresh cryptographic keys before the request",
            variable=self.vars["register_keys"], bg=self.SURFACE, fg=self.MUTED,
            activebackground=self.SURFACE, activeforeground=self.TEXT, selectcolor=self.SURFACE_2,
            font=("DejaVu Sans", 9)
        )
        check.grid(row=5, column=1, columnspan=3, sticky="w", pady=(10, 0))
        self._button(profile, "Detect Chip ID from ADB", self._detect_chip_id).grid(
            row=6, column=1, sticky="w", pady=(10, 0)
        )

        actions = self._card(content, "Unlock workflow", "Use the first four actions in order.")
        names = [
            ("1  Check eligibility", "Confirm this device can apply", "unlock-condition-match", False),
            ("2  Apply for unlock", "Submit the unlock request", "apply-unlock", True),
            ("3  Check status", "View review and approval state", "get-apply-status", False),
            ("4  Get unlock code", "Retrieve an issued authorization", "get-history-unlock-code", False),
            ("Sync lock state", "Update server-side lock status", "update-client-lock-status", False),
            ("Lock client", "Send the client lock request", "lock-client", True),
        ]
        for index, (title, detail, endpoint, important) in enumerate(names):
            tile = tk.Frame(actions, bg=self.SURFACE_2, highlightthickness=1, highlightbackground=self.BORDER)
            tile.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 8), pady=6)
            tile.columnconfigure(0, weight=1)
            copy = tk.Frame(tile, bg=self.SURFACE_2)
            copy.grid(row=0, column=0, sticky="w", padx=15, pady=13)
            tk.Label(
                copy, text=title, bg=self.SURFACE_2, fg=self.TEXT,
                font=("DejaVu Sans", 10, "bold")
            ).pack(anchor="w")
            tk.Label(
                copy, text=detail, bg=self.SURFACE_2, fg=self.MUTED,
                font=("DejaVu Sans", 8)
            ).pack(anchor="w", pady=(2, 0))
            self._button(
                tile, "Run  →", lambda item=endpoint: self._device_action(item), primary=False
            ).grid(row=0, column=1, padx=12)
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(3, weight=1)

        root_card = self._card(content, "Gain temp root", "Run the local completion script and verify the current root state.")
        root_card.columnconfigure(1, weight=1)
        self.root_status = tk.Label(root_card, text="Ready", bg=self.SURFACE, fg=self.MUTED, font=("DejaVu Sans", 9))
        self._button(root_card, "Run root helper  →", self._run_root_helper, primary=True).grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.root_status.grid(row=0, column=2, sticky="w", padx=(14, 2), pady=4)
        self.root_version = tk.StringVar(value="No version available")
        self.root_version_menu = ttk.Combobox(root_card, textvariable=self.root_version,
            values=("No version available",), state="disabled", width=14, style="Modern.TCombobox")
        self.root_version_menu.grid(row=0, column=0, sticky="w")
        tk.Label(
            root_card,
            text=(
                "Temporary root may take several attempts. Keep the phone awake on the home "
                "screen; disabling System Optimization may improve reliability. If the phone "
                "reboots, unlock it and try again."
            ),
            bg=self.SURFACE,
            fg=self.WARNING,
            font=("DejaVu Sans", 8),
            justify="left",
            wraplength=900,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))

        helper = self._card(
            content,
            "Install unlock authorization",
            "Back up, patch, and write the approved authorization to oplusreserve1.",
        )
        helper.columnconfigure(1, weight=1)
        steps = tk.Frame(helper, bg=self.SURFACE_2, highlightthickness=1, highlightbackground=self.BORDER)
        steps.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(2, 12))
        tk.Label(
            steps,
            text="REQUIRES",
            bg=self.SURFACE_2,
            fg=self.MUTED,
            font=("DejaVu Sans", 8, "bold"),
        ).pack(anchor="w", padx=15, pady=(12, 5))
        self.helper_readiness = tk.Label(
            steps,
            text="ADB device  •  root access  •  issued unlock code",
            bg=self.SURFACE_2,
            fg=self.MUTED,
            font=("DejaVu Sans", 9),
            justify="left",
        )
        self.helper_readiness.pack(anchor="w", padx=15, pady=(0, 12))
        helper_buttons = tk.Frame(helper, bg=self.SURFACE)
        helper_buttons.grid(row=1, column=0, columnspan=2, sticky="ew")
        self._button(helper_buttons, "Check requirements", self._check_unlock_helper).pack(side="left")
        self.apply_helper_button = self._button(
            helper_buttons,
            "Apply authorization to phone  →",
            self._apply_unlock_authorization,
            primary=True,
        )
        self.apply_helper_button.pack(side="left", padx=9)
        self.apply_helper_button.configure(state="disabled")
        self._button(
            helper_buttons, "Enter unlock code", self._enter_unlock_code
        ).pack(side="right")
        tk.Label(
            helper,
            text="Creates a local backup first. This writes oplusreserve1 but does not reboot, wipe, or unlock bootloader.",
            bg=self.SURFACE,
            fg=self.MUTED,
            font=("DejaVu Sans", 8),
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.reboot_bootloader_button = self._button(
            helper, "Reboot to bootloader", self._reboot_to_bootloader, primary=True
        )
        self.reboot_bootloader_button.grid(row=3, column=1, sticky="e", pady=(14, 0))
        self.reboot_bootloader_button.configure(state="disabled")

    def _run_root_helper(self) -> None:
        """Run only the bundled harmless completion script; do not execute a preload payload."""
        self.root_status.configure(text="Running…", fg=self.WARNING)
        self._append("$ root helper started…\n")
        self.update_idletasks()
        _, _, _, prj_id = getattr(self, "_connected_device_info", ("", "", "", ""))
        target_folder = {"24831": "OP15", "24855": "ACE6T"}.get(prj_id, "OP15")
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
        version = self.root_version.get()
        script_dir = bundle_root / "android-helper" / "assets" / target_folder / version
        script = script_dir / ("root.bat" if os.name == "nt" else "root.sh")

        def worker() -> None:
            try:
                command = ["cmd", "/c", str(script)] if os.name == "nt" else ["sh", str(script)]
                helper_env = os.environ.copy()
                if os.name != "nt" and getattr(sys, "frozen", False):
                    original_library_path = helper_env.pop("LD_LIBRARY_PATH_ORIG", "")
                    if original_library_path:
                        helper_env["LD_LIBRARY_PATH"] = original_library_path
                    else:
                        helper_env.pop("LD_LIBRARY_PATH", None)
                result = subprocess.run(
                    command, cwd=str(script_dir),
                    capture_output=True, text=True, env=helper_env,
                )
                output = (result.stdout + result.stderr).strip().lower()
                ok = result.returncode == 0 and ("root complete" in output or "uid=0(root)" in output)
                detail = "Complete — root complete" if ok else ("Failed — script returned an error" if result.returncode else "Failed — completion message missing")
                self.after(0, self._root_helper_finished, ok, detail, result.stdout + result.stderr)
            except Exception as exc:
                self.after(0, self._root_helper_finished, False, f"Failed — {exc}", "")

        threading.Thread(target=worker, daemon=True).start()

    def _root_helper_finished(self, success: bool, detail: str, output: str = "") -> None:
        self.root_status.configure(text=detail, fg=self.SUCCESS if success else self.DANGER)
        if output.strip():
            self._append(output.rstrip() + "\n")
        self._append(f"root helper: {'complete' if success else 'failed'}\n\n")

    def _reboot_to_bootloader(self) -> None:
        if self.busy:
            return
        try:
            device = inspect_device()
            adb = shutil.which("adb")
            if not adb:
                raise UnlockHelperError("ADB is not installed or unavailable.")
            result = subprocess.run([adb, "-s", device.serial, "reboot", "bootloader"], capture_output=True, text=True, timeout=15)
            if result.returncode:
                raise UnlockHelperError((result.stderr or result.stdout).strip() or "ADB reboot failed.")
            self.reboot_bootloader_button.configure(state="disabled")
            self.status.configure(text="Rebooting to bootloader…")
        except Exception as exc:
            messagebox.showerror("Could not reboot", str(exc))

    def _build_output(self, frame: tk.Frame) -> None:
        top = tk.Frame(frame, bg=self.BG)
        top.pack(fill="x", padx=34, pady=(28, 18))
        title = tk.Frame(top, bg=self.BG)
        title.pack(side="left")
        self._page_header(title, "Diagnostics", "Technical log", "Raw requests and server responses appear here.")
        self._button(top, "Clear console", self._clear_output).pack(side="right", anchor="n")
        console = tk.Frame(frame, bg="#080d18", highlightthickness=1, highlightbackground=self.BORDER)
        console.pack(fill="both", expand=True, padx=34, pady=(0, 30))
        bar = tk.Frame(console, bg=self.SURFACE, height=38)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        for color in (self.DANGER, self.WARNING, self.SUCCESS):
            tk.Label(bar, text="●", bg=self.SURFACE, fg=color, font=("DejaVu Sans", 10)).pack(
                side="left", padx=(12 if color == self.DANGER else 0, 5)
            )
        tk.Label(
            bar, text="deeptest-2.0 / activity", bg=self.SURFACE, fg=self.MUTED,
            font=("DejaVu Sans Mono", 8)
        ).pack(side="left", padx=10)
        text_wrap = tk.Frame(console, bg="#080d18")
        text_wrap.pack(fill="both", expand=True, padx=2, pady=2)
        self.output = tk.Text(
            text_wrap, wrap="word", font=("DejaVu Sans Mono", 9), state="disabled",
            bg="#080d18", fg="#c7d2e5", insertbackground=self.TEXT, bd=0,
            padx=18, pady=16, selectbackground=self.ACCENT
        )
        scroll = ttk.Scrollbar(text_wrap, orient="vertical", command=self.output.yview)
        self.output.configure(yscrollcommand=scroll.set)
        self.output.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _auth_options(self) -> list[str]:
        args = ["--model", str(self.vars["model"].get())]
        mapping = {"host": "--host", "duid": "--duid", "ouid": "--ouid", "udid": "--guid", "device_id": "--device-id"}
        for key, flag in mapping.items():
            value = str(self.vars[key].get()).strip()
            if value:
                args += [flag, value]
        return args

    def _token_prefix(self) -> list[str]:
        return ["-m", "deeptesting.token_cli", "--token-cache", str(self.vars["token_cache"].get())]

    def _send_code(self) -> None:
        account = str(self.vars["account"].get()).strip()
        if not account:
            messagebox.showwarning("Missing account", "Enter an email address or phone number.")
            return
        self.auto_resume_attempts.clear()
        args = self._token_prefix() + ["login"]
        if self.vars["account_type"].get() == "Phone":
            args += ["--phone", account, "--country-calling-code", str(self.vars["calling_code"].get())]
        else:
            args += ["--email", account]
        self._run(args + self._auth_options(), "Sending verification code…")

    def _verify(self) -> None:
        code = str(self.vars["verification_code"].get()).strip()
        if not code:
            messagebox.showwarning("Missing code", "Enter the verification code you received.")
            return
        self._run(self._token_prefix() + ["verify", code] + self._auth_options(), "Verifying and authorizing…")

    def _continue_saved_verification(self) -> None:
        session_path = APP_DIR / "login-session.json"
        try:
            session = json.loads(session_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            messagebox.showwarning("No saved verification", "There is no usable saved login session.")
            return
        if not isinstance(session, dict) or not session.get("process_token"):
            messagebox.showwarning("No saved verification", "The saved login session has no process token.")
            return
        self._start_hybrid_verification({
            "status": "interaction_required",
            "kind": "verification",
            "url": "",
        })

    def _resume_saved_stage(self, stage: str) -> bool:
        ticket = self._saved_login_ticket()
        if not ticket:
            return False
        self.vars["ticket"].set(ticket)
        self.vars["ticket_stage"].set(stage)
        args = self._token_prefix() + [
            "resume", "--stage", stage, "--ticket", ticket
        ] + self._auth_options()
        self._run(args, f"Continuing {stage} automatically…")
        return True

    def _resume(self) -> None:
        ticket = str(self.vars["ticket"].get()).strip()
        if not ticket:
            messagebox.showwarning("Missing ticket", "Enter the challenge ticket.")
            return
        args = self._token_prefix() + [
            "resume", "--stage", str(self.vars["ticket_stage"].get()), "--ticket", ticket
        ] + self._auth_options()
        self._run(args, "Resuming verification…")

    @staticmethod
    def _ticket_from_input(value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        if "://" not in value:
            return value
        parsed = urlparse(value)
        query = parse_qs(parsed.query)
        fragment = parse_qs(parsed.fragment)
        for key in ("ticket", "verifyTicket", "verificationTicket", "token"):
            candidate = query.get(key) or fragment.get(key)
            if candidate and candidate[0]:
                return candidate[0]
        return ""

    def _start_hybrid_verification(self, challenge: dict[str, object]) -> None:
        self.status.configure(text="Loading available identity checks…")
        self.status_dot.configure(fg=self.WARNING)
        self.progress.start(12)

        def worker() -> None:
            try:
                device = HeyTapDeviceProfile(
                    model=str(self.vars["model"].get()),
                    duid=str(self.vars["duid"].get()),
                    ouid=str(self.vars["ouid"].get()),
                    guid=str(self.vars["udid"].get()),
                    device_id=str(self.vars["device_id"].get()),
                )
                verifier = HybridVerifier(device=device)
                methods = verifier.methods()
            except Exception as exc:
                self.after(0, self._hybrid_discovery_failed, challenge, str(exc))
                return
            self.after(0, self._hybrid_methods_ready, challenge, verifier, methods)

        threading.Thread(target=worker, daemon=True).start()

    def _hybrid_discovery_failed(self, challenge: dict[str, object], error: str) -> None:
        self.progress.stop()
        self._append(f"Could not load direct identity verification: {error}\n\n")
        if "200052" in error or "200047" in error:
            self.status.configure(text="Saved login session expired; existing authorization is unaffected")
            self.status_dot.configure(fg=self.WARNING)
            messagebox.showinfo(
                "Saved login expired",
                "This login attempt has expired and cannot be continued.\n\n"
                "Your existing auth.json authorization is still ready for device requests. "
                "To authorize another account, start a new email/SMS login or import its token JSON.",
            )
            return
        self._show_challenge(challenge)

    def _hybrid_methods_ready(
        self,
        challenge: dict[str, object],
        verifier: HybridVerifier,
        data: dict[str, object],
    ) -> None:
        self.progress.stop()
        methods = data.get("verMethodList")
        if not isinstance(methods, list):
            self._append("HeyTap returned no usable identity methods.\n\n")
            self._show_challenge(challenge)
            return
        password_method = next(
            (
                item for item in methods
                if isinstance(item, dict) and item.get("verMethod") == "PASSWORD"
            ),
            None,
        )
        if not password_method:
            names = [
                str(item.get("verMethod"))
                for item in methods if isinstance(item, dict) and item.get("verMethod")
            ]
            self._append(f"Unsupported identity methods: {', '.join(names) or 'none'}\n\n")
            self._show_challenge(challenge)
            return
        show_info = password_method.get("showInfo")
        account = str(show_info.get("accountName") or "") if isinstance(show_info, dict) else ""
        self._show_password_verification(verifier, account)

    def _show_password_verification(self, verifier: HybridVerifier, account: str) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Verify HeyTap password")
        dialog.geometry("520x330")
        dialog.resizable(False, False)
        dialog.configure(bg=self.BG)
        dialog.transient(self)
        dialog.grab_set()

        body = tk.Frame(dialog, bg=self.BG, padx=30, pady=27)
        body.pack(fill="both", expand=True)
        tk.Label(
            body, text="FINAL IDENTITY CHECK", bg=self.BG, fg=self.SUCCESS,
            font=("DejaVu Sans", 8, "bold")
        ).pack(anchor="w")
        tk.Label(
            body, text="Enter your HeyTap password", bg=self.BG, fg=self.TEXT,
            font=("DejaVu Sans", 20, "bold")
        ).pack(anchor="w", pady=(6, 6))
        tk.Label(
            body,
            text=f"HeyTap requires the account password for {account or 'this account'}.",
            bg=self.BG, fg=self.MUTED, font=("DejaVu Sans", 10)
        ).pack(anchor="w", pady=(0, 19))
        tk.Label(
            body, text="PASSWORD", bg=self.BG, fg=self.MUTED,
            font=("DejaVu Sans", 8, "bold")
        ).pack(anchor="w", pady=(0, 7))
        password = tk.StringVar()
        entry = ttk.Entry(body, textvariable=password, show="●", style="Modern.TEntry")
        entry.pack(fill="x")
        error = tk.Label(body, text="", bg=self.BG, fg=self.DANGER, font=("DejaVu Sans", 8))
        error.pack(anchor="w", pady=(6, 0))
        buttons = tk.Frame(body, bg=self.BG)
        buttons.pack(fill="x", pady=(15, 0))
        submit = self._button(buttons, "Verify password  →", lambda: verify(), primary=True)
        submit.pack(side="right")

        def verify() -> None:
            secret = password.get()
            if not secret:
                error.configure(text="Enter your HeyTap account password.")
                return
            entry.configure(state="disabled")
            submit.configure(state="disabled")
            error.configure(text="Verifying securely…", fg=self.WARNING)
            self.progress.start(12)

            def worker() -> None:
                try:
                    ticket = verifier.verify_password(secret)
                except Exception as exc:
                    self.after(0, failed, str(exc))
                    return
                self.after(0, succeeded, ticket)

            threading.Thread(target=worker, daemon=True).start()

        def failed(reason: str) -> None:
            self.progress.stop()
            password.set("")
            entry.configure(state="normal")
            submit.configure(state="normal")
            error.configure(text=reason, fg=self.DANGER)
            entry.focus_set()

        def succeeded(ticket: str) -> None:
            self.progress.stop()
            password.set("")
            self.vars["ticket"].set(ticket)
            self.vars["ticket_stage"].set("verification")
            dialog.destroy()
            self._resume()

        dialog.bind("<Return>", lambda _event: verify())
        entry.focus_set()

    def _show_challenge(self, challenge: dict[str, object]) -> None:
        url = str(challenge.get("url") or "")
        stage = str(challenge.get("kind") or "verification")
        if stage not in {"verification", "completion"}:
            stage = "verification"
        self.vars["ticket_stage"].set(stage)

        dialog = tk.Toplevel(self)
        dialog.title("Additional verification required")
        dialog.geometry("620x440")
        dialog.minsize(540, 400)
        dialog.configure(bg=self.BG)
        dialog.transient(self)
        dialog.grab_set()

        body = tk.Frame(dialog, bg=self.BG, padx=30, pady=26)
        body.pack(fill="both", expand=True)
        tk.Label(
            body, text="IDENTITY CHECK", bg=self.BG, fg=self.WARNING,
            font=("DejaVu Sans", 8, "bold")
        ).pack(anchor="w")
        tk.Label(
            body, text="One more security step", bg=self.BG, fg=self.TEXT,
            font=("DejaVu Sans", 21, "bold")
        ).pack(anchor="w", pady=(6, 7))
        tk.Label(
            body,
            text=(
                "HeyTap accepted your SMS code, but requires identity verification "
                "on a trusted mobile device before it can authorize DeepTesting."
            ),
            bg=self.BG, fg=self.MUTED, justify="left", wraplength=545,
            font=("DejaVu Sans", 10)
        ).pack(anchor="w", pady=(0, 18))

        steps = tk.Frame(body, bg=self.SURFACE, highlightthickness=1, highlightbackground=self.BORDER)
        steps.pack(fill="x")
        for number, text in (
            ("1", "Open the check on your OnePlus or OPPO phone."),
            ("2", "Complete the identity check in the phone browser."),
            ("3", "Return here and click “I completed verification”."),
        ):
            row = tk.Frame(steps, bg=self.SURFACE)
            row.pack(fill="x", padx=16, pady=7)
            tk.Label(
                row, text=number, width=2, bg=self.ACCENT, fg="white",
                font=("DejaVu Sans", 8, "bold")
            ).pack(side="left")
            tk.Label(
                row, text=text, bg=self.SURFACE, fg=self.TEXT,
                font=("DejaVu Sans", 9)
            ).pack(side="left", padx=10)

        value = tk.StringVar()
        fallback = tk.Frame(body, bg=self.BG)
        fallback.pack(fill="x", pady=(16, 0))
        tk.Label(
            fallback, text="OPTIONAL: REPLACEMENT TICKET", bg=self.BG, fg=self.MUTED,
            font=("DejaVu Sans", 8, "bold")
        ).pack(anchor="w", pady=(0, 7))
        entry = ttk.Entry(fallback, textvariable=value, style="Modern.TEntry")
        entry.pack(fill="x")
        tk.Label(
            fallback, text="Usually leave this empty—the ticket from your login session is reused.",
            bg=self.BG, fg=self.MUTED, font=("DejaVu Sans", 8)
        ).pack(anchor="w", pady=(5, 0))

        error = tk.Label(body, text="", bg=self.BG, fg=self.DANGER, font=("DejaVu Sans", 8))
        error.pack(anchor="w", pady=(5, 0))
        buttons = tk.Frame(body, bg=self.BG)
        buttons.pack(fill="x", pady=(13, 0))

        def open_challenge() -> None:
            if not url or not webbrowser.open(url):
                self.clipboard_clear()
                self.clipboard_append(url)
                error.configure(text="Could not open the browser. The verification URL was copied.")

        def open_on_phone() -> None:
            adb = shutil.which("adb")
            if not adb:
                self.clipboard_clear()
                self.clipboard_append(url)
                error.configure(text="ADB is not installed. The URL was copied; open it on your phone.")
                return
            try:
                result = subprocess.run(
                    [adb, "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url],
                    capture_output=True, text=True, timeout=10
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                error.configure(text=f"Could not contact the phone: {exc}")
                return
            if result.returncode:
                error.configure(text="No authorized Android device found. Connect it with USB debugging enabled.")
            else:
                error.configure(text="Opened on the connected phone. Complete the check there.")

        def continue_login() -> None:
            ticket = self._ticket_from_input(value.get()) or self._saved_login_ticket()
            if not ticket:
                error.configure(text="The saved login ticket is missing. Paste a replacement ticket.")
                entry.focus_set()
                return
            self.vars["ticket"].set(ticket)
            dialog.destroy()
            self._resume()

        self._button(buttons, "Open on this computer", open_challenge).pack(side="left")
        self._button(buttons, "Open on phone  ↗", open_on_phone, primary=True).pack(side="left", padx=8)
        self._button(buttons, "I completed verification  →", continue_login, primary=True).pack(side="right")
        dialog.bind("<Return>", lambda _event: continue_login())

    @staticmethod
    def _saved_login_ticket() -> str:
        path = APP_DIR / "login-session.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""
        return str(value.get("ticket") or "") if isinstance(value, dict) else ""

    def _token_action(self, action: str) -> None:
        self._run(self._token_prefix() + [action] + self._auth_options(), "Updating authorization…")

    def _import_token(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose authorization JSON", filetypes=(("JSON files", "*.json"), ("All files", "*"))
        )
        if path:
            self._run(self._token_prefix() + ["import", path], "Importing authorization…")

    def _device_action(self, endpoint: str) -> None:
        udid = str(self.vars["udid"].get()).strip()
        if not udid:
            messagebox.showwarning("Missing device GUID", "Enter the device GUID (UDID) first.")
            return
        if endpoint == "apply-unlock" and not messagebox.askyesno(
            "Submit unlock application?",
            "This will submit an unlock application for the configured device. Continue?",
        ):
            return
        if endpoint == "lock-client" and not messagebox.askyesno(
            "Lock client?",
            "This action changes the client lock state. Continue?",
        ):
            return
        args = [
            "-m", "deeptesting.cli", endpoint,
            "--token-cache", str(self.vars["token_cache"].get()),
            "--udid", udid,
            "--model", str(self.vars["model"].get()),
            "--ota-version", str(self.vars["ota_version"].get()),
            "--brand", str(self.vars["brand"].get()),
            "--operator", str(self.vars["operator"].get()),
            "--chip-id", str(self.vars["chip_id"].get()),
            "--os-version", str(self.vars["os_version"].get()),
            "--app-version", str(self.vars["app_version"].get()),
            "--client-lock-status", str(self.vars["lock_status"].get()),
            "--host", str(self.vars["api_host"].get()),
        ]
        if self.vars["register_keys"].get():
            args.append("--register-keys")
        self._run(args, f"Running {endpoint}…")

    def _copy_unlock_code(self) -> None:
        code = self._effective_unlock_code()
        if not code:
            return
        self.clipboard_clear()
        self.clipboard_append(code)
        self.status.configure(text="Unlock code copied to clipboard")
        self.status_dot.configure(fg=self.SUCCESS)

    def _effective_unlock_code(self) -> str:
        return self.manual_unlock_code_value or self.last_unlock_code

    def _enter_unlock_code(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Enter unlock code")
        dialog.configure(bg=self.SURFACE)
        dialog.transient(self)

        tk.Label(
            dialog,
            text="Enter the 632-character hexadecimal unlock code",
            bg=self.SURFACE,
            fg=self.TEXT,
            font=("DejaVu Sans", 11, "bold"),
        ).pack(anchor="w", padx=20, pady=(18, 5))
        tk.Label(
            dialog,
            text="Only hexadecimal characters 0–9 and A–F are accepted.",
            bg=self.SURFACE,
            fg=self.MUTED,
            font=("DejaVu Sans", 9),
        ).pack(anchor="w", padx=20, pady=(0, 12))

        result: list[str] = []

        entry = tk.Entry(
            dialog,
            bg=self.SURFACE_2,
            fg=self.TEXT,
            insertbackground=self.TEXT,
            relief="flat",
            font=("DejaVu Sans Mono", 9),
            width=82,
        )
        entry.pack(fill="x", padx=20, ipady=9)

        footer = tk.Frame(dialog, bg=self.SURFACE)
        footer.pack(fill="x", padx=20, pady=16)
        count_label = tk.Label(
            footer, text="0 / 632", bg=self.SURFACE, fg=self.WARNING,
            font=("DejaVu Sans", 9),
        )
        count_label.pack(side="left")

        def accept() -> None:
            code = entry.get()
            if len(code) == 632:
                result.append(code)
                dialog.destroy()

        load_button = self._button(footer, "Load code", accept, primary=True)
        load_button.pack(side="right")
        load_button.configure(state="disabled")
        self._button(footer, "Cancel", dialog.destroy).pack(side="right", padx=(0, 8))
        self._button(footer, "Clear", lambda: entry.delete(0, "end")).pack(
            side="right", padx=(0, 8)
        )

        def validate_input(candidate: str) -> bool:
            return len(candidate) <= 632 and re.fullmatch(r"[0-9a-fA-F]*", candidate) is not None

        def refresh_input_state() -> None:
            if not dialog.winfo_exists():
                return
            length = len(entry.get())
            ready = length == 632
            count_label.configure(
                text=f"{length} / 632",
                fg=self.SUCCESS if ready else self.WARNING,
            )
            load_button.configure(state="normal" if ready else "disabled")
            dialog.after(75, refresh_input_state)

        entry.configure(
            validate="key",
            validatecommand=(dialog.register(validate_input), "%P"),
        )
        dialog.after(75, refresh_input_state)

        def select_all(_event: object = None) -> str:
            entry.selection_range(0, "end")
            entry.icursor("end")
            return "break"

        def paste_code(_event: object = None) -> str:
            entry.focus_force()
            dialog.update_idletasks()
            before = entry.get()

            def native_paste() -> None:
                entry.focus_force()
                entry.selection_range(0, "end")
                entry.event_generate("<<Paste>>")

            def fallback_paste() -> None:
                if entry.get() == before:
                    native_paste()

            dialog.after(20, native_paste)
            dialog.after(150, fallback_paste)
            return "break"

        entry.bind("<Control-a>", select_all)
        entry.bind("<Control-A>", select_all)
        entry.bind("<Control-v>", paste_code)
        entry.bind("<Control-V>", paste_code)
        dialog.bind("<Control-a>", select_all)
        dialog.bind("<Control-A>", select_all)
        dialog.bind("<Control-v>", paste_code)
        dialog.bind("<Control-V>", paste_code)
        paste_button = self._button(footer, "Paste clipboard", paste_code)
        paste_button.bind("<ButtonPress-1>", paste_code)
        paste_button.pack(side="left", padx=(12, 0))
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.bind("<Return>", lambda _event: accept())
        dialog.update_idletasks()
        width = 820
        height = 230
        x = self.winfo_rootx() + max(20, (self.winfo_width() - width) // 2)
        y = self.winfo_rooty() + max(40, (self.winfo_height() - height) // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")
        dialog.resizable(False, False)
        dialog.lift()
        dialog.wait_visibility()
        dialog.grab_set()
        entry.focus_force()
        dialog.update()
        dialog.after(150, entry.focus_force)
        dialog.after(400, entry.focus_force)
        self.wait_window(dialog)

        if not result:
            return
        code = result[0]
        self.last_unlock_code = code
        self.manual_unlock_code = True
        self.manual_unlock_code_value = code
        self.apply_helper_button.configure(state="normal")
        self._helper_readiness_code = "Unlock code ready"
        if hasattr(self, "_helper_readiness_root"):
            self._helper_readiness_color = self.SUCCESS if self._helper_readiness_root == "root ready" else self.WARNING
            self._render_helper_readiness()
        else:
            self.helper_readiness.configure(
                text="Unlock code ready  •  run Check requirements",
                fg=self.WARNING,
            )
        self.status.configure(text="Manual unlock code loaded")
        self.status_dot.configure(fg=self.SUCCESS)

    def _show_device_result(self, endpoint: str, payload: dict[str, object]) -> None:
        code = payload.get("code")
        data = payload.get("data")
        title = "Request completed"
        detail = str(payload.get("message") or "")
        color = self.SUCCESS if code == 200 else self.WARNING
        unlock_code = ""

        if isinstance(data, dict):
            candidate = data.get("unlockCode")
            unlock_code = candidate if isinstance(candidate, str) else ""
        elif endpoint == "get-history-unlock-code" and isinstance(data, str):
            unlock_code = data

        if unlock_code:
            self.last_unlock_code = unlock_code
            self.manual_unlock_code = False
            self.manual_unlock_code_value = ""
            self.apply_helper_button.configure(state="normal")
            title = "Unlock approved — code ready"
            detail = "Your signed unlock authorization was issued. Copy it and keep it private."
            self.copy_code_button.pack(side="right", padx=20, pady=15)
        elif not self.manual_unlock_code:
            self.last_unlock_code = ""
            self.apply_helper_button.configure(state="disabled")
            self.copy_code_button.pack_forget()

        if endpoint == "apply-unlock" and code == 200:
            title = "Application submitted"
            expected = data.get("exceptPassTime") if isinstance(data, dict) else None
            if isinstance(expected, (int, float)):
                when = datetime.fromtimestamp(expected / 1000).astimezone()
                detail = f"Expected review time: {when:%d %B %Y at %H:%M %Z}."
            else:
                detail = "The server accepted your unlock application."
        elif endpoint == "get-apply-status" and isinstance(data, dict):
            review = data.get("reviewStatus")
            if review == 2:
                title = "Application approved"
                detail = "This device is approved for unlocking."
            elif data.get("hasUnlockRecord"):
                title = "Application under review"
                detail = "An unlock application exists. Check again after the expected review time."
        elif code == -1019:
            title = "No application yet"
            detail = "This device has no unlock application. Check eligibility, then apply."
        elif code == -1018:
            title = "Unlock code not ready"
            detail = "No unlock code has been issued yet. Check the application status first."
        elif endpoint == "unlock-condition-match" and code == 200:
            title = "Device is eligible"
            detail = "The eligibility check passed. You can submit an unlock application."
        elif code != 200:
            title = "The server declined this request"
            color = self.DANGER

        self.device_result_title.configure(text=title, fg=color)
        self.device_result_detail.configure(text=detail)
        self._show_page("device")

    def _check_unlock_helper(self) -> None:
        if self.busy:
            messagebox.showinfo("Please wait", "Another operation is still running.")
            return
        self.helper_readiness.configure(text="Checking the connected phone…", fg=self.WARNING)

        def worker() -> None:
            try:
                device = inspect_device()
            except UnlockHelperError as exc:
                self.after(0, self._unlock_helper_checked, None, str(exc))
                return
            self.after(0, self._unlock_helper_checked, device, "")

        threading.Thread(target=worker, daemon=True).start()

    def _unlock_helper_checked(self, device: object, error: str) -> None:
        if error:
            self.helper_readiness.configure(text=f"Not ready — {error}", fg=self.DANGER)
            return
        model = getattr(device, "model", "Android device")
        serial = getattr(device, "serial", "")
        self._helper_device_model = model
        self._helper_device_serial = serial
        rooted = bool(getattr(device, "rooted", False))
        unlock_code = self._effective_unlock_code()
        code_status = "Unlock code ready" if unlock_code else "run Check status to load code"
        root_status = "root ready" if rooted else "root permission missing"
        color = self.SUCCESS if rooted and unlock_code else self.WARNING
        self._helper_readiness_root = root_status
        self._helper_readiness_code = code_status
        self._helper_readiness_color = color
        self._render_helper_readiness()

    def _render_helper_readiness(self) -> None:
        model = getattr(self, "_helper_device_model", "Android device")
        serial = getattr(self, "_helper_device_serial", "")
        shown = serial if self._show_sensitive else ("*" * len(serial) if serial else "unknown")
        root_status = getattr(self, "_helper_readiness_root", "")
        code_status = getattr(self, "_helper_readiness_code", "")
        if root_status and code_status:
            self.helper_readiness.configure(text=f"{model} ({shown})  •  {root_status}  •  {code_status}", fg=self._helper_readiness_color)

    def _apply_unlock_authorization(self) -> None:
        code = self._effective_unlock_code()
        if not code:
            messagebox.showwarning(
                "Unlock code not loaded",
                "Run Check status, Get unlock code, or enter the unlock code manually first.",
            )
            return
        if self.busy:
            messagebox.showinfo("Please wait", "Another operation is still running.")
            return
        if not messagebox.askyesno(
            "Apply authorization to this phone?",
            "This will call the rooted Oplus engineer service with the issued unlock "
            "authorization. It will not reboot or erase the phone.\n\nContinue?",
        ):
            return

        self.reboot_bootloader_button.configure(state="disabled")
        self.busy = True
        self.status.configure(text="Applying unlock authorization to the phone…")
        self.status_dot.configure(fg=self.WARNING)
        self.progress.start(12)
        self._append("$ adb … FastbootUnlockHelper ••••\n")

        def worker() -> None:
            try:
                output = apply_authorization(code)
            except UnlockHelperError as exc:
                self.after(0, self._unlock_authorization_finished, False, str(exc))
                return
            self.after(0, self._unlock_authorization_finished, True, output)

        threading.Thread(target=worker, daemon=True).start()

    def _unlock_authorization_finished(self, success: bool, detail: str) -> None:
        self.busy = False
        self.progress.stop()
        if success:
            self.reboot_bootloader_button.configure(state="normal")
            self.device_result_title.configure(
                text="Authorization installed on phone", fg=self.SUCCESS
            )
            self.device_result_detail.configure(
                text="The patched reserve image was written. No reboot, wipe, or bootloader unlock was performed."
            )
            self.helper_readiness.configure(
                text="Ready — reserve image patched and flashed", fg=self.SUCCESS
            )
            self.status.configure(text="Phone accepted the unlock authorization")
            self.status_dot.configure(fg=self.SUCCESS)
            safe_lines = [
                line for line in detail.splitlines()
                if not line.lower().startswith("authorization")
            ]
            self._append("\n".join(safe_lines) + "\n\n")
        else:
            self.reboot_bootloader_button.configure(state="disabled")
            self.device_result_title.configure(
                text="Phone did not accept the authorization", fg=self.DANGER
            )
            self.device_result_detail.configure(text=detail)
            self.helper_readiness.configure(text=f"Not ready — {detail}", fg=self.DANGER)
            self.status.configure(text="Authorization helper failed")
            self.status_dot.configure(fg=self.DANGER)
            self._append(f"error: {detail}\n\n")
        self._show_page("device")

    def _detect_chip_id(self) -> None:
        adb = shutil.which("adb")
        if not adb:
            messagebox.showerror("ADB not found", "Install Android platform-tools and reconnect the phone.")
            return
        self.status.configure(text="Reading Chip ID from the connected phone…")
        self.status_dot.configure(fg=self.WARNING)

        def worker() -> None:
            commands = (
                [adb, "shell", "cat", "/proc/oplusVersion/serialID"],
                [adb, "shell", "getprop", "ro.boot.chipid"],
            )
            for index, command in enumerate(commands):
                try:
                    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    continue
                value = result.stdout.strip()
                if result.returncode == 0 and value:
                    if index == 1 and not value.lower().startswith("0x"):
                        value = "0x" + value
                    self.after(0, self._chip_id_detected, value)
                    return
            self.after(
                0,
                lambda: messagebox.showerror(
                    "Chip ID unavailable",
                    "ADB could not read /proc/oplusVersion/serialID or ro.boot.chipid.",
                ),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_connected_device(self) -> None:
        adb = shutil.which("adb")
        if not adb:
            self.connected_device_status.configure(
                text="○  ADB not installed", fg=self.DANGER
            )
            return
        self.connected_device_status.configure(text="○  Checking ADB…", fg=self.WARNING)

        def worker() -> None:
            try:
                result = subprocess.run(
                    [adb, "devices", "-l"], capture_output=True, text=True, timeout=10
                )
            except (OSError, subprocess.TimeoutExpired):
                self.after(0, self._connected_device_updated, "", "", "ADB did not respond")
                return
            device_line = next(
                (
                    line.strip() for line in result.stdout.splitlines()[1:]
                    if line.strip() and " device" in f" {line}"
                ),
                "",
            )
            if not device_line:
                self.after(0, self._connected_device_updated, "", "", "No authorized device")
                return
            parts = device_line.split()
            serial = parts[0]
            properties = {
                key: value
                for item in parts[1:] if ":" in item
                for key, value in (item.split(":", 1),)
            }
            model = properties.get("model") or properties.get("product") or "Android device"
            prop_result = subprocess.run(
                [adb, "-s", serial, "shell", "getprop", "ro.boot.prjname"],
                capture_output=True, text=True, timeout=10,
            )
            prj_id = prop_result.stdout.strip()
            ota_result = subprocess.run(
                [adb, "-s", serial, "shell", "getprop", "ro.build.version.ota"],
                capture_output=True, text=True, timeout=10,
            )
            ota = ota_result.stdout.strip()
            self.after(0, self._connected_device_updated, model, serial, "", prj_id, ota)

        threading.Thread(target=worker, daemon=True).start()

    def _connected_device_updated(
        self, model: str, serial: str, error: str, prj_id: str = "", ota: str = ""
    ) -> None:
        if error:
            self._connected_device_info = ("Android device", "", "", "")
            self.connected_device_status.configure(text=f"○  {error}", fg=self.WARNING)
            self._helper_device_model = ""
            self._helper_device_serial = ""
            self._helper_readiness_root = ""
            self._helper_readiness_code = ""
            if hasattr(self, "helper_readiness"):
                self.helper_readiness.configure(text="No connected device", fg=self.WARNING)
            return
        target_name = model
        if prj_id == "24831":
            target_name = "OnePlus 15"
        elif prj_id == "24855":
            target_name = "OnePlus Ace 6T"
        self._connected_device_info = (target_name, model, serial, prj_id)
        self._render_connected_device()
        if prj_id == "24831":
            self.vars["model"].set("PLK110")
            # The custom ROM may report a CPH/Project-Infinity build OTA string;
            # DeepTest must submit the PLK110 target firmware identifier.
            self.vars["ota_version"].set("PLK110_11.A.68_0680_202606250030")
            self._save_settings()
        elif prj_id == "24855":
            self.vars["model"].set("PLR110")
            self.vars["ota_version"].set("PLR110_11.A.62_0620_202606152334")
            self._save_settings()
        self._set_root_versions({"24831": "OP15", "24855": "ACE6T"}.get(prj_id, "OP15"))

    def _toggle_device_ids(self) -> None:
        self._show_sensitive = not self._show_sensitive
        self._render_connected_device()

    def _toggle_sensitive(self) -> None:
        self._show_sensitive = not self._show_sensitive
        self.sensitive_button.configure(text="Hide critical information" if self._show_sensitive else "Show critical information")
        if hasattr(self, "_chip_entry"):
            self._chip_entry.configure(show="" if self._show_sensitive else "•")
        self._render_connected_device()
        self._render_helper_readiness()

    def _toggle_chip_visibility(self, entry: ttk.Entry) -> None:
        entry.configure(show="" if entry.cget("show") else "•")

    def _render_connected_device(self) -> None:
        target_name, model, serial, prj_id = getattr(self, "_connected_device_info", ("Android device", "", "", ""))
        if not serial:
            self.connected_device_status.configure(text="○  No authorized device", fg=self.WARNING)
            return
        shown_serial = serial if self._show_sensitive else ("*" * len(serial) if serial else "unknown")
        self.connected_device_status.configure(text=f"●  {target_name}\n{model}\n{shown_serial}\nPRJ-ID: {prj_id or 'unknown'}", fg=self.SUCCESS)

    def _set_root_versions(self, folder: str) -> None:
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
        root = bundle_root / "android-helper" / "assets" / folder
        versions = sorted(path.name for path in root.iterdir() if path.is_dir()) if root.is_dir() else []
        if versions:
            self.root_version_menu.configure(values=versions, state="readonly")
            self.root_version.set(versions[0])
        else:
            self.root_version_menu.configure(values=("No version available",), state="disabled")
            self.root_version.set("No version available")
    def _chip_id_detected(self, value: str) -> None:
        self.vars["chip_id"].set(value)
        self._save_settings()
        self.status.configure(text=f"Chip ID detected: {value}")
        self.status_dot.configure(fg=self.SUCCESS)

    def _run(self, args: list[str], status: str, *, show_output: bool = False) -> None:
        if self.busy:
            messagebox.showinfo("Please wait", "Another operation is still running.")
            return
        self._save_settings()
        self.busy = True
        self.active_operation = ""
        if "deeptesting.cli" in args:
            index = args.index("deeptesting.cli")
            if index + 1 < len(args):
                self.active_operation = args[index + 1]
        self.status.configure(text=status)
        self.status_dot.configure(fg=self.WARNING)
        self.progress.start(12)
        self._append("$ " + self._friendly_command(args) + "\n")
        if show_output:
            self._show_page("activity")

        def worker() -> None:
            try:
                proc = subprocess.run(
                    [sys.executable, *args], text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=330,
                    env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
                )
                text = (proc.stdout + proc.stderr).strip()
                self.after(0, self._finished, proc.returncode, text)
            except subprocess.TimeoutExpired:
                self.after(0, self._finished, 1, "The operation timed out.")
            except OSError as exc:
                self.after(0, self._finished, 1, f"Could not start the operation: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _friendly_command(args: list[str]) -> str:
        hidden = []
        skip = False
        redact_next = False
        for item in args:
            if skip:
                hidden.append("••••")
                skip = False
            elif redact_next:
                hidden.append("••••")
                redact_next = False
            else:
                hidden.append(item)
                skip = item in {"--ticket"}
                redact_next = item == "verify"
        return " ".join(hidden)

    def _finished(self, code: int, text: str) -> None:
        self.busy = False
        self.progress.stop()
        self._append((text or "(No output)") + "\n\n")
        handled_device_result = False
        if self.active_operation:
            try:
                start = text.index("{")
                payload, _end = json.JSONDecoder().raw_decode(text[start:])
            except (ValueError, json.JSONDecodeError):
                pass
            else:
                if isinstance(payload, dict) and isinstance(payload.get("code"), int):
                    self._show_device_result(self.active_operation, payload)
                    handled_device_result = True
        if code == 0:
            self.status.configure(text="Completed successfully")
            self.status_dot.configure(fg=self.SUCCESS)
        elif code == 3:
            self.status.configure(text="Waiting for browser identity verification")
            self.status_dot.configure(fg=self.WARNING)
            try:
                start = text.index("{")
                challenge, _end = json.JSONDecoder().raw_decode(text[start:])
            except (ValueError, json.JSONDecodeError):
                self._show_page("activity")
            else:
                if isinstance(challenge, dict) and challenge.get("status") == "interaction_required":
                    stage = str(challenge.get("kind") or "verification")
                    if stage == "verification":
                        self._start_hybrid_verification(challenge)
                    elif stage == "completion" and stage not in self.auto_resume_attempts:
                        self.auto_resume_attempts.add(stage)
                        if not self._resume_saved_stage("completion"):
                            self._show_challenge(challenge)
                    else:
                        self._show_challenge(challenge)
                else:
                    self._show_page("activity")
        else:
            if handled_device_result:
                self.status.configure(text="Server response received")
                self.status_dot.configure(fg=self.WARNING)
            else:
                self.status.configure(text="Operation failed; see Technical log")
                self.status_dot.configure(fg=self.DANGER)
                self._show_page("activity")
        self._update_token_status()

    def _append(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", text)
        self.output.see("end")
        self.output.configure(state="disabled")

    def _clear_output(self) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _update_token_status(self) -> None:
        path = Path(str(self.vars["token_cache"].get())).expanduser()
        if path.is_file():
            self.token_status.configure(text=f"●  Ready\n{path.name}", fg=self.SUCCESS)
        else:
            self.token_status.configure(text="○  Not connected\nSign in or import a token", fg=self.WARNING)

    def _save_settings(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            key: value.get() for key, value in self.vars.items()
            if key not in {"verification_code", "ticket"}
        }
        tmp = SETTINGS_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(SETTINGS_PATH)

    def _close(self) -> None:
        self._save_settings()
        self.destroy()


def main() -> int:
    app = DeepTestingApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
