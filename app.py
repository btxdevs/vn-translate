import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import cv2
from PIL import Image, ImageTk
import os
import win32gui  # Needed for IsWindow check in capture loop
from paddleocr import PaddleOCR, paddleocr
import platform
from pathlib import Path  # Import Path
import mss  # For screen capture in snip mode
import numpy as np  # For mss image conversion

# Import utilities
# Corrected import: capture_screen_region now tries direct first
from utils.capture import get_window_title, capture_window, capture_screen_region
from utils.config import load_rois, ROI_CONFIGS_DIR, _get_game_hash
# Import settings functions
from utils.settings import (
    load_settings,
    set_setting,
    get_setting,
    update_settings,
    get_overlay_config_for_roi,  # Used for both ROI and Snip config
    save_overlay_config_for_roi,
    DEFAULT_SINGLE_OVERLAY_CONFIG  # Still used if snip config load fails
)
from utils.roi import ROI
# Import translation utils
from utils.translation import CACHE_DIR, CONTEXT_DIR, _load_context, translate_text
from utils.translation import context_messages as global_context_messages

# Import UI components
from ui.capture_tab import CaptureTab
from ui.roi_tab import ROITab
from ui.text_tab import TextTab, StableTextTab
from ui.translation_tab import TranslationTab
from ui.overlay_tab import OverlayTab, SNIP_ROI_NAME  # Import special name
from ui.overlay_manager import OverlayManager
from ui.floating_overlay_window import FloatingOverlayWindow, ClosableFloatingOverlayWindow
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
        self.config_file = None

        window_title = "Visual Novel Translator"
        master.title(window_title)
        master.geometry("1200x800")
        master.minsize(1000, 700)
        master.protocol("WM_DELETE_WINDOW", self.on_close)

        # Ensure directories
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Warning: Cache dir create failed: {e}")
        try:
            ROI_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Warning: ROI Configs dir create failed: {e}")
        try:
            CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Warning: Context History dir create failed: {e}")

        # Initialize variables
        self.capturing = False
        self.roi_selection_active = False
        self.selected_hwnd = None
        self.capture_thread = None
        self.rois = []
        self.current_frame = None
        self.display_frame_tk = None
        self.snapshot_frame = None
        self.using_snapshot = False
        self.roi_start_coords = None
        self.roi_draw_rect_id = None
        self.scale_x, self.scale_y = 1.0, 1.0
        self.frame_display_coords = {'x': 0, 'y': 0, 'w': 0, 'h': 0}

        # Snip & Translate Variables
        self.snip_mode_active = False
        self.snip_overlay = None
        self.snip_canvas = None
        self.snip_start_coords = None
        self.snip_rect_id = None
        self.current_snip_window = None

        self.text_history = {}
        self.stable_texts = {}
        self.stable_threshold = get_setting("stable_threshold", 3)
        self.max_display_width = get_setting("max_display_width", 800)
        self.max_display_height = get_setting("max_display_height", 600)
        self.last_status_message = ""

        self.ocr = None
        self.ocr_lang = get_setting("ocr_language", "jpn")
        self._resize_job = None

        self._setup_ui()
        self.overlay_manager = OverlayManager(self.master, self)
        self.floating_controls = None

        initial_ocr_lang = self.ocr_lang or "jpn"
        self.update_ocr_engine(initial_ocr_lang, initial_load=True)
        self.show_floating_controls()

    def _setup_ui(self):
        """Set up the main UI layout and tabs."""
        # --- Menu Bar ---
        menu_bar = tk.Menu(self.master)
        self.master.config(menu=menu_bar)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(
            label="Save ROIs for Current Game",
            command=lambda: self.roi_tab.save_rois_for_current_game()
            if hasattr(self, 'roi_tab')
            else None,
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        window_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Window", menu=window_menu)
        window_menu.add_command(
            label="Show Floating Controls", command=self.show_floating_controls
        )

        # --- Paned Window Layout ---
        self.paned_window = ttk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left frame (Preview Canvas)
        self.left_frame = ttk.Frame(self.paned_window, padding=0)
        self.paned_window.add(self.left_frame, weight=3)
        self.canvas = tk.Canvas(self.left_frame, bg="gray15", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        # Right frame (Tabs)
        self.right_frame = ttk.Frame(self.paned_window, padding=(5, 0, 0, 0))
        self.paned_window.add(self.right_frame, weight=1)
        self.notebook = ttk.Notebook(self.right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create and add tabs
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
        self.status_bar = ttk.Label(
            self.status_bar_frame,
            text="Status: Initializing...",
            anchor=tk.W,
            padding=(5, 2),
        )
        self.status_bar.pack(fill=tk.X)
        self.update_status("Ready. Select a window.")

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
                        if (
                                hasattr(self, "capture_tab")
                                and hasattr(self.capture_tab, "status_label")
                                and self.capture_tab.status_label.winfo_exists()
                        ):
                            self.capture_tab.status_label.config(text=new_text)
                except tk.TclError:
                    pass
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
        _load_context(hwnd)  # Loads history into global list
        all_game_contexts = get_setting("game_specific_context", {})
        game_hash = _get_game_hash(hwnd) if hwnd else None
        context_text_for_ui = all_game_contexts.get(game_hash, "") if game_hash else ""
        if hasattr(self, 'translation_tab') and self.translation_tab.frame.winfo_exists():
            self.translation_tab.load_context_for_game(context_text_for_ui)
        # else: print("Translation tab not available to display context.")

    def load_rois_for_hwnd(self, hwnd):
        """Load ROIs and context automatically for the given window handle."""
        if not hwnd:
            if self.rois:
                print("Clearing ROIs as no window is selected.")
                self.rois = []
                self.config_file = None
                if hasattr(self, "roi_tab"):
                    self.roi_tab.update_roi_list()
                if hasattr(self, "overlay_manager"):
                    self.overlay_manager.rebuild_overlays()
                self.master.title("Visual Novel Translator")
                self.update_status("No window selected. ROIs cleared.")
                self._clear_text_data()
                self.load_game_context(None)
            return

        self.update_status(f"Checking for ROIs for HWND {hwnd}...")
        try:
            loaded_rois, loaded_path = load_rois(hwnd)
            if loaded_path:
                self.rois = loaded_rois
                self.config_file = loaded_path
                self.update_status(f"Loaded {len(loaded_rois)} ROIs for current game.")
                self.master.title(
                    f"Visual Novel Translator - {os.path.basename(loaded_path)}"
                )
            else:
                if self.rois:
                    print(f"No ROIs found for HWND {hwnd}. Clearing previous ROIs.")
                    self.rois = []
                    self.config_file = None
                    self.master.title("Visual Novel Translator")
                self.update_status(
                    f"No ROIs found for current game. Define new ROIs."
                )

            self.load_game_context(hwnd)  # Loads additional context text + history

            if hasattr(self, "roi_tab"):
                self.roi_tab.update_roi_list()
            if hasattr(self, "overlay_manager"):
                self.overlay_manager.rebuild_overlays()
            self._clear_text_data()

        except Exception as e:
            self.update_status(f"Error loading ROIs/Context for HWND {hwnd}: {str(e)}")
            import traceback

            traceback.print_exc()
            self.rois = []
            self.config_file = None
            if hasattr(self, "roi_tab"):
                self.roi_tab.update_roi_list()
            if hasattr(self, "overlay_manager"):
                self.overlay_manager.rebuild_overlays()
            self.master.title("Visual Novel Translator")
            self._clear_text_data()
            self.load_game_context(None)

    def _clear_text_data(self):
        """Clears text history, stable text, and updates relevant UI tabs."""
        self.text_history = {}
        self.stable_texts = {}

        # Use try-except blocks for UI updates
        def safe_update(widget, update_func, *args):
            if hasattr(self, widget) and getattr(self, widget).frame.winfo_exists():
                try:
                    update_func(*args)
                except tk.TclError:
                    pass  # Widget might be destroyed
                except Exception as e:
                    print(f"Error updating {widget}: {e}")

        safe_update("text_tab", self.text_tab.update_text, {})
        safe_update("stable_text_tab", self.stable_text_tab.update_text, {})
        if hasattr(self, "translation_tab") and self.translation_tab.frame.winfo_exists():
            try:
                self.translation_tab.translation_display.config(state=tk.NORMAL)
                self.translation_tab.translation_display.delete(1.0, tk.END)
                self.translation_tab.translation_display.config(state=tk.DISABLED)
            except tk.TclError:
                pass
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.clear_all_overlays()

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
                    self.master.after_idle(
                        lambda: self.update_status(f"OCR Ready ({lang_code}).")
                    )
                    return

            if not initial_load:
                print(f"Initializing OCR engine for {lang_code}...")
            self.master.after_idle(
                lambda: self.update_status(f"Initializing OCR ({lang_code})...")
            )

            try:
                # Consider adding use_gpu=paddleocr.is_gpu_available() if needed
                new_ocr_engine = PaddleOCR(use_angle_cls=True, lang=ocr_lang_paddle, show_log=False)
                with OCR_ENGINE_LOCK:
                    self.ocr = new_ocr_engine
                    self.ocr_lang = lang_code
                print(f"OCR engine ready for {lang_code}.")
                self.master.after_idle(
                    lambda: self.update_status(f"OCR Ready ({lang_code}).")
                )
            except Exception as e:
                print(f"!!! Error initializing PaddleOCR for lang {lang_code}: {e}")
                import traceback

                traceback.print_exc()
                self.master.after_idle(
                    lambda: self.update_status(f"OCR Error ({lang_code}): Check console")
                )
                with OCR_ENGINE_LOCK:
                    self.ocr = None

        threading.Thread(target=init_engine, daemon=True).start()

    def start_capture(self):
        """Start capturing from the selected window."""
        if self.capturing:
            return
        if not self.selected_hwnd:
            messagebox.showwarning(
                "Warning", "No visual novel window selected.", parent=self.master
            )
            return
        if not self.rois and self.selected_hwnd:
            self.load_rois_for_hwnd(self.selected_hwnd)

        with OCR_ENGINE_LOCK:
            ocr_ready = bool(self.ocr)
        if not ocr_ready:
            current_lang = self.ocr_lang or "jpn"
            self.update_ocr_engine(current_lang)
            messagebox.showinfo(
                "OCR Not Ready", "OCR is initializing...", parent=self.master
            )

        if self.using_snapshot:
            self.return_to_live()
        self.capturing = True
        self.capture_thread = threading.Thread(
            target=self.capture_process, daemon=True
        )
        self.capture_thread.start()
        if hasattr(self, "capture_tab"):
            self.capture_tab.on_capture_started()
        title = get_window_title(self.selected_hwnd) or f"HWND {self.selected_hwnd}"
        self.update_status(f"Capturing: {title}")
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
            if not getattr(self, "_finalize_stop_in_progress", False):
                self._finalize_stop_in_progress = True
                self._finalize_stop_capture()

    def _finalize_stop_capture(self):
        """Actions to perform in the main thread after capture stops."""
        try:
            if self.capturing:
                print("Warning: Finalizing stop capture while flag is still true.")
                self.capturing = False
            print("Finalizing stop capture UI updates...")
            if hasattr(self, "capture_tab") and self.capture_tab.frame.winfo_exists():
                self.capture_tab.on_capture_stopped()
            if hasattr(self, "overlay_manager"):
                self.overlay_manager.hide_all_overlays()
            self.update_status("Capture stopped.")
        finally:
            self._finalize_stop_in_progress = False

    def take_snapshot(self):
        """Take a snapshot of the current frame for static analysis."""
        if not self.capturing and self.current_frame is None:
            messagebox.showwarning(
                "Warning", "Capture not running and no frame available.", parent=self.master
            )
            return
        if self.current_frame is None:
            messagebox.showwarning(
                "Warning", "No frame captured yet.", parent=self.master
            )
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
        if self.capturing:
            title = get_window_title(self.selected_hwnd) or f"HWND {self.selected_hwnd}"
            self.update_status(f"Capturing: {title}")
        else:
            self.update_status("Capture stopped.")

    def toggle_roi_selection(self):
        """Enable or disable ROI selection mode."""
        if not self.roi_selection_active:
            if not self.selected_hwnd:
                messagebox.showwarning(
                    "Warning", "Select a game window first.", parent=self.master
                )
                return
            frame_available = self.current_frame is not None or self.snapshot_frame is not None
            if not frame_available:
                if not self.capturing:
                    print("No frame available, attempting snapshot...")
                    frame = capture_window(self.selected_hwnd)
                    if frame is not None:
                        self.current_frame = frame
                        self.take_snapshot()
                    if not self.using_snapshot:
                        messagebox.showwarning(
                            "Warning", "Could not capture frame.", parent=self.master
                        )
                        return
                else:
                    messagebox.showwarning(
                        "Warning", "Waiting for first frame.", parent=self.master
                    )
                    return

            if self.capturing and not self.using_snapshot:
                self.take_snapshot()
            if not self.using_snapshot:
                return  # Snapshot failed

            self.roi_selection_active = True
            if hasattr(self, "roi_tab"):
                self.roi_tab.on_roi_selection_toggled(True)
            # Status handled by roi_tab
        else:
            self.roi_selection_active = False
            if hasattr(self, "roi_tab"):
                self.roi_tab.on_roi_selection_toggled(False)
            if self.roi_draw_rect_id:
                try:
                    self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError:
                    pass
            self.roi_draw_rect_id = None
            self.roi_start_coords = None
            self.update_status("ROI selection cancelled.")
            if self.using_snapshot:
                self.return_to_live()

    # --- Snip & Translate Implementation ---
    def start_snip_mode(self):
        """Initiates the screen snipping process."""
        if self.snip_mode_active:
            print("Snip mode already active.")
            return

        with OCR_ENGINE_LOCK:
            if not self.ocr:
                messagebox.showwarning(
                    "OCR Not Ready", "OCR engine not initialized.", parent=self.master
                )
                return

        print("Starting Snip & Translate mode...")
        self.snip_mode_active = True
        self.update_status("Snip mode: Click and drag to select region, Esc to cancel.")

        try:
            self.snip_overlay = tk.Toplevel(self.master)
            self.snip_overlay.attributes("-fullscreen", True)
            self.snip_overlay.attributes("-alpha", 0.3)
            self.snip_overlay.overrideredirect(True)
            self.snip_overlay.attributes("-topmost", True)
            self.snip_overlay.configure(cursor="crosshair")
            self.snip_overlay.grab_set()

            self.snip_canvas = tk.Canvas(self.snip_overlay, highlightthickness=0, bg="#888888")
            self.snip_canvas.pack(fill=tk.BOTH, expand=True)
            self.snip_canvas.bind("<ButtonPress-1>", self.on_snip_mouse_down)
            self.snip_canvas.bind("<B1-Motion>", self.on_snip_mouse_drag)
            self.snip_canvas.bind("<ButtonRelease-1>", self.on_snip_mouse_up)
            self.snip_overlay.bind("<Escape>", lambda e: self.cancel_snip_mode())

            self.snip_start_coords = None
            self.snip_rect_id = None
        except Exception as e:
            print(f"Error creating snip overlay: {e}")
            self.cancel_snip_mode()

    def on_snip_mouse_down(self, event):
        if not self.snip_mode_active or not self.snip_canvas:
            return
        self.snip_start_coords = (event.x_root, event.y_root)
        if self.snip_rect_id:
            try:
                self.snip_canvas.delete(self.snip_rect_id)
            except tk.TclError:
                pass
        self.snip_rect_id = self.snip_canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="red", width=2, tags="snip_rect"
        )

    def on_snip_mouse_drag(self, event):
        if not self.snip_mode_active or not self.snip_start_coords or not self.snip_rect_id or not self.snip_canvas:
            return
        sx_root, sy_root = self.snip_start_coords
        cx_root, cy_root = event.x_root, event.y_root
        try:
            start_x = sx_root - self.snip_overlay.winfo_rootx()
            start_y = sy_root - self.snip_overlay.winfo_rooty()
            current_x = cx_root - self.snip_overlay.winfo_rootx()
            current_y = cy_root - self.snip_overlay.winfo_rooty()
            self.snip_canvas.coords(self.snip_rect_id, start_x, start_y, current_x, current_y)
        except tk.TclError:
            self.snip_rect_id = None
            self.snip_start_coords = None

    def on_snip_mouse_up(self, event):
        if not self.snip_mode_active or not self.snip_start_coords or not self.snip_rect_id or not self.snip_canvas:
            self.cancel_snip_mode()
            return
        try:
            coords = self.snip_canvas.coords(self.snip_rect_id)
            if len(coords) == 4:
                overlay_x = self.snip_overlay.winfo_rootx()
                overlay_y = self.snip_overlay.winfo_rooty()
                x1, y1, x2, y2 = (
                    int(coords[0]) + overlay_x,
                    int(coords[1]) + overlay_y,
                    int(coords[2]) + overlay_x,
                    int(coords[3]) + overlay_y,
                )
                screen_coords = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                self.finish_snip_mode(screen_coords)
            else:
                print("Invalid coordinates from snip rectangle.")
                self.cancel_snip_mode()
        except tk.TclError:
            print("Error getting snip rectangle coordinates.")
            self.cancel_snip_mode()
        except Exception as e:
            print(f"Error during snip mouse up: {e}")
            self.cancel_snip_mode()

    def cancel_snip_mode(self):
        """Cleans up the snipping overlay and resets state."""
        if not self.snip_mode_active:
            return
        print("Cancelling snip mode.")
        if self.snip_overlay and self.snip_overlay.winfo_exists():
            try:
                self.snip_overlay.grab_release()
                self.snip_overlay.destroy()
            except tk.TclError:
                pass
        self.snip_overlay = None
        self.snip_canvas = None
        self.snip_start_coords = None
        self.snip_rect_id = None
        self.snip_mode_active = False
        self.master.configure(cursor="")
        self.update_status("Snip mode cancelled.")

    def finish_snip_mode(self, screen_coords):
        """Processes the selected region after snipping."""
        x1, y1, x2, y2 = screen_coords
        width, height = x2 - x1, y2 - y1
        min_snip_size = 5
        if width < min_snip_size or height < min_snip_size:
            messagebox.showwarning(
                "Snip Too Small",
                f"Selected region too small (min {min_snip_size}x{min_snip_size} px).",
                parent=self.master,
            )
            self.cancel_snip_mode()
            return

        monitor = {"left": x1, "top": y1, "width": width, "height": height}
        # Clean up UI *before* starting processing
        if self.snip_overlay and self.snip_overlay.winfo_exists():
            try:
                self.snip_overlay.grab_release()
                self.snip_overlay.destroy()
            except tk.TclError:
                pass
        self.snip_overlay = None
        self.snip_canvas = None
        self.snip_start_coords = None
        self.snip_rect_id = None
        self.snip_mode_active = False
        self.master.configure(cursor="")
        self.update_status("Processing snipped region...")
        print(f"Snipped region (Screen Coords): {monitor}")
        threading.Thread(target=self._process_snip_thread, args=(monitor,), daemon=True).start()

    def _process_snip_thread(self, screen_region):
        """Background thread to capture, OCR, and translate the snipped region."""
        try:
            # 1. Capture Screen Region (now tries direct first)
            img_bgr = capture_screen_region(screen_region)
            if img_bgr is None:
                self.master.after_idle(
                    lambda: self.update_status("Snip Error: Failed to capture region.")
                )
                return

            # 2. Perform OCR
            with OCR_ENGINE_LOCK:
                ocr_engine_instance = self.ocr
            if not ocr_engine_instance:
                self.master.after_idle(
                    lambda: self.update_status("Snip Error: OCR engine not ready.")
                )
                return

            print("[Snip OCR] Running OCR...")
            ocr_result_raw = ocr_engine_instance.ocr(img_bgr, cls=True)
            text_lines = []
            if ocr_result_raw and isinstance(ocr_result_raw, list) and len(ocr_result_raw) > 0:
                current_result_set = (
                    ocr_result_raw[0]
                    if isinstance(ocr_result_raw[0], list)
                    else ocr_result_raw
                )
                if current_result_set:
                    for item in current_result_set:
                        text_info = None
                        if isinstance(item, list) and len(item) >= 2:
                            text_info = item[1]
                        elif isinstance(item, tuple) and len(item) >= 2:
                            text_info = item
                        if (
                                isinstance(text_info, (tuple, list))
                                and len(text_info) >= 1
                                and text_info[0]
                        ):
                            text_lines.append(str(text_info[0]))
            extracted_text = " ".join(text_lines).strip()
            print(f"[Snip OCR] Extracted: '{extracted_text}'")

            if not extracted_text:
                self.master.after_idle(
                    lambda: self.update_status("Snip: No text found in region.")
                )
                self.master.after_idle(
                    lambda: self.display_snip_translation("[No text found]", screen_region)
                )
                return

            # 3. Translate Text (no cache, no history)
            config = (
                self.translation_tab.get_translation_config()
                if hasattr(self, "translation_tab")
                else None
            )
            if not config:
                self.master.after_idle(
                    lambda: self.update_status("Snip Error: Translation config unavailable.")
                )
                return

            # Format as single 'snip' ROI for translation function
            aggregated_input_snip = f"[snip]: {extracted_text}"
            print("[Snip Translate] Translating...")
            translation_result = translate_text(
                aggregated_input_text=aggregated_input_snip,
                hwnd=None,  # Indicate no specific game window
                preset=config,
                target_language=config["target_language"],
                additional_context=config["additional_context"],
                context_limit=config.get("context_limit", 10),
                skip_cache=True,  # DO NOT CACHE
                skip_history=True,  # DO NOT SAVE TO HISTORY
            )

            final_text = "[Translation Error]"
            if isinstance(translation_result, dict):
                if "error" in translation_result:
                    final_text = f"Error: {translation_result['error']}"
                elif "snip" in translation_result:
                    final_text = translation_result["snip"]
                elif translation_result:
                    final_text = next(iter(translation_result.values()), "[Parsing Failed]")

            print(f"[Snip Translate] Result: '{final_text}'")
            self.master.after_idle(
                lambda: self.update_status("Snip translation complete.")
            )
            self.master.after_idle(
                lambda: self.display_snip_translation(final_text, screen_region)
            )

        except Exception as e:
            error_msg = f"Error processing snip: {e}"
            print(error_msg)
            import traceback

            traceback.print_exc()
            self.master.after_idle(
                lambda: self.update_status(f"Snip Error: {error_msg[:60]}...")
            )
            self.master.after_idle(
                lambda: self.display_snip_translation(f"[Error: {error_msg}]", screen_region)
            )

    def display_snip_translation(self, text, region):
        """Displays the snipped translation in a temporary floating window."""
        # Destroy previous snip window
        if self.current_snip_window and self.current_snip_window.winfo_exists():
            try:
                self.current_snip_window.destroy_window()
            except tk.TclError:
                pass
        self.current_snip_window = None

        try:
            # --- Get config for the special snip window ---
            snip_config = get_overlay_config_for_roi(SNIP_ROI_NAME)
            # Ensure it's treated as enabled for display purposes
            snip_config["enabled"] = True

            self.current_snip_window = ClosableFloatingOverlayWindow(
                self.master,
                roi_name=SNIP_ROI_NAME,  # Use the special name
                initial_config=snip_config,
                manager_ref=None,  # Not managed by OverlayManager
            )

            # Position near the snipped region
            pos_x = region["left"] + region["width"] + 10
            pos_y = region["top"] + region["height"] - 30
            win_width_req = self.current_snip_window.winfo_reqwidth()
            win_height_req = self.current_snip_window.winfo_reqheight()
            screen_width = self.master.winfo_screenwidth()
            screen_height = self.master.winfo_screenheight()
            if pos_x + win_width_req > screen_width:
                pos_x = region["left"] - win_width_req - 10
            if pos_y + win_height_req > screen_height:
                pos_y = screen_height - win_height_req - 10
            pos_x = max(0, pos_x)
            pos_y = max(0, pos_y)

            # Use configured geometry ONLY if explicitly saved for snip? No, position dynamically.
            # If geometry WAS saved for snip (undesirable), ignore it here.
            # Default size is handled by window itself based on config's wraplength.
            self.current_snip_window.geometry(f"+{pos_x}+{pos_y}")

            # Set text and show (bypassing global toggle)
            self.current_snip_window.update_text(text, global_overlays_enabled=True)

        except Exception as e:
            print(f"Error creating snip result window: {e}")
            import traceback

            traceback.print_exc()
            if self.current_snip_window:
                try:
                    self.current_snip_window.destroy_window()
                except Exception:
                    pass
            self.current_snip_window = None
            messagebox.showerror(
                "Snip Error",
                f"Could not display snip result:\n{e}",
                parent=self.master,
            )

    # --- End Snip & Translate ---

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
                if not self.selected_hwnd or not win32gui.IsWindow(self.selected_hwnd):
                    print("Capture target window lost. Stopping.")
                    self.master.after_idle(self.handle_capture_failure)
                    break
                frame = capture_window(self.selected_hwnd)
                if frame is None:
                    print("Warning: capture_window returned None.")
                    time.sleep(0.5)
                    continue
                self.current_frame = frame
                frame_to_display = frame

                with OCR_ENGINE_LOCK:
                    ocr_engine_instance = self.ocr
                if self.rois and ocr_engine_instance:
                    self._process_rois(frame, ocr_engine_instance)

                current_time = time.time()
                if current_time - last_frame_time >= target_sleep_time:
                    if frame_to_display is not None:
                        frame_copy = frame_to_display.copy()
                        self.master.after_idle(lambda f=frame_copy: self._display_frame(f))
                    last_frame_time = current_time

                elapsed = time.time() - loop_start_time
                sleep_duration = max(0.001, target_sleep_time - elapsed)
                time.sleep(sleep_duration)
            except Exception as e:
                print(f"!!! Error in capture loop: {e}")
                import traceback

                traceback.print_exc()
                self.master.after_idle(
                    lambda msg=str(e): self.update_status(f"Capture loop error: {msg[:60]}...")
                )
                time.sleep(1)
        print("Capture thread finished or exited.")

    def handle_capture_failure(self):
        """Called from main thread if capture fails definitively."""
        if self.capturing:
            self.update_status("Window lost or uncapturable. Stopping capture.")
            print("Failed to capture the selected window.")
            self.stop_capture()

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
                        cw / 2,
                        ch / 2,
                        text="No Image\n(Select Window & Start)",
                        fill="gray50",
                        tags="display_content",
                        justify=tk.CENTER,
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
            img = Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))
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
                    current_result_set = (
                        ocr_result_raw[0]
                        if isinstance(ocr_result_raw[0], list)
                        else ocr_result_raw
                    )
                    if current_result_set:
                        for item in current_result_set:
                            text_info = None
                            if isinstance(item, list) and len(item) >= 2:
                                text_info = item[1]
                            elif isinstance(item, tuple) and len(item) >= 2:
                                text_info = item
                            if isinstance(text_info, (tuple, list)) and len(text_info) >= 1 and text_info[0]:
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
                    if roi.name in new_stable:
                        del new_stable[roi.name]
                        stable_changed = True
            except Exception as e:
                print(f"!!! OCR Error for ROI {roi.name}: {e}")
                extracted[roi.name] = "[OCR Error]"
                self.text_history[roi.name] = {"text": "[OCR Error]", "count": 1}
                if roi.name in new_stable:
                    del new_stable[roi.name]
                    stable_changed = True

        # Schedule UI updates safely
        if hasattr(self, "text_tab") and self.text_tab.frame.winfo_exists():
            self.master.after_idle(lambda et=extracted.copy(): self.text_tab.update_text(et))
        if stable_changed:
            self.stable_texts = new_stable
            if hasattr(self, "stable_text_tab") and self.stable_text_tab.frame.winfo_exists():
                self.master.after_idle(
                    lambda st=self.stable_texts.copy(): self.stable_text_tab.update_text(st)
                )
            if (
                    hasattr(self, "translation_tab")
                    and self.translation_tab.frame.winfo_exists()
                    and self.translation_tab.is_auto_translate_enabled()
            ):
                if any(self.stable_texts.values()):
                    self.master.after_idle(self.translation_tab.perform_translation)
                else:
                    if hasattr(self, "overlay_manager"):
                        self.master.after_idle(self.overlay_manager.clear_all_overlays)
                    if hasattr(self, "translation_tab"):
                        self.master.after_idle(
                            lambda: self.translation_tab.update_translation_results({}, "[No stable text]")
                        )

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
                self.canvas.create_rectangle(dx1, dy1, dx2, dy2, outline="lime", width=1, tags=("display_content", f"roi_{i}"))
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

    def on_mouse_down(self, event):
        """Start ROI definition drag."""
        if not self.roi_selection_active or not self.using_snapshot:
            return
        img_x, img_y = self.frame_display_coords["x"], self.frame_display_coords["y"]
        img_w, img_h = self.frame_display_coords["w"], self.frame_display_coords["h"]
        if not (img_x <= event.x < img_x + img_w and img_y <= event.y < img_y + img_h):
            self.roi_start_coords = None
            if self.roi_draw_rect_id:
                try:
                    self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError:
                    pass
            self.roi_draw_rect_id = None
            return
        self.roi_start_coords = (event.x, event.y)
        if self.roi_draw_rect_id:
            try:
                self.canvas.delete(self.roi_draw_rect_id)
            except tk.TclError:
                pass
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
        cx = max(img_x, min(event.x, img_x + img_w))
        cy = max(img_y, min(event.y, img_y + img_h))
        try:
            clamped_sx = max(img_x, min(sx, img_x + img_w))
            clamped_sy = max(img_y, min(sy, img_y + img_h))
            self.canvas.coords(self.roi_draw_rect_id, clamped_sx, clamped_sy, cx, cy)
        except tk.TclError:
            self.roi_draw_rect_id = None
            self.roi_start_coords = None

    def on_mouse_up(self, event):
        """Finalize ROI definition on mouse release."""
        if not self.roi_selection_active or not self.roi_start_coords or not self.roi_draw_rect_id:
            if self.roi_draw_rect_id:
                try:
                    self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError:
                    pass
            self.roi_draw_rect_id = None
            self.roi_start_coords = None
            return
        try:
            coords = self.canvas.coords(self.roi_draw_rect_id)
        except tk.TclError:
            coords = None
        if self.roi_draw_rect_id:
            try:
                self.canvas.delete(self.roi_draw_rect_id)
            except tk.TclError:
                pass
        self.roi_draw_rect_id = None
        self.roi_start_coords = None
        self.roi_selection_active = False
        if hasattr(self, "roi_tab"):
            self.roi_tab.on_roi_selection_toggled(False)

        if coords is None or len(coords) != 4:
            print("ROI definition failed (invalid coords).")
            return
        x1d, y1d, x2d, y2d = map(int, coords)
        min_size = 5
        if abs(x2d - x1d) < min_size or abs(y2d - y1d) < min_size:
            messagebox.showwarning(
                "ROI Too Small",
                f"Min {min_size}x{min_size} px required.",
                parent=self.master,
            )
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
            if not messagebox.askyesno(
                    "ROI Exists", f"Overwrite ROI '{roi_name}'?", parent=self.master
            ):
                return
            overwrite_name = roi_name
        elif roi_name == SNIP_ROI_NAME:  # Prevent using the special name
            messagebox.showerror(
                "Invalid Name",
                f"Cannot use reserved name '{SNIP_ROI_NAME}'.",
                parent=self.master,
            )
            return

        ox, oy = self.frame_display_coords["x"], self.frame_display_coords["y"]
        rx1, ry1 = min(x1d, x2d) - ox, min(y1d, y2d) - oy
        rx2, ry2 = max(x1d, x2d) - ox, max(y1d, y2d) - oy
        if self.scale_x <= 0 or self.scale_y <= 0:
            print("Error: Invalid scale factor.")
            return
        ox1, oy1 = int(rx1 / self.scale_x), int(ry1 / self.scale_y)
        ox2, oy2 = int(rx2 / self.scale_x), int(ry2 / self.scale_y)
        if abs(ox2 - ox1) < 1 or abs(oy2 - oy1) < 1:
            messagebox.showwarning(
                "ROI Too Small", "Calculated ROI size too small.", parent=self.master
            )
            return

        new_roi = ROI(roi_name, ox1, oy1, ox2, oy2)
        if overwrite_name:
            self.rois = [r for r in self.rois if r.name != overwrite_name]
        self.rois.append(new_roi)
        print(f"Created/Updated ROI: {new_roi.to_dict()}")
        if hasattr(self, "roi_tab"):
            self.roi_tab.update_roi_list()
        self._draw_rois()
        action = "created" if not overwrite_name else "updated"
        self.update_status(f"ROI '{roi_name}' {action}. Remember to save.")

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
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.create_overlay_for_roi(new_roi)
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
            self.update_status("Error showing controls.")

    def hide_floating_controls(self):
        """Hides the floating control window."""
        if self.floating_controls and self.floating_controls.winfo_exists():
            self.floating_controls.withdraw()

    def on_close(self):
        """Handle application closing."""
        print("Close requested...")
        if self.snip_mode_active:
            self.cancel_snip_mode()
        if self.current_snip_window and self.current_snip_window.winfo_exists():
            try:
                self.current_snip_window.destroy_window()
            except Exception:
                pass
            self.current_snip_window = None
        if self.capturing:
            self.update_status("Stopping capture before closing...")
            self.stop_capture()
            self.master.after(500, self.check_capture_stopped_and_close)
        else:
            self._finalize_close()

    def check_capture_stopped_and_close(self):
        """Check if capture stopped before finalizing close."""
        if not self.capturing and (self.capture_thread is None or not self.capture_thread.is_alive()):
            self._finalize_close()
        else:
            print("Waiting for capture thread...")
            self.master.after(500, self.check_capture_stopped_and_close)

    def _finalize_close(self):
        """Final cleanup and destroy window."""
        print("Finalizing close...")
        self.capturing = False
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.destroy_all_overlays()
        if self.floating_controls and self.floating_controls.winfo_exists():
            try:
                # Save position
                if self.floating_controls.state() == "normal":
                    geo = self.floating_controls.geometry()
                    parts = geo.split("+")
                    if len(parts) == 3:
                        x_str, y_str = parts[1], parts[2]
                        if x_str.isdigit() and y_str.isdigit():
                            set_setting("floating_controls_pos", f"{x_str},{y_str}")
                        else:
                            print(f"Warn: Invalid float coords: {geo}")
                    else:
                        print(f"Warn: Could not parse float geo: {geo}")
            except Exception as e:
                print(f"Error saving float pos: {e}")
            try:
                self.floating_controls.destroy()
            except tk.TclError:
                pass
        if self.current_snip_window and self.current_snip_window.winfo_exists():
            try:
                self.current_snip_window.destroy_window()
            except Exception:
                pass
        print("Exiting application.")
        try:
            self.master.quit()
            self.master.destroy()
        except tk.TclError:
            pass
        except Exception as e:
            print(f"Error during final destruction: {e}")


# --- END OF FILE app.py ---
