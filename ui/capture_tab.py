# --- START OF FILE ui/capture_tab.py ---

import tkinter as tk
from tkinter import ttk
from ui.base import BaseTab
from utils.capture import get_windows, get_window_title
from utils.settings import get_setting, set_setting # Import settings functions

class CaptureTab(BaseTab):
    """Tab for window capture settings."""

    OCR_LANGUAGES = ["jpn", "jpn_vert", "eng", "chi_sim", "chi_tra", "kor"] # Add more if Paddle supports

    def setup_ui(self):
        capture_frame = ttk.LabelFrame(self.frame, text="Capture Settings", padding="10")
        capture_frame.pack(fill=tk.X, pady=10)

        # --- Window selection ---
        win_frame = ttk.Frame(capture_frame)
        win_frame.pack(fill=tk.X)
        ttk.Label(win_frame, text="Visual Novel Window:").pack(anchor=tk.W)

        self.window_var = tk.StringVar()
        self.window_combo = ttk.Combobox(win_frame, textvariable=self.window_var, width=50, state="readonly") # Increased width
        self.window_combo.pack(fill=tk.X, pady=(5, 0))
        self.window_combo.bind("<<ComboboxSelected>>", self.on_window_selected)


        # --- Buttons ---
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
                                       command=self.app.take_snapshot, state=tk.DISABLED) # Initially disabled
        self.snapshot_btn.pack(side=tk.LEFT, padx=5)

        self.live_view_btn = ttk.Button(btn_frame, text="Return to Live",
                                        command=self.app.return_to_live, state=tk.DISABLED)
        self.live_view_btn.pack(side=tk.LEFT, padx=5)

        # --- Language selection ---
        lang_frame = ttk.Frame(capture_frame)
        lang_frame.pack(fill=tk.X, pady=(10, 5))
        ttk.Label(lang_frame, text="OCR Language:").pack(side=tk.LEFT, anchor=tk.W)

        self.lang_var = tk.StringVar()
        self.lang_combo = ttk.Combobox(lang_frame, textvariable=self.lang_var, width=15,
                                       values=self.OCR_LANGUAGES, state="readonly")

        # Load last used language or default
        default_lang = get_setting("ocr_language", "jpn")
        if default_lang in self.OCR_LANGUAGES:
            self.lang_combo.set(default_lang)
        elif self.OCR_LANGUAGES:
            self.lang_combo.current(0) # Fallback to first

        self.lang_combo.pack(side=tk.LEFT, anchor=tk.W, padx=5)
        self.lang_combo.bind("<<ComboboxSelected>>", self.on_language_changed)

        # --- Status label ---
        # This label is now mostly redundant as status is shown in main window's status bar
        # We keep it for structure but rely on app.update_status()
        self.status_label = ttk.Label(capture_frame, text="Status: Ready")
        self.status_label.pack(fill=tk.X, pady=(10, 0), anchor=tk.W)

        # Initialize window list
        self.refresh_window_list()

    def refresh_window_list(self):
        """Refresh the list of available windows."""
        self.app.update_status("Refreshing window list...") # Use app's status update
        self.window_combo.config(state=tk.NORMAL) # Allow clearing
        self.window_combo.set("") # Clear current selection
        # Don't clear app.selected_hwnd here, let on_window_selected handle it
        # self.app.selected_hwnd = None # Clear app's selected handle
        try:
            windows = get_windows()
            # Filter out windows with no title or specific unwanted titles (like this app itself)
            filtered_windows = {}
            app_title = self.app.master.title()
            for hwnd in windows:
                title = get_window_title(hwnd)
                # Basic filtering - might need refinement
                if title and title != app_title and "Program Manager" not in title and "Default IME" not in title:
                    filtered_windows[hwnd] = f"{hwnd}: {title}"

            window_titles = list(filtered_windows.values())
            self.window_handles = list(filtered_windows.keys()) # Store handles separately
            self.window_combo['values'] = window_titles

            if window_titles:
                # Try to re-select the previously selected window if it still exists
                # Use the app's current selected_hwnd
                last_hwnd = self.app.selected_hwnd
                if last_hwnd and last_hwnd in self.window_handles:
                    try:
                        idx = self.window_handles.index(last_hwnd)
                        self.window_combo.current(idx)
                        # Don't call on_window_selected here, avoid potential loop/redundancy
                    except ValueError:
                        # Handle not found, selection will be cleared or default
                        self.app.selected_hwnd = None # Clear app state if window disappeared
                        self.app.load_rois_for_hwnd(None) # Clear ROIs if window gone
                elif self.app.selected_hwnd:
                    # If a window was selected but isn't in the new list
                    self.app.selected_hwnd = None
                    self.app.load_rois_for_hwnd(None) # Clear ROIs

                self.app.update_status(f"Found {len(window_titles)} windows. Select one.")
            else:
                self.app.update_status("No suitable windows found.")
                if self.app.selected_hwnd:
                    self.app.selected_hwnd = None
                    self.app.load_rois_for_hwnd(None) # Clear ROIs if no windows found

            self.window_combo.config(state="readonly")

        except Exception as e:
            self.app.update_status(f"Error refreshing windows: {e}")
            self.window_combo.config(state="readonly")


    def on_window_selected(self, event=None):
        """Update the application's selected HWND and load game-specific ROIs."""
        try:
            selected_index = self.window_combo.current()
            if selected_index >= 0 and selected_index < len(self.window_handles):
                new_hwnd = self.window_handles[selected_index]
                if new_hwnd != self.app.selected_hwnd:
                    self.app.selected_hwnd = new_hwnd
                    title = self.window_combo.get().split(":", 1)[-1].strip()
                    self.app.update_status(f"Window selected: {title}")
                    print(f"Selected window HWND: {self.app.selected_hwnd}")

                    # --- Trigger automatic ROI loading for the selected window ---
                    self.app.load_rois_for_hwnd(new_hwnd)
                    # --- End of ROI loading trigger ---

                    # If capture is running, changing window might require restart?
                    if self.app.capturing:
                        # Stop capture if window changes while running? Or just update status?
                        self.app.update_status(f"Window changed to {title}. Restart capture if needed.")
                        # self.app.stop_capture() # Optional: Force stop on window change
            else:
                # This case should ideally not happen with readonly combobox selection
                if self.app.selected_hwnd is not None:
                    self.app.selected_hwnd = None
                    self.app.update_status("No window selected.")
                    self.app.load_rois_for_hwnd(None) # Clear ROIs if selection cleared
        except Exception as e:
            self.app.selected_hwnd = None
            self.app.update_status(f"Error selecting window: {e}")
            self.app.load_rois_for_hwnd(None) # Clear ROIs on error


    def on_language_changed(self, event=None):
        """Callback when OCR language is changed."""
        new_lang = self.lang_var.get()
        if new_lang in self.OCR_LANGUAGES:
            print(f"OCR Language changed to: {new_lang}")
            # Save the setting
            set_setting("ocr_language", new_lang)
            # Notify the main app to update the OCR engine
            self.app.update_ocr_engine(new_lang)
            # Status update handled by update_ocr_engine
        else:
            self.app.update_status("Invalid language selected.")


    def update_status(self, message):
        """Update the local status label (mirroring main status bar)."""
        self.status_label.config(text=f"Status: {message}")
        # Main status bar updated by self.app.update_status()


    def on_capture_started(self):
        """Update UI when capture starts."""
        self.start_btn.config(state=tk.DISABLED)
        self.refresh_btn.config(state=tk.DISABLED)
        self.window_combo.config(state=tk.DISABLED) # Disable window change during capture
        self.stop_btn.config(state=tk.NORMAL)
        self.snapshot_btn.config(state=tk.NORMAL) # Enable snapshot after starting
        self.live_view_btn.config(state=tk.DISABLED)

    def on_capture_stopped(self):
        """Update UI when capture stops."""
        self.start_btn.config(state=tk.NORMAL)
        self.refresh_btn.config(state=tk.NORMAL)
        self.window_combo.config(state="readonly") # Re-enable window selection
        self.stop_btn.config(state=tk.DISABLED)
        self.snapshot_btn.config(state=tk.DISABLED)
        self.live_view_btn.config(state=tk.DISABLED)

    def on_snapshot_taken(self):
        """Update UI when a snapshot is taken."""
        # Keep snapshot button enabled, user might return to live and take another
        self.live_view_btn.config(state=tk.NORMAL) # Allow returning to live
        # Stop button remains enabled
        # Status updated by app.take_snapshot calling app.update_status

    def on_live_view_resumed(self):
        """Update UI when returning to live view."""
        self.live_view_btn.config(state=tk.DISABLED)
        if self.app.capturing: # Only enable snapshot if capture is actually running
            self.snapshot_btn.config(state=tk.NORMAL)
            # Status updated by app.return_to_live calling app.update_status
        else:
            # If capture stopped while in snapshot mode (unlikely but possible)
            self.snapshot_btn.config(state=tk.DISABLED)
            self.on_capture_stopped() # Ensure UI reflects stopped state

# --- END OF FILE ui/capture_tab.py ---