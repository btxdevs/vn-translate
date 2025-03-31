
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
from ui.base import BaseTab
from utils.capture import capture_window
from utils.config import save_rois
from utils.settings import get_overlay_config_for_roi, update_settings, get_setting
from utils.roi import ROI # Import ROI class
from ui.overlay_tab import SNIP_ROI_NAME
from ui.preview_window import PreviewWindow
from ui.color_picker import ScreenColorPicker
import os
import cv2

class ROITab(BaseTab):
    def setup_ui(self):
        # --- Main Paned Window for this Tab ---
        self.main_pane = ttk.PanedWindow(self.frame, orient=tk.VERTICAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True)

        # --- Top Pane: ROI Definition and List ---
        top_frame = ttk.Frame(self.main_pane, padding=0)
        self.main_pane.add(top_frame, weight=1) # Adjust weight as needed

        roi_frame = ttk.LabelFrame(top_frame, text="Regions of Interest (ROIs)", padding="10")
        roi_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        create_frame = ttk.Frame(roi_frame)
        create_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(create_frame, text="New ROI Name:").pack(side=tk.LEFT, anchor=tk.W, pady=(5, 0), padx=(0, 5))
        self.roi_name_entry = ttk.Entry(create_frame, width=15)
        self.roi_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=(5, 0))
        self.roi_name_entry.insert(0, "dialogue")
        self.create_roi_btn = ttk.Button(create_frame, text="Define ROI", command=self.app.toggle_roi_selection)
        self.create_roi_btn.pack(side=tk.LEFT, padx=(5, 0), pady=(5, 0))
        ttk.Label(roi_frame, text="Click 'Define ROI', then click and drag on the image preview.", font=('TkDefaultFont', 8)).pack(anchor=tk.W, pady=(0, 5))

        list_manage_frame = ttk.Frame(roi_frame)
        list_manage_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        list_frame = ttk.Frame(list_manage_frame)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        ttk.Label(list_frame, text="Current Game ROIs ([O]=Overlay, [C]=Color, [P]=Preproc, [X]=Cutout, [I]=Invert):").pack(anchor=tk.W) # Updated label
        roi_scrollbar = ttk.Scrollbar(list_frame)
        roi_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.roi_listbox = tk.Listbox(list_frame, height=6, selectmode=tk.SINGLE, exportselection=False, yscrollcommand=roi_scrollbar.set)
        self.roi_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        roi_scrollbar.config(command=self.roi_listbox.yview)
        self.roi_listbox.bind("<<ListboxSelect>>", self.on_roi_selected)

        manage_btn_frame = ttk.Frame(list_manage_frame)
        manage_btn_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(5, 0))
        self.move_up_btn = ttk.Button(manage_btn_frame, text="▲ Up", width=8, command=self.move_roi_up, state=tk.DISABLED)
        self.move_up_btn.pack(pady=2, anchor=tk.N)
        self.move_down_btn = ttk.Button(manage_btn_frame, text="▼ Down", width=8, command=self.move_roi_down, state=tk.DISABLED)
        self.move_down_btn.pack(pady=2, anchor=tk.N)
        # Add Redefine Button
        self.redefine_roi_btn = ttk.Button(manage_btn_frame, text="Redefine", width=8, command=self.redefine_selected_roi, state=tk.DISABLED)
        self.redefine_roi_btn.pack(pady=(10, 2), anchor=tk.N) # Place it above Delete
        self.delete_roi_btn = ttk.Button(manage_btn_frame, text="Delete", width=8, command=self.delete_selected_roi, state=tk.DISABLED)
        self.delete_roi_btn.pack(pady=2, anchor=tk.N) # Adjusted padding
        self.config_overlay_btn = ttk.Button(manage_btn_frame, text="Overlay...", width=8, command=self.configure_selected_overlay, state=tk.DISABLED)
        self.config_overlay_btn.pack(pady=(5, 2), anchor=tk.N)

        # --- Bottom Pane: Configuration Sections (Color Filter, Preprocessing) ---
        bottom_frame = ttk.Frame(self.main_pane, padding=0)
        self.main_pane.add(bottom_frame, weight=1) # Adjust weight as needed

        # --- Color Filter Configuration ---
        self.color_filter_frame = ttk.LabelFrame(bottom_frame, text="Color Filtering (for selected ROI)", padding="10")
        self.color_filter_frame.pack(fill=tk.X, pady=(5, 5))
        self.color_widgets = {}
        self._build_color_filter_widgets() # Call helper to build

        # --- OCR Preprocessing Configuration ---
        self.preprocess_frame = ttk.LabelFrame(bottom_frame, text="OCR Preprocessing (for selected ROI)", padding="10")
        self.preprocess_frame.pack(fill=tk.X, pady=(5, 5))
        self.preprocess_widgets = {}
        self._build_preprocessing_widgets() # Call helper to build

        # --- Apply & Preview Buttons (Combined) ---
        action_btn_frame = ttk.Frame(bottom_frame)
        action_btn_frame.pack(fill=tk.X, pady=(10, 5), padx=5)

        self.apply_settings_btn = ttk.Button(action_btn_frame, text="Apply All ROI Settings", command=self.apply_roi_settings)
        self.apply_settings_btn.pack(side=tk.LEFT, padx=5)
        self.preview_orig_btn = ttk.Button(action_btn_frame, text="Preview Original", command=self.show_original_preview)
        self.preview_orig_btn.pack(side=tk.LEFT, padx=5)
        self.preview_filter_btn = ttk.Button(action_btn_frame, text="Preview Processed", command=self.show_processed_preview)
        self.preview_filter_btn.pack(side=tk.LEFT, padx=5)

        # --- Bottom part: Save All ROIs ---
        file_btn_frame = ttk.Frame(bottom_frame)
        file_btn_frame.pack(fill=tk.X, pady=(5, 10))
        self.save_rois_btn = ttk.Button(file_btn_frame, text="Save All ROI Settings for Current Game", command=self.save_rois_for_current_game)
        self.save_rois_btn.pack(side=tk.LEFT, padx=5)

        # Initial state
        self.update_roi_list()
        self.set_config_widgets_state(tk.DISABLED) # Single function to disable both sections

    def _build_color_filter_widgets(self):
        """Helper to create widgets for the color filter section."""
        frame = self.color_filter_frame
        widgets = self.color_widgets

        # Enable Checkbox
        widgets['enabled_var'] = tk.BooleanVar(value=False)
        widgets['enabled_check'] = ttk.Checkbutton(
            frame, text="Enable Color Filter", variable=widgets['enabled_var']
        )
        widgets['enabled_check'].grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=(0, 5))

        # Target Color
        ttk.Label(frame, text="Target Color:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=2)
        widgets['target_color_var'] = tk.StringVar(value="#FFFFFF")
        widgets['target_color_label'] = ttk.Label(frame, text="       ", background="#FFFFFF", relief=tk.SUNKEN, width=8)
        widgets['target_color_label'].grid(row=1, column=1, sticky=tk.W, pady=2)
        widgets['pick_target_btn'] = ttk.Button(frame, text="Pick...", width=6, command=lambda: self.pick_color('target'))
        widgets['pick_target_btn'].grid(row=1, column=2, padx=(5, 2), pady=2)
        widgets['pick_screen_btn'] = ttk.Button(frame, text="Screen", width=7, command=self.pick_color_from_screen)
        widgets['pick_screen_btn'].grid(row=1, column=3, padx=(2, 0), pady=2)

        # Replacement Color
        ttk.Label(frame, text="Replace With:").grid(row=2, column=0, sticky=tk.W, padx=(0, 5), pady=2)
        default_replace_hex = ROI.rgb_to_hex(ROI.DEFAULT_REPLACEMENT_COLOR_RGB)
        widgets['replace_color_var'] = tk.StringVar(value=default_replace_hex)
        widgets['replace_color_label'] = ttk.Label(frame, text="       ", background=default_replace_hex, relief=tk.SUNKEN, width=8)
        widgets['replace_color_label'].grid(row=2, column=1, sticky=tk.W, pady=2)
        widgets['pick_replace_btn'] = ttk.Button(frame, text="Pick...", width=6, command=lambda: self.pick_color('replace'))
        widgets['pick_replace_btn'].grid(row=2, column=2, padx=(5, 2), pady=2)

        # Threshold
        ttk.Label(frame, text="Threshold:").grid(row=3, column=0, sticky=tk.W, padx=(0, 5), pady=2)
        widgets['threshold_var'] = tk.IntVar(value=30)
        widgets['threshold_scale'] = ttk.Scale(
            frame, from_=0, to=200, orient=tk.HORIZONTAL,
            variable=widgets['threshold_var'], length=150,
            command=lambda v: widgets['threshold_label_var'].set(f"{int(float(v))}")
        )
        widgets['threshold_scale'].grid(row=3, column=1, columnspan=2, sticky=tk.EW, pady=2)
        widgets['threshold_label_var'] = tk.StringVar(value="30")
        ttk.Label(frame, textvariable=widgets['threshold_label_var'], width=4).grid(row=3, column=3, sticky=tk.W, padx=(5, 0), pady=2)

    def _build_preprocessing_widgets(self):
        """Helper to create widgets for the OCR preprocessing section."""
        frame = self.preprocess_frame
        widgets = self.preprocess_widgets
        defaults = ROI.DEFAULT_PREPROCESSING

        # --- Column Configuration ---
        frame.columnconfigure(1, weight=0) # Standard widgets
        frame.columnconfigure(2, weight=0) # Labels/Spinners
        frame.columnconfigure(3, weight=0) # Standard widgets
        frame.columnconfigure(4, weight=1) # Scales/Expandable
        frame.columnconfigure(5, weight=0) # Labels/Spinners

        row = 0

        # --- Basic Operations ---
        widgets['grayscale_var'] = tk.BooleanVar(value=defaults['grayscale'])
        widgets['grayscale_check'] = ttk.Checkbutton(frame, text="Grayscale", variable=widgets['grayscale_var'])
        widgets['grayscale_check'].grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)

        widgets['invert_colors_var'] = tk.BooleanVar(value=defaults['invert_colors'])
        widgets['invert_colors_check'] = ttk.Checkbutton(frame, text="Invert Colors", variable=widgets['invert_colors_var'])
        widgets['invert_colors_check'].grid(row=row, column=3, sticky=tk.W, padx=5, pady=2)
        row += 1

        # --- Sharpening (Slider) ---
        ttk.Label(frame, text="Sharpen:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        widgets['sharpening_strength_var'] = tk.DoubleVar(value=defaults['sharpening_strength'])
        # Use a local function for the command to update the label
        def _update_sharpen_label(value):
            try:
                # Check if widget exists before accessing
                if 'sharpening_strength_label_var' in widgets and widgets['sharpening_strength_label_var']:
                    widgets['sharpening_strength_label_var'].set(f"{float(value):.2f}")
            except (tk.TclError, ValueError): pass # Ignore errors if widget gone or value invalid

        widgets['sharpening_strength_scale'] = ttk.Scale(
            frame, from_=0.0, to=1.0, orient=tk.HORIZONTAL,
            variable=widgets['sharpening_strength_var'], length=120,
            command=_update_sharpen_label
        )
        widgets['sharpening_strength_scale'].grid(row=row, column=1, columnspan=3, sticky=tk.EW, padx=5, pady=2)
        widgets['sharpening_strength_label_var'] = tk.StringVar(value=f"{defaults['sharpening_strength']:.2f}")
        ttk.Label(frame, textvariable=widgets['sharpening_strength_label_var'], width=5).grid(row=row, column=4, sticky=tk.W, padx=(5, 0), pady=2)
        row += 1


        # --- Scaling ---
        widgets['scaling_enabled_var'] = tk.BooleanVar(value=defaults['scaling_enabled'])
        widgets['scaling_enabled_check'] = ttk.Checkbutton(frame, text="Scale", variable=widgets['scaling_enabled_var'])
        widgets['scaling_enabled_check'].grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)

        widgets['scale_factor_var'] = tk.DoubleVar(value=defaults['scale_factor'])
        widgets['scale_factor_spin'] = ttk.Spinbox(frame, from_=0.5, to=4.0, increment=0.1, width=5, textvariable=widgets['scale_factor_var'])
        widgets['scale_factor_spin'].grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(frame, text="Factor").grid(row=row, column=2, sticky=tk.W, padx=(0,5), pady=2)
        row += 1

        # --- Cutout ---
        widgets['cutout_enabled_var'] = tk.BooleanVar(value=defaults['cutout_enabled'])
        widgets['cutout_enabled_check'] = ttk.Checkbutton(frame, text="Cutout Blank Space", variable=widgets['cutout_enabled_var'])
        widgets['cutout_enabled_check'].grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)

        widgets['cutout_padding_var'] = tk.IntVar(value=defaults['cutout_padding'])
        widgets['cutout_padding_spin'] = ttk.Spinbox(frame, from_=0, to=50, increment=1, width=5, textvariable=widgets['cutout_padding_var'])
        widgets['cutout_padding_spin'].grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(frame, text="Pad").grid(row=row, column=2, sticky=tk.W, padx=(0,5), pady=2)

        widgets['cutout_bg_threshold_var'] = tk.IntVar(value=defaults['cutout_bg_threshold'])
        widgets['cutout_bg_threshold_spin'] = ttk.Spinbox(frame, from_=0, to=127, increment=1, width=5, textvariable=widgets['cutout_bg_threshold_var'])
        widgets['cutout_bg_threshold_spin'].grid(row=row, column=3, sticky=tk.W, padx=5, pady=2)
        ttk.Label(frame, text="BG Thresh").grid(row=row, column=4, sticky=tk.W, padx=(0,5), pady=2)
        row += 1

        # --- Binarization ---
        ttk.Label(frame, text="Binarize:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        widgets['binarization_type_var'] = tk.StringVar(value=defaults['binarization_type'])
        widgets['binarization_type_combo'] = ttk.Combobox(frame, textvariable=widgets['binarization_type_var'], values=ROI.BINARIZATION_TYPES, state="readonly", width=15)
        widgets['binarization_type_combo'].grid(row=row, column=1, columnspan=2, sticky=tk.W, padx=5, pady=2)
        widgets['binarization_type_combo'].bind("<<ComboboxSelected>>", self._on_binarization_type_change)
        row += 1

        # Adaptive Threshold Parameters (initially hidden/disabled)
        widgets['adaptive_params_frame'] = ttk.Frame(frame)
        widgets['adaptive_params_frame'].grid(row=row, column=0, columnspan=4, sticky=tk.EW, padx=5, pady=0)

        ttk.Label(widgets['adaptive_params_frame'], text="Block Size:").grid(row=0, column=0, sticky=tk.W, padx=0, pady=1)
        widgets['adaptive_block_size_var'] = tk.IntVar(value=defaults['adaptive_block_size'])
        widgets['adaptive_block_size_spin'] = ttk.Spinbox(widgets['adaptive_params_frame'], from_=3, to=51, increment=2, width=5, textvariable=widgets['adaptive_block_size_var'])
        widgets['adaptive_block_size_spin'].grid(row=0, column=1, sticky=tk.W, padx=5, pady=1)

        ttk.Label(widgets['adaptive_params_frame'], text="C Value:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=1)
        widgets['adaptive_c_value_var'] = tk.IntVar(value=defaults['adaptive_c_value'])
        widgets['adaptive_c_value_spin'] = ttk.Spinbox(widgets['adaptive_params_frame'], from_=-10, to=10, increment=1, width=5, textvariable=widgets['adaptive_c_value_var'])
        widgets['adaptive_c_value_spin'].grid(row=0, column=3, sticky=tk.W, padx=5, pady=1)
        row += 1 # Increment row after placing the adaptive frame

        # --- Noise Reduction ---
        widgets['median_blur_enabled_var'] = tk.BooleanVar(value=defaults['median_blur_enabled'])
        widgets['median_blur_enabled_check'] = ttk.Checkbutton(frame, text="Median Blur", variable=widgets['median_blur_enabled_var'])
        widgets['median_blur_enabled_check'].grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)

        widgets['median_blur_ksize_var'] = tk.IntVar(value=defaults['median_blur_ksize'])
        widgets['median_blur_ksize_spin'] = ttk.Spinbox(frame, from_=3, to=15, increment=2, width=5, textvariable=widgets['median_blur_ksize_var'])
        widgets['median_blur_ksize_spin'].grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(frame, text="KSize").grid(row=row, column=2, sticky=tk.W, padx=(0,5), pady=2)
        row += 1

        # --- Morphological Operations ---
        widgets['dilation_enabled_var'] = tk.BooleanVar(value=defaults['dilation_enabled'])
        widgets['dilation_enabled_check'] = ttk.Checkbutton(frame, text="Dilation", variable=widgets['dilation_enabled_var'])
        widgets['dilation_enabled_check'].grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)

        widgets['erosion_enabled_var'] = tk.BooleanVar(value=defaults['erosion_enabled'])
        widgets['erosion_enabled_check'] = ttk.Checkbutton(frame, text="Erosion", variable=widgets['erosion_enabled_var'])
        widgets['erosion_enabled_check'].grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)

        widgets['morph_ksize_var'] = tk.IntVar(value=defaults['morph_ksize'])
        widgets['morph_ksize_spin'] = ttk.Spinbox(frame, from_=1, to=15, increment=1, width=5, textvariable=widgets['morph_ksize_var'])
        widgets['morph_ksize_spin'].grid(row=row, column=2, sticky=tk.W, padx=5, pady=2)
        ttk.Label(frame, text="KSize").grid(row=row, column=3, sticky=tk.W, padx=(0,5), pady=2)
        row += 1

        # Initial state for adaptive params
        self._update_adaptive_param_state()

    def _on_binarization_type_change(self, event=None):
        """Callback when binarization type changes to enable/disable adaptive params."""
        self._update_adaptive_param_state()

    def _update_adaptive_param_state(self):
        """Enable/disable adaptive threshold parameter widgets based on combobox selection."""
        widgets = self.preprocess_widgets
        # Check if widgets dict and the specific var exist
        if not widgets or 'binarization_type_var' not in widgets:
            return
        try:
            is_adaptive = widgets['binarization_type_var'].get() == "Adaptive Gaussian"
            new_state = tk.NORMAL if is_adaptive else tk.DISABLED

            if 'adaptive_params_frame' in widgets and widgets['adaptive_params_frame'].winfo_exists():
                for child in widgets['adaptive_params_frame'].winfo_children():
                    if isinstance(child, (ttk.Spinbox, ttk.Label)):
                        child.configure(state=new_state)
        except tk.TclError:
            pass # Frame might not exist yet or is being destroyed
        except AttributeError:
            pass # Handle case where widgets['adaptive_params_frame'] might not be set yet

    def set_config_widgets_state(self, state):
        """Enable or disable all widgets in the config frames."""
        valid_states = (tk.NORMAL, tk.DISABLED)
        actual_state = state if state in valid_states else tk.DISABLED
        scale_state = tk.NORMAL if actual_state == tk.NORMAL else tk.DISABLED
        combobox_state = 'readonly' if actual_state == tk.NORMAL else tk.DISABLED

        frames_to_process = []
        if hasattr(self, 'color_filter_frame') and self.color_filter_frame.winfo_exists():
            frames_to_process.append(self.color_filter_frame)
        if hasattr(self, 'preprocess_frame') and self.preprocess_frame.winfo_exists():
            frames_to_process.append(self.preprocess_frame)

        try:
            for frame in frames_to_process:
                for widget in frame.winfo_children():
                    # Handle nested frames like adaptive_params_frame
                    if isinstance(widget, (ttk.Frame, tk.Frame)):
                        # Don't disable the frame itself, disable its children
                        # Check if the widget is the adaptive params frame before iterating
                        is_adaptive_frame = hasattr(self, 'preprocess_widgets') and widget == self.preprocess_widgets.get('adaptive_params_frame')
                        if not is_adaptive_frame:
                            for sub_widget in widget.winfo_children():
                                try: sub_widget.configure(state=actual_state)
                                except tk.TclError: pass
                    else:
                        widget_class = widget.winfo_class()
                        try:
                            if widget_class in ('TButton', 'TCheckbutton', 'TSpinbox'):
                                widget.configure(state=actual_state)
                            elif widget_class == 'TCombobox':
                                widget.configure(state=combobox_state)
                            elif widget_class in ('Scale', 'TScale'): # Handle Scales
                                widget.configure(state=scale_state)
                            # Labels are usually kept enabled
                        except tk.TclError: pass

            # Special handling for adaptive params based on binarization type
            if state == tk.NORMAL:
                self._update_adaptive_param_state()
            else: # If disabling everything, disable adaptive params too
                if hasattr(self, 'preprocess_widgets') and 'adaptive_params_frame' in self.preprocess_widgets and self.preprocess_widgets['adaptive_params_frame'].winfo_exists():
                    for child in self.preprocess_widgets['adaptive_params_frame'].winfo_children():
                        try: child.configure(state=tk.DISABLED)
                        except tk.TclError: pass

            # Enable/Disable Apply and Preview buttons based on overall state
            if hasattr(self, 'apply_settings_btn'): self.apply_settings_btn.config(state=actual_state)
            if hasattr(self, 'preview_orig_btn'): self.preview_orig_btn.config(state=actual_state)
            if hasattr(self, 'preview_filter_btn'): self.preview_filter_btn.config(state=actual_state)

        except tk.TclError:
            print("TclError setting config widget state (widgets might be closing).")
        except Exception as e:
            print(f"Error setting config widget state: {e}")


    def on_roi_selected(self, event=None):
        selection = self.roi_listbox.curselection()
        has_selection = bool(selection)
        num_items = self.roi_listbox.size()
        idx = selection[0] if has_selection else -1

        self.move_up_btn.config(state=tk.NORMAL if has_selection and idx > 0 else tk.DISABLED)
        self.move_down_btn.config(state=tk.NORMAL if has_selection and idx < num_items - 1 else tk.DISABLED)
        self.delete_roi_btn.config(state=tk.NORMAL if has_selection else tk.DISABLED)
        # Enable Redefine button only if an ROI is selected
        self.redefine_roi_btn.config(state=tk.NORMAL if has_selection else tk.DISABLED)
        can_config_overlay = has_selection and hasattr(self.app, 'overlay_tab') and self.app.overlay_tab.frame.winfo_exists()
        self.config_overlay_btn.config(state=tk.NORMAL if can_config_overlay else tk.DISABLED)

        if has_selection:
            roi = self.get_selected_roi_object()
            if roi:
                self.load_roi_settings(roi) # Load both color and preprocess
                self.set_config_widgets_state(tk.NORMAL)
            else:
                self.set_config_widgets_state(tk.DISABLED)
        else:
            self.set_config_widgets_state(tk.DISABLED)

    def get_selected_roi_object(self):
        """Gets the ROI object corresponding to the listbox selection."""
        selection = self.roi_listbox.curselection()
        if not selection:
            return None
        try:
            # Extract name robustly, handling potential multiple ']'
            listbox_text = self.roi_listbox.get(selection[0])
            parts = listbox_text.split("]")
            roi_name = parts[-1].strip() # Get text after the last ']'
            return next((r for r in self.app.rois if r.name == roi_name), None)
        except (tk.TclError, IndexError, StopIteration, ValueError):
            # Add listbox_text to the error message if it exists
            error_text = f"Error getting selected ROI object from text: '{listbox_text}'" if 'listbox_text' in locals() else "Error getting selected ROI object"
            print(error_text)
            return None

    def load_roi_settings(self, roi):
        """Loads the settings (color filter + preprocessing) from the ROI object into the UI."""
        if not roi: return
        self._load_color_filter_settings(roi)
        self._load_preprocessing_settings(roi)

    def _load_color_filter_settings(self, roi):
        """Loads only the color filter settings from the ROI object into the UI."""
        if not hasattr(self, 'color_widgets'): return
        widgets = self.color_widgets
        try:
            widgets['enabled_var'].set(roi.color_filter_enabled)
            target_hex = ROI.rgb_to_hex(roi.target_color)
            widgets['target_color_var'].set(target_hex)
            widgets['target_color_label'].config(background=target_hex)
            replace_hex = ROI.rgb_to_hex(roi.replacement_color)
            widgets['replace_color_var'].set(replace_hex)
            widgets['replace_color_label'].config(background=replace_hex)
            widgets['threshold_var'].set(roi.color_threshold)
            widgets['threshold_label_var'].set(str(roi.color_threshold))
        except tk.TclError: print("TclError loading color filter settings (widget might be destroyed).")
        except Exception as e: print(f"Error loading color filter settings for {roi.name}: {e}")

    def _load_preprocessing_settings(self, roi):
        """Loads only the preprocessing settings from the ROI object into the UI."""
        if not hasattr(self, 'preprocess_widgets'): return
        widgets = self.preprocess_widgets
        settings = roi.preprocessing # Get the dict from the ROI object
        defaults = ROI.DEFAULT_PREPROCESSING # Get defaults for fallback
        try:
            widgets['grayscale_var'].set(settings.get('grayscale', defaults['grayscale']))
            widgets['binarization_type_var'].set(settings.get('binarization_type', defaults['binarization_type']))
            widgets['adaptive_block_size_var'].set(settings.get('adaptive_block_size', defaults['adaptive_block_size']))
            widgets['adaptive_c_value_var'].set(settings.get('adaptive_c_value', defaults['adaptive_c_value']))
            widgets['scaling_enabled_var'].set(settings.get('scaling_enabled', defaults['scaling_enabled']))
            widgets['scale_factor_var'].set(settings.get('scale_factor', defaults['scale_factor']))
            # Load sharpening strength
            sharpen_strength = settings.get('sharpening_strength', defaults['sharpening_strength'])
            widgets['sharpening_strength_var'].set(sharpen_strength)
            widgets['sharpening_strength_label_var'].set(f"{sharpen_strength:.2f}") # Update label too

            widgets['median_blur_enabled_var'].set(settings.get('median_blur_enabled', defaults['median_blur_enabled']))
            widgets['median_blur_ksize_var'].set(settings.get('median_blur_ksize', defaults['median_blur_ksize']))
            widgets['dilation_enabled_var'].set(settings.get('dilation_enabled', defaults['dilation_enabled']))
            widgets['erosion_enabled_var'].set(settings.get('erosion_enabled', defaults['erosion_enabled']))
            widgets['morph_ksize_var'].set(settings.get('morph_ksize', defaults['morph_ksize']))

            # Load new cutout and invert settings
            widgets['cutout_enabled_var'].set(settings.get('cutout_enabled', defaults['cutout_enabled']))
            widgets['cutout_padding_var'].set(settings.get('cutout_padding', defaults['cutout_padding']))
            widgets['cutout_bg_threshold_var'].set(settings.get('cutout_bg_threshold', defaults['cutout_bg_threshold']))
            widgets['invert_colors_var'].set(settings.get('invert_colors', defaults['invert_colors']))

            # Update adaptive param visibility after loading
            self._update_adaptive_param_state()
        except tk.TclError: print("TclError loading preprocessing settings (widget might be destroyed).")
        except Exception as e: print(f"Error loading preprocessing settings for {roi.name}: {e}")

    def apply_roi_settings(self):
        """Applies the UI settings (color + preprocess) to the selected in-memory ROI object."""
        roi = self.get_selected_roi_object()
        if not roi:
            messagebox.showwarning("Warning", "No ROI selected to apply settings to.", parent=self.app.master)
            return

        try:
            # Apply Color Filter Settings
            roi.color_filter_enabled = self.color_widgets['enabled_var'].get()
            roi.target_color = ROI.hex_to_rgb(self.color_widgets['target_color_var'].get())
            roi.replacement_color = ROI.hex_to_rgb(self.color_widgets['replace_color_var'].get())
            roi.color_threshold = self.color_widgets['threshold_var'].get()

            # Apply Preprocessing Settings
            new_preprocess_settings = {}
            widgets = self.preprocess_widgets
            defaults = ROI.DEFAULT_PREPROCESSING
            for key in defaults:
                var_name = f"{key}_var"
                if var_name in widgets:
                    try:
                        # Get value, special handling for doublevar
                        if isinstance(widgets[var_name], tk.DoubleVar):
                            value = round(widgets[var_name].get(), 3) # Round float values
                        else:
                            value = widgets[var_name].get()
                        new_preprocess_settings[key] = value
                    except (tk.TclError, ValueError) as e:
                        print(f"Warning: Could not read UI value for {key}, using default. Error: {e}")
                        new_preprocess_settings[key] = defaults[key]
                else:
                    # Handle cases where widget name doesn't directly match key_var (e.g., binarization_type)
                    if key == "binarization_type":
                        new_preprocess_settings[key] = widgets['binarization_type_var'].get()
                    else:
                        print(f"Warning: UI variable for preprocessing key '{key}' not found.")
                        new_preprocess_settings[key] = defaults[key]

            # Validate specific numeric values
            block_size = new_preprocess_settings.get('adaptive_block_size', defaults['adaptive_block_size'])
            if block_size < 3 or block_size % 2 == 0:
                messagebox.showwarning("Invalid Value", f"Adaptive Block Size ({block_size}) must be odd and >= 3. Using default.", parent=self.app.master)
                new_preprocess_settings['adaptive_block_size'] = defaults['adaptive_block_size']
                widgets['adaptive_block_size_var'].set(defaults['adaptive_block_size']) # Reset UI

            median_ksize = new_preprocess_settings.get('median_blur_ksize', defaults['median_blur_ksize'])
            if median_ksize < 3 or median_ksize % 2 == 0:
                messagebox.showwarning("Invalid Value", f"Median Blur KSize ({median_ksize}) must be odd and >= 3. Using default.", parent=self.app.master)
                new_preprocess_settings['median_blur_ksize'] = defaults['median_blur_ksize']
                widgets['median_blur_ksize_var'].set(defaults['median_blur_ksize']) # Reset UI

            morph_ksize = new_preprocess_settings.get('morph_ksize', defaults['morph_ksize'])
            if morph_ksize < 1:
                messagebox.showwarning("Invalid Value", f"Morph KSize ({morph_ksize}) must be >= 1. Using default.", parent=self.app.master)
                new_preprocess_settings['morph_ksize'] = defaults['morph_ksize']
                widgets['morph_ksize_var'].set(defaults['morph_ksize']) # Reset UI

            scale_factor = new_preprocess_settings.get('scale_factor', defaults['scale_factor'])
            if scale_factor <= 0:
                messagebox.showwarning("Invalid Value", f"Scale Factor ({scale_factor}) must be > 0. Using default.", parent=self.app.master)
                new_preprocess_settings['scale_factor'] = defaults['scale_factor']
                widgets['scale_factor_var'].set(defaults['scale_factor']) # Reset UI

            sharpen_strength = new_preprocess_settings.get('sharpening_strength', defaults['sharpening_strength'])
            if not (0.0 <= sharpen_strength <= 1.0):
                messagebox.showwarning("Invalid Value", f"Sharpen Strength ({sharpen_strength:.2f}) must be between 0.0 and 1.0. Clamping.", parent=self.app.master)
                sharpen_strength = max(0.0, min(1.0, sharpen_strength))
                new_preprocess_settings['sharpening_strength'] = sharpen_strength
                widgets['sharpening_strength_var'].set(sharpen_strength) # Reset UI
                widgets['sharpening_strength_label_var'].set(f"{sharpen_strength:.2f}") # Reset UI label

            # Validate new cutout settings
            cutout_pad = new_preprocess_settings.get('cutout_padding', defaults['cutout_padding'])
            if cutout_pad < 0:
                messagebox.showwarning("Invalid Value", f"Cutout Padding ({cutout_pad}) must be >= 0. Using default.", parent=self.app.master)
                new_preprocess_settings['cutout_padding'] = defaults['cutout_padding']
                widgets['cutout_padding_var'].set(defaults['cutout_padding']) # Reset UI

            cutout_thresh = new_preprocess_settings.get('cutout_bg_threshold', defaults['cutout_bg_threshold'])
            if not (0 <= cutout_thresh <= 127):
                messagebox.showwarning("Invalid Value", f"Cutout BG Threshold ({cutout_thresh}) must be between 0 and 127. Using default.", parent=self.app.master)
                new_preprocess_settings['cutout_bg_threshold'] = defaults['cutout_bg_threshold']
                widgets['cutout_bg_threshold_var'].set(defaults['cutout_bg_threshold']) # Reset UI


            roi.preprocessing = new_preprocess_settings # Update the ROI's dict

            self.update_roi_list() # Update listbox display immediately

            self.app.update_status(f"Settings updated for '{roi.name}'. (Save ROIs to persist)")
            print(f"Applied in-memory settings for {roi.name}")

        except tk.TclError:
            messagebox.showerror("Error", "Could not read settings from UI (widgets might be destroyed).", parent=self.app.master)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply ROI settings: {e}", parent=self.app.master)


    def pick_color(self, color_type):
        """Opens a color chooser dialog. color_type is 'target' or 'replace'."""
        roi = self.get_selected_roi_object()
        if not roi: return

        if color_type == 'target':
            var = self.color_widgets['target_color_var']
            label = self.color_widgets['target_color_label']
            title = "Choose Target Color"
        elif color_type == 'replace':
            var = self.color_widgets['replace_color_var']
            label = self.color_widgets['replace_color_label']
            title = "Choose Replacement Color"
        else:
            return # Invalid type

        initial_color_hex = var.get()
        try:
            color_code = colorchooser.askcolor(title=title,
                                               initialcolor=initial_color_hex,
                                               parent=self.app.master)
            if color_code and color_code[1]:
                new_hex_color = color_code[1]
                var.set(new_hex_color)
                label.config(background=new_hex_color)
                # print(f"{color_type.capitalize()} color picked for {roi.name}: {new_hex_color}")
        except Exception as e:
            messagebox.showerror("Color Picker Error", f"Failed to open color picker: {e}", parent=self.app.master)

    def pick_color_from_screen(self):
        """Starts the screen color picking process (for target color)."""
        roi = self.get_selected_roi_object()
        if not roi:
            messagebox.showwarning("Warning", "Select an ROI first.", parent=self.app.master)
            return

        self.app.update_status("Screen Color Picker: Click anywhere on screen (Esc to cancel).")
        # Use the fixed ScreenColorPicker
        picker = ScreenColorPicker(self.app.master)
        picker.grab_color(self._on_screen_color_picked) # Pass callback

    def _on_screen_color_picked(self, color_rgb):
        """Callback function after screen color is picked (for target color)."""
        if color_rgb:
            roi = self.get_selected_roi_object()
            if roi:
                hex_color = ROI.rgb_to_hex(color_rgb)
                self.color_widgets['target_color_var'].set(hex_color)
                self.color_widgets['target_color_label'].config(background=hex_color)
                self.app.update_status(f"Screen color picked: {hex_color}. Apply settings if desired.")
                print(f"Screen color picked for {roi.name} target: {color_rgb} -> {hex_color}")
            else:
                self.app.update_status("Screen color picked, but no ROI selected.")
        else:
            self.app.update_status("Screen color picking cancelled.")

    def show_original_preview(self):
        """Shows a preview of the original selected ROI content."""
        self._show_preview(processed=False)

    def show_processed_preview(self):
        """Shows a preview of the selected ROI after color filtering AND preprocessing."""
        self._show_preview(processed=True)

    def _show_preview(self, processed=False):
        """Helper function to generate and show ROI previews."""
        roi = self.get_selected_roi_object()
        if not roi:
            messagebox.showwarning("Warning", "No ROI selected.", parent=self.app.master)
            return

        source_frame = None
        if self.app.using_snapshot and self.app.snapshot_frame is not None:
            source_frame = self.app.snapshot_frame
        elif self.app.current_frame is not None:
            source_frame = self.app.current_frame
        elif self.app.selected_hwnd:
            self.app.update_status("Capturing frame for preview...")
            source_frame = capture_window(self.app.selected_hwnd) # Use app's capture method
            if source_frame is not None:
                self.app.current_frame = source_frame
                self.app.update_status("Frame captured for preview.")
            else:
                self.app.update_status("Failed to capture frame for preview.")

        if source_frame is None:
            messagebox.showerror("Error", "No frame available to generate preview.", parent=self.app.master)
            return

        roi_img_original = roi.extract_roi(source_frame)
        if roi_img_original is None:
            messagebox.showerror("Error", f"Could not extract ROI '{roi.name}' from frame.", parent=self.app.master)
            return

        preview_img = roi_img_original
        title_suffix = "Original"

        if processed:
            title_suffix = "Processed"
            # Apply the *current UI settings* for preview
            try:
                # Create a temporary ROI instance with current UI settings
                temp_roi = ROI("temp_preview", 0,0,1,1) # Dummy coords

                # Apply color filter settings from UI
                temp_roi.color_filter_enabled = self.color_widgets['enabled_var'].get()
                temp_roi.target_color = ROI.hex_to_rgb(self.color_widgets['target_color_var'].get())
                temp_roi.replacement_color = ROI.hex_to_rgb(self.color_widgets['replace_color_var'].get())
                temp_roi.color_threshold = self.color_widgets['threshold_var'].get()

                # Apply preprocessing settings from UI
                temp_preprocess = {}
                widgets = self.preprocess_widgets
                defaults = ROI.DEFAULT_PREPROCESSING
                for key in defaults:
                    var_name = f"{key}_var"
                    if var_name in widgets:
                        # Get value, special handling for doublevar
                        if isinstance(widgets[var_name], tk.DoubleVar):
                            value = round(widgets[var_name].get(), 3)
                        else:
                            value = widgets[var_name].get()
                        temp_preprocess[key] = value
                    elif key == "binarization_type":
                        temp_preprocess[key] = widgets['binarization_type_var'].get()
                    else:
                        temp_preprocess[key] = defaults[key]
                temp_roi.preprocessing = temp_preprocess

                # Apply processing steps in the correct order
                img_after_color = temp_roi.apply_color_filter(roi_img_original.copy())
                # Pass the color-filtered image to preprocessing
                preview_img = temp_roi.apply_ocr_preprocessing(img_after_color)

                if preview_img is None:
                    messagebox.showerror("Error", "Failed to apply processing for preview.", parent=self.app.master)
                    return

            except Exception as e:
                messagebox.showerror("Error", f"Error applying processing for preview: {e}", parent=self.app.master)
                import traceback
                traceback.print_exc()
                return

        # Convert final preview image for display (handle grayscale or color)
        try:
            if len(preview_img.shape) == 2: # Grayscale
                preview_img_rgb = cv2.cvtColor(preview_img, cv2.COLOR_GRAY2RGB)
            elif len(preview_img.shape) == 3 and preview_img.shape[2] == 3: # BGR/RGB
                # Assume BGR from OpenCV steps, convert to RGB for display
                preview_img_rgb = cv2.cvtColor(preview_img, cv2.COLOR_BGR2RGB)
            else:
                raise ValueError("Unsupported image format for preview")
        except (cv2.error, ValueError) as e:
            messagebox.showerror("Preview Error", f"Failed to convert image for display: {e}", parent=self.app.master)
            return

        PreviewWindow(self.app.master, f"ROI Preview: {roi.name} - {title_suffix}", preview_img_rgb)


    # --- Other methods (on_roi_selection_toggled, update_roi_list, save_rois, move, delete, configure_overlay) ---

    def on_roi_selection_toggled(self, active):
        """Callback from App when ROI selection mode changes."""
        if active:
            self.create_roi_btn.config(text="Cancel Define")
            # Update status based on whether we are redefining or creating new
            if self.app.roi_to_redefine:
                self.app.update_status(f"Redefining '{self.app.roi_to_redefine}'. Drag on preview.")
            else:
                self.app.update_status("ROI selection active. Drag on preview.")
            self.app.master.config(cursor="crosshair")
        else:
            self.create_roi_btn.config(text="Define ROI")
            self.app.master.config(cursor="")
            # Status is updated by the app when cancelling or finishing

    def update_roi_list(self):
        current_selection_index = self.roi_listbox.curselection()
        selected_text = self.roi_listbox.get(current_selection_index[0]) if current_selection_index else None

        self.roi_listbox.delete(0, tk.END)
        for roi in self.app.rois:
            if roi.name == SNIP_ROI_NAME: continue

            # Overlay Status
            overlay_config = get_overlay_config_for_roi(roi.name)
            is_overlay_enabled = overlay_config.get('enabled', True)
            overlay_prefix = "[O]" if is_overlay_enabled else "[ ]"

            # Color Filter Status
            color_prefix = "[C]" if roi.color_filter_enabled else "[ ]"

            # Preprocessing Status (Basic check)
            preprocess_enabled = any(v for k, v in roi.preprocessing.items() if isinstance(v, bool) and v and k not in ['cutout_enabled', 'invert_colors', 'grayscale', 'scaling_enabled']) \
                                 or roi.preprocessing.get("binarization_type", "None") != "None" \
                                 or roi.preprocessing.get("sharpening_strength", 0.0) > 0.0
            preprocess_prefix = "[P]" if preprocess_enabled else "[ ]"

            # Cutout Status
            cutout_prefix = "[X]" if roi.preprocessing.get("cutout_enabled", False) else "[ ]"

            # Invert Status
            invert_prefix = "[I]" if roi.preprocessing.get("invert_colors", False) else "[ ]"

            # Construct the display string with all indicators
            self.roi_listbox.insert(tk.END, f"{overlay_prefix}{color_prefix}{preprocess_prefix}{cutout_prefix}{invert_prefix} {roi.name}")

        new_idx_to_select = -1
        if selected_text:
            # Extract name robustly
            selected_name = selected_text.split("]")[-1].strip()
            all_names_in_listbox = [item.split("]")[-1].strip() for item in self.roi_listbox.get(0, tk.END)]
            try:
                new_idx_to_select = all_names_in_listbox.index(selected_name)
            except ValueError: pass

        if new_idx_to_select != -1:
            self.roi_listbox.selection_clear(0, tk.END)
            self.roi_listbox.selection_set(new_idx_to_select)
            self.roi_listbox.activate(new_idx_to_select)
            self.roi_listbox.see(new_idx_to_select)

        if hasattr(self.app, 'overlay_tab') and self.app.overlay_tab.frame.winfo_exists():
            self.app.overlay_tab.update_roi_list()

        self.on_roi_selected() # Update button states and config UI

    def save_rois_for_current_game(self):
        if not self.app.selected_hwnd:
            messagebox.showwarning("Save ROIs", "No game window selected.", parent=self.app.master)
            return
        rois_to_save = [roi for roi in self.app.rois if roi.name != SNIP_ROI_NAME]

        saved_path = save_rois(rois_to_save, self.app.selected_hwnd)
        if saved_path is not None:
            self.app.config_file = saved_path
            self.app.update_status(f"Saved {len(rois_to_save)} ROIs for current game.")
            self.app.master.title(f"Visual Novel Translator - {os.path.basename(saved_path)}")
        else:
            self.app.update_status("Failed to save ROIs for current game.")

    def move_roi_up(self):
        selection = self.roi_listbox.curselection()
        if not selection or selection[0] == 0: return
        roi = self.get_selected_roi_object()
        if not roi: return

        try:
            idx_in_app_list = self.app.rois.index(roi)
            prev_app_idx = idx_in_app_list - 1
            while prev_app_idx >= 0 and self.app.rois[prev_app_idx].name == SNIP_ROI_NAME:
                prev_app_idx -= 1
            if prev_app_idx < 0: return

            self.app.rois[idx_in_app_list], self.app.rois[prev_app_idx] = self.app.rois[prev_app_idx], self.app.rois[idx_in_app_list]
            self.update_roi_list() # Rebuild and reselect
        except (ValueError, IndexError) as e:
            print(f"Error finding ROI for move up: {e}")

    def move_roi_down(self):
        selection = self.roi_listbox.curselection()
        if not selection: return
        idx_in_listbox = selection[0]
        # Need to count non-snip ROIs for correct index check
        non_snip_rois_count = sum(1 for r in self.app.rois if r.name != SNIP_ROI_NAME)
        if idx_in_listbox >= non_snip_rois_count - 1: return

        roi = self.get_selected_roi_object()
        if not roi: return

        try:
            idx_in_app_list = self.app.rois.index(roi)
            next_app_idx = idx_in_app_list + 1
            while next_app_idx < len(self.app.rois) and self.app.rois[next_app_idx].name == SNIP_ROI_NAME:
                next_app_idx += 1
            if next_app_idx >= len(self.app.rois): return

            self.app.rois[idx_in_app_list], self.app.rois[next_app_idx] = self.app.rois[next_app_idx], self.app.rois[idx_in_app_list]
            self.update_roi_list() # Rebuild and reselect
        except (ValueError, IndexError) as e:
            print(f"Error finding ROI for move down: {e}")


    def delete_selected_roi(self):
        roi = self.get_selected_roi_object()
        if not roi: return
        if roi.name == SNIP_ROI_NAME: return

        confirm = messagebox.askyesno("Delete ROI", f"Delete ROI '{roi.name}'?", parent=self.app.master)
        if not confirm: return

        self.app.rois.remove(roi)

        all_overlay_settings = get_setting("overlay_settings", {})
        if roi.name in all_overlay_settings:
            del all_overlay_settings[roi.name]
            update_settings({"overlay_settings": all_overlay_settings})

        if hasattr(self.app, 'overlay_manager'):
            self.app.overlay_manager.destroy_overlay(roi.name)

        if roi.name in self.app.text_history: del self.app.text_history[roi.name]
        if roi.name in self.app.stable_texts: del self.app.stable_texts[roi.name]

        def safe_update(widget_name, update_method, data):
            widget = getattr(self.app, widget_name, None)
            if widget and hasattr(widget, 'frame') and widget.frame.winfo_exists():
                try: update_method(data)
                except tk.TclError: pass
                except Exception as e: print(f"Error updating {widget_name} after delete: {e}")

        safe_update('text_tab', self.app.text_tab.update_text, self.app.text_history)
        safe_update('stable_text_tab', self.app.stable_text_tab.update_text, self.app.stable_texts)

        self.update_roi_list()
        self.app.update_status(f"ROI '{roi.name}' deleted. (Save ROIs to persist)")

    def redefine_selected_roi(self):
        """Initiates the process to redefine the selected ROI's boundaries."""
        roi = self.get_selected_roi_object()
        if not roi:
            messagebox.showwarning("Warning", "No ROI selected to redefine.", parent=self.app.master)
            return

        # Set the state in the app to indicate which ROI is being redefined
        self.app.roi_to_redefine = roi.name

        # Activate the ROI selection mode (this will also handle snapshotting)
        self.app.toggle_roi_selection()

    def configure_selected_overlay(self):
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

            notebook_widget.select(overlay_tab_widget)

            if hasattr(self.app.overlay_tab, 'roi_names_for_combo') and roi.name in self.app.overlay_tab.roi_names_for_combo:
                self.app.overlay_tab.selected_roi_var.set(roi.name)
                self.app.overlay_tab.load_roi_config()
            else:
                print(f"ROI '{roi.name}' not found in Overlay Tab combo after switch.")

        except (tk.TclError, AttributeError) as e:
            print(f"Error switching to overlay tab: {e}")
            messagebox.showerror("Error", "Could not switch to Overlay tab.", parent=self.app.master)
        except Exception as e:
            print(f"Unexpected error configuring overlay: {e}")

# --- END OF FILE ui/roi_tab.py ---