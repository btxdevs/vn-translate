Okay, this involves changes across several files to integrate the color filtering logic, UI configuration, and preview functionality.

Here are the full contents of the modified files:

**1. `utils/roi.py` (Updated)**

```python
# --- START OF FILE roi.py ---

import cv2
import numpy as np
import tkinter as tk # Added for color conversion

class ROI:
    def __init__(self, name, x1, y1, x2, y2,
                 color_filter_enabled=False, target_color=(255, 255, 255), color_threshold=30):
        self.name = name
        self.x1 = min(x1, x2)
        self.y1 = min(y1, y2)
        self.x2 = max(x1, x2)
        self.y2 = max(y1, y2)
        # Color Filtering Attributes
        self.color_filter_enabled = color_filter_enabled
        # Store target_color consistently as an RGB tuple (int, int, int)
        if isinstance(target_color, str):
             # Attempt conversion from hex if needed (e.g., from old format)
             try:
                 hex_color = target_color.lstrip('#')
                 self.target_color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
             except:
                 self.target_color = (255, 255, 255) # Default fallback
        elif isinstance(target_color, (list, tuple)) and len(target_color) == 3:
             self.target_color = tuple(int(c) for c in target_color)
        else:
             self.target_color = (255, 255, 255) # Default fallback

        try:
            self.color_threshold = int(color_threshold)
        except (ValueError, TypeError):
            self.color_threshold = 30

    def to_dict(self):
        return {
            "name": self.name,
            "x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2,
            "color_filter_enabled": self.color_filter_enabled,
            "target_color": self.target_color, # Save as RGB tuple
            "color_threshold": self.color_threshold
        }

    @classmethod
    def from_dict(cls, data):
        # Provide defaults for backward compatibility
        color_filter_enabled = data.get("color_filter_enabled", False)
        target_color = data.get("target_color", (255, 255, 255)) # Expecting RGB tuple
        color_threshold = data.get("color_threshold", 30)
        return cls(data["name"], data["x1"], data["y1"], data["x2"], data["y2"],
                   color_filter_enabled, target_color, color_threshold)

    def extract_roi(self, frame):
        """Extracts the ROI portion from the frame."""
        try:
            h, w = frame.shape[:2]
            # Ensure coordinates are within frame bounds
            y1 = max(0, int(self.y1))
            y2 = min(h, int(self.y2))
            x1 = max(0, int(self.x1))
            x2 = min(w, int(self.x2))
            # Check for invalid dimensions after clamping
            if y1 >= y2 or x1 >= x2:
                # print(f"Warning: ROI '{self.name}' has invalid dimensions after clamping ({x1},{y1} to {x2},{y2}).")
                return None
            return frame[y1:y2, x1:x2]
        except Exception as e:
            print(f"Error extracting ROI image for {self.name}: {e}")
            return None

    def apply_color_filter(self, roi_img):
        """Applies color filtering to the extracted ROI image if enabled."""
        if not self.color_filter_enabled or roi_img is None:
            return roi_img

        try:
            # Target color is stored as RGB, convert to BGR for OpenCV
            target_bgr = self.target_color[::-1]
            thresh = self.color_threshold

            # Calculate lower and upper bounds in BGR
            lower_bound = np.array([max(0, c - thresh) for c in target_bgr], dtype=np.uint8)
            upper_bound = np.array([min(255, c + thresh) for c in target_bgr], dtype=np.uint8)

            # Create a mask where pixels are within the threshold
            mask = cv2.inRange(roi_img, lower_bound, upper_bound)

            # Create a black background image
            # background = np.zeros_like(roi_img) # Option 1: Black background
            background = np.full_like(roi_img, (255, 255, 255)) # Option 2: White background (often better for OCR)


            # Copy only the pixels within the mask from the original ROI to the background
            # This keeps the original color of the matching pixels
            filtered_img = cv2.bitwise_and(roi_img, roi_img, mask=mask)

            # Combine the filtered pixels with the inverse mask of the background
            # Pixels outside the mask will take the background color
            background_masked = cv2.bitwise_and(background, background, mask=cv2.bitwise_not(mask))
            result_img = cv2.add(filtered_img, background_masked)


            # --- Alternative: Make non-matching pixels black ---
            # result_img = roi_img.copy()
            # result_img[mask == 0] = [0, 0, 0] # Set non-matching pixels to black
            # ---

            return result_img

        except Exception as e:
            print(f"Error applying color filter for ROI {self.name}: {e}")
            return roi_img # Return original on error

    def get_overlay_config(self, global_settings):
        # This remains unchanged, deals only with overlay appearance
        from ui.overlay_manager import OverlayManager # Keep import local if needed
        # Find the OverlayManager's default config if possible, otherwise use a hardcoded one
        try:
            defaults = OverlayManager.DEFAULT_OVERLAY_CONFIG.copy()
        except AttributeError:
             # Fallback if OverlayManager or its constant isn't available yet
             defaults = {
                 "enabled": True, "font_family": "Segoe UI", "font_size": 14,
                 "font_color": "white", "bg_color": "#222222", "alpha": 1.0,
                 "wraplength": 450, "justify": "left", "geometry": None
             }

        roi_specific_settings = global_settings.get('overlay_settings', {}).get(self.name, {})
        config = defaults.copy()
        config.update(roi_specific_settings)
        return config

    @staticmethod
    def rgb_to_hex(rgb_tuple):
        """Converts an (R, G, B) tuple to #RRGGBB hex string."""
        try:
            return f"#{int(rgb_tuple[0]):02x}{int(rgb_tuple[1]):02x}{int(rgb_tuple[2]):02x}"
        except:
            return "#FFFFFF" # Fallback

    @staticmethod
    def hex_to_rgb(hex_string):
        """Converts an #RRGGBB hex string to (R, G, B) tuple."""
        try:
            hex_color = hex_string.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        except:
            return (255, 255, 255) # Fallback

# --- END OF FILE roi.py ---
```

**2. `utils/config.py` (Updated)**

