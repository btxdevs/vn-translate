import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import copy
from ui.base import BaseTab
from utils.translation import translate_text, clear_cache, reset_context
from utils.config import save_translation_presets, load_translation_presets

# Default presets configuration
DEFAULT_PRESETS = {
    "OpenAI (GPT-3.5)": {
        "api_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-3.5-turbo",
        "system_prompt": (
            "You are a professional translator. Translate the following text from its source language to the target language. "
            "Return your answer in the following format:\n"
            "<|1|> translated text for segment 1\n"
            "<|2|> translated text for segment 2\n"
            "and so on. Provide only the translated text lines, each preceded by its tag."
        ),
        "temperature": 0.3,
        "top_p": 1.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "max_tokens": 1000
    },
    "OpenAI (GPT-4)": {
        "api_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4",
        "system_prompt": (
            "You are a professional translator. Translate the following text from its source language to the target language. "
            "Return your answer in the following format:\n"
            "<|1|> translated text for segment 1\n"
            "<|2|> translated text for segment 2\n"
            "and so on. Provide only the translated text lines, each preceded by its tag."
        ),
        "temperature": 0.3,
        "top_p": 1.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "max_tokens": 1000
    },
    "Claude": {
        "api_url": "https://api.anthropic.com/v1",
        "api_key": "",
        "model": "claude-3-haiku-20240307",
        "system_prompt": (
            "You are a translation assistant. Translate the following text and format your answer as follows:\n"
            "<|1|> translated text for segment 1\n"
            "<|2|> translated text for segment 2\n"
            "Only output the tagged lines."
        ),
        "temperature": 0.3,
        "top_p": 1.0,
        "max_tokens": 1000
    },
    "Mistral": {
        "api_url": "https://api.mistral.ai/v1",
        "api_key": "",
        "model": "mistral-medium",
        "system_prompt": (
            "You are a professional translator. Translate the following text accurately and return the output in this format:\n"
            "<|1|> translated text for segment 1\n"
            "<|2|> translated text for segment 2\n"
            "Only include the tagged lines."
        ),
        "temperature": 0.3,
        "top_p": 0.95,
        "max_tokens": 1000
    }
}

