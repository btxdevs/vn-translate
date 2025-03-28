import json
import os

SETTINGS_FILE = "vn_translator_settings.json"

DEFAULT_SETTINGS = {
    "last_preset_name": None,
    "target_language": "en",
    "stable_threshold": 3,
    "max_display_width": 800,
    "max_display_height": 600,
    "auto_translate": False,
    "ocr_language": "jpn",
    "global_overlays_enabled": True,
    "overlay_settings": {},
    "floating_controls_pos": None,
    "game_specific_context": {}
}

DEFAULT_SINGLE_OVERLAY_CONFIG = {
    "enabled": True,
    "font_family": "Segoe UI",
    "font_size": 14,
    "font_color": "white",
    "bg_color": "#222222",
    "alpha": 1.0,
    "wraplength": 450,
    "justify": "left",
    "geometry": None
}

def load_settings():
    settings = DEFAULT_SETTINGS.copy()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                loaded_settings = json.load(f)
            for key, default_value in DEFAULT_SETTINGS.items():
                settings[key] = loaded_settings.get(key, default_value)
        except Exception as e:
            print(f"Error loading settings: {e}. Using defaults.")
    return settings

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

def get_setting(key, default=None):
    settings = load_settings()
    fallback_default = DEFAULT_SETTINGS.get(key, default)
    return settings.get(key, fallback_default)

def set_setting(key, value):
    settings = load_settings()
    settings[key] = value
    return save_settings(settings)

def update_settings(new_values):
    settings = load_settings()
    settings.update(new_values)
    return save_settings(settings)

def get_overlay_config_for_roi(roi_name):
    config = DEFAULT_SINGLE_OVERLAY_CONFIG.copy()
    all_overlay_settings = get_setting("overlay_settings", {})
    roi_specific_saved = all_overlay_settings.get(roi_name, {})
    config.update(roi_specific_saved)
    return config

def save_overlay_config_for_roi(roi_name, new_partial_config):
    all_overlay_settings = get_setting("overlay_settings", {})
    if roi_name not in all_overlay_settings:
        all_overlay_settings[roi_name] = {}
    if 'geometry' in new_partial_config:
        all_overlay_settings[roi_name]['geometry'] = new_partial_config['geometry']
    for key, value in new_partial_config.items():
        if key != 'geometry':
            all_overlay_settings[roi_name][key] = value
    return update_settings({"overlay_settings": all_overlay_settings})
