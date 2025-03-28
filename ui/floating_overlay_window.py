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
        self.manager = manager_ref
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        self.configure(background=self.config.get('bg_color', '#222222'))
        self._apply_alpha()
        self._offset_x = 0
        self._offset_y = 0
        self._dragging = False
        self._resizing = False
        self._resize_start_x = 0
        self._resize_start_y = 0
        self._resize_start_width = 0
        self._resize_start_height = 0
        self.content_frame = tk.Frame(self, bg=self.config.get('bg_color', '#222222'))
        self.content_frame.pack(fill=tk.BOTH, expand=True)
        self.label_var = tk.StringVar()
        self.label = tk.Label(self.content_frame, textvariable=self.label_var, padx=5, pady=2)
        self._update_label_config()
        self.label.grid(row=0, column=0, sticky="nsew")
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.grip_size = 10
        self.grip = tk.Frame(self, width=self.grip_size, height=self.grip_size, bg='grey50', cursor="bottom_right_corner")
        self.grip.place(relx=1.0, rely=1.0, anchor='se')
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
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
        try:
            alpha_value = float(self.config.get('alpha', 1.0))
            alpha_value = max(0.0, min(1.0, alpha_value))
            self.wm_attributes("-alpha", alpha_value)
        except (ValueError, TypeError, tk.TclError):
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
            except Exception:
                pass
        self.center_and_default_size()

    def _save_geometry(self):
        if self.roi_name == "_snip_translate":
            return
        try:
            if not self.winfo_exists():
                return
            current_geometry = self.geometry()
            if 'x' in current_geometry and '+' in current_geometry:
                if self.config.get('geometry') != current_geometry:
                    self.config['geometry'] = current_geometry
                    save_overlay_config_for_roi(self.roi_name, {'geometry': current_geometry})
            else:
                pass
        except (tk.TclError, Exception):
            pass

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
        except Exception:
            pass

    def _update_label_config(self):
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
            label_font = tkFont.Font(size=font_size)
        self.label.config(font=label_font, fg=font_color, bg=bg_color, wraplength=wraplength, justify=justify_align)
        self.content_frame.config(bg=bg_color)
        self.configure(background=bg_color)

    def update_text(self, text, global_overlays_enabled=True):
        if not isinstance(text, str):
            text = str(text)
        if text != self.label_var.get():
            self.label_var.set(text)
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        manager_global_state = global_overlays_enabled
        if self.manager:
            manager_global_state = self.manager.global_overlays_enabled
        elif self.roi_name == "_snip_translate":
            manager_global_state = True
        is_individually_enabled = self.config.get('enabled', True)
        should_be_visible_if_enabled = manager_global_state and is_individually_enabled
        self.update_idletasks()
        try:
            is_visible = self.state() == 'normal'
        except tk.TclError:
            return
        if should_be_visible_if_enabled and bool(text) and not is_visible:
            try:
                self.deiconify()
                self.lift()
            except tk.TclError:
                pass
        elif not should_be_visible_if_enabled and is_visible:
            try:
                self.withdraw()
            except tk.TclError:
                pass

    def update_config(self, new_config):
        needs_geom_reload = False
        if 'geometry' in new_config and new_config['geometry'] != self.config.get('geometry'):
            if new_config['geometry'] is None:
                needs_geom_reload = True
        self.config = new_config
        self._update_label_config()
        self._apply_alpha()
        if needs_geom_reload:
            self._load_geometry()
        manager_global_state = True
        if self.manager:
            manager_global_state = self.manager.global_overlays_enabled
        self.update_text(self.label_var.get(), global_overlays_enabled=manager_global_state)

    def on_press(self, event):
        widget = event.widget
        while widget is not None:
            if widget == self.grip or getattr(widget, '_is_close_button', False):
                return
            widget = widget.master
        self._offset_x = event.x
        self._offset_y = event.y
        self._dragging = True

    def on_drag(self, event):
        if not self._dragging:
            return
        new_x = self.winfo_x() + event.x - self._offset_x
        new_y = self.winfo_y() + event.y - self._offset_y
        if self.winfo_exists():
            try:
                self.geometry(f"+{new_x}+{new_y}")
            except tk.TclError:
                pass

    def on_release(self, event):
        if not self._dragging:
            return
        self._dragging = False
        self._save_geometry()

    def on_resize_press(self, event):
        self._resizing = True
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        if not self.winfo_exists():
            self._resizing = False
            return
        try:
            self._resize_start_width = self.winfo_width()
            self._resize_start_height = self.winfo_height()
        except tk.TclError:
            self._resizing = False
            return

    def on_resize_drag(self, event):
        if not self._resizing:
            return
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
                pass

    def on_resize_release(self, event):
        if not self._resizing:
            return
        self._resizing = False
        self._save_geometry()

    def destroy_window(self):
        try:
            if self.winfo_exists():
                self.destroy()
        except (tk.TclError, Exception):
            pass

class ClosableFloatingOverlayWindow(FloatingOverlayWindow):
    def __init__(self, master, roi_name, initial_config, manager_ref):
        super().__init__(master, roi_name, initial_config, manager_ref)
        style = ttk.Style(self)
        style.configure("Close.TButton", padding=0, font=('Segoe UI', 7))
        close_button = ttk.Button(
            self.content_frame,
            text="✕",
            command=self.destroy_window,
            width=2,
            style="Close.TButton"
        )
        close_button._is_close_button = True
        close_button.grid(row=0, column=1, sticky="ne", padx=(0, 1), pady=(1, 0))
        self.content_frame.grid_columnconfigure(1, weight=0)

    def _save_geometry(self):
        pass
