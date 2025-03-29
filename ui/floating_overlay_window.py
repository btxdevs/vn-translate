# --- START OF FILE ui/floating_overlay_window.py ---

import tkinter as tk
from tkinter import font as tkFont
from tkinter import ttk
from utils.settings import save_overlay_config_for_roi

class FloatingOverlayWindow(tk.Toplevel):
    MIN_WIDTH = 50
    MIN_HEIGHT = 30

    def __init__(self, master, roi_name, initial_config, manager_ref):
        super().__init__(master)
        self.roi_name = roi_name
        self.config = initial_config
        self.master = master
        self.manager = manager_ref # Reference to OverlayManager or None

        # Window setup
        self.overrideredirect(True) # No standard window decorations
        self.wm_attributes("-topmost", True) # Keep on top
        self.configure(background=self.config.get('bg_color', '#222222')) # Set background
        self._apply_alpha() # Set transparency

        # Dragging/Resizing state
        self._offset_x = 0
        self._offset_y = 0
        self._dragging = False
        self._resizing = False
        self._resize_start_x = 0
        self._resize_start_y = 0
        self._resize_start_width = 0
        self._resize_start_height = 0

        # Content Frame (allows padding and easier layout)
        self.content_frame = tk.Frame(self, bg=self.config.get('bg_color', '#222222'))
        self.content_frame.pack(fill=tk.BOTH, expand=True)

        # Main Text Label
        self.label_var = tk.StringVar()
        self.label = tk.Label(
            self.content_frame,
            textvariable=self.label_var,
            padx=5, # Horizontal padding within the label
            pady=2  # Vertical padding within the label
        )
        self._update_label_config() # Apply font, color, wrap etc.
        self.label.grid(row=0, column=0, sticky="nsew") # Place label in grid

        # Configure grid weights for content frame (makes label expand)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # Resize Grip
        self.grip_size = 10
        self.grip = tk.Frame(
            self,
            width=self.grip_size,
            height=self.grip_size,
            bg='grey50', # Make grip visible
            cursor="bottom_right_corner"
        )
        # Place grip at bottom right corner
        self.grip.place(relx=1.0, rely=1.0, anchor='se')

        # --- Bind Events ---
        # Dragging (bind to window, content frame, and label)
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.label.bind("<ButtonPress-1>", self.on_press)
        self.label.bind("<B1-Motion>", self.on_drag)
        self.label.bind("<ButtonRelease-1>", self.on_release)
        self.content_frame.bind("<ButtonPress-1>", self.on_press)
        self.content_frame.bind("<B1-Motion>", self.on_drag)
        self.content_frame.bind("<ButtonRelease-1>", self.on_release)

        # Resizing (bind only to grip)
        self.grip.bind("<ButtonPress-1>", self.on_resize_press)
        self.grip.bind("<B1-Motion>", self.on_resize_drag)
        self.grip.bind("<ButtonRelease-1>", self.on_resize_release)

        # Load initial size/position and hide
        self._load_geometry()
        self.withdraw() # Start hidden

    def _apply_alpha(self):
        """Applies the alpha (transparency) setting from the config."""
        try:
            # Ensure alpha is float between 0.0 and 1.0
            alpha_value = float(self.config.get('alpha', 1.0))
            alpha_value = max(0.0, min(1.0, alpha_value))
            self.wm_attributes("-alpha", alpha_value)
        except (ValueError, TypeError, tk.TclError) as e:
            print(f"Warning: Could not apply alpha for {self.roi_name}: {e}. Using 1.0.")
            try:
                self.wm_attributes("-alpha", 1.0) # Fallback to opaque
            except tk.TclError: pass # Ignore if window doesn't exist

    def _load_geometry(self):
        """Loads window size and position from config, or sets defaults."""
        saved_geometry = self.config.get('geometry')
        # Check if geometry string looks valid (e.g., "WxH+X+Y")
        if saved_geometry and isinstance(saved_geometry, str) and 'x' in saved_geometry and '+' in saved_geometry:
            try:
                parts = saved_geometry.split('+')
                size_part, pos_parts = parts[0], parts[1:]
                if len(pos_parts) == 2 and 'x' in size_part:
                    w_str, h_str = size_part.split('x')
                    # Ensure minimum size constraints
                    w = max(self.MIN_WIDTH, int(w_str))
                    h = max(self.MIN_HEIGHT, int(h_str))
                    x, y = int(pos_parts[0]), int(pos_parts[1])
                    self.geometry(f"{w}x{h}+{x}+{y}")
                    # print(f"Loaded geometry for {self.roi_name}: {w}x{h}+{x}+{y}") # Debug
                    return # Success
            except Exception as e:
                print(f"Warning: Failed to parse saved geometry '{saved_geometry}' for {self.roi_name}: {e}")
        # Fallback if no valid geometry saved
        # print(f"No valid geometry found for {self.roi_name}, centering.") # Debug
        self.center_and_default_size()

    def _save_geometry(self):
        """Saves the current window size and position to the config."""
        # Do not save geometry for the temporary snip window
        if self.roi_name == "_snip_translate":
            return

        try:
            if not self.winfo_exists():
                return # Don't save if window is gone

            current_geometry = self.geometry()
            # Basic check if geometry string looks valid
            if 'x' in current_geometry and '+' in current_geometry:
                # Only save if it actually changed
                if self.config.get('geometry') != current_geometry:
                    # print(f"Saving geometry for {self.roi_name}: {current_geometry}") # Debug
                    self.config['geometry'] = current_geometry
                    # Use manager's method if available, otherwise direct save
                    if self.manager and hasattr(self.manager, 'save_specific_overlay_config'):
                        self.manager.save_specific_overlay_config(self.roi_name, {'geometry': current_geometry})
                    else:
                        # Fallback for windows not managed (like snip - though it shouldn't save)
                        save_overlay_config_for_roi(self.roi_name, {'geometry': current_geometry})
            else:
                # This shouldn't happen if the window exists
                print(f"Warning: Invalid geometry string generated for {self.roi_name}: {current_geometry}")
        except tk.TclError:
            # Window might be destroyed during the process
            # print(f"Debug: TclError saving geometry for {self.roi_name} (likely destroyed)")
            pass
        except Exception as e:
            print(f"Error saving geometry for {self.roi_name}: {e}")

    def center_and_default_size(self):
        """Sets a default size and centers the window roughly."""
        try:
            self.update_idletasks() # Ensure dimensions are calculated if possible

            # Estimate default width based on wraplength + padding
            default_width = max(self.MIN_WIDTH, self.config.get('wraplength', 450) + 20)
            default_height = max(self.MIN_HEIGHT, 50) # Default height

            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()

            # Center horizontally, place in upper third vertically
            x = max(0, (screen_width // 2) - (default_width // 2))
            y = max(0, (screen_height // 3) - (default_height // 2))

            self.geometry(f"{default_width}x{default_height}+{x}+{y}")
        except tk.TclError:
            # May fail if called too early or window is destroyed
            print(f"Warning: TclError during center_and_default_size for {self.roi_name}")
        except Exception as e:
            print(f"Error centering window {self.roi_name}: {e}")

    def _update_label_config(self):
        """Applies font, color, wrap, and justification settings to the label."""
        font_family = self.config.get('font_family', 'Segoe UI')
        font_size = self.config.get('font_size', 14)
        font_color = self.config.get('font_color', 'white')
        bg_color = self.config.get('bg_color', '#222222')
        wraplength = self.config.get('wraplength', 450) # Pixels to wrap at

        # Map justification string to Tkinter constants
        justify_map = {'left': tk.LEFT, 'center': tk.CENTER, 'right': tk.RIGHT}
        justify_align = justify_map.get(self.config.get('justify', 'left'), tk.LEFT)

        try:
            # Create font object
            label_font = tkFont.Font(family=font_family, size=font_size)
        except tk.TclError:
            # Fallback if font family is invalid
            print(f"Warning: Font family '{font_family}' not found for {self.roi_name}. Using default.")
            label_font = tkFont.Font(size=font_size)

        # Configure the label
        self.label.config(
            font=label_font,
            fg=font_color,
            bg=bg_color,
            wraplength=wraplength,
            justify=justify_align
        )
        # Update background colors of containers
        self.content_frame.config(bg=bg_color)
        self.configure(background=bg_color) # Window background

    def update_text(self, text, global_overlays_enabled=True):
        """Updates the label text and manages window visibility."""
        # Ensure text is a string
        if not isinstance(text, str):
            text = str(text)

        # Update text variable only if changed
        if text != self.label_var.get():
            self.label_var.set(text)

        # Check if window still exists before proceeding
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return # Window is gone

        # Determine if the window *should* be visible
        manager_global_state = global_overlays_enabled
        # If managed, get global state from manager
        if self.manager and hasattr(self.manager, 'global_overlays_enabled'):
            manager_global_state = self.manager.global_overlays_enabled
        # Snip window is always considered globally enabled when it exists
        elif self.roi_name == "_snip_translate":
            manager_global_state = True

        is_individually_enabled = self.config.get('enabled', True)
        should_be_visible = manager_global_state and is_individually_enabled and bool(text)

        # Get current visibility state
        try:
            is_currently_visible = self.state() == 'normal'
        except tk.TclError:
            return # Window likely destroyed

        # Update visibility state if needed
        if should_be_visible and not is_currently_visible:
            try:
                self.deiconify() # Show/unhide
                self.lift() # Bring to front
            except tk.TclError: pass # Ignore if destroyed mid-operation
        elif not should_be_visible and is_currently_visible:
            try:
                self.withdraw() # Hide
            except tk.TclError: pass # Ignore if destroyed mid-operation


    def update_config(self, new_config):
        """Applies a new configuration dictionary to the window."""
        needs_geom_reload = False
        # Check if geometry needs reloading (e.g., reset button)
        if 'geometry' in new_config and new_config['geometry'] != self.config.get('geometry'):
            # If new geometry is explicitly None, trigger reload/reset
            if new_config['geometry'] is None:
                needs_geom_reload = True
                # Keep existing geometry in self.config until reload happens
                # but remove it from new_config so it doesn't overwrite immediately
                del new_config['geometry']

        # Update the internal config dictionary
        self.config.update(new_config) # Use update to merge changes

        # Apply visual changes
        self._update_label_config()
        self._apply_alpha()

        # Reload geometry if requested (e.g., reset)
        if needs_geom_reload:
            self._load_geometry()
        # If geometry was provided directly in new_config (and not None), apply it
        elif 'geometry' in new_config and new_config['geometry'] is not None:
            # Ensure minimum size constraints are met when applying directly
            try:
                parts = new_config['geometry'].split('+')
                size_part, pos_parts = parts[0], parts[1:]
                if len(pos_parts) == 2 and 'x' in size_part:
                    w_str, h_str = size_part.split('x')
                    w = max(self.MIN_WIDTH, int(w_str))
                    h = max(self.MIN_HEIGHT, int(h_str))
                    x, y = int(pos_parts[0]), int(pos_parts[1])
                    self.geometry(f"{w}x{h}+{x}+{y}")
            except Exception:
                print(f"Warning: Failed to apply specific geometry '{new_config['geometry']}' for {self.roi_name}")
                self._load_geometry() # Fallback to load/default


        # Update visibility based on potentially changed 'enabled' state
        manager_global_state = True
        if self.manager and hasattr(self.manager, 'global_overlays_enabled'):
            manager_global_state = self.manager.global_overlays_enabled
        self.update_text(self.label_var.get(), global_overlays_enabled=manager_global_state)

    # --- Dragging Methods ---
    def on_press(self, event):
        """Records click offset for dragging, ignores clicks on grip/close button."""
        # Check if the click originated from the grip or a close button
        widget = event.widget
        while widget is not None:
            if widget == self.grip or getattr(widget, '_is_close_button', False):
                return # Do not start drag if click is on grip or close button
            widget = widget.master # Check parent widget

        # Start dragging state
        self._offset_x = event.x
        self._offset_y = event.y
        self._dragging = True

    def on_drag(self, event):
        """Moves the window based on mouse movement during drag."""
        if not self._dragging:
            return
        # Calculate new window position
        new_x = self.winfo_x() + event.x - self._offset_x
        new_y = self.winfo_y() + event.y - self._offset_y
        # Apply new position
        if self.winfo_exists():
            try:
                self.geometry(f"+{new_x}+{new_y}")
            except tk.TclError: pass # Ignore if window destroyed

    def on_release(self, event):
        """Ends dragging state and saves the new position."""
        if not self._dragging:
            return
        self._dragging = False
        self._save_geometry() # Save position after dragging stops

    # --- Resizing Methods ---
    def on_resize_press(self, event):
        """Records starting position and size for resizing."""
        self._resizing = True
        self._resize_start_x = event.x_root # Use screen coordinates for resize start
        self._resize_start_y = event.y_root
        # Get current size safely
        if not self.winfo_exists():
            self._resizing = False
            return
        try:
            self._resize_start_width = self.winfo_width()
            self._resize_start_height = self.winfo_height()
        except tk.TclError:
            self._resizing = False # Failed to get size, cancel resize
            return

    def on_resize_drag(self, event):
        """Resizes the window based on mouse movement from the grip."""
        if not self._resizing:
            return
        # Calculate change in mouse position (screen coordinates)
        delta_x = event.x_root - self._resize_start_x
        delta_y = event.y_root - self._resize_start_y
        # Calculate new size, enforcing minimum dimensions
        new_width = max(self.MIN_WIDTH, self._resize_start_width + delta_x)
        new_height = max(self.MIN_HEIGHT, self._resize_start_height + delta_y)
        # Apply new size (position remains the same during resize)
        if self.winfo_exists():
            try:
                current_x = self.winfo_x()
                current_y = self.winfo_y()
                self.geometry(f"{new_width}x{new_height}+{current_x}+{current_y}")
            except tk.TclError: pass # Ignore if window destroyed

    def on_resize_release(self, event):
        """Ends resizing state and saves the new size/position."""
        if not self._resizing:
            return
        self._resizing = False
        self._save_geometry() # Save size/position after resizing stops

    def destroy_window(self):
        """Safely destroys the window."""
        # print(f"Destroying window for {self.roi_name}") # Debug
        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            # print(f"Debug: TclError destroying window {self.roi_name} (already gone?)")
            pass # Ignore if already destroyed
        except Exception as e:
            print(f"Error destroying window {self.roi_name}: {e}")


class ClosableFloatingOverlayWindow(FloatingOverlayWindow):
    """A floating overlay window with a small close button."""
    def __init__(self, master, roi_name, initial_config, manager_ref):
        super().__init__(master, roi_name, initial_config, manager_ref)

        # Style for the small close button
        style = ttk.Style(self)
        # Configure padding and font size for the button style
        style.configure("Close.TButton", padding=0, font=('Segoe UI', 7))

        # Create the close button
        close_button = ttk.Button(
            self.content_frame, # Place button inside the content frame
            text="✕", # Close symbol (Unicode multiplication sign)
            command=self.destroy_window, # Command to close the window
            width=2, # Make button small
            style="Close.TButton" # Apply the custom style
        )
        # Add a flag to identify this button during drag checks
        close_button._is_close_button = True

        # Place the button in the top-right corner of the content frame grid
        close_button.grid(row=0, column=1, sticky="ne", padx=(0, 1), pady=(1, 0))

        # Ensure the button column doesn't expand (column 0 holds the label and expands)
        self.content_frame.grid_columnconfigure(1, weight=0)

    def _save_geometry(self):
        """Override save_geometry for closable windows (like snip) to prevent saving."""
        # print(f"Skipping geometry save for closable window: {self.roi_name}") # Debug
        pass # Do not save geometry for temporary/closable windows

# --- END OF FILE ui/floating_overlay_window.py ---