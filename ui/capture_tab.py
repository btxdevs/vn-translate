import tkinter as tk
from tkinter import ttk
from ui.base import BaseTab
from utils.capture import get_windows, get_window_title

class CaptureTab(BaseTab):
    """Tab for window capture settings."""

    def setup_ui(self):
        capture_frame = ttk.LabelFrame(self.frame, text="Capture Settings", padding="10")
        capture_frame.pack(fill=tk.X, pady=10)

        # Window selection
        ttk.Label(capture_frame, text="Select visual novel window:").pack(anchor=tk.W)
        self.window_combo = ttk.Combobox(capture_frame, width=40)
        self.window_combo.pack(fill=tk.X, pady=(5, 10))

        # Buttons
        btn_frame = ttk.Frame(capture_frame)
        btn_frame.pack(fill=tk.X)

        self.refresh_btn = ttk.Button(btn_frame, text="Refresh Windows",
                                      command=self.refresh_window_list)
        self.refresh_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.start_btn = ttk.Button(btn_frame, text="Start Capture",
                                    command=self.app.start_capture)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(btn_frame, text="Stop Capture",
                                   command=self.app.stop_capture, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.snapshot_btn = ttk.Button(btn_frame, text="Take Snapshot",
                                       command=self.app.take_snapshot)
        self.snapshot_btn.pack(side=tk.LEFT, padx=5)

        self.live_view_btn = ttk.Button(btn_frame, text="Return to Live",
                                        command=self.app.return_to_live, state=tk.DISABLED)
        self.live_view_btn.pack(side=tk.LEFT, padx=5)

        # Language selection
        ttk.Label(capture_frame, text="OCR Language:").pack(anchor=tk.W, pady=(10, 5))
        self.lang_combo = ttk.Combobox(capture_frame, width=20,
                                       values=["jpn", "jpn_vert", "eng", "chi_sim", "chi_tra", "kor"])
        self.lang_combo.current(0)
        self.lang_combo.pack(anchor=tk.W)

        # Status label
        self.status_label = ttk.Label(capture_frame, text="Status: Ready")
        self.status_label.pack(fill=tk.X, pady=(10, 0))

        # Initialize window list
        self.refresh_window_list()

    def refresh_window_list(self):
        """Refresh the list of available windows."""
        windows = get_windows()
        window_titles = [f"{hwnd}: {get_window_title(hwnd)}" for hwnd in windows]
        self.window_combo['values'] = window_titles
        self.window_combo.set("")
        self.update_status("Window list refreshed.")

    def update_status(self, message):
        """Update the status message."""
        self.status_label.config(text=f"Status: {message}")

    def on_capture_started(self):
        """Update UI when capture starts."""
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.snapshot_btn.config(state=tk.NORMAL)

    def on_capture_stopped(self):
        """Update UI when capture stops."""
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.snapshot_btn.config(state=tk.DISABLED)

    def on_snapshot_taken(self):
        """Update UI when a snapshot is taken."""
        self.live_view_btn.config(state=tk.NORMAL)
        self.snapshot_btn.config(state=tk.DISABLED)
        self.update_status("Snapshot taken. You can now define ROIs on this static image.")

    def on_live_view_resumed(self):
        """Update UI when returning to live view."""
        self.live_view_btn.config(state=tk.DISABLED)
        self.snapshot_btn.config(state=tk.NORMAL)
        self.update_status("Returned to live view.")