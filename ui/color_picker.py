import tkinter as tk
import mss
import numpy as np

class ScreenColorPicker:
    def __init__(self, master):
        self.master = master
        self.overlay = None
        self.callback = None

    def grab_color(self, callback):
        if self.overlay and self.overlay.winfo_exists():
            return
        self.callback = callback
        try:
            self.overlay = tk.Toplevel(self.master)
            self.overlay.attributes("-fullscreen", True)
            self.overlay.attributes("-alpha", 0.01)
            self.overlay.overrideredirect(True)
            self.overlay.attributes("-topmost", True)
            self.overlay.configure(cursor="crosshair")
            self.overlay.grab_set()
            self.overlay.bind("<ButtonPress-1>", self._on_click)
            self.overlay.bind("<Escape>", self._on_cancel)
            self.overlay.focus_force()
        except Exception as e:
            print(f"Error creating color picker overlay: {e}")
            self._cleanup()
            if self.callback:
                self.callback(None)

    def _on_click(self, event):
        x, y = event.x_root, event.y_root
        if self.overlay and self.overlay.winfo_exists():
            try:
                self.overlay.grab_release()
                self.overlay.destroy()
            except tk.TclError:
                pass
        self.overlay = None
        color_rgb = None
        try:
            monitor = {"top": y, "left": x, "width": 1, "height": 1}
            with mss.mss() as sct:
                sct_img = sct.grab(monitor)
            img_array = np.array(sct_img, dtype=np.uint8)
            if img_array.size >= 3:
                b, g, r = img_array[0, 0][:3]
                color_rgb = (int(r), int(g), int(b))
        except Exception as e:
            print(f"Error capturing screen color: {e}")
        if self.callback:
            try:
                self.callback(color_rgb)
            except Exception as cb_err:
                print(f"Error executing color picker callback: {cb_err}")
        self.callback = None

    def _on_cancel(self, event=None):
        print("Color picking cancelled.")
        self._cleanup()
        if self.callback:
            try:
                self.callback(None)
            except Exception as cb_err:
                print(f"Error executing cancellation callback: {cb_err}")
        self.callback = None

    def _cleanup(self):
        if self.overlay and self.overlay.winfo_exists():
            try:
                self.overlay.grab_release()
                self.overlay.destroy()
            except tk.TclError:
                pass
        self.overlay = None