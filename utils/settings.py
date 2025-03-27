# --- START OF FILE utils/settings.py ---

import json
import os

# Default settings file
SETTINGS_FILE = "vn_translator_settings.json"

# Default settings
DEFAULT_SETTINGS = {
    # Removed "last_roi_config" as it's now game-specific/automatic
    "last_preset_name": None,
    "target_language": "en",
    # Removed "additional_context" - now game-specific
    "stable_threshold": 3,
    "max_display_width": 800,
    "max_display_height": 600,
    "auto_translate": False,
    "ocr_language": "jpn",
    "global_overlays_enabled": True,
    "overlay_settings": {}, # roi_name: {config dict}
    "floating_controls_pos": None,
    "game_specific_context": {} # NEW: {game_hash: context_string}
}

# Default values for a single overlay's settings
DEFAULT_SINGLE_OVERLAY_CONFIG = {
    "enabled": True,
    "font_family": "Segoe UI",
    "font_size": 14,
    "font_color": "white",
    "bg_color": "#222222",
    "alpha": 1.0, # Added: Default 1.0 (fully opaque)
    "wraplength": 450,
    "justify": "left",
    "geometry": None
}

# --- load_settings, save_settings, get_setting, set_setting, update_settings remain the same ---

def load_settings():
    """Load application settings."""
    settings = DEFAULT_SETTINGS.copy()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                loaded_settings = json.load(f)
            # Merge carefully in case new defaults were added
            for key, default_value in DEFAULT_SETTINGS.items():
                settings[key] = loaded_settings.get(key, default_value)
        except Exception as e:
            print(f"Error loading settings: {e}. Using defaults.")
    return settings

def save_settings(settings):
    """Save application settings."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        # print(f"Settings saved to {SETTINGS_FILE}") # Less verbose
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

def get_setting(key, default=None):
    """Get a specific setting value."""
    settings = load_settings()
    # Use the key's default from DEFAULT_SETTINGS if available, otherwise use the provided default
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


# --- get_overlay_config_for_roi, save_overlay_config_for_roi remain the same ---

def get_overlay_config_for_roi(roi_name):
    """Gets the specific config for an ROI, merging with defaults."""
    config = DEFAULT_SINGLE_OVERLAY_CONFIG.copy()
    all_overlay_settings = get_setting("overlay_settings", {})
    roi_specific_saved = all_overlay_settings.get(roi_name, {})
    config.update(roi_specific_saved)
    return config

def save_overlay_config_for_roi(roi_name, new_partial_config):
    """Updates and saves the config for a specific overlay ROI."""
    all_overlay_settings = get_setting("overlay_settings", {})
    if roi_name not in all_overlay_settings:
        all_overlay_settings[roi_name] = {}
    # Ensure geometry is saved even if None
    if 'geometry' in new_partial_config:
        all_overlay_settings[roi_name]['geometry'] = new_partial_config['geometry']
    # Update other keys
    for key, value in new_partial_config.items():
        if key != 'geometry': # Avoid overwriting None geometry if not explicitly passed
            all_overlay_settings[roi_name][key] = value

    return update_settings({"overlay_settings": all_overlay_settings})


# --- END OF FILE utils/settings.py ---