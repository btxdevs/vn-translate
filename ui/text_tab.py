import tkinter as tk
from tkinter import ttk
from ui.base import BaseTab

class TextTab(BaseTab):
    """Tab for displaying extracted text."""

    def setup_ui(self):
        text_frame = ttk.LabelFrame(self.frame, text="Extracted Text", padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.text_display = tk.Text(text_frame, wrap=tk.WORD, height=15, width=40)
        self.text_display.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame, command=self.text_display.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_display.config(yscrollcommand=scrollbar.set)
        self.text_display.config(state=tk.DISABLED)

    def update_text(self, text_dict):
        """
        Update the text display with extracted text.

        Args:
            text_dict: Dictionary mapping ROI names to extracted text
        """
        self.text_display.config(state=tk.NORMAL)
        self.text_display.delete(1.0, tk.END)

        for roi_name, text in text_dict.items():
            self.text_display.insert(tk.END, f"[{roi_name}]:\n{text}\n\n")

        self.text_display.config(state=tk.DISABLED)

class StableTextTab(BaseTab):
    """Tab for displaying stable extracted text."""

    def setup_ui(self):
        stable_text_frame = ttk.LabelFrame(self.frame, text="Stable Extracted Text", padding="10")
        stable_text_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.stable_text_display = tk.Text(stable_text_frame, wrap=tk.WORD, height=15, width=40)
        self.stable_text_display.pack(fill=tk.BOTH, expand=True)

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

        for roi_name, text in stable_texts.items():
            if text:
                self.stable_text_display.insert(tk.END, f"[{roi_name}]:\n{text}\n\n")

        self.stable_text_display.config(state=tk.DISABLED)