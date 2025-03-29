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
    "ocr_engine": "paddle",
    "global_overlays_enabled": True,
    "overlay_settings": {},
    "floating_controls_pos": None,
    "game_specific_context": {},
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
    "geometry": None,
}


def load_settings():
    settings = DEFAULT_SETTINGS.copy()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                loaded_settings = json.load(f)
            for key, default_value in DEFAULT_SETTINGS.items():
                settings[key] = loaded_settings.get(key, default_value)
        except Exception:
            pass
    return settings


def save_settings(settings):
    try:
        valid_settings = {k: settings.get(k, DEFAULT_SETTINGS.get(k)) for k in DEFAULT_SETTINGS}
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(valid_settings, f, indent=2)
        return True
    except Exception:
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
    for key, default_value in DEFAULT_SINGLE_OVERLAY_CONFIG.items():
        if key not in config:
            config[key] = default_value
    return config


def save_overlay_config_for_roi(roi_name, new_partial_config):
    all_overlay_settings = get_setting("overlay_settings", {})
    current_config = all_overlay_settings.get(roi_name, {})
    current_config.update(new_partial_config)
    all_overlay_settings[roi_name] = current_config
    if "geometry" in new_partial_config and new_partial_config["geometry"] is None:
        all_overlay_settings[roi_name]["geometry"] = None
    return update_settings({"overlay_settings": all_overlay_settings})