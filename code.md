Okay, I will refactor the code to pass the `stable_texts` dictionary directly to the translation function, ensuring each ROI's text is treated as a distinct segment. This involves modifying `ui/translation_tab.py` and `utils/translation.py`. `app.py` doesn't require changes for *this specific* request, but I'll include it as requested.

--- START OF FILE translation_tab.py ---
```python
# --- START OF FILE ui/translation_tab.py ---

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import copy
from ui.base import BaseTab
from utils.translation import translate_text, clear_all_cache, clear_current_game_cache, reset_context # Updated imports
from utils.config import save_translation_presets, load_translation_presets, _get_game_hash # Import _get_game_hash
from utils.settings import get_setting, set_setting, update_settings # Import settings functions

# Default presets configuration (REMOVING system_prompt from UI defaults)
# NOTE: Existing saved presets might still contain 'system_prompt',
# but it won't be used by the UI or passed explicitly to translate_text anymore.
DEFAULT_PRESETS = {
    "OpenAI (GPT-3.5)": {
        "api_url": "https://api.openai.com/v1/chat/completions",
        "api_key": "",
        "model": "gpt-3.5-turbo",
        # "system_prompt": "...", # REMOVED FROM HERE
        "temperature": 0.3,
        "top_p": 1.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "max_tokens": 1000,
        "context_limit": 10
    },
    "OpenAI (GPT-4)": {
        "api_url": "https://api.openai.com/v1/chat/completions",
        "api_key": "",
        "model": "gpt-4",
        # "system_prompt": "...", # REMOVED FROM HERE
        "temperature": 0.3,
        "top_p": 1.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "max_tokens": 1000,
        "context_limit": 10
    },
    "Claude": {
        "api_url": "https://api.anthropic.com/v1/messages",
        "api_key": "",
        "model": "claude-3-haiku-20240307",
        # "system_prompt": "...", # REMOVED FROM HERE
        "temperature": 0.3,
        "top_p": 1.0,
        "max_tokens": 1000,
        "context_limit": 10
    },
    "Mistral": {
        "api_url": "https://api.mistral.ai/v1/chat/completions",
        "api_key": "",
        "model": "mistral-medium-latest",
        # "system_prompt": "...", # REMOVED FROM HERE
        "temperature": 0.3,
        "top_p": 0.95,
        "max_tokens": 1000,
        "context_limit": 10
    }
    ,"Local Model (LM Studio/Ollama)": {
        "api_url": "http://localhost:1234/v1/chat/completions",
        "api_key": "not-needed",
        "model": "loaded-model-name",
        # "system_prompt": "...", # REMOVED FROM HERE
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

        # Additional context (Now game-specific, loaded dynamically)
        ttk.Label(self.basic_frame, text="Additional Context (Game Specific):", anchor=tk.NW).grid(row=1, column=0, sticky=tk.NW, padx=5, pady=5)
        self.additional_context_text = tk.Text(self.basic_frame, width=40, height=5, wrap=tk.WORD)
        self.additional_context_text.grid(row=1, column=1, sticky=tk.NSEW, padx=5, pady=5) # Expand fully
        scroll_ctx = ttk.Scrollbar(self.basic_frame, command=self.additional_context_text.yview)
        scroll_ctx.grid(row=1, column=2, sticky=tk.NS, pady=5)
        self.additional_context_text.config(yscrollcommand=scroll_ctx.set)
        # Bind to game-specific save function
        self.additional_context_text.bind("<FocusOut>", self.save_context_for_current_game)
        # Use Shift+Return to insert newline, regular Return to save
        self.additional_context_text.bind("<Return>", self.save_context_for_current_game)
        self.additional_context_text.bind("<Shift-Return>", lambda e: self.additional_context_text.insert(tk.INSERT, '\n'))

        # Make context column expandable
        self.basic_frame.columnconfigure(1, weight=1)
        self.basic_frame.rowconfigure(1, weight=1) # Allow context text to expand vertically


        # === Preset Settings Tab ===
        self.preset_settings_frame = ttk.Frame(self.settings_notebook, padding=10)
        self.settings_notebook.add(self.preset_settings_frame, text="Preset Details") # Renamed tab

        # Current row index
        row_num = 0

        # API Key (Part of Preset)
        ttk.Label(self.preset_settings_frame, text="API Key:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=5)
        self.api_key_entry = ttk.Entry(self.preset_settings_frame, width=40, show="*")
        self.api_key_entry.grid(row=row_num, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        row_num += 1

        # API URL (Part of Preset)
        ttk.Label(self.preset_settings_frame, text="API URL:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=5)
        self.api_url_entry = ttk.Entry(self.preset_settings_frame, width=40)
        self.api_url_entry.grid(row=row_num, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        row_num += 1

        # Model (Part of Preset)
        ttk.Label(self.preset_settings_frame, text="Model:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=5)
        self.model_entry = ttk.Entry(self.preset_settings_frame, width=40)
        self.model_entry.grid(row=row_num, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        row_num += 1

        # System prompt REMOVED from UI
        # ttk.Label(self.preset_settings_frame, text="System Prompt:", anchor=tk.NW).grid(row=row_num, column=0, sticky=tk.NW, padx=5, pady=5)
        # self.system_prompt_text = tk.Text(self.preset_settings_frame, width=50, height=6, wrap=tk.WORD)
        # self.system_prompt_text.grid(row=row_num, column=1, sticky=tk.NSEW, padx=5, pady=5)
        # scroll_sys = ttk.Scrollbar(self.preset_settings_frame, command=self.system_prompt_text.yview)
        # scroll_sys.grid(row=row_num, column=2, sticky=tk.NS, pady=5)
        # self.system_prompt_text.config(yscrollcommand=scroll_sys.set)
        # row_num += 1 # Increment row if prompt was present

        # Context Limit (Part of Preset)
        ttk.Label(self.preset_settings_frame, text="Context Limit (History):").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=5)
        self.context_limit_entry = ttk.Entry(self.preset_settings_frame, width=10)
        self.context_limit_entry.grid(row=row_num, column=1, sticky=tk.W, padx=5, pady=5)
        row_num += 1

        # --- Advanced Parameters Frame ---
        adv_param_frame = ttk.Frame(self.preset_settings_frame)
        adv_param_frame.grid(row=row_num, column=0, columnspan=3, sticky=tk.EW, pady=(10,0))
        row_num += 1 # Increment row after placing the frame

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
        # self.preset_settings_frame.rowconfigure(3, weight=1) # Row 3 was system prompt, remove if not needed

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

        self.reset_context_btn = ttk.Button(cache_context_frame, text="Reset Translation Context", command=self.reset_translation_context) # Command updated below
        self.reset_context_btn.pack(side=tk.TOP, padx=5, pady=(5,2), anchor=tk.W) # Add some top padding

        # --- Translate Buttons (Grouped) ---
        translate_btn_frame = ttk.Frame(action_frame)
        translate_btn_frame.pack(side=tk.RIGHT, padx=5, pady=5)

        self.translate_btn = ttk.Button(translate_btn_frame, text="Translate", command=self.perform_translation)
        self.translate_btn.pack(side=tk.LEFT, padx=(0, 2)) # Normal translate

        self.force_translate_btn = ttk.Button(translate_btn_frame, text="Force Retranslate", command=self.perform_force_translation)
        self.force_translate_btn.pack(side=tk.LEFT, padx=(2, 0)) # Force retranslate


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

    def load_context_for_game(self, context_text):
        """Loads the game-specific context into the text widget."""
        try:
            if not self.additional_context_text.winfo_exists(): return
            self.additional_context_text.config(state=tk.NORMAL)
            self.additional_context_text.delete("1.0", tk.END)
            if context_text: self.additional_context_text.insert("1.0", context_text)
        except tk.TclError: print("Error updating context text widget (might be destroyed).")
        except Exception as e: print(f"Unexpected error loading context: {e}")

    def save_context_for_current_game(self, event=None):
        """Save the content of the context text widget for the current game."""
        if event and event.keysym == 'Return' and not (event.state & 0x0001): pass
        elif event and event.keysym == 'Return': return "break"
        current_hwnd = self.app.selected_hwnd
        if not current_hwnd: return
        game_hash = _get_game_hash(current_hwnd)
        if not game_hash: print("Cannot save context: Could not get game hash."); return
        try:
            if not self.additional_context_text.winfo_exists(): return
            new_context = self.additional_context_text.get("1.0", tk.END).strip()
            all_game_contexts = get_setting("game_specific_context", {})
            if all_game_contexts.get(game_hash) != new_context:
                all_game_contexts[game_hash] = new_context
                if update_settings({"game_specific_context": all_game_contexts}):
                    print(f"Game-specific context saved for hash {game_hash[:8]}...")
                    self.app.update_status("Game context saved.")
                else: messagebox.showerror("Error", "Failed to save game-specific context.")
        except tk.TclError: print("Error accessing context text widget (might be destroyed).")
        except Exception as e: print(f"Error saving game context: {e}"); messagebox.showerror("Error", f"Failed to save game context: {e}")
        if event and event.keysym == 'Return': return "break"

    def save_basic_settings(self, event=None):
        """Save non-preset, non-game-specific settings like target language."""
        new_target_lang = self.target_lang_entry.get().strip()
        settings_to_update = {}
        changed = False
        if new_target_lang != self.target_language:
            settings_to_update["target_language"] = new_target_lang
            self.target_language = new_target_lang
            changed = True
        if changed and settings_to_update:
            if update_settings(settings_to_update):
                print("General translation settings (language) updated.")
                self.app.update_status("Target language saved.")
            else: messagebox.showerror("Error", "Failed to save target language setting.")

    def toggle_auto_translate(self):
        """Save the auto-translate setting."""
        self.auto_translate_enabled = self.auto_translate_var.get()
        if set_setting("auto_translate", self.auto_translate_enabled):
            status_msg = f"Auto-translate {'enabled' if self.auto_translate_enabled else 'disabled'}."
            print(status_msg)
            self.app.update_status(status_msg)
            if self.app.floating_controls and self.app.floating_controls.winfo_exists():
                self.app.floating_controls.auto_var.set(self.auto_translate_enabled)
        else: messagebox.showerror("Error", "Failed to save auto-translate setting.")

    def is_auto_translate_enabled(self):
        """Check if auto-translation is enabled."""
        return self.auto_translate_var.get()

    def get_translation_config(self):
        """Get the current translation preset AND general settings (NO system prompt from UI)."""
        preset_name = self.preset_combo.get()
        if not preset_name or preset_name not in self.translation_presets:
            messagebox.showerror("Error", "No valid translation preset selected.", parent=self.app.master)
            return None

        preset_config_base = self.translation_presets.get(preset_name)
        if not preset_config_base:
            messagebox.showerror("Error", f"Could not load preset data for '{preset_name}'.", parent=self.app.master)
            return None

        api_key_from_ui = self.api_key_entry.get().strip()

        try:
            preset_config_from_ui = {
                "api_key": api_key_from_ui,
                "api_url": self.api_url_entry.get().strip(),
                "model": self.model_entry.get().strip(),
                # "system_prompt": self.system_prompt_text.get("1.0", tk.END).strip(), # REMOVED
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
        except tk.TclError:
            messagebox.showerror("Error", "UI elements missing. Cannot read preset details.", parent=self.app.master)
            return None

        target_lang = self.target_lang_entry.get().strip()
        try:
            additional_ctx = self.additional_context_text.get("1.0", tk.END).strip()
        except tk.TclError: additional_ctx = ""

        working_config = preset_config_from_ui
        working_config["target_language"] = target_lang
        working_config["additional_context"] = additional_ctx

        if not working_config.get("api_url"):
            messagebox.showwarning("Warning", "API URL is missing in preset details.", parent=self.app.master)
        if not working_config.get("model"):
            messagebox.showwarning("Warning", "Model name is missing in preset details.", parent=self.app.master)

        return working_config

    def on_preset_selected(self, event=None):
        """Load the selected preset into the UI fields (excluding system prompt)."""
        preset_name = self.preset_combo.get()
        if not preset_name or preset_name not in self.translation_presets:
            print(f"Invalid preset selected: {preset_name}")
            return

        preset = self.translation_presets[preset_name]
        print(f"Loading preset '{preset_name}' into UI.")

        try:
            preset_api_key = preset.get("api_key", "")
            self.api_key_entry.delete(0, tk.END)
            self.api_key_entry.insert(0, preset_api_key)

            self.api_url_entry.delete(0, tk.END)
            self.api_url_entry.insert(0, preset.get("api_url", ""))

            self.model_entry.delete(0, tk.END)
            self.model_entry.insert(0, preset.get("model", ""))

            # self.system_prompt_text.delete("1.0", tk.END) # REMOVED
            # self.system_prompt_text.insert("1.0", preset.get("system_prompt", "")) # REMOVED

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

            set_setting("last_preset_name", preset_name)
        except tk.TclError:
            print("Error updating preset UI elements (might be destroyed).")

    def get_current_preset_values_for_saving(self):
        """Get ONLY the preset-specific values from the UI fields for saving (NO system prompt)."""
        try:
            preset_data = {
                "api_key": self.api_key_entry.get().strip(),
                "api_url": self.api_url_entry.get().strip(),
                "model": self.model_entry.get().strip(),
                # "system_prompt": self.system_prompt_text.get("1.0", tk.END).strip(), # REMOVED
                "temperature": float(self.temperature_entry.get().strip() or 0.3),
                "top_p": float(self.top_p_entry.get().strip() or 1.0),
                "frequency_penalty": float(self.frequency_penalty_entry.get().strip() or 0.0),
                "presence_penalty": float(self.presence_penalty_entry.get().strip() or 0.0),
                "max_tokens": int(self.max_tokens_entry.get().strip() or 1000),
                "context_limit": int(self.context_limit_entry.get().strip() or 10)
            }
            if not preset_data["api_url"] or not preset_data["model"]:
                print("Warning: Saving preset with potentially empty API URL or Model.")
            return preset_data
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid number format in Preset Details: {e}", parent=self.app.master)
            return None
        except tk.TclError:
            messagebox.showerror("Error", "UI elements missing. Cannot read preset details.", parent=self.app.master)
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
        if preset_data is None: return
        confirm = messagebox.askyesno("Confirm Save", f"Overwrite preset '{preset_name}' with current settings?", parent=self.app.master)
        if not confirm: return
        self.translation_presets[preset_name] = preset_data
        if save_translation_presets(self.translation_presets):
            messagebox.showinfo("Saved", f"Preset '{preset_name}' has been updated.", parent=self.app.master)

    def save_preset_as(self):
        """Save the current UI settings (preset part) as a new preset."""
        new_name = simpledialog.askstring("Save Preset As", "Enter a name for the new preset:", parent=self.app.master)
        if not new_name: return
        new_name = new_name.strip()
        if not new_name: messagebox.showwarning("Warning", "Preset name cannot be empty.", parent=self.app.master); return
        preset_data = self.get_current_preset_values_for_saving()
        if preset_data is None: return
        if new_name in self.translation_presets:
            overwrite = messagebox.askyesno("Overwrite", f"Preset '{new_name}' already exists. Overwrite?", parent=self.app.master)
            if not overwrite: return
        self.translation_presets[new_name] = preset_data
        if save_translation_presets(self.translation_presets):
            self.preset_names = sorted(list(self.translation_presets.keys()))
            self.preset_combo['values'] = self.preset_names
            self.preset_combo.set(new_name)
            set_setting("last_preset_name", new_name)
            messagebox.showinfo("Saved", f"Preset '{new_name}' has been saved.", parent=self.app.master)
        else:
            if new_name in self.translation_presets: del self.translation_presets[new_name]

    def delete_preset(self):
        """Delete the selected preset."""
        preset_name = self.preset_combo.get()
        if not preset_name: messagebox.showwarning("Warning", "No preset selected to delete.", parent=self.app.master); return
        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete preset '{preset_name}'?", parent=self.app.master)
        if not confirm: return
        if preset_name in self.translation_presets:
            original_data = self.translation_presets[preset_name]
            del self.translation_presets[preset_name]
            if save_translation_presets(self.translation_presets):
                self.preset_names = sorted(list(self.translation_presets.keys()))
                self.preset_combo['values'] = self.preset_names
                new_selection = ""
                if self.preset_names: new_selection = self.preset_names[0]; self.preset_combo.current(0)
                else: self.preset_combo.set("")
                if get_setting("last_preset_name") == preset_name: set_setting("last_preset_name", new_selection)
                self.on_preset_selected()
                messagebox.showinfo("Deleted", f"Preset '{preset_name}' has been deleted.", parent=self.app.master)
            else:
                self.translation_presets[preset_name] = original_data
                messagebox.showerror("Error", "Failed to save presets after deletion. The preset was not deleted.", parent=self.app.master)

    def _start_translation_thread(self, force_recache=False):
        """Internal helper to start the translation thread."""
        config = self.get_translation_config()
        if config is None:
            print("Translation cancelled due to configuration error.")
            self.app.update_status("Translation cancelled: Configuration error.")
            return
        current_hwnd = self.app.selected_hwnd
        if not current_hwnd:
            messagebox.showwarning("Warning", "No game window selected. Cannot translate.", parent=self.app.master)
            self.app.update_status("Translation cancelled: No window selected.")
            return

        # Get the stable texts dictionary directly
        texts_to_translate = {name: text for name, text in self.app.stable_texts.items() if text and text.strip()}

        if not texts_to_translate:
            print("No stable text available to translate.")
            self.app.update_status("No stable text to translate.")
            try:
                if self.translation_display.winfo_exists():
                    self.translation_display.config(state=tk.NORMAL)
                    self.translation_display.delete(1.0, tk.END)
                    self.translation_display.insert(tk.END, "[No stable text detected]")
                    self.translation_display.config(state=tk.DISABLED)
            except tk.TclError: pass
            if hasattr(self.app, 'overlay_manager'): self.app.overlay_manager.clear_all_overlays()
            return

        # No longer need aggregated_input_text here
        # aggregated_input_text = "\n".join([f"[{name}]: {text}" for name, text in texts_to_translate.items()])

        status_msg = "Translating..." if not force_recache else "Forcing retranslation..."
        self.app.update_status(status_msg)
        try:
            if self.translation_display.winfo_exists():
                self.translation_display.config(state=tk.NORMAL)
                self.translation_display.delete(1.0, tk.END)
                self.translation_display.insert(tk.END, f"{status_msg}\n")
                self.translation_display.config(state=tk.DISABLED)
        except tk.TclError: pass
        if hasattr(self.app, 'overlay_manager'):
            for roi_name in texts_to_translate: self.app.overlay_manager.update_overlay(roi_name, "...")

        def translation_thread():
            try:
                # Pass the dictionary directly
                translated_segments = translate_text(
                    stable_texts_dict=texts_to_translate, # CHANGED: Pass dictionary
                    hwnd=current_hwnd,
                    preset=config, # Preset no longer contains system_prompt from UI
                    target_language=config["target_language"],
                    additional_context=config["additional_context"],
                    context_limit=config.get("context_limit", 10),
                    force_recache=force_recache
                )
                if "error" in translated_segments:
                    error_msg = translated_segments["error"]
                    print(f"Translation API Error: {error_msg}")
                    self.app.master.after_idle(lambda: self.update_translation_display_error(error_msg))
                    if hasattr(self.app, 'overlay_manager'):
                        first_roi = next(iter(texts_to_translate), None)
                        if first_roi:
                            self.app.master.after_idle(lambda name=first_roi: self.app.overlay_manager.update_overlay(name, f"Error!"))
                            for r_name in texts_to_translate:
                                if r_name != first_roi: self.app.master.after_idle(lambda n=r_name: self.app.overlay_manager.update_overlay(n, ""))
                else:
                    print("Translation successful.")
                    preview_lines = []
                    # Use the original input dictionary keys for iteration order consistency if needed
                    # Or iterate through ROIs if order matters and ROIs are available
                    rois_to_iterate = self.app.rois if hasattr(self.app, 'rois') else []
                    sorted_roi_names = [roi.name for roi in rois_to_iterate if roi.name in translated_segments]
                    # Add any missing keys from translated_segments (shouldn't happen ideally)
                    for name in translated_segments:
                        if name not in sorted_roi_names:
                            sorted_roi_names.append(name)

                    for roi_name in sorted_roi_names:
                        # Get original text from the input dictionary
                        original_text = texts_to_translate.get(roi_name, "") # Use input dict
                        translated_text = translated_segments.get(roi_name)
                        if original_text.strip(): # Check original text, not stable_texts which might update
                            preview_lines.append(f"[{roi_name}]:")
                            preview_lines.append(translated_text if translated_text else "[Translation N/A]")
                            preview_lines.append("")
                    preview_text = "\n".join(preview_lines).strip()
                    self.app.master.after_idle(lambda seg=translated_segments, prev=preview_text: self.update_translation_results(seg, prev))
            except Exception as e:
                error_msg = f"Unexpected error during translation thread: {str(e)}"
                print(error_msg)
                import traceback
                traceback.print_exc()
                self.app.master.after_idle(lambda: self.update_translation_display_error(error_msg))
                if hasattr(self.app, 'overlay_manager'): self.app.master.after_idle(self.app.overlay_manager.clear_all_overlays)

        threading.Thread(target=translation_thread, daemon=True).start()

    def perform_translation(self):
        """Translate the stable text using the current settings (uses cache)."""
        self._start_translation_thread(force_recache=False)

    def perform_force_translation(self):
        """Force re-translation of the stable text, skipping cache check but updating cache."""
        self._start_translation_thread(force_recache=True)

    def update_translation_results(self, translated_segments, preview_text):
        """Update the preview display and overlays with translation results. Runs in main thread."""
        self.app.update_status("Translation complete.")
        try:
            if self.translation_display.winfo_exists():
                self.translation_display.config(state=tk.NORMAL)
                self.translation_display.delete(1.0, tk.END)
                self.translation_display.insert(tk.END, preview_text if preview_text else "[No translation received]")
                self.translation_display.config(state=tk.DISABLED)
        except tk.TclError: pass
        if hasattr(self.app, 'overlay_manager'): self.app.overlay_manager.update_overlays(translated_segments)
        self.last_translation_result = translated_segments
        self.last_translation_input = self.app.stable_texts.copy()

    def update_translation_display_error(self, error_message):
        """Update the preview display with an error message. Runs in main thread."""
        self.app.update_status(f"Translation Error: {error_message[:50]}...")
        try:
            if self.translation_display.winfo_exists():
                self.translation_display.config(state=tk.NORMAL)
                self.translation_display.delete(1.0, tk.END)
                self.translation_display.insert(tk.END, f"Translation Error:\n\n{error_message}")
                self.translation_display.config(state=tk.DISABLED)
        except tk.TclError: pass
        self.last_translation_result = None
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
        if not current_hwnd: messagebox.showwarning("Warning", "No game window selected. Cannot clear current game cache.", parent=self.app.master); return
        if messagebox.askyesno("Confirm Clear Current Cache", "Are you sure you want to delete the translation cache for the currently selected game?", parent=self.app.master):
            result = clear_current_game_cache(current_hwnd)
            messagebox.showinfo("Cache Cleared", result, parent=self.app.master)
            self.app.update_status("Current game translation cache cleared.")

    def reset_translation_context(self):
        """Reset the translation context history and delete the file for the current game."""
        current_hwnd = self.app.selected_hwnd
        if messagebox.askyesno("Confirm Reset Context", "Are you sure you want to reset the translation context history for the current game?\n(This will delete the saved history file)", parent=self.app.master):
            result = reset_context(current_hwnd)
            messagebox.showinfo("Context Reset", result, parent=self.app.master)
            self.app.update_status("Translation context reset.")

# --- END OF FILE ui/translation_tab.py ---
```

