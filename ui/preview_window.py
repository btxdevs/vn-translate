import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk


class PreviewWindow(tk.Toplevel):
    def __init__(self, master, title="Preview", image_np=None):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.grab_set()
        self.resizable(False, False)
        self.image_label = ttk.Label(self)
        self.image_label.pack(padx=5, pady=5)
        self.photo_image = None
        if image_np is not None:
            self.update_image(image_np)
        else:
            self.image_label.config(text="No image data.")
        self.update_idletasks()
        master_x = master.winfo_rootx()
        master_y = master.winfo_rooty()
        master_w = master.winfo_width()
        master_h = master.winfo_height()
        win_w = self.winfo_width()
        win_h = self.winfo_height()
        x = master_x + (master_w - win_w) // 2
        y = master_y + (master_h - win_h) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        self.bind("<Escape>", lambda e: self.close_window())

    def update_image(self, image_np):
        if image_np is None or image_np.size == 0:
            self.image_label.config(image='', text="Invalid image data.")
            self.photo_image = None
            return
        try:
            if len(image_np.shape) == 3 and image_np.shape[2] == 3:
                img_pil = Image.fromarray(image_np)
            elif len(image_np.shape) == 2:
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