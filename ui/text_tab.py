import tkinter as tk
from tkinter import ttk
from ui.base import BaseTab

class TextTab(BaseTab):
    """Tab for displaying extracted text."""

    def setup_ui(self):
        text_frame = ttk.LabelFrame(self.frame, text="Live Extracted Text (per frame)", padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True, pady=5) # Reduced pady

        self.text_display = tk.Text(text_frame, wrap=tk.WORD, height=10, width=40, # Reduced height
                                    font=("Consolas", 9) ) # Monospace font?
        self.text_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame, command=self.text_display.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_display.config(yscrollcommand=scrollbar.set)
        self.text_display.config(state=tk.DISABLED) # Start disabled

    def update_text(self, text_dict):
        """
        Update the text display with extracted text.

        Args:
            text_dict: Dictionary mapping ROI names to extracted text
        """
        self.text_display.config(state=tk.NORMAL)
        self.text_display.delete(1.0, tk.END)

        # Maintain ROI order from app.rois
        for roi in self.app.rois:
            roi_name = roi.name
            text = text_dict.get(roi_name, "") # Get text or default empty
            if text: # Only display if text was extracted
                self.text_display.insert(tk.END, f"[{roi_name}]:\n{text}\n\n")
            else:
                self.text_display.insert(tk.END, f"[{roi_name}]:\n-\n\n") # Placeholder


        self.text_display.config(state=tk.DISABLED)

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
        self.stable_text_display.config(state=tk.NORMAL)
        self.stable_text_display.delete(1.0, tk.END)

        # Maintain ROI order from app.rois
        has_stable_text = False
        for roi in self.app.rois:
            roi_name = roi.name
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