import tkinter as tk
from tkinter import ttk
from ui.base import BaseTab
from utils.capture import get_windows, get_window_title
from utils.settings import get_setting, set_setting
from utils.ocr import _windows_ocr_available

class CaptureTab(BaseTab):
    OCR_LANGUAGES = ["jpn", "jpn_vert", "eng", "chi_sim", "chi_tra", "kor"]
    OCR_ENGINES = ["paddle", "easyocr"]
    if _windows_ocr_available:
        OCR_ENGINES.append("windows")

    def setup_ui(self):
        capture_frame = ttk.LabelFrame(self.frame, text="Capture Settings", padding="10")
        capture_frame.pack(fill=tk.X, pady=10)

        win_frame = ttk.Frame(capture_frame)
        win_frame.pack(fill=tk.X)
        ttk.Label(win_frame, text="Visual Novel Window:").pack(anchor=tk.W)
        self.window_var = tk.StringVar()
        self.window_combo = ttk.Combobox(win_frame, textvariable=self.window_var, width=50, state="readonly")
        self.window_combo.pack(fill=tk.X, pady=(5, 0))
        self.window_combo.bind("<<ComboboxSelected>>", self.on_window_selected)

        btn_frame = ttk.Frame(capture_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 10))
        self.refresh_btn = ttk.Button(btn_frame, text="Refresh List", command=self.refresh_window_list)
        self.refresh_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.start_btn = ttk.Button(btn_frame, text="Start Capture", command=self.app.start_capture)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(btn_frame, text="Stop Capture", command=self.app.stop_capture, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        self.snapshot_btn = ttk.Button(btn_frame, text="Take Snapshot", command=self.app.take_snapshot, state=tk.DISABLED)
        self.snapshot_btn.pack(side=tk.LEFT, padx=5)
        self.live_view_btn = ttk.Button(btn_frame, text="Return to Live", command=self.app.return_to_live, state=tk.DISABLED)
        self.live_view_btn.pack(side=tk.LEFT, padx=5)

        ocr_frame = ttk.Frame(capture_frame)
        ocr_frame.pack(fill=tk.X, pady=(10, 5))
        ttk.Label(ocr_frame, text="OCR Engine:").pack(side=tk.LEFT, anchor=tk.W, padx=(0, 5))
        self.engine_var = tk.StringVar()
        self.engine_combo = ttk.Combobox(ocr_frame, textvariable=self.engine_var, width=12,
                                         values=self.OCR_ENGINES, state="readonly")
        default_engine = get_setting("ocr_engine", "paddle")
        if default_engine in self.OCR_ENGINES:
            self.engine_combo.set(default_engine)
        elif self.OCR_ENGINES:
            self.engine_combo.current(0)
        self.engine_combo.pack(side=tk.LEFT, anchor=tk.W, padx=5)
        self.engine_combo.bind("<<ComboboxSelected>>", self.on_engine_selected)

        ttk.Label(ocr_frame, text="Language:").pack(side=tk.LEFT, anchor=tk.W, padx=(15, 5))
        self.lang_var = tk.StringVar()
        self.lang_combo = ttk.Combobox(ocr_frame, textvariable=self.lang_var, width=10,
                                       values=self.OCR_LANGUAGES, state="readonly")
        default_lang = get_setting("ocr_language", "jpn")
        if default_lang in self.OCR_LANGUAGES:
            self.lang_combo.set(default_lang)
        elif self.OCR_LANGUAGES:
            self.lang_combo.current(0)
        self.lang_combo.pack(side=tk.LEFT, anchor=tk.W, padx=5)
        self.lang_combo.bind("<<ComboboxSelected>>", self.on_language_changed)

        self.status_label = ttk.Label(capture_frame, text="Status: Ready")
        self.status_label.pack(fill=tk.X, pady=(10, 0), anchor=tk.W)

        self.refresh_window_list()

    def refresh_window_list(self):
        self.app.update_status("Refreshing window list...")
        self.window_combo.config(state=tk.NORMAL)
        self.window_combo.set("")
        try:
            windows = get_windows()
            filtered_windows = {}
            app_title = self.app.master.title()
            for hwnd in windows:
                title = get_window_title(hwnd)
                if title and title != app_title and "Program Manager" not in title and "Default IME" not in title:
                    filtered_windows[hwnd] = f"{hwnd}: {title}"
            window_titles = list(filtered_windows.values())
            self.window_handles = list(filtered_windows.keys())
            self.window_combo['values'] = window_titles

            if window_titles:
                last_hwnd = self.app.selected_hwnd
                if last_hwnd and last_hwnd in self.window_handles:
                    try:
                        idx = self.window_handles.index(last_hwnd)
                        self.window_combo.current(idx)
                    except ValueError:
                        self.app.selected_hwnd = None
                        self.app.load_rois_for_hwnd(None)
                elif self.app.selected_hwnd:
                    self.app.selected_hwnd = None
                    self.app.load_rois_for_hwnd(None)
                self.app.update_status(f"Found {len(window_titles)} windows. Select one.")
            else:
                self.app.update_status("No suitable windows found.")
                if self.app.selected_hwnd:
                    self.app.selected_hwnd = None
                    self.app.load_rois_for_hwnd(None)
            self.window_combo.config(state="readonly")
        except Exception as e:
            self.app.update_status(f"Error refreshing windows: {e}")
            self.window_combo.config(state="readonly")

    def on_window_selected(self, event=None):
        try:
            selected_index = self.window_combo.current()
            if 0 <= selected_index < len(self.window_handles):
                new_hwnd = self.window_handles[selected_index]
                if new_hwnd != self.app.selected_hwnd:
                    self.app.selected_hwnd = new_hwnd
                    title = self.window_combo.get().split(":", 1)[-1].strip()
                    self.app.update_status(f"Window selected: {title}")
                    self.app.load_rois_for_hwnd(new_hwnd)
                    if self.app.capturing:
                        self.app.update_status(f"Window changed to {title}. Restart capture if needed.")
            else:
                if self.app.selected_hwnd is not None:
                    self.app.selected_hwnd = None
                    self.app.update_status("No window selected.")
                    self.app.load_rois_for_hwnd(None)
        except Exception as e:
            self.app.selected_hwnd = None
            self.app.update_status(f"Error selecting window: {e}")
            self.app.load_rois_for_hwnd(None)

    def on_engine_selected(self, event=None):
        new_engine = self.engine_var.get()
        if new_engine in self.OCR_ENGINES:
            set_setting("ocr_engine", new_engine)
            current_lang = self.lang_var.get() or "jpn"
            self.app.set_ocr_engine(new_engine, current_lang)
        else:
            self.app.update_status("Invalid OCR engine selected.")

    def on_language_changed(self, event=None):
        new_lang = self.lang_var.get()
        if new_lang in self.OCR_LANGUAGES:
            set_setting("ocr_language", new_lang)
            current_engine = self.engine_var.get() or "paddle"
            self.app.update_ocr_language(new_lang, current_engine)
        else:
            self.app.update_status("Invalid language selected.")

    def update_status(self, message):
        self.status_label.config(text=f"Status: {message}")

    def on_capture_started(self):
        self.start_btn.config(state=tk.DISABLED)
        self.refresh_btn.config(state=tk.DISABLED)
        self.window_combo.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.snapshot_btn.config(state=tk.NORMAL)
        self.live_view_btn.config(state=tk.DISABLED)

    def on_capture_stopped(self):
        self.start_btn.config(state=tk.NORMAL)
        self.refresh_btn.config(state=tk.NORMAL)
        self.window_combo.config(state="readonly")
        self.stop_btn.config(state=tk.DISABLED)
        self.snapshot_btn.config(state=tk.DISABLED)
        self.live_view_btn.config(state=tk.DISABLED)

    def on_snapshot_taken(self):
        self.live_view_btn.config(state=tk.NORMAL)

    def on_live_view_resumed(self):
        self.live_view_btn.config(state=tk.DISABLED)
        if self.app.capturing:
            self.snapshot_btn.config(state=tk.NORMAL)
        else:
            self.snapshot_btn.config(state=tk.DISABLED)
            self.on_capture_stopped()