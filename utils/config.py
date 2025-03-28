import json
import os
import tkinter.messagebox as messagebox
from utils.roi import ROI
from utils.settings import set_setting, get_setting
from utils.capture import get_executable_details
import hashlib
from pathlib import Path

PRESETS_FILE = "translation_presets.json"
APP_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROI_CONFIGS_DIR = APP_DIR / "roi_configs"

def _ensure_roi_configs_dir():
    try:
        ROI_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error creating ROI configs directory {ROI_CONFIGS_DIR}: {e}")

def _get_game_hash(hwnd):
    exe_path, file_size = get_executable_details(hwnd)
    if exe_path and file_size is not None:
        try:
            identity_string = f"{os.path.normpath(exe_path).lower()}|{file_size}"
            hasher = hashlib.sha256()
            hasher.update(identity_string.encode('utf-8'))
            return hasher.hexdigest()
        except Exception as e:
            print(f"Error generating game hash: {e}")
    return None

def _get_roi_config_path(hwnd):
    game_hash = _get_game_hash(hwnd)
    if game_hash:
        return ROI_CONFIGS_DIR / f"{game_hash}_rois.json"
    else:
        print("Warning: Could not determine game hash for ROI config path.")
        return None

def save_rois(rois, hwnd):
    if not hwnd:
        messagebox.showerror("Error", "Cannot save ROIs: No game window selected.")
        return None
    if not rois:
        messagebox.showwarning("Warning", "No ROIs defined to save.")
        return None
    _ensure_roi_configs_dir()
    save_path = _get_roi_config_path(hwnd)
    if not save_path:
        messagebox.showerror("Error", "Could not determine game-specific file path to save ROIs.")
        return None
    try:
        roi_data = [roi.to_dict() for roi in rois]
        with open(save_path, 'w', encoding="utf-8") as f:
            json.dump(roi_data, f, indent=2)
        print(f"ROIs saved successfully for current game to {save_path.name}")
        return str(save_path)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save ROIs to {save_path.name}: {str(e)}")
        return None

def load_rois(hwnd):
    if not hwnd:
        print("Cannot load ROIs: No game window handle provided.")
        return [], None
    _ensure_roi_configs_dir()
    load_path = _get_roi_config_path(hwnd)
    rois = []
    if not load_path:
        print("Could not determine game-specific file path to load ROIs.")
        return [], None
    if load_path.exists():
        try:
            with open(load_path, 'r', encoding="utf-8") as f:
                roi_data = json.load(f)
            rois = [ROI.from_dict(data) for data in roi_data]
            print(f"ROIs loaded successfully for current game from {load_path.name}")
            return rois, str(load_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load ROIs from '{load_path.name}': {str(e)}")
            return [], None
    else:
        print(f"No ROI config file found for current game ({load_path.name}).")
        return [], None

def save_translation_presets(presets, file_path=PRESETS_FILE):
    try:
        preset_path_obj = Path(file_path)
        preset_path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(preset_path_obj, "w", encoding="utf-8") as f:
            json.dump(presets, f, indent=2)
        print(f"Translation presets saved to {file_path}")
        return True
    except Exception as e:
        print(f"Error saving translation presets: {e}")
        messagebox.showerror("Error", f"Failed to save translation presets: {e}")
        return False

def load_translation_presets(file_path=PRESETS_FILE):
    preset_path_obj = Path(file_path)
    if preset_path_obj.exists():
        try:
            with open(preset_path_obj, "r", encoding="utf-8") as f:
                content = f.read()
                if not content:
                    return {}
                return json.loads(content)
        except json.JSONDecodeError:
            print(f"Error: Translation presets file '{file_path}' is corrupted or empty.")
            messagebox.showerror("Preset Load Error", f"Could not load presets from '{file_path}'. File might be corrupted.")
            return {}
        except Exception as e:
            print(f"Error loading translation presets: {e}")
            messagebox.showerror("Error", f"Failed to load translation presets: {e}.")
    return {}
