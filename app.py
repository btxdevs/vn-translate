import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import cv2
import numpy as np
from PIL import Image, ImageTk
import os
import win32gui

from utils.capture import get_window_title, capture_window, capture_screen_region
from utils.config import load_rois, ROI_CONFIGS_DIR, _get_game_hash
from utils.settings import load_settings, set_setting, get_setting, get_overlay_config_for_roi
from utils.roi import ROI
from utils.translation import CACHE_DIR, CONTEXT_DIR, _load_context, translate_text
import utils.ocr as ocr

from ui.capture_tab import CaptureTab
from ui.roi_tab import ROITab
from ui.text_tab import TextTab, StableTextTab
from ui.translation_tab import TranslationTab
from ui.overlay_tab import OverlayTab, SNIP_ROI_NAME
from ui.overlay_manager import OverlayManager
from ui.floating_overlay_window import FloatingOverlayWindow, ClosableFloatingOverlayWindow
from ui.floating_controls import FloatingControls
from ui.preview_window import PreviewWindow
from ui.color_picker import ScreenColorPicker

FPS = 10
FRAME_DELAY = 1.0 / FPS


class VisualNovelTranslatorApp:
    def __init__(self, master):
        self.master = master
        self.settings = load_settings()
        self.config_file = None

        master.title("Visual Novel Translator")
        master.geometry("1200x800")
        master.minsize(1000, 700)
        master.protocol("WM_DELETE_WINDOW", self.on_close)
        self._ensure_dirs()

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
        self.frame_display_coords = {"x": 0, "y": 0, "w": 0, "h": 0}

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

        self.ocr_engine_type = get_setting("ocr_engine", "paddle")
        self.ocr_lang = get_setting("ocr_language", "jpn")
        self.ocr_engine_ready = False
        self._ocr_init_thread = None

        self._resize_job = None

        self._setup_ui()
        self.overlay_manager = OverlayManager(self.master, self)
        self.floating_controls = None

        self._trigger_ocr_initialization(self.ocr_engine_type, self.ocr_lang, initial_load=True)
        self.show_floating_controls()

    def _ensure_dirs(self):
        for d in [CACHE_DIR, ROI_CONFIGS_DIR, CONTEXT_DIR]:
            try:
                d.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"Warning: Failed to create directory {d}: {e}")

    def _setup_ui(self):
        menu_bar = tk.Menu(self.master)
        self.master.config(menu=menu_bar)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(
            label="Save All ROI Settings for Current Game",
            command=lambda: self.roi_tab.save_rois_for_current_game() if hasattr(self, "roi_tab") else None,
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)

        window_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Window", menu=window_menu)
        window_menu.add_command(label="Show Floating Controls", command=self.show_floating_controls)

        self.paned_window = ttk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.left_frame = ttk.Frame(self.paned_window, padding=0)
        self.paned_window.add(self.left_frame, weight=3)
        self.canvas = tk.Canvas(self.left_frame, bg="gray15", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        self.right_frame = ttk.Frame(self.paned_window, padding=(5, 0, 0, 0))
        self.paned_window.add(self.right_frame, weight=1)
        self.notebook = ttk.Notebook(self.right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
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
        def _do_update():
            if hasattr(self, "status_bar") and self.status_bar.winfo_exists():
                new_text = f"Status: {message}"
                if new_text != self.status_bar.cget("text"):
                    self.status_bar.config(text=new_text)
                    self.last_status_message = message
                    if (
                            hasattr(self, "capture_tab")
                            and hasattr(self.capture_tab, "status_label")
                            and self.capture_tab.status_label.winfo_exists()
                    ):
                        self.capture_tab.status_label.config(text=new_text)
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
        _load_context(hwnd)
        all_game_contexts = get_setting("game_specific_context", {})
        game_hash = _get_game_hash(hwnd) if hwnd else None
        context_text_for_ui = all_game_contexts.get(game_hash, "") if game_hash else ""
        if hasattr(self, "translation_tab") and self.translation_tab.frame.winfo_exists():
            self.translation_tab.load_context_for_game(context_text_for_ui)

    def load_rois_for_hwnd(self, hwnd):
        if not hwnd:
            if self.rois:
                self.rois = []
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
            if loaded_path is not None:
                self.rois = loaded_rois
                self.config_file = loaded_path
                if loaded_rois:
                    self.update_status(f"Loaded {len(loaded_rois)} ROIs for current game.")
                    self.master.title(f"Visual Novel Translator - {os.path.basename(loaded_path)}")
                else:
                    self.update_status("ROI config found but empty/invalid. Define new ROIs.")
                    self.master.title(f"Visual Novel Translator - {os.path.basename(loaded_path)}")
            else:
                if self.rois:
                    self.rois = []
                    self.config_file = None
                    self.master.title("Visual Novel Translator")
                self.update_status("No ROIs found for current game. Define new ROIs.")
            self.load_game_context(hwnd)
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
        self.text_history = {}
        self.stable_texts = {}

        def safe_update(widget_attr_name, update_method_name, *args):
            widget = getattr(self, widget_attr_name, None)
            if widget and hasattr(widget, "frame") and widget.frame.winfo_exists():
                update_method = getattr(widget, update_method_name, None)
                if update_method:
                    try:
                        update_method(*args)
                    except Exception:
                        pass

        safe_update("text_tab", "update_text", {})
        safe_update("stable_text_tab", "update_text", {})
        if hasattr(self, "translation_tab") and self.translation_tab.frame.winfo_exists():
            try:
                self.translation_tab.translation_display.config(state=tk.NORMAL)
                self.translation_tab.translation_display.delete(1.0, tk.END)
                self.translation_tab.translation_display.config(state=tk.DISABLED)
            except tk.TclError:
                pass
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.clear_all_overlays()

    def _trigger_ocr_initialization(self, engine_type, lang_code, initial_load=False):
        if self._ocr_init_thread and self._ocr_init_thread.is_alive():
            return

        self.ocr_engine_ready = False
        status_msg = f"Initializing OCR ({engine_type}/{lang_code})..."
        if not initial_load:
            print(status_msg)
        self.update_status(status_msg)

        def init_task():
            try:
                dummy_img = np.zeros((10, 10, 3), dtype=np.uint8)
                ocr.extract_text(dummy_img, lang=lang_code, engine_type=engine_type)
                self.ocr_engine_ready = True
                success_msg = f"OCR Ready ({engine_type}/{lang_code})."
                print(success_msg)
                self.master.after_idle(lambda: self.update_status(success_msg))
            except Exception as e:
                self.ocr_engine_ready = False
                error_msg = f"OCR Error ({engine_type}/{lang_code}): {str(e)[:60]}..."
                print(f"Error during OCR initialization: {e}")
                self.master.after_idle(lambda: self.update_status(error_msg))

        self._ocr_init_thread = threading.Thread(target=init_task, daemon=True)
        self._ocr_init_thread.start()

    def set_ocr_engine(self, engine_type, lang_code):
        if engine_type == self.ocr_engine_type:
            self._trigger_ocr_initialization(engine_type, lang_code)
            return
        self.ocr_engine_type = engine_type
        set_setting("ocr_engine", engine_type)
        self._trigger_ocr_initialization(engine_type, lang_code)

    def update_ocr_language(self, lang_code, engine_type):
        if lang_code == self.ocr_lang and self.ocr_engine_ready and engine_type == self.ocr_engine_type:
            return
        self.ocr_lang = lang_code
        set_setting("ocr_language", lang_code)
        self._trigger_ocr_initialization(engine_type, lang_code)

    def update_stable_threshold(self, new_value):
        try:
            new_threshold = int(float(new_value))
            if new_threshold >= 1 and self.stable_threshold != new_threshold:
                self.stable_threshold = new_threshold
                if set_setting("stable_threshold", new_threshold):
                    self.update_status(f"Stability threshold set to {new_threshold}.")
                else:
                    self.update_status("Error saving stability threshold.")
        except (ValueError, TypeError):
            print(f"Ignored invalid threshold value: {new_value}")

    def start_capture(self):
        if self.capturing:
            return
        if not self.selected_hwnd:
            messagebox.showwarning("Warning", "No visual novel window selected.", parent=self.master)
            return
        if not self.rois and self.selected_hwnd:
            self.load_rois_for_hwnd(self.selected_hwnd)
        if not self.ocr_engine_ready:
            self._trigger_ocr_initialization(self.ocr_engine_type, self.ocr_lang)
            messagebox.showinfo(
                "OCR Not Ready",
                f"OCR ({self.ocr_engine_type}/{self.ocr_lang}) is initializing...",
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
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.rebuild_overlays()

    def stop_capture(self):
        if not self.capturing:
            return
        self.capturing = False
        self.master.after(100, self._check_thread_and_finalize_stop)

    def _check_thread_and_finalize_stop(self):
        if self.capture_thread and self.capture_thread.is_alive():
            self.master.after(100, self._check_thread_and_finalize_stop)
        else:
            self.capture_thread = None
            if not getattr(self, "_finalize_stop_in_progress", False):
                self._finalize_stop_in_progress = True
                self._finalize_stop_capture()

    def _finalize_stop_capture(self):
        try:
            if self.capturing:
                self.capturing = False
            if hasattr(self, "capture_tab") and self.capture_tab.frame.winfo_exists():
                self.capture_tab.on_capture_stopped()
            if hasattr(self, "overlay_manager"):
                self.overlay_manager.hide_all_overlays()
            self.update_status("Capture stopped.")
        finally:
            self._finalize_stop_in_progress = False

    def take_snapshot(self):
        if self.current_frame is None:
            if self.capturing:
                messagebox.showwarning("Warning", "Waiting for first frame to capture.", parent=self.master)
            else:
                messagebox.showwarning("Warning", "Start capture or select window first.", parent=self.master)
            return
        self.snapshot_frame = self.current_frame.copy()
        self.using_snapshot = True
        self._display_frame(self.snapshot_frame)
        if hasattr(self, "capture_tab"):
            self.capture_tab.on_snapshot_taken()
        self.update_status("Snapshot taken. Define ROIs or return to live.")

    def return_to_live(self):
        if not self.using_snapshot:
            return
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
        if not self.roi_selection_active:
            if not self.selected_hwnd:
                messagebox.showwarning("Warning", "Select a game window first.", parent=self.master)
                return
            frame_available = self.current_frame is not None or self.snapshot_frame is not None
            if not frame_available:
                if not self.capturing:
                    frame = capture_window(self.selected_hwnd)
                    if frame is not None:
                        self.current_frame = frame
                        self.take_snapshot()
                    if not self.using_snapshot:
                        messagebox.showwarning("Warning", "Could not capture frame for ROI definition.", parent=self.master)
                        return
                else:
                    messagebox.showwarning("Warning", "Waiting for first frame to be captured.", parent=self.master)
                    return
            if self.capturing and not self.using_snapshot:
                self.take_snapshot()
            if not self.using_snapshot:
                return
            self.roi_selection_active = True
            if hasattr(self, "roi_tab"):
                self.roi_tab.on_roi_selection_toggled(True)
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

    def start_snip_mode(self):
        if self.snip_mode_active:
            return
        if not self.ocr_engine_ready:
            messagebox.showwarning(
                "OCR Not Ready",
                f"OCR engine ({self.ocr_engine_type}/{self.ocr_lang}) not initialized. Cannot use Snip & Translate.",
                parent=self.master,
            )
            return
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
        try:
            sx_root, sy_root = self.snip_start_coords
            start_x_canvas = sx_root - self.snip_overlay.winfo_rootx()
            start_y_canvas = sy_root - self.snip_overlay.winfo_rooty()
        except (tk.TclError, TypeError):
            self.snip_rect_id = None
            self.snip_start_coords = None
            return
        try:
            self.snip_canvas.coords(self.snip_rect_id, start_x_canvas, start_y_canvas, event.x, event.y)
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
                x1_screen = int(coords[0]) + overlay_x
                y1_screen = int(coords[1]) + overlay_y
                x2_screen = int(coords[2]) + overlay_x
                y2_screen = int(coords[3]) + overlay_y
                screen_coords_tuple = (
                    min(x1_screen, x2_screen),
                    min(y1_screen, y2_screen),
                    max(x1_screen, x2_screen),
                    max(y1_screen, y2_screen),
                )
                self.finish_snip_mode(screen_coords_tuple)
            else:
                self.cancel_snip_mode()
        except Exception as e:
            print(f"Error during snip mouse up: {e}")
            self.cancel_snip_mode()

    def cancel_snip_mode(self):
        if not self.snip_mode_active:
            return
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

    def finish_snip_mode(self, screen_coords_tuple):
        x1, y1, x2, y2 = screen_coords_tuple
        width = x2 - x1
        height = y2 - y1
        if width < 5 or height < 5:
            messagebox.showwarning("Snip Too Small", "Selected region too small (min 5x5 px).", parent=self.master)
            self.cancel_snip_mode()
            return
        monitor_region = {"left": x1, "top": y1, "width": width, "height": height}
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
        threading.Thread(target=self._process_snip_thread, args=(monitor_region,), daemon=True).start()

    def _process_snip_thread(self, screen_region):
        try:
            img_bgr = capture_screen_region(screen_region)
            if img_bgr is None:
                self.master.after_idle(lambda: self.update_status("Snip Error: Failed to capture region."))
                return
            if not self.ocr_engine_ready:
                self.master.after_idle(
                    lambda: self.update_status(f"Snip Error: OCR ({self.ocr_engine_type}/{self.ocr_lang}) not ready.")
                )
                return
            extracted_text = ocr.extract_text(img_bgr, lang=self.ocr_lang, engine_type=self.ocr_engine_type)
            if extracted_text.startswith("[") and "Error]" in extracted_text:
                self.master.after_idle(lambda: self.update_status(f"Snip: {extracted_text}"))
                self.master.after_idle(lambda: self.display_snip_translation(extracted_text, screen_region))
                return
            if not extracted_text:
                self.master.after_idle(lambda: self.update_status("Snip: No text found in region."))
                self.master.after_idle(lambda: self.display_snip_translation("[No text found]", screen_region))
                return
            config = self.translation_tab.get_translation_config() if hasattr(self, "translation_tab") else None
            if not config:
                self.master.after_idle(lambda: self.update_status("Snip Error: Translation config unavailable."))
                self.master.after_idle(lambda: self.display_snip_translation("[Translation Config Error]", screen_region))
                return
            snip_tag_name = "_snip_translate"
            aggregated_input_snip = f"[{snip_tag_name}]: {extracted_text}"
            translation_result = translate_text(
                aggregated_input_text=aggregated_input_snip,
                hwnd=None,
                preset=config,
                target_language=config["target_language"],
                additional_context=config["additional_context"],
                context_limit=0,
                skip_cache=True,
                skip_history=True,
            )
            final_text = "[Translation Error]"
            if isinstance(translation_result, dict):
                if "error" in translation_result:
                    final_text = f"Error: {translation_result['error']}"
                elif snip_tag_name in translation_result:
                    final_text = translation_result[snip_tag_name]
                elif len(translation_result) == 1:
                    final_text = next(iter(translation_result.values()), "[Parsing Failed]")
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
        if self.current_snip_window and self.current_snip_window.winfo_exists():
            try:
                self.current_snip_window.destroy_window()
            except tk.TclError:
                pass
        self.current_snip_window = None
        try:
            snip_config = get_overlay_config_for_roi(SNIP_ROI_NAME)
            snip_config["enabled"] = True
            self.current_snip_window = ClosableFloatingOverlayWindow(
                self.master, roi_name=SNIP_ROI_NAME, initial_config=snip_config, manager_ref=None
            )
            pos_x = region["left"] + region["width"] + 10
            pos_y = region["top"]
            self.current_snip_window.update_idletasks()
            win_width = self.current_snip_window.winfo_width()
            win_height = self.current_snip_window.winfo_height()
            screen_width = self.master.winfo_screenwidth()
            screen_height = self.master.winfo_screenheight()
            if pos_x + win_width > screen_width:
                pos_x = region["left"] - win_width - 10
            if pos_y + win_height > screen_height:
                pos_y = screen_height - win_height - 10
            pos_x = max(0, pos_x)
            pos_y = max(0, pos_y)
            self.current_snip_window.geometry(f"+{pos_x}+{pos_y}")
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
            messagebox.showerror("Snip Error", f"Could not display snip result:\n{e}", parent=self.master)

    def capture_process(self):
        last_frame_time = time.time()
        target_sleep_time = FRAME_DELAY
        while self.capturing:
            loop_start_time = time.time()
            frame_to_display = None
            try:
                if self.using_snapshot:
                    time.sleep(0.05)
                    continue
                if not self.selected_hwnd or not win32gui.IsWindow(self.selected_hwnd):
                    self.master.after_idle(self.handle_capture_failure)
                    break
                frame = capture_window(self.selected_hwnd)
                if frame is None:
                    time.sleep(0.5)
                    continue
                self.current_frame = frame
                frame_to_display = frame
                if self.rois and self.ocr_engine_ready:
                    self._process_rois(frame)
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
                import traceback

                traceback.print_exc()
                self.master.after_idle(lambda msg=str(e): self.update_status(f"Capture loop error: {msg[:60]}..."))
                time.sleep(1)
        print("Capture thread finished.")

    def handle_capture_failure(self):
        if self.capturing:
            self.update_status("Window lost or uncapturable. Stopping capture.")
            self.stop_capture()

    def on_canvas_resize(self, event=None):
        if self._resize_job:
            self.master.after_cancel(self._resize_job)
        self._resize_job = self.master.after(100, self._perform_resize_redraw)

    def _perform_resize_redraw(self):
        self._resize_job = None
        if not self.canvas.winfo_exists():
            return
        frame = self.snapshot_frame if self.using_snapshot else self.current_frame
        self._display_frame(frame)

    def _display_frame(self, frame):
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
                        text="No Image\n(Select Window & Start Capture)",
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
            try:
                cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
                self.canvas.create_text(cw / 2, ch / 2, text=f"Display Error:\n{e}", fill="red", tags="display_content")
            except Exception:
                pass

    def _process_rois(self, frame):
        if frame is None or not self.ocr_engine_ready:
            return
        extracted = {}
        stable_changed = False
        new_stable = self.stable_texts.copy()
        for roi in self.rois:
            if roi.name == SNIP_ROI_NAME:
                continue
            roi_img_original = roi.extract_roi(frame)
            roi_img_processed = roi.apply_color_filter(roi_img_original)
            if roi_img_processed is None or roi_img_processed.size == 0:
                extracted[roi.name] = ""
                if roi.name in self.text_history:
                    del self.text_history[roi.name]
                if roi.name in new_stable:
                    del new_stable[roi.name]
                    stable_changed = True
                continue
            try:
                text = ocr.extract_text(roi_img_processed, lang=self.ocr_lang, engine_type=self.ocr_engine_type)
                extracted[roi.name] = text
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
                    if not was_stable or current_stable_text != text:
                        new_stable[roi.name] = text
                        stable_changed = True
                elif was_stable:
                    if roi.name in new_stable:
                        del new_stable[roi.name]
                        stable_changed = True
            except Exception as e:
                print(f"OCR Error for ROI {roi.name}: {e}")
                extracted[roi.name] = "[OCR Error]"
                self.text_history[roi.name] = {"text": "[OCR Error]", "count": 1}
                if roi.name in new_stable:
                    del new_stable[roi.name]
                    stable_changed = True
        if hasattr(self, "text_tab") and self.text_tab.frame.winfo_exists():
            self.master.after_idle(lambda et=extracted.copy(): self.text_tab.update_text(et))
        if stable_changed:
            self.stable_texts = new_stable
            if hasattr(self, "stable_text_tab") and self.stable_text_tab.frame.winfo_exists():
                self.master.after_idle(lambda st=self.stable_texts.copy(): self.stable_text_tab.update_text(st))
            if (
                    hasattr(self, "translation_tab")
                    and self.translation_tab.frame.winfo_exists()
                    and self.translation_tab.is_auto_translate_enabled()
            ):
                user_roi_names = {roi.name for roi in self.rois if roi.name != SNIP_ROI_NAME}
                all_rois_are_stable = bool(user_roi_names) and user_roi_names.issubset(self.stable_texts.keys())
                if all_rois_are_stable:
                    self.master.after_idle(self.translation_tab.perform_translation)
                else:
                    if not self.stable_texts:
                        if hasattr(self, "overlay_manager"):
                            self.master.after_idle(self.overlay_manager.clear_all_overlays)
                        if hasattr(self, "translation_tab"):
                            self.master.after_idle(lambda: self.translation_tab.update_translation_results({}, "[Waiting for stable text...]"))

    def _draw_rois(self):
        if not hasattr(self, "canvas") or not self.canvas.winfo_exists() or self.frame_display_coords["w"] <= 0:
            return
        ox, oy = self.frame_display_coords["x"], self.frame_display_coords["y"]
        self.canvas.delete("roi_drawing")
        for i, roi in enumerate(self.rois):
            if roi.name == SNIP_ROI_NAME:
                continue
            try:
                dx1 = int(roi.x1 * self.scale_x) + ox
                dy1 = int(roi.y1 * self.scale_y) + oy
                dx2 = int(roi.x2 * self.scale_x) + ox
                dy2 = int(roi.y2 * self.scale_y) + oy
                self.canvas.create_rectangle(
                    dx1, dy1, dx2, dy2, outline="lime", width=1, tags=("display_content", "roi_drawing", f"roi_{i}")
                )
                self.canvas.create_text(
                    dx1 + 3,
                    dy1 + 1,
                    text=roi.name,
                    fill="lime",
                    anchor=tk.NW,
                    font=("TkDefaultFont", 8),
                    tags=("display_content", "roi_drawing", f"roi_label_{i}"),
                    )
            except Exception as e:
                print(f"Error drawing ROI {roi.name}: {e}")

    def on_mouse_down(self, event):
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
        if not self.roi_selection_active or not self.roi_start_coords or not self.roi_draw_rect_id:
            if self.roi_draw_rect_id:
                try:
                    self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError:
                    pass
            self.roi_draw_rect_id = None
            self.roi_start_coords = None
            if self.roi_selection_active:
                self.roi_selection_active = False
                if hasattr(self, "roi_tab"):
                    self.roi_tab.on_roi_selection_toggled(False)
                if self.using_snapshot:
                    self.return_to_live()
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
        self.roi_selection_active = False
        if hasattr(self, "roi_tab"):
            self.roi_tab.on_roi_selection_toggled(False)
        if coords is None or len(coords) != 4:
            if self.using_snapshot:
                self.return_to_live()
            return

        x1d, y1d, x2d, y2d = map(int, coords)
        if abs(x2d - x1d) < 5 or abs(y2d - y1d) < 5:
            messagebox.showwarning("ROI Too Small", "Defined region too small (min 5x5 px required).", parent=self.master)
            if self.using_snapshot:
                self.return_to_live()
            return

        roi_name = self.roi_tab.roi_name_entry.get().strip()
        overwrite_name = None
        existing_names = {r.name for r in self.rois if r.name != SNIP_ROI_NAME}
        if not roi_name:
            i = 1
            roi_name = f"roi_{i}"
            while roi_name in existing_names:
                i += 1
                roi_name = f"roi_{i}"
        elif roi_name in existing_names:
            if not messagebox.askyesno("ROI Exists", f"An ROI named '{roi_name}' already exists. Overwrite it?", parent=self.master):
                if self.using_snapshot:
                    self.return_to_live()
                return
            overwrite_name = roi_name
        elif roi_name == SNIP_ROI_NAME:
            messagebox.showerror("Invalid Name", f"Cannot use the reserved name '{SNIP_ROI_NAME}'. Please choose another.", parent=self.master)
            if self.using_snapshot:
                self.return_to_live()
            return

        ox, oy = self.frame_display_coords["x"], self.frame_display_coords["y"]
        rx1, ry1 = min(x1d, x2d) - ox, min(y1d, y2d) - oy
        rx2, ry2 = max(x1d, x2d) - ox, max(y1d, y2d) - oy
        if self.scale_x <= 0 or self.scale_y <= 0:
            if self.using_snapshot:
                self.return_to_live()
            return
        orig_x1, orig_y1 = int(rx1 / self.scale_x), int(ry1 / self.scale_y)
        orig_x2, orig_y2 = int(rx2 / self.scale_x), int(ry2 / self.scale_y)
        if abs(orig_x2 - orig_x1) < 1 or abs(orig_y2 - orig_y1) < 1:
            messagebox.showwarning("ROI Too Small", "Calculated ROI size is too small in original frame.", parent=self.master)
            if self.using_snapshot:
                self.return_to_live()
            return
        new_roi = ROI(roi_name, orig_x1, orig_y1, orig_x2, orig_y2)
        if overwrite_name:
            found = False
            for i, r in enumerate(self.rois):
                if r.name == overwrite_name:
                    new_roi.color_filter_enabled = r.color_filter_enabled
                    new_roi.target_color = r.target_color
                    new_roi.replacement_color = r.replacement_color
                    new_roi.color_threshold = r.color_threshold
                    self.rois[i] = new_roi
                    found = True
                    break
            if not found:
                self.rois.append(new_roi)
        else:
            self.rois.append(new_roi)
        self.update_status(f"ROI '{roi_name}' {'updated' if overwrite_name else 'created'}. Remember to save ROI settings.")

        if hasattr(self, "roi_tab"):
            existing_names_now = {r.name for r in self.rois if r.name != SNIP_ROI_NAME}
            next_name = "dialogue" if "dialogue" not in existing_names_now else ""
            if not next_name:
                i = 1
                next_name = f"roi_{i}"
                while next_name in existing_names_now:
                    i += 1
                    next_name = f"roi_{i}"
            self.roi_tab.roi_name_entry.delete(0, tk.END)
            self.roi_tab.roi_name_entry.insert(0, next_name)
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.create_overlay_for_roi(new_roi)
        if self.using_snapshot:
            self.return_to_live()

    def show_floating_controls(self):
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
        if self.floating_controls and self.floating_controls.winfo_exists():
            self.floating_controls.withdraw()

    def on_close(self):
        if self.snip_mode_active:
            self.cancel_snip_mode()
        if self.roi_selection_active:
            self.toggle_roi_selection()
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
        if not self.capturing and (self.capture_thread is None or not self.capture_thread.is_alive()):
            self._finalize_close()
        else:
            self.master.after(500, self.check_capture_stopped_and_close)

    def _finalize_close(self):
        self.capturing = False
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.destroy_all_overlays()
        if self.floating_controls and self.floating_controls.winfo_exists():
            try:
                if self.floating_controls.state() == "normal":
                    geo = self.floating_controls.geometry()
                    parts = geo.split("+")
                    if len(parts) == 3:
                        x_str, y_str = parts[1], parts[2]
                        if x_str.isdigit() and y_str.isdigit():
                            set_setting("floating_controls_pos", f"{x_str},{y_str}")
            except Exception as e:
                print(f"Error saving floating controls position: {e}")
            try:
                self.floating_controls.destroy()
            except tk.TclError:
                pass
        if self.current_snip_window and self.current_snip_window.winfo_exists():
            try:
                self.current_snip_window.destroy_window()
            except Exception:
                pass
        try:
            self.master.quit()
            self.master.destroy()
        except Exception:
            pass