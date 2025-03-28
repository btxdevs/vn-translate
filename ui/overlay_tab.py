# --- START OF FILE ui/overlay_tab.py ---

import tkinter as tk
from tkinter import ttk, colorchooser, messagebox
from ui.base import BaseTab
from utils.settings import get_overlay_config_for_roi, save_overlay_config_for_roi, DEFAULT_SINGLE_OVERLAY_CONFIG
import tkinter.font as tkFont
import re

# --- Module-level constant for the special Snip overlay config ---
SNIP_ROI_NAME = "Snip Translate"
# --- End constant ---

class OverlayTab(BaseTab):
    """Tab for configuring floating overlay appearance."""

    DEFAULT_CONFIG = DEFAULT_SINGLE_OVERLAY_CONFIG
    JUSTIFY_OPTIONS = ["left", "center", "right"]
    # SNIP_ROI_NAME is now defined at the module level above

    def setup_ui(self):
        main_frame = ttk.Frame(self.frame, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Global Enable
        global_frame = ttk.Frame(main_frame)
        global_frame.pack(fill=tk.X, pady=(0, 10))
        initial_global_state = True
        if hasattr(self.app, 'overlay_manager'):
            initial_global_state = self.app.overlay_manager.global_overlays_enabled
        self.global_enable_var = tk.BooleanVar(value=initial_global_state)
        global_check = ttk.Checkbutton(global_frame, text="Enable Translation Overlays Globally (excl. Snip)",
                                       variable=self.global_enable_var, command=self.toggle_global_overlays)
        global_check.pack(side=tk.LEFT)

        # ROI Selection
        roi_select_frame = ttk.Frame(main_frame)
        roi_select_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(roi_select_frame, text="Configure Overlay for:").pack(side=tk.LEFT, padx=(0, 5))

        # Initial population - update_roi_list will add the snip option
        self.roi_names_for_combo = [] # Store names specifically for the combobox
        self.selected_roi_var = tk.StringVar()
        self.roi_combo = ttk.Combobox(roi_select_frame, textvariable=self.selected_roi_var,
                                      values=self.roi_names_for_combo, state="readonly", width=25)
        self.roi_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.roi_combo.bind("<<ComboboxSelected>>", self.load_roi_config)

        # Configuration Area
        self.config_frame = ttk.LabelFrame(main_frame, text="Overlay Appearance Settings", padding=10)
        self.config_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.widgets = {}
        self.build_config_widgets()
        # Use after_idle to ensure app.rois is populated if loaded automatically
        self.app.master.after_idle(self.load_initial_config)


    def build_config_widgets(self):
        frame = self.config_frame
        for widget in frame.winfo_children():
            widget.destroy()
        self.widgets = {}

        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=0)
        row_num = 0

        # Enabled Checkbox (Label text changes based on selected ROI)
        self.widgets['enabled_var'] = tk.BooleanVar()
        self.widgets['enabled_check'] = ttk.Checkbutton(frame, text="Enabled", variable=self.widgets['enabled_var'])
        self.widgets['enabled_check'].grid(row=row_num, column=0, columnspan=4, sticky=tk.W, pady=5)
        row_num += 1

        # Font Family
        ttk.Label(frame, text="Font Family:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        try: available_fonts = sorted([f for f in tkFont.families() if not f.startswith('@')])
        except Exception: available_fonts = ["Arial", "Segoe UI", "Times New Roman"] # Fallback
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

        # Alpha/Transparency Slider
        ttk.Label(frame, text="Transparency:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        self.widgets['alpha_var'] = tk.DoubleVar(value=self.DEFAULT_CONFIG['alpha'])
        self.widgets['alpha_label_var'] = tk.StringVar(value=f"{self.widgets['alpha_var'].get():.2f}")
        alpha_slider = ttk.Scale(
            frame, from_=0.1, to=1.0, orient=tk.HORIZONTAL, variable=self.widgets['alpha_var'],
            length=150, command=self._update_alpha_label
        )
        alpha_slider.grid(row=row_num, column=1, sticky=tk.EW, padx=5, pady=2)
        alpha_value_label = ttk.Label(frame, textvariable=self.widgets['alpha_label_var'], width=5)
        alpha_value_label.grid(row=row_num, column=2, sticky=tk.W, padx=5, pady=2)
        row_num += 1

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

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=row_num, column=0, columnspan=4, pady=15)
        save_button = ttk.Button(button_frame, text="Apply Appearance", command=self.save_roi_config)
        save_button.pack(side=tk.LEFT, padx=5)
        self.widgets['reset_geom_button'] = ttk.Button(button_frame, text="Reset Position/Size", command=self.reset_geometry)
        self.widgets['reset_geom_button'].pack(side=tk.LEFT, padx=5)

        self.set_widgets_state(tk.DISABLED) # Initially disabled until an ROI is loaded

    def _update_alpha_label(self, value):
        """Updates the label next to the alpha slider."""
        if 'alpha_label_var' in self.widgets:
            try:
                self.widgets['alpha_label_var'].set(f"{float(value):.2f}")
            except: pass

    def update_color_preview(self, config_key):
        var = self.widgets.get(f"{config_key}_var")
        preview = self.widgets.get(f"{config_key}_preview")
        if var and preview:
            color = var.get()
            try:
                preview.winfo_rgb(color) # Check if color is valid
                preview.config(background=color)
            except tk.TclError:
                # Use default background if invalid color typed
                preview.config(background=self.DEFAULT_CONFIG.get(config_key, 'SystemButtonFace'))

    def choose_color(self, config_key, title):
        var = self.widgets.get(f"{config_key}_var")
        preview = self.widgets.get(f"{config_key}_preview")
        if not var or not preview: return
        initial_color = var.get()
        try:
            # Validate initial color before opening picker
            preview.winfo_rgb(initial_color)
            color_code = colorchooser.askcolor(title=title, initialcolor=initial_color, parent=self.frame)
        except tk.TclError:
            # If initial color is invalid, open picker without it
            color_code = colorchooser.askcolor(title=title, parent=self.frame)

        if color_code and color_code[1]: # If a color was chosen and it's valid
            hex_color = color_code[1]
            var.set(hex_color)
            try: preview.config(background=hex_color)
            except tk.TclError: print(f"Error setting preview: {hex_color}")


    def load_roi_config(self, event=None):
        roi_name = self.selected_roi_var.get()
        if not roi_name:
            self.set_widgets_state(tk.DISABLED)
            self.config_frame.config(text="Overlay Appearance Settings (No Selection)")
            return

        # Special handling for the Snip overlay name
        is_snip_config = (roi_name == SNIP_ROI_NAME) # Use module constant
        config_label = f"Appearance Settings for [Snip Window]" if is_snip_config else f"Appearance Settings for [{roi_name}]"
        self.config_frame.config(text=config_label)

        config = get_overlay_config_for_roi(roi_name)

        # Update UI widgets
        try:
            # Update 'Enabled' checkbox text and state
            enabled_text = "Enabled (Always On for Snip)" if is_snip_config else "Enabled for this ROI"
            self.widgets['enabled_check'].config(text=enabled_text)
            self.widgets['enabled_var'].set(config.get('enabled', self.DEFAULT_CONFIG['enabled']))
            # Disable the 'Enabled' checkbox for the snip config as it's always conceptually enabled
            self.widgets['enabled_check'].config(state=tk.DISABLED if is_snip_config else tk.NORMAL)

            self.widgets['font_family_var'].set(config.get('font_family', self.DEFAULT_CONFIG['font_family']))
            self.widgets['font_size_var'].set(config.get('font_size', self.DEFAULT_CONFIG['font_size']))
            self.widgets['font_color_var'].set(config.get('font_color', self.DEFAULT_CONFIG['font_color']))
            self.widgets['bg_color_var'].set(config.get('bg_color', self.DEFAULT_CONFIG['bg_color']))
            self.widgets['justify_var'].set(config.get('justify', self.DEFAULT_CONFIG['justify']))
            self.widgets['wraplength_var'].set(config.get('wraplength', self.DEFAULT_CONFIG['wraplength']))
            self.widgets['alpha_var'].set(config.get('alpha', self.DEFAULT_CONFIG['alpha']))
            self._update_alpha_label(self.widgets['alpha_var'].get())

            self.update_color_preview('font_color')
            self.update_color_preview('bg_color')

            # Disable "Reset Position/Size" for Snip window as it's temporary
            self.widgets['reset_geom_button'].config(state=tk.DISABLED if is_snip_config else tk.NORMAL)

            # Enable all other widgets (except the 'Enabled' checkbox if it's the snip config)
            global_state = self.global_enable_var.get()
            # Snip config widgets are enabled even if global overlays are off
            enable_widgets = global_state or is_snip_config
            self.set_widgets_state(tk.NORMAL if enable_widgets else tk.DISABLED)
            # Re-apply disabled state specifically for snip's 'enabled' checkbox and reset button
            if is_snip_config:
                if 'enabled_check' in self.widgets and self.widgets['enabled_check'].winfo_exists():
                    self.widgets['enabled_check'].config(state=tk.DISABLED)
                if 'reset_geom_button' in self.widgets and self.widgets['reset_geom_button'].winfo_exists():
                    self.widgets['reset_geom_button'].config(state=tk.DISABLED)

        except tk.TclError:
            print("Error updating overlay config UI elements (might be destroyed)")
            self.set_widgets_state(tk.DISABLED)


    def save_roi_config(self):
        roi_name = self.selected_roi_var.get()
        if not roi_name:
            messagebox.showwarning("Warning", "No ROI or Snip Window selected.", parent=self.app.master)
            return

        is_snip_config = (roi_name == SNIP_ROI_NAME) # Use module constant
        new_appearance_config = {}
        try:
            new_appearance_config = {
                # Read 'enabled' state unless it's the snip config (which is always true conceptually)
                'enabled': True if is_snip_config else self.widgets['enabled_var'].get(),
                'font_family': self.widgets['font_family_var'].get(),
                'font_size': self.widgets['font_size_var'].get(),
                'font_color': self.widgets['font_color_var'].get(),
                'bg_color': self.widgets['bg_color_var'].get(),
                'justify': self.widgets['justify_var'].get(),
                'wraplength': self.widgets['wraplength_var'].get(),
                'alpha': round(self.widgets['alpha_var'].get(), 3),
            }
            # Geometry is handled separately by reset_geometry and window interaction
        except (ValueError, tk.TclError) as e:
            messagebox.showerror("Error Reading Value", f"Could not read setting: {e}", parent=self.app.master)
            return
        except Exception as e:
            messagebox.showerror("Error Reading Value", f"Unexpected error: {e}", parent=self.app.master)
            return

        # Validation (Alpha range handled by slider)
        if not 8 <= new_appearance_config['font_size'] <= 72: messagebox.showerror("Error", "Font size must be 8-72.", parent=self.app.master); return
        if not 50 <= new_appearance_config['wraplength'] <= 5000: messagebox.showerror("Error", "Wrap width must be 50-5000.", parent=self.app.master); return
        try: self.frame.winfo_rgb(new_appearance_config['font_color'])
        except tk.TclError: messagebox.showerror("Error", f"Invalid Font Color: '{new_appearance_config['font_color']}'.", parent=self.app.master); return
        try: self.frame.winfo_rgb(new_appearance_config['bg_color'])
        except tk.TclError: messagebox.showerror("Error", f"Invalid Background Color: '{new_appearance_config['bg_color']}'.", parent=self.app.master); return

        # --- Save using utility function ---
        if save_overlay_config_for_roi(roi_name, new_appearance_config):
            config_type = "Snip window appearance" if is_snip_config else f"Overlay appearance for {roi_name}"
            self.app.update_status(f"{config_type} saved.")
            if hasattr(self.app, 'roi_tab'):
                # Update the main ROI list display if an actual ROI was changed
                if not is_snip_config:
                    self.app.roi_tab.update_roi_list()

            # Apply live changes via OverlayManager ONLY for managed ROIs
            if not is_snip_config and hasattr(self.app, 'overlay_manager'):
                self.app.overlay_manager.update_overlay_config(roi_name, new_appearance_config)
            # Snip window config is read when it's created next time

        else:
            messagebox.showerror("Error", f"Failed to save overlay settings for {roi_name}.", parent=self.app.master)


    def reset_geometry(self):
        roi_name = self.selected_roi_var.get()
        if not roi_name or roi_name == SNIP_ROI_NAME: # Use module constant
            messagebox.showwarning("Warning", "No ROI selected or cannot reset Snip window.", parent=self.app.master)
            return
        if messagebox.askyesno("Confirm Reset", f"Reset position/size for ROI '{roi_name}'?", parent=self.app.master):
            if hasattr(self.app, 'overlay_manager'):
                if self.app.overlay_manager.reset_overlay_geometry(roi_name):
                    self.app.update_status(f"Geometry reset for {roi_name}.")
                else: messagebox.showerror("Error", f"Failed to reset geometry for {roi_name}.", parent=self.app.master)
            else: messagebox.showerror("Error", "Overlay Manager not available.", parent=self.app.master)

    def toggle_global_overlays(self):
        enabled = self.global_enable_var.get()
        if hasattr(self.app, 'overlay_manager'):
            self.app.overlay_manager.set_global_overlays_enabled(enabled)
            # Reload config to potentially re-enable widgets if global state changed
            self.load_roi_config()
        else:
            # Revert checkbox if manager not found
            self.global_enable_var.set(not enabled)

    def update_roi_list(self):
        """Updates the combobox with current ROIs + the special Snip option."""
        game_rois = [roi.name for roi in self.app.rois if roi.name != SNIP_ROI_NAME] # Exclude snip here
        # Ensure SNIP_ROI_NAME is always present
        self.roi_names_for_combo = sorted(game_rois) + [SNIP_ROI_NAME] # Use module constant

        current_selection = self.selected_roi_var.get()
        self.roi_combo['values'] = self.roi_names_for_combo

        if current_selection in self.roi_names_for_combo:
            self.roi_combo.set(current_selection)
        elif self.roi_names_for_combo:
            # Default to first item (usually first ROI or SNIP if no ROIs)
            self.roi_combo.current(0)
            # Load config for the newly selected default
            self.load_roi_config()
        else:
            # Should not happen as SNIP_ROI_NAME is always added
            self.roi_combo.set("")
            self.selected_roi_var.set("")
            self.set_widgets_state(tk.DISABLED)
            self.config_frame.config(text="Overlay Appearance Settings (No Selection)")


    def load_initial_config(self):
        """Loads the list and selects the first/last used item."""
        self.update_roi_list()
        # Don't automatically call load_roi_config here,
        # let update_roi_list handle setting default if needed and trigger load


    def set_widgets_state(self, state):
        """Enable/disable all configuration widgets."""
        if not hasattr(self, 'config_frame') or not self.config_frame.winfo_exists(): return

        valid_tk_states = (tk.NORMAL, tk.DISABLED, tk.ACTIVE)
        combobox_state = 'readonly' if state == tk.NORMAL else tk.DISABLED
        scale_state = tk.NORMAL if state == tk.NORMAL else tk.DISABLED
        actual_state = state if state in valid_tk_states else tk.DISABLED

        # List of widgets to manage state for (exclude labels, previews, frames)
        # Find widgets precisely within config_frame and button_frame
        container_frames = [self.config_frame]
        button_frame = next((w for w in self.config_frame.winfo_children() if isinstance(w, ttk.Frame)), None)
        if button_frame: container_frames.append(button_frame)

        for frame in container_frames:
            for widget in frame.winfo_children():
                widget_class = widget.winfo_class()
                try:
                    if widget_class in ('TButton', 'TSpinbox', 'TCheckbutton', 'TEntry', 'Text'):
                        # Keep "Apply Appearance" button always enabled? Or disable when no ROI?
                        # For now, disable all based on `actual_state`
                        widget.configure(state=actual_state)
                    elif widget_class == 'TCombobox':
                        widget.configure(state=combobox_state)
                    elif widget_class == 'Scale' or widget_class == 'TScale': # Handle Tkinter and ttk Scale
                        widget.configure(state=scale_state)
                    # Labels, Frames, Previews are not disabled
                except tk.TclError: pass # Ignore errors for widgets being destroyed
                except Exception as e: print(f"Error setting state for {widget_class}: {e}")

        # Special handling after bulk state change:
        # If disabling, ensure snip's enable/reset buttons remain disabled
        # If enabling, ensure snip's enable/reset buttons are disabled IF snip is selected
        roi_name = self.selected_roi_var.get()
        is_snip_config = (roi_name == SNIP_ROI_NAME) # Use module constant
        if is_snip_config:
            # These should be disabled regardless of the main 'state' argument if snip is selected
            if 'enabled_check' in self.widgets and self.widgets['enabled_check'].winfo_exists():
                self.widgets['enabled_check'].config(state=tk.DISABLED)
            if 'reset_geom_button' in self.widgets and self.widgets['reset_geom_button'].winfo_exists():
                self.widgets['reset_geom_button'].config(state=tk.DISABLED)
        # Ensure Apply button is enabled if any config is selected and widgets are generally enabled
        apply_button = next((w for w in button_frame.winfo_children() if isinstance(w, ttk.Button) and w.cget('text') == "Apply Appearance"), None) if button_frame else None
        if apply_button:
            apply_button_state = tk.NORMAL if roi_name and actual_state == tk.NORMAL else tk.DISABLED
            try: apply_button.configure(state=apply_button_state)
            except tk.TclError: pass


# --- END OF FILE ui/overlay_tab.py ---