```python
# --- START OF FILE config.py ---

import json
import os
import tkinter.messagebox as messagebox
from utils.roi import ROI # Ensure ROI class is imported
from utils.settings import set_setting, get_setting # Keep these if still used elsewhere
from utils.capture import get_executable_details
import hashlib
from pathlib import Path

PRESETS_FILE = "translation_presets.json"
APP_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROI_CONFIGS_DIR = APP_DIR / "roi_configs"

def _ensure_roi_configs_dir():
    try:
        ROI_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error creating ROI configs directory {ROI_CONFIGS_DIR}: {e}")

def _get_game_hash(hwnd):
    # This function remains the same
    exe_path, file_size = get_executable_details(hwnd)
    if exe_path and file_size is not None:
        try:
            # Normalize path separators and case for consistency
            identity_string = f"{os.path.normpath(exe_path).lower()}|{file_size}"
            hasher = hashlib.sha256()
            hasher.update(identity_string.encode('utf-8'))
            return hasher.hexdigest()
        except Exception as e:
            print(f"Error generating game hash: {e}")
    return None

def _get_roi_config_path(hwnd):
    # This function remains the same
    game_hash = _get_game_hash(hwnd)
    if game_hash:
        return ROI_CONFIGS_DIR / f"{game_hash}_rois.json"
    else:
        print("Warning: Could not determine game hash for ROI config path.")
        return None

def save_rois(rois, hwnd):
    """Saves the list of ROI objects to a game-specific JSON file."""
    if not hwnd:
        messagebox.showerror("Error", "Cannot save ROIs: No game window selected.")
        return None
    # Allow saving an empty list to clear config for a game
    # if not rois:
    #     messagebox.showwarning("Warning", "No ROIs defined to save.")
    #     return None

    _ensure_roi_configs_dir()
    save_path = _get_roi_config_path(hwnd)
    if not save_path:
        messagebox.showerror("Error", "Could not determine game-specific file path to save ROIs.")
        return None

    try:
        # Use the updated ROI.to_dict() which includes color filter settings
        roi_data = [roi.to_dict() for roi in rois]
        with open(save_path, 'w', encoding="utf-8") as f:
            json.dump(roi_data, f, indent=2)
        print(f"ROIs saved successfully for current game to {save_path.name}")
        return str(save_path)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save ROIs to {save_path.name}: {str(e)}")
        return None

def load_rois(hwnd):
    """Loads ROIs from a game-specific JSON file."""
    if not hwnd:
        print("Cannot load ROIs: No game window handle provided.")
        return [], None # Return empty list and None path

    _ensure_roi_configs_dir()
    load_path = _get_roi_config_path(hwnd)
    rois = []
    if not load_path:
        print("Could not determine game-specific file path to load ROIs.")
        return [], None # Return empty list and None path

    if load_path.exists():
        try:
            with open(load_path, 'r', encoding="utf-8") as f:
                content = f.read()
                if not content.strip(): # Handle empty file
                    print(f"ROI config file found but empty: {load_path.name}")
                    return [], str(load_path) # Return empty list but valid path

                roi_data = json.loads(content)
                if not isinstance(roi_data, list):
                     print(f"Error: ROI config file {load_path.name} does not contain a list.")
                     return [], str(load_path) # Return empty list but valid path

            # Use the updated ROI.from_dict() which handles missing color filter keys
            rois = [ROI.from_dict(data) for data in roi_data]
            print(f"ROIs loaded successfully for current game from {load_path.name}")
            return rois, str(load_path)

        except json.JSONDecodeError as e:
             messagebox.showerror("Error", f"Failed to load ROIs from '{load_path.name}': Invalid JSON - {str(e)}")
             return [], None # Indicate load failure
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load ROIs from '{load_path.name}': {str(e)}")
            return [], None # Indicate load failure
    else:
        print(f"No ROI config file found for current game ({load_path.name}).")
        return [], None # No file found, return empty list and None path

# --- Translation Preset functions remain the same ---
def save_translation_presets(presets, file_path=PRESETS_FILE):
    try:
        preset_path_obj = Path(file_path)
        preset_path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(preset_path_obj, "w", encoding="utf-8") as f:
            json.dump(presets, f, indent=2)
        print(f"Translation presets saved to {file_path}")
        return True
    except Exception as e:
        print(f"Error saving translation presets: {e}")
        messagebox.showerror("Error", f"Failed to save translation presets: {e}")
        return False

def load_translation_presets(file_path=PRESETS_FILE):
    preset_path_obj = Path(file_path)
    if preset_path_obj.exists():
        try:
            with open(preset_path_obj, "r", encoding="utf-8") as f:
                content = f.read()
                if not content:
                    return {} # Return empty dict for empty file
                return json.loads(content)
        except json.JSONDecodeError:
            print(f"Error: Translation presets file '{file_path}' is corrupted or empty.")
            messagebox.showerror("Preset Load Error", f"Could not load presets from '{file_path}'. File might be corrupted.")
            return {}
        except Exception as e:
            print(f"Error loading translation presets: {e}")
            messagebox.showerror("Error", f"Failed to load translation presets: {e}.")
            return {} # Return empty dict on other errors
    return {} # Return empty dict if file doesn't exist

# --- END OF FILE config.py ---
```

**3. `ui/roi_tab.py` (Updated)**

