import tkinter as tk
from tkinter import ttk, messagebox, simpledialog # Keep simpledialog just in case? No, remove if not used.
import pyperclip
from utils.settings import get_setting, set_setting

# --- Custom Dialog for Multiline Input ---
class MultilineInputDialog(tk.Toplevel):
    def __init__(self, parent, title=None, prompt=None):
        super().__init__(parent)
        self.transient(parent)
        self.parent = parent
        self.result = None # Store the result here

        if title:
            self.title(title)

        if prompt:
            ttk.Label(self, text=prompt, justify=tk.LEFT).pack(padx=10, pady=(10, 5), anchor=tk.W)

        # Text widget for multiline input
        self.text_widget = tk.Text(self, width=50, height=8, wrap=tk.WORD)
        self.text_widget.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        # Add scrollbar
        scrollbar = ttk.Scrollbar(self.text_widget, command=self.text_widget.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_widget.config(yscrollcommand=scrollbar.set)


        # Buttons frame
        button_frame = ttk.Frame(self)
        button_frame.pack(padx=10, pady=(5, 10), fill=tk.X)

        ok_button = ttk.Button(button_frame, text="OK", width=10, command=self.on_ok)
        ok_button.pack(side=tk.RIGHT, padx=5)

        cancel_button = ttk.Button(button_frame, text="Cancel", width=10, command=self.on_cancel)
        cancel_button.pack(side=tk.RIGHT)

        # Make dialog modal
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.geometry("+%d+%d" % (parent.winfo_rootx()+50, parent.winfo_rooty()+50))
        self.text_widget.focus_set()

        # Wait for the dialog to close
        self.wait_window(self)

    def on_ok(self, event=None):
        self.result = self.text_widget.get("1.0", tk.END).strip()
        self.destroy()

    def on_cancel(self, event=None):
        self.result = None # Indicate cancellation
        self.destroy()

# --- Floating Controls Window ---
class FloatingControls(tk.Toplevel):
    """A small, draggable, topmost window for quick translation actions."""
    def __init__(self, master, app_ref):
        super().__init__(master)
        self.app = app_ref
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        self.title("Controls")
        self._offset_x = 0
        self._offset_y = 0
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.configure(background='#ECECEC')
        style = ttk.Style(self)
        style.configure("Floating.TButton", padding=2, font=('Segoe UI', 8))
        style.configure("Toolbutton.TCheckbutton", padding=3, font=('Segoe UI', 10), indicatoron=False)
        style.map("Toolbutton.TCheckbutton",
                  background=[('selected', '#CCCCCC'), ('!selected', '#E0E0E0')],
                  foreground=[('selected', 'black'), ('!selected', 'black')])

        button_frame = ttk.Frame(self, padding=5)
        button_frame.pack(fill=tk.BOTH, expand=True)

        col_index = 0

        # Retranslate
        self.retranslate_btn = ttk.Button(button_frame, text="🔄", width=3, style="Floating.TButton",
                                          command=self.app.translation_tab.perform_translation)
        self.retranslate_btn.grid(row=0, column=col_index, padx=2, pady=2)
        self.add_tooltip(self.retranslate_btn, "Re-translate (use cache)")
        col_index += 1

        # Force Retranslate
        self.force_retranslate_btn = ttk.Button(button_frame, text="⚡", width=3, style="Floating.TButton",
                                                command=self.app.translation_tab.perform_force_translation)
        self.force_retranslate_btn.grid(row=0, column=col_index, padx=2, pady=2)
        self.add_tooltip(self.force_retranslate_btn, "Force re-translate & update cache")
        col_index += 1

        # Translate with Comment (NEW)
        self.translate_comment_btn = ttk.Button(button_frame, text="💬🔄", width=4, style="Floating.TButton",
                                                command=self.translate_with_comment)
        self.translate_comment_btn.grid(row=0, column=col_index, padx=2, pady=2)
        self.add_tooltip(self.translate_comment_btn, "Translate with Comment (use cache)")
        col_index += 1

        # Force Retranslate with Comment (NEW)
        self.force_translate_comment_btn = ttk.Button(button_frame, text="💬⚡", width=4, style="Floating.TButton",
                                                      command=self.force_translate_with_comment)
        self.force_translate_comment_btn.grid(row=0, column=col_index, padx=2, pady=2)
        self.add_tooltip(self.force_translate_comment_btn, "Force re-translate with Comment & update cache")
        col_index += 1

        # Copy
        self.copy_btn = ttk.Button(button_frame, text="📋", width=3, style="Floating.TButton",
                                   command=self.copy_last_translation)
        self.copy_btn.grid(row=0, column=col_index, padx=2, pady=2)
        self.add_tooltip(self.copy_btn, "Copy last translation(s)")
        col_index += 1

        # Snip
        self.snip_btn = ttk.Button(button_frame, text="✂️", width=3, style="Floating.TButton",
                                   command=self.start_snip_mode)
        self.snip_btn.grid(row=0, column=col_index, padx=2, pady=2)
        self.add_tooltip(self.snip_btn, "Snip & Translate Region")
        col_index += 1

        # Auto-Translate Toggle
        initial_auto_state = False
        if hasattr(self.app, 'translation_tab') and self.app.translation_tab:
            initial_auto_state = self.app.translation_tab.is_auto_translate_enabled()
        self.auto_var = tk.BooleanVar(value=initial_auto_state)
        self.auto_btn = ttk.Checkbutton(button_frame, text="🤖", style="Toolbutton.TCheckbutton",
                                        variable=self.auto_var, command=self.toggle_auto_translate,
                                        width=3)
        self.auto_btn.grid(row=0, column=col_index, padx=2, pady=2)
        self.add_tooltip(self.auto_btn, "Toggle Auto-Translate")
        col_index += 1

        # Overlay Toggle
        initial_overlay_state = True
        if hasattr(self.app, 'overlay_manager') and self.app.overlay_manager:
            initial_overlay_state = self.app.overlay_manager.global_overlays_enabled
        self.overlay_var = tk.BooleanVar(value=initial_overlay_state)
        self.overlay_btn = ttk.Checkbutton(button_frame, text="👁️", style="Toolbutton.TCheckbutton",
                                           variable=self.overlay_var, command=self.toggle_overlays,
                                           width=3)
        self.overlay_btn.grid(row=0, column=col_index, padx=2, pady=2)
        self.add_tooltip(self.overlay_btn, "Show/Hide Overlays")
        col_index += 1

        # Close Button
        self.close_btn = ttk.Button(button_frame, text="✕", width=2, style="Floating.TButton",
                                    command=self.withdraw)
        self.close_btn.grid(row=0, column=col_index, padx=(5, 2), pady=2)
        self.add_tooltip(self.close_btn, "Hide Controls")

        # Positioning
        saved_pos = get_setting("floating_controls_pos")
        if saved_pos:
            try:
                x, y = map(int, saved_pos.split(','))
                self.update_idletasks()
                win_width = self.winfo_reqwidth()
                win_height = self.winfo_reqheight()
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()
                if 0 <= x <= screen_width - win_width and 0 <= y <= screen_height - win_height:
                    self.geometry(f"+{x}+{y}")
                else:
                    print("Saved floating controls position out of bounds, centering.")
                    self.center_window()
            except Exception as e:
                print(f"Error parsing saved position '{saved_pos}': {e}. Centering window.")
                self.center_window()
        else:
            self.center_window()

        self.master.after_idle(self.update_button_states)
        self.deiconify()

    def center_window(self):
        try:
            self.update_idletasks()
            width = self.winfo_reqwidth()
            screen_width = self.winfo_screenwidth()
            x = (screen_width // 2) - (width // 2)
            y = 10
            self.geometry(f'+{x}+{y}')
        except Exception as e:
            print(f"Error centering floating controls: {e}")

    def on_press(self, event):
        self._offset_x = event.x
        self._offset_y = event.y

    def on_drag(self, event):
        new_x = self.winfo_x() + event.x - self._offset_x
        new_y = self.winfo_y() + event.y - self._offset_y
        self.geometry(f"+{new_x}+{new_y}")

    def on_release(self, event):
        try:
            x = self.winfo_x()
            y = self.winfo_y()
            set_setting("floating_controls_pos", f"{x},{y}")
        except Exception as e:
            print(f"Error saving floating controls position: {e}")

    def copy_last_translation(self):
        if not hasattr(self.app, 'translation_tab') or not hasattr(self.app.translation_tab, 'last_translation_result'):
            self.app.update_status("No translation available.")
            return
        last_result = getattr(self.app.translation_tab, 'last_translation_result', None)
        if last_result and isinstance(last_result, dict):
            copy_text = ""
            rois_to_iterate = self.app.rois if hasattr(self.app, 'rois') else []
            for roi in rois_to_iterate:
                roi_name = roi.name
                if roi_name in last_result:
                    translation = last_result[roi_name]
                    if translation and translation not in ["[Translation Missing]", "[Translation N/A]"]:
                        if copy_text:
                            copy_text += "\n\n"
                        copy_text += translation
            if copy_text:
                try:
                    pyperclip.copy(copy_text)
                    print("Last translation copied to clipboard.")
                    self.app.update_status("Translation copied.")
                except pyperclip.PyperclipException as e:
                    print(f"Pyperclip Error: {e}")
                    self.app.update_status("Error: Could not copy (Pyperclip).")
                    messagebox.showerror("Clipboard Error", f"Could not copy text to clipboard.\nPyperclip error: {e}", parent=self)
                except Exception as e:
                    print(f"Error copying to clipboard: {e}")
                    self.app.update_status("Error copying translation.")
            else:
                self.app.update_status("No translation to copy.")
        else:
            self.app.update_status("No translation to copy.")

    def start_snip_mode(self):
        if hasattr(self.app, 'start_snip_mode'):
            self.app.start_snip_mode()
        else:
            print("Error: Snip mode function not found in main app.")
            messagebox.showerror("Error", "Snip & Translate feature not available.", parent=self)

    def _get_multiline_comment(self, title, prompt):
        """Opens a custom dialog for multiline comment input."""
        dialog = MultilineInputDialog(self, title=title, prompt=prompt)
        # The dialog's result is stored in dialog.result after it closes
        return dialog.result

    def translate_with_comment(self):
        """Prompts for a multiline comment and starts translation (using cache)."""
        comment = self._get_multiline_comment("Translate with Comment", "Enter a comment to guide the translation:")
        if comment is None: # User cancelled
            self.app.update_status("Translation with comment cancelled.")
            return
        # comment is already stripped by the dialog

        if hasattr(self.app, 'translation_tab') and hasattr(self.app.translation_tab, 'perform_translation_with_comment'):
            self.app.translation_tab.perform_translation_with_comment(comment, force_recache=False)
        else:
            print("Error: Translation tab or comment function not found.")
            messagebox.showerror("Error", "Translate with comment feature not available.", parent=self)

    def force_translate_with_comment(self):
        """Prompts for a multiline comment and starts force re-translation."""
        comment = self._get_multiline_comment("Force Translate with Comment", "Enter a comment to guide the translation:")
        if comment is None: # User cancelled
            self.app.update_status("Force translation with comment cancelled.")
            return
        # comment is already stripped by the dialog

        if hasattr(self.app, 'translation_tab') and hasattr(self.app.translation_tab, 'perform_translation_with_comment'):
            self.app.translation_tab.perform_translation_with_comment(comment, force_recache=True)
        else:
            print("Error: Translation tab or comment function not found.")
            messagebox.showerror("Error", "Force translate with comment feature not available.", parent=self)

    def toggle_auto_translate(self):
        if not hasattr(self.app, 'translation_tab') or not self.app.translation_tab:
            print("Error: Translation tab not found.")
            self.auto_var.set(not self.auto_var.get())
            return
        try:
            is_enabled_now = self.auto_var.get()
            print(f"Floating controls: Setting auto-translate to: {is_enabled_now}")
            self.app.translation_tab.auto_translate_var.set(is_enabled_now)
            self.app.translation_tab.toggle_auto_translate()
        except Exception as e:
            print(f"Error invoking main auto-translate toggle: {e}")
            try:
                self.auto_var.set(not is_enabled_now)
            except Exception:
                pass

    def toggle_overlays(self):
        if not hasattr(self.app, 'overlay_manager') or not self.app.overlay_manager:
            print("Error: Overlay manager not found.")
            self.overlay_var.set(not self.overlay_var.get())
            return
        try:
            new_state = self.overlay_var.get()
            print(f"Floating controls: Setting global overlays to: {new_state}")
            self.app.overlay_manager.set_global_overlays_enabled(new_state)
        except Exception as e:
            print(f"Error invoking overlay manager toggle: {e}")
            try:
                self.overlay_var.set(not new_state)
            except Exception:
                pass

    def update_button_states(self):
        try:
            if hasattr(self.app, 'translation_tab') and self.app.translation_tab and hasattr(self, 'auto_var') and self.auto_var:
                if self.auto_btn.winfo_exists():
                    self.auto_var.set(self.app.translation_tab.is_auto_translate_enabled())
            if hasattr(self.app, 'overlay_manager') and self.app.overlay_manager and hasattr(self, 'overlay_var') and self.overlay_var:
                if self.overlay_btn.winfo_exists():
                    self.overlay_var.set(self.app.overlay_manager.global_overlays_enabled)
        except tk.TclError:
            print("Warning: TclError during floating controls state update (widgets closing?).")
        except Exception as e:
            print(f"Error updating floating control states: {e}")

    def add_tooltip(self, widget, text):
        Tooltip(widget, text)

class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.enter_id = None
        self.leave_id = None
        self.widget.bind("<Enter>", self.schedule_show, add='+')
        self.widget.bind("<Leave>", self.schedule_hide, add='+')
        self.widget.bind("<ButtonPress>", self.force_hide, add='+')

    def schedule_show(self, event=None):
        self.unschedule()
        self.enter_id = self.widget.after(500, self.showtip)

    def schedule_hide(self, event=None):
        self.unschedule()
        self.leave_id = self.widget.after(100, self.hidetip)

    def unschedule(self):
        enter_id = self.enter_id
        self.enter_id = None
        if enter_id:
            try:
                self.widget.after_cancel(enter_id)
            except Exception:
                pass
        leave_id = self.leave_id
        self.leave_id = None
        if leave_id:
            try:
                self.widget.after_cancel(leave_id)
            except Exception:
                pass

    def showtip(self):
        self.unschedule()
        if self.tipwindow or not self.text:
            return
        try:
            if not self.widget.winfo_exists():
                return
            x, y, _, _ = self.widget.bbox("insert")
            x += self.widget.winfo_rootx() + 20
            y += self.widget.winfo_rooty() + self.widget.winfo_height() + 5
            self.tipwindow = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                             background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                             font=("tahoma", "8", "normal"), wraplength=200)
            label.pack(ipadx=2, ipady=1)
        except tk.TclError:
            self.tipwindow = None
        except Exception as e:
            print(f"Error showing tooltip: {e}")
            self.tipwindow = None

    def hidetip(self):
        self.unschedule()
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            try:
                tw.destroy()
            except tk.TclError:
                pass

    def force_hide(self, event=None):
        self.hidetip()