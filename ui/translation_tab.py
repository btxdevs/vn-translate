# --- START OF FILE ui/translation_tab.py ---

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import copy
from ui.base import BaseTab
from utils.translation import translate_text, clear_all_cache, clear_current_game_cache, reset_context # Updated imports
from utils.config import save_translation_presets, load_translation_presets
from utils.settings import get_setting, set_setting, update_settings # Import settings functions

# Default presets configuration
DEFAULT_PRESETS = {
    "OpenAI (GPT-3.5)": {
        "api_url": "https://api.openai.com/v1/chat/completions", # Corrected endpoint
        "api_key": "",
        "model": "gpt-3.5-turbo",
        "system_prompt": (
            "You are a professional translator. Translate the following text from its source language to the target language. "
            "Return your answer in the following format:\n"
            "<|1|> translated text for segment 1\n"
            "<|2|> translated text for segment 2\n"
            "and so on. Provide only the tagged translated text lines, each preceded by its tag."
        ),
        "temperature": 0.3,
        "top_p": 1.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "max_tokens": 1000,
        "context_limit": 10
    },
    "OpenAI (GPT-4)": {
        "api_url": "https://api.openai.com/v1/chat/completions", # Corrected endpoint
        "api_key": "",
        "model": "gpt-4", # Or specific variants like gpt-4-turbo-preview
        "system_prompt": (
            "You are a professional translator. Translate the following text from its source language to the target language. "
            "Return your answer in the following format:\n"
            "<|1|> translated text for segment 1\n"
            "<|2|> translated text for segment 2\n"
            "and so on. Provide only the tagged translated text lines, each preceded by its tag."
        ),
        "temperature": 0.3,
        "top_p": 1.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "max_tokens": 1000,
        "context_limit": 10
    },
    "Claude": {
        "api_url": "https://api.anthropic.com/v1/messages", # Corrected endpoint
        "api_key": "", # Requires header x-api-key
        "model": "claude-3-haiku-20240307", # Or other Claude models
        "system_prompt": ( # Claude uses 'system' parameter, not message role
            "You are a translation assistant. Translate the following text and format your answer as follows:\n"
            "<|1|> translated text for segment 1\n"
            "<|2|> translated text for segment 2\n"
            "Only output the tagged lines."
        ),
        "temperature": 0.3,
        "top_p": 1.0, # Check if Claude supports top_p, might use top_k
        "max_tokens": 1000, # Claude uses max_tokens
        "context_limit": 10
        # Note: Claude API structure differs significantly from OpenAI.
        # utils.translation.py would need adaptation for non-OpenAI compatible APIs.
        # This preset might not work without modifications to the API call logic.
    },
    "Mistral": {
        "api_url": "https://api.mistral.ai/v1/chat/completions", # OpenAI compatible endpoint
        "api_key": "",
        "model": "mistral-medium-latest", # Or other Mistral models
        "system_prompt": (
            "You are a professional translator. Translate the following text accurately and return the output in this format:\n"
            "<|1|> translated text for segment 1\n"
            "<|2|> translated text for segment 2\n"
            "Only include the tagged lines."
        ),
        "temperature": 0.3,
        "top_p": 0.95, # Mistral supports top_p
        "max_tokens": 1000,
        "context_limit": 10
    }
    # Add Local LLM Example (using LM Studio / Ollama OpenAI compatible endpoint)
    ,"Local Model (LM Studio/Ollama)": {
        "api_url": "http://localhost:1234/v1/chat/completions", # Example LM Studio endpoint
        "api_key": "not-needed", # Usually not needed for local
        "model": "loaded-model-name", # Specify the model loaded in your local server
        "system_prompt": (
            "You are a helpful translation assistant. Translate the provided text segments into the target language. "
            "The input format uses tags like <|1|>, <|2|>, etc. Your response MUST strictly adhere to this format, "
            "reproducing the exact same tags for each corresponding translated segment. "
            "Output ONLY the tagged translated lines."
        ),
        "temperature": 0.5,
        "top_p": 1.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "max_tokens": 1500,
        "context_limit": 5
    }
}

class TranslationTab(BaseTab):
    """Tab for translation settings and results with improved preset management."""

    def setup_ui(self):
        # --- Load relevant settings ---
        self.target_language = get_setting("target_language", "en")
        self.additional_context = get_setting("additional_context", "")
        self.auto_translate_enabled = get_setting("auto_translate", False)
        last_preset_name = get_setting("last_preset_name")

        # --- Translation settings frame ---
        self.settings_frame = ttk.LabelFrame(self.frame, text="Translation Settings", padding="10")
        self.settings_frame.pack(fill=tk.X, pady=10)

        # --- Preset Management ---
        preset_frame = ttk.Frame(self.settings_frame)
        preset_frame.pack(fill=tk.X, pady=5)

        ttk.Label(preset_frame, text="Preset:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)

        # Load presets
        self.translation_presets = load_translation_presets()
        if not self.translation_presets:
            self.translation_presets = copy.deepcopy(DEFAULT_PRESETS)
            # Optionally save the defaults if they were missing
            # save_translation_presets(self.translation_presets)

        self.preset_names = sorted(list(self.translation_presets.keys())) # Sort names
        self.preset_combo = ttk.Combobox(preset_frame, values=self.preset_names, width=30, state="readonly") # Wider
        preset_index = -1
        if last_preset_name and last_preset_name in self.preset_names:
            try:
                preset_index = self.preset_names.index(last_preset_name)
            except ValueError:
                pass # Name not found
        if preset_index != -1:
            self.preset_combo.current(preset_index)
        elif self.preset_names:
            self.preset_combo.current(0) # Default to first if last not found

        self.preset_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        self.preset_combo.bind("<<ComboboxSelected>>", self.on_preset_selected)

        # Preset management buttons
        btn_frame = ttk.Frame(preset_frame)
        btn_frame.grid(row=0, column=2, padx=5, pady=5)

        self.save_preset_btn = ttk.Button(btn_frame, text="Save", command=self.save_preset)
        self.save_preset_btn.pack(side=tk.LEFT, padx=2)

        self.save_as_preset_btn = ttk.Button(btn_frame, text="Save As...", command=self.save_preset_as)
        self.save_as_preset_btn.pack(side=tk.LEFT, padx=2)

        self.delete_preset_btn = ttk.Button(btn_frame, text="Delete", command=self.delete_preset)
        self.delete_preset_btn.pack(side=tk.LEFT, padx=2)

        # Make preset combo column expandable
        preset_frame.columnconfigure(1, weight=1)

        # --- Notebook for settings ---
        self.settings_notebook = ttk.Notebook(self.settings_frame)
        self.settings_notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        # === Basic Settings Tab ===
        self.basic_frame = ttk.Frame(self.settings_notebook, padding=10)
        self.settings_notebook.add(self.basic_frame, text="General Settings") # Renamed tab

        # Target language (Loads from general settings)
        ttk.Label(self.basic_frame, text="Target Language:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.target_lang_entry = ttk.Entry(self.basic_frame, width=15) # Wider
        self.target_lang_entry.insert(0, self.target_language)
        self.target_lang_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        self.target_lang_entry.bind("<FocusOut>", self.save_basic_settings) # Save on leaving field
        self.target_lang_entry.bind("<Return>", self.save_basic_settings)   # Save on pressing Enter

        # Additional context (Loads from general settings)
        ttk.Label(self.basic_frame, text="Additional Context:", anchor=tk.NW).grid(row=1, column=0, sticky=tk.NW, padx=5, pady=5)
        self.additional_context_text = tk.Text(self.basic_frame, width=40, height=5, wrap=tk.WORD)
        self.additional_context_text.grid(row=1, column=1, sticky=tk.NSEW, padx=5, pady=5) # Expand fully
        scroll_ctx = ttk.Scrollbar(self.basic_frame, command=self.additional_context_text.yview)
        scroll_ctx.grid(row=1, column=2, sticky=tk.NS, pady=5)
        self.additional_context_text.config(yscrollcommand=scroll_ctx.set)
        self.additional_context_text.insert("1.0", self.additional_context)
        self.additional_context_text.bind("<FocusOut>", self.save_basic_settings) # Save on leaving field

        # Make context column expandable
        self.basic_frame.columnconfigure(1, weight=1)
        self.basic_frame.rowconfigure(1, weight=1) # Allow context text to expand vertically


        # === Preset Settings Tab ===
        self.preset_settings_frame = ttk.Frame(self.settings_notebook, padding=10)
        self.settings_notebook.add(self.preset_settings_frame, text="Preset Details") # Renamed tab

        # API Key (Part of Preset)
        ttk.Label(self.preset_settings_frame, text="API Key:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.api_key_entry = ttk.Entry(self.preset_settings_frame, width=40, show="*")
        self.api_key_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=5)

        # API URL (Part of Preset)
        ttk.Label(self.preset_settings_frame, text="API URL:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.api_url_entry = ttk.Entry(self.preset_settings_frame, width=40)
        self.api_url_entry.grid(row=1, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=5)

        # Model (Part of Preset)
        ttk.Label(self.preset_settings_frame, text="Model:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.model_entry = ttk.Entry(self.preset_settings_frame, width=40)
        self.model_entry.grid(row=2, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=5)

        # System prompt (Part of Preset)
        ttk.Label(self.preset_settings_frame, text="System Prompt:", anchor=tk.NW).grid(row=3, column=0, sticky=tk.NW, padx=5, pady=5)
        self.system_prompt_text = tk.Text(self.preset_settings_frame, width=50, height=6, wrap=tk.WORD)
        self.system_prompt_text.grid(row=3, column=1, sticky=tk.NSEW, padx=5, pady=5) # Expand
        scroll_sys = ttk.Scrollbar(self.preset_settings_frame, command=self.system_prompt_text.yview)
        scroll_sys.grid(row=3, column=2, sticky=tk.NS, pady=5)
        self.system_prompt_text.config(yscrollcommand=scroll_sys.set)

        # Context Limit (Part of Preset)
        ttk.Label(self.preset_settings_frame, text="Context Limit (History):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.context_limit_entry = ttk.Entry(self.preset_settings_frame, width=10)
        self.context_limit_entry.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)

        # --- Advanced Parameters Frame ---
        adv_param_frame = ttk.Frame(self.preset_settings_frame)
        adv_param_frame.grid(row=5, column=0, columnspan=3, sticky=tk.EW, pady=(10,0))

        # Temperature (Part of Preset)
        ttk.Label(adv_param_frame, text="Temp:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.temperature_entry = ttk.Entry(adv_param_frame, width=8)
        self.temperature_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        # Top P (Part of Preset)
        ttk.Label(adv_param_frame, text="Top P:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=2)
        self.top_p_entry = ttk.Entry(adv_param_frame, width=8)
        self.top_p_entry.grid(row=0, column=3, sticky=tk.W, padx=5, pady=2)

        # Frequency Penalty (Part of Preset)
        ttk.Label(adv_param_frame, text="Freq Pen:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.frequency_penalty_entry = ttk.Entry(adv_param_frame, width=8)
        self.frequency_penalty_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        # Presence Penalty (Part of Preset)
        ttk.Label(adv_param_frame, text="Pres Pen:").grid(row=1, column=2, sticky=tk.W, padx=5, pady=2)
        self.presence_penalty_entry = ttk.Entry(adv_param_frame, width=8)
        self.presence_penalty_entry.grid(row=1, column=3, sticky=tk.W, padx=5, pady=2)

        # Max Tokens (Part of Preset)
        ttk.Label(adv_param_frame, text="Max Tokens:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.max_tokens_entry = ttk.Entry(adv_param_frame, width=8)
        self.max_tokens_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        # Make columns expandable in preset settings frame
        self.preset_settings_frame.columnconfigure(1, weight=1)
        self.preset_settings_frame.rowconfigure(3, weight=1) # Allow system prompt to expand

        # Load initial preset data
        self.on_preset_selected() # Load data for the initially selected preset

        # === Action Buttons ===
        action_frame = ttk.Frame(self.settings_frame)
        action_frame.pack(fill=tk.X, pady=10)

        # --- Cache and Context Buttons ---
        cache_context_frame = ttk.Frame(action_frame)
        cache_context_frame.pack(side=tk.LEFT, padx=0)

        self.clear_current_cache_btn = ttk.Button(cache_context_frame, text="Clear Current Game Cache", command=self.clear_current_translation_cache)
        self.clear_current_cache_btn.pack(side=tk.TOP, padx=5, pady=2, anchor=tk.W)

        self.clear_all_cache_btn = ttk.Button(cache_context_frame, text="Clear All Cache", command=self.clear_all_translation_cache)
        self.clear_all_cache_btn.pack(side=tk.TOP, padx=5, pady=2, anchor=tk.W)

        self.reset_context_btn = ttk.Button(cache_context_frame, text="Reset Translation Context", command=self.reset_translation_context)
        self.reset_context_btn.pack(side=tk.TOP, padx=5, pady=(5,2), anchor=tk.W) # Add some top padding

        # --- Translate Button ---
        self.translate_btn = ttk.Button(action_frame, text="Translate Stable Text Now", command=self.perform_translation)
        self.translate_btn.pack(side=tk.RIGHT, padx=5, pady=5) # Add padding

        # === Auto Translation Option (Loads from general settings) ===
        auto_frame = ttk.Frame(self.settings_frame)
        auto_frame.pack(fill=tk.X, pady=5)

        self.auto_translate_var = tk.BooleanVar(value=self.auto_translate_enabled)
        self.auto_translate_check = ttk.Checkbutton(
            auto_frame,
            text="Auto-translate when stable text changes",
            variable=self.auto_translate_var,
            command=self.toggle_auto_translate # Save setting on change
        )
        self.auto_translate_check.pack(side=tk.LEFT, padx=5)

        # === Translation Output ===
        output_frame = ttk.LabelFrame(self.frame, text="Translated Text (Preview)", padding="10")
        output_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.translation_display = tk.Text(output_frame, wrap=tk.WORD, height=10, width=40) # Reduced height
        self.translation_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(output_frame, command=self.translation_display.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.translation_display.config(yscrollcommand=scrollbar.set)
        self.translation_display.config(state=tk.DISABLED)

    def save_basic_settings(self, event=None):
        """Save non-preset settings like target language and additional context."""
        new_target_lang = self.target_lang_entry.get().strip()
        new_additional_context = self.additional_context_text.get("1.0", tk.END).strip()

        # Use update_settings for efficiency
        settings_to_update = {}
        changed = False
        if new_target_lang != self.target_language:
            settings_to_update["target_language"] = new_target_lang
            self.target_language = new_target_lang
            changed = True
        if new_additional_context != self.additional_context:
            settings_to_update["additional_context"] = new_additional_context
            self.additional_context = new_additional_context
            changed = True

        if changed and settings_to_update:
            if update_settings(settings_to_update):
                print("General translation settings (lang/context) updated.")
                self.app.update_status("Target language/context saved.")
            else:
                messagebox.showerror("Error", "Failed to save general translation settings.")
        elif changed: # Should not happen if settings_to_update is empty but check anyway
            print("Logic error: Changed flag set but no settings to update.")


    def toggle_auto_translate(self):
        """Save the auto-translate setting."""
        self.auto_translate_enabled = self.auto_translate_var.get()
        if set_setting("auto_translate", self.auto_translate_enabled):
            status_msg = f"Auto-translate {'enabled' if self.auto_translate_enabled else 'disabled'}."
            print(status_msg)
            self.app.update_status(status_msg)
            # Sync with floating controls if they exist
            if self.app.floating_controls and self.app.floating_controls.winfo_exists():
                self.app.floating_controls.auto_var.set(self.auto_translate_enabled)
        else:
            messagebox.showerror("Error", "Failed to save auto-translate setting.")


    def is_auto_translate_enabled(self):
        """Check if auto-translation is enabled."""
        return self.auto_translate_var.get() # Use the variable directly

    def get_translation_config(self):
        """Get the current translation preset AND general settings."""
        preset_name = self.preset_combo.get()
        if not preset_name or preset_name not in self.translation_presets:
            messagebox.showerror("Error", "No valid translation preset selected.", parent=self.app.master)
            return None

        # Get preset values directly from the stored dictionary
        preset_config_base = self.translation_presets.get(preset_name)
        if not preset_config_base:
            messagebox.showerror("Error", f"Could not load preset data for '{preset_name}'.", parent=self.app.master)
            return None

        # --- Crucially, get API key from the UI entry, not the saved preset ---
        # This allows users to enter keys without saving them permanently in the preset file
        api_key_from_ui = self.api_key_entry.get().strip()

        # --- Get other preset values from UI (allowing unsaved changes for translation) ---
        try:
            preset_config_from_ui = {
                "api_key": api_key_from_ui, # Use UI key
                "api_url": self.api_url_entry.get().strip(),
                "model": self.model_entry.get().strip(),
                "system_prompt": self.system_prompt_text.get("1.0", tk.END).strip(),
                "temperature": float(self.temperature_entry.get().strip() or 0.3),
                "top_p": float(self.top_p_entry.get().strip() or 1.0),
                "frequency_penalty": float(self.frequency_penalty_entry.get().strip() or 0.0),
                "presence_penalty": float(self.presence_penalty_entry.get().strip() or 0.0),
                "max_tokens": int(self.max_tokens_entry.get().strip() or 1000),
                "context_limit": int(self.context_limit_entry.get().strip() or 10)
            }
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid number format in Preset Details: {e}", parent=self.app.master)
            return None


        # --- Get general settings from UI / saved state ---
        target_lang = self.target_lang_entry.get().strip()
        additional_ctx = self.additional_context_text.get("1.0", tk.END).strip()

        # --- Combine into a working configuration ---
        # Use the preset settings currently displayed in the UI
        working_config = preset_config_from_ui
        # Add the non-preset settings
        working_config["target_language"] = target_lang
        working_config["additional_context"] = additional_ctx

        # Validate required fields (URL and Model primarily)
        # API Key validity checked by API call itself
        if not working_config.get("api_url"):
            messagebox.showwarning("Warning", "API URL is missing in preset details.", parent=self.app.master)
            # return None # Allow proceeding maybe?
        if not working_config.get("model"):
            messagebox.showwarning("Warning", "Model name is missing in preset details.", parent=self.app.master)
            # return None

        return working_config


    def on_preset_selected(self, event=None):
        """Load the selected preset into the UI fields, BUT keep UI API key if already entered."""
        preset_name = self.preset_combo.get()
        if not preset_name or preset_name not in self.translation_presets:
            # Keep current UI values if selection is invalid
            print(f"Invalid preset selected: {preset_name}")
            return

        preset = self.translation_presets[preset_name]
        print(f"Loading preset '{preset_name}' into UI.")

        # --- Load preset values into UI ---
        # Preserve API Key if user has entered one, otherwise load from preset
        current_api_key = self.api_key_entry.get().strip()
        preset_api_key = preset.get("api_key", "")
        self.api_key_entry.delete(0, tk.END)
        self.api_key_entry.insert(0, current_api_key if current_api_key else preset_api_key)


        self.api_url_entry.delete(0, tk.END)
        self.api_url_entry.insert(0, preset.get("api_url", ""))

        self.model_entry.delete(0, tk.END)
        self.model_entry.insert(0, preset.get("model", ""))

        self.system_prompt_text.delete("1.0", tk.END)
        self.system_prompt_text.insert("1.0", preset.get("system_prompt", ""))

        self.context_limit_entry.delete(0, tk.END)
        self.context_limit_entry.insert(0, str(preset.get("context_limit", 10)))

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

        # --- Save the name of the selected preset ---
        set_setting("last_preset_name", preset_name)


    def get_current_preset_values_for_saving(self):
        """Get ONLY the preset-specific values from the UI fields for saving."""
        try:
            # Only include fields that belong IN the preset file
            preset_data = {
                "api_key": self.api_key_entry.get().strip(), # Save the key from UI to preset
                "api_url": self.api_url_entry.get().strip(),
                "model": self.model_entry.get().strip(),
                "system_prompt": self.system_prompt_text.get("1.0", tk.END).strip(),
                "temperature": float(self.temperature_entry.get().strip() or 0.3),
                "top_p": float(self.top_p_entry.get().strip() or 1.0),
                "frequency_penalty": float(self.frequency_penalty_entry.get().strip() or 0.0),
                "presence_penalty": float(self.presence_penalty_entry.get().strip() or 0.0),
                "max_tokens": int(self.max_tokens_entry.get().strip() or 1000),
                "context_limit": int(self.context_limit_entry.get().strip() or 10)
            }
            # Basic validation
            if not preset_data["api_url"] or not preset_data["model"]:
                # Don't prevent saving, but maybe warn?
                print("Warning: Saving preset with potentially empty API URL or Model.")
            return preset_data
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid number format in Preset Details: {e}", parent=self.app.master)
            return None
        except Exception as e:
            messagebox.showerror("Error", f"Could not read preset settings: {e}", parent=self.app.master)
            return None

    def save_preset(self):
        """Save the current UI settings (preset part) to the selected preset."""
        preset_name = self.preset_combo.get()
        if not preset_name:
            messagebox.showwarning("Warning", "No preset selected to save over.", parent=self.app.master)
            return

        preset_data = self.get_current_preset_values_for_saving()
        if preset_data is None:
            return # Error message already shown

        confirm = messagebox.askyesno("Confirm Save", f"Overwrite preset '{preset_name}' with current settings?", parent=self.app.master)
        if not confirm:
            return

        self.translation_presets[preset_name] = preset_data
        if save_translation_presets(self.translation_presets):
            messagebox.showinfo("Saved", f"Preset '{preset_name}' has been updated.", parent=self.app.master)
        else:
            # Error message shown by save_translation_presets
            pass


    def save_preset_as(self):
        """Save the current UI settings (preset part) as a new preset."""
        new_name = simpledialog.askstring("Save Preset As", "Enter a name for the new preset:", parent=self.app.master)
        if not new_name:
            return # User cancelled

        new_name = new_name.strip()
        if not new_name:
            messagebox.showwarning("Warning", "Preset name cannot be empty.", parent=self.app.master)
            return

        preset_data = self.get_current_preset_values_for_saving()
        if preset_data is None:
            return # Error message already shown

        if new_name in self.translation_presets:
            overwrite = messagebox.askyesno("Overwrite", f"Preset '{new_name}' already exists. Overwrite?", parent=self.app.master)
            if not overwrite:
                return

        self.translation_presets[new_name] = preset_data
        if save_translation_presets(self.translation_presets):
            # Update the combobox
            self.preset_names = sorted(list(self.translation_presets.keys()))
            self.preset_combo['values'] = self.preset_names
            self.preset_combo.set(new_name)
            # Save the new name as the last used
            set_setting("last_preset_name", new_name)
            messagebox.showinfo("Saved", f"Preset '{new_name}' has been saved.", parent=self.app.master)
        else:
            # Error message shown by save_translation_presets
            # Rollback the addition? Maybe not necessary if saving failed.
            if new_name in self.translation_presets:
                del self.translation_presets[new_name] # Clean up if it was added locally


    def delete_preset(self):
        """Delete the selected preset."""
        preset_name = self.preset_combo.get()
        if not preset_name:
            messagebox.showwarning("Warning", "No preset selected to delete.", parent=self.app.master)
            return

        # Prevent deleting the last preset? Optional.
        # if len(self.translation_presets) <= 1:
        #     messagebox.showwarning("Warning", "Cannot delete the last preset.")
        #     return

        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete preset '{preset_name}'?", parent=self.app.master)
        if not confirm:
            return

        if preset_name in self.translation_presets:
            original_data = self.translation_presets[preset_name] # Keep for potential rollback
            del self.translation_presets[preset_name]
            if save_translation_presets(self.translation_presets):
                # Update the combobox
                self.preset_names = sorted(list(self.translation_presets.keys()))
                self.preset_combo['values'] = self.preset_names
                new_selection = ""
                if self.preset_names:
                    new_selection = self.preset_names[0]
                    self.preset_combo.current(0)
                else:
                    self.preset_combo.set("") # Clear if no presets left
                # Update last used preset if the deleted one was selected
                if get_setting("last_preset_name") == preset_name:
                    set_setting("last_preset_name", new_selection)

                self.on_preset_selected() # Load the new selection's data (or clear UI if none)
                messagebox.showinfo("Deleted", f"Preset '{preset_name}' has been deleted.", parent=self.app.master)
            else:
                # Error message shown by save_translation_presets
                # Re-add the preset locally on failed save
                self.translation_presets[preset_name] = original_data
                messagebox.showerror("Error", "Failed to save presets after deletion. The preset was not deleted.", parent=self.app.master)


    def perform_translation(self):
        """Translate the stable text using the current settings."""
        # Get combined config (preset + general settings like lang, context)
        config = self.get_translation_config()
        if config is None:
            print("Translation cancelled due to configuration error.")
            self.app.update_status("Translation cancelled: Configuration error.")
            return # Error message already shown

        # --- Get the HWND for game-specific caching ---
        current_hwnd = self.app.selected_hwnd
        if not current_hwnd:
            messagebox.showwarning("Warning", "No game window selected. Cannot determine game for caching.", parent=self.app.master)
            self.app.update_status("Translation cancelled: No window selected.")
            return

        # Get text to translate (only non-empty stable texts)
        texts_to_translate = {name: text for name, text in self.app.stable_texts.items() if text and text.strip()}

        if not texts_to_translate:
            print("No stable text available to translate.")
            self.app.update_status("No stable text to translate.")
            # Clear previous translation display
            self.translation_display.config(state=tk.NORMAL)
            self.translation_display.delete(1.0, tk.END)
            self.translation_display.insert(tk.END, "[No stable text detected]")
            self.translation_display.config(state=tk.DISABLED)
            # Clear overlays
            if hasattr(self.app, 'overlay_manager'):
                self.app.overlay_manager.clear_all_overlays()
            return

        # Format text for the API (using original ROI names as keys for now)
        # utils.translation.preprocess_text_for_translation handles the <|n|> conversion
        aggregated_input_text = "\n".join([f"[{name}]: {text}" for name, text in texts_to_translate.items()])

        self.app.update_status("Translating...")
        # Show translating message in preview
        self.translation_display.config(state=tk.NORMAL)
        self.translation_display.delete(1.0, tk.END)
        self.translation_display.insert(tk.END, "Translating...\n")
        self.translation_display.config(state=tk.DISABLED)

        # Show translating message in overlays
        if hasattr(self.app, 'overlay_manager'):
            for roi_name in texts_to_translate:
                self.app.overlay_manager.update_overlay(roi_name, "...") # Indicate loading


        # --- Perform translation in a separate thread ---
        def translation_thread():
            try:
                # Call the translation utility function
                # It handles caching, context, API call, and parsing <|n|> output
                # It now returns a dictionary mapping the original ROI name to the translation
                translated_segments = translate_text(
                    aggregated_input_text=aggregated_input_text, # Text with "[ROI_Name]: content" format
                    hwnd=current_hwnd, # Pass HWND for caching
                    preset=config, # Pass the combined config from get_translation_config
                    target_language=config["target_language"],
                    additional_context=config["additional_context"],
                    context_limit=config.get("context_limit", 10) # Pass context limit
                )

                # --- Process results ---
                if "error" in translated_segments:
                    error_msg = translated_segments["error"]
                    print(f"Translation API Error: {error_msg}")
                    # Display error in preview (via main thread)
                    self.app.master.after_idle(lambda: self.update_translation_display_error(error_msg))
                    # Display error in one overlay? Or clear them?
                    if hasattr(self.app, 'overlay_manager'):
                        first_roi = next(iter(texts_to_translate), None)
                        if first_roi:
                            self.app.master.after_idle(lambda name=first_roi: self.app.overlay_manager.update_overlay(name, f"Error!"))
                            # Clear others maybe?
                            for r_name in texts_to_translate:
                                if r_name != first_roi:
                                    self.app.master.after_idle(lambda n=r_name: self.app.overlay_manager.update_overlay(n, ""))


                else:
                    print("Translation successful.")
                    # Prepare display text for the preview box
                    preview_lines = []
                    # Use app's ROI order for display consistency
                    for roi in self.app.rois:
                        roi_name = roi.name
                        original_text = self.app.stable_texts.get(roi_name, "") # Check original stable text
                        translated_text = translated_segments.get(roi_name) # Use ROI name as key

                        # Only show lines for ROIs that had text AND received a translation
                        if original_text.strip(): # Was there input for this ROI?
                            preview_lines.append(f"[{roi_name}]:")
                            preview_lines.append(translated_text if translated_text else "[Translation N/A]")
                            preview_lines.append("") # Add blank line

                    preview_text = "\n".join(preview_lines).strip() # Remove trailing newline

                    # Update UI (Preview and Overlays) from the main thread
                    self.app.master.after_idle(lambda seg=translated_segments, prev=preview_text: self.update_translation_results(seg, prev))

            except Exception as e:
                error_msg = f"Unexpected error during translation thread: {str(e)}"
                print(error_msg)
                import traceback
                traceback.print_exc()
                self.app.master.after_idle(lambda: self.update_translation_display_error(error_msg))
                # Clear overlays on unexpected error
                if hasattr(self.app, 'overlay_manager'):
                    self.app.master.after_idle(self.app.overlay_manager.clear_all_overlays)


        threading.Thread(target=translation_thread, daemon=True).start()

    def update_translation_results(self, translated_segments, preview_text):
        """Update the preview display and overlays with translation results. Runs in main thread."""
        self.app.update_status("Translation complete.")
        # Update preview text box
        self.translation_display.config(state=tk.NORMAL)
        self.translation_display.delete(1.0, tk.END)
        self.translation_display.insert(tk.END, preview_text if preview_text else "[No translation received]")
        self.translation_display.config(state=tk.DISABLED)

        # Update overlays
        if hasattr(self.app, 'overlay_manager'):
            self.app.overlay_manager.update_overlays(translated_segments)

        # Store last successful translation for potential re-translation/copy
        self.last_translation_result = translated_segments
        self.last_translation_input = self.app.stable_texts.copy() # Store the input that led to this


    def update_translation_display_error(self, error_message):
        """Update the preview display with an error message. Runs in main thread."""
        self.app.update_status(f"Translation Error: {error_message[:50]}...") # Show snippet in status
        self.translation_display.config(state=tk.NORMAL)
        self.translation_display.delete(1.0, tk.END)
        self.translation_display.insert(tk.END, f"Translation Error:\n\n{error_message}")
        self.translation_display.config(state=tk.DISABLED)
        self.last_translation_result = None # Clear last result on error
        self.last_translation_input = None

    def clear_all_translation_cache(self):
        """Clear ALL translation cache files and show confirmation."""
        if messagebox.askyesno("Confirm Clear All Cache", "Are you sure you want to delete ALL translation cache files?", parent=self.app.master):
            result = clear_all_cache()
            messagebox.showinfo("Cache Cleared", result, parent=self.app.master)
            self.app.update_status("All translation cache cleared.")

    def clear_current_translation_cache(self):
        """Clear the translation cache for the current game and show confirmation."""
        current_hwnd = self.app.selected_hwnd
        if not current_hwnd:
            messagebox.showwarning("Warning", "No game window selected. Cannot clear current game cache.", parent=self.app.master)
            return

        if messagebox.askyesno("Confirm Clear Current Cache", "Are you sure you want to delete the translation cache for the currently selected game?", parent=self.app.master):
            result = clear_current_game_cache(current_hwnd)
            messagebox.showinfo("Cache Cleared", result, parent=self.app.master)
            self.app.update_status("Current game translation cache cleared.")


    def reset_translation_context(self):
        """Reset the translation context history and show confirmation."""
        result = reset_context()
        messagebox.showinfo("Context Reset", result, parent=self.app.master)
        self.app.update_status("Translation context reset.")

# --- END OF FILE ui/translation_tab.py ---