```python
# --- START OF FILE roi_tab.py ---

import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
from ui.base import BaseTab
from utils.config import save_rois
from utils.settings import get_overlay_config_for_roi, update_settings, get_setting # Keep settings import if needed elsewhere
from utils.roi import ROI # Import ROI for color conversion
from ui.overlay_tab import SNIP_ROI_NAME
from ui.preview_window import PreviewWindow # Import the new preview window
from ui.color_picker import ScreenColorPicker # Import the screen color picker
import os
import cv2 # Needed for preview generation

class ROITab(BaseTab):
    def setup_ui(self):
        # --- Main ROI definition and list ---
        roi_frame = ttk.LabelFrame(self.frame, text="Regions of Interest (ROIs)", padding="10")
        roi_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        # Top part: Create ROI
        create_frame = ttk.Frame(roi_frame)
        create_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(create_frame, text="New ROI Name:").pack(side=tk.LEFT, anchor=tk.W, pady=(5, 0), padx=(0, 5))
        self.roi_name_entry = ttk.Entry(create_frame, width=15)
        self.roi_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=(5, 0))
        self.roi_name_entry.insert(0, "dialogue")
        self.create_roi_btn = ttk.Button(create_frame, text="Define ROI", command=self.app.toggle_roi_selection)
        self.create_roi_btn.pack(side=tk.LEFT, padx=(5, 0), pady=(5, 0))
        ttk.Label(roi_frame, text="Click 'Define ROI', then click and drag on the image preview.", font=('TkDefaultFont', 8)).pack(anchor=tk.W, pady=(0, 5))

        # Middle part: List and management buttons
        list_manage_frame = ttk.Frame(roi_frame)
        list_manage_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # ROI Listbox
        list_frame = ttk.Frame(list_manage_frame)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        ttk.Label(list_frame, text="Current Game ROIs ([O]=Overlay, [C]=Color Filter):").pack(anchor=tk.W)
        roi_scrollbar = ttk.Scrollbar(list_frame)
        roi_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.roi_listbox = tk.Listbox(list_frame, height=6, selectmode=tk.SINGLE, exportselection=False, yscrollcommand=roi_scrollbar.set)
        self.roi_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        roi_scrollbar.config(command=self.roi_listbox.yview)
        self.roi_listbox.bind("<<ListboxSelect>>", self.on_roi_selected)

        # Management Buttons (Up/Down/Delete/Overlay Config)
        manage_btn_frame = ttk.Frame(list_manage_frame)
        manage_btn_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(5, 0))
        self.move_up_btn = ttk.Button(manage_btn_frame, text="▲ Up", width=8, command=self.move_roi_up, state=tk.DISABLED)
        self.move_up_btn.pack(pady=2, anchor=tk.N)
        self.move_down_btn = ttk.Button(manage_btn_frame, text="▼ Down", width=8, command=self.move_roi_down, state=tk.DISABLED)
        self.move_down_btn.pack(pady=2, anchor=tk.N)
        self.delete_roi_btn = ttk.Button(manage_btn_frame, text="Delete", width=8, command=self.delete_selected_roi, state=tk.DISABLED)
        self.delete_roi_btn.pack(pady=(10, 2), anchor=tk.N)
        self.config_overlay_btn = ttk.Button(manage_btn_frame, text="Overlay...", width=8, command=self.configure_selected_overlay, state=tk.DISABLED)
        self.config_overlay_btn.pack(pady=(5, 2), anchor=tk.N)

        # --- Color Filter Configuration ---
        self.color_filter_frame = ttk.LabelFrame(self.frame, text="Color Filtering (for selected ROI)", padding="10")
        self.color_filter_frame.pack(fill=tk.X, pady=(5, 5))
        self.color_widgets = {} # Dictionary to hold color filter widgets

        # Enable Checkbox
        self.color_widgets['enabled_var'] = tk.BooleanVar(value=False)
        self.color_widgets['enabled_check'] = ttk.Checkbutton(
            self.color_filter_frame, text="Enable Color Filter", variable=self.color_widgets['enabled_var']
        )
        self.color_widgets['enabled_check'].grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=(0, 5))

        # Target Color
        ttk.Label(self.color_filter_frame, text="Target Color:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=2)
        self.color_widgets['target_color_var'] = tk.StringVar(value="#FFFFFF") # Store as hex for UI
        self.color_widgets['target_color_label'] = ttk.Label(self.color_filter_frame, text="       ", background="#FFFFFF", relief=tk.SUNKEN, width=8)
        self.color_widgets['target_color_label'].grid(row=1, column=1, sticky=tk.W, pady=2)
        self.color_widgets['pick_color_btn'] = ttk.Button(self.color_filter_frame, text="Pick...", width=6, command=self.pick_color)
        self.color_widgets['pick_color_btn'].grid(row=1, column=2, padx=(5, 2), pady=2)
        self.color_widgets['pick_screen_btn'] = ttk.Button(self.color_filter_frame, text="Screen", width=7, command=self.pick_color_from_screen)
        self.color_widgets['pick_screen_btn'].grid(row=1, column=3, padx=(2, 0), pady=2)

        # Threshold
        ttk.Label(self.color_filter_frame, text="Threshold:").grid(row=2, column=0, sticky=tk.W, padx=(0, 5), pady=2)
        self.color_widgets['threshold_var'] = tk.IntVar(value=30)
        self.color_widgets['threshold_scale'] = ttk.Scale(
            self.color_filter_frame, from_=0, to=100, orient=tk.HORIZONTAL,
            variable=self.color_widgets['threshold_var'], length=150,
            command=lambda v: self.color_widgets['threshold_label_var'].set(f"{int(float(v))}")
        )
        self.color_widgets['threshold_scale'].grid(row=2, column=1, columnspan=2, sticky=tk.EW, pady=2)
        self.color_widgets['threshold_label_var'] = tk.StringVar(value="30")
        ttk.Label(self.color_filter_frame, textvariable=self.color_widgets['threshold_label_var'], width=4).grid(row=2, column=3, sticky=tk.W, padx=(5, 0), pady=2)

        # Apply & Preview Buttons
        color_btn_frame = ttk.Frame(self.color_filter_frame)
        color_btn_frame.grid(row=3, column=0, columnspan=4, pady=(10, 0))
        self.color_widgets['apply_btn'] = ttk.Button(color_btn_frame, text="Apply Filter Settings", command=self.apply_color_filter_settings)
        self.color_widgets['apply_btn'].pack(side=tk.LEFT, padx=5)
        self.color_widgets['preview_orig_btn'] = ttk.Button(color_btn_frame, text="Preview Original", command=self.show_original_preview)
        self.color_widgets['preview_orig_btn'].pack(side=tk.LEFT, padx=5)
        self.color_widgets['preview_filter_btn'] = ttk.Button(color_btn_frame, text="Preview Filtered", command=self.show_filtered_preview)
        self.color_widgets['preview_filter_btn'].pack(side=tk.LEFT, padx=5)

        # --- Bottom part: Save All ROIs ---
        file_btn_frame = ttk.Frame(self.frame) # Place it directly in self.frame now
        file_btn_frame.pack(fill=tk.X, pady=(5, 10))
        self.save_rois_btn = ttk.Button(file_btn_frame, text="Save All ROI Settings for Current Game", command=self.save_rois_for_current_game)
        self.save_rois_btn.pack(side=tk.LEFT, padx=5)

        # Initial state
        self.update_roi_list()
        self.set_color_filter_widgets_state(tk.DISABLED)

    def set_color_filter_widgets_state(self, state):
        """Enable or disable all widgets in the color filter frame."""
        if not hasattr(self, 'color_filter_frame') or not self.color_filter_frame.winfo_exists():
            return
        valid_states = (tk.NORMAL, tk.DISABLED)
        actual_state = state if state in valid_states else tk.DISABLED
        scale_state = tk.NORMAL if actual_state == tk.NORMAL else tk.DISABLED

        try:
            for widget in self.color_filter_frame.winfo_children():
                widget_class = widget.winfo_class()
                # Handle container frames like the button frame
                if isinstance(widget, (ttk.Frame, tk.Frame)):
                     for sub_widget in widget.winfo_children():
                         sub_widget_class = sub_widget.winfo_class()
                         try:
                             if sub_widget_class in ('TButton', 'TCheckbutton'):
                                 sub_widget.configure(state=actual_state)
                         except tk.TclError: pass
                # Handle direct children
                elif widget_class in ('TButton', 'TCheckbutton'):
                    widget.configure(state=actual_state)
                elif widget_class in ('Scale', 'TScale'):
                     widget.configure(state=scale_state)
                # Labels are usually kept enabled, but could be disabled too
                # elif widget_class in ('TLabel', 'Label'):
                #    widget.configure(state=actual_state)
        except tk.TclError:
            print("TclError setting color filter widget state (widgets might be closing).")
        except Exception as e:
            print(f"Error setting color filter widget state: {e}")


    def on_roi_selected(self, event=None):
        selection = self.roi_listbox.curselection()
        has_selection = bool(selection)
        num_items = self.roi_listbox.size()
        idx = selection[0] if has_selection else -1

        # Update Up/Down/Delete/Overlay buttons
        self.move_up_btn.config(state=tk.NORMAL if has_selection and idx > 0 else tk.DISABLED)
        self.move_down_btn.config(state=tk.NORMAL if has_selection and idx < num_items - 1 else tk.DISABLED)
        self.delete_roi_btn.config(state=tk.NORMAL if has_selection else tk.DISABLED)
        can_config_overlay = has_selection and hasattr(self.app, 'overlay_tab') and self.app.overlay_tab.frame.winfo_exists()
        self.config_overlay_btn.config(state=tk.NORMAL if can_config_overlay else tk.DISABLED)

        # Update Color Filter section
        if has_selection:
            roi = self.get_selected_roi_object()
            if roi:
                self.load_color_filter_settings(roi)
                self.set_color_filter_widgets_state(tk.NORMAL)
            else:
                # Should not happen if listbox selection is valid, but handle defensively
                self.set_color_filter_widgets_state(tk.DISABLED)
        else:
            self.set_color_filter_widgets_state(tk.DISABLED)

    def get_selected_roi_object(self):
        """Gets the ROI object corresponding to the listbox selection."""
        selection = self.roi_listbox.curselection()
        if not selection:
            return None
        try:
            listbox_text = self.roi_listbox.get(selection[0])
            # Extract name carefully, considering prefixes like [O] [C]
            roi_name = listbox_text.split("]")[-1].strip()
            return next((r for r in self.app.rois if r.name == roi_name), None)
        except (tk.TclError, IndexError, StopIteration):
            return None

    def load_color_filter_settings(self, roi):
        """Loads the color filter settings from the ROI object into the UI."""
        if not roi or not hasattr(self, 'color_widgets'):
            return
        try:
            self.color_widgets['enabled_var'].set(roi.color_filter_enabled)
            hex_color = ROI.rgb_to_hex(roi.target_color)
            self.color_widgets['target_color_var'].set(hex_color)
            self.color_widgets['target_color_label'].config(background=hex_color)
            self.color_widgets['threshold_var'].set(roi.color_threshold)
            self.color_widgets['threshold_label_var'].set(str(roi.color_threshold))
        except tk.TclError:
             print("TclError loading color filter settings (widget might be destroyed).")
        except Exception as e:
             print(f"Error loading color filter settings for {roi.name}: {e}")

    def apply_color_filter_settings(self):
        """Applies the UI settings to the selected in-memory ROI object."""
        roi = self.get_selected_roi_object()
        if not roi:
            messagebox.showwarning("Warning", "No ROI selected to apply settings to.", parent=self.app.master)
            return

        try:
            roi.color_filter_enabled = self.color_widgets['enabled_var'].get()
            hex_color = self.color_widgets['target_color_var'].get()
            roi.target_color = ROI.hex_to_rgb(hex_color) # Store as RGB tuple
            roi.color_threshold = self.color_widgets['threshold_var'].get()

            # Update the listbox display immediately
            self.update_roi_list()

            self.app.update_status(f"Color filter settings updated for '{roi.name}'. (Save ROIs to persist)")
            print(f"Applied in-memory color settings for {roi.name}: enabled={roi.color_filter_enabled}, color={roi.target_color}, thresh={roi.color_threshold}")

        except tk.TclError:
             messagebox.showerror("Error", "Could not read settings from UI (widgets might be destroyed).", parent=self.app.master)
        except Exception as e:
             messagebox.showerror("Error", f"Failed to apply color filter settings: {e}", parent=self.app.master)

    def pick_color(self):
        """Opens a color chooser dialog to select the target color."""
        roi = self.get_selected_roi_object()
        if not roi: return

        initial_color_hex = self.color_widgets['target_color_var'].get()
        try:
             # askcolor returns ((r,g,b), hex) or (None, None)
             color_code = colorchooser.askcolor(title="Choose Target Color",
                                                initialcolor=initial_color_hex,
                                                parent=self.app.master)
             if color_code and color_code[1]: # Check if a color was chosen (hex is not None)
                 new_hex_color = color_code[1]
                 self.color_widgets['target_color_var'].set(new_hex_color)
                 self.color_widgets['target_color_label'].config(background=new_hex_color)
                 # Optionally apply immediately to the ROI object, or wait for "Apply" button
                 # roi.target_color = ROI.hex_to_rgb(new_hex_color)
                 # print(f"Color picked for {roi.name}: {new_hex_color}")
        except Exception as e:
             messagebox.showerror("Color Picker Error", f"Failed to open color picker: {e}", parent=self.app.master)

    def pick_color_from_screen(self):
        """Starts the screen color picking process."""
        roi = self.get_selected_roi_object()
        if not roi:
            messagebox.showwarning("Warning", "Select an ROI first.", parent=self.app.master)
            return

        self.app.update_status("Screen Color Picker: Click anywhere on screen (Esc to cancel).")
        # Hide the main window temporarily to avoid picking from it? Optional.
        # self.app.master.withdraw()
        picker = ScreenColorPicker(self.app.master)
        picker.grab_color(self._on_screen_color_picked)

    def _on_screen_color_picked(self, color_rgb):
        """Callback function after screen color is picked."""
        # Restore main window if it was hidden
        # self.app.master.deiconify()

        if color_rgb:
            roi = self.get_selected_roi_object()
            if roi:
                hex_color = ROI.rgb_to_hex(color_rgb)
                self.color_widgets['target_color_var'].set(hex_color)
                self.color_widgets['target_color_label'].config(background=hex_color)
                # Apply immediately or wait for Apply button? Let's wait.
                # roi.target_color = color_rgb
                self.app.update_status(f"Screen color picked: {hex_color}. Apply settings if desired.")
                print(f"Screen color picked for {roi.name}: {color_rgb} -> {hex_color}")
            else:
                 self.app.update_status("Screen color picked, but no ROI selected.")
        else:
            self.app.update_status("Screen color picking cancelled.")

    def show_original_preview(self):
        """Shows a preview of the original selected ROI content."""
        self._show_preview(filtered=False)

    def show_filtered_preview(self):
        """Shows a preview of the selected ROI after color filtering."""
        roi = self.get_selected_roi_object()
        if roi and not roi.color_filter_enabled:
             messagebox.showinfo("Info", "Color filtering is not enabled for this ROI.", parent=self.app.master)
             # Optionally, still show the original if filter is off
             # self._show_preview(filtered=False)
             return
        self._show_preview(filtered=True)

    def _show_preview(self, filtered=False):
        """Helper function to generate and show ROI previews."""
        roi = self.get_selected_roi_object()
        if not roi:
            messagebox.showwarning("Warning", "No ROI selected.", parent=self.app.master)
            return

        # Get the source frame (prefer snapshot if available and in use)
        source_frame = None
        if self.app.using_snapshot and self.app.snapshot_frame is not None:
            source_frame = self.app.snapshot_frame
        elif self.app.current_frame is not None:
             source_frame = self.app.current_frame
        elif self.app.selected_hwnd:
             # Try to capture a single frame if none is available
             self.app.update_status("Capturing frame for preview...")
             source_frame = self.app.capture_window(self.app.selected_hwnd)
             if source_frame is not None:
                 self.app.current_frame = source_frame # Store it
                 self.app.update_status("Frame captured for preview.")
             else:
                  self.app.update_status("Failed to capture frame for preview.")

        if source_frame is None:
            messagebox.showerror("Error", "No frame available to generate preview.", parent=self.app.master)
            return

        roi_img = roi.extract_roi(source_frame)
        if roi_img is None:
             messagebox.showerror("Error", f"Could not extract ROI '{roi.name}' from frame.", parent=self.app.master)
             return

        preview_img = roi_img
        title_suffix = "Original"
        if filtered:
            # Apply the *current UI settings* for preview, not necessarily saved ones
            try:
                 temp_roi = ROI("temp", 0,0,1,1) # Create dummy ROI to hold current UI settings
                 temp_roi.color_filter_enabled = self.color_widgets['enabled_var'].get()
                 temp_roi.target_color = ROI.hex_to_rgb(self.color_widgets['target_color_var'].get())
                 temp_roi.color_threshold = self.color_widgets['threshold_var'].get()

                 preview_img = temp_roi.apply_color_filter(roi_img.copy()) # Apply filter to a copy
                 title_suffix = f"Filtered (Color: {ROI.rgb_to_hex(temp_roi.target_color)}, Thresh: {temp_roi.color_threshold})"
                 if preview_img is None: # apply_color_filter might return None on error
                      messagebox.showerror("Error", "Failed to apply color filter for preview.", parent=self.app.master)
                      return
            except Exception as e:
                 messagebox.showerror("Error", f"Error applying filter for preview: {e}", parent=self.app.master)
                 return

        # Convert BGR (OpenCV) to RGB for display
        try:
             preview_img_rgb = cv2.cvtColor(preview_img, cv2.COLOR_BGR2RGB)
        except cv2.error as e:
             messagebox.showerror("Preview Error", f"Failed to convert image for display: {e}", parent=self.app.master)
             return

        # Create and show the preview window
        PreviewWindow(self.app.master, f"ROI Preview: {roi.name} - {title_suffix}", preview_img_rgb)


    # --- Other methods (update_roi_list, save_rois, move, delete, configure_overlay) ---

    def on_roi_selection_toggled(self, active):
        # This method remains largely the same
        if active:
            self.create_roi_btn.config(text="Cancel Define")
            self.app.update_status("ROI selection active. Drag on preview.")
            self.app.master.config(cursor="crosshair")
        else:
            self.create_roi_btn.config(text="Define ROI")
            self.app.master.config(cursor="")
            # Reset color filter UI if selection is cancelled without choosing an ROI
            # self.on_roi_selected() # Re-evaluates based on current selection

    def update_roi_list(self):
        # This method needs to be updated to show color filter status
        current_selection_index = self.roi_listbox.curselection()
        selected_text = self.roi_listbox.get(current_selection_index[0]) if current_selection_index else None

        self.roi_listbox.delete(0, tk.END)
        for roi in self.app.rois:
            if roi.name == SNIP_ROI_NAME:
                continue

            # Get overlay status
            overlay_config = get_overlay_config_for_roi(roi.name)
            is_overlay_enabled = overlay_config.get('enabled', False) # Default to False if not set? Check defaults. Let's assume default is True from settings.py
            overlay_prefix = "[O]" if is_overlay_enabled else "[ ]"

            # Get color filter status
            color_prefix = "[C]" if roi.color_filter_enabled else "[ ]"

            self.roi_listbox.insert(tk.END, f"{overlay_prefix}{color_prefix} {roi.name}") # Note the space

        new_idx_to_select = -1
        if selected_text:
            # Find the index based on the text *after* the prefixes
            selected_name = selected_text.split("]")[-1].strip()
            all_names_in_listbox = [item.split("]")[-1].strip() for item in self.roi_listbox.get(0, tk.END)]
            try:
                new_idx_to_select = all_names_in_listbox.index(selected_name)
            except ValueError:
                pass # Name not found (e.g., after deletion)

        if new_idx_to_select != -1:
            self.roi_listbox.selection_clear(0, tk.END) # Clear previous selection visually
            self.roi_listbox.selection_set(new_idx_to_select)
            self.roi_listbox.activate(new_idx_to_select)
            self.roi_listbox.see(new_idx_to_select) # Ensure visible

        # Update related UI elements
        if hasattr(self.app, 'overlay_tab') and self.app.overlay_tab.frame.winfo_exists():
            self.app.overlay_tab.update_roi_list() # Update overlay tab's dropdown too

        self.on_roi_selected() # Update button states and color filter UI

    def save_rois_for_current_game(self):
        # This method remains the same, but now saves the updated ROI objects
        if not self.app.selected_hwnd:
            messagebox.showwarning("Save ROIs", "No game window selected.", parent=self.app.master)
            return
        # Include all ROIs, even if empty, to allow clearing config
        rois_to_save = [roi for roi in self.app.rois if roi.name != SNIP_ROI_NAME]
        # if not rois_to_save:
        #     # Allow saving empty list
        #     if not messagebox.askyesno("Save ROIs", "No actual game ROIs defined. Save empty config for this game?", parent=self.app.master):
        #          return

        saved_path = save_rois(rois_to_save, self.app.selected_hwnd) # save_rois uses roi.to_dict()
        if saved_path is not None: # Check for None, as save_rois can return None on error
            self.app.config_file = saved_path
            self.app.update_status(f"Saved {len(rois_to_save)} ROIs for current game.")
            self.app.master.title(f"Visual Novel Translator - {os.path.basename(saved_path)}")
        else:
            # Error message already shown by save_rois
            self.app.update_status("Failed to save ROIs for current game.")

    def move_roi_up(self):
        # Logic remains the same, operates on self.app.rois list
        selection = self.roi_listbox.curselection()
        if not selection or selection[0] == 0:
            return
        idx_in_listbox = selection[0]
        roi = self.get_selected_roi_object()
        if not roi: return

        try:
            idx_in_app_list = self.app.rois.index(roi)
            # Find the previous non-SNIP ROI index
            prev_app_idx = idx_in_app_list - 1
            while prev_app_idx >= 0 and self.app.rois[prev_app_idx].name == SNIP_ROI_NAME:
                prev_app_idx -= 1
            if prev_app_idx < 0: # Already at the top (ignoring SNIP)
                return

            # Swap in the app's list
            self.app.rois[idx_in_app_list], self.app.rois[prev_app_idx] = self.app.rois[prev_app_idx], self.app.rois[idx_in_app_list]

            self.update_roi_list() # Rebuild listbox from the updated app list
            # Try to re-select the moved item
            listbox_items = self.roi_listbox.get(0, tk.END)
            target_text = f"[{'O' if get_overlay_config_for_roi(roi.name).get('enabled', True) else ' '}]" \
                          f"[{'C' if roi.color_filter_enabled else ' '}] {roi.name}"
            try:
                 new_idx_in_listbox = list(listbox_items).index(target_text)
                 self.roi_listbox.selection_set(new_idx_in_listbox)
                 self.roi_listbox.activate(new_idx_in_listbox)
            except ValueError:
                 pass # Item not found? Should not happen.
            self.on_roi_selected() # Update button states
        except (ValueError, IndexError) as e:
            print(f"Error finding ROI for move up: {e}")


    def move_roi_down(self):
        # Logic remains the same, operates on self.app.rois list
        selection = self.roi_listbox.curselection()
        if not selection: return
        idx_in_listbox = selection[0]
        if idx_in_listbox >= self.roi_listbox.size() - 1: return # Already at bottom

        roi = self.get_selected_roi_object()
        if not roi: return

        try:
            idx_in_app_list = self.app.rois.index(roi)
             # Find the next non-SNIP ROI index
            next_app_idx = idx_in_app_list + 1
            while next_app_idx < len(self.app.rois) and self.app.rois[next_app_idx].name == SNIP_ROI_NAME:
                next_app_idx += 1
            if next_app_idx >= len(self.app.rois): # Already at the bottom (ignoring SNIP)
                return

            # Swap in the app's list
            self.app.rois[idx_in_app_list], self.app.rois[next_app_idx] = self.app.rois[next_app_idx], self.app.rois[idx_in_app_list]

            self.update_roi_list() # Rebuild listbox
            # Try to re-select
            listbox_items = self.roi_listbox.get(0, tk.END)
            target_text = f"[{'O' if get_overlay_config_for_roi(roi.name).get('enabled', True) else ' '}]" \
                          f"[{'C' if roi.color_filter_enabled else ' '}] {roi.name}"
            try:
                 new_idx_in_listbox = list(listbox_items).index(target_text)
                 self.roi_listbox.selection_set(new_idx_in_listbox)
                 self.roi_listbox.activate(new_idx_in_listbox)
            except ValueError:
                 pass
            self.on_roi_selected()
        except (ValueError, IndexError) as e:
            print(f"Error finding ROI for move down: {e}")

    def delete_selected_roi(self):
        # Logic remains largely the same
        roi = self.get_selected_roi_object()
        if not roi: return
        if roi.name == SNIP_ROI_NAME: return # Should not be possible via UI

        confirm = messagebox.askyesno("Delete ROI", f"Delete ROI '{roi.name}'?", parent=self.app.master)
        if not confirm: return

        # Remove from app list
        self.app.rois.remove(roi)

        # Remove associated overlay settings (if any)
        all_overlay_settings = get_setting("overlay_settings", {})
        if roi.name in all_overlay_settings:
            del all_overlay_settings[roi.name]
            update_settings({"overlay_settings": all_overlay_settings}) # Save updated settings

        # Destroy live overlay window
        if hasattr(self.app, 'overlay_manager'):
            self.app.overlay_manager.destroy_overlay(roi.name)

        # Clear related text data
        if roi.name in self.app.text_history: del self.app.text_history[roi.name]
        if roi.name in self.app.stable_texts: del self.app.stable_texts[roi.name]

        # Update UI elements that show text
        def safe_update(widget_name, update_method, data):
            widget = getattr(self.app, widget_name, None)
            if widget and hasattr(widget, 'frame') and widget.frame.winfo_exists():
                try: update_method(data)
                except tk.TclError: pass
                except Exception as e: print(f"Error updating {widget_name} after delete: {e}")

        safe_update('text_tab', self.app.text_tab.update_text, self.app.text_history)
        safe_update('stable_text_tab', self.app.stable_text_tab.update_text, self.app.stable_texts)

        # Refresh ROI list UI
        self.update_roi_list()
        self.app.update_status(f"ROI '{roi.name}' deleted. (Save ROIs to persist)")

    def configure_selected_overlay(self):
        # Logic remains the same
        roi = self.get_selected_roi_object()
        if not roi: return

        if not hasattr(self.app, 'overlay_tab') or not self.app.overlay_tab.frame.winfo_exists():
            messagebox.showerror("Error", "Overlay tab not available.", parent=self.app.master)
            return

        try:
            overlay_tab_widget = self.app.overlay_tab.frame
            notebook_widget = overlay_tab_widget.master
            if not isinstance(notebook_widget, ttk.Notebook):
                raise tk.TclError("Parent not Notebook")

            # Switch to the Overlay tab
            notebook_widget.select(overlay_tab_widget)

            # Select the correct ROI in the overlay tab's combobox
            if hasattr(self.app.overlay_tab, 'roi_names_for_combo') and roi.name in self.app.overlay_tab.roi_names_for_combo:
                self.app.overlay_tab.selected_roi_var.set(roi.name)
                self.app.overlay_tab.load_roi_config() # Load its config into the UI
            else:
                print(f"ROI '{roi.name}' not found in Overlay Tab combo after switch.")

        except (tk.TclError, AttributeError) as e:
            print(f"Error switching to overlay tab: {e}")
            messagebox.showerror("Error", "Could not switch to Overlay tab.", parent=self.app.master)
        except Exception as e:
            print(f"Unexpected error configuring overlay: {e}")


# --- END OF FILE roi_tab.py ---
```

