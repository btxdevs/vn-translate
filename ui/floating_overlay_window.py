# --- START OF FILE ui/floating_overlay_window.py ---

import tkinter as tk
from tkinter import font as tkFont
from utils.settings import get_overlay_config_for_roi, save_overlay_config_for_roi

class FloatingOverlayWindow(tk.Toplevel):
    """
    A floating, draggable, resizable window to display translated text for an ROI.
    """
    MIN_WIDTH = 50
    MIN_HEIGHT = 30

    def __init__(self, master, roi_name, initial_config):
        super().__init__(master)
        self.roi_name = roi_name
        self.config = initial_config
        self.master = master

        # --- Window Configuration ---
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        self.configure(background=self.config.get('bg_color', '#222222'))

        # --- Apply Alpha Transparency ---
        self._apply_alpha() # Apply initial alpha

        # Dragging Variables
        self._offset_x = 0
        self._offset_y = 0
        self._dragging = False

        # Resizing Variables
        self._resizing = False
        self._resize_start_x = 0
        self._resize_start_y = 0
        self._resize_start_width = 0
        self._resize_start_height = 0

        # Content Label
        self.label_var = tk.StringVar()
        self.label = tk.Label(
            self,
            textvariable=self.label_var,
            padx=5, pady=2
        )
        self._update_label_config() # Includes setting label bg/fg etc
        self.label.pack(fill=tk.BOTH, expand=True)

        # Resize Grip
        self.grip_size = 10
        self.grip = tk.Frame(self, width=self.grip_size, height=self.grip_size, bg='grey50', cursor="bottom_right_corner")
        self.grip.place(relx=1.0, rely=1.0, anchor='se')

        # Bindings
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.label.bind("<ButtonPress-1>", self.on_press)
        self.label.bind("<B1-Motion>", self.on_drag)
        self.label.bind("<ButtonRelease-1>", self.on_release)
        self.grip.bind("<ButtonPress-1>", self.on_resize_press)
        self.grip.bind("<B1-Motion>", self.on_resize_drag)
        self.grip.bind("<ButtonRelease-1>", self.on_resize_release)

        # Initial Geometry
        self._load_geometry()

        self.withdraw() # Start hidden

    def _apply_alpha(self):
        """Applies the alpha value from config to the window."""
        try:
            alpha_value = float(self.config.get('alpha', 1.0))
            # Clamp value between 0.0 and 1.0
            alpha_value = max(0.0, min(1.0, alpha_value))
            self.wm_attributes("-alpha", alpha_value)
        except (ValueError, TypeError, tk.TclError) as e:
            print(f"Overlay '{self.roi_name}': Error applying alpha ({self.config.get('alpha')}): {e}")
            self.wm_attributes("-alpha", 1.0) # Fallback to opaque

    def _load_geometry(self):
        saved_geometry = self.config.get('geometry')
        if saved_geometry and isinstance(saved_geometry, str) and 'x' in saved_geometry and '+' in saved_geometry:
            try:
                parts = saved_geometry.split('+')
                size_part, pos_parts = parts[0], parts[1:]
                if len(pos_parts) == 2 and 'x' in size_part:
                    w_str, h_str = size_part.split('x')
                    w, h = max(self.MIN_WIDTH, int(w_str)), max(self.MIN_HEIGHT, int(h_str))
                    x, y = int(pos_parts[0]), int(pos_parts[1])
                    self.geometry(f"{w}x{h}+{x}+{y}")
                    # print(f"Overlay '{self.roi_name}': Loaded geometry {w}x{h}+{x}+{y}") # Less verbose
                    return
                else: print(f"Overlay '{self.roi_name}': Invalid geometry format '{saved_geometry}'.")
            except Exception as e: print(f"Overlay '{self.roi_name}': Error parsing geometry '{saved_geometry}': {e}.")
        # print(f"Overlay '{self.roi_name}': No valid geometry saved. Using default.") # Less verbose
        self.center_and_default_size()


    def _save_geometry(self):
        try:
            if not self.winfo_exists(): return
            current_geometry = self.geometry()
            if 'x' in current_geometry and '+' in current_geometry:
                self.config['geometry'] = current_geometry
                if save_overlay_config_for_roi(self.roi_name, {'geometry': current_geometry}):
                    pass # print(f"Overlay '{self.roi_name}': Saved geometry {current_geometry}") # Less verbose
                else: print(f"Overlay '{self.roi_name}': Failed to save geometry.")
            else: print(f"Overlay '{self.roi_name}': Invalid geometry to save: {current_geometry}")
        except tk.TclError as e: print(f"Overlay '{self.roi_name}': Error getting geometry: {e}")
        except Exception as e: print(f"Overlay '{self.roi_name}': Error saving geometry: {e}")


    def center_and_default_size(self):
        try:
            self.update_idletasks()
            default_width = max(self.MIN_WIDTH, self.config.get('wraplength', 450) + 20)
            default_height = max(self.MIN_HEIGHT, 50)
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            x = max(0, (screen_width // 2) - (default_width // 2))
            y = max(0, (screen_height // 3) - (default_height // 2))
            self.geometry(f"{default_width}x{default_height}+{x}+{y}")
            # print(f"Overlay '{self.roi_name}': Set default geometry {default_width}x{default_height}+{x}+{y}") # Less verbose
        except Exception as e: print(f"Overlay '{self.roi_name}': Error setting default geometry: {e}")


    def _update_label_config(self):
        font_family = self.config.get('font_family', 'Segoe UI')
        font_size = self.config.get('font_size', 14)
        font_color = self.config.get('font_color', 'white')
        bg_color = self.config.get('bg_color', '#222222')
        wraplength = self.config.get('wraplength', 450)
        justify_map = {'left': tk.LEFT, 'center': tk.CENTER, 'right': tk.RIGHT}
        justify_align = justify_map.get(self.config.get('justify', 'left'), tk.LEFT)
        try: label_font = tkFont.Font(family=font_family, size=font_size)
        except tk.TclError: label_font = tkFont.Font(size=font_size); print(f"Warn: Font '{font_family}' not found for '{self.roi_name}'.")

        self.label.config(font=label_font, fg=font_color, bg=bg_color, wraplength=wraplength, justify=justify_align)
        self.configure(background=bg_color)


    def update_text(self, text):
        if not isinstance(text, str): text = str(text)
        current_text = self.label_var.get()
        if text != current_text: self.label_var.set(text)

        should_be_visible = bool(text) and self.config.get('enabled', True)
        is_visible = self.state() == 'normal'

        # Check if window exists before modifying state
        if not self.winfo_exists(): return

        if should_be_visible and not is_visible: self.deiconify(); self.lift()
        elif not should_be_visible and is_visible: self.withdraw()

    def update_config(self, new_config):
        needs_geom_reload = False
        if 'geometry' in new_config and new_config['geometry'] != self.config.get('geometry'):
            if new_config['geometry'] is None: needs_geom_reload = True

        self.config = new_config
        self._update_label_config()
        self._apply_alpha() # Re-apply alpha in case it changed

        if needs_geom_reload: self._load_geometry()

        # Re-evaluate visibility
        is_enabled = self.config.get('enabled', True)
        has_text = bool(self.label_var.get())
        should_be_visible = is_enabled and has_text
        is_visible = self.state() == 'normal'

        if not self.winfo_exists(): return

        if should_be_visible and not is_visible: self.deiconify(); self.lift()
        elif not should_be_visible and is_visible: self.withdraw()


    # --- Dragging Methods ---
    def on_press(self, event):
        if event.widget == self.grip: return
        self._offset_x = event.x
        self._offset_y = event.y
        self._dragging = True

    def on_drag(self, event):
        if not self._dragging: return
        new_x = self.winfo_x() + event.x - self._offset_x
        new_y = self.winfo_y() + event.y - self._offset_y
        # Prevent updating geometry if window is closing
        if self.winfo_exists():
            self.geometry(f"+{new_x}+{new_y}")

    def on_release(self, event):
        if not self._dragging: return
        self._dragging = False
        self._save_geometry()


    # --- Resizing Methods ---
    def on_resize_press(self, event):
        self._resizing = True
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        # Check if window exists before getting width/height
        if not self.winfo_exists():
            self._resizing = False # Cannot resize non-existent window
            return
        self._resize_start_width = self.winfo_width()
        self._resize_start_height = self.winfo_height()

    def on_resize_drag(self, event):
        if not self._resizing: return
        delta_x = event.x_root - self._resize_start_x
        delta_y = event.y_root - self._resize_start_y
        new_width = max(self.MIN_WIDTH, self._resize_start_width + delta_x)
        new_height = max(self.MIN_HEIGHT, self._resize_start_height + delta_y)

        # Check if window exists before setting geometry
        if self.winfo_exists():
            current_x = self.winfo_x()
            current_y = self.winfo_y()
            self.geometry(f"{new_width}x{new_height}+{current_x}+{current_y}")

    def on_resize_release(self, event):
        if not self._resizing: return
        self._resizing = False
        self._save_geometry()


    def destroy_window(self):
        try:
            if self.winfo_exists(): self.destroy()
        except tk.TclError: pass # Ignore if already gone
        except Exception as e: print(f"Error destroying overlay {self.roi_name}: {e}")

# --- END OF FILE ui/floating_overlay_window.py ---