#!/usr/bin/python
# coding=utf-8

import json
import os
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import urllib.request
import ctypes

try:
    from PIL import Image, ImageTk, ImageDraw
except Exception:
    Image = None
    ImageTk = None
    ImageDraw = None


CURRENT_PATH = os.path.dirname(os.path.abspath(__file__))
MEMBERS_FILE = os.path.join(CURRENT_PATH, "members.json")
CONFIG_FILE = os.path.join(CURRENT_PATH, "config.json")
DATA_DIR = os.path.join(CURRENT_PATH, "data")
os.makedirs(DATA_DIR, exist_ok=True)
CHECKER_STATE_FILE = os.path.join(DATA_DIR, "dashboard_state.json")
ACTIVE_RECORDINGS_FILE = os.path.join(DATA_DIR, "active_recordings.json")
RECORDING_HISTORY_FILE = os.path.join(DATA_DIR, "recording_history.json")
AVATAR_CACHE_DIR = os.path.join(CURRENT_PATH, "avatar_cache")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def setup_dpi_awareness():
    if os.name != "nt":
        return
    try:
        # Windows 10+ 最佳：Per-Monitor V2
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        # 舊版 Windows fallback
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
    try:
        # Windows 10+: per-monitor DPI aware (最清晰)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass


def get_lanczos_filter():
    if Image is None:
        return None
    try:
        return Image.Resampling.LANCZOS
    except Exception:
        return getattr(Image, "LANCZOS", getattr(Image, "ANTIALIAS", None))


def setup_tk_scaling(root):
    if os.name != "nt":
        return
    try:
        # 讓 Tk 文字縮放與目前系統 DPI 對齊，避免 Windows 二次縮放造成模糊
        dpi = ctypes.windll.user32.GetDpiForSystem()
        root.tk.call("tk", "scaling", float(dpi) / 72.0)
    except Exception:
        pass