**4. `app.py` (Updated)**

```python
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
```

**5. New File: `ui/preview_window.py`**

```python
# --- START OF FILE ui/preview_window.py ---

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import numpy as np

class PreviewWindow(tk.Toplevel):
    """A simple Toplevel window to display an image preview."""

    def __init__(self, master, title="Preview", image_np=None):
        super().__init__(master)
        self.title(title)
        self.transient(master) # Keep window on top of master
        self.grab_set() # Modal behavior (optional)
        self.resizable(False, False)

        self.image_label = ttk.Label(self)
        self.image_label.pack(padx=5, pady=5)

        self.photo_image = None # Keep a reference

        if image_np is not None:
            self.update_image(image_np)
        else:
            self.image_label.config(text="No image data.")

        # Center the window relative to the master
        self.update_idletasks()
        master_x = master.winfo_rootx()
        master_y = master.winfo_rooty()
        master_w = master.winfo_width()
        master_h = master.winfo_height()
        win_w = self.winfo_width()
        win_h = self.winfo_height()
        x = master_x + (master_w - win_w) // 2
        y = master_y + (master_h - win_h) // 3 # Position slightly higher
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self.protocol("WM_DELETE_WINDOW", self.close_window)
        self.bind("<Escape>", lambda e: self.close_window())

    def update_image(self, image_np):
        """Updates the displayed image."""
        if image_np is None or image_np.size == 0:
            self.image_label.config(image='', text="Invalid image data.")
            self.photo_image = None
            return

        try:
            # Ensure image is in a displayable format (e.g., RGB)
            if len(image_np.shape) == 3 and image_np.shape[2] == 3:
                # Assume BGR from OpenCV, convert to RGB for PIL
                # If it's already RGB, this won't hurt much
                # img_rgb = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB) # Done in roi_tab now
                img_pil = Image.fromarray(image_np) # Assumes input is RGB now
            elif len(image_np.shape) == 2: # Grayscale
                img_pil = Image.fromarray(image_np, 'L')
            else:
                 self.image_label.config(image='', text="Unsupported image format.")
                 self.photo_image = None
                 return

            self.photo_image = ImageTk.PhotoImage(img_pil)
            self.image_label.config(image=self.photo_image, text="")

        except Exception as e:
            print(f"Error updating preview image: {e}")
            self.image_label.config(image='', text=f"Error: {e}")
            self.photo_image = None

    def close_window(self):
        self.grab_release()
        self.destroy()

# --- END OF FILE ui/preview_window.py ---
```

