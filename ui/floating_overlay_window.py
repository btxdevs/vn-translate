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
        self.config = initial_config # Received from manager (merged defaults + saved)
        self.master = master # Keep ref to main app root if needed

        # --- Window Configuration ---
        self.overrideredirect(True)  # No window decorations
        self.wm_attributes("-topmost", True) # Keep on top
        self.configure(background=self.config.get('bg_color', '#222222')) # Use bg_color for window

        # --- Dragging Variables ---
        self._offset_x = 0
        self._offset_y = 0
        self._dragging = False

        # --- Resizing Variables ---
        self._resizing = False
        self._resize_start_x = 0
        self._resize_start_y = 0
        self._resize_start_width = 0
        self._resize_start_height = 0

        # --- Content Label ---
        self.label_var = tk.StringVar()
        self.label = tk.Label(
            self,
            textvariable=self.label_var,
            padx=5, pady=2 # Padding inside the label
        )
        # Apply initial config to label
        self._update_label_config()
        # Pack label to fill the window
        self.label.pack(fill=tk.BOTH, expand=True)

        # --- Resize Grip ---
        self.grip_size = 10
        self.grip = tk.Frame(self, width=self.grip_size, height=self.grip_size, bg='grey50', cursor="bottom_right_corner")
        self.grip.place(relx=1.0, rely=1.0, anchor='se') # Place in bottom-right corner

        # --- Bindings ---
        # Dragging (bind to label and window background)
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.label.bind("<ButtonPress-1>", self.on_press)
        self.label.bind("<B1-Motion>", self.on_drag)
        self.label.bind("<ButtonRelease-1>", self.on_release)
        # Resizing (bind to grip)
        self.grip.bind("<ButtonPress-1>", self.on_resize_press)
        self.grip.bind("<B1-Motion>", self.on_resize_drag)
        self.grip.bind("<ButtonRelease-1>", self.on_resize_release)

        # --- Initial Geometry ---
        self._load_geometry()

        # Start hidden, shown by manager based on text/enabled status
        self.withdraw()

    def _load_geometry(self):
        """Loads and applies the saved geometry (WxH+X+Y) or sets a default."""
        saved_geometry = self.config.get('geometry') # Geometry is part of the config dict

        if saved_geometry and isinstance(saved_geometry, str) and 'x' in saved_geometry and '+' in saved_geometry:
            try:
                # Basic validation
                parts = saved_geometry.split('+')
                size_part = parts[0]
                pos_part = parts[1:]
                if len(pos_part) == 2 and 'x' in size_part:
                    w_str, h_str = size_part.split('x')
                    w, h = int(w_str), int(h_str)
                    x, y = int(pos_part[0]), int(pos_part[1])

                    # Ensure minimum size
                    w = max(self.MIN_WIDTH, w)
                    h = max(self.MIN_HEIGHT, h)

                    # Basic screen bounds check (optional, user might place partially off-screen)
                    # screen_width = self.winfo_screenwidth()
                    # screen_height = self.winfo_screenheight()
                    # x = max(0, min(x, screen_width - w))
                    # y = max(0, min(y, screen_height - h))

                    self.geometry(f"{w}x{h}+{x}+{y}")
                    print(f"Overlay '{self.roi_name}': Loaded geometry {w}x{h}+{x}+{y}")
                    return # Success
                else:
                    print(f"Overlay '{self.roi_name}': Invalid geometry format '{saved_geometry}'. Using default.")
            except Exception as e:
                print(f"Overlay '{self.roi_name}': Error parsing geometry '{saved_geometry}': {e}. Using default.")
        else:
            print(f"Overlay '{self.roi_name}': No valid geometry saved. Using default.")


        # Default position/size if load failed or no geometry saved
        self.center_and_default_size()

    def _save_geometry(self):
        """Saves the current window geometry (WxH+X+Y) to settings."""
        try:
            # Ensure window exists before getting geometry
            if not self.winfo_exists():
                return

            # Get WxH+X+Y string
            current_geometry = self.geometry()
            # Optional: Validate format before saving? `winfo_geometry()` is usually reliable.
            if 'x' in current_geometry and '+' in current_geometry:
                # Update the config dict in memory
                self.config['geometry'] = current_geometry
                # Use the settings utility function to save just this part for this ROI
                if save_overlay_config_for_roi(self.roi_name, {'geometry': current_geometry}):
                    print(f"Overlay '{self.roi_name}': Saved geometry {current_geometry}")
                else:
                    print(f"Overlay '{self.roi_name}': Failed to save geometry.")
            else:
                print(f"Overlay '{self.roi_name}': Invalid geometry to save: {current_geometry}")

        except tk.TclError as e:
            print(f"Overlay '{self.roi_name}': Error getting geometry (window closed?): {e}")
        except Exception as e:
            print(f"Overlay '{self.roi_name}': Unexpected error saving geometry: {e}")


    def center_and_default_size(self):
        """Sets a default size and centers the window on the screen."""
        try:
            self.update_idletasks() # Ensure calculations are based on current state
            default_width = max(self.MIN_WIDTH, self.config.get('wraplength', 450) + 20) # Estimate width
            # Estimate height based on a line or two of text? Hard to do accurately.
            default_height = max(self.MIN_HEIGHT, 50)

            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            x = (screen_width // 2) - (default_width // 2)
            y = (screen_height // 3) - (default_height // 2) # Place towards top-center third

            # Clamp initial position if needed
            x = max(0, min(x, screen_width - default_width))
            y = max(0, min(y, screen_height - default_height))

            self.geometry(f"{default_width}x{default_height}+{x}+{y}")
            print(f"Overlay '{self.roi_name}': Set default geometry {default_width}x{default_height}+{x}+{y}")
        except Exception as e:
            print(f"Overlay '{self.roi_name}': Error setting default geometry: {e}")


    def _update_label_config(self):
        """Applies current self.config appearance settings to the label widget."""
        font_family = self.config.get('font_family', 'Segoe UI')
        font_size = self.config.get('font_size', 14)
        font_color = self.config.get('font_color', 'white')
        bg_color = self.config.get('bg_color', '#222222')
        wraplength = self.config.get('wraplength', 450)
        justify_map = {'left': tk.LEFT, 'center': tk.CENTER, 'right': tk.RIGHT}
        justify_align = justify_map.get(self.config.get('justify', 'left'), tk.LEFT)

        try:
            label_font = tkFont.Font(family=font_family, size=font_size)
        except tk.TclError:
            print(f"Warning: Font '{font_family}' not found for overlay '{self.roi_name}'. Using default.")
            label_font = tkFont.Font(size=font_size)

        self.label.config(
            font=label_font,
            fg=font_color,
            bg=bg_color, # Label background matches window
            wraplength=wraplength,
            justify=justify_align
        )
        # Update window background as well
        self.configure(background=bg_color)


    def update_text(self, text):
        """Update the text displayed and visibility."""
        if not isinstance(text, str):
            text = str(text)

        current_text = self.label_var.get()
        if text != current_text:
            self.label_var.set(text)

        # Update visibility based on text and enabled status in config
        should_be_visible = bool(text) and self.config.get('enabled', True)
        is_visible = self.state() == 'normal'

        if should_be_visible and not is_visible:
            self.deiconify() # Show window if hidden
            self.lift()      # Ensure it's on top
        elif not should_be_visible and is_visible:
            self.withdraw()  # Hide if no text or disabled

    def update_config(self, new_config):
        """Update the appearance and visibility based on new configuration."""
        # Check if geometry changed externally (e.g., reset button)
        # Geometry is usually updated only by user interaction (drag/resize) or loading.
        # But if a "reset" function clears it in settings, we might need to react.
        needs_geom_reload = False
        if 'geometry' in new_config and new_config['geometry'] != self.config.get('geometry'):
            if new_config['geometry'] is None: # Indication to reset position?
                needs_geom_reload = True

        # Update internal config
        self.config = new_config
        self._update_label_config() # Apply appearance changes

        if needs_geom_reload:
            self._load_geometry() # Apply default geometry if None was passed

        # Re-evaluate visibility based on the new 'enabled' status and current text
        is_enabled = self.config.get('enabled', True)
        has_text = bool(self.label_var.get())
        should_be_visible = is_enabled and has_text
        is_visible = self.state() == 'normal'

        if should_be_visible and not is_visible:
            self.deiconify()
            self.lift()
        elif not should_be_visible and is_visible:
            self.withdraw()


    # --- Dragging Methods ---
    def on_press(self, event):
        """Start dragging."""
        # Ensure click is not on the resize grip
        if event.widget == self.grip:
            return # Let resize handle this

        self._offset_x = event.x
        self._offset_y = event.y
        self._dragging = True
        # print(f"Drag start: {self.roi_name}")

    def on_drag(self, event):
        """Move window during drag."""
        if not self._dragging:
            return

        new_x = self.winfo_x() + event.x - self._offset_x
        new_y = self.winfo_y() + event.y - self._offset_y
        self.geometry(f"+{new_x}+{new_y}")

    def on_release(self, event):
        """Save the window position when dragging stops."""
        if not self._dragging:
            return

        self._dragging = False
        self._save_geometry() # Save includes position WxH+X+Y
        # print(f"Drag end: {self.roi_name}")


    # --- Resizing Methods ---
    def on_resize_press(self, event):
        """Start resizing."""
        self._resizing = True
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._resize_start_width = self.winfo_width()
        self._resize_start_height = self.winfo_height()
        # print(f"Resize start: {self.roi_name}")

    def on_resize_drag(self, event):
        """Resize window during drag."""
        if not self._resizing:
            return

        delta_x = event.x_root - self._resize_start_x
        delta_y = event.y_root - self._resize_start_y

        new_width = self._resize_start_width + delta_x
        new_height = self._resize_start_height + delta_y

        # Enforce minimum size
        new_width = max(self.MIN_WIDTH, new_width)
        new_height = max(self.MIN_HEIGHT, new_height)

        # Update geometry (keeping current position)
        current_x = self.winfo_x()
        current_y = self.winfo_y()
        self.geometry(f"{new_width}x{new_height}+{current_x}+{current_y}")

    def on_resize_release(self, event):
        """Save the window size and position when resizing stops."""
        if not self._resizing:
            return

        self._resizing = False
        # Width/Height might have changed label's requested wraplength needed?
        # Maybe update wraplength automatically or provide a way? For now, just save.
        self._save_geometry() # Save includes size WxH+X+Y
        # print(f"Resize end: {self.roi_name}")


    def destroy_window(self):
        """Safely destroy the overlay window."""
        try:
            # print(f"Destroying overlay window for {self.roi_name}")
            self.destroy()
        except tk.TclError as e:
            # print(f"Error destroying overlay {self.roi_name} (already destroyed?): {e}")
            pass # Ignore if already gone
        except Exception as e:
            print(f"Unexpected error destroying overlay {self.roi_name}: {e}")

# --- END OF FILE ui/floating_overlay_window.py ---