class RecorderGui:
    def __init__(self, root):
        self.root = root
        self.root.title("TPE48 LangLiveRecorder Alpha 4")
        self.root.geometry("1320x780")
        self.root.minsize(1120, 650)

        self.member_map = {}
        self.group_var = tk.StringVar(value="akb48ttp_members")
        self.status_var = tk.StringVar(value="就緒")
        self.summary_var = tk.StringVar(value="尚無快照資料")
        self.active_count_var = tk.StringVar(value="0")
        self.live_count_var = tk.StringVar(value="0")
        self.history_count_var = tk.StringVar(value="0")
        self.search_var = tk.StringVar(value="")
        self.filter_var = tk.StringVar(value="全部")
        self.auto_refresh_var = tk.BooleanVar(value=True)
        self.refresh_seconds_var = tk.IntVar(value=8)
        self.avatar_photo_refs = {}
        self.last_cards_signature = None
        self.last_members_signature = None
        self.last_active_signature = None
        self.last_history_signature = None
        self.config_data = load_json(CONFIG_FILE, {})

        self.cfg_stall_seconds = tk.StringVar(value="")
        self.cfg_max_stall_restarts = tk.StringVar(value="")
        self.cfg_stall_check_after = tk.StringVar(value="")
        self.cfg_min_segment_seconds = tk.StringVar(value="")
        self.cfg_fast_retry_limit = tk.StringVar(value="")
        self.cfg_fast_retry_delay = tk.StringVar(value="")
        self.cfg_backoff_base = tk.StringVar(value="")
        self.cfg_backoff_max = tk.StringVar(value="")
        self.cfg_gate_days = tk.StringVar(value="")
        self.cfg_gate_min_records = tk.StringVar(value="")
        self.cfg_gate_min_success_rate = tk.StringVar(value="")
        self.cfg_gate_max_avg_restarts = tk.StringVar(value="")
        self.cfg_gate_max_short_ratio = tk.StringVar(value="")

        self.setup_theme()
        self.build_ui()
        self.load_settings_to_form()
        self.refresh_all()

    def setup_theme(self):
        self.ui_font = "Taipei Sans TC Beta"
        self.fallback_font = "Microsoft JhengHei UI"
        self.root.configure(bg="#f7f7f9")
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", background="#f7f7f9", foreground="#222222")
        style.configure("TFrame", background="#f7f7f9")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("TLabel", background="#f7f7f9", foreground="#222222")
        style.configure("Header.TLabel", font=(self.ui_font, 14, "bold"))
        style.configure("Sub.TLabel", foreground="#666666")
        style.configure("CardTitle.TLabel", background="#ffffff", foreground="#FF7A32", font=(self.ui_font, 9, "bold"))
        style.configure("CardValue.TLabel", background="#ffffff", foreground="#1f1f1f", font=(self.ui_font, 16, "bold"))

        style.configure("TButton", padding=4, font=(self.ui_font, 9))
        style.map("TButton", background=[("active", "#ffe1d0")])

        style.configure("TNotebook", background="#f7f7f9", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 8), font=(self.ui_font, 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#FF7A32")], foreground=[("selected", "#ffffff")])

        style.configure("Treeview",
                        background="#ffffff",
                        fieldbackground="#ffffff",
                        foreground="#222222",
                        bordercolor="#d8d8de",
                        rowheight=24,
                        font=(self.ui_font, 9))
        style.configure("Treeview.Heading",
                        background="#FF7A32",
                        foreground="#ffffff",
                        font=(self.ui_font, 9, "bold"))
        style.map("Treeview",
                  background=[("selected", "#ffd8c4")],
                  foreground=[("selected", "#1f1f1f")])

    def build_ui(self):
        top = ttk.Frame(self.root, padding=(10, 8))
        top.pack(fill=tk.X)

        ttk.Label(top, text="TPE48 LangLiveRecorder", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Label(top, text="  桌面版 MVP", style="Sub.TLabel").pack(side=tk.LEFT, pady=(4, 0))

        toolbar = ttk.Frame(self.root, padding=(10, 0, 10, 6))
        toolbar.pack(fill=tk.X)

        ttk.Label(toolbar, text="群組").pack(side=tk.LEFT)
        self.group_combo = ttk.Combobox(toolbar, textvariable=self.group_var, state="readonly", width=24)
        self.group_combo.pack(side=tk.LEFT, padx=(6, 10))
        self.group_combo.bind("<<ComboboxSelected>>", lambda _e: self.load_members())

        ttk.Button(toolbar, text="啟動 Checker", command=self.start_checker).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="停止 Checker", command=self.stop_checker).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="立即刷新", command=self.refresh_all_once).pack(side=tk.LEFT, padx=4)
        ttk.Label(toolbar, text="搜尋").pack(side=tk.LEFT, padx=(12, 4))
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=16)
        search_entry.pack(side=tk.LEFT, padx=(0, 6))
        search_entry.bind("<KeyRelease>", lambda _e: self.refresh_all_once())
        ttk.Label(toolbar, text="篩選").pack(side=tk.LEFT, padx=(6, 4))
        filter_combo = ttk.Combobox(toolbar, textvariable=self.filter_var, state="readonly", width=8, values=["全部", "開播中", "錄影中"])
        filter_combo.pack(side=tk.LEFT, padx=(0, 6))
        filter_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_all_once())
        ttk.Checkbutton(toolbar, text="自動刷新", variable=self.auto_refresh_var).pack(side=tk.LEFT, padx=(8, 4))
        ttk.Label(toolbar, text="秒數").pack(side=tk.LEFT, padx=(4, 4))
        refresh_spin = ttk.Spinbox(toolbar, from_=3, to=60, textvariable=self.refresh_seconds_var, width=4)
        refresh_spin.pack(side=tk.LEFT)

        cards = ttk.Frame(self.root, padding=(10, 0, 10, 8))
        cards.pack(fill=tk.X)
        self.build_stat_card(cards, "目前開播", self.live_count_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.build_stat_card(cards, "錄影中", self.active_count_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self.build_stat_card(cards, "歷史筆數", self.history_count_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

        ttk.Label(self.root, textvariable=self.summary_var, style="Sub.TLabel").pack(anchor="w", padx=12, pady=(0, 4))

        ttk.Separator(self.root, orient="horizontal").pack(fill=tk.X, padx=8, pady=(0, 6))

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        self.tab_cards = ttk.Frame(notebook)
        self.tab_members = ttk.Frame(notebook)
        self.tab_active = ttk.Frame(notebook)
        self.tab_history = ttk.Frame(notebook)
        self.tab_settings = ttk.Frame(notebook)
        notebook.add(self.tab_cards, text="卡片牆")
        notebook.add(self.tab_members, text="成員與開播狀態")
        notebook.add(self.tab_active, text="錄影中")
        notebook.add(self.tab_history, text="錄影歷史")
        notebook.add(self.tab_settings, text="設定")

        self.build_cards_tab()
        self.build_members_tab()
        self.build_active_tab()
        self.build_history_tab()
        self.build_settings_tab()

        status_bar = ttk.Frame(self.root, padding=(8, 4))
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Separator(status_bar, orient="horizontal").pack(fill=tk.X, side=tk.TOP, pady=(0, 6))
        ttk.Label(status_bar, textvariable=self.status_var, style="Sub.TLabel").pack(side=tk.LEFT)

    def build_stat_card(self, parent, title, var):
        card = ttk.Frame(parent, style="Card.TFrame", padding=8)
        ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, textvariable=var, style="CardValue.TLabel").pack(anchor="w")
        return card

    def build_cards_tab(self):
        tip = ttk.Frame(self.tab_cards, padding=4)
        tip.pack(fill=tk.X)
        ttk.Label(tip, text="卡片模式：可直接對單一成員啟動/停止錄影", style="Sub.TLabel").pack(side=tk.LEFT)

        self.cards_canvas = tk.Canvas(self.tab_cards, bg="#f7f7f9", highlightthickness=0)
        self.cards_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0), pady=(0, 4))

        scrollbar = ttk.Scrollbar(self.tab_cards, orient=tk.VERTICAL, command=self.cards_canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 4), pady=(0, 4))
        self.cards_canvas.configure(yscrollcommand=scrollbar.set)

        self.cards_wrap = ttk.Frame(self.cards_canvas, style="TFrame")
        self.cards_window_id = self.cards_canvas.create_window((0, 0), window=self.cards_wrap, anchor="nw")
        self.cards_wrap.bind("<Configure>", self.on_cards_configure)
        self.cards_canvas.bind("<Configure>", self.on_cards_canvas_resize)

    def on_cards_configure(self, _event):
        self.cards_canvas.configure(scrollregion=self.cards_canvas.bbox("all"))

    def on_cards_canvas_resize(self, event):
        self.cards_canvas.itemconfig(self.cards_window_id, width=event.width)

    def render_member_cards(self, members_snapshot, active_data):
        for widget in self.cards_wrap.winfo_children():
            widget.destroy()
        self.avatar_photo_refs = {}

        columns = 5
        for col in range(columns):
            self.cards_wrap.grid_columnconfigure(col, weight=1, uniform="cards")
        for idx, m in enumerate(members_snapshot):
            uid = str(m.get("uid", ""))
            nickname = m.get("nickname", "") or "-"
            is_live = bool(m.get("is_live"))
            launched = bool(m.get("launched_recorder"))
            is_recording = uid in active_data

            # Tkinter 沒有原生圓角 Frame，改用柔和外框與內邊距來呈現較圓滑視覺
            card = tk.Frame(
                self.cards_wrap,
                bg="#ffe8db",
                bd=0,
                highlightthickness=1,
                highlightbackground="#ffb78f",
                highlightcolor="#ffb78f"
            )
            r = idx // columns
            c = idx % columns
            card.grid(row=r, column=c, sticky="nsew", padx=5, pady=5)
            inner = tk.Frame(card, bg="#ffffff", bd=0, padx=8, pady=8)
            inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
            inner.grid_columnconfigure(1, weight=1)

            avatar_url = m.get("liveimg_url") or m.get("avatar_url") or ""
            avatar_photo = self.get_avatar_photo(uid, avatar_url)
            if avatar_photo is not None:
                self.avatar_photo_refs[uid] = avatar_photo
                tk.Label(inner, image=avatar_photo, bg="#ffffff").grid(row=0, column=0, rowspan=5, sticky="nw", padx=(0, 8))
            else:
                tk.Label(inner, text="👤", bg="#ffffff", fg="#9a9a9a", font=(self.ui_font, 20)).grid(row=0, column=0, rowspan=5, sticky="nw", padx=(0, 8))

            tk.Label(inner, text=nickname, bg="#ffffff", fg="#202020", font=(self.ui_font, 11, "bold")).grid(row=0, column=1, sticky="w")
            tk.Label(inner, text="UID: {0}".format(uid), bg="#ffffff", fg="#787878", font=(self.ui_font, 9)).grid(row=1, column=1, sticky="w", pady=(1, 3))

            status_text = "開播中" if is_live else "離線"
            status_color = "#33d17a" if is_live else "#ff6b6b"
            tk.Label(inner, text=status_text, bg="#ffffff", fg=status_color, font=(self.ui_font, 10, "bold")).grid(row=2, column=1, sticky="w")

            rec_text = "錄影中" if is_recording else ("已觸發" if launched else "未錄影")
            rec_color = "#FF7A32" if is_recording else "#7f7f7f"
            tk.Label(inner, text=rec_text, bg="#ffffff", fg=rec_color, font=(self.ui_font, 9)).grid(row=3, column=1, sticky="w", pady=(1, 4))

            actions = tk.Frame(inner, bg="#ffffff")
            actions.grid(row=4, column=1, sticky="w", pady=(2, 0))
            tk.Button(
                actions,
                text="開始",
                command=lambda u=uid: self.start_member_by_uid(u),
                bg="#FF7A32",
                fg="#ffffff",
                activebackground="#e96d2b",
                relief=tk.FLAT,
                font=(self.ui_font, 9, "bold"),
                padx=8,
                pady=3,
                bd=0,
                highlightthickness=0,
                takefocus=False
            ).pack(side=tk.LEFT, padx=(0, 6))
            tk.Button(
                actions,
                text="停止",
                command=lambda u=uid: self.stop_member_by_uid(u),
                bg="#ededf0",
                fg="#333333",
                activebackground="#dfdfe3",
                relief=tk.FLAT,
                font=(self.ui_font, 9, "bold"),
                padx=8,
                pady=3,
                bd=0,
                highlightthickness=0,
                takefocus=False
            ).pack(side=tk.LEFT)

    def get_avatar_cache_path(self, uid, avatar_url):
        os.makedirs(AVATAR_CACHE_DIR, exist_ok=True)
        ext = ".jpg"
        lower_url = avatar_url.lower()
        if ".png" in lower_url:
            ext = ".png"
        elif ".jpg" in lower_url or ".jpeg" in lower_url:
            ext = ".jpg"
        elif ".webp" in lower_url:
            ext = ".webp"
        filename = "{0}{1}".format(uid, ext)
        return os.path.join(AVATAR_CACHE_DIR, filename)

    def get_avatar_photo(self, uid, avatar_url):
        if not avatar_url or Image is None or ImageTk is None or ImageDraw is None:
            return None
        try:
            cache_path = self.get_avatar_cache_path(uid, avatar_url)
            if (not os.path.exists(cache_path)) or os.path.getsize(cache_path) < 128:
                urllib.request.urlretrieve(avatar_url, cache_path)
            size = 64
            resample_filter = get_lanczos_filter()
            image = Image.open(cache_path).convert("RGBA")
            if resample_filter is not None:
                image = image.resize((size, size), resample=resample_filter)
            else:
                image = image.resize((size, size))
            mask = Image.new("L", (size, size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size - 1, size - 1), fill=255)
            image.putalpha(mask)
            return ImageTk.PhotoImage(image)
        except Exception:
            return None

    def build_members_tab(self):
        toolbar = ttk.Frame(self.tab_members, padding=6)
        toolbar.pack(fill=tk.X)
        ttk.Button(toolbar, text="對選取成員立即錄影", command=self.start_selected_member).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Label(toolbar, text="提示：雙擊可快速錄影", style="Sub.TLabel").pack(side=tk.LEFT)

        cols = ("uid", "nickname", "is_live", "launched")
        self.member_tree = ttk.Treeview(self.tab_members, columns=cols, show="headings", height=24)
        self.member_tree.heading("uid", text="UID")
        self.member_tree.heading("nickname", text="暱稱")
        self.member_tree.heading("is_live", text="開播狀態")
        self.member_tree.heading("launched", text="已觸發錄影")
        self.member_tree.column("uid", width=130, anchor=tk.CENTER)
        self.member_tree.column("nickname", width=220)
        self.member_tree.column("is_live", width=100, anchor=tk.CENTER)
        self.member_tree.column("launched", width=120, anchor=tk.CENTER)
        self.member_tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        self.member_tree.bind("<Double-1>", lambda _e: self.start_selected_member())

    def build_active_tab(self):
        toolbar = ttk.Frame(self.tab_active, padding=6)
        toolbar.pack(fill=tk.X)
        ttk.Button(toolbar, text="停止選取錄影", command=self.stop_selected_recording).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Label(toolbar, text="提示：雙擊可停止錄影", style="Sub.TLabel").pack(side=tk.LEFT)

        cols = ("uid", "nickname", "started_at", "restart_count", "last_failure_reason", "output_file")
        self.active_tree = ttk.Treeview(self.tab_active, columns=cols, show="headings", height=24)
        self.active_tree.heading("uid", text="UID")
        self.active_tree.heading("nickname", text="暱稱")
        self.active_tree.heading("started_at", text="開始時間")
        self.active_tree.heading("restart_count", text="重啟次數")
        self.active_tree.heading("last_failure_reason", text="最後失敗原因")
        self.active_tree.heading("output_file", text="輸出檔案")
        self.active_tree.column("uid", width=130, anchor=tk.CENTER)
        self.active_tree.column("nickname", width=180)
        self.active_tree.column("started_at", width=180, anchor=tk.CENTER)
        self.active_tree.column("restart_count", width=90, anchor=tk.CENTER)
        self.active_tree.column("last_failure_reason", width=220)
        self.active_tree.column("output_file", width=460)
        self.active_tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        self.active_tree.bind("<Double-1>", lambda _e: self.stop_selected_recording())

    def build_history_tab(self):
        cols = ("ended_at", "uid", "nickname", "success", "restarts", "category", "reason", "elapsed")
        self.history_tree = ttk.Treeview(self.tab_history, columns=cols, show="headings", height=26)
        self.history_tree.heading("ended_at", text="結束時間")
        self.history_tree.heading("uid", text="UID")
        self.history_tree.heading("nickname", text="暱稱")
        self.history_tree.heading("success", text="結果")
        self.history_tree.heading("restarts", text="重啟次數")
        self.history_tree.heading("category", text="失敗分類")
        self.history_tree.heading("reason", text="檢查結果")
        self.history_tree.heading("elapsed", text="時長(秒)")
        self.history_tree.column("ended_at", width=170, anchor=tk.CENTER)
        self.history_tree.column("uid", width=120, anchor=tk.CENTER)
        self.history_tree.column("nickname", width=160)
        self.history_tree.column("success", width=80, anchor=tk.CENTER)
        self.history_tree.column("restarts", width=90, anchor=tk.CENTER)
        self.history_tree.column("category", width=130, anchor=tk.CENTER)
        self.history_tree.column("reason", width=280)
        self.history_tree.column("elapsed", width=90, anchor=tk.CENTER)
        self.history_tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    def build_settings_tab(self):
        wrap = ttk.Frame(self.tab_settings, padding=10)
        wrap.pack(fill=tk.BOTH, expand=True)

        title = ttk.Frame(wrap)
        title.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(title, text="設定頁（config.json）", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(title, text="重載設定", command=self.reload_settings_from_disk).pack(side=tk.RIGHT, padx=4)
        ttk.Button(title, text="儲存設定", command=self.save_settings_to_disk).pack(side=tk.RIGHT, padx=4)

        recorder_box = ttk.LabelFrame(wrap, text="Recorder 參數", padding=10)
        recorder_box.pack(fill=tk.X, pady=(0, 10))
        self.add_setting_row(recorder_box, 0, "stall_seconds", self.cfg_stall_seconds)
        self.add_setting_row(recorder_box, 1, "max_stall_restarts", self.cfg_max_stall_restarts)
        self.add_setting_row(recorder_box, 2, "stall_check_after_seconds", self.cfg_stall_check_after)
        self.add_setting_row(recorder_box, 3, "min_segment_seconds", self.cfg_min_segment_seconds)
        self.add_setting_row(recorder_box, 4, "fast_retry_limit", self.cfg_fast_retry_limit)
        self.add_setting_row(recorder_box, 5, "fast_retry_delay_seconds", self.cfg_fast_retry_delay)
        self.add_setting_row(recorder_box, 6, "backoff_base_seconds", self.cfg_backoff_base)
        self.add_setting_row(recorder_box, 7, "backoff_max_seconds", self.cfg_backoff_max)

        gate_box = ttk.LabelFrame(wrap, text="Alpha 5 Gate 參數", padding=10)
        gate_box.pack(fill=tk.X)
        self.add_setting_row(gate_box, 0, "days", self.cfg_gate_days)
        self.add_setting_row(gate_box, 1, "min_records", self.cfg_gate_min_records)
        self.add_setting_row(gate_box, 2, "min_success_rate", self.cfg_gate_min_success_rate)
        self.add_setting_row(gate_box, 3, "max_avg_restarts", self.cfg_gate_max_avg_restarts)
        self.add_setting_row(gate_box, 4, "max_short_ratio", self.cfg_gate_max_short_ratio)

    def add_setting_row(self, parent, row_idx, label_text, var):
        ttk.Label(parent, text=label_text).grid(row=row_idx, column=0, sticky="w", padx=(0, 10), pady=4)
        ttk.Entry(parent, textvariable=var, width=24).grid(row=row_idx, column=1, sticky="w", pady=4)

    def load_settings_to_form(self):
        recorder = self.config_data.get("recorder", {})
        gate = self.config_data.get("alpha5_gate", {})
        self.cfg_stall_seconds.set(str(recorder.get("stall_seconds", 20)))
        self.cfg_max_stall_restarts.set(str(recorder.get("max_stall_restarts", 20)))
        self.cfg_stall_check_after.set(str(recorder.get("stall_check_after_seconds", 30)))
        self.cfg_min_segment_seconds.set(str(recorder.get("min_segment_seconds", 120)))
        self.cfg_fast_retry_limit.set(str(recorder.get("fast_retry_limit", 3)))
        self.cfg_fast_retry_delay.set(str(recorder.get("fast_retry_delay_seconds", 2)))
        self.cfg_backoff_base.set(str(recorder.get("backoff_base_seconds", 5)))
        self.cfg_backoff_max.set(str(recorder.get("backoff_max_seconds", 60)))

        self.cfg_gate_days.set(str(gate.get("days", 3)))
        self.cfg_gate_min_records.set(str(gate.get("min_records", 30)))
        self.cfg_gate_min_success_rate.set(str(gate.get("min_success_rate", 0.9)))
        self.cfg_gate_max_avg_restarts.set(str(gate.get("max_avg_restarts", 1.2)))
        self.cfg_gate_max_short_ratio.set(str(gate.get("max_short_ratio", 0.35)))

    def reload_settings_from_disk(self):
        self.config_data = load_json(CONFIG_FILE, {})
        self.load_settings_to_form()
        self.status_var.set("設定已從磁碟重載")

    def save_settings_to_disk(self):
        try:
            new_config = {
                "recorder": {
                    "stall_seconds": int(self.cfg_stall_seconds.get()),
                    "max_stall_restarts": int(self.cfg_max_stall_restarts.get()),
                    "stall_check_after_seconds": int(self.cfg_stall_check_after.get()),
                    "min_segment_seconds": int(self.cfg_min_segment_seconds.get()),
                    "fast_retry_limit": int(self.cfg_fast_retry_limit.get()),
                    "fast_retry_delay_seconds": int(self.cfg_fast_retry_delay.get()),
                    "backoff_base_seconds": int(self.cfg_backoff_base.get()),
                    "backoff_max_seconds": int(self.cfg_backoff_max.get())
                },
                "alpha5_gate": {
                    "days": int(self.cfg_gate_days.get()),
                    "min_records": int(self.cfg_gate_min_records.get()),
                    "min_success_rate": float(self.cfg_gate_min_success_rate.get()),
                    "max_avg_restarts": float(self.cfg_gate_max_avg_restarts.get()),
                    "max_short_ratio": float(self.cfg_gate_max_short_ratio.get())
                }
            }
        except ValueError:
            messagebox.showerror("錯誤", "設定格式錯誤，請確認數值欄位。")
            return

        ok = save_json(CONFIG_FILE, new_config)
        if not ok:
            messagebox.showerror("錯誤", "寫入 config.json 失敗")
            return
        self.config_data = new_config
        self.status_var.set("設定已儲存到 config.json")

    def start_checker(self):
        try:
            subprocess.Popen(["cmd.exe", "/c", "start", "", "run.bat"], cwd=CURRENT_PATH, shell=False)
            self.status_var.set("已送出啟動 Checker 指令")
        except Exception as e:
            messagebox.showerror("錯誤", "啟動 Checker 失敗: {0}".format(e))

    def stop_checker(self):
        try:
            cmd = 'taskkill /FI "WINDOWTITLE eq TTP Lang Live Checker" /T /F'
            subprocess.call(cmd, cwd=CURRENT_PATH, shell=True)
            self.status_var.set("已送出停止 Checker 指令")
        except Exception as e:
            messagebox.showerror("錯誤", "停止 Checker 失敗: {0}".format(e))

    def start_selected_member(self):
        selected = self.member_tree.selection()
        if not selected:
            messagebox.showinfo("提示", "請先選取成員")
            return
        item = self.member_tree.item(selected[0], "values")
        uid = item[0]
        self.start_member_by_uid(uid)

    def start_member_by_uid(self, uid):
        try:
            subprocess.call(["record.bat", uid], cwd=CURRENT_PATH)
            self.status_var.set("已送出錄影啟動: {0}".format(uid))
        except Exception as e:
            messagebox.showerror("錯誤", "啟動錄影失敗: {0}".format(e))

    def stop_selected_recording(self):
        selected = self.active_tree.selection()
        if not selected:
            messagebox.showinfo("提示", "請先選取錄影項目")
            return
        item = self.active_tree.item(selected[0], "values")
        uid = item[0]
        self.stop_member_by_uid(uid)

    def stop_member_by_uid(self, uid):
        try:
            cmd = 'taskkill /FI "WINDOWTITLE eq TTP {0}" /T /F'.format(uid)
            subprocess.call(cmd, cwd=CURRENT_PATH, shell=True)
            self.status_var.set("已送出停止錄影: {0}".format(uid))
        except Exception as e:
            messagebox.showerror("錯誤", "停止錄影失敗: {0}".format(e))

    def refresh_all(self):
        if self.auto_refresh_var.get():
            self.refresh_all_once()
        interval_ms = max(3000, int(self.refresh_seconds_var.get()) * 1000)
        self.root.after(interval_ms, self.refresh_all)

    def refresh_all_once(self):
        self.load_groups()
        self.load_members()
        self.load_active()
        self.load_history()

    def load_groups(self):
        data = load_json(MEMBERS_FILE, {})
        groups = sorted([k for k in data.keys() if k.endswith("_members")])
        if not groups:
            groups = ["akb48ttp_members"]
        self.group_combo["values"] = groups
        if self.group_var.get() not in groups:
            self.group_var.set(groups[0])

    def load_members(self):
        checker = load_json(CHECKER_STATE_FILE, {})
        members_snapshot = checker.get("members", [])
        keyword = self.search_var.get().strip().lower()
        filter_mode = self.filter_var.get()
        self.member_map = {str(m.get("uid", "")): m for m in members_snapshot}
        total_live_count = len([m for m in members_snapshot if m.get("is_live")])
        active_data = load_json(ACTIVE_RECORDINGS_FILE, {})
        filtered_members = []
        for m in members_snapshot:
            uid = str(m.get("uid", ""))
            nickname = (m.get("nickname", "") or "-")
            is_live_flag = bool(m.get("is_live"))
            is_recording = uid in active_data
            if keyword and (keyword not in uid.lower()) and (keyword not in nickname.lower()):
                continue
            if filter_mode == "開播中" and not is_live_flag:
                continue
            if filter_mode == "錄影中" and not is_recording:
                continue
            filtered_members.append(m)

        live_count = 0
        members_rows = []
        for m in filtered_members:
            uid = str(m.get("uid", ""))
            nickname = m.get("nickname", "") or "-"
            is_live = "開播中" if m.get("is_live") else "離線"
            if m.get("is_live"):
                live_count += 1
            launched = "錄影中" if uid in active_data else ("是" if m.get("launched_recorder") else "-")
            members_rows.append((uid, nickname, is_live, launched))

        if members_rows != self.last_members_signature:
            selected = self.member_tree.selection()
            selected_uid = None
            if selected:
                selected_uid = self.member_tree.item(selected[0], "values")[0]

            for iid in self.member_tree.get_children():
                self.member_tree.delete(iid)
            for row in members_rows:
                self.member_tree.insert("", tk.END, values=row)

            if selected_uid:
                for iid in self.member_tree.get_children():
                    vals = self.member_tree.item(iid, "values")
                    if vals and vals[0] == selected_uid:
                        self.member_tree.selection_set(iid)
                        break
            self.last_members_signature = members_rows

        cards_signature = [
            (
                str(m.get("uid", "")),
                m.get("nickname", "") or "-",
                bool(m.get("is_live")),
                bool(m.get("launched_recorder")),
                str(m.get("liveimg_url", "") or ""),
                str(m.get("avatar_url", "") or ""),
                str(m.get("uid", "")) in active_data
            )
            for m in filtered_members
        ]
        if cards_signature != self.last_cards_signature:
            self.render_member_cards(filtered_members, active_data)
            self.last_cards_signature = cards_signature

        updated_at = checker.get("updated_at", "-")
        self.live_count_var.set(str(total_live_count))
        self.summary_var.set(
            "最近快照更新：{0}    監控群組：{1}    目前顯示：{2}".format(
                updated_at, checker.get("group", "-"), len(filtered_members)
            )
        )
        self.status_var.set("資料已刷新")

    def load_active(self):
        active_data = load_json(ACTIVE_RECORDINGS_FILE, {})
        self.active_count_var.set(str(len(active_data)))
        rows = [
            (
                uid,
                item.get("nickname", "") or "-",
                item.get("started_at", "") or "-",
                item.get("restart_count", 0),
                item.get("last_failure_reason", "-"),
                item.get("output_file", "") or "-"
            )
            for uid, item in active_data.items()
        ]
        if rows != self.last_active_signature:
            selected = self.active_tree.selection()
            selected_uid = None
            if selected:
                selected_uid = self.active_tree.item(selected[0], "values")[0]

            for iid in self.active_tree.get_children():
                self.active_tree.delete(iid)
            for row in rows:
                self.active_tree.insert("", tk.END, values=row)

            if selected_uid:
                for iid in self.active_tree.get_children():
                    vals = self.active_tree.item(iid, "values")
                    if vals and vals[0] == selected_uid:
                        self.active_tree.selection_set(iid)
                        break
            self.last_active_signature = rows

    def load_history(self):
        history = load_json(RECORDING_HISTORY_FILE, [])
        recent = list(reversed(history[-200:]))
        self.history_count_var.set(str(len(history)))
        rows = [
            (
                h.get("ended_at", "") or "-",
                h.get("uid", "") or "-",
                h.get("nickname", "") or "-",
                "成功" if h.get("success") else "失敗",
                h.get("restart_count", 0),
                h.get("failure_category", "") or "-",
                h.get("reason", "") or "-",
                h.get("elapsed_seconds", 0),
            )
            for h in recent
        ]
        if rows != self.last_history_signature:
            for iid in self.history_tree.get_children():
                self.history_tree.delete(iid)
            for row in rows:
                self.history_tree.insert("", tk.END, values=row)
            self.last_history_signature = rows


def main():
    setup_dpi_awareness()
    root = tk.Tk()
    setup_tk_scaling(root)
    app = RecorderGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
