# --- START OF FILE ui/floating_overlay_window.py ---

import tkinter as tk
from tkinter import font as tkFont
from tkinter import ttk # Import ttk for styled button
from utils.settings import get_overlay_config_for_roi, save_overlay_config_for_roi

class FloatingOverlayWindow(tk.Toplevel):
    """
    A floating, draggable, resizable window to display translated text for an ROI.
    """
    MIN_WIDTH = 50
    MIN_HEIGHT = 30

    def __init__(self, master, roi_name, initial_config, manager_ref):
        super().__init__(master)
        self.roi_name = roi_name
        self.config = initial_config
        self.master = master
        self.manager = manager_ref # Reference to OverlayManager

        # --- Window Configuration ---
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        self.configure(background=self.config.get('bg_color', '#222222'))
        self._apply_alpha()

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

        # Content Frame (to hold label and potentially other widgets like close btn)
        self.content_frame = tk.Frame(self, bg=self.config.get('bg_color', '#222222'))
        self.content_frame.pack(fill=tk.BOTH, expand=True)

        # Content Label
        self.label_var = tk.StringVar()
        self.label = tk.Label(
            self.content_frame, # Place label in content_frame
            textvariable=self.label_var,
            padx=5, pady=2
        )
        self._update_label_config()
        # Use grid for label to potentially allow placing close button next to it
        self.label.grid(row=0, column=0, sticky="nsew")
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # Resize Grip
        self.grip_size = 10
        self.grip = tk.Frame(self, width=self.grip_size, height=self.grip_size, bg='grey50', cursor="bottom_right_corner")
        self.grip.place(relx=1.0, rely=1.0, anchor='se')

        # Bindings
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
        # Bind dragging to label and content_frame as well
        self.label.bind("<ButtonPress-1>", self.on_press)
        self.label.bind("<B1-Motion>", self.on_drag)
        self.label.bind("<ButtonRelease-1>", self.on_release)
        self.content_frame.bind("<ButtonPress-1>", self.on_press)
        self.content_frame.bind("<B1-Motion>", self.on_drag)
        self.content_frame.bind("<ButtonRelease-1>", self.on_release)

        self.grip.bind("<ButtonPress-1>", self.on_resize_press)
        self.grip.bind("<B1-Motion>", self.on_resize_drag)
        self.grip.bind("<ButtonRelease-1>", self.on_resize_release)

        self._load_geometry()
        self.withdraw()

    def _apply_alpha(self):
        """Applies the alpha value from config to the window."""
        try:
            alpha_value = float(self.config.get('alpha', 1.0))
            alpha_value = max(0.0, min(1.0, alpha_value))
            self.wm_attributes("-alpha", alpha_value)
        except (ValueError, TypeError, tk.TclError) as e:
            print(f"Overlay '{self.roi_name}': Error applying alpha ({self.config.get('alpha')}): {e}")
            self.wm_attributes("-alpha", 1.0)

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
                    return
                else: print(f"Overlay '{self.roi_name}': Invalid geometry format '{saved_geometry}'.")
            except Exception as e: print(f"Overlay '{self.roi_name}': Error parsing geometry '{saved_geometry}': {e}.")
        self.center_and_default_size()


    def _save_geometry(self):
        """Saves geometry unless it's a special window like _snip_translate."""
        if self.roi_name == "_snip_translate":
            # print("Skipping geometry save for temporary snip window.")
            return # Don't save geometry for the temporary snip window

        try:
            if not self.winfo_exists(): return
            current_geometry = self.geometry()
            if 'x' in current_geometry and '+' in current_geometry:
                # Only save if geometry actually changed compared to config
                if self.config.get('geometry') != current_geometry:
                    self.config['geometry'] = current_geometry # Update local config view
                    if save_overlay_config_for_roi(self.roi_name, {'geometry': current_geometry}):
                        pass # print(f"Overlay '{self.roi_name}': Geometry saved.")
                    else: print(f"Overlay '{self.roi_name}': Failed to save geometry.")
            else: print(f"Overlay '{self.roi_name}': Invalid geometry to save: {current_geometry}")
        except tk.TclError as e: print(f"Overlay '{self.roi_name}': Error getting geometry: {e}")
        except Exception as e: print(f"Overlay '{self.roi_name}': Error saving geometry: {e}")


    def center_and_default_size(self):
        try:
            self.update_idletasks()
            # Make default size slightly dependent on wrap length from config
            default_width = max(self.MIN_WIDTH, self.config.get('wraplength', 450) + 20) # Add padding
            default_height = max(self.MIN_HEIGHT, 50) # Fixed default height? Or estimate based on font?
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            x = max(0, (screen_width // 2) - (default_width // 2))
            y = max(0, (screen_height // 3) - (default_height // 2)) # Position in upper third
            self.geometry(f"{default_width}x{default_height}+{x}+{y}")
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

        # Update label, content frame, and main window background
        self.label.config(font=label_font, fg=font_color, bg=bg_color, wraplength=wraplength, justify=justify_align)
        self.content_frame.config(bg=bg_color)
        self.configure(background=bg_color)

    def update_text(self, text, global_overlays_enabled=True):
        if not isinstance(text, str): text = str(text)
        current_text = self.label_var.get()
        if text != current_text: self.label_var.set(text)

        # Check widget existence early
        try:
            if not self.winfo_exists(): return
        except tk.TclError:
            return # Exit if window is destroyed

        # Determine visibility based on GLOBAL state (if managed), text, and INDIVIDUAL config
        manager_global_state = global_overlays_enabled
        if self.manager: # If managed, use the manager's current global state
            manager_global_state = self.manager.global_overlays_enabled
        elif self.roi_name == "_snip_translate":
            manager_global_state = True # Snip window ignores global toggle

        # Visibility rule: Must be enabled globally AND individually
        # AND (for showing) must have text. Hiding only happens if disabled.
        is_individually_enabled = self.config.get('enabled', True)
        should_be_visible_if_enabled = manager_global_state and is_individually_enabled

        # Update tasks to get reliable state
        self.update_idletasks()
        try:
            is_visible = self.state() == 'normal'
        except tk.TclError:
            return # Exit if window is destroyed

        # Decide whether to show or hide
        if should_be_visible_if_enabled and bool(text) and not is_visible:
            # Show if: globally enabled, individually enabled, has text, and not currently visible
            try:
                self.deiconify()
                self.lift()
            except tk.TclError:
                pass # Ignore if destroyed during operation
        elif not should_be_visible_if_enabled and is_visible:
            # Hide ONLY if: globally disabled OR individually disabled, and currently visible
            # (Do NOT hide just because text is empty)
            try:
                self.withdraw()
            except tk.TclError:
                pass # Ignore if destroyed during operation

    def update_config(self, new_config):
        needs_geom_reload = False
        if 'geometry' in new_config and new_config['geometry'] != self.config.get('geometry'):
            if new_config['geometry'] is None: needs_geom_reload = True

        self.config = new_config
        self._update_label_config()
        self._apply_alpha()

        if needs_geom_reload: self._load_geometry()

        # Re-evaluate visibility using the current text and the NEW config
        manager_global_state = True # Default for unmanaged windows like snip
        if self.manager:
            manager_global_state = self.manager.global_overlays_enabled

        self.update_text(self.label_var.get(), global_overlays_enabled=manager_global_state)


    # --- Dragging Methods ---
    def on_press(self, event):
        # Check if the event originated from the grip or a potential close button
        widget = event.widget
        while widget is not None:
            if widget == self.grip or getattr(widget, '_is_close_button', False):
                return # Don't start drag if pressing grip or close button
            widget = widget.master
        self._offset_x = event.x
        self._offset_y = event.y
        self._dragging = True

    def on_drag(self, event):
        if not self._dragging: return
        new_x = self.winfo_x() + event.x - self._offset_x
        new_y = self.winfo_y() + event.y - self._offset_y
        if self.winfo_exists():
            try:
                self.geometry(f"+{new_x}+{new_y}")
            except tk.TclError:
                pass # Window might be destroyed during drag

    def on_release(self, event):
        if not self._dragging: return
        self._dragging = False
        self._save_geometry() # This will be skipped for snip window


    # --- Resizing Methods ---
    def on_resize_press(self, event):
        self._resizing = True
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        if not self.winfo_exists():
            self._resizing = False; return
        try:
            self._resize_start_width = self.winfo_width()
            self._resize_start_height = self.winfo_height()
        except tk.TclError:
            self._resizing = False; return

    def on_resize_drag(self, event):
        if not self._resizing: return
        delta_x = event.x_root - self._resize_start_x
        delta_y = event.y_root - self._resize_start_y
        new_width = max(self.MIN_WIDTH, self._resize_start_width + delta_x)
        new_height = max(self.MIN_HEIGHT, self._resize_start_height + delta_y)

        if self.winfo_exists():
            try:
                current_x = self.winfo_x()
                current_y = self.winfo_y()
                self.geometry(f"{new_width}x{new_height}+{current_x}+{current_y}")
            except tk.TclError:
                pass # Window might be destroyed during resize

    def on_resize_release(self, event):
        if not self._resizing: return
        self._resizing = False
        self._save_geometry() # Skipped for snip window


    def destroy_window(self):
        try:
            if self.winfo_exists(): self.destroy()
        except tk.TclError: pass
        except Exception as e: print(f"Error destroying overlay {self.roi_name}: {e}")


# --- ADDED: Closable version for Snip & Translate ---
class ClosableFloatingOverlayWindow(FloatingOverlayWindow):
    """A FloatingOverlayWindow with an added close button."""

    def __init__(self, master, roi_name, initial_config, manager_ref):
        super().__init__(master, roi_name, initial_config, manager_ref)

        # Add a close button
        # Use ttk.Button for better styling potential if needed
        # Style it to be small and subtle
        style = ttk.Style(self)
        style.configure("Close.TButton", padding=0, font=('Segoe UI', 7)) # Very small padding/font

        close_button = ttk.Button(
            self.content_frame, # Add to content_frame
            text="✕",
            command=self.destroy_window,
            width=2, # Small width
            style="Close.TButton"
        )
        # Mark this button so drag logic can ignore it
        close_button._is_close_button = True

        # Place it in the top-right corner using grid
        close_button.grid(row=0, column=1, sticky="ne", padx=(0,1), pady=(1,0)) # North-East corner
        self.content_frame.grid_columnconfigure(1, weight=0) # Don't expand close button column

    # Override _save_geometry to ensure it never saves for this type
    def _save_geometry(self):
        # print("ClosableFloatingOverlayWindow: Geometry save intentionally skipped.")
        pass

# --- END OF FILE ui/floating_overlay_window.py ---