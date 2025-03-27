import tkinter as tk
from tkinter import ttk, colorchooser, messagebox # Added messagebox
from ui.base import BaseTab
from utils.settings import get_setting, update_settings # update_settings for saving
import tkinter.font as tkFont
import re # Need regex for color validation

class OverlayTab(BaseTab):
    """Tab for configuring translation overlays."""

    # Define default values here consistent with OverlayManager
    # Import defaults from the manager to ensure consistency
    try:
        # Try importing defaults - handle potential circularity if manager imports this tab
        from ui.overlay_manager import OverlayManager
        DEFAULT_CONFIG = OverlayManager.DEFAULT_OVERLAY_CONFIG
    except ImportError:
        # Fallback defaults if import fails
        print("Warning: Could not import OverlayManager defaults. Using fallback in OverlayTab.")
        DEFAULT_CONFIG = {
            "enabled": True, "font_family": "Segoe UI", "font_size": 14,
            "font_color": "white", "bg_color": "#222222", "alpha": 0.85,
            "position": "bottom_roi", "wraplength": 450, "justify": "left"
        }


    POSITION_OPTIONS = [
        "bottom_roi", "top_roi", "center_roi",
        "bottom_game", "top_game", "center_game"
        # Add more if needed, e.g., fixed coordinates, corners
    ]

    JUSTIFY_OPTIONS = ["left", "center", "right"]

    def setup_ui(self):
        # --- Main Frame ---
        main_frame = ttk.Frame(self.frame, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Global Enable ---
        global_frame = ttk.Frame(main_frame)
        global_frame.pack(fill=tk.X, pady=(0, 10))

        # Check if overlay_manager exists before accessing its state
        initial_global_state = True # Default if manager not ready
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

        self.roi_names = [roi.name for roi in self.app.rois] # Get initial list
        self.selected_roi_var = tk.StringVar()
        self.roi_combo = ttk.Combobox(roi_select_frame, textvariable=self.selected_roi_var,
                                      values=self.roi_names, state="readonly", width=25) # Wider
        if self.roi_names:
            self.roi_combo.current(0)
        self.roi_combo.pack(side=tk.LEFT, fill=tk.X, expand=True) # Expand combobox
        self.roi_combo.bind("<<ComboboxSelected>>", self.load_roi_config)

        # --- Configuration Area (populated based on selection) ---
        self.config_frame = ttk.LabelFrame(main_frame, text="Overlay Settings", padding=10)
        self.config_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Create the widgets holder
        self.widgets = {}
        # Build the widgets initially (they will be empty/disabled until ROI selected)
        self.build_config_widgets()

        # Load initial config for the first ROI (if any) after UI is fully built
        self.app.master.after_idle(self.load_initial_config)


    def build_config_widgets(self):
        """Creates the widgets for overlay configuration within self.config_frame."""
        frame = self.config_frame
        # Clear previous widgets if any (important if rebuilding)
        for widget in frame.winfo_children():
            widget.destroy()

        # --- Widgets Dictionary ---
        self.widgets = {} # Reset dictionary

        # Grid configuration
        frame.columnconfigure(1, weight=1) # Allow entry/combo fields to expand

        # Row counter
        row_num = 0

        # Enabled Checkbox
        self.widgets['enabled_var'] = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Enabled for this ROI", variable=self.widgets['enabled_var']).grid(row=row_num, column=0, columnspan=3, sticky=tk.W, pady=5)
        row_num += 1

        # Font Family
        ttk.Label(frame, text="Font Family:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        # List available fonts (can be slow, consider limiting or using entry with validation)
        try:
            # Filter out fonts starting with '@' (often vertical variants not useful here)
            available_fonts = sorted([f for f in tkFont.families() if not f.startswith('@')])
        except Exception as e:
            print(f"Error getting system fonts: {e}. Using fallback list.")
            available_fonts = ["Arial", "Segoe UI", "Times New Roman", "Courier New", "Verdana", "Tahoma", "MS Gothic"] # Common fonts
        self.widgets['font_family_var'] = tk.StringVar()
        # Use Combobox but allow typing for unlisted fonts
        self.widgets['font_family_combo'] = ttk.Combobox(frame, textvariable=self.widgets['font_family_var'], values=available_fonts, width=25)
        self.widgets['font_family_combo'].grid(row=row_num, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=2)
        row_num += 1

        # Font Size
        ttk.Label(frame, text="Font Size:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        self.widgets['font_size_var'] = tk.IntVar(value=self.DEFAULT_CONFIG['font_size'])
        # Use Spinbox for easy increment/decrement
        ttk.Spinbox(frame, from_=8, to=72, increment=1, width=5, textvariable=self.widgets['font_size_var']).grid(row=row_num, column=1, sticky=tk.W, padx=5, pady=2)
        row_num += 1

        # Font Color
        ttk.Label(frame, text="Font Color:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        self.widgets['font_color_var'] = tk.StringVar(value=self.DEFAULT_CONFIG['font_color'])
        # Entry field for hex color
        font_color_entry = ttk.Entry(frame, textvariable=self.widgets['font_color_var'], width=10)
        font_color_entry.grid(row=row_num, column=1, sticky=tk.W, padx=5, pady=2)
        font_color_entry.bind("<FocusOut>", lambda e, key='font_color': self.update_color_preview(key))
        font_color_entry.bind("<Return>", lambda e, key='font_color': self.update_color_preview(key))
        # Color picker button
        self.widgets['font_color_btn'] = ttk.Button(frame, text="🎨", width=3,
                                                    command=lambda: self.choose_color('font_color', 'Font Color'))
        self.widgets['font_color_btn'].grid(row=row_num, column=2, sticky=tk.W, padx=(0, 5), pady=2)
        # Color preview label
        self.widgets['font_color_preview'] = tk.Label(frame, text="   ", relief=tk.SUNKEN, width=3, borderwidth=1)
        self.widgets['font_color_preview'].grid(row=row_num, column=3, sticky=tk.W, padx=2)
        self.update_color_preview('font_color') # Set initial preview
        row_num += 1

        # Background Color
        ttk.Label(frame, text="Background Color:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        self.widgets['bg_color_var'] = tk.StringVar(value=self.DEFAULT_CONFIG['bg_color'])
        # Entry field
        bg_color_entry = ttk.Entry(frame, textvariable=self.widgets['bg_color_var'], width=10)
        bg_color_entry.grid(row=row_num, column=1, sticky=tk.W, padx=5, pady=2)
        bg_color_entry.bind("<FocusOut>", lambda e, key='bg_color': self.update_color_preview(key))
        bg_color_entry.bind("<Return>", lambda e, key='bg_color': self.update_color_preview(key))
        # Color picker button
        self.widgets['bg_color_btn'] = ttk.Button(frame, text="🎨", width=3,
                                                  command=lambda: self.choose_color('bg_color', 'Background Color'))
        self.widgets['bg_color_btn'].grid(row=row_num, column=2, sticky=tk.W, padx=(0, 5), pady=2)
        # Color preview label
        self.widgets['bg_color_preview'] = tk.Label(frame, text="   ", relief=tk.SUNKEN, width=3, borderwidth=1)
        self.widgets['bg_color_preview'].grid(row=row_num, column=3, sticky=tk.W, padx=2)
        self.update_color_preview('bg_color') # Set initial preview
        row_num += 1

        # Position
        ttk.Label(frame, text="Position:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        self.widgets['position_var'] = tk.StringVar()
        self.widgets['position_combo'] = ttk.Combobox(frame, textvariable=self.widgets['position_var'], values=self.POSITION_OPTIONS, state="readonly", width=25)
        self.widgets['position_combo'].grid(row=row_num, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=2)
        row_num += 1

        # Justify
        ttk.Label(frame, text="Alignment:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        self.widgets['justify_var'] = tk.StringVar()
        self.widgets['justify_combo'] = ttk.Combobox(frame, textvariable=self.widgets['justify_var'], values=self.JUSTIFY_OPTIONS, state="readonly", width=10)
        self.widgets['justify_combo'].grid(row=row_num, column=1, sticky=tk.W, padx=5, pady=2)
        row_num += 1


        # Wraplength
        ttk.Label(frame, text="Wrap Width (px):").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        self.widgets['wraplength_var'] = tk.IntVar(value=self.DEFAULT_CONFIG['wraplength'])
        ttk.Spinbox(frame, from_=100, to=2000, increment=25, width=7, textvariable=self.widgets['wraplength_var']).grid(row=row_num, column=1, sticky=tk.W, padx=5, pady=2)
        row_num += 1


        # --- Save Button ---
        # Place save button outside the grid loop
        save_button = ttk.Button(frame, text="Apply and Save Settings for this ROI", command=self.save_roi_config)
        save_button.grid(row=row_num, column=0, columnspan=4, pady=15) # Span all columns


    def update_color_preview(self, config_key):
        """Updates the color preview label based on the entry/variable."""
        var = self.widgets.get(f"{config_key}_var")
        preview = self.widgets.get(f"{config_key}_preview")
        if var and preview:
            color = var.get()
            try:
                # Check if color is a valid Tk color string
                preview.winfo_rgb(color) # This will raise TclError if invalid
                preview.config(background=color)
            except tk.TclError:
                # If invalid, revert preview to default color
                preview.config(background=self.DEFAULT_CONFIG.get(config_key, 'SystemButtonFace')) # Fallback color

    def choose_color(self, config_key, title):
        """Opens a color chooser dialog and updates the variable and preview."""
        var = self.widgets.get(f"{config_key}_var")
        preview = self.widgets.get(f"{config_key}_preview")
        if not var or not preview: return

        # Askcolor returns tuple ((r,g,b), hex) or (None, None)
        # Use the current color in the variable as the initial color
        initial_color = var.get()
        try:
            # Ensure initial color is valid before passing
            preview.winfo_rgb(initial_color) # Test color validity
            color_code = colorchooser.askcolor(title=title, initialcolor=initial_color, parent=self.frame)
        except tk.TclError: # Handle invalid initial color potentially
            print(f"Invalid initial color '{initial_color}' for {config_key}, using default picker.")
            color_code = colorchooser.askcolor(title=title, parent=self.frame)


        if color_code and color_code[1]: # Check if a color was selected (hex part)
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
            self.config_frame.config(text="Overlay Settings (No ROI Selected)")
            return

        # Ensure overlay manager exists
        if not hasattr(self.app, 'overlay_manager'):
            print("Error: Overlay Manager not initialized yet.")
            self.set_widgets_state(tk.DISABLED)
            return

        # Get the merged config (defaults + specific) for this ROI
        config = self.app.overlay_manager._get_roi_config(roi_name)
        self.config_frame.config(text=f"Overlay Settings for [{roi_name}]")

        # Update UI widgets, using defaults from DEFAULT_CONFIG as fallback
        self.widgets['enabled_var'].set(config.get('enabled', self.DEFAULT_CONFIG['enabled']))
        self.widgets['font_family_var'].set(config.get('font_family', self.DEFAULT_CONFIG['font_family']))
        self.widgets['font_size_var'].set(config.get('font_size', self.DEFAULT_CONFIG['font_size']))
        self.widgets['font_color_var'].set(config.get('font_color', self.DEFAULT_CONFIG['font_color']))
        self.widgets['bg_color_var'].set(config.get('bg_color', self.DEFAULT_CONFIG['bg_color']))
        self.widgets['position_var'].set(config.get('position', self.DEFAULT_CONFIG['position']))
        self.widgets['justify_var'].set(config.get('justify', self.DEFAULT_CONFIG['justify']))
        self.widgets['wraplength_var'].set(config.get('wraplength', self.DEFAULT_CONFIG['wraplength']))

        # Update color previews
        self.update_color_preview('font_color')
        self.update_color_preview('bg_color')

        # Enable widgets only if global overlays are enabled
        global_state = self.global_enable_var.get()
        self.set_widgets_state(tk.NORMAL if global_state else tk.DISABLED)


    def save_roi_config(self):
        """Saves the current UI configuration for the selected ROI."""
        roi_name = self.selected_roi_var.get()
        if not roi_name:
            messagebox.showwarning("Warning", "No ROI selected to save configuration for.", parent=self.app.master)
            return

        # Read values from widgets
        new_config = {}
        try:
            new_config = {
                'enabled': self.widgets['enabled_var'].get(),
                'font_family': self.widgets['font_family_var'].get(),
                'font_size': self.widgets['font_size_var'].get(),
                'font_color': self.widgets['font_color_var'].get(),
                'bg_color': self.widgets['bg_color_var'].get(),
                'position': self.widgets['position_var'].get(),
                'justify': self.widgets['justify_var'].get(),
                'wraplength': self.widgets['wraplength_var'].get(),
                # Add alpha later if needed
            }
        except tk.TclError as e:
            messagebox.showerror("Error Reading Value", f"Could not read setting value: {e}", parent=self.app.master)
            return
        except Exception as e:
            messagebox.showerror("Error Reading Value", f"Unexpected error reading settings: {e}", parent=self.app.master)
            return


        # Validate values
        if not 8 <= new_config['font_size'] <= 72:
            messagebox.showerror("Error", "Font size must be between 8 and 72.", parent=self.app.master)
            return
        if not 100 <= new_config['wraplength'] <= 5000:
            messagebox.showerror("Error", "Wrap width must be between 100 and 5000.", parent=self.app.master)
            return
        # Validate colors (basic hex check or try using winfo_rgb)
        color_pattern = r'^#(?:[0-9a-fA-F]{3}){1,2}$'
        try:
            self.frame.winfo_rgb(new_config['font_color']) # Test font color
        except tk.TclError:
            messagebox.showerror("Error", f"Invalid Font Color format: '{new_config['font_color']}'. Use a valid Tk color name or hex code (e.g., #RRGGBB).", parent=self.app.master)
            return
        try:
            self.frame.winfo_rgb(new_config['bg_color']) # Test background color
        except tk.TclError:
            messagebox.showerror("Error", f"Invalid Background Color format: '{new_config['bg_color']}'. Use a valid Tk color name or hex code (e.g., #RRGGBB).", parent=self.app.master)
            return


        # Update via OverlayManager (which handles saving to settings and applying live)
        if hasattr(self.app, 'overlay_manager'):
            self.app.overlay_manager.update_overlay_config(roi_name, new_config)
            self.app.update_status(f"Overlay settings saved for {roi_name}.")
            # Update ROI list display indicator in roi_tab
            if hasattr(self.app, 'roi_tab'):
                self.app.roi_tab.update_roi_list()
        else:
            messagebox.showerror("Error", "Overlay Manager not available. Cannot save settings.", parent=self.app.master)


    def toggle_global_overlays(self):
        """Callback for the global enable checkbox."""
        enabled = self.global_enable_var.get()
        if hasattr(self.app, 'overlay_manager'):
            self.app.overlay_manager.set_global_overlays_enabled(enabled)
            # Status update handled by manager
            # Enable/disable the ROI specific config area based on this
            self.set_widgets_state(tk.NORMAL if enabled else tk.DISABLED)
            if enabled and self.selected_roi_var.get():
                # If re-enabling, ensure the specific ROI config is loaded correctly
                self.load_roi_config()
        else:
            print("Error: Overlay Manager not available.")
            # Revert checkbox state if manager doesn't exist to apply the change
            self.global_enable_var.set(not enabled)


    def update_roi_list(self):
        """Called by the main app (e.g., from roi_tab) when the ROI list changes."""
        self.roi_names = [roi.name for roi in self.app.rois]
        current_selection = self.selected_roi_var.get()

        self.roi_combo['values'] = self.roi_names

        if current_selection in self.roi_names:
            # Keep current selection if still valid
            self.roi_combo.set(current_selection)
            # No need to reload config here, it's only called when list changes,
            # selection event handles loading. Unless list order matters for index?
            # self.load_roi_config() # Re-load config to be safe
        elif self.roi_names:
            # Select first ROI if previous selection gone or no previous selection
            self.roi_combo.current(0)
            self.load_roi_config() # Load config for the new first item
        else:
            # No ROIs left
            self.roi_combo.set("")
            self.selected_roi_var.set("")
            self.set_widgets_state(tk.DISABLED) # Disable config if no ROIs
            self.config_frame.config(text="Overlay Settings (No ROIs Defined)")


    def load_initial_config(self):
        """Load config for the initially selected ROI after UI is built."""
        # Make sure ROI list is up-to-date first
        self.update_roi_list()
        # Now load config based on the (potentially updated) selection
        if self.selected_roi_var.get():
            self.load_roi_config()
        else:
            self.set_widgets_state(tk.DISABLED)
            self.config_frame.config(text="Overlay Settings (No ROIs Defined)")

    def set_widgets_state(self, state):
        """Enable or disable all configuration widgets in the config_frame."""
        # Check if config_frame exists and has children
        if not hasattr(self, 'config_frame') or not self.config_frame.winfo_exists():
            return

        # Define valid states for standard Tk/TTK widgets
        valid_tk_states = (tk.NORMAL, tk.DISABLED, tk.ACTIVE)
        # State for Combobox is different ('readonly' or 'disabled')
        combobox_state = 'readonly' if state == tk.NORMAL else tk.DISABLED # Correctly use string 'readonly'

        actual_state = state if state in valid_tk_states else tk.DISABLED

        for widget in self.config_frame.winfo_children():
            # Check widget type and apply state appropriately
            widget_class = widget.winfo_class()
            try:
                if widget_class in ('TButton', 'TSpinbox', 'TCheckbutton', 'TEntry', 'Text'):
                    widget.configure(state=actual_state)
                elif widget_class == 'TCombobox':
                    # Combobox uses 'readonly' or 'disabled'
                    widget.configure(state=combobox_state) # Use the derived combobox state
                # Labels generally don't have a state property that affects appearance directly
                # elif widget_class == 'TLabel' or widget_class == 'Label':
                #      # Optional: Change foreground color to indicate disabled state
                #      fg_color = 'black' if actual_state == tk.NORMAL else 'gray50'
                #      widget.configure(foreground=fg_color)
            except tk.TclError as e:
                # Ignore errors for widgets that might not support the state option
                # print(f"Ignoring TclError setting state for {widget_class}: {e}")
                pass
            except Exception as e:
                print(f"Unexpected error setting state for {widget_class}: {e}")