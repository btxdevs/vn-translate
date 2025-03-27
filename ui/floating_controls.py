import tkinter as tk
from tkinter import ttk
import pyperclip # For copy functionality (install: pip install pyperclip)
from utils.settings import get_setting, set_setting

class FloatingControls(tk.Toplevel):
    """A small, draggable, topmost window for quick translation actions."""

    def __init__(self, master, app_ref):
        super().__init__(master)
        self.app = app_ref

        # --- Window Configuration ---
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        self.title("Controls")
        # Make transparent on Windows? Less useful for controls.
        # self.wm_attributes("-transparentcolor", "gray1")
        # self.config(bg="gray1")

        # Make window draggable
        self._offset_x = 0
        self._offset_y = 0
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release) # Save position on release

        # Style
        self.configure(background='#ECECEC') # Light grey background
        style = ttk.Style(self)
        # Define a smaller button style
        style.configure("Floating.TButton", padding=2, font=('Segoe UI', 8))
        # Use 'TButton' for checkbuttons to make them look like toggle buttons
        style.map("Toolbutton.TButton",
                  relief=[('pressed', 'sunken'), ('!pressed', 'raised')])
        style.configure("Toolbutton.TButton", padding=2, font=('Segoe UI', 10)) # Slightly larger font for symbols


        # --- Content ---
        button_frame = ttk.Frame(self, padding=5, style="Floating.TFrame") # Use a style?
        button_frame.pack(fill=tk.BOTH, expand=True)

        # Re-translate Button
        self.retranslate_btn = ttk.Button(button_frame, text="🔄", width=3, style="Floating.TButton",
                                          command=self.app.translation_tab.perform_translation)
        self.retranslate_btn.grid(row=0, column=0, padx=2, pady=2)
        self.add_tooltip(self.retranslate_btn, "Re-translate stable text")


        # Copy Last Translation Button
        self.copy_btn = ttk.Button(button_frame, text="📋", width=3, style="Floating.TButton",
                                   command=self.copy_last_translation)
        self.copy_btn.grid(row=0, column=1, padx=2, pady=2)
        self.add_tooltip(self.copy_btn, "Copy last translation(s)")

        # Toggle Auto-Translate Button (using Checkbutton)
        self.auto_var = tk.BooleanVar(value=self.app.translation_tab.is_auto_translate_enabled())
        self.auto_btn = ttk.Checkbutton(button_frame, text="🤖", style="Toolbutton.TButton", # Checkbutton styled as Button
                                        variable=self.auto_var, command=self.toggle_auto_translate,
                                        width=3)
        self.auto_btn.grid(row=0, column=2, padx=2, pady=2)
        self.add_tooltip(self.auto_btn, "Toggle Auto-Translate")


        # Show/Hide Overlays Button (using Checkbutton)
        self.overlay_var = tk.BooleanVar(value=self.app.overlay_manager.global_overlays_enabled)
        self.overlay_btn = ttk.Checkbutton(button_frame, text="👁️", style="Toolbutton.TButton",
                                           variable=self.overlay_var, command=self.toggle_overlays,
                                           width=3)
        self.overlay_btn.grid(row=0, column=3, padx=2, pady=2)
        self.add_tooltip(self.overlay_btn, "Show/Hide Overlays")


        # Close Button (Optional - using withdraw)
        self.close_btn = ttk.Button(button_frame, text="✕", width=2, style="Floating.TButton",
                                    command=self.withdraw) # Hide instead of destroy
        self.close_btn.grid(row=0, column=4, padx=(5, 2), pady=2)
        self.add_tooltip(self.close_btn, "Hide Controls")

        # --- Initial Position ---
        saved_pos = get_setting("floating_controls_pos")
        if saved_pos:
            try:
                x, y = map(int, saved_pos.split(','))
                # Check bounds roughly
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()
                # Ensure it's fully visible
                self.update_idletasks() # Needed to get initial size estimate
                win_width = self.winfo_reqwidth()
                win_height = self.winfo_reqheight()

                if 0 <= x < screen_width - win_width and 0 <= y < screen_height - win_height:
                    self.geometry(f"+{x}+{y}")
                else:
                    print("Saved floating controls position out of bounds, centering.")
                    self.center_window()
            except Exception as e:
                print(f"Error parsing saved position '{saved_pos}': {e}. Centering window.")
                self.center_window()
        else:
            self.center_window()

        # Ensure state variables match app state after initialization
        self.update_button_states()

        self.deiconify() # Show the window

    def center_window(self):
        """Positions the window near the top center of the screen."""
        self.update_idletasks() # Calculate size
        width = self.winfo_reqwidth()
        # height = self.winfo_reqheight() # Height not needed for this centering
        screen_width = self.winfo_screenwidth()
        # screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = 10 # Position near top-center
        self.geometry(f'+{x}+{y}')

    def on_press(self, event):
        """Start dragging."""
        self._offset_x = event.x
        self._offset_y = event.y
        # self.focus_force() # Bring to front when clicked (might not be needed with topmost)

    def on_drag(self, event):
        """Move window during drag."""
        new_x = self.winfo_x() + event.x - self._offset_x
        new_y = self.winfo_y() + event.y - self._offset_y
        self.geometry(f"+{new_x}+{new_y}")

    def on_release(self, event):
        """Save the window position when dragging stops."""
        x = self.winfo_x()
        y = self.winfo_y()
        set_setting("floating_controls_pos", f"{x},{y}")
        print(f"Floating controls position saved: {x},{y}")

    def copy_last_translation(self):
        """Copies the last successful translation to the clipboard."""
        last_result = getattr(self.app.translation_tab, 'last_translation_result', None)
        if last_result and isinstance(last_result, dict):
            # Format: Combine translations from different ROIs in app's ROI order
            copy_text = ""
            for roi in self.app.rois: # Iterate in ROI order
                roi_name = roi.name
                if roi_name in last_result:
                    translation = last_result[roi_name]
                    if translation and translation != "[Translation Missing]":
                        if copy_text: copy_text += "\n\n" # Separator between ROIs
                        # Optionally include ROI name?
                        # copy_text += f"[{roi_name}]\n{translation}"
                        copy_text += translation # Just the translated text

            if copy_text:
                try:
                    pyperclip.copy(copy_text)
                    print("Last translation copied to clipboard.")
                    self.app.update_status("Translation copied.") # Update main status
                except pyperclip.PyperclipException as e:
                    print(f"Pyperclip Error: Could not copy to clipboard. Is it installed and configured? Error: {e}")
                    self.app.update_status("Error: Could not copy (Pyperclip).")
                    messagebox.showerror("Clipboard Error", f"Could not copy text to clipboard.\nPyperclip error: {e}", parent=self)
                except Exception as e:
                    print(f"Error copying to clipboard: {e}")
                    self.app.update_status("Error copying translation.")
            else:
                print("No text found in last translation result.")
                self.app.update_status("No translation to copy.")
        else:
            print("No previous translation available to copy.")
            self.app.update_status("No translation to copy.")

    def toggle_auto_translate(self):
        """Toggles the auto-translate feature via the main app's setting."""
        # The Checkbutton variable (self.auto_var) changes automatically.
        # This command should now call the main app's toggle function.
        is_enabled_after_toggle = self.auto_var.get()
        print(f"Floating controls toggling auto-translate to: {is_enabled_after_toggle}")

        # Find the Checkbutton in the translation tab and invoke its command
        try:
            main_checkbutton = self.app.translation_tab.auto_translate_check
            # Set the main variable first to ensure invoke() sees the correct state
            self.app.translation_tab.auto_translate_var.set(is_enabled_after_toggle)
            # Call the command associated with the main checkbutton
            main_checkbutton.invoke()
        except Exception as e:
            print(f"Error invoking main auto-translate toggle: {e}")
            # Revert local state if invocation failed?
            self.auto_var.set(not is_enabled_after_toggle)


    def toggle_overlays(self):
        """Toggles the global overlay visibility via the OverlayManager."""
        # Variable changes automatically via Checkbutton binding
        new_state = self.overlay_var.get()
        print(f"Floating controls toggling global overlays to: {new_state}")
        self.app.overlay_manager.set_global_overlays_enabled(new_state)
        # Status update handled by set_global_overlays_enabled


    def update_button_states(self):
        """Syncs button check states with the application state (e.g., on show)."""
        if self.app.translation_tab:
            self.auto_var.set(self.app.translation_tab.is_auto_translate_enabled())
        if self.app.overlay_manager:
            self.overlay_var.set(self.app.overlay_manager.global_overlays_enabled)


    def add_tooltip(self, widget, text):
        """Simple tooltip implementation."""
        tooltip = Tooltip(widget, text)
        #widget.bind("<Enter>", lambda event, t=tooltip: t.showtip())
        #widget.bind("<Leave>", lambda event, t=tooltip: t.hidetip())


