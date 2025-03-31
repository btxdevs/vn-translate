
import tkinter as tk
from tkinter import ttk
from ui.base import BaseTab
from ui.overlay_tab import SNIP_ROI_NAME
import time # Import time module

class TextTab(BaseTab):
    def setup_ui(self):
        # --- Rate Indicator ---
        rate_frame = ttk.Frame(self.frame)
        rate_frame.pack(fill=tk.X, pady=(0, 5))
        self.rate_label_var = tk.StringVar(value="Rate: N/A")
        ttk.Label(rate_frame, textvariable=self.rate_label_var, anchor=tk.E).pack(side=tk.RIGHT, padx=5)
        self.last_update_time = time.perf_counter()
        self.updates_since_last_calc = 0
        self.last_rate_calc_time = time.perf_counter()
        # --- End Rate Indicator ---

        settings_frame = ttk.Frame(self.frame, padding=(0, 0, 0, 10))
        settings_frame.pack(fill=tk.X, pady=5)
        ttk.Label(settings_frame, text="Stability Threshold:").pack(side=tk.LEFT, padx=(0, 5))
        self.threshold_var = tk.IntVar(value=self.app.stable_threshold)
        self.threshold_label_var = tk.StringVar()
        threshold_slider = ttk.Scale(
            settings_frame,
            from_=1,
            to=15,
            orient=tk.HORIZONTAL,
            variable=self.threshold_var,
            length=120,
            command=self.on_threshold_change
        )
        threshold_slider.pack(side=tk.LEFT, padx=5)
        threshold_value_label = ttk.Label(
            settings_frame,
            textvariable=self.threshold_label_var,
            width=3,
            anchor=tk.W
        )
        threshold_value_label.pack(side=tk.LEFT, padx=(0, 5))
        self._update_threshold_label(self.app.stable_threshold)

        text_frame = ttk.LabelFrame(self.frame, text="Live Extracted Text (per frame)", padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True, pady=0)
        self.text_display = tk.Text(text_frame, wrap=tk.WORD, height=10, width=40, font=("Consolas", 9))
        self.text_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(text_frame, command=self.text_display.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_display.config(yscrollcommand=scrollbar.set)
        self.text_display.config(state=tk.DISABLED)

        # Variable to store the last displayed text content
        self.last_displayed_text = None

    def _update_threshold_label(self, value):
        try:
            int_value = int(float(value))
            self.threshold_label_var.set(str(int_value))
        except (ValueError, tk.TclError):
            self.threshold_label_var.set("?")

    def on_threshold_change(self, value):
        try:
            new_threshold = int(float(value))
            self.app.update_stable_threshold(new_threshold)
            self._update_threshold_label(new_threshold)
        except ValueError:
            print("Invalid threshold value from slider")
        except Exception as e:
            print(f"Error updating threshold: {e}")

    def update_text(self, text_dict):
        if not self.text_display.winfo_exists():
            return

        # --- Update Rate Calculation ---
        current_time = time.perf_counter()
        self.updates_since_last_calc += 1
        time_since_last_calc = current_time - self.last_rate_calc_time
        if time_since_last_calc >= 1.0: # Update rate roughly every second
            rate = self.updates_since_last_calc / time_since_last_calc
            try:
                self.rate_label_var.set(f"Rate: {rate:.1f} FPS")
            except tk.TclError: pass # Ignore if widget destroyed
            self.updates_since_last_calc = 0
            self.last_rate_calc_time = current_time
        # --- End Update Rate Calculation ---

        # --- Construct new text content ---
        new_text_content_parts = []
        for roi in self.app.rois:
            roi_name = roi.name
            if roi_name == SNIP_ROI_NAME:
                continue
            text = text_dict.get(roi_name, "")
            if text:
                new_text_content_parts.append(f"[{roi_name}]:\n{text}\n\n")
            else:
                new_text_content_parts.append(f"[{roi_name}]:\n-\n\n")
        new_text_content = "".join(new_text_content_parts)
        # --- End Construct new text content ---

        # --- Conditional Update ---
        if new_text_content == self.last_displayed_text:
            # print("TextTab: Content unchanged, skipping update.") # Optional debug log
            return # Skip update if content is identical
        # --- End Conditional Update ---

        # --- Update Text Widget ---
        self.last_displayed_text = new_text_content # Store the new content
        try:
            self.text_display.config(state=tk.NORMAL)
            self.text_display.delete(1.0, tk.END)
            # Insert the pre-constructed string
            self.text_display.insert(tk.END, new_text_content)
            self.text_display.config(state=tk.DISABLED)
        except tk.TclError:
            print("Warning: TextTab text_display widget likely destroyed during update.")
            self.last_displayed_text = None # Reset cache if widget error occurs
        except Exception as e:
            print(f"Error updating TextTab: {e}")
            self.last_displayed_text = None # Reset cache on error
        # --- End Update Text Widget ---


class StableTextTab(BaseTab):
    def setup_ui(self):
        stable_text_frame = ttk.LabelFrame(self.frame, text="Stable Text (Input for Translation)", padding="10")
        stable_text_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.stable_text_display = tk.Text(stable_text_frame, wrap=tk.WORD, height=10, width=40, font=("Consolas", 9))
        self.stable_text_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(stable_text_frame, command=self.stable_text_display.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.stable_text_display.config(yscrollcommand=scrollbar.set)
        self.stable_text_display.config(state=tk.DISABLED)

    def update_text(self, stable_texts):
        if not self.stable_text_display.winfo_exists():
            return
        try:
            self.stable_text_display.config(state=tk.NORMAL)
            self.stable_text_display.delete(1.0, tk.END)
            has_stable_text = False
            for roi in self.app.rois:
                roi_name = roi.name
                if roi_name == SNIP_ROI_NAME:
                    continue
                text = stable_texts.get(roi_name, "")
                if text:
                    has_stable_text = True
                    self.stable_text_display.insert(tk.END, f"[{roi_name}]:\n{text}\n\n")
            if not has_stable_text:
                self.stable_text_display.insert(tk.END, "[Waiting for stable text...]")
            self.stable_text_display.config(state=tk.DISABLED)
        except tk.TclError:
            print("Warning: StableTextTab stable_text_display widget likely destroyed during update.")
        except Exception as e:
            print(f"Error updating StableTextTab: {e}")