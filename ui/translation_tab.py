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
        # Allow saving via Return unless Shift is held
        if event and event.keysym == 'Return' and (event.state & 0x0001): # Shift key modifier
            # Allow default Shift+Return behavior (insert newline)
            return
        elif event and event.keysym == 'Return':
            # Prevent default Return behavior (newline insertion) and trigger save
            pass # Handled below
        elif event and event.type == tk.EventType.FocusOut:
            # Trigger save on focus out
            pass # Handled below
        elif event:
            # Ignore other events
            return

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

        # Prevent newline insertion on regular Return press
        if event and event.keysym == 'Return' and not (event.state & 0x0001):
            return "break" # Stop the event propagation

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
        # Prevent newline insertion if triggered by Return key
        if event and event.keysym == 'Return':
            return "break"

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

            # System prompt REMOVED from UI

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

    def _start_translation_thread(self, force_recache=False, user_comment=None): # Added user_comment
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
        # Use a copy to avoid potential race conditions if app.stable_texts changes mid-thread
        texts_to_translate = self.app.stable_texts.copy()
        # Filter out empty texts *after* copying
        texts_to_translate = {name: text for name, text in texts_to_translate.items() if text and text.strip()}


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

        status_msg = "Translating..."
        if user_comment:
            status_msg = "Translating with comment..."
        if force_recache:
            status_msg = "Forcing retranslation..."
            if user_comment:
                status_msg = "Forcing retranslation with comment..."

        self.app.update_status(status_msg)
        try:
            if self.translation_display.winfo_exists():
                self.translation_display.config(state=tk.NORMAL)
                self.translation_display.delete(1.0, tk.END)
                self.translation_display.insert(tk.END, f"{status_msg}\n")
                self.translation_display.config(state=tk.DISABLED)
        except tk.TclError: pass

        # Update overlays to show "..." while translating
        if hasattr(self.app, 'overlay_manager'):
            for roi_name in texts_to_translate:
                self.app.overlay_manager.update_overlay_text(roi_name, "...")

        # Keep a reference to the input dictionary for preview construction
        input_texts_for_preview = texts_to_translate.copy()

        # Define the thread function locally to capture variables
        def translation_thread_task():
            try:
                # Pass the dictionary directly and the comment
                translated_segments = translate_text(
                    stable_texts_dict=texts_to_translate, # Pass the filtered dictionary
                    hwnd=current_hwnd,
                    preset=config,
                    target_language=config["target_language"],
                    additional_context=config["additional_context"],
                    context_limit=config.get("context_limit", 10),
                    force_recache=force_recache,
                    user_comment=user_comment # Pass the comment here
                )
                if "error" in translated_segments:
                    error_msg = translated_segments["error"]
                    print(f"Translation API Error: {error_msg}")
                    self.app.master.after_idle(lambda: self.update_translation_display_error(error_msg))
                    if hasattr(self.app, 'overlay_manager'):
                        first_roi = next(iter(texts_to_translate), None)
                        if first_roi:
                            self.app.master.after_idle(lambda name=first_roi: self.app.overlay_manager.update_overlay_text(name, f"Error!"))
                        for r_name in texts_to_translate:
                            if r_name != first_roi:
                                self.app.master.after_idle(lambda n=r_name: self.app.overlay_manager.update_overlay_text(n, ""))
                else:
                    print("Translation successful.")
                    preview_lines = []
                    # Use the original input dictionary keys for iteration order consistency
                    # Sort keys for deterministic preview order
                    sorted_roi_names = sorted(input_texts_for_preview.keys())

                    for roi_name in sorted_roi_names:
                        # Get original text from the input dictionary used for this translation call
                        original_text = input_texts_for_preview.get(roi_name, "")
                        translated_text = translated_segments.get(roi_name) # Get from result dict

                        # We already filtered empty original_text, so this check might be redundant
                        # but keep it for safety
                        if original_text:
                            preview_lines.append(f"[{roi_name}]:")
                            # Append the full translated text, preserving newlines
                            preview_lines.append(translated_text if translated_text else "[Translation N/A]")
                            preview_lines.append("") # Add blank line separator

                    # Join lines for the final preview string
                    preview_text = "\n".join(preview_lines).strip()
                    # Schedule UI update on main thread
                    self.app.master.after_idle(lambda seg=translated_segments, prev=preview_text: self.update_translation_results(seg, prev))
            except Exception as e:
                error_msg = f"Unexpected error during translation thread: {str(e)}"
                print(error_msg)
                import traceback
                traceback.print_exc()
                self.app.master.after_idle(lambda: self.update_translation_display_error(error_msg))
                if hasattr(self.app, 'overlay_manager'): self.app.master.after_idle(self.app.overlay_manager.clear_all_overlays)

        threading.Thread(target=translation_thread_task, daemon=True).start()

    def perform_translation(self):
        """Translate the stable text using the current settings (uses cache)."""
        self._start_translation_thread(force_recache=False, user_comment=None)

    def perform_force_translation(self):
        """Force re-translation of the stable text, skipping cache check but updating cache."""
        self._start_translation_thread(force_recache=True, user_comment=None)

    def perform_translation_with_comment(self, comment, force_recache=False):
        """Translate the stable text, including a user comment (cache behavior depends on force_recache)."""
        self._start_translation_thread(force_recache=force_recache, user_comment=comment)

    def update_translation_results(self, translated_segments, preview_text):
        """Update the preview display and overlays with translation results. Runs in main thread."""
        self.app.update_status("Translation complete.")
        # print(f"[PREVIEW DEBUG] Updating display with text:\n{repr(preview_text)}") # Add repr() for debugging
        try:
            if self.translation_display.winfo_exists():
                self.translation_display.config(state=tk.NORMAL)
                self.translation_display.delete(1.0, tk.END)
                # Ensure preview_text is a string before inserting
                text_to_insert = preview_text if isinstance(preview_text, str) else "[Invalid Preview Format]"
                self.translation_display.insert(tk.END, text_to_insert if text_to_insert else "[No translation received]")
                self.translation_display.config(state=tk.DISABLED)
        except tk.TclError:
            print("[PREVIEW DEBUG] TclError updating translation display (widget destroyed?).")
            pass
        except Exception as e:
            print(f"[PREVIEW DEBUG] Error updating translation display: {e}")

        if hasattr(self.app, 'overlay_manager'): self.app.overlay_manager.update_overlays(translated_segments)
        self.last_translation_result = translated_segments
        # Store the input that led to this result (use the app's current stable_texts)
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
        # Check if hwnd is None (no window selected) - still allow reset but inform user
        confirm_msg = "Are you sure you want to reset the translation context history"
        if current_hwnd:
            confirm_msg += " for the current game?\n(This will delete the saved history file)"
        else:
            confirm_msg += "?\n(No game window selected, cannot delete specific file)"
        confirm_msg += "."

        if messagebox.askyesno("Confirm Reset Context", confirm_msg, parent=self.app.master):
            result = reset_context(current_hwnd) # Pass hwnd (even if None)
            messagebox.showinfo("Context Reset", result, parent=self.app.master)
            self.app.update_status("Translation context reset.")