class TranslationTab(BaseTab):
    """Tab for translation settings and results with improved preset management."""

    def setup_ui(self):
        # Translation settings frame
        self.settings_frame = ttk.LabelFrame(self.frame, text="Translation Settings", padding="10")
        self.settings_frame.pack(fill=tk.X, pady=10)

        # === Preset Management ===
        preset_frame = ttk.Frame(self.settings_frame)
        preset_frame.pack(fill=tk.X, pady=5)

        ttk.Label(preset_frame, text="Preset:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)

        # Load presets
        self.translation_presets = load_translation_presets()
        if not self.translation_presets:
            self.translation_presets = copy.deepcopy(DEFAULT_PRESETS)

        self.preset_names = list(self.translation_presets.keys())
        self.preset_combo = ttk.Combobox(preset_frame, values=self.preset_names, width=25)
        if self.preset_names:
            self.preset_combo.current(0)
        self.preset_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        self.preset_combo.bind("<<ComboboxSelected>>", self.on_preset_selected)

        # Preset management buttons
        btn_frame = ttk.Frame(preset_frame)
        btn_frame.grid(row=0, column=2, padx=5, pady=5)

        self.save_preset_btn = ttk.Button(btn_frame, text="Save", command=self.save_preset)
        self.save_preset_btn.pack(side=tk.LEFT, padx=2)

        self.save_as_preset_btn = ttk.Button(btn_frame, text="Save As", command=self.save_preset_as)
        self.save_as_preset_btn.pack(side=tk.LEFT, padx=2)

        self.delete_preset_btn = ttk.Button(btn_frame, text="Delete", command=self.delete_preset)
        self.delete_preset_btn.pack(side=tk.LEFT, padx=2)

        # Notebook for settings
        self.settings_notebook = ttk.Notebook(self.settings_frame)
        self.settings_notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        # === Basic Settings Tab ===
        self.basic_frame = ttk.Frame(self.settings_notebook, padding=10)
        self.settings_notebook.add(self.basic_frame, text="Basic Settings")

        # Target language
        ttk.Label(self.basic_frame, text="Target Language:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.target_lang_entry = ttk.Entry(self.basic_frame, width=10)
        self.target_lang_entry.insert(0, "en")
        self.target_lang_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)

        # API Key
        ttk.Label(self.basic_frame, text="API Key:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.api_key_entry = ttk.Entry(self.basic_frame, width=40, show="*")
        self.api_key_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        # API URL
        ttk.Label(self.basic_frame, text="API URL:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.api_url_entry = ttk.Entry(self.basic_frame, width=40)
        self.api_url_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

        # Model
        ttk.Label(self.basic_frame, text="Model:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.model_entry = ttk.Entry(self.basic_frame, width=40)
        self.model_entry.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)

        # Additional context
        ttk.Label(self.basic_frame, text="Additional Context:").grid(row=4, column=0, sticky=tk.NW, padx=5, pady=5)
        self.additional_context_text = tk.Text(self.basic_frame, width=40, height=5, wrap=tk.WORD)
        self.additional_context_text.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
        scroll_ctx = ttk.Scrollbar(self.basic_frame, command=self.additional_context_text.yview)
        scroll_ctx.grid(row=4, column=2, sticky=tk.NS, pady=5)
        self.additional_context_text.config(yscrollcommand=scroll_ctx.set)

        # === Advanced Settings Tab ===
        self.advanced_frame = ttk.Frame(self.settings_notebook, padding=10)
        self.settings_notebook.add(self.advanced_frame, text="Advanced Settings")

        # Context Limit
        ttk.Label(self.advanced_frame, text="Context Limit:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        self.context_limit_entry = ttk.Entry(self.advanced_frame, width=10)
        self.context_limit_entry.grid(row=6, column=1, sticky=tk.W, padx=5, pady=5)
        self.context_limit_entry.insert(0, str(10))  # Set default value

        # System prompt
        ttk.Label(self.advanced_frame, text="System Prompt:").grid(row=0, column=0, sticky=tk.NW, padx=5, pady=5)
        self.system_prompt_text = tk.Text(self.advanced_frame, width=50, height=6, wrap=tk.WORD)
        self.system_prompt_text.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        scroll_sys = ttk.Scrollbar(self.advanced_frame, command=self.system_prompt_text.yview)
        scroll_sys.grid(row=0, column=2, sticky=tk.NS, pady=5)
        self.system_prompt_text.config(yscrollcommand=scroll_sys.set)

        # Temperature
        ttk.Label(self.advanced_frame, text="Temperature:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.temperature_entry = ttk.Entry(self.advanced_frame, width=10)
        self.temperature_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        # Top P
        ttk.Label(self.advanced_frame, text="Top P:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.top_p_entry = ttk.Entry(self.advanced_frame, width=10)
        self.top_p_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

        # Frequency Penalty
        ttk.Label(self.advanced_frame, text="Frequency Penalty:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.frequency_penalty_entry = ttk.Entry(self.advanced_frame, width=10)
        self.frequency_penalty_entry.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)

        # Presence Penalty
        ttk.Label(self.advanced_frame, text="Presence Penalty:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.presence_penalty_entry = ttk.Entry(self.advanced_frame, width=10)
        self.presence_penalty_entry.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)

        # Max Tokens
        ttk.Label(self.advanced_frame, text="Max Tokens:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.max_tokens_entry = ttk.Entry(self.advanced_frame, width=10)
        self.max_tokens_entry.grid(row=5, column=1, sticky=tk.W, padx=5, pady=5)

        # Load initial preset
        self.on_preset_selected()

        # === Action Buttons ===
        action_frame = ttk.Frame(self.settings_frame)
        action_frame.pack(fill=tk.X, pady=10)

        self.clear_cache_btn = ttk.Button(action_frame, text="Clear Translation Cache", command=clear_cache)
        self.clear_cache_btn.pack(side=tk.LEFT, padx=5)

        self.reset_context_btn = ttk.Button(action_frame, text="Reset Translation Context", command=reset_context)
        self.reset_context_btn.pack(side=tk.LEFT, padx=5)

        self.translate_btn = ttk.Button(action_frame, text="Translate Stable Text", command=self.perform_translation)
        self.translate_btn.pack(side=tk.RIGHT, padx=5)

        # === Auto Translation Option ===
        auto_frame = ttk.Frame(self.settings_frame)
        auto_frame.pack(fill=tk.X, pady=5)

        self.auto_translate_var = tk.BooleanVar(value=False)
        self.auto_translate_check = ttk.Checkbutton(
            auto_frame,
            text="Auto-translate when stable text changes",
            variable=self.auto_translate_var
        )
        self.auto_translate_check.pack(side=tk.LEFT, padx=5)

        # === Translation Output ===
        output_frame = ttk.LabelFrame(self.frame, text="Translated Text", padding="10")
        output_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.translation_display = tk.Text(output_frame, wrap=tk.WORD, height=15, width=40)
        self.translation_display.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(output_frame, command=self.translation_display.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.translation_display.config(yscrollcommand=scrollbar.set)
        self.translation_display.config(state=tk.DISABLED)


    def is_auto_translate_enabled(self):
        """Check if auto-translation is enabled."""
        return self.auto_translate_var.get()

    def get_translation_preset(self):
        """Get the current translation preset and settings."""
        preset = self.get_current_preset_values()
        if preset is None:
            return None

        return {
            "preset": preset,
            "target_language": self.target_lang_entry.get().strip(),
            "additional_context": self.additional_context_text.get("1.0", tk.END).strip()
        }

    def on_preset_selected(self, event=None):
        """Load the selected preset into the UI fields."""
        preset_name = self.preset_combo.get()
        if not preset_name or preset_name not in self.translation_presets:
            return

        preset = self.translation_presets[preset_name]

        # Basic settings
        self.api_key_entry.delete(0, tk.END)
        self.api_key_entry.insert(0, preset.get("api_key", ""))

        self.api_url_entry.delete(0, tk.END)
        self.api_url_entry.insert(0, preset.get("api_url", ""))

        self.model_entry.delete(0, tk.END)
        self.model_entry.insert(0, preset.get("model", ""))

        # Advanced settings
        self.system_prompt_text.delete("1.0", tk.END)
        self.system_prompt_text.insert("1.0", preset.get("system_prompt", ""))

        self.temperature_entry.delete(0, tk.END)
        self.temperature_entry.insert(0, str(preset.get("temperature", 0.3)))

        self.top_p_entry.delete(0, tk.END)
        self.top_p_entry.insert(0, str(preset.get("top_p", 1.0)))

        self.frequency_penalty_entry.delete(0, tk.END)
        self.frequency_penalty_entry.insert(0, str(preset.get("frequency_penalty", 0.0)))

        self.presence_penalty_entry.delete(0, tk.END)
        self.presence_penalty_entry.insert(0, str(preset.get("presence_penalty", 0.0)))

        self.max_tokens_entry.delete(0, tk.END)
        self.max_tokens_entry.insert(0, str(preset.get("max_tokens", 1000)))

    def get_current_preset_values(self):
        """Get all values from the UI fields as a preset configuration."""
        try:
            preset = {
                "api_key": self.api_key_entry.get().strip(),
                "api_url": self.api_url_entry.get().strip(),
                "model": self.model_entry.get().strip(),
                "system_prompt": self.system_prompt_text.get("1.0", tk.END).strip(),
                "temperature": float(self.temperature_entry.get().strip() or 0.3),
                "top_p": float(self.top_p_entry.get().strip() or 1.0),
                "frequency_penalty": float(self.frequency_penalty_entry.get().strip() or 0.0),
                "presence_penalty": float(self.presence_penalty_entry.get().strip() or 0.0),
                "max_tokens": int(self.max_tokens_entry.get().strip() or 1000),
                "context_limit": int(self.context_limit_entry.get().strip() or 10)  # Add this line
            }
            return preset
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid number format: {e}")
            return None

    def save_preset(self):
        """Save the current settings to the selected preset."""
        preset_name = self.preset_combo.get()
        if not preset_name:
            messagebox.showwarning("Warning", "No preset selected.")
            return

        preset = self.get_current_preset_values()
        if preset is None:
            return

        self.translation_presets[preset_name] = preset
        if save_translation_presets(self.translation_presets):
            messagebox.showinfo("Saved", f"Preset '{preset_name}' has been updated.")
        else:
            messagebox.showerror("Error", "Failed to save presets.")

    def save_preset_as(self):
        """Save the current settings as a new preset."""
        new_name = simpledialog.askstring("Save Preset As", "Enter a name for the new preset:")
        if not new_name:
            return

        if new_name in self.translation_presets:
            overwrite = messagebox.askyesno("Overwrite", f"Preset '{new_name}' already exists. Overwrite?")
            if not overwrite:
                return

        preset = self.get_current_preset_values()
        if preset is None:
            return

        self.translation_presets[new_name] = preset
        if save_translation_presets(self.translation_presets):
            # Update the combobox
            self.preset_names = list(self.translation_presets.keys())
            self.preset_combo['values'] = self.preset_names
            self.preset_combo.set(new_name)
            messagebox.showinfo("Saved", f"Preset '{new_name}' has been saved.")
        else:
            messagebox.showerror("Error", "Failed to save presets.")

    def delete_preset(self):
        """Delete the selected preset."""
        preset_name = self.preset_combo.get()
        if not preset_name:
            messagebox.showwarning("Warning", "No preset selected.")
            return

        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete preset '{preset_name}'?")
        if not confirm:
            return

        if preset_name in self.translation_presets:
            del self.translation_presets[preset_name]
            if save_translation_presets(self.translation_presets):
                # Update the combobox
                self.preset_names = list(self.translation_presets.keys())
                self.preset_combo['values'] = self.preset_names
                if self.preset_names:
                    self.preset_combo.current(0)
                    self.on_preset_selected()
                messagebox.showinfo("Deleted", f"Preset '{preset_name}' has been deleted.")
            else:
                messagebox.showerror("Error", "Failed to save presets after deletion.")

    def perform_translation(self):
        """Translate the stable text using the current settings."""
        # Get text to translate
        aggregated_lines = []
        translation_mapping = {}  # Maps translation indices to ROI indices
        translation_idx = 1

        for idx, roi in enumerate(self.app.rois):
            text = self.app.stable_texts.get(roi.name, "").strip()
            if text:  # Only include non-empty texts
                tag = str(translation_idx)
                aggregated_lines.append(f"[{roi.name}]: {text}")
                translation_mapping[translation_idx] = idx
                translation_idx += 1

        aggregated_text = "\n".join(aggregated_lines)

        # Exit quietly if there's nothing to translate
        if not aggregated_text.strip():
            return

        # Get translation settings
        preset = self.get_current_preset_values()
        if preset is None:
            return

        target_lang = self.target_lang_entry.get().strip()
        additional_context = self.additional_context_text.get("1.0", tk.END).strip()

        # Show translating message
        self.translation_display.config(state=tk.NORMAL)
        self.translation_display.delete(1.0, tk.END)
        self.translation_display.insert(tk.END, "Translating...\n")
        self.translation_display.config(state=tk.DISABLED)

        # Perform translation in a separate thread
        def translation_thread():
            try:
                segments = translate_text(
                    aggregated_text,
                    preset=preset,
                    target_language=target_lang,
                    additional_context=additional_context
                )

                # Process results
                preview_lines = [""] * len(self.app.rois)  # Initialize with empty strings

                if "error" in segments:
                    preview_lines[0] = segments["error"]  # Show error in the first position
                else:
                    for trans_idx, roi_idx in translation_mapping.items():
                        tag = str(trans_idx)
                        segment_text = segments.get(tag, "[No translation]")
                        preview_lines[roi_idx] = segment_text

                preview = "\n".join(preview_lines)

                # Update UI
                self.translation_display.config(state=tk.NORMAL)
                self.translation_display.delete(1.0, tk.END)
                self.translation_display.insert(tk.END, preview)
                self.translation_display.config(state=tk.DISABLED)
            except Exception as e:
                self.translation_display.config(state=tk.NORMAL)
                self.translation_display.delete(1.0, tk.END)
                self.translation_display.insert(tk.END, f"Translation error: {str(e)}")
                self.translation_display.config(state=tk.DISABLED)

        threading.Thread(target=translation_thread, daemon=True).start()