--- START OF FILE translation.py ---
```python
# --- START OF FILE utils/translation.py ---

import json
import re
import os
from openai import OpenAI, APIError # Import APIError for specific handling
from pathlib import Path
import hashlib # For cache key generation
import time # For potential corrupted cache backup naming
from utils.capture import get_executable_details # Import the new function

# File-based cache settings
APP_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Get app root directory
CACHE_DIR = APP_DIR / "cache"
CONTEXT_DIR = APP_DIR / "context_history" # NEW: Directory for context files

# Context management (global list - represents the currently loaded context)
context_messages = []

# --- Logging Helper ---
def format_message_for_log(message):
    """Formats a message dictionary for concise logging."""
    role = message.get('role', 'unknown')
    content = message.get('content', '')
    content_display = (content[:75] + '...') if len(content) > 78 else content
    content_display = content_display.replace('\n', '\\n')
    return f"[{role}] '{content_display}'"

# --- Directory and Hashing ---

def _ensure_cache_dir():
    """Make sure the cache directory exists"""
    try: CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e: print(f"Error creating cache directory {CACHE_DIR}: {e}")

def _ensure_context_dir():
    """Make sure the context history directory exists"""
    try: CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e: print(f"Error creating context directory {CONTEXT_DIR}: {e}")

def _get_game_hash(hwnd):
    """Generates a hash based on the game's executable path and size."""
    if not hwnd: return None
    exe_path, file_size = get_executable_details(hwnd)
    if exe_path and file_size is not None:
        try:
            identity_string = f"{os.path.normpath(exe_path).lower()}|{file_size}"
            hasher = hashlib.sha256()
            hasher.update(identity_string.encode('utf-8'))
            return hasher.hexdigest()
        except Exception as e: print(f"Error generating game hash: {e}")
    return None

def _get_cache_file_path(hwnd):
    """Gets the specific cache file path for the given game window."""
    if hwnd is None: return None
    game_hash = _get_game_hash(hwnd)
    if game_hash: return CACHE_DIR / f"{game_hash}.json"
    else: print("Warning: Could not determine game hash. Using default cache file."); return CACHE_DIR / "default_cache.json"

def _get_context_file_path(hwnd):
    """Gets the specific context history file path for the given game window."""
    if hwnd is None: return None
    game_hash = _get_game_hash(hwnd)
    if game_hash: return CONTEXT_DIR / f"{game_hash}_context.json"
    else: print("Warning: Could not determine game hash for context file path."); return None

# --- Cache Handling ---

def _load_cache(cache_file_path):
    """Load the translation cache from the specified game file"""
    _ensure_cache_dir()
    try:
        if cache_file_path.exists():
            with open(cache_file_path, 'r', encoding='utf-8') as f: content = f.read()
            if not content: return {}
            return json.loads(content)
    except json.JSONDecodeError:
        print(f"Warning: Cache file {cache_file_path} is corrupted or empty. Starting fresh cache.")
        try:
            corrupted_path = cache_file_path.parent / f"{cache_file_path.name}.corrupted_{int(time.time())}"
            os.rename(cache_file_path, corrupted_path)
            print(f"Corrupted cache backed up to {corrupted_path}")
        except Exception as backup_err: print(f"Error backing up corrupted cache file: {backup_err}")
        return {}
    except Exception as e: print(f"Error loading cache from {cache_file_path}: {e}")
    return {}

def _save_cache(cache, cache_file_path):
    """Save the translation cache to the specified game file"""
    _ensure_cache_dir()
    try:
        with open(cache_file_path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e: print(f"Error saving cache to {cache_file_path}: {e}")

def clear_current_game_cache(hwnd):
    """Clear the translation cache for the currently selected game."""
    cache_file_path = _get_cache_file_path(hwnd)
    if not cache_file_path: return "Could not identify game to clear cache (or cache skipped)."
    if cache_file_path.exists():
        try:
            os.remove(cache_file_path)
            print(f"Cache file deleted: {cache_file_path}")
            return f"Cache cleared for the current game ({cache_file_path.stem})."
        except Exception as e: print(f"Error deleting cache file {cache_file_path}: {e}"); return f"Error clearing current game cache: {e}"
    else: print(f"Cache file not found for current game: {cache_file_path}"); return "Cache for the current game was already empty."

def clear_all_cache():
    """Clear all translation cache files in the cache directory."""
    _ensure_cache_dir()
    cleared_count = 0
    errors = []
    try:
        for item in CACHE_DIR.iterdir():
            if item.is_file() and item.suffix == '.json':
                try: os.remove(item); cleared_count += 1; print(f"Deleted cache file: {item.name}")
                except Exception as e: errors.append(item.name); print(f"Error deleting cache file {item.name}: {e}")
        if errors: return f"Cleared {cleared_count} cache files. Errors deleting: {', '.join(errors)}."
        elif cleared_count > 0: return f"Successfully cleared all {cleared_count} translation cache files."
        else: return "Cache directory was empty or contained no cache files."
    except Exception as e: print(f"Error iterating cache directory {CACHE_DIR}: {e}"); return f"Error accessing cache directory: {e}"

# --- Context History Handling ---

def _load_context(hwnd):
    """Loads context history from the game-specific file into the global list."""
    global context_messages
    context_messages = []
    if hwnd is None: print("[CONTEXT] HWND is None, skipping context load."); return
    _ensure_context_dir()
    context_file_path = _get_context_file_path(hwnd)
    if not context_file_path: print("[CONTEXT] Cannot load context, failed to get file path."); return
    if context_file_path.exists():
        try:
            with open(context_file_path, 'r', encoding='utf-8') as f: content = f.read()
            if content:
                loaded_history = json.loads(content)
                if isinstance(loaded_history, list):
                    context_messages = loaded_history
                    print(f"[CONTEXT] Loaded {len(context_messages)} messages from {context_file_path.name}")
                else: print(f"[CONTEXT] Error: Loaded context from {context_file_path.name} is not a list. Resetting history.")
            else: print(f"[CONTEXT] Context file {context_file_path.name} is empty.")
        except json.JSONDecodeError: print(f"[CONTEXT] Error: Context file {context_file_path.name} is corrupted. Resetting history.")
        except Exception as e: print(f"[CONTEXT] Error loading context from {context_file_path.name}: {e}. Resetting history.")
    else: print(f"[CONTEXT] No context file found for current game ({context_file_path.name}). Starting fresh history.")

def _save_context(hwnd):
    """Saves the current global context_messages (full history) to the game-specific file."""
    global context_messages
    if hwnd is None: return
    _ensure_context_dir()
    context_file_path = _get_context_file_path(hwnd)
    if not context_file_path: print("[CONTEXT] Cannot save context, failed to get file path."); return
    try:
        with open(context_file_path, 'w', encoding='utf-8') as f:
            # Save the entire context_messages list
            json.dump(context_messages, f, ensure_ascii=False, indent=2)
    except Exception as e: print(f"Error saving context to {context_file_path.name}: {e}")

def reset_context(hwnd):
    """Reset the global translation context history AND delete the game-specific file."""
    global context_messages
    context_messages = []
    print("[CONTEXT] In-memory context history reset.")
    if hwnd is None: return "Context history reset (no game specified to delete file)."
    context_file_path = _get_context_file_path(hwnd)
    if context_file_path and context_file_path.exists():
        try:
            os.remove(context_file_path)
            print(f"[CONTEXT] Deleted context file: {context_file_path.name}")
            return "Translation context history reset and file deleted."
        except Exception as e: print(f"[CONTEXT] Error deleting context file {context_file_path.name}: {e}"); return f"Context history reset, but error deleting file: {e}"
    elif context_file_path: return "Context history reset (no file found to delete)."
    else: return "Context history reset (could not determine file path)."

# MODIFIED add_context_message
def add_context_message(message):
    """Add a message to the global translation context history. No trimming here."""
    global context_messages
    context_messages.append(message)
    # No trimming logic here - the full history is maintained in context_messages

# --- Translation Core Logic ---

def get_cache_key(text, target_language):
    """Generate a unique cache key based ONLY on the input text and target language."""
    hasher = hashlib.sha256()
    hasher.update(text.encode('utf-8'))
    hasher.update(target_language.encode('utf-8'))
    return hasher.hexdigest()

def get_cached_translation(cache_key, cache_file_path):
    """Get a cached translation if it exists from the specific game cache file."""
    if not cache_file_path: return None
    cache = _load_cache(cache_file_path)
    return cache.get(cache_key)

def set_cache_translation(cache_key, translation, cache_file_path):
    """Cache a translation result to the specific game cache file."""
    if not cache_file_path: return
    cache = _load_cache(cache_file_path)
    cache[cache_key] = translation
    _save_cache(cache, cache_file_path)

def parse_translation_output(response_text, original_tag_mapping):
    """
    Parse the translation output from a tagged format (<|n|>)
    and map it back to the original ROI names using the tag_mapping.
    """
    parsed_segments = {}
    # Updated pattern to better handle potential whitespace and newlines around tags/content
    pattern = r"<\|(\d+)\|>(.*?)(?=<\|\d+\|>|$)"
    matches = re.findall(pattern, response_text, re.DOTALL | re.MULTILINE)

    if matches:
        for segment_number, content in matches:
            original_roi_name = original_tag_mapping.get(segment_number)
            if original_roi_name:
                # Clean leading/trailing whitespace, including newlines
                cleaned_content = content.strip()
                # Remove potential trailing tag from the current segment's content
                cleaned_content = re.sub(r'<\|\d+\|>$', '', cleaned_content).strip()
                parsed_segments[original_roi_name] = cleaned_content
            else:
                print(f"Warning: Received segment number '{segment_number}' which was not in the original mapping.")
    else:
        # Fallback: Try line-based parsing if the main pattern fails
        # This is less robust if content has newlines but might catch simple cases
        line_pattern = r"^\s*<\|(\d+)\|>\s*(.*)$"
        lines = response_text.strip().split('\n')
        found_line_match = False
        for line in lines:
            match = re.match(line_pattern, line)
            if match:
                found_line_match = True
                segment_number, content = match.groups()
                original_roi_name = original_tag_mapping.get(segment_number)
                if original_roi_name:
                    parsed_segments[original_roi_name] = content.strip()
                else:
                    print(f"Warning: Received segment number '{segment_number}' (line match) which was not in original mapping.")

        # If still no matches and only one ROI was expected, assume plain text response
        if not found_line_match and len(original_tag_mapping) == 1 and not response_text.startswith("<|"):
            first_tag = next(iter(original_tag_mapping))
            first_roi = original_tag_mapping[first_tag]
            print(f"[LLM PARSE] Warning: Response had no tags, assuming plain text response for single ROI '{first_roi}'.")
            parsed_segments[first_roi] = response_text.strip()
        elif not found_line_match and not matches:
            # If multiple ROIs were expected but no tags found
            print("[LLM PARSE] Failed to parse any <|n|> segments from response and multiple segments expected.")
            return {"error": f"Error: Unable to extract formatted translation.\nRaw response:\n{response_text}"}

    # Check for missing ROIs compared to the original input
    missing_rois = set(original_tag_mapping.values()) - set(parsed_segments.keys())
    if missing_rois:
        print(f"[LLM PARSE] Warning: Translation response missing segments for ROIs: {', '.join(missing_rois)}")
        for roi_name in missing_rois:
            parsed_segments[roi_name] = "[Translation Missing]" # Add placeholder

    # Final check if parsing completely failed
    if not parsed_segments and original_tag_mapping:
        print("[LLM PARSE] Error: Failed to parse any segments despite expecting tags.")
        return {"error": f"Error: Failed to extract any segments.\nRaw response:\n{response_text}"}

    return parsed_segments

# MODIFIED preprocess_text_for_translation
def preprocess_text_for_translation(stable_texts_dict):
    """
    Convert input dictionary {roi_name: text} to the numbered format <|1|> text.
    Handles multi-line text within each ROI's content correctly.
    Returns the preprocessed string and the tag mapping.
    """
    preprocessed_lines = []
    tag_mapping = {}
    segment_count = 1

    # Iterate through the dictionary items directly
    for roi_name, content in stable_texts_dict.items():
        content_stripped = content.strip() if content else ""
        if content_stripped: # Only process if content is not empty after stripping
            tag_mapping[str(segment_count)] = roi_name
            # Append the full content (preserving internal newlines) with the tag
            preprocessed_lines.append(f"<|{segment_count}|> {content_stripped}")
            segment_count += 1
        else:
            print(f"Skipping empty content for ROI: {roi_name}")

    if not tag_mapping:
        print("Warning: No non-empty text found in input dictionary during preprocessing.")

    # Join the processed lines with newlines for the final string
    return '\n'.join(preprocessed_lines), tag_mapping

# MODIFIED translate_text function signature and preprocessing call
def translate_text(stable_texts_dict, hwnd, preset, target_language="en", additional_context="", context_limit=10, force_recache=False, skip_cache=False, skip_history=False):
    """
    Translate the given text segments (from a dictionary) using an OpenAI-compatible API client,
    using game-specific caching and context. System prompt is constructed internally.
    Context history sent to the API is limited by context_limit.
    """
    cache_file_path = None if skip_cache else _get_cache_file_path(hwnd)
    if not skip_cache and not cache_file_path and hwnd is not None:
        print("Error: Cannot proceed with cached translation without a valid game identifier.")
        return {"error": "Could not determine cache file path for the game."}

    # Preprocess the input dictionary into the tagged string format
    preprocessed_text_for_llm, tag_mapping = preprocess_text_for_translation(stable_texts_dict)

    if not preprocessed_text_for_llm or not tag_mapping:
        print("No valid text segments found after preprocessing. Nothing to translate.")
        return {} # Return empty dict if nothing to translate

    # Cache key is based on the preprocessed text (what the LLM sees) and target language
    cache_key = get_cache_key(preprocessed_text_for_llm, target_language)

    # --- Cache Check ---
    if not skip_cache and not force_recache:
        cached_result = get_cached_translation(cache_key, cache_file_path)
        if cached_result:
            # Validate cache integrity (ensure all expected ROIs are present)
            if isinstance(cached_result, dict) and not 'error' in cached_result:
                # Check if all ROI names from the *original input* are keys in the cached result
                if all(roi_name in cached_result for roi_name in stable_texts_dict.keys() if stable_texts_dict[roi_name].strip()):
                    print(f"[CACHE] HIT for key: {cache_key[:10]}... in {cache_file_path.name if cache_file_path else 'N/A'}")
                    return cached_result
                else:
                    print("[CACHE] WARN: Cached result incomplete or missing expected ROIs, fetching fresh translation.")
            else:
                print("[CACHE] WARN: Cached result format mismatch or error, fetching fresh translation.")
        else:
            print(f"[CACHE] MISS for key: {cache_key[:10]}... in {cache_file_path.name if cache_file_path else 'N/A'}")
    elif skip_cache: print(f"[CACHE] SKIP requested (skip_cache=True)")
    elif force_recache: print(f"[CACHE] SKIP requested (force_recache=True) for key: {cache_key[:10]}...")
    # --- End Cache Check ---


    # --- Construct System Prompt Internally ---
    base_system_prompt = (
        "You are a professional translation assistant. Your task is to translate text segments accurately "
        "from their source language into the target language specified in the user prompt. "
        "The input text segments are marked with tags like <|1|>, <|2|>, etc. "
        "Your response MUST strictly adhere to this format, reproducing the exact same tags for each corresponding translated segment. "
        "For example, if the input is '<|1|> Hello\n<|2|> World' and the target language is French, the output must be '<|1|> Bonjour\n<|2|> Le monde'. "
        "Do NOT include ANY extra text, commentary, explanations, greetings, summaries, apologies, or any conversational filler before, between, or after the tagged translations."
    )
    system_content = base_system_prompt
    system_message = {"role": "system", "content": system_content}
    # --- End System Prompt Construction ---

    # --- Prepare Context History for API Call (Apply Limit) ---
    history_to_send = []
    if not skip_history:
        global context_messages # Use the full history stored globally
        try:
            # Use the context_limit passed to this function (originating from the preset)
            limit_exchanges = int(context_limit)
            limit_exchanges = max(1, limit_exchanges) # Ensure at least 1 exchange
        except (ValueError, TypeError):
            limit_exchanges = 10 # Fallback default if invalid
            print(f"[CONTEXT] Warning: Invalid context_limit value '{context_limit}'. Using default: {limit_exchanges}")

        # Calculate the number of messages (user + assistant) to send based on the exchange limit
        max_messages_to_send = limit_exchanges * 2

        # Slice the global context_messages list to get only the most recent messages
        if len(context_messages) > max_messages_to_send:
            # Select the last 'max_messages_to_send' items from the full history
            history_to_send = context_messages[-max_messages_to_send:]
            print(f"[CONTEXT] Sending last {len(history_to_send)} messages ({limit_exchanges} exchanges limit) to API.")
        else:
            # Send the entire history if it's shorter than the limit
            history_to_send = list(context_messages)
            print(f"[CONTEXT] Sending all {len(history_to_send)} available messages (within {limit_exchanges} exchanges limit) to API.")
    # --- End Context History Preparation ---

    # --- Construct User Message for API ---
    current_user_message_parts = []
    if additional_context.strip():
        current_user_message_parts.append(f"Additional context for this translation: {additional_context.strip()}")
    current_user_message_parts.append(f"Translate the following segments into {target_language}, maintaining the exact <|n|> tags:")
    # Use the preprocessed text string here
    current_user_message_parts.append(preprocessed_text_for_llm)
    current_user_content_with_context = "\n\n".join(current_user_message_parts)
    current_user_message_for_api = {"role": "user", "content": current_user_content_with_context}
    # --- End Construct User Message ---

    # Prepare the user message that will be *added* to the full history (without additional context)
    history_user_message = None
    if not skip_history:
        history_user_message_parts = [
            f"Translate the following segments into {target_language}, maintaining the exact <|n|> tags:",
            preprocessed_text_for_llm # Use the same preprocessed text for history
        ]
        history_user_content = "\n\n".join(history_user_message_parts)
        history_user_message = {"role": "user", "content": history_user_content}

    # Construct the final list of messages for the API call (using the potentially sliced history_to_send)
    messages_for_api = [system_message] + history_to_send + [current_user_message_for_api]

    if not preset.get("model") or not preset.get("api_url"):
        missing = [f for f in ["model", "api_url"] if not preset.get(f)]
        errmsg = f"Missing required preset fields: {', '.join(missing)}"
        print(f"[API] Error: {errmsg}")
        return {"error": errmsg}

    payload = {
        "model": preset["model"], "messages": messages_for_api,
        "temperature": preset.get("temperature", 0.3), "max_tokens": preset.get("max_tokens", 1000)
    }
    for param in ["top_p", "frequency_penalty", "presence_penalty"]:
        if param in preset and preset[param] is not None:
            try: payload[param] = float(preset[param])
            except (ValueError, TypeError): print(f"Warning: Invalid value for parameter '{param}': {preset[param]}. Skipping.")

    print("-" * 20 + " LLM Request " + "-" * 20)
    print(f"[API] Endpoint: {preset.get('api_url')}")
    print(f"[API] Model: {preset['model']}")
    print(f"[API] Payload Parameters (excluding messages):")
    for key, value in payload.items():
        if key != "messages": print(f"  - {key}: {value}")
    print(f"[API] Messages ({len(messages_for_api)} total):")
    if messages_for_api[0]['role'] == 'system': print(f"  - [system] (Internal prompt used)")
    if history_to_send:
        # Log the number of messages *actually sent*
        print(f"  - [CONTEXT HISTORY - {len(history_to_send)} messages sent]:")
        for msg in history_to_send: print(f"    - {format_message_for_log(msg)}")
    print(f"  - {format_message_for_log(current_user_message_for_api)}")
    print("-" * 55)

    try:
        api_key = preset.get("api_key") or None
        client = OpenAI(base_url=preset.get("api_url"), api_key=api_key)
    except Exception as e: print(f"[API] Error creating API client: {e}"); return {"error": f"Error creating API client: {e}"}

    response_text = None
    try:
        completion = client.chat.completions.create(**payload)
        if not completion.choices or not completion.choices[0].message or completion.choices[0].message.content is None:
            print("[API] Error: Invalid response structure received from API.")
            try: print(f"[API] Raw Response Object: {completion}")
            except Exception as log_err: print(f"[API] Error logging raw response object: {log_err}")
            return {"error": "Invalid response structure received from API."}
        response_text = completion.choices[0].message.content.strip()
        print("-" * 20 + " LLM Response " + "-" * 20)
        print(f"[API] Raw Response Text ({len(response_text)} chars):\n{response_text}")
        print("-" * 56)
    except APIError as e:
        error_message = str(e)
        status_code = getattr(e, 'status_code', 'N/A')
        try:
            error_body = json.loads(getattr(e, 'body', '{}') or '{}')
            detail = error_body.get('error', {}).get('message', '')
            if detail: error_message = detail
        except: pass
        log_msg = f"[API] APIError during translation request: Status {status_code}, Error: {error_message}"
        print(log_msg)
        print(f"[API] Request Model: {payload.get('model')}")
        return {"error": f"API Error ({status_code}): {error_message}"}
    except Exception as e:
        error_message = str(e)
        log_msg = f"[API] Error during translation request: {error_message}"
        print(log_msg)
        import traceback
        traceback.print_exc()
        return {"error": f"Error during API request: {error_message}"}

    # Parse the response using the original tag mapping
    final_translations = parse_translation_output(response_text, tag_mapping)
    if 'error' in final_translations:
        print("[LLM PARSE] Parsing failed after receiving response.")
        return final_translations

    # --- Add to Stored History (using history_user_message) ---
    if not skip_history and history_user_message:
        add_to_history = True
        # Check if the exact same user input was the last user input in the *full stored* history
        if len(context_messages) >= 2:
            last_user_message_in_stored_history = context_messages[-2]
            if last_user_message_in_stored_history.get('role') == 'user':
                if last_user_message_in_stored_history.get('content') == history_user_message.get('content'):
                    add_to_history = False
                    print("[CONTEXT] Input identical to previous user message in stored history. Skipping history update.")

        if add_to_history:
            current_assistant_message = {"role": "assistant", "content": response_text}
            # Add to the full global history list (no limit applied here)
            add_context_message(history_user_message)
            add_context_message(current_assistant_message)
            _save_context(hwnd) # Save the updated full history
    # --- End Add to Stored History ---

    # --- Cache the successful result ---
    if not skip_cache and cache_file_path:
        # Cache the parsed dictionary result, not the raw response
        set_cache_translation(cache_key, final_translations, cache_file_path)
        print(f"[CACHE] Translation cached/updated successfully in {cache_file_path.name}")
    elif not skip_cache and not cache_file_path:
        print("[CACHE] Warning: Could not cache translation (invalid path).")
    # --- End Cache ---

    return final_translations

# --- END OF FILE utils/translation.py ---
```