**6. New File: `ui/color_picker.py`**

```python
# --- START OF FILE ui/color_picker.py ---

import tkinter as tk
import mss
import numpy as np
import cv2 # Only needed if converting color space, mss gives RGB

class ScreenColorPicker:
    """Handles capturing a color from anywhere on the screen."""

    def __init__(self, master):
        self.master = master
        self.overlay = None
        self.callback = None

    def grab_color(self, callback):
        """Creates the overlay and starts the color picking process."""
        if self.overlay and self.overlay.winfo_exists():
            print("Color picker already active.")
            return

        self.callback = callback
        try:
            self.overlay = tk.Toplevel(self.master)
            self.overlay.attributes("-fullscreen", True)
            self.overlay.attributes("-alpha", 0.1) # Very transparent
            self.overlay.overrideredirect(True)
            self.overlay.attributes("-topmost", True)
            self.overlay.configure(cursor="crosshair") # Use crosshair cursor
            self.overlay.grab_set() # Capture input

            # Bind events
            self.overlay.bind("<ButtonPress-1>", self._on_click)
            self.overlay.bind("<Escape>", self._on_cancel)

        except Exception as e:
            print(f"Error creating color picker overlay: {e}")
            self._cleanup()
            if self.callback:
                self.callback(None) # Notify callback of failure/cancellation

    def _on_click(self, event):
        """Callback when the user clicks on the overlay."""
        x, y = event.x_root, event.y_root
        print(f"Color picker clicked at screen coordinates: ({x}, {y})")

        color_rgb = None
        try:
            # Define the 1x1 pixel region to capture
            monitor = {"top": y, "left": x, "width": 1, "height": 1}
            with mss.mss() as sct:
                sct_img = sct.grab(monitor)

            # Convert the raw BGRA data to a NumPy array
            img_array = np.array(sct_img, dtype=np.uint8)

            # Extract the single pixel's color (mss provides BGRA)
            # We want RGB, so take the first 3 channels and reverse order
            if img_array.size >= 3:
                 b, g, r, _ = img_array[0, 0] # Extract BGRA
                 color_rgb = (int(r), int(g), int(b)) # Convert to RGB tuple
                 print(f"Picked color (RGB): {color_rgb}")
            else:
                 print("Error: Captured image data is too small.")

        except Exception as e:
            print(f"Error capturing screen color: {e}")

        # Clean up the overlay
        self._cleanup()

        # Call the original callback with the result (color_rgb or None)
        if self.callback:
            self.callback(color_rgb)

    def _on_cancel(self, event=None):
        """Callback when the user presses Escape."""
        print("Color picking cancelled.")
        self._cleanup()
        if self.callback:
            self.callback(None) # Notify callback of cancellation

    def _cleanup(self):
        """Destroys the overlay window and releases grab."""
        if self.overlay and self.overlay.winfo_exists():
            try:
                self.overlay.grab_release()
                self.overlay.destroy()
            except tk.TclError:
                pass # Ignore if already destroyed
        self.overlay = None
        self.callback = None

# --- END OF FILE ui/color_picker.py ---
```

