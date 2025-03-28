import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import copy
from ui.base import BaseTab
from utils.translation import translate_text, clear_all_cache, clear_current_game_cache, reset_context
from utils.config import save_translation_presets, load_translation_presets, _get_game_hash
from utils.settings import get_setting, set_setting, update_settings

DEFAULT_PRESETS = {
    "OpenAI (GPT-3.5)": {
        "api_url": "https://api.openai.com/v1/chat/completions",
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
        "api_url": "https://api.openai.com/v1/chat/completions",
        "api_key": "",
        "model": "gpt-4",
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
        "api_url": "https://api.anthropic.com/v1/messages",
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
        "max_tokens": 1000,
        "context_limit": 10
    },
    "Mistral": {
        "api_url": "https://api.mistral.ai/v1/chat/completions",
        "api_key": "",
        "model": "mistral-medium-latest",
        "system_prompt": (
            "You are a professional translator. Translate the following text accurately and return the output in this format:\n"
            "<|1|> translated text for segment 1\n"
            "<|2|> translated text for segment 2\n"
            "Only include the tagged lines."
        ),
        "temperature": 0.3,
        "top_p": 0.95,
        "max_tokens": 1000,
        "context_limit": 10
    },
    "Local Model (LM Studio/Ollama)": {
        "api_url": "http://localhost:1234/v1/chat/completions",
        "api_key": "not-needed",
        "model": "loaded-model-name",
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
    def setup_ui(self):
        self.target_language = get_setting("target_language", "en")
        self.auto_translate_enabled = get_setting("auto_translate", False)
        last_preset_name = get_setting("last_preset_name")

        self.settings_frame = ttk.LabelFrame(self.frame, text="Translation Settings", padding="10")
        self.settings_frame.pack(fill=tk.X, pady=10)

        preset_frame = ttk.Frame(self.settings_frame)
        preset_frame.pack(fill=tk.X, pady=5)

        ttk.Label(preset_frame, text="Preset:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)

        self.translation_presets = load_translation_presets()
        if not self.translation_presets:
            self.translation_presets = copy.deepcopy(DEFAULT_PRESETS)

        self.preset_names = sorted(list(self.translation_presets.keys()))
        self.preset_combo = ttk.Combobox(preset_frame, values=self.preset_names, width=30, state="readonly")
        preset_index = -1
        if last_preset_name and last_preset_name in self.preset_names:
            try:
                preset_index = self.preset_names.index(last_preset_name)
            except ValueError:
                pass
        if preset_index != -1:
            self.preset_combo.current(preset_index)
        elif self.preset_names:
            self.preset_combo.current(0)

        self.preset_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        self.preset_combo.bind("<<ComboboxSelected>>", self.on_preset_selected)

        btn_frame = ttk.Frame(preset_frame)
        btn_frame.grid(row=0, column=2, padx=5, pady=5)

        self.save_preset_btn = ttk.Button(btn_frame, text="Save", command=self.save_preset)
        self.save_preset_btn.pack(side=tk.LEFT, padx=2)
        self.save_as_preset_btn = ttk.Button(btn_frame, text="Save As...", command=self.save_preset_as)
        self.save_as_preset_btn.pack(side=tk.LEFT, padx=2)
        self.delete_preset_btn = ttk.Button(btn_frame, text="Delete", command=self.delete_preset)
        self.delete_preset_btn.pack(side=tk.LEFT, padx=2)

        preset_frame.columnconfigure(1, weight=1)

        self.settings_notebook = ttk.Notebook(self.settings_frame)
        self.settings_notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        self.basic_frame = ttk.Frame(self.settings_notebook, padding=10)
        self.settings_notebook.add(self.basic_frame, text="General Settings")

        ttk.Label(self.basic_frame, text="Target Language:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.target_lang_entry = ttk.Entry(self.basic_frame, width=15)
        self.target_lang_entry.insert(0, self.target_language)
        self.target_lang_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        self.target_lang_entry.bind("<FocusOut>", self.save_basic_settings)
        self.target_lang_entry.bind("<Return>", self.save_basic_settings)

        ttk.Label(self.basic_frame, text="Additional Context (Game Specific):", anchor=tk.NW).grid(row=1, column=0, sticky=tk.NW, padx=5, pady=5)
        self.additional_context_text = tk.Text(self.basic_frame, width=40, height=5, wrap=tk.WORD)
        self.additional_context_text.grid(row=1, column=1, sticky=tk.NSEW, padx=5, pady=5)
        scroll_ctx = ttk.Scrollbar(self.basic_frame, command=self.additional_context_text.yview)
        scroll_ctx.grid(row=1, column=2, sticky=tk.NS, pady=5)
        self.additional_context_text.config(yscrollcommand=scroll_ctx.set)
        self.additional_context_text.bind("<FocusOut>", self.save_context_for_current_game)
        self.additional_context_text.bind("<Return>", self.save_context_for_current_game)
        self.additional_context_text.bind("<Shift-Return>", lambda e: self.additional_context_text.insert(tk.INSERT, '\n'))

        self.basic_frame.columnconfigure(1, weight=1)
        self.basic_frame.rowconfigure(1, weight=1)

        self.preset_settings_frame = ttk.Frame(self.settings_notebook, padding=10)
        self.settings_notebook.add(self.preset_settings_frame, text="Preset Details")

        ttk.Label(self.preset_settings_frame, text="API Key:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.api_key_entry = ttk.Entry(self.preset_settings_frame, width=40, show="*")
        self.api_key_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=5)

        ttk.Label(self.preset_settings_frame, text="API URL:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.api_url_entry = ttk.Entry(self.preset_settings_frame, width=40)
        self.api_url_entry.grid(row=1, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=5)

        ttk.Label(self.preset_settings_frame, text="Model:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.model_entry = ttk.Entry(self.preset_settings_frame, width=40)
        self.model_entry.grid(row=2, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=5)

        ttk.Label(self.preset_settings_frame, text="System Prompt:", anchor=tk.NW).grid(row=3, column=0, sticky=tk.NW, padx=5, pady=5)
        self.system_prompt_text = tk.Text(self.preset_settings_frame, width=50, height=6, wrap=tk.WORD)
        self.system_prompt_text.grid(row=3, column=1, sticky=tk.NSEW, padx=5, pady=5)
        scroll_sys = ttk.Scrollbar(self.preset_settings_frame, command=self.system_prompt_text.yview)
        scroll_sys.grid(row=3, column=2, sticky=tk.NS, pady=5)
        self.system_prompt_text.config(yscrollcommand=scroll_sys.set)

        ttk.Label(self.preset_settings_frame, text="Context Limit (History):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.context_limit_entry = ttk.Entry(self.preset_settings_frame, width=10)
        self.context_limit_entry.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)

        adv_param_frame = ttk.Frame(self.preset_settings_frame)
        adv_param_frame.grid(row=5, column=0, columnspan=3, sticky=tk.EW, pady=(10,0))

        ttk.Label(adv_param_frame, text="Temp:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.temperature_entry = ttk.Entry(adv_param_frame, width=8)
        self.temperature_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(adv_param_frame, text="Top P:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=2)
        self.top_p_entry = ttk.Entry(adv_param_frame, width=8)
        self.top_p_entry.grid(row=0, column=3, sticky=tk.W, padx=5, pady=2)

        ttk.Label(adv_param_frame, text="Freq Pen:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.frequency_penalty_entry = ttk.Entry(adv_param_frame, width=8)
        self.frequency_penalty_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(adv_param_frame, text="Pres Pen:").grid(row=1, column=2, sticky=tk.W, padx=5, pady=2)
        self.presence_penalty_entry = ttk.Entry(adv_param_frame, width=8)
        self.presence_penalty_entry.grid(row=1, column=3, sticky=tk.W, padx=5, pady=2)

        ttk.Label(adv_param_frame, text="Max Tokens:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.max_tokens_entry = ttk.Entry(adv_param_frame, width=8)
        self.max_tokens_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        self.preset_settings_frame.columnconfigure(1, weight=1)
        self.preset_settings_frame.rowconfigure(3, weight=1)

        self.on_preset_selected()

        action_frame = ttk.Frame(self.settings_frame)
        action_frame.pack(fill=tk.X, pady=10)

        cache_context_frame = ttk.Frame(action_frame)
        cache_context_frame.pack(side=tk.LEFT, padx=0)

        self.clear_current_cache_btn = ttk.Button(cache_context_frame, text="Clear Current Game Cache", command=self.clear_current_translation_cache)
        self.clear_current_cache_btn.pack(side=tk.TOP, padx=5, pady=2, anchor=tk.W)

        self.clear_all_cache_btn = ttk.Button(cache_context_frame, text="Clear All Cache", command=self.clear_all_translation_cache)
        self.clear_all_cache_btn.pack(side=tk.TOP, padx=5, pady=2, anchor=tk.W)

        self.reset_context_btn = ttk.Button(cache_context_frame, text="Reset Translation Context", command=self.reset_translation_context)
        self.reset_context_btn.pack(side=tk.TOP, padx=5, pady=(5,2), anchor=tk.W)

        translate_btn_frame = ttk.Frame(action_frame)
        translate_btn_frame.pack(side=tk.RIGHT, padx=5, pady=5)

        self.translate_btn = ttk.Button(translate_btn_frame, text="Translate", command=self.perform_translation)
        self.translate_btn.pack(side=tk.LEFT, padx=(0, 2))
        self.force_translate_btn = ttk.Button(translate_btn_frame, text="Force Retranslate", command=self.perform_force_translation)
        self.force_translate_btn.pack(side=tk.LEFT, padx=(2, 0))

        auto_frame = ttk.Frame(self.settings_frame)
        auto_frame.pack(fill=tk.X, pady=5)

        self.auto_translate_var = tk.BooleanVar(value=self.auto_translate_enabled)
        self.auto_translate_check = ttk.Checkbutton(
            auto_frame,
            text="Auto-translate when stable text changes",
            variable=self.auto_translate_var,
            command=self.toggle_auto_translate
        )
        self.auto_translate_check.pack(side=tk.LEFT, padx=5)

        output_frame = ttk.LabelFrame(self.frame, text="Translated Text (Preview)", padding="10")
        output_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.translation_display = tk.Text(output_frame, wrap=tk.WORD, height=10, width=40)
        self.translation_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(output_frame, command=self.translation_display.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.translation_display.config(yscrollcommand=scrollbar.set)
        self.translation_display.config(state=tk.DISABLED)

    def load_context_for_game(self, context_text):
        try:
            if not self.additional_context_text.winfo_exists():
                return
            self.additional_context_text.config(state=tk.NORMAL)
            self.additional_context_text.delete("1.0", tk.END)
            if context_text:
                self.additional_context_text.insert("1.0", context_text)
        except tk.TclError:
            print("Error updating context text widget (might be destroyed).")
        except Exception as e:
            print(f"Unexpected error loading context: {e}")

    def save_context_for_current_game(self, event=None):
        if event and event.keysym == 'Return' and not (event.state & 0x0001):
            pass
        elif event and event.keysym == 'Return':
            return "break"

        current_hwnd = self.app.selected_hwnd
        if not current_hwnd:
            return

        game_hash = _get_game_hash(current_hwnd)
        if not game_hash:
            print("Cannot save context: Could not get game hash.")
            return

        try:
            if not self.additional_context_text.winfo_exists():
                return

            new_context = self.additional_context_text.get("1.0", tk.END).strip()

            all_game_contexts = get_setting("game_specific_context", {})
            if all_game_contexts.get(game_hash) != new_context:
                all_game_contexts[game_hash] = new_context
                if update_settings({"game_specific_context": all_game_contexts}):
                    print(f"Game-specific context saved for hash {game_hash[:8]}...")
                    self.app.update_status("Game context saved.")
                else:
                    messagebox.showerror("Error", "Failed to save game-specific context.")
        except tk.TclError:
            print("Error accessing context text widget (might be destroyed).")
        except Exception as e:
            print(f"Error saving game context: {e}")
            messagebox.showerror("Error", f"Failed to save game context: {e}")

        if event and event.keysym == 'Return':
            return "break"

    def save_basic_settings(self, event=None):
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
            else:
                messagebox.showerror("Error", "Failed to save target language setting.")

    def toggle_auto_translate(self):
        self.auto_translate_enabled = self.auto_translate_var.get()
        if set_setting("auto_translate", self.auto_translate_enabled):
            status_msg = f"Auto-translate {'enabled' if self.auto_translate_enabled else 'disabled'}."
            print(status_msg)
            self.app.update_status(status_msg)
            if self.app.floating_controls and self.app.floating_controls.winfo_exists():
                self.app.floating_controls.auto_var.set(self.auto_translate_enabled)
        else:
            messagebox.showerror("Error", "Failed to save auto-translate setting.")

    def is_auto_translate_enabled(self):
        return self.auto_translate_var.get()

    def get_translation_config(self):
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
        except tk.TclError:
            messagebox.showerror("Error", "UI elements missing. Cannot read preset details.", parent=self.app.master)
            return None

        target_lang = self.target_lang_entry.get().strip()
        try:
            additional_ctx = self.additional_context_text.get("1.0", tk.END).strip()
        except tk.TclError:
            additional_ctx = ""

        working_config = preset_config_from_ui
        working_config["target_language"] = target_lang
        working_config["additional_context"] = additional_ctx

        if not working_config.get("api_url"):
            messagebox.showwarning("Warning", "API URL is missing in preset details.", parent=self.app.master)
        if not working_config.get("model"):
            messagebox.showwarning("Warning", "Model name is missing in preset details.", parent=self.app.master)

        return working_config

    def on_preset_selected(self, event=None):
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

            set_setting("last_preset_name", preset_name)
        except tk.TclError:
            print("Error updating preset UI elements (might be destroyed).")

    def get_current_preset_values_for_saving(self):
        try:
            preset_data = {
                "api_key": self.api_key_entry.get().strip(),
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
        preset_name = self.preset_combo.get()
        if not preset_name:
            messagebox.showwarning("Warning", "No preset selected to save over.", parent=self.app.master)
            return

        preset_data = self.get_current_preset_values_for_saving()
        if preset_data is None:
            return

        confirm = messagebox.askyesno("Confirm Save", f"Overwrite preset '{preset_name}' with current settings?", parent=self.app.master)
        if not confirm:
            return

        self.translation_presets[preset_name] = preset_data
        if save_translation_presets(self.translation_presets):
            messagebox.showinfo("Saved", f"Preset '{preset_name}' has been updated.", parent=self.app.master)

    def save_preset_as(self):
        new_name = simpledialog.askstring("Save Preset As", "Enter a name for the new preset:", parent=self.app.master)
        if not new_name:
            return

        new_name = new_name.strip()
        if not new_name:
            messagebox.showwarning("Warning", "Preset name cannot be empty.", parent=self.app.master)
            return

        preset_data = self.get_current_preset_values_for_saving()
        if preset_data is None:
            return

        if new_name in self.translation_presets:
            overwrite = messagebox.askyesno("Overwrite", f"Preset '{new_name}' already exists. Overwrite?", parent=self.app.master)
            if not overwrite:
                return

        self.translation_presets[new_name] = preset_data
        if save_translation_presets(self.translation_presets):
            self.preset_names = sorted(list(self.translation_presets.keys()))
            self.preset_combo['values'] = self.preset_names
            self.preset_combo.set(new_name)
            set_setting("last_preset_name", new_name)
            messagebox.showinfo("Saved", f"Preset '{new_name}' has been saved.", parent=self.app.master)
        else:
            if new_name in self.translation_presets:
                del self.translation_presets[new_name]

    def delete_preset(self):
        preset_name = self.preset_combo.get()
        if not preset_name:
            messagebox.showwarning("Warning", "No preset selected to delete.", parent=self.app.master)
            return

        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete preset '{preset_name}'?", parent=self.app.master)
        if not confirm:
            return

        if preset_name in self.translation_presets:
            original_data = self.translation_presets[preset_name]
            del self.translation_presets[preset_name]
            if save_translation_presets(self.translation_presets):
                self.preset_names = sorted(list(self.translation_presets.keys()))
                self.preset_combo['values'] = self.preset_names
                new_selection = ""
                if self.preset_names:
                    new_selection = self.preset_names[0]
                    self.preset_combo.current(0)
                else:
                    self.preset_combo.set("")
                if get_setting("last_preset_name") == preset_name:
                    set_setting("last_preset_name", new_selection)
                self.on_preset_selected()
                messagebox.showinfo("Deleted", f"Preset '{preset_name}' has been deleted.", parent=self.app.master)
            else:
                self.translation_presets[preset_name] = original_data
                messagebox.showerror("Error", "Failed to save presets after deletion. The preset was not deleted.", parent=self.app.master)

    def _start_translation_thread(self, force_recache=False):
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
            except tk.TclError:
                pass
            if hasattr(self.app, 'overlay_manager'):
                self.app.overlay_manager.clear_all_overlays()
            return

        aggregated_input_text = "\n".join([f"[{name}]: {text}" for name, text in texts_to_translate.items()])
        status_msg = "Translating..." if not force_recache else "Forcing retranslation..."
        self.app.update_status(status_msg)
        try:
            if self.translation_display.winfo_exists():
                self.translation_display.config(state=tk.NORMAL)
                self.translation_display.delete(1.0, tk.END)
                self.translation_display.insert(tk.END, f"{status_msg}\n")
                self.translation_display.config(state=tk.DISABLED)
        except tk.TclError:
            pass

        if hasattr(self.app, 'overlay_manager'):
            for roi_name in texts_to_translate:
                self.app.overlay_manager.update_overlay(roi_name, "...")

        def translation_thread():
            try:
                translated_segments = translate_text(
                    aggregated_input_text=aggregated_input_text,
                    hwnd=current_hwnd,
                    preset=config,
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
                            self.app.master.after_idle(lambda name=first_roi: self.app.overlay_manager.update_overlay(name, "Error!"))
                            for r_name in texts_to_translate:
                                if r_name != first_roi:
                                    self.app.master.after_idle(lambda n=r_name: self.app.overlay_manager.update_overlay(n, ""))
                else:
                    print("Translation successful.")
                    preview_lines = []
                    rois_to_iterate = self.app.rois if hasattr(self.app, 'rois') else []
                    for roi in rois_to_iterate:
                        roi_name = roi.name
                        original_text = self.app.stable_texts.get(roi_name, "")
                        translated_text = translated_segments.get(roi_name)
                        if original_text.strip():
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
                if hasattr(self.app, 'overlay_manager'):
                    self.app.master.after_idle(self.app.overlay_manager.clear_all_overlays)

        threading.Thread(target=translation_thread, daemon=True).start()

    def perform_translation(self):
        self._start_translation_thread(force_recache=False)

    def perform_force_translation(self):
        self._start_translation_thread(force_recache=True)

    def update_translation_results(self, translated_segments, preview_text):
        self.app.update_status("Translation complete.")
        try:
            if self.translation_display.winfo_exists():
                self.translation_display.config(state=tk.NORMAL)
                self.translation_display.delete(1.0, tk.END)
                self.translation_display.insert(tk.END, preview_text if preview_text else "[No translation received]")
                self.translation_display.config(state=tk.DISABLED)
        except tk.TclError:
            pass

        if hasattr(self.app, 'overlay_manager'):
            self.app.overlay_manager.update_overlays(translated_segments)

        self.last_translation_result = translated_segments
        self.last_translation_input = self.app.stable_texts.copy()

    def update_translation_display_error(self, error_message):
        self.app.update_status(f"Translation Error: {error_message[:50]}...")
        try:
            if self.translation_display.winfo_exists():
                self.translation_display.config(state=tk.NORMAL)
                self.translation_display.delete(1.0, tk.END)
                self.translation_display.insert(tk.END, f"Translation Error:\n\n{error_message}")
                self.translation_display.config(state=tk.DISABLED)
        except tk.TclError:
            pass
        self.last_translation_result = None
        self.last_translation_input = None

    def clear_all_translation_cache(self):
        if messagebox.askyesno("Confirm Clear All Cache", "Are you sure you want to delete ALL translation cache files?", parent=self.app.master):
            result = clear_all_cache()
            messagebox.showinfo("Cache Cleared", result, parent=self.app.master)
            self.app.update_status("All translation cache cleared.")

    def clear_current_translation_cache(self):
        current_hwnd = self.app.selected_hwnd
        if not current_hwnd:
            messagebox.showwarning("Warning", "No game window selected. Cannot clear current game cache.", parent=self.app.master)
            return

        if messagebox.askyesno("Confirm Clear Current Cache", "Are you sure you want to delete the translation cache for the currently selected game?", parent=self.app.master):
            result = clear_current_game_cache(current_hwnd)
            messagebox.showinfo("Cache Cleared", result, parent=self.app.master)
            self.app.update_status("Current game translation cache cleared.")

    def reset_translation_context(self):
        current_hwnd = self.app.selected_hwnd
        if messagebox.askyesno("Confirm Reset Context", "Are you sure you want to reset the translation context history for the current game?\n(This will delete the saved history file)", parent=self.app.master):
            result = reset_context(current_hwnd)
            messagebox.showinfo("Context Reset", result, parent=self.app.master)
            self.app.update_status("Translation context reset.")
