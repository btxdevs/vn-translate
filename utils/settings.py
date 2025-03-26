import json
import os

# Default settings file
SETTINGS_FILE = "vn_translator_settings.json"

# Default settings
DEFAULT_SETTINGS = {
    "last_roi_config": "vn_translator_config.json",
    "last_preset": None,
    "stable_threshold": 3,
    "max_display_width": 800,
    "max_display_height": 600
}

def load_settings():
    """Load application settings."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading settings: {e}")
    return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    """Save application settings."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

def get_setting(key, default=None):
    """Get a specific setting value."""
    settings = load_settings()
    return settings.get(key, default)

def set_setting(key, value):
    """Set a specific setting value."""
    settings = load_settings()
    settings[key] = value
    return save_settings(settings)