**Summary of Changes:**

1.  **`ROI` Class (`utils/roi.py`):**
    *   Added `color_filter_enabled`, `target_color` (as RGB tuple), `color_threshold` attributes.
    *   Updated `to_dict` and `from_dict` to handle these new attributes, ensuring backward compatibility.
    *   Added `apply_color_filter` method using `cv2.inRange` to create a mask and apply it (setting non-matching pixels to white).
    *   Added static methods `rgb_to_hex` and `hex_to_rgb` for convenience.
2.  **ROI Saving/Loading (`utils/config.py`):**
    *   Modified `save_rois` and `load_rois` to implicitly use the updated `ROI.to_dict` and `ROI.from_dict` methods, so they now handle the color filter settings automatically.
3.  **ROI Tab UI (`ui/roi_tab.py`):**
    *   Added a new `LabelFrame` for "Color Filtering".
    *   Added widgets: Checkbutton (enable), Label (color preview), Buttons (Pick Color, Pick from Screen), Scale (threshold), Buttons (Apply, Preview Original, Preview Filtered).
    *   `on_roi_selected`: Now loads the selected ROI's filter settings into the UI and enables/disables the filter section.
    *   `apply_color_filter_settings`: Reads UI values and updates the *in-memory* `ROI` object. Reminds the user to save the main ROI config.
    *   `pick_color`: Uses `colorchooser`.
    *   `pick_color_from_screen`: Uses the new `ScreenColorPicker` class.
    *   `_show_preview`: Handles generating original or filtered previews using the new `PreviewWindow`. It applies the *current UI settings* for the filtered preview.
    *   `update_roi_list`: Added a `[C]` prefix to indicate if color filtering is enabled for an ROI.
    *   Imported `PreviewWindow` and `ScreenColorPicker`.
4.  **App Logic (`app.py`):**
    *   `_process_rois`: Now calls `roi.apply_color_filter()` on the extracted ROI image before passing it to OCR.
    *   Imported `PreviewWindow` and `ScreenColorPicker`.
5.  **Preview Window (`ui/preview_window.py`):**
    *   New `Toplevel` window class to display a NumPy image using PIL/Tkinter.
6.  **Screen Color Picker (`ui/color_picker.py`):**
    *   New class using `mss` to create a full-screen overlay, capture the color at the click position, and return it via a callback.

Remember to place the new files (`preview_window.py` and `color_picker.py`) inside the `ui` directory.