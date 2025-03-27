import json
import os

# Default settings file
SETTINGS_FILE = "vn_translator_settings.json"

# Default settings
DEFAULT_SETTINGS = {
    "last_roi_config": "vn_translator_config.json",
    "last_preset_name": None, # Store the name of the last used preset
    "target_language": "en",
    "additional_context": "",
    "stable_threshold": 3,
    "max_display_width": 800,
    "max_display_height": 600,
    "auto_translate": False,
    "ocr_language": "jpn", # Added OCR language setting
    "global_overlays_enabled": True, # Added global overlay toggle
    "overlay_settings": {}, # roi_name: {enabled: bool, font_size: int, ...}
    "floating_controls_pos": None # "x,y"
}

def load_settings():
    """Load application settings."""
    settings = DEFAULT_SETTINGS.copy()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                loaded_settings = json.load(f)
            settings.update(loaded_settings) # Merge loaded settings over defaults
        except Exception as e:
            print(f"Error loading settings: {e}. Using defaults.")
    return settings

def save_settings(settings):
    """Save application settings."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        print(f"Settings saved to {SETTINGS_FILE}") # Add confirmation
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

def get_setting(key, default=None):
    """Get a specific setting value."""
    settings = load_settings()
    # Use default from DEFAULT_SETTINGS if key exists there, otherwise use passed default
    fallback_default = DEFAULT_SETTINGS.get(key, default)
    return settings.get(key, fallback_default)

def set_setting(key, value):
    """Set a specific setting value and save immediately."""
    settings = load_settings()
    settings[key] = value
    return save_settings(settings)

def update_settings(new_values):
    """Update multiple settings values and save."""
    settings = load_settings()
    settings.update(new_values)
    return save_settings(settings)