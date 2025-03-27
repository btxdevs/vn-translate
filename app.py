import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import cv2
from PIL import Image, ImageTk
import os
import win32gui
from paddleocr import PaddleOCR, paddleocr # Import base exception class if needed
import platform # For platform-specific code if needed

# Import utilities
from utils.capture import get_window_title, capture_window
from utils.config import load_rois # Keep using config.load_rois
from utils.settings import load_settings, save_settings, get_setting, set_setting, update_settings
from utils.roi import ROI

# Import UI components
from ui.capture_tab import CaptureTab
from ui.roi_tab import ROITab
from ui.text_tab import TextTab, StableTextTab
from ui.translation_tab import TranslationTab
from ui.overlay_tab import OverlayTab # Import new tab
from ui.overlay_manager import OverlayManager # Import manager
from ui.floating_controls import FloatingControls # Import floating controls

# Constants
FPS = 10 # Target FPS for capture loop
FRAME_DELAY = 1.0 / FPS
OCR_ENGINE_LOCK = threading.Lock() # Lock for OCR engine access/reinitialization

class VisualNovelTranslatorApp:
    """Main application class for the Visual Novel Translator."""

    def __init__(self, master):
        self.master = master
        self.settings = load_settings() # Load settings early
        self.config_file = self.settings.get("last_roi_config") # Load last used path
        # Use default only if last_roi_config was None or empty in settings
        if not self.config_file:
            self.config_file = "vn_translator_config.json"


        # Update title based on loaded config
        window_title = "Visual Novel Translator"
        # Show filename in title only if it exists and is not the default name maybe?
        if self.config_file and os.path.exists(self.config_file): # and os.path.basename(self.config_file) != "vn_translator_config.json":
            window_title += f" - {os.path.basename(self.config_file)}"
        master.title(window_title)
        master.geometry("1200x800")
        master.minsize(1000, 700)
        master.protocol("WM_DELETE_WINDOW", self.on_close) # Handle closing


        # --- Initialize variables ---
        self.capturing = False
        self.roi_selection_active = False
        self.selected_hwnd = None
        self.capture_thread = None
        self.rois = []
        self.current_frame = None      # Raw captured frame (BGR numpy array)
        self.display_frame_tk = None # PhotoImage for canvas (keep reference)
        self.snapshot_frame = None     # Snapshot frame (BGR numpy array)
        self.using_snapshot = False
        self.roi_start_coords = None # Store (x,y) tuple during ROI drag
        self.roi_draw_rect_id = None # Canvas item ID for drawing ROI rect
        self.scale_x, self.scale_y = 1.0, 1.0 # Scaling of preview image relative to original
        self.frame_display_coords = {'x': 0, 'y': 0, 'w': 0, 'h': 0} # Image position/size on canvas

        self.text_history = {} # roi_name: {"text": str, "count": int}
        self.stable_texts = {} # roi_name: stable_text_str
        # Load settings for stability etc.
        self.stable_threshold = get_setting("stable_threshold", 3)
        self.max_display_width = get_setting("max_display_width", 800)
        self.max_display_height = get_setting("max_display_height", 600)
        self.last_status_message = ""

        self.ocr = None # Initialize later in a thread-safe way
        self.ocr_lang = get_setting("ocr_language", "jpn") # Load last used lang
        self._resize_job = None # For debouncing canvas resize

        # --- Setup UI ---
        self._setup_ui() # Creates tabs and layout

        # --- Initialize Managers ---
        # Needs to happen after master is fully initialized but before loading things that need it
        self.overlay_manager = OverlayManager(self.master, self)
        self.floating_controls = None # Created later

        # --- Load initial config (ROIs) ---
        # Must happen after UI tabs are created (roi_tab) and overlay_manager exists
        self._load_initial_rois()

        # --- Initialize OCR Engine ---
        # Do this in a non-blocking way
        # Needs capture_tab to exist to get initial language if setting missing
        initial_ocr_lang = self.ocr_lang
        if hasattr(self, 'capture_tab') and not initial_ocr_lang:
            initial_ocr_lang = self.capture_tab.lang_var.get() or "jpn"
        self.update_ocr_engine(initial_ocr_lang, initial_load=True)

        # --- Show Floating Controls ---
        # Can be called after main loop starts if preferred
        self.show_floating_controls()


    def _setup_ui(self):
        """Set up the main UI layout and tabs."""
        # Main PanedWindow for resizable layout
        self.paned_window = ttk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- Left frame for preview ---
        self.left_frame = ttk.Frame(self.paned_window, padding=0) # No padding on frame itself
        self.paned_window.add(self.left_frame, weight=3) # Give more weight initially

        # Canvas fills the left frame
        self.canvas = tk.Canvas(self.left_frame, bg="gray15", highlightthickness=0) # Darker background
        self.canvas.pack(fill=tk.BOTH, expand=True)
        # Bind mouse events for ROI definition
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        # Bind resize event to redraw frame
        self.canvas.bind("<Configure>", self.on_canvas_resize)


        # --- Right frame for controls ---
        self.right_frame = ttk.Frame(self.paned_window, padding=(5, 0, 0, 0)) # Pad left side only
        self.paned_window.add(self.right_frame, weight=1) # Less weight initially

        self.notebook = ttk.Notebook(self.right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs (order can matter for dependencies during init)
        self.capture_tab = CaptureTab(self.notebook, self)
        self.notebook.add(self.capture_tab.frame, text="Capture")

        self.roi_tab = ROITab(self.notebook, self)
        self.notebook.add(self.roi_tab.frame, text="ROIs")

        # Add Overlay Tab after ROI Tab
        self.overlay_tab = OverlayTab(self.notebook, self)
        self.notebook.add(self.overlay_tab.frame, text="Overlays")

        self.text_tab = TextTab(self.notebook, self)
        self.notebook.add(self.text_tab.frame, text="Live Text") # Renamed

        self.stable_text_tab = StableTextTab(self.notebook, self)
        self.notebook.add(self.stable_text_tab.frame, text="Stable Text") # Renamed

        self.translation_tab = TranslationTab(self.notebook, self)
        self.notebook.add(self.translation_tab.frame, text="Translation")

        # Add a status bar at the bottom
        self.status_bar_frame = ttk.Frame(self.master, relief=tk.SUNKEN)
        self.status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_bar = ttk.Label(self.status_bar_frame, text="Status: Initializing...", anchor=tk.W, padding=(5, 2))
        self.status_bar.pack(fill=tk.X)
        self.update_status("Ready.") # Initial status


    def update_status(self, message):
        """Update the status bar message, preventing rapid duplicate messages."""
        # Use `after_idle` to ensure this runs in the main thread
        def _do_update():
            # Check if status_bar widget exists and is valid before configuring
            if hasattr(self, 'status_bar') and self.status_bar.winfo_exists():
                # Check current text using cget to avoid potential issues if called during destruction
                try:
                    current_text = self.status_bar.cget("text")
                except tk.TclError:
                    current_text = "" # Widget might be dying

                new_text = f"Status: {message}"
                if new_text != current_text: # Only update if message is different
                    try:
                        self.status_bar.config(text=new_text)
                    except tk.TclError: pass # Ignore if widget died between check and config
                    self.last_status_message = message # Store the message part only

                    # Update CaptureTab's status label too for consistency, checking its frame and label
                    if hasattr(self, 'capture_tab') and hasattr(self.capture_tab, 'frame') and self.capture_tab.frame.winfo_exists():
                        if hasattr(self.capture_tab, 'status_label') and self.capture_tab.status_label.winfo_exists():
                            try:
                                self.capture_tab.status_label.config(text=new_text)
                            except tk.TclError: pass # Ignore if dying
            else:
                # Fallback if called before UI fully ready or after destruction
                # print(f"STATUS (UI not ready): {message}")
                self.last_status_message = message

        # Schedule the update only if the main window exists
        try:
            if self.master.winfo_exists():
                self.master.after_idle(_do_update)
            else:
                # If master window gone, just store last message
                self.last_status_message = message
        except Exception: # Catch potential errors if master is in weird state
            self.last_status_message = message


    def _load_initial_rois(self):
        """Load ROIs from the last used config file on startup."""
        if self.config_file and os.path.exists(self.config_file):
            self.update_status(f"Loading ROIs from {os.path.basename(self.config_file)}...")
            try:
                # Use the load_rois function from config.py
                rois, loaded_path = load_rois(initial_path=self.config_file)

                if loaded_path and rois is not None: # Check success (path returned, rois not None)
                    self.rois = rois
                    self.config_file = loaded_path # Ensure config_file is updated
                    # Update UI elements that depend on ROIs
                    # Use hasattr checks for safety during init sequence
                    if hasattr(self, 'roi_tab'): self.roi_tab.update_roi_list()
                    if hasattr(self, 'overlay_manager'): self.overlay_manager.rebuild_overlays()

                    self.update_status(f"Loaded {len(rois)} ROIs from {os.path.basename(loaded_path)}")
                    self.master.title(f"Visual Novel Translator - {os.path.basename(loaded_path)}")
                elif rois is None and loaded_path is None: # Explicit failure indication from load_rois (e.g., file corrupted)
                    self.update_status(f"Error loading ROIs from {os.path.basename(self.config_file)}. See console.")
                # else: # User cancelled load dialog (rois=[], loaded_path=None)
                # Status update likely handled within load_rois/dialogs. Keep previous state.
                # self.update_status("ROI loading cancelled or failed.")

            except Exception as e:
                self.update_status(f"Error loading initial ROIs: {str(e)}")
                import traceback
                traceback.print_exc()
        else:
            self.update_status("No previous ROI config found or file missing. Define new ROIs or load a file.")


    def update_ocr_engine(self, lang_code, initial_load=False):
        """Initialize or update the PaddleOCR engine in a separate thread."""
        def init_engine():
            global OCR_ENGINE_LOCK
            lang_map = {"jpn": "japan", "jpn_vert": "japan", "eng": "en", "chi_sim": "ch", "chi_tra": "ch", "kor": "ko"}
            # Add more mappings as needed based on PaddleOCR supported languages
            ocr_lang_paddle = lang_map.get(lang_code, "en") # Default to English if code unknown

            # Prevent unnecessary re-initialization if lang didn't actually change
            with OCR_ENGINE_LOCK:
                # Check the internal language code used by the PaddleOCR instance
                current_paddle_lang = getattr(self.ocr, 'lang', None) if self.ocr else None
                if current_paddle_lang == ocr_lang_paddle:
                    print(f"OCR engine already initialized with the correct language ({lang_code}).")
                    self.master.after_idle(lambda: self.update_status(f"OCR Ready ({lang_code})."))
                    return

            # If language changed or no engine yet, proceed with initialization
            print(f"Attempting to initialize OCR engine for language: {lang_code} (Paddle code: {ocr_lang_paddle})...")
            # Update status immediately if possible
            self.master.after_idle(lambda: self.update_status(f"Initializing OCR ({lang_code})..."))

            try:
                # This can take time, especially first download
                new_ocr_engine = PaddleOCR(use_angle_cls=True, lang=ocr_lang_paddle, show_log=False)
                print(f"PaddleOCR initialized successfully for {ocr_lang_paddle}.")

                # --- Critical Section: Update self.ocr ---
                with OCR_ENGINE_LOCK:
                    self.ocr = new_ocr_engine
                    # Store the app's lang code ('jpn', 'eng', etc.) which might differ from paddle's internal code
                    self.ocr_lang = lang_code
                # --- End Critical Section ---

                print(f"OCR engine ready for {lang_code}.")
                # Update status in main thread
                self.master.after_idle(lambda: self.update_status(f"OCR Ready ({lang_code})."))

            except paddleocr.PaddleocrError as pe: # Catch specific Paddle errors if possible
                print(f"!!! PaddleOCR specific error initializing for lang {lang_code}: {pe}")
                self.master.after_idle(lambda: self.update_status(f"OCR Error ({lang_code}): {pe}"))
                with OCR_ENGINE_LOCK: self.ocr = None
            except Exception as e:
                print(f"!!! General error initializing PaddleOCR for lang {lang_code}: {e}")
                import traceback
                traceback.print_exc()
                # Update status in main thread
                self.master.after_idle(lambda: self.update_status(f"OCR Error ({lang_code}): Check console"))
                # Fallback: Disable OCR features?
                with OCR_ENGINE_LOCK:
                    self.ocr = None

        # Run in a separate thread to avoid blocking UI
        threading.Thread(target=init_engine, daemon=True).start()


    def start_capture(self):
        """Start capturing from the selected window."""
        if self.capturing:
            self.update_status("Capture already running.")
            return

        if not self.selected_hwnd:
            messagebox.showwarning("Warning", "No visual novel window selected.", parent=self.master)
            return

        # Check window validity *before* starting thread
        if not win32gui.IsWindow(self.selected_hwnd):
            messagebox.showerror("Error", "Selected window no longer exists. Refresh the list.", parent=self.master)
            if hasattr(self, 'capture_tab'): self.capture_tab.refresh_window_list() # Attempt to refresh
            return

        # Check if OCR is ready (non-blocking check)
        with OCR_ENGINE_LOCK:
            ocr_ready = bool(self.ocr)

        if not ocr_ready:
            # Maybe initiate OCR loading if not already attempting?
            current_lang = self.ocr_lang # Use the stored language preference
            if not current_lang: current_lang = "jpn" # Fallback
            self.update_ocr_engine(current_lang) # Re-trigger loading if needed
            messagebox.showinfo("OCR Not Ready", "The OCR engine is still initializing. Capture will start, but text extraction may be delayed or fail until OCR is ready.", parent=self.master)
            # Proceed with capture anyway? Or prevent start? Let's proceed.


        if self.using_snapshot:
            self.return_to_live() # Ensure we are in live mode

        self.capturing = True
        # Reset text history/stable text when starting new capture session? Optional.
        # self.text_history = {}
        # self.stable_texts = {}

        self.capture_thread = threading.Thread(target=self.capture_process, daemon=True)
        self.capture_thread.start()

        # Update UI immediately
        if hasattr(self, 'capture_tab'): self.capture_tab.on_capture_started()
        title = get_window_title(self.selected_hwnd) or f"HWND {self.selected_hwnd}"
        self.update_status(f"Capturing: {title}")
        if hasattr(self, 'overlay_manager'): self.overlay_manager.rebuild_overlays() # Ensure overlays match current ROIs

    def stop_capture(self):
        """Stop the current capture process gracefully."""
        if not self.capturing:
            # self.update_status("Capture is not running.") # Avoid noise if called multiple times
            return

        print("Stop capture requested...")
        self.capturing = False # Signal the thread to stop

        # Use `after` to periodically check if the thread has finished before finalizing UI.
        self.master.after(100, self._check_thread_and_finalize_stop)


    def _check_thread_and_finalize_stop(self):
        """Checks if capture thread finished, calls finalize or re-schedules check."""
        # Check thread existence and liveness
        if self.capture_thread and self.capture_thread.is_alive():
            # print("Waiting for capture thread to finish...") # Reduce console noise
            self.master.after(100, self._check_thread_and_finalize_stop) # Check again
        else:
            # Thread is gone or dead, safe to finalize
            # print("Capture thread finished.")
            self.capture_thread = None # Clear thread reference
            # Ensure finalize runs only once if multiple checks were scheduled
            if not hasattr(self, '_finalize_stop_called') or not self._finalize_stop_called:
                self._finalize_stop_called = True
                self._finalize_stop_capture()


    def _finalize_stop_capture(self):
        """Actions to perform in the main thread after capture stops."""
        # Check if the capturing flag is actually false now
        if self.capturing:
            print("Warning: _finalize_stop_capture called while capturing flag still true.")
            # This might indicate a race condition or error. Reset flag for safety.
            self.capturing = False

        print("Finalizing stop capture UI updates...")
        # Reset the flag used by _check_thread_...
        self._finalize_stop_called = False

        # Update UI elements safely, checking if they exist
        if hasattr(self, 'capture_tab') and self.capture_tab.frame.winfo_exists():
            self.capture_tab.on_capture_stopped()
        # Clear potentially stale data? Optional.
        # self.current_frame = None
        # self._display_frame(None) # Clear canvas?
        if hasattr(self, 'overlay_manager'):
            self.overlay_manager.hide_all_overlays() # Hide overlays when capture stops
        self.update_status("Capture stopped.")


    def take_snapshot(self):
        """Take a snapshot of the current frame for static analysis (ROI definition)."""
        # Allow snapshot even if capture just stopped but frame exists
        if not self.capturing and self.current_frame is None:
            messagebox.showwarning("Warning", "Capture is not running and no frame available. Cannot take snapshot.", parent=self.master)
            return
        if self.current_frame is None:
            messagebox.showwarning("Warning", "No frame captured yet to take snapshot.", parent=self.master)
            return

        print("Taking snapshot...")
        self.snapshot_frame = self.current_frame.copy() # Ensure it's a copy
        self.using_snapshot = True
        self._display_frame(self.snapshot_frame) # Display the static frame

        if hasattr(self, 'capture_tab'): self.capture_tab.on_snapshot_taken()
        self.update_status("Snapshot taken. Define ROIs or return to live.")


    def return_to_live(self):
        """Return to live view from snapshot mode."""
        if not self.using_snapshot:
            return

        print("Returning to live view...")
        self.using_snapshot = False
        self.snapshot_frame = None
        # If capture is running, the capture loop will provide the next frame.
        # If capture stopped, display black/placeholder?
        # Let's display the *last known* live frame immediately if available.
        if self.current_frame is not None:
            self._display_frame(self.current_frame)
        else:
            self._display_frame(None) # Display nothing if no live frame available

        if hasattr(self, 'capture_tab'): self.capture_tab.on_live_view_resumed()
        # Status updated within on_live_view_resumed checks self.capturing
        # self.update_status("Returned to live view." if self.capturing else "Returned to stopped state.")


    def toggle_roi_selection(self):
        """Enable or disable ROI selection mode."""
        # --- If activating ROI selection ---
        if not self.roi_selection_active:
            # Must have an image (live or snapshot) to draw on
            frame_available = self.current_frame is not None or self.snapshot_frame is not None
            if not frame_available:
                messagebox.showwarning("Warning", "Start capture or take a snapshot before defining ROIs.", parent=self.master)
                return

            # If live capturing, automatically take snapshot
            if self.capturing and not self.using_snapshot:
                print("Taking snapshot automatically for ROI definition.")
                self.take_snapshot()
                # Check if snapshot succeeded before activating ROI mode
                if not self.using_snapshot:
                    print("Snapshot failed, cannot activate ROI selection.")
                    return

            # Now activate ROI selection mode
            self.roi_selection_active = True
            if hasattr(self, 'roi_tab'): self.roi_tab.on_roi_selection_toggled(True) # Updates button text, status, cursor

        # --- If deactivating ROI selection ---
        else:
            self.roi_selection_active = False
            if hasattr(self, 'roi_tab'): self.roi_tab.on_roi_selection_toggled(False) # Updates button text, status, cursor
            # Clean up drawing rectangle if it exists from an incomplete drag
            if self.roi_draw_rect_id:
                self.canvas.delete(self.roi_draw_rect_id)
                self.roi_draw_rect_id = None
            self.roi_start_coords = None
            self.update_status("ROI selection cancelled.")
            # Do NOT automatically return to live here. User might want to stay on snapshot.


    def capture_process(self):
        """Background thread for continuous window capture and processing."""
        last_frame_time = time.time()
        target_sleep_time = FRAME_DELAY # Target delay between frames

        print("Capture thread started.")
        while self.capturing: # Loop controlled by self.capturing flag
            loop_start_time = time.time()
            frame_to_display = None
            try:
                # If in snapshot mode, just sleep and wait
                if self.using_snapshot:
                    time.sleep(0.05) # Sleep briefly to yield CPU
                    continue

                # --- Capture Frame ---
                frame = capture_window(self.selected_hwnd)
                if frame is None:
                    # Window lost or uncapturable
                    if self.capturing: # Check flag again in case stop was requested concurrently
                        print("Capture window returned None. Signaling failure.")
                        # Schedule failure handling in main thread
                        self.master.after_idle(self.handle_capture_failure)
                    break # Exit capture loop immediately

                # --- Store & Process Frame ---
                self.current_frame = frame # Store the latest raw frame (BGR)
                frame_to_display = frame # Use this frame for display update

                # --- Process ROIs for text if OCR is ready ---
                # Get OCR engine instance safely using lock
                ocr_engine_instance = None
                with OCR_ENGINE_LOCK:
                    if self.ocr:
                        ocr_engine_instance = self.ocr

                if self.rois and ocr_engine_instance:
                    # Process ROIs using the captured frame and the OCR instance
                    # Pass the engine instance to avoid issues if it's re-initialized concurrently
                    self._process_rois(frame, ocr_engine_instance)


                # --- Schedule UI Display Update (Rate Limited) ---
                current_time = time.time()
                # Only schedule redraw if enough time has passed OR if it's the very first frame after starting maybe?
                if current_time - last_frame_time >= target_sleep_time:
                    # Schedule _display_frame to run in the main thread
                    # Pass a copy to prevent modifications by subsequent loop iterations
                    if frame_to_display is not None:
                        frame_copy_for_display = frame_to_display.copy()
                        self.master.after_idle(lambda f=frame_copy_for_display: self._display_frame(f))
                    last_frame_time = current_time


                # --- Calculate Sleep Time ---
                # Ensure positive sleep time
                elapsed = time.time() - loop_start_time
                sleep_duration = max(0.001, target_sleep_time - elapsed) # Sleep at least 1ms
                time.sleep(sleep_duration)

            except Exception as e:
                print(f"!!! Error in capture loop: {e}")
                import traceback
                traceback.print_exc()
                # Update status safely via main thread
                self.master.after_idle(lambda msg=str(e): self.update_status(f"Capture loop error: {msg[:60]}..."))
                # Pause for a moment to prevent rapid error loops
                time.sleep(1)


        # --- Post-Loop Cleanup (runs when self.capturing becomes False or loop breaks) ---
        print("Capture thread finished or exited.")
        # Final UI state update is handled by stop_capture -> _check_thread_... -> _finalize_stop_capture
        # Or by handle_capture_failure -> stop_capture -> ...


    def handle_capture_failure(self):
        """Called from main thread if capture_window returns None while capturing."""
        # Check if we are still supposed to be capturing (flag might have been set false by stop_capture)
        if self.capturing:
            self.update_status("Window lost or uncapturable. Stopping capture.")
            # Avoid showing messagebox if window was simply closed normally? Hard to tell.
            # messagebox.showerror("Capture Error", "Failed to capture the selected window. It might be closed, minimized, or protected.", parent=self.master)
            print("Failed to capture the selected window. It might be closed, minimized, or protected.")
            # Initiate stop process
            self.stop_capture()
            # Refresh window list to help user re-select
            if hasattr(self, 'capture_tab'): self.capture_tab.refresh_window_list()


    def on_canvas_resize(self, event=None):
        """Called when the canvas size changes. Redraw current/snapshot frame."""
        # Debounce using `after` to avoid excessive redraws during rapid resizing
        if self._resize_job:
            self.master.after_cancel(self._resize_job)
        # Schedule the redraw operation after a short delay (e.g., 100ms)
        self._resize_job = self.master.after(100, self._perform_resize_redraw)


    def _perform_resize_redraw(self):
        """Actually redraws the frame after a resize event debounce."""
        self._resize_job = None # Clear the job ID
        # Check if canvas still exists
        if not self.canvas.winfo_exists():
            return
        frame_to_display = self.snapshot_frame if self.using_snapshot else self.current_frame
        # If no frame, _display_frame handles clearing the canvas
        self._display_frame(frame_to_display)


    def _display_frame(self, frame):
        """
        Display a frame on the canvas, fitting and centering it.
        Handles None frame by clearing canvas.
        """
        # Check if canvas exists and is valid
        if not hasattr(self, 'canvas') or not self.canvas.winfo_exists():
            return

        # Clear previous content (image and ROIs) first
        self.canvas.delete("display_content")
        self.display_frame_tk = None # Clear PhotoImage reference to allow GC

        # If frame is None, just keep canvas clear
        if frame is None:
            # Optionally draw a placeholder message?
            try:
                cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
                if cw > 1 and ch > 1: # Avoid drawing if canvas isn't ready
                    self.canvas.create_text(cw/2, ch/2, text="No Image", fill="gray50", tags="display_content", font=('Segoe UI', 12))
            except Exception: pass # Ignore errors during potential shutdown
            return

        try:
            frame_height, frame_width = frame.shape[:2]
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()

            # Prevent division by zero if frame or canvas dimensions are invalid
            if frame_width <= 0 or frame_height <= 0 or canvas_width <= 1 or canvas_height <= 1:
                # print("Warning: Invalid frame or canvas dimensions for display.")
                return

            # Calculate scaling factor to fit frame within canvas
            scale_w = canvas_width / frame_width
            scale_h = canvas_height / frame_height
            scale = min(scale_w, scale_h)

            # Optional: Prevent upscaling beyond 1:1?
            # scale = min(scale, 1.0)

            new_width = int(frame_width * scale)
            new_height = int(frame_height * scale)

            # Ensure dimensions are at least 1 pixel
            if new_width < 1 or new_height < 1:
                # print("Warning: Calculated display dimensions too small.")
                return

            # Store scale and position info for ROI mapping
            self.scale_x = scale
            self.scale_y = scale
            self.frame_display_coords['x'] = (canvas_width - new_width) // 2
            self.frame_display_coords['y'] = (canvas_height - new_height) // 2
            self.frame_display_coords['w'] = new_width
            self.frame_display_coords['h'] = new_height

            # Resize and convert frame for display using OpenCV
            # Use INTER_LINEAR for a good balance of speed and quality
            interpolation_method = cv2.INTER_LINEAR if scale < 1.0 else cv2.INTER_CUBIC # Use better quality if upscaling slightly
            resized_frame = cv2.resize(frame, (new_width, new_height), interpolation=interpolation_method)
            # Convert BGR (from OpenCV) to RGB for PIL/Tkinter
            display_rgb = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)

            # Convert numpy array to PhotoImage using PIL
            img = Image.fromarray(display_rgb)
            self.display_frame_tk = ImageTk.PhotoImage(image=img) # Store reference on self

            # --- Draw on Canvas ---
            # Draw the image itself
            self.canvas.create_image(
                self.frame_display_coords['x'], self.frame_display_coords['y'],
                anchor=tk.NW,
                image=self.display_frame_tk, # Use the stored reference
                tags=("display_content", "frame_image")
            )

            # Draw ROIs on top of the image
            self._draw_rois()

        except Exception as e:
            print(f"Error displaying frame: {e}")
            import traceback
            traceback.print_exc()


    def _process_rois(self, frame, ocr_engine):
        """
        Process ROIs on the given frame using the provided OCR engine instance.
        This method assumes it's called from the capture thread.
        """
        if frame is None or ocr_engine is None:
            # print("Skipping ROI processing: No frame or OCR engine.") # Reduce noise
            return

        extracted_texts = {}
        stable_text_changed = False
        new_stable_texts = self.stable_texts.copy() # Work on a copy for this frame's results

        for roi in self.rois:
            # Extract image for the current ROI
            roi_img = roi.extract_roi(frame)
            if roi_img is None or roi_img.size == 0:
                extracted_texts[roi.name] = "" # Mark as empty if extraction failed
                continue # Skip to next ROI

            try:
                # --- Perform OCR ---
                ocr_result_raw = ocr_engine.ocr(roi_img, cls=True) # cls=True is recommended

                # --- Extract Text from OCR Result ---
                text_lines = []
                # Added check for None result from ocr.ocr itself
                if ocr_result_raw is not None and isinstance(ocr_result_raw, list) and len(ocr_result_raw) > 0:
                    # Handle potential extra list layer added in some versions
                    current_result_set = ocr_result_raw[0] if isinstance(ocr_result_raw[0], list) else ocr_result_raw

                    if current_result_set: # Check if the result set for the image is not empty
                        for item in current_result_set:
                            # Try to extract text tuple (text, confidence) robustly
                            text_info = None
                            if isinstance(item, list) and len(item) >= 2: # Common format [[box], (text, conf)]
                                text_info = item[1]
                            # Handle other potential formats if necessary...

                            if isinstance(text_info, (tuple, list)) and len(text_info) >= 1:
                                text_content = text_info[0]
                                # confidence = text_info[1] if len(text_info) > 1 else 0.0
                                if text_content: # Add non-empty text
                                    text_lines.append(str(text_content))

                # Join lines (use space or newline based on language? Space is usually safer)
                text = " ".join(text_lines).strip()
                extracted_texts[roi.name] = text

                # --- Update Stability Tracking ---
                history = self.text_history.get(roi.name, {"text": "", "count": 0})
                if text == history["text"]:
                    history["count"] += 1
                else:
                    # Reset count if text changes
                    history = {"text": text, "count": 1}
                # Store updated history
                self.text_history[roi.name] = history

                # Check for new stable text
                is_now_stable = history["count"] >= self.stable_threshold
                was_stable = roi.name in self.stable_texts
                current_stable_text = self.stable_texts.get(roi.name)

                if is_now_stable:
                    if not was_stable or current_stable_text != text:
                        # Became stable or stable text changed
                        new_stable_texts[roi.name] = text
                        stable_text_changed = True
                        # print(f"ROI '{roi.name}' became stable: '{text[:30]}...'") # Reduce noise
                elif was_stable:
                    # Was stable, but text changed and is no longer stable
                    del new_stable_texts[roi.name]
                    stable_text_changed = True
                    # print(f"ROI '{roi.name}' became unstable.")


            except Exception as e:
                print(f"!!! Error during OCR processing for ROI {roi.name}: {e}")
                # Avoid printing full traceback in loop unless debugging
                # import traceback
                # traceback.print_exc()
                extracted_texts[roi.name] = "[OCR Error]"
                # Reset stability for this ROI on error
                self.text_history[roi.name] = {"text": "[OCR Error]", "count": 1}
                if roi.name in new_stable_texts:
                    del new_stable_texts[roi.name]
                    stable_text_changed = True # Becoming unstable is a change


        # --- Schedule UI Updates (in main thread) ---
        # Update live text display always, checking widget existence
        if hasattr(self, 'text_tab') and self.text_tab.frame.winfo_exists():
            self.master.after_idle(lambda et=extracted_texts.copy(): self.text_tab.update_text(et))

        # Update stable text display and potentially trigger translation only if changes occurred
        if stable_text_changed:
            self.stable_texts = new_stable_texts # Update the main stable text dict reference
            if hasattr(self, 'stable_text_tab') and self.stable_text_tab.frame.winfo_exists():
                self.master.after_idle(lambda st=self.stable_texts.copy(): self.stable_text_tab.update_text(st))

            # Trigger auto-translation if enabled and translation tab exists
            if hasattr(self, 'translation_tab') and self.translation_tab.frame.winfo_exists() and \
                    self.translation_tab.is_auto_translate_enabled():
                # print("[Auto-Translate] Stable text changed, scheduling translation.") # Reduce noise
                # Use `after_idle` to ensure it runs after the stable text UI update
                self.master.after_idle(self.translation_tab.perform_translation)


    def _draw_rois(self):
        """Draw ROI rectangles on the canvas over the displayed frame."""
        # Check if canvas and coords are valid
        if not hasattr(self, 'canvas') or not self.canvas.winfo_exists() or \
                self.frame_display_coords['w'] <= 0 or self.frame_display_coords['h'] <= 0:
            return

        offset_x = self.frame_display_coords['x']
        offset_y = self.frame_display_coords['y']

        for i, roi in enumerate(self.rois):
            try:
                # Scale ROI coords to display coords
                disp_x1 = int(roi.x1 * self.scale_x) + offset_x
                disp_y1 = int(roi.y1 * self.scale_y) + offset_y
                disp_x2 = int(roi.x2 * self.scale_x) + offset_x
                disp_y2 = int(roi.y2 * self.scale_y) + offset_y

                # Draw rectangle
                self.canvas.create_rectangle(
                    disp_x1, disp_y1, disp_x2, disp_y2,
                    outline="lime", width=1, tags=("display_content", f"roi_{i}")
                )
                # Draw label slightly inside the rectangle
                self.canvas.create_text(
                    disp_x1 + 3, disp_y1 + 1, # Offset slightly from top-left
                    text=roi.name, fill="lime", anchor=tk.NW,
                    font=('TkDefaultFont', 8), tags=("display_content", f"roi_label_{i}")
                )
            except Exception as e:
                print(f"Error drawing ROI {roi.name}: {e}")

    # --- Mouse Events for ROI Definition ---

    def on_mouse_down(self, event):
        """Handle mouse button press for starting ROI selection."""
        # Only act if ROI selection is active AND we are using a snapshot
        if not self.roi_selection_active or not self.using_snapshot:
            return

        # Check if click is within the displayed image bounds
        img_x = self.frame_display_coords['x']
        img_y = self.frame_display_coords['y']
        img_w = self.frame_display_coords['w']
        img_h = self.frame_display_coords['h']

        if not (img_x <= event.x < img_x + img_w and img_y <= event.y < img_y + img_h):
            # print("ROI start click outside image bounds.")
            self.roi_start_coords = None # Reset start coords if outside
            # Clean up any previous drawing rectangle visually
            if self.roi_draw_rect_id:
                self.canvas.delete(self.roi_draw_rect_id)
                self.roi_draw_rect_id = None
            return # Ignore clicks outside the image

        # Store starting coordinates relative to canvas
        self.roi_start_coords = (event.x, event.y)

        # Delete previous drawing rectangle if any (e.g., from a cancelled drag)
        if self.roi_draw_rect_id:
            self.canvas.delete(self.roi_draw_rect_id)

        # Create a new rectangle for visual feedback (initially zero size)
        self.roi_draw_rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="red", width=2, tags="roi_drawing" # Use specific tag
        )
        # print(f"ROI draw started at ({event.x}, {event.y})")

    def on_mouse_drag(self, event):
        """Handle mouse drag for resizing ROI selection rectangle."""
        # Only act if selection active and started correctly
        if not self.roi_selection_active or not self.roi_start_coords or not self.roi_draw_rect_id:
            return

        # Update the coordinates of the drawing rectangle
        start_x, start_y = self.roi_start_coords
        # Clamp drag position to canvas bounds for visual neatness
        curr_x = max(0, min(event.x, self.canvas.winfo_width()))
        curr_y = max(0, min(event.y, self.canvas.winfo_height()))

        # Check if canvas item still exists before configuring coords
        try:
            self.canvas.coords(self.roi_draw_rect_id, start_x, start_y, curr_x, curr_y)
        except tk.TclError:
            # Handle case where item might have been deleted unexpectedly
            self.roi_draw_rect_id = None
            self.roi_start_coords = None


    def on_mouse_up(self, event):
        """Handle mouse button release for finalizing ROI selection."""
        # Only act if selection active and started correctly
        if not self.roi_selection_active or not self.roi_start_coords or not self.roi_draw_rect_id:
            # If drag started but ended outside, or mode deactivated during drag, just cleanup
            if self.roi_draw_rect_id:
                try: self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError: pass
            self.roi_draw_rect_id = None
            self.roi_start_coords = None
            # Don't automatically deactivate ROI mode here unless error occurred
            return

        # Get final coordinates of the drawn rectangle from canvas item
        try:
            # Ensure coords returns 4 values
            coords = self.canvas.coords(self.roi_draw_rect_id)
            if len(coords) == 4:
                x1_disp, y1_disp, x2_disp, y2_disp = map(int, coords)
            else:
                raise ValueError("Invalid coordinates returned from canvas item.")
        except (tk.TclError, ValueError) as e:
            print(f"Error getting ROI rectangle coordinates: {e}")
            if self.roi_draw_rect_id:
                try: self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError: pass
            self.roi_draw_rect_id = None
            self.roi_start_coords = None
            # Deactivate ROI mode on error
            if hasattr(self, 'roi_tab'): self.roi_tab.on_roi_selection_toggled(False)
            self.roi_selection_active = False
            return

        # Clean up drawing rectangle (visual feedback)
        # Check existence before deleting
        if self.roi_draw_rect_id:
            try: self.canvas.delete(self.roi_draw_rect_id)
            except tk.TclError: pass
        self.roi_draw_rect_id = None
        self.roi_start_coords = None # Reset start coords

        # Automatically turn off ROI selection mode after definition attempt
        self.roi_selection_active = False
        if hasattr(self, 'roi_tab'): self.roi_tab.on_roi_selection_toggled(False)

        # Check if ROI is reasonably sized
        min_size = 5
        if abs(x2_disp - x1_disp) < min_size or abs(y2_disp - y1_disp) < min_size:
            messagebox.showwarning("ROI Too Small", f"The selected region is too small (min {min_size}x{min_size} pixels). Please try again.", parent=self.master)
            return # Selection mode already turned off

        # Get ROI name from entry
        roi_name = self.roi_tab.roi_name_entry.get().strip()
        original_roi_name_if_overwrite = None
        if not roi_name:
            # Find next available default name (roi_1, roi_2, ...)
            i = 1
            while f"roi_{i}" in [r.name for r in self.rois]: i += 1
            roi_name = f"roi_{i}"
        elif roi_name in [r.name for r in self.rois]:
            # Name exists, ask user to overwrite
            if not messagebox.askyesno("ROI Exists", f"An ROI named '{roi_name}' already exists. Overwrite it?", parent=self.master):
                # User chose not to overwrite, cancel ROI creation
                self.update_status("ROI creation cancelled (name exists).")
                return
            else:
                # User chose to overwrite, store name for later removal
                original_roi_name_if_overwrite = roi_name


        # --- Convert display coordinates (relative to canvas) to original frame coordinates ---
        img_x_offset = self.frame_display_coords['x']
        img_y_offset = self.frame_display_coords['y']
        img_w = self.frame_display_coords['w']
        img_h = self.frame_display_coords['h']

        # Coordinates relative to the *displayed image* top-left
        # Ensure coordinates are ordered correctly (min_x, min_y, max_x, max_y)
        rel_x1 = min(x1_disp, x2_disp) - img_x_offset
        rel_y1 = min(y1_disp, y2_disp) - img_y_offset
        rel_x2 = max(x1_disp, x2_disp) - img_x_offset
        rel_y2 = max(y1_disp, y2_disp) - img_y_offset

        # Clamp coordinates to be within the relative image bounds (0 to img_w, 0 to img_h)
        clamped_rel_x1 = max(0, min(rel_x1, img_w))
        clamped_rel_y1 = max(0, min(rel_y1, img_h))
        clamped_rel_x2 = max(0, min(rel_x2, img_w))
        clamped_rel_y2 = max(0, min(rel_y2, img_h))

        # Check again if clamping made the ROI too small
        if clamped_rel_x2 - clamped_rel_x1 < min_size or clamped_rel_y2 - clamped_rel_y1 < min_size:
            messagebox.showwarning("ROI Too Small", f"The effective region within the image is too small after clamping (min {min_size}x{min_size} pixels). Please try again.", parent=self.master)
            return

        # Convert relative coordinates back to original frame coordinates using scale
        # Handle potential zero scale factor (though unlikely if display works)
        if self.scale_x == 0 or self.scale_y == 0:
            messagebox.showerror("Error", "Image scale is zero, cannot calculate ROI coordinates.", parent=self.master)
            return

        orig_x1 = int(clamped_rel_x1 / self.scale_x)
        orig_y1 = int(clamped_rel_y1 / self.scale_y)
        orig_x2 = int(clamped_rel_x2 / self.scale_x)
        orig_y2 = int(clamped_rel_y2 / self.scale_y)

        # Final coordinates (should be ordered correctly now)
        final_x1, final_y1, final_x2, final_y2 = orig_x1, orig_y1, orig_x2, orig_y2


        # --- Create and Add/Replace ROI ---
        new_roi = ROI(roi_name, final_x1, final_y1, final_x2, final_y2)

        # If overwriting, remove the old one first
        if original_roi_name_if_overwrite:
            self.rois = [r for r in self.rois if r.name != original_roi_name_if_overwrite]
            # Remove old overlay and its settings
            if hasattr(self, 'overlay_manager'):
                if original_roi_name_if_overwrite in self.overlay_manager.overlay_settings:
                    del self.overlay_manager.overlay_settings[original_roi_name_if_overwrite]
                    # Persist removal? Only necessary if save doesn't overwrite whole dict
                    # update_settings({"overlay_settings": self.overlay_manager.overlay_settings})
                self.overlay_manager.destroy_overlay(original_roi_name_if_overwrite)


        self.rois.append(new_roi)
        print(f"Created/Updated ROI: {roi_name} ({final_x1},{final_y1}) -> ({final_x2},{final_y2})")

        # --- Update UI ---
        if hasattr(self, 'roi_tab'): self.roi_tab.update_roi_list() # Update listbox
        self._draw_rois() # Redraw ROIs including the new one on the snapshot
        # ROI selection mode was already turned off

        # Update status
        action = "created" if not original_roi_name_if_overwrite else "updated"
        self.update_status(f"ROI '{roi_name}' {action}.")

        # Automatically suggest next ROI name in the entry box
        if hasattr(self, 'roi_tab'):
            next_name_suggestion = ""
            # Prefer 'dialogue' if not present
            if "dialogue" not in [r.name for r in self.rois]:
                next_name_suggestion = "dialogue"
            else: # Find next generic 'roi_n'
                i = 1
                while f"roi_{i}" in [r.name for r in self.rois]: i += 1
                next_name_suggestion = f"roi_{i}"

            self.roi_tab.roi_name_entry.delete(0, tk.END)
            self.roi_tab.roi_name_entry.insert(0, next_name_suggestion)


        # Ensure overlay exists/is updated for the new/modified ROI
        if hasattr(self, 'overlay_manager'):
            self.overlay_manager.create_overlay_for_roi(new_roi) # Create/Recreate


    def show_floating_controls(self):
        """Creates and shows the floating control window if not already visible."""
        try:
            # Check if widget exists and hasn't been destroyed
            if self.floating_controls is None or not self.floating_controls.winfo_exists():
                print("Creating floating controls window.")
                self.floating_controls = FloatingControls(self.master, self)
            else:
                # If already exists, just bring it to front and update state
                self.floating_controls.deiconify() # Make visible if withdrawn
                self.floating_controls.lift()      # Bring to top
                self.floating_controls.update_button_states() # Sync states
            self.update_status("Floating controls shown.")
        except Exception as e:
            print(f"Error showing floating controls: {e}")
            self.update_status("Error showing floating controls.")

    def hide_floating_controls(self):
        """Hides the floating control window."""
        if self.floating_controls and self.floating_controls.winfo_exists():
            self.floating_controls.withdraw()
            self.update_status("Floating controls hidden.")


    def on_close(self):
        """Handle application closing sequence."""
        print("Close requested...")
        # Optional: Ask user for confirmation?
        # if not messagebox.askyesno("Quit", "Are you sure you want to quit?", parent=self.master):
        #     return

        # Stop capture if running
        if self.capturing:
            self.update_status("Stopping capture before closing...")
            self.stop_capture() # Initiates the stop sequence
            # Use `after` to periodically check if capture stopped before finalizing close
            self.master.after(100, self.check_capture_stopped_and_close)
        else:
            # If capture not running, proceed directly to final close
            self._finalize_close()

    def check_capture_stopped_and_close(self):
        """Check if capture thread finished before closing."""
        # Check if the capturing flag is false AND the thread reference is gone or dead
        if not self.capturing and (self.capture_thread is None or not self.capture_thread.is_alive()):
            # print("Capture confirmed stopped.")
            self._finalize_close()
        else:
            # print("Waiting a bit longer for capture thread to stop...")
            # Check again after a delay
            self.master.after(200, self.check_capture_stopped_and_close)


    def _finalize_close(self):
        """Perform final cleanup and destroy the main window."""
        print("Finalizing close...")
        # Ensure capture is definitely marked as stopped
        self.capturing = False

        # Destroy overlays and controls safely, checking existence
        if hasattr(self, 'overlay_manager'):
            self.overlay_manager.destroy_all_overlays()
        if self.floating_controls and self.floating_controls.winfo_exists():
            # Save position one last time? Already saved on release drag.
            try:
                # Only save if window is not withdrawn (geometry might be weird otherwise)
                if self.floating_controls.state() == 'normal':
                    x, y = map(int, self.floating_controls.geometry().split('+')[1:])
                    set_setting("floating_controls_pos", f"{x},{y}")
            except Exception as e:
                print(f"Could not save floating controls position on close: {e}")
            try:
                self.floating_controls.destroy()
            except tk.TclError: pass # Ignore if already destroyed

        # Optional: Save other settings explicitly if needed (most are saved incrementally)
        # update_settings({...})

        print("Exiting application.")
        try:
            # Stop the Tkinter main loop
            self.master.quit()
            # Explicitly destroy the window
            self.master.destroy()
        except tk.TclError:
            print("Main window likely already destroyed.") # Ignore error if already gone
        except Exception as e:
            print(f"Error during final window destruction: {e}")