import tkinter as tk
from tkinter import font as tkFont
import platform
import win32gui # For positioning relative to game window and click-through
import win32con
import win32api # For GetSystemMetrics

class OverlayWindow(tk.Toplevel):
    """A transparent, topmost window to display translated text for an ROI."""

    def __init__(self, master, roi_name, config, game_hwnd):
        super().__init__(master)
        self.roi_name = roi_name
        self.config = config
        self.game_hwnd = game_hwnd
        self.last_geometry = "" # To avoid unnecessary geometry updates

        # --- Window Configuration ---
        self.overrideredirect(True)  # No window decorations (title bar, borders)
        self.wm_attributes("-topmost", True) # Keep on top

        # --- Transparency & Click-Through (Windows Specific) ---
        self.transparent_color = 'gray1' # A color unlikely to be used
        self.configure(bg=self.transparent_color)

        if platform.system() == "Windows":
            try:
                # Set background color to be transparent
                self.wm_attributes("-transparentcolor", self.transparent_color)

                # Set window style for click-through (WS_EX_LAYERED | WS_EX_TRANSPARENT)
                hwnd = self.winfo_id() # Get HWND after window is created
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                style |= win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
                # Remove WS_EX_APPWINDOW to prevent appearing in taskbar/alt+tab
                style &= ~win32con.WS_EX_APPWINDOW
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)

                # Optional: Set alpha for the whole window (might affect text readability)
                # alpha_percent = int(config.get('alpha', 0.85) * 255) # Use config alpha
                # win32gui.SetLayeredWindowAttributes(hwnd, 0, alpha_percent, win32con.LWA_ALPHA) # 0=ColorKey, 1=Alpha

            except Exception as e:
                print(f"Error setting window attributes for {self.roi_name}: {e}")
        else:
            print("Warning: Overlay transparency/click-through might not work correctly on non-Windows OS.")
            # Basic alpha setting for other platforms (might not be click-through)
            alpha = config.get('alpha', 0.85)
            self.wm_attributes("-alpha", alpha)

        # --- Content Label ---
        self.label_var = tk.StringVar()
        self._update_label_config() # Apply initial config to label

        self.label.pack(fill=tk.BOTH, expand=True)

        self.withdraw() # Start hidden

    def _update_label_config(self):
        """Applies current self.config to the label widget."""
        font_family = self.config.get('font_family', 'Segoe UI')
        font_size = self.config.get('font_size', 14)
        font_color = self.config.get('font_color', 'white')
        bg_color = self.config.get('bg_color', '#222222') # Use actual bg color for the label
        wraplength = self.config.get('wraplength', 450) # Wrap text width
        justify_map = {'left': tk.LEFT, 'center': tk.CENTER, 'right': tk.RIGHT}
        justify_align = justify_map.get(self.config.get('justify', 'left'), tk.LEFT)

        try:
            label_font = tkFont.Font(family=font_family, size=font_size)
        except tk.TclError:
            print(f"Warning: Font '{font_family}' not found. Using default.")
            label_font = tkFont.Font(size=font_size) # Use default family

        if hasattr(self, 'label'): # If label exists, reconfigure
            self.label.config(
                font=label_font,
                fg=font_color,
                bg=bg_color,
                wraplength=wraplength,
                justify=justify_align
            )
        else: # Create label if it doesn't exist
            self.label = tk.Label(
                self,
                textvariable=self.label_var,
                font=label_font,
                fg=font_color,
                bg=bg_color,
                wraplength=wraplength,
                justify=justify_align,
                padx=5, pady=2
            )

        # Optional: Re-apply alpha based on config if needed for non-Windows
        # if platform.system() != "Windows":
        #     alpha = self.config.get('alpha', 0.85)
        #     self.wm_attributes("-alpha", alpha)


    def update_text(self, text):
        """Update the text displayed in the overlay."""
        if not isinstance(text, str):
            text = str(text) # Ensure it's a string

        # Limit length?
        # max_len = 500
        # if len(text) > max_len:
        #     text = text[:max_len] + "..."

        current_text = self.label_var.get()
        # Only update if text actually changed
        if text != current_text:
            self.label_var.set(text)

        # Update visibility based on text and enabled status
        should_be_visible = bool(text) and self.config.get('enabled', True)
        is_visible = self.state() == 'normal'

        if should_be_visible:
            # Update position before showing, but only if needed
            self.update_position_if_needed()
            if not is_visible:
                self.deiconify() # Show window if hidden
                self.lift() # Ensure it's on top
        elif is_visible:
            self.withdraw() # Hide if no text or disabled


    def update_config(self, new_config):
        """Update the appearance based on new configuration."""
        self.config = new_config
        self._update_label_config() # Apply changes to label

        # Update visibility based on new enabled status and current text
        is_enabled = new_config.get('enabled', True)
        has_text = bool(self.label_var.get())

        if is_enabled and has_text:
            self.update_position_if_needed() # Recalc position
            self.deiconify()
            self.lift()
        else:
            self.withdraw()


    def update_position_if_needed(self, roi_rect_in_game_coords=None):
        """Calculates desired geometry and applies it only if changed."""
        new_geometry = self._calculate_geometry(roi_rect_in_game_coords)
        if new_geometry and new_geometry != self.last_geometry:
            self.geometry(new_geometry)
            self.last_geometry = new_geometry


    def _calculate_geometry(self, roi_rect_in_game_coords=None):
        """
        Calculates the desired geometry string "+x+y" for the overlay.
        roi_rect_in_game_coords: tuple (x1, y1, x2, y2) of the ROI within the game window's client area.
        Returns "+x+y" string or None if calculation fails.
        """
        try:
            # Check game window validity
            if not self.game_hwnd or not win32gui.IsWindow(self.game_hwnd) or win32gui.IsIconic(self.game_hwnd):
                if self.state() == 'normal': # Only print if window was visible
                    print(f"Game window {self.game_hwnd} not found or minimized. Hiding overlay {self.roi_name}.")
                    self.withdraw()
                return None

            # Get game window's client area in screen coordinates
            game_client_rect = get_client_rect(self.game_hwnd) # Uses utils.capture function
            if not game_client_rect:
                print(f"Could not get game client rect for HWND {self.game_hwnd}.")
                # Fallback to full window rect? Might be less accurate for positioning relative to client area.
                game_client_rect = get_window_rect(self.game_hwnd)
                if not game_client_rect:
                    if self.state() == 'normal': self.withdraw()
                    return None

            game_x, game_y, game_r, game_b = game_client_rect
            game_width = game_r - game_x
            game_height = game_b - game_y

            # If specific ROI coords relative to game client area are given
            if roi_rect_in_game_coords:
                roi_x1_rel, roi_y1_rel, roi_x2_rel, roi_y2_rel = roi_rect_in_game_coords
                # Ensure ROI coords are within game client bounds before calculating screen coords
                roi_x1_rel = max(0, min(roi_x1_rel, game_width))
                roi_y1_rel = max(0, min(roi_y1_rel, game_height))
                roi_x2_rel = max(0, min(roi_x2_rel, game_width))
                roi_y2_rel = max(0, min(roi_y2_rel, game_height))

                # Absolute screen coordinates of the ROI
                roi_abs_x1 = game_x + roi_x1_rel
                roi_abs_y1 = game_y + roi_y1_rel
                roi_abs_x2 = game_x + roi_x2_rel
                roi_abs_y2 = game_y + roi_y2_rel
                roi_width = roi_abs_x2 - roi_abs_x1
                roi_height = roi_abs_y2 - roi_abs_y1
            else:
                # Fallback: Position relative to the game window itself if no ROI provided
                # E.g., bottom center of the game window
                roi_abs_x1 = game_x + game_width // 4
                roi_abs_y1 = game_y + game_height - 100 # Guess a position
                roi_abs_x2 = game_x + 3 * game_width // 4
                roi_abs_y2 = game_y + game_height - 20 # Guess a position
                roi_width = roi_abs_x2 - roi_abs_x1
                roi_height = roi_abs_y2 - roi_abs_y1


            # --- Calculate Overlay Position based on config ---
            position_mode = self.config.get('position', 'bottom_roi')
            # Ensure overlay window size is calculated accurately
            self.update_idletasks()
            overlay_width = self.label.winfo_reqwidth() # Use requested width of the label
            overlay_height = self.label.winfo_reqheight() # Use requested height of the label

            # Add small safety margin?
            overlay_width += 2
            overlay_height += 2

            x, y = 0, 0
            offset = 5 # Default pixel offset from ROI/Game edge

            if position_mode == 'bottom_roi':
                x = roi_abs_x1 + roi_width // 2 - overlay_width // 2
                y = roi_abs_y2 + offset
            elif position_mode == 'top_roi':
                x = roi_abs_x1 + roi_width // 2 - overlay_width // 2
                y = roi_abs_y1 - overlay_height - offset
            elif position_mode == 'center_roi':
                x = roi_abs_x1 + roi_width // 2 - overlay_width // 2
                y = roi_abs_y1 + roi_height // 2 - overlay_height // 2
            elif position_mode == 'bottom_game':
                x = game_x + game_width // 2 - overlay_width // 2
                y = game_b - overlay_height - offset
            elif position_mode == 'top_game':
                x = game_x + game_width // 2 - overlay_width // 2
                y = game_y + offset
            elif position_mode == 'center_game':
                x = game_x + game_width // 2 - overlay_width // 2
                y = game_y + game_height // 2 - overlay_height // 2
            # Add more modes: fixed coordinates? bottom_left_roi etc.
            else: # Default to bottom_roi
                x = roi_abs_x1 + roi_width // 2 - overlay_width // 2
                y = roi_abs_y2 + offset

            # --- Ensure overlay stays within screen bounds ---
            # Use win32api for potentially multi-monitor aware screen size
            screen_width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
            screen_height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
            screen_left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
            screen_top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)

            # Clamp position
            x = max(screen_left, min(x, screen_left + screen_width - overlay_width))
            y = max(screen_top, min(y, screen_top + screen_height - overlay_height))

            return f"+{int(x)}+{int(y)}"

        except Exception as e:
            print(f"Error calculating position for overlay {self.roi_name}: {e}")
            if self.state() == 'normal': self.withdraw() # Hide if positioning fails
            return None

    def destroy_window(self):
        """Safely destroy the overlay window."""
        try:
            self.destroy()
        except tk.TclError as e:
            print(f"Error destroying overlay {self.roi_name} (already destroyed?): {e}")
        except Exception as e:
            print(f"Unexpected error destroying overlay {self.roi_name}: {e}")

# Helper function (outside class) needed by capture.py if used there
def get_client_rect(hwnd):
    """Helper to get client rect in screen coords. Avoids circular import."""
    try:
        if not win32gui.IsWindow(hwnd): return None
        client_rect_rel = win32gui.GetClientRect(hwnd)
        pt_tl = wintypes.POINT(client_rect_rel[0], client_rect_rel[1])
        pt_br = wintypes.POINT(client_rect_rel[2], client_rect_rel[3])
        if not windll.user32.ClientToScreen(hwnd, byref(pt_tl)): return None
        if not windll.user32.ClientToScreen(hwnd, byref(pt_br)): return None
        return (pt_tl.x, pt_tl.y, pt_br.x, pt_br.y)
    except Exception:
        return None

# Helper function (outside class) needed by capture.py if used there
def get_window_rect(hwnd):
    """Helper to get window rect in screen coords. Avoids circular import."""
    try:
        if not win32gui.IsWindow(hwnd): return None
        return win32gui.GetWindowRect(hwnd)
    except Exception:
        return None