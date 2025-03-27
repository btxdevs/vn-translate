# --- START OF FILE ui/floating_controls.py ---

import tkinter as tk
from tkinter import ttk, messagebox
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
        # Configure Checkbutton style to look like a toggle button
        # Use different foreground colors for selected/unselected states
        style.configure("Toolbutton.TCheckbutton", padding=3, font=('Segoe UI', 10), indicatoron=False) # indicatoron=False makes it look like a button
        style.map("Toolbutton.TCheckbutton",
                  #relief=[('selected', 'sunken'), ('!selected', 'raised')], # Standard button relief
                  background=[('selected', '#CCCCCC'), ('!selected', '#E0E0E0')], # Different background when selected
                  foreground=[('selected', 'black'), ('!selected', 'black')]) # Keep text color consistent or change as needed

        # --- Content ---
        button_frame = ttk.Frame(self, padding=5) # Removed style reference for simplicity
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

        # --- Toggle Auto-Translate Button (using Checkbutton styled as Button) ---
        # Ensure TranslationTab exists before accessing its state
        initial_auto_state = False
        if hasattr(self.app, 'translation_tab') and self.app.translation_tab:
            initial_auto_state = self.app.translation_tab.is_auto_translate_enabled()

        self.auto_var = tk.BooleanVar(value=initial_auto_state)
        self.auto_btn = ttk.Checkbutton(button_frame, text="🤖", style="Toolbutton.TCheckbutton", # Use Checkbutton with custom style
                                        variable=self.auto_var, command=self.toggle_auto_translate,
                                        width=3)
        self.auto_btn.grid(row=0, column=2, padx=2, pady=2)
        self.add_tooltip(self.auto_btn, "Toggle Auto-Translate")

        # --- Show/Hide Overlays Button (using Checkbutton styled as Button) ---
        initial_overlay_state = True
        if hasattr(self.app, 'overlay_manager') and self.app.overlay_manager:
            initial_overlay_state = self.app.overlay_manager.global_overlays_enabled

        self.overlay_var = tk.BooleanVar(value=initial_overlay_state)
        self.overlay_btn = ttk.Checkbutton(button_frame, text="👁️", style="Toolbutton.TCheckbutton",
                                           variable=self.overlay_var, command=self.toggle_overlays,
                                           width=3)
        self.overlay_btn.grid(row=0, column=3, padx=2, pady=2)
        self.add_tooltip(self.overlay_btn, "Show/Hide Overlays")

        # Close Button
        self.close_btn = ttk.Button(button_frame, text="✕", width=2, style="Floating.TButton",
                                    command=self.withdraw) # Hide instead of destroy
        self.close_btn.grid(row=0, column=4, padx=(5, 2), pady=2)
        self.add_tooltip(self.close_btn, "Hide Controls")

        # --- Initial Position ---
        saved_pos = get_setting("floating_controls_pos")
        if saved_pos:
            try:
                x, y = map(int, saved_pos.split(','))
                self.update_idletasks() # Needed for size estimate
                win_width = self.winfo_reqwidth()
                win_height = self.winfo_reqheight()
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()

                # Ensure fully visible
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

        # Ensure state variables match app state after initialization
        # Needs to be called *after* the mainloop starts potentially, or on show
        self.master.after_idle(self.update_button_states) # Defer update slightly

        self.deiconify() # Show the window

    def center_window(self):
        """Positions the window near the top center of the screen."""
        try:
            self.update_idletasks() # Calculate size
            width = self.winfo_reqwidth()
            screen_width = self.winfo_screenwidth()
            x = (screen_width // 2) - (width // 2)
            y = 10 # Position near top-center
            self.geometry(f'+{x}+{y}')
        except Exception as e:
            print(f"Error centering floating controls: {e}")


    def on_press(self, event):
        """Start dragging."""
        self._offset_x = event.x
        self._offset_y = event.y

    def on_drag(self, event):
        """Move window during drag."""
        new_x = self.winfo_x() + event.x - self._offset_x
        new_y = self.winfo_y() + event.y - self._offset_y
        self.geometry(f"+{new_x}+{new_y}")

    def on_release(self, event):
        """Save the window position when dragging stops."""
        try:
            x = self.winfo_x()
            y = self.winfo_y()
            set_setting("floating_controls_pos", f"{x},{y}")
            # print(f"Floating controls position saved: {x},{y}") # Less verbose
        except Exception as e:
            print(f"Error saving floating controls position: {e}")

    def copy_last_translation(self):
        """Copies the last successful translation to the clipboard."""
        last_result = getattr(self.app.translation_tab, 'last_translation_result', None)
        if last_result and isinstance(last_result, dict):
            copy_text = ""
            for roi in self.app.rois: # Iterate in ROI order
                roi_name = roi.name
                if roi_name in last_result:
                    translation = last_result[roi_name]
                    if translation and translation != "[Translation Missing]":
                        if copy_text: copy_text += "\n\n" # Separator
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
                # print("No text found in last translation result.") # Less verbose
                self.app.update_status("No translation to copy.")
        else:
            # print("No previous translation available to copy.") # Less verbose
            self.app.update_status("No translation to copy.")

    def toggle_auto_translate(self):
        """Toggles the auto-translate feature via the main app's translation tab."""
        # Check if translation tab exists
        if not hasattr(self.app, 'translation_tab') or not self.app.translation_tab:
            print("Error: Translation tab not found.")
            # Revert the button state if the action can't be performed
            self.auto_var.set(not self.auto_var.get())
            return

        try:
            # Get the new desired state from this button's variable
            is_enabled_now = self.auto_var.get()
            print(f"Floating controls: Setting auto-translate to: {is_enabled_now}")

            # Set the variable in the main TranslationTab
            self.app.translation_tab.auto_translate_var.set(is_enabled_now)

            # Call the command associated with the main checkbutton in TranslationTab
            # This ensures saving the setting and updating status happens correctly.
            self.app.translation_tab.toggle_auto_translate()

        except Exception as e:
            print(f"Error invoking main auto-translate toggle: {e}")
            # Attempt to revert local state if invocation failed
            try:
                self.auto_var.set(not is_enabled_now)
            except: # Ignore secondary errors during revert
                pass


    def toggle_overlays(self):
        """Toggles the global overlay visibility via the OverlayManager."""
        if not hasattr(self.app, 'overlay_manager') or not self.app.overlay_manager:
            print("Error: Overlay manager not found.")
            self.overlay_var.set(not self.overlay_var.get())
            return

        try:
            new_state = self.overlay_var.get()
            print(f"Floating controls: Setting global overlays to: {new_state}")
            # Call the manager's method which handles saving and applying the state
            self.app.overlay_manager.set_global_overlays_enabled(new_state)
        except Exception as e:
            print(f"Error invoking overlay manager toggle: {e}")
            try:
                self.overlay_var.set(not new_state)
            except:
                pass


    def update_button_states(self):
        """Syncs button check states with the application state (e.g., on show)."""
        try:
            if hasattr(self.app, 'translation_tab') and self.app.translation_tab and self.auto_var:
                self.auto_var.set(self.app.translation_tab.is_auto_translate_enabled())
            if hasattr(self.app, 'overlay_manager') and self.app.overlay_manager and self.overlay_var:
                self.overlay_var.set(self.app.overlay_manager.global_overlays_enabled)
            # print("Floating controls states updated.") # Less verbose
        except tk.TclError:
            # Can happen if widgets are being destroyed during update
            print("Warning: TclError during floating controls state update (widgets closing?).")
        except Exception as e:
            print(f"Error updating floating control states: {e}")


    def add_tooltip(self, widget, text):
        """Simple tooltip implementation."""
        # Consider using a more robust library like `tkinter.tix` or `ttkthemes`' tooltips if needed
        Tooltip(widget, text)


# Simple Tooltip class (remains the same)
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
            try:
                self.widget.after_cancel(enter_id)
            except: # Ignore errors if widget/after cancelled elsewhere
                pass

        leave_id = self.leave_id
        self.leave_id = None
        if leave_id:
            try:
                self.widget.after_cancel(leave_id)
            except:
                pass

    def showtip(self):
        self.unschedule()
        if self.tipwindow or not self.text:
            return
        try:
            # Check if widget still exists
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
        except tk.TclError: # Handle cases where widget might be destroyed between checks
            self.tipwindow = None # Ensure tipwindow is None if creation failed
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
                pass # Window might already be destroyed

    def force_hide(self, event=None):
        self.hidetip() # Hide immediately on click

# --- END OF FILE ui/floating_controls.py ---