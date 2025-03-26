import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import cv2
from PIL import Image, ImageTk
import os
import win32gui
from paddleocr import PaddleOCR

# Import utilities
from utils.capture import get_window_title, capture_window
from utils.config import load_rois
from utils.settings import load_settings
from utils.roi import ROI

# Import UI components
from ui.capture_tab import CaptureTab
from ui.roi_tab import ROITab
from ui.text_tab import TextTab, StableTextTab
from ui.translation_tab import TranslationTab

# Constants
FPS = 10
FRAME_DELAY = 1.0 / FPS

class VisualNovelTranslatorApp:
    """Main application class for the Visual Novel Translator."""

    def __init__(self, master):
        self.master = master
        master.title("Visual Novel Translator - Setup")
        master.geometry("1200x800")
        master.minsize(1000, 700)

        # Load application settings
        self.settings = load_settings()

        # Initialize variables
        self.capturing = False
        self.roi_selection_active = False
        self.selected_hwnd = None
        self.capture_thread = None
        self.rois = []
        self.current_frame = None
        self.snapshot_frame = None
        self.roi_start_x = None
        self.roi_start_y = None
        self.roi_rect = None
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.config_file = self.settings.get("last_roi_config", "vn_translator_config.json")
        self.using_snapshot = False
        self.text_history = {}
        self.stable_texts = {}
        self.stable_threshold = self.settings.get("stable_threshold", 3)
        self.max_display_width = self.settings.get("max_display_width", 800)
        self.max_display_height = self.settings.get("max_display_height", 600)

        # Setup UI
        self._setup_ui()

        # Load config
        self._load_config()

        # Initialize OCR
        lang_map = {"jpn": "japan", "jpn_vert": "japan", "eng": "en", "chi_sim": "ch", "chi_tra": "ch", "kor": "ko"}
        default_lang = self.capture_tab.lang_combo.get() if self.capture_tab.lang_combo.get() else "jpn"
        ocr_lang = lang_map.get(default_lang, "en")
        self.ocr = PaddleOCR(use_angle_cls=True, lang=ocr_lang, show_log=False)

    def _setup_ui(self):
        """Set up the UI components."""
        # Left frame for captured window preview
        self.left_frame = ttk.Frame(self.master, padding="10")
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.left_frame, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

        # Right frame with Notebook tabs
        self.right_frame = ttk.Frame(self.master, padding="10")
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False)

        self.notebook = ttk.Notebook(self.right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self.capture_tab = CaptureTab(self.notebook, self)
        self.notebook.add(self.capture_tab.frame, text="Capture")

        self.roi_tab = ROITab(self.notebook, self)
        self.notebook.add(self.roi_tab.frame, text="ROIs")

        self.text_tab = TextTab(self.notebook, self)
        self.notebook.add(self.text_tab.frame, text="Extracted Text")

        self.stable_text_tab = StableTextTab(self.notebook, self)
        self.notebook.add(self.stable_text_tab.frame, text="Stable Text")

        self.translation_tab = TranslationTab(self.notebook, self)
        self.notebook.add(self.translation_tab.frame, text="Translation")

    def _load_config(self):
        """Load the configuration files."""
        if os.path.exists(self.config_file):
            try:
                rois, config_file = load_rois(self.config_file, silent=True)
                if rois:
                    self.rois = rois
                    if config_file:
                        self.config_file = config_file
                    self.roi_tab.update_roi_list()
                    self.capture_tab.update_status(f"Loaded {len(rois)} ROIs from {config_file}")
            except Exception as e:
                self.capture_tab.update_status(f"Error loading ROIs: {str(e)}")
        else:
            self.capture_tab.update_status("No saved ROIs found. Create new ROIs when ready.")

    def start_capture(self):
        """Start capturing from the selected window."""
        selection = self.capture_tab.window_combo.get().strip()
        if not selection:
            messagebox.showwarning("Warning", "Please select a window to capture.")
            return

        try:
            hwnd = int(selection.split(":")[0])
            if not win32gui.IsWindow(hwnd):
                messagebox.showerror("Error", "Selected window does not exist.")
                return
            self.selected_hwnd = hwnd
        except Exception as e:
            messagebox.showerror("Error", f"Invalid window selection: {e}")
            return

        if self.using_snapshot:
            self.return_to_live()

        self.capturing = True
        self.capture_thread = threading.Thread(target=self.capture_process, daemon=True)
        self.capture_thread.start()

        self.capture_tab.on_capture_started()
        self.capture_tab.update_status(f"Capturing {get_window_title(self.selected_hwnd)}")

    def stop_capture(self):
        """Stop the current capture process."""
        self.capturing = False
        if self.capture_thread:
            self.capture_thread.join(timeout=1.0)
        self.capture_tab.on_capture_stopped()
        self.capture_tab.update_status("Capture stopped.")

    def take_snapshot(self):
        """Take a snapshot of the current frame."""
        if self.current_frame is None:
            messagebox.showwarning("Warning", "No frame captured yet. Start capture first.")
            return

        self.snapshot_frame = self.current_frame.copy()
        self.using_snapshot = True
        self._display_frame(self.snapshot_frame)

        self.capture_tab.on_snapshot_taken()

    def return_to_live(self):
        """Return to live view from snapshot mode."""
        self.using_snapshot = False
        self.snapshot_frame = None

        self.capture_tab.on_live_view_resumed()

    def toggle_roi_selection(self):
        """Enable or disable ROI selection mode."""
        self.roi_selection_active = not self.roi_selection_active
        self.roi_tab.on_roi_selection_toggled(self.roi_selection_active)

        if self.roi_selection_active:
            if self.current_frame is None and not self.using_snapshot:
                messagebox.showwarning("Warning", "No frame captured yet. Start capture or take a snapshot first.")
                self.roi_selection_active = False
                self.roi_tab.on_roi_selection_toggled(False)
                return

            if not self.using_snapshot and self.current_frame is not None:
                self.snapshot_frame = self.current_frame.copy()
                self.using_snapshot = True
                self._display_frame(self.snapshot_frame)
                self.capture_tab.on_snapshot_taken()
                self.capture_tab.update_status("Frame frozen for ROI selection.")
        else:
            if self.roi_rect:
                self.canvas.delete(self.roi_rect)
                self.roi_rect = None
            if self.using_snapshot:
                self.using_snapshot = False
                self.snapshot_frame = None
                self.capture_tab.on_live_view_resumed()

    def capture_process(self):
        """Background thread for continuous window capture."""
        start_time = time.time()
        while self.capturing:
            try:
                if self.using_snapshot:
                    time.sleep(FRAME_DELAY)
                    continue

                frame = capture_window(self.selected_hwnd)
                if frame is None:
                    self.capture_tab.update_status("Window closed or cannot capture.")
                    self.capturing = False
                    break

                self.current_frame = frame.copy()
                self._display_frame(frame)

                if self.rois:
                    self._process_rois()

                elapsed = time.time() - start_time
                sleep_time = FRAME_DELAY - elapsed if FRAME_DELAY - elapsed > 0 else 0
                time.sleep(sleep_time)
                start_time = time.time()
            except Exception as e:
                print(f"Capture error: {e}")
                self.capture_tab.update_status(f"Error during capture: {str(e)}")
                self.capturing = False
                break

        self.master.after(0, self.capture_tab.on_capture_stopped)

    def _display_frame(self, frame):
        """Display a frame on the canvas."""
        if frame is None:
            return

        frame_height, frame_width = frame.shape[:2]
        scale = min(self.max_display_width / frame_width, self.max_display_height / frame_height)
        new_width = int(frame_width * scale)
        new_height = int(frame_height * scale)

        self.scale_x = scale
        self.scale_y = scale

        display_frame = cv2.resize(frame, (new_width, new_height))
        display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)

        img = Image.fromarray(display_frame)
        img_tk = ImageTk.PhotoImage(image=img)

        self.canvas.config(width=new_width, height=new_height)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
        self.canvas.image = img_tk

        self._draw_rois()

    def _process_rois(self):
        """Process all ROIs in the current frame to extract text."""
        if self.current_frame is None:
            return

        extracted_texts = {}
        stable_text_changed = False

        for roi in self.rois:
            try:
                roi_img = self.current_frame[roi.y1:roi.y2, roi.x1:roi.x2]
                lang = self.capture_tab.lang_combo.get()

                # Handle OCR properly with null checks
                result = self.ocr.ocr(roi_img, cls=True)

                # Initialize empty text
                text = ""

                # Check if result is not None
                if result is not None:
                    for line in result:
                        # Some versions of PaddleOCR may return empty lists
                        if line:
                            for word_info in line:
                                if word_info and len(word_info) >= 2 and word_info[1] and len(word_info[1]) >= 1:
                                    text += word_info[1][0] + " "

                text = text.strip()
                extracted_texts[roi.name] = text

                # Update text history for stability detection
                prev_entry = self.text_history.get(roi.name, {"text": "", "count": 0})
                if text == prev_entry["text"]:
                    prev_entry["count"] += 1
                else:
                    prev_entry = {"text": text, "count": 1}

                self.text_history[roi.name] = prev_entry

                # Check if text is stable
                if prev_entry["count"] >= self.stable_threshold:
                    # Check if this is a new stable text
                    if self.stable_texts.get(roi.name) != text:
                        stable_text_changed = True
                    self.stable_texts[roi.name] = text
            except Exception as e:
                print(f"Error processing ROI {roi.name}: {e}")
                extracted_texts[roi.name] = ""

        # Update displays
        self.text_tab.update_text(extracted_texts)
        self.stable_text_tab.update_text(self.stable_texts)

        # Check if we should auto-translate
        if stable_text_changed and hasattr(self, 'translation_tab') and self.translation_tab.is_auto_translate_enabled():
            self.master.after(0, self.translation_tab.perform_translation)

    def _draw_rois(self):
        """Draw ROI rectangles on the canvas."""
        for i in range(len(self.rois)):
            self.canvas.delete(f"roi_{i}")
            self.canvas.delete(f"roi_label_{i}")

        for i, roi in enumerate(self.rois):
            x1 = int(roi.x1 * self.scale_x)
            y1 = int(roi.y1 * self.scale_y)
            x2 = int(roi.x2 * self.scale_x)
            y2 = int(roi.y2 * self.scale_y)

            self.canvas.create_rectangle(x1, y1, x2, y2, outline="green", width=2, tags=f"roi_{i}")
            self.canvas.create_text(x1+5, y1+5, text=roi.name, fill="lime", anchor=tk.NW, tags=f"roi_label_{i}")

    def on_mouse_down(self, event):
        """Handle mouse button press for ROI selection."""
        if not self.roi_selection_active:
            return

        self.roi_start_x = event.x
        self.roi_start_y = event.y
        self.roi_rect = self.canvas.create_rectangle(
            self.roi_start_x, self.roi_start_y,
            self.roi_start_x, self.roi_start_y,
            outline="red", width=2
        )

    def on_mouse_drag(self, event):
        """Handle mouse drag for ROI selection."""
        if not self.roi_selection_active or self.roi_rect is None:
            return

        self.canvas.coords(self.roi_rect, self.roi_start_x, self.roi_start_y, event.x, event.y)

    def on_mouse_up(self, event):
        """Handle mouse button release for ROI selection."""
        if not self.roi_selection_active or self.roi_rect is None:
            return

        x1, y1, x2, y2 = self.canvas.coords(self.roi_rect)
        if abs(x2 - x1) < 10 or abs(y2 - y1) < 10:
            messagebox.showwarning("Warning", "ROI too small. Please drag to create a larger region.")
            self.canvas.delete(self.roi_rect)
            self.roi_rect = None
            return

        roi_name = self.roi_tab.roi_name_entry.get().strip()
        if not roi_name:
            roi_name = f"roi_{len(self.rois) + 1}"

        orig_x1 = int(x1 / self.scale_x)
        orig_y1 = int(y1 / self.scale_y)
        orig_x2 = int(x2 / self.scale_x)
        orig_y2 = int(y2 / self.scale_y)

        new_roi = ROI(roi_name, orig_x1, orig_y1, orig_x2, orig_y2)
        self.rois.append(new_roi)

        self.roi_tab.update_roi_list()
        self.canvas.delete(self.roi_rect)
        self.roi_rect = None

        self.roi_selection_active = False
        self.roi_tab.on_roi_selection_toggled(False)

        self.using_snapshot = False
        self.snapshot_frame = None
        self.capture_tab.on_live_view_resumed()
        self.capture_tab.update_status(f"ROI '{roi_name}' created. Resumed live capture.")