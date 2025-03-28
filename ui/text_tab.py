# --- START OF FILE ui/text_tab.py ---

import tkinter as tk
from tkinter import ttk
from ui.base import BaseTab
from ui.overlay_tab import SNIP_ROI_NAME
from utils.settings import set_setting # Import set_setting

class TextTab(BaseTab):
    """Tab for displaying extracted text and setting stability."""

    def setup_ui(self):
        # --- Stability Threshold Setting ---
        settings_frame = ttk.Frame(self.frame, padding=(0, 0, 0, 10))
        settings_frame.pack(fill=tk.X, pady=5)

        ttk.Label(settings_frame, text="Stability Threshold:").pack(side=tk.LEFT, padx=(0, 5))

        self.threshold_var = tk.IntVar(value=self.app.stable_threshold)
        self.threshold_label_var = tk.StringVar() # For displaying the value

        # Create the slider
        threshold_slider = ttk.Scale(
            settings_frame,
            from_=1,
            to=15, # Increased max range slightly
            orient=tk.HORIZONTAL,
            variable=self.threshold_var,
            length=120,
            command=self.on_threshold_change # Use command for live updates
        )
        threshold_slider.pack(side=tk.LEFT, padx=5)

        # Create the label to show the current value
        threshold_value_label = ttk.Label(
            settings_frame,
            textvariable=self.threshold_label_var,
            width=3, # Fixed width for the label
            anchor=tk.W
        )
        threshold_value_label.pack(side=tk.LEFT, padx=(0, 5))

        self._update_threshold_label(self.app.stable_threshold) # Set initial label value

        # --- Live Extracted Text Display ---
        text_frame = ttk.LabelFrame(self.frame, text="Live Extracted Text (per frame)", padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True, pady=0) # Removed top pady

        self.text_display = tk.Text(text_frame, wrap=tk.WORD, height=10, width=40, # Reduced height
                                    font=("Consolas", 9) ) # Monospace font?
        self.text_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame, command=self.text_display.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_display.config(yscrollcommand=scrollbar.set)
        self.text_display.config(state=tk.DISABLED) # Start disabled

    def _update_threshold_label(self, value):
        """Updates the label showing the threshold value."""
        try:
            int_value = int(float(value)) # Scale gives float, convert cleanly
            self.threshold_label_var.set(str(int_value))
        except (ValueError, tk.TclError):
            # Handle potential errors during update or widget destruction
            self.threshold_label_var.set("?")

    def on_threshold_change(self, value):
        """Callback when the stability threshold slider is moved."""
        try:
            new_threshold = int(float(value))
            # Update the app's threshold and save the setting
            self.app.update_stable_threshold(new_threshold)
            # Update the label next to the slider
            self._update_threshold_label(new_threshold)
        except ValueError:
            print("Invalid threshold value from slider")
        except Exception as e:
            print(f"Error updating threshold: {e}")

    def update_text(self, text_dict):
        """
        Update the text display with extracted text.

        Args:
            text_dict: Dictionary mapping ROI names to extracted text
        """
        # Prevent updates if widget is destroyed
        if not self.text_display.winfo_exists():
            return

        try:
            self.text_display.config(state=tk.NORMAL)
            self.text_display.delete(1.0, tk.END)

            # Maintain ROI order from app.rois
            for roi in self.app.rois:
                roi_name = roi.name
                # Skip special internal ROIs like snip if they appear
                if roi_name == SNIP_ROI_NAME: continue

                text = text_dict.get(roi_name, "") # Get text or default empty
                if text: # Only display if text was extracted
                    self.text_display.insert(tk.END, f"[{roi_name}]:\n{text}\n\n")
                else:
                    self.text_display.insert(tk.END, f"[{roi_name}]:\n-\n\n") # Placeholder

            self.text_display.config(state=tk.DISABLED)
        except tk.TclError:
            # Handle cases where the widget might be destroyed during update
            print("Warning: TextTab text_display widget likely destroyed during update.")
        except Exception as e:
            print(f"Error updating TextTab: {e}")


class StableTextTab(BaseTab):
    """Tab for displaying stable extracted text."""

    def setup_ui(self):
        stable_text_frame = ttk.LabelFrame(self.frame, text="Stable Text (Input for Translation)", padding="10")
        stable_text_frame.pack(fill=tk.BOTH, expand=True, pady=5) # Reduced pady

        self.stable_text_display = tk.Text(stable_text_frame, wrap=tk.WORD, height=10, width=40, # Reduced height
                                           font=("Consolas", 9))
        self.stable_text_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(stable_text_frame, command=self.stable_text_display.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.stable_text_display.config(yscrollcommand=scrollbar.set)
        self.stable_text_display.config(state=tk.DISABLED)

    def update_text(self, stable_texts):
        """
        Update the stable text display.

        Args:
            stable_texts: Dictionary mapping ROI names to stable text
        """
        # Prevent updates if widget is destroyed
        if not self.stable_text_display.winfo_exists():
            return

        try:
            self.stable_text_display.config(state=tk.NORMAL)
            self.stable_text_display.delete(1.0, tk.END)

            # Maintain ROI order from app.rois
            has_stable_text = False
            for roi in self.app.rois:
                roi_name = roi.name
                # Skip special internal ROIs like snip if they appear
                if roi_name == SNIP_ROI_NAME: continue

                text = stable_texts.get(roi_name, "")
                if text:
                    has_stable_text = True
                    self.stable_text_display.insert(tk.END, f"[{roi_name}]:\n{text}\n\n")
                # Optionally show placeholder even if no stable text for that ROI?
                # else:
                #     self.stable_text_display.insert(tk.END, f"[{roi_name}]:\n[No stable text]\n\n")

            if not has_stable_text:
                self.stable_text_display.insert(tk.END, "[Waiting for stable text...]")

            self.stable_text_display.config(state=tk.DISABLED)
        except tk.TclError:
            # Handle cases where the widget might be destroyed during update
            print("Warning: StableTextTab stable_text_display widget likely destroyed during update.")
        except Exception as e:
            print(f"Error updating StableTextTab: {e}")

# --- END OF FILE ui/text_tab.py ---