# --- START OF FILE app.py ---

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import cv2
from PIL import Image, ImageTk
import os
import win32gui # Needed for IsWindow check in capture loop
from paddleocr import PaddleOCR, paddleocr
import platform
from pathlib import Path # Import Path

# Import utilities
from utils.capture import get_window_title, capture_window
from utils.config import load_rois, ROI_CONFIGS_DIR, _get_game_hash # Import load_rois, directory and hash func
# Import settings functions, including the new overlay config helpers
from utils.settings import (
    load_settings,
    set_setting,
    get_setting,
    update_settings,
    get_overlay_config_for_roi,
    save_overlay_config_for_roi,
)
from utils.roi import ROI
from utils.translation import CACHE_DIR, CONTEXT_DIR, _load_context # Import dirs and load_context

# Import UI components
from ui.capture_tab import CaptureTab
from ui.roi_tab import ROITab
from ui.text_tab import TextTab, StableTextTab
from ui.translation_tab import TranslationTab
from ui.overlay_tab import OverlayTab
from ui.overlay_manager import OverlayManager  # Still used to manage window lifecycle
# FloatingOverlayWindow is imported by OverlayManager
from ui.floating_controls import FloatingControls

# Constants
FPS = 10
FRAME_DELAY = 1.0 / FPS
OCR_ENGINE_LOCK = threading.Lock()


