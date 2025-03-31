# --- START OF FILE app.py ---

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import cv2
import numpy as np
from PIL import Image, ImageTk
import os
import win32gui


# Utility Imports
from utils.capture import get_window_title, capture_window, capture_screen_region
from utils.config import load_rois, ROI_CONFIGS_DIR, _get_game_hash # Use config functions
from utils.settings import load_settings, set_setting, get_setting, get_overlay_config_for_roi
from utils.roi import ROI
from utils.translation import CACHE_DIR, CONTEXT_DIR, _load_context, translate_text
import utils.ocr as ocr # Import the refactored ocr module

# UI Imports
from ui.capture_tab import CaptureTab
from ui.roi_tab import ROITab
from ui.text_tab import TextTab, StableTextTab
from ui.translation_tab import TranslationTab
from ui.overlay_tab import OverlayTab, SNIP_ROI_NAME
from ui.overlay_manager import OverlayManager
from ui.floating_overlay_window import FloatingOverlayWindow, ClosableFloatingOverlayWindow
from ui.floating_controls import FloatingControls
from ui.preview_window import PreviewWindow # Import the new preview window
from ui.color_picker import ScreenColorPicker # Import screen color picker

FPS = 10 # Target frames per second for capture loop
FRAME_DELAY = 1.0 / FPS

class VisualNovelTranslatorApp:
    def __init__(self, master):
        self.master = master
        self.settings = load_settings()
        self.config_file = None # Path to the currently loaded game-specific ROI config

        window_title = "Visual Novel Translator"
        master.title(window_title)
        master.geometry("1200x800") # Initial size
        master.minsize(1000, 700) # Minimum size
        master.protocol("WM_DELETE_WINDOW", self.on_close)

        # Ensure necessary directories exist
        self._ensure_dirs()

        # State variables
        self.capturing = False
        self.roi_selection_active = False
        self.selected_hwnd = None
        self.capture_thread = None
        self.rois = [] # List of ROI objects for the current game
        self.current_frame = None # Last captured frame (NumPy array)
        self.display_frame_tk = None # PhotoImage for canvas display
        self.snapshot_frame = None # Stored frame for snapshot mode
        self.using_snapshot = False # Flag if snapshot is active
        self.roi_start_coords = None # For drawing new ROIs on canvas
        self.roi_draw_rect_id = None # Canvas item ID for the drawing rectangle
        self.scale_x, self.scale_y = 1.0, 1.0 # Scaling factor for display
        self.frame_display_coords = {'x': 0, 'y': 0, 'w': 0, 'h': 0} # Position/size on canvas

        # Snip & Translate state
        self.snip_mode_active = False
        self.snip_overlay = None
        self.snip_canvas = None
        self.snip_start_coords = None
        self.snip_rect_id = None
        self.current_snip_window = None # Holds the ClosableFloatingOverlayWindow for snip results

        # Text processing state
        self.text_history = {} # Tracks consecutive identical OCR results per ROI
        self.stable_texts = {} # Holds text considered stable for translation
        self.stable_threshold = get_setting("stable_threshold", 3)
        self.max_display_width = get_setting("max_display_width", 800) # Max width for canvas image
        self.max_display_height = get_setting("max_display_height", 600) # Max height for canvas image
        self.last_status_message = ""

        # OCR Engine State
        self.ocr_engine_type = get_setting("ocr_engine", "paddle") # Store the selected type
        self.ocr_lang = get_setting("ocr_language", "jpn")
        self.ocr_engine_ready = False # Flag to track if the current engine is ready
        self._ocr_init_thread = None # Thread for background initialization

        self._resize_job = None # For debouncing canvas resize events

        # Setup UI components
        self._setup_ui()
        self.overlay_manager = OverlayManager(self.master, self) # Initialize OverlayManager
        self.floating_controls = None # Initialize as None

        # Initialize OCR engine (now happens in background)
        self._trigger_ocr_initialization(self.ocr_engine_type, self.ocr_lang, initial_load=True)
        # Do NOT show floating controls on startup anymore
        # self.show_floating_controls()

    def _ensure_dirs(self):
        """Creates necessary directories if they don't exist."""
        dirs_to_check = [CACHE_DIR, ROI_CONFIGS_DIR, CONTEXT_DIR]
        for d in dirs_to_check:
            try:
                d.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"Warning: Failed to create directory {d}: {e}")

    def _setup_ui(self):
        """Builds the main UI elements."""
        # --- Menu Bar ---
        menu_bar = tk.Menu(self.master)
        self.master.config(menu=menu_bar)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="File", menu=file_menu)
        # Add command to save ROIs (references roi_tab method)
        file_menu.add_command(label="Save All ROI Settings for Current Game",
                              command=lambda: self.roi_tab.save_rois_for_current_game() if hasattr(self, 'roi_tab') else None)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)

        window_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Window", menu=window_menu)
        window_menu.add_command(label="Show Floating Controls", command=self.show_floating_controls)
        # Add command to hide, although closing the window does the same
        window_menu.add_command(label="Hide Floating Controls", command=self.hide_floating_controls)


        # --- Main Layout (Paned Window) ---
        self.paned_window = ttk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left Pane: Image Preview Canvas
        self.left_frame = ttk.Frame(self.paned_window, padding=0)
        self.paned_window.add(self.left_frame, weight=3) # Give more weight initially
        self.canvas = tk.Canvas(self.left_frame, bg="gray15", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        # Bind mouse events for ROI definition
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        # Bind resize event
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        # Right Pane: Control Tabs
        self.right_frame = ttk.Frame(self.paned_window, padding=(5, 0, 0, 0))
        self.paned_window.add(self.right_frame, weight=1)
        self.notebook = ttk.Notebook(self.right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Initialize Tabs
        self.capture_tab = CaptureTab(self.notebook, self)
        self.notebook.add(self.capture_tab.frame, text="Capture")
        self.roi_tab = ROITab(self.notebook, self)
        self.notebook.add(self.roi_tab.frame, text="ROIs")
        self.overlay_tab = OverlayTab(self.notebook, self)
        self.notebook.add(self.overlay_tab.frame, text="Overlays")
        self.text_tab = TextTab(self.notebook, self)
        self.notebook.add(self.text_tab.frame, text="Live Text")
        self.stable_text_tab = StableTextTab(self.notebook, self)
        self.notebook.add(self.stable_text_tab.frame, text="Stable Text")
        self.translation_tab = TranslationTab(self.notebook, self)
        self.notebook.add(self.translation_tab.frame, text="Translation")

        # --- Status Bar ---
        self.status_bar_frame = ttk.Frame(self.master, relief=tk.SUNKEN)
        self.status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_bar = ttk.Label(self.status_bar_frame, text="Status: Initializing...", anchor=tk.W, padding=(5, 2))
        self.status_bar.pack(fill=tk.X)
        self.update_status("Ready. Select a window.")

    def update_status(self, message):
        """Updates the status bar text (thread-safe)."""
        def _do_update():
            if hasattr(self, "status_bar") and self.status_bar.winfo_exists():
                try:
                    current_text = self.status_bar.cget("text")
                    new_text = f"Status: {message}"
                    if new_text != current_text:
                        self.status_bar.config(text=new_text)
                        self.last_status_message = message
                        # Also update the status label in the Capture tab if it exists
                        if hasattr(self, "capture_tab") and hasattr(self.capture_tab, "status_label") and self.capture_tab.status_label.winfo_exists():
                            self.capture_tab.status_label.config(text=new_text)
                except tk.TclError:
                    # Widget might be destroyed during shutdown
                    pass
            else:
                # Store message if status bar isn't ready yet
                self.last_status_message = message

        try:
            # Schedule the update on the main thread
            if self.master.winfo_exists():
                self.master.after_idle(_do_update)
            else:
                self.last_status_message = message # Store if master window gone
        except Exception:
            # Fallback if scheduling fails
            self.last_status_message = message

    def load_game_context(self, hwnd):
        """Loads translation context history and game-specific context."""
        _load_context(hwnd) # Load history from file into memory (translation.py)

        # Load game-specific additional context from settings
        all_game_contexts = get_setting("game_specific_context", {})
        game_hash = _get_game_hash(hwnd) if hwnd else None
        context_text_for_ui = all_game_contexts.get(game_hash, "") if game_hash else ""

        # Update the UI in the Translation tab
        if hasattr(self, 'translation_tab') and self.translation_tab.frame.winfo_exists():
            self.translation_tab.load_context_for_game(context_text_for_ui)

    def load_rois_for_hwnd(self, hwnd):
        """Loads ROI configuration when the selected window changes."""
        if not hwnd:
            # Clear ROIs if no window is selected
            if self.rois: # Only clear if there were ROIs before
                print("Clearing ROIs as no window is selected.")
                self.rois = []
                self.config_file = None
                if hasattr(self, "roi_tab"): self.roi_tab.update_roi_list()
                # Destroy existing overlays managed by the manager
                if hasattr(self, "overlay_manager"): self.overlay_manager.destroy_all_overlays()
                self.master.title("Visual Novel Translator") # Reset title
                self.update_status("No window selected. ROIs cleared.")
                self._clear_text_data() # Clear text history, stable text, etc.
                self.load_game_context(None) # Load default/empty context
            return

        self.update_status(f"Checking for ROIs for HWND {hwnd}...")
        try:
            # Use the load_rois function from config.py
            loaded_rois, loaded_path = load_rois(hwnd)

            if loaded_path is not None: # A config file was found or load attempt was made
                self.rois = loaded_rois # This might be an empty list if file was empty/corrupt
                self.config_file = loaded_path
                if loaded_rois:
                    self.update_status(f"Loaded {len(loaded_rois)} ROIs for current game.")
                    self.master.title(f"Visual Novel Translator - {os.path.basename(loaded_path)}")
                else:
                    # File existed but was empty or invalid
                    self.update_status("ROI config found but empty/invalid. Define new ROIs.")
                    self.master.title(f"Visual Novel Translator - {os.path.basename(loaded_path)}")

            else: # No config file found for this game
                if self.rois: # Clear if switching from a game that had ROIs
                    print(f"No ROIs found for HWND {hwnd}. Clearing previous ROIs.")
                    self.rois = []
                    self.config_file = None
                    self.master.title("Visual Novel Translator") # Reset title
                self.update_status("No ROIs found for current game. Define new ROIs.")

            # Always load context after potentially changing games
            self.load_game_context(hwnd)

            # Update UI elements related to ROIs
            if hasattr(self, "roi_tab"): self.roi_tab.update_roi_list()
            # Rebuild overlay *data structures* but don't show windows yet
            if hasattr(self, "overlay_manager"):
                self.overlay_manager.rebuild_overlays() # Rebuilds internal state, visibility controlled by capture state
            self._clear_text_data() # Clear previous text data

        except Exception as e:
            # General error during loading
            self.update_status(f"Error loading ROIs/Context for HWND {hwnd}: {str(e)}")
            import traceback
            traceback.print_exc()
            # Reset state
            self.rois = []
            self.config_file = None
            if hasattr(self, "roi_tab"): self.roi_tab.update_roi_list()
            if hasattr(self, "overlay_manager"): self.overlay_manager.destroy_all_overlays() # Destroy on error
            self.master.title("Visual Novel Translator")
            self._clear_text_data()
            self.load_game_context(None)

    def _clear_text_data(self):
        """Resets text history, stable text, and clears related UI displays."""
        self.text_history = {}
        self.stable_texts = {}

        # Safely update UI tabs if they exist
        def safe_update(widget_attr_name, update_method_name, *args):
            widget = getattr(self, widget_attr_name, None)
            if widget and hasattr(widget, 'frame') and widget.frame.winfo_exists():
                update_method = getattr(widget, update_method_name, None)
                if update_method:
                    try:
                        update_method(*args)
                    except tk.TclError: pass # Ignore errors if widget is destroyed
                    except Exception as e: print(f"Error updating {widget_attr_name}: {e}")

        safe_update("text_tab", "update_text", {})
        safe_update("stable_text_tab", "update_text", {})

        # Clear translation preview display
        if hasattr(self, "translation_tab") and self.translation_tab.frame.winfo_exists():
            try:
                self.translation_tab.translation_display.config(state=tk.NORMAL)
                self.translation_tab.translation_display.delete(1.0, tk.END)
                self.translation_tab.translation_display.config(state=tk.DISABLED)
            except tk.TclError: pass

        # Clear any text currently shown in overlays (if capture isn't running)
        if hasattr(self, "overlay_manager") and not self.capturing:
            self.overlay_manager.clear_all_overlays()

    def _trigger_ocr_initialization(self, engine_type, lang_code, initial_load=False):
        """Starts the OCR engine initialization in a background thread."""
        # Abort if an init thread is already running
        if self._ocr_init_thread and self._ocr_init_thread.is_alive():
            print("[OCR Init] Initialization already in progress. Ignoring new request.")
            return

        self.ocr_engine_ready = False # Mark as not ready until init completes
        status_msg = f"Initializing OCR ({engine_type}/{lang_code})..."
        if not initial_load:
            print(status_msg)
        self.update_status(status_msg)

        def init_task():
            try:
                # Call the extract_text function with a dummy image just to trigger initialization
                # This relies on the caching/initialization logic within ocr.py
                dummy_img = np.zeros((10, 10, 3), dtype=np.uint8) # Small dummy image
                ocr.extract_text(dummy_img, lang=lang_code, engine_type=engine_type)
                # If no exception, initialization was successful (or already done)
                self.ocr_engine_ready = True
                success_msg = f"OCR Ready ({engine_type}/{lang_code})."
                print(success_msg)
                self.master.after_idle(lambda: self.update_status(success_msg))
            except Exception as e:
                self.ocr_engine_ready = False
                error_msg = f"OCR Error ({engine_type}/{lang_code}): {str(e)[:60]}..."
                print(f"!!! Error during OCR initialization thread: {e}")
                # import traceback # Optional: uncomment for full trace
                # traceback.print_exc()
                self.master.after_idle(lambda: self.update_status(error_msg))

        self._ocr_init_thread = threading.Thread(target=init_task, daemon=True)
        self._ocr_init_thread.start()

    def set_ocr_engine(self, engine_type, lang_code):
        """Sets the desired OCR engine and triggers initialization."""
        if engine_type == self.ocr_engine_type:
            print(f"OCR engine already set to {engine_type}.")
            # Still might need re-init if language changed implicitly, trigger anyway
            self._trigger_ocr_initialization(engine_type, lang_code)
            return

        print(f"Setting OCR engine to: {engine_type}")
        self.ocr_engine_type = engine_type
        set_setting("ocr_engine", engine_type) # Save preference
        self._trigger_ocr_initialization(engine_type, lang_code)

    def update_ocr_language(self, lang_code, engine_type):
        """Sets the desired OCR language and triggers engine re-initialization."""
        if lang_code == self.ocr_lang and self.ocr_engine_ready:
            # Check if the current *engine* matches the requested one too
            if engine_type == self.ocr_engine_type:
                print(f"OCR language already set to {lang_code} for engine {engine_type}.")
                return # No change needed if engine is ready and matches

        print(f"Setting OCR language to: {lang_code} for engine {engine_type}")
        self.ocr_lang = lang_code
        set_setting("ocr_language", lang_code) # Save preference
        # Always trigger re-initialization when language changes, using the current engine type
        self._trigger_ocr_initialization(engine_type, lang_code)


    def update_stable_threshold(self, new_value):
        """Updates the stability threshold from UI controls."""
        try:
            new_threshold = int(float(new_value))
            if new_threshold >= 1:
                if self.stable_threshold != new_threshold:
                    self.stable_threshold = new_threshold
                    # Save the setting persistently
                    if set_setting("stable_threshold", new_threshold):
                        self.update_status(f"Stability threshold set to {new_threshold}.")
                        print(f"Stability threshold updated to: {new_threshold}")
                    else:
                        self.update_status("Error saving stability threshold.")
            else:
                print(f"Ignored invalid threshold value: {new_threshold}")
        except (ValueError, TypeError):
            print(f"Ignored non-numeric threshold value: {new_value}")

    def start_capture(self):
        """Starts the main capture and processing loop."""
        if self.capturing: return # Already running
        if not self.selected_hwnd:
            messagebox.showwarning("Warning", "No visual novel window selected.", parent=self.master)
            return

        # Ensure ROIs are loaded for the selected game
        if not self.rois and self.selected_hwnd:
            # This call now just loads data, doesn't show overlays
            self.load_rois_for_hwnd(self.selected_hwnd)

        # Check if OCR engine is ready
        if not self.ocr_engine_ready:
            # If not ready, trigger initialization again and inform user
            self._trigger_ocr_initialization(self.ocr_engine_type, self.ocr_lang)
            messagebox.showinfo("OCR Not Ready", f"OCR ({self.ocr_engine_type}/{self.ocr_lang}) is initializing... Capture will start, but text extraction may be delayed.", parent=self.master)

        # If currently viewing a snapshot, return to live view first
        if self.using_snapshot: self.return_to_live()

        self.capturing = True
        # Start the capture loop in a separate thread
        self.capture_thread = threading.Thread(target=self.capture_process, daemon=True)
        self.capture_thread.start()

        # Update UI state
        if hasattr(self, "capture_tab"): self.capture_tab.on_capture_started()
        title = get_window_title(self.selected_hwnd) or f"HWND {self.selected_hwnd}"
        self.update_status(f"Capturing: {title}")

        # Notify OverlayManager that capture has started, which will show overlays
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.notify_capture_started()

        # Show floating controls now that capture is active
        self.show_floating_controls()

    def stop_capture(self):
        """Stops the capture loop."""
        if not self.capturing: return # Already stopped
        print("Stop capture requested...")
        self.capturing = False # Signal the thread to stop
        # Wait a short time and then check if the thread has finished
        self.master.after(100, self._check_thread_and_finalize_stop)

    def _check_thread_and_finalize_stop(self):
        """Checks if the capture thread has stopped and finalizes UI updates."""
        if self.capture_thread and self.capture_thread.is_alive():
            # Thread still running, check again later
            self.master.after(100, self._check_thread_and_finalize_stop)
        else:
            # Thread finished, finalize UI state
            self.capture_thread = None
            # Use a flag to prevent multiple finalizations if called rapidly
            if not getattr(self, "_finalize_stop_in_progress", False):
                self._finalize_stop_in_progress = True
                self._finalize_stop_capture()

    def _finalize_stop_capture(self):
        """Updates UI elements after capture has fully stopped."""
        try:
            # Ensure flag is correct even if called directly
            if self.capturing:
                print("Warning: Finalizing stop capture while flag is still true.")
                self.capturing = False

            print("Finalizing stop capture UI updates...")
            # Update Capture tab buttons
            if hasattr(self, "capture_tab") and self.capture_tab.frame.winfo_exists():
                self.capture_tab.on_capture_stopped()
            # Notify OverlayManager to hide overlays
            if hasattr(self, "overlay_manager"):
                self.overlay_manager.notify_capture_stopped()
            # Hide floating controls
            self.hide_floating_controls()
            self.update_status("Capture stopped.")
        finally:
            # Reset the finalization flag
            self._finalize_stop_in_progress = False

    def take_snapshot(self):
        """Freezes the display on the current frame for ROI definition."""
        # Check if there's a frame to snapshot
        if self.current_frame is None:
            if self.capturing:
                messagebox.showwarning("Warning", "Waiting for first frame to capture.", parent=self.master)
            else:
                messagebox.showwarning("Warning", "Start capture or select window first.", parent=self.master)
            return

        print("Taking snapshot...")
        self.snapshot_frame = self.current_frame.copy() # Store a copy
        self.using_snapshot = True
        self._display_frame(self.snapshot_frame) # Update canvas with the snapshot

        # Update UI state
        if hasattr(self, "capture_tab"): self.capture_tab.on_snapshot_taken()
        self.update_status("Snapshot taken. Define ROIs or return to live.")

    def return_to_live(self):
        """Resumes displaying live captured frames."""
        if not self.using_snapshot: return # Already live

        print("Returning to live view...")
        self.using_snapshot = False
        self.snapshot_frame = None # Clear the stored snapshot
        # Display the latest live frame if available, otherwise clear canvas
        self._display_frame(self.current_frame if self.current_frame is not None else None)

        # Update UI state
        if hasattr(self, "capture_tab"): self.capture_tab.on_live_view_resumed()
        if self.capturing:
            title = get_window_title(self.selected_hwnd) or f"HWND {self.selected_hwnd}"
            self.update_status(f"Capturing: {title}")
        else:
            self.update_status("Capture stopped.") # Or "Ready" if appropriate

    def toggle_roi_selection(self):
        """Activates or deactivates ROI definition mode."""
        if not self.roi_selection_active:
            # --- Pre-checks before activating ---
            if not self.selected_hwnd:
                messagebox.showwarning("Warning", "Select a game window first.", parent=self.master)
                return

            # Ensure a frame is available for drawing on
            frame_available = self.current_frame is not None or self.snapshot_frame is not None
            if not frame_available:
                if not self.capturing:
                    # Try to take a snapshot if not capturing
                    print("No frame available, attempting snapshot for ROI definition...")
                    frame = capture_window(self.selected_hwnd)
                    if frame is not None:
                        self.current_frame = frame # Store it even if not capturing
                        self.take_snapshot() # This sets using_snapshot = True
                    # Check if snapshot succeeded
                    if not self.using_snapshot:
                        messagebox.showwarning("Warning", "Could not capture frame for ROI definition.", parent=self.master)
                        return
                else:
                    # Capturing but no frame yet
                    messagebox.showwarning("Warning", "Waiting for first frame to be captured.", parent=self.master)
                    return

            # If capturing live, switch to snapshot mode automatically
            if self.capturing and not self.using_snapshot:
                self.take_snapshot()
            # If still not using snapshot (e.g., snapshot failed), abort
            if not self.using_snapshot:
                print("Failed to enter snapshot mode for ROI definition.")
                return

            # --- Activate ROI selection mode ---
            self.roi_selection_active = True
            if hasattr(self, "roi_tab"): self.roi_tab.on_roi_selection_toggled(True)
            # Status updated in roi_tab

        else:
            # --- Deactivate ROI selection mode ---
            self.roi_selection_active = False
            if hasattr(self, "roi_tab"): self.roi_tab.on_roi_selection_toggled(False)
            # Clean up drawing rectangle if it exists
            if self.roi_draw_rect_id:
                try: self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError: pass
            self.roi_draw_rect_id = None
            self.roi_start_coords = None
            self.update_status("ROI selection cancelled.")
            # Automatically return to live view if we were in snapshot mode
            if self.using_snapshot: self.return_to_live()

    def start_snip_mode(self):
        """Initiates the screen region selection for Snip & Translate."""
        if self.snip_mode_active:
            print("Snip mode already active.")
            return

        # Check OCR readiness
        if not self.ocr_engine_ready:
            messagebox.showwarning("OCR Not Ready", f"OCR engine ({self.ocr_engine_type}/{self.ocr_lang}) not initialized. Cannot use Snip & Translate.", parent=self.master)
            # Optionally trigger initialization again
            # self._trigger_ocr_initialization(self.ocr_engine_type, self.ocr_lang)
            return

        print("Starting Snip & Translate mode...")
        self.snip_mode_active = True
        self.update_status("Snip mode: Click and drag to select region, Esc to cancel.")

        try:
            # Create a full-screen, semi-transparent overlay window
            self.snip_overlay = tk.Toplevel(self.master)
            self.snip_overlay.attributes("-fullscreen", True)
            self.snip_overlay.attributes("-alpha", 0.3) # Make it see-through
            self.snip_overlay.overrideredirect(True) # No window decorations
            self.snip_overlay.attributes("-topmost", True) # Stay on top
            self.snip_overlay.configure(cursor="crosshair") # Set cursor
            self.snip_overlay.grab_set() # Capture all input events

            # Canvas for drawing the selection rectangle
            self.snip_canvas = tk.Canvas(self.snip_overlay, highlightthickness=0, bg="#888888") # Gray background
            self.snip_canvas.pack(fill=tk.BOTH, expand=True)

            # Bind mouse and keyboard events
            self.snip_canvas.bind("<ButtonPress-1>", self.on_snip_mouse_down)
            self.snip_canvas.bind("<B1-Motion>", self.on_snip_mouse_drag)
            self.snip_canvas.bind("<ButtonRelease-1>", self.on_snip_mouse_up)
            self.snip_overlay.bind("<Escape>", lambda e: self.cancel_snip_mode()) # Cancel on Escape key

            # Reset state variables
            self.snip_start_coords = None
            self.snip_rect_id = None
        except Exception as e:
            print(f"Error creating snip overlay: {e}")
            self.cancel_snip_mode() # Clean up if overlay creation fails

    def on_snip_mouse_down(self, event):
        """Handles mouse button press during snip mode."""
        if not self.snip_mode_active or not self.snip_canvas: return
        # Record starting position (screen coordinates)
        self.snip_start_coords = (event.x_root, event.y_root)
        # Delete previous rectangle if any
        if self.snip_rect_id:
            try: self.snip_canvas.delete(self.snip_rect_id)
            except tk.TclError: pass
        # Create a new rectangle starting and ending at the click point (canvas coordinates)
        self.snip_rect_id = self.snip_canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="red", width=2, tags="snip_rect"
        )

    def on_snip_mouse_drag(self, event):
        """Handles mouse drag during snip mode."""
        if not self.snip_mode_active or not self.snip_start_coords or not self.snip_rect_id or not self.snip_canvas: return

        # Get start coordinates (relative to canvas)
        try:
            # Use the stored screen coordinates for start point
            sx_root, sy_root = self.snip_start_coords
            # Convert start screen coords to current overlay's canvas coords
            start_x_canvas = sx_root - self.snip_overlay.winfo_rootx()
            start_y_canvas = sy_root - self.snip_overlay.winfo_rooty()
        except (tk.TclError, TypeError):
            # Failsafe if overlay gone or coords invalid
            self.snip_rect_id = None
            self.snip_start_coords = None
            return

        # Update rectangle coordinates with current mouse position (canvas coordinates)
        try:
            self.snip_canvas.coords(self.snip_rect_id, start_x_canvas, start_y_canvas, event.x, event.y)
        except tk.TclError:
            # Handle potential errors if canvas/rect is destroyed unexpectedly
            self.snip_rect_id = None
            self.snip_start_coords = None

    def on_snip_mouse_up(self, event):
        """Handles mouse button release during snip mode."""
        if not self.snip_mode_active or not self.snip_start_coords or not self.snip_rect_id or not self.snip_canvas:
            self.cancel_snip_mode() # Should not happen, but cancel defensively
            return

        try:
            # Get final rectangle coordinates (canvas coordinates)
            coords = self.snip_canvas.coords(self.snip_rect_id)
            if len(coords) == 4:
                # Convert canvas coordinates to screen coordinates
                overlay_x = self.snip_overlay.winfo_rootx()
                overlay_y = self.snip_overlay.winfo_rooty()
                x1_screen = int(coords[0]) + overlay_x
                y1_screen = int(coords[1]) + overlay_y
                x2_screen = int(coords[2]) + overlay_x
                y2_screen = int(coords[3]) + overlay_y

                # Ensure correct order (top-left, bottom-right)
                screen_coords_tuple = (min(x1_screen, x2_screen), min(y1_screen, y2_screen),
                                       max(x1_screen, x2_screen), max(y1_screen, y2_screen))

                # Finish snip mode and process the selected region
                self.finish_snip_mode(screen_coords_tuple)
            else:
                print("Invalid coordinates from snip rectangle.")
                self.cancel_snip_mode()
        except tk.TclError:
            print("Error getting snip rectangle coordinates (widget destroyed?).")
            self.cancel_snip_mode()
        except Exception as e:
            print(f"Error during snip mouse up: {e}")
            self.cancel_snip_mode()

    def cancel_snip_mode(self):
        """Cleans up the snip overlay and resets state."""
        if not self.snip_mode_active: return
        print("Cancelling snip mode.")
        if self.snip_overlay and self.snip_overlay.winfo_exists():
            try:
                self.snip_overlay.grab_release() # Release input grab
                self.snip_overlay.destroy()     # Destroy the overlay window
            except tk.TclError: pass # Ignore errors if already destroyed
        # Reset state variables
        self.snip_overlay = None
        self.snip_canvas = None
        self.snip_start_coords = None
        self.snip_rect_id = None
        self.snip_mode_active = False
        self.master.configure(cursor="") # Reset main window cursor
        self.update_status("Snip mode cancelled.")

    def finish_snip_mode(self, screen_coords_tuple):
        """Processes the selected screen region after snip mode ends."""
        x1, y1, x2, y2 = screen_coords_tuple
        width = x2 - x1
        height = y2 - y1
        min_snip_size = 5 # Minimum pixel dimension

        # Validate size
        if width < min_snip_size or height < min_snip_size:
            messagebox.showwarning("Snip Too Small", f"Selected region too small (min {min_snip_size}x{min_snip_size} px).", parent=self.master)
            self.cancel_snip_mode() # Cancel if too small
            return

        # Define the region dictionary for capture function
        monitor_region = {"left": x1, "top": y1, "width": width, "height": height}

        # Clean up the overlay *before* starting processing
        if self.snip_overlay and self.snip_overlay.winfo_exists():
            try:
                self.snip_overlay.grab_release()
                self.snip_overlay.destroy()
            except tk.TclError: pass
        self.snip_overlay = None
        self.snip_canvas = None
        self.snip_start_coords = None
        self.snip_rect_id = None
        self.snip_mode_active = False
        self.master.configure(cursor="") # Reset cursor

        # Update status and start processing in a thread
        self.update_status("Processing snipped region...")
        print(f"Snipped region (Screen Coords): {monitor_region}")
        threading.Thread(target=self._process_snip_thread, args=(monitor_region,), daemon=True).start()

    def _process_snip_thread(self, screen_region):
        """Background thread to capture, OCR, and translate the snipped region."""
        try:
            # 1. Capture the screen region
            img_bgr = capture_screen_region(screen_region)
            if img_bgr is None:
                self.master.after_idle(lambda: self.update_status("Snip Error: Failed to capture region."))
                return

            # 2. Perform OCR (using the currently selected engine and language)
            if not self.ocr_engine_ready:
                self.master.after_idle(lambda: self.update_status(f"Snip Error: OCR ({self.ocr_engine_type}/{self.ocr_lang}) not ready."))
                return

            print(f"[Snip OCR] Running OCR ({self.ocr_engine_type}/{self.ocr_lang})...")
            # Pass engine type and language to the unified extract_text function
            extracted_text = ocr.extract_text(img_bgr, lang=self.ocr_lang, engine_type=self.ocr_engine_type)
            print(f"[Snip OCR] Extracted: '{extracted_text}'")

            # Check for OCR errors indicated by the function
            if extracted_text.startswith("[") and "Error]" in extracted_text:
                self.master.after_idle(lambda: self.update_status(f"Snip: {extracted_text}"))
                self.master.after_idle(lambda: self.display_snip_translation(extracted_text, screen_region))
                return

            if not extracted_text:
                self.master.after_idle(lambda: self.update_status("Snip: No text found in region."))
                self.master.after_idle(lambda: self.display_snip_translation("[No text found]", screen_region))
                return

            # 3. Translate the extracted text
            config = self.translation_tab.get_translation_config() if hasattr(self, "translation_tab") else None
            if not config:
                self.master.after_idle(lambda: self.update_status("Snip Error: Translation config unavailable."))
                self.master.after_idle(lambda: self.display_snip_translation("[Translation Config Error]", screen_region))
                return

            # Use a dictionary for snip translation input (still needed for structure)
            snip_tag_name = "_snip_translate" # Internal use only
            snip_input_dict = {snip_tag_name: extracted_text}

            print("[Snip Translate] Translating...")
            translation_result = translate_text(
                stable_texts_dict=snip_input_dict, # Pass dictionary (will be handled differently inside)
                hwnd=None, # No specific game window for snip cache/context
                preset=config,
                target_language=config["target_language"],
                additional_context=config["additional_context"],
                context_limit=0, # No context history for snips
                skip_cache=True, # Don't cache snips
                skip_history=True, # Don't add snips to history
                user_comment=None, # No user comment for snip
                is_snip=True # Indicate this is a snip translation
            )

            # 4. Process translation result (which should now be plain text for snips)
            final_text = "[Translation Error]"
            if isinstance(translation_result, dict) and "error" in translation_result:
                final_text = f"Error: {translation_result['error']}"
            elif isinstance(translation_result, str):
                final_text = translation_result # Expecting plain string now
            # Remove the old dictionary parsing logic for snips

            print(f"[Snip Translate] Result: '{final_text}'")
            self.master.after_idle(lambda: self.update_status("Snip translation complete."))
            self.master.after_idle(lambda: self.display_snip_translation(final_text, screen_region))

        except Exception as e:
            error_msg = f"Error processing snip: {e}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            self.master.after_idle(lambda: self.update_status(f"Snip Error: {error_msg[:60]}..."))
            self.master.after_idle(lambda: self.display_snip_translation(f"[Error: {error_msg}]", screen_region))

    def display_snip_translation(self, text, region):
        """Creates or updates the floating window for snip results."""
        # Close existing snip window if open
        if self.current_snip_window and self.current_snip_window.winfo_exists():
            try: self.current_snip_window.destroy_window()
            except tk.TclError: pass
        self.current_snip_window = None

        try:
            # Get the specific configuration for the snip window
            snip_config = get_overlay_config_for_roi(SNIP_ROI_NAME)
            snip_config["enabled"] = True # Snip window is always enabled when created

            # Create the closable overlay window
            self.current_snip_window = ClosableFloatingOverlayWindow(
                self.master,
                roi_name=SNIP_ROI_NAME, # Use the special name
                initial_config=snip_config,
                manager_ref=None # Snip window is independent of the manager
            )
            # The window's __init__ calls _update_visibility, which for Closable...
            # ensures it becomes visible. update_text below will handle resizing.

            # --- Position the snip window intelligently (BEFORE resizing) ---
            # Default position: to the right of the snipped region
            pos_x = region["left"] + region["width"] + 10
            pos_y = region["top"]
            # Apply initial position before potential resize
            self.current_snip_window.geometry(f"+{pos_x}+{pos_y}")
            self.current_snip_window.update_idletasks() # Calculate initial size/pos

            # --- Update text and trigger auto-resize ---
            self.current_snip_window.update_text(text) # This now handles resizing

            # --- Re-check screen bounds AFTER resizing ---
            self.current_snip_window.update_idletasks() # Ensure final dimensions are calculated
            win_width = self.current_snip_window.winfo_width()
            win_height = self.current_snip_window.winfo_height()
            # Get potentially updated position
            pos_x = self.current_snip_window.winfo_x()
            pos_y = self.current_snip_window.winfo_y()
            screen_width = self.master.winfo_screenwidth()
            screen_height = self.master.winfo_screenheight()

            # Adjust if it goes off-screen right
            if pos_x + win_width > screen_width:
                pos_x = region["left"] - win_width - 10 # Try left
            # Adjust if it goes off-screen bottom
            if pos_y + win_height > screen_height:
                pos_y = screen_height - win_height - 10 # Move up
            # Ensure it doesn't go off-screen top or left
            pos_x = max(0, pos_x)
            pos_y = max(0, pos_y)

            # Apply the final calculated position
            self.current_snip_window.geometry(f"+{pos_x}+{pos_y}")


        except Exception as e:
            print(f"Error creating snip result window: {e}")
            import traceback
            traceback.print_exc()
            # Clean up partially created window if error occurred
            if self.current_snip_window:
                try: self.current_snip_window.destroy_window()
                except Exception: pass
            self.current_snip_window = None
            messagebox.showerror("Snip Error", f"Could not display snip result:\n{e}", parent=self.master)

    def capture_process(self):
        """The main loop running in a separate thread for capturing and processing."""
        last_frame_time = time.time()
        target_sleep_time = FRAME_DELAY
        print("Capture thread started.")

        while self.capturing:
            loop_start_time = time.time()
            frame_to_display = None

            try:
                # If in snapshot mode, just sleep briefly and continue
                if self.using_snapshot:
                    time.sleep(0.05) # Short sleep to prevent busy-waiting
                    continue

                # Check if the target window is still valid
                if not self.selected_hwnd or not win32gui.IsWindow(self.selected_hwnd):
                    print("Capture target window lost or invalid. Stopping.")
                    self.master.after_idle(self.handle_capture_failure)
                    break # Exit the loop

                # Capture the window content
                frame = capture_window(self.selected_hwnd)
                if frame is None:
                    # Handle capture failure (e.g., window minimized, protected content)
                    print("Warning: capture_window returned None. Retrying...")
                    time.sleep(0.5) # Wait a bit longer before retrying
                    continue

                # Store the latest frame
                self.current_frame = frame
                frame_to_display = frame # Use this frame for display update

                # Process ROIs if OCR is ready and ROIs exist
                if self.rois and self.ocr_engine_ready:
                    self._process_rois(frame) # Pass only frame, engine details are instance vars

                # --- Frame Display Timing ---
                # Update display roughly at the target FPS
                current_time = time.time()
                if current_time - last_frame_time >= target_sleep_time:
                    if frame_to_display is not None:
                        # Send a copy to the main thread for display
                        frame_copy = frame_to_display.copy()
                        self.master.after_idle(lambda f=frame_copy: self._display_frame(f))
                    last_frame_time = current_time

                # --- Loop Delay Calculation ---
                elapsed = time.time() - loop_start_time
                sleep_duration = max(0.001, target_sleep_time - elapsed) # Ensure positive sleep
                time.sleep(sleep_duration)

            except Exception as e:
                print(f"!!! Error in capture loop: {e}")
                import traceback
                traceback.print_exc()
                # Update status bar from main thread
                self.master.after_idle(lambda msg=str(e): self.update_status(f"Capture loop error: {msg[:60]}..."))
                time.sleep(1) # Pause briefly after an error

        print("Capture thread finished or exited.")

    def handle_capture_failure(self):
        """Called from main thread if capture loop detects window loss."""
        if self.capturing: # Only act if we thought we were capturing
            self.update_status("Window lost or uncapturable. Stopping capture.")
            print("Capture target window became invalid.")
            self.stop_capture() # Initiate the stop sequence

    def on_canvas_resize(self, event=None):
        """Handles canvas resize events, debouncing redraw."""
        if self._resize_job:
            self.master.after_cancel(self._resize_job)
        # Schedule the actual redraw after a short delay
        self._resize_job = self.master.after(100, self._perform_resize_redraw)

    def _perform_resize_redraw(self):
        """Redraws the frame on the canvas after resizing."""
        self._resize_job = None # Reset the job ID
        if not self.canvas.winfo_exists(): return # Check if canvas still exists

        # Determine which frame to display (snapshot or live)
        frame = self.snapshot_frame if self.using_snapshot else self.current_frame
        self._display_frame(frame) # Call the display function

    def _display_frame(self, frame):
        """Displays the given frame (NumPy array) on the canvas."""
        if not hasattr(self, "canvas") or not self.canvas.winfo_exists(): return

        # Clear previous content
        self.canvas.delete("display_content")
        self.display_frame_tk = None # Release previous PhotoImage reference

        # Handle case where frame is None (e.g., before capture starts)
        if frame is None:
            try:
                cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
                if cw > 1 and ch > 1: # Ensure canvas has valid dimensions
                    self.canvas.create_text(
                        cw / 2, ch / 2,
                        text="No Image\n(Select Window & Start Capture)",
                        fill="gray50", tags="display_content", justify=tk.CENTER
                    )
            except Exception: pass # Ignore errors during placeholder text creation
            return

        try:
            fh, fw = frame.shape[:2]
            cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()

            # Check for invalid dimensions
            if fw <= 0 or fh <= 0 or cw <= 1 or ch <= 1: return

            # Calculate scaling factor to fit frame within canvas
            scale = min(cw / fw, ch / fh)
            nw, nh = int(fw * scale), int(fh * scale)

            # Check for invalid scaled dimensions
            if nw < 1 or nh < 1: return

            # Store scaling and position info
            self.scale_x, self.scale_y = scale, scale
            self.frame_display_coords = {
                "x": (cw - nw) // 2, "y": (ch - nh) // 2, # Center the image
                "w": nw, "h": nh
            }

            # Resize image using OpenCV (linear interpolation is usually good enough)
            resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
            # Convert BGR (OpenCV) to RGB (PIL)
            img = Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))
            # Convert PIL image to Tkinter PhotoImage
            self.display_frame_tk = ImageTk.PhotoImage(image=img)

            # Display the image on the canvas
            self.canvas.create_image(
                self.frame_display_coords["x"], self.frame_display_coords["y"],
                anchor=tk.NW, image=self.display_frame_tk,
                tags=("display_content", "frame_image") # Add tags for easy deletion/identification
            )

            # Draw ROI rectangles on top
            self._draw_rois()

        except Exception as e:
            print(f"Error displaying frame: {e}")
            # Attempt to display error message on canvas
            try:
                cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
                self.canvas.create_text(cw/2, ch/2, text=f"Display Error:\n{e}", fill="red", tags="display_content")
            except Exception: pass # Ignore errors during error display

    def _process_rois(self, frame):
        """Extracts text from ROIs, applies processing, checks stability, and triggers translation."""
        if frame is None or not self.ocr_engine_ready:
            # print("_process_rois skipped: No frame or OCR not ready.")
            return

        extracted = {}
        stable_changed = False
        new_stable = self.stable_texts.copy()

        for roi in self.rois:
            if roi.name == SNIP_ROI_NAME: continue # Skip the special snip ROI

            roi_img_original = roi.extract_roi(frame)
            if roi_img_original is None:
                extracted[roi.name] = ""
                # Reset history and stability if ROI becomes invalid
                if roi.name in self.text_history: del self.text_history[roi.name]
                if roi.name in new_stable:
                    del new_stable[roi.name]
                    stable_changed = True
                continue

            # Apply color filter first
            roi_img_color_filtered = roi.apply_color_filter(roi_img_original)
            # Apply OCR preprocessing steps
            roi_img_for_ocr = roi.apply_ocr_preprocessing(roi_img_color_filtered)

            if roi_img_for_ocr is None or roi_img_for_ocr.size == 0:
                extracted[roi.name] = ""
                # Reset history and stability if processing fails
                if roi.name in self.text_history: del self.text_history[roi.name]
                if roi.name in new_stable:
                    del new_stable[roi.name]
                    stable_changed = True
                continue

            try:
                # Call the unified OCR function from utils.ocr with the fully processed image
                text = ocr.extract_text(roi_img_for_ocr, lang=self.ocr_lang, engine_type=self.ocr_engine_type)
                extracted[roi.name] = text

                # --- Stability Check ---
                history = self.text_history.get(roi.name, {"text": "", "count": 0})
                if text == history["text"]:
                    history["count"] += 1
                else:
                    history = {"text": text, "count": 1}
                self.text_history[roi.name] = history

                is_now_stable = history["count"] >= self.stable_threshold
                was_stable = roi.name in self.stable_texts
                current_stable_text = self.stable_texts.get(roi.name)

                if is_now_stable:
                    # Mark as stable if threshold met and text is different from previous stable text
                    if not was_stable or current_stable_text != text:
                        new_stable[roi.name] = text
                        stable_changed = True
                elif was_stable:
                    # If it was stable but no longer meets threshold (text changed), remove it
                    if roi.name in new_stable:
                        del new_stable[roi.name]
                        stable_changed = True
                # --- End Stability Check ---

            except Exception as e:
                # Handle errors during OCR for a specific ROI
                print(f"!!! OCR Error for ROI {roi.name}: {e}")
                extracted[roi.name] = "[OCR Error]"
                self.text_history[roi.name] = {"text": "[OCR Error]", "count": 1}
                if roi.name in new_stable:
                    del new_stable[roi.name]
                    stable_changed = True

        # --- Update UI and Trigger Translation (Scheduled on Main Thread) ---
        if hasattr(self, "text_tab") and self.text_tab.frame.winfo_exists():
            # Update the "Live Text" tab
            self.master.after_idle(lambda et=extracted.copy(): self.text_tab.update_text(et))

        if stable_changed:
            self.stable_texts = new_stable
            if hasattr(self, "stable_text_tab") and self.stable_text_tab.frame.winfo_exists():
                # Update the "Stable Text" tab
                self.master.after_idle(lambda st=self.stable_texts.copy(): self.stable_text_tab.update_text(st))

            # --- Auto-Translate Trigger Logic ---
            if hasattr(self, "translation_tab") and self.translation_tab.frame.winfo_exists() and self.translation_tab.is_auto_translate_enabled():
                # Get all user-defined ROI names (excluding the snip one)
                user_roi_names = {roi.name for roi in self.rois if roi.name != SNIP_ROI_NAME}

                # Check if user ROIs exist AND if all of them are keys in the *new* stable_texts
                # Also ensure stable_texts is not empty overall
                all_rois_are_stable = bool(user_roi_names) and user_roi_names.issubset(self.stable_texts.keys()) and bool(self.stable_texts)

                if all_rois_are_stable:
                    # All conditions met: Trigger translation
                    print("[Auto-Translate] All ROIs stable, triggering translation.")
                    # Use after_idle to ensure it runs on the main thread
                    self.master.after_idle(self.translation_tab.perform_translation)
                else:
                    # Not all ROIs are stable, or no user ROIs exist, or stable_texts became empty.
                    # Check if the reason is that stable_texts became empty.
                    if not self.stable_texts: # If the stable text dictionary is now empty
                        print("[Auto-Translate] Stable text cleared, clearing overlays.")
                        if hasattr(self, "overlay_manager"):
                            self.master.after_idle(self.overlay_manager.clear_all_overlays)
                        # Also clear the translation preview
                        if hasattr(self, "translation_tab"):
                            self.master.after_idle(lambda: self.translation_tab.update_translation_results({}, "[Waiting for stable text...]"))
                    # else:
                    # Some ROIs might be stable, but not all. Do nothing.
                    # print("[Auto-Translate] Waiting for all ROIs to stabilize.") # Optional log
            # --- End of Auto-Translate Logic ---


    def _draw_rois(self):
        """Draws ROI rectangles and labels on the canvas."""
        if not hasattr(self, "canvas") or not self.canvas.winfo_exists() or self.frame_display_coords["w"] <= 0:
            return

        ox, oy = self.frame_display_coords["x"], self.frame_display_coords["y"]
        # Clear only ROI drawings, not the frame image
        self.canvas.delete("roi_drawing")

        for i, roi in enumerate(self.rois):
            if roi.name == SNIP_ROI_NAME: continue # Don't draw the snip ROI

            try:
                # Calculate display coordinates based on scaling and offset
                dx1 = int(roi.x1 * self.scale_x) + ox
                dy1 = int(roi.y1 * self.scale_y) + oy
                dx2 = int(roi.x2 * self.scale_x) + ox
                dy2 = int(roi.y2 * self.scale_y) + oy

                # Draw rectangle
                self.canvas.create_rectangle(
                    dx1, dy1, dx2, dy2,
                    outline="lime", width=1, # Lime green outline
                    tags=("display_content", "roi_drawing", f"roi_{i}") # Add tags
                )
                # Draw label
                self.canvas.create_text(
                    dx1 + 3, dy1 + 1, # Position slightly inside top-left corner
                    text=roi.name, fill="lime", anchor=tk.NW,
                    font=("TkDefaultFont", 8), # Small font
                    tags=("display_content", "roi_drawing", f"roi_label_{i}")
                )
            except Exception as e:
                print(f"Error drawing ROI {roi.name}: {e}")

    # --- Mouse Events for ROI Definition ---

    def on_mouse_down(self, event):
        """Handles mouse button press on the canvas (for ROI definition)."""
        # Only active during ROI definition AND when using a snapshot
        if not self.roi_selection_active or not self.using_snapshot: return

        # Check if click is within the displayed image bounds
        img_x, img_y = self.frame_display_coords["x"], self.frame_display_coords["y"]
        img_w, img_h = self.frame_display_coords["w"], self.frame_display_coords["h"]
        if not (img_x <= event.x < img_x + img_w and img_y <= event.y < img_y + img_h):
            # Click outside image, cancel drawing
            self.roi_start_coords = None
            if self.roi_draw_rect_id:
                try: self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError: pass
            self.roi_draw_rect_id = None
            return

        # Record start coordinates (canvas coords)
        self.roi_start_coords = (event.x, event.y)
        # Delete previous drawing rectangle if it exists
        if self.roi_draw_rect_id:
            try: self.canvas.delete(self.roi_draw_rect_id)
            except tk.TclError: pass
        # Create new rectangle starting and ending at the click point
        self.roi_draw_rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="red", width=2, tags="roi_drawing" # Red outline for drawing
        )

    def on_mouse_drag(self, event):
        """Handles mouse drag on the canvas (for ROI definition)."""
        if not self.roi_selection_active or not self.roi_start_coords or not self.roi_draw_rect_id: return

        sx, sy = self.roi_start_coords
        # Clamp current coordinates to be within the image bounds on canvas
        img_x, img_y = self.frame_display_coords["x"], self.frame_display_coords["y"]
        img_w, img_h = self.frame_display_coords["w"], self.frame_display_coords["h"]
        cx = max(img_x, min(event.x, img_x + img_w))
        cy = max(img_y, min(event.y, img_y + img_h))

        try:
            # Also clamp start coordinates just in case they were slightly off
            clamped_sx = max(img_x, min(sx, img_x + img_w))
            clamped_sy = max(img_y, min(sy, img_y + img_h))
            # Update the drawing rectangle coordinates
            self.canvas.coords(self.roi_draw_rect_id, clamped_sx, clamped_sy, cx, cy)
        except tk.TclError:
            # Handle error if canvas/rectangle destroyed unexpectedly
            self.roi_draw_rect_id = None
            self.roi_start_coords = None

    def on_mouse_up(self, event):
        """Handles mouse button release on the canvas (completes ROI definition)."""
        # Check if ROI definition was active and started correctly
        if not self.roi_selection_active or not self.roi_start_coords or not self.roi_draw_rect_id:
            # Clean up potential dangling rectangle if drag never happened
            if self.roi_draw_rect_id:
                try: self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError: pass
            self.roi_draw_rect_id = None
            self.roi_start_coords = None
            # If selection was active but failed, deactivate it
            if self.roi_selection_active:
                self.roi_selection_active = False
                if hasattr(self, "roi_tab"): self.roi_tab.on_roi_selection_toggled(False)
                if self.using_snapshot: self.return_to_live() # Exit snapshot if active
            return

        # Get final coordinates of the drawing rectangle
        try: coords = self.canvas.coords(self.roi_draw_rect_id)
        except tk.TclError: coords = None # Handle error if widget destroyed

        # Clean up drawing rectangle and reset state *before* processing ROI
        if self.roi_draw_rect_id:
            try: self.canvas.delete(self.roi_draw_rect_id)
            except tk.TclError: pass
        self.roi_draw_rect_id = None
        self.roi_start_coords = None
        self.roi_selection_active = False # Deactivate selection mode
        if hasattr(self, "roi_tab"): self.roi_tab.on_roi_selection_toggled(False)

        # Validate coordinates and size
        if coords is None or len(coords) != 4:
            print("ROI definition failed (invalid coords).")
            if self.using_snapshot: self.return_to_live() # Exit snapshot
            return

        x1d, y1d, x2d, y2d = map(int, coords)
        min_size = 5 # Minimum size in pixels on the canvas
        if abs(x2d - x1d) < min_size or abs(y2d - y1d) < min_size:
            messagebox.showwarning("ROI Too Small", f"Defined region too small (min {min_size}x{min_size} px required).", parent=self.master)
            if self.using_snapshot: self.return_to_live() # Exit snapshot
            return

        # --- Get ROI Name ---
        roi_name = self.roi_tab.roi_name_entry.get().strip()
        overwrite_name = None
        existing_names = {r.name for r in self.rois if r.name != SNIP_ROI_NAME}

        if not roi_name: # Generate default name if empty
            i = 1
            roi_name = f"roi_{i}"
            while roi_name in existing_names: i += 1; roi_name = f"roi_{i}"
        elif roi_name in existing_names: # Check for overwrite
            if not messagebox.askyesno("ROI Exists", f"An ROI named '{roi_name}' already exists. Overwrite it?", parent=self.master):
                if self.using_snapshot: self.return_to_live() # Exit snapshot if user cancels
                return
            overwrite_name = roi_name
        elif roi_name == SNIP_ROI_NAME: # Check for reserved name
            messagebox.showerror("Invalid Name", f"Cannot use the reserved name '{SNIP_ROI_NAME}'. Please choose another.", parent=self.master)
            if self.using_snapshot: self.return_to_live() # Exit snapshot
            return

        # --- Convert Canvas Coords to Original Frame Coords ---
        ox, oy = self.frame_display_coords["x"], self.frame_display_coords["y"]
        # Coords relative to the displayed image's top-left corner
        rx1, ry1 = min(x1d, x2d) - ox, min(y1d, y2d) - oy
        rx2, ry2 = max(x1d, x2d) - ox, max(y1d, y2d) - oy

        # Check for valid scaling factor
        if self.scale_x <= 0 or self.scale_y <= 0:
            print("Error: Invalid scaling factor during ROI creation.")
            if self.using_snapshot: self.return_to_live() # Exit snapshot
            return

        # Convert relative display coords back to original frame coords
        orig_x1, orig_y1 = int(rx1 / self.scale_x), int(ry1 / self.scale_y)
        orig_x2, orig_y2 = int(rx2 / self.scale_x), int(ry2 / self.scale_y)

        # Final size check in original coordinates
        if abs(orig_x2 - orig_x1) < 1 or abs(orig_y2 - orig_y1) < 1:
            messagebox.showwarning("ROI Too Small", "Calculated ROI size is too small in original frame.", parent=self.master)
            if self.using_snapshot: self.return_to_live() # Exit snapshot
            return

        # --- Create or Update ROI Object ---
        # Create new ROI with default processing settings
        new_roi = ROI(roi_name, orig_x1, orig_y1, orig_x2, orig_y2)

        if overwrite_name:
            found = False
            for i, r in enumerate(self.rois):
                if r.name == overwrite_name:
                    # Preserve existing color filter AND preprocessing settings when overwriting geometry
                    new_roi.color_filter_enabled = r.color_filter_enabled
                    new_roi.target_color = r.target_color
                    new_roi.replacement_color = r.replacement_color
                    new_roi.color_threshold = r.color_threshold
                    new_roi.preprocessing = r.preprocessing # Copy the whole dict
                    self.rois[i] = new_roi
                    found = True
                    break
            if not found: # Should not happen if overwrite_name was set
                print(f"Warning: Tried to overwrite '{overwrite_name}' but not found.")
                self.rois.append(new_roi) # Add as new if somehow not found
        else:
            # Add the new ROI to the list
            self.rois.append(new_roi)

        print(f"Created/Updated ROI: {new_roi.to_dict()}")

        # --- Update UI and State ---
        if hasattr(self, "roi_tab"): self.roi_tab.update_roi_list() # Update listbox
        self._draw_rois() # Redraw ROIs on canvas
        action = "created" if not overwrite_name else "updated"
        self.update_status(f"ROI '{roi_name}' {action}. Remember to save ROI settings.")

        # Suggest next ROI name in the entry box
        if hasattr(self, "roi_tab"):
            existing_names_now = {r.name for r in self.rois if r.name != SNIP_ROI_NAME}
            next_name = "dialogue" if "dialogue" not in existing_names_now else ""
            if not next_name: # Generate roi_N if dialogue exists
                i = 1
                next_name = f"roi_{i}"
                while next_name in existing_names_now: i += 1; next_name = f"roi_{i}"
            self.roi_tab.roi_name_entry.delete(0, tk.END)
            self.roi_tab.roi_name_entry.insert(0, next_name)

        # Create or update the corresponding overlay window in the manager
        # The manager will handle visibility based on capture state
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.create_overlay_for_roi(new_roi)

        # Return to live view if we were in snapshot mode
        if self.using_snapshot: self.return_to_live()

    # --- Floating Controls and Closing ---

    def show_floating_controls(self):
        """Shows or brings the floating controls window to the front."""
        # Only show if capture is active
        if not self.capturing:
            # If trying to show via menu when not capturing, maybe give feedback?
            # print("Cannot show floating controls: Capture not active.")
            # Or just silently do nothing.
            return

        try:
            if self.floating_controls is None or not self.floating_controls.winfo_exists():
                self.floating_controls = FloatingControls(self.master, self)
            else:
                self.floating_controls.deiconify() # Ensure it's not minimized/withdrawn
                self.floating_controls.lift()      # Bring to top
                self.floating_controls.update_button_states() # Sync button states
        except Exception as e:
            print(f"Error showing floating controls: {e}")
            self.update_status("Error showing controls.")

    def hide_floating_controls(self):
        """Hides the floating controls window."""
        if self.floating_controls and self.floating_controls.winfo_exists():
            try:
                self.floating_controls.withdraw()
            except tk.TclError:
                pass # Ignore if already destroyed

    def on_close(self):
        """Handles the application closing sequence."""
        print("Close requested...")
        # Cancel any active modes
        if self.snip_mode_active: self.cancel_snip_mode()
        if self.roi_selection_active: self.toggle_roi_selection()

        # Close the snip result window if it's open
        if self.current_snip_window and self.current_snip_window.winfo_exists():
            try: self.current_snip_window.destroy_window()
            except Exception: pass
            self.current_snip_window = None

        # Stop capture if running and wait for it to finish
        if self.capturing:
            self.update_status("Stopping capture before closing...")
            self.stop_capture()
            # Schedule check to finalize close after capture stops
            self.master.after(500, self.check_capture_stopped_and_close)
        else:
            # If not capturing, proceed to final close steps directly
            self._finalize_close()

    def check_capture_stopped_and_close(self):
        """Checks if capture thread is stopped, then finalizes close."""
        # Check if capture flag is off AND thread is gone or dead
        if not self.capturing and (self.capture_thread is None or not self.capture_thread.is_alive()):
            self._finalize_close()
        else:
            # Still waiting for capture to stop
            print("Waiting for capture thread to stop...")
            self.master.after(500, self.check_capture_stopped_and_close)

    def _finalize_close(self):
        """Performs final cleanup before exiting."""
        print("Finalizing close...")
        self.capturing = False # Ensure flag is false

        # Destroy all overlay windows managed by the manager
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.destroy_all_overlays()

        # Save floating controls position and destroy the window
        if self.floating_controls and self.floating_controls.winfo_exists():
            try:
                # Only save position if the window is visible (not withdrawn)
                if self.floating_controls.state() == "normal":
                    geo = self.floating_controls.geometry()
                    parts = geo.split('+')
                    if len(parts) == 3: # Format like WxH+X+Y
                        x_str, y_str = parts[1], parts[2]
                        # Basic check if coordinates look valid
                        if x_str.isdigit() and y_str.isdigit():
                            set_setting("floating_controls_pos", f"{x_str},{y_str}")
                        else: print(f"Warn: Invalid floating controls coordinates in geometry: {geo}")
                    else: print(f"Warn: Could not parse floating controls geometry: {geo}")
            except Exception as e: print(f"Error saving floating controls position: {e}")
            # Destroy the window regardless of saving position
            try: self.floating_controls.destroy()
            except tk.TclError: pass # Ignore error if already destroyed

        # Ensure snip result window is destroyed (double check)
        if self.current_snip_window and self.current_snip_window.winfo_exists():
            try: self.current_snip_window.destroy_window()
            except Exception: pass

        print("Exiting application.")
        try:
            # Standard Tkinter exit sequence
            self.master.quit()
            self.master.destroy()
        except tk.TclError: pass # Ignore errors if widgets already gone
        except Exception as e: print(f"Error during final window destruction: {e}")

# --- END OF FILE app.py ---