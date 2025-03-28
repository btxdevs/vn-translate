# --- START OF FILE app.py ---

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import cv2
from PIL import Image, ImageTk
import os
import win32gui
from paddleocr import PaddleOCR

# Utility Imports
from utils.capture import get_window_title, capture_window, capture_screen_region
from utils.config import load_rois, ROI_CONFIGS_DIR, _get_game_hash # Use config functions
from utils.settings import load_settings, set_setting, get_setting, get_overlay_config_for_roi
from utils.roi import ROI
from utils.translation import CACHE_DIR, CONTEXT_DIR, _load_context, translate_text

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
OCR_ENGINE_LOCK = threading.Lock()


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

        # OCR Engine
        self.ocr = None
        self.ocr_lang = get_setting("ocr_language", "jpn")
        self._resize_job = None # For debouncing canvas resize events

        # Setup UI components
        self._setup_ui()
        self.overlay_manager = OverlayManager(self.master, self)
        self.floating_controls = None

        # Initialize OCR engine and show controls
        initial_ocr_lang = self.ocr_lang or "jpn"
        self.update_ocr_engine(initial_ocr_lang, initial_load=True)
        self.show_floating_controls() # Show floating controls on startup

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
                if hasattr(self, "overlay_manager"): self.overlay_manager.rebuild_overlays()
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
            if hasattr(self, "overlay_manager"): self.overlay_manager.rebuild_overlays()
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
            if hasattr(self, "overlay_manager"): self.overlay_manager.rebuild_overlays()
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

        # Clear any text currently shown in overlays
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.clear_all_overlays()

    def update_ocr_engine(self, lang_code, initial_load=False):
        """Initializes or updates the OCR engine in a separate thread."""
        def init_engine():
            global OCR_ENGINE_LOCK
            # Mapping for PaddleOCR language codes
            lang_map = {
                "jpn": "japan", "jpn_vert": "japan", "eng": "en",
                "chi_sim": "ch", "chi_tra": "ch", "kor": "ko",
            }
            ocr_lang_paddle = lang_map.get(lang_code, "en") # Default to English

            # Check if engine exists and language matches
            with OCR_ENGINE_LOCK:
                current_paddle_lang = getattr(self.ocr, "lang", None) if self.ocr else None
                if current_paddle_lang == ocr_lang_paddle and self.ocr is not None:
                    if not initial_load: print(f"OCR engine already initialized with {lang_code}.")
                    self.master.after_idle(lambda: self.update_status(f"OCR Ready ({lang_code})."))
                    return # No change needed

            # Update status before potentially long initialization
            status_msg = f"Initializing OCR ({lang_code})..."
            if not initial_load: print(status_msg)
            self.master.after_idle(lambda: self.update_status(status_msg))

            try:
                # Initialize PaddleOCR (this can take time)
                new_ocr_engine = PaddleOCR(use_angle_cls=True, lang=ocr_lang_paddle, show_log=False)
                # Safely update the instance variable
                with OCR_ENGINE_LOCK:
                    self.ocr = new_ocr_engine
                    self.ocr_lang = lang_code # Store the requested code (e.g., 'jpn_vert')
                print(f"OCR engine ready for {lang_code}.")
                self.master.after_idle(lambda: self.update_status(f"OCR Ready ({lang_code})."))
            except Exception as e:
                print(f"!!! Error initializing PaddleOCR for lang {lang_code}: {e}")
                import traceback
                traceback.print_exc()
                self.master.after_idle(lambda: self.update_status(f"OCR Error ({lang_code}): Check console"))
                # Ensure ocr is None on failure
                with OCR_ENGINE_LOCK:
                    self.ocr = None

        # Start initialization in a background thread to avoid freezing the UI
        threading.Thread(target=init_engine, daemon=True).start()

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
            self.load_rois_for_hwnd(self.selected_hwnd)
            # If still no ROIs after loading, maybe warn? Depends on desired behavior.
            # if not self.rois:
            #    messagebox.showinfo("Info", "No ROIs defined for this game. Capture started, but no text will be extracted.", parent=self.master)

        # Check if OCR engine is ready
        with OCR_ENGINE_LOCK: ocr_ready = bool(self.ocr)
        if not ocr_ready:
            current_lang = self.ocr_lang or "jpn"
            self.update_ocr_engine(current_lang) # Trigger initialization if not ready
            messagebox.showinfo("OCR Not Ready", "OCR is initializing... Capture will start, but text extraction may be delayed.", parent=self.master)
            # Allow capture to start anyway, OCR will be used when ready

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

        # Ensure overlays are ready/rebuilt for the current ROIs
        if hasattr(self, "overlay_manager"): self.overlay_manager.rebuild_overlays()

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
            # Hide overlays
            if hasattr(self, "overlay_manager"):
                self.overlay_manager.hide_all_overlays()
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
        with OCR_ENGINE_LOCK:
            if not self.ocr:
                messagebox.showwarning("OCR Not Ready", "OCR engine not initialized. Cannot use Snip & Translate.", parent=self.master)
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
            start_x_canvas, start_y_canvas = self.snip_canvas.coords(self.snip_rect_id)[:2]
        except (tk.TclError, IndexError):
            # Failsafe if rect_id is somehow invalid
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

            # 2. Perform OCR
            with OCR_ENGINE_LOCK: ocr_engine_instance = self.ocr
            if not ocr_engine_instance:
                self.master.after_idle(lambda: self.update_status("Snip Error: OCR engine not ready."))
                return

            print("[Snip OCR] Running OCR...")
            # Apply color filtering if configured for the special SNIP_ROI_NAME
            # (We need a way to configure this, maybe via OverlayTab?)
            # For now, assume no filtering for snip.
            # If filtering was desired:
            # snip_roi_config = get_overlay_config_for_roi(SNIP_ROI_NAME) # This gets overlay config... need ROI config
            # temp_roi = ROI(SNIP_ROI_NAME, 0,0,1,1) # Dummy ROI to hold filter settings
            # temp_roi.color_filter_enabled = get_setting(...) # Need a way to get snip filter settings
            # temp_roi.target_color = ...
            # temp_roi.color_threshold = ...
            # img_to_ocr = temp_roi.apply_color_filter(img_bgr)

            img_to_ocr = img_bgr # Use original captured image for now

            ocr_result_raw = ocr_engine_instance.ocr(img_to_ocr, cls=True)

            # Extract text from OCR result
            text_lines = []
            # Handle potential variations in PaddleOCR output format
            if ocr_result_raw and isinstance(ocr_result_raw, list) and len(ocr_result_raw) > 0:
                # Sometimes result is [[line1], [line2]], sometimes [[[box],[text,conf]],...]
                current_result_set = ocr_result_raw[0] if isinstance(ocr_result_raw[0], list) else ocr_result_raw
                if current_result_set:
                    for item in current_result_set:
                        text_info = None
                        # Check typical formats: [[box], [text, conf]] or ([text, conf])
                        if isinstance(item, list) and len(item) >= 2 and isinstance(item[1], (list, tuple)):
                            text_info = item[1]
                        elif isinstance(item, tuple) and len(item) >= 2: # Direct text/conf tuple? Less common.
                            text_info = item
                        # Extract text if found
                        if isinstance(text_info, (tuple, list)) and len(text_info) >= 1 and text_info[0]:
                            text_lines.append(str(text_info[0]))

            extracted_text = " ".join(text_lines).strip()
            print(f"[Snip OCR] Extracted: '{extracted_text}'")

            if not extracted_text:
                self.master.after_idle(lambda: self.update_status("Snip: No text found in region."))
                # Show "No text found" in the snip result window
                self.master.after_idle(lambda: self.display_snip_translation("[No text found]", screen_region))
                return

            # 3. Translate the extracted text
            # Get translation config (API key, model, etc.) from the TranslationTab
            config = self.translation_tab.get_translation_config() if hasattr(self, "translation_tab") else None
            if not config:
                self.master.after_idle(lambda: self.update_status("Snip Error: Translation config unavailable."))
                # Display error in snip window
                self.master.after_idle(lambda: self.display_snip_translation("[Translation Config Error]", screen_region))
                return

            # Format input for translation function (using a consistent tag)
            # Use a unique name unlikely to clash with user ROIs
            snip_tag_name = "_snip_translate"
            aggregated_input_snip = f"[{snip_tag_name}]: {extracted_text}"

            print("[Snip Translate] Translating...")
            # Call translation function: skip cache and history for snips
            translation_result = translate_text(
                aggregated_input_text=aggregated_input_snip,
                hwnd=None, # No specific game window for snip
                preset=config,
                target_language=config["target_language"],
                additional_context=config["additional_context"], # Use global/game context if needed?
                context_limit=0, # Don't use history for snip
                skip_cache=True, # Don't cache snip results
                skip_history=True, # Don't add snip to history
            )

            # 4. Process translation result
            final_text = "[Translation Error]" # Default on failure
            if isinstance(translation_result, dict):
                if "error" in translation_result:
                    final_text = f"Error: {translation_result['error']}"
                # Check for the specific tag we used
                elif snip_tag_name in translation_result:
                    final_text = translation_result[snip_tag_name]
                # Fallback if tag mismatch but only one result
                elif len(translation_result) == 1:
                    final_text = next(iter(translation_result.values()), "[Parsing Failed]")

            print(f"[Snip Translate] Result: '{final_text}'")
            self.master.after_idle(lambda: self.update_status("Snip translation complete."))
            # Display the final text in the snip result window
            self.master.after_idle(lambda: self.display_snip_translation(final_text, screen_region))

        except Exception as e:
            # Catch-all for errors during the thread
            error_msg = f"Error processing snip: {e}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            self.master.after_idle(lambda: self.update_status(f"Snip Error: {error_msg[:60]}..."))
            # Display error in snip window
            self.master.after_idle(lambda: self.display_snip_translation(f"[Error: {error_msg}]", screen_region))

    def display_snip_translation(self, text, region):
        """Creates or updates the floating window for snip results."""
        # Close previous snip window if it exists
        if self.current_snip_window and self.current_snip_window.winfo_exists():
            try: self.current_snip_window.destroy_window()
            except tk.TclError: pass
        self.current_snip_window = None

        try:
            # Get appearance settings for the special snip window
            # These are configured via the OverlayTab using the SNIP_ROI_NAME
            snip_config = get_overlay_config_for_roi(SNIP_ROI_NAME)
            snip_config["enabled"] = True # Ensure it's treated as enabled

            # Create the closable floating window instance
            self.current_snip_window = ClosableFloatingOverlayWindow(
                self.master,
                roi_name=SNIP_ROI_NAME, # Use the special name
                initial_config=snip_config,
                manager_ref=None # Snip window is independent of the main overlay manager
            )

            # Calculate position (try bottom-right of snip region, adjust if off-screen)
            pos_x = region["left"] + region["width"] + 10
            pos_y = region["top"]
            self.current_snip_window.update_idletasks() # Ensure window size is calculated
            win_width = self.current_snip_window.winfo_width()
            win_height = self.current_snip_window.winfo_height()
            screen_width = self.master.winfo_screenwidth()
            screen_height = self.master.winfo_screenheight()

            # Adjust if going off right edge
            if pos_x + win_width > screen_width:
                pos_x = region["left"] - win_width - 10
            # Adjust if going off bottom edge
            if pos_y + win_height > screen_height:
                pos_y = screen_height - win_height - 10
            # Ensure not off top or left edge
            pos_x = max(0, pos_x)
            pos_y = max(0, pos_y)

            # Set geometry and update text
            self.current_snip_window.geometry(f"+{pos_x}+{pos_y}")
            # update_text handles making the window visible
            self.current_snip_window.update_text(text, global_overlays_enabled=True)

        except Exception as e:
            print(f"Error creating snip result window: {e}")
            import traceback
            traceback.print_exc()
            # Clean up if window creation failed partially
            if self.current_snip_window:
                try: self.current_snip_window.destroy_window()
                except Exception: pass
            self.current_snip_window = None
            messagebox.showerror("Snip Error", f"Could not display snip result:\n{e}", parent=self.master)

    def capture_process(self):
        """The main loop running in a separate thread for capturing and processing."""
        last_frame_time = time.time()
        target_sleep_time = FRAME_DELAY # Calculated from FPS
        print("Capture thread started.")

        while self.capturing:
            loop_start_time = time.time()
            frame_to_display = None # Frame to be shown on canvas

            try:
                # If in snapshot mode, just sleep briefly
                if self.using_snapshot:
                    time.sleep(0.05)
                    continue

                # Check if the target window is still valid
                if not self.selected_hwnd or not win32gui.IsWindow(self.selected_hwnd):
                    print("Capture target window lost or invalid. Stopping.")
                    # Schedule UI update and stop action on main thread
                    self.master.after_idle(self.handle_capture_failure)
                    break # Exit the loop

                # Capture the window content
                frame = capture_window(self.selected_hwnd)
                if frame is None:
                    # Capture failed (e.g., window minimized, protected content)
                    print("Warning: capture_window returned None. Retrying...")
                    time.sleep(0.5) # Wait before retrying
                    continue

                # Store the latest valid frame
                self.current_frame = frame
                frame_to_display = frame # Use this frame for display update

                # Process ROIs if OCR engine is ready and ROIs are defined
                with OCR_ENGINE_LOCK: ocr_engine_instance = self.ocr
                if self.rois and ocr_engine_instance:
                    # Process ROIs (OCR, stability check, translation trigger)
                    self._process_rois(frame, ocr_engine_instance)

                # Update the preview canvas periodically
                current_time = time.time()
                # Check if enough time has passed since last display update
                if current_time - last_frame_time >= target_sleep_time:
                    if frame_to_display is not None:
                        # Send a copy to the main thread for display
                        frame_copy = frame_to_display.copy()
                        self.master.after_idle(lambda f=frame_copy: self._display_frame(f))
                    last_frame_time = current_time

                # Calculate sleep duration to maintain target FPS
                elapsed = time.time() - loop_start_time
                sleep_duration = max(0.001, target_sleep_time - elapsed)
                time.sleep(sleep_duration)

            except Exception as e:
                # Catch unexpected errors in the loop
                print(f"!!! Error in capture loop: {e}")
                import traceback
                traceback.print_exc()
                # Update status bar on main thread
                self.master.after_idle(lambda msg=str(e): self.update_status(f"Capture loop error: {msg[:60]}..."))
                time.sleep(1) # Pause briefly after an error

        print("Capture thread finished or exited.")

    def handle_capture_failure(self):
        """Called from main thread if capture loop detects window loss."""
        if self.capturing: # Check if stop hasn't already been initiated
            self.update_status("Window lost or uncapturable. Stopping capture.")
            print("Capture target window became invalid.")
            self.stop_capture() # Initiate the stop process

    def on_canvas_resize(self, event=None):
        """Handles canvas resize events, debouncing redraw."""
        # Cancel previous resize job if it exists
        if self._resize_job:
            self.master.after_cancel(self._resize_job)
        # Schedule redraw after a short delay to avoid rapid updates
        self._resize_job = self.master.after(100, self._perform_resize_redraw)

    def _perform_resize_redraw(self):
        """Redraws the frame on the canvas after resizing."""
        self._resize_job = None # Clear the job ID
        if not self.canvas.winfo_exists(): return # Check if canvas still exists

        # Determine which frame to display (snapshot or live)
        frame = self.snapshot_frame if self.using_snapshot else self.current_frame
        self._display_frame(frame) # Call the display function

    def _display_frame(self, frame):
        """Displays the given frame (NumPy array) on the canvas."""
        if not hasattr(self, "canvas") or not self.canvas.winfo_exists(): return

        # Clear previous content
        self.canvas.delete("display_content")
        self.display_frame_tk = None # Release reference to previous PhotoImage

        if frame is None:
            # Display placeholder text if no frame is available
            try:
                cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
                if cw > 1 and ch > 1: # Ensure canvas has size
                    self.canvas.create_text(
                        cw / 2, ch / 2,
                        text="No Image\n(Select Window & Start Capture)",
                        fill="gray50", tags="display_content", justify=tk.CENTER
                    )
            except Exception: pass # Ignore errors during placeholder drawing
            return

        try:
            # Get frame and canvas dimensions
            fh, fw = frame.shape[:2]
            cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()

            # Check for invalid dimensions
            if fw <= 0 or fh <= 0 or cw <= 1 or ch <= 1: return

            # Calculate scaling factor to fit frame within canvas while preserving aspect ratio
            scale = min(cw / fw, ch / fh)
            nw, nh = int(fw * scale), int(fh * scale) # New width and height

            # Ensure new dimensions are valid
            if nw < 1 or nh < 1: return

            # Store scaling factor and display coordinates
            self.scale_x, self.scale_y = scale, scale
            self.frame_display_coords = {
                "x": (cw - nw) // 2, "y": (ch - nh) // 2, # Centering offset
                "w": nw, "h": nh
            }

            # Resize the frame
            resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
            # Convert from BGR (OpenCV) to RGB (PIL/Tkinter)
            img = Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))
            # Create PhotoImage object
            self.display_frame_tk = ImageTk.PhotoImage(image=img)

            # Draw the image on the canvas
            self.canvas.create_image(
                self.frame_display_coords["x"], self.frame_display_coords["y"],
                anchor=tk.NW, image=self.display_frame_tk,
                tags=("display_content", "frame_image") # Add tags for easy deletion
            )

            # Draw ROI rectangles on top of the image
            self._draw_rois()

        except Exception as e:
            print(f"Error displaying frame: {e}")
            # Optionally display an error message on the canvas
            try:
                cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
                self.canvas.create_text(cw/2, ch/2, text=f"Display Error:\n{e}", fill="red", tags="display_content")
            except: pass

    def _process_rois(self, frame, ocr_engine):
        """Extracts text from ROIs, checks stability, and triggers translation."""
        if frame is None or ocr_engine is None: return

        extracted = {} # Store current OCR results for Live Text tab
        stable_changed = False # Flag if stable text needs update/translation
        new_stable = self.stable_texts.copy() # Work on a copy

        for roi in self.rois:
            if roi.name == SNIP_ROI_NAME: continue # Skip the special snip name

            roi_img_original = roi.extract_roi(frame)

            # Apply color filter if enabled for this ROI
            roi_img_processed = roi.apply_color_filter(roi_img_original)

            # Check if ROI extraction or filtering failed
            if roi_img_processed is None or roi_img_processed.size == 0:
                extracted[roi.name] = "" # No text if ROI is invalid/empty
                # Clear stability tracking if ROI becomes invalid
                if roi.name in self.text_history: del self.text_history[roi.name]
                if roi.name in new_stable:
                    del new_stable[roi.name]
                    stable_changed = True
                continue

            # Perform OCR on the (potentially filtered) ROI image
            try:
                ocr_result_raw = ocr_engine.ocr(roi_img_processed, cls=True)

                # Extract text lines from OCR result
                text_lines = []
                if ocr_result_raw and isinstance(ocr_result_raw, list) and len(ocr_result_raw) > 0:
                    current_result_set = ocr_result_raw[0] if isinstance(ocr_result_raw[0], list) else ocr_result_raw
                    if current_result_set:
                        for item in current_result_set:
                            text_info = None
                            if isinstance(item, list) and len(item) >= 2 and isinstance(item[1], (list, tuple)):
                                text_info = item[1]
                            elif isinstance(item, tuple) and len(item) >= 2:
                                text_info = item
                            if isinstance(text_info, (tuple, list)) and len(text_info) >= 1 and text_info[0]:
                                text_lines.append(str(text_info[0]))

                text = " ".join(text_lines).strip() # Combine lines
                extracted[roi.name] = text

                # --- Stability Check ---
                history = self.text_history.get(roi.name, {"text": "", "count": 0})
                if text == history["text"]:
                    history["count"] += 1 # Increment count if text is the same
                else:
                    history = {"text": text, "count": 1} # Reset count if text changed
                self.text_history[roi.name] = history # Update history

                is_now_stable = history["count"] >= self.stable_threshold
                was_stable = roi.name in self.stable_texts
                current_stable_text = self.stable_texts.get(roi.name)

                if is_now_stable:
                    # Text is stable now
                    if not was_stable or current_stable_text != text:
                        # Update stable text if it wasn't stable before or if the stable text changed
                        new_stable[roi.name] = text
                        stable_changed = True
                elif was_stable:
                    # Text was stable but is no longer considered stable (count reset)
                    if roi.name in new_stable:
                        del new_stable[roi.name] # Remove from stable texts
                        stable_changed = True

            except Exception as e:
                # Handle OCR errors for this specific ROI
                print(f"!!! OCR Error for ROI {roi.name}: {e}")
                extracted[roi.name] = "[OCR Error]"
                self.text_history[roi.name] = {"text": "[OCR Error]", "count": 1}
                # Ensure it's removed from stable text if an error occurs
                if roi.name in new_stable:
                    del new_stable[roi.name]
                    stable_changed = True

        # --- Update UI after processing all ROIs ---

        # Update Live Text tab (schedule on main thread)
        if hasattr(self, "text_tab") and self.text_tab.frame.winfo_exists():
            self.master.after_idle(lambda et=extracted.copy(): self.text_tab.update_text(et))

        # If stable text changed, update Stable Text tab and trigger auto-translate
        if stable_changed:
            self.stable_texts = new_stable # Update the main stable text dictionary
            # Update Stable Text tab (schedule on main thread)
            if hasattr(self, "stable_text_tab") and self.stable_text_tab.frame.winfo_exists():
                self.master.after_idle(lambda st=self.stable_texts.copy(): self.stable_text_tab.update_text(st))

            # Trigger auto-translation if enabled and there's stable text
            if (hasattr(self, "translation_tab") and
                    self.translation_tab.frame.winfo_exists() and
                    self.translation_tab.is_auto_translate_enabled()):

                if any(self.stable_texts.values()): # Check if there's actually any stable text
                    self.master.after_idle(self.translation_tab.perform_translation)
                else:
                    # Clear overlays and translation preview if stable text becomes empty
                    if hasattr(self, "overlay_manager"):
                        self.master.after_idle(self.overlay_manager.clear_all_overlays)
                    if hasattr(self, "translation_tab"):
                        # Update translation preview to show nothing is stable
                        self.master.after_idle(lambda: self.translation_tab.update_translation_results({}, "[No stable text]"))

    def _draw_rois(self):
        """Draws ROI rectangles and labels on the canvas."""
        # Check if canvas is ready and has valid dimensions
        if not hasattr(self, "canvas") or not self.canvas.winfo_exists() or self.frame_display_coords["w"] <= 0:
            return

        # Get offset of the displayed image on the canvas
        ox, oy = self.frame_display_coords["x"], self.frame_display_coords["y"]
        # Delete previous ROI drawings
        self.canvas.delete("roi_drawing")

        for i, roi in enumerate(self.rois):
            if roi.name == SNIP_ROI_NAME: continue # Don't draw the special snip ROI

            try:
                # Calculate display coordinates based on original ROI coords and scaling
                dx1 = int(roi.x1 * self.scale_x) + ox
                dy1 = int(roi.y1 * self.scale_y) + oy
                dx2 = int(roi.x2 * self.scale_x) + ox
                dy2 = int(roi.y2 * self.scale_y) + oy

                # Draw rectangle
                self.canvas.create_rectangle(
                    dx1, dy1, dx2, dy2,
                    outline="lime", width=1, # Green outline
                    tags=("display_content", "roi_drawing", f"roi_{i}") # Add tags
                )
                # Draw label
                self.canvas.create_text(
                    dx1 + 3, dy1 + 1, # Position slightly inside top-left corner
                    text=roi.name, fill="lime", anchor=tk.NW, # Green text
                    font=("TkDefaultFont", 8), # Small font
                    tags=("display_content", "roi_drawing", f"roi_label_{i}") # Add tags
                )
            except Exception as e:
                print(f"Error drawing ROI {roi.name}: {e}")

    # --- Mouse Events for ROI Definition ---

    def on_mouse_down(self, event):
        """Handles mouse button press on the canvas (for ROI definition)."""
        # Only act if ROI selection is active and using snapshot
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

        # Record start coordinates (canvas coordinates)
        self.roi_start_coords = (event.x, event.y)
        # Delete previous drawing rectangle if any
        if self.roi_draw_rect_id:
            try: self.canvas.delete(self.roi_draw_rect_id)
            except tk.TclError: pass
        # Create new drawing rectangle
        self.roi_draw_rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="red", width=2, tags="roi_drawing" # Red outline for drawing
        )

    def on_mouse_drag(self, event):
        """Handles mouse drag on the canvas (for ROI definition)."""
        # Only act if dragging started correctly
        if not self.roi_selection_active or not self.roi_start_coords or not self.roi_draw_rect_id: return

        sx, sy = self.roi_start_coords
        # Clamp current coordinates to be within the image bounds
        img_x, img_y = self.frame_display_coords["x"], self.frame_display_coords["y"]
        img_w, img_h = self.frame_display_coords["w"], self.frame_display_coords["h"]
        cx = max(img_x, min(event.x, img_x + img_w))
        cy = max(img_y, min(event.y, img_y + img_h))

        # Update the drawing rectangle coordinates
        try:
            # Also clamp start coords just in case they were slightly off
            clamped_sx = max(img_x, min(sx, img_x + img_w))
            clamped_sy = max(img_y, min(sy, img_y + img_h))
            self.canvas.coords(self.roi_draw_rect_id, clamped_sx, clamped_sy, cx, cy)
        except tk.TclError:
            # Handle error if rectangle was destroyed
            self.roi_draw_rect_id = None
            self.roi_start_coords = None

    def on_mouse_up(self, event):
        """Handles mouse button release on the canvas (completes ROI definition)."""
        # Check if ROI definition was in progress
        if not self.roi_selection_active or not self.roi_start_coords or not self.roi_draw_rect_id:
            # Clean up just in case rect_id exists but start_coords is None
            if self.roi_draw_rect_id:
                try: self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError: pass
            self.roi_draw_rect_id = None
            self.roi_start_coords = None
            # Don't deactivate roi_selection_active here if click was outside image
            return

        # Get final coordinates of the drawing rectangle
        try: coords = self.canvas.coords(self.roi_draw_rect_id)
        except tk.TclError: coords = None

        # Clean up drawing rectangle and reset state immediately
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
            if self.using_snapshot: self.return_to_live() # Return to live if failed
            return

        x1d, y1d, x2d, y2d = map(int, coords) # Display coordinates
        min_size = 5 # Minimum pixel size on screen
        if abs(x2d - x1d) < min_size or abs(y2d - y1d) < min_size:
            messagebox.showwarning("ROI Too Small", f"Defined region too small (min {min_size}x{min_size} px required).", parent=self.master)
            if self.using_snapshot: self.return_to_live() # Return to live if failed
            return

        # --- Get ROI Name ---
        roi_name = self.roi_tab.roi_name_entry.get().strip()
        overwrite_name = None
        existing_names = {r.name for r in self.rois if r.name != SNIP_ROI_NAME}

        if not roi_name:
            # Auto-generate name if empty
            i = 1; roi_name = f"roi_{i}"
            while roi_name in existing_names: i += 1; roi_name = f"roi_{i}"
        elif roi_name in existing_names:
            # Ask for confirmation if name exists
            if not messagebox.askyesno("ROI Exists", f"An ROI named '{roi_name}' already exists. Overwrite it?", parent=self.master):
                if self.using_snapshot: self.return_to_live() # Return to live if cancelled
                return
            overwrite_name = roi_name # Flag for overwrite
        elif roi_name == SNIP_ROI_NAME:
            # Prevent using reserved name
            messagebox.showerror("Invalid Name", f"Cannot use the reserved name '{SNIP_ROI_NAME}'. Please choose another.", parent=self.master)
            if self.using_snapshot: self.return_to_live()
            return

        # --- Convert display coordinates to original frame coordinates ---
        ox, oy = self.frame_display_coords["x"], self.frame_display_coords["y"] # Image offset on canvas
        # Coordinates relative to the displayed image
        rx1, ry1 = min(x1d, x2d) - ox, min(y1d, y2d) - oy
        rx2, ry2 = max(x1d, x2d) - ox, max(y1d, y2d) - oy

        # Check for valid scaling factor
        if self.scale_x <= 0 or self.scale_y <= 0:
            print("Error: Invalid scaling factor during ROI creation.")
            if self.using_snapshot: self.return_to_live()
            return

        # Convert back to original frame coordinates
        orig_x1, orig_y1 = int(rx1 / self.scale_x), int(ry1 / self.scale_y)
        orig_x2, orig_y2 = int(rx2 / self.scale_x), int(ry2 / self.scale_y)

        # Final size check on original coordinates
        if abs(orig_x2 - orig_x1) < 1 or abs(orig_y2 - orig_y1) < 1:
            messagebox.showwarning("ROI Too Small", "Calculated ROI size is too small in original frame.", parent=self.master)
            if self.using_snapshot: self.return_to_live()
            return

        # --- Create or Update ROI Object ---
        # Create new ROI with default color filter settings
        new_roi = ROI(roi_name, orig_x1, orig_y1, orig_x2, orig_y2)

        if overwrite_name:
            # Find existing ROI and replace it
            found = False
            for i, r in enumerate(self.rois):
                if r.name == overwrite_name:
                    # Preserve color filter settings from the old ROI if overwriting
                    new_roi.color_filter_enabled = r.color_filter_enabled
                    new_roi.target_color = r.target_color
                    new_roi.color_threshold = r.color_threshold
                    self.rois[i] = new_roi
                    found = True
                    break
            if not found: # Should not happen if overwrite_name was set
                print(f"Warning: Tried to overwrite '{overwrite_name}' but not found.")
                self.rois.append(new_roi) # Add as new instead
        else:
            # Add the new ROI to the list
            self.rois.append(new_roi)

        print(f"Created/Updated ROI: {new_roi.to_dict()}")

        # Update UI
        if hasattr(self, "roi_tab"): self.roi_tab.update_roi_list() # Update listbox
        self._draw_rois() # Redraw ROIs on canvas
        action = "created" if not overwrite_name else "updated"
        self.update_status(f"ROI '{roi_name}' {action}. Remember to save ROI settings.")

        # Suggest next ROI name in the entry box
        if hasattr(self, "roi_tab"):
            existing_names_now = {r.name for r in self.rois if r.name != SNIP_ROI_NAME}
            next_name = "dialogue" if "dialogue" not in existing_names_now else ""
            if not next_name: # If "dialogue" exists, find next "roi_N"
                i = 1; next_name = f"roi_{i}"
                while next_name in existing_names_now: i += 1; next_name = f"roi_{i}"
            self.roi_tab.roi_name_entry.delete(0, tk.END)
            self.roi_tab.roi_name_entry.insert(0, next_name)

        # Create overlay window for the new/updated ROI
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.create_overlay_for_roi(new_roi)

        # Return to live view if we were in snapshot mode
        if self.using_snapshot: self.return_to_live()

    # --- Floating Controls and Closing ---

    def show_floating_controls(self):
        """Shows or brings the floating controls window to the front."""
        try:
            if self.floating_controls is None or not self.floating_controls.winfo_exists():
                # Create if it doesn't exist
                self.floating_controls = FloatingControls(self.master, self)
            else:
                # Deiconify (if minimized/hidden) and lift (bring to front)
                self.floating_controls.deiconify()
                self.floating_controls.lift()
                # Update button states (e.g., auto-translate toggle)
                self.floating_controls.update_button_states()
        except Exception as e:
            print(f"Error showing floating controls: {e}")
            self.update_status("Error showing controls.")

    def hide_floating_controls(self):
        """Hides the floating controls window."""
        if self.floating_controls and self.floating_controls.winfo_exists():
            self.floating_controls.withdraw() # Hide instead of destroy

    def on_close(self):
        """Handles the application closing sequence."""
        print("Close requested...")
        # Cancel any active modes
        if self.snip_mode_active: self.cancel_snip_mode()
        if self.roi_selection_active: self.toggle_roi_selection() # Cancel ROI selection

        # Close any open snip result window
        if self.current_snip_window and self.current_snip_window.winfo_exists():
            try: self.current_snip_window.destroy_window()
            except Exception: pass
            self.current_snip_window = None

        # Stop capture if running
        if self.capturing:
            self.update_status("Stopping capture before closing...")
            self.stop_capture()
            # Check periodically if capture has stopped before finalizing close
            self.master.after(500, self.check_capture_stopped_and_close)
        else:
            # If capture not running, proceed to finalize close immediately
            self._finalize_close()

    def check_capture_stopped_and_close(self):
        """Checks if capture thread is stopped, then finalizes close."""
        # Check capturing flag and thread status
        if not self.capturing and (self.capture_thread is None or not self.capture_thread.is_alive()):
            # Capture is stopped, finalize closing
            self._finalize_close()
        else:
            # Still stopping, check again later
            print("Waiting for capture thread to stop...")
            self.master.after(500, self.check_capture_stopped_and_close)

    def _finalize_close(self):
        """Performs final cleanup before exiting."""
        print("Finalizing close...")
        self.capturing = False # Ensure flag is false

        # Destroy all overlay windows managed by OverlayManager
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.destroy_all_overlays()

        # Save floating controls position and destroy the window
        if self.floating_controls and self.floating_controls.winfo_exists():
            try:
                # Only save position if the window is visible/normal
                if self.floating_controls.state() == "normal":
                    geo = self.floating_controls.geometry() # Format: "WxH+X+Y"
                    parts = geo.split('+')
                    if len(parts) == 3: # Expecting size, x, y
                        x_str, y_str = parts[1], parts[2]
                        # Basic validation
                        if x_str.isdigit() and y_str.isdigit():
                            set_setting("floating_controls_pos", f"{x_str},{y_str}")
                        else: print(f"Warn: Invalid floating controls coordinates in geometry: {geo}")
                    else: print(f"Warn: Could not parse floating controls geometry: {geo}")
            except Exception as e: print(f"Error saving floating controls position: {e}")
            # Destroy the window regardless of position saving success
            try: self.floating_controls.destroy()
            except tk.TclError: pass # Ignore error if already destroyed

        # Ensure snip result window is destroyed (redundant check)
        if self.current_snip_window and self.current_snip_window.winfo_exists():
            try: self.current_snip_window.destroy_window()
            except Exception: pass

        print("Exiting application.")
        # Quit the Tkinter main loop and destroy the main window
        try:
            self.master.quit()
            self.master.destroy()
        except tk.TclError: pass # Ignore errors if already destroying
        except Exception as e: print(f"Error during final window destruction: {e}")

# --- END OF FILE app.py ---