class VisualNovelTranslatorApp:
    """Main application class for the Visual Novel Translator."""

    def __init__(self, master):
        self.master = master
        self.settings = load_settings()
        # config_file is now dynamic, based on loaded game
        self.config_file = None # Start with no config file loaded

        window_title = "Visual Novel Translator"
        # Title updated later when ROIs are loaded for a game
        master.title(window_title)
        master.geometry("1200x800")
        master.minsize(1000, 700)
        master.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- Ensure Required Directories Exist ---
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            print(f"Cache directory ensured at: {CACHE_DIR}")
        except Exception as e:
            print(f"Warning: Could not create cache directory {CACHE_DIR}: {e}")
        try:
            ROI_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
            print(f"ROI Configs directory ensured at: {ROI_CONFIGS_DIR}")
        except Exception as e:
            print(f"Warning: Could not create ROI Configs directory {ROI_CONFIGS_DIR}: {e}")
        try: # NEW: Ensure context directory exists
            CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
            print(f"Context History directory ensured at: {CONTEXT_DIR}")
        except Exception as e:
            print(f"Warning: Could not create Context History directory {CONTEXT_DIR}: {e}")


        # --- Initialize variables ---
        self.capturing = False
        self.roi_selection_active = False
        self.selected_hwnd = None
        self.capture_thread = None
        self.rois = [] # Start with empty ROIs
        self.current_frame = None
        self.display_frame_tk = None
        self.snapshot_frame = None
        self.using_snapshot = False
        self.roi_start_coords = None
        self.roi_draw_rect_id = None
        self.scale_x, self.scale_y = 1.0, 1.0
        self.frame_display_coords = {'x': 0, 'y': 0, 'w': 0, 'h': 0}

        self.text_history = {}
        self.stable_texts = {}
        self.stable_threshold = get_setting("stable_threshold", 3)
        self.max_display_width = get_setting("max_display_width", 800)
        self.max_display_height = get_setting("max_display_height", 600)
        self.last_status_message = ""

        self.ocr = None
        self.ocr_lang = get_setting("ocr_language", "jpn")
        self._resize_job = None

        # --- Setup UI ---
        self._setup_ui() # Calls the modified method

        # --- Initialize Managers ---
        self.overlay_manager = OverlayManager(self.master, self)  # Still needed
        self.floating_controls = None

        # --- Load initial config (ROIs) ---
        # REMOVED: ROIs are now loaded when a window is selected
        # self._load_initial_rois()

        # --- Initialize OCR Engine ---
        initial_ocr_lang = self.ocr_lang or "jpn"
        self.update_ocr_engine(initial_ocr_lang, initial_load=True)

        # --- Show Floating Controls (Initial show) ---
        self.show_floating_controls()

    def _setup_ui(self):
        """Set up the main UI layout and tabs."""

        # --- ADD MENU BAR ---
        menu_bar = tk.Menu(self.master)
        self.master.config(menu=menu_bar)

        # Create "File" menu (optional, example)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="File", menu=file_menu)
        # Removed Load/Save As, kept Save (which is now game-specific)
        file_menu.add_command(label="Save ROIs for Current Game", command=lambda: self.roi_tab.save_rois_for_current_game() if hasattr(self, 'roi_tab') else None)
        # file_menu.add_command(label="Load ROI Config...", command=lambda: self.roi_tab.load_rois() if hasattr(self, 'roi_tab') else None) # REMOVED
        # file_menu.add_command(label="Save ROI Config As...", command=lambda: self.roi_tab.save_rois() if hasattr(self, 'roi_tab') else None) # REMOVED
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)

        # Create "Window" menu
        window_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Window", menu=window_menu)
        window_menu.add_command(label="Show Floating Controls", command=self.show_floating_controls)
        # --- END OF MENU BAR ADDITION ---

        self.paned_window = ttk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left frame for preview
        self.left_frame = ttk.Frame(self.paned_window, padding=0)
        self.paned_window.add(self.left_frame, weight=3)
        self.canvas = tk.Canvas(self.left_frame, bg="gray15", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        # Right frame for controls
        self.right_frame = ttk.Frame(self.paned_window, padding=(5, 0, 0, 0))
        self.paned_window.add(self.right_frame, weight=1)
        self.notebook = ttk.Notebook(self.right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self.capture_tab = CaptureTab(self.notebook, self)
        self.notebook.add(self.capture_tab.frame, text="Capture")
        self.roi_tab = ROITab(self.notebook, self)
        self.notebook.add(self.roi_tab.frame, text="ROIs")
        self.overlay_tab = OverlayTab(self.notebook, self)  # Overlay config tab
        self.notebook.add(self.overlay_tab.frame, text="Overlays")
        self.text_tab = TextTab(self.notebook, self)
        self.notebook.add(self.text_tab.frame, text="Live Text")
        self.stable_text_tab = StableTextTab(self.notebook, self)
        self.notebook.add(self.stable_text_tab.frame, text="Stable Text")
        self.translation_tab = TranslationTab(self.notebook, self)
        self.notebook.add(self.translation_tab.frame, text="Translation")

        # Status bar
        self.status_bar_frame = ttk.Frame(self.master, relief=tk.SUNKEN)
        self.status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_bar = ttk.Label(
            self.status_bar_frame,
            text="Status: Initializing...",
            anchor=tk.W,
            padding=(5, 2)
        )
        self.status_bar.pack(fill=tk.X)
        self.update_status("Ready. Select a window.") # Updated initial status

    def update_status(self, message):
        """Update the status bar message."""
        def _do_update():
            if hasattr(self, "status_bar") and self.status_bar.winfo_exists():
                try:
                    current_text = self.status_bar.cget("text")
                    new_text = f"Status: {message}"
                    if new_text != current_text:
                        self.status_bar.config(text=new_text)
                        self.last_status_message = message
                        # Update CaptureTab's label too
                        if (
                                hasattr(self, "capture_tab")
                                and hasattr(self.capture_tab, "status_label")
                                and self.capture_tab.status_label.winfo_exists()
                        ):
                            self.capture_tab.status_label.config(text=new_text)
                except tk.TclError:
                    pass  # Ignore if dying
            else:
                self.last_status_message = message

        try:
            if self.master.winfo_exists():
                self.master.after_idle(_do_update)
            else:
                self.last_status_message = message
        except Exception:
            self.last_status_message = message

    def load_game_context(self, hwnd):
        """Loads the game-specific context and updates the TranslationTab."""
        # Load context from file (updates global context_messages in translation.py)
        _load_context(hwnd)

        # Get the loaded context (which is now in the global list)
        # We don't need the text content here, just need to trigger UI update
        # context_to_load = "" # Default if load failed or no context
        # if hwnd:
        #     game_hash = _get_game_hash(hwnd)
        #     if game_hash:
        #         all_contexts = get_setting("game_specific_context", {})
        #         context_to_load = all_contexts.get(game_hash, "")

        # Update the UI in TranslationTab using the loaded global context
        # (This part seems redundant if _load_context updates the global var directly)
        # Let's simplify: _load_context handles the global var, UI just reads it when needed.
        # However, we DO need to update the *display* in the TranslationTab UI.
        # We need the actual text loaded by _load_context for this.
        # Let's modify _load_context to return the loaded list or empty list.

        # --- Reworked approach: _load_context updates global, we read global for UI ---
        from utils.translation import context_messages as loaded_context_list # Import the global list

        # Reconstruct the text representation if needed for display (though maybe not necessary?)
        # For now, just signal that context was loaded/cleared.
        # The translation tab itself reads the global context_messages when sending.
        # We *do* need to update the "Additional Context" text box though.
        all_game_contexts = get_setting("game_specific_context", {})
        game_hash = _get_game_hash(hwnd) if hwnd else None
        context_text_for_ui = all_game_contexts.get(game_hash, "") if game_hash else ""

        if hasattr(self, 'translation_tab') and self.translation_tab.frame.winfo_exists():
            self.translation_tab.load_context_for_game(context_text_for_ui)
        else:
            print("Translation tab not available to display context.")


    def load_rois_for_hwnd(self, hwnd):
        """Load ROIs and context automatically for the given window handle."""
        if not hwnd:
            # Clear ROIs if hwnd is None (e.g., window closed or selection cleared)
            if self.rois: # Only update if there were ROIs before
                print("Clearing ROIs as no window is selected.")
                self.rois = []
                self.config_file = None
                if hasattr(self, "roi_tab"): self.roi_tab.update_roi_list()
                if hasattr(self, "overlay_manager"): self.overlay_manager.rebuild_overlays()
                self.master.title("Visual Novel Translator")
                self.update_status("No window selected. ROIs cleared.")
                # Clear text displays and context
                self._clear_text_data()
                self.load_game_context(None) # Clear context display and global context list
            return

        self.update_status(f"Checking for ROIs for HWND {hwnd}...")
        try:
            loaded_rois, loaded_path = load_rois(hwnd) # Pass hwnd to load_rois

            if loaded_path: # ROIs were found and loaded
                self.rois = loaded_rois
                self.config_file = loaded_path
                self.update_status(f"Loaded {len(loaded_rois)} ROIs for current game.")
                self.master.title(f"Visual Novel Translator - {os.path.basename(loaded_path)}")
            else: # No ROI file found for this game
                if self.rois: # If there were ROIs from a previous game, clear them
                    print(f"No ROIs found for HWND {hwnd}. Clearing previous ROIs.")
                    self.rois = []
                    self.config_file = None
                    self.master.title("Visual Novel Translator")
                    self.update_status(f"No ROIs found for current game. Define new ROIs.")
                else:
                    # No previous ROIs and none found for current game
                    self.update_status(f"No ROIs found for current game. Define new ROIs.")

            # --- Load Game Context and History ---
            self.load_game_context(hwnd) # Loads game-specific additional context text
            _load_context(hwnd) # Loads game-specific history into global list
            # --- End Load Game Context ---

            # Update UI regardless of whether ROIs were loaded or cleared
            if hasattr(self, "roi_tab"): self.roi_tab.update_roi_list()
            if hasattr(self, "overlay_manager"): self.overlay_manager.rebuild_overlays()
            # Clear stale text data when switching games/configs
            self._clear_text_data()

        except Exception as e:
            self.update_status(f"Error loading ROIs/Context for HWND {hwnd}: {str(e)}")
            import traceback
            traceback.print_exc()
            # Clear ROIs and context on error
            self.rois = []
            self.config_file = None
            if hasattr(self, "roi_tab"): self.roi_tab.update_roi_list()
            if hasattr(self, "overlay_manager"): self.overlay_manager.rebuild_overlays()
            self.master.title("Visual Novel Translator")
            self._clear_text_data()
            self.load_game_context(None) # Clear context display and global list

    def _clear_text_data(self):
        """Clears text history, stable text, and updates relevant UI tabs."""
        self.text_history = {}
        self.stable_texts = {}
        if hasattr(self, 'text_tab') and self.text_tab.frame.winfo_exists():
            try: self.text_tab.update_text({})
            except tk.TclError: pass
        if hasattr(self, 'stable_text_tab') and self.stable_text_tab.frame.winfo_exists():
            try: self.stable_text_tab.update_text({})
            except tk.TclError: pass
        if hasattr(self, 'translation_tab') and self.translation_tab.frame.winfo_exists():
            try:
                # Clear translation preview
                self.translation_tab.translation_display.config(state=tk.NORMAL)
                self.translation_tab.translation_display.delete(1.0, tk.END)
                self.translation_tab.translation_display.config(state=tk.DISABLED)
                # Clear additional context display (loading new one handles this)
                # self.translation_tab.load_context_for_game("")
            except tk.TclError: pass # Ignore if widget destroyed
        if hasattr(self, 'overlay_manager'):
            self.overlay_manager.clear_all_overlays()


    # def _load_initial_rois(self): # REMOVED
    #     """Load ROIs from the last used config file on startup."""
    #     # ... (logic removed as loading is now triggered by window selection) ...
    #     pass

    def update_ocr_engine(self, lang_code, initial_load=False):
        """Initialize or update the PaddleOCR engine in a separate thread."""
        def init_engine():
            global OCR_ENGINE_LOCK
            lang_map = {
                "jpn": "japan",
                "jpn_vert": "japan",
                "eng": "en",
                "chi_sim": "ch",
                "chi_tra": "ch",
                "kor": "ko",
            }
            ocr_lang_paddle = lang_map.get(lang_code, "en")

            with OCR_ENGINE_LOCK:
                current_paddle_lang = getattr(self.ocr, "lang", None) if self.ocr else None
                if current_paddle_lang == ocr_lang_paddle and self.ocr is not None:
                    if not initial_load:
                        print(f"OCR engine already initialized with {lang_code}.")
                    self.master.after_idle(lambda: self.update_status(f"OCR Ready ({lang_code})."))
                    return

            if not initial_load:
                print(f"Initializing OCR engine for {lang_code}...")
            self.master.after_idle(lambda: self.update_status(f"Initializing OCR ({lang_code})..."))

            try:
                # Explicitly check for GPU availability if desired
                # use_gpu = paddleocr.is_gpu_available() # Requires GPU-enabled PaddlePaddle
                # print(f"Using GPU for OCR: {use_gpu}")
                # new_ocr_engine = PaddleOCR(use_angle_cls=True, lang=ocr_lang_paddle, show_log=False, use_gpu=use_gpu)
                new_ocr_engine = PaddleOCR(use_angle_cls=True, lang=ocr_lang_paddle, show_log=False)
                with OCR_ENGINE_LOCK:
                    self.ocr = new_ocr_engine
                    self.ocr_lang = lang_code  # Store the requested code ('jpn', 'eng')
                print(f"OCR engine ready for {lang_code}.")
                self.master.after_idle(lambda: self.update_status(f"OCR Ready ({lang_code})."))
            except Exception as e:
                print(f"!!! Error initializing PaddleOCR for lang {lang_code}: {e}")
                import traceback
                traceback.print_exc()
                self.master.after_idle(lambda: self.update_status(f"OCR Error ({lang_code}): Check console"))
                with OCR_ENGINE_LOCK:
                    self.ocr = None

        threading.Thread(target=init_engine, daemon=True).start()

    def start_capture(self):
        """Start capturing from the selected window."""
        if self.capturing:
            return
        if not self.selected_hwnd:
            messagebox.showwarning("Warning", "No visual novel window selected.", parent=self.master)
            return

        # Attempt to load ROIs/Context for the selected window if not already loaded
        if not self.rois and self.selected_hwnd:
            self.load_rois_for_hwnd(self.selected_hwnd) # This now also loads context

        with OCR_ENGINE_LOCK:
            ocr_ready = bool(self.ocr)
        if not ocr_ready:
            current_lang = self.ocr_lang or "jpn"
            self.update_ocr_engine(current_lang)
            messagebox.showinfo(
                "OCR Not Ready",
                "OCR is initializing. Capture starting, but text extraction may be delayed.",
                parent=self.master,
            )

        if self.using_snapshot:
            self.return_to_live()

        self.capturing = True
        self.capture_thread = threading.Thread(target=self.capture_process, daemon=True)
        self.capture_thread.start()

        if hasattr(self, "capture_tab"):
            self.capture_tab.on_capture_started()
        title = get_window_title(self.selected_hwnd) or f"HWND {self.selected_hwnd}"
        self.update_status(f"Capturing: {title}")
        # Rebuild overlays ensures they are created if ROIs were just loaded
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.rebuild_overlays()

    def stop_capture(self):
        """Stop the current capture process gracefully."""
        if not self.capturing:
            return
        print("Stop capture requested...")
        self.capturing = False
        self.master.after(100, self._check_thread_and_finalize_stop)

    def _check_thread_and_finalize_stop(self):
        """Checks if capture thread finished, calls finalize or re-schedules check."""
        if self.capture_thread and self.capture_thread.is_alive():
            self.master.after(100, self._check_thread_and_finalize_stop)
        else:
            self.capture_thread = None
            # Use a flag to prevent multiple calls if check runs again before flag is reset
            if not getattr(self, "_finalize_stop_in_progress", False):
                self._finalize_stop_in_progress = True
                self._finalize_stop_capture()


    def _finalize_stop_capture(self):
        """Actions to perform in the main thread after capture stops."""
        try:
            if self.capturing:  # Safety check
                print("Warning: Finalizing stop capture while flag is still true.")
                self.capturing = False

            print("Finalizing stop capture UI updates...")
            if hasattr(self, "capture_tab") and self.capture_tab.frame.winfo_exists():
                self.capture_tab.on_capture_stopped()
            if hasattr(self, "overlay_manager"):
                self.overlay_manager.hide_all_overlays()  # Hide overlays
            self.update_status("Capture stopped.")
        finally:
            self._finalize_stop_in_progress = False # Reset flag


    def take_snapshot(self):
        """Take a snapshot of the current frame for static analysis."""
        if not self.capturing and self.current_frame is None:
            messagebox.showwarning("Warning", "Capture not running and no frame available.", parent=self.master)
            return
        if self.current_frame is None:
            messagebox.showwarning("Warning", "No frame captured yet.", parent=self.master)
            return

        print("Taking snapshot...")
        self.snapshot_frame = self.current_frame.copy()
        self.using_snapshot = True
        self._display_frame(self.snapshot_frame)

        if hasattr(self, "capture_tab"):
            self.capture_tab.on_snapshot_taken()
        self.update_status("Snapshot taken. Define ROIs or return to live.")

    def return_to_live(self):
        """Return to live view from snapshot mode."""
        if not self.using_snapshot:
            return
        print("Returning to live view...")
        self.using_snapshot = False
        self.snapshot_frame = None
        self._display_frame(self.current_frame if self.current_frame is not None else None)
        if hasattr(self, "capture_tab"):
            self.capture_tab.on_live_view_resumed()
        # Update status based on whether capture is still running
        if self.capturing:
            title = get_window_title(self.selected_hwnd) or f"HWND {self.selected_hwnd}"
            self.update_status(f"Capturing: {title}")
        else:
            self.update_status("Capture stopped.")


    def toggle_roi_selection(self):
        """Enable or disable ROI selection mode."""
        if not self.roi_selection_active:
            # Check if a window is selected first
            if not self.selected_hwnd:
                messagebox.showwarning("Warning", "Select a game window first.", parent=self.master)
                return

            frame_available = self.current_frame is not None or self.snapshot_frame is not None
            if not frame_available:
                # If no frame, try taking a snapshot now if capture isn't running
                if not self.capturing:
                    print("No frame available, attempting snapshot...")
                    frame = capture_window(self.selected_hwnd)
                    if frame is not None:
                        self.current_frame = frame # Store it even if not capturing
                        self.take_snapshot()
                        # Check if snapshot was successful
                        if not self.using_snapshot: return # Exit if snapshot failed
                    else:
                        messagebox.showwarning("Warning", "Could not capture frame. Start capture or check window.", parent=self.master)
                        return
                else: # Capture running but no frame yet
                    messagebox.showwarning("Warning", "Waiting for first frame. Try again shortly.", parent=self.master)
                    return

            # If capture is running, ensure we are in snapshot mode
            if self.capturing and not self.using_snapshot:
                self.take_snapshot()
                if not self.using_snapshot:
                    return  # Snapshot failed

            # If we got here, we have a snapshot (or were already in snapshot mode)
            self.roi_selection_active = True
            if hasattr(self, "roi_tab"):
                self.roi_tab.on_roi_selection_toggled(True)
        else:
            # --- Deactivating ROI selection ---
            self.roi_selection_active = False
            if hasattr(self, "roi_tab"):
                self.roi_tab.on_roi_selection_toggled(False)
            if self.roi_draw_rect_id:
                try:
                    self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError: pass # Ignore if already deleted
            self.roi_draw_rect_id = None
            self.roi_start_coords = None
            self.update_status("ROI selection cancelled.")
            # If cancelled while in snapshot mode, return to live
            if self.using_snapshot:
                self.return_to_live()

    def capture_process(self):
        """Background thread for capture and processing."""
        last_frame_time = time.time()
        target_sleep_time = FRAME_DELAY
        print("Capture thread started.")
        while self.capturing:
            loop_start_time = time.time()
            frame_to_display = None
            try:
                if self.using_snapshot:
                    time.sleep(0.05)
                    continue

                # Ensure hwnd is still valid before capturing
                if not self.selected_hwnd or not win32gui.IsWindow(self.selected_hwnd):
                    print("Capture target window lost or invalid. Stopping.")
                    # Use after_idle to ensure thread-safe call to stop_capture
                    self.master.after_idle(self.handle_capture_failure)
                    break # Exit the loop

                frame = capture_window(self.selected_hwnd)
                if frame is None:
                    # Don't immediately stop, could be a temporary glitch (e.g., window minimized briefly)
                    # Log the failure, maybe add a counter?
                    print("Warning: capture_window returned None.")
                    time.sleep(0.5) # Wait a bit before retrying
                    continue # Skip processing this cycle

                self.current_frame = frame
                frame_to_display = frame

                ocr_engine_instance = None
                with OCR_ENGINE_LOCK:
                    ocr_engine_instance = self.ocr

                if self.rois and ocr_engine_instance:
                    self._process_rois(frame, ocr_engine_instance)

                current_time = time.time()
                # Update display frame less frequently if needed, or based on change
                if current_time - last_frame_time >= target_sleep_time:
                    if frame_to_display is not None:
                        frame_copy = frame_to_display.copy()
                        # Use after_idle for thread safety when updating Tkinter UI
                        self.master.after_idle(lambda f=frame_copy: self._display_frame(f))
                    last_frame_time = current_time

                elapsed = time.time() - loop_start_time
                sleep_duration = max(0.001, target_sleep_time - elapsed)
                time.sleep(sleep_duration)

            except Exception as e:
                print(f"!!! Error in capture loop: {e}")
                import traceback
                traceback.print_exc()
                # Use after_idle for thread safety when updating Tkinter UI
                self.master.after_idle(
                    lambda msg=str(e): self.update_status(f"Capture loop error: {msg[:60]}...")
                )
                time.sleep(1) # Pause after error before retrying
        print("Capture thread finished or exited.")

    def handle_capture_failure(self):
        """Called from main thread if capture fails definitively."""
        if self.capturing: # Check if stop wasn't already called
            self.update_status("Window lost or uncapturable. Stopping capture.")
            print("Failed to capture the selected window.")
            self.stop_capture() # This will handle UI updates
            # Optionally refresh window list? Might be redundant if user needs to select anyway.
            # if hasattr(self, "capture_tab"):
            #     self.capture_tab.refresh_window_list()

    def on_canvas_resize(self, event=None):
        """Debounced canvas resize handler."""
        if self._resize_job:
            self.master.after_cancel(self._resize_job)
        self._resize_job = self.master.after(100, self._perform_resize_redraw)

    def _perform_resize_redraw(self):
        """Actual redraw logic after resize debounce."""
        self._resize_job = None
        if not self.canvas.winfo_exists():
            return
        frame = self.snapshot_frame if self.using_snapshot else self.current_frame
        self._display_frame(frame)

    def _display_frame(self, frame):
        """Display frame on canvas, fitting and centering."""
        if not hasattr(self, "canvas") or not self.canvas.winfo_exists():
            return
        self.canvas.delete("display_content")
        self.display_frame_tk = None

        if frame is None:
            try:
                cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
                if cw > 1 and ch > 1:
                    self.canvas.create_text(
                        cw / 2, ch / 2, text="No Image\n(Select Window and Start Capture)", fill="gray50", tags="display_content", justify=tk.CENTER
                    )
            except Exception:
                pass
            return

        try:
            fh, fw = frame.shape[:2]
            cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
            if fw <= 0 or fh <= 0 or cw <= 1 or ch <= 1:
                return

            scale = min(cw / fw, ch / fh)
            nw, nh = int(fw * scale), int(fh * scale)
            if nw < 1 or nh < 1:
                return

            self.scale_x, self.scale_y = scale, scale
            self.frame_display_coords = {
                "x": (cw - nw) // 2,
                "y": (ch - nh) // 2,
                "w": nw,
                "h": nh,
            }

            resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
            display_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(display_rgb)
            self.display_frame_tk = ImageTk.PhotoImage(image=img)

            self.canvas.create_image(
                self.frame_display_coords["x"],
                self.frame_display_coords["y"],
                anchor=tk.NW,
                image=self.display_frame_tk,
                tags=("display_content", "frame_image"),
            )
            self._draw_rois()

        except Exception as e:
            print(f"Error displaying frame: {e}")

    def _process_rois(self, frame, ocr_engine):
        """Process ROIs on frame, update text/stability, schedule UI updates."""
        if frame is None or ocr_engine is None:
            return

        extracted = {}
        stable_changed = False
        new_stable = self.stable_texts.copy()

        for roi in self.rois:
            roi_img = roi.extract_roi(frame)
            if roi_img is None or roi_img.size == 0:
                extracted[roi.name] = ""
                continue

            try:
                ocr_result_raw = ocr_engine.ocr(roi_img, cls=True)
                text_lines = []
                if ocr_result_raw and isinstance(ocr_result_raw, list) and len(ocr_result_raw) > 0:
                    # Handle potential nested list structure from PaddleOCR
                    current_result_set = ocr_result_raw[0] if isinstance(ocr_result_raw[0], list) else ocr_result_raw
                    if current_result_set:
                        for item in current_result_set:
                            # Extract text part, handling different possible structures
                            text_info = None
                            if isinstance(item, list) and len(item) >= 2:
                                text_info = item[1] # Often [box, (text, confidence)]
                            elif isinstance(item, tuple) and len(item) >= 2:
                                text_info = item # Sometimes just (text, confidence)? Check Paddle docs/output.

                            # Check if text_info is valid and extract text
                            if (
                                    isinstance(text_info, (tuple, list))
                                    and len(text_info) >= 1
                                    and text_info[0]
                            ):
                                text_lines.append(str(text_info[0]))
                text = " ".join(text_lines).strip()
                extracted[roi.name] = text

                history = self.text_history.get(roi.name, {"text": "", "count": 0})
                if text == history["text"]:
                    history["count"] += 1
                else:
                    history = {"text": text, "count": 1}
                self.text_history[roi.name] = history

                is_now_stable = history["count"] >= self.stable_threshold
                was_stable = roi.name in self.stable_texts
                current_stable = self.stable_texts.get(roi.name)

                if is_now_stable:
                    if not was_stable or current_stable != text:
                        new_stable[roi.name] = text
                        stable_changed = True
                elif was_stable:
                    # Text became unstable or disappeared
                    if roi.name in new_stable: # Check if it exists before deleting
                        del new_stable[roi.name]
                        stable_changed = True

            except Exception as e:
                print(f"!!! OCR Error for ROI {roi.name}: {e}")
                extracted[roi.name] = "[OCR Error]"
                self.text_history[roi.name] = {"text": "[OCR Error]", "count": 1}
                if roi.name in new_stable:
                    del new_stable[roi.name]
                    stable_changed = True

        # Schedule UI updates only if the widgets exist and use after_idle for thread safety
        if hasattr(self, "text_tab") and self.text_tab.frame.winfo_exists():
            self.master.after_idle(lambda et=extracted.copy(): self.text_tab.update_text(et))

        if stable_changed:
            self.stable_texts = new_stable
            if hasattr(self, "stable_text_tab") and self.stable_text_tab.frame.winfo_exists():
                self.master.after_idle(
                    lambda st=self.stable_texts.copy(): self.stable_text_tab.update_text(st)
                )
            # Trigger auto-translation if enabled and stable text changed
            if (
                    hasattr(self, "translation_tab")
                    and self.translation_tab.frame.winfo_exists()
                    and self.translation_tab.is_auto_translate_enabled()
            ):
                # Only trigger if there's actually stable text to translate
                if any(self.stable_texts.values()):
                    self.master.after_idle(self.translation_tab.perform_translation)
                else:
                    # If stable text disappeared, clear overlays/translation preview
                    if hasattr(self, 'overlay_manager'):
                        self.master.after_idle(self.overlay_manager.clear_all_overlays)
                    if hasattr(self, 'translation_tab'):
                        self.master.after_idle(lambda: self.translation_tab.update_translation_results({}, "[No stable text detected]"))


    def _draw_rois(self):
        """Draw ROI rectangles on the canvas."""
        if not hasattr(self, "canvas") or not self.canvas.winfo_exists() or self.frame_display_coords["w"] <= 0:
            return
        ox, oy = self.frame_display_coords["x"], self.frame_display_coords["y"]
        for i, roi in enumerate(self.rois):
            try:
                dx1 = int(roi.x1 * self.scale_x) + ox
                dy1 = int(roi.y1 * self.scale_y) + oy
                dx2 = int(roi.x2 * self.scale_x) + ox
                dy2 = int(roi.y2 * self.scale_y) + oy
                self.canvas.create_rectangle(
                    dx1, dy1, dx2, dy2, outline="lime", width=1, tags=("display_content", f"roi_{i}")
                )
                self.canvas.create_text(
                    dx1 + 3,
                    dy1 + 1,
                    text=roi.name,
                    fill="lime",
                    anchor=tk.NW,
                    font=("TkDefaultFont", 8),
                    tags=("display_content", f"roi_label_{i}"),
                    )
            except Exception as e:
                print(f"Error drawing ROI {roi.name}: {e}")

    # --- Mouse Events for ROI Definition ---
    def on_mouse_down(self, event):
        """Start ROI definition drag."""
        if not self.roi_selection_active or not self.using_snapshot:
            return
        img_x, img_y = self.frame_display_coords["x"], self.frame_display_coords["y"]
        img_w, img_h = self.frame_display_coords["w"], self.frame_display_coords["h"]
        # Only start drawing if click is within the displayed image bounds
        if not (img_x <= event.x < img_x + img_w and img_y <= event.y < img_y + img_h):
            self.roi_start_coords = None
            if self.roi_draw_rect_id:
                try: self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError: pass
            self.roi_draw_rect_id = None
            return
        self.roi_start_coords = (event.x, event.y)
        if self.roi_draw_rect_id:
            try: self.canvas.delete(self.roi_draw_rect_id)
            except tk.TclError: pass
        self.roi_draw_rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="red", width=2, tags="roi_drawing"
        )

    def on_mouse_drag(self, event):
        """Update ROI definition rectangle during drag."""
        if not self.roi_selection_active or not self.roi_start_coords or not self.roi_draw_rect_id:
            return
        sx, sy = self.roi_start_coords
        img_x, img_y = self.frame_display_coords["x"], self.frame_display_coords["y"]
        img_w, img_h = self.frame_display_coords["w"], self.frame_display_coords["h"]

        # Clamp current coordinates to be within the image bounds on canvas
        cx = max(img_x, min(event.x, img_x + img_w))
        cy = max(img_y, min(event.y, img_y + img_h))

        try:
            # Ensure start coords are also clamped in case mouse down was slightly off
            clamped_sx = max(img_x, min(sx, img_x + img_w))
            clamped_sy = max(img_y, min(sy, img_y + img_h))
            self.canvas.coords(self.roi_draw_rect_id, clamped_sx, clamped_sy, cx, cy)
        except tk.TclError:
            self.roi_draw_rect_id = None
            self.roi_start_coords = None

    def on_mouse_up(self, event):
        """Finalize ROI definition on mouse release."""
        if not self.roi_selection_active or not self.roi_start_coords or not self.roi_draw_rect_id:
            # Clean up drawing rectangle if it exists but shouldn't
            if self.roi_draw_rect_id:
                try: self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError: pass
            self.roi_draw_rect_id = None
            self.roi_start_coords = None
            # If ROI selection wasn't active, don't return to live unnecessarily
            # if self.using_snapshot:
            #     self.return_to_live()
            return

        try:
            coords = self.canvas.coords(self.roi_draw_rect_id)
        except tk.TclError:
            coords = None # Rectangle was likely deleted

        # Clean up drawing rectangle ID and state
        if self.roi_draw_rect_id:
            try: self.canvas.delete(self.roi_draw_rect_id)
            except tk.TclError: pass
        self.roi_draw_rect_id = None
        self.roi_start_coords = None
        self.roi_selection_active = False  # Turn off mode
        if hasattr(self, "roi_tab"):
            self.roi_tab.on_roi_selection_toggled(False) # Update button text

        # --- Finalize ROI Creation ---
        if coords is None or len(coords) != 4:
            print("ROI definition failed or cancelled (invalid coords).")
            if self.using_snapshot: self.return_to_live()
            return

        x1d, y1d, x2d, y2d = map(int, coords)
        min_size = 5 # Minimum pixel size on canvas
        if abs(x2d - x1d) < min_size or abs(y2d - y1d) < min_size:
            messagebox.showwarning(
                "ROI Too Small",
                f"Selected region too small (min {min_size}x{min_size} px on preview).",
                parent=self.master,
            )
            if self.using_snapshot: self.return_to_live()
            return

        roi_name = self.roi_tab.roi_name_entry.get().strip()
        overwrite_name = None
        if not roi_name:
            i = 1
            roi_name = f"roi_{i}"
            while roi_name in [r.name for r in self.rois]:
                i += 1
                roi_name = f"roi_{i}"
        elif roi_name in [r.name for r in self.rois]:
            if not messagebox.askyesno("ROI Exists", f"Overwrite ROI '{roi_name}'?", parent=self.master):
                if self.using_snapshot: self.return_to_live() # User cancelled overwrite
                return
            overwrite_name = roi_name

        # Convert canvas coordinates back to original frame coordinates
        ox, oy = self.frame_display_coords["x"], self.frame_display_coords["y"]
        # img_w, img_h = self.frame_display_coords["w"], self.frame_display_coords["h"] # Not needed directly here

        # Coordinates relative to the displayed image top-left corner
        rx1 = min(x1d, x2d) - ox
        ry1 = min(y1d, y2d) - oy
        rx2 = max(x1d, x2d) - ox
        ry2 = max(y1d, y2d) - oy

        # Clamp relative coordinates just in case (should be within bounds due to drag clamping)
        # crx1 = max(0, min(rx1, img_w))
        # cry1 = max(0, min(ry1, img_h))
        # crx2 = max(0, min(rx2, img_w))
        # cry2 = max(0, min(ry2, img_h))

        # Check scale validity before division
        if self.scale_x <= 0 or self.scale_y <= 0:
            print("Error: Invalid display scale factor.")
            if self.using_snapshot: self.return_to_live()
            return

        # Convert clamped relative coordinates to original frame coordinates
        ox1 = int(rx1 / self.scale_x)
        oy1 = int(ry1 / self.scale_y)
        ox2 = int(rx2 / self.scale_x)
        oy2 = int(ry2 / self.scale_y)

        # Final check on original coordinates size
        if abs(ox2 - ox1) < 1 or abs(oy2 - oy1) < 1:
            messagebox.showwarning("ROI Too Small", "Calculated ROI size is too small in original image.", parent=self.master)
            if self.using_snapshot: self.return_to_live()
            return

        new_roi = ROI(roi_name, ox1, oy1, ox2, oy2)

        if overwrite_name:
            self.rois = [r for r in self.rois if r.name != overwrite_name]
            # Overwriting: Keep existing overlay settings unless explicitly reset?
            # Or clear them? Let's keep them for now.
            # if hasattr(self, "overlay_manager"):
            #     all_settings = get_setting("overlay_settings", {})
            #     if overwrite_name in all_settings:
            #         del all_settings[overwrite_name]
            #     update_settings({"overlay_settings": all_settings})
            #     self.overlay_manager.destroy_overlay(overwrite_name) # Destroy old overlay if needed

        self.rois.append(new_roi)
        print(f"Created/Updated ROI: {new_roi.to_dict()}")

        if hasattr(self, "roi_tab"):
            self.roi_tab.update_roi_list() # Update listbox
        self._draw_rois()  # Redraw ROIs on the snapshot
        action = "created" if not overwrite_name else "updated"
        self.update_status(f"ROI '{roi_name}' {action}. Remember to save.") # Remind user to save

        # Suggest next name
        if hasattr(self, "roi_tab"):
            next_name = "dialogue" if "dialogue" not in [r.name for r in self.rois] else ""
            if not next_name:
                i = 1
                next_name = f"roi_{i}"
                while next_name in [r.name for r in self.rois]:
                    i += 1
                    next_name = f"roi_{i}"
            self.roi_tab.roi_name_entry.delete(0, tk.END)
            self.roi_tab.roi_name_entry.insert(0, next_name)

        # Create or update overlay window for the new/modified ROI
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.create_overlay_for_roi(new_roi)

        # Return to live view after successful ROI creation/update
        if self.using_snapshot:
            self.return_to_live()


    def show_floating_controls(self):
        """Creates/shows the floating control window."""
        try:
            if self.floating_controls is None or not self.floating_controls.winfo_exists():
                self.floating_controls = FloatingControls(self.master, self)
            else:
                self.floating_controls.deiconify()
                self.floating_controls.lift()
                self.floating_controls.update_button_states()
        except Exception as e:
            print(f"Error showing floating controls: {e}")
            self.update_status("Error showing floating controls.")

    def hide_floating_controls(self):
        """Hides the floating control window."""
        if self.floating_controls and self.floating_controls.winfo_exists():
            self.floating_controls.withdraw()

    def on_close(self):
        """Handle application closing."""
        print("Close requested...")
        if self.capturing:
            self.update_status("Stopping capture before closing...")
            self.stop_capture()
            # Give capture thread time to stop before finalizing
            self.master.after(500, self.check_capture_stopped_and_close) # Increased delay slightly
        else:
            self._finalize_close()

    def check_capture_stopped_and_close(self):
        """Check if capture stopped before finalizing close."""
        if not self.capturing and (self.capture_thread is None or not self.capture_thread.is_alive()):
            self._finalize_close()
        else:
            # If still capturing, wait longer
            print("Waiting for capture thread to stop...")
            self.master.after(500, self.check_capture_stopped_and_close)

    def _finalize_close(self):
        """Final cleanup and destroy window."""
        print("Finalizing close...")
        self.capturing = False # Ensure flag is false
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.destroy_all_overlays()
        if self.floating_controls and self.floating_controls.winfo_exists():
            try:
                # Save position only if it's currently visible/normal
                if self.floating_controls.state() == "normal":
                    # Extract geometry parts carefully
                    geo = self.floating_controls.geometry() # e.g., "150x50+100+200"
                    parts = geo.split('+')
                    if len(parts) == 3: # Should have size, x, y
                        x_str, y_str = parts[1], parts[2]
                        # Validate they are numbers before saving
                        if x_str.isdigit() and y_str.isdigit():
                            set_setting("floating_controls_pos", f"{x_str},{y_str}")
                        else:
                            print(f"Warning: Invalid coordinates in floating controls geometry: {geo}")
                    else:
                        print(f"Warning: Could not parse floating controls geometry for saving: {geo}")
            except Exception as e:
                print(f"Error saving floating controls position: {e}")
            try:
                self.floating_controls.destroy()
            except tk.TclError:
                pass

        print("Exiting application.")
        try:
            self.master.quit()
            self.master.destroy()
        except tk.TclError:
            pass # Ignore errors if already destroyed
        except Exception as e:
            print(f"Error during final destruction: {e}")

# --- END OF FILE app.py ---