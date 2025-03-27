# --- START OF FILE utils/settings.py ---

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
    "ocr_language": "jpn",
    "global_overlays_enabled": True,
    "overlay_settings": {}, # roi_name: {enabled: bool, font_size: int, ..., geometry: "WxH+X+Y" or None}
    "floating_controls_pos": None # "x,y"
}

# Default values for a single overlay's settings within overlay_settings[roi_name]
# This structure will be merged with saved settings for each ROI.
DEFAULT_SINGLE_OVERLAY_CONFIG = {
    "enabled": True,
    "font_family": "Segoe UI",
    "font_size": 14,
    "font_color": "white",
    "bg_color": "#222222",
    # "alpha": 0.85, # No longer used directly by the window for transparency
    # "position": "bottom_roi", # No longer used, user controls position/size
    "wraplength": 450,
    "justify": "left",
    "geometry": None # Holds "WxH+X+Y", default is None (auto-size/center)
}


def load_settings():
    """Load application settings."""
    settings = DEFAULT_SETTINGS.copy()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                loaded_settings = json.load(f)
            # Deep merge for overlay_settings? No, just update the top level.
            # The manager will handle merging defaults for individual ROIs.
            settings.update(loaded_settings)
        except Exception as e:
            print(f"Error loading settings: {e}. Using defaults.")
    return settings

def save_settings(settings):
    """Save application settings."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        print(f"Settings saved to {SETTINGS_FILE}")
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

# Function to get merged config for a single ROI, combining defaults and saved specifics
def get_overlay_config_for_roi(roi_name):
    """Gets the specific config for an ROI, merging with defaults."""
    config = DEFAULT_SINGLE_OVERLAY_CONFIG.copy()
    all_overlay_settings = get_setting("overlay_settings", {})
    roi_specific_saved = all_overlay_settings.get(roi_name, {})
    config.update(roi_specific_saved)
    return config

# Function to save the config for a single ROI
def save_overlay_config_for_roi(roi_name, new_partial_config):
    """Updates and saves the config for a specific overlay ROI."""
    all_overlay_settings = get_setting("overlay_settings", {})
    if roi_name not in all_overlay_settings:
        all_overlay_settings[roi_name] = {}
    all_overlay_settings[roi_name].update(new_partial_config)
    return update_settings({"overlay_settings": all_overlay_settings})

# --- END OF FILE utils/settings.py ---