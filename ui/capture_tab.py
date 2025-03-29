import tkinter as tk
from tkinter import ttk
from ui.base import BaseTab
from utils.capture import get_windows, get_window_title
from utils.settings import get_setting, set_setting
from utils.ocr import _windows_ocr_available # Import check function

class CaptureTab(BaseTab):
    OCR_LANGUAGES = ["jpn", "jpn_vert", "eng", "chi_sim", "chi_tra", "kor"]
    # Define available engines
    OCR_ENGINES = ["paddle", "easyocr"]
    if _windows_ocr_available: # Conditionally add Windows OCR
        OCR_ENGINES.append("windows")

    def setup_ui(self):
        capture_frame = ttk.LabelFrame(self.frame, text="Capture Settings", padding="10")
        capture_frame.pack(fill=tk.X, pady=10)

        # --- Window Selection ---
        win_frame = ttk.Frame(capture_frame)
        win_frame.pack(fill=tk.X)
        ttk.Label(win_frame, text="Visual Novel Window:").pack(anchor=tk.W)
        self.window_var = tk.StringVar()
        self.window_combo = ttk.Combobox(win_frame, textvariable=self.window_var, width=50, state="readonly")
        self.window_combo.pack(fill=tk.X, pady=(5, 0))
        self.window_combo.bind("<<ComboboxSelected>>", self.on_window_selected)

        # --- Capture Buttons ---
        btn_frame = ttk.Frame(capture_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 10))
        self.refresh_btn = ttk.Button(btn_frame, text="Refresh List",
                                      command=self.refresh_window_list)
        self.refresh_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.start_btn = ttk.Button(btn_frame, text="Start Capture",
                                    command=self.app.start_capture)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(btn_frame, text="Stop Capture",
                                   command=self.app.stop_capture, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        self.snapshot_btn = ttk.Button(btn_frame, text="Take Snapshot",
                                       command=self.app.take_snapshot, state=tk.DISABLED)
        self.snapshot_btn.pack(side=tk.LEFT, padx=5)
        self.live_view_btn = ttk.Button(btn_frame, text="Return to Live",
                                        command=self.app.return_to_live, state=tk.DISABLED)
        self.live_view_btn.pack(side=tk.LEFT, padx=5)

        # --- OCR Settings Frame ---
        ocr_frame = ttk.Frame(capture_frame)
        ocr_frame.pack(fill=tk.X, pady=(10, 5))

        # OCR Engine Selection
        ttk.Label(ocr_frame, text="OCR Engine:").pack(side=tk.LEFT, anchor=tk.W, padx=(0, 5))
        self.engine_var = tk.StringVar()
        self.engine_combo = ttk.Combobox(ocr_frame, textvariable=self.engine_var, width=12,
                                         values=self.OCR_ENGINES, state="readonly")
        default_engine = get_setting("ocr_engine", "paddle")
        if default_engine in self.OCR_ENGINES:
            self.engine_combo.set(default_engine)
        elif self.OCR_ENGINES:
            self.engine_combo.current(0) # Default to first available
        self.engine_combo.pack(side=tk.LEFT, anchor=tk.W, padx=5)
        self.engine_combo.bind("<<ComboboxSelected>>", self.on_engine_selected)

        # OCR Language Selection
        ttk.Label(ocr_frame, text="Language:").pack(side=tk.LEFT, anchor=tk.W, padx=(15, 5)) # Added spacing
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

        # --- Status Label ---
        self.status_label = ttk.Label(capture_frame, text="Status: Ready")
        self.status_label.pack(fill=tk.X, pady=(10, 0), anchor=tk.W)

        # Initial population
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
                # Basic filtering
                if title and title != app_title and "Program Manager" not in title and "Default IME" not in title:
                    filtered_windows[hwnd] = f"{hwnd}: {title}"

            window_titles = list(filtered_windows.values())
            self.window_handles = list(filtered_windows.keys()) # Store HWNDs in the same order
            self.window_combo['values'] = window_titles

            if window_titles:
                last_hwnd = self.app.selected_hwnd
                # Try to re-select the previously selected window if it still exists
                if last_hwnd and last_hwnd in self.window_handles:
                    try:
                        idx = self.window_handles.index(last_hwnd)
                        self.window_combo.current(idx)
                    except ValueError:
                        # Handle case where HWND exists but somehow index fails (shouldn't happen)
                        self.app.selected_hwnd = None
                        self.app.load_rois_for_hwnd(None)
                elif self.app.selected_hwnd: # If previous HWND is no longer valid
                    self.app.selected_hwnd = None
                    self.app.load_rois_for_hwnd(None)

                self.app.update_status(f"Found {len(window_titles)} windows. Select one.")
            else:
                self.app.update_status("No suitable windows found.")
                if self.app.selected_hwnd: # Clear selection if no windows found
                    self.app.selected_hwnd = None
                    self.app.load_rois_for_hwnd(None)

            self.window_combo.config(state="readonly") # Set back to readonly after update

        except Exception as e:
            self.app.update_status(f"Error refreshing windows: {e}")
            self.window_combo.config(state="readonly") # Ensure readonly on error

    def on_window_selected(self, event=None):
        try:
            selected_index = self.window_combo.current()
            if 0 <= selected_index < len(self.window_handles):
                new_hwnd = self.window_handles[selected_index]
                if new_hwnd != self.app.selected_hwnd:
                    self.app.selected_hwnd = new_hwnd
                    title = self.window_combo.get().split(":", 1)[-1].strip()
                    self.app.update_status(f"Window selected: {title}")
                    print(f"Selected window HWND: {self.app.selected_hwnd}")
                    # Load ROIs and context specific to this window
                    self.app.load_rois_for_hwnd(new_hwnd)
                    # If capture was running, maybe notify user to restart?
                    if self.app.capturing:
                        self.app.update_status(f"Window changed to {title}. Restart capture if needed.")
            else:
                # Handle case where selection is somehow invalid
                if self.app.selected_hwnd is not None:
                    self.app.selected_hwnd = None
                    self.app.update_status("No window selected.")
                    self.app.load_rois_for_hwnd(None)
        except Exception as e:
            # General error handling
            self.app.selected_hwnd = None
            self.app.update_status(f"Error selecting window: {e}")
            self.app.load_rois_for_hwnd(None)

    def on_engine_selected(self, event=None):
        """Handles selection of a new OCR engine."""
        new_engine = self.engine_var.get()
        if new_engine in self.OCR_ENGINES:
            print(f"OCR Engine selection changed to: {new_engine}")
            set_setting("ocr_engine", new_engine)
            # Trigger the app to update/initialize the selected engine
            # Pass the currently selected language as well
            current_lang = self.lang_var.get() or "jpn"
            self.app.set_ocr_engine(new_engine, current_lang)
        else:
            self.app.update_status("Invalid OCR engine selected.")

    def on_language_changed(self, event=None):
        """Handles selection of a new OCR language."""
        new_lang = self.lang_var.get()
        if new_lang in self.OCR_LANGUAGES:
            print(f"OCR Language changed to: {new_lang}")
            set_setting("ocr_language", new_lang)
            # Trigger the app to update the OCR engine with the new language
            # Pass the currently selected engine type
            current_engine = self.engine_var.get() or "paddle"
            self.app.update_ocr_language(new_lang, current_engine)
        else:
            self.app.update_status("Invalid language selected.")

    def update_status(self, message):
        """Updates the status label text."""
        self.status_label.config(text=f"Status: {message}")

    # --- State Update Callbacks from App ---
    def on_capture_started(self):
        self.start_btn.config(state=tk.DISABLED)
        self.refresh_btn.config(state=tk.DISABLED)
        self.window_combo.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.snapshot_btn.config(state=tk.NORMAL)
        self.live_view_btn.config(state=tk.DISABLED) # Cannot return to live if already live

    def on_capture_stopped(self):
        self.start_btn.config(state=tk.NORMAL)
        self.refresh_btn.config(state=tk.NORMAL)
        self.window_combo.config(state="readonly") # Re-enable selection
        self.stop_btn.config(state=tk.DISABLED)
        self.snapshot_btn.config(state=tk.DISABLED) # Cannot snapshot if not capturing
        self.live_view_btn.config(state=tk.DISABLED)

    def on_snapshot_taken(self):
        # Snapshot implies capture was running, so keep stop/snapshot enabled
        # self.start_btn.config(state=tk.DISABLED) # Keep disabled
        # self.refresh_btn.config(state=tk.DISABLED) # Keep disabled
        # self.window_combo.config(state=tk.DISABLED) # Keep disabled
        # self.stop_btn.config(state=tk.NORMAL) # Keep enabled
        # self.snapshot_btn.config(state=tk.NORMAL) # Keep enabled
        self.live_view_btn.config(state=tk.NORMAL) # Enable returning to live

    def on_live_view_resumed(self):
        self.live_view_btn.config(state=tk.DISABLED)
        # Restore state based on whether capture is still active
        if self.app.capturing:
            self.snapshot_btn.config(state=tk.NORMAL)
            # Other buttons should already be in the 'capturing' state
        else:
            # If capture somehow stopped while snapshot was active, reset fully
            self.snapshot_btn.config(state=tk.DISABLED)
            self.on_capture_stopped()