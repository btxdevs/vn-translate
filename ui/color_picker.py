# --- START OF FILE ui/color_picker.py ---

import tkinter as tk
import mss
import numpy as np
# import cv2 # Not needed if mss provides RGB directly or we handle BGRA

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
            # Optionally bring existing picker to front? Or just ignore.
            # self.overlay.lift()
            return

        self.callback = callback
        try:
            self.overlay = tk.Toplevel(self.master)
            self.overlay.attributes("-fullscreen", True)
            self.overlay.attributes("-alpha", 0.01) # Make almost fully transparent
            self.overlay.overrideredirect(True)
            self.overlay.attributes("-topmost", True)
            self.overlay.configure(cursor="crosshair")
            self.overlay.grab_set()

            self.overlay.bind("<ButtonPress-1>", self._on_click)
            self.overlay.bind("<Escape>", self._on_cancel)

            # Focus the overlay window to ensure it receives key events like Escape
            self.overlay.focus_force()

        except Exception as e:
            print(f"Error creating color picker overlay: {e}")
            self._cleanup()
            if self.callback:
                self.callback(None)

    def _on_click(self, event):
        """Callback when the user clicks on the overlay."""
        x, y = event.x_root, event.y_root
        print(f"Color picker clicked at screen coordinates: ({x}, {y})")

        # --- Critical Change: Destroy overlay BEFORE capture ---
        # Release grab and destroy the overlay window immediately
        # so it doesn't interfere with the mss capture.
        if self.overlay and self.overlay.winfo_exists():
            try:
                self.overlay.grab_release()
                self.overlay.destroy()
            except tk.TclError: pass # Ignore if already gone
        self.overlay = None # Mark as destroyed
        # ---

        color_rgb = None
        try:
            # Define the 1x1 pixel region to capture at the click coordinates
            monitor = {"top": y, "left": x, "width": 1, "height": 1}

            # Use mss to capture the screen pixel *after* overlay is gone
            with mss.mss() as sct:
                sct_img = sct.grab(monitor)

            # Convert the raw BGRA data to a NumPy array
            # mss returns RGB data in monitor dict mode, BGRA in tuple mode?
            # Let's assume BGRA for safety and convert.
            img_array = np.array(sct_img, dtype=np.uint8)

            # Extract the single pixel's color
            if img_array.size >= 3:
                # Assuming BGRA format from mss raw capture
                b, g, r = img_array[0, 0][:3] # Take first 3 channels (ignore alpha)
                color_rgb = (int(r), int(g), int(b)) # Convert to RGB tuple
                print(f"Picked color (RGB): {color_rgb}")
            else:
                print("Error: Captured image data is too small or invalid.")

        except mss.ScreenShotError as sct_err:
            print(f"Error capturing screen color with mss: {sct_err}")
        except Exception as e:
            print(f"Error processing captured screen color: {e}")
            import traceback
            traceback.print_exc()


        # Call the original callback with the result (color_rgb or None)
        if self.callback:
            # Ensure callback is called even if capture fails
            try:
                self.callback(color_rgb)
            except Exception as cb_err:
                print(f"Error executing color picker callback: {cb_err}")
        self.callback = None # Prevent multiple calls

    def _on_cancel(self, event=None):
        """Callback when the user presses Escape."""
        print("Color picking cancelled.")
        self._cleanup() # Destroy overlay
        if self.callback:
            try:
                self.callback(None) # Notify callback of cancellation
            except Exception as cb_err:
                print(f"Error executing cancellation callback: {cb_err}")
        self.callback = None

    def _cleanup(self):
        """Destroys the overlay window and releases grab if necessary."""
        if self.overlay and self.overlay.winfo_exists():
            try:
                self.overlay.grab_release()
                self.overlay.destroy()
            except tk.TclError:
                pass
        self.overlay = None
        # Keep self.callback until it's called or cancelled

# --- END OF FILE ui/color_picker.py ---