# Simple Tooltip class (optional, basic version)
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
        self.widget.bind("<ButtonPress>", self.force_hide, add='+') # Hide on click

    def schedule_show(self, event=None):
        self.unschedule()
        self.enter_id = self.widget.after(500, self.showtip) # Delay showing tip

    def schedule_hide(self, event=None):
        self.unschedule()
        self.leave_id = self.widget.after(100, self.hidetip) # Slight delay hiding

    def unschedule(self):
        enter_id = self.enter_id
        self.enter_id = None
        if enter_id:
            self.widget.after_cancel(enter_id)

        leave_id = self.leave_id
        self.leave_id = None
        if leave_id:
            self.widget.after_cancel(leave_id)

    def showtip(self):
        self.unschedule() # Ensure hide isn't scheduled
        if self.tipwindow or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert") # Get position relative to widget
        # Calculate position relative to screen
        x += self.widget.winfo_rootx() + 20
        y += self.widget.winfo_rooty() + self.widget.winfo_height() + 5 # Below widget
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", "8", "normal"), wraplength=200) # Wrap long tooltips
        label.pack(ipadx=2, ipady=1)
        # Schedule auto-hide after some time?
        # self.leave_id = self.widget.after(5000, self.hidetip)


    def hidetip(self):
        self.unschedule()
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            try:
                tw.destroy()
            except tk.TclError:
                pass # Window might already be destroyed

    def force_hide(self, event=None):
        self.hidetip() # Hide immediately on click