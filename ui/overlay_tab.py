# --- START OF FILE ui/overlay_tab.py ---

import tkinter as tk
from tkinter import ttk, colorchooser, messagebox
from ui.base import BaseTab
# Import settings functions directly as manager role is reduced here
from utils.settings import get_overlay_config_for_roi, save_overlay_config_for_roi, DEFAULT_SINGLE_OVERLAY_CONFIG
import tkinter.font as tkFont
import re

class OverlayTab(BaseTab):
    """Tab for configuring floating overlay appearance."""

    # Use the default config from settings
    DEFAULT_CONFIG = DEFAULT_SINGLE_OVERLAY_CONFIG

    # Position options removed
    JUSTIFY_OPTIONS = ["left", "center", "right"]

    def setup_ui(self):
        # --- Main Frame ---
        main_frame = ttk.Frame(self.frame, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Global Enable ---
        global_frame = ttk.Frame(main_frame)
        global_frame.pack(fill=tk.X, pady=(0, 10))

        initial_global_state = True
        if hasattr(self.app, 'overlay_manager'):
            initial_global_state = self.app.overlay_manager.global_overlays_enabled

        self.global_enable_var = tk.BooleanVar(value=initial_global_state)
        global_check = ttk.Checkbutton(global_frame, text="Enable Translation Overlays Globally",
                                       variable=self.global_enable_var, command=self.toggle_global_overlays)
        global_check.pack(side=tk.LEFT)

        # --- ROI Selection ---
        roi_select_frame = ttk.Frame(main_frame)
        roi_select_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(roi_select_frame, text="Configure Overlay for ROI:").pack(side=tk.LEFT, padx=(0, 5))

        self.roi_names = [roi.name for roi in self.app.rois]
        self.selected_roi_var = tk.StringVar()
        self.roi_combo = ttk.Combobox(roi_select_frame, textvariable=self.selected_roi_var,
                                      values=self.roi_names, state="readonly", width=25)
        if self.roi_names:
            self.roi_combo.current(0)
        self.roi_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.roi_combo.bind("<<ComboboxSelected>>", self.load_roi_config)

        # --- Configuration Area ---
        self.config_frame = ttk.LabelFrame(main_frame, text="Overlay Appearance Settings", padding=10)
        self.config_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.widgets = {}
        self.build_config_widgets() # Build widgets

        # Load initial config after UI is built
        self.app.master.after_idle(self.load_initial_config)


    def build_config_widgets(self):
        """Creates the widgets for overlay configuration within self.config_frame."""
        frame = self.config_frame
        for widget in frame.winfo_children():
            widget.destroy()

        self.widgets = {} # Reset dictionary

        # Grid configuration
        frame.columnconfigure(1, weight=1) # Allow entry/combo fields to expand
        frame.columnconfigure(3, weight=0) # Color preview fixed size

        row_num = 0

        # Enabled Checkbox
        self.widgets['enabled_var'] = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Enabled for this ROI", variable=self.widgets['enabled_var']).grid(row=row_num, column=0, columnspan=4, sticky=tk.W, pady=5)
        row_num += 1

        # Font Family
        ttk.Label(frame, text="Font Family:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        try:
            available_fonts = sorted([f for f in tkFont.families() if not f.startswith('@')])
        except Exception:
            available_fonts = ["Arial", "Segoe UI", "Times New Roman", "Courier New", "Verdana", "Tahoma", "MS Gothic"]
        self.widgets['font_family_var'] = tk.StringVar()
        self.widgets['font_family_combo'] = ttk.Combobox(frame, textvariable=self.widgets['font_family_var'], values=available_fonts, width=25)
        self.widgets['font_family_combo'].grid(row=row_num, column=1, columnspan=3, sticky=tk.EW, padx=5, pady=2)
        row_num += 1

        # Font Size
        ttk.Label(frame, text="Font Size:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        self.widgets['font_size_var'] = tk.IntVar(value=self.DEFAULT_CONFIG['font_size'])
        ttk.Spinbox(frame, from_=8, to=72, increment=1, width=5, textvariable=self.widgets['font_size_var']).grid(row=row_num, column=1, sticky=tk.W, padx=5, pady=2)
        row_num += 1

        # Font Color
        ttk.Label(frame, text="Font Color:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        self.widgets['font_color_var'] = tk.StringVar(value=self.DEFAULT_CONFIG['font_color'])
        font_color_entry = ttk.Entry(frame, textvariable=self.widgets['font_color_var'], width=10)
        font_color_entry.grid(row=row_num, column=1, sticky=tk.W, padx=5, pady=2)
        font_color_entry.bind("<FocusOut>", lambda e, key='font_color': self.update_color_preview(key))
        font_color_entry.bind("<Return>", lambda e, key='font_color': self.update_color_preview(key))
        self.widgets['font_color_btn'] = ttk.Button(frame, text="🎨", width=3, command=lambda: self.choose_color('font_color', 'Font Color'))
        self.widgets['font_color_btn'].grid(row=row_num, column=2, sticky=tk.W, padx=(0, 5), pady=2)
        self.widgets['font_color_preview'] = tk.Label(frame, text="   ", relief=tk.SUNKEN, width=3, borderwidth=1)
        self.widgets['font_color_preview'].grid(row=row_num, column=3, sticky=tk.W, padx=2)
        self.update_color_preview('font_color')
        row_num += 1

        # Background Color
        ttk.Label(frame, text="Background Color:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        self.widgets['bg_color_var'] = tk.StringVar(value=self.DEFAULT_CONFIG['bg_color'])
        bg_color_entry = ttk.Entry(frame, textvariable=self.widgets['bg_color_var'], width=10)
        bg_color_entry.grid(row=row_num, column=1, sticky=tk.W, padx=5, pady=2)
        bg_color_entry.bind("<FocusOut>", lambda e, key='bg_color': self.update_color_preview(key))
        bg_color_entry.bind("<Return>", lambda e, key='bg_color': self.update_color_preview(key))
        self.widgets['bg_color_btn'] = ttk.Button(frame, text="🎨", width=3, command=lambda: self.choose_color('bg_color', 'Background Color'))
        self.widgets['bg_color_btn'].grid(row=row_num, column=2, sticky=tk.W, padx=(0, 5), pady=2)
        self.widgets['bg_color_preview'] = tk.Label(frame, text="   ", relief=tk.SUNKEN, width=3, borderwidth=1)
        self.widgets['bg_color_preview'].grid(row=row_num, column=3, sticky=tk.W, padx=2)
        self.update_color_preview('bg_color')
        row_num += 1

        # Position Setting REMOVED

        # Justify
        ttk.Label(frame, text="Text Alignment:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        self.widgets['justify_var'] = tk.StringVar()
        self.widgets['justify_combo'] = ttk.Combobox(frame, textvariable=self.widgets['justify_var'], values=self.JUSTIFY_OPTIONS, state="readonly", width=10)
        self.widgets['justify_combo'].grid(row=row_num, column=1, sticky=tk.W, padx=5, pady=2)
        row_num += 1

        # Wraplength
        ttk.Label(frame, text="Wrap Width (px):").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        self.widgets['wraplength_var'] = tk.IntVar(value=self.DEFAULT_CONFIG['wraplength'])
        ttk.Spinbox(frame, from_=50, to=2000, increment=10, width=7, textvariable=self.widgets['wraplength_var']).grid(row=row_num, column=1, sticky=tk.W, padx=5, pady=2)
        row_num += 1

        # --- Buttons ---
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=row_num, column=0, columnspan=4, pady=15)

        save_button = ttk.Button(button_frame, text="Apply Appearance", command=self.save_roi_config)
        save_button.pack(side=tk.LEFT, padx=5)

        reset_geom_button = ttk.Button(button_frame, text="Reset Position/Size", command=self.reset_geometry)
        reset_geom_button.pack(side=tk.LEFT, padx=5)

        # Initially disable widgets until an ROI is selected
        self.set_widgets_state(tk.DISABLED)


    def update_color_preview(self, config_key):
        """Updates the color preview label based on the entry/variable."""
        var = self.widgets.get(f"{config_key}_var")
        preview = self.widgets.get(f"{config_key}_preview")
        if var and preview:
            color = var.get()
            try:
                preview.winfo_rgb(color)
                preview.config(background=color)
            except tk.TclError:
                preview.config(background=self.DEFAULT_CONFIG.get(config_key, 'SystemButtonFace'))

    def choose_color(self, config_key, title):
        """Opens a color chooser dialog and updates the variable and preview."""
        var = self.widgets.get(f"{config_key}_var")
        preview = self.widgets.get(f"{config_key}_preview")
        if not var or not preview: return

        initial_color = var.get()
        try:
            preview.winfo_rgb(initial_color)
            color_code = colorchooser.askcolor(title=title, initialcolor=initial_color, parent=self.frame)
        except tk.TclError:
            color_code = colorchooser.askcolor(title=title, parent=self.frame)

        if color_code and color_code[1]:
            hex_color = color_code[1]
            var.set(hex_color)
            try:
                preview.config(background=hex_color)
            except tk.TclError:
                print(f"Error setting preview for chosen color: {hex_color}")


    def load_roi_config(self, event=None):
        """Loads the configuration for the currently selected ROI into the UI."""
        roi_name = self.selected_roi_var.get()
        if not roi_name:
            self.set_widgets_state(tk.DISABLED)
            self.config_frame.config(text="Overlay Appearance Settings (No ROI Selected)")
            return

        # Use utility function to get merged config
        config = get_overlay_config_for_roi(roi_name)
        self.config_frame.config(text=f"Overlay Appearance Settings for [{roi_name}]")

        # Update UI widgets (only appearance settings controlled here)
        self.widgets['enabled_var'].set(config.get('enabled', self.DEFAULT_CONFIG['enabled']))
        self.widgets['font_family_var'].set(config.get('font_family', self.DEFAULT_CONFIG['font_family']))
        self.widgets['font_size_var'].set(config.get('font_size', self.DEFAULT_CONFIG['font_size']))
        self.widgets['font_color_var'].set(config.get('font_color', self.DEFAULT_CONFIG['font_color']))
        self.widgets['bg_color_var'].set(config.get('bg_color', self.DEFAULT_CONFIG['bg_color']))
        self.widgets['justify_var'].set(config.get('justify', self.DEFAULT_CONFIG['justify']))
        self.widgets['wraplength_var'].set(config.get('wraplength', self.DEFAULT_CONFIG['wraplength']))
        # Geometry is NOT loaded into this tab's UI elements

        # Update color previews
        self.update_color_preview('font_color')
        self.update_color_preview('bg_color')

        # Enable widgets if global overlays are enabled
        global_state = self.global_enable_var.get()
        self.set_widgets_state(tk.NORMAL if global_state else tk.DISABLED)


    def save_roi_config(self):
        """Saves the current UI APPEARANCE configuration for the selected ROI."""
        roi_name = self.selected_roi_var.get()
        if not roi_name:
            messagebox.showwarning("Warning", "No ROI selected to save configuration for.", parent=self.app.master)
            return

        # Read APPEARANCE values from widgets
        new_appearance_config = {}
        try:
            new_appearance_config = {
                'enabled': self.widgets['enabled_var'].get(),
                'font_family': self.widgets['font_family_var'].get(),
                'font_size': self.widgets['font_size_var'].get(),
                'font_color': self.widgets['font_color_var'].get(),
                'bg_color': self.widgets['bg_color_var'].get(),
                'justify': self.widgets['justify_var'].get(),
                'wraplength': self.widgets['wraplength_var'].get(),
            }
        except tk.TclError as e:
            messagebox.showerror("Error Reading Value", f"Could not read setting value: {e}", parent=self.app.master)
            return
        except Exception as e:
            messagebox.showerror("Error Reading Value", f"Unexpected error reading settings: {e}", parent=self.app.master)
            return


        # Validate values (similar to before, but exclude position/alpha)
        if not 8 <= new_appearance_config['font_size'] <= 72:
            messagebox.showerror("Error", "Font size must be between 8 and 72.", parent=self.app.master)
            return
        if not 50 <= new_appearance_config['wraplength'] <= 5000: # Adjusted min wrap width
            messagebox.showerror("Error", "Wrap width must be between 50 and 5000.", parent=self.app.master)
            return
        try: self.frame.winfo_rgb(new_appearance_config['font_color'])
        except tk.TclError:
            messagebox.showerror("Error", f"Invalid Font Color format: '{new_appearance_config['font_color']}'.", parent=self.app.master)
            return
        try: self.frame.winfo_rgb(new_appearance_config['bg_color'])
        except tk.TclError:
            messagebox.showerror("Error", f"Invalid Background Color format: '{new_appearance_config['bg_color']}'.", parent=self.app.master)
            return

        # Update via OverlayManager (which handles saving and applying live)
        if hasattr(self.app, 'overlay_manager'):
            self.app.overlay_manager.update_overlay_config(roi_name, new_appearance_config)
            self.app.update_status(f"Overlay appearance saved for {roi_name}.")
            # Update ROI list display indicator in roi_tab
            if hasattr(self.app, 'roi_tab'):
                self.app.roi_tab.update_roi_list()
        else:
            messagebox.showerror("Error", "Overlay Manager not available. Cannot save settings.", parent=self.app.master)

    def reset_geometry(self):
        """Resets the position and size for the selected overlay."""
        roi_name = self.selected_roi_var.get()
        if not roi_name:
            messagebox.showwarning("Warning", "No ROI selected to reset geometry for.", parent=self.app.master)
            return

        if messagebox.askyesno("Confirm Reset", f"Reset position and size for overlay '{roi_name}' to default?", parent=self.app.master):
            if hasattr(self.app, 'overlay_manager'):
                if self.app.overlay_manager.reset_overlay_geometry(roi_name):
                    self.app.update_status(f"Overlay geometry reset for {roi_name}.")
                else:
                    messagebox.showerror("Error", f"Failed to reset geometry for {roi_name}.", parent=self.app.master)
            else:
                messagebox.showerror("Error", "Overlay Manager not available.", parent=self.app.master)


    def toggle_global_overlays(self):
        """Callback for the global enable checkbox."""
        enabled = self.global_enable_var.get()
        if hasattr(self.app, 'overlay_manager'):
            # Manager handles saving the global state and showing/hiding/rebuilding
            self.app.overlay_manager.set_global_overlays_enabled(enabled)
            # Enable/disable the ROI specific config area based on this
            self.set_widgets_state(tk.NORMAL if enabled else tk.DISABLED)
            if enabled and self.selected_roi_var.get():
                # If re-enabling, ensure the config UI reflects the loaded state
                self.load_roi_config()
        else:
            print("Error: Overlay Manager not available.")
            self.global_enable_var.set(not enabled) # Revert checkbox


    def update_roi_list(self):
        """Called when the ROI list changes."""
        self.roi_names = [roi.name for roi in self.app.rois]
        current_selection = self.selected_roi_var.get()

        self.roi_combo['values'] = self.roi_names

        if current_selection in self.roi_names:
            self.roi_combo.set(current_selection)
        elif self.roi_names:
            self.roi_combo.current(0)
            self.load_roi_config() # Load config for the new first item
        else:
            self.roi_combo.set("")
            self.selected_roi_var.set("")
            self.set_widgets_state(tk.DISABLED)
            self.config_frame.config(text="Overlay Appearance Settings (No ROIs Defined)")


    def load_initial_config(self):
        """Load config for the initially selected ROI after UI is built."""
        self.update_roi_list()
        if self.selected_roi_var.get():
            self.load_roi_config()
        else:
            self.set_widgets_state(tk.DISABLED)
            self.config_frame.config(text="Overlay Appearance Settings (No ROIs Defined)")

    def set_widgets_state(self, state):
        """Enable or disable all configuration widgets in the config_frame."""
        if not hasattr(self, 'config_frame') or not self.config_frame.winfo_exists():
            return

        valid_tk_states = (tk.NORMAL, tk.DISABLED, tk.ACTIVE)
        combobox_state = 'readonly' if state == tk.NORMAL else tk.DISABLED
        actual_state = state if state in valid_tk_states else tk.DISABLED

        # Iterate through children of config_frame AND button_frame inside it
        container_frames = [self.config_frame]
        button_frame = next((w for w in self.config_frame.winfo_children() if isinstance(w, ttk.Frame)), None)
        if button_frame:
            container_frames.append(button_frame)

        for frame in container_frames:
            for widget in frame.winfo_children():
                widget_class = widget.winfo_class()
                try:
                    if widget_class in ('TButton', 'TSpinbox', 'TCheckbutton', 'TEntry', 'Text', 'Frame'): # Include Frame for grip
                        # Special handling for the grip Frame if needed, maybe change bg color?
                        if widget == self.widgets.get('grip'): # Example check
                            widget.configure(cursor="bottom_right_corner" if actual_state == tk.NORMAL else "")
                            widget.configure(bg='grey50' if actual_state == tk.NORMAL else 'grey80')
                        else:
                            widget.configure(state=actual_state)
                    elif widget_class == 'TCombobox':
                        widget.configure(state=combobox_state)
                    # Labels generally don't need state change
                except tk.TclError: pass # Ignore errors
                except Exception as e: print(f"Error setting state for {widget_class}: {e}")

# --- END OF FILE ui/overlay_tab.py ---