--- START OF FILE app.py ---
```python
# --- START OF FILE app.py ---

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import cv2
import numpy as np
from PIL import Image, ImageTk
import os
import win32gui


# Utility Imports
from utils.capture import get_window_title, capture_window, capture_screen_region
from utils.config import load_rois, ROI_CONFIGS_DIR, _get_game_hash # Use config functions
from utils.settings import load_settings, set_setting, get_setting, get_overlay_config_for_roi
from utils.roi import ROI
from utils.translation import CACHE_DIR, CONTEXT_DIR, _load_context, translate_text
import utils.ocr as ocr # Import the refactored ocr module

# UI Imports
from ui.capture_tab import CaptureTab
from ui.roi_tab import ROITab
from ui.text_tab import TextTab, StableTextTab
from ui.translation_tab import TranslationTab
from ui.overlay_tab import OverlayTab, SNIP_ROI_NAME
from ui.overlay_manager import OverlayManager
from ui.floating_overlay_window import FloatingOverlayWindow, ClosableFloatingOverlayWindow
from ui.floating_controls import FloatingControls
from ui.preview_window import PreviewWindow # Import the new preview window
from ui.color_picker import ScreenColorPicker # Import screen color picker

FPS = 10 # Target frames per second for capture loop
FRAME_DELAY = 1.0 / FPS
# OCR_ENGINE_LOCK = threading.Lock() # Removed - locking handled within ocr module if needed


class VisualNovelTranslatorApp:
    def __init__(self, master):
        self.master = master
        self.settings = load_settings()
        self.config_file = None # Path to the currently loaded game-specific ROI config

        window_title = "Visual Novel Translator"
        master.title(window_title)
        master.geometry("1200x800") # Initial size
        master.minsize(1000, 700) # Minimum size
        master.protocol("WM_DELETE_WINDOW", self.on_close)

        # Ensure necessary directories exist
        self._ensure_dirs()

        # State variables
        self.capturing = False
        self.roi_selection_active = False
        self.selected_hwnd = None
        self.capture_thread = None
        self.rois = [] # List of ROI objects for the current game
        self.current_frame = None # Last captured frame (NumPy array)
        self.display_frame_tk = None # PhotoImage for canvas display
        self.snapshot_frame = None # Stored frame for snapshot mode
        self.using_snapshot = False # Flag if snapshot is active
        self.roi_start_coords = None # For drawing new ROIs on canvas
        self.roi_draw_rect_id = None # Canvas item ID for the drawing rectangle
        self.scale_x, self.scale_y = 1.0, 1.0 # Scaling factor for display
        self.frame_display_coords = {'x': 0, 'y': 0, 'w': 0, 'h': 0} # Position/size on canvas

        # Snip & Translate state
        self.snip_mode_active = False
        self.snip_overlay = None
        self.snip_canvas = None
        self.snip_start_coords = None
        self.snip_rect_id = None
        self.current_snip_window = None # Holds the ClosableFloatingOverlayWindow for snip results

        # Text processing state
        self.text_history = {} # Tracks consecutive identical OCR results per ROI
        self.stable_texts = {} # Holds text considered stable for translation
        self.stable_threshold = get_setting("stable_threshold", 3)
        self.max_display_width = get_setting("max_display_width", 800) # Max width for canvas image
        self.max_display_height = get_setting("max_display_height", 600) # Max height for canvas image
        self.last_status_message = ""

        # OCR Engine State
        self.ocr_engine_type = get_setting("ocr_engine", "paddle") # Store the selected type
        self.ocr_lang = get_setting("ocr_language", "jpn")
        self.ocr_engine_ready = False # Flag to track if the current engine is ready
        self._ocr_init_thread = None # Thread for background initialization

        self._resize_job = None # For debouncing canvas resize events

        # Setup UI components
        self._setup_ui()
        self.overlay_manager = OverlayManager(self.master, self)
        self.floating_controls = None

        # Initialize OCR engine (now happens in background)
        self._trigger_ocr_initialization(self.ocr_engine_type, self.ocr_lang, initial_load=True)
        self.show_floating_controls() # Show floating controls on startup

    def _ensure_dirs(self):
        """Creates necessary directories if they don't exist."""
        dirs_to_check = [CACHE_DIR, ROI_CONFIGS_DIR, CONTEXT_DIR]
        for d in dirs_to_check:
            try:
                d.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"Warning: Failed to create directory {d}: {e}")

    def _setup_ui(self):
        """Builds the main UI elements."""
        # --- Menu Bar ---
        menu_bar = tk.Menu(self.master)
        self.master.config(menu=menu_bar)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="File", menu=file_menu)
        # Add command to save ROIs (references roi_tab method)
        file_menu.add_command(label="Save All ROI Settings for Current Game",
                              command=lambda: self.roi_tab.save_rois_for_current_game() if hasattr(self, 'roi_tab') else None)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)

        window_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Window", menu=window_menu)
        window_menu.add_command(label="Show Floating Controls", command=self.show_floating_controls)

        # --- Main Layout (Paned Window) ---
        self.paned_window = ttk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left Pane: Image Preview Canvas
        self.left_frame = ttk.Frame(self.paned_window, padding=0)
        self.paned_window.add(self.left_frame, weight=3) # Give more weight initially
        self.canvas = tk.Canvas(self.left_frame, bg="gray15", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        # Bind mouse events for ROI definition
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        # Bind resize event
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        # Right Pane: Control Tabs
        self.right_frame = ttk.Frame(self.paned_window, padding=(5, 0, 0, 0))
        self.paned_window.add(self.right_frame, weight=1)
        self.notebook = ttk.Notebook(self.right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Initialize Tabs
        self.capture_tab = CaptureTab(self.notebook, self)
        self.notebook.add(self.capture_tab.frame, text="Capture")
        self.roi_tab = ROITab(self.notebook, self)
        self.notebook.add(self.roi_tab.frame, text="ROIs")
        self.overlay_tab = OverlayTab(self.notebook, self)
        self.notebook.add(self.overlay_tab.frame, text="Overlays")
        self.text_tab = TextTab(self.notebook, self)
        self.notebook.add(self.text_tab.frame, text="Live Text")
        self.stable_text_tab = StableTextTab(self.notebook, self)
        self.notebook.add(self.stable_text_tab.frame, text="Stable Text")
        self.translation_tab = TranslationTab(self.notebook, self)
        self.notebook.add(self.translation_tab.frame, text="Translation")

        # --- Status Bar ---
        self.status_bar_frame = ttk.Frame(self.master, relief=tk.SUNKEN)
        self.status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_bar = ttk.Label(self.status_bar_frame, text="Status: Initializing...", anchor=tk.W, padding=(5, 2))
        self.status_bar.pack(fill=tk.X)
        self.update_status("Ready. Select a window.")

    def update_status(self, message):
        """Updates the status bar text (thread-safe)."""
        def _do_update():
            if hasattr(self, "status_bar") and self.status_bar.winfo_exists():
                try:
                    current_text = self.status_bar.cget("text")
                    new_text = f"Status: {message}"
                    if new_text != current_text:
                        self.status_bar.config(text=new_text)
                        self.last_status_message = message
                        # Also update the status label in the Capture tab if it exists
                        if hasattr(self, "capture_tab") and hasattr(self.capture_tab, "status_label") and self.capture_tab.status_label.winfo_exists():
                            self.capture_tab.status_label.config(text=new_text)
                except tk.TclError:
                    # Widget might be destroyed during shutdown
                    pass
            else:
                # Store message if status bar isn't ready yet
                self.last_status_message = message

        try:
            # Schedule the update on the main thread
            if self.master.winfo_exists():
                self.master.after_idle(_do_update)
            else:
                self.last_status_message = message # Store if master window gone
        except Exception:
            # Fallback if scheduling fails
            self.last_status_message = message

    def load_game_context(self, hwnd):
        """Loads translation context history and game-specific context."""
        _load_context(hwnd) # Load history from file into memory (translation.py)

        # Load game-specific additional context from settings
        all_game_contexts = get_setting("game_specific_context", {})
        game_hash = _get_game_hash(hwnd) if hwnd else None
        context_text_for_ui = all_game_contexts.get(game_hash, "") if game_hash else ""

        # Update the UI in the Translation tab
        if hasattr(self, 'translation_tab') and self.translation_tab.frame.winfo_exists():
            self.translation_tab.load_context_for_game(context_text_for_ui)

    def load_rois_for_hwnd(self, hwnd):
        """Loads ROI configuration when the selected window changes."""
        if not hwnd:
            # Clear ROIs if no window is selected
            if self.rois: # Only clear if there were ROIs before
                print("Clearing ROIs as no window is selected.")
                self.rois = []
                self.config_file = None
                if hasattr(self, "roi_tab"): self.roi_tab.update_roi_list()
                if hasattr(self, "overlay_manager"): self.overlay_manager.rebuild_overlays()
                self.master.title("Visual Novel Translator") # Reset title
                self.update_status("No window selected. ROIs cleared.")
                self._clear_text_data() # Clear text history, stable text, etc.
                self.load_game_context(None) # Load default/empty context
            return

        self.update_status(f"Checking for ROIs for HWND {hwnd}...")
        try:
            # Use the load_rois function from config.py
            loaded_rois, loaded_path = load_rois(hwnd)

            if loaded_path is not None: # A config file was found or load attempt was made
                self.rois = loaded_rois # This might be an empty list if file was empty/corrupt
                self.config_file = loaded_path
                if loaded_rois:
                    self.update_status(f"Loaded {len(loaded_rois)} ROIs for current game.")
                    self.master.title(f"Visual Novel Translator - {os.path.basename(loaded_path)}")
                else:
                    # File existed but was empty or invalid
                    self.update_status("ROI config found but empty/invalid. Define new ROIs.")
                    self.master.title(f"Visual Novel Translator - {os.path.basename(loaded_path)}")

            else: # No config file found for this game
                if self.rois: # Clear if switching from a game that had ROIs
                    print(f"No ROIs found for HWND {hwnd}. Clearing previous ROIs.")
                    self.rois = []
                    self.config_file = None
                    self.master.title("Visual Novel Translator") # Reset title
                self.update_status("No ROIs found for current game. Define new ROIs.")

            # Always load context after potentially changing games
            self.load_game_context(hwnd)

            # Update UI elements related to ROIs
            if hasattr(self, "roi_tab"): self.roi_tab.update_roi_list()
            if hasattr(self, "overlay_manager"): self.overlay_manager.rebuild_overlays()
            self._clear_text_data() # Clear previous text data

        except Exception as e:
            # General error during loading
            self.update_status(f"Error loading ROIs/Context for HWND {hwnd}: {str(e)}")
            import traceback
            traceback.print_exc()
            # Reset state
            self.rois = []
            self.config_file = None
            if hasattr(self, "roi_tab"): self.roi_tab.update_roi_list()
            if hasattr(self, "overlay_manager"): self.overlay_manager.rebuild_overlays()
            self.master.title("Visual Novel Translator")
            self._clear_text_data()
            self.load_game_context(None)

    def _clear_text_data(self):
        """Resets text history, stable text, and clears related UI displays."""
        self.text_history = {}
        self.stable_texts = {}

        # Safely update UI tabs if they exist
        def safe_update(widget_attr_name, update_method_name, *args):
            widget = getattr(self, widget_attr_name, None)
            if widget and hasattr(widget, 'frame') and widget.frame.winfo_exists():
                update_method = getattr(widget, update_method_name, None)
                if update_method:
                    try:
                        update_method(*args)
                    except tk.TclError: pass # Ignore errors if widget is destroyed
                    except Exception as e: print(f"Error updating {widget_attr_name}: {e}")

        safe_update("text_tab", "update_text", {})
        safe_update("stable_text_tab", "update_text", {})

        # Clear translation preview display
        if hasattr(self, "translation_tab") and self.translation_tab.frame.winfo_exists():
            try:
                self.translation_tab.translation_display.config(state=tk.NORMAL)
                self.translation_tab.translation_display.delete(1.0, tk.END)
                self.translation_tab.translation_display.config(state=tk.DISABLED)
            except tk.TclError: pass

        # Clear any text currently shown in overlays
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.clear_all_overlays()

    def _trigger_ocr_initialization(self, engine_type, lang_code, initial_load=False):
        """Starts the OCR engine initialization in a background thread."""
        # Abort if an init thread is already running
        if self._ocr_init_thread and self._ocr_init_thread.is_alive():
            print("[OCR Init] Initialization already in progress. Ignoring new request.")
            return

        self.ocr_engine_ready = False # Mark as not ready until init completes
        status_msg = f"Initializing OCR ({engine_type}/{lang_code})..."
        if not initial_load:
            print(status_msg)
        self.update_status(status_msg)

        def init_task():
            try:
                # Call the extract_text function with a dummy image just to trigger initialization
                # This relies on the caching/initialization logic within ocr.py
                dummy_img = np.zeros((10, 10, 3), dtype=np.uint8) # Small dummy image
                ocr.extract_text(dummy_img, lang=lang_code, engine_type=engine_type)
                # If no exception, initialization was successful (or already done)
                self.ocr_engine_ready = True
                success_msg = f"OCR Ready ({engine_type}/{lang_code})."
                print(success_msg)
                self.master.after_idle(lambda: self.update_status(success_msg))
            except Exception as e:
                self.ocr_engine_ready = False
                error_msg = f"OCR Error ({engine_type}/{lang_code}): {str(e)[:60]}..."
                print(f"!!! Error during OCR initialization thread: {e}")
                # import traceback # Optional: uncomment for full trace
                # traceback.print_exc()
                self.master.after_idle(lambda: self.update_status(error_msg))

        self._ocr_init_thread = threading.Thread(target=init_task, daemon=True)
        self._ocr_init_thread.start()

    def set_ocr_engine(self, engine_type, lang_code):
        """Sets the desired OCR engine and triggers initialization."""
        if engine_type == self.ocr_engine_type:
            print(f"OCR engine already set to {engine_type}.")
            # Still might need re-init if language changed implicitly, trigger anyway
            self._trigger_ocr_initialization(engine_type, lang_code)
            return

        print(f"Setting OCR engine to: {engine_type}")
        self.ocr_engine_type = engine_type
        set_setting("ocr_engine", engine_type) # Save preference
        self._trigger_ocr_initialization(engine_type, lang_code)

    def update_ocr_language(self, lang_code, engine_type):
        """Sets the desired OCR language and triggers engine re-initialization."""
        if lang_code == self.ocr_lang and self.ocr_engine_ready:
            # Check if the current *engine* matches the requested one too
            if engine_type == self.ocr_engine_type:
                print(f"OCR language already set to {lang_code} for engine {engine_type}.")
                return # No change needed if engine is ready and matches

        print(f"Setting OCR language to: {lang_code} for engine {engine_type}")
        self.ocr_lang = lang_code
        set_setting("ocr_language", lang_code) # Save preference
        # Always trigger re-initialization when language changes, using the current engine type
        self._trigger_ocr_initialization(engine_type, lang_code)


    def update_stable_threshold(self, new_value):
        """Updates the stability threshold from UI controls."""
        try:
            new_threshold = int(float(new_value))
            if new_threshold >= 1:
                if self.stable_threshold != new_threshold:
                    self.stable_threshold = new_threshold
                    # Save the setting persistently
                    if set_setting("stable_threshold", new_threshold):
                        self.update_status(f"Stability threshold set to {new_threshold}.")
                        print(f"Stability threshold updated to: {new_threshold}")
                    else:
                        self.update_status("Error saving stability threshold.")
            else:
                print(f"Ignored invalid threshold value: {new_threshold}")
        except (ValueError, TypeError):
            print(f"Ignored non-numeric threshold value: {new_value}")

    def start_capture(self):
        """Starts the main capture and processing loop."""
        if self.capturing: return # Already running
        if not self.selected_hwnd:
            messagebox.showwarning("Warning", "No visual novel window selected.", parent=self.master)
            return

        # Ensure ROIs are loaded for the selected game
        if not self.rois and self.selected_hwnd:
            self.load_rois_for_hwnd(self.selected_hwnd)

        # Check if OCR engine is ready
        if not self.ocr_engine_ready:
            # If not ready, trigger initialization again and inform user
            self._trigger_ocr_initialization(self.ocr_engine_type, self.ocr_lang)
            messagebox.showinfo("OCR Not Ready", f"OCR ({self.ocr_engine_type}/{self.ocr_lang}) is initializing... Capture will start, but text extraction may be delayed.", parent=self.master)
        # else:
        # print(f"OCR engine ({self.ocr_engine_type}/{self.ocr_lang}) is ready.")

        # If currently viewing a snapshot, return to live view first
        if self.using_snapshot: self.return_to_live()

        self.capturing = True
        # Start the capture loop in a separate thread
        self.capture_thread = threading.Thread(target=self.capture_process, daemon=True)
        self.capture_thread.start()

        # Update UI state
        if hasattr(self, "capture_tab"): self.capture_tab.on_capture_started()
        title = get_window_title(self.selected_hwnd) or f"HWND {self.selected_hwnd}"
        self.update_status(f"Capturing: {title}")

        # Ensure overlays are ready/rebuilt for the current ROIs
        if hasattr(self, "overlay_manager"): self.overlay_manager.rebuild_overlays()

    def stop_capture(self):
        """Stops the capture loop."""
        if not self.capturing: return # Already stopped
        print("Stop capture requested...")
        self.capturing = False # Signal the thread to stop
        # Wait a short time and then check if the thread has finished
        self.master.after(100, self._check_thread_and_finalize_stop)

    def _check_thread_and_finalize_stop(self):
        """Checks if the capture thread has stopped and finalizes UI updates."""
        if self.capture_thread and self.capture_thread.is_alive():
            # Thread still running, check again later
            self.master.after(100, self._check_thread_and_finalize_stop)
        else:
            # Thread finished, finalize UI state
            self.capture_thread = None
            # Use a flag to prevent multiple finalizations if called rapidly
            if not getattr(self, "_finalize_stop_in_progress", False):
                self._finalize_stop_in_progress = True
                self._finalize_stop_capture()

    def _finalize_stop_capture(self):
        """Updates UI elements after capture has fully stopped."""
        try:
            # Ensure flag is correct even if called directly
            if self.capturing:
                print("Warning: Finalizing stop capture while flag is still true.")
                self.capturing = False

            print("Finalizing stop capture UI updates...")
            # Update Capture tab buttons
            if hasattr(self, "capture_tab") and self.capture_tab.frame.winfo_exists():
                self.capture_tab.on_capture_stopped()
            # Hide overlays
            if hasattr(self, "overlay_manager"):
                self.overlay_manager.hide_all_overlays()
            self.update_status("Capture stopped.")
        finally:
            # Reset the finalization flag
            self._finalize_stop_in_progress = False

    def take_snapshot(self):
        """Freezes the display on the current frame for ROI definition."""
        # Check if there's a frame to snapshot
        if self.current_frame is None:
            if self.capturing:
                messagebox.showwarning("Warning", "Waiting for first frame to capture.", parent=self.master)
            else:
                messagebox.showwarning("Warning", "Start capture or select window first.", parent=self.master)
            return

        print("Taking snapshot...")
        self.snapshot_frame = self.current_frame.copy() # Store a copy
        self.using_snapshot = True
        self._display_frame(self.snapshot_frame) # Update canvas with the snapshot

        # Update UI state
        if hasattr(self, "capture_tab"): self.capture_tab.on_snapshot_taken()
        self.update_status("Snapshot taken. Define ROIs or return to live.")

    def return_to_live(self):
        """Resumes displaying live captured frames."""
        if not self.using_snapshot: return # Already live

        print("Returning to live view...")
        self.using_snapshot = False
        self.snapshot_frame = None # Clear the stored snapshot
        # Display the latest live frame if available, otherwise clear canvas
        self._display_frame(self.current_frame if self.current_frame is not None else None)

        # Update UI state
        if hasattr(self, "capture_tab"): self.capture_tab.on_live_view_resumed()
        if self.capturing:
            title = get_window_title(self.selected_hwnd) or f"HWND {self.selected_hwnd}"
            self.update_status(f"Capturing: {title}")
        else:
            self.update_status("Capture stopped.") # Or "Ready" if appropriate

    def toggle_roi_selection(self):
        """Activates or deactivates ROI definition mode."""
        if not self.roi_selection_active:
            # --- Pre-checks before activating ---
            if not self.selected_hwnd:
                messagebox.showwarning("Warning", "Select a game window first.", parent=self.master)
                return

            # Ensure a frame is available for drawing on
            frame_available = self.current_frame is not None or self.snapshot_frame is not None
            if not frame_available:
                if not self.capturing:
                    # Try to take a snapshot if not capturing
                    print("No frame available, attempting snapshot for ROI definition...")
                    frame = capture_window(self.selected_hwnd)
                    if frame is not None:
                        self.current_frame = frame # Store it even if not capturing
                        self.take_snapshot() # This sets using_snapshot = True
                    # Check if snapshot succeeded
                    if not self.using_snapshot:
                        messagebox.showwarning("Warning", "Could not capture frame for ROI definition.", parent=self.master)
                        return
                else:
                    # Capturing but no frame yet
                    messagebox.showwarning("Warning", "Waiting for first frame to be captured.", parent=self.master)
                    return

            # If capturing live, switch to snapshot mode automatically
            if self.capturing and not self.using_snapshot:
                self.take_snapshot()
            # If still not using snapshot (e.g., snapshot failed), abort
            if not self.using_snapshot:
                print("Failed to enter snapshot mode for ROI definition.")
                return

            # --- Activate ROI selection mode ---
            self.roi_selection_active = True
            if hasattr(self, "roi_tab"): self.roi_tab.on_roi_selection_toggled(True)
            # Status updated in roi_tab

        else:
            # --- Deactivate ROI selection mode ---
            self.roi_selection_active = False
            if hasattr(self, "roi_tab"): self.roi_tab.on_roi_selection_toggled(False)
            # Clean up drawing rectangle if it exists
            if self.roi_draw_rect_id:
                try: self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError: pass
            self.roi_draw_rect_id = None
            self.roi_start_coords = None
            self.update_status("ROI selection cancelled.")
            # Automatically return to live view if we were in snapshot mode
            if self.using_snapshot: self.return_to_live()

    def start_snip_mode(self):
        """Initiates the screen region selection for Snip & Translate."""
        if self.snip_mode_active:
            print("Snip mode already active.")
            return

        # Check OCR readiness
        if not self.ocr_engine_ready:
            messagebox.showwarning("OCR Not Ready", f"OCR engine ({self.ocr_engine_type}/{self.ocr_lang}) not initialized. Cannot use Snip & Translate.", parent=self.master)
            # Optionally trigger initialization again
            # self._trigger_ocr_initialization(self.ocr_engine_type, self.ocr_lang)
            return

        print("Starting Snip & Translate mode...")
        self.snip_mode_active = True
        self.update_status("Snip mode: Click and drag to select region, Esc to cancel.")

        try:
            # Create a full-screen, semi-transparent overlay window
            self.snip_overlay = tk.Toplevel(self.master)
            self.snip_overlay.attributes("-fullscreen", True)
            self.snip_overlay.attributes("-alpha", 0.3) # Make it see-through
            self.snip_overlay.overrideredirect(True) # No window decorations
            self.snip_overlay.attributes("-topmost", True) # Stay on top
            self.snip_overlay.configure(cursor="crosshair") # Set cursor
            self.snip_overlay.grab_set() # Capture all input events

            # Canvas for drawing the selection rectangle
            self.snip_canvas = tk.Canvas(self.snip_overlay, highlightthickness=0, bg="#888888") # Gray background
            self.snip_canvas.pack(fill=tk.BOTH, expand=True)

            # Bind mouse and keyboard events
            self.snip_canvas.bind("<ButtonPress-1>", self.on_snip_mouse_down)
            self.snip_canvas.bind("<B1-Motion>", self.on_snip_mouse_drag)
            self.snip_canvas.bind("<ButtonRelease-1>", self.on_snip_mouse_up)
            self.snip_overlay.bind("<Escape>", lambda e: self.cancel_snip_mode()) # Cancel on Escape key

            # Reset state variables
            self.snip_start_coords = None
            self.snip_rect_id = None
        except Exception as e:
            print(f"Error creating snip overlay: {e}")
            self.cancel_snip_mode() # Clean up if overlay creation fails

    def on_snip_mouse_down(self, event):
        """Handles mouse button press during snip mode."""
        if not self.snip_mode_active or not self.snip_canvas: return
        # Record starting position (screen coordinates)
        self.snip_start_coords = (event.x_root, event.y_root)
        # Delete previous rectangle if any
        if self.snip_rect_id:
            try: self.snip_canvas.delete(self.snip_rect_id)
            except tk.TclError: pass
        # Create a new rectangle starting and ending at the click point (canvas coordinates)
        self.snip_rect_id = self.snip_canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="red", width=2, tags="snip_rect"
        )

    def on_snip_mouse_drag(self, event):
        """Handles mouse drag during snip mode."""
        if not self.snip_mode_active or not self.snip_start_coords or not self.snip_rect_id or not self.snip_canvas: return

        # Get start coordinates (relative to canvas)
        try:
            # Use the stored screen coordinates for start point
            sx_root, sy_root = self.snip_start_coords
            # Convert start screen coords to current overlay's canvas coords
            start_x_canvas = sx_root - self.snip_overlay.winfo_rootx()
            start_y_canvas = sy_root - self.snip_overlay.winfo_rooty()
        except (tk.TclError, TypeError):
            # Failsafe if overlay gone or coords invalid
            self.snip_rect_id = None
            self.snip_start_coords = None
            return

        # Update rectangle coordinates with current mouse position (canvas coordinates)
        try:
            self.snip_canvas.coords(self.snip_rect_id, start_x_canvas, start_y_canvas, event.x, event.y)
        except tk.TclError:
            # Handle potential errors if canvas/rect is destroyed unexpectedly
            self.snip_rect_id = None
            self.snip_start_coords = None

    def on_snip_mouse_up(self, event):
        """Handles mouse button release during snip mode."""
        if not self.snip_mode_active or not self.snip_start_coords or not self.snip_rect_id or not self.snip_canvas:
            self.cancel_snip_mode() # Should not happen, but cancel defensively
            return

        try:
            # Get final rectangle coordinates (canvas coordinates)
            coords = self.snip_canvas.coords(self.snip_rect_id)
            if len(coords) == 4:
                # Convert canvas coordinates to screen coordinates
                overlay_x = self.snip_overlay.winfo_rootx()
                overlay_y = self.snip_overlay.winfo_rooty()
                x1_screen = int(coords[0]) + overlay_x
                y1_screen = int(coords[1]) + overlay_y
                x2_screen = int(coords[2]) + overlay_x
                y2_screen = int(coords[3]) + overlay_y

                # Ensure correct order (top-left, bottom-right)
                screen_coords_tuple = (min(x1_screen, x2_screen), min(y1_screen, y2_screen),
                                       max(x1_screen, x2_screen), max(y1_screen, y2_screen))

                # Finish snip mode and process the selected region
                self.finish_snip_mode(screen_coords_tuple)
            else:
                print("Invalid coordinates from snip rectangle.")
                self.cancel_snip_mode()
        except tk.TclError:
            print("Error getting snip rectangle coordinates (widget destroyed?).")
            self.cancel_snip_mode()
        except Exception as e:
            print(f"Error during snip mouse up: {e}")
            self.cancel_snip_mode()

    def cancel_snip_mode(self):
        """Cleans up the snip overlay and resets state."""
        if not self.snip_mode_active: return
        print("Cancelling snip mode.")
        if self.snip_overlay and self.snip_overlay.winfo_exists():
            try:
                self.snip_overlay.grab_release() # Release input grab
                self.snip_overlay.destroy()     # Destroy the overlay window
            except tk.TclError: pass # Ignore errors if already destroyed
        # Reset state variables
        self.snip_overlay = None
        self.snip_canvas = None
        self.snip_start_coords = None
        self.snip_rect_id = None
        self.snip_mode_active = False
        self.master.configure(cursor="") # Reset main window cursor
        self.update_status("Snip mode cancelled.")

    def finish_snip_mode(self, screen_coords_tuple):
        """Processes the selected screen region after snip mode ends."""
        x1, y1, x2, y2 = screen_coords_tuple
        width = x2 - x1
        height = y2 - y1
        min_snip_size = 5 # Minimum pixel dimension

        # Validate size
        if width < min_snip_size or height < min_snip_size:
            messagebox.showwarning("Snip Too Small", f"Selected region too small (min {min_snip_size}x{min_snip_size} px).", parent=self.master)
            self.cancel_snip_mode() # Cancel if too small
            return

        # Define the region dictionary for capture function
        monitor_region = {"left": x1, "top": y1, "width": width, "height": height}

        # Clean up the overlay *before* starting processing
        if self.snip_overlay and self.snip_overlay.winfo_exists():
            try:
                self.snip_overlay.grab_release()
                self.snip_overlay.destroy()
            except tk.TclError: pass
        self.snip_overlay = None
        self.snip_canvas = None
        self.snip_start_coords = None
        self.snip_rect_id = None
        self.snip_mode_active = False
        self.master.configure(cursor="") # Reset cursor

        # Update status and start processing in a thread
        self.update_status("Processing snipped region...")
        print(f"Snipped region (Screen Coords): {monitor_region}")
        threading.Thread(target=self._process_snip_thread, args=(monitor_region,), daemon=True).start()

    def _process_snip_thread(self, screen_region):
        """Background thread to capture, OCR, and translate the snipped region."""
        try:
            # 1. Capture the screen region
            img_bgr = capture_screen_region(screen_region)
            if img_bgr is None:
                self.master.after_idle(lambda: self.update_status("Snip Error: Failed to capture region."))
                return

            # 2. Perform OCR (using the currently selected engine and language)
            if not self.ocr_engine_ready:
                self.master.after_idle(lambda: self.update_status(f"Snip Error: OCR ({self.ocr_engine_type}/{self.ocr_lang}) not ready."))
                return

            print(f"[Snip OCR] Running OCR ({self.ocr_engine_type}/{self.ocr_lang})...")
            # Pass engine type and language to the unified extract_text function
            extracted_text = ocr.extract_text(img_bgr, lang=self.ocr_lang, engine_type=self.ocr_engine_type)
            print(f"[Snip OCR] Extracted: '{extracted_text}'")

            # Check for OCR errors indicated by the function
            if extracted_text.startswith("[") and "Error]" in extracted_text:
                self.master.after_idle(lambda: self.update_status(f"Snip: {extracted_text}"))
                self.master.after_idle(lambda: self.display_snip_translation(extracted_text, screen_region))
                return

            if not extracted_text:
                self.master.after_idle(lambda: self.update_status("Snip: No text found in region."))
                self.master.after_idle(lambda: self.display_snip_translation("[No text found]", screen_region))
                return

            # 3. Translate the extracted text
            config = self.translation_tab.get_translation_config() if hasattr(self, "translation_tab") else None
            if not config:
                self.master.after_idle(lambda: self.update_status("Snip Error: Translation config unavailable."))
                self.master.after_idle(lambda: self.display_snip_translation("[Translation Config Error]", screen_region))
                return

            # Use a dictionary for snip translation input
            snip_tag_name = "_snip_translate"
            snip_input_dict = {snip_tag_name: extracted_text}

            print("[Snip Translate] Translating...")
            translation_result = translate_text(
                stable_texts_dict=snip_input_dict, # Pass dictionary
                hwnd=None, # No specific game window for snip cache/context
                preset=config,
                target_language=config["target_language"],
                additional_context=config["additional_context"],
                context_limit=0, # No context history for snips
                skip_cache=True, # Don't cache snips
                skip_history=True, # Don't add snips to history
            )

            # 4. Process translation result
            final_text = "[Translation Error]"
            if isinstance(translation_result, dict):
                if "error" in translation_result:
                    final_text = f"Error: {translation_result['error']}"
                elif snip_tag_name in translation_result:
                    final_text = translation_result[snip_tag_name]
                elif len(translation_result) == 1: # Handle case where tag might be missing but only one result
                    final_text = next(iter(translation_result.values()), "[Parsing Failed]")

            print(f"[Snip Translate] Result: '{final_text}'")
            self.master.after_idle(lambda: self.update_status("Snip translation complete."))
            self.master.after_idle(lambda: self.display_snip_translation(final_text, screen_region))

        except Exception as e:
            error_msg = f"Error processing snip: {e}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            self.master.after_idle(lambda: self.update_status(f"Snip Error: {error_msg[:60]}..."))
            self.master.after_idle(lambda: self.display_snip_translation(f"[Error: {error_msg}]", screen_region))

    def display_snip_translation(self, text, region):
        """Creates or updates the floating window for snip results."""
        # Close existing snip window if open
        if self.current_snip_window and self.current_snip_window.winfo_exists():
            try: self.current_snip_window.destroy_window()
            except tk.TclError: pass
        self.current_snip_window = None

        try:
            # Get the specific configuration for the snip window
            snip_config = get_overlay_config_for_roi(SNIP_ROI_NAME)
            snip_config["enabled"] = True # Snip window is always enabled when created

            # Create the closable overlay window
            self.current_snip_window = ClosableFloatingOverlayWindow(
                self.master,
                roi_name=SNIP_ROI_NAME, # Use the special name
                initial_config=snip_config,
                manager_ref=None # Snip window is independent of the manager
            )

            # --- Position the snip window intelligently ---
            # Default position: to the right of the snipped region
            pos_x = region["left"] + region["width"] + 10
            pos_y = region["top"]

            # Ensure window is fully visible on screen
            self.current_snip_window.update_idletasks() # Ensure dimensions are calculated
            win_width = self.current_snip_window.winfo_width()
            win_height = self.current_snip_window.winfo_height()
            screen_width = self.master.winfo_screenwidth()
            screen_height = self.master.winfo_screenheight()

            # Adjust if it goes off-screen right
            if pos_x + win_width > screen_width:
                pos_x = region["left"] - win_width - 10 # Try left
            # Adjust if it goes off-screen bottom
            if pos_y + win_height > screen_height:
                pos_y = screen_height - win_height - 10 # Move up
            # Ensure it doesn't go off-screen top or left
            pos_x = max(0, pos_x)
            pos_y = max(0, pos_y)

            # Apply the calculated position
            self.current_snip_window.geometry(f"+{pos_x}+{pos_y}")

            # Update the text and ensure it's visible
            self.current_snip_window.update_text(text, global_overlays_enabled=True) # Force show

        except Exception as e:
            print(f"Error creating snip result window: {e}")
            import traceback
            traceback.print_exc()
            # Clean up partially created window if error occurred
            if self.current_snip_window:
                try: self.current_snip_window.destroy_window()
                except Exception: pass
            self.current_snip_window = None
            messagebox.showerror("Snip Error", f"Could not display snip result:\n{e}", parent=self.master)

    def capture_process(self):
        """The main loop running in a separate thread for capturing and processing."""
        last_frame_time = time.time()
        target_sleep_time = FRAME_DELAY
        print("Capture thread started.")

        while self.capturing:
            loop_start_time = time.time()
            frame_to_display = None

            try:
                # If in snapshot mode, just sleep briefly and continue
                if self.using_snapshot:
                    time.sleep(0.05) # Short sleep to prevent busy-waiting
                    continue

                # Check if the target window is still valid
                if not self.selected_hwnd or not win32gui.IsWindow(self.selected_hwnd):
                    print("Capture target window lost or invalid. Stopping.")
                    self.master.after_idle(self.handle_capture_failure)
                    break # Exit the loop

                # Capture the window content
                frame = capture_window(self.selected_hwnd)
                if frame is None:
                    # Handle capture failure (e.g., window minimized, protected content)
                    print("Warning: capture_window returned None. Retrying...")
                    time.sleep(0.5) # Wait a bit longer before retrying
                    continue

                # Store the latest frame
                self.current_frame = frame
                frame_to_display = frame # Use this frame for display update

                # Process ROIs if OCR is ready and ROIs exist
                if self.rois and self.ocr_engine_ready:
                    self._process_rois(frame) # Pass only frame, engine details are instance vars
                # elif not self.ocr_engine_ready:
                # Optional: Log that OCR is still initializing if needed
                # print("[Capture Loop] Waiting for OCR engine...")
                # pass

                # --- Frame Display Timing ---
                # Update display roughly at the target FPS
                current_time = time.time()
                if current_time - last_frame_time >= target_sleep_time:
                    if frame_to_display is not None:
                        # Send a copy to the main thread for display
                        frame_copy = frame_to_display.copy()
                        self.master.after_idle(lambda f=frame_copy: self._display_frame(f))
                    last_frame_time = current_time

                # --- Loop Delay Calculation ---
                elapsed = time.time() - loop_start_time
                sleep_duration = max(0.001, target_sleep_time - elapsed) # Ensure positive sleep
                time.sleep(sleep_duration)

            except Exception as e:
                print(f"!!! Error in capture loop: {e}")
                import traceback
                traceback.print_exc()
                # Update status bar from main thread
                self.master.after_idle(lambda msg=str(e): self.update_status(f"Capture loop error: {msg[:60]}..."))
                time.sleep(1) # Pause briefly after an error

        print("Capture thread finished or exited.")

    def handle_capture_failure(self):
        """Called from main thread if capture loop detects window loss."""
        if self.capturing: # Only act if we thought we were capturing
            self.update_status("Window lost or uncapturable. Stopping capture.")
            print("Capture target window became invalid.")
            self.stop_capture() # Initiate the stop sequence

    def on_canvas_resize(self, event=None):
        """Handles canvas resize events, debouncing redraw."""
        if self._resize_job:
            self.master.after_cancel(self._resize_job)
        # Schedule the actual redraw after a short delay
        self._resize_job = self.master.after(100, self._perform_resize_redraw)

    def _perform_resize_redraw(self):
        """Redraws the frame on the canvas after resizing."""
        self._resize_job = None # Reset the job ID
        if not self.canvas.winfo_exists(): return # Check if canvas still exists

        # Determine which frame to display (snapshot or live)
        frame = self.snapshot_frame if self.using_snapshot else self.current_frame
        self._display_frame(frame) # Call the display function

    def _display_frame(self, frame):
        """Displays the given frame (NumPy array) on the canvas."""
        if not hasattr(self, "canvas") or not self.canvas.winfo_exists(): return

        # Clear previous content
        self.canvas.delete("display_content")
        self.display_frame_tk = None # Release previous PhotoImage reference

        # Handle case where frame is None (e.g., before capture starts)
        if frame is None:
            try:
                cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
                if cw > 1 and ch > 1: # Ensure canvas has valid dimensions
                    self.canvas.create_text(
                        cw / 2, ch / 2,
                        text="No Image\n(Select Window & Start Capture)",
                        fill="gray50", tags="display_content", justify=tk.CENTER
                    )
            except Exception: pass # Ignore errors during placeholder text creation
            return

        try:
            fh, fw = frame.shape[:2]
            cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()

            # Check for invalid dimensions
            if fw <= 0 or fh <= 0 or cw <= 1 or ch <= 1: return

            # Calculate scaling factor to fit frame within canvas
            scale = min(cw / fw, ch / fh)
            nw, nh = int(fw * scale), int(fh * scale)

            # Check for invalid scaled dimensions
            if nw < 1 or nh < 1: return

            # Store scaling and position info
            self.scale_x, self.scale_y = scale, scale
            self.frame_display_coords = {
                "x": (cw - nw) // 2, "y": (ch - nh) // 2, # Center the image
                "w": nw, "h": nh
            }

            # Resize image using OpenCV (linear interpolation is usually good enough)
            resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
            # Convert BGR (OpenCV) to RGB (PIL)
            img = Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))
            # Convert PIL image to Tkinter PhotoImage
            self.display_frame_tk = ImageTk.PhotoImage(image=img)

            # Display the image on the canvas
            self.canvas.create_image(
                self.frame_display_coords["x"], self.frame_display_coords["y"],
                anchor=tk.NW, image=self.display_frame_tk,
                tags=("display_content", "frame_image") # Add tags for easy deletion/identification
            )

            # Draw ROI rectangles on top
            self._draw_rois()

        except Exception as e:
            print(f"Error displaying frame: {e}")
            # Attempt to display error message on canvas
            try:
                cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
                self.canvas.create_text(cw/2, ch/2, text=f"Display Error:\n{e}", fill="red", tags="display_content")
            except: pass # Ignore errors during error display

    def _process_rois(self, frame):
        """Extracts text from ROIs, checks stability, and triggers translation."""
        # No need to pass ocr_engine, use self.ocr_engine_type and self.ocr_lang
        if frame is None or not self.ocr_engine_ready:
            # print("_process_rois skipped: No frame or OCR not ready.")
            return

        extracted = {}
        stable_changed = False
        new_stable = self.stable_texts.copy()

        for roi in self.rois:
            if roi.name == SNIP_ROI_NAME: continue # Skip the special snip ROI

            roi_img_original = roi.extract_roi(frame)
            roi_img_processed = roi.apply_color_filter(roi_img_original) # Apply filter

            if roi_img_processed is None or roi_img_processed.size == 0:
                extracted[roi.name] = ""
                # Reset history and stability if ROI becomes invalid
                if roi.name in self.text_history: del self.text_history[roi.name]
                if roi.name in new_stable:
                    del new_stable[roi.name]
                    stable_changed = True
                continue

            try:
                # Call the unified OCR function from utils.ocr
                text = ocr.extract_text(roi_img_processed, lang=self.ocr_lang, engine_type=self.ocr_engine_type)
                extracted[roi.name] = text

                # --- Stability Check ---
                history = self.text_history.get(roi.name, {"text": "", "count": 0})
                if text == history["text"]:
                    history["count"] += 1
                else:
                    history = {"text": text, "count": 1}
                self.text_history[roi.name] = history

                is_now_stable = history["count"] >= self.stable_threshold
                was_stable = roi.name in self.stable_texts
                current_stable_text = self.stable_texts.get(roi.name)

                if is_now_stable:
                    # Mark as stable if threshold met and text is different from previous stable text
                    if not was_stable or current_stable_text != text:
                        new_stable[roi.name] = text
                        stable_changed = True
                elif was_stable:
                    # If it was stable but no longer meets threshold (text changed), remove it
                    if roi.name in new_stable:
                        del new_stable[roi.name]
                        stable_changed = True
                # --- End Stability Check ---

            except Exception as e:
                # Handle errors during OCR for a specific ROI
                print(f"!!! OCR Error for ROI {roi.name}: {e}")
                extracted[roi.name] = "[OCR Error]"
                self.text_history[roi.name] = {"text": "[OCR Error]", "count": 1}
                if roi.name in new_stable:
                    del new_stable[roi.name]
                    stable_changed = True

        # --- Update UI and Trigger Translation (Scheduled on Main Thread) ---
        if hasattr(self, "text_tab") and self.text_tab.frame.winfo_exists():
            # Update the "Live Text" tab
            self.master.after_idle(lambda et=extracted.copy(): self.text_tab.update_text(et))

        if stable_changed:
            self.stable_texts = new_stable
            if hasattr(self, "stable_text_tab") and self.stable_text_tab.frame.winfo_exists():
                # Update the "Stable Text" tab
                self.master.after_idle(lambda st=self.stable_texts.copy(): self.stable_text_tab.update_text(st))

            # --- Auto-Translate Trigger Logic ---
            if hasattr(self, "translation_tab") and self.translation_tab.frame.winfo_exists() and self.translation_tab.is_auto_translate_enabled():
                # Get all user-defined ROI names (excluding the snip one)
                user_roi_names = {roi.name for roi in self.rois if roi.name != SNIP_ROI_NAME}

                # Check if user ROIs exist AND if all of them are keys in the *new* stable_texts
                # Also ensure stable_texts is not empty overall
                all_rois_are_stable = bool(user_roi_names) and user_roi_names.issubset(self.stable_texts.keys()) and bool(self.stable_texts)

                if all_rois_are_stable:
                    # All conditions met: Trigger translation
                    print("[Auto-Translate] All ROIs stable, triggering translation.")
                    # Use after_idle to ensure it runs on the main thread
                    self.master.after_idle(self.translation_tab.perform_translation)
                else:
                    # Not all ROIs are stable, or no user ROIs exist, or stable_texts became empty.
                    # Check if the reason is that stable_texts became empty.
                    if not self.stable_texts: # If the stable text dictionary is now empty
                        print("[Auto-Translate] Stable text cleared, clearing overlays.")
                        if hasattr(self, "overlay_manager"):
                            self.master.after_idle(self.overlay_manager.clear_all_overlays)
                        # Also clear the translation preview
                        if hasattr(self, "translation_tab"):
                            self.master.after_idle(lambda: self.translation_tab.update_translation_results({}, "[Waiting for stable text...]"))
                    # else:
                    # Some ROIs might be stable, but not all. Do nothing.
                    # print("[Auto-Translate] Waiting for all ROIs to stabilize.") # Optional log
            # --- End of Auto-Translate Logic ---


    def _draw_rois(self):
        """Draws ROI rectangles and labels on the canvas."""
        if not hasattr(self, "canvas") or not self.canvas.winfo_exists() or self.frame_display_coords["w"] <= 0:
            return

        ox, oy = self.frame_display_coords["x"], self.frame_display_coords["y"]
        # Clear only ROI drawings, not the frame image
        self.canvas.delete("roi_drawing")

        for i, roi in enumerate(self.rois):
            if roi.name == SNIP_ROI_NAME: continue # Don't draw the snip ROI

            try:
                # Calculate display coordinates based on scaling and offset
                dx1 = int(roi.x1 * self.scale_x) + ox
                dy1 = int(roi.y1 * self.scale_y) + oy
                dx2 = int(roi.x2 * self.scale_x) + ox
                dy2 = int(roi.y2 * self.scale_y) + oy

                # Draw rectangle
                self.canvas.create_rectangle(
                    dx1, dy1, dx2, dy2,
                    outline="lime", width=1, # Lime green outline
                    tags=("display_content", "roi_drawing", f"roi_{i}") # Add tags
                )
                # Draw label
                self.canvas.create_text(
                    dx1 + 3, dy1 + 1, # Position slightly inside top-left corner
                    text=roi.name, fill="lime", anchor=tk.NW,
                    font=("TkDefaultFont", 8), # Small font
                    tags=("display_content", "roi_drawing", f"roi_label_{i}")
                )
            except Exception as e:
                print(f"Error drawing ROI {roi.name}: {e}")

    # --- Mouse Events for ROI Definition ---

    def on_mouse_down(self, event):
        """Handles mouse button press on the canvas (for ROI definition)."""
        # Only active during ROI definition AND when using a snapshot
        if not self.roi_selection_active or not self.using_snapshot: return

        # Check if click is within the displayed image bounds
        img_x, img_y = self.frame_display_coords["x"], self.frame_display_coords["y"]
        img_w, img_h = self.frame_display_coords["w"], self.frame_display_coords["h"]
        if not (img_x <= event.x < img_x + img_w and img_y <= event.y < img_y + img_h):
            # Click outside image, cancel drawing
            self.roi_start_coords = None
            if self.roi_draw_rect_id:
                try: self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError: pass
            self.roi_draw_rect_id = None
            return

        # Record start coordinates (canvas coords)
        self.roi_start_coords = (event.x, event.y)
        # Delete previous drawing rectangle if it exists
        if self.roi_draw_rect_id:
            try: self.canvas.delete(self.roi_draw_rect_id)
            except tk.TclError: pass
        # Create new rectangle starting and ending at the click point
        self.roi_draw_rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="red", width=2, tags="roi_drawing" # Red outline for drawing
        )

    def on_mouse_drag(self, event):
        """Handles mouse drag on the canvas (for ROI definition)."""
        if not self.roi_selection_active or not self.roi_start_coords or not self.roi_draw_rect_id: return

        sx, sy = self.roi_start_coords
        # Clamp current coordinates to be within the image bounds on canvas
        img_x, img_y = self.frame_display_coords["x"], self.frame_display_coords["y"]
        img_w, img_h = self.frame_display_coords["w"], self.frame_display_coords["h"]
        cx = max(img_x, min(event.x, img_x + img_w))
        cy = max(img_y, min(event.y, img_y + img_h))

        try:
            # Also clamp start coordinates just in case they were slightly off
            clamped_sx = max(img_x, min(sx, img_x + img_w))
            clamped_sy = max(img_y, min(sy, img_y + img_h))
            # Update the drawing rectangle coordinates
            self.canvas.coords(self.roi_draw_rect_id, clamped_sx, clamped_sy, cx, cy)
        except tk.TclError:
            # Handle error if canvas/rectangle destroyed unexpectedly
            self.roi_draw_rect_id = None
            self.roi_start_coords = None

    def on_mouse_up(self, event):
        """Handles mouse button release on the canvas (completes ROI definition)."""
        # Check if ROI definition was active and started correctly
        if not self.roi_selection_active or not self.roi_start_coords or not self.roi_draw_rect_id:
            # Clean up potential dangling rectangle if drag never happened
            if self.roi_draw_rect_id:
                try: self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError: pass
            self.roi_draw_rect_id = None
            self.roi_start_coords = None
            # If selection was active but failed, deactivate it
            if self.roi_selection_active:
                self.roi_selection_active = False
                if hasattr(self, "roi_tab"): self.roi_tab.on_roi_selection_toggled(False)
                if self.using_snapshot: self.return_to_live() # Exit snapshot if active
            return

        # Get final coordinates of the drawing rectangle
        try: coords = self.canvas.coords(self.roi_draw_rect_id)
        except tk.TclError: coords = None # Handle error if widget destroyed

        # Clean up drawing rectangle and reset state *before* processing ROI
        if self.roi_draw_rect_id:
            try: self.canvas.delete(self.roi_draw_rect_id)
            except tk.TclError: pass
        self.roi_draw_rect_id = None
        self.roi_start_coords = None
        self.roi_selection_active = False # Deactivate selection mode
        if hasattr(self, "roi_tab"): self.roi_tab.on_roi_selection_toggled(False)

        # Validate coordinates and size
        if coords is None or len(coords) != 4:
            print("ROI definition failed (invalid coords).")
            if self.using_snapshot: self.return_to_live() # Exit snapshot
            return

        x1d, y1d, x2d, y2d = map(int, coords)
        min_size = 5 # Minimum size in pixels on the canvas
        if abs(x2d - x1d) < min_size or abs(y2d - y1d) < min_size:
            messagebox.showwarning("ROI Too Small", f"Defined region too small (min {min_size}x{min_size} px required).", parent=self.master)
            if self.using_snapshot: self.return_to_live() # Exit snapshot
            return

        # --- Get ROI Name ---
        roi_name = self.roi_tab.roi_name_entry.get().strip()
        overwrite_name = None
        existing_names = {r.name for r in self.rois if r.name != SNIP_ROI_NAME}

        if not roi_name: # Generate default name if empty
            i = 1
            roi_name = f"roi_{i}"
            while roi_name in existing_names: i += 1; roi_name = f"roi_{i}"
        elif roi_name in existing_names: # Check for overwrite
            if not messagebox.askyesno("ROI Exists", f"An ROI named '{roi_name}' already exists. Overwrite it?", parent=self.master):
                if self.using_snapshot: self.return_to_live() # Exit snapshot if user cancels
                return
            overwrite_name = roi_name
        elif roi_name == SNIP_ROI_NAME: # Check for reserved name
            messagebox.showerror("Invalid Name", f"Cannot use the reserved name '{SNIP_ROI_NAME}'. Please choose another.", parent=self.master)
            if self.using_snapshot: self.return_to_live() # Exit snapshot
            return

        # --- Convert Canvas Coords to Original Frame Coords ---
        ox, oy = self.frame_display_coords["x"], self.frame_display_coords["y"]
        # Coords relative to the displayed image's top-left corner
        rx1, ry1 = min(x1d, x2d) - ox, min(y1d, y2d) - oy
        rx2, ry2 = max(x1d, x2d) - ox, max(y1d, y2d) - oy

        # Check for valid scaling factor
        if self.scale_x <= 0 or self.scale_y <= 0:
            print("Error: Invalid scaling factor during ROI creation.")
            if self.using_snapshot: self.return_to_live() # Exit snapshot
            return

        # Convert relative display coords back to original frame coords
        orig_x1, orig_y1 = int(rx1 / self.scale_x), int(ry1 / self.scale_y)
        orig_x2, orig_y2 = int(rx2 / self.scale_x), int(ry2 / self.scale_y)

        # Final size check in original coordinates
        if abs(orig_x2 - orig_x1) < 1 or abs(orig_y2 - orig_y1) < 1:
            messagebox.showwarning("ROI Too Small", "Calculated ROI size is too small in original frame.", parent=self.master)
            if self.using_snapshot: self.return_to_live() # Exit snapshot
            return

        # --- Create or Update ROI Object ---
        new_roi = ROI(roi_name, orig_x1, orig_y1, orig_x2, orig_y2)

        if overwrite_name:
            found = False
            for i, r in enumerate(self.rois):
                if r.name == overwrite_name:
                    # Preserve color filter settings when overwriting geometry
                    new_roi.color_filter_enabled = r.color_filter_enabled
                    new_roi.target_color = r.target_color
                    new_roi.replacement_color = r.replacement_color
                    new_roi.color_threshold = r.color_threshold
                    self.rois[i] = new_roi
                    found = True
                    break
            if not found: # Should not happen if overwrite_name was set
                print(f"Warning: Tried to overwrite '{overwrite_name}' but not found.")
                self.rois.append(new_roi) # Add as new if somehow not found
        else:
            # Add the new ROI to the list
            self.rois.append(new_roi)

        print(f"Created/Updated ROI: {new_roi.to_dict()}")

        # --- Update UI and State ---
        if hasattr(self, "roi_tab"): self.roi_tab.update_roi_list() # Update listbox
        self._draw_rois() # Redraw ROIs on canvas
        action = "created" if not overwrite_name else "updated"
        self.update_status(f"ROI '{roi_name}' {action}. Remember to save ROI settings.")

        # Suggest next ROI name in the entry box
        if hasattr(self, "roi_tab"):
            existing_names_now = {r.name for r in self.rois if r.name != SNIP_ROI_NAME}
            next_name = "dialogue" if "dialogue" not in existing_names_now else ""
            if not next_name: # Generate roi_N if dialogue exists
                i = 1
                next_name = f"roi_{i}"
                while next_name in existing_names_now: i += 1; next_name = f"roi_{i}"
            self.roi_tab.roi_name_entry.delete(0, tk.END)
            self.roi_tab.roi_name_entry.insert(0, next_name)

        # Create or update the corresponding overlay window
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.create_overlay_for_roi(new_roi)

        # Return to live view if we were in snapshot mode
        if self.using_snapshot: self.return_to_live()

    # --- Floating Controls and Closing ---

    def show_floating_controls(self):
        """Shows or brings the floating controls window to the front."""
        try:
            if self.floating_controls is None or not self.floating_controls.winfo_exists():
                self.floating_controls = FloatingControls(self.master, self)
            else:
                self.floating_controls.deiconify() # Ensure it's not minimized/withdrawn
                self.floating_controls.lift()      # Bring to top
                self.floating_controls.update_button_states() # Sync button states
        except Exception as e:
            print(f"Error showing floating controls: {e}")
            self.update_status("Error showing controls.")

    def hide_floating_controls(self):
        """Hides the floating controls window."""
        if self.floating_controls and self.floating_controls.winfo_exists():
            self.floating_controls.withdraw()

    def on_close(self):
        """Handles the application closing sequence."""
        print("Close requested...")
        # Cancel any active modes
        if self.snip_mode_active: self.cancel_snip_mode()
        if self.roi_selection_active: self.toggle_roi_selection()

        # Close the snip result window if it's open
        if self.current_snip_window and self.current_snip_window.winfo_exists():
            try: self.current_snip_window.destroy_window()
            except Exception: pass
            self.current_snip_window = None

        # Stop capture if running and wait for it to finish
        if self.capturing:
            self.update_status("Stopping capture before closing...")
            self.stop_capture()
            # Schedule check to finalize close after capture stops
            self.master.after(500, self.check_capture_stopped_and_close)
        else:
            # If not capturing, proceed to final close steps directly
            self._finalize_close()

    def check_capture_stopped_and_close(self):
        """Checks if capture thread is stopped, then finalizes close."""
        # Check if capture flag is off AND thread is gone or dead
        if not self.capturing and (self.capture_thread is None or not self.capture_thread.is_alive()):
            self._finalize_close()
        else:
            # Still waiting for capture to stop
            print("Waiting for capture thread to stop...")
            self.master.after(500, self.check_capture_stopped_and_close)

    def _finalize_close(self):
        """Performs final cleanup before exiting."""
        print("Finalizing close...")
        self.capturing = False # Ensure flag is false

        # Destroy all overlay windows managed by the manager
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.destroy_all_overlays()

        # Save floating controls position and destroy the window
        if self.floating_controls and self.floating_controls.winfo_exists():
            try:
                # Only save position if the window is visible (not withdrawn)
                if self.floating_controls.state() == "normal":
                    geo = self.floating_controls.geometry()
                    parts = geo.split('+')
                    if len(parts) == 3: # Format like WxH+X+Y
                        x_str, y_str = parts[1], parts[2]
                        # Basic check if coordinates look valid
                        if x_str.isdigit() and y_str.isdigit():
                            set_setting("floating_controls_pos", f"{x_str},{y_str}")
                        else: print(f"Warn: Invalid floating controls coordinates in geometry: {geo}")
                    else: print(f"Warn: Could not parse floating controls geometry: {geo}")
            except Exception as e: print(f"Error saving floating controls position: {e}")
            # Destroy the window regardless of saving position
            try: self.floating_controls.destroy()
            except tk.TclError: pass # Ignore error if already destroyed

        # Ensure snip result window is destroyed (double check)
        if self.current_snip_window and self.current_snip_window.winfo_exists():
            try: self.current_snip_window.destroy_window()
            except Exception: pass

        print("Exiting application.")
        try:
            # Standard Tkinter exit sequence
            self.master.quit()
            self.master.destroy()
        except tk.TclError: pass # Ignore errors if widgets already gone
        except Exception as e: print(f"Error during final window destruction: {e}")

# --- END OF FILE app.py ---
```