# --- START OF FILE ui/preview_window.py ---

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import numpy as np

class PreviewWindow(tk.Toplevel):
    """A simple Toplevel window to display an image preview."""

    def __init__(self, master, title="Preview", image_np=None):
        super().__init__(master)
        self.title(title)
        self.transient(master) # Keep window on top of master
        self.grab_set() # Modal behavior (optional)
        self.resizable(False, False)

        self.image_label = ttk.Label(self)
        self.image_label.pack(padx=5, pady=5)

        self.photo_image = None # Keep a reference

        if image_np is not None:
            self.update_image(image_np)
        else:
            self.image_label.config(text="No image data.")

        # Center the window relative to the master
        self.update_idletasks()
        master_x = master.winfo_rootx()
        master_y = master.winfo_rooty()
        master_w = master.winfo_width()
        master_h = master.winfo_height()
        win_w = self.winfo_width()
        win_h = self.winfo_height()
        x = master_x + (master_w - win_w) // 2
        y = master_y + (master_h - win_h) // 3 # Position slightly higher
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self.protocol("WM_DELETE_WINDOW", self.close_window)
        self.bind("<Escape>", lambda e: self.close_window())

    def update_image(self, image_np):
        """Updates the displayed image."""
        if image_np is None or image_np.size == 0:
            self.image_label.config(image='', text="Invalid image data.")
            self.photo_image = None
            return

        try:
            # Ensure image is in a displayable format (e.g., RGB)
            if len(image_np.shape) == 3 and image_np.shape[2] == 3:
                # Assume BGR from OpenCV, convert to RGB for PIL
                # If it's already RGB, this won't hurt much
                # img_rgb = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB) # Done in roi_tab now
                img_pil = Image.fromarray(image_np) # Assumes input is RGB now
            elif len(image_np.shape) == 2: # Grayscale
                img_pil = Image.fromarray(image_np, 'L')
            else:
                self.image_label.config(image='', text="Unsupported image format.")
                self.photo_image = None
                return

            self.photo_image = ImageTk.PhotoImage(img_pil)
            self.image_label.config(image=self.photo_image, text="")

        except Exception as e:
            print(f"Error updating preview image: {e}")
            self.image_label.config(image='', text=f"Error: {e}")
            self.photo_image = None

    def close_window(self):
        self.grab_release()
        self.destroy()

# --- END OF FILE ui